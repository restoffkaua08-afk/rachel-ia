from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_CORE" / "src"))
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))

from cognitive_runtime import (
    RESUME_PLAN_ENV,
    NedCognitiveBridge,
    NedToolPlanner,
    ToolPlan,
    resume_plan_from_environment,
    should_use_tool_planner,
)


class FakePlanner:
    def __init__(self, *, planned: ToolPlan | None = None, heuristic: ToolPlan | None = None) -> None:
        self.planned = planned
        self.heuristic = heuristic
        self.plan_calls = 0
        self.heuristic_calls = 0

    def plan(self, content: str) -> ToolPlan:
        self.plan_calls += 1
        if self.planned is None:
            raise AssertionError("model planner must not run")
        return self.planned

    def heuristic_plan(self, content: str) -> ToolPlan | None:
        self.heuristic_calls += 1
        if self.heuristic is not None:
            return self.heuristic
        return NedToolPlanner.heuristic_plan(content)


class FakeTools:
    def __init__(self, result: dict) -> None:
        self.result = result
        self.registry = {
            "arya.project.create": object(),
            "arya.project.generate": object(),
            "bran.remember": object(),
            "bran.search": object(),
            "web.research": object(),
        }
        self.calls: list[tuple[str, dict, str | None]] = []

    def invoke(self, tool: str, arguments: dict, approval_id: str | None = None) -> dict:
        self.calls.append((tool, arguments, approval_id))
        return dict(self.result)


class CognitiveReliabilityTests(unittest.TestCase):
    def bridge(self, *, planner: FakePlanner, tools: FakeTools) -> NedCognitiveBridge:
        bridge = NedCognitiveBridge.__new__(NedCognitiveBridge)
        bridge.planner = planner
        bridge.tools = tools
        bridge._capture_learning_event = lambda *args, **kwargs: "learning-event"
        bridge.chat = lambda content, conversation_id=None, system_prompt=None: {
            "state": "completed",
            "conversation_id": conversation_id or "conversation-test",
            "message": {"role": "assistant", "content": "Resposta grounded."},
        }
        return bridge

    def completed_tools(self) -> FakeTools:
        return FakeTools({
            "state": "completed",
            "tool": "arya.project.create",
            "result": {"created": True},
            "request_event_id": "request-2",
            "completion_event_id": "completion-2",
            "approval": {"id": "approval-1"},
        })

    def test_canonical_entry_is_handle_and_assist_is_alias(self) -> None:
        tools = FakeTools({})
        planner = FakePlanner()
        bridge = self.bridge(planner=planner, tools=tools)
        direct = bridge.handle("Explique recursão")
        alias = bridge.assist("Explique recursão")
        self.assertEqual(direct["tool_plan"]["source"], "fast-chat")
        self.assertEqual(alias["tool_plan"]["source"], "fast-chat")
        self.assertEqual(planner.plan_calls, 0)

    def test_normal_conversation_uses_fast_path_without_model_planner(self) -> None:
        self.assertFalse(should_use_tool_planner("Qual a diferença entre RAM e SSD?"))
        tools = FakeTools({})
        planner = FakePlanner()
        result = self.bridge(planner=planner, tools=tools).handle(
            "Qual a diferença entre RAM e SSD?"
        )
        self.assertEqual(result["tool_plan"]["source"], "fast-chat")
        self.assertEqual(planner.plan_calls, 0)
        self.assertEqual(tools.calls, [])
        self.assertFalse(result["execution"]["executed"])

    def test_action_like_unknown_request_may_consult_model_planner(self) -> None:
        self.assertTrue(should_use_tool_planner("Execute a tarefa necessária nesse projeto"))
        plan = ToolPlan("chat", None, {}, "Sem ferramenta adequada.", "model")
        tools = FakeTools({})
        planner = FakePlanner(planned=plan)
        result = self.bridge(planner=planner, tools=tools).handle(
            "Execute a tarefa necessária nesse projeto"
        )
        self.assertEqual(planner.plan_calls, 1)
        self.assertEqual(result["tool_plan"]["source"], "model")

    def test_approval_required_exposes_exact_resume_plan_and_no_execution_claim(self) -> None:
        plan = ToolPlan(
            "tool",
            "arya.project.create",
            {"project": "faculdade"},
            "Criar projeto solicitado.",
            "model",
        )
        tools = FakeTools({
            "state": "approval_required",
            "tool": "arya.project.create",
            "approval": {"id": "approval-1"},
            "request_event_id": "request-1",
        })
        planner = FakePlanner(planned=plan)
        result = self.bridge(planner=planner, tools=tools).handle("execute essa criação")

        self.assertEqual(result["state"], "approval_required")
        self.assertEqual(result["resume_plan"], result["tool_plan"])
        self.assertEqual(result["resume_plan"]["arguments"], {"project": "faculdade"})
        self.assertFalse(result["execution"]["executed"])
        self.assertFalse(result["execution"]["verified"])
        self.assertEqual(planner.plan_calls, 1)

    def test_resume_plan_skips_planner_and_executes_exact_envelope(self) -> None:
        plan = ToolPlan(
            "tool",
            "arya.project.create",
            {"project": "faculdade"},
            "Criar projeto solicitado.",
            "model",
        )
        tools = self.completed_tools()
        planner = FakePlanner()
        bridge = self.bridge(planner=planner, tools=tools)

        result = bridge.handle(
            "texto original",
            approval_id="approval-1",
            resume_plan={
                "action": plan.action,
                "tool": plan.tool,
                "arguments": plan.arguments,
                "reason": plan.reason,
                "source": plan.source,
            },
        )

        self.assertEqual(planner.plan_calls, 0)
        self.assertEqual(planner.heuristic_calls, 0)
        self.assertEqual(
            tools.calls,
            [("arya.project.create", {"project": "faculdade"}, "approval-1")],
        )
        self.assertTrue(result["execution"]["executed"])
        self.assertTrue(result["execution"]["verified"])
        self.assertTrue(result["execution"]["resumed"])
        self.assertIsNone(result["resume_plan"])

    def test_process_environment_carries_exact_resume_plan_without_replanning(self) -> None:
        plan = {
            "action": "tool",
            "tool": "arya.project.create",
            "arguments": {"project": "faculdade"},
            "reason": "Criar projeto solicitado.",
            "source": "model",
        }
        tools = self.completed_tools()
        planner = FakePlanner()
        bridge = self.bridge(planner=planner, tools=tools)

        with patch.dict(os.environ, {RESUME_PLAN_ENV: json.dumps(plan)}, clear=False):
            self.assertEqual(resume_plan_from_environment(), plan)
            result = bridge.handle("texto original", approval_id="approval-1")

        self.assertEqual(planner.plan_calls, 0)
        self.assertEqual(planner.heuristic_calls, 0)
        self.assertEqual(tools.calls[0][0], "arya.project.create")
        self.assertEqual(tools.calls[0][1], {"project": "faculdade"})
        self.assertTrue(result["execution"]["resumed"])

    def test_invalid_process_environment_fails_closed(self) -> None:
        bridge = self.bridge(planner=FakePlanner(), tools=FakeTools({}))
        with patch.dict(os.environ, {RESUME_PLAN_ENV: "not-json"}, clear=False):
            with self.assertRaisesRegex(ValueError, "environment payload"):
                bridge.handle("texto original", approval_id="approval-1")

    def test_legacy_approval_resume_uses_only_deterministic_route_never_model_planner(self) -> None:
        deterministic = ToolPlan(
            "tool",
            "bran.remember",
            {"content": "prefiro respostas curtas", "source": "user-approved", "kind": "preference"},
            "Registrar memória solicitada pelo usuário.",
            "deterministic",
        )
        planner = FakePlanner(heuristic=deterministic)
        tools = FakeTools({
            "state": "completed",
            "tool": "bran.remember",
            "result": {"stored": True},
            "request_event_id": "request-3",
            "completion_event_id": "completion-3",
            "approval": {"id": "approval-2"},
        })
        bridge = self.bridge(planner=planner, tools=tools)

        result = bridge.handle(
            "lembre que prefiro respostas curtas",
            approval_id="approval-2",
        )

        self.assertEqual(planner.plan_calls, 0)
        self.assertEqual(planner.heuristic_calls, 1)
        self.assertTrue(result["execution"]["resumed"])

    def test_legacy_approval_without_deterministic_route_fails_closed_instead_of_replanning(self) -> None:
        planner = FakePlanner(heuristic=None)
        planner.heuristic_plan = lambda content: None
        tools = FakeTools({})
        bridge = self.bridge(planner=planner, tools=tools)

        with self.assertRaisesRegex(ValueError, "resume_plan"):
            bridge.handle("faça uma ação ambígua", approval_id="approval-model")

        self.assertEqual(planner.plan_calls, 0)
        self.assertEqual(tools.calls, [])

    def test_non_completed_tool_state_never_claims_execution(self) -> None:
        plan = ToolPlan(
            "tool",
            "arya.project.create",
            {"project": "faculdade"},
            "Criar projeto solicitado.",
            "model",
        )
        planner = FakePlanner(planned=plan)
        tools = FakeTools({
            "state": "denied",
            "tool": "arya.project.create",
            "request_event_id": "request-4",
            "approval": None,
        })
        bridge = self.bridge(planner=planner, tools=tools)
        bridge.chat = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("chat must not synthesize a success response for denied tools")
        )

        result = bridge.handle("execute essa criação")

        self.assertEqual(result["state"], "denied")
        self.assertFalse(result["execution"]["executed"])
        self.assertFalse(result["execution"]["verified"])
        self.assertIn("não foi concluída", result["message"]["content"])

    def test_resume_plan_requires_approval_id(self) -> None:
        bridge = self.bridge(planner=FakePlanner(), tools=FakeTools({}))
        with self.assertRaisesRegex(ValueError, "requires approval_id"):
            bridge.handle(
                "qualquer coisa",
                resume_plan={
                    "action": "tool",
                    "tool": "arya.project.create",
                    "arguments": {"project": "x"},
                    "reason": "teste",
                    "source": "test",
                },
            )

    def test_natural_research_intent_routes_without_internal_name(self) -> None:
        plan = NedToolPlanner.heuristic_plan("Pesquise a versão mais recente do Python")
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.tool, "web.research")
        self.assertEqual(plan.arguments["query"], "a versão mais recente do Python")
        self.assertEqual(plan.source, "deterministic")

    def test_natural_memory_intent_routes_without_internal_name(self) -> None:
        plan = NedToolPlanner.heuristic_plan("Lembre que eu prefiro respostas curtas")
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.tool, "bran.remember")
        self.assertEqual(plan.arguments["content"], "eu prefiro respostas curtas")

    def test_natural_project_action_routes_without_internal_name(self) -> None:
        plan = NedToolPlanner.heuristic_plan(
            "Crie um site chamado portfolio: uma página pessoal simples"
        )
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.tool, "arya.project.generate")
        self.assertEqual(plan.arguments["project"], "portfolio")
        self.assertEqual(plan.arguments["project_type"], "site")


if __name__ == "__main__":
    unittest.main()
