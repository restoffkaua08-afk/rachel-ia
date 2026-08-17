from __future__ import annotations

import json
import unittest

from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

POLICY = (
    ROOT
    / "RACHEL_EVALUATION"
    / "CONFIG"
    / "evaluation-promotion-policy.json"
)


class EvaluationPromotionPolicyTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(
        cls,
    ):
        cls.policy = json.loads(
            POLICY.read_text(
                encoding="utf-8-sig"
            )
        )

    def test_owner_is_dany(
        self,
    ):
        self.assertEqual(
            "dany",
            self.policy[
                "owner"
            ],
        )

    def test_promptfoo_and_dspy_are_declared(
        self,
    ):
        organs = self.policy[
            "organs"
        ]

        self.assertIn(
            "promptfoo",
            organs,
        )

        self.assertIn(
            "dspy",
            organs,
        )

    def test_temporary_runtime_is_not_promotable_as_rachel(
        self,
    ):
        temporary = self.policy[
            "subjects"
        ][
            "temporary_runtime"
        ]

        self.assertEqual(
            "qwen3:1.7b",
            temporary[
                "id"
            ],
        )

        self.assertFalse(
            temporary[
                "promotable_as_rachel_model"
            ]
        )

    def test_rachel_model_candidate_does_not_exist_yet(
        self,
    ):
        candidate = self.policy[
            "subjects"
        ][
            "rachel_model"
        ]

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
                "candidate_available"
            ]
        )

    def test_thresholds_are_not_invented(
        self,
    ):
        promotion = self.policy[
            "promotion_policy"
        ]

        self.assertEqual(
            "not-calibrated",
            promotion[
                "thresholds_state"
            ],
        )

        self.assertFalse(
            promotion[
                "numeric_thresholds_defined"
            ]
        )

    def test_promotion_is_blocked(
        self,
    ):
        promotion = self.policy[
            "promotion_policy"
        ]

        self.assertEqual(
            "blocked",
            promotion[
                "state"
            ],
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

    def test_dany_and_cyber_boundaries(
        self,
    ):
        promotion = self.policy[
            "promotion_policy"
        ]

        self.assertTrue(
            promotion[
                "dany_approval_required"
            ]
        )

        self.assertTrue(
            promotion[
                "cyber_required_for_external_publish"
            ]
        )

    def test_all_execution_is_disabled(
        self,
    ):
        execution = self.policy[
            "execution"
        ]

        for key in (
            "evaluation_execution_enabled",
            "promptfoo_invocation_enabled",
            "dspy_optimization_enabled",
            "model_generation_enabled",
            "report_write_enabled",
            "promotion_execution_enabled",
            "external_publish_enabled",
            "training_execution_enabled",
            "weights_modified",
        ):
            self.assertFalse(
                execution[
                    key
                ],
                msg=key,
            )


if __name__ == "__main__":
    unittest.main()
