from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from rachel_core.adapters.knowledge_sqlite import SQLiteKnowledgeAdapter


SCHEMA = """
CREATE TABLE cognitive_memories (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    normalized_hash TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    source TEXT NOT NULL,
    confidence REAL NOT NULL,
    importance INTEGER NOT NULL,
    consent TEXT NOT NULL,
    status TEXT NOT NULL,
    metadata TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL,
    updated_at_ms INTEGER NOT NULL,
    last_accessed_ms INTEGER,
    access_count INTEGER NOT NULL DEFAULT 0
)
"""


class SQLiteKnowledgeAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "bran-cognitive.db"
        connection = sqlite3.connect(self.path)
        connection.execute(SCHEMA)
        rows = [
            (
                "doc-1",
                "OAuth 2.0 usa authorization code para delegacao segura.",
                "note",
                "docs/oauth.md",
                1.0,
                3,
                json.dumps({"kind": "document_chunk", "chunk_index": 0}),
                100,
            ),
            (
                "doc-2",
                "Refresh tokens podem renovar sessoes sem pedir credenciais novamente.",
                "note",
                "docs/oauth.md",
                1.0,
                3,
                json.dumps({"kind": "document_chunk", "chunk_index": 1}),
                200,
            ),
            (
                "personal-1",
                "Eu prefiro respostas curtas sobre OAuth.",
                "preference",
                "conversation",
                1.0,
                5,
                json.dumps({"kind": "preference"}),
                300,
            ),
        ]
        for item in rows:
            connection.execute(
                """
                INSERT INTO cognitive_memories
                (id, content, normalized_hash, category, source, confidence,
                 importance, consent, status, metadata, created_at_ms,
                 updated_at_ms, last_accessed_ms, access_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'explicit', 'active', ?, ?, ?, NULL, 0)
                """,
                (
                    item[0], item[1], f"hash-{item[0]}", item[2], item[3],
                    item[4], item[5], item[6], item[7], item[7],
                ),
            )
        connection.commit()
        connection.close()
        self.adapter = SQLiteKnowledgeAdapter(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_search_returns_only_document_chunks(self):
        results = self.adapter.search("OAuth", limit=5)
        ids = {item["id"] for item in results}
        self.assertIn("doc-1", ids)
        self.assertNotIn("personal-1", ids)
        self.assertTrue(all(item["metadata"]["kind"] == "document_chunk" for item in results))

    def test_search_ranks_relevant_document(self):
        results = self.adapter.search("refresh tokens", limit=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "doc-2")
        self.assertIn("credenciais", results[0]["content"])

    def test_status_counts_only_document_chunks(self):
        status = self.adapter.status()
        self.assertTrue(status["available"])
        self.assertTrue(status["database_exists"])
        self.assertEqual(status["document_chunks"], 2)

    def test_missing_database_is_safe_and_ready(self):
        missing = SQLiteKnowledgeAdapter(Path(self.temp.name) / "missing.db")
        self.assertEqual(missing.search("OAuth"), [])
        status = missing.status()
        self.assertTrue(status["available"])
        self.assertFalse(status["database_exists"])


if __name__ == "__main__":
    unittest.main()
