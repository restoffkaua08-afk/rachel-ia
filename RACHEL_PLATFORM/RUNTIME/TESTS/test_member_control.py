import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONTROLLER = ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC" / "member_control.py"


class MemberControlTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CONTROLLER), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_team_has_ten_members(self) -> None:
        result = self.run_cli("team")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len([line for line in result.stdout.splitlines() if " | " in line]), 10)

    def test_tyrion_has_all_organs(self) -> None:
        result = self.run_cli("member", "status", "tyrion")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(len(payload["organs"]), 23)
        self.assertEqual(payload["missing_organs"], [])


if __name__ == "__main__":
    unittest.main()
