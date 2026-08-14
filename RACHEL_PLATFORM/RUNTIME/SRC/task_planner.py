from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import closing
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable


VALID_STATES = {
    "planned",
    "awaiting_approval",
    "ready",
    "running",
    "completed",
    "failed",
    "cancelled",
}

TERMINAL_STATES = {"completed", "failed", "cancelled"}

EFFECTS = {
    "read": ("low", False),
    "inspect": ("low", False),
    "search": ("low", False),
    "status": ("low", False),
    "list": ("low", False),
    "external": ("medium", True),
    "write": ("medium", True),
    "create": ("medium", True),
    "edit": ("medium", True),
    "execute": ("high", True),
    "install": ("high", True),
    "publish": ("high", True),
    "delete": ("critical", True),
    "admin": ("critical", True),
}


class PlanError(ValueError):
    pass


def now_ms() -> int:
    return int(time.time() * 1000)


def stable_step_id(position: int, title: str, tool: str) -> str:
    material = f"{position}:{title.strip()}:{tool.strip()}".encode("utf-8")
    digest = hashlib.sha256(material).hexdigest()[:10]
    return f"step_{position:02d}_{digest}"


@dataclass
class TaskStep:
    id: str
    title: str
    description: str
    member: str
    tool: str
    effect: str
    arguments: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    risk: str = "low"
    approval_required: bool = False
    state: str = "planned"
    result: dict[str, Any] | None = None
    error: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], position: int) -> "TaskStep":
        title = str(data.get("title", "")).strip()
        tool = str(data.get("tool", "")).strip()
        effect = str(data.get("effect", "inspect")).strip().lower()

        if not title:
            raise PlanError(f"Step {position} has no title.")

        if not tool:
            raise PlanError(f"Step {position} has no tool.")

        if effect not in EFFECTS:
            raise PlanError(f"Unsupported effect: {effect}")

        risk, approval_required = EFFECTS[effect]

        step_id = str(data.get("id", "")).strip()
        if not step_id:
            step_id = stable_step_id(position, title, tool)

        arguments = data.get("arguments", {})
        if not isinstance(arguments, dict):
            raise PlanError(f"Arguments for {step_id} must be an object.")

        dependencies = data.get("depends_on", [])
        if not isinstance(dependencies, list):
            raise PlanError(f"Dependencies for {step_id} must be a list.")

        state = str(data.get("state", "planned")).strip().lower()
        if state not in VALID_STATES:
            raise PlanError(f"Invalid state for {step_id}: {state}")

        return cls(
            id=step_id,
            title=title,
            description=str(data.get("description", "")).strip(),
            member=str(data.get("member", "ned")).strip().lower(),
            tool=tool,
            effect=effect,
            arguments=arguments,
            depends_on=[str(item).strip() for item in dependencies],
            risk=risk,
            approval_required=approval_required,
            state=state,
        )


@dataclass
class TaskPlan:
    id: str
    goal: str
    steps: list[TaskStep]
    state: str
    created_at_ms: int
    updated_at_ms: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "state": self.state,
            "created_at_ms": self.created_at_ms,
            "updated_at_ms": self.updated_at_ms,
            "metadata": self.metadata,
            "steps": [asdict(step) for step in self.steps],
        }


class PlanValidator:
    def __init__(self, maximum_steps: int = 50) -> None:
        self.maximum_steps = maximum_steps

    def validate(self, plan: TaskPlan) -> TaskPlan:
        if not plan.goal.strip():
            raise PlanError("The plan goal cannot be empty.")

        if len(plan.goal) > 4000:
            raise PlanError("The plan goal is above the size limit.")

        if not plan.steps:
            raise PlanError("A plan must contain at least one step.")

        if len(plan.steps) > self.maximum_steps:
            raise PlanError("The plan exceeds the maximum number of steps.")

        identifiers = [step.id for step in plan.steps]

        if len(identifiers) != len(set(identifiers)):
            raise PlanError("Step identifiers must be unique.")

        known = set(identifiers)

        for step in plan.steps:
            if step.id in step.depends_on:
                raise PlanError(f"Step {step.id} depends on itself.")

            unknown = set(step.depends_on) - known
            if unknown:
                names = ", ".join(sorted(unknown))
                raise PlanError(
                    f"Step {step.id} has unknown dependencies: {names}"
                )

        self._reject_cycles(plan.steps)
        return plan

    def _reject_cycles(self, steps: Iterable[TaskStep]) -> None:
        graph = {step.id: list(step.depends_on) for step in steps}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(step_id: str) -> None:
            if step_id in visited:
                return

            if step_id in visiting:
                raise PlanError("The plan contains a dependency cycle.")

            visiting.add(step_id)

            for dependency in graph.get(step_id, []):
                visit(dependency)

            visiting.remove(step_id)
            visited.add(step_id)

        for identifier in graph:
            visit(identifier)


class NedTaskPlanner:
    def __init__(self, validator: PlanValidator | None = None) -> None:
        self.validator = validator or PlanValidator()

    def create(
        self,
        goal: str,
        specifications: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> TaskPlan:
        timestamp = now_ms()
        steps = [
            TaskStep.from_dict(specification, position)
            for position, specification in enumerate(specifications, start=1)
        ]

        requires_approval = any(step.approval_required for step in steps)
        plan_state = "awaiting_approval" if requires_approval else "ready"

        plan = TaskPlan(
            id=f"plan_{uuid.uuid4().hex}",
            goal=goal.strip(),
            steps=steps,
            state=plan_state,
            created_at_ms=timestamp,
            updated_at_ms=timestamp,
            metadata={
                "planner": "ned",
                "execution_enabled": False,
                "requires_approval": requires_approval,
                **(metadata or {}),
            },
        )

        return self.validator.validate(plan)


class PlanStore:
    def __init__(self, database: Path | str) -> None:
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database), timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS task_plans (
                    id TEXT PRIMARY KEY,
                    goal TEXT NOT NULL,
                    state TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at_ms INTEGER NOT NULL,
                    updated_at_ms INTEGER NOT NULL
                )
                """
            )
            connection.commit()

    def save(self, plan: TaskPlan) -> TaskPlan:
        payload = json.dumps(
            plan.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
        )

        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO task_plans (
                    id,
                    goal,
                    state,
                    payload,
                    created_at_ms,
                    updated_at_ms
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    goal = excluded.goal,
                    state = excluded.state,
                    payload = excluded.payload,
                    updated_at_ms = excluded.updated_at_ms
                """,
                (
                    plan.id,
                    plan.goal,
                    plan.state,
                    payload,
                    plan.created_at_ms,
                    plan.updated_at_ms,
                ),
            )
            connection.commit()

        return plan

    def get(self, plan_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT payload FROM task_plans WHERE id = ?",
                (plan_id,),
            ).fetchone()

        if row is None:
            return None

        return json.loads(row["payload"])

    def list(self, limit: int = 20) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 100))

        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT payload
                FROM task_plans
                ORDER BY created_at_ms DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()

        return [json.loads(row["payload"]) for row in rows]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ned-task-planner")
    parser.add_argument(
        "--database",
        default=str(
            Path(__file__).resolve().parents[2]
            / "STATE"
            / "task-plans.db"
        ),
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")

    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--goal", required=True)
    steps_source = create_parser.add_mutually_exclusive_group(required=True)
    steps_source.add_argument("--steps-json")
    steps_source.add_argument("--steps-file")

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("--plan-id", required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--limit", type=int, default=20)

    return parser


def main() -> int:
    parser = build_parser()
    arguments = parser.parse_args()
    store = PlanStore(arguments.database)

    if arguments.command == "status":
        print(
            json.dumps(
                {
                    "available": True,
                    "member": "ned",
                    "persistent": True,
                    "validation": True,
                    "dependency_cycles_blocked": True,
                    "execution_enabled": False,
                    "cyber_authorization": True,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if arguments.command == "create":
        if arguments.steps_file:
            steps_path = Path(arguments.steps_file).resolve()

            if not steps_path.is_file():
                raise PlanError(f"Steps file not found: {steps_path}")

            try:
                steps_payload = steps_path.read_text(encoding="utf-8")
            except OSError as error:
                raise PlanError(
                    f"Unable to read steps file: {error}"
                ) from error
        else:
            steps_payload = arguments.steps_json

        try:
            specifications = json.loads(steps_payload)
        except json.JSONDecodeError as error:
            raise PlanError(f"Invalid steps JSON: {error}") from error

        if not isinstance(specifications, list):
            raise PlanError("Steps JSON must contain a list.")

        plan = NedTaskPlanner().create(
            goal=arguments.goal,
            specifications=specifications,
            metadata={"transport": "cli"},
        )
        store.save(plan)
        print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
        return 0

    if arguments.command == "show":
        plan = store.get(arguments.plan_id)

        if plan is None:
            raise PlanError("Plan not found.")

        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    if arguments.command == "list":
        print(
            json.dumps(
                store.list(arguments.limit),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    raise PlanError("Unsupported command.")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PlanError as error:
        print(
            json.dumps(
                {"state": "rejected", "error": str(error)},
                ensure_ascii=False,
                indent=2,
            )
        )
        raise SystemExit(2)
