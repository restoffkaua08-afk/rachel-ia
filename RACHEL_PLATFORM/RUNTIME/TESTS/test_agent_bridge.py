from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)

BRIDGE = (
    ROOT
    / "APP"
    / "bridge"
    / "rachel_bridge.py"
)


class AgentBridgeTests(
    unittest.TestCase
):

    def setUp(
        self,
    ):

        self.temp = (
            tempfile.TemporaryDirectory()
        )

        self.root = Path(
            self.temp.name
        )

        self.state = (
            self.root
            / "STATE"
        )

        self.state.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.request = (
            self.root
            / "request.json"
        )

        self.env = (
            os.environ.copy()
        )

        self.env[
            "RACHEL_RUNTIME_ROOT"
        ] = str(ROOT)

        self.env[
            "RACHEL_STATE_ROOT"
        ] = str(
            self.state
        )

        self.env[
            "PYTHONUTF8"
        ] = "1"

        self.env[
            "PYTHONDONTWRITEBYTECODE"
        ] = "1"

    def tearDown(
        self,
    ):

        self.temp.cleanup()

    def raw_call(
        self,
        action: str,
    ) -> tuple[int, dict]:

        self.request.write_text(
            json.dumps(
                {
                    "action": action,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        process = subprocess.run(
            [
                sys.executable,
                "-B",
                "-X",
                "utf8",
                str(BRIDGE),
                "--request-file",
                str(self.request),
            ],
            cwd=str(ROOT),
            env=self.env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )

        response = json.loads(
            process.stdout.strip()
        )

        return (
            process.returncode,
            response,
        )

    def call(
        self,
        action: str,
    ) -> dict:

        code, response = (
            self.raw_call(
                action
            )
        )

        self.assertEqual(
            0,
            code,
            msg=response,
        )

        self.assertTrue(
            response[
                "ok"
            ],
            msg=response,
        )

        return response[
            "payload"
        ]

    def fingerprint(
        self,
    ) -> list[str]:

        items: list[str] = []

        for path in sorted(
            item
            for item
            in self.root.rglob("*")
            if item.is_file()
            and item != self.request
        ):

            digest = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()

            items.append(
                (
                    str(
                        path.relative_to(
                            self.root
                        )
                    ).replace(
                        "\\",
                        "/",
                    )
                    + "|"
                    + str(
                        path.stat().st_size
                    )
                    + "|"
                    + digest
                )
            )

        return items

    def test_agent_status(
        self,
    ):

        status = self.call(
            "agent_status"
        )

        self.assertEqual(
            "rachel",
            status[
                "owner"
            ],
        )

        self.assertEqual(
            "inspection-only",
            status[
                "state"
            ],
        )

        self.assertTrue(
            status[
                "read_only"
            ]
        )

        self.assertFalse(
            status[
                "database_access"
            ]
        )

        self.assertFalse(
            status[
                "model_access"
            ]
        )

        self.assertFalse(
            status[
                "goal_execution"
            ]
        )

        self.assertFalse(
            status[
                "task_execution"
            ]
        )

        self.assertFalse(
            status[
                "tool_execution"
            ]
        )

    def test_agent_dependencies(
        self,
    ):

        dependencies = self.call(
            "agent_dependencies"
        )

        self.assertEqual(
            "static-ast",
            dependencies[
                "inspection_mode"
            ],
        )

        self.assertEqual(
            5,
            dependencies[
                "dependency_count"
            ],
        )

        self.assertEqual(
            5,
            dependencies[
                "available_count"
            ],
        )

        self.assertTrue(
            dependencies[
                "all_available"
            ]
        )

        self.assertFalse(
            dependencies[
                "operational_imports_performed"
            ]
        )

    def test_agent_authority(
        self,
    ):

        authority = self.call(
            "agent_authority"
        )

        self.assertTrue(
            authority[
                "ready"
            ]
        )

        self.assertEqual(
            "deny",
            authority[
                "default_tool_policy"
            ],
        )

        self.assertEqual(
            22,
            authority[
                "tool_count"
            ],
        )

        self.assertEqual(
            14,
            authority[
                "effect_policy_count"
            ],
        )

        self.assertEqual(
            [],
            authority[
                "unknown_effects"
            ],
        )

        self.assertFalse(
            authority[
                "approval_created"
            ]
        )

        self.assertFalse(
            authority[
                "approval_consumed"
            ]
        )

    def test_agent_readiness(
        self,
    ):

        readiness = self.call(
            "agent_readiness"
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

        self.assertFalse(
            readiness[
                "execution_enabled"
            ]
        )

    def test_agent_blockers(
        self,
    ):

        blockers = self.call(
            "agent_blockers"
        )

        self.assertEqual(
            5,
            blockers[
                "count"
            ],
        )

        self.assertFalse(
            blockers[
                "ready"
            ]
        )

        self.assertTrue(
            blockers[
                "read_only"
            ]
        )

        self.assertFalse(
            blockers[
                "execution_enabled"
            ]
        )

        expected = {
            "agent-loop-execution-disabled",
            "agent-runtime-execution-disabled",
            "goal-decomposition-disabled",
            "task-execution-by-agent-disabled",
            "tool-execution-by-agent-disabled",
        }

        self.assertEqual(
            expected,
            set(
                blockers[
                    "items"
                ]
            ),
        )

    def test_agent_budgets(
        self,
    ):

        budgets = self.call(
            "agent_budgets"
        )

        self.assertEqual(
            "explicit-per-goal-no-default",
            budgets[
                "strategy"
            ],
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
                "runtime_accounting_enabled"
            ]
        )

        self.assertFalse(
            budgets[
                "budget_enforcement_enabled"
            ]
        )

        self.assertFalse(
            budgets[
                "execution_enabled"
            ]
        )

        self.assertTrue(
            budgets[
                "read_only"
            ]
        )


    def test_agent_execution_envelope(
        self,
    ):

        envelope = self.call(
            "agent_execution_envelope"
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

        self.assertTrue(
            envelope[
                "single_step_slice_required"
            ]
        )

        self.assertFalse(
            envelope[
                "new_executor_required"
            ]
        )

        self.assertTrue(
            envelope[
                "checkpoint_required"
            ]
        )

        self.assertTrue(
            envelope[
                "observation_required"
            ]
        )

        self.assertTrue(
            envelope[
                "authorization_revalidation_required"
            ]
        )

        self.assertTrue(
            envelope[
                "budget_revalidation_required"
            ]
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

        self.assertTrue(
            envelope[
                "read_only"
            ]
        )


    def test_dashboard_contains_agent_status(
        self,
    ):

        dashboard = self.call(
            "dashboard"
        )

        self.assertIn(
            "agent",
            dashboard,
        )

        agent = dashboard[
            "agent"
        ]

        self.assertEqual(
            "rachel",
            agent[
                "owner"
            ],
        )

        self.assertTrue(
            agent[
                "read_only"
            ]
        )

        self.assertFalse(
            agent[
                "goal_execution"
            ]
        )

        self.assertFalse(
            agent[
                "tool_execution"
            ]
        )

        self.assertFalse(
            agent[
                "training_execution"
            ]
        )

        self.assertTrue(
            agent[
                "budgets"
            ][
                "contract_ready"
            ]
        )

        self.assertEqual(
            4,
            agent[
                "budgets"
            ][
                "dimension_count"
            ],
        )

        self.assertFalse(
            agent[
                "budgets"
            ][
                "defaults_allowed"
            ]
        )

        self.assertFalse(
            agent[
                "budgets"
            ][
                "goal_budget_resolved"
            ]
        )

        self.assertTrue(
            agent[
                "execution_envelope"
            ][
                "contract_ready"
            ]
        )

        self.assertEqual(
            1,
            agent[
                "execution_envelope"
            ][
                "maximum_completed_steps_per_slice"
            ],
        )

        self.assertFalse(
            agent[
                "execution_envelope"
            ][
                "automatic_continue"
            ]
        )

        self.assertFalse(
            agent[
                "execution_envelope"
            ][
                "execution_enabled"
            ]
        )

    def test_agent_read_actions_do_not_mutate_seeded_state(
        self,
    ):

        # Primeiro boot apenas prepara o portable state
        # via runtime_paths. Depois disso, actions Agent
        # precisam ser estritamente de leitura.
        self.call(
            "runtime_paths"
        )

        before = self.fingerprint()

        for action in (
            "agent_status",
            "agent_dependencies",
            "agent_authority",
            "agent_readiness",
            "agent_blockers",
            "agent_budgets",
            "agent_execution_envelope",
        ):

            self.call(
                action
            )

        after = self.fingerprint()

        self.assertEqual(
            before,
            after,
        )

    def test_agent_execution_action_does_not_exist(
        self,
    ):

        code, response = self.raw_call(
            "agent_execute"
        )

        self.assertNotEqual(
            0,
            code,
        )

        self.assertFalse(
            response[
                "ok"
            ]
        )

        self.assertEqual(
            "ValueError",
            response[
                "error"
            ][
                "type"
            ],
        )

        self.assertIn(
            "Unsupported action",
            response[
                "error"
            ][
                "message"
            ],
        )


if __name__ == "__main__":
    unittest.main()
