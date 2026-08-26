from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from runtime_paths import CONFIG

from arya_runtime import run as arya_run, safe_cwd
from bran_cognitive import CognitiveMemory
from cognitive_runtime import DanyEvaluator
from dev_runtime import DevRuntime
from filesystem_runtime import FilesystemRuntime
from git_runtime import GitRuntime
from knowledge_runtime import VisaoIngestor, status as knowledge_status
from process_runtime import ProcessRuntime
from project_generator import ProjectGenerator
from project_intelligence_runtime import ProjectIntelligenceRuntime
from project_quality import ProjectQuality
from project_workspace import ProjectWorkspace
from research_runtime import ResearchEngine
from search_runtime import SearchEngine
from security_runtime import ApprovalError, ApprovalStore
from team_runtime import CyberPolicy, JhonLogger, KingEventBus, TyrionSupervisor, doctor
from web_runtime import WebClient, evidence_summary


class ToolError(RuntimeError):
    pass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    member: str
    effect: str
    description: str
    parameters: dict[str, str]


def _load_registry() -> dict[str, ToolSpec]:
    payload = json.loads((CONFIG / "tools.registry.json").read_text(encoding="utf-8-sig"))
    return {
        item["name"]: ToolSpec(
            name=item["name"],
            member=item["member"],
            effect=item["effect"],
            description=item["description"],
            parameters=dict(item.get("parameters", {})),
        )
        for item in payload["tools"]
    }


def _require_text(arguments: dict[str, Any], key: str, maximum: int = 50_000) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ToolError(f"'{key}' must be a non-empty string")
    if len(value) > maximum:
        raise ToolError(f"'{key}' exceeds {maximum} characters")
    return value.strip()


def _optional_text(arguments: dict[str, Any], key: str, default: str, maximum: int = 5_000) -> str:
    value = arguments.get(key, default)
    if not isinstance(value, str):
        raise ToolError(f"'{key}' must be a string")
    if len(value) > maximum:
        raise ToolError(f"'{key}' exceeds {maximum} characters")
    return value.strip() or default


def _optional_nullable_text(arguments: dict[str, Any], key: str, maximum: int = 5_000) -> str | None:
    value = arguments.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ToolError(f"'{key}' must be a string or null")
    if len(value) > maximum:
        raise ToolError(f"'{key}' exceeds {maximum} characters")
    return value.strip() or None


def _optional_bool(arguments: dict[str, Any], key: str, default: bool = False) -> bool:
    value = arguments.get(key, default)
    if not isinstance(value, bool):
        raise ToolError(f"'{key}' must be a boolean")
    return value


def _optional_string_list(arguments: dict[str, Any], key: str) -> list[str] | None:
    value = arguments.get(key)
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ToolError(f"'{key}' must be an array of strings or null")
    return value


def _required_string_list(arguments: dict[str, Any], key: str) -> list[str]:
    value = _optional_string_list(arguments, key)
    if not value:
        raise ToolError(f"'{key}' must contain at least one string")
    return value


def _bounded_int(arguments: dict[str, Any], key: str, default: int, minimum: int, maximum: int) -> int:
    value = arguments.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ToolError(f"'{key}' must be an integer")
    return max(minimum, min(value, maximum))


class ToolCoordinator:
    def __init__(
        self,
        memory: CognitiveMemory | None = None,
        approvals: ApprovalStore | None = None,
        filesystem: FilesystemRuntime | None = None,
        git: GitRuntime | None = None,
        dev: DevRuntime | None = None,
        processes: ProcessRuntime | None = None,
        projects: ProjectIntelligenceRuntime | None = None,
    ) -> None:
        self.registry = _load_registry()
        self.cyber = CyberPolicy()
        self.king = KingEventBus()
        self.jhon = JhonLogger()
        self.bran = memory or CognitiveMemory()
        self.approvals = approvals or ApprovalStore()
        self.filesystem = filesystem or FilesystemRuntime()
        self.git = git or GitRuntime(self.filesystem)
        self.dev = dev or DevRuntime(self.filesystem)
        self.processes = processes or ProcessRuntime(self.filesystem)
        self.projects = projects or ProjectIntelligenceRuntime(self.filesystem, self.bran)

    def list_tools(self) -> list[dict[str, Any]]:
        return [asdict(spec) for spec in self.registry.values()]

    def inspect(self, name: str) -> dict[str, Any]:
        spec = self.registry.get(name)
        if spec is None:
            raise ToolError(f"Unknown tool: {name}")
        return asdict(spec)

    def _effective_effect(self, spec: ToolSpec, arguments: dict[str, Any]) -> str:
        scoped_family = (
            spec.name.startswith("filesystem.")
            or spec.name.startswith("git.")
            or spec.name.startswith("dev.")
            or spec.name.startswith("project.")
            or spec.name == "process.start"
        )
        scope_free = {
            "filesystem.status",
            "filesystem.scope.grant",
            "filesystem.scope.revoke",
        }
        if scoped_family and spec.name not in scope_free:
            scope = str(arguments.get("scope", "workspace")).strip().casefold()
            self.filesystem.root(scope)
            low_risk = spec.effect in {"read", "inspect", "list", "search", "status"}
            already_granted = scope in self.filesystem.session_scopes
            if scope != "workspace" and not already_granted and low_risk:
                return "external"
        return spec.effect

    def invoke(self, name: str, arguments: dict[str, Any] | None = None, approval_id: str | None = None) -> dict[str, Any]:
        spec = self.registry.get(name)
        if spec is None:
            raise ToolError(f"Unknown tool: {name}")
        args = arguments or {}
        if not isinstance(args, dict):
            raise ToolError("Tool arguments must be a JSON object")
        try:
            effective_effect = self._effective_effect(spec, args)
        except Exception as error:
            raise ToolError(str(error)) from error

        consumed_approval = None
        authorized = False
        if approval_id:
            consumed_approval = self.approvals.consume(approval_id, name, effective_effect, args)
            authorized = True

        decision = self.cyber.check(effective_effect, authorized)
        request_event = self.king.publish(
            "tool.requested",
            {"tool": name, "member": spec.member, "effect": effective_effect, "declared_effect": spec.effect},
            sender="ned",
            recipient=spec.member,
        )
        self.jhon.write(
            "info", "tools", "tool.requested",
            tool=name, member=spec.member, effect=effective_effect, authorized=authorized,
        )

        if not decision.allowed:
            self.jhon.write("warning", "cyber", "tool.blocked", tool=name, risk=decision.risk, effect=effective_effect)
            approval = None
            if decision.approval_required:
                approval = self.approvals.request(name, effective_effect, decision.risk, args, decision.reason)
                self.king.publish(
                    "approval.requested",
                    {"approval_id": approval["id"], "tool": name, "risk": decision.risk, "effect": effective_effect},
                    sender="cyber",
                    recipient="user",
                )
            return {
                "state": "approval_required" if decision.approval_required else "denied",
                "tool": name,
                "member": spec.member,
                "policy": asdict(decision),
                "approval": approval,
                "request_event_id": request_event["id"],
                "duration_ms": None,
                "duration_scope": "not-executed",
            }

        started = time.perf_counter()
        try:
            result = self._execute(name, args, authorized)
        except Exception as error:
            duration_ms = int((time.perf_counter() - started) * 1000)
            self.jhon.write("error", spec.member, "tool.failed", tool=name, error_type=type(error).__name__, duration_ms=duration_ms)
            self.king.publish(
                "tool.failed",
                {"tool": name, "error_type": type(error).__name__, "duration_ms": duration_ms},
                sender=spec.member,
                recipient="ned",
            )
            raise

        duration_ms = int((time.perf_counter() - started) * 1000)
        completion = self.king.publish(
            "tool.completed",
            {"tool": name, "member": spec.member, "duration_ms": duration_ms},
            sender=spec.member,
            recipient="ned",
        )
        self.jhon.write("info", spec.member, "tool.completed", tool=name, duration_ms=duration_ms)
        return {
            "state": "completed",
            "tool": name,
            "member": spec.member,
            "result": result,
            "policy": asdict(decision),
            "effective_effect": effective_effect,
            "request_event_id": request_event["id"],
            "completion_event_id": completion["id"],
            "approval": consumed_approval,
            "duration_ms": duration_ms,
            "duration_scope": "tool-execution-only",
        }

    def _execute(self, name: str, args: dict[str, Any], authorized: bool) -> Any:
        scope = lambda: _require_text(args, "scope", 50)
        path = lambda: _optional_text(args, "path", ".", 1_000)

        if name == "filesystem.status":
            return self.filesystem.describe()
        if name == "filesystem.scope.grant":
            return self.filesystem.grant_scope(
                _require_text(args, "name", 64),
                _require_text(args, "root", 2_000),
                authorized,
            )
        if name == "filesystem.scope.revoke":
            return self.filesystem.revoke_scope(_require_text(args, "name", 64), authorized)
        if name == "filesystem.list":
            return self.filesystem.list(scope(), path())
        if name == "filesystem.stat":
            return self.filesystem.stat(scope(), _require_text(args, "path", 1_000))
        if name == "filesystem.read":
            return self.filesystem.read(scope(), _require_text(args, "path", 1_000))
        if name == "filesystem.search":
            return self.filesystem.search(scope(), _require_text(args, "query", 2_000), path(), _bounded_int(args, "limit", 50, 1, 200))
        if name == "filesystem.mkdir":
            return self.filesystem.mkdir(scope(), _require_text(args, "path", 1_000), authorized)
        if name == "filesystem.write":
            return self.filesystem.write(scope(), _require_text(args, "path", 1_000), _require_text(args, "content", 1_000_000), authorized)
        if name == "filesystem.patch":
            return self.filesystem.patch(scope(), _require_text(args, "path", 1_000), _require_text(args, "old", 500_000), str(args.get("new", "")), authorized)
        if name == "filesystem.copy":
            return self.filesystem.copy(scope(), _require_text(args, "source", 1_000), _require_text(args, "destination", 1_000), authorized)
        if name == "filesystem.move":
            return self.filesystem.move(scope(), _require_text(args, "source", 1_000), _require_text(args, "destination", 1_000), authorized)
        if name == "filesystem.delete":
            return self.filesystem.delete(scope(), _require_text(args, "path", 1_000), authorized)

        if name == "git.status":
            return self.git.status(scope(), path())
        if name == "git.diff":
            return self.git.diff(scope(), path(), staged=_optional_bool(args, "staged", False), files=_optional_string_list(args, "files"))
        if name == "git.log":
            return self.git.log(scope(), path(), _bounded_int(args, "limit", 20, 1, 100))
        if name == "git.branches":
            return self.git.branches(scope(), path())
        if name == "git.stage":
            return self.git.stage(scope(), path(), _required_string_list(args, "files"), authorized)
        if name == "git.commit":
            return self.git.commit(scope(), path(), _require_text(args, "message", 500), authorized)
        if name == "git.branch.create":
            return self.git.create_branch(scope(), path(), _require_text(args, "branch", 200), authorized)
        if name == "git.checkout":
            return self.git.checkout(scope(), path(), _require_text(args, "branch", 200), authorized)

        if name == "dev.detect":
            return self.dev.detect(scope(), path())
        if name in {"dev.test", "dev.build", "dev.lint", "dev.typecheck"}:
            return self.dev.run(
                scope(), path(), name.split(".", 1)[1], authorized,
                _bounded_int(args, "timeout_seconds", 300, 10, 900),
            )

        if name == "process.start":
            return self.processes.start(scope(), path(), _require_text(args, "profile", 100), authorized)
        if name == "process.list":
            return self.processes.list()
        if name == "process.status":
            return self.processes.status(_require_text(args, "process_id", 200))
        if name == "process.logs":
            return self.processes.logs(_require_text(args, "process_id", 200), _bounded_int(args, "maximum_bytes", 20_000, 1_000, 100_000))
        if name == "process.stop":
            return self.processes.stop(_require_text(args, "process_id", 200), authorized)

        if name == "project.discover":
            return self.projects.discover(scope(), path())
        if name == "project.map":
            return self.projects.repo_map(scope(), path(), _bounded_int(args, "maximum_files", 400, 20, 1_000))
        if name == "project.dependencies":
            return self.projects.dependencies(scope(), path())
        if name == "project.symbols":
            return self.projects.symbols(scope(), path(), _optional_nullable_text(args, "query", 500), _bounded_int(args, "limit", 500, 1, 5_000))
        if name == "project.search":
            return self.projects.search(scope(), path(), _require_text(args, "query", 2_000), _bounded_int(args, "limit", 30, 1, 100))
        if name == "project.context":
            return self.projects.context_for(
                scope(),
                path(),
                _require_text(args, "task", 8_000),
                max_files=_bounded_int(args, "limit", 12, 1, 19),
            )
        if name == "project.instructions.read":
            return self.projects.read_instructions(scope(), path())
        if name == "project.instructions.write":
            return self.projects.write_instructions(scope(), path(), _require_text(args, "content", 50_000), authorized)
        if name == "project.memory.remember":
            return self.projects.remember_decision(scope(), path(), _require_text(args, "decision", 20_000), authorized)
        if name == "project.memory.search":
            return self.projects.search_decisions(scope(), path(), _require_text(args, "query", 5_000), _bounded_int(args, "limit", 10, 1, 50))

        if name == "arya.project.review":
            result = ProjectQuality().review(_require_text(args, "project", 80))
            result["dany"] = asdict(DanyEvaluator().evaluate(json.dumps(result, ensure_ascii=False)))
            return result
        if name == "arya.project.report":
            return ProjectQuality().write_report(_require_text(args, "project", 80), authorized)
        if name == "arya.project.status":
            return ProjectWorkspace().status()
        if name == "arya.project.create":
            return ProjectWorkspace().create_project(_require_text(args, "project", 80), authorized)
        if name == "arya.project.write":
            files = args.get("files")
            if not isinstance(files, list):
                raise ToolError("'files' must be an array")
            return ProjectWorkspace().write_files(_require_text(args, "project", 80), files, authorized)
        if name == "arya.project.inspect":
            return ProjectWorkspace().inspect(_require_text(args, "project", 80))
        if name == "arya.project.read":
            return ProjectWorkspace().read_file(_require_text(args, "project", 80), _require_text(args, "path", 500))
        if name == "arya.project.generate":
            return ProjectGenerator().create(
                project=_require_text(args, "project", 80),
                goal=_require_text(args, "goal", 8_000),
                project_type=str(args.get("project_type", "auto"))[:100],
                approved=authorized,
            )

        if name == "web.fetch":
            evidence = WebClient().fetch(_require_text(args, "url", 4_000))
            include_content = args.get("include_content", True)
            if not isinstance(include_content, bool):
                raise ToolError("'include_content' must be a boolean")
            return evidence_summary(evidence, include_content=include_content)
        if name == "web.search":
            return SearchEngine().search(_require_text(args, "query", 500), _bounded_int(args, "limit", 8, 1, 20))
        if name == "web.research":
            return ResearchEngine().research(_require_text(args, "query", 500), _bounded_int(args, "max_sources", 3, 1, 5))
        if name == "runtime.doctor":
            return doctor()
        if name == "tyrion.health":
            organ_id = args.get("organ_id")
            if organ_id is not None and not isinstance(organ_id, str):
                raise ToolError("'organ_id' must be a string or null")
            return TyrionSupervisor().health(organ_id)
        if name == "bran.search":
            return self.bran.search(_require_text(args, "query", 5_000), _bounded_int(args, "limit", 10, 1, 100))
        if name == "bran.remember":
            category = str(args.get("category", args.get("kind", "note")))[:100]
            return self.bran.remember(
                _require_text(args, "content"),
                approved=authorized,
                source=str(args.get("source", "user-approved"))[:200],
                category=category,
                metadata={"requested_by": "ned", "authorized_by": "cyber", "transport": "tool"},
            )
        if name == "visao.status":
            return knowledge_status()["visao"]
        if name == "visao.ingest":
            return VisaoIngestor(self.bran).ingest(safe_cwd(_require_text(args, "path", 2_000)))
        if name == "arya.list":
            folder = safe_cwd(str(args.get("path", ".")))
            return [item.name for item in sorted(folder.iterdir())]
        if name == "arya.run":
            command = _require_text(args, "command", 500)
            raw_arguments = args.get("arguments", [])
            if not isinstance(raw_arguments, list) or not all(isinstance(item, str) for item in raw_arguments):
                raise ToolError("'arguments' must be an array of strings")
            cwd = args.get("cwd")
            if cwd is not None and not isinstance(cwd, str):
                raise ToolError("'cwd' must be a string or null")
            return arya_run(command, raw_arguments, cwd, authorized)
        if name == "king.recent":
            return KingEventBus().recent(_bounded_int(args, "limit", 20, 1, 200))
        if name == "dany.evaluate":
            return asdict(DanyEvaluator().evaluate(_require_text(args, "content")))
        if name == "cyber.check":
            effect = _require_text(args, "effect", 100)
            requested_approval = args.get("approved", False)
            if not isinstance(requested_approval, bool):
                raise ToolError("'approved' must be a boolean")
            return asdict(CyberPolicy().check(effect, requested_approval))
        raise ToolError(f"Tool has no executor: {name}")


def parse_arguments(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ToolError(f"Invalid arguments JSON: {error.msg}") from error
    if not isinstance(payload, dict):
        raise ToolError("Arguments JSON must be an object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(prog="rachel-tools")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("list")
    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("name")
    invoke_parser = sub.add_parser("invoke")
    invoke_parser.add_argument("name")
    invoke_parser.add_argument("--arguments")
    invoke_parser.add_argument("--arguments-base64")
    invoke_parser.add_argument("--approval-id")
    args = parser.parse_args()
    coordinator = ToolCoordinator()
    try:
        if args.action == "list":
            result = coordinator.list_tools()
        elif args.action == "inspect":
            result = coordinator.inspect(args.name)
        else:
            if args.arguments and args.arguments_base64:
                raise ToolError("Use only one arguments transport")
            raw_arguments = args.arguments or "{}"
            if args.arguments_base64:
                try:
                    raw_arguments = base64.b64decode(args.arguments_base64.encode("ascii"), validate=True).decode("utf-8")
                except (ValueError, UnicodeDecodeError) as error:
                    raise ToolError("Invalid Base64 arguments") from error
            result = coordinator.invoke(args.name, parse_arguments(raw_arguments), approval_id=args.approval_id)
    except (OSError, ValueError, ToolError, ApprovalError) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if isinstance(result, dict) and result.get("state") in {"approval_required", "denied"}:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
