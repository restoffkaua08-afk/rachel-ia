import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))
from cognitive_runtime import DanyEvaluator, NedCognitiveBridge


class CognitiveTests(unittest.TestCase):
    def test_dany_accepts_valid_content(self):
        report = DanyEvaluator().evaluate("Resposta valida e objetiva.")
        self.assertTrue(report.accepted)
        self.assertEqual(report.score, 100)

    def test_dany_rejects_empty_content(self):
        self.assertFalse(DanyEvaluator().evaluate("   ").accepted)

    def test_ned_uses_core_pipeline(self):
        bridge = NedCognitiveBridge()
        result = bridge.chat("Teste cognitivo")
        self.assertEqual(result["state"], "completed")
        self.assertTrue(result["quality"]["accepted"])


if __name__ == "__main__":
    unittest.main()
