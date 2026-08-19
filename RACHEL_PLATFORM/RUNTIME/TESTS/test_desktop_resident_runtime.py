from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_CORE" / "src"))
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))
sys.path.insert(0, str(ROOT / "APP" / "bridge"))

from rachel_server import ResidentBridge, process_envelope


class FakeCognitive:
    def __init__(self) -> None:
        self.status_calls = 0
        self.chat_calls = 0
        self.handle_calls = 0
        self.last_handle = None

    def status(self):
        self.status_calls += 1
        return {"status": "ok", "instance": id(self)}

    def chat(self, content, conversation_id=None):
        self.chat_calls += 1
        return {
            "state": "completed",
            "conversation_id": conversation_id or "resident-conversation",
            "message": {"content": f"chat:{content}"},
        }

    def handle(
        self,
        content,
        conversation_id=None,
        approval_id=None,
        resume_plan=None,
    ):
        self.handle_calls += 1
        self.last_handle = {
            "content": content,
            "conversation_id": conversation_id,
            "approval_id": approval_id,
            "resume_plan": resume_plan,
        }
        return {
            "state": "completed",
            "conversation_id": conversation_id or "resident-conversation",
            "message": {"content": f"assist:{content}"},
        }


class DesktopResidentRuntimeTests(unittest.TestCase):
    def services(self):
        cognitive = FakeCognitive()
        fallback_calls = []

        def fallback(payload):
            fallback_calls.append(dict(payload))
            return {"legacy": payload.get("action")}

        return ResidentBridge(cognitive=cognitive, fallback_execute=fallback), cognitive, fallback_calls

    def test_same_cognitive_instance_is_reused_across_requests(self):
        services, cognitive, _ = self.services()

        first = process_envelope(
            {"request_id": "req-1", "payload": {"action": "chat", "content": "oi"}},
            services,
        )
        second = process_envelope(
            {"request_id": "req-2", "payload": {"action": "chat", "content": "de novo"}},
            services,
        )

        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])
        self.assertEqual(cognitive.chat_calls, 2)
        self.assertEqual(services.requests, 2)
        self.assertEqual(first["request_id"], "req-1")
        self.assertEqual(second["request_id"], "req-2")

    def test_exact_resume_plan_is_forwarded_to_canonical_handle(self):
        services, cognitive, _ = self.services()
        resume_plan = {
            "action": "tool",
            "tool": "bran.remember",
            "arguments": {"content": "teste"},
            "reason": "teste",
            "source": "deterministic",
        }

        response = process_envelope(
            {
                "request_id": "req-resume",
                "payload": {
                    "action": "assist",
                    "content": "lembre disso",
                    "conversation_id": "conv-1",
                    "approval_id": "approval-1",
                    "resume_plan": resume_plan,
                },
            },
            services,
        )

        self.assertTrue(response["ok"])
        self.assertEqual(cognitive.handle_calls, 1)
        self.assertEqual(cognitive.last_handle["approval_id"], "approval-1")
        self.assertEqual(cognitive.last_handle["resume_plan"], resume_plan)

    def test_request_correlation_and_metrics_are_always_present(self):
        services, _, _ = self.services()
        response = process_envelope(
            {"request_id": "req-metrics", "payload": {"action": "resident_status"}},
            services,
        )

        self.assertEqual(response["kind"], "response")
        self.assertEqual(response["request_id"], "req-metrics")
        self.assertTrue(response["ok"])
        self.assertTrue(response["metrics"]["resident"])
        self.assertGreaterEqual(response["metrics"]["total_ms"], 0)
        self.assertIn("ttft_ms", response["metrics"])
        self.assertIn("tool_latency_ms", response["metrics"])

    def test_invalid_envelopes_fail_closed_without_crashing_server(self):
        services, _, _ = self.services()

        missing_payload = process_envelope({"request_id": "req-bad"}, services)
        missing_id = process_envelope({"payload": {"action": "status"}}, services)

        self.assertFalse(missing_payload["ok"])
        self.assertEqual(missing_payload["request_id"], "req-bad")
        self.assertFalse(missing_id["ok"])
        self.assertEqual(missing_id["request_id"], "invalid-request")

    def test_legacy_actions_remain_compatible_during_migration(self):
        services, _, fallback_calls = self.services()
        response = process_envelope(
            {
                "request_id": "req-legacy",
                "payload": {"action": "memory_search", "query": "x"},
            },
            services,
        )

        self.assertTrue(response["ok"])
        self.assertEqual(response["payload"], {"legacy": "memory_search"})
        self.assertEqual(fallback_calls, [{"action": "memory_search", "query": "x"}])

    def test_pyinstaller_entrypoint_uses_resident_server(self):
        spec = (ROOT / "APP" / "sidecar" / "rachel_backend.spec").read_text(encoding="utf-8")
        self.assertIn('"rachel_server.py"', spec)
        self.assertIn('APP / "bridge"', spec)


if __name__ == "__main__":
    unittest.main()
