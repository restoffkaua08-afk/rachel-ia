import json
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(
    0,
    str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"),
)

from search_runtime import (
    BingRssProvider,
    SearchEngine,
    SearchError,
    SearchPolicy,
    WikipediaProvider,
    canonical_url,
    classify_authority,
    coverage_score,
    normalize_query,
)


class SearchRuntimeTests(unittest.TestCase):
    def test_rejects_empty_query(self):
        with self.assertRaises(SearchError):
            normalize_query("   ")

    def test_canonical_url_removes_tracking(self):
        result = canonical_url(
            "https://example.com/docs/?utm_source=test&id=2#top"
        )
        self.assertEqual(
            result,
            "https://example.com/docs?id=2",
        )

    def test_query_coverage(self):
        score = coverage_score(
            "python documentação",
            "Documentação oficial Python",
            "Guia completo.",
        )
        self.assertEqual(score, 1.0)

    def test_classifies_primary_source(self):
        authority, score = classify_authority(
            "https://docs.python.org/3/",
            SearchPolicy(),
        )
        self.assertEqual(authority, "primary")
        self.assertEqual(score, 1.0)

    def test_parses_bing_rss(self):
        content = """
        <rss>
          <channel>
            <item>
              <title>Python Documentation</title>
              <link>https://docs.python.org/3/</link>
              <description>Official documentation</description>
            </item>
          </channel>
        </rss>
        """
        results = BingRssProvider.parse(content, 5)
        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["title"],
            "Python Documentation",
        )

    def test_parses_wikipedia_opensearch(self):
        content = json.dumps(
            [
                "Python",
                ["Python"],
                ["Programming language"],
                ["https://en.wikipedia.org/wiki/Python"],
            ]
        )
        results = WikipediaProvider.parse(content, 5)
        self.assertEqual(len(results), 1)
        self.assertIn("wikipedia.org", results[0]["url"])

    def test_ranking_prefers_primary_source(self):
        engine = SearchEngine(providers=[])
        ranked = engine.rank(
            "python documentation",
            [
                {
                    "title": "Random Python page",
                    "url": "https://example.com/python",
                    "description": "Python documentation",
                    "provider": "bing-rss",
                    "position": 1,
                },
                {
                    "title": "Python Documentation",
                    "url": "https://docs.python.org/3/",
                    "description": "Official Python documentation",
                    "provider": "bing-rss",
                    "position": 2,
                },
            ],
            5,
        )
        self.assertEqual(
            ranked[0].authority,
            "primary",
        )

    def test_deduplicates_canonical_urls(self):
        engine = SearchEngine(providers=[])
        ranked = engine.rank(
            "Rachel IA",
            [
                {
                    "title": "Rachel",
                    "url": "https://example.com/page?utm_source=a",
                    "description": "Rachel IA",
                    "provider": "bing-rss",
                    "position": 1,
                },
                {
                    "title": "Rachel duplicate",
                    "url": "https://example.com/page",
                    "description": "Rachel IA",
                    "provider": "wikipedia-opensearch",
                    "position": 1,
                },
            ],
            5,
        )
        self.assertEqual(len(ranked), 1)


if __name__ == "__main__":
    unittest.main()
