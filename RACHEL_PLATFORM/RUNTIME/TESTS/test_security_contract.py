import inspect
import subprocess
import unittest
from pathlib import Path
import sys

SRC = Path(__file__).resolve().parents[1] / "SRC"
sys.path.insert(0, str(SRC))

from cognitive_runtime import NedCognitiveBridge
from task_executor import (
    TaskExecutor,
    build_parser as build_executor_parser,
    parse_approval_bindings,
)
from task_runtime import (
    TaskOrchestrator,
    build_parser as build_task_parser,
)
from tools_runtime import ToolCoordinator


class SecurityContractTests(unittest.TestCase):
    def test_only_token_contract_remains(self):
        tool = inspect.signature(
            ToolCoordinator.invoke
        ).parameters
        executor = inspect.signature(
            TaskExecutor.execute
        ).parameters
        task = inspect.signature(
            TaskOrchestrator.execute
        ).parameters

        self.assertNotIn("approved", tool)
        self.assertIn("approval_id", tool)
        self.assertNotIn("approved_steps", executor)
        self.assertNotIn("approve_all", executor)
        self.assertIn("approval_ids", executor)
        self.assertNotIn("approved_steps", task)
        self.assertNotIn("approve_all", task)

    def test_cognitive_assist_uses_approval_id_contract(self):
        parameters = inspect.signature(
            NedCognitiveBridge.assist
        ).parameters

        self.assertNotIn("approved", parameters)
        self.assertIn("approval_id", parameters)

        source = (
            SRC / "cognitive_runtime.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            'assist.add_argument("--approval-id")',
            source,
        )
        self.assertNotIn(
            'assist.add_argument("--approved"',
            source,
        )

    def test_cognitive_cli_rejects_legacy_approved_flag(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SRC / "cognitive_runtime.py"),
                "cognitive",
                "assist",
                "ola",
                "--approved",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertEqual(result.returncode, 2)

    def test_executor_cli_rejects_approve_all(self):
        parser = build_executor_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "run",
                    "--plan-id",
                    "plan_test",
                    "--approve-all",
                ]
            )

    def test_task_cli_rejects_approved_step(self):
        parser = build_task_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "run",
                    "--plan-id",
                    "plan_test",
                    "--approved-step",
                    "write",
                ]
            )

    def test_binding_parser_requires_cyber_token(self):
        approval_id = "approval_" + "a" * 32
        parsed = parse_approval_bindings(
            ["write=" + approval_id]
        )
        self.assertEqual(
            parsed,
            {"write": approval_id},
        )

        with self.assertRaises(Exception):
            parse_approval_bindings(
                ["write=yes"]
            )


if __name__ == "__main__":
    unittest.main()
