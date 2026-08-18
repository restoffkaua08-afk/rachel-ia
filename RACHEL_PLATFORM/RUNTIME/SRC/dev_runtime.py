from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from filesystem_runtime import FilesystemRuntime


MAX_OUTPUT = 60_000


class DevRuntimeError(RuntimeError):
    pass


class DevRuntime:
    """Typed project validation commands selected from project metadata.

    This runtime never accepts an arbitrary shell command. It detects a known
    project family and maps a semantic operation (test/build/lint/typecheck) to
    a bounded executable/argument list. Execution remains a Cyber-governed
    effect in ToolCoordinator.
    """

    def __init__(self, filesystem: FilesystemRuntime | None = None) -> None:
        self.filesystem = filesystem or FilesystemRuntime()

    def project_root(self, scope: str, path: str = ".") -> Path:
        root = self.filesystem.target(scope, path)
        if not root.is_dir():
            raise DevRuntimeError("Project target is not a directory")
        return root

    def detect(self, scope: str, path: str = ".") -> dict[str, Any]:
        root = self.project_root(scope, path)
        package = root / "package.json"
        cargo = root / "Cargo.toml"
        pyproject = root / "pyproject.toml"
        requirements = root / "requirements.txt"

        scripts: dict[str, Any] = {}
        package_manager = None
        if package.is_file():
            try:
                payload = json.loads(package.read_text(encoding="utf-8"))
                if isinstance(payload.get("scripts"), dict):
                    scripts = dict(payload["scripts"])
            except (OSError, json.JSONDecodeError):
                scripts = {}
            if (root / "pnpm-lock.yaml").exists():
                package_manager = "pnpm"
            elif (root / "yarn.lock").exists():
                package_manager = "yarn"
            else:
                package_manager = "npm"

        families = []
        if package.is_file():
            families.append("node")
        if cargo.is_file():
            families.append("rust")
        if pyproject.is_file() or requirements.is_file() or any(root.glob("*.py")):
            families.append("python")

        return {
            "scope": scope.casefold(),
            "path": path,
            "families": families,
            "primary": families[0] if families else None,
            "package_manager": package_manager,
            "scripts": sorted(str(key) for key in scripts),
            "files": {
                "package_json": package.is_file(),
                "cargo_toml": cargo.is_file(),
                "pyproject_toml": pyproject.is_file(),
                "requirements_txt": requirements.is_file(),
            },
        }

    @staticmethod
    def _package_payload(root: Path) -> dict[str, Any]:
        try:
            payload = json.loads((root / "package.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise DevRuntimeError("Unable to parse package.json") from error
        if not isinstance(payload, dict):
            raise DevRuntimeError("package.json root must be an object")
        return payload

    @staticmethod
    def _which(executable: str) -> str:
        resolved = shutil.which(executable)
        if not resolved:
            raise DevRuntimeError(f"Required executable is unavailable: {executable}")
        return resolved

    def _node_command(self, root: Path, operation: str) -> list[str]:
        payload = self._package_payload(root)
        scripts = payload.get("scripts", {})
        if not isinstance(scripts, dict):
            scripts = {}

        aliases = {
            "test": ["test"],
            "build": ["build"],
            "lint": ["lint"],
            "typecheck": ["typecheck", "type-check", "check:types", "types"],
        }
        script = next((name for name in aliases[operation] if name in scripts), None)
        if script is None:
            raise DevRuntimeError(
                f"package.json does not define a supported {operation} script"
            )

        if (root / "pnpm-lock.yaml").exists():
            return [self._which("pnpm"), "run", script]
        if (root / "yarn.lock").exists():
            return [self._which("yarn"), "run", script]
        return [self._which("npm"), "run", script]

    def _rust_command(self, operation: str) -> list[str]:
        cargo = self._which("cargo")
        mapping = {
            "test": [cargo, "test", "--locked"],
            "build": [cargo, "build", "--locked"],
            "lint": [cargo, "clippy", "--locked", "--", "-D", "warnings"],
            "typecheck": [cargo, "check", "--locked"],
        }
        return mapping[operation]

    def _python_command(self, root: Path, operation: str) -> list[str]:
        python = sys.executable
        if operation == "test":
            if (root / "pytest.ini").exists() or (root / "conftest.py").exists():
                return [python, "-m", "pytest", "-q"]
            return [python, "-m", "unittest", "discover"]
        if operation == "build":
            source = "src" if (root / "src").is_dir() else "."
            return [python, "-m", "compileall", "-q", source]
        if operation == "lint":
            if shutil.which("ruff"):
                return [self._which("ruff"), "check", "."]
            raise DevRuntimeError("No supported Python linter is available")
        if operation == "typecheck":
            if shutil.which("mypy"):
                return [self._which("mypy"), "."]
            if shutil.which("pyright"):
                return [self._which("pyright"), "."]
            raise DevRuntimeError("No supported Python type checker is available")
        raise DevRuntimeError(f"Unsupported Python operation: {operation}")

    def plan(self, scope: str, path: str, operation: str) -> dict[str, Any]:
        normalized = str(operation).strip().casefold()
        if normalized not in {"test", "build", "lint", "typecheck"}:
            raise DevRuntimeError("Unknown development operation")
        root = self.project_root(scope, path)
        detected = self.detect(scope, path)
        families = detected["families"]
        if not families:
            raise DevRuntimeError("Unable to detect a supported project family")

        # Prefer the project family with the strongest explicit project manifest.
        if "node" in families:
            command = self._node_command(root, normalized)
            family = "node"
        elif "rust" in families:
            command = self._rust_command(normalized)
            family = "rust"
        else:
            command = self._python_command(root, normalized)
            family = "python"

        return {
            "scope": scope.casefold(),
            "path": path,
            "operation": normalized,
            "family": family,
            "executable": Path(command[0]).name,
            "arguments": command[1:],
            "shell": False,
        }

    def run(
        self,
        scope: str,
        path: str,
        operation: str,
        approved: bool,
        timeout_seconds: int = 300,
    ) -> dict[str, Any]:
        if not approved:
            raise PermissionError("Cyber approval is required to execute project validation")
        root = self.project_root(scope, path)
        plan = self.plan(scope, path, operation)

        # Reconstruct from the validated semantic plan; no user-supplied command.
        family = plan["family"]
        if family == "node":
            command = self._node_command(root, plan["operation"])
        elif family == "rust":
            command = self._rust_command(plan["operation"])
        else:
            command = self._python_command(root, plan["operation"])

        timeout = max(10, min(int(timeout_seconds), 900))
        try:
            process = subprocess.run(
                command,
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise DevRuntimeError(f"Project validation failed to execute: {error}") from error

        stdout = process.stdout or ""
        stderr = process.stderr or ""
        return {
            **plan,
            "returncode": process.returncode,
            "successful": process.returncode == 0,
            "stdout": stdout[-MAX_OUTPUT:],
            "stderr": stderr[-MAX_OUTPUT:],
            "stdout_truncated": len(stdout) > MAX_OUTPUT,
            "stderr_truncated": len(stderr) > MAX_OUTPUT,
            "timeout_seconds": timeout,
        }
