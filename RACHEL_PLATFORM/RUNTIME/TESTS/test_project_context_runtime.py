from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_CORE" / "src"))
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))

from bran_cognitive import CognitiveMemory
from filesystem_runtime import FilesystemRuntime
from project_intelligence_runtime import ProjectIntelligenceRuntime


class ProjectContextRuntimeTests(unittest.TestCase):
    def test_context_for_reads_ranked_files_and_enforces_hard_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            project = workspace / "demo"
            source = project / "src"
            source.mkdir(parents=True)

            filesystem = FilesystemRuntime(
                scopes={"workspace": workspace},
                backup_root=root / "backups",
            )
            memory = CognitiveMemory(root / "bran.db")
            runtime = ProjectIntelligenceRuntime(filesystem=filesystem, memory=memory)

            for index in range(30):
                body = ("helper text\n" * 80)
                if index in {3, 17}:
                    body += "def refresh_access_token():\n    return 'token refresh authentication'\n"
                (source / f"module_{index:02d}.py").write_text(body, encoding="utf-8")

            result = runtime.context_for(
                "workspace",
                "demo",
                "corrija refresh do token de autenticação",
                max_tokens=900,
                max_files=19,
            )

            self.assertLessEqual(result["estimated_tokens"], 900)
            self.assertLessEqual(result["count"], 19)
            self.assertLess(result["count"], 20)
            self.assertEqual("conservative-char-budget", result["context_strategy"])
            self.assertTrue(result["files"])
            self.assertTrue(all("content" in item for item in result["files"]))
            self.assertTrue(
                any(item["path"] in {"src/module_03.py", "src/module_17.py"} for item in result["files"])
            )

    def test_context_for_never_allows_budget_above_project_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            project = workspace / "demo"
            project.mkdir(parents=True)
            (project / "auth.py").write_text(
                "def authenticate_token(token):\n    return token\n" * 100,
                encoding="utf-8",
            )

            runtime = ProjectIntelligenceRuntime(
                filesystem=FilesystemRuntime(
                    scopes={"workspace": workspace},
                    backup_root=root / "backups",
                ),
                memory=CognitiveMemory(root / "bran.db"),
            )

            result = runtime.context_for(
                "workspace",
                "demo",
                "authenticate token",
                max_tokens=50_000,
                max_files=100,
            )

            self.assertEqual(8_000, result["max_tokens"])
            self.assertEqual(19, result["max_files"])
            self.assertLessEqual(result["estimated_tokens"], 8_000)
            self.assertLess(result["count"], 20)


if __name__ == "__main__":
    unittest.main()
