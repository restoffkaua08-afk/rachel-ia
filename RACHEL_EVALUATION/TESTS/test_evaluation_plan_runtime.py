from __future__ import annotations

import sys
import unittest

from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

RUNTIME = (
    ROOT
    / "RACHEL_PLATFORM"
    / "RUNTIME"
    / "SRC"
)

if str(RUNTIME) not in sys.path:
    sys.path.insert(
        0,
        str(RUNTIME),
    )


from evaluation_plan_runtime import (
    EvaluationPlanRuntime,
)


class EvaluationPlanRuntimeTests(
    unittest.TestCase
):

    def service(
        self,
    ) -> EvaluationPlanRuntime:

        return EvaluationPlanRuntime()

    def test_owner_is_dany(
        self,
    ):

        status = (
            self.service()
            .status()
        )

        self.assertEqual(
            "dany",
            status[
                "owner"
            ],
        )

    def test_four_phases_exist(
        self,
    ):

        preview = (
            self.service()
            .preview()
        )

        self.assertEqual(
            4,
            preview[
                "phase_count"
            ],
        )

        ids = {
            item[
                "id"
            ]
            for item
            in preview[
                "phases"
            ]
        }

        self.assertEqual(
            {
                "baseline-evaluation",
                "candidate-evaluation",
                "regression-comparison",
                "promotion-decision",
            },
            ids,
        )

    def test_baseline_is_blocked(
        self,
    ):

        plan = (
            self.service()
            .baseline_plan()
        )

        self.assertFalse(
            plan[
                "ready"
            ]
        )

        for blocker in (
            "baseline-not-evaluated",
            "suite-execution-disabled",
            "model-execution-disabled",
            "promptfoo-invocation-disabled",
            "report-write-disabled",
        ):
            self.assertIn(
                blocker,
                plan[
                    "blockers"
                ],
            )

    def test_candidate_is_blocked(
        self,
    ):

        plan = (
            self.service()
            .candidate_plan()
        )

        self.assertFalse(
            plan[
                "ready"
            ]
        )

        for blocker in (
            "candidate-checkpoint-not-created",
            "candidate-checkpoint-unverified",
            "candidate-unavailable",
            "candidate-not-evaluated",
            "suite-execution-disabled",
            "model-execution-disabled",
            "promptfoo-invocation-disabled",
            "report-write-disabled",
        ):
            self.assertIn(
                blocker,
                plan[
                    "blockers"
                ],
            )

    def test_regression_is_blocked(
        self,
    ):

        plan = (
            self.service()
            .regression_plan()
        )

        self.assertFalse(
            plan[
                "ready"
            ]
        )

        for blocker in (
            "baseline-evaluation-report-unavailable",
            "candidate-evaluation-report-unavailable",
            "regression-comparison-unavailable",
            "thresholds-not-calibrated",
            "comparison-execution-disabled",
        ):
            self.assertIn(
                blocker,
                plan[
                    "blockers"
                ],
            )

    def test_promotion_is_blocked(
        self,
    ):

        plan = (
            self.service()
            .promotion_plan()
        )

        self.assertFalse(
            plan[
                "ready"
            ]
        )

        for blocker in (
            "candidate-checkpoint-not-created",
            "candidate-checkpoint-unverified",
            "candidate-unavailable",
            "candidate-evaluation-results-unavailable",
            "regression-comparison-unavailable",
            "thresholds-not-calibrated",
            "decision-recording-disabled",
            "promotion-execution-disabled",
        ):
            self.assertIn(
                blocker,
                plan[
                    "blockers"
                ],
            )

    def test_no_phase_is_ready(
        self,
    ):

        preview = (
            self.service()
            .preview()
        )

        self.assertFalse(
            preview[
                "ready"
            ]
        )

        self.assertEqual(
            0,
            preview[
                "ready_phase_count"
            ],
        )

        self.assertEqual(
            4,
            preview[
                "blocked_phase_count"
            ],
        )

    def test_thresholds_remain_uncalibrated(
        self,
    ):

        preview = (
            self.service()
            .preview()
        )

        self.assertEqual(
            "not-calibrated",
            preview[
                "thresholds_state"
            ],
        )

        self.assertFalse(
            preview[
                "numeric_thresholds_defined"
            ]
        )

    def test_plan_is_read_only(
        self,
    ):

        preview = (
            self.service()
            .preview()
        )

        self.assertTrue(
            preview[
                "read_only"
            ]
        )

        self.assertFalse(
            preview[
                "plan_is_execution"
            ]
        )

        self.assertFalse(
            preview[
                "authorization_granted"
            ]
        )

        self.assertFalse(
            preview[
                "evaluation_executed"
            ]
        )

        self.assertFalse(
            preview[
                "report_generated"
            ]
        )

        self.assertFalse(
            preview[
                "comparison_computed"
            ]
        )

        self.assertFalse(
            preview[
                "decision_recorded"
            ]
        )

        self.assertFalse(
            preview[
                "promotion_executed"
            ]
        )

        self.assertFalse(
            preview[
                "training_execution_enabled"
            ]
        )

        self.assertFalse(
            preview[
                "weights_modified"
            ]
        )

    def test_no_execution_methods_exist(
        self,
    ):

        service = self.service()

        for method in (
            "run",
            "execute",
            "evaluate",
            "generate_report",
            "compare",
            "record_decision",
            "promote",
            "train",
        ):
            self.assertFalse(
                hasattr(
                    service,
                    method,
                ),
                msg=method,
            )


if __name__ == "__main__":
    unittest.main()
