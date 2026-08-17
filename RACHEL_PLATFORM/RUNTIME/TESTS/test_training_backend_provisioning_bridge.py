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


class TrainingBackendProvisioningBridgeTests(
    unittest.TestCase
):

    def setUp(self):

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

        self.env = os.environ.copy()

        self.env[
            "RACHEL_RUNTIME_ROOT"
        ] = str(ROOT)

        self.env[
            "RACHEL_STATE_ROOT"
        ] = str(state)

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
                    "samwell_training_backend_status"
                )
            }
        )

        self.assertEqual(
            "samwell",
            status[
                "contract"
            ][
                "owner"
            ],
        )

        self.assertTrue(
            status[
                "contract_only"
            ]
        )

        self.assertFalse(
            status[
                "training_execution_enabled"
            ]
        )

    def test_plan(self):

        plan = self.call(
            {
                "action": (
                    "samwell_training_backend_plan"
                )
            }
        )

        self.assertEqual(
            "blocked",
            plan[
                "state"
            ],
        )

        self.assertFalse(
            plan[
                "provisioning_execution_enabled"
            ]
        )

        self.assertFalse(
            plan[
                "command_generation_enabled"
            ]
        )

        self.assertFalse(
            plan[
                "training_execution_enabled"
            ]
        )

    def test_dashboard(self):

        dashboard = self.call(
            {
                "action": "dashboard"
            }
        )

        self.assertIn(
            "training_backend_provisioning",
            dashboard,
        )

        provisioning = dashboard[
            "training_backend_provisioning"
        ]

        self.assertEqual(
            "samwell",
            provisioning[
                "contract"
            ][
                "owner"
            ],
        )

    def test_packaging_is_not_training(self):

        status = self.call(
            {
                "action": (
                    "samwell_training_backend_status"
                )
            }
        )

        self.assertFalse(
            status[
                "environment"
            ][
                "use_packaging_python"
            ]
        )

        self.assertFalse(
            status[
                "environment"
            ][
                "use_packaging_torch"
            ]
        )


if __name__ == "__main__":
    unittest.main()
