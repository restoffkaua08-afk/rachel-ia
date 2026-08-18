from __future__ import annotations

import json
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


class ProjectIntelligenceRuntimeTests(unittest.TestCase):
    def build_runtime(self, root: Path):
        workspace = root / "workspace"
        workspace.mkdir(parents=True)
        filesystem = FilesystemRuntime(
            scopes={"workspace": workspace},
            backup_root=root / "backups",
        )
        memory = CognitiveMemory(root / "bran.db")
        return ProjectIntelligenceRuntime(filesystem=filesystem, memory=memory), workspace

    def seed_project(self, workspace: Path):
        project = workspace / "demo"
        (project / "src").mkdir(parents=True)
        (project / "node_modules" / "ignored-lib").mkdir(parents=True)
        (project / ".git").mkdir(parents=True)
        (project / ".gitignore").write_text("ignored.txt\ncache/\n", encoding="utf-8")
        (project / "ignored.txt").write_text("should never index", encoding="utf-8")
        (project / "node_modules" / "ignored-lib" / "index.js").write_text("export const hidden = 1", encoding="utf-8")
        (project / "package.json").write_text(
            json.dumps(
                {
                    "name": "demo",
                    "dependencies": {"react": "^19.0.0"},
                    "devDependencies": {"typescript": "^5.0.0"},
                }
            ),
            encoding="utf-8",
        )
        (project / "pyproject.toml").write_text(
            '[project]\nname = "demo-python"\ndependencies = ["httpx>=0.27", "pydantic>=2"]\n',
            encoding="utf-8",
        )
        (project / "src" / "service.py").write_text(
            "class AuthService:\n    def login(self, token):\n        return token\n\ndef build_session():\n    return AuthService()\n",
            encoding="utf-8",
        )
        (project / "src" / "auth.ts").write_text(
            "export interface User { id: string }\nexport class TokenStore {}\nexport function validateToken(token: string) { return !!token }\n",
            encoding="utf-8",
        )
        (project / "README.md").write_text("Projeto de autenticação e login com token.", encoding="utf-8")
        return project

    def test_discovery_repo_map_and_ignore_rules(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime, workspace = self.build_runtime(Path(temp))
            self.seed_project(workspace)

            discovery = runtime.discover("workspace", "demo")
            self.assertTrue(discovery["git_repository"])
            self.assertIn("package.json", discovery["manifests"])
            self.assertIn("pyproject.toml", discovery["manifests"])
            self.assertGreaterEqual(discovery["languages"]["python"], 1)
            self.assertGreaterEqual(discovery["languages"]["typescript"], 1)

            repo_map = runtime.repo_map("workspace", "demo")
            paths = {item["path"] for item in repo_map["files"]}
            self.assertNotIn("ignored.txt", paths)
            self.assertFalse(any(path.startswith("node_modules/") for path in paths))
            self.assertIn("src/service.py", paths)

    def test_dependency_map_combines_supported_manifests(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime, workspace = self.build_runtime(Path(temp))
            self.seed_project(workspace)

            result = runtime.dependencies("workspace", "demo")
            self.assertIn("react@^19.0.0", result["sources"]["package.json"])
            self.assertIn("typescript@^5.0.0", result["sources"]["package.json"])
            self.assertIn("httpx>=0.27", result["sources"]["pyproject.toml"])
            self.assertGreaterEqual(result["dependency_count"], 4)

    def test_symbol_index_supports_python_and_typescript(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime, workspace = self.build_runtime(Path(temp))
            self.seed_project(workspace)

            result = runtime.symbols("workspace", "demo")
            names = {item["name"] for item in result["symbols"]}
            self.assertIn("AuthService", names)
            self.assertIn("login", names)
            self.assertIn("build_session", names)
            self.assertIn("TokenStore", names)
            self.assertIn("validateToken", names)
            self.assertIn("User", names)

    def test_code_search_and_working_set_prioritize_relevant_files(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime, workspace = self.build_runtime(Path(temp))
            self.seed_project(workspace)

            search = runtime.search("workspace", "demo", "login token")
            paths = [item["path"] for item in search["results"]]
            self.assertIn("src/service.py", paths)
            self.assertTrue(any(path in {"src/auth.ts", "README.md"} for path in paths))

            context = runtime.working_set("workspace", "demo", "corrija login e validação de token", limit=5)
            working_paths = {item["path"] for item in context["files"]}
            self.assertIn("src/service.py", working_paths)
            self.assertIn("src/auth.ts", working_paths)
            self.assertEqual("bounded-working-set", context["context_strategy"])

    def test_project_instructions_use_typed_filesystem_and_require_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime, workspace = self.build_runtime(Path(temp))
            self.seed_project(workspace)

            with self.assertRaises(PermissionError):
                runtime.write_instructions("workspace", "demo", "Sempre rode testes.", approved=False)

            written = runtime.write_instructions("workspace", "demo", "Sempre rode testes.", approved=True)
            self.assertTrue(written["verified"])

            result = runtime.read_instructions("workspace", "demo")
            self.assertEqual(1, result["count"])
            self.assertEqual(".rachel/instructions.md", result["items"][0]["path"])
            self.assertIn("Sempre rode testes", result["items"][0]["content"])

    def test_architecture_decisions_reuse_bran_instead_of_new_memory_database(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime, workspace = self.build_runtime(Path(temp))
            self.seed_project(workspace)

            pending = runtime.remember_decision(
                "workspace",
                "demo",
                "usar PostgreSQL como banco principal",
                approved=False,
            )
            self.assertEqual("approval_required", pending["state"])

            stored = runtime.remember_decision(
                "workspace",
                "demo",
                "usar PostgreSQL como banco principal",
                approved=True,
            )
            self.assertEqual("stored", stored["state"])
            self.assertEqual("decision", stored["memory"]["category"])
            self.assertEqual("architecture-decision", stored["memory"]["metadata"]["kind"])

            result = runtime.search_decisions("workspace", "demo", "PostgreSQL")
            self.assertEqual(1, result["count"])
            self.assertIn("PostgreSQL", result["items"][0]["content"])


if __name__ == "__main__":
    unittest.main()
