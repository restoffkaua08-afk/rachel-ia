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
from security_runtime import ApprovalStore
from tools_runtime import ToolCoordinator


class ProjectContextToolTests(unittest.TestCase):
    def test_project_context_returns_real_content_within_hard_limits(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            project = workspace / "demo"
            source = project / "src"
            source.mkdir(parents=True)

            for index in range(40):
                content = f"def helper_{index}():\n    return {index}\n"
                if index == 17:
                    content += "\ndef refresh_access_token():\n    return 'auth token refresh'\n"
                (source / f"module_{index:02d}.py").write_text(content, encoding="utf-8")

            filesystem = FilesystemRuntime(
                scopes={"workspace": workspace},
                backup_root=root / "backups",
            )
            memory = CognitiveMemory(root / "bran.db")
            projects = ProjectIntelligenceRuntime(filesystem=filesystem, memory=memory)
            tools = ToolCoordinator(
                memory=memory,
                approvals=ApprovalStore(root / "approvals.db"),
                filesystem=filesystem,
                projects=projects,
            )

            response = tools.invoke(
                "project.context",
                {
                    "scope": "workspace",
                    "path": "demo",
                    "task": "corrija o refresh do token de autenticação",
                    "limit": 30,
                },
            )

            self.assertEqual("completed", response["state"])
            result = response["result"]
            self.assertLessEqual(result["count"], 19)
            self.assertLessEqual(result["estimated_tokens"], 8_000)
            self.assertTrue(result["files"])
            self.assertTrue(all("content" in item for item in result["files"]))
            relevant = next(
                item for item in result["files"] if item["path"] == "src/module_17.py"
            )
            self.assertIn("refresh_access_token", relevant["content"])


if __name__ == "__main__":
    unittest.main()
