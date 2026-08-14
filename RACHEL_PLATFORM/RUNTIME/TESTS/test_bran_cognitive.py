import tempfile
import unittest
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))
from bran_cognitive import CognitiveMemory

class BranCognitiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.memory = CognitiveMemory(Path(self.temp.name) / "memory.db")
    def tearDown(self): self.temp.cleanup()
    def test_memory_requires_approval(self):
        result = self.memory.remember("Prefiro respostas técnicas")
        self.assertEqual(result["state"], "approval_required")
    def test_approved_memory_is_searchable(self):
        stored = self.memory.remember("Prefiro relatórios técnicos completos", approved=True)
        self.assertEqual(stored["state"], "stored")
        self.assertEqual(len(self.memory.search("relatórios técnicos")), 1)
    def test_secret_is_denied_even_with_approval(self):
        result = self.memory.remember("api_key=sk-abcdefghijklmnopqrstuvwxyz123456", approved=True)
        self.assertEqual(result["state"], "denied")
    def test_duplicate_updates_one_record(self):
        self.memory.remember("Meu projeto usa HTML", approved=True)
        result = self.memory.remember("Meu projeto usa HTML", approved=True)
        self.assertTrue(result["duplicate_updated"])
        self.assertEqual(self.memory.status()["total"], 1)

if __name__ == "__main__": unittest.main()
