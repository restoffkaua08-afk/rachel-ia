import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))

from dany_runtime import build_eval_context, evaluate_runtime_response, quality_payload


class DanyRuntimeTests(unittest.TestCase):
    def test_research_context_extracts_citations_and_primary_sources(self):
        result = {
            "state": "completed",
            "sources": [
                {"url": "https://docs.python.org/3/", "authority": "primary"},
                {"url": "https://example.org/article", "authority": "secondary"},
            ],
        }
        context = build_eval_context(
            "Pesquise Python",
            tool_name="web.research",
            tool_result=result,
        )
        self.assertTrue(context.research)
        self.assertEqual(context.primary_source_count, 1)
        self.assertEqual(
            context.citations,
            ("https://docs.python.org/3/", "https://example.org/article"),
        )

    def test_research_without_primary_source_requires_low_confidence(self):
        result = {
            "state": "completed",
            "sources": [
                {"url": "https://example.org/article", "authority": "secondary"}
            ],
        }
        report = evaluate_runtime_response(
            "A evidência é limitada e a confiança é baixa; não encontrei fonte primária. https://example.org/article",
            "Pesquise mudanças recentes",
            tool_name="web.research",
            tool_result=result,
            factuality_verified=False,
        )
        self.assertTrue(report.checks["citations_present"])
        self.assertTrue(report.checks["admits_uncertainty"])

    def test_failed_nested_command_is_not_accepted_as_success(self):
        result = {
            "state": "completed",
            "result": {
                "command": "pytest",
                "returncode": 1,
                "stderr": "1 failed",
            },
        }
        report = evaluate_runtime_response(
            "Os testes foram executados com sucesso.",
            "Rode os testes",
            tool_name="arya.command.execute",
            tool_result=result,
        )
        self.assertFalse(report.accepted)
        self.assertFalse(report.checks["tool_result_consistent"])

    def test_code_checks_are_discovered_from_result(self):
        result = {
            "state": "completed",
            "validation": {
                "pytest": "passed",
                "lint": "passed",
                "build": "passed",
            },
        }
        context = build_eval_context(
            "Valide o projeto",
            tool_name="arya.project.generate",
            tool_result=result,
        )
        self.assertTrue(context.code_validation_required)
        self.assertIn("pytest", context.code_checks_run)
        self.assertIn("lint", context.code_checks_run)
        self.assertIn("build", context.code_checks_run)

    def test_quality_payload_identifies_professional_validator(self):
        report = evaluate_runtime_response(
            "Resposta objetiva.",
            "Responda de forma objetiva",
        )
        payload = quality_payload(report)
        self.assertEqual(payload["validator"], "dany-professional")
        self.assertIn("scope", payload)


if __name__ == "__main__":
    unittest.main()
