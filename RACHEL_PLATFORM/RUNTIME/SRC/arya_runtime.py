from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from runtime_paths import PORTABLE_MODE, ROOT, WORKSPACE

ARYA_ROOT = WORKSPACE if PORTABLE_MODE else ROOT
ALLOWED_READ = {"git", "python", "py", "node", "npm", "cargo", "rustc", "cmake", "ffmpeg"}
BLOCKED_ARGUMENTS = {"--force", "-force", "--delete", "--hard", "format", "shutdown", "reboot"}


def safe_cwd(value: str | None) -> Path:
    path = (Path(value) if value else ARYA_ROOT).resolve()
    try:
        path.relative_to(ARYA_ROOT)
    except ValueError as error:
        raise ValueError("Arya can only operate inside the Rachel workspace") from error
    return path


def run(command: str, arguments: list[str], cwd: str | None, approved: bool) -> dict:
    executable = Path(command).name.casefold().removesuffix(".exe")
    normalized = {item.casefold() for item in arguments}
    if normalized & BLOCKED_ARGUMENTS:
        raise PermissionError("Cyber blocked a high-risk argument")
    read_only = executable in ALLOWED_READ and not normalized.intersection({"commit", "push", "install", "add", "run", "build"})
    if not read_only and not approved:
        raise PermissionError("Cyber requires explicit approval for this command")
    process = subprocess.run(
        [command, *arguments], cwd=safe_cwd(cwd), capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=300, shell=False,
    )
    return {
        "command": command, "arguments": arguments, "returncode": process.returncode,
        "stdout": process.stdout[-20000:], "stderr": process.stderr[-20000:],
        "approved": approved, "read_only": read_only,
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
            print(json.dumps([p.name for p in sorted(folder.iterdir())], ensure_ascii=False, indent=2))
            return 0
        result = run(args.command, args.arguments, args.cwd, args.approved)
    except (OSError, ValueError, PermissionError, subprocess.TimeoutExpired) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 3
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result["returncode"]


if __name__ == "__main__":
    raise SystemExit(main())
