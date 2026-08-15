from __future__ import annotations

import os
import shutil
import sys

from pathlib import Path
from typing import Any


class RuntimePathError(RuntimeError):
    pass


def _environment_path(
    name: str,
) -> Path | None:
    raw = os.getenv(name)

    if raw is None:
        return None

    clean = raw.strip()

    if not clean:
        return None

    return Path(
        clean
    ).expanduser().resolve()


def _valid_runtime_root(
    path: Path,
) -> bool:
    return (
        (
            path
            / "RACHEL_PLATFORM"
            / "CONFIG"
        ).is_dir()
        and (
            path
            / "RACHEL_PLATFORM"
            / "RUNTIME"
            / "SRC"
        ).is_dir()
    )


def _default_runtime_root() -> Path:
    configured = _environment_path(
        "RACHEL_RUNTIME_ROOT"
    )

    if configured is not None:
        if not _valid_runtime_root(
            configured
        ):
            raise RuntimePathError(
                "RACHEL_RUNTIME_ROOT does not contain "
                "a valid Rachel runtime."
            )

        return configured


    candidates: list[Path] = []


    if getattr(
        sys,
        "frozen",
        False,
    ):
        bundle = getattr(
            sys,
            "_MEIPASS",
            None,
        )

        if bundle:
            candidates.append(
                Path(bundle).resolve()
            )

        candidates.append(
            Path(
                sys.executable
            ).resolve().parent
        )


    candidates.append(
        Path(
            __file__
        ).resolve().parents[3]
    )


    for candidate in candidates:
        if _valid_runtime_root(
            candidate
        ):
            return candidate


    raise RuntimePathError(
        "Unable to locate the Rachel runtime root."
    )


ROOT = _default_runtime_root()

PLATFORM = (
    ROOT
    / "RACHEL_PLATFORM"
)

RUNTIME_SRC = (
    PLATFORM
    / "RUNTIME"
    / "SRC"
)

CORE_SRC = (
    ROOT
    / "RACHEL_CORE"
    / "src"
)

SOURCE_CONFIG = (
    PLATFORM
    / "CONFIG"
)


_state_override = _environment_path(
    "RACHEL_STATE_ROOT"
)

PORTABLE_MODE = (
    _state_override
    is not None
)


STATE = (
    _state_override
    if _state_override is not None
    else PLATFORM / "STATE"
)

STATE_ROOT = STATE


if PORTABLE_MODE:
    DATA_ROOT = STATE.parent
    CONFIG = DATA_ROOT / "CONFIG"
    LOGS = DATA_ROOT / "LOGS"
    WORKSPACE = DATA_ROOT / "WORKSPACE"
else:
    DATA_ROOT = PLATFORM
    CONFIG = SOURCE_CONFIG
    LOGS = PLATFORM / "LOGS"
    WORKSPACE = ROOT / "RACHEL_WORKSPACE"


def _seed_config() -> None:
    if not PORTABLE_MODE:
        return

    if not SOURCE_CONFIG.is_dir():
        raise RuntimePathError(
            "Runtime CONFIG directory is missing."
        )

    CONFIG.mkdir(
        parents=True,
        exist_ok=True,
    )

    for source in SOURCE_CONFIG.rglob("*"):
        relative = source.relative_to(
            SOURCE_CONFIG
        )

        target = CONFIG / relative

        if source.is_dir():
            target.mkdir(
                parents=True,
                exist_ok=True,
            )
            continue

        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not target.exists():
            shutil.copy2(
                source,
                target,
            )


if PORTABLE_MODE:
    STATE.mkdir(
        parents=True,
        exist_ok=True,
    )

    LOGS.mkdir(
        parents=True,
        exist_ok=True,
    )

    WORKSPACE.mkdir(
        parents=True,
        exist_ok=True,
    )

    _seed_config()


os.environ.setdefault(
    "RACHEL_HOME",
    str(
        STATE
        / "core"
    ),
)


def describe_paths() -> dict[str, Any]:
    return {
        "runtime_root": str(ROOT),
        "platform": str(PLATFORM),
        "runtime_src": str(RUNTIME_SRC),
        "core_src": str(CORE_SRC),
        "source_config": str(SOURCE_CONFIG),
        "state_root": str(STATE_ROOT),
        "state": str(STATE),
        "config": str(CONFIG),
        "logs": str(LOGS),
        "workspace": str(WORKSPACE),
        "data_root": str(DATA_ROOT),
        "portable_mode": PORTABLE_MODE,
        "rachel_home": os.getenv(
            "RACHEL_HOME"
        ),
    }
