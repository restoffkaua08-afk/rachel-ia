from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))

from context_budget import ContextBudget, bound_context_items, estimate_tokens


class ContextBudgetTests(unittest.TestCase):
    def test_estimate_tokens_is_conservative_and_deterministic(self):
        self.assertEqual(0, estimate_tokens(""))
        self.assertEqual(1, estimate_tokens("abc"))
        self.assertEqual(2, estimate_tokens("abcd"))

    def test_context_never_exceeds_file_limit(self):
        items = [
            {"path": f"src/file_{index}.py", "content": "print('ok')\n"}
            for index in range(40)
        ]
        result = bound_context_items(items)
        self.assertLessEqual(result["file_count"], 19)
        self.assertTrue(result["truncated"])

    def test_context_never_exceeds_token_budget(self):
        budget = ContextBudget(max_tokens=100, max_files=19)
        items = [
            {"path": "src/a.py", "content": "a" * 240},
            {"path": "src/b.py", "content": "b" * 240},
        ]
        result = bound_context_items(items, budget)
        self.assertLessEqual(result["estimated_tokens"], 100)
        self.assertEqual(100, result["max_tokens"])
        self.assertTrue(result["truncated"])

    def test_rank_order_is_preserved(self):
        items = [
            {"path": "first.py", "content": "first"},
            {"path": "second.py", "content": "second"},
        ]
        result = bound_context_items(items, ContextBudget(max_tokens=100, max_files=2))
        self.assertEqual(["first.py", "second.py"], [item["path"] for item in result["items"]])


if __name__ == "__main__":
    unittest.main()
