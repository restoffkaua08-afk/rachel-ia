import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_CORE" / "src"))
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))
from cognitive_runtime import DanyEvaluator, NedCognitiveBridge, NedToolPlanner, should_propose_memory
from dany_professional import DanyProfessional


class CognitiveTests(unittest.TestCase):
    def test_dany_accepts_valid_content(self):
        report = DanyEvaluator().evaluate("Resposta valida e objetiva.")
        self.assertTrue(report.accepted)
        self.assertEqual(report.score, 100)

    def test_dany_rejects_empty_content(self):
        self.assertFalse(DanyEvaluator().evaluate("   ").accepted)

    def test_cognitive_runtime_uses_professional_dany_alias(self):
        self.assertIs(DanyEvaluator, DanyProfessional)

    def test_ned_uses_core_pipeline(self):
        bridge = NedCognitiveBridge()
        result = bridge.chat("Teste cognitivo")
        self.assertEqual(result["state"], "completed")
        self.assertTrue(result["quality"]["accepted"])
        self.assertEqual(result["quality"]["validator"], "dany-professional")
        self.assertIn(result["quality_scope"], {"structural", "structural-and-evidence-consistency", "grounded"})

    def test_status_reports_tools(self):
        status = NedCognitiveBridge().status()
        self.assertTrue(status["capabilities"]["tools"])
        self.assertGreaterEqual(status["tool_count"], 11)
        self.assertEqual(status["quality_member"], "dany")
        self.assertEqual(status["quality_scope"], "professional-contextual")

    def test_health_request_routes_to_tyrion(self):
        plan = NedToolPlanner.heuristic_plan("Verifique a saúde dos órgãos")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.tool, "tyrion.health")

    def test_preference_becomes_memory_proposal(self):
        self.assertTrue(
            should_propose_memory(
                "Eu prefiro relatórios técnicos objetivos e organizados."
            )
        )

    def test_common_question_does_not_become_memory(self):
        self.assertFalse(
            should_propose_memory(
                "Qual é o status atual dos órgãos?"
            )
        )

    def test_research_request_routes_to_web(self):
        plan = NedToolPlanner.heuristic_plan(
            "Pesquise documentação oficial do Python"
        )
        self.assertIsNotNone(plan)
        self.assertEqual(plan.tool, "web.research")
        self.assertIn("Python", plan.arguments["query"])

    def test_document_request_routes_to_visao(self):
        plan = NedToolPlanner.heuristic_plan(
            r"Analise o arquivo C:\Projetos\relatorio.pdf"
        )
        self.assertIsNotNone(plan)
        self.assertEqual(plan.tool, "visao.ingest")
        self.assertTrue(
            plan.arguments["path"].endswith("relatorio.pdf")
        )

    def test_memory_write_routes_to_bran(self):
        plan = NedToolPlanner.heuristic_plan("Lembre que eu prefiro relatórios técnicos")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.tool, "bran.remember")


if __name__ == "__main__":
    unittest.main()
