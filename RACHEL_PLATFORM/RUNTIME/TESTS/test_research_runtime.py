import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(
    0,
    str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"),
)

from dany_runtime import evaluate_runtime_response
from research_runtime import (
    ResearchEngine,
    ResearchQualityEvaluator,
)
from web_runtime import WebEvidence


class FakeSearchEngine:
    def __init__(self):
        self.calls = []

    def search(self, query, limit=8):
        self.calls.append((query, limit))
        return {
            "query": query,
            "result_count": 2,
            "providers_used": ["fixture"],
            "provider_errors": [],
            "results": [
                {
                    "title": "Python Documentation",
                    "url": "https://docs.python.org/3/",
                    "description": "Official documentation",
                    "provider": "fixture",
                    "authority": "primary",
                    "authority_score": 1.0,
                    "score": 0.95,
                },
                {
                    "title": "PEP Index",
                    "url": "https://peps.python.org/",
                    "description": "Python proposals",
                    "provider": "fixture",
                    "authority": "technical",
                    "authority_score": 0.85,
                    "score": 0.85,
                },
            ],
        }


class FakeSearchWithoutPrimary:
    def search(self, query, limit=8):
        return {
            "query": query,
            "result_count": 1,
            "providers_used": ["fixture"],
            "provider_errors": [],
            "results": [
                {
                    "title": "Community summary",
                    "url": "https://example.com/summary",
                    "description": "Secondary summary",
                    "provider": "fixture",
                    "authority": "general",
                    "authority_score": 0.5,
                    "score": 0.8,
                }
            ],
        }


class FakeWebClient:
    def fetch(self, url):
        return WebEvidence(
            url=url,
            final_url=url,
            title=(
                "Python Documentation"
                if "docs." in url
                else "PEP Index"
                if "peps." in url
                else "Community summary"
            ),
            content="Verified technical source content.",
            content_type="text/html",
            status_code=200,
            retrieved_at_ms=1000,
            sha256="a" * 64,
            from_cache=False,
        )


class FreshWebClient:
    def fetch(self, url):
        return WebEvidence(
            url=url,
            final_url=url,
            title="Python Documentation",
            content=(
                "Published 2026-08-20. This official technical source describes "
                "the current Python API behavior and supported interfaces."
            ),
            content_type="text/html",
            status_code=200,
            retrieved_at_ms=1787788800000,
            sha256="b" * 64,
            from_cache=False,
        )


class ConflictingWebClient:
    def fetch(self, url):
        content = (
            "Published 2026-08-20. The documented version is 3.13 and this "
            "statement is part of the official technical reference."
            if "docs." in url
            else
            "Published 2026-08-21. The documented version is 3.14 and this "
            "statement is part of the technical proposal index."
        )
        return WebEvidence(
            url=url,
            final_url=url,
            title="Technical source",
            content=content,
            content_type="text/html",
            status_code=200,
            retrieved_at_ms=1787788800000,
            sha256="c" * 64,
            from_cache=False,
        )


class ResearchRuntimeTests(unittest.TestCase):
    def test_quality_accepts_cited_sources(self):
        report = ResearchQualityEvaluator().evaluate(
            [
                {
                    "url": "https://docs.python.org/3/",
                    "content": "Official content",
                    "authority": "primary",
                    "citation": {
                        "title": "Python",
                        "url": "https://docs.python.org/3/",
                    },
                },
                {
                    "url": "https://peps.python.org/",
                    "content": "Technical content",
                    "authority": "technical",
                    "citation": {
                        "title": "PEP",
                        "url": "https://peps.python.org/",
                    },
                },
            ]
        )
        self.assertTrue(report.accepted)
        self.assertEqual(report.score, 100)
        self.assertEqual(1, report.primary_sources)

    def test_quality_rejects_missing_content(self):
        report = ResearchQualityEvaluator().evaluate(
            [
                {
                    "url": "https://example.com/",
                    "content": "",
                    "authority": "general",
                    "citation": {
                        "title": "Example",
                        "url": "https://example.com/",
                    },
                }
            ]
        )
        self.assertFalse(report.accepted)
        self.assertIn(
            "CONTENT_AVAILABLE",
            report.issues,
        )

    def test_required_primary_source_is_a_real_gate(self):
        report = ResearchQualityEvaluator().evaluate(
            [
                {
                    "url": "https://example.com/",
                    "content": "Secondary content",
                    "authority": "general",
                    "citation": {
                        "title": "Example",
                        "url": "https://example.com/",
                    },
                }
            ],
            require_primary_source=True,
        )
        self.assertFalse(report.accepted)
        self.assertIn("HAS_REQUIRED_PRIMARY_SOURCE", report.issues)

    def test_research_builds_cited_evidence_and_uses_multi_query(self):
        search = FakeSearchEngine()
        engine = ResearchEngine(
            search_engine=search,
            web_client=FakeWebClient(),
        )
        result = engine.research(
            "Python documentation",
            max_sources=2,
        )
        self.assertEqual(result["state"], "completed")
        self.assertEqual(len(result["sources"]), 2)
        self.assertTrue(result["quality"]["accepted"])
        self.assertGreaterEqual(result["search"]["query_count"], 2)
        self.assertEqual(result["search"]["query_count"], len(search.calls))
        self.assertTrue(result["research_plan"]["require_primary_source"])
        self.assertEqual("claim-evidence", result["synthesis"]["mode"])
        self.assertEqual("near-claim", result["synthesis"]["citation_policy"])
        self.assertFalse(
            result["memory"]["stored_automatically"]
        )

    def test_current_research_does_not_fake_freshness(self):
        engine = ResearchEngine(
            search_engine=FakeSearchEngine(),
            web_client=FakeWebClient(),
        )
        result = engine.research(
            "mudancas atuais da API Python",
            max_sources=2,
        )
        self.assertTrue(result["research_plan"]["freshness_required"])
        self.assertFalse(result["quality"]["freshness_verified"])
        self.assertIn("FRESHNESS_VERIFIED", result["quality"]["issues"])
        self.assertIn(
            "freshness_unverified",
            result["synthesis"]["required_disclosures"],
        )
        self.assertEqual("completed_with_warnings", result["state"])

        bad = evaluate_runtime_response(
            "A API Python está atualizada segundo https://docs.python.org/3/.",
            "mudancas atuais da API Python",
            tool_name="web.research",
            tool_result=result,
        )
        self.assertFalse(bad.accepted)
        self.assertFalse(bad.checks["freshness_consistent"])

        good = evaluate_runtime_response(
            "A atualidade não foi verificada; a evidência disponível está em "
            "https://docs.python.org/3/.",
            "mudancas atuais da API Python",
            tool_name="web.research",
            tool_result=result,
        )
        self.assertTrue(good.checks["freshness_consistent"])

    def test_current_research_verifies_recent_publication_signal(self):
        engine = ResearchEngine(
            search_engine=FakeSearchEngine(),
            web_client=FreshWebClient(),
        )
        result = engine.research(
            "mudancas atuais da API Python",
            max_sources=2,
        )
        self.assertTrue(result["quality"]["freshness_verified"])
        self.assertEqual("2026-08-20", result["sources"][0]["published_at"])
        self.assertTrue(result["sources"][0]["freshness_verified"])
        self.assertGreater(result["evidence"]["claim_count"], 0)
        self.assertNotIn(
            "freshness_unverified",
            result["synthesis"]["required_disclosures"],
        )
        self.assertEqual("completed", result["state"])

    def test_conflicting_factual_markers_are_exposed_as_warning(self):
        engine = ResearchEngine(
            search_engine=FakeSearchEngine(),
            web_client=ConflictingWebClient(),
        )
        result = engine.research("Python documentation", max_sources=2)
        self.assertGreater(result["evidence"]["conflict_count"], 0)
        self.assertEqual("version", result["evidence"]["conflicts"][0]["marker"])
        self.assertIn(
            "source_conflicts",
            result["synthesis"]["required_disclosures"],
        )
        self.assertGreater(result["synthesis"]["supported_claim_count"], 0)
        self.assertEqual("completed_with_warnings", result["state"])

        hidden_conflict = evaluate_runtime_response(
            "Python está na versão 3.13 segundo https://docs.python.org/3/.",
            "Python documentation",
            tool_name="web.research",
            tool_result=result,
        )
        self.assertFalse(hidden_conflict.accepted)
        self.assertFalse(
            hidden_conflict.checks["research_conflicts_disclosed"]
        )

        disclosed_conflict = evaluate_runtime_response(
            "As fontes divergem: a documentação registra versão 3.13 em "
            "https://docs.python.org/3/, enquanto a proposta registra versão "
            "3.14 em https://peps.python.org/.",
            "Python documentation",
            tool_name="web.research",
            tool_result=result,
        )
        self.assertTrue(
            disclosed_conflict.checks["research_conflicts_disclosed"]
        )
        self.assertTrue(disclosed_conflict.accepted)

    def test_professional_query_without_primary_source_is_warning_not_fake_success(self):
        engine = ResearchEngine(
            search_engine=FakeSearchWithoutPrimary(),
            web_client=FakeWebClient(),
        )
        result = engine.research("documentacao atual da API", max_sources=1)
        self.assertFalse(result["quality"]["accepted"])
        self.assertEqual(0, result["quality"]["primary_sources"])
        self.assertIn(
            "primary_source_missing",
            result["synthesis"]["required_disclosures"],
        )
        self.assertEqual("completed_with_warnings", result["state"])


if __name__ == "__main__":
    unittest.main()
