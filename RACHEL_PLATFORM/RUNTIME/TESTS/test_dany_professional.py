import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))

from dany_professional import DanyProfessional, EvalContext


class DanyProfessionalTests(unittest.TestCase):
    def setUp(self):
        self.dany = DanyProfessional()

    def test_empty_response_is_rejected(self):
        report = self.dany.evaluate("   ", EvalContext(request="Explique o resultado"))
        self.assertFalse(report.accepted)
        self.assertIn("NOT_EMPTY", report.issues)

    def test_score_is_not_automatically_one_hundred(self):
        report = self.dany.evaluate(
            "Resposta genérica.",
            EvalContext(request="Explique autenticação OAuth em detalhes"),
        )
        self.assertLess(report.score, 100)
        self.assertIn("REQUEST_FULFILLED", report.issues)

    def test_failed_tool_cannot_be_described_as_success(self):
        context = EvalContext(
            request="Rode os testes",
            tool_result={
                "state": "completed",
                "result": {
                    "returncode": 1,
                    "successful": False,
                    "stderr": "2 tests failed",
                },
            },
            evidence={"returncode": 1, "stderr": "2 tests failed"},
        )
        report = self.dany.evaluate(
            "Os testes foram executados com sucesso.",
            context,
        )
        self.assertFalse(report.accepted)
        self.assertFalse(report.checks["tool_result_consistent"])

    def test_failed_tool_is_accepted_when_failure_is_stated(self):
        context = EvalContext(
            request="Rode os testes",
            tool_result={
                "state": "completed",
                "result": {"returncode": 1, "successful": False},
            },
            evidence={"returncode": 1, "successful": False},
        )
        report = self.dany.evaluate(
            "A execução falhou; o returncode foi 1 e o resultado não foi verificado como sucesso.",
            context,
        )
        self.assertTrue(report.checks["tool_result_consistent"])

    def test_research_without_primary_source_requires_low_confidence(self):
        context = EvalContext(
            request="Pesquise mudanças recentes",
            research=True,
            primary_source_count=0,
            citations=(),
            evidence={"sources": [{"authority": "secondary"}]},
            factuality_verified=False,
        )
        bad = self.dany.evaluate(
            "As mudanças estão confirmadas.",
            context,
        )
        self.assertFalse(bad.accepted)
        self.assertFalse(bad.checks["citations_present"])
        self.assertFalse(bad.checks["admits_uncertainty"])

        good = self.dany.evaluate(
            "A evidência é limitada e a confiança é baixa; não encontrei fonte primária para confirmar a afirmação.",
            context,
        )
        self.assertTrue(good.checks["citations_present"])
        self.assertTrue(good.checks["admits_uncertainty"])

    def test_research_with_sources_requires_returned_citation(self):
        context = EvalContext(
            request="Pesquise Python",
            research=True,
            primary_source_count=1,
            citations=("https://docs.python.org/3/",),
            evidence={
                "sources": [
                    {
                        "url": "https://docs.python.org/3/",
                        "authority": "primary",
                    }
                ]
            },
        )
        without = self.dany.evaluate("Python possui documentação oficial.", context)
        self.assertFalse(without.accepted)
        self.assertFalse(without.checks["citations_present"])

        with_citation = self.dany.evaluate(
            "A documentação oficial está em https://docs.python.org/3/.",
            context,
        )
        self.assertTrue(with_citation.checks["citations_present"])

    def test_research_conflicts_must_be_disclosed(self):
        context = EvalContext(
            request="Compare as fontes",
            research=True,
            primary_source_count=1,
            research_conflict_count=1,
            citations=("https://docs.example/source",),
            evidence={
                "sources": [{"url": "https://docs.example/source", "authority": "primary"}],
                "evidence": {"conflict_count": 1},
            },
        )
        bad = self.dany.evaluate(
            "A conclusão está confirmada em https://docs.example/source.",
            context,
        )
        self.assertFalse(bad.accepted)
        self.assertFalse(bad.checks["research_conflicts_disclosed"])

        good = self.dany.evaluate(
            "Há divergência entre as fontes; a evidência disponível inclui https://docs.example/source.",
            context,
        )
        self.assertTrue(good.checks["research_conflicts_disclosed"])

    def test_unverified_freshness_requires_explicit_uncertainty(self):
        context = EvalContext(
            request="Pesquise a informação atual",
            research=True,
            primary_source_count=1,
            citations=("https://docs.example/current",),
            freshness_required=True,
            freshness_verified=False,
            evidence={"sources": [{"url": "https://docs.example/current", "authority": "primary"}]},
        )
        bad = self.dany.evaluate(
            "A informação atual está em https://docs.example/current.",
            context,
        )
        self.assertFalse(bad.accepted)
        self.assertFalse(bad.checks["freshness_consistent"])

        good = self.dany.evaluate(
            "A data de publicação não foi verificada; a fonte consultada é https://docs.example/current.",
            context,
        )
        self.assertTrue(good.checks["freshness_consistent"])
        self.assertTrue(good.checks["admits_uncertainty"])

    def test_verified_freshness_does_not_require_uncertainty(self):
        context = EvalContext(
            request="Pesquise a informação atual",
            research=True,
            primary_source_count=1,
            citations=("https://docs.example/current",),
            freshness_required=True,
            freshness_verified=True,
            evidence={"sources": [{"url": "https://docs.example/current", "authority": "primary"}]},
        )
        report = self.dany.evaluate(
            "A fonte atual consultada é https://docs.example/current.",
            context,
        )
        self.assertTrue(report.checks["freshness_consistent"])

    def test_url_not_present_in_evidence_is_rejected(self):
        context = EvalContext(
            request="Mostre a fonte",
            evidence={"url": "https://example.com/source"},
        )
        report = self.dany.evaluate(
            "A fonte é https://invented.example/fake.",
            context,
        )
        self.assertFalse(report.accepted)
        self.assertFalse(report.checks["no_obvious_hallucination"])

    def test_structural_only_validation_can_be_admitted(self):
        context = EvalContext(
            request="Valide este conteúdo",
            evidence={"structure": "valid"},
            factuality_verified=False,
        )
        report = self.dany.evaluate(
            "Validei apenas a estrutura; não verifiquei a factualidade.",
            context,
        )
        self.assertTrue(report.checks["admits_uncertainty"])
        self.assertEqual("structural-and-evidence-consistency", report.scope)

    def test_code_success_claim_requires_real_validation_check(self):
        context = EvalContext(
            request="Valide o projeto",
            code_validation_required=True,
            code_checks_run=(),
        )
        report = self.dany.evaluate(
            "Os testes passaram e o projeto foi validado com sucesso.",
            context,
        )
        self.assertFalse(report.accepted)
        self.assertFalse(report.checks["code_validation_consistent"])

        verified = self.dany.evaluate(
            "Os testes passaram.",
            EvalContext(
                request="Valide o projeto",
                code_validation_required=True,
                code_checks_run=("pytest",),
            ),
        )
        self.assertTrue(verified.checks["code_validation_consistent"])


if __name__ == "__main__":
    unittest.main()
