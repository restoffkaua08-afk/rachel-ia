from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from threading import Lock
from typing import Any

from filesystem_runtime import FilesystemRuntime
from runtime_paths import STATE


PROCESS_LOG_ROOT = STATE / "process-logs"


class ProcessRuntimeError(RuntimeError):
    pass


class ProcessRuntime:
    """Manage only development processes started by RACHEL itself."""

    def __init__(
        self,
        filesystem: FilesystemRuntime | None = None,
        log_root: Path | None = None,
    ) -> None:
        self.filesystem = filesystem or FilesystemRuntime()
        self.log_root = Path(log_root or PROCESS_LOG_ROOT).resolve()
        self.log_root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._items: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _which(name: str) -> str:
        value = shutil.which(name)
        if not value:
            raise ProcessRuntimeError(f"Required executable is unavailable: {name}")
        return value

    def _command(self, root: Path, profile: str) -> list[str]:
        selected = str(profile).strip().casefold()
        if selected == "python.module":
            if not (root / "__main__.py").is_file():
                raise ProcessRuntimeError("python.module requires __main__.py")
            return [sys.executable, "."]

        package = root / "package.json"
        if selected in {"node.dev", "node.start"}:
            if not package.is_file():
                raise ProcessRuntimeError("Node profile requires package.json")
            try:
                payload = json.loads(package.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise ProcessRuntimeError("Unable to parse package.json") from error
            scripts = payload.get("scripts", {})
            script = "dev" if selected == "node.dev" else "start"
            if not isinstance(scripts, dict) or script not in scripts:
                raise ProcessRuntimeError(f"package.json has no {script} script")
            if (root / "pnpm-lock.yaml").exists():
                return [self._which("pnpm"), "run", script]
            if (root / "yarn.lock").exists():
                return [self._which("yarn"), "run", script]
            return [self._which("npm"), "run", script]

        if selected == "rust.run":
            if not (root / "Cargo.toml").is_file():
                raise ProcessRuntimeError("rust.run requires Cargo.toml")
            return [self._which("cargo"), "run", "--locked"]

        raise ProcessRuntimeError("Unknown governed process profile")

    def start(
        self,
        scope: str,
        path: str,
        profile: str,
        approved: bool,
    ) -> dict[str, Any]:
        if not approved:
            raise PermissionError("Cyber approval is required to start a process")
        root = self.filesystem.target(scope, path)
        if not root.is_dir():
            raise ProcessRuntimeError("Process project root is not a directory")
        command = self._command(root, profile)
        process_id = "process_" + uuid.uuid4().hex
        stdout_path = self.log_root / f"{process_id}.stdout.log"
        stderr_path = self.log_root / f"{process_id}.stderr.log"
        stdout_handle = stdout_path.open("wb")
        stderr_handle = stderr_path.open("wb")

        try:
            process = subprocess.Popen(
                command,
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=stderr_handle,
                shell=False,
            )
        except Exception:
            stdout_handle.close()
            stderr_handle.close()
            raise

        item = {
            "process_id": process_id,
            "process": process,
            "scope": scope.casefold(),
            "path": path,
            "profile": profile.casefold(),
            "pid": process.pid,
            "started_at_ms": int(time.time() * 1000),
            "stdout_path": stdout_path,
            "stderr_path": stderr_path,
            "stdout_handle": stdout_handle,
            "stderr_handle": stderr_handle,
        }
        with self._lock:
            self._items[process_id] = item

        time.sleep(0.05)
        return self.status(process_id)

    def _item(self, process_id: str) -> dict[str, Any]:
        with self._lock:
            item = self._items.get(process_id)
        if item is None:
            raise ProcessRuntimeError("Unknown RACHEL-owned process")
        return item

    def status(self, process_id: str) -> dict[str, Any]:
        item = self._item(process_id)
        process: subprocess.Popen[bytes] = item["process"]
        returncode = process.poll()
        return {
            "process_id": process_id,
            "pid": item["pid"],
            "scope": item["scope"],
            "path": item["path"],
            "profile": item["profile"],
            "running": returncode is None,
            "returncode": returncode,
            "started_at_ms": item["started_at_ms"],
            "owned_by_rachel": True,
        }

    def list(self) -> dict[str, Any]:
        with self._lock:
            ids = list(self._items)
        items = [self.status(process_id) for process_id in ids]
        return {
            "count": len(items),
            "items": items,
            "scope": "rachel-owned-only",
        }

    def logs(self, process_id: str, maximum_bytes: int = 20_000) -> dict[str, Any]:
        item = self._item(process_id)
        limit = max(1_000, min(int(maximum_bytes), 100_000))
        for key in ("stdout_handle", "stderr_handle"):
            try:
                item[key].flush()
            except OSError:
                pass

        def tail(path: Path) -> str:
            if not path.exists():
                return ""
            data = path.read_bytes()
            return data[-limit:].decode("utf-8", errors="replace")

        return {
            **self.status(process_id),
            "stdout": tail(item["stdout_path"]),
            "stderr": tail(item["stderr_path"]),
            "maximum_bytes": limit,
        }

    def stop(self, process_id: str, approved: bool) -> dict[str, Any]:
        if not approved:
            raise PermissionError("Cyber approval is required to stop a process")
        item = self._item(process_id)
        process: subprocess.Popen[bytes] = item["process"]
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

        for key in ("stdout_handle", "stderr_handle"):
            try:
                item[key].close()
            except OSError:
                pass

        result = self.status(process_id)
        result["verified_stopped"] = not result["running"]
        return result
