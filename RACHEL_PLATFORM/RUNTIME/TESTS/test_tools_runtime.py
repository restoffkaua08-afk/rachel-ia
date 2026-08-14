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
            result = tools.invoke(
                "bran.remember",
                {
                    "content": "Prefiro relatórios técnicos organizados.",
                    "source": "unit-test",
                    "kind": "preference",
                },
                approved=True,
            )
            self.assertEqual(result["state"], "completed")
            self.assertEqual(result["result"]["state"], "stored")
            self.assertEqual(memory.status()["active"], 1)

    def test_governed_memory_is_searchable_through_tool(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = CognitiveMemory(Path(directory) / "memory.db")
            tools = ToolCoordinator(memory=memory)
            tools.invoke(
                "bran.remember",
                {
                    "content": "O projeto principal utiliza arquitetura modular.",
                    "source": "unit-test",
                    "kind": "project",
                },
                approved=True,
            )
            result = tools.invoke(
                "bran.search",
                {"query": "arquitetura modular", "limit": 5},
            )
            self.assertEqual(result["state"], "completed")
            self.assertEqual(len(result["result"]), 1)

    def test_unknown_tool_is_blocked(self):
        with self.assertRaises(ToolError):
            self.tools.invoke("unknown.tool", {})
    def test_arguments_must_be_object(self):
        with self.assertRaises(ToolError):
            parse_arguments("[]")

if __name__ == "__main__": unittest.main()
