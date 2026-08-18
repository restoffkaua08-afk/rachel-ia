from __future__ import annotations

import json
import unittest

from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

POLICY = (
    ROOT
    / "RACHEL_PLATFORM"
    / "CONFIG"
    / "stage-15-system-readiness-policy.json"
)


class Stage15SystemReadinessContractTests(
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

    def test_identity(
        self,
    ):

        self.assertEqual(
            15,
            self.policy[
                "stage"
            ],
        )

        self.assertEqual(
            15,
            self.policy[
                "stage_count"
            ],
        )

        self.assertEqual(
            "rachel",
            self.policy[
                "owner"
            ],
        )

        self.assertEqual(
            "contract-defined-audit-pending",
            self.policy[
                "state"
            ],
        )

    def test_truthful_readiness(
        self,
    ):

        principles = (
            self.policy[
                "principles"
            ]
        )

        self.assertTrue(
            principles[
                "truthful_readiness"
            ]
        )

        self.assertTrue(
            principles[
                "no_false_ready"
            ]
        )

        self.assertTrue(
            principles[
                "evidence_required"
            ]
        )

        self.assertTrue(
            principles[
                "blocked_is_valid_state"
            ]
        )

        self.assertFalse(
            principles[
                "architecture_closure_is_not_capability_activation"
            ]
            is False
        )

    def test_classification_states(
        self,
    ):

        allowed = set(
            self.policy[
                "classification"
            ][
                "allowed_states"
            ]
        )

        self.assertEqual(
            {
                "ready",
                "blocked",
                "reserved",
                "deferred",
                "unavailable",
                "not-applicable",
            },
            allowed,
        )

        self.assertFalse(
            self.policy[
                "classification"
            ][
                "unknown_defaults_to_ready"
            ]
        )

    def test_twenty_audit_domains(
        self,
    ):

        domains = (
            self.policy[
                "audit_domains"
            ]
        )

        self.assertEqual(
            20,
            len(
                domains
            ),
        )

        self.assertEqual(
            20,
            len(
                {
                    item[
                        "id"
                    ]
                    for item
                    in domains
                }
            ),
        )

        for domain in domains:

            self.assertTrue(
                domain[
                    "required"
                ]
            )

    def test_known_agent_constraints(
        self,
    ):

        constraints = (
            self.policy[
                "known_constraints"
            ]
        )

        for key in (
            "agent_execution_enabled",
            "agent_goal_execution_enabled",
            "agent_task_execution_enabled",
            "agent_tool_execution_enabled",
            "browser_agent_integration_enabled",
            "background_agent_execution_enabled",
            "unattended_agent_execution_enabled",
            "self_modification_enabled",
        ):

            self.assertFalse(
                constraints[
                    key
                ],
                msg=key,
            )

    def test_training_and_model_constraints(
        self,
    ):

        constraints = (
            self.policy[
                "known_constraints"
            ]
        )

        self.assertFalse(
            constraints[
                "training_execution_enabled"
            ]
        )

        self.assertFalse(
            constraints[
                "training_runtime_provisioned"
            ]
        )

        self.assertFalse(
            constraints[
                "rachel_model_checkpoint_created"
            ]
        )

        self.assertFalse(
            constraints[
                "evaluation_promotion_decided"
            ]
        )

        self.assertFalse(
            constraints[
                "weights_modified"
            ]
        )

    def test_stage15_cannot_activate_capabilities(
        self,
    ):

        rules = (
            self.policy[
                "stage_15_rules"
            ]
        )

        for key, value in rules.items():

            self.assertFalse(
                value,
                msg=key,
            )

    def test_closure_does_not_require_fake_readiness(
        self,
    ):

        gate = (
            self.policy[
                "closure_gate"
            ]
        )

        self.assertFalse(
            gate[
                "all_capabilities_ready_required"
            ]
        )

        self.assertFalse(
            gate[
                "zero_blockers_required"
            ]
        )

        self.assertFalse(
            gate[
                "agent_execution_required"
            ]
        )

        self.assertFalse(
            gate[
                "training_required"
            ]
        )

        self.assertFalse(
            gate[
                "model_checkpoint_required"
            ]
        )

        self.assertFalse(
            gate[
                "browser_execution_required"
            ]
        )

    def test_initial_readiness_is_not_complete(
        self,
    ):

        readiness = (
            self.policy[
                "initial_readiness"
            ]
        )

        for value in readiness.values():

            self.assertFalse(
                value
            )

    def test_stage14_baseline(
        self,
    ):

        baseline = (
            self.policy[
                "stage_14_baseline"
            ]
        )

        self.assertEqual(
            (
                "57b52f8cd9061ff43c2f44411d55234cff6fa057"
            ),
            baseline[
                "merge_commit"
            ],
        )

        self.assertEqual(
            7,
            baseline[
                "agent_read_actions"
            ],
        )

        self.assertEqual(
            0,
            baseline[
                "agent_execution_actions"
            ],
        )

        self.assertEqual(
            4,
            baseline[
                "agent_readiness_ready_phases"
            ],
        )

        self.assertEqual(
            5,
            baseline[
                "agent_readiness_total_phases"
            ],
        )

        self.assertEqual(
            "blocked",
            baseline[
                "agent_execution_phase"
            ],
        )

    def test_next_step_is_inventory(
        self,
    ):

        self.assertEqual(
            "15/1B",
            self.policy[
                "next"
            ][
                "step"
            ],
        )

        self.assertIn(
            "inventory",
            self.policy[
                "next"
            ][
                "goal"
            ].lower(),
        )


if __name__ == "__main__":
    unittest.main()
