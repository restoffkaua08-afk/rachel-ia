import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_CORE" / "src"))
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))
from bran_cognitive import CognitiveMemory
from tools_runtime import ToolCoordinator, ToolError, parse_arguments

class ToolsRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tools = ToolCoordinator()
    def test_registry_has_expected_members(self):
        members = {item["member"] for item in self.tools.list_tools()}
        self.assertTrue({"ned", "bran", "visao", "arya", "cyber", "dany", "jhon", "tyrion", "king"} - {"ned"} <= members)
        self.assertGreaterEqual(len(self.tools.list_tools()), 11)
    def test_web_tools_are_registered(self):
        names = {
            item["name"]
            for item in self.tools.list_tools()
        }
        self.assertTrue(
            {
                "web.fetch",
                "web.search",
                "web.research",
            } <= names
        )

    def test_web_research_requires_approval(self):
        result = self.tools.invoke(
            "web.research",
            {"query": "Python documentation"},
        )
        self.assertEqual(
            result["state"],
            "approval_required",
        )

    def test_read_tool_executes_without_approval(self):
        result = self.tools.invoke("dany.evaluate", {"content": "conteudo valido"})
        self.assertEqual(result["state"], "completed")
        self.assertTrue(result["result"]["accepted"])
    def test_write_tool_requires_approval(self):
        result = self.tools.invoke("bran.remember", {"content": "nao deve executar"})
        self.assertEqual(result["state"], "approval_required")
    def test_approved_write_uses_governed_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = CognitiveMemory(Path(directory) / "memory.db")
            tools = ToolCoordinator(memory=memory)
            arguments = {
                "content": "Preferencia tecnica organizada.",
                "source": "unit-test",
                "kind": "preference",
            }
            pending = tools.invoke(
                "bran.remember",
                arguments,
            )
            approval_id = pending["approval"]["id"]
            tools.approvals.decide(
                approval_id,
                True,
            )
            result = tools.invoke(
                "bran.remember",
                arguments,
                approval_id=approval_id,
            )
            self.assertEqual(result["state"], "completed")
            self.assertEqual(result["result"]["state"], "stored")
            self.assertEqual(memory.status()["active"], 1)

    def test_governed_memory_is_searchable_through_tool(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = CognitiveMemory(Path(directory) / "memory.db")
            tools = ToolCoordinator(memory=memory)
            arguments = {
                "content": "Projeto usa arquitetura modular.",
                "source": "unit-test",
                "kind": "project",
            }
            pending = tools.invoke(
                "bran.remember",
                arguments,
            )
            approval_id = pending["approval"]["id"]
            tools.approvals.decide(
                approval_id,
                True,
            )
            tools.invoke(
                "bran.remember",
                arguments,
                approval_id=approval_id,
            )
            result = tools.invoke(
                "bran.search",
                {"query": "arquitetura modular", "limit": 5},
            )
            self.assertEqual(result["state"], "completed")
            self.assertEqual(len(result["result"]), 1)

    def test_boolean_approval_parameter_is_removed(self):
        import inspect
        parameters = inspect.signature(
            ToolCoordinator.invoke
        ).parameters
        self.assertNotIn("approved", parameters)
        self.assertIn("approval_id", parameters)

    def test_approval_response_hides_argument_values(self):
        import json
        secret = "private-value-987"
        result = self.tools.invoke(
            "bran.remember",
            {
                "content": secret,
                "source": "unit-test",
            },
        )
        serialized = json.dumps(
            result,
            ensure_ascii=False,
        )
        self.assertNotIn(secret, serialized)
        self.assertNotIn("arguments", result)

    def test_approval_is_single_use_through_tool_runtime(self):
        from security_runtime import ApprovalError

        with tempfile.TemporaryDirectory() as directory:
            memory = CognitiveMemory(Path(directory) / "memory.db")
            tools = ToolCoordinator(memory=memory)
            arguments = {
                "content": "Governed memory.",
                "kind": "note",
            }
            pending = tools.invoke(
                "bran.remember",
                arguments,
            )
            approval_id = pending["approval"]["id"]
            tools.approvals.decide(
                approval_id,
                True,
            )
            completed = tools.invoke(
                "bran.remember",
                arguments,
                approval_id=approval_id,
            )
            self.assertEqual(
                completed["state"],
                "completed",
            )

            with self.assertRaises(ApprovalError):
                tools.invoke(
                    "bran.remember",
                    arguments,
                    approval_id=approval_id,
                )

    def test_unknown_tool_is_blocked(self):
        with self.assertRaises(ToolError):
            self.tools.invoke("unknown.tool", {})
    def test_arguments_must_be_object(self):
        with self.assertRaises(ToolError):
            parse_arguments("[]")

if __name__ == "__main__": unittest.main()
