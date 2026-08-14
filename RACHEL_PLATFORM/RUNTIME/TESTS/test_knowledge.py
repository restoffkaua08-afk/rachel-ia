import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))
from knowledge_runtime import BranMemory, VisaoIngestor


class KnowledgeTests(unittest.TestCase):
    def test_bran_remembers_and_searches(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = BranMemory(Path(directory) / "memory.db")
            memory.remember("Rachel possui memoria persistente")
            results = memory.search("persistente")
            self.assertEqual(len(results), 1)

    def test_bran_deduplicates_same_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = BranMemory(Path(directory) / "memory.db")
            first = memory.remember("mesmo conteudo")
            second = memory.remember("mesmo conteudo")
            self.assertEqual(first["id"], second["id"])
            self.assertEqual(memory.count(), 1)

    def test_visao_ingests_text(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "document.md"
            source.write_text("Conhecimento para Bran", encoding="utf-8")
            memory = BranMemory(base / "memory.db")
            result = VisaoIngestor(memory).ingest(source)
            self.assertGreater(result["characters"], 0)
            self.assertEqual(len(memory.search("Conhecimento")), 1)


if __name__ == "__main__":
    unittest.main()
