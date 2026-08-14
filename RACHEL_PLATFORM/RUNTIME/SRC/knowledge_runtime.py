from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[3]
PLATFORM = ROOT / "RACHEL_PLATFORM"
STATE = PLATFORM / "STATE"


class BranMemory:
    def __init__(self, path: Path | None = None) -> None:
        STATE.mkdir(parents=True, exist_ok=True)
        self.path = path or STATE / "bran-memory.db"
        connection = sqlite3.connect(self.path)
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    source TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at_ms INTEGER NOT NULL
                )
                """
            )
            connection.commit()
        finally:
            connection.close()

    def remember(
        self,
        content: str,
        source: str = "user",
        kind: str = "note",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = content.strip()
        if not normalized:
            raise ValueError("Memory content cannot be empty")
        memory_id = hashlib.sha256(f"{source}\0{kind}\0{normalized}".encode("utf-8")).hexdigest()
        record = {
            "id": memory_id,
            "content": normalized,
            "source": source,
            "kind": kind,
            "metadata": metadata or {},
            "created_at_ms": int(time.time() * 1000),
        }
        connection = sqlite3.connect(self.path)
        try:
            connection.execute(
                "INSERT OR REPLACE INTO memories VALUES (?, ?, ?, ?, ?, ?)",
                (
                    record["id"], record["content"], record["source"],
                    record["kind"], json.dumps(record["metadata"], ensure_ascii=False),
                    record["created_at_ms"],
                ),
            )
            connection.commit()
        finally:
            connection.close()
        return record

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        terms = [term.casefold() for term in query.split() if term.strip()]
        connection = sqlite3.connect(self.path)
        try:
            rows = connection.execute(
                "SELECT id, content, source, kind, metadata, created_at_ms "
                "FROM memories ORDER BY created_at_ms DESC"
            ).fetchall()
        finally:
            connection.close()
        scored = []
        for row in rows:
            text = row[1].casefold()
            score = sum(text.count(term) for term in terms) if terms else 1
            if score > 0:
                scored.append(
                    {
                        "id": row[0], "content": row[1], "source": row[2],
                        "kind": row[3], "metadata": json.loads(row[4]),
                        "created_at_ms": row[5], "score": score,
                    }
                )
        scored.sort(key=lambda item: (item["score"], item["created_at_ms"]), reverse=True)
        return scored[: max(1, min(limit, 100))]

    def count(self) -> int:
        connection = sqlite3.connect(self.path)
        try:
            return int(connection.execute("SELECT COUNT(*) FROM memories").fetchone()[0])
        finally:
            connection.close()


class VisaoIngestor:
    TEXT_SUFFIXES = {".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".sql", ".ps1", ".toml", ".yaml", ".yml", ".xml"}

    def __init__(self, memory: BranMemory) -> None:
        self.memory = memory

    def extract(self, path: Path) -> tuple[str, dict[str, Any]]:
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(path)
        suffix = path.suffix.casefold()
        metadata = {"path": str(path.resolve()), "suffix": suffix, "size": path.stat().st_size}
        if suffix in self.TEXT_SUFFIXES:
            return path.read_text(encoding="utf-8-sig", errors="replace"), metadata
        if suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            return json.dumps(payload, ensure_ascii=False, indent=2), metadata
        if suffix == ".csv":
            with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as stream:
                rows = list(csv.reader(stream))
            return "\n".join(" | ".join(row) for row in rows), metadata
        if suffix == ".pdf" and importlib.util.find_spec("docling"):
            from docling.document_converter import DocumentConverter
            result = DocumentConverter().convert(str(path))
            return result.document.export_to_markdown(), {**metadata, "engine": "docling"}
        if suffix == ".pdf":
            raise RuntimeError("PDF requires the Docling adapter environment")
        raise ValueError(f"Unsupported file type: {suffix}")

    def ingest(self, path: Path) -> dict[str, Any]:
        content, metadata = self.extract(path)
        record = self.memory.remember(content, source=str(path.resolve()), kind="document", metadata=metadata)
        return {"memory_id": record["id"], "characters": len(content), "metadata": metadata}


def status() -> dict[str, Any]:
    return {
        "bran": {"available": True, "memories": BranMemory().count()},
        "visao": {
            "available": True,
            "text_ingestion": True,
            "json_ingestion": True,
            "csv_ingestion": True,
            "docling_installed": importlib.util.find_spec("docling") is not None,
            "qdrant_client_installed": importlib.util.find_spec("qdrant_client") is not None,
            "presidio_installed": importlib.util.find_spec("presidio_analyzer") is not None,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="rachel-knowledge")
    sub = parser.add_subparsers(dest="domain", required=True)
    memory = sub.add_parser("memory")
    memory_sub = memory.add_subparsers(dest="action", required=True)
    remember = memory_sub.add_parser("remember")
    remember.add_argument("content")
    remember.add_argument("--source", default="user")
    search = memory_sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=10)
    memory_sub.add_parser("status")
    vision = sub.add_parser("vision")
    vision_sub = vision.add_subparsers(dest="action", required=True)
    ingest = vision_sub.add_parser("ingest")
    ingest.add_argument("path")
    vision_sub.add_parser("status")
    args = parser.parse_args()
    bran = BranMemory()
    if args.domain == "memory" and args.action == "remember":
        print(json.dumps(bran.remember(args.content, args.source), ensure_ascii=False, indent=2))
        return 0
    if args.domain == "memory" and args.action == "search":
        print(json.dumps(bran.search(args.query, args.limit), ensure_ascii=False, indent=2))
        return 0
    if args.domain == "memory" and args.action == "status":
        print(json.dumps(status()["bran"], ensure_ascii=False, indent=2))
        return 0
    if args.domain == "vision" and args.action == "ingest":
        try:
            result = VisaoIngestor(bran).ingest(Path(args.path))
        except (OSError, ValueError, RuntimeError) as error:
            print(str(error), file=sys.stderr)
            return 2
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.domain == "vision" and args.action == "status":
        print(json.dumps(status()["visao"], ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
