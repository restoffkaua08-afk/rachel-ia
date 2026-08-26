from __future__ import annotations

import sys
import unittest
from pathlib import Path
from threading import Event
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_CORE" / "src"))
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))
sys.path.insert(0, str(ROOT / "APP" / "bridge"))

from rachel_core.domain.enums import Role, RunState
from rachel_core.domain.models import ChatResult, Message
from rachel_server import CancellationRegistry, ResidentBridge, response_envelope


class FakeStreamingChat:
    model = SimpleNamespace(provider_name="fake", model_name="fake-model")

    def chat_stream(self, request, on_chunk, is_cancelled=None):
        chunks = ["Olá ", "mundo"]
        emitted = []
        for chunk in chunks:
            if is_cancelled and is_cancelled():
                content = "".join(emitted)
                return ChatResult(
                    conversation_id=request.conversation_id or "conv-stream",
                    run_id="run-cancelled",
                    message=Message(
                        conversation_id=request.conversation_id or "conv-stream",
                        role=Role.ASSISTANT,
                        content=content,
                        metadata={"streamed": True, "cancelled": True},
                    ),
                    state=RunState.CANCELLED,
                    provider="fake",
                    model="fake-model",
                    duration_ms=1,
                )
            emitted.append(chunk)
            on_chunk(chunk)

        return ChatResult(
            conversation_id=request.conversation_id or "conv-stream",
            run_id="run-stream",
            message=Message(
                conversation_id=request.conversation_id or "conv-stream",
                role=Role.ASSISTANT,
                content="".join(emitted),
                metadata={"streamed": True},
            ),
            state=RunState.COMPLETED,
            provider="fake",
            model="fake-model",
            duration_ms=2,
        )


class FakePlanner:
    def heuristic_plan(self, content):
        return None


class FakeLearning:
    def update_quality(self, *args, **kwargs):
        return None


class FakeCognitive:
    def __init__(self):
        self.container = SimpleNamespace(
            chat=FakeStreamingChat(),
            learning=FakeLearning(),
        )
        self.planner = FakePlanner()

    def prepare_memory(self, content):
        return [], None, None

    def status(self):
        return {"status": "ok"}

    def _execution(self, **kwargs):
        return kwargs


class DesktopStreamingRuntimeTests(unittest.TestCase):
    def test_live_chat_emits_deltas_and_returns_stream_metrics(self):
        bridge = ResidentBridge(
            cognitive=FakeCognitive(),
            fallback_execute=lambda payload: {},
        )
        events = []

        payload, metrics = bridge.execute_live(
            {"action": "chat", "content": "oi"},
            lambda event, body: events.append((event, body)),
            Event(),
        )

        deltas = [body["delta"] for event, body in events if event == "chat.delta"]
        self.assertEqual(["Olá ", "mundo"], deltas)
        self.assertEqual("Olá mundo", payload["message"]["content"])
        self.assertTrue(payload["streaming"]["enabled"])
        self.assertIsNotNone(metrics["ttft_ms"])
        self.assertTrue(payload["quality"]["accepted"])
        self.assertEqual(payload["quality"]["validator"], "dany-professional")
        self.assertEqual(payload["quality_scope"], "structural")

    def test_cancel_registry_signals_active_generation(self):
        registry = CancellationRegistry()
        event = registry.register("req-1")
        self.assertFalse(event.is_set())
        self.assertEqual(["req-1"], registry.active())

        cancelled = registry.cancel_all()
        self.assertEqual(["req-1"], cancelled)
        self.assertTrue(event.is_set())

        registry.remove("req-1")
        self.assertEqual([], registry.active())

    def test_metrics_are_not_faked_when_ttft_is_unknown(self):
        response = response_envelope(
            "req-1",
            ok=True,
            payload={"state": "completed"},
            total_ms=120,
            ttft_ms=None,
            tool_latency_ms=None,
        )
        self.assertEqual(120, response["metrics"]["total_ms"])
        self.assertIsNone(response["metrics"]["ttft_ms"])
        self.assertIsNone(response["metrics"]["tool_latency_ms"])

    def test_tauri_source_buffers_ndjson_and_exposes_cancel_command(self):
        source = (ROOT / "APP" / "src-tauri" / "src" / "lib.rs").read_text(
            encoding="utf-8"
        )
        self.assertIn("stdout_buffer", source)
        self.assertIn("route_stdout_bytes", source)
        self.assertIn("rachel_cancel", source)
        self.assertIn('"cancel_all"', source)
        self.assertIn('"rachel-runtime-event"', source)


if __name__ == "__main__":
    unittest.main()
