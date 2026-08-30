from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from browser_live_session_runtime import BrowserLiveSessionRuntime
from browser_runtime import BrowserPageEvidence


class FakePersistentBackend:
    def __init__(self) -> None:
        self.handles: set[str] = set()
        self.created: list[str] = []
        self.navigated: list[tuple[str, str]] = []
        self.closed: list[str] = []

    def create(self, session_id: str, *, validate_request):
        self.handles.add(session_id)
        self.created.append(session_id)

    def navigate(
        self,
        session_id: str,
        url: str,
        *,
        timeout_seconds: int,
        validate_request,
        maximum_text_characters: int,
    ) -> BrowserPageEvidence:
        if session_id not in self.handles:
            raise RuntimeError("missing live handle")
        requested = validate_request(url)
        self.navigated.append((session_id, requested))
        return BrowserPageEvidence(
            requested_url=requested,
            final_url=requested,
            title="Example",
            text="hello",
            html_characters=20,
            text_characters=5,
        )

    def close(self, session_id: str) -> bool:
        existed = session_id in self.handles
        self.handles.discard(session_id)
        if existed:
            self.closed.append(session_id)
        return existed

    def active(self) -> int:
        return len(self.handles)


class BrowserLiveSessionRuntimeTests(unittest.TestCase):
    def service(self):
        backend = FakePersistentBackend()
        validated: list[str] = []

        def validate(url: str) -> str:
            if not isinstance(url, str) or not url.startswith("https://"):
                raise ValueError("blocked url")
            validated.append(url)
            return url

        service = BrowserLiveSessionRuntime(
            validate_url=validate,
            timeout_seconds=5,
            maximum_text_characters=1000,
            backend=backend,
        )
        return service, backend, validated

    def test_create_keeps_live_context_and_navigates_same_session(self):
        service, backend, _ = self.service()
        created = service.create("https://example.com")
        session_id = created["session"]["session_id"]

        self.assertTrue(created["live_context"])
        self.assertIn(session_id, backend.handles)
        self.assertEqual(1, backend.active())

        second = service.navigate(session_id, "https://example.com/docs")
        self.assertEqual(session_id, second["session"]["session_id"])
        self.assertEqual("https://example.com/docs", second["session"]["current_url"])
        self.assertEqual(2, len(backend.navigated))

    def test_invalid_navigation_fails_before_backend_mutation(self):
        service, backend, _ = self.service()
        created = service.create("https://example.com")
        session_id = created["session"]["session_id"]
        before = list(backend.navigated)

        with self.assertRaises(ValueError):
            service.navigate(session_id, "http://127.0.0.1/private")

        self.assertEqual(before, backend.navigated)
        self.assertEqual("https://example.com", service.get(session_id)["session"]["current_url"])

    def test_close_closes_live_and_logical_state(self):
        service, backend, _ = self.service()
        created = service.create("https://example.com")
        session_id = created["session"]["session_id"]

        closed = service.close(session_id)
        self.assertTrue(closed["live_context_closed"])
        self.assertTrue(closed["session"]["closed"])
        self.assertEqual(0, backend.active())

        with self.assertRaises(Exception):
            service.get(session_id)

    def test_status_is_truthful_and_read_only(self):
        service, backend, _ = self.service()
        status = service.status()
        self.assertTrue(status["live_playwright_context_persistence"])
        self.assertFalse(status["effectful_actions_enabled"])
        self.assertEqual("persistent-read-only", status["mode"])
        self.assertEqual(0, status["live_contexts"])
        self.assertEqual(0, backend.active())


if __name__ == "__main__":
    unittest.main()
