from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_SRC = ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"
CORE_SRC = ROOT / "RACHEL_CORE" / "src"
STATE = ROOT / "RACHEL_PLATFORM" / "STATE"

for source in (RUNTIME_SRC, CORE_SRC):
    value = str(source)
    if value not in sys.path:
        sys.path.insert(0, value)

os.environ.setdefault(
    "RACHEL_HOME",
    str(STATE / "core"),
)

os.environ.setdefault(
    "RACHEL_MODEL_PROVIDER",
    "mock",
)


def required_text(
    payload: dict[str, Any],
    key: str,
    maximum: int = 50_000,
) -> str:
    value = payload.get(key)

    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")

    value = value.strip()

    if not value:
        raise ValueError(f"{key} cannot be empty")

    if len(value) > maximum:
        raise ValueError(f"{key} exceeds {maximum} characters")

    return value


def optional_text(
    payload: dict[str, Any],
    key: str,
    maximum: int = 500,
) -> str | None:
    value = payload.get(key)

    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(f"{key} must be string or null")

    value = value.strip()

    if not value:
        return None

    if len(value) > maximum:
        raise ValueError(f"{key} exceeds {maximum} characters")

    return value


def execute(
    payload: dict[str, Any],
) -> dict[str, Any]:
    from cognitive_runtime import NedCognitiveBridge

    bridge = NedCognitiveBridge()
    action = payload.get("action")

    if action == "status":
        return bridge.status()

    if action == "chat":
        return bridge.chat(
            required_text(payload, "content"),
            optional_text(payload, "conversation_id"),
        )

    if action == "assist":
        return bridge.assist(
            required_text(payload, "content"),
            optional_text(payload, "conversation_id"),
            approval_id=optional_text(
                payload,
                "approval_id",
                maximum=200,
            ),
        )

    raise ValueError(
        f"Unsupported action: {action}"
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)

        if not isinstance(payload, dict):
            raise ValueError(
                "Bridge request must be an object"
            )

        result = execute(payload)

        print(
            json.dumps(
                {
                    "ok": True,
                    "payload": result,
                },
                ensure_ascii=False,
            )
        )

        return 0

    except Exception as error:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "type": type(error).__name__,
                        "message": str(error),
                    },
                },
                ensure_ascii=False,
            )
        )

        return 2


if __name__ == "__main__":
    raise SystemExit(main())
