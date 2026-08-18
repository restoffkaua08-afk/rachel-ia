from __future__ import annotations

import ast
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


from agent_runtime import (
    AgentRuntime,
)


class AgentRuntimeTests(
    unittest.TestCase
):

    def service(
        self,
    ) -> AgentRuntime:

        return AgentRuntime(
            root=ROOT
        )

    def test_status_is_read_only(
        self,
    ):

        status = (
            self.service()
            .status()
        )

        self.assertEqual(
            "rachel",
            status[
                "owner"
            ],
        )

        self.assertEqual(
            "governed-autonomy",
            status[
                "mode"
            ],
        )

        self.assertTrue(
            status[
                "available"
            ]
        )

        self.assertTrue(
            status[
                "read_only"
            ]
        )

        for key in (
            "filesystem_mutation",
            "database_access",
            "model_access",
            "operational_runtime_imports",
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

    def test_dependencies_are_available(
        self,
    ):

        dependencies = (
            self.service()
            .dependencies()
        )

        self.assertEqual(
            "static-ast",
            dependencies[
                "inspection_mode"
            ],
        )

        self.assertFalse(
            dependencies[
                "operational_imports_performed"
            ]
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

        for item in (
            dependencies[
                "items"
            ]
        ):

            self.assertTrue(
                item[
                    "available"
                ],
                msg=item,
            )

    def test_authority_is_ready(
        self,
    ):

        authority = (
            self.service()
            .authority_map()
        )

        self.assertEqual(
            "rachel",
            authority[
                "coordinator"
            ],
        )

        self.assertEqual(
            "ned",
            authority[
                "planner"
            ],
        )

        self.assertEqual(
            "ned",
            authority[
                "executor"
            ],
        )

        self.assertEqual(
            "arya",
            authority[
                "tools"
            ],
        )

        self.assertEqual(
            "cyber",
            authority[
                "authorization"
            ],
        )

        self.assertEqual(
            "deny",
            authority[
                "default_tool_policy"
            ],
        )

        self.assertTrue(
            authority[
                "ready"
            ]
        )

        self.assertEqual(
            [],
            authority[
                "blockers"
            ],
        )

    def test_approval_contract_is_bound(
        self,
    ):

        approval = (
            self.service()
            .authority_map()[
                "approval_policy"
            ]
        )

        self.assertTrue(
            approval[
                "single_use"
            ]
        )

        self.assertTrue(
            approval[
                "bind_tool"
            ]
        )

        self.assertTrue(
            approval[
                "bind_arguments"
            ]
        )

        self.assertFalse(
            approval[
                "store_argument_values"
            ]
        )

    def test_tool_registry_is_static(
        self,
    ):

        authority = (
            self.service()
            .authority_map()
        )

        self.assertGreater(
            authority[
                "tool_count"
            ],
            0,
        )

        self.assertEqual(
            [],
            authority[
                "unknown_effects"
            ],
        )

        for item in (
            authority[
                "registered_tools"
            ]
        ):

            self.assertNotEqual(
                "unknown",
                item[
                    "risk"
                ],
            )

    def test_effect_policy_is_from_task_planner(
        self,
    ):

        effect = (
            self.service()
            .effect_policies()
        )

        self.assertEqual(
            "task_planner.EFFECTS",
            effect[
                "source"
            ],
        )

        self.assertTrue(
            effect[
                "static_inspection"
            ]
        )

        self.assertGreaterEqual(
            effect[
                "count"
            ],
            10,
        )

        index = {
            item[
                "effect"
            ]: item
            for item
            in effect[
                "items"
            ]
        }

        self.assertFalse(
            index[
                "read"
            ][
                "approval_required"
            ]
        )

        self.assertTrue(
            index[
                "external"
            ][
                "approval_required"
            ]
        )

        self.assertTrue(
            index[
                "execute"
            ][
                "approval_required"
            ]
        )

    def test_readiness_is_blocked_only_by_future_execution_contract(
        self,
    ):

        readiness = (
            self.service()
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

        for blocker in (
            "agent-runtime-execution-disabled",
            "agent-loop-execution-disabled",
            "goal-decomposition-disabled",
            "task-execution-by-agent-disabled",
            "tool-execution-by-agent-disabled",
        ):
            self.assertIn(
                blocker,
                readiness[
                    "blockers"
                ],
            )

    def test_capabilities_do_not_execute(
        self,
    ):

        capabilities = (
            self.service()
            .capabilities()
        )

        for key in (
            "read_status",
            "inspect_authority",
            "inspect_dependencies",
            "inspect_readiness",
            "inspect_blockers",
            "inspect_tool_registry",
        ):
            self.assertTrue(
                capabilities[
                    key
                ],
                msg=key,
            )

        for key in (
            "execute_goal",
            "decompose_goal",
            "create_task_plan",
            "execute_task_plan",
            "invoke_tool",
            "request_approval",
            "consume_approval",
            "browser_navigation",
            "background_loop",
            "unattended_execution",
            "external_publish",
            "credential_use",
            "self_modification",
            "self_update",
            "train_model",
        ):
            self.assertFalse(
                capabilities[
                    key
                ],
                msg=key,
            )

    def test_no_execution_method_exists(
        self,
    ):

        service = self.service()

        for method in (
            "run",
            "execute",
            "invoke",
            "plan",
            "execute_goal",
            "execute_task",
            "request_approval",
            "consume_approval",
            "navigate",
            "train",
        ):
            self.assertFalse(
                hasattr(
                    service,
                    method,
                ),
                msg=method,
            )

    def test_agent_runtime_does_not_import_operational_components(
        self,
    ):

        path = (
            RUNTIME
            / "agent_runtime.py"
        )

        module = ast.parse(
            path.read_text(
                encoding="utf-8-sig"
            ),
            filename=str(
                path
            ),
        )

        imported: set[str] = set()

        for node in ast.walk(
            module
        ):

            if isinstance(
                node,
                ast.Import,
            ):

                imported.update(
                    alias.name
                    for alias
                    in node.names
                )

            elif isinstance(
                node,
                ast.ImportFrom,
            ):

                if node.module:
                    imported.add(
                        node.module
                    )

        forbidden = {
            "task_runtime",
            "task_planner",
            "task_executor",
            "tools_runtime",
            "security_runtime",
            "rachel_core.bootstrap",
        }

        self.assertTrue(
            forbidden.isdisjoint(
                imported
            ),
            msg=sorted(
                imported
            ),
        )

    def test_browser_remains_reserved(
        self,
    ):

        status = (
            self.service()
            .status()
        )

        self.assertEqual(
            "reserved-not-integrated",
            status[
                "browser"
            ][
                "state"
            ],
        )

        self.assertFalse(
            status[
                "browser"
            ][
                "execution_enabled"
            ]
        )


if __name__ == "__main__":
    unittest.main()
