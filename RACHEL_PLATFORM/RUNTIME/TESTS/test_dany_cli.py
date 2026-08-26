import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"
CLI = SRC / "dany_cli.py"
SCRIPT = ROOT / "RACHEL_PLATFORM" / "SCRIPTS" / "rachel.ps1"


class DanyCliTests(unittest.TestCase):
    def run_cli(self, *args: str):
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    def test_cli_accepts_grounded_structural_response(self):
        process = self.run_cli(
            "Resposta objetiva sobre OAuth.",
            "--request",
            "Explique OAuth",
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        payload = json.loads(process.stdout)
        self.assertTrue(payload["accepted"])
        self.assertIn("scope", payload)

    def test_cli_rejects_failed_tool_described_as_success(self):
        process = self.run_cli(
            "Os testes foram executados com sucesso.",
            "--request",
            "Rode os testes",
            "--tool-result-json",
            '{"state":"completed","result":{"returncode":1,"stderr":"1 failed"}}',
        )
        self.assertEqual(process.returncode, 1)
        payload = json.loads(process.stdout)
        self.assertFalse(payload["accepted"])
        self.assertIn("TOOL_RESULT_CONSISTENT", payload["issues"])

    def test_cli_research_requires_low_confidence_without_primary_source(self):
        process = self.run_cli(
            "A evidência é limitada e a confiança é baixa; não encontrei fonte primária.",
            "--request",
            "Pesquise mudanças recentes",
            "--research",
            "--primary-source-count",
            "0",
            "--factuality-verified",
            "false",
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        payload = json.loads(process.stdout)
        self.assertTrue(payload["checks"]["admits_uncertainty"])

    def test_powershell_router_separates_evaluate_from_cognitive(self):
        content = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('$danyCli = Join-Path $root "RACHEL_PLATFORM\\RUNTIME\\SRC\\dany_cli.py"', content)
        self.assertIn('$evaluateDomains = @("evaluate")', content)
        self.assertIn('& $python $danyCli @($args | Select-Object -Skip 1)', content)
        self.assertEqual(content.count('$cognitiveDomains = @("cognitive")'), 1)


if __name__ == "__main__":
    unittest.main()
