import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_CORE" / "src"))
sys.path.insert(
    0,
    str(
        ROOT
        / "RACHEL_PLATFORM"
        / "RUNTIME"
        / "SRC"
    ),
)

from cognitive_runtime import extract_task_goal
from task_runtime import TaskOrchestrator, TaskRuntimeError


class FakeTool:
    def __init__(
        self,
        name,
        member,
        effect,
        description="Test tool",
    ):
        self.name = name
        self.member = member
        self.effect = effect
        self.description = description
        self.parameters = {}


class FakeCoordinator:
    def __init__(self):
        self.registry = {
            "runtime.doctor": FakeTool(
                "runtime.doctor",
                "jhon",
                "status",
            ),
            "arya.run": FakeTool(
                "arya.run",
                "arya",
                "execute",
            ),
        }

    def list_tools(self):
        return [
            {
                "name": tool.name,
                "member": tool.member,
                "effect": tool.effect,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in self.registry.values()
        ]

    def invoke(
        self,
        name,
        arguments=None,
        approved=False,
    ):
        return {
            "state": "completed",
            "tool": name,
            "result": {
                "approved": approved,
                "arguments": arguments or {},
            },
        }


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeModel:
    def __init__(self, payload):
        self.payload = payload

    def generate(self, messages, system_prompt):
        return FakeResponse(
            json.dumps(
                self.payload,
                ensure_ascii=False,
            )
        )


class TaskRuntimeTests(unittest.TestCase):
    def test_detects_task_request(self):
        goal = extract_task_goal(
            "Rachel, planeje criar um site institucional"
        )
        self.assertEqual(
            goal,
            "criar um site institucional",
        )

    def test_common_chat_is_not_task_request(self):
        self.assertIsNone(
            extract_task_goal(
                "Qual linguagem voce recomenda?"
            )
        )

    def test_model_plan_is_secured_by_registry(self):
        payload = {
            "steps": [
                {
                    "id": "inspect",
                    "title": "Inspect",
                    "tool": "runtime.doctor",
                    "effect": "delete",
                    "member": "unknown",
                    "arguments": {},
                    "depends_on": [],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as directory:
            orchestrator = TaskOrchestrator(
                database=Path(directory) / "plans.db",
                coordinator=FakeCoordinator(),
                model=FakeModel(payload),
            )

            plan = orchestrator.create_plan(
                "Inspect the runtime"
            )

            self.assertEqual(
                plan["steps"][0]["effect"],
                "status",
            )
            self.assertEqual(
                plan["steps"][0]["member"],
                "jhon",
            )

    def test_unknown_model_tool_is_rejected(self):
        payload = {
            "steps": [
                {
                    "id": "invalid",
                    "title": "Invalid",
                    "tool": "invented.tool",
                    "arguments": {},
                    "depends_on": [],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as directory:
            orchestrator = TaskOrchestrator(
                database=Path(directory) / "plans.db",
                coordinator=FakeCoordinator(),
                model=FakeModel(payload),
            )

            with self.assertRaises(TaskRuntimeError):
                orchestrator.create_plan(
                    "Invalid task"
                )

    def test_manual_plan_executes_end_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            orchestrator = TaskOrchestrator(
                database=Path(directory) / "plans.db",
                coordinator=FakeCoordinator(),
                model=FakeModel({"steps": []}),
            )

            plan = orchestrator.create_plan(
                "Inspect and execute",
                specifications=[
                    {
                        "id": "inspect",
                        "title": "Inspect",
                        "tool": "runtime.doctor",
                        "arguments": {},
                        "depends_on": [],
                    },
                    {
                        "id": "execute",
                        "title": "Execute",
                        "tool": "arya.run",
                        "arguments": {
                            "command": "python",
                            "arguments": ["test.py"],
                        },
                        "depends_on": ["inspect"],
                    },
                ],
                source="test",
            )

            blocked = orchestrator.execute(
                plan["id"]
            )

            self.assertEqual(
                blocked["state"],
                "awaiting_approval",
            )

            completed = orchestrator.execute(
                plan["id"],
                approved_steps={"execute"},
            )

            self.assertEqual(
                completed["state"],
                "completed",
            )


if __name__ == "__main__":
    unittest.main()
