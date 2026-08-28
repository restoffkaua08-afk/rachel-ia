from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
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


class DashboardRuntimeTests(
    unittest.TestCase
):

    def test_dashboard_uses_lightweight_samwell_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request = root / "request.json"
            state = root / "STATE"
            state.mkdir(
                parents=True,
                exist_ok=True,
            )

            request.write_text(
                json.dumps(
                    {
                        "action": "dashboard",
                    }
                ),
                encoding="utf-8",
            )

            env = os.environ.copy()
            env[
                "RACHEL_RUNTIME_ROOT"
            ] = str(ROOT)
            env[
                "RACHEL_STATE_ROOT"
            ] = str(state)
            env[
                "PYTHONUTF8"
            ] = "1"
            env[
                "PYTHONDONTWRITEBYTECODE"
            ] = "1"

            started = time.perf_counter()
            process = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-X",
                    "utf8",
                    str(BRIDGE),
                    "--request-file",
                    str(request),
                ],
                cwd=str(ROOT),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
                check=False,
            )
            elapsed = (
                time.perf_counter()
                - started
            )

            self.assertEqual(
                0,
                process.returncode,
                msg=process.stderr,
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

            dashboard = response[
                "payload"
            ]
            samwell = dashboard[
                "samwell"
            ]

            self.assertEqual(
                "lightweight",
                samwell[
                    "status_mode"
                ],
            )
            self.assertFalse(
                samwell[
                    "deep_audit_performed"
                ]
            )
            self.assertFalse(
                samwell[
                    "audit"
                ][
                    "performed"
                ]
            )
            self.assertIn(
                "agent",
                dashboard,
            )
            self.assertLess(
                elapsed,
                30.0,
                msg=(
                    "Dashboard exceeded 30s; "
                    f"elapsed={elapsed:.3f}s"
                ),
            )


if __name__ == "__main__":
    unittest.main()
