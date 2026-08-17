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


class SamwellBridgeTests(
    unittest.TestCase
):

    def setUp(self):

        self.temp = (
            tempfile.TemporaryDirectory()
        )

        self.root = Path(
            self.temp.name
        )

        self.state = (
            self.root
            / "STATE"
        )

        self.state.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.env = os.environ.copy()

        self.env[
            "RACHEL_RUNTIME_ROOT"
        ] = str(ROOT)

        self.env[
            "RACHEL_STATE_ROOT"
        ] = str(
            self.state
        )

        self.env[
            "PYTHONUTF8"
        ] = "1"

    def tearDown(self):
        self.temp.cleanup()

    def call(
        self,
        payload: dict,
    ) -> dict:

        request = (
            self.root
            / (
                "request-"
                + next(
                    tempfile
                    ._get_candidate_names()
                )
                + ".json"
            )
        )

        request.write_text(
            json.dumps(
                payload,
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

        response = json.loads(
            process.stdout.strip()
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

        self.assertTrue(
            response.get(
                "ok"
            ),
            msg=response,
        )

        return response[
            "payload"
        ]

    def test_status(self):

        status = self.call(
            {
                "action": (
                    "samwell_status"
                )
            }
        )

        self.assertEqual(
            "samwell",
            status[
                "member"
            ][
                "id"
            ],
        )

        self.assertEqual(
            "Portable Runtime",
            status[
                "portable_runtime"
            ][
                "display_name"
            ],
        )

        self.assertFalse(
            status[
                "execution_enabled"
            ]
        )

    def test_audit_is_read_only(self):

        audit = self.call(
            {
                "action": (
                    "samwell_audit"
                )
            }
        )

        self.assertGreater(
            audit[
                "total"
            ],
            10,
        )

        self.assertFalse(
            audit[
                "system_mutation"
            ]
        )

    def test_training_plan_is_blocked(self):

        plan = self.call(
            {
                "action": (
                    "samwell_provision_plan"
                ),
                "mode": "training",
            }
        )

        self.assertTrue(
            plan[
                "requires_cyber"
            ]
        )

        self.assertFalse(
            plan[
                "execution_enabled"
            ]
        )

    def test_dashboard_contains_samwell(self):

        dashboard = self.call(
            {
                "action": (
                    "dashboard"
                )
            }
        )

        self.assertIn(
            "samwell",
            dashboard,
        )

        self.assertEqual(
            "samwell",
            dashboard[
                "samwell"
            ][
                "member"
            ][
                "id"
            ],
        )


if __name__ == "__main__":
    unittest.main()
