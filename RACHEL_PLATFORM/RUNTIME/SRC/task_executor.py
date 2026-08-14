from __future__ import annotations

import argparse
import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any

from task_planner import PlanStore
from tools_runtime import ToolCoordinator


TERMINAL_STATES = {"completed", "failed", "cancelled"}


class ExecutionError(RuntimeError):
    pass


class TaskExecutor:
    def __init__(
        self,
        store: PlanStore,
        coordinator: ToolCoordinator | Any | None = None,
    ) -> None:
        self.store = store
        self.coordinator = coordinator or ToolCoordinator()

    def _publish(
        self,
        event_type: str,
        payload: dict[str, Any],
        sender: str,
        recipient: str,
    ) -> None:
        king = getattr(self.coordinator, "king", None)
        if king is not None and hasattr(king, "publish"):
            king.publish(
                event_type,
                payload,
                sender=sender,
                recipient=recipient,
            )

    def _log(
        self,
        level: str,
        component: str,
        event: str,
        **fields: Any,
    ) -> None:
        jhon = getattr(self.coordinator, "jhon", None)
        if jhon is not None and hasattr(jhon, "write"):
            jhon.write(level, component, event, **fields)

    def _persist(self, payload: dict[str, Any]) -> None:
        payload["updated_at_ms"] = int(time.time() * 1000)

        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
        )

        with closing(
            sqlite3.connect(str(self.store.database), timeout=10)
        ) as connection:
            connection.execute(
                """
                UPDATE task_plans
                SET state = ?,
                    payload = ?,
                    updated_at_ms = ?
                WHERE id = ?
                """,
                (
                    payload["state"],
                    serialized,
                    payload["updated_at_ms"],
                    payload["id"],
                ),
            )

            if connection.total_changes != 1:
                raise ExecutionError(
                    f"Plan was not updated: {payload['id']}"
                )

            connection.commit()

    @staticmethod
    def _step_map(
        payload: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        return {
            str(step["id"]): step
            for step in payload.get("steps", [])
        }

    @staticmethod
    def _approved(
        step: dict[str, Any],
        approved_steps: set[str],
        approve_all: bool,
    ) -> bool:
        if not bool(step.get("approval_required", False)):
            return False

        return approve_all or str(step["id"]) in approved_steps

    def status(self) -> dict[str, Any]:
        return {
            "available": True,
            "member": "ned",
            "execution": True,
            "resumable": True,
            "persistent_checkpoints": True,
            "cyber_authorization": True,
            "arya_tools": True,
            "king_events": True,
            "jhon_observability": True,
            "skip_completed_steps": True,
        }

    def execute(
        self,
        plan_id: str,
        approved_steps: set[str] | None = None,
        approve_all: bool = False,
        maximum_steps: int | None = None,
    ) -> dict[str, Any]:
        approvals = set(approved_steps or set())
        payload = self.store.get(plan_id)

        if payload is None:
            raise ExecutionError(f"Plan not found: {plan_id}")

        if payload.get("state") == "completed":
            return {
                "state": "completed",
                "plan_id": plan_id,
                "resumed": True,
                "already_completed": True,
                "plan": payload,
            }

        if payload.get("state") in {"failed", "cancelled"}:
            raise ExecutionError(
                f"Plan cannot run from state: {payload.get('state')}"
            )

        step_map = self._step_map(payload)

        if not step_map:
            raise ExecutionError("Plan has no executable steps.")

        unknown_approvals = approvals - set(step_map)
        if unknown_approvals:
            raise ExecutionError(
                "Unknown approved steps: "
                + ", ".join(sorted(unknown_approvals))
            )

        payload["state"] = "running"
        payload.setdefault("metadata", {})
        payload["metadata"]["execution_enabled"] = True
        payload["metadata"]["executor"] = "ned-task-executor"
        payload["metadata"]["last_resume_at_ms"] = int(
            time.time() * 1000
        )
        self._persist(payload)

        self._publish(
            "plan.started",
            {"plan_id": plan_id, "goal": payload.get("goal", "")},
            sender="ned",
            recipient="king",
        )
        self._log(
            "info",
            "ned",
            "plan.started",
            plan_id=plan_id,
        )

        executed_now = 0

        while True:
            progress = False
            pending_exists = False

            for step in payload["steps"]:
                state = str(step.get("state", "planned"))

                if state == "completed":
                    continue

                if state in {"failed", "cancelled"}:
                    payload["state"] = "failed"
                    self._persist(payload)

                    return {
                        "state": "failed",
                        "plan_id": plan_id,
                        "failed_step": step["id"],
                        "plan": payload,
                    }

                pending_exists = True
                dependencies = [
                    step_map[dependency]
                    for dependency in step.get("depends_on", [])
                ]

                failed_dependencies = [
                    dependency["id"]
                    for dependency in dependencies
                    if dependency.get("state") in {
                        "failed",
                        "cancelled",
                    }
                ]

                if failed_dependencies:
                    step["state"] = "cancelled"
                    step["error"] = (
                        "Dependency failed: "
                        + ", ".join(failed_dependencies)
                    )
                    payload["state"] = "failed"
                    self._persist(payload)

                    self._publish(
                        "plan.failed",
                        {
                            "plan_id": plan_id,
                            "step_id": step["id"],
                            "reason": "dependency_failed",
                        },
                        sender="ned",
                        recipient="jhon",
                    )

                    return {
                        "state": "failed",
                        "plan_id": plan_id,
                        "failed_step": step["id"],
                        "plan": payload,
                    }

                if not all(
                    dependency.get("state") == "completed"
                    for dependency in dependencies
                ):
                    continue

                approved = self._approved(
                    step,
                    approvals,
                    approve_all,
                )

                if (
                    bool(step.get("approval_required", False))
                    and not approved
                ):
                    step["state"] = "awaiting_approval"
                    payload["state"] = "awaiting_approval"
                    self._persist(payload)

                    self._publish(
                        "plan.approval_required",
                        {
                            "plan_id": plan_id,
                            "step_id": step["id"],
                            "tool": step["tool"],
                            "effect": step["effect"],
                            "risk": step["risk"],
                        },
                        sender="cyber",
                        recipient="ned",
                    )
                    self._log(
                        "warning",
                        "cyber",
                        "plan.approval_required",
                        plan_id=plan_id,
                        step_id=step["id"],
                        tool=step["tool"],
                    )

                    return {
                        "state": "awaiting_approval",
                        "plan_id": plan_id,
                        "approval": {
                            "step_id": step["id"],
                            "title": step["title"],
                            "tool": step["tool"],
                            "effect": step["effect"],
                            "risk": step["risk"],
                            "arguments": step.get("arguments", {}),
                        },
                        "executed_now": executed_now,
                        "plan": payload,
                    }

                step["state"] = "running"
                step["error"] = None
                self._persist(payload)

                self._publish(
                    "plan.step.started",
                    {
                        "plan_id": plan_id,
                        "step_id": step["id"],
                        "tool": step["tool"],
                    },
                    sender="ned",
                    recipient=str(step.get("member", "unknown")),
                )
                self._log(
                    "info",
                    "ned",
                    "plan.step.started",
                    plan_id=plan_id,
                    step_id=step["id"],
                    tool=step["tool"],
                )

                try:
                    response = self.coordinator.invoke(
                        str(step["tool"]),
                        dict(step.get("arguments", {})),
                        approved=approved,
                    )
                except Exception as error:
                    step["state"] = "failed"
                    step["error"] = (
                        f"{type(error).__name__}: {error}"
                    )
                    payload["state"] = "failed"
                    self._persist(payload)

                    self._publish(
                        "plan.step.failed",
                        {
                            "plan_id": plan_id,
                            "step_id": step["id"],
                            "error_type": type(error).__name__,
                        },
                        sender=str(step.get("member", "unknown")),
                        recipient="ned",
                    )
                    self._log(
                        "error",
                        str(step.get("member", "unknown")),
                        "plan.step.failed",
                        plan_id=plan_id,
                        step_id=step["id"],
                        error_type=type(error).__name__,
                    )

                    return {
                        "state": "failed",
                        "plan_id": plan_id,
                        "failed_step": step["id"],
                        "error": step["error"],
                        "executed_now": executed_now,
                        "plan": payload,
                    }

                response_state = str(
                    response.get("state", "failed")
                )

                if response_state == "approval_required":
                    step["state"] = "awaiting_approval"
                    payload["state"] = "awaiting_approval"
                    step["result"] = response
                    self._persist(payload)

                    return {
                        "state": "awaiting_approval",
                        "plan_id": plan_id,
                        "approval": {
                            "step_id": step["id"],
                            "title": step["title"],
                            "tool": step["tool"],
                            "effect": step["effect"],
                            "risk": step["risk"],
                            "arguments": step.get("arguments", {}),
                        },
                        "executed_now": executed_now,
                        "plan": payload,
                    }

                if response_state != "completed":
                    step["state"] = "failed"
                    step["result"] = response
                    step["error"] = (
                        f"Tool returned state: {response_state}"
                    )
                    payload["state"] = "failed"
                    self._persist(payload)

                    return {
                        "state": "failed",
                        "plan_id": plan_id,
                        "failed_step": step["id"],
                        "executed_now": executed_now,
                        "plan": payload,
                    }

                step["state"] = "completed"
                step["result"] = response
                step["error"] = None
                executed_now += 1
                progress = True
                self._persist(payload)

                self._publish(
                    "plan.step.completed",
                    {
                        "plan_id": plan_id,
                        "step_id": step["id"],
                        "tool": step["tool"],
                    },
                    sender=str(step.get("member", "unknown")),
                    recipient="ned",
                )
                self._log(
                    "info",
                    str(step.get("member", "unknown")),
                    "plan.step.completed",
                    plan_id=plan_id,
                    step_id=step["id"],
                )

                if (
                    maximum_steps is not None
                    and executed_now >= maximum_steps
                ):
                    payload["state"] = "ready"
                    self._persist(payload)

                    return {
                        "state": "paused",
                        "plan_id": plan_id,
                        "reason": "step_limit",
                        "executed_now": executed_now,
                        "plan": payload,
                    }

            if not pending_exists:
                payload["state"] = "completed"
                payload["metadata"]["completed_at_ms"] = int(
                    time.time() * 1000
                )
                self._persist(payload)

                self._publish(
                    "plan.completed",
                    {
                        "plan_id": plan_id,
                        "goal": payload.get("goal", ""),
                    },
                    sender="ned",
                    recipient="king",
                )
                self._log(
                    "info",
                    "ned",
                    "plan.completed",
                    plan_id=plan_id,
                )

                return {
                    "state": "completed",
                    "plan_id": plan_id,
                    "executed_now": executed_now,
                    "plan": payload,
                }

            if not progress:
                payload["state"] = "failed"
                payload["metadata"]["failure_reason"] = (
                    "No executable step was found."
                )
                self._persist(payload)

                return {
                    "state": "failed",
                    "plan_id": plan_id,
                    "error": "No executable step was found.",
                    "executed_now": executed_now,
                    "plan": payload,
                }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rachel-task-executor"
    )
    parser.add_argument(
        "--database",
        default=str(
            Path(__file__).resolve().parents[2]
            / "STATE"
            / "task-plans.db"
        ),
    )

    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )
    commands.add_parser("status")

    run_parser = commands.add_parser("run")
    run_parser.add_argument("--plan-id", required=True)
    run_parser.add_argument(
        "--approved-step",
        action="append",
        default=[],
    )
    run_parser.add_argument(
        "--approve-all",
        action="store_true",
    )
    run_parser.add_argument(
        "--maximum-steps",
        type=int,
    )

    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    executor = TaskExecutor(
        PlanStore(arguments.database)
    )

    if arguments.command == "status":
        print(
            json.dumps(
                executor.status(),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if (
        arguments.maximum_steps is not None
        and arguments.maximum_steps < 1
    ):
        raise ExecutionError(
            "Maximum steps must be greater than zero."
        )

    result = executor.execute(
        plan_id=arguments.plan_id,
        approved_steps=set(arguments.approved_step),
        approve_all=arguments.approve_all,
        maximum_steps=arguments.maximum_steps,
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )

    if result["state"] == "awaiting_approval":
        return 3

    if result["state"] == "failed":
        return 2

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ExecutionError as error:
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
