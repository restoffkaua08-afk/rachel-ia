import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))
from project_workspace import ProjectWorkspace, WorkspaceError


class WorkspaceTests(unittest.TestCase):
    def runtime(self):
        temp = tempfile.TemporaryDirectory()
        work = ProjectWorkspace(Path(temp.name) / "projects", ROOT / "RACHEL_PLATFORM" / "CONFIG" / "project.policy.json")
        return temp, work

    def test_create_requires_approval(self):
        temp, work = self.runtime()
        try:
            with self.assertRaises(PermissionError): work.create_project("site", False)
        finally: temp.cleanup()

    def test_traversal_is_blocked(self):
        temp, work = self.runtime()
        try:
            work.create_project("site", True)
            with self.assertRaises(WorkspaceError): work.write_files("site", [{"path": "../bad.txt", "content": "x"}], True)
        finally: temp.cleanup()

    def test_secret_is_blocked(self):
        temp, work = self.runtime()
        try:
            work.create_project("site", True)
            with self.assertRaises(WorkspaceError): work.write_files("site", [{"path": ".env", "content": "x"}], True)
        finally: temp.cleanup()

    def test_write_requires_approval(self):
        temp, work = self.runtime()
        try:
            work.create_project("site", True)
            with self.assertRaises(PermissionError): work.write_files("site", [{"path": "index.html", "content": "x"}], False)
        finally: temp.cleanup()

    def test_batch_write_and_inspection(self):
        temp, work = self.runtime()
        try:
            work.create_project("site", True)
            result = work.write_files("site", [{"path": "index.html", "content": "<h1>Site</h1>"}, {"path": "css/style.css", "content": "body{}"}, {"path": "js/main.js", "content": "console.log('ok')"}], True)
            self.assertEqual(result["file_count"], 3)
            self.assertEqual(work.inspect("site")["file_count"], 3)
        finally: temp.cleanup()

    def test_overwrite_creates_backup(self):
        temp, work = self.runtime()
        try:
            work.create_project("site", True)
            work.write_files("site", [{"path": "index.html", "content": "v1"}], True)
            work.write_files("site", [{"path": "index.html", "content": "v2"}], True)
            backups = list((work.project_path("site") / ".rachel" / "history").rglob("index.html"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), "v1")
        finally: temp.cleanup()

    def test_read_returns_hash(self):
        temp, work = self.runtime()
        try:
            work.create_project("site", True)
            work.write_files("site", [{"path": "README.md", "content": "# Site"}], True)
            self.assertEqual(len(work.read_file("site", "README.md")["sha256"]), 64)
        finally: temp.cleanup()

    def test_executable_is_blocked(self):
        temp, work = self.runtime()
        try:
            work.create_project("site", True)
            with self.assertRaises(WorkspaceError): work.write_files("site", [{"path": "bad.exe", "content": "x"}], True)
        finally: temp.cleanup()


if __name__ == "__main__": unittest.main()
