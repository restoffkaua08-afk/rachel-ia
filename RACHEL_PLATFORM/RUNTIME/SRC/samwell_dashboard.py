from __future__ import annotations

from typing import Any

from samwell_runtime import SamwellRuntime


def lightweight_status(runtime: SamwellRuntime | None = None) -> dict[str, Any]:
    """Return dashboard-safe Samwell metadata without executing dependency probes.

    The dashboard is a status projection, not a dependency audit. Expensive command,
    Python-package and environment probes remain available through SamwellRuntime.audit()
    and SamwellRuntime.status() when an explicit deep diagnostic is requested.
    """
    service = runtime or SamwellRuntime()
    catalog = service.catalog
    dependencies = list(catalog.get("dependencies", []))
    modes = catalog.get("modes", {})

    return {
        "member": {
            "id": "samwell",
            "name": "Samwell",
            "sector": "Dependencias, Ambientes e Portabilidade",
            "state": "operational",
        },
        "status_mode": "lightweight",
        "deep_audit_performed": False,
        "dependency_catalog": {
            "total": len(dependencies),
            "mode_count": len(modes),
            "schema_version": catalog.get("schema_version"),
        },
        "portable_runtime": {
            "internal_term": "frozen",
            "display_name": "Portable Runtime",
            "managed_by": "samwell",
            "external_python_required": False,
            **service._portable_probe(),
        },
        "requires_cyber_for_mutation": True,
        "execution_enabled": False,
        "automatic_install": False,
        "automatic_update": False,
        "automatic_remove": False,
        "automatic_repair": False,
        "training_execution_enabled": False,
        "weights_modified": False,
    }
