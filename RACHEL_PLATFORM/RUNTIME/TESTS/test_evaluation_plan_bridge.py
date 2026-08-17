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


class EvaluationPlanBridgeTests(
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

    def test_plan_status(
        self,
    ):

        status = self.call(
            "evaluation_plan_status"
        )

        self.assertEqual(
            "dany",
            status[
                "owner"
            ],
        )

        self.assertFalse(
            status[
                "ready"
            ]
        )

        self.assertEqual(
            4,
            status[
                "blocked_phase_count"
            ],
        )

        self.assertTrue(
            status[
                "read_only"
            ]
        )

        self.assertFalse(
            status[
                "execution_enabled"
            ]
        )

    def test_plan_preview(
        self,
    ):

        preview = self.call(
            "evaluation_plan_preview"
        )

        self.assertEqual(
            4,
            preview[
                "phase_count"
            ],
        )

        self.assertEqual(
            0,
            preview[
                "ready_phase_count"
            ],
        )

        self.assertFalse(
            preview[
                "evaluation_executed"
            ]
        )

        self.assertFalse(
            preview[
                "report_generated"
            ]
        )

        self.assertFalse(
            preview[
                "comparison_computed"
            ]
        )

        self.assertFalse(
            preview[
                "decision_recorded"
            ]
        )

        self.assertFalse(
            preview[
                "promotion_executed"
            ]
        )

    def test_dashboard_contains_plan(
        self,
    ):

        dashboard = self.call(
            "dashboard"
        )

        self.assertIn(
            "evaluation_plan",
            dashboard,
        )

        plan = dashboard[
            "evaluation_plan"
        ]

        self.assertEqual(
            "dany",
            plan[
                "owner"
            ],
        )

        self.assertFalse(
            plan[
                "ready"
            ]
        )

        self.assertTrue(
            plan[
                "read_only"
            ]
        )

        self.assertFalse(
            plan[
                "execution_enabled"
            ]
        )


if __name__ == "__main__":
    unittest.main()
