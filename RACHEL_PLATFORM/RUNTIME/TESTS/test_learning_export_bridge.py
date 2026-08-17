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

CORE_SRC = (
    ROOT
    / "RACHEL_CORE"
    / "src"
)

BRIDGE = (
    ROOT
    / "APP"
    / "bridge"
    / "rachel_bridge.py"
)

if str(CORE_SRC) not in sys.path:
    sys.path.insert(
        0,
        str(CORE_SRC),
    )


from rachel_core.dataset_export import (
    DatasetExportFactory,
)

from rachel_core.dataset_factory import (
    DatasetFactory,
)


class LearningExportBridgeTests(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:

        self.temp = (
            tempfile
            .TemporaryDirectory()
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

        self.factory = DatasetFactory(
            self.state
            / "learning-datasets"
        )

        self.exporter = (
            DatasetExportFactory(
                self.state
                / "training-exports"
            )
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

    def tearDown(
        self,
    ) -> None:
        self.temp.cleanup()

    def approved_version(
        self,
        suffix: str,
        count: int = 10,
    ) -> str:

        manifest = (
            self.factory
            .create_version(
                "conversation",
                [
                    {
                        "source_kind": (
                            "experience"
                        ),
                        "source_id": (
                            f"exp_{suffix}_{index}"
                        ),
                        "payload": {
                            "user": (
                                f"Pergunta {index}"
                            ),
                            "assistant": (
                                f"Resposta {index}"
                            ),
                        },
                        "provenance": {
                            "quality_score": 100,
                            "review_state": (
                                "user_accepted"
                            ),
                            "dany_gate": (
                                "passed"
                            ),
                        },
                    }
                    for index
                    in range(count)
                ],
                metadata={
                    "test": suffix,
                },
            )
        )

        version_id = (
            manifest[
                "version_id"
            ]
        )

        self.factory.record_review_transition(
            version_id,
            target_state=(
                "approved-for-export"
            ),
            reviewer="bridge-test",
            dany_accepted=True,
            dany_score=100,
            dany_issues=[],
            dany_checks={
                "bridge_test": True,
            },
            authorization=(
                "cyber-consumed"
            ),
        )

        return version_id

    def call(
        self,
        payload: dict,
        *,
        expect_ok: bool = True,
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
            timeout=90,
        )

        try:
            response = json.loads(
                process.stdout.strip()
            )
        except json.JSONDecodeError as error:
            raise AssertionError(
                "Bridge stdout invalido: "
                + process.stdout
                + "\nSTDERR: "
                + process.stderr
            ) from error

        if expect_ok:
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

        self.assertNotEqual(
            0,
            process.returncode,
        )

        self.assertFalse(
            response.get(
                "ok"
            )
        )

        return response[
            "error"
        ]

    def test_plan_is_available_on_desktop(
        self,
    ):
        version_id = (
            self.approved_version(
                "plan"
            )
        )

        plan = self.call(
            {
                "action": (
                    "learning_export_plan"
                ),
                "version_id": (
                    version_id
                ),
                "eval_percent": 20,
                "split_seed": (
                    "desktop-seed"
                ),
            }
        )

        self.assertEqual(
            8,
            plan[
                "train_count"
            ],
        )

        self.assertEqual(
            2,
            plan[
                "eval_count"
            ],
        )

        self.assertEqual(
            "desktop-seed",
            plan[
                "split_seed"
            ],
        )

        self.assertFalse(
            plan[
                "automatic_training"
            ]
        )

    def test_complete_cyber_export_flow(
        self,
    ):
        version_id = (
            self.approved_version(
                "flow"
            )
        )

        pending = self.call(
            {
                "action": (
                    "learning_export_request"
                ),
                "version_id": (
                    version_id
                ),
                "eval_percent": 20,
                "split_seed": (
                    "desktop-flow-v1"
                ),
            }
        )

        approval_id = (
            pending[
                "approval"
            ][
                "id"
            ]
        )

        self.assertEqual(
            "medium",
            pending[
                "approval"
            ][
                "risk"
            ],
        )

        self.assertEqual(
            "write",
            pending[
                "approval"
            ][
                "effect"
            ],
        )

        self.assertEqual(
            0,
            self.exporter
            .status()[
                "exports"
            ],
        )

        security = self.call(
            {
                "action": (
                    "security_snapshot"
                ),
                "limit": 50,
            }
        )

        matches = [
            item
            for item
            in security[
                "items"
            ]
            if item[
                "id"
            ]
            == approval_id
        ]

        self.assertEqual(
            1,
            len(matches),
        )

        card = matches[0]

        self.assertEqual(
            "learning.dataset.export_local",
            card[
                "tool"
            ],
        )

        self.assertEqual(
            "MEDIUM",
            card[
                "risk_label"
            ],
        )

        confirmation = (
            "APROVAR "
            + approval_id
        )

        self.assertEqual(
            confirmation,
            card[
                "confirmation"
            ][
                "approve"
            ],
        )

        decision = self.call(
            {
                "action": (
                    "security_decide"
                ),
                "approval_id": (
                    approval_id
                ),
                "allow": True,
                "confirmation": (
                    confirmation
                ),
            }
        )

        self.assertEqual(
            "approved",
            decision[
                "status"
            ],
        )

        self.assertEqual(
            0,
            self.exporter
            .status()[
                "exports"
            ],
        )

        result = self.call(
            {
                "action": (
                    "learning_export_execute"
                ),
                "version_id": (
                    version_id
                ),
                "approval_id": (
                    approval_id
                ),
                "eval_percent": 20,
                "split_seed": (
                    "desktop-flow-v1"
                ),
            }
        )

        self.assertEqual(
            "ready-local",
            result[
                "state"
            ],
        )

        self.assertEqual(
            "consumed",
            result[
                "cyber"
            ][
                "status"
            ],
        )

        export_id = (
            result[
                "export"
            ][
                "id"
            ]
        )

        verify = self.call(
            {
                "action": (
                    "learning_export_verify"
                ),
                "export_id": (
                    export_id
                ),
            }
        )

        self.assertTrue(
            verify[
                "integrity"
            ]
        )

        self.assertEqual(
            8,
            verify[
                "train_count"
            ],
        )

        self.assertEqual(
            2,
            verify[
                "eval_count"
            ],
        )

        listing = self.call(
            {
                "action": (
                    "learning_export_list"
                ),
                "limit": 20,
            }
        )

        self.assertEqual(
            1,
            len(
                listing[
                    "items"
                ]
            ),
        )

        self.assertEqual(
            export_id,
            listing[
                "items"
            ][0][
                "id"
            ],
        )

    def test_approved_request_cannot_change_split(
        self,
    ):
        version_id = (
            self.approved_version(
                "binding"
            )
        )

        pending = self.call(
            {
                "action": (
                    "learning_export_request"
                ),
                "version_id": (
                    version_id
                ),
                "eval_percent": 20,
                "split_seed": (
                    "seed-original"
                ),
            }
        )

        approval_id = (
            pending[
                "approval"
            ][
                "id"
            ]
        )

        self.call(
            {
                "action": (
                    "security_decide"
                ),
                "approval_id": (
                    approval_id
                ),
                "allow": True,
                "confirmation": (
                    "APROVAR "
                    + approval_id
                ),
            }
        )

        error = self.call(
            {
                "action": (
                    "learning_export_execute"
                ),
                "version_id": (
                    version_id
                ),
                "approval_id": (
                    approval_id
                ),
                "eval_percent": 10,
                "split_seed": (
                    "seed-original"
                ),
            },
            expect_ok=False,
        )

        self.assertEqual(
            "ApprovalError",
            error[
                "type"
            ],
        )

        self.assertEqual(
            0,
            self.exporter
            .status()[
                "exports"
            ],
        )

    def test_dashboard_reports_local_exports(
        self,
    ):
        status = self.call(
            {
                "action": (
                    "learning_export_status"
                ),
            }
        )

        self.assertEqual(
            0,
            status[
                "exports"
            ],
        )

        self.assertFalse(
            status[
                "automatic_training"
            ]
        )

        dashboard = self.call(
            {
                "action": "dashboard",
            }
        )

        self.assertIn(
            "learning_exports",
            dashboard,
        )

        self.assertEqual(
            0,
            dashboard[
                "learning_exports"
            ][
                "exports"
            ],
        )


if __name__ == "__main__":
    unittest.main()