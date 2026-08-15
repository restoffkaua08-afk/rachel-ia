import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))
from project_quality import ProjectQuality
from project_workspace import ProjectWorkspace


class QualityTests(unittest.TestCase):
    def runtime(self):
        temp = tempfile.TemporaryDirectory()
        workspace = ProjectWorkspace(Path(temp.name) / "projects", ROOT / "RACHEL_PLATFORM" / "CONFIG" / "project.policy.json")
        workspace.create_project("site", True)
        return temp, workspace, ProjectQuality(workspace)

    def test_complete_site_is_accepted(self):
        temp, workspace, quality = self.runtime()
        try:
            workspace.write_files("site", [
                {"path": "index.html", "content": '<!doctype html><html lang="pt-BR"><head><meta name="viewport" content="width=device-width"><title>Site</title><link rel="stylesheet" href="style.css"></head><body><h1>Site</h1><script src="main.js"></script></body></html>'},
                {"path": "style.css", "content": "body { color: white; }"},
                {"path": "main.js", "content": "console.log('ready');"},
                {"path": "README.md", "content": "# Site\n\nProjeto funcional."},
            ], True)
            result = quality.review("site")
            self.assertTrue(result["accepted"])
            self.assertEqual(result["score"], 100)
        finally: temp.cleanup()

    def test_broken_reference_is_rejected(self):
        temp, workspace, quality = self.runtime()
        try:
            workspace.write_files("site", [{"path": "index.html", "content": '<html lang="pt-BR"><head><meta name="viewport" content="width=device-width"><title>Site</title></head><body><a href="missing.html">Link</a></body></html>'}], True)
            result = quality.review("site")
            self.assertFalse(result["accepted"])
            self.assertFalse(result["checks"]["local_references_exist"])
        finally: temp.cleanup()

    def test_report_requires_approval(self):
        temp, _, quality = self.runtime()
        try:
            with self.assertRaises(PermissionError): quality.write_report("site", False)
        finally: temp.cleanup()

    def test_report_is_persisted(self):
        temp, workspace, quality = self.runtime()
        try:
            workspace.write_files("site", [{"path": "README.md", "content": "# Site"}], True)
            quality.write_report("site", True)
            report = workspace.read_file("site", "RACHEL_REPORT.md")
            self.assertIn("Relatorio de desenvolvimento", report["content"])
        finally: temp.cleanup()


if __name__ == "__main__": unittest.main()
