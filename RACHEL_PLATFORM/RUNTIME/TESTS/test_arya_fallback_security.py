from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_CORE" / "src"))
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))

from arya_runtime import run
from tools_runtime import ToolCoordinator


class AryaFallbackSecurityTests(unittest.TestCase):
    def test_shell_interpreters_are_blocked_even_when_approved(self) -> None:
        for shell in ("powershell.exe", "pwsh", "cmd.exe", "bash", "wsl"):
            with self.subTest(shell=shell):
                with self.assertRaises(PermissionError):
                    run(shell, [], None, approved=True)

    def test_executable_paths_are_blocked(self) -> None:
        with self.assertRaises(PermissionError):
            run(sys.executable, ["--version"], None, approved=True)

    def test_fallback_always_requires_cyber_approval(self) -> None:
        with self.assertRaises(PermissionError):
            run("python", ["--version"], None, approved=False)

    @unittest.skipUnless(shutil.which("python"), "python executable is required")
    def test_approved_allowlisted_fallback_runs_without_shell(self) -> None:
        result = run("python", ["--version"], None, approved=True)
        self.assertEqual(0, result["returncode"])
        self.assertTrue(result["fallback"])
        self.assertFalse(result["shell"])
        self.assertTrue(result["approved"])

    def test_common_operations_have_typed_tools_instead_of_shell(self) -> None:
        names = {item["name"] for item in ToolCoordinator().list_tools()}
        expected = {
            "filesystem.mkdir",
            "filesystem.write",
            "filesystem.patch",
            "git.status",
            "git.diff",
            "git.stage",
            "git.commit",
            "dev.test",
            "dev.build",
            "dev.lint",
            "dev.typecheck",
            "process.start",
            "process.stop",
        }
        self.assertTrue(expected <= names)
        self.assertIn("arya.run", names)


if __name__ == "__main__":
    unittest.main()
