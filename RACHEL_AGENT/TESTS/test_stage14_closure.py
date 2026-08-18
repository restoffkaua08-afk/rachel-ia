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


from agent_runtime import AgentRuntime


FINAL_FROZEN = (
    ROOT
    / "RACHEL_AGENT"
    / "REPORTS"
    / "stage-14-final-frozen-validation.json"
)

CLOSURE = (
    ROOT
    / "RACHEL_AGENT"
    / "REPORTS"
    / "stage-14-closure.json"
)

DESKTOP = (
    ROOT
    / "RACHEL_AGENT"
    / "CONFIG"
    / "agent-desktop-bridge.json"
)


class Stage14ClosureTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(
        cls,
    ):

        cls.frozen = json.loads(
            FINAL_FROZEN.read_text(
                encoding="utf-8-sig"
            )
        )

        cls.closure = json.loads(
            CLOSURE.read_text(
                encoding="utf-8-sig"
            )
        )

        cls.desktop = json.loads(
            DESKTOP.read_text(
                encoding="utf-8-sig"
            )
        )

        cls.agent = AgentRuntime(
            root=ROOT
        )

    def test_closure_identity(
        self,
    ):

        self.assertEqual(
            14,
            self.closure[
                "stage"
            ],
        )

        self.assertEqual(
            "rachel",
            self.closure[
                "owner"
            ],
        )

        self.assertEqual(
            "technically-closed-execution-disabled",
            self.closure[
                "state"
            ],
        )

        self.assertTrue(
            self.closure[
                "technical_completion"
            ]
        )

        self.assertFalse(
            self.closure[
                "execution_activation"
            ]
        )

    def test_final_frozen_identity(
        self,
    ):

        self.assertEqual(
            "validated",
            self.frozen[
                "state"
            ],
        )

        self.assertEqual(
            (
                "f4d5e4cd7944c2367e3f4fb017de5d9f9d53f60c"
            ),
            self.frozen[
                "runtime_source_commit"
            ],
        )

        self.assertEqual(
            (
                "D386A244E70C75F2486BCD0FC8406249431677BA870084E1073B4223FC5A655D"
            ),
            self.frozen[
                "portable_runtime"
            ][
                "sha256"
            ],
        )

        self.assertFalse(
            self.frozen[
                "portable_runtime"
            ][
                "historical_sha_reused"
            ]
        )

        self.assertTrue(
            self.frozen[
                "portable_runtime"
            ][
                "self_contained"
            ]
        )

    def test_final_bundle(
        self,
    ):

        bundle = (
            self.frozen[
                "bundle"
            ]
        )

        self.assertEqual(
            4,
            bundle[
                "required_config_count"
            ],
        )

        self.assertEqual(
            4,
            bundle[
                "required_config_available"
            ],
        )

        self.assertTrue(
            bundle[
                "agent_runtime_policy"
            ]
        )

        self.assertTrue(
            bundle[
                "agent_desktop_bridge"
            ]
        )

        self.assertTrue(
            bundle[
                "autonomy_budget_policy"
            ]
        )

        self.assertTrue(
            bundle[
                "execution_envelope_policy"
            ]
        )

    def test_agent_read_surface(
        self,
    ):

        agent = (
            self.frozen[
                "agent"
            ]
        )

        self.assertEqual(
            7,
            agent[
                "read_actions"
            ],
        )

        self.assertEqual(
            0,
            agent[
                "read_action_mutations"
            ],
        )

        self.assertEqual(
            0,
            agent[
                "execution_actions"
            ],
        )

        self.assertEqual(
            9,
            agent[
                "forbidden_actions_tested"
            ],
        )

        self.assertEqual(
            0,
            agent[
                "forbidden_actions_accepted"
            ],
        )

    def test_desktop_contract_has_seven_reads(
        self,
    ):

        self.assertEqual(
            7,
            len(
                self.desktop[
                    "bridge"
                ][
                    "read_actions"
                ]
            ),
        )

        self.assertEqual(
            [],
            self.desktop[
                "bridge"
            ][
                "execution_actions"
            ],
        )

    def test_budget_contract_remains_non_executable(
        self,
    ):

        budgets = (
            self.agent
            .budgets()
        )

        self.assertTrue(
            budgets[
                "contract_ready"
            ]
        )

        self.assertEqual(
            4,
            budgets[
                "dimension_count"
            ],
        )

        self.assertFalse(
            budgets[
                "defaults_allowed"
            ]
        )

        self.assertFalse(
            budgets[
                "goal_budget_resolved"
            ]
        )

        self.assertFalse(
            budgets[
                "goal_budget_materialized"
            ]
        )

        self.assertFalse(
            budgets[
                "execution_enabled"
            ]
        )

    def test_execution_envelope_remains_disabled(
        self,
    ):

        envelope = (
            self.agent
            .execution_envelope()
        )

        self.assertTrue(
            envelope[
                "contract_ready"
            ]
        )

        self.assertEqual(
            "maximum_steps",
            envelope[
                "existing_limit_parameter"
            ],
        )

        self.assertEqual(
            1,
            envelope[
                "maximum_completed_steps_per_slice"
            ],
        )

        self.assertFalse(
            envelope[
                "automatic_continue"
            ]
        )

        self.assertFalse(
            envelope[
                "automatic_retry"
            ]
        )

        self.assertFalse(
            envelope[
                "automatic_replan"
            ]
        )

        self.assertFalse(
            envelope[
                "execution_enabled"
            ]
        )

    def test_readiness_is_intentionally_blocked(
        self,
    ):

        readiness = (
            self.agent
            .readiness()
        )

        self.assertFalse(
            readiness[
                "ready"
            ]
        )

        self.assertEqual(
            5,
            readiness[
                "phase_count"
            ],
        )

        self.assertEqual(
            4,
            readiness[
                "ready_phase_count"
            ],
        )

        self.assertEqual(
            1,
            readiness[
                "blocked_phase_count"
            ],
        )

        self.assertEqual(
            5,
            readiness[
                "blocker_count"
            ],
        )

    def test_remaining_blockers_are_execution_only(
        self,
    ):

        self.assertEqual(
            {
                "agent-loop-execution-disabled",
                "agent-runtime-execution-disabled",
                "goal-decomposition-disabled",
                "task-execution-by-agent-disabled",
                "tool-execution-by-agent-disabled",
            },
            set(
                self.agent
                .blockers()
            ),
        )

    def test_agent_execution_stays_off(
        self,
    ):

        status = (
            self.agent
            .status()
        )

        for key in (
            "goal_execution",
            "task_execution",
            "tool_execution",
            "approval_creation",
            "approval_consumption",
            "browser_execution",
            "background_execution",
            "unattended_execution",
            "external_effect",
            "self_modification",
            "training_execution",
            "weights_modified",
        ):

            self.assertFalse(
                status[
                    key
                ],
                msg=key,
            )

    def test_closure_does_not_mutate_frozen_payload(
        self,
    ):

        evidence = (
            self.frozen[
                "evidence_policy"
            ]
        )

        self.assertFalse(
            evidence[
                "post_build_closure_files_bundled"
            ]
        )

        self.assertFalse(
            evidence[
                "runtime_or_bundle_mutated_after_final_build"
            ]
        )

        self.assertTrue(
            evidence[
                "final_frozen_sha_remains_authoritative"
            ]
        )

    def test_next_step_is_publication_only(
        self,
    ):

        next_step = (
            self.closure[
                "next"
            ]
        )

        self.assertEqual(
            "14/1I",
            next_step[
                "step"
            ],
        )

        self.assertIn(
            "publish",
            next_step[
                "goal"
            ].lower(),
        )


if __name__ == "__main__":
    unittest.main()
