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


class EvaluationBridgeTests(
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

    def test_status_backward_compatibility(
        self,
    ):

        status = self.call(
            {
                "action": "evaluation_status"
            }
        )

        self.assertEqual(
            "dany",
            status[
                "member"
            ][
                "id"
            ],
        )

        # Alias legado do 1B.
        self.assertEqual(
            "qwen3:1.7b",
            status[
                "temporary_baseline"
            ][
                "id"
            ],
        )

        # Campo novo.
        self.assertEqual(
            "qwen3:1.7b",
            status[
                "baseline"
            ][
                "subject_id"
            ],
        )

        # Compatibilidade + campo explicito.
        self.assertEqual(
            "rachel-model-v0.1",
            status[
                "candidate"
            ][
                "id"
            ],
        )

        self.assertEqual(
            "rachel-model-v0.1",
            status[
                "candidate"
            ][
                "model_id"
            ],
        )

    def test_suites(
        self,
    ):

        result = self.call(
            {
                "action": "evaluation_suites"
            }
        )

        self.assertEqual(
            7,
            len(
                result[
                    "items"
                ]
            ),
        )

        self.assertFalse(
            result[
                "execution_enabled"
            ]
        )

    def test_suite_detail(
        self,
    ):

        suite = self.call(
            {
                "action": "evaluation_suite",
                "suite_id": "contract-integrity",
            }
        )

        self.assertEqual(
            "contract-integrity",
            suite[
                "id"
            ],
        )

        self.assertFalse(
            suite[
                "execution_enabled"
            ]
        )

    def test_promotion_blocked(
        self,
    ):

        result = self.call(
            {
                "action": (
                    "evaluation_promotion_eligibility"
                )
            }
        )

        self.assertFalse(
            result[
                "eligible"
            ]
        )

        self.assertEqual(
            "blocked",
            result[
                "state"
            ],
        )

    def test_dashboard(
        self,
    ):

        dashboard = self.call(
            {
                "action": "dashboard"
            }
        )

        self.assertIn(
            "evaluation",
            dashboard,
        )

        evaluation = dashboard[
            "evaluation"
        ]

        self.assertEqual(
            "dany",
            evaluation[
                "member"
            ][
                "id"
            ],
        )

        self.assertTrue(
            evaluation[
                "read_only"
            ]
        )

        self.assertFalse(
            evaluation[
                "model_execution"
            ]
        )

        self.assertFalse(
            evaluation[
                "promotion_executed"
            ]
        )


if __name__ == "__main__":
    unittest.main()
