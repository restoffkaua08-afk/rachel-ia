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
        self.approval_tools = {"arya.run"}
        self.invalid_approvals = set()
        self.sequence = 0

    def invoke(
        self,
        name,
        arguments=None,
        approval_id=None,
    ):
        self.calls.append(
            {
                "name": name,
                "arguments": arguments or {},
                "approval_id": approval_id,
            }
        )

        if name in self.fail_tools:
            raise RuntimeError("simulated tool failure")

        if approval_id in self.invalid_approvals:
            from security_runtime import ApprovalError
            raise ApprovalError("Approval expired")

        if name in self.approval_tools and approval_id is None:
            self.sequence += 1
            return {
                "state": "approval_required",
                "tool": name,
                "approval": {
                    "id": "approval_" + f"{self.sequence:032d}",
                    "tool": name,
                    "effect": "execute",
                    "risk": "medium",
                    "status": "pending",
                    "arguments_summary": "{}",
                },
            }

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
            self.assertIsNone(coordinator.calls[0]["approval_id"])
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
            self.assertEqual(len(coordinator.calls), 1)
            self.assertTrue(
                result["approval"]["id"].startswith("approval_")
            )
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
            approval_id = first["approval"]["id"]

            second = executor.execute(
                plan.id,
                approval_ids={
                    "create": approval_id,
                },
            )

            self.assertEqual(second["state"], "completed")
            self.assertEqual(
                coordinator.calls[-1]["approval_id"],
                approval_id,
            )
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
                    approval_ids={
                        "unknown": "approval_" + "1" * 32,
                    },
                )
        finally:
            temporary.cleanup()

    def test_stale_approval_requests_fresh_token(self):
        temporary, store, coordinator, executor = (
            self.create_runtime()
        )

        try:
            plan = NedTaskPlanner().create(
                "Create safely",
                [
                    {
                        "id": "create",
                        "title": "Create",
                        "member": "arya",
                        "tool": "arya.run",
                        "effect": "create",
                    }
                ],
            )
            store.save(plan)

            first = executor.execute(plan.id)
            stale = first["approval"]["id"]
            coordinator.invalid_approvals.add(stale)

            second = executor.execute(
                plan.id,
                approval_ids={"create": stale},
            )

            self.assertEqual(
                second["state"],
                "awaiting_approval",
            )
            self.assertNotEqual(
                second["approval"]["id"],
                stale,
            )
            self.assertEqual(
                second["plan"]["state"],
                "awaiting_approval",
            )
        finally:
            temporary.cleanup()

    def test_legacy_boolean_parameters_are_removed(self):
        import inspect
        parameters = inspect.signature(
            TaskExecutor.execute
        ).parameters
        self.assertNotIn("approved_steps", parameters)
        self.assertNotIn("approve_all", parameters)
        self.assertIn("approval_ids", parameters)


if __name__ == "__main__":
    unittest.main()
