from __future__ import annotations

import json
import unittest

from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

CONFIG = (
    ROOT
    / "RACHEL_EVALUATION"
    / "CONFIG"
)


class EvaluationManifestTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(
        cls,
    ):

        cls.baseline = json.loads(
            (
                CONFIG
                / "evaluation-baseline.json"
            ).read_text(
                encoding="utf-8-sig"
            )
        )

        cls.candidate = json.loads(
            (
                CONFIG
                / "evaluation-candidate.json"
            ).read_text(
                encoding="utf-8-sig"
            )
        )

    def test_baseline_identity(
        self,
    ):

        self.assertEqual(
            "qwen3:1.7b",
            self.baseline[
                "subject_id"
            ],
        )

        self.assertEqual(
            "temporary-baseline",
            self.baseline[
                "subject_type"
            ],
        )

        self.assertFalse(
            self.baseline[
                "promotable_as_rachel_model"
            ]
        )

    def test_baseline_not_evaluated(
        self,
    ):

        self.assertFalse(
            self.baseline[
                "metrics_available"
            ]
        )

        self.assertIsNone(
            self.baseline[
                "metrics"
            ]
        )

        self.assertFalse(
            self.baseline[
                "suite_results_available"
            ]
        )

    def test_candidate_identity(
        self,
    ):

        self.assertEqual(
            "rachel-model-v0.1",
            self.candidate[
                "model_id"
            ],
        )

        self.assertEqual(
            "Qwen/Qwen3-1.7B-Base",
            self.candidate[
                "base_repository"
            ],
        )

    def test_candidate_checkpoint_absent(
        self,
    ):

        checkpoint = (
            self.candidate[
                "checkpoint"
            ]
        )

        self.assertEqual(
            "not-created",
            checkpoint[
                "state"
            ],
        )

        self.assertIsNone(
            checkpoint[
                "checkpoint_id"
            ]
        )

        self.assertFalse(
            checkpoint[
                "verified"
            ]
        )

    def test_training_not_executed(
        self,
    ):

        training = (
            self.candidate[
                "training"
            ]
        )

        self.assertEqual(
            "not-executed",
            training[
                "state"
            ],
        )

        self.assertFalse(
            training[
                "execution_enabled"
            ]
        )

        self.assertFalse(
            training[
                "weights_modified"
            ]
        )

    def test_promotion_blocked(
        self,
    ):

        promotion = (
            self.candidate[
                "promotion"
            ]
        )

        self.assertEqual(
            "blocked",
            promotion[
                "state"
            ],
        )

        self.assertFalse(
            promotion[
                "eligible"
            ]
        )

        self.assertFalse(
            promotion[
                "execution_enabled"
            ]
        )


if __name__ == "__main__":
    unittest.main()
