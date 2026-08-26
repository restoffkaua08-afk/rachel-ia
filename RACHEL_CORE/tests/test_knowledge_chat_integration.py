from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from rachel_core.adapters.audit_jsonl import JsonlAuditAdapter
from rachel_core.adapters.knowledge_sqlite import SQLiteKnowledgeAdapter
from rachel_core.adapters.memory_sqlite import SQLiteMemoryAdapter
from rachel_core.application import ChatService
from rachel_core.domain.models import ChatRequest, ModelResponse


class RecordingModel:
    provider_name = "recording"
    model_name = "recording-v1"

    def __init__(self) -> None:
        self.last_system_prompt: str | None = None

    def health(self):
        return {"available": True, "reachable": True}

    def generate(self, messages, system_prompt):
        self.last_system_prompt = system_prompt
        return ModelResponse(
            content="Resposta baseada no contexto recuperado.",
            provider=self.provider_name,
            model=self.model_name,
        )

    def generate_stream(self, messages, system_prompt):
        self.last_system_prompt = system_prompt
        yield "Resposta baseada no contexto recuperado."


class KnowledgeChatIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.knowledge_db = root / "bran-cognitive.db"
        connection = sqlite3.connect(self.knowledge_db)
        connection.execute(
            """
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
        )
        connection.execute(
            """
            INSERT INTO cognitive_memories
            (id, content, normalized_hash, category, source, confidence,
             importance, consent, status, metadata, created_at_ms,
             updated_at_ms, last_accessed_ms, access_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 0)
            """,
            (
                "doc-oauth-1",
                "OAuth usa authorization code para delegar acesso sem compartilhar a senha.",
                "hash-oauth",
                "note",
                "docs/oauth.md",
                1.0,
                3,
                "explicit",
                "active",
                json.dumps({"kind": "document_chunk", "chunk_index": 0}),
                100,
                100,
            ),
        )
        connection.commit()
        connection.close()

        self.model = RecordingModel()
        self.service = ChatService(
            model=self.model,
            memory=SQLiteMemoryAdapter(root / "rachel.db"),
            audit=JsonlAuditAdapter(root / "audit.jsonl"),
            knowledge=SQLiteKnowledgeAdapter(self.knowledge_db),
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_indexed_document_is_injected_as_chat_evidence(self):
        result = self.service.chat(ChatRequest(content="Explique OAuth authorization code"))
        self.assertEqual(result.state.value, "completed")
        self.assertIsNotNone(self.model.last_system_prompt)
        prompt = self.model.last_system_prompt or ""
        self.assertIn("Evidências recuperadas", prompt)
        self.assertIn("OAuth usa authorization code", prompt)
        self.assertIn("docs/oauth.md", prompt)

    def test_unrelated_query_does_not_inject_document(self):
        self.service.chat(ChatRequest(content="Explique árvores binárias"))
        prompt = self.model.last_system_prompt or ""
        self.assertNotIn("OAuth usa authorization code", prompt)


if __name__ == "__main__":
    unittest.main()
