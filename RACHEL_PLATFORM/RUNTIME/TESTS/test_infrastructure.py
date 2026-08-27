import json
import tempfile
import unittest
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))
from team_runtime import CyberPolicy, KingEventBus, NedRouter, TyrionSupervisor


class InfrastructureTests(unittest.TestCase):
    def test_king_persists_event(self):
        with tempfile.TemporaryDirectory() as directory:
            bus = KingEventBus(Path(directory) / "events.db")
            created = bus.publish("test.event", {"ok": True})
            recent = bus.recent()
            self.assertEqual(recent[0]["id"], created["id"])

    def test_cyber_blocks_write_without_approval(self):
        decision = CyberPolicy().check("write")
        self.assertFalse(decision.allowed)
        self.assertTrue(decision.approval_required)

    def test_cyber_allows_approved_write(self):
        self.assertTrue(CyberPolicy().check("write", approved=True).allowed)

    def test_ned_routes_voice_to_stella(self):
        self.assertIn("stella", NedRouter().route("transcrever audio"))

    def test_ned_routes_browser_context_to_arya(self):
        self.assertIn("arya", NedRouter().route("abra este site no navegador"))

    def test_ned_extracts_browser_title_intent(self):
        intent = NedRouter().browser_intent("abra https://example.com e me diga o título")
        self.assertIsNotNone(intent)
        self.assertEqual(intent["tool"], "browser.title")
        self.assertEqual(intent["arguments"]["url"], "https://example.com")
        self.assertEqual(intent["effect"], "read")
        self.assertEqual(intent["member"], "arya")

    def test_ned_extracts_browser_read_intent(self):
        intent = NedRouter().browser_intent("leia o conteúdo de https://example.com/docs")
        self.assertEqual(intent["tool"], "browser.read")
        self.assertEqual(intent["arguments"]["url"], "https://example.com/docs")

    def test_ned_defaults_explicit_url_to_open(self):
        intent = NedRouter().browser_intent("visite https://example.com")
        self.assertEqual(intent["tool"], "browser.open")

    def test_ned_does_not_invent_browser_intent_without_context(self):
        self.assertIsNone(NedRouter().browser_intent("me diga o titulo do projeto"))

    @pytest.mark.requires_submodules
    @pytest.mark.xfail(reason="Requer 23 submódulos Git inicializados em FONTES/REPOSITORIOS; CI usa submodules:false", strict=False)
    def test_tyrion_sees_all_organs(self):
        health = TyrionSupervisor().health()
        self.assertEqual(health["total"], 23)
        self.assertEqual(health["failed"], 0)


if __name__ == "__main__":
    unittest.main()
