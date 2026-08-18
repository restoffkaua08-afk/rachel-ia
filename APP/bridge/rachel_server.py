from __future__ import annotations

import json
import sys
import time
from typing import Any, Callable

from rachel_bridge import (
    execute as legacy_execute,
    main as legacy_main,
    optional_object,
    optional_text,
    required_text,
)
from cognitive_runtime import NedCognitiveBridge


PROTOCOL_VERSION = 1


class ResidentBridge:
    """Long-lived desktop service container.

    The cognitive bridge is created once and reused for all chat/assist requests,
    preserving the provider, Core container, memory handles and tool coordinator
    across the desktop session. Legacy administrative actions stay compatible
    through the existing bridge while they are migrated incrementally.
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

    def status(self) -> dict[str, Any]:
        return {
            "resident": True,
            "protocol_version": PROTOCOL_VERSION,
            "requests": self.requests,
            "uptime_ms": max(0, int((time.time() - self.started_at) * 1000)),
            "cognitive": self.cognitive.status(),
        }

    def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.requests += 1
        action = payload.get("action")

        if action == "resident_status":
            return self.status()

        if action == "status":
            status = self.cognitive.status()
            status["resident_runtime"] = True
            status["resident_requests"] = self.requests
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


def response_envelope(
    request_id: str,
    *,
    ok: bool,
    payload: dict[str, Any] | None = None,
    error: Exception | None = None,
    total_ms: int,
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "kind": "response",
        "request_id": request_id,
        "ok": ok,
        "metrics": {
            "resident": True,
            "total_ms": total_ms,
            "ttft_ms": total_ms,
            "tool_latency_ms": None,
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
    started = time.perf_counter()

    request_id = envelope.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        request_id = "invalid-request"
        error = ValueError("request_id must be a non-empty string")
        return response_envelope(
            request_id,
            ok=False,
            error=error,
            total_ms=int((time.perf_counter() - started) * 1000),
        )

    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        error = ValueError("payload must be an object")
        return response_envelope(
            request_id,
            ok=False,
            error=error,
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

    ready = {
        "kind": "event",
        "event": "runtime.ready",
        "request_id": None,
        "payload": {
            "resident": True,
            "protocol_version": PROTOCOL_VERSION,
        },
    }
    print(json.dumps(ready, ensure_ascii=False), flush=True)

    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue

        try:
            envelope = json.loads(line)
            if not isinstance(envelope, dict):
                raise ValueError("request envelope must be an object")
            response = process_envelope(envelope, services)
        except Exception as error:
            response = response_envelope(
                "invalid-request",
                ok=False,
                error=error,
                total_ms=0,
            )

        print(json.dumps(response, ensure_ascii=False), flush=True)

    return 0


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--server":
        return server_loop()
    return legacy_main()


if __name__ == "__main__":
    raise SystemExit(main())
