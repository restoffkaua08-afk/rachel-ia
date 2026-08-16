from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


from runtime_paths import CONFIG, LOGS, PLATFORM, PORTABLE_MODE, ROOT, STATE


@dataclass
class OrganHealth:
    organ_id: str
    source_exists: bool
    manifest_exists: bool
    git_exists: bool
    status: str
    detail: str


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def organs_from_registry() -> list[dict[str, Any]]:
    payload = load_json(CONFIG / "organs.registry.json")
    return list(payload.get("orgaos", []))


def resolve_source(organ: dict[str, Any]) -> Path:
    alias = str(organ.get("alias") or organ.get("id") or "").replace("rachel.", "")
    junction = PLATFORM / "ORGAOS" / alias / "fonte"
    if junction.exists():
        return junction.resolve()
    candidates = list((ROOT / "FONTES" / "REPOSITORIOS").glob("*"))
    normalized = alias.replace("-", "").lower()
    for candidate in candidates:
        if candidate.name.replace("-", "").replace("_", "").lower() == normalized:
            return candidate.resolve()
    return junction


def inspect_organ(organ: dict[str, Any]) -> OrganHealth:
    organ_id = str(organ.get("alias") or organ.get("id") or organ.get("nome_original") or "unknown")
    alias = organ_id.replace("rachel.", "")
    source = resolve_source(organ)
    manifest = PLATFORM / "ORGAOS" / alias / "organ.json"
    source_exists = source.exists()
    manifest_exists = manifest.exists()

    git_exists = (
        (source / ".git").exists()
        if source_exists
        else False
    )

    packaged = (
        PORTABLE_MODE
        and manifest_exists
        and not source_exists
    )

    ok = (
        source_exists
        and manifest_exists
    ) or packaged

    if (
        source_exists
        and manifest_exists
    ):
        detail = str(
            source
        )

    elif packaged:
        detail = (
            "packaged organ manifest; "
            "development source checkout "
            "not bundled"
        )

    else:
        detail = (
            "source or manifest missing"
        )

    return OrganHealth(
        organ_id=organ_id,
        source_exists=source_exists,
        manifest_exists=manifest_exists,
        git_exists=git_exists,
        status=(
            "available"
            if ok
            else "failed"
        ),
        detail=detail,
    )


def audit() -> int:
    STATE.mkdir(parents=True, exist_ok=True)
    results = [inspect_organ(item) for item in organs_from_registry()]
    payload = {
        "schema_version": "1.0",
        "generated_at_epoch": int(time.time()),
        "python": sys.version,
        "platform": sys.platform,
        "organs": [asdict(item) for item in results],
        "summary": {
            "total": len(results),
            "available": sum(item.status == "available" for item in results),
            "failed": sum(item.status == "failed" for item in results),
        },
    }
    output = STATE / "organs.health.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(f"Health report: {output}")
    return 0 if payload["summary"]["failed"] == 0 else 1


def show_routes() -> int:
    print(json.dumps(load_json(CONFIG / "capability.routes.json"), ensure_ascii=False, indent=2))
    return 0


def doctor() -> int:
    checks = {
        "python": sys.version.split()[0],
        "root": str(ROOT),
        "registry": (CONFIG / "organs.registry.json").exists(),
        "profiles": (CONFIG / "runtime.profiles.json").exists(),
        "routes": (CONFIG / "capability.routes.json").exists(),
        "secrets_in_environment": bool(os.getenv("RACHEL_SECRETS_CONFIGURED")),
    }
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if all(v for k, v in checks.items() if k not in {"python", "root", "secrets_in_environment"}) else 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="rachel-supervisor")
    parser.add_argument("command", choices=["audit", "doctor", "routes"])
    args = parser.parse_args()
    return {"audit": audit, "doctor": doctor, "routes": show_routes}[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
