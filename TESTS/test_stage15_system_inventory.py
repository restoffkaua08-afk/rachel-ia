from __future__ import annotations

import json
import unittest

from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

REPORTS = (
    ROOT
    / "RELATORIOS"
    / "STAGE-15"
)

INVENTORY = (
    REPORTS
    / "system-inventory.json"
)

MATRIX = (
    REPORTS
    / "readiness-matrix.json"
)

BLOCKERS = (
    REPORTS
    / "blocker-register.json"
)

POLICY = (
    ROOT
    / "RACHEL_PLATFORM"
    / "CONFIG"
    / "stage-15-system-readiness-policy.json"
)


class Stage15SystemInventoryTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(
        cls,
    ):

        cls.inventory = json.loads(
            INVENTORY.read_text(
                encoding="utf-8-sig"
            )
        )

        cls.matrix = json.loads(
            MATRIX.read_text(
                encoding="utf-8-sig"
            )
        )

        cls.blockers = json.loads(
            BLOCKERS.read_text(
                encoding="utf-8-sig"
            )
        )

        cls.policy = json.loads(
            POLICY.read_text(
                encoding="utf-8-sig"
            )
        )

        cls.domains = {
            item["id"]: item
            for item
            in cls.inventory[
                "domains"
            ]
        }

    def test_exact_twenty_domains(
        self,
    ):

        expected = [
            item["id"]
            for item
            in self.policy[
                "audit_domains"
            ]
        ]

        actual = [
            item["id"]
            for item
            in self.inventory[
                "domains"
            ]
        ]

        self.assertEqual(
            20,
            len(actual),
        )

        self.assertEqual(
            expected,
            actual,
        )

    def test_states_are_contract_states(
        self,
    ):

        allowed = set(
            self.policy[
                "classification"
            ][
                "allowed_states"
            ]
        )

        for item in self.inventory[
            "domains"
        ]:

            self.assertIn(
                item["state"],
                allowed,
            )

    def test_ready_always_has_evidence(
        self,
    ):

        for item in self.inventory[
            "domains"
        ]:

            if item["state"] == "ready":

                self.assertGreater(
                    len(
                        item["evidence"]
                    ),
                    0,
                    msg=item["id"],
                )

    def test_known_blocked_capabilities_are_not_ready(
        self,
    ):

        for domain in (
            "model",
            "evaluation-promotion",
            "agent-runtime",
            "browser",
            "training-runtime",
        ):

            self.assertNotEqual(
                "ready",
                self.domains[
                    domain
                ][
                    "state"
                ],
                msg=domain,
            )

    def test_agent_remains_blocked(
        self,
    ):

        agent = self.domains[
            "agent-runtime"
        ]

        self.assertEqual(
            "blocked",
            agent[
                "state"
            ],
        )

        serialized = json.dumps(
            agent,
            sort_keys=True,
        )

        self.assertIn(
            "execution",
            serialized.lower(),
        )

    def test_browser_remains_reserved(
        self,
    ):

        self.assertEqual(
            "reserved",
            self.domains[
                "browser"
            ][
                "state"
            ],
        )

    def test_model_remains_blocked(
        self,
    ):

        self.assertEqual(
            "blocked",
            self.domains[
                "model"
            ][
                "state"
            ],
        )

    def test_evaluation_remains_blocked(
        self,
    ):

        self.assertEqual(
            "blocked",
            self.domains[
                "evaluation-promotion"
            ][
                "state"
            ],
        )

    def test_training_not_claimed_ready(
        self,
    ):

        self.assertIn(
            self.domains[
                "training-runtime"
            ][
                "state"
            ],
            {
                "unavailable",
                "blocked",
            },
        )

    def test_portable_matches_stage14_frozen(
        self,
    ):

        portable = self.inventory[
            "portable_runtime"
        ]

        self.assertTrue(
            portable[
                "matches_stage14_frozen"
            ]
        )

        self.assertEqual(
            (
                "D386A244E70C75F2486BCD0FC8406249431677BA870084E1073B4223FC5A655D"
            ),
            portable[
                "sha256"
            ],
        )

    def test_matrix_counts_add_to_twenty(
        self,
    ):

        summary = self.matrix[
            "summary"
        ]

        total = (
            summary["ready"]
            + summary["blocked"]
            + summary["reserved"]
            + summary["deferred"]
            + summary["unavailable"]
            + summary["not_applicable"]
        )

        self.assertEqual(
            20,
            total,
        )

        self.assertEqual(
            20,
            self.matrix[
                "domain_count"
            ],
        )

    def test_system_not_claimed_production_ready(
        self,
    ):

        self.assertFalse(
            self.matrix[
                "production_ready"
            ]
        )

        self.assertFalse(
            self.matrix[
                "architecture_closed"
            ]
        )

    def test_inventory_progress_recorded(
        self,
    ):

        progress = self.matrix[
            "stage_progress"
        ]

        self.assertTrue(
            progress[
                "inventory_completed"
            ]
        )

        self.assertTrue(
            progress[
                "matrix_completed"
            ]
        )

        self.assertTrue(
            progress[
                "blockers_registered"
            ]
        )

        self.assertFalse(
            progress[
                "architecture_closed"
            ]
        )

        self.assertFalse(
            progress[
                "stage_ready"
            ]
        )

    def test_blocker_register_matches_non_ready_domains(
        self,
    ):

        expected = {
            item["id"]
            for item
            in self.inventory[
                "domains"
            ]
            if item[
                "state"
            ] != "ready"
        }

        actual = {
            item["domain"]
            for item
            in self.blockers[
                "entries"
            ]
        }

        self.assertEqual(
            expected,
            actual,
        )

        self.assertEqual(
            len(expected),
            self.blockers[
                "entry_count"
            ],
        )

    def test_no_blocker_allows_bypass(
        self,
    ):

        self.assertFalse(
            self.blockers[
                "bypass_allowed"
            ]
        )

        for blocker in self.blockers[
            "entries"
        ]:

            self.assertFalse(
                blocker[
                    "bypass_allowed"
                ]
            )


if __name__ == "__main__":
    unittest.main()
