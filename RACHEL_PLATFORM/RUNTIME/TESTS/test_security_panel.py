import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))

from security_panel import SecurityPanel
from security_runtime import ApprovalStore


class SecurityPanelTests(unittest.TestCase):
    def store(self):
        temp = tempfile.TemporaryDirectory()
        policy = Path(temp.name) / "policy.json"
        policy.write_text(
            json.dumps(
                {
                    "default_ttl_seconds": 300,
                    "maximum_ttl_seconds": 1800,
                    "single_use": True,
                    "bind_tool": True,
                    "bind_arguments": True,
                    "store_argument_values": False,
                }
            ),
            encoding="utf-8",
        )
        return temp, ApprovalStore(Path(temp.name) / "approvals.db", policy)

    def test_panel_orders_higher_risk_first(self):
        temp, store = self.store()
        try:
            store.request("low.tool", "read", "low", {"query": "x"}, "Baixo risco")
            store.request("high.tool", "write", "high", {"path": "x"}, "Alto risco")
            panel = SecurityPanel(store)
            snapshot = panel.snapshot()
            self.assertEqual(snapshot["items"][0]["risk"], "high")
            self.assertEqual(snapshot["items"][1]["risk"], "low")
        finally:
            temp.cleanup()

    def test_panel_never_exposes_argument_values(self):
        temp, store = self.store()
        try:
            secret = "valor-super-secreto-123"
            approval = store.request(
                "arya.project.create",
                "create",
                "medium",
                {"project": secret, "token": "abc123"},
                "Criar projeto",
            )
            panel = SecurityPanel(store)
            card = panel.show(approval["id"])
            rendered = panel.render_card(card)
            serialized = json.dumps(card, ensure_ascii=False)
            self.assertNotIn(secret, rendered)
            self.assertNotIn(secret, serialized)
            self.assertNotIn("abc123", rendered)
            self.assertNotIn("abc123", serialized)
            self.assertIn("project", rendered)
            self.assertIn("token", rendered)
        finally:
            temp.cleanup()

    def test_panel_exposes_explicit_confirmation_phrases(self):
        temp, store = self.store()
        try:
            approval = store.request(
                "arya.project.write",
                "write",
                "high",
                {"path": "README.md", "content": "x"},
                "Alterar arquivo",
            )
            card = SecurityPanel(store).show(approval["id"])
            self.assertEqual(card["confirmation"]["approve"], f"APROVAR {approval['id']}")
            self.assertEqual(card["confirmation"]["deny"], f"NEGAR {approval['id']}")
        finally:
            temp.cleanup()

    def test_panel_can_approve_and_deny(self):
        temp, store = self.store()
        try:
            first = store.request("tool.a", "write", "medium", {"a": 1}, "A")
            second = store.request("tool.b", "delete", "high", {"b": 2}, "B")
            panel = SecurityPanel(store)
            approved = panel.decide(first["id"], True)
            denied = panel.decide(second["id"], False)
            self.assertEqual(approved["status"], "approved")
            self.assertEqual(denied["status"], "denied")
        finally:
            temp.cleanup()

    def test_snapshot_is_frontend_ready_json(self):
        temp, store = self.store()
        try:
            store.request("tool.a", "create", "medium", {"name": "demo"}, "Criar")
            snapshot = SecurityPanel(store).snapshot()
            encoded = json.dumps(snapshot, ensure_ascii=False)
            decoded = json.loads(encoded)
            self.assertEqual(decoded["state"], "ready")
            self.assertEqual(decoded["total"], 1)
            self.assertEqual(decoded["items"][0]["risk_label"], "MEDIUM")
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
