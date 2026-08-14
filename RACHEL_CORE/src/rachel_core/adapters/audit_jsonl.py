from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

from ..domain.models import utc_now
from ..privacy import redact


class JsonlAuditAdapter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def record(self, event: str, correlation_id: str, data: dict[str, Any]) -> None:
        entry = {
            "timestamp": utc_now(),
            "event": event,
            "correlation_id": correlation_id,
            "data": redact(data),
        }
        encoded = json.dumps(entry, ensure_ascii=False, separators=(",", ":"))
        with self._lock, self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded + "\n")

