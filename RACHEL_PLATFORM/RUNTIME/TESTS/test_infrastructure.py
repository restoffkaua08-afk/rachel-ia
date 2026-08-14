import json
import tempfile
import unittest
from pathlib import Path
import sys

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

    def test_tyrion_sees_all_organs(self):
        health = TyrionSupervisor().health()
        self.assertEqual(health["total"], 23)
        self.assertEqual(health["failed"], 0)


if __name__ == "__main__":
    unittest.main()
