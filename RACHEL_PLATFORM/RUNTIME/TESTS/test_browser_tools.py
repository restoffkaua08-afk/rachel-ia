import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))

from bran_cognitive import CognitiveMemory
from security_runtime import ApprovalStore
from tools_runtime import ToolCoordinator


class FakeBrowser:
    def __init__(self):
        self.calls = []

    def status(self):
        return {"available": True, "read_only_navigation": True}

    def open(self, url):
        self.calls.append(("open", url))
        return {
            "requested_url": url,
            "final_url": url,
            "title": "Example Domain",
            "text": "Example body",
            "text_characters": 12,
        }

    def title(self, url):
        self.calls.append(("title", url))
        return {"requested_url": url, "final_url": url, "title": "Example Domain"}

    def read(self, url):
        self.calls.append(("read", url))
        return {
            "requested_url": url,
            "final_url": url,
            "title": "Example Domain",
            "text": "Example body",
            "text_characters": 12,
        }


class BrowserToolIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.coordinator = ToolCoordinator(
            memory=CognitiveMemory(path=root / "memory.db"),
            approvals=ApprovalStore(path=root / "approvals.db"),
            browser=FakeBrowser(),
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_browser_read_executes_without_approval(self):
        result = self.coordinator.invoke(
            "browser.title",
            {"url": "https://example.com"},
        )
        self.assertEqual("completed", result["state"])
        self.assertEqual("read", result["effective_effect"])
        self.assertEqual("Example Domain", result["result"]["title"])

    def test_browser_read_returns_visible_text(self):
        result = self.coordinator.invoke(
            "browser.read",
            {"url": "https://example.com"},
        )
        self.assertEqual("completed", result["state"])
        self.assertEqual("Example body", result["result"]["text"])

    def test_effectful_browser_action_requires_cyber_approval(self):
        result = self.coordinator.invoke(
            "browser.form",
            {"fields": {"email": "example@example.com"}},
        )
        self.assertEqual("approval_required", result["state"])
        self.assertEqual("external", result["policy"]["effect"])
        self.assertTrue(result["policy"]["approval_required"])
        self.assertIsNotNone(result["approval"])

    def test_browser_tools_are_discoverable(self):
        names = {item["name"] for item in self.coordinator.list_tools()}
        self.assertIn("browser.open", names)
        self.assertIn("browser.read", names)
        self.assertIn("browser.form", names)


if __name__ == "__main__":
    unittest.main()
