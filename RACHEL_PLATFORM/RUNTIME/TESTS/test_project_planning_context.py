from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

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


class FakeProjectRuntime:
    def __init__(self):
        self.calls = []

    def context_for(self, scope, path, task, max_tokens=8000, max_files=19):
        self.calls.append(
            {
                "scope": scope,
                "path": path,
                "task": task,
                "max_tokens": max_tokens,
                "max_files": max_files,
            }
        )
        return {
            "items": [
                {
                    "path": "src/auth.py",
                    "content": "def refresh_access_token():\n    return 'ok'\n",
                }
            ],
            "estimated_tokens": 32,
            "file_count": 1,
            "truncated": False,
        }


class FakeCoordinator:
    def __init__(self):
        self.projects = FakeProjectRuntime()
        self.registry = {
            "runtime.doctor": FakeSpec(
                "runtime.doctor",
                "jhon",
                "status",
                parameters={},
            )
        }

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


class FakeResponse:
    def __init__(self, content):
        self.content = content


class CapturingModel:
    provider_name = "fake"
    model_name = "fake-model"

    def __init__(self):
        self.messages = []
        self.system_prompt = None

    def generate(self, messages, system_prompt):
        self.messages = messages
        self.system_prompt = system_prompt
        return FakeResponse(
            json.dumps(
                {
                    "steps": [
                        {
                            "id": "inspect",
                            "title": "Inspect",
                            "tool": "runtime.doctor",
                            "arguments": {},
                            "depends_on": [],
                        }
                    ]
                }
            )
        )


class ProjectPlanningContextTests(unittest.TestCase):
    def build(self, directory: str):
        coordinator = FakeCoordinator()
        model = CapturingModel()
        orchestrator = TaskOrchestrator(
            database=Path(directory) / "plans.db",
            coordinator=coordinator,
            model=model,
            learning=FakeLearning(),
        )
        return orchestrator, coordinator, model

    def test_project_goal_injects_bounded_context_into_model_message(self):
        with tempfile.TemporaryDirectory() as directory:
            orchestrator, coordinator, model = self.build(directory)

            plan = orchestrator.create_plan(
                "Corrija o bug no projeto de autenticacao"
            )

            self.assertEqual("ready", plan["state"])
            self.assertEqual(1, len(coordinator.projects.calls))
            call = coordinator.projects.calls[0]
            self.assertEqual("workspace", call["scope"])
            self.assertEqual(".", call["path"])
            self.assertLessEqual(call["max_tokens"], 8000)
            self.assertLessEqual(call["max_files"], 19)

            content = model.messages[0].content
            self.assertIn("[PROJECT_CONTEXT_BOUNDED]", content)
            self.assertIn("src/auth.py", content)
            self.assertIn("refresh_access_token", content)
            self.assertIn("project-intelligence", content)

    def test_agent_loop_model_planning_receives_bounded_project_context(self):
        with tempfile.TemporaryDirectory() as directory:
            orchestrator, coordinator, model = self.build(directory)
            runtime = AgentLoopRuntime(
                orchestrator=orchestrator,
                store=AgentRunStore(Path(directory) / "agent-runs.db"),
                policy_path=(
                    ROOT
                    / "RACHEL_AGENT"
                    / "CONFIG"
                    / "professional-agent-policy.json"
                ),
            )

            created = runtime.start(
                "Corrija o bug no projeto de autenticacao",
                execute=False,
            )

            self.assertEqual("ready", created["state"])
            self.assertEqual(1, len(coordinator.projects.calls))
            content = model.messages[0].content
            self.assertIn("[PROJECT_CONTEXT_BOUNDED]", content)
            self.assertIn("refresh_access_token", content)

    def test_non_project_goal_does_not_scan_project_context(self):
        with tempfile.TemporaryDirectory() as directory:
            orchestrator, coordinator, model = self.build(directory)

            orchestrator.create_plan("Mostre o status atual")

            self.assertEqual([], coordinator.projects.calls)
            self.assertNotIn(
                "[PROJECT_CONTEXT_BOUNDED]",
                model.messages[0].content,
            )


if __name__ == "__main__":
    unittest.main()
