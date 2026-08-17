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
    / "RACHEL_AGENT"
    / "CONFIG"
    / "agent-runtime-policy.json"
)


class AgentRuntimePolicyTests(
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
            1,
            self.policy[
                "schema_version"
            ],
        )

        self.assertEqual(
            14,
            self.policy[
                "stage"
            ],
        )

        self.assertEqual(
            "rachel",
            self.policy[
                "owner"
            ],
        )

        self.assertEqual(
            "contract-defined-execution-disabled",
            self.policy[
                "state"
            ],
        )

    def test_reuses_existing_task_runtime(
        self,
    ):

        architecture = (
            self.policy[
                "architecture"
            ]
        )

        self.assertTrue(
            architecture[
                "reuse_existing_task_runtime"
            ]
        )

        self.assertFalse(
            architecture[
                "duplicate_task_executor"
            ]
        )

        self.assertFalse(
            architecture[
                "duplicate_cyber_authorization"
            ]
        )

        self.assertFalse(
            architecture[
                "duplicate_tool_coordinator"
            ]
        )

    def test_roles_are_separated(
        self,
    ):

        architecture = (
            self.policy[
                "architecture"
            ]
        )

        self.assertEqual(
            "rachel",
            architecture[
                "coordinator"
            ],
        )

        self.assertEqual(
            "ned",
            architecture[
                "planner"
            ],
        )

        self.assertEqual(
            "ned",
            architecture[
                "executor"
            ],
        )

        self.assertEqual(
            "arya",
            architecture[
                "tool_coordinator"
            ],
        )

        self.assertEqual(
            "cyber",
            architecture[
                "authorization"
            ],
        )

    def test_plan_before_execution(
        self,
    ):

        loop = (
            self.policy[
                "agent_loop"
            ]
        )

        self.assertTrue(
            loop[
                "plan_before_execution"
            ]
        )

        self.assertTrue(
            loop[
                "deterministic_plan_validation_required"
            ]
        )

        self.assertTrue(
            loop[
                "stepwise_execution_required"
            ]
        )

        self.assertFalse(
            loop[
                "execution_enabled"
            ]
        )

    def test_authority_is_deny_by_default(
        self,
    ):

        authority = (
            self.policy[
                "authority"
            ]
        )

        self.assertTrue(
            authority[
                "deny_by_default"
            ]
        )

        self.assertTrue(
            authority[
                "cyber_authorization_required"
            ]
        )

        self.assertTrue(
            authority[
                "approval_must_bind_to_effect"
            ]
        )

        self.assertTrue(
            authority[
                "approval_must_bind_to_step"
            ]
        )

        self.assertTrue(
            authority[
                "single_use_approval_required"
            ]
        )

    def test_no_approve_all_or_self_approval(
        self,
    ):

        authority = (
            self.policy[
                "authority"
            ]
        )

        self.assertFalse(
            authority[
                "global_approve_all_allowed"
            ]
        )

        self.assertFalse(
            authority[
                "boolean_approval_allowed"
            ]
        )

        self.assertFalse(
            authority[
                "self_approval_allowed"
            ]
        )

        self.assertFalse(
            authority[
                "approval_inheritance_allowed"
            ]
        )

        self.assertFalse(
            authority[
                "approval_reuse_allowed"
            ]
        )

    def test_unattended_autonomy_disabled(
        self,
    ):

        autonomy = (
            self.policy[
                "autonomy"
            ]
        )

        self.assertEqual(
            "contract-only",
            autonomy[
                "current_level"
            ],
        )

        for key in (
            "goal_decomposition_enabled",
            "autonomous_loop_enabled",
            "unattended_execution_enabled",
            "background_execution_enabled",
            "self_spawn_enabled",
            "self_replication_enabled",
            "self_modification_enabled",
            "self_update_enabled",
            "automatic_tool_installation_enabled",
            "automatic_permission_expansion_enabled",
            "automatic_external_publish_enabled",
            "automatic_credential_use_enabled",
        ):
            self.assertFalse(
                autonomy[
                    key
                ],
                msg=key,
            )

    def test_browser_not_integrated(
        self,
    ):

        browser = (
            self.policy[
                "browser"
            ]
        )

        self.assertEqual(
            "reserved-not-integrated",
            browser[
                "integration_state"
            ],
        )

        for key in (
            "navigation_execution_enabled",
            "form_submission_enabled",
            "download_execution_enabled",
            "session_mutation_enabled",
            "authenticated_action_enabled",
        ):
            self.assertFalse(
                browser[
                    key
                ],
                msg=key,
            )

    def test_budgets_are_not_invented(
        self,
    ):

        budgets = (
            self.policy[
                "budgets"
            ]
        )

        self.assertEqual(
            "contract-defined-explicit-per-goal",
            budgets[
                "state"
            ],
        )

        self.assertIsNone(
            budgets[
                "maximum_iterations"
            ]
        )

        self.assertIsNone(
            budgets[
                "maximum_tool_calls"
            ]
        )

        self.assertIsNone(
            budgets[
                "wall_clock_limit_seconds"
            ]
        )

        self.assertIsNone(
            budgets[
                "maximum_consecutive_failures"
            ]
        )

        self.assertFalse(
            budgets[
                "invent_defaults_allowed"
            ]
        )

    def test_effect_execution_disabled(
        self,
    ):

        self.assertFalse(
            self.policy[
                "effects"
            ][
                "effect_execution_enabled"
            ]
        )

    def test_all_stage_execution_disabled(
        self,
    ):

        execution = (
            self.policy[
                "execution"
            ]
        )

        for key, value in execution.items():

            self.assertFalse(
                value,
                msg=key,
            )

    def test_1a_is_contract_only(
        self,
    ):

        stage = (
            self.policy[
                "stage_14_1a"
            ]
        )

        self.assertTrue(
            stage[
                "contract_only"
            ]
        )

        for key in (
            "runtime_created",
            "desktop_bridge_integrated",
            "portable_runtime_integrated",
            "agent_execution_performed",
            "tool_effect_performed",
            "browser_effect_performed",
            "external_effect_performed",
        ):
            self.assertFalse(
                stage[
                    key
                ],
                msg=key,
            )


if __name__ == "__main__":
    unittest.main()
