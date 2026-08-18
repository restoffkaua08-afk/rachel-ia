from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_CORE" / "src"))
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))

from dev_runtime import DevRuntime
from filesystem_runtime import FilesystemRuntime
from security_runtime import ApprovalStore
from tools_runtime import ToolCoordinator


class DevRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.workspace = root / "workspace"
        self.desktop = root / "desktop"
        self.documents = root / "documents"
        self.downloads = root / "downloads"
        for item in (
            self.workspace,
            self.desktop,
            self.documents,
            self.downloads,
        ):
            item.mkdir(parents=True)

        self.project = self.workspace / "python-project"
        self.project.mkdir()
        (self.project / "app.py").write_text(
            "def add(a, b):\n    return a + b\n",
            encoding="utf-8",
        )
        (self.project / "test_app.py").write_text(
            "import unittest\n"
            "from app import add\n\n"
            "class AddTests(unittest.TestCase):\n"
            "    def test_add(self):\n"
            "        self.assertEqual(4, add(2, 2))\n",
            encoding="utf-8",
        )

        filesystem = FilesystemRuntime(
            scopes={
                "workspace": self.workspace,
                "desktop": self.desktop,
                "documents": self.documents,
                "downloads": self.downloads,
            },
            backup_root=root / "backups",
        )
        approvals = ApprovalStore(root / "approvals.db")
        dev = DevRuntime(filesystem)
        self.approvals = approvals
        self.tools = ToolCoordinator(
            filesystem=filesystem,
            approvals=approvals,
            dev=dev,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def approve(self, pending: dict) -> str:
        approval_id = pending["approval"]["id"]
        self.approvals.decide(approval_id, True)
        return approval_id

    def test_detect_is_read_only_in_workspace(self) -> None:
        result = self.tools.invoke(
            "dev.detect",
            {"scope": "workspace", "path": "python-project"},
        )
        self.assertEqual("completed", result["state"])
        self.assertIn("python", result["result"]["families"])
        self.assertEqual("inspect", result["effective_effect"])

    def test_build_requires_execute_approval_and_uses_typed_plan(self) -> None:
        arguments = {
            "scope": "workspace",
            "path": "python-project",
            "timeout_seconds": 60,
        }
        pending = self.tools.invoke("dev.build", arguments)
        self.assertEqual("approval_required", pending["state"])
        self.assertEqual("execute", pending["approval"]["effect"])

        result = self.tools.invoke(
            "dev.build",
            arguments,
            approval_id=self.approve(pending),
        )
        self.assertEqual("completed", result["state"])
        self.assertTrue(result["result"]["successful"])
        self.assertEqual("python", result["result"]["family"])
        self.assertEqual("build", result["result"]["operation"])
        self.assertFalse(result["result"]["shell"])

    def test_test_operation_executes_real_unittest_suite(self) -> None:
        arguments = {
            "scope": "workspace",
            "path": "python-project",
            "timeout_seconds": 60,
        }
        pending = self.tools.invoke("dev.test", arguments)
        result = self.tools.invoke(
            "dev.test",
            arguments,
            approval_id=self.approve(pending),
        )
        self.assertTrue(result["result"]["successful"])
        self.assertEqual(0, result["result"]["returncode"])
        combined = result["result"]["stdout"] + result["result"]["stderr"]
        self.assertIn("OK", combined)

    def test_external_detect_requires_permission_before_inspection(self) -> None:
        external = self.desktop / "project"
        external.mkdir()
        (external / "app.py").write_text("x = 1\n", encoding="utf-8")
        arguments = {"scope": "desktop", "path": "project"}
        pending = self.tools.invoke("dev.detect", arguments)
        self.assertEqual("approval_required", pending["state"])
        self.assertEqual("external", pending["approval"]["effect"])

        result = self.tools.invoke(
            "dev.detect",
            arguments,
            approval_id=self.approve(pending),
        )
        self.assertEqual("completed", result["state"])
        self.assertIn("python", result["result"]["families"])


if __name__ == "__main__":
    unittest.main()
