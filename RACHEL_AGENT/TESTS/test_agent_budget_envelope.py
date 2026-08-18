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


BUDGET = (
    ROOT
    / "RACHEL_AGENT"
    / "CONFIG"
    / "autonomy-budget-policy.json"
)

ENVELOPE = (
    ROOT
    / "RACHEL_AGENT"
    / "CONFIG"
    / "execution-envelope-policy.json"
)

FROZEN = (
    ROOT
    / "RACHEL_AGENT"
    / "CONFIG"
    / "stage-14-frozen-validation-1d.json"
)


class AgentBudgetEnvelopeTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(
        cls,
    ):

        cls.budget = json.loads(
            BUDGET.read_text(
                encoding="utf-8-sig"
            )
        )

        cls.envelope = json.loads(
            ENVELOPE.read_text(
                encoding="utf-8-sig"
            )
        )

        cls.frozen = json.loads(
            FROZEN.read_text(
                encoding="utf-8-sig"
            )
        )

        cls.agent = AgentRuntime(
            root=ROOT
        )

    def test_budget_contract_is_defined(
        self,
    ):

        self.assertEqual(
            "contract-defined",
            self.budget[
                "state"
            ],
        )

        self.assertEqual(
            "explicit-per-goal-no-default",
            self.budget[
                "strategy"
            ],
        )

        self.assertTrue(
            self.budget[
                "contract_ready"
            ]
        )

    def test_no_budget_defaults_exist(
        self,
    ):

        self.assertFalse(
            self.budget[
                "defaults_allowed"
            ]
        )

        self.assertFalse(
            self.budget[
                "goal_budget_resolved"
            ]
        )

        self.assertFalse(
            self.budget[
                "goal_budget_materialized"
            ]
        )

        dimensions = {
            item[
                "id"
            ]: item
            for item
            in self.budget[
                "dimensions"
            ]
        }

        self.assertEqual(
            {
                "maximum_iterations",
                "maximum_tool_calls",
                "wall_clock_limit_seconds",
                "maximum_consecutive_failures",
            },
            set(
                dimensions
            ),
        )

        for item in dimensions.values():

            self.assertTrue(
                item[
                    "required"
                ]
            )

            self.assertIsNone(
                item[
                    "default"
                ]
            )

    def test_budget_cannot_expand_itself(
        self,
    ):

        admission = (
            self.budget[
                "admission"
            ]
        )

        self.assertTrue(
            admission[
                "budget_must_be_explicit"
            ]
        )

        self.assertEqual(
            "deny",
            admission[
                "missing_dimension_behavior"
            ],
        )

        self.assertFalse(
            admission[
                "automatic_budget_expansion"
            ]
        )

        self.assertFalse(
            admission[
                "model_may_choose_budget"
            ]
        )

        self.assertFalse(
            admission[
                "agent_may_expand_own_budget"
            ]
        )

    def test_execution_envelope_reuses_task_executor_limit(
        self,
    ):

        executor = (
            self.envelope[
                "task_executor"
            ]
        )

        self.assertEqual(
            "maximum_steps",
            executor[
                "existing_limit_parameter"
            ],
        )

        self.assertEqual(
            1,
            executor[
                "maximum_completed_steps_per_slice"
            ],
        )

        self.assertTrue(
            executor[
                "single_step_slice_required"
            ]
        )

        self.assertFalse(
            executor[
                "new_executor_required"
            ]
        )

    def test_execution_envelope_requires_checkpoint(
        self,
    ):

        continuation = (
            self.envelope[
                "continuation"
            ]
        )

        self.assertFalse(
            continuation[
                "automatic_continue"
            ]
        )

        self.assertTrue(
            continuation[
                "checkpoint_required"
            ]
        )

        self.assertTrue(
            continuation[
                "observation_required"
            ]
        )

        self.assertTrue(
            continuation[
                "authorization_revalidation_required"
            ]
        )

        self.assertTrue(
            continuation[
                "budget_revalidation_required"
            ]
        )

    def test_execution_remains_disabled(
        self,
    ):

        for key, value in (
            self.envelope[
                "execution"
            ].items()
        ):

            self.assertFalse(
                value,
                msg=key,
            )

    def test_runtime_budget_status(
        self,
    ):

        budget = (
            self.agent
            .budgets()
        )

        self.assertTrue(
            budget[
                "contract_ready"
            ]
        )

        self.assertEqual(
            4,
            budget[
                "dimension_count"
            ],
        )

        self.assertFalse(
            budget[
                "defaults_allowed"
            ]
        )

        self.assertFalse(
            budget[
                "goal_budget_resolved"
            ]
        )

        self.assertFalse(
            budget[
                "execution_enabled"
            ]
        )

    def test_runtime_envelope_status(
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
                "execution_enabled"
            ]
        )

    def test_budget_phase_is_now_ready(
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

        self.assertNotIn(
            "autonomy-budgets-not-defined",
            readiness[
                "blockers"
            ],
        )

        phases = {
            item[
                "id"
            ]: item
            for item
            in readiness[
                "phases"
            ]
        }

        self.assertTrue(
            phases[
                "autonomy-budgets"
            ][
                "ready"
            ]
        )

        self.assertFalse(
            phases[
                "agent-execution"
            ][
                "ready"
            ]
        )

    def test_only_execution_blockers_remain(
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

    def test_frozen_1d_proof_is_historical(
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
                "9595d01c179745b1cd7aae07a8079abb8fd163fc"
            ),
            self.frozen[
                "source_commit"
            ],
        )

        self.assertEqual(
            (
                "6CEDDF1EA2626AF2CED3E531883B4EAED50F31ED97F0C52954DAE1C6A1F866F1"
            ),
            self.frozen[
                "portable_runtime"
            ][
                "sha256"
            ],
        )

        self.assertTrue(
            self.frozen[
                "historical_proof"
            ]
        )


if __name__ == "__main__":
    unittest.main()
