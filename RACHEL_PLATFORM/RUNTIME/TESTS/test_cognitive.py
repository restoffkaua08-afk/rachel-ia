import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))
from cognitive_runtime import DanyEvaluator, NedCognitiveBridge, NedToolPlanner


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

    def test_status_reports_tools(self):
        status = NedCognitiveBridge().status()
        self.assertTrue(status["capabilities"]["tools"])
        self.assertGreaterEqual(status["tool_count"], 11)

    def test_health_request_routes_to_tyrion(self):
        plan = NedToolPlanner.heuristic_plan("Verifique a saúde dos órgãos")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.tool, "tyrion.health")

    def test_memory_write_routes_to_bran(self):
        plan = NedToolPlanner.heuristic_plan("Lembre que eu prefiro relatórios técnicos")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.tool, "bran.remember")


if __name__ == "__main__":
    unittest.main()
