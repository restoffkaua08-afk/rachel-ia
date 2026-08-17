from __future__ import annotations

import json
import unittest

from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

CONTRACT = (
    ROOT
    / "RACHEL_AGENT"
    / "CONFIG"
    / "agent-desktop-bridge.json"
)

BRIDGE = (
    ROOT
    / "APP"
    / "bridge"
    / "rachel_bridge.py"
)

SPEC = (
    ROOT
    / "APP"
    / "sidecar"
    / "rachel_backend.spec"
)


class AgentDesktopContractTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(
        cls,
    ):

        cls.contract = json.loads(
            CONTRACT.read_text(
                encoding="utf-8-sig"
            )
        )

        cls.bridge = BRIDGE.read_text(
            encoding="utf-8-sig"
        )

        cls.spec = SPEC.read_text(
            encoding="utf-8-sig"
        )

    def test_identity(
        self,
    ):

        self.assertEqual(
            1,
            self.contract[
                "schema_version"
            ],
        )

        self.assertEqual(
            14,
            self.contract[
                "stage"
            ],
        )

        self.assertEqual(
            "rachel",
            self.contract[
                "owner"
            ],
        )

        self.assertEqual(
            "integrated-read-only-source",
            self.contract[
                "state"
            ],
        )

    def test_exact_read_actions(
        self,
    ):

        bridge = (
            self.contract[
                "bridge"
            ]
        )

        self.assertEqual(
            [
                "agent_status",
                "agent_dependencies",
                "agent_authority",
                "agent_readiness",
                "agent_blockers",
            ],
            bridge[
                "read_actions"
            ],
        )

        self.assertEqual(
            [],
            bridge[
                "execution_actions"
            ],
        )

    def test_no_agent_execution_actions_declared(
        self,
    ):

        bridge = (
            self.contract[
                "bridge"
            ]
        )

        for key in (
            "goal_execution_action_available",
            "task_execution_action_available",
            "tool_execution_action_available",
            "approval_creation_action_available",
            "approval_consumption_action_available",
            "browser_execution_action_available",
        ):

            self.assertFalse(
                bridge[
                    key
                ],
                msg=key,
            )

    def test_dashboard_is_read_only_agent_status(
        self,
    ):

        dashboard = (
            self.contract[
                "dashboard"
            ]
        )

        self.assertTrue(
            dashboard[
                "integrated"
            ]
        )

        self.assertEqual(
            "agent",
            dashboard[
                "key"
            ],
        )

        self.assertEqual(
            "AgentRuntime.status",
            dashboard[
                "payload"
            ],
        )

        self.assertTrue(
            dashboard[
                "read_only_agent_payload"
            ]
        )

    def test_packaging_prepared_but_not_frozen_yet(
        self,
    ):

        packaging = (
            self.contract[
                "packaging"
            ]
        )

        self.assertTrue(
            packaging[
                "agent_config_bundled"
            ]
        )

        self.assertTrue(
            packaging[
                "runtime_source_bundled"
            ]
        )

        self.assertTrue(
            packaging[
                "runtime_hidden_import_via_src_glob"
            ]
        )

        self.assertFalse(
            packaging[
                "frozen_rebuild_performed"
            ]
        )

        self.assertEqual(
            "pending",
            packaging[
                "frozen_validation_state"
            ],
        )

        self.assertIn(
            "RACHEL_AGENT/CONFIG",
            self.spec,
        )

        self.assertIn(
            'SRC.glob(',
            self.spec,
        )

    def test_all_execution_flags_remain_false(
        self,
    ):

        for key, value in (
            self.contract[
                "execution"
            ].items()
        ):

            self.assertFalse(
                value,
                msg=key,
            )

    def test_bridge_contains_no_agent_execute_action(
        self,
    ):

        self.assertIn(
            'if action == "agent_status"',
            self.bridge,
        )

        self.assertIn(
            'if action == "agent_dependencies"',
            self.bridge,
        )

        self.assertIn(
            'if action == "agent_authority"',
            self.bridge,
        )

        self.assertIn(
            'if action == "agent_readiness"',
            self.bridge,
        )

        self.assertIn(
            'if action == "agent_blockers"',
            self.bridge,
        )

        for forbidden in (
            'if action == "agent_execute"',
            'if action == "agent_run"',
            'if action == "agent_invoke_tool"',
            'if action == "agent_request_approval"',
            'if action == "agent_consume_approval"',
        ):

            self.assertNotIn(
                forbidden,
                self.bridge,
            )


if __name__ == "__main__":
    unittest.main()
