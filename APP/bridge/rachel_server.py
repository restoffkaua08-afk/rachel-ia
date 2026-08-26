from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from threading import Event, Lock
from typing import Any, Callable

from rachel_bridge import (
    execute as legacy_execute,
    main as legacy_main,
    optional_object,
    optional_text,
    required_text,
)
from cognitive_runtime import (
    NedCognitiveBridge,
    ToolPlan,
    extract_task_goal,
    should_use_tool_planner,
)
from dany_runtime import evaluate_runtime_response, quality_payload
from rachel_core.domain.enums import RunState
from rachel_core.domain.models import ChatRequest


PROTOCOL_VERSION = 2
MAX_RESIDENT_WORKERS = 2


class CancellationRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._events: dict[str, Event] = {}

    def register(self, request_id: str) -> Event:
        event = Event()
        with self._lock:
            self._events[request_id] = event
        return event

    def remove(self, request_id: str) -> None:
        with self._lock:
            self._events.pop(request_id, None)

    def cancel_all(self) -> list[str]:
        with self._lock:
            items = list(self._events.items())
        for _, event in items:
            event.set()
        return [request_id for request_id, _ in items]

    def active(self) -> list[str]:
        with self._lock:
            return list(self._events)


class ResidentBridge:
    """Long-lived desktop service container.

    A single cognitive bridge is reused across the desktop session. Common chat
    can stream directly from the provider while tool-bearing requests preserve
    the canonical Ned/Cyber flow.
    """

    def __init__(
        self,
        cognitive: NedCognitiveBridge | None = None,
        fallback_execute: Callable[[dict[str, Any]], dict[str, Any]] = legacy_execute,
    ) -> None:
        self.cognitive = cognitive or NedCognitiveBridge()
        self.fallback_execute = fallback_execute
        self.started_at = time.time()
        self.requests = 0
        self._counter_lock = Lock()

    def _count_request(self) -> None:
        with self._counter_lock:
            self.requests += 1

    def status(self) -> dict[str, Any]:
        return {
            "resident": True,
            "protocol_version": PROTOCOL_VERSION,
            "requests": self.requests,
            "uptime_ms": max(0, int((time.time() - self.started_at) * 1000)),
            "cognitive": self.cognitive.status(),
            "streaming": True,
            "cancellable_generation": True,
            "max_workers": MAX_RESIDENT_WORKERS,
        }

    def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Compatibility path used by tests and non-streaming callers."""
        self._count_request()
        action = payload.get("action")

        if action == "resident_status":
            return self.status()
        if action == "status":
            status = self.cognitive.status()
            status["resident_runtime"] = True
            status["resident_requests"] = self.requests
            status["streaming_transport"] = True
            return status
        if action == "chat":
            return self.cognitive.chat(
                required_text(payload, "content"),
                optional_text(payload, "conversation_id"),
            )
        if action == "assist":
            return self.cognitive.handle(
                required_text(payload, "content"),
                optional_text(payload, "conversation_id"),
                approval_id=optional_text(payload, "approval_id", maximum=200),
                resume_plan=optional_object(payload, "resume_plan"),
            )
        return self.fallback_execute(payload)

    def _stream_cognitive_chat(
        self,
        content: str,
        conversation_id: str | None,
        emit: Callable[[str, dict[str, Any]], None],
        cancel_event: Event,
        *,
        system_prompt: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        recalled, proposal, memory_context = self.cognitive.prepare_memory(content)
        effective_system = system_prompt or ""
        if memory_context:
            effective_system = (
                effective_system.rstrip()
                + ("\n\n" if effective_system.strip() else "")
                + memory_context
            )

        started = time.perf_counter()
        first_delta_ms: int | None = None

        def on_chunk(chunk: str) -> None:
            nonlocal first_delta_ms
            elapsed = int((time.perf_counter() - started) * 1000)
            if first_delta_ms is None:
                first_delta_ms = elapsed
            emit(
                "chat.delta",
                {
                    "delta": chunk,
                    "elapsed_ms": elapsed,
                },
            )

        emit("chat.started", {"conversation_id": conversation_id})
        result = self.cognitive.container.chat.chat_stream(
            ChatRequest(
                content=content,
                conversation_id=conversation_id,
                system_prompt=effective_system or None,
            ),
            on_chunk,
            cancel_event.is_set,
        )

        payload = result.to_dict()
        payload["streaming"] = {
            "enabled": True,
            "ttft_ms": first_delta_ms,
            "cancelled": result.state == RunState.CANCELLED,
        }
        payload["memory"] = {
            "recalled_count": len(recalled),
            "recalled": [
                {
                    "id": item["id"],
                    "content": item["content"],
                    "category": item["category"],
                    "relevance": item.get("relevance"),
                }
                for item in recalled
            ],
            "proposal": proposal,
            "proposal_requires_approval": proposal is not None,
        }

        if result.state == RunState.COMPLETED:
            report = evaluate_runtime_response(result.message.content, content)
            payload["quality"] = quality_payload(report)
            payload["quality_scope"] = report.scope
            experience_id = result.message.metadata.get("learning_experience_id")
            if experience_id:
                self.cognitive.container.learning.update_quality(
                    experience_id,
                    accepted=report.accepted,
                    score=report.score,
                    issues=report.issues,
                    checks=report.checks,
                )
            if not report.accepted:
                raise RuntimeError(f"Dany rejected the streamed response: {report.issues}")
            emit(
                "chat.completed",
                {
                    "conversation_id": result.conversation_id,
                    "run_id": result.run_id,
                    "duration_ms": result.duration_ms,
                    "ttft_ms": first_delta_ms,
                },
            )
        else:
            payload["quality"] = None
            payload["quality_scope"] = "not-evaluated-cancelled"
            emit(
                "chat.cancelled",
                {
                    "conversation_id": result.conversation_id,
                    "run_id": result.run_id,
                    "duration_ms": result.duration_ms,
                },
            )

        return payload, {
            "ttft_ms": first_delta_ms,
            "tool_latency_ms": None,
        }

    def execute_live(
        self,
        payload: dict[str, Any],
        emit: Callable[[str, dict[str, Any]], None],
        cancel_event: Event,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        self._count_request()
        action = payload.get("action")

        if action == "resident_status":
            return self.status(), {"ttft_ms": 0, "tool_latency_ms": None}

        if action == "status":
            status = self.cognitive.status()
            status["resident_runtime"] = True
            status["resident_requests"] = self.requests
            status["streaming_transport"] = True
            return status, {"ttft_ms": 0, "tool_latency_ms": None}

        if action == "chat":
            return self._stream_cognitive_chat(
                required_text(payload, "content"),
                optional_text(payload, "conversation_id"),
                emit,
                cancel_event,
            )

        if action == "assist":
            content = required_text(payload, "content")
            conversation_id = optional_text(payload, "conversation_id")
            approval_id = optional_text(payload, "approval_id", maximum=200)
            resume_plan = optional_object(payload, "resume_plan")

            # Common conversation is streamed without an unnecessary tool-planner call.
            if (
                approval_id is None
                and resume_plan is None
                and extract_task_goal(content) is None
                and self.cognitive.planner.heuristic_plan(content) is None
                and not should_use_tool_planner(content)
            ):
                response, metrics = self._stream_cognitive_chat(
                    content,
                    conversation_id,
                    emit,
                    cancel_event,
                )
                fast_plan = ToolPlan(
                    "chat",
                    None,
                    {},
                    "Conversa normal; fast path sem planner de ferramentas.",
                    "fast-chat-stream",
                )
                response["tool_plan"] = asdict(fast_plan)
                response["tool_result"] = None
                response["resume_plan"] = None
                response["execution"] = self.cognitive._execution(
                    state="not_executed",
                    planned=False,
                    executed=False,
                    verified=False,
                )
                return response, metrics

            emit("agent.phase", {"phase": "planning-or-tool", "state": "started"})
            started = time.perf_counter()
            response = self.cognitive.handle(
                content,
                conversation_id,
                approval_id=approval_id,
                resume_plan=resume_plan,
            )
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            has_tool = isinstance(response.get("tool_result"), dict)
            emit(
                "agent.phase",
                {
                    "phase": "planning-or-tool",
                    "state": response.get("state", "completed"),
                    "elapsed_ms": elapsed_ms,
                    "tool": (
                        response.get("tool_plan", {}).get("tool")
                        if isinstance(response.get("tool_plan"), dict)
                        else None
                    ),
                },
            )
            return response, {
                "ttft_ms": None,
                # Until the tool coordinator exposes its own timer this value is
                # intentionally an end-to-end action latency, never mislabeled.
                "tool_latency_ms": elapsed_ms if has_tool else None,
                "tool_latency_scope": "action-end-to-end" if has_tool else None,
            }

        response = self.fallback_execute(payload)
        return response, {"ttft_ms": None, "tool_latency_ms": None}


def response_envelope(
    request_id: str,
    *,
    ok: bool,
    payload: dict[str, Any] | None = None,
    error: Exception | None = None,
    total_ms: int,
    ttft_ms: int | None = None,
    tool_latency_ms: int | None = None,
    tool_latency_scope: str | None = None,
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "kind": "response",
        "request_id": request_id,
        "ok": ok,
        "metrics": {
            "resident": True,
            "total_ms": total_ms,
            "ttft_ms": ttft_ms,
            "tool_latency_ms": tool_latency_ms,
            "tool_latency_scope": tool_latency_scope,
        },
    }
    if ok:
        response["payload"] = payload or {}
    else:
        assert error is not None
        response["error"] = {
            "type": type(error).__name__,
            "message": str(error),
        }
    return response


def process_envelope(
    envelope: dict[str, Any],
    services: ResidentBridge,
) -> dict[str, Any]:
    """Synchronous compatibility processor used by unit tests."""
    started = time.perf_counter()
    request_id = envelope.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        request_id = "invalid-request"
        return response_envelope(
            request_id,
            ok=False,
            error=ValueError("request_id must be a non-empty string"),
            total_ms=int((time.perf_counter() - started) * 1000),
        )

    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        return response_envelope(
            request_id,
            ok=False,
            error=ValueError("payload must be an object"),
            total_ms=int((time.perf_counter() - started) * 1000),
        )

    try:
        result = services.execute(payload)
        return response_envelope(
            request_id,
            ok=True,
            payload=result,
            total_ms=int((time.perf_counter() - started) * 1000),
        )
    except Exception as error:
        return response_envelope(
            request_id,
            ok=False,
            error=error,
            total_ms=int((time.perf_counter() - started) * 1000),
        )


def server_loop() -> int:
    services = ResidentBridge()
    cancellations = CancellationRegistry()
    output_lock = Lock()
    executor = ThreadPoolExecutor(
        max_workers=MAX_RESIDENT_WORKERS,
        thread_name_prefix="rachel-resident",
    )

    def write(message: dict[str, Any]) -> None:
        line = json.dumps(message, ensure_ascii=False)
        with output_lock:
            print(line, flush=True)

    write(
        {
            "kind": "event",
            "event": "runtime.ready",
            "request_id": None,
            "payload": {
                "resident": True,
                "protocol_version": PROTOCOL_VERSION,
                "streaming": True,
                "cancellable_generation": True,
            },
        }
    )

    def worker(envelope: dict[str, Any], request_id: str, cancel_event: Event) -> None:
        started = time.perf_counter()

        def emit(event: str, payload: dict[str, Any]) -> None:
            write(
                {
                    "kind": "event",
                    "event": event,
                    "request_id": request_id,
                    "payload": payload,
                }
            )

        try:
            payload = envelope.get("payload")
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")
            result, metrics = services.execute_live(payload, emit, cancel_event)
            write(
                response_envelope(
                    request_id,
                    ok=True,
                    payload=result,
                    total_ms=int((time.perf_counter() - started) * 1000),
                    ttft_ms=metrics.get("ttft_ms"),
                    tool_latency_ms=metrics.get("tool_latency_ms"),
                    tool_latency_scope=metrics.get("tool_latency_scope"),
                )
            )
        except Exception as error:
            write(
                response_envelope(
                    request_id,
                    ok=False,
                    error=error,
                    total_ms=int((time.perf_counter() - started) * 1000),
                )
            )
        finally:
            cancellations.remove(request_id)

    try:
        for raw in sys.stdin:
            line = raw.strip()
            if not line:
                continue

            try:
                envelope = json.loads(line)
                if not isinstance(envelope, dict):
                    raise ValueError("request envelope must be an object")
                request_id = envelope.get("request_id")
                if not isinstance(request_id, str) or not request_id.strip():
                    raise ValueError("request_id must be a non-empty string")
                payload = envelope.get("payload")
                if not isinstance(payload, dict):
                    raise ValueError("payload must be an object")
            except Exception as error:
                write(
                    response_envelope(
                        "invalid-request",
                        ok=False,
                        error=error,
                        total_ms=0,
                    )
                )
                continue

            if payload.get("action") == "cancel_all":
                cancelled_ids = cancellations.cancel_all()
                write(
                    response_envelope(
                        request_id,
                        ok=True,
                        payload={
                            "state": "cancel_requested",
                            "cancelled_request_ids": cancelled_ids,
                            "count": len(cancelled_ids),
                        },
                        total_ms=0,
                        ttft_ms=0,
                    )
                )
                continue

            cancel_event = cancellations.register(request_id)
            executor.submit(worker, envelope, request_id, cancel_event)
    finally:
        cancellations.cancel_all()
        executor.shutdown(wait=False, cancel_futures=True)

    return 0


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--server":
        return server_loop()
    return legacy_main()


if __name__ == "__main__":
    raise SystemExit(main())
