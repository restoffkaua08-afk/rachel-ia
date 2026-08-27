import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))

from research_strategy import plan_research_queries


class ResearchStrategyTests(unittest.TestCase):
    def test_simple_query_keeps_single_query(self):
        plan = plan_research_queries("historia do protocolo HTTP")
        self.assertEqual(("historia do protocolo HTTP",), plan.queries)
        self.assertFalse(plan.freshness_required)

    def test_current_query_requests_primary_and_freshness(self):
        plan = plan_research_queries("mudancas atuais da API Python")
        self.assertTrue(plan.require_primary_source)
        self.assertTrue(plan.freshness_required)
        self.assertEqual(30, plan.freshness_window_days)
        self.assertGreaterEqual(len(plan.queries), 2)
        self.assertTrue(any("official" in query for query in plan.queries[1:]))

    def test_technical_query_adds_official_documentation_variant(self):
        plan = plan_research_queries("documentacao da API FastAPI")
        self.assertTrue(plan.technical_query)
        self.assertTrue(plan.require_primary_source)
        self.assertTrue(
            any("official documentation release notes" in query for query in plan.queries)
        )

    def test_comparison_query_adds_specification_variant(self):
        plan = plan_research_queries("compare PostgreSQL vs MySQL")
        self.assertTrue(plan.comparison_query)
        self.assertTrue(plan.require_primary_source)
        self.assertTrue(any("official specifications" in query for query in plan.queries))

    def test_variants_are_deduplicated_and_bounded(self):
        plan = plan_research_queries("latest API docs compare versao atual")
        self.assertLessEqual(len(plan.queries), 4)
        self.assertEqual(len(plan.queries), len({item.casefold() for item in plan.queries}))

    def test_empty_query_is_rejected(self):
        with self.assertRaises(ValueError):
            plan_research_queries("   ")


if __name__ == "__main__":
    unittest.main()
