from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_CORE" / "src"))
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))

from bran_cognitive import CognitiveMemory
from cognitive_runtime import NedCognitiveBridge, NedToolPlanner
from security_runtime import ApprovalStore
from tools_runtime import ToolCoordinator


class SilentKing:
    def __init__(self) -> None:
        self.index = 0

    def publish(self, *args, **kwargs):
        self.index += 1
        return {"id": f"event-{self.index}"}


class SilentJhon:
    def write(self, *args, **kwargs) -> None:
        return None


class ForbiddenModel:
    provider_name = "forbidden-test-model"
    model_name = "forbidden-test-model"

    def generate(self, *args, **kwargs):
        raise AssertionError("deterministic natural-language E2E must not call the model planner")


class Lote1NaturalE2E(unittest.TestCase):
    def make_bridge(self, directory: str):
        root = Path(directory)
        memory = CognitiveMemory(root / "memory.db")
        approvals = ApprovalStore(root / "approvals.db")
        tools = ToolCoordinator(memory=memory, approvals=approvals)
        tools.king = SilentKing()
        tools.jhon = SilentJhon()

        bridge = NedCognitiveBridge.__new__(NedCognitiveBridge)
        bridge.tools = tools
        bridge.planner = NedToolPlanner(tools, ForbiddenModel())
        bridge._capture_learning_event = lambda *args, **kwargs: "learning-e2e"
        bridge.chat = lambda content, conversation_id=None, system_prompt=None: {
            "state": "completed",
            "conversation_id": conversation_id or "e2e-conversation",
            "message": {
                "role": "assistant",
                "content": "Execução confirmada pela evidência da ferramenta.",
            },
        }
        return bridge, tools, memory, approvals

    def assert_pending(self, result, tool_name: str) -> None:
        self.assertEqual(result["state"], "approval_required")
        self.assertEqual(result["tool_plan"]["tool"], tool_name)
        self.assertEqual(result["resume_plan"], result["tool_plan"])
        self.assertFalse(result["execution"]["executed"])
        self.assertFalse(result["execution"]["verified"])
        self.assertIsInstance(result["tool_result"]["approval"]["id"], str)

    def test_research_natural_language_reaches_real_cyber_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bridge, _, _, _ = self.make_bridge(directory)
            result = bridge.handle("Pesquise documentação oficial do Python")
            self.assert_pending(result, "web.research")

    def test_project_natural_language_reaches_real_cyber_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bridge, _, _, _ = self.make_bridge(directory)
            result = bridge.handle(
                "Crie um site chamado portfolio: uma página pessoal simples"
            )
            self.assert_pending(result, "arya.project.generate")

    def test_memory_natural_language_approval_resume_and_execution_are_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bridge, _, memory, approvals = self.make_bridge(directory)
            content = "Lembre que eu prefiro respostas técnicas objetivas"

            pending = bridge.handle(content)
            self.assert_pending(pending, "bran.remember")

            approval_id = pending["tool_result"]["approval"]["id"]
            approvals.decide(approval_id, True)

            completed = bridge.handle(
                content,
                approval_id=approval_id,
                resume_plan=pending["resume_plan"],
            )

            self.assertEqual(completed["state"], "completed")
            self.assertTrue(completed["execution"]["executed"])
            self.assertTrue(completed["execution"]["verified"])
            self.assertTrue(completed["execution"]["resumed"])
            self.assertEqual(completed["tool_result"]["tool"], "bran.remember")
            self.assertEqual(memory.status()["active"], 1)

            recalled = memory.search("respostas técnicas objetivas", limit=5)
            self.assertEqual(len(recalled), 1)
            self.assertIn("objetivas", recalled[0]["content"])


if __name__ == "__main__":
    unittest.main()
