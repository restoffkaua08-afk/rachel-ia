from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from runtime_paths import ROOT, STATE
from task_runtime import TaskOrchestrator


POLICY_PATH = ROOT / "RACHEL_AGENT" / "CONFIG" / "professional-agent-policy.json"
DEFAULT_DATABASE = STATE / "professional-agent-runs.db"


class AgentLoopError(RuntimeError):
    pass


@dataclass(frozen=True)
class AgentBudget:
    profile: str
    maximum_iterations: int
    maximum_tool_calls: int
    wall_clock_limit_seconds: int
    maximum_consecutive_failures: int


class AgentRunStore:
    def __init__(self, database: str | Path | None = None) -> None:
        self.database = Path(database or DEFAULT_DATABASE)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(str(self.database), timeout=10)) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_runs (
                    id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    current_plan_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at_ms INTEGER NOT NULL,
                    updated_at_ms INTEGER NOT NULL
                )
                """
            )
            connection.commit()

    def create(self, payload: dict[str, Any]) -> None:
        now = int(time.time() * 1000)
        payload["created_at_ms"] = now
        payload["updated_at_ms"] = now
        with closing(sqlite3.connect(str(self.database), timeout=10)) as connection:
            connection.execute(
                """
                INSERT INTO agent_runs
                (id, state, goal, current_plan_id, payload, created_at_ms, updated_at_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["id"],
                    payload["state"],
                    payload["goal"],
                    payload["current_plan_id"],
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    now,
                    now,
                ),
            )
            connection.commit()

    def save(self, payload: dict[str, Any]) -> None:
        now = int(time.time() * 1000)
        payload["updated_at_ms"] = now
        with closing(sqlite3.connect(str(self.database), timeout=10)) as connection:
            connection.execute(
                """
                UPDATE agent_runs
                SET state = ?, current_plan_id = ?, payload = ?, updated_at_ms = ?
                WHERE id = ?
                """,
                (
                    payload["state"],
                    payload["current_plan_id"],
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    now,
                    payload["id"],
                ),
            )
            if connection.total_changes != 1:
                raise AgentLoopError(f"Agent run was not updated: {payload['id']}")
            connection.commit()

    def get(self, run_id: str) -> dict[str, Any] | None:
        with closing(sqlite3.connect(str(self.database), timeout=10)) as connection:
            row = connection.execute(
                "SELECT payload FROM agent_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(row[0])
        if not isinstance(payload, dict):
            raise AgentLoopError("Stored agent payload is invalid")
        return payload

    def list(self, limit: int = 20) -> list[dict[str, Any]]:
        maximum = max(1, min(int(limit), 100))
        with closing(sqlite3.connect(str(self.database), timeout=10)) as connection:
            rows = connection.execute(
                "SELECT payload FROM agent_runs ORDER BY updated_at_ms DESC LIMIT ?",
                (maximum,),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]


class AgentLoopRuntime:
    def __init__(
        self,
        *,
        orchestrator: TaskOrchestrator | None = None,
        store: AgentRunStore | None = None,
        policy_path: str | Path | None = None,
    ) -> None:
        self.orchestrator = orchestrator or TaskOrchestrator()
        self.store = store or AgentRunStore()
        self.policy_path = Path(policy_path or POLICY_PATH)
        self.policy = self._load_policy()

    def _load_policy(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.policy_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as error:
            raise AgentLoopError(f"Invalid professional agent policy: {error}") from error
        if not isinstance(payload, dict) or payload.get("state") != "enabled-governed-foreground":
            raise AgentLoopError("Professional agent policy is not enabled")
        execution = payload.get("execution")
        authorization = payload.get("authorization")
        if not isinstance(execution, dict) or execution.get("foreground_only") is not True:
            raise AgentLoopError("Agent must remain foreground-only")
        if not isinstance(authorization, dict) or authorization.get("self_approval") is not False:
            raise AgentLoopError("Agent self-approval must remain disabled")
        return payload

    def _budget(self, goal: str, requested_profile: str | None) -> AgentBudget:
        selection = self.policy["profile_selection"]
        profiles = self.policy["budget_profiles"]
        hard_caps = self.policy["hard_caps"]

        if requested_profile is not None:
            profile = str(requested_profile).strip().casefold()
            if profile not in profiles:
                raise AgentLoopError(f"Unknown budget profile: {requested_profile}")
        else:
            normalized = " ".join(goal.casefold().split())
            keywords = [str(item).casefold() for item in selection["project_profile_keywords"]]
            profile = (
                "project"
                if any(keyword in normalized for keyword in keywords)
                else str(selection["default_profile"])
            )

        values = profiles[profile]
        budget = AgentBudget(
            profile=profile,
            maximum_iterations=int(values["maximum_iterations"]),
            maximum_tool_calls=int(values["maximum_tool_calls"]),
            wall_clock_limit_seconds=int(values["wall_clock_limit_seconds"]),
            maximum_consecutive_failures=int(values["maximum_consecutive_failures"]),
        )
        for key, value in asdict(budget).items():
            if key == "profile":
                continue
            if value < 1 or value > int(hard_caps[key]):
                raise AgentLoopError(f"Budget profile exceeds hard cap: {key}")
        return budget

    @staticmethod
    def _compact(value: Any, depth: int = 0) -> Any:
        if depth > 5:
            return "<depth-limit>"
        if isinstance(value, str):
            return value if len(value) <= 2_000 else value[:2_000] + "...<truncated>"
        if isinstance(value, list):
            return [AgentLoopRuntime._compact(item, depth + 1) for item in value[:12]]
        if isinstance(value, dict):
            return {
                str(key): AgentLoopRuntime._compact(item, depth + 1)
                for key, item in list(value.items())[:40]
                if key not in {"approval_id", "approval_ids"}
            }
        return value

    @staticmethod
    def _completed_step_ids(plan: dict[str, Any]) -> set[str]:
        return {
            str(step.get("id"))
            for step in plan.get("steps", [])
            if isinstance(step, dict) and step.get("state") == "completed"
        }

    @staticmethod
    def _find_step(plan: dict[str, Any], step_id: str) -> dict[str, Any] | None:
        for step in plan.get("steps", []):
            if isinstance(step, dict) and str(step.get("id")) == step_id:
                return step
        return None

    def _verify_step(self, step: dict[str, Any]) -> dict[str, Any]:
        tool = str(step.get("tool", ""))
        response = step.get("result")
        if not isinstance(response, dict):
            return {
                "verified": False,
                "scope": "tool-result",
                "reason": "missing-tool-result",
            }
        if response.get("state") != "completed":
            return {
                "verified": False,
                "scope": "tool-state",
                "reason": f"tool-state-{response.get('state')}",
            }

        result = response.get("result")
        if not isinstance(result, dict):
            return {
                "verified": True,
                "scope": "tool-completion-contract",
                "reason": "completed-with-nonobject-result",
            }

        if "verified" in result:
            return {
                "verified": result.get("verified") is True,
                "scope": "post-action",
                "reason": "explicit-verification-field",
            }

        if tool.startswith("dev.") and tool != "dev.detect":
            return {
                "verified": result.get("successful") is True,
                "scope": "process-returncode",
                "reason": "development-validation",
            }

        if tool == "process.start":
            return {
                "verified": result.get("owned_by_rachel") is True and result.get("running") is True,
                "scope": "process-ownership",
                "reason": "owned-process-start",
            }

        if tool == "process.stop":
            return {
                "verified": result.get("verified_stopped") is True,
                "scope": "process-stop",
                "reason": "owned-process-stop",
            }

        if tool == "git.branch.create":
            return {
                "verified": result.get("created") is True,
                "scope": "git-branch",
                "reason": "branch-visible-after-create",
            }

        if tool == "bran.remember":
            return {
                "verified": result.get("state") == "stored",
                "scope": "memory-store",
                "reason": "memory-storage-state",
            }

        return {
            "verified": True,
            "scope": "tool-completion-contract",
            "reason": "no-stronger-verifier-required",
        }

    def _publish(self, event: str, payload: dict[str, Any]) -> None:
        king = getattr(self.orchestrator.coordinator, "king", None)
        if king is not None and hasattr(king, "publish"):
            king.publish(event, payload, sender="rachel", recipient="ned")

    def _new_run_payload(
        self,
        goal: str,
        plan: dict[str, Any],
        budget: AgentBudget,
    ) -> dict[str, Any]:
        return {
            "id": "agent_" + uuid.uuid4().hex,
            "goal": goal,
            "state": "ready",
            "current_plan_id": str(plan["id"]),
            "root_plan_id": str(plan["id"]),
            "plan_history": [str(plan["id"])],
            "budget": asdict(budget),
            "counters": {
                "iterations": 0,
                "tool_calls": 0,
                "consecutive_failures": 0,
                "repairs": 0,
                "active_ms": 0,
            },
            "control": {
                "pause_requested": False,
                "cancel_requested": False,
            },
            "observations": [],
            "last_result": None,
            "last_error": None,
            "completion": None,
        }

    def start(
        self,
        goal: str,
        *,
        budget_profile: str | None = None,
        specifications: list[dict[str, Any]] | None = None,
        execute: bool = True,
        cancel_check: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        clean_goal = " ".join(str(goal).strip().split())
        if not clean_goal:
            raise AgentLoopError("Agent goal cannot be empty")
        budget = self._budget(clean_goal, budget_profile)
        plan = self.orchestrator.create_plan(
            clean_goal,
            specifications=specifications,
            source="professional-agent",
        )
        payload = self._new_run_payload(clean_goal, plan, budget)
        self.store.create(payload)
        self._publish(
            "agent.goal.created",
            {
                "run_id": payload["id"],
                "plan_id": payload["current_plan_id"],
                "budget_profile": budget.profile,
            },
        )
        if not execute:
            return self.public(payload)
        return self.continue_run(payload["id"], cancel_check=cancel_check)

    def _budget_exhausted(self, payload: dict[str, Any]) -> str | None:
        budget = payload["budget"]
        counters = payload["counters"]
        if counters["iterations"] >= budget["maximum_iterations"]:
            return "maximum_iterations"
        if counters["tool_calls"] >= budget["maximum_tool_calls"]:
            return "maximum_tool_calls"
        if counters["active_ms"] >= budget["wall_clock_limit_seconds"] * 1000:
            return "wall_clock_limit_seconds"
        if counters["consecutive_failures"] >= budget["maximum_consecutive_failures"]:
            return "maximum_consecutive_failures"
        return None

    def _append_observation(
        self,
        payload: dict[str, Any],
        observation: dict[str, Any],
    ) -> None:
        payload.setdefault("observations", []).append(self._compact(observation))
        payload["observations"] = payload["observations"][-100:]

    def _repair(self, payload: dict[str, Any], failure: dict[str, Any]) -> None:
        counters = payload["counters"]
        counters["repairs"] += 1
        observations = payload.get("observations", [])[-8:]
        repair_goal = (
            f"Objetivo original: {payload['goal']}\n\n"
            "O plano anterior não pôde continuar com segurança. Crie um plano de reparo somente para "
            "o trabalho ainda necessário. Não trate autorizações anteriores como válidas e não repita "
            "mutações já confirmadas, a menos que a evidência mostre que precisam ser corrigidas.\n\n"
            f"Falha observada: {json.dumps(self._compact(failure), ensure_ascii=False)}\n"
            f"Observações confirmadas: {json.dumps(self._compact(observations), ensure_ascii=False)}"
        )
        child = self.orchestrator.create_plan(
            repair_goal,
            specifications=None,
            source="professional-agent-repair",
        )
        payload["current_plan_id"] = str(child["id"])
        payload["plan_history"].append(str(child["id"]))
        self._publish(
            "agent.repair.created",
            {
                "run_id": payload["id"],
                "plan_id": child["id"],
                "repair_number": counters["repairs"],
            },
        )

    def continue_run(
        self,
        run_id: str,
        *,
        approval_ids: dict[str, str] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        payload = self.store.get(run_id)
        if payload is None:
            raise AgentLoopError(f"Agent run not found: {run_id}")
        if payload["state"] == "completed":
            return self.public(payload)
        if payload["state"] == "cancelled":
            raise AgentLoopError("Cancelled agent run cannot be resumed")
        if payload["state"] == "failed":
            raise AgentLoopError("Failed agent run cannot be resumed without a repair child plan")

        payload["control"]["pause_requested"] = False
        payload["state"] = "running"
        approvals = dict(approval_ids or {})
        slice_started = time.perf_counter()

        try:
            while True:
                payload["counters"]["active_ms"] += int(
                    (time.perf_counter() - slice_started) * 1000
                )
                slice_started = time.perf_counter()

                if (cancel_check and cancel_check()) or payload["control"]["cancel_requested"]:
                    payload["state"] = "cancelled"
                    payload["completion"] = {"reason": "cancel_requested"}
                    self.store.save(payload)
                    self._publish("agent.cancelled", {"run_id": run_id})
                    return self.public(payload)

                if payload["control"]["pause_requested"]:
                    payload["state"] = "paused"
                    self.store.save(payload)
                    return self.public(payload)

                exhausted = self._budget_exhausted(payload)
                if exhausted:
                    payload["state"] = "paused"
                    payload["completion"] = {
                        "reason": "budget_exhausted",
                        "dimension": exhausted,
                    }
                    self.store.save(payload)
                    self._publish(
                        "agent.budget.exhausted",
                        {"run_id": run_id, "dimension": exhausted},
                    )
                    return self.public(payload)

                before = self.orchestrator.show(payload["current_plan_id"])
                before_completed = self._completed_step_ids(before)
                result = self.orchestrator.execute(
                    payload["current_plan_id"],
                    approval_ids=approvals,
                    maximum_steps=1,
                )
                approvals = {}
                payload["counters"]["iterations"] += 1

                state = str(result.get("state", "failed"))
                executed_now = int(result.get("executed_now", 0) or 0)
                if executed_now > 0:
                    payload["counters"]["tool_calls"] += executed_now
                elif state == "awaiting_approval":
                    payload["counters"]["tool_calls"] += 1
                elif state == "failed" and result.get("failed_step"):
                    payload["counters"]["tool_calls"] += 1

                payload["last_result"] = self._compact(result)

                if state == "awaiting_approval":
                    payload["state"] = "awaiting_approval"
                    payload["completion"] = None
                    self.store.save(payload)
                    self._publish(
                        "agent.awaiting_approval",
                        {
                            "run_id": run_id,
                            "plan_id": payload["current_plan_id"],
                            "step_id": result.get("approval", {}).get("step_id"),
                        },
                    )
                    public = self.public(payload)
                    public["approval"] = result.get("approval")
                    public["plan"] = result.get("plan")
                    return public

                if state == "failed":
                    failure = {
                        "plan_id": payload["current_plan_id"],
                        "step_id": result.get("failed_step"),
                        "error": result.get("error"),
                        "kind": "execution-failure",
                    }
                    payload["last_error"] = self._compact(failure)
                    payload["counters"]["consecutive_failures"] += 1
                    self._append_observation(payload, failure)
                    if self._budget_exhausted(payload) == "maximum_consecutive_failures":
                        payload["state"] = "failed"
                        payload["completion"] = {
                            "reason": "failure_budget_exhausted",
                            "failure": self._compact(failure),
                        }
                        self.store.save(payload)
                        return self.public(payload)
                    self._repair(payload, failure)
                    self.store.save(payload)
                    continue

                after_plan = result.get("plan")
                if not isinstance(after_plan, dict):
                    after_plan = self.orchestrator.show(payload["current_plan_id"])
                after_completed = self._completed_step_ids(after_plan)
                newly_completed = sorted(after_completed - before_completed)

                verification_failed = None
                for step_id in newly_completed:
                    step = self._find_step(after_plan, step_id)
                    if step is None:
                        continue
                    verification = self._verify_step(step)
                    observation = {
                        "kind": "step-observation",
                        "plan_id": payload["current_plan_id"],
                        "step_id": step_id,
                        "tool": step.get("tool"),
                        "verification": verification,
                        "result": self._compact(step.get("result")),
                    }
                    self._append_observation(payload, observation)
                    if not verification["verified"]:
                        verification_failed = observation
                        break

                if verification_failed is not None:
                    payload["counters"]["consecutive_failures"] += 1
                    payload["last_error"] = self._compact(verification_failed)
                    if self._budget_exhausted(payload) == "maximum_consecutive_failures":
                        payload["state"] = "failed"
                        payload["completion"] = {
                            "reason": "verification_failure_budget_exhausted",
                            "failure": self._compact(verification_failed),
                        }
                        self.store.save(payload)
                        return self.public(payload)
                    self._repair(payload, verification_failed)
                    self.store.save(payload)
                    continue

                if newly_completed:
                    payload["counters"]["consecutive_failures"] = 0
                    payload["last_error"] = None

                if state == "completed":
                    payload["state"] = "completed"
                    payload["completion"] = {
                        "reason": "goal-plan-completed",
                        "verified": True,
                        "plan_id": payload["current_plan_id"],
                    }
                    self.store.save(payload)
                    self._publish(
                        "agent.completed",
                        {
                            "run_id": run_id,
                            "plan_id": payload["current_plan_id"],
                            "iterations": payload["counters"]["iterations"],
                            "tool_calls": payload["counters"]["tool_calls"],
                        },
                    )
                    return self.public(payload)

                if state != "paused":
                    unknown = {
                        "kind": "unknown-execution-state",
                        "state": state,
                        "plan_id": payload["current_plan_id"],
                    }
                    payload["state"] = "failed"
                    payload["last_error"] = unknown
                    payload["completion"] = {"reason": "unknown_state"}
                    self.store.save(payload)
                    return self.public(payload)

                self.store.save(payload)

        finally:
            latest = self.store.get(run_id)
            if latest is not None and latest.get("state") == "running":
                latest["counters"]["active_ms"] += int(
                    (time.perf_counter() - slice_started) * 1000
                )
                self.store.save(latest)

    def pause(self, run_id: str) -> dict[str, Any]:
        payload = self.store.get(run_id)
        if payload is None:
            raise AgentLoopError(f"Agent run not found: {run_id}")
        if payload["state"] in {"completed", "cancelled", "failed"}:
            return self.public(payload)
        payload["control"]["pause_requested"] = True
        payload["state"] = "paused"
        self.store.save(payload)
        self._publish("agent.paused", {"run_id": run_id})
        return self.public(payload)

    def cancel(self, run_id: str) -> dict[str, Any]:
        payload = self.store.get(run_id)
        if payload is None:
            raise AgentLoopError(f"Agent run not found: {run_id}")
        if payload["state"] == "completed":
            return self.public(payload)
        payload["control"]["cancel_requested"] = True
        payload["state"] = "cancelled"
        payload["completion"] = {"reason": "cancel_requested"}
        self.store.save(payload)
        self._publish("agent.cancelled", {"run_id": run_id})
        return self.public(payload)

    def show(self, run_id: str) -> dict[str, Any]:
        payload = self.store.get(run_id)
        if payload is None:
            raise AgentLoopError(f"Agent run not found: {run_id}")
        return self.public(payload)

    def list(self, limit: int = 20) -> list[dict[str, Any]]:
        return [self.public(item) for item in self.store.list(limit)]

    @staticmethod
    def public(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": payload["id"],
            "goal": payload["goal"],
            "state": payload["state"],
            "current_plan_id": payload["current_plan_id"],
            "root_plan_id": payload["root_plan_id"],
            "plan_history": list(payload.get("plan_history", [])),
            "budget": dict(payload["budget"]),
            "counters": dict(payload["counters"]),
            "observations": list(payload.get("observations", []))[-20:],
            "last_error": payload.get("last_error"),
            "completion": payload.get("completion"),
            "created_at_ms": payload.get("created_at_ms"),
            "updated_at_ms": payload.get("updated_at_ms"),
            "background_execution": False,
            "unattended_execution": False,
            "approval_inheritance": False,
        }
