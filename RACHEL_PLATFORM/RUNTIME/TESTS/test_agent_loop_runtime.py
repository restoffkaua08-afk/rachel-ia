from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_CORE" / "src"))
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))

from agent_loop_runtime import AgentLoopRuntime, AgentRunStore
from task_runtime import TaskOrchestrator


@dataclass
class FakeSpec:
    name: str
    member: str
    effect: str
    description: str = "fake"
    parameters: dict | None = None


class FakeLearning:
    def capture_event(self, **kwargs):
        return None


class FakeModel:
    provider_name = "fake"
    model_name = "fake-model"

    def generate(self, messages, system):
        raise AssertionError("model should not run in provided-specification tests")


class FakeCoordinator:
    def __init__(self):
        self.registry = {
            "read.fake": FakeSpec("read.fake", "visao", "read", parameters={}),
            "write.fake": FakeSpec("write.fake", "arya", "write", parameters={}),
        }
        self.calls = []
        self.king = SimpleNamespace(publish=lambda *args, **kwargs: None)
        self.jhon = SimpleNamespace(write=lambda *args, **kwargs: None)

    def list_tools(self):
        return [
            {
                "name": item.name,
                "member": item.member,
                "effect": item.effect,
                "description": item.description,
                "parameters": item.parameters or {},
            }
            for item in self.registry.values()
        ]

    def invoke(self, name, arguments, approval_id=None):
        self.calls.append((name, dict(arguments), approval_id))
        if name == "write.fake" and approval_id is None:
            return {
                "state": "approval_required",
                "tool": name,
                "member": "arya",
                "approval": {
                    "id": "approval_fake",
                    "effect": "write",
                    "risk": "medium",
                },
                "policy": {"allowed": False, "approval_required": True},
            }
        return {
            "state": "completed",
            "tool": name,
            "member": self.registry[name].member,
            "result": {"verified": True, "value": arguments.get("value")},
            "policy": {"allowed": True, "approval_required": False},
        }


class RepairOrchestrator:
    def __init__(self):
        self.coordinator = SimpleNamespace(
            king=SimpleNamespace(publish=lambda *args, **kwargs: None)
        )
        self.plans = {}
        self.created = 0

    def create_plan(self, goal, specifications=None, source="model"):
        self.created += 1
        plan_id = f"plan_{self.created}"
        verified = self.created > 1
        plan = {
            "id": plan_id,
            "goal": goal,
            "state": "ready",
            "steps": [
                {
                    "id": "step_1",
                    "tool": "filesystem.write",
                    "state": "planned",
                    "result": None,
                }
            ],
        }
        self.plans[plan_id] = plan
        self.plans[plan_id]["_next_verified"] = verified
        return {key: value for key, value in plan.items() if not key.startswith("_")}

    def show(self, plan_id):
        return self.plans[plan_id]

    def execute(self, plan_id, approval_ids=None, maximum_steps=None):
        plan = self.plans[plan_id]
        step = plan["steps"][0]
        step["state"] = "completed"
        step["result"] = {
            "state": "completed",
            "tool": "filesystem.write",
            "result": {"verified": plan["_next_verified"]},
        }
        plan["state"] = "completed"
        return {
            "state": "completed",
            "plan_id": plan_id,
            "executed_now": 1,
            "plan": plan,
        }


class AgentLoopRuntimeTests(unittest.TestCase):
    def build_runtime(self, directory: Path, coordinator=None):
        coordinator = coordinator or FakeCoordinator()
        orchestrator = TaskOrchestrator(
            database=directory / "plans.db",
            coordinator=coordinator,
            model=FakeModel(),
            learning=FakeLearning(),
        )
        runtime = AgentLoopRuntime(
            orchestrator=orchestrator,
            store=AgentRunStore(directory / "agent.db"),
            policy_path=ROOT / "RACHEL_AGENT" / "CONFIG" / "professional-agent-policy.json",
        )
        return runtime, coordinator

    def test_two_steps_run_one_checkpoint_at_a_time_until_completed(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime, coordinator = self.build_runtime(Path(temp))
            result = runtime.start(
                "Leia duas evidências",
                specifications=[
                    {"id": "one", "tool": "read.fake", "arguments": {"value": 1}, "depends_on": []},
                    {"id": "two", "tool": "read.fake", "arguments": {"value": 2}, "depends_on": ["one"]},
                ],
            )
            self.assertEqual("completed", result["state"])
            self.assertGreaterEqual(result["counters"]["iterations"], 2)
            self.assertEqual(2, result["counters"]["tool_calls"])
            self.assertEqual(2, len(coordinator.calls))
            self.assertTrue(result["completion"]["verified"])

    def test_approval_pauses_and_resume_uses_exact_step_binding(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime, coordinator = self.build_runtime(Path(temp))
            waiting = runtime.start(
                "Faça uma alteração governada",
                specifications=[
                    {"id": "write", "tool": "write.fake", "arguments": {"value": "x"}, "depends_on": []},
                ],
            )
            self.assertEqual("awaiting_approval", waiting["state"])
            self.assertEqual("write", waiting["approval"]["step_id"])
            self.assertEqual("approval_fake", waiting["approval"]["id"])

            completed = runtime.continue_run(
                waiting["id"],
                approval_ids={"write": "approval_fake"},
            )
            self.assertEqual("completed", completed["state"])
            self.assertEqual("approval_fake", coordinator.calls[-1][2])
            self.assertFalse(completed["approval_inheritance"])

    def test_cancel_check_stops_before_tool_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime, coordinator = self.build_runtime(Path(temp))
            created = runtime.start(
                "Não execute ainda",
                specifications=[
                    {"id": "one", "tool": "read.fake", "arguments": {}, "depends_on": []},
                ],
                execute=False,
            )
            cancelled = runtime.continue_run(created["id"], cancel_check=lambda: True)
            self.assertEqual("cancelled", cancelled["state"])
            self.assertEqual([], coordinator.calls)

    def test_failed_verification_creates_child_repair_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            orchestrator = RepairOrchestrator()
            runtime = AgentLoopRuntime(
                orchestrator=orchestrator,
                store=AgentRunStore(Path(temp) / "agent.db"),
                policy_path=ROOT / "RACHEL_AGENT" / "CONFIG" / "professional-agent-policy.json",
            )
            result = runtime.start("Corrija até verificar")
            self.assertEqual("completed", result["state"])
            self.assertEqual(2, len(result["plan_history"]))
            self.assertEqual(1, result["counters"]["repairs"])
            self.assertGreaterEqual(len(result["observations"]), 2)

    def test_project_keyword_selects_fixed_project_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime, _ = self.build_runtime(Path(temp))
            created = runtime.start(
                "Corrija o projeto e rode os testes",
                specifications=[
                    {"id": "one", "tool": "read.fake", "arguments": {}, "depends_on": []},
                ],
                execute=False,
            )
            self.assertEqual("project", created["budget"]["profile"])
            self.assertLessEqual(created["budget"]["maximum_iterations"], 60)
            self.assertFalse(created["background_execution"])
            self.assertFalse(created["unattended_execution"])


if __name__ == "__main__":
    unittest.main()
