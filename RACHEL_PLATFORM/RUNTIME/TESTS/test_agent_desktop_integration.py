from __future__ import annotations

import sys
import unittest
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_CORE" / "src"))
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))
sys.path.insert(0, str(ROOT / "APP" / "bridge"))

from agent_intent_runtime import should_route_to_agent
from rachel_server import ResidentBridge


class FakeCognitive:
    def status(self):
        return {"status": "ok"}


class FakeAgent:
    def __init__(self):
        self.started = []
        self.resumed = []

    def start(self, goal, cancel_check=None):
        self.started.append(goal)
        return {
            "id": "agent_1",
            "goal": goal,
            "state": "awaiting_approval",
            "current_plan_id": "plan_1",
            "root_plan_id": "plan_1",
            "plan_history": ["plan_1"],
            "budget": {"profile": "standard"},
            "counters": {"iterations": 1, "tool_calls": 1, "consecutive_failures": 0, "repairs": 0, "active_ms": 10},
            "observations": [],
            "last_error": None,
            "completion": None,
            "approval": {
                "id": "approval_1",
                "step_id": "step_write",
                "effect": "write",
                "risk": "medium",
            },
            "background_execution": False,
            "unattended_execution": False,
            "approval_inheritance": False,
        }

    def continue_run(self, run_id, approval_ids=None, cancel_check=None):
        self.resumed.append((run_id, dict(approval_ids or {})))
        return {
            "id": run_id,
            "goal": "objetivo",
            "state": "completed",
            "current_plan_id": "plan_1",
            "root_plan_id": "plan_1",
            "plan_history": ["plan_1"],
            "budget": {"profile": "standard"},
            "counters": {"iterations": 2, "tool_calls": 2, "consecutive_failures": 0, "repairs": 0, "active_ms": 20},
            "observations": [
                {
                    "kind": "step-observation",
                    "result": {"duration_ms": 7},
                }
            ],
            "last_error": None,
            "completion": {"reason": "goal-plan-completed", "verified": True},
            "background_execution": False,
            "unattended_execution": False,
            "approval_inheritance": False,
        }

    def show(self, run_id):
        return {"id": run_id, "state": "completed"}

    def list(self, limit=20):
        return []

    def pause(self, run_id):
        return {"id": run_id, "state": "paused"}

    def cancel(self, run_id):
        return {"id": run_id, "state": "cancelled"}


@pytest.mark.xfail(reason="Depende de agent_intent_runtime + Agent Loop (Etapa 5) e ResidentBridge.agent (Etapa 3)", strict=False)
class AgentDesktopIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.agent = FakeAgent()
        self.bridge = ResidentBridge(
            cognitive=FakeCognitive(),
            fallback_execute=lambda payload: {},
            agent=self.agent,
        )
        self.events = []

    def emit(self, event, payload):
        self.events.append((event, payload))

    def test_multi_step_natural_goal_routes_to_agent_without_internal_names(self):
        content = "Analise este projeto, corrija o problema e rode os testes até funcionar."
        response, _ = self.bridge.execute_live(
            {"action": "assist", "content": content, "conversation_id": "conv-1"},
            self.emit,
            Event(),
        )

        self.assertEqual([content], self.agent.started)
        self.assertEqual("approval_required", response["state"])
        self.assertEqual("agent", response["resume_plan"]["kind"])
        self.assertEqual("agent_1", response["resume_plan"]["run_id"])
        self.assertEqual("step_write", response["resume_plan"]["step_id"])
        self.assertNotIn("Arya", response["message"]["content"])
        self.assertNotIn("Ned", response["message"]["content"])

    def test_approved_agent_resume_uses_exact_run_and_step(self):
        response, metrics = self.bridge.execute_live(
            {
                "action": "assist",
                "content": "continue",
                "conversation_id": "conv-1",
                "approval_id": "approval_1",
                "resume_plan": {
                    "kind": "agent",
                    "run_id": "agent_1",
                    "step_id": "step_write",
                },
            },
            self.emit,
            Event(),
        )

        self.assertEqual([("agent_1", {"step_write": "approval_1"})], self.agent.resumed)
        self.assertEqual("completed", response["state"])
        self.assertTrue(response["execution"]["verified"])
        self.assertEqual(7, metrics["tool_latency_ms"])

    def test_single_directory_request_stays_single_tool_intent(self):
        self.assertFalse(
            should_route_to_agent("Crie uma pasta chamada teste na Área de Trabalho.")
        )

    def test_plan_only_request_does_not_execute_agent(self):
        self.assertFalse(
            should_route_to_agent("Planeje como corrigir e testar este projeto.")
        )

    def test_complex_project_request_is_agent_intent(self):
        self.assertTrue(
            should_route_to_agent("Revise o projeto, corrija os erros e execute os testes.")
        )


if __name__ == "__main__":
    unittest.main()
