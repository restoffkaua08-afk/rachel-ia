from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "RACHEL_PLATFORM" / "CONFIG"
DEFAULT_ROOT = ROOT / "RACHEL_WORKSPACE" / "PROJECTS"


class WorkspaceError(RuntimeError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ProjectWorkspace:
    def __init__(self, root=None, policy_path=None):
        self.root = Path(root or DEFAULT_ROOT).resolve()
        source = Path(policy_path or CONFIG / "project.policy.json")
        self.policy = json.loads(source.read_text(encoding="utf-8-sig"))
        self.root.mkdir(parents=True, exist_ok=True)

    def status(self) -> dict[str, Any]:
        return {
            "available": True,
            "member": "arya",
            "root": str(self.root),
            "atomic_writes": True,
            "backups": True,
            "rollback": True,
            "approval_required": True,
        }

    def project_path(self, name: str) -> Path:
        clean = name.strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", clean) or clean in {".", ".."}:
            raise WorkspaceError("Invalid project name.")
        path = (self.root / clean).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as error:
            raise WorkspaceError("Project escaped the workspace.") from error
        return path

    def _relative(self, value: str) -> PurePosixPath:
        normalized = value.strip().replace("\\", "/")
        relative = PurePosixPath(normalized)
        if not normalized or len(normalized) > 240 or relative.is_absolute() or ".." in relative.parts:
            raise WorkspaceError("Unsafe relative path.")
        if any(part in {"", ".", ".rachel"} for part in relative.parts):
            raise WorkspaceError("Reserved path component.")
        return relative

    def _target(self, project: str, value: str) -> Path:
        base = self.project_path(project)
        relative = self._relative(value)
        target = base.joinpath(*relative.parts).resolve()
        try:
            target.relative_to(base)
        except ValueError as error:
            raise WorkspaceError("File escaped the project.") from error
        current = target
        while current != base.parent:
            if current.exists() and current.is_symlink():
                raise WorkspaceError("Symbolic links are blocked.")
            if current == base:
                break
            current = current.parent
        return target

    def _validate_file(self, relative: PurePosixPath, content: str) -> bytes:
        name = relative.name.casefold()
        if name in {str(x).casefold() for x in self.policy["blocked_names"]}:
            raise WorkspaceError(f"Blocked file name: {relative.name}")
        if name == ".gitignore":
            extension = ".gitignore"
        elif name.endswith(".env.example"):
            extension = ".env.example"
        else:
            extension = relative.suffix.casefold()
        allowed = {str(x).casefold() for x in self.policy["allowed_extensions"]}
        if extension not in allowed:
            raise WorkspaceError(f"Unsupported extension: {extension}")
        encoded = content.encode("utf-8")
        if len(encoded) > int(self.policy["maximum_file_size_bytes"]):
            raise WorkspaceError(f"File exceeds limit: {relative}")
        return encoded

    def create_project(self, project: str, approved: bool) -> dict[str, Any]:
        if not approved:
            raise PermissionError("Cyber requires approval to create projects.")
        path = self.project_path(project)
        created = not path.exists()
        (path / ".rachel" / "history").mkdir(parents=True, exist_ok=True)
        return {"project": project, "path": str(path), "created": created}

    def write_files(self, project: str, specifications: Any, approved: bool) -> dict[str, Any]:
        if not approved:
            raise PermissionError("Cyber requires approval to write files.")
        base = self.project_path(project)
        if not base.is_dir():
            raise WorkspaceError("Project does not exist.")
        if not isinstance(specifications, list) or not specifications:
            raise WorkspaceError("Specifications must be a non-empty list.")
        if len(specifications) > int(self.policy["maximum_files"]):
            raise WorkspaceError("File count exceeds policy.")

        prepared = []
        seen = set()
        for item in specifications:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("content"), str):
                raise WorkspaceError("Invalid file specification.")
            relative = self._relative(item["path"])
            target = self._target(project, item["path"])
            key = str(target).casefold()
            if key in seen:
                raise WorkspaceError(f"Duplicated target: {relative}")
            seen.add(key)
            content = self._validate_file(relative, item["content"])
            prepared.append((relative.as_posix(), target, content))

        operation = f"write_{int(time.time()*1000)}_{uuid.uuid4().hex[:8]}"
        internal = base / ".rachel"
        staging = internal / "staging" / operation
        history = internal / "history" / operation
        snapshots = {}
        staging.mkdir(parents=True, exist_ok=False)
        try:
            for relative, target, content in prepared:
                snapshots[target] = target.read_bytes() if target.exists() else None
                staged = staging / relative
                staged.parent.mkdir(parents=True, exist_ok=True)
                staged.write_bytes(content)
            for relative, target, content in prepared:
                previous = snapshots[target]
                if previous is not None:
                    backup = history / relative
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    backup.write_bytes(previous)
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staging / relative, target)
            manifest = {
                "operation_id": operation,
                "project": project,
                "file_count": len(prepared),
                "files": [{"path": r, "size_bytes": len(c), "sha256": digest(c), "overwritten": snapshots[t] is not None} for r, t, c in prepared],
            }
            temp_manifest = internal / "last-operation.tmp"
            temp_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temp_manifest, internal / "last-operation.json")
            return {"state": "completed", **manifest}
        except Exception:
            for target, previous in snapshots.items():
                try:
                    if previous is None:
                        if target.exists(): target.unlink()
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(previous)
                except OSError:
                    pass
            raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def read_file(self, project: str, relative: str) -> dict[str, Any]:
        target = self._target(project, relative)
        if not target.is_file():
            raise WorkspaceError("File not found.")
        content = target.read_text(encoding="utf-8")
        return {"project": project, "path": self._relative(relative).as_posix(), "content": content, "sha256": digest(content.encode("utf-8"))}

    def inspect(self, project: str) -> dict[str, Any]:
        base = self.project_path(project)
        if not base.is_dir():
            raise WorkspaceError("Project does not exist.")
        files = []
        for item in sorted(base.rglob("*")):
            if item.is_file():
                relative = item.relative_to(base)
                if relative.parts[0] != ".rachel":
                    files.append({"path": relative.as_posix(), "size_bytes": item.stat().st_size, "sha256": digest(item.read_bytes())})
        return {"project": project, "path": str(base), "file_count": len(files), "files": files}


def load_specs(value: str):
    path = Path(value).resolve()
    if not path.is_file():
        raise WorkspaceError("Specification file not found.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise WorkspaceError("Specification must contain a list.")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(prog="arya-workspace")
    parser.add_argument("--root")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    create = commands.add_parser("create"); create.add_argument("--project", required=True); create.add_argument("--approved", action="store_true")
    write = commands.add_parser("write"); write.add_argument("--project", required=True); write.add_argument("--specifications-file", required=True); write.add_argument("--approved", action="store_true")
    inspect = commands.add_parser("inspect"); inspect.add_argument("--project", required=True)
    read = commands.add_parser("read"); read.add_argument("--project", required=True); read.add_argument("--path", required=True)
    args = parser.parse_args()
    workspace = ProjectWorkspace(args.root)
    if args.command == "status": result = workspace.status()
    elif args.command == "create": result = workspace.create_project(args.project, args.approved)
    elif args.command == "write": result = workspace.write_files(args.project, load_specs(args.specifications_file), args.approved)
    elif args.command == "inspect": result = workspace.inspect(args.project)
    else: result = workspace.read_file(args.project, args.path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, PermissionError, WorkspaceError, json.JSONDecodeError) as error:
        print(json.dumps({"state": "rejected", "error": str(error)}, ensure_ascii=False, indent=2))
        raise SystemExit(3)
