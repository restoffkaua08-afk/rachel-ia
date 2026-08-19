from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_CORE" / "src"))
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))

from bran_cognitive import CognitiveMemory
from filesystem_runtime import FilesystemError, FilesystemRuntime
from security_runtime import ApprovalStore
from tools_runtime import ToolCoordinator


class FilesystemScopeGrantTests(unittest.TestCase):
    def build_tools(self, root: Path):
        workspace = root / "workspace"
        external = root / "client-project"
        workspace.mkdir()
        external.mkdir()
        (external / "README.md").write_text("Projeto autorizado", encoding="utf-8")
        filesystem = FilesystemRuntime(
            scopes={"workspace": workspace},
            backup_root=root / "backups",
        )
        tools = ToolCoordinator(
            memory=CognitiveMemory(root / "memory.db"),
            approvals=ApprovalStore(root / "approvals.db"),
            filesystem=filesystem,
        )
        return tools, filesystem, external

    def test_session_scope_requires_cyber_and_is_not_persistent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tools, filesystem, external = self.build_tools(root)
            args = {"name": "client-project", "root": str(external.resolve())}

            pending = tools.invoke("filesystem.scope.grant", args)
            self.assertEqual("approval_required", pending["state"])
            approval_id = pending["approval"]["id"]
            tools.approvals.decide(approval_id, True)
            granted = tools.invoke("filesystem.scope.grant", args, approval_id=approval_id)

            self.assertEqual("completed", granted["state"])
            self.assertTrue(granted["result"]["session_only"])
            self.assertFalse(granted["result"]["persistent"])
            self.assertIn("client-project", filesystem.session_scopes)

            fresh = FilesystemRuntime(
                scopes={"workspace": root / "fresh-workspace"},
                backup_root=root / "fresh-backups",
            )
            self.assertNotIn("client-project", fresh.scope_names())

    def test_granted_scope_allows_low_risk_reads_without_reapproving_each_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tools, _, external = self.build_tools(root)
            args = {"name": "client-project", "root": str(external.resolve())}
            pending = tools.invoke("filesystem.scope.grant", args)
            approval_id = pending["approval"]["id"]
            tools.approvals.decide(approval_id, True)
            tools.invoke("filesystem.scope.grant", args, approval_id=approval_id)

            listing = tools.invoke("filesystem.list", {"scope": "client-project", "path": "."})
            reading = tools.invoke("filesystem.read", {"scope": "client-project", "path": "README.md"})
            self.assertEqual("completed", listing["state"])
            self.assertEqual("completed", reading["state"])
            self.assertIn("Projeto autorizado", reading["result"]["content"])

    def test_mutations_inside_granted_scope_still_require_fresh_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tools, _, external = self.build_tools(root)
            grant_args = {"name": "client-project", "root": str(external.resolve())}
            pending = tools.invoke("filesystem.scope.grant", grant_args)
            approval_id = pending["approval"]["id"]
            tools.approvals.decide(approval_id, True)
            tools.invoke("filesystem.scope.grant", grant_args, approval_id=approval_id)

            write_args = {"scope": "client-project", "path": "notes.txt", "content": "teste"}
            write_pending = tools.invoke("filesystem.write", write_args)
            self.assertEqual("approval_required", write_pending["state"])
            self.assertNotEqual(approval_id, write_pending["approval"]["id"])

    def test_revoke_is_governed_and_removes_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tools, filesystem, external = self.build_tools(root)
            grant_args = {"name": "client-project", "root": str(external.resolve())}
            pending = tools.invoke("filesystem.scope.grant", grant_args)
            grant_id = pending["approval"]["id"]
            tools.approvals.decide(grant_id, True)
            tools.invoke("filesystem.scope.grant", grant_args, approval_id=grant_id)

            revoke_args = {"name": "client-project"}
            revoke_pending = tools.invoke("filesystem.scope.revoke", revoke_args)
            self.assertEqual("approval_required", revoke_pending["state"])
            revoke_id = revoke_pending["approval"]["id"]
            tools.approvals.decide(revoke_id, True)
            revoked = tools.invoke("filesystem.scope.revoke", revoke_args, approval_id=revoke_id)
            self.assertTrue(revoked["result"]["revoked"])
            with self.assertRaises(FilesystemError):
                filesystem.root("client-project")

    def test_builtin_scope_cannot_be_replaced_or_revoked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, filesystem, external = self.build_tools(root)
            with self.assertRaises(FilesystemError):
                filesystem.grant_scope("workspace", str(external), approved=True)
            with self.assertRaises(FilesystemError):
                filesystem.revoke_scope("workspace", approved=True)


if __name__ == "__main__":
    unittest.main()
