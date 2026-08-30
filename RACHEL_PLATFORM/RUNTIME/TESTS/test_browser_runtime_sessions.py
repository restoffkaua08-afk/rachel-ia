from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "SRC"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from browser_runtime import BrowserRuntime
from web_runtime import WebPolicy


class FakeLiveSessions:
    def __init__(self) -> None:
        self.calls = []

    def create(self, url=None):
        self.calls.append(("create", url))
        return {"session": {"session_id": "s1", "page_id": "p1", "current_url": url}, "live_context": True}

    def navigate(self, session_id, url):
        self.calls.append(("navigate", session_id, url))
        return {"session": {"session_id": session_id, "page_id": "p1", "current_url": url}, "live_context": True}

    def get(self, session_id):
        self.calls.append(("get", session_id))
        return {"session": {"session_id": session_id, "page_id": "p1"}, "live_context": True}

    def close(self, session_id):
        self.calls.append(("close", session_id))
        return {"session": {"session_id": session_id, "closed": True}, "live_context_closed": True}

    def cleanup(self):
        return {"removed": [], "removed_count": 0, "active": 1, "live_contexts": 1}

    def status(self):
        return {"live_playwright_context_persistence": True, "live_contexts": 1, "effectful_actions_enabled": False, "mode": "persistent-read-only"}


class BrowserRuntimeSessionTests(unittest.TestCase):
    def test_runtime_exposes_persistent_session_lifecycle(self):
        live = FakeLiveSessions()
        runtime = BrowserRuntime(policy=WebPolicy(), live_sessions=live)
        opened = runtime.session_open("https://example.com")
        self.assertEqual(opened["session"]["session_id"], "s1")
        runtime.session_navigate("s1", "https://example.com/docs")
        runtime.session_get("s1")
        runtime.session_close("s1")
        self.assertEqual([call[0] for call in live.calls], ["create", "navigate", "get", "close"])

    def test_status_is_truthful_and_effects_stay_disabled(self):
        runtime = BrowserRuntime(policy=WebPolicy(), live_sessions=FakeLiveSessions())
        status = runtime.status()
        self.assertTrue(status["persistent_sessions_available"])
        self.assertTrue(status["session"]["live_playwright_context_persistence"])
        self.assertEqual(status["session"]["mode"], "persistent-read-only")
        self.assertFalse(status["effectful_actions_enabled"])
        self.assertEqual(status["actions"]["click"], "external")


if __name__ == "__main__":
    unittest.main()
