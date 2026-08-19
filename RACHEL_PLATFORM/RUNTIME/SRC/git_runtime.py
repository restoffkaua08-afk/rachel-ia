from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

from filesystem_runtime import FilesystemRuntime


MAX_OUTPUT = 60_000
BRANCH_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}")


class GitRuntimeError(RuntimeError):
    pass


class GitRuntime:
    def __init__(
        self,
        filesystem: FilesystemRuntime | None = None,
        executable: str | None = None,
    ) -> None:
        self.filesystem = filesystem or FilesystemRuntime()
        self.executable = executable or shutil.which("git") or "git"

    def _repo(self, scope: str, path: str = ".") -> Path:
        root = self.filesystem.target(scope, path)
        if not root.is_dir():
            raise GitRuntimeError("Git target is not a directory")
        marker = root / ".git"
        if not marker.exists():
            raise GitRuntimeError("Directory is not a Git repository")
        if marker.is_symlink():
            raise GitRuntimeError("Git metadata symlink is blocked")
        return root

    @staticmethod
    def _relative_path(value: str) -> str:
        raw = str(value).strip().replace("\\", "/")
        relative = PurePosixPath(raw)
        if (
            not raw
            or relative.is_absolute()
            or ".." in relative.parts
            or any(part in {"", "."} for part in relative.parts)
        ):
            raise GitRuntimeError("Unsafe Git relative path")
        return relative.as_posix()

    @staticmethod
    def _branch(value: str) -> str:
        branch = str(value).strip()
        if not BRANCH_PATTERN.fullmatch(branch):
            raise GitRuntimeError("Invalid Git branch name")
        if branch.endswith("/") or "//" in branch or ".." in branch or "@{" in branch:
            raise GitRuntimeError("Unsafe Git branch name")
        return branch

    def _run(
        self,
        repo: Path,
        arguments: list[str],
        *,
        timeout: int = 120,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        try:
            process = subprocess.run(
                [self.executable, *arguments],
                cwd=repo,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise GitRuntimeError(f"Git execution failed: {error}") from error

        if check and process.returncode != 0:
            detail = (process.stderr or process.stdout).strip()[-4_000:]
            raise GitRuntimeError(
                f"Git command failed with code {process.returncode}: {detail}"
            )
        return process

    def status(self, scope: str, path: str = ".") -> dict[str, Any]:
        repo = self._repo(scope, path)
        branch = self._run(repo, ["branch", "--show-current"]).stdout.strip()
        status = self._run(
            repo,
            ["status", "--short", "--untracked-files=all"],
        ).stdout
        lines = [line for line in status.splitlines() if line.strip()]
        return {
            "scope": scope.casefold(),
            "path": path,
            "branch": branch or None,
            "clean": not lines,
            "changes": lines[:500],
            "truncated": len(lines) > 500,
        }

    def diff(
        self,
        scope: str,
        path: str = ".",
        *,
        staged: bool = False,
        files: list[str] | None = None,
    ) -> dict[str, Any]:
        repo = self._repo(scope, path)
        arguments = ["diff", "--no-ext-diff", "--unified=3"]
        if staged:
            arguments.append("--cached")
        if files:
            safe_files = [self._relative_path(item) for item in files]
            arguments.extend(["--", *safe_files])
        process = self._run(repo, arguments)
        output = process.stdout
        return {
            "scope": scope.casefold(),
            "path": path,
            "staged": staged,
            "diff": output[-MAX_OUTPUT:],
            "truncated": len(output) > MAX_OUTPUT,
        }

    def log(self, scope: str, path: str = ".", limit: int = 20) -> dict[str, Any]:
        repo = self._repo(scope, path)
        maximum = max(1, min(int(limit), 100))
        process = self._run(
            repo,
            [
                "log",
                f"-n{maximum}",
                "--date=iso-strict",
                "--pretty=format:%H%x09%an%x09%ad%x09%s",
            ],
        )
        items = []
        for line in process.stdout.splitlines():
            parts = line.split("\t", 3)
            if len(parts) == 4:
                items.append(
                    {
                        "sha": parts[0],
                        "author": parts[1],
                        "date": parts[2],
                        "subject": parts[3],
                    }
                )
        return {
            "scope": scope.casefold(),
            "path": path,
            "count": len(items),
            "items": items,
        }

    def branches(self, scope: str, path: str = ".") -> dict[str, Any]:
        repo = self._repo(scope, path)
        current = self._run(repo, ["branch", "--show-current"]).stdout.strip()
        process = self._run(repo, ["branch", "--format=%(refname:short)"])
        branches = [line.strip() for line in process.stdout.splitlines() if line.strip()]
        return {
            "scope": scope.casefold(),
            "path": path,
            "current": current or None,
            "branches": branches,
        }

    def stage(
        self,
        scope: str,
        path: str,
        files: list[str],
        approved: bool,
    ) -> dict[str, Any]:
        if not approved:
            raise PermissionError("Cyber approval is required to stage Git files")
        if not isinstance(files, list) or not files:
            raise GitRuntimeError("Git stage requires at least one file")
        safe_files = [self._relative_path(item) for item in files]
        repo = self._repo(scope, path)
        self._run(repo, ["add", "--", *safe_files])
        staged = self._run(repo, ["diff", "--cached", "--name-only", "--"]).stdout
        names = [line for line in staged.splitlines() if line.strip()]
        return {
            "scope": scope.casefold(),
            "path": path,
            "requested": safe_files,
            "staged": names,
            "verified": all(item in names for item in safe_files),
        }

    def commit(
        self,
        scope: str,
        path: str,
        message: str,
        approved: bool,
    ) -> dict[str, Any]:
        if not approved:
            raise PermissionError("Cyber approval is required to create a Git commit")
        clean_message = str(message).strip()
        if not clean_message or len(clean_message) > 500 or "\x00" in clean_message:
            raise GitRuntimeError("Invalid Git commit message")
        repo = self._repo(scope, path)
        staged = self._run(repo, ["diff", "--cached", "--name-only"]).stdout
        staged_files = [line for line in staged.splitlines() if line.strip()]
        if not staged_files:
            raise GitRuntimeError("There are no staged files to commit")
        self._run(repo, ["commit", "-m", clean_message], timeout=180)
        head = self._run(repo, ["rev-parse", "HEAD"]).stdout.strip()
        subject = self._run(repo, ["log", "-1", "--pretty=%s"]).stdout.strip()
        return {
            "scope": scope.casefold(),
            "path": path,
            "sha": head,
            "subject": subject,
            "files": staged_files,
            "verified": bool(head) and subject == clean_message.splitlines()[0],
        }

    def create_branch(
        self,
        scope: str,
        path: str,
        branch: str,
        approved: bool,
    ) -> dict[str, Any]:
        if not approved:
            raise PermissionError("Cyber approval is required to create a Git branch")
        safe_branch = self._branch(branch)
        repo = self._repo(scope, path)
        self._run(repo, ["branch", safe_branch])
        branches = self.branches(scope, path)["branches"]
        return {
            "scope": scope.casefold(),
            "path": path,
            "branch": safe_branch,
            "created": safe_branch in branches,
            "checked_out": False,
        }

    def checkout(
        self,
        scope: str,
        path: str,
        branch: str,
        approved: bool,
    ) -> dict[str, Any]:
        if not approved:
            raise PermissionError("Cyber approval is required to switch Git branches")
        safe_branch = self._branch(branch)
        repo = self._repo(scope, path)
        self._run(repo, ["switch", safe_branch])
        current = self._run(repo, ["branch", "--show-current"]).stdout.strip()
        return {
            "scope": scope.casefold(),
            "path": path,
            "branch": safe_branch,
            "current": current,
            "verified": current == safe_branch,
        }
