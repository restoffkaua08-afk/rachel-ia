import tempfile
import unittest
from pathlib import Path
import sys

SRC = Path(__file__).resolve().parents[1] / "SRC"
sys.path.insert(0, str(SRC))

from task_executor import TaskExecutor
from task_planner import NedTaskPlanner, PlanStore


class FakeEvents:
    def __init__(self):
        self.events = []

    def publish(
        self,
        event_type,
        payload,
        sender,
        recipient,
    ):
        event = {
            "id": f"event-{len(self.events) + 1}",
            "type": event_type,
            "payload": payload,
            "sender": sender,
            "recipient": recipient,
        }
        self.events.append(event)
        return event


class FakeLogger:
    def __init__(self):
        self.entries = []

    def write(self, level, component, event, **fields):
        self.entries.append(
            {
                "level": level,
                "component": component,
                "event": event,
                "fields": fields,
            }
        )


class FakeCoordinator:
    def __init__(self):
        self.king = FakeEvents()
        self.jhon = FakeLogger()
        self.calls = []
        self.fail_tools = set()

    def invoke(self, name, arguments=None, approved=False):
        self.calls.append(
            {
                "name": name,
                "arguments": arguments or {},
                "approved": approved,
            }
        )

        if name in self.fail_tools:
            raise RuntimeError("simulated tool failure")

        return {
            "state": "completed",
            "tool": name,
            "result": {"ok": True},
        }


class TaskExecutorTests(unittest.TestCase):
    def create_runtime(self):
        temporary = tempfile.TemporaryDirectory()
        database = Path(temporary.name) / "plans.db"
        store = PlanStore(database)
        coordinator = FakeCoordinator()
        executor = TaskExecutor(store, coordinator)
        return temporary, store, coordinator, executor

    def test_read_only_plan_completes(self):
        temporary, store, coordinator, executor = (
            self.create_runtime()
        )

        try:
            plan = NedTaskPlanner().create(
                "Inspect runtime",
                [
                    {
                        "id": "inspect",
                        "title": "Inspect runtime",
                        "member": "jhon",
                        "tool": "runtime.doctor",
                        "effect": "status",
                    }
                ],
            )
            store.save(plan)

            result = executor.execute(plan.id)

            self.assertEqual(result["state"], "completed")
            self.assertEqual(len(coordinator.calls), 1)
            self.assertFalse(coordinator.calls[0]["approved"])
        finally:
            temporary.cleanup()

    def test_write_step_waits_for_approval(self):
        temporary, store, coordinator, executor = (
            self.create_runtime()
        )

        try:
            plan = NedTaskPlanner().create(
                "Create file",
                [
                    {
                        "id": "create_file",
                        "title": "Create file",
                        "member": "arya",
                        "tool": "arya.run",
                        "effect": "create",
                    }
                ],
            )
            store.save(plan)

            result = executor.execute(plan.id)

            self.assertEqual(
                result["state"],
                "awaiting_approval",
            )
            self.assertEqual(len(coordinator.calls), 0)
        finally:
            temporary.cleanup()

    def test_approved_plan_resumes_and_completes(self):
        temporary, store, coordinator, executor = (
            self.create_runtime()
        )

        try:
            plan = NedTaskPlanner().create(
                "Inspect and create",
                [
                    {
                        "id": "inspect",
                        "title": "Inspect",
                        "member": "jhon",
                        "tool": "runtime.doctor",
                        "effect": "status",
                    },
                    {
                        "id": "create",
                        "title": "Create",
                        "member": "arya",
                        "tool": "arya.run",
                        "effect": "create",
                        "depends_on": ["inspect"],
                    },
                ],
            )
            store.save(plan)

            first = executor.execute(plan.id)

            self.assertEqual(
                first["state"],
                "awaiting_approval",
            )
            self.assertEqual(len(coordinator.calls), 1)

            second = executor.execute(
                plan.id,
                approved_steps={"create"},
            )

            self.assertEqual(second["state"], "completed")
            self.assertEqual(len(coordinator.calls), 2)
            self.assertTrue(coordinator.calls[-1]["approved"])
        finally:
            temporary.cleanup()

    def test_completed_steps_are_not_repeated(self):
        temporary, store, coordinator, executor = (
            self.create_runtime()
        )

        try:
            plan = NedTaskPlanner().create(
                "Two inspections",
                [
                    {
                        "id": "first",
                        "title": "First",
                        "member": "jhon",
                        "tool": "runtime.doctor",
                        "effect": "status",
                    },
                    {
                        "id": "second",
                        "title": "Second",
                        "member": "tyrion",
                        "tool": "tyrion.health",
                        "effect": "status",
                        "depends_on": ["first"],
                    },
                ],
            )
            store.save(plan)

            paused = executor.execute(
                plan.id,
                maximum_steps=1,
            )

            self.assertEqual(paused["state"], "paused")
            self.assertEqual(len(coordinator.calls), 1)

            completed = executor.execute(plan.id)

            self.assertEqual(
                completed["state"],
                "completed",
            )
            self.assertEqual(len(coordinator.calls), 2)
            self.assertEqual(
                coordinator.calls[0]["name"],
                "runtime.doctor",
            )
            self.assertEqual(
                coordinator.calls[1]["name"],
                "tyrion.health",
            )
        finally:
            temporary.cleanup()

    def test_failure_is_persisted(self):
        temporary, store, coordinator, executor = (
            self.create_runtime()
        )

        try:
            coordinator.fail_tools.add("runtime.doctor")
            plan = NedTaskPlanner().create(
                "Fail safely",
                [
                    {
                        "id": "failure",
                        "title": "Failure",
                        "member": "jhon",
                        "tool": "runtime.doctor",
                        "effect": "status",
                    }
                ],
            )
            store.save(plan)

            result = executor.execute(plan.id)
            persisted = store.get(plan.id)

            self.assertEqual(result["state"], "failed")
            self.assertEqual(persisted["state"], "failed")
            self.assertEqual(
                persisted["steps"][0]["state"],
                "failed",
            )
        finally:
            temporary.cleanup()

    def test_unknown_approval_is_rejected(self):
        temporary, store, coordinator, executor = (
            self.create_runtime()
        )

        try:
            plan = NedTaskPlanner().create(
                "Inspect",
                [
                    {
                        "id": "inspect",
                        "title": "Inspect",
                        "member": "jhon",
                        "tool": "runtime.doctor",
                        "effect": "status",
                    }
                ],
            )
            store.save(plan)

            with self.assertRaises(Exception):
                executor.execute(
                    plan.id,
                    approved_steps={"unknown"},
                )
        finally:
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
