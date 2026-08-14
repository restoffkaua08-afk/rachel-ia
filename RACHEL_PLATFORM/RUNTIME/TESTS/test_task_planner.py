import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "SRC"
sys.path.insert(0, str(SRC))

from task_planner import NedTaskPlanner, PlanError, PlanStore


class TaskPlannerTests(unittest.TestCase):
    def setUp(self):
        self.planner = NedTaskPlanner()

    def test_read_only_plan_is_ready(self):
        plan = self.planner.create(
            "Inspect the project",
            [
                {
                    "title": "List project files",
                    "member": "arya",
                    "tool": "arya.list",
                    "effect": "list",
                }
            ],
        )

        self.assertEqual(plan.state, "ready")
        self.assertFalse(plan.steps[0].approval_required)

    def test_write_plan_requires_approval(self):
        plan = self.planner.create(
            "Create a project file",
            [
                {
                    "title": "Create index file",
                    "member": "arya",
                    "tool": "arya.run",
                    "effect": "create",
                }
            ],
        )

        self.assertEqual(plan.state, "awaiting_approval")
        self.assertTrue(plan.steps[0].approval_required)
        self.assertEqual(plan.steps[0].risk, "medium")

    def test_unknown_dependency_is_rejected(self):
        with self.assertRaises(PlanError):
            self.planner.create(
                "Invalid plan",
                [
                    {
                        "title": "Second step",
                        "tool": "runtime.doctor",
                        "effect": "inspect",
                        "depends_on": ["missing_step"],
                    }
                ],
            )

    def test_dependency_cycle_is_rejected(self):
        with self.assertRaises(PlanError):
            self.planner.create(
                "Cyclic plan",
                [
                    {
                        "id": "step_a",
                        "title": "Step A",
                        "tool": "runtime.doctor",
                        "effect": "inspect",
                        "depends_on": ["step_b"],
                    },
                    {
                        "id": "step_b",
                        "title": "Step B",
                        "tool": "runtime.doctor",
                        "effect": "inspect",
                        "depends_on": ["step_a"],
                    },
                ],
            )

    def test_plan_is_persisted_and_recovered(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "plans.db"
            store = PlanStore(database)
            plan = self.planner.create(
                "Check runtime health",
                [
                    {
                        "title": "Inspect runtime",
                        "member": "jhon",
                        "tool": "runtime.doctor",
                        "effect": "status",
                    }
                ],
            )

            store.save(plan)
            recovered = store.get(plan.id)

            self.assertIsNotNone(recovered)
            self.assertEqual(recovered["id"], plan.id)
            self.assertEqual(recovered["goal"], plan.goal)

    def test_generated_step_ids_are_stable(self):
        specification = [
            {
                "title": "Inspect runtime",
                "member": "jhon",
                "tool": "runtime.doctor",
                "effect": "status",
            }
        ]

        first = self.planner.create("First", specification)
        second = self.planner.create("Second", specification)

        self.assertEqual(first.steps[0].id, second.steps[0].id)


if __name__ == "__main__":
    unittest.main()
