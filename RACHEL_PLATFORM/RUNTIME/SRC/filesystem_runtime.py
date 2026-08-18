from __future__ import annotations

import hashlib
import os
import re
import shutil
import time
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

from runtime_paths import STATE, WORKSPACE


MAX_TEXT_BYTES = 1_000_000
MAX_LIST_ENTRIES = 500
MAX_SEARCH_FILES = 300
BACKUP_ROOT = STATE / "filesystem-backups"
SCOPE_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")


class FilesystemError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FilesystemRuntime:
    """Typed filesystem operations constrained to explicit named scopes.

    Built-in scopes are local defaults. Additional project folders can be granted
    only for the lifetime of this runtime process. Session grants are never
    persisted by this class and require Cyber approval before being installed.
    The model always uses a scope name plus a relative path after the grant.
    """

    def __init__(
        self,
        scopes: dict[str, Path] | None = None,
        backup_root: Path | None = None,
    ) -> None:
        home = Path.home().resolve()
        defaults = {
            "workspace": WORKSPACE.resolve(),
            "desktop": (home / "Desktop").resolve(),
            "documents": (home / "Documents").resolve(),
            "downloads": (home / "Downloads").resolve(),
        }
        supplied = scopes or defaults
        self.scopes = {
            str(name).casefold(): Path(root).expanduser().resolve()
            for name, root in supplied.items()
        }
        if "workspace" not in self.scopes:
            raise FilesystemError("workspace scope is required")
        self.builtin_scopes = frozenset(self.scopes)
        self.session_scopes: set[str] = set()
        self.backup_root = Path(backup_root or BACKUP_ROOT).resolve()
        self.scopes["workspace"].mkdir(parents=True, exist_ok=True)
        self.backup_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _scope_name(name: str) -> str:
        key = str(name).strip().casefold()
        if not SCOPE_NAME_PATTERN.fullmatch(key):
            raise FilesystemError(
                "Scope name must contain 3-64 lowercase letters, numbers, '.', '_' or '-'"
            )
        return key

    def scope_names(self) -> list[str]:
        return sorted(self.scopes)

    def grant_scope(self, name: str, root: str, approved: bool) -> dict[str, Any]:
        if not approved:
            raise PermissionError("Cyber approval is required to grant a filesystem scope")
        key = self._scope_name(name)
        if key in self.builtin_scopes:
            raise FilesystemError("Built-in filesystem scopes cannot be replaced")
        candidate = Path(str(root)).expanduser()
        if not candidate.is_absolute():
            raise FilesystemError("Granted folder must be an absolute path")
        resolved = candidate.resolve(strict=True)
        if not resolved.is_dir():
            raise FilesystemError("Granted filesystem scope must be an existing directory")
        if resolved.is_symlink():
            raise FilesystemError("Symbolic links cannot be granted as filesystem scopes")
        if resolved == self.backup_root or self.backup_root in resolved.parents:
            raise FilesystemError("Rachel internal backup storage cannot become a user scope")
        self.scopes[key] = resolved
        self.session_scopes.add(key)
        return {
            "name": key,
            "granted": True,
            "session_only": True,
            "persistent": False,
            "available": True,
        }

    def revoke_scope(self, name: str, approved: bool) -> dict[str, Any]:
        if not approved:
            raise PermissionError("Cyber approval is required to revoke a filesystem scope")
        key = str(name).strip().casefold()
        if key in self.builtin_scopes:
            raise FilesystemError("Built-in filesystem scopes cannot be revoked")
        existed = key in self.session_scopes
        self.session_scopes.discard(key)
        if existed:
            self.scopes.pop(key, None)
        return {
            "name": key,
            "revoked": existed,
            "session_only": True,
            "persistent": False,
        }

    def root(self, scope: str) -> Path:
        key = str(scope).strip().casefold()
        root = self.scopes.get(key)
        if root is None:
            raise FilesystemError(f"Unknown filesystem scope: {scope}")
        if key != "workspace" and not root.exists():
            raise FilesystemError(f"Filesystem scope is unavailable: {key}")
        return root

    @staticmethod
    def _relative(value: str | None, *, allow_root: bool = True) -> PurePosixPath:
        raw = "." if value is None else str(value).strip().replace("\\", "/")
        if raw in {"", "."}:
            if allow_root:
                return PurePosixPath(".")
            raise FilesystemError("A relative path is required")
        relative = PurePosixPath(raw)
        if relative.is_absolute() or ".." in relative.parts:
            raise FilesystemError("Path must stay inside the selected scope")
        if any(part in {"", "."} for part in relative.parts):
            raise FilesystemError("Unsafe relative path component")
        if "\x00" in raw or len(raw) > 1_000:
            raise FilesystemError("Invalid relative path")
        return relative

    def target(
        self,
        scope: str,
        value: str | None = ".",
        *,
        allow_root: bool = True,
    ) -> Path:
        root = self.root(scope)
        relative = self._relative(value, allow_root=allow_root)
        candidate = root if str(relative) == "." else root.joinpath(*relative.parts)
        target = candidate.resolve(strict=False)
        try:
            target.relative_to(root)
        except ValueError as error:
            raise FilesystemError("Path escaped the selected scope") from error
        current = target
        while True:
            if current.exists() and current.is_symlink():
                raise FilesystemError("Symbolic links are blocked")
            if current == root:
                break
            if current == current.parent:
                raise FilesystemError("Unable to validate scoped path")
            current = current.parent
        return target

    def describe(self) -> dict[str, Any]:
        return {
            "available": True,
            "scopes": [
                {
                    "name": name,
                    "available": root.exists(),
                    "default": name == "workspace",
                    "session_grant": name in self.session_scopes,
                    "persistent": name not in self.session_scopes,
                }
                for name, root in sorted(self.scopes.items())
            ],
            "typed_operations": [
                "scope.grant", "scope.revoke", "list", "stat", "read", "search",
                "mkdir", "write", "patch", "copy", "move", "delete",
            ],
            "shell_required": False,
            "symlinks": "blocked",
            "atomic_writes": True,
            "backups": True,
            "session_grants_persisted": False,
        }

    def list(self, scope: str, path: str = ".") -> dict[str, Any]:
        directory = self.target(scope, path)
        if not directory.is_dir():
            raise FilesystemError("Directory not found")
        items = []
        for item in sorted(directory.iterdir(), key=lambda value: value.name.casefold()):
            if len(items) >= MAX_LIST_ENTRIES:
                break
            if item.is_symlink():
                kind, size = "symlink-blocked", None
            elif item.is_dir():
                kind, size = "directory", None
            elif item.is_file():
                kind, size = "file", item.stat().st_size
            else:
                kind, size = "other", None
            items.append({"name": item.name, "type": kind, "size_bytes": size})
        return {
            "scope": scope.casefold(), "path": path, "count": len(items),
            "truncated": len(items) >= MAX_LIST_ENTRIES, "items": items,
        }

    def stat(self, scope: str, path: str) -> dict[str, Any]:
        target = self.target(scope, path, allow_root=False)
        if not target.exists():
            return {"scope": scope.casefold(), "path": path, "exists": False}
        if target.is_symlink():
            raise FilesystemError("Symbolic links are blocked")
        return {
            "scope": scope.casefold(), "path": path, "exists": True,
            "type": "directory" if target.is_dir() else "file" if target.is_file() else "other",
            "size_bytes": target.stat().st_size if target.is_file() else None,
            "modified_ns": target.stat().st_mtime_ns,
        }

    def read(self, scope: str, path: str) -> dict[str, Any]:
        target = self.target(scope, path, allow_root=False)
        if not target.is_file():
            raise FilesystemError("File not found")
        data = target.read_bytes()
        if len(data) > MAX_TEXT_BYTES:
            raise FilesystemError("File exceeds text read limit")
        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise FilesystemError("File is not UTF-8 text") from error
        return {
            "scope": scope.casefold(), "path": path, "content": content,
            "size_bytes": len(data), "sha256": sha256_bytes(data),
        }

    def search(self, scope: str, query: str, path: str = ".", limit: int = 50) -> dict[str, Any]:
        needle = str(query).strip()
        if not needle:
            raise FilesystemError("Search query is required")
        directory = self.target(scope, path)
        if not directory.is_dir():
            raise FilesystemError("Search directory not found")
        maximum = max(1, min(int(limit), 200))
        matches = []
        inspected = 0
        lowered = needle.casefold()
        for item in sorted(directory.rglob("*")):
            if inspected >= MAX_SEARCH_FILES or len(matches) >= maximum:
                break
            if not item.is_file() or item.is_symlink():
                continue
            try:
                item.relative_to(directory)
                size = item.stat().st_size
            except OSError:
                continue
            if size > MAX_TEXT_BYTES:
                continue
            inspected += 1
            try:
                text = item.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for number, line in enumerate(text.splitlines(), start=1):
                if lowered in line.casefold():
                    matches.append({
                        "path": item.relative_to(self.root(scope)).as_posix(),
                        "line": number,
                        "text": line[:500],
                    })
                    if len(matches) >= maximum:
                        break
        return {
            "scope": scope.casefold(), "path": path, "query": needle,
            "inspected_files": inspected, "count": len(matches), "matches": matches,
        }

    def mkdir(self, scope: str, path: str, approved: bool) -> dict[str, Any]:
        if not approved:
            raise PermissionError("Cyber approval is required to create a directory")
        target = self.target(scope, path, allow_root=False)
        existed = target.exists()
        if existed and not target.is_dir():
            raise FilesystemError("Target exists and is not a directory")
        target.mkdir(parents=True, exist_ok=True)
        verified = target.is_dir()
        return {
            "scope": scope.casefold(), "path": path, "created": not existed,
            "exists": verified, "verified": verified,
        }

    def _backup(self, target: Path, scope: str, relative_path: str) -> str | None:
        if not target.exists():
            return None
        if not target.is_file():
            raise FilesystemError("Only files can be backed up by this operation")
        operation_id = f"fs_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        destination = self.backup_root / operation_id / scope.casefold() / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, destination)
        return operation_id

    def write(self, scope: str, path: str, content: str, approved: bool) -> dict[str, Any]:
        if not approved:
            raise PermissionError("Cyber approval is required to write a file")
        if not isinstance(content, str):
            raise FilesystemError("File content must be text")
        data = content.encode("utf-8")
        if len(data) > MAX_TEXT_BYTES:
            raise FilesystemError("File exceeds text write limit")
        target = self.target(scope, path, allow_root=False)
        if target.exists() and not target.is_file():
            raise FilesystemError("Target exists and is not a file")
        backup_id = self._backup(target, scope, path)
        created = not target.exists()
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.rachel-{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_bytes(data)
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink(missing_ok=True)
        verified_data = target.read_bytes()
        return {
            "scope": scope.casefold(), "path": path, "created": created,
            "overwritten": not created, "size_bytes": len(data),
            "sha256": sha256_bytes(data), "backup_id": backup_id,
            "verified": verified_data == data,
        }

    def patch(self, scope: str, path: str, old: str, new: str, approved: bool) -> dict[str, Any]:
        if not approved:
            raise PermissionError("Cyber approval is required to patch a file")
        current = self.read(scope, path)["content"]
        occurrences = current.count(old)
        if occurrences != 1:
            raise FilesystemError(f"Patch requires exactly one match; found {occurrences}")
        result = self.write(scope, path, current.replace(old, new, 1), approved=True)
        result["patch_matches"] = occurrences
        return result

    def copy(self, scope: str, source: str, destination: str, approved: bool) -> dict[str, Any]:
        if not approved:
            raise PermissionError("Cyber approval is required to copy a file")
        src = self.target(scope, source, allow_root=False)
        dst = self.target(scope, destination, allow_root=False)
        if not src.is_file():
            raise FilesystemError("Source file not found")
        if dst.exists() and not dst.is_file():
            raise FilesystemError("Destination exists and is not a file")
        backup_id = self._backup(dst, scope, destination)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        verified = dst.is_file() and sha256_bytes(src.read_bytes()) == sha256_bytes(dst.read_bytes())
        return {
            "scope": scope.casefold(), "source": source, "destination": destination,
            "backup_id": backup_id, "verified": verified,
        }

    def move(self, scope: str, source: str, destination: str, approved: bool) -> dict[str, Any]:
        if not approved:
            raise PermissionError("Cyber approval is required to move a path")
        src = self.target(scope, source, allow_root=False)
        dst = self.target(scope, destination, allow_root=False)
        if not src.exists():
            raise FilesystemError("Source path not found")
        if dst.exists():
            raise FilesystemError("Destination already exists")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return {
            "scope": scope.casefold(), "source": source, "destination": destination,
            "verified": dst.exists() and not src.exists(),
        }

    def delete(self, scope: str, path: str, approved: bool) -> dict[str, Any]:
        if not approved:
            raise PermissionError("Cyber approval is required to delete a path")
        target = self.target(scope, path, allow_root=False)
        if not target.exists():
            return {
                "scope": scope.casefold(), "path": path, "deleted": False,
                "verified": True, "reason": "not-found",
            }
        if target.is_dir():
            try:
                target.rmdir()
            except OSError as error:
                raise FilesystemError("Directory deletion is non-recursive; directory must be empty") from error
        elif target.is_file():
            target.unlink()
        else:
            raise FilesystemError("Unsupported path type")
        return {
            "scope": scope.casefold(), "path": path, "deleted": True,
            "verified": not target.exists(),
        }
