from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_CORE" / "src"))
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))

from rachel_core.adapters.knowledge_sqlite import SQLiteKnowledgeAdapter
from bran_cognitive import CognitiveMemory
from document_runtime import DocumentChunk, DocumentResult
from knowledge_runtime import VisaoIngestor


class FakeExtractor:
    def __init__(self, content: str) -> None:
        self.content = content

    def extract(self, path: Path) -> DocumentResult:
        encoded = self.content.encode("utf-8")
        chunk = DocumentChunk(
            index=0,
            content=self.content,
            start_character=0,
            end_character=len(self.content),
            character_count=len(self.content),
            sha256=hashlib.sha256(encoded).hexdigest(),
        )
        return DocumentResult(
            content=self.content,
            chunks=(chunk,),
            metadata={
                "path": str(path.resolve()),
                "name": path.name,
                "extension": path.suffix,
                "sha256": hashlib.sha256(encoded).hexdigest(),
            },
        )


class KnowledgePortIntegrationTests(unittest.TestCase):
    def test_visao_ingestion_becomes_searchable_core_knowledge(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "oauth-notes.txt"
            source.write_text("fixture", encoding="utf-8")
            database = root / "bran-cognitive.db"
            content = (
                "PKCE protege o authorization code contra interceptacao em "
                "clientes publicos OAuth."
            )

            memory = CognitiveMemory(path=database)
            ingestor = VisaoIngestor(
                memory,
                extractor=FakeExtractor(content),
            )
            result = ingestor.ingest(source)

            self.assertEqual(result["state"], "stored")
            self.assertEqual(result["chunks_stored"], 1)

            knowledge = SQLiteKnowledgeAdapter(database)
            matches = knowledge.search("PKCE authorization code", limit=5)

            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0]["metadata"]["kind"], "document_chunk")
            self.assertIn("PKCE", matches[0]["content"])
            self.assertEqual(matches[0]["source"], str(source.resolve()))

    def test_personal_memory_does_not_enter_knowledge_port(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "bran-cognitive.db"
            memory = CognitiveMemory(path=database)
            stored = memory.remember(
                "Eu prefiro PKCE em clientes publicos.",
                approved=True,
                source="conversation",
                category="preference",
            )
            self.assertEqual(stored["state"], "stored")

            knowledge = SQLiteKnowledgeAdapter(database)
            self.assertEqual(knowledge.search("PKCE clientes publicos"), [])


if __name__ == "__main__":
    unittest.main()
