from __future__ import annotations

from typing import Any

from samwell_runtime import SamwellRuntime


def lightweight_status(runtime: SamwellRuntime | None = None) -> dict[str, Any]:
    """Return the canonical dashboard-safe Samwell status projection.

    SamwellRuntime.status() is intentionally lightweight and must not execute command,
    Python-package or environment probes. Deep diagnostics remain explicit through
    SamwellRuntime.audit() or SamwellRuntime.deep_status().
    """
    return (runtime or SamwellRuntime()).status()
