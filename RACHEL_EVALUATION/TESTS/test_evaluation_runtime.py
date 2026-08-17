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
    EvaluationRuntimeError,
)


class EvaluationRuntimeTests(
    unittest.TestCase
):

    def service(
        self,
    ) -> EvaluationRuntime:

        return EvaluationRuntime()

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
                "member"
            ][
                "id"
            ],
        )

    def test_registry_has_all_policy_layers(
        self,
    ):

        service = self.service()

        policy_ids = {
            item[
                "id"
            ]
            for item
            in service.policy[
                "evaluation_layers"
            ]
        }

        suite_ids = {
            item[
                "id"
            ]
            for item
            in service.registry[
                "suites"
            ]
        }

        self.assertEqual(
            policy_ids,
            suite_ids,
        )

        self.assertEqual(
            7,
            len(
                suite_ids
            ),
        )

    def test_contract_integrity_is_static_and_read_only(
        self,
    ):

        suite = (
            self.service()
            .suite(
                "contract-integrity"
            )
        )

        self.assertEqual(
            "internal-static",
            suite[
                "runner"
            ],
        )

        self.assertFalse(
            suite[
                "requires_model_execution"
            ]
        )

        self.assertFalse(
            suite[
                "execution_enabled"
            ]
        )

    def test_promptfoo_suites_remain_disabled(
        self,
    ):

        suites = (
            self.service()
            .registry[
                "suites"
            ]
        )

        promptfoo = [
            item
            for item
            in suites
            if item[
                "runner"
            ]
            == "promptfoo"
        ]

        self.assertGreater(
            len(
                promptfoo
            ),
            0,
        )

        for suite in promptfoo:

            self.assertTrue(
                suite[
                    "requires_promptfoo"
                ]
            )

            self.assertFalse(
                suite[
                    "execution_enabled"
                ]
            )

    def test_dspy_is_declared_but_never_invoked(
        self,
    ):

        service = self.service()

        self.assertFalse(
            service.registry[
                "dspy"
            ][
                "invocation_enabled"
            ]
        )

        self.assertFalse(
            service.registry[
                "dspy"
            ][
                "automatic_optimization"
            ]
        )

    def test_thresholds_are_not_defined(
        self,
    ):

        service = self.service()

        for suite in service.registry[
            "suites"
        ]:
            self.assertIsNone(
                suite[
                    "thresholds"
                ]
            )

        self.assertEqual(
            "not-calibrated",
            service.policy[
                "promotion_policy"
            ][
                "thresholds_state"
            ],
        )

    def test_baseline_is_not_rachel_model(
        self,
    ):

        baseline = (
            self.service()
            .status()[
                "temporary_baseline"
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
                "promotable_as_rachel_model"
            ]
        )

    def test_candidate_is_not_available(
        self,
    ):

        candidate = (
            self.service()
            .status()[
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

    def test_promotion_is_blocked(
        self,
    ):

        promotion = (
            self.service()
            .promotion_eligibility()
        )

        self.assertFalse(
            promotion[
                "eligible"
            ]
        )

        self.assertEqual(
            "blocked",
            promotion[
                "state"
            ],
        )

        for blocker in (
            "candidate-checkpoint-not-created",
            "candidate-unavailable",
            "thresholds-not-calibrated",
            "promotion-execution-disabled",
        ):
            self.assertIn(
                blocker,
                promotion[
                    "blockers"
                ],
            )

    def test_runtime_is_read_only(
        self,
    ):

        status = (
            self.service()
            .status()
        )

        self.assertTrue(
            status[
                "read_only"
            ]
        )

        self.assertFalse(
            status[
                "filesystem_mutation"
            ]
        )

        self.assertFalse(
            status[
                "model_execution"
            ]
        )

        self.assertFalse(
            status[
                "report_written"
            ]
        )

        self.assertFalse(
            status[
                "promotion_executed"
            ]
        )

        self.assertFalse(
            status[
                "training_execution_enabled"
            ]
        )

        self.assertFalse(
            status[
                "weights_modified"
            ]
        )

    def test_execution_capabilities_are_disabled(
        self,
    ):

        capabilities = (
            self.service()
            .status()[
                "capabilities"
            ]
        )

        for key in (
            "execute_suite",
            "execute_model",
            "invoke_promptfoo",
            "invoke_dspy",
            "write_report",
            "promote_model",
            "train_model",
        ):
            self.assertFalse(
                capabilities[
                    key
                ],
                msg=key,
            )

    def test_unknown_suite_is_rejected(
        self,
    ):

        with self.assertRaises(
            EvaluationRuntimeError
        ):
            self.service().suite(
                "suite-inexistente"
            )

    def test_no_execution_methods_exist(
        self,
    ):

        service = self.service()

        for method in (
            "run",
            "execute",
            "evaluate",
            "invoke_promptfoo",
            "invoke_dspy",
            "write_report",
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
