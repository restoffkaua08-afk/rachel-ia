from __future__ import annotations

import json
import os
import sys

from dataclasses import asdict
from pathlib import Path
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(
        encoding="utf-8"
    )


DEFAULT_ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(
    os.environ.get("RACHEL_RUNTIME_ROOT")
    or DEFAULT_ROOT
).expanduser().resolve()
RUNTIME_SRC = ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"
CORE_SRC = ROOT / "RACHEL_CORE" / "src"


for source in (
    RUNTIME_SRC,
    CORE_SRC,
):
    value = str(source)

    if value not in sys.path:
        sys.path.insert(
            0,
            value,
        )


from runtime_paths import STATE

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
        raise ValueError(
            f"{key} must be a string"
        )

    value = value.strip()

    if not value:
        raise ValueError(
            f"{key} cannot be empty"
        )

    if len(value) > maximum:
        raise ValueError(
            f"{key} exceeds {maximum} characters"
        )

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
        raise ValueError(
            f"{key} must be string or null"
        )

    value = value.strip()

    if not value:
        return None

    if len(value) > maximum:
        raise ValueError(
            f"{key} exceeds {maximum} characters"
        )

    return value


def bounded_int(
    payload: dict[str, Any],
    key: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    value = payload.get(
        key,
        default,
    )

    if (
        isinstance(value, bool)
        or not isinstance(value, int)
    ):
        raise ValueError(
            f"{key} must be an integer"
        )

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


def health_snapshot() -> dict[str, Any]:
    from supervisor import (
        inspect_organ,
        organs_from_registry,
    )

    organs = [
        asdict(
            inspect_organ(item)
        )
        for item in organs_from_registry()
    ]

    available = sum(
        item["status"] == "available"
        for item in organs
    )

    return {
        "total": len(organs),
        "available": available,
        "failed": len(organs) - available,
        "items": organs,
    }


def dashboard() -> dict[str, Any]:
    from bran_cognitive import CognitiveMemory
    from cognitive_runtime import NedCognitiveBridge
    from security_panel import SecurityPanel
    from voice_diagnostics import doctor

    return {
        "runtime": NedCognitiveBridge().status(),
        "cyber": SecurityPanel().snapshot(
            status="pending",
            limit=50,
        ),
        "memory": CognitiveMemory().status(),
        "voice": doctor(
            include_hardware=False
        ),
        "health": health_snapshot(),
    }


def execute(
    payload: dict[str, Any],
) -> dict[str, Any]:

    action = payload.get(
        "action"
    )


    if action == "dashboard":
        return dashboard()


    if action == "status":
        from cognitive_runtime import NedCognitiveBridge

        return NedCognitiveBridge().status()


    if action == "chat":
        from cognitive_runtime import NedCognitiveBridge

        return NedCognitiveBridge().chat(
            required_text(
                payload,
                "content",
            ),
            optional_text(
                payload,
                "conversation_id",
            ),
        )


    if action == "assist":
        from cognitive_runtime import NedCognitiveBridge

        return NedCognitiveBridge().assist(
            required_text(
                payload,
                "content",
            ),
            optional_text(
                payload,
                "conversation_id",
            ),
            approval_id=optional_text(
                payload,
                "approval_id",
                maximum=200,
            ),
        )


    if action == "security_snapshot":
        from security_panel import SecurityPanel

        return SecurityPanel().snapshot(
            status="pending",
            limit=bounded_int(
                payload,
                "limit",
                50,
                1,
                100,
            ),
        )


    if action == "security_decide":
        from security_panel import SecurityPanel

        approval_id = required_text(
            payload,
            "approval_id",
            200,
        )

        allow = payload.get(
            "allow"
        )

        if not isinstance(
            allow,
            bool,
        ):
            raise ValueError(
                "allow must be boolean"
            )

        confirmation = required_text(
            payload,
            "confirmation",
            500,
        )

        panel = SecurityPanel()

        card = panel.show(
            approval_id
        )

        mode = (
            "approve"
            if allow
            else "deny"
        )

        expected = (
            card
            .get("confirmation", {})
            .get(mode)
        )

        if (
            not isinstance(
                expected,
                str,
            )
            or confirmation != expected
        ):
            raise ValueError(
                "Explicit Cyber confirmation does not match"
            )

        return panel.decide(
            approval_id,
            allow,
        )


    if action == "memory_status":
        from bran_cognitive import CognitiveMemory

        return CognitiveMemory().status()


    if action == "memory_search":
        from bran_cognitive import CognitiveMemory

        return {
            "items": CognitiveMemory().search(
                required_text(
                    payload,
                    "query",
                    5_000,
                ),
                bounded_int(
                    payload,
                    "limit",
                    10,
                    1,
                    50,
                ),
            )
        }


    if action == "voice_status":
        from voice_diagnostics import doctor

        include_hardware = payload.get(
            "include_hardware",
            True,
        )

        if not isinstance(
            include_hardware,
            bool,
        ):
            raise ValueError(
                "include_hardware must be boolean"
            )

        return doctor(
            include_hardware=include_hardware
        )


    if action == "health":
        return health_snapshot()


    raise ValueError(
        f"Unsupported action: {action}"
    )


def main() -> int:
    try:
        payload = json.load(
            sys.stdin
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "Bridge request must be an object"
            )

        result = execute(
            payload
        )

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
    raise SystemExit(
        main()
    )
