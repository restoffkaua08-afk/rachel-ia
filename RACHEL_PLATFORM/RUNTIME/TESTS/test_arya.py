import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))
from arya_runtime import run, safe_cwd

class AryaTests(unittest.TestCase):
    def test_workspace_is_allowed(self):
        self.assertEqual(safe_cwd(None), ROOT)
    def test_outside_workspace_is_blocked(self):
        with self.assertRaises(ValueError): safe_cwd(str(ROOT.parent))
    def test_read_only_python_runs_without_approval(self):
        result = run(sys.executable, ["--version"], None, False)
        self.assertEqual(result["returncode"], 0)

    def test_git_accepts_option_arguments(self):
        result = run("git", ["status", "--short"], None, False)
        self.assertEqual(result["returncode"], 0)

if __name__ == "__main__": unittest.main()
