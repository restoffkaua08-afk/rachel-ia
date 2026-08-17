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


class Stage13ClosureTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(
        cls,
    ):

        cls.closure = json.loads(
            (
                CONFIG
                / "stage-13-closure.json"
            ).read_text(
                encoding="utf-8-sig"
            )
        )

    def test_stage_identity(
        self,
    ):

        self.assertEqual(
            13,
            self.closure[
                "stage"
            ],
        )

        self.assertEqual(
            "technically-closed-pre-publication",
            self.closure[
                "state"
            ],
        )

    def test_evaluation_owner_and_suites(
        self,
    ):

        evaluation = (
            self.closure[
                "evaluation"
            ]
        )

        self.assertEqual(
            "dany",
            evaluation[
                "owner"
            ],
        )

        self.assertEqual(
            7,
            evaluation[
                "suite_count"
            ],
        )

        self.assertEqual(
            "read-only",
            evaluation[
                "runtime"
            ],
        )

    def test_baseline_remains_temporary(
        self,
    ):

        baseline = (
            self.closure[
                "baseline"
            ]
        )

        self.assertEqual(
            "qwen3:1.7b",
            baseline[
                "id"
            ],
        )

        self.assertFalse(
            baseline[
                "evaluated"
            ]
        )

        self.assertFalse(
            baseline[
                "promotable_as_rachel_model"
            ]
        )

    def test_candidate_does_not_exist_yet(
        self,
    ):

        candidate = (
            self.closure[
                "candidate"
            ]
        )

        self.assertEqual(
            "rachel-model-v0.1",
            candidate[
                "id"
            ],
        )

        self.assertEqual(
            "not-created",
            candidate[
                "checkpoint_state"
            ],
        )

        self.assertFalse(
            candidate[
                "available"
            ]
        )

        self.assertFalse(
            candidate[
                "evaluated"
            ]
        )

        self.assertFalse(
            candidate[
                "weights_modified"
            ]
        )

    def test_report_not_produced(
        self,
    ):

        report = (
            self.closure[
                "report"
            ]
        )

        self.assertEqual(
            "not-produced",
            report[
                "state"
            ],
        )

        self.assertFalse(
            report[
                "write_enabled"
            ]
        )

        self.assertFalse(
            report[
                "fabricated_scores_allowed"
            ]
        )

    def test_regression_not_computed(
        self,
    ):

        regression = (
            self.closure[
                "regression"
            ]
        )

        self.assertEqual(
            "not-computed",
            regression[
                "state"
            ],
        )

        self.assertEqual(
            "not-calibrated",
            regression[
                "thresholds_state"
            ],
        )

        self.assertFalse(
            regression[
                "numeric_thresholds_defined"
            ]
        )

    def test_promotion_stays_blocked(
        self,
    ):

        promotion = (
            self.closure[
                "promotion_decision"
            ]
        )

        self.assertEqual(
            "not-decided",
            promotion[
                "state"
            ],
        )

        self.assertEqual(
            "blocked",
            promotion[
                "promotion_state"
            ],
        )

        self.assertFalse(
            promotion[
                "automatic_decision"
            ]
        )

        self.assertFalse(
            promotion[
                "automatic_promotion"
            ]
        )

        self.assertFalse(
            promotion[
                "promotion_execution_enabled"
            ]
        )

    def test_plan_is_fully_blocked(
        self,
    ):

        plan = (
            self.closure[
                "evaluation_plan"
            ]
        )

        self.assertEqual(
            4,
            plan[
                "phase_count"
            ],
        )

        self.assertEqual(
            0,
            plan[
                "ready_phase_count"
            ],
        )

        self.assertEqual(
            4,
            plan[
                "blocked_phase_count"
            ],
        )

        self.assertEqual(
            17,
            plan[
                "global_blocker_count"
            ],
        )

        self.assertTrue(
            plan[
                "read_only"
            ]
        )

        self.assertFalse(
            plan[
                "authorization_granted"
            ]
        )

    def test_frozen_runtime_proof(
        self,
    ):

        frozen = (
            self.closure[
                "frozen_validation"
            ]
        )

        self.assertEqual(
            "validated",
            frozen[
                "state"
            ],
        )

        self.assertTrue(
            frozen[
                "portable_mode"
            ]
        )

        self.assertTrue(
            frozen[
                "evaluation_frozen"
            ]
        )

        self.assertTrue(
            frozen[
                "evaluation_plan_frozen"
            ]
        )

        self.assertTrue(
            frozen[
                "dashboard_frozen"
            ]
        )

        self.assertEqual(
            0,
            frozen[
                "evaluation_writes"
            ],
        )

    def test_all_execution_stays_disabled(
        self,
    ):

        execution = (
            self.closure[
                "execution"
            ]
        )

        for key, value in execution.items():

            self.assertFalse(
                value,
                msg=key,
            )

    def test_publication_not_done_yet(
        self,
    ):

        publication = (
            self.closure[
                "publication"
            ]
        )

        self.assertFalse(
            publication[
                "branch_push"
            ]
        )

        self.assertFalse(
            publication[
                "pull_request_created"
            ]
        )

        self.assertFalse(
            publication[
                "merged_to_main"
            ]
        )


if __name__ == "__main__":
    unittest.main()
