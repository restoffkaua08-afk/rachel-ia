import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))

from browser_runtime import BrowserError, BrowserPageEvidence, BrowserRuntime
from web_runtime import WebSecurityError


class FakePolicy:
    timeout_seconds = 10
    maximum_text_characters = 5000
    allowed_schemes = {"http", "https"}
    blocked_hosts = {"localhost"}
    blocked_networks = ()


class FakeBackend:
    def __init__(self):
        self.calls = []
        self.validated = []

    def open_page(
        self,
        url,
        *,
        timeout_seconds,
        validate_request,
        maximum_text_characters,
    ):
        self.calls.append((url, timeout_seconds, maximum_text_characters))
        requested = validate_request(url)
        self.validated.append(requested)
        final_url = validate_request("https://example.com/final")
        self.validated.append(final_url)
        return BrowserPageEvidence(
            requested_url=requested,
            final_url=final_url,
            title="Example Domain",
            text="Example body",
            html_characters=100,
            text_characters=12,
        )


class InvalidBackend:
    def open_page(self, *args, **kwargs):
        return {"title": "invalid"}


class BrowserRuntimeTests(unittest.TestCase):
    @staticmethod
    def resolver(host, port, *args, **kwargs):
        if host == "example.com":
            return [(2, 1, 6, "", ("93.184.216.34", port or 443))]
        if host == "localhost":
            return [(2, 1, 6, "", ("127.0.0.1", port or 80))]
        return [(2, 1, 6, "", ("93.184.216.34", port or 443))]

    def test_open_returns_governed_page_evidence(self):
        backend = FakeBackend()
        runtime = BrowserRuntime(
            backend=backend,
            policy=FakePolicy(),
            resolver=self.resolver,
        )
        result = runtime.open("https://example.com")

        self.assertEqual("Example Domain", result["title"])
        self.assertEqual("https://example.com/", result["requested_url"])
        self.assertEqual("https://example.com/final", result["final_url"])
        self.assertEqual(2, len(backend.validated))

    def test_title_returns_minimal_read_only_projection(self):
        runtime = BrowserRuntime(
            backend=FakeBackend(),
            policy=FakePolicy(),
            resolver=self.resolver,
        )
        result = runtime.title("example.com")
        self.assertEqual(
            {
                "requested_url": "https://example.com/",
                "final_url": "https://example.com/final",
                "title": "Example Domain",
            },
            result,
        )

    def test_read_returns_text_projection(self):
        runtime = BrowserRuntime(
            backend=FakeBackend(),
            policy=FakePolicy(),
            resolver=self.resolver,
        )
        result = runtime.read("example.com")
        self.assertEqual("Example Domain", result["title"])
        self.assertEqual("Example body", result["text"])
        self.assertEqual(12, result["text_characters"])

    def test_ssrf_policy_blocks_localhost_before_backend_navigation(self):
        runtime = BrowserRuntime(
            backend=FakeBackend(),
            policy=FakePolicy(),
            resolver=self.resolver,
        )
        with self.assertRaises(WebSecurityError):
            runtime.open("http://localhost")

    def test_effect_model_separates_read_from_effectful_actions(self):
        self.assertEqual("read", BrowserRuntime.effect_for("open"))
        self.assertEqual("read", BrowserRuntime.effect_for("read"))
        self.assertEqual("external", BrowserRuntime.effect_for("click"))
        self.assertEqual("external", BrowserRuntime.effect_for("form"))
        self.assertEqual("external", BrowserRuntime.effect_for("login"))
        self.assertEqual("external", BrowserRuntime.effect_for("upload"))
        self.assertEqual("external", BrowserRuntime.effect_for("download"))

    def test_unknown_action_is_rejected(self):
        with self.assertRaises(BrowserError):
            BrowserRuntime.effect_for("javascript")

    def test_invalid_backend_evidence_is_rejected(self):
        runtime = BrowserRuntime(
            backend=InvalidBackend(),
            policy=FakePolicy(),
            resolver=self.resolver,
        )
        with self.assertRaises(BrowserError):
            runtime.open("https://example.com")

    def test_status_does_not_enable_effectful_actions(self):
        runtime = BrowserRuntime(
            backend=FakeBackend(),
            policy=FakePolicy(),
            resolver=self.resolver,
        )
        status = runtime.status()
        self.assertTrue(status["read_only_navigation"])
        self.assertFalse(status["effectful_actions_enabled"])
        self.assertEqual("web-policy-every-request", status["request_guard"])
        self.assertEqual("read", status["actions"]["open"])
        self.assertEqual("external", status["actions"]["form"])


if __name__ == "__main__":
    unittest.main()
