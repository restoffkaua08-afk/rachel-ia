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
    def search(self, query, limit=8):
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


class FakeWebClient:
    def fetch(self, url):
        return WebEvidence(
            url=url,
            final_url=url,
            title=(
                "Python Documentation"
                if "docs." in url
                else "PEP Index"
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

    def test_research_builds_cited_evidence(self):
        engine = ResearchEngine(
            search_engine=FakeSearchEngine(),
            web_client=FakeWebClient(),
        )
        result = engine.research(
            "Python documentation",
            max_sources=2,
        )
        self.assertEqual(result["state"], "completed")
        self.assertEqual(len(result["sources"]), 2)
        self.assertTrue(result["quality"]["accepted"])
        self.assertFalse(
            result["memory"]["stored_automatically"]
        )


if __name__ == "__main__":
    unittest.main()
