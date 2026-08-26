from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any


class SQLiteKnowledgeAdapter:
    """Read-only KnowledgePort over Bran's governed document chunks.

    Visao already stores approved document chunks in the `cognitive_memories`
    table with metadata.kind=`document_chunk`. This adapter exposes only those
    chunks to the Core knowledge port, keeping personal memories out of RAG.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path).expanduser().resolve()

    def _table_available(self, connection: sqlite3.Connection) -> bool:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cognitive_memories'"
        ).fetchone()
        return row is not None

    def status(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "available": True,
                "backend": "sqlite",
                "database_exists": False,
                "document_chunks": 0,
                "path": str(self.path),
            }

        try:
            connection = sqlite3.connect(self.path)
            try:
                if not self._table_available(connection):
                    return {
                        "available": True,
                        "backend": "sqlite",
                        "database_exists": True,
                        "document_chunks": 0,
                        "path": str(self.path),
                    }
                rows = connection.execute(
                    "SELECT metadata FROM cognitive_memories WHERE status = 'active'"
                ).fetchall()
            finally:
                connection.close()
        except sqlite3.Error as error:
            return {
                "available": False,
                "backend": "sqlite",
                "database_exists": True,
                "document_chunks": 0,
                "path": str(self.path),
                "error_type": type(error).__name__,
            }

        chunks = 0
        for (raw_metadata,) in rows:
            try:
                metadata = json.loads(raw_metadata or "{}")
            except (TypeError, json.JSONDecodeError):
                continue
            if metadata.get("kind") == "document_chunk":
                chunks += 1

        return {
            "available": True,
            "backend": "sqlite",
            "database_exists": True,
            "document_chunks": chunks,
            "path": str(self.path),
        }

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        normalized = " ".join(str(query).strip().split())
        if not normalized or not self.path.exists():
            return []

        selected_limit = max(1, min(int(limit), 50))
        terms = {
            term
            for term in re.findall(r"[\wÀ-ÿ]+", normalized.casefold())
            if len(term) >= 2
        }
        if not terms:
            return []

        try:
            connection = sqlite3.connect(self.path)
            try:
                if not self._table_available(connection):
                    return []
                rows = connection.execute(
                    """
                    SELECT id, content, category, source, confidence, importance,
                           metadata, updated_at_ms
                    FROM cognitive_memories
                    WHERE status = 'active'
                    """
                ).fetchall()
            finally:
                connection.close()
        except sqlite3.Error:
            return []

        matches: list[dict[str, Any]] = []
        for row in rows:
            try:
                metadata = json.loads(row[6] or "{}")
            except (TypeError, json.JSONDecodeError):
                continue
            if metadata.get("kind") != "document_chunk":
                continue

            content = str(row[1])
            source = str(row[3])
            metadata_text = json.dumps(metadata, ensure_ascii=False)
            haystack = f"{content}\n{source}\n{metadata_text}".casefold()
            lexical_matches = sum(1 for term in terms if term in haystack)
            if lexical_matches <= 0:
                continue

            confidence = float(row[4])
            importance = int(row[5])
            score = round(
                lexical_matches
                + confidence * 0.25
                + importance * 0.10,
                3,
            )
            matches.append(
                {
                    "id": str(row[0]),
                    "content": content,
                    "source": source,
                    "category": str(row[2]),
                    "metadata": metadata,
                    "relevance": score,
                    "updated_at_ms": int(row[7]),
                }
            )

        matches.sort(
            key=lambda item: (item["relevance"], item["updated_at_ms"]),
            reverse=True,
        )
        return matches[:selected_limit]
