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


from rachel_core.dataset_factory import (
    DatasetFactory,
)


class LearningDatasetBridgeTests(
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

    def version(
        self,
        suffix: str,
    ) -> dict:

        return (
            self.factory
            .create_version(
                "conversation",
                [
                    {
                        "source_kind": (
                            "experience"
                        ),
                        "source_id": (
                            "exp_bridge_"
                            + suffix
                        ),
                        "payload": {
                            "user": (
                                "Pergunta "
                                + suffix
                            ),
                            "assistant": (
                                "Resposta valida "
                                + suffix
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
                ],
                metadata={
                    "test": (
                        "learning-dataset-bridge"
                    ),
                    "suffix": suffix,
                },
            )
        )

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
                    tempfile._get_candidate_names()
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
            timeout=60,
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

    def test_status_and_review_are_available(
        self,
    ):
        manifest = self.version(
            "status"
        )

        status = self.call(
            {
                "action": (
                    "learning_dataset_status"
                ),
            }
        )

        self.assertEqual(
            1,
            status[
                "versions"
            ],
        )

        self.assertEqual(
            1,
            status[
                "states"
            ][
                "candidate"
            ],
        )

        review = self.call(
            {
                "action": (
                    "learning_dataset_review"
                ),
                "version_id": (
                    manifest[
                        "version_id"
                    ]
                ),
            }
        )

        self.assertTrue(
            review[
                "integrity"
            ][
                "integrity"
            ]
        )

        self.assertTrue(
            review[
                "dany"
            ][
                "accepted"
            ]
        )

        self.assertEqual(
            100,
            review[
                "dany"
            ][
                "minimum_score"
            ],
        )

    def test_complete_security_panel_flow(
        self,
    ):
        manifest = self.version(
            "flow"
        )

        version_id = (
            manifest[
                "version_id"
            ]
        )

        pending = self.call(
            {
                "action": (
                    "learning_dataset_request_export"
                ),
                "version_id": (
                    version_id
                ),
            }
        )

        self.assertEqual(
            "approval_required",
            pending[
                "state"
            ],
        )

        approval = (
            pending[
                "approval"
            ]
        )

        approval_id = (
            approval[
                "id"
            ]
        )

        self.assertEqual(
            "high",
            approval[
                "risk"
            ],
        )

        self.assertEqual(
            "publish",
            approval[
                "effect"
            ],
        )

        self.assertEqual(
            "candidate",
            self.factory
            .get_version(
                version_id
            )[
                "state"
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

        cards = (
            security[
                "items"
            ]
        )

        matches = [
            item
            for item
            in cards
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
            (
                "learning.dataset."
                "approve_export"
            ),
            card[
                "tool"
            ],
        )

        self.assertEqual(
            "HIGH",
            card[
                "risk_label"
            ],
        )

        self.assertEqual(
            (
                "APROVAR "
                + approval_id
            ),
            card[
                "confirmation"
            ][
                "approve"
            ],
        )

        decided = self.call(
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

        self.assertEqual(
            "approved",
            decided[
                "status"
            ],
        )

        self.assertEqual(
            "candidate",
            self.factory
            .get_version(
                version_id
            )[
                "state"
            ],
        )

        promoted = self.call(
            {
                "action": (
                    "learning_dataset_approve_export"
                ),
                "version_id": (
                    version_id
                ),
                "approval_id": (
                    approval_id
                ),
            }
        )

        self.assertEqual(
            "approved-for-export",
            promoted[
                "state"
            ],
        )

        self.assertEqual(
            "consumed",
            promoted[
                "cyber"
            ][
                "status"
            ],
        )

        self.assertFalse(
            promoted[
                "automatic_training"
            ]
        )

        self.assertFalse(
            promoted[
                "external_export"
            ]
        )

        stored = (
            self.factory
            .get_version(
                version_id
            )
        )

        self.assertEqual(
            "approved-for-export",
            stored[
                "state"
            ],
        )

        history = self.call(
            {
                "action": (
                    "learning_dataset_review_history"
                ),
                "version_id": (
                    version_id
                ),
            }
        )

        self.assertEqual(
            1,
            len(
                history[
                    "items"
                ]
            ),
        )

        self.assertEqual(
            "cyber-consumed",
            history[
                "items"
            ][0][
                "authorization"
            ],
        )

    def test_wrong_explicit_confirmation_is_rejected(
        self,
    ):
        manifest = self.version(
            "confirmation"
        )

        version_id = (
            manifest[
                "version_id"
            ]
        )

        pending = self.call(
            {
                "action": (
                    "learning_dataset_request_export"
                ),
                "version_id": (
                    version_id
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

        error = self.call(
            {
                "action": (
                    "security_decide"
                ),
                "approval_id": (
                    approval_id
                ),
                "allow": True,
                "confirmation": (
                    "APROVAR ERRADO"
                ),
            },
            expect_ok=False,
        )

        self.assertEqual(
            "ValueError",
            error[
                "type"
            ],
        )

        self.assertEqual(
            "candidate",
            self.factory
            .get_version(
                version_id
            )[
                "state"
            ],
        )

    def test_versions_action_lists_registry(
        self,
    ):
        first = self.version(
            "list-1"
        )

        second = (
            self.factory
            .create_version(
                "preference",
                [
                    {
                        "source_kind": (
                            "feedback"
                        ),
                        "source_id": (
                            "fb_list"
                        ),
                        "payload": {
                            "prompt": (
                                "Pergunta"
                            ),
                            "rejected_response": (
                                "A"
                            ),
                            "preferred_response": (
                                "B"
                            ),
                        },
                        "provenance": {
                            "explicit_user_feedback": (
                                True
                            ),
                        },
                    }
                ],
                metadata={
                    "test": (
                        "list-preference"
                    ),
                },
            )
        )

        result = self.call(
            {
                "action": (
                    "learning_dataset_versions"
                ),
                "limit": 20,
            }
        )

        ids = {
            item[
                "id"
            ]
            for item
            in result[
                "items"
            ]
        }

        self.assertIn(
            first[
                "version_id"
            ],
            ids,
        )

        self.assertIn(
            second[
                "version_id"
            ],
            ids,
        )

        filtered = self.call(
            {
                "action": (
                    "learning_dataset_versions"
                ),
                "dataset_type": (
                    "preference"
                ),
                "limit": 20,
            }
        )

        self.assertEqual(
            1,
            len(
                filtered[
                    "items"
                ]
            ),
        )

        self.assertEqual(
            "preference",
            filtered[
                "items"
            ][0][
                "dataset_type"
            ],
        )


if __name__ == "__main__":
    unittest.main()