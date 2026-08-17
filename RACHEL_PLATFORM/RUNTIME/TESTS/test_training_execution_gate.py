from __future__ import annotations

import json
import sys
import tempfile
import unittest

from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)

for path in (
    ROOT
    / "RACHEL_CORE"
    / "src",
    ROOT
    / "RACHEL_PLATFORM"
    / "RUNTIME"
    / "SRC",
):
    if str(path) not in sys.path:
        sys.path.insert(
            0,
            str(path),
        )


from cognitive_runtime import (
    DanyEvaluator,
)

from security_runtime import (
    ApprovalError,
    ApprovalStore,
)

from team_runtime import (
    CyberPolicy,
)

from rachel_core.model_contract import (
    ModelContract,
)

from rachel_core.training_run_planner import (
    TrainingRunPlanner,
)

from training_execution_gate import (
    TRAINING_DRY_RUN_EFFECT,
    TRAINING_DRY_RUN_TOOL,
    TrainingExecutionGate,
    TrainingExecutionGateError,
)


CONTRACT_PATH = (
    ROOT
    / "RACHEL_PLATFORM"
    / "CONFIG"
    / "rachel-model-v0.1.json"
)

PROFILES_PATH = (
    ROOT
    / "RACHEL_PLATFORM"
    / "CONFIG"
    / "training-hardware-profiles.json"
)


class TrainingExecutionGateTests(
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

        self.policy = (
            self.root
            / "approval.policy.json"
        )

        self.policy.write_text(
            json.dumps(
                {
                    "default_ttl_seconds": 300,
                    "maximum_ttl_seconds": 1800,
                }
            ),
            encoding="utf-8",
        )

        self.approvals = (
            ApprovalStore(
                path=(
                    self.root
                    / "approvals.db"
                ),
                policy_path=(
                    self.policy
                ),
            )
        )

        self.contract = (
            ModelContract.from_path(
                CONTRACT_PATH
            )
        )

        self.planner = (
            TrainingRunPlanner(
                contract=self.contract,
                profiles_path=(
                    PROFILES_PATH
                ),
            )
        )

        self.gate = (
            TrainingExecutionGate(
                planner=self.planner,
                approvals=self.approvals,
                evaluator=DanyEvaluator(),
                cyber=CyberPolicy(),
                root=(
                    self.root
                    / "dry-runs"
                ),
            )
        )

    def tearDown(
        self,
    ):
        self.temp.cleanup()

    @staticmethod
    def dataset():
        return {
            "id": "sft-compiled-gate-test",
            "state": "compiled-local",
            "training_format": "sft",
            "integrity": True,
            "train_count": 80,
            "eval_count": 20,
            "train_sha256": "a" * 64,
            "eval_sha256": "b" * 64,
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

    def request(
        self,
        dataset=None,
        hardware=None,
    ):
        return (
            self.gate
            .request_dry_run(
                dataset
                or self.dataset(),
                observed_hardware=(
                    hardware
                    or self.capable_hardware()
                ),
            )
        )

    def test_review_uses_dany_and_never_executes_training(
        self,
    ):
        review = (
            self.gate
            .review(
                self.dataset(),
                observed_hardware=(
                    self.capable_hardware()
                ),
            )
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
                "score"
            ],
        )

        self.assertFalse(
            review[
                "training_started"
            ]
        )

        self.assertFalse(
            review[
                "litgpt_invoked"
            ]
        )

        self.assertFalse(
            review[
                "weights_modified"
            ]
        )

    def test_request_requires_cyber_medium_write_approval(
        self,
    ):
        request = self.request()

        approval = request[
            "approval"
        ]

        self.assertEqual(
            "approval-required",
            request[
                "state"
            ],
        )

        self.assertEqual(
            TRAINING_DRY_RUN_TOOL,
            approval[
                "tool"
            ],
        )

        self.assertEqual(
            TRAINING_DRY_RUN_EFFECT,
            approval[
                "effect"
            ],
        )

        self.assertEqual(
            "medium",
            approval[
                "risk"
            ],
        )

        self.assertEqual(
            "pending",
            approval[
                "status"
            ],
        )

        self.assertEqual(
            [],
            list(
                (
                    self.root
                    / "dry-runs"
                )
                .glob(
                    "*/manifest.json"
                )
            ),
        )

    def test_approved_dry_run_materializes_safe_manifest(
        self,
    ):
        request = self.request()

        approval_id = request[
            "approval"
        ][
            "id"
        ]

        self.approvals.decide(
            approval_id,
            True,
        )

        result = (
            self.gate
            .materialize_dry_run(
                self.dataset(),
                approval_id,
                observed_hardware=(
                    self.capable_hardware()
                ),
            )
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

        verification = (
            self.gate
            .verify_manifest(
                result[
                    "run_id"
                ]
            )
        )

        self.assertTrue(
            verification[
                "integrity"
            ]
        )

        self.assertTrue(
            verification[
                "safe_execution"
            ]
        )

    def test_argument_tampering_is_rejected(
        self,
    ):
        request = self.request()

        approval_id = request[
            "approval"
        ][
            "id"
        ]

        self.approvals.decide(
            approval_id,
            True,
        )

        changed = self.dataset()

        changed[
            "train_sha256"
        ] = "c" * 64

        with self.assertRaises(
            ApprovalError
        ):
            self.gate.materialize_dry_run(
                changed,
                approval_id,
                observed_hardware=(
                    self.capable_hardware()
                ),
            )

        manifests = list(
            (
                self.root
                / "dry-runs"
            )
            .glob(
                "*/manifest.json"
            )
        )

        self.assertEqual(
            [],
            manifests,
        )

    def test_denied_approval_cannot_materialize(
        self,
    ):
        request = self.request()

        approval_id = request[
            "approval"
        ][
            "id"
        ]

        self.approvals.decide(
            approval_id,
            False,
        )

        with self.assertRaises(
            ApprovalError
        ):
            self.gate.materialize_dry_run(
                self.dataset(),
                approval_id,
                observed_hardware=(
                    self.capable_hardware()
                ),
            )

    def test_approval_is_single_use(
        self,
    ):
        request = self.request()

        approval_id = request[
            "approval"
        ][
            "id"
        ]

        self.approvals.decide(
            approval_id,
            True,
        )

        result = (
            self.gate
            .materialize_dry_run(
                self.dataset(),
                approval_id,
                observed_hardware=(
                    self.capable_hardware()
                ),
            )
        )

        second_gate = (
            TrainingExecutionGate(
                planner=self.planner,
                approvals=self.approvals,
                evaluator=DanyEvaluator(),
                cyber=CyberPolicy(),
                root=(
                    self.root
                    / "second-dry-runs"
                ),
            )
        )

        with self.assertRaises(
            ApprovalError
        ):
            second_gate.materialize_dry_run(
                self.dataset(),
                approval_id,
                observed_hardware=(
                    self.capable_hardware()
                ),
            )

        self.assertEqual(
            "dry-run-materialized",
            result[
                "state"
            ],
        )

    def test_current_hardware_remains_blocked_but_dry_run_reviewable(
        self,
    ):
        review = (
            self.gate
            .review(
                self.dataset()
            )
        )

        plan = review[
            "plan"
        ]

        self.assertEqual(
            "planned-blocked",
            plan[
                "state"
            ],
        )

        self.assertFalse(
            plan[
                "execution_allowed"
            ]
        )

        self.assertIn(
            "nvidia-cuda-required",
            plan[
                "blockers"
            ],
        )

        self.assertTrue(
            review[
                "dany"
            ][
                "accepted"
            ]
        )

    def test_gate_exposes_no_training_executor(
        self,
    ):
        self.assertFalse(
            hasattr(
                self.gate,
                "execute_training",
            )
        )

        status = (
            self.gate
            .status()
        )

        self.assertFalse(
            status[
                "training_execution_enabled"
            ]
        )

        self.assertFalse(
            status[
                "automatic_training"
            ]
        )

        self.assertFalse(
            status[
                "weights_modified"
            ]
        )


if __name__ == "__main__":
    unittest.main()