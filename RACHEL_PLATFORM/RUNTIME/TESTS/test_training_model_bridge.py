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


class TrainingModelBridgeTests(
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

        self.env = (
            os.environ.copy()
        )

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

    @staticmethod
    def dataset():
        return {
            "id": (
                "sft-compiled-desktop-test"
            ),
            "state": (
                "compiled-local"
            ),
            "training_format": (
                "sft"
            ),
            "integrity": True,
            "train_count": 80,
            "eval_count": 20,
            "train_sha256": (
                "a" * 64
            ),
            "eval_sha256": (
                "b" * 64
            ),
        }

    @staticmethod
    def capable_hardware():
        return {
            "nvidia_cuda": True,
            "torch_cuda": True,
            "vram_gb": 24.0,
            "ram_gb": 32.0,
            "free_disk_gb": 120.0,
            "weight_training_allowed": True,
        }

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
            timeout=120,
        )

        response = json.loads(
            process.stdout.strip()
        )

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

    def test_model_status_exposes_selected_base(
        self,
    ):
        status = self.call(
            {
                "action": (
                    "model_status"
                )
            }
        )

        model = status[
            "model"
        ]

        self.assertEqual(
            "rachel-model-v0.1",
            model[
                "model_id"
            ],
        )

        self.assertEqual(
            "Qwen/Qwen3-1.7B-Base",
            model[
                "base_model_repository"
            ],
        )

        self.assertFalse(
            status[
                "can_train_weights"
            ]
        )

        self.assertFalse(
            status[
                "training_execution_enabled"
            ]
        )

    def test_training_run_preview_is_lora_sft_only(
        self,
    ):
        preview = self.call(
            {
                "action": (
                    "training_run_preview"
                )
            }
        )

        recipe = preview[
            "template"
        ][
            "recipe"
        ]

        self.assertEqual(
            "lora",
            recipe[
                "method"
            ],
        )

        self.assertEqual(
            "sft",
            recipe[
                "training_format"
            ],
        )

        self.assertFalse(
            preview[
                "can_train_weights"
            ]
        )

        self.assertFalse(
            preview[
                "automatic_training"
            ]
        )

    def test_dry_run_request_is_visible_in_security_panel(
        self,
    ):
        request = self.call(
            {
                "action": (
                    "training_dry_run_request"
                ),
                "compiled_dataset": (
                    self.dataset()
                ),
                "observed_hardware": (
                    self.capable_hardware()
                ),
            }
        )

        approval = request[
            "approval"
        ]

        snapshot = self.call(
            {
                "action": (
                    "security_snapshot"
                ),
                "limit": 50,
            }
        )

        cards = {
            item["id"]: item
            for item
            in snapshot[
                "items"
            ]
        }

        self.assertIn(
            approval[
                "id"
            ],
            cards,
        )

        card = cards[
            approval[
                "id"
            ]
        ]

        self.assertEqual(
            "learning.training.dry_run_manifest",
            card[
                "tool"
            ],
        )

        self.assertEqual(
            "write",
            card[
                "effect"
            ],
        )

        self.assertEqual(
            "medium",
            card[
                "risk"
            ],
        )

    def test_full_desktop_dry_run_flow_is_safe(
        self,
    ):
        dataset = self.dataset()

        hardware = (
            self.capable_hardware()
        )

        request = self.call(
            {
                "action": (
                    "training_dry_run_request"
                ),
                "compiled_dataset": (
                    dataset
                ),
                "observed_hardware": (
                    hardware
                ),
            }
        )

        approval_id = (
            request[
                "approval"
            ][
                "id"
            ]
        )

        snapshot = self.call(
            {
                "action": (
                    "security_snapshot"
                ),
                "limit": 50,
            }
        )

        card = next(
            item
            for item
            in snapshot[
                "items"
            ]
            if item[
                "id"
            ]
            == approval_id
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
                    card[
                        "confirmation"
                    ][
                        "approve"
                    ]
                ),
            }
        )

        self.assertEqual(
            "approved",
            decision[
                "status"
            ],
        )

        result = self.call(
            {
                "action": (
                    "training_dry_run_materialize"
                ),
                "compiled_dataset": (
                    dataset
                ),
                "observed_hardware": (
                    hardware
                ),
                "approval_id": (
                    approval_id
                ),
            }
        )

        self.assertEqual(
            "dry-run-materialized",
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

        self.assertFalse(
            result[
                "training_started"
            ]
        )

        self.assertFalse(
            result[
                "litgpt_invoked"
            ]
        )

        self.assertFalse(
            result[
                "weights_modified"
            ]
        )

        verify = self.call(
            {
                "action": (
                    "training_dry_run_verify"
                ),
                "run_id": (
                    result[
                        "run_id"
                    ]
                ),
            }
        )

        self.assertTrue(
            verify[
                "integrity"
            ]
        )

        self.assertTrue(
            verify[
                "safe_execution"
            ]
        )

    def test_argument_tampering_fails_through_bridge(
        self,
    ):
        dataset = self.dataset()

        hardware = (
            self.capable_hardware()
        )

        request = self.call(
            {
                "action": (
                    "training_dry_run_request"
                ),
                "compiled_dataset": (
                    dataset
                ),
                "observed_hardware": (
                    hardware
                ),
            }
        )

        approval_id = (
            request[
                "approval"
            ][
                "id"
            ]
        )

        snapshot = self.call(
            {
                "action": (
                    "security_snapshot"
                )
            }
        )

        card = next(
            item
            for item
            in snapshot[
                "items"
            ]
            if item[
                "id"
            ]
            == approval_id
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
                    card[
                        "confirmation"
                    ][
                        "approve"
                    ]
                ),
            }
        )

        changed = dict(
            dataset
        )

        changed[
            "train_sha256"
        ] = "c" * 64

        error = self.call(
            {
                "action": (
                    "training_dry_run_materialize"
                ),
                "compiled_dataset": (
                    changed
                ),
                "observed_hardware": (
                    hardware
                ),
                "approval_id": (
                    approval_id
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

        self.assertIn(
            "arguments",
            error[
                "message"
            ].casefold(),
        )

    def test_dashboard_contains_stage12_surfaces(
        self,
    ):
        dashboard = self.call(
            {
                "action": (
                    "dashboard"
                )
            }
        )

        self.assertIn(
            "rachel_model",
            dashboard,
        )

        self.assertIn(
            "training_run",
            dashboard,
        )

        self.assertIn(
            "training_execution_gate",
            dashboard,
        )

        self.assertFalse(
            dashboard[
                "rachel_model"
            ][
                "can_train_weights"
            ]
        )

        self.assertFalse(
            dashboard[
                "training_execution_gate"
            ][
                "training_execution_enabled"
            ]
        )


if __name__ == "__main__":
    unittest.main()