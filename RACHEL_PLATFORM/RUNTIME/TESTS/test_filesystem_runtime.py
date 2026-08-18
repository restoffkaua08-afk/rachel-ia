from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_CORE" / "src"))
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))

from filesystem_runtime import FilesystemError, FilesystemRuntime
from security_runtime import ApprovalStore
from tools_runtime import ToolCoordinator


class FilesystemRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.workspace = root / "workspace"
        self.desktop = root / "desktop"
        self.documents = root / "documents"
        self.downloads = root / "downloads"
        for path in (
            self.workspace,
            self.desktop,
            self.documents,
            self.downloads,
        ):
            path.mkdir(parents=True)

        self.filesystem = FilesystemRuntime(
            scopes={
                "workspace": self.workspace,
                "desktop": self.desktop,
                "documents": self.documents,
                "downloads": self.downloads,
            },
            backup_root=root / "backups",
        )
        self.approvals = ApprovalStore(root / "approvals.db")
        self.tools = ToolCoordinator(
            filesystem=self.filesystem,
            approvals=self.approvals,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def approve(self, pending: dict) -> str:
        approval_id = pending["approval"]["id"]
        self.approvals.decide(approval_id, True)
        return approval_id

    def test_scope_escape_is_blocked(self) -> None:
        with self.assertRaises(FilesystemError):
            self.filesystem.target("workspace", "../outside.txt")

    def test_workspace_read_is_low_risk_and_needs_no_approval(self) -> None:
        (self.workspace / "hello.txt").write_text("Olá", encoding="utf-8")
        result = self.tools.invoke(
            "filesystem.read",
            {"scope": "workspace", "path": "hello.txt"},
        )
        self.assertEqual("completed", result["state"])
        self.assertEqual("read", result["effective_effect"])
        self.assertEqual("Olá", result["result"]["content"])

    def test_desktop_read_is_upgraded_to_external_and_requires_approval(self) -> None:
        (self.desktop / "private.txt").write_text("conteúdo", encoding="utf-8")
        arguments = {"scope": "desktop", "path": "private.txt"}
        pending = self.tools.invoke("filesystem.read", arguments)

        self.assertEqual("approval_required", pending["state"])
        self.assertEqual("external", pending["policy"]["effect"])
        self.assertEqual("external", pending["approval"]["effect"])

        approval_id = self.approve(pending)
        completed = self.tools.invoke(
            "filesystem.read",
            arguments,
            approval_id=approval_id,
        )
        self.assertEqual("completed", completed["state"])
        self.assertEqual("external", completed["effective_effect"])
        self.assertEqual("conteúdo", completed["result"]["content"])

    def test_desktop_mkdir_requires_exact_approval_and_verifies_result(self) -> None:
        arguments = {"scope": "desktop", "path": "teste"}
        pending = self.tools.invoke("filesystem.mkdir", arguments)
        self.assertEqual("approval_required", pending["state"])
        self.assertEqual("create", pending["approval"]["effect"])

        approval_id = self.approve(pending)
        result = self.tools.invoke(
            "filesystem.mkdir",
            arguments,
            approval_id=approval_id,
        )
        self.assertEqual("completed", result["state"])
        self.assertTrue(result["result"]["created"])
        self.assertTrue(result["result"]["verified"])
        self.assertTrue((self.desktop / "teste").is_dir())

    def test_write_is_atomic_verified_and_backed_up_on_overwrite(self) -> None:
        arguments = {
            "scope": "workspace",
            "path": "notes/report.txt",
            "content": "versão 1",
        }
        first_pending = self.tools.invoke("filesystem.write", arguments)
        first = self.tools.invoke(
            "filesystem.write",
            arguments,
            approval_id=self.approve(first_pending),
        )
        self.assertTrue(first["result"]["created"])
        self.assertTrue(first["result"]["verified"])
        self.assertIsNone(first["result"]["backup_id"])

        second_arguments = {
            **arguments,
            "content": "versão 2",
        }
        second_pending = self.tools.invoke("filesystem.write", second_arguments)
        second = self.tools.invoke(
            "filesystem.write",
            second_arguments,
            approval_id=self.approve(second_pending),
        )
        self.assertTrue(second["result"]["overwritten"])
        self.assertTrue(second["result"]["verified"])
        self.assertIsInstance(second["result"]["backup_id"], str)
        self.assertEqual(
            "versão 2",
            (self.workspace / "notes" / "report.txt").read_text(encoding="utf-8"),
        )

    def test_patch_requires_exact_single_match(self) -> None:
        target = self.workspace / "config.txt"
        target.write_text("mode=old\n", encoding="utf-8")
        arguments = {
            "scope": "workspace",
            "path": "config.txt",
            "old": "mode=old",
            "new": "mode=new",
        }
        pending = self.tools.invoke("filesystem.patch", arguments)
        result = self.tools.invoke(
            "filesystem.patch",
            arguments,
            approval_id=self.approve(pending),
        )
        self.assertEqual(1, result["result"]["patch_matches"])
        self.assertTrue(result["result"]["verified"])
        self.assertIn("mode=new", target.read_text(encoding="utf-8"))

    def test_delete_directory_is_intentionally_non_recursive(self) -> None:
        folder = self.workspace / "keep"
        folder.mkdir()
        (folder / "file.txt").write_text("x", encoding="utf-8")
        with self.assertRaises(FilesystemError):
            self.filesystem.delete("workspace", "keep", approved=True)
        self.assertTrue(folder.exists())


if __name__ == "__main__":
    unittest.main()
