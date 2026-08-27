import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(
    0,
    str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"),
)

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
        self.assertEqual("completed_with_warnings", result["state"])

    def test_professional_query_without_primary_source_is_warning_not_fake_success(self):
        engine = ResearchEngine(
            search_engine=FakeSearchWithoutPrimary(),
            web_client=FakeWebClient(),
        )
        result = engine.research("documentacao atual da API", max_sources=1)
        self.assertFalse(result["quality"]["accepted"])
        self.assertEqual(0, result["quality"]["primary_sources"])
        self.assertEqual("completed_with_warnings", result["state"])


if __name__ == "__main__":
    unittest.main()
