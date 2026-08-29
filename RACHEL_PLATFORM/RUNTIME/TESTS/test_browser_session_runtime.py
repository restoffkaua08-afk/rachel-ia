from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from browser_session_runtime import BrowserSessionError, BrowserSessionManager


class BrowserSessionRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = 1_000_000
        self.validated: list[str] = []

        def clock() -> int:
            return self.now

        def validate(url: str) -> str:
            self.validated.append(url)
            if not url.startswith(("https://", "http://")):
                raise ValueError("blocked")
            return url.rstrip("/")

        self.manager = BrowserSessionManager(
            validate_url=validate,
            ttl_seconds=60,
            maximum_sessions=2,
            clock_ms=clock,
        )

    def test_create_and_navigate_validate_every_url(self) -> None:
        created = self.manager.create("https://example.com/")
        session_id = created["session_id"]
        self.assertEqual("https://example.com", created["current_url"])
        self.assertEqual("https://example.com", created["origin"])

        navigated = self.manager.navigate(session_id, "https://example.org/path")
        self.assertEqual("https://example.org/path", navigated["current_url"])
        self.assertEqual("https://example.org", navigated["origin"])
        self.assertEqual(
            ["https://example.com/", "https://example.org/path"],
            self.validated,
        )

    def test_invalid_navigation_does_not_mutate_session(self) -> None:
        created = self.manager.create("https://example.com")
        session_id = created["session_id"]
        with self.assertRaises(ValueError):
            self.manager.navigate(session_id, "file:///etc/passwd")
        current = self.manager.get(session_id)
        self.assertEqual("https://example.com", current["current_url"])

    def test_expired_session_fails_closed(self) -> None:
        created = self.manager.create("https://example.com")
        self.now += 61_000
        with self.assertRaises(BrowserSessionError):
            self.manager.get(created["session_id"])
        self.assertEqual(0, self.manager.status()["active_sessions"])

    def test_lru_eviction_is_bounded(self) -> None:
        first = self.manager.create("https://one.example")
        self.now += 1_000
        second = self.manager.create("https://two.example")
        self.now += 1_000
        self.manager.get(second["session_id"])
        self.now += 1_000
        third = self.manager.create("https://three.example")
        self.assertEqual(first["session_id"], third["evicted_session_id"])
        with self.assertRaises(BrowserSessionError):
            self.manager.get(first["session_id"])
        self.assertEqual(2, self.manager.status()["active_sessions"])

    def test_close_is_explicit_and_idempotent(self) -> None:
        created = self.manager.create("https://example.com")
        session_id = created["session_id"]
        first = self.manager.close(session_id)
        second = self.manager.close(session_id)
        self.assertTrue(first["closed"])
        self.assertFalse(first["already_absent"])
        self.assertFalse(second["closed"])
        self.assertTrue(second["already_absent"])

    def test_status_does_not_claim_live_context_persistence(self) -> None:
        status = self.manager.status()
        self.assertTrue(status["persistent_metadata"])
        self.assertFalse(status["live_playwright_context_persistence"])
        self.assertFalse(status["effectful_actions_enabled"])


if __name__ == "__main__":
    unittest.main()
