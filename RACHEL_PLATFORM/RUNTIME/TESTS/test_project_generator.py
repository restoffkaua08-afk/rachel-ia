import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_CORE" / "src"))
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))
from cognitive_runtime import NedToolPlanner
from project_generator import GenerationError, ProjectGenerator
from project_workspace import ProjectWorkspace


class Response:
    def __init__(self, content): self.content = content


class Model:
    def __init__(self, payload): self.payload = payload
    def generate(self, messages, system): return Response(json.dumps(self.payload))


class GeneratorTests(unittest.TestCase):
    def runtime(self, payload):
        temp = tempfile.TemporaryDirectory()
        workspace = ProjectWorkspace(Path(temp.name) / "projects", ROOT / "RACHEL_PLATFORM" / "CONFIG" / "project.policy.json")
        return temp, workspace, ProjectGenerator(workspace, Model(payload))

    def test_generates_complete_static_site(self):
        payload = {"summary": "Site", "architecture": "Static", "files": [{"path": "index.html", "content": "<h1>Site</h1>"}, {"path": "style.css", "content": "body{}"}, {"path": "main.js", "content": "console.log('ok')"}]}
        temp, workspace, generator = self.runtime(payload)
        try:
            result = generator.create("site", "Create a site", "website", True)
            self.assertEqual(result["file_count"], 3)
            self.assertEqual(workspace.inspect("site")["file_count"], 3)
        finally: temp.cleanup()

    def test_generation_requires_approval(self):
        temp, _, generator = self.runtime({"files": [{"path": "index.html", "content": "x"}]})
        try:
            with self.assertRaises(PermissionError): generator.create("site", "Create", "website", False)
        finally: temp.cleanup()

    def test_invalid_model_json_is_rejected(self):
        temp = tempfile.TemporaryDirectory()
        workspace = ProjectWorkspace(Path(temp.name) / "projects", ROOT / "RACHEL_PLATFORM" / "CONFIG" / "project.policy.json")
        class InvalidModel:
            def generate(self, messages, system): return Response("not json")
        try:
            with self.assertRaises(GenerationError): ProjectGenerator(workspace, InvalidModel()).specifications("Create site")
        finally: temp.cleanup()

    def test_ned_routes_project_generation(self):
        plan = NedToolPlanner.heuristic_plan("Crie um site chamado portfolio: portfolio profissional")
        self.assertIsNotNone(plan)
        self.assertEqual(plan.tool, "arya.project.generate")
        self.assertEqual(plan.arguments["project"], "portfolio")


if __name__ == "__main__": unittest.main()
