from __future__ import annotations

import json
import sys
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


from evaluation_runtime import (
    EvaluationRuntime,
)


class EvaluationDecisionContractTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(
        cls,
    ):

        cls.report = json.loads(
            (
                CONFIG
                / "evaluation-report-contract.json"
            ).read_text(
                encoding="utf-8-sig"
            )
        )

        cls.regression = json.loads(
            (
                CONFIG
                / "regression-comparison-contract.json"
            ).read_text(
                encoding="utf-8-sig"
            )
        )

        cls.decision = json.loads(
            (
                CONFIG
                / "promotion-decision-contract.json"
            ).read_text(
                encoding="utf-8-sig"
            )
        )

    def test_all_contracts_owned_by_dany(
        self,
    ):

        for contract in (
            self.report,
            self.regression,
            self.decision,
        ):
            self.assertEqual(
                "dany",
                contract[
                    "owner"
                ],
            )

    def test_report_contract_does_not_fabricate_results(
        self,
    ):

        results = self.report[
            "results"
        ]

        self.assertEqual(
            "not-produced",
            results[
                "state"
            ],
        )

        self.assertFalse(
            results[
                "metrics_available"
            ]
        )

        self.assertFalse(
            results[
                "numeric_scores_available"
            ]
        )

        self.assertFalse(
            results[
                "synthetic_results_allowed"
            ]
        )

        self.assertFalse(
            results[
                "fabricated_scores_allowed"
            ]
        )

    def test_report_write_disabled(
        self,
    ):

        self.assertFalse(
            self.report[
                "storage"
            ][
                "write_enabled"
            ]
        )

        self.assertFalse(
            self.report[
                "execution"
            ][
                "report_write_enabled"
            ]
        )

    def test_regression_requires_equivalent_evidence(
        self,
    ):

        comparability = (
            self.regression[
                "comparability"
            ]
        )

        for key in (
            "same_suite_registry_required",
            "same_input_set_required",
            "same_evaluator_version_required",
            "same_metric_definitions_required",
            "incomparable_results_must_block",
        ):
            self.assertTrue(
                comparability[
                    key
                ],
                msg=key,
            )

    def test_regression_thresholds_not_calibrated(
        self,
    ):

        thresholds = (
            self.regression[
                "thresholds"
            ]
        )

        self.assertEqual(
            "not-calibrated",
            thresholds[
                "state"
            ],
        )

        self.assertFalse(
            thresholds[
                "numeric_thresholds_defined"
            ]
        )

        self.assertIsNone(
            thresholds[
                "values"
            ]
        )

    def test_regression_not_computed(
        self,
    ):

        result = (
            self.regression[
                "result"
            ]
        )

        self.assertEqual(
            "not-computed",
            result[
                "state"
            ],
        )

        self.assertFalse(
            result[
                "comparison_available"
            ]
        )

        self.assertFalse(
            result[
                "pass_fail_available"
            ]
        )

    def test_decision_is_separate_from_execution(
        self,
    ):

        separation = (
            self.decision[
                "separation_of_concerns"
            ]
        )

        self.assertFalse(
            separation[
                "training_implies_promotion"
            ]
        )

        self.assertFalse(
            separation[
                "evaluation_implies_promotion"
            ]
        )

        self.assertFalse(
            separation[
                "eligibility_implies_execution"
            ]
        )

        self.assertTrue(
            separation[
                "decision_is_not_execution"
            ]
        )

    def test_promotion_decision_not_recorded(
        self,
    ):

        decision = (
            self.decision[
                "decision"
            ]
        )

        self.assertEqual(
            "not-decided",
            decision[
                "state"
            ],
        )

        self.assertIsNone(
            decision[
                "current_decision"
            ]
        )

        self.assertFalse(
            decision[
                "automatic_decision"
            ]
        )

        self.assertFalse(
            decision[
                "decision_recording_enabled"
            ]
        )

    def test_promotion_stays_blocked(
        self,
    ):

        promotion = (
            self.decision[
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
                "automatic_promotion"
            ]
        )

        self.assertFalse(
            promotion[
                "promotion_execution_enabled"
            ]
        )

    def test_runtime_exposes_contracts_read_only(
        self,
    ):

        status = (
            EvaluationRuntime()
            .status()
        )

        contracts = (
            status[
                "decision_contracts"
            ]
        )

        self.assertEqual(
            "dany",
            contracts[
                "owner"
            ],
        )

        self.assertEqual(
            "not-produced",
            contracts[
                "report"
            ][
                "result_state"
            ],
        )

        self.assertEqual(
            "not-computed",
            contracts[
                "regression"
            ][
                "result_state"
            ],
        )

        self.assertEqual(
            "not-decided",
            contracts[
                "promotion_decision"
            ][
                "decision_state"
            ],
        )

        self.assertTrue(
            contracts[
                "read_only"
            ]
        )

        self.assertFalse(
            contracts[
                "execution_enabled"
            ]
        )

        self.assertFalse(
            contracts[
                "report_written"
            ]
        )

        self.assertFalse(
            contracts[
                "comparison_computed"
            ]
        )

        self.assertFalse(
            contracts[
                "decision_recorded"
            ]
        )

        self.assertFalse(
            contracts[
                "promotion_executed"
            ]
        )

        self.assertFalse(
            contracts[
                "training_execution_enabled"
            ]
        )

        self.assertFalse(
            contracts[
                "weights_modified"
            ]
        )

    def test_new_execution_capabilities_disabled(
        self,
    ):

        capabilities = (
            EvaluationRuntime()
            .status()[
                "capabilities"
            ]
        )

        self.assertTrue(
            capabilities[
                "read_report_contract"
            ]
        )

        self.assertTrue(
            capabilities[
                "read_regression_contract"
            ]
        )

        self.assertTrue(
            capabilities[
                "read_promotion_decision_contract"
            ]
        )

        self.assertFalse(
            capabilities[
                "write_report"
            ]
        )

        self.assertFalse(
            capabilities[
                "compute_regression"
            ]
        )

        self.assertFalse(
            capabilities[
                "record_promotion_decision"
            ]
        )

        self.assertFalse(
            capabilities[
                "promote_model"
            ]
        )

        self.assertFalse(
            capabilities[
                "train_model"
            ]
        )


if __name__ == "__main__":
    unittest.main()
