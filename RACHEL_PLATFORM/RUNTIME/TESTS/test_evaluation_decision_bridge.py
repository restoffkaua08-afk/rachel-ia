from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)

BRIDGE = (
    ROOT
    / "APP"
    / "bridge"
    / "rachel_bridge.py"
)


class EvaluationDecisionBridgeTests(
    unittest.TestCase
):

    def setUp(
        self,
    ):

        self.temp = (
            tempfile.TemporaryDirectory()
        )

        self.root = Path(
            self.temp.name
        )

        state = (
            self.root
            / "STATE"
        )

        state.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.env = (
            os.environ.copy()
        )

        self.env[
            "RACHEL_RUNTIME_ROOT"
        ] = str(ROOT)

        self.env[
            "RACHEL_STATE_ROOT"
        ] = str(state)

        self.env[
            "PYTHONUTF8"
        ] = "1"

    def tearDown(
        self,
    ):

        self.temp.cleanup()

    def call(
        self,
        action: str,
    ) -> dict:

        request = (
            self.root
            / "request.json"
        )

        request.write_text(
            json.dumps(
                {
                    "action": action,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        process = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                str(BRIDGE),
                "--request-file",
                str(request),
            ],
            cwd=str(ROOT),
            env=self.env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )

        self.assertEqual(
            0,
            process.returncode,
            msg=(
                process.stderr
                + "\n"
                + process.stdout
            ),
        )

        response = json.loads(
            process.stdout.strip()
        )

        self.assertTrue(
            response[
                "ok"
            ],
            msg=response,
        )

        return response[
            "payload"
        ]

    def assert_contracts(
        self,
        evaluation: dict,
    ):

        contracts = evaluation[
            "decision_contracts"
        ]

        self.assertEqual(
            "dany",
            contracts[
                "owner"
            ],
        )

        self.assertEqual(
            "not-produced",
            contracts[
                "report"
            ][
                "result_state"
            ],
        )

        self.assertEqual(
            "not-computed",
            contracts[
                "regression"
            ][
                "result_state"
            ],
        )

        self.assertEqual(
            "not-decided",
            contracts[
                "promotion_decision"
            ][
                "decision_state"
            ],
        )

        self.assertFalse(
            contracts[
                "execution_enabled"
            ]
        )

        self.assertFalse(
            contracts[
                "report_written"
            ]
        )

        self.assertFalse(
            contracts[
                "comparison_computed"
            ]
        )

        self.assertFalse(
            contracts[
                "decision_recorded"
            ]
        )

        self.assertFalse(
            contracts[
                "promotion_executed"
            ]
        )

        self.assertFalse(
            contracts[
                "weights_modified"
            ]
        )

    def test_evaluation_status_contains_decision_contracts(
        self,
    ):

        evaluation = (
            self.call(
                "evaluation_status"
            )
        )

        self.assert_contracts(
            evaluation
        )

    def test_dashboard_contains_decision_contracts(
        self,
    ):

        dashboard = self.call(
            "dashboard"
        )

        self.assertIn(
            "evaluation",
            dashboard,
        )

        self.assert_contracts(
            dashboard[
                "evaluation"
            ]
        )


if __name__ == "__main__":
    unittest.main()
