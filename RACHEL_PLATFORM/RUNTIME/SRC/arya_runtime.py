from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from runtime_paths import PORTABLE_MODE, ROOT, WORKSPACE


ARYA_ROOT = WORKSPACE if PORTABLE_MODE else ROOT
FALLBACK_EXECUTABLES = {
    "git",
    "python",
    "py",
    "node",
    "npm",
    "pnpm",
    "cargo",
    "rustc",
    "cmake",
    "ffmpeg",
}
BLOCKED_SHELLS = {
    "powershell",
    "pwsh",
    "cmd",
    "bash",
    "sh",
    "zsh",
    "wsl",
    "cscript",
    "wscript",
}
MAX_ARGUMENTS = 128
MAX_ARGUMENT_LENGTH = 8_000


def safe_cwd(value: str | None) -> Path:
    path = (Path(value) if value else ARYA_ROOT).resolve()
    try:
        path.relative_to(ARYA_ROOT)
    except ValueError as error:
        raise ValueError("Arya can only operate inside the Rachel workspace") from error
    if not path.is_dir():
        raise ValueError("Arya working directory does not exist")
    return path


def _resolve_executable(command: str) -> tuple[str, str]:
    raw = str(command).strip()
    if not raw or "\x00" in raw:
        raise PermissionError("Invalid fallback executable")
    if "/" in raw or "\\" in raw or Path(raw).name != raw:
        raise PermissionError(
            "arya.run accepts executable names from PATH only; absolute or relative executable paths are blocked"
        )

    basename = Path(raw).name.casefold().removesuffix(".exe")
    if basename in BLOCKED_SHELLS:
        raise PermissionError("Shell interpreters are blocked in arya.run")
    if basename not in FALLBACK_EXECUTABLES:
        raise PermissionError("Executable is not allowed in the controlled fallback")

    resolved = shutil.which(raw)
    if not resolved:
        resolved = shutil.which(f"{basename}.exe")
    if not resolved:
        raise FileNotFoundError(f"Fallback executable is unavailable: {raw}")
    return resolved, basename


def _validate_arguments(arguments: list[str]) -> list[str]:
    if not isinstance(arguments, list) or not all(isinstance(item, str) for item in arguments):
        raise ValueError("arguments must be an array of strings")
    if len(arguments) > MAX_ARGUMENTS:
        raise ValueError("Too many fallback arguments")
    output = []
    for item in arguments:
        if "\x00" in item or len(item) > MAX_ARGUMENT_LENGTH:
            raise ValueError("Invalid fallback argument")
        output.append(item)
    return output


def run(command: str, arguments: list[str], cwd: str | None, approved: bool) -> dict:
    """Controlled escape hatch for cases that have no typed capability.

    Common filesystem, Git, build/test/lint/typecheck and managed-process actions
    have dedicated tools and must not be tunneled through shell interpreters.
    This fallback always requires explicit Cyber approval and only resolves a
    small executable allowlist from PATH with ``shell=False``.
    """
    if not approved:
        raise PermissionError("Cyber requires explicit approval for arya.run fallback")

    executable, basename = _resolve_executable(command)
    safe_arguments = _validate_arguments(arguments)
    process = subprocess.run(
        [executable, *safe_arguments],
        cwd=safe_cwd(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        shell=False,
    )
    return {
        "command": basename,
        "arguments": safe_arguments,
        "returncode": process.returncode,
        "stdout": process.stdout[-20_000:],
        "stderr": process.stderr[-20_000:],
        "approved": True,
        "read_only": False,
        "fallback": True,
        "shell": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="arya")
    sub = parser.add_subparsers(dest="action", required=True)
    execute = sub.add_parser("run")
    execute.add_argument("command")
    execute.add_argument("arguments", nargs="*")
    execute.add_argument("--cwd")
    execute.add_argument("--approved", action="store_true")
    listing = sub.add_parser("list")
    listing.add_argument("path", nargs="?", default=".")
    args, unknown = parser.parse_known_args()
    if args.action == "run" and unknown:
        args.arguments.extend(unknown)
    elif unknown:
        parser.error(f"unrecognized arguments: {' '.join(unknown)}")

    try:
        if args.action == "list":
            folder = safe_cwd(args.path)
            print(
                json.dumps(
                    [p.name for p in sorted(folder.iterdir())],
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        result = run(args.command, args.arguments, args.cwd, args.approved)
    except (
        OSError,
        ValueError,
        PermissionError,
        subprocess.TimeoutExpired,
    ) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 3

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result["returncode"]


if __name__ == "__main__":
    raise SystemExit(main())
