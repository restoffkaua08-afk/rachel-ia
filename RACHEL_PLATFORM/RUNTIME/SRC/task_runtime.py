from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from runtime_paths import CORE_SRC, ROOT, STATE

if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

STATE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("RACHEL_HOME", str(STATE / "core"))

from rachel_core.bootstrap import build_container
from rachel_core.domain.enums import Role
from rachel_core.domain.models import Message

from task_executor import (
    TaskExecutor,
    parse_approval_bindings,
)
from task_planner import NedTaskPlanner, PlanError, PlanStore
from tools_runtime import ToolCoordinator


class TaskRuntimeError(RuntimeError):
    pass


def decode_base64(value: str) -> str:
    try:
        return base64.b64decode(
            value.encode("ascii"),
            validate=True,
        ).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as error:
        raise TaskRuntimeError(
            "Invalid Base64 content."
        ) from error


class TaskOrchestrator:
    def __init__(
        self,
        database: str | Path | None = None,
        coordinator: Any | None = None,
        model: Any | None = None,
    ) -> None:
        self.database = Path(
            database or STATE / "task-plans.db"
        )
        self.store = PlanStore(self.database)
        self.coordinator = coordinator or ToolCoordinator()
        self.model = model

        if self.model is None:
            self.model = build_container().chat.model

    def status(self) -> dict[str, Any]:
        return {
            "available": True,
            "member": "ned",
            "model_planning": True,
            "deterministic_validation": True,
            "persistent_plans": True,
            "resumable_execution": True,
            "cyber_authorization": True,
            "tool_count": len(
                self.coordinator.list_tools()
            ),
            "database": str(self.database),
        }

    def _extract_json(
        self,
        content: str,
    ) -> dict[str, Any]:
        text = content.strip()
        fenced = re.search(r"\{.*\}", text, re.S)

        try:
            payload = json.loads(
                fenced.group(0) if fenced else text
            )
        except json.JSONDecodeError as error:
            raise TaskRuntimeError(
                f"Model returned invalid plan JSON: {error}"
            ) from error

        if not isinstance(payload, dict):
            raise TaskRuntimeError(
                "Model plan must be a JSON object."
            )

        return payload

    def _secure_specifications(
        self,
        specifications: Any,
    ) -> list[dict[str, Any]]:
        if not isinstance(specifications, list):
            raise TaskRuntimeError(
                "Plan steps must be a list."
            )

        registry = self.coordinator.registry
        secured: list[dict[str, Any]] = []

        for position, raw in enumerate(
            specifications,
            start=1,
        ):
            if not isinstance(raw, dict):
                raise TaskRuntimeError(
                    f"Step {position} must be an object."
                )

            tool_name = str(
                raw.get("tool", "")
            ).strip()

            if tool_name not in registry:
                raise TaskRuntimeError(
                    f"Unknown tool in step {position}: "
                    f"{tool_name}"
                )

            tool = registry[tool_name]
            step_id = str(
                raw.get("id", f"step_{position:02d}")
            ).strip()

            if not re.fullmatch(
                r"[a-zA-Z0-9_-]{1,80}",
                step_id,
            ):
                raise TaskRuntimeError(
                    f"Invalid step identifier: {step_id}"
                )

            arguments = raw.get("arguments", {})
            dependencies = raw.get("depends_on", [])

            if not isinstance(arguments, dict):
                raise TaskRuntimeError(
                    f"Arguments for {step_id} must be an object."
                )

            if not isinstance(dependencies, list):
                raise TaskRuntimeError(
                    f"Dependencies for {step_id} must be a list."
                )

            secured.append(
                {
                    "id": step_id,
                    "title": str(
                        raw.get(
                            "title",
                            f"Execute {tool_name}",
                        )
                    ).strip(),
                    "description": str(
                        raw.get("description", "")
                    ).strip(),
                    "member": tool.member,
                    "tool": tool.name,
                    "effect": tool.effect,
                    "arguments": arguments,
                    "depends_on": [
                        str(item).strip()
                        for item in dependencies
                    ],
                }
            )

        return secured

    def model_specifications(
        self,
        goal: str,
    ) -> list[dict[str, Any]]:
        catalog = [
            {
                "name": item["name"],
                "member": item["member"],
                "effect": item["effect"],
                "description": item["description"],
                "parameters": item["parameters"],
            }
            for item in self.coordinator.list_tools()
        ]

        system = (
            "Voce e Ned, planejador de tarefas da Rachel. "
            "Converta o objetivo em um plano executavel. "
            "Responda SOMENTE um objeto JSON valido. "
            "Use exclusivamente as ferramentas fornecidas. "
            "Nunca invente ferramenta, parametro ou resultado. "
            "Cada etapa deve ter id, title, description, "
            "tool, arguments e depends_on. "
            "Os ids devem usar apenas letras, numeros, "
            "hifen ou sublinhado. "
            "Dependencias devem referenciar ids anteriores. "
            "Apenas planeje; nao afirme que executou. "
            'Formato: {"steps":[...],"reasoning_summary":"..."}. '
            "Ferramentas: "
            + json.dumps(
                catalog,
                ensure_ascii=False,
            )
        )

        message = Message(
            conversation_id="task-planner",
            role=Role.USER,
            content=goal,
        )

        response = self.model.generate(
            [message],
            system,
        )
        payload = self._extract_json(
            response.content
        )

        return self._secure_specifications(
            payload.get("steps")
        )

    def create_plan(
        self,
        goal: str,
        specifications: list[dict[str, Any]]
        | None = None,
        source: str = "model",
    ) -> dict[str, Any]:
        clean_goal = " ".join(goal.strip().split())

        if not clean_goal:
            raise TaskRuntimeError(
                "Task goal cannot be empty."
            )

        secured = (
            self._secure_specifications(specifications)
            if specifications is not None
            else self.model_specifications(clean_goal)
        )

        try:
            plan = NedTaskPlanner().create(
                goal=clean_goal,
                specifications=secured,
                metadata={
                    "source": source,
                    "orchestrator": "task-runtime",
                    "model_planning": (
                        specifications is None
                    ),
                },
            )
        except PlanError as error:
            raise TaskRuntimeError(str(error)) from error

        self.store.save(plan)
        return plan.to_dict()

    def execute(
        self,
        plan_id: str,
        approval_ids: dict[str, str] | None = None,
        maximum_steps: int | None = None,
    ) -> dict[str, Any]:
        return TaskExecutor(
            self.store,
            self.coordinator,
        ).execute(
            plan_id=plan_id,
            approval_ids=approval_ids,
            maximum_steps=maximum_steps,
        )

    def show(self, plan_id: str) -> dict[str, Any]:
        plan = self.store.get(plan_id)

        if plan is None:
            raise TaskRuntimeError(
                f"Plan not found: {plan_id}"
            )

        return plan

    def list(self, limit: int) -> list[dict[str, Any]]:
        return self.store.list(limit)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rachel-task"
    )
    parser.add_argument(
        "--database",
        default=str(STATE / "task-plans.db"),
    )

    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    commands.add_parser("status")

    plan = commands.add_parser("plan")
    goal_transport = plan.add_mutually_exclusive_group(
        required=True
    )
    goal_transport.add_argument("--goal")
    goal_transport.add_argument("--goal-base64")
    plan.add_argument("--steps-file")

    run = commands.add_parser("run")
    run.add_argument("--plan-id", required=True)
    run.add_argument(
        "--approval",
        action="append",
        default=[],
        metavar="STEP_ID=APPROVAL_ID",
    )
    run.add_argument("--maximum-steps", type=int)

    show = commands.add_parser("show")
    show.add_argument("--plan-id", required=True)

    listing = commands.add_parser("list")
    listing.add_argument("--limit", type=int, default=20)

    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    orchestrator = TaskOrchestrator(
        database=arguments.database
    )

    if arguments.command == "status":
        result = orchestrator.status()

    elif arguments.command == "plan":
        goal = (
            decode_base64(arguments.goal_base64)
            if arguments.goal_base64
            else arguments.goal
        )

        specifications = None
        source = "model"

        if arguments.steps_file:
            path = Path(
                arguments.steps_file
            ).resolve()

            if not path.is_file():
                raise TaskRuntimeError(
                    f"Steps file not found: {path}"
                )

            try:
                specifications = json.loads(
                    path.read_text(encoding="utf-8")
                )
            except (
                OSError,
                json.JSONDecodeError,
            ) as error:
                raise TaskRuntimeError(
                    f"Invalid steps file: {error}"
                ) from error

            source = "provided"

        result = orchestrator.create_plan(
            goal=goal,
            specifications=specifications,
            source=source,
        )

    elif arguments.command == "run":
        if (
            arguments.maximum_steps is not None
            and arguments.maximum_steps < 1
        ):
            raise TaskRuntimeError(
                "Maximum steps must be greater than zero."
            )

        result = orchestrator.execute(
            plan_id=arguments.plan_id,
            approval_ids=parse_approval_bindings(
                arguments.approval
            ),
            maximum_steps=arguments.maximum_steps,
        )

    elif arguments.command == "show":
        result = orchestrator.show(
            arguments.plan_id
        )

    else:
        result = orchestrator.list(
            max(1, min(arguments.limit, 100))
        )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )

    if (
        isinstance(result, dict)
        and result.get("state")
        == "awaiting_approval"
    ):
        return 3

    if (
        isinstance(result, dict)
        and result.get("state") == "failed"
    ):
        return 2

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        OSError,
        ValueError,
        PlanError,
        TaskRuntimeError,
    ) as error:
        print(
            json.dumps(
                {
                    "state": "failed",
                    "error": str(error),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        raise SystemExit(2)
