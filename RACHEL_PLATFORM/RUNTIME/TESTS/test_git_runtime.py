from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_CORE" / "src"))
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))

from filesystem_runtime import FilesystemRuntime
from git_runtime import GitRuntime
from security_runtime import ApprovalStore
from tools_runtime import ToolCoordinator


@unittest.skipUnless(shutil.which("git"), "git executable is required")
class GitRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.workspace = root / "workspace"
        self.desktop = root / "desktop"
        self.documents = root / "documents"
        self.downloads = root / "downloads"
        for directory in (
            self.workspace,
            self.desktop,
            self.documents,
            self.downloads,
        ):
            directory.mkdir(parents=True)

        self.repo = self.workspace / "repo"
        self.repo.mkdir()
        self._git(self.repo, "init")
        self._git(self.repo, "config", "user.email", "rachel-tests@example.invalid")
        self._git(self.repo, "config", "user.name", "Rachel Tests")
        (self.repo / "README.md").write_text("# Demo\n", encoding="utf-8")
        self._git(self.repo, "add", "README.md")
        self._git(self.repo, "commit", "-m", "initial")

        self.external_repo = self.desktop / "repo"
        self.external_repo.mkdir()
        self._git(self.external_repo, "init")
        self._git(
            self.external_repo,
            "config",
            "user.email",
            "rachel-tests@example.invalid",
        )
        self._git(self.external_repo, "config", "user.name", "Rachel Tests")
        (self.external_repo / "README.md").write_text("# External\n", encoding="utf-8")
        self._git(self.external_repo, "add", "README.md")
        self._git(self.external_repo, "commit", "-m", "initial")

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
        git = GitRuntime(filesystem=filesystem, executable=shutil.which("git"))
        self.approvals = approvals
        self.tools = ToolCoordinator(
            filesystem=filesystem,
            approvals=approvals,
            git=git,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def _git(repo: Path, *arguments: str) -> str:
        process = subprocess.run(
            [shutil.which("git") or "git", *arguments],
            cwd=repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        return process.stdout.strip()

    def approve(self, pending: dict) -> str:
        approval_id = pending["approval"]["id"]
        self.approvals.decide(approval_id, True)
        return approval_id

    def test_workspace_status_and_diff_are_read_only(self) -> None:
        status = self.tools.invoke(
            "git.status",
            {"scope": "workspace", "path": "repo"},
        )
        self.assertEqual("completed", status["state"])
        self.assertTrue(status["result"]["clean"])

        (self.repo / "README.md").write_text("# Changed\n", encoding="utf-8")
        diff = self.tools.invoke(
            "git.diff",
            {
                "scope": "workspace",
                "path": "repo",
                "staged": False,
                "files": ["README.md"],
            },
        )
        self.assertEqual("completed", diff["state"])
        self.assertIn("Changed", diff["result"]["diff"])
        self.assertEqual("read", diff["effective_effect"])

    def test_external_git_status_requires_cyber_approval(self) -> None:
        arguments = {"scope": "desktop", "path": "repo"}
        pending = self.tools.invoke("git.status", arguments)
        self.assertEqual("approval_required", pending["state"])
        self.assertEqual("external", pending["approval"]["effect"])

        completed = self.tools.invoke(
            "git.status",
            arguments,
            approval_id=self.approve(pending),
        )
        self.assertEqual("completed", completed["state"])
        self.assertEqual("external", completed["effective_effect"])

    def test_stage_and_commit_are_separate_governed_operations(self) -> None:
        (self.repo / "feature.txt").write_text("feature\n", encoding="utf-8")
        stage_args = {
            "scope": "workspace",
            "path": "repo",
            "files": ["feature.txt"],
        }
        stage_pending = self.tools.invoke("git.stage", stage_args)
        self.assertEqual("approval_required", stage_pending["state"])
        self.assertEqual("edit", stage_pending["approval"]["effect"])
        staged = self.tools.invoke(
            "git.stage",
            stage_args,
            approval_id=self.approve(stage_pending),
        )
        self.assertTrue(staged["result"]["verified"])
        self.assertIn("feature.txt", staged["result"]["staged"])

        commit_args = {
            "scope": "workspace",
            "path": "repo",
            "message": "feat: add feature",
        }
        commit_pending = self.tools.invoke("git.commit", commit_args)
        self.assertEqual("approval_required", commit_pending["state"])
        self.assertEqual("write", commit_pending["approval"]["effect"])
        committed = self.tools.invoke(
            "git.commit",
            commit_args,
            approval_id=self.approve(commit_pending),
        )
        self.assertTrue(committed["result"]["verified"])
        self.assertEqual("feat: add feature", committed["result"]["subject"])
        self.assertEqual(40, len(committed["result"]["sha"]))

    def test_branch_creation_does_not_checkout_silently(self) -> None:
        before = self.tools.invoke(
            "git.branches",
            {"scope": "workspace", "path": "repo"},
        )["result"]["current"]

        arguments = {
            "scope": "workspace",
            "path": "repo",
            "branch": "agent/test-branch",
        }
        pending = self.tools.invoke("git.branch.create", arguments)
        result = self.tools.invoke(
            "git.branch.create",
            arguments,
            approval_id=self.approve(pending),
        )
        self.assertTrue(result["result"]["created"])
        self.assertFalse(result["result"]["checked_out"])

        after = self.tools.invoke(
            "git.branches",
            {"scope": "workspace", "path": "repo"},
        )["result"]["current"]
        self.assertEqual(before, after)

    def test_push_is_not_registered_as_a_generic_git_capability(self) -> None:
        names = {item["name"] for item in self.tools.list_tools()}
        self.assertNotIn("git.push", names)


if __name__ == "__main__":
    unittest.main()
