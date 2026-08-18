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

GATE = json.loads(
    (
        REPORTS
        / "system-readiness-gate.json"
    ).read_text(
        encoding="utf-8-sig"
    )
)

PORTABLE = json.loads(
    (
        REPORTS
        / "portable-runtime-stage15-1dc.json"
    ).read_text(
        encoding="utf-8-sig"
    )
)

REGRESSION = json.loads(
    (
        REPORTS
        / "final-regression-1dc.json"
    ).read_text(
        encoding="utf-8-sig"
    )
)

MATRIX = json.loads(
    (
        REPORTS
        / "readiness-matrix.json"
    ).read_text(
        encoding="utf-8-sig"
    )
)


class Stage15SystemReadinessGateTests(
    unittest.TestCase
):

    def test_gate_passes_for_architecture_closure(
        self,
    ):

        self.assertEqual(
            "pass-for-architecture-closure",
            GATE[
                "state"
            ],
        )

        self.assertTrue(
            GATE[
                "architecture_closure_gate"
            ][
                "pass"
            ]
        )

        self.assertTrue(
            GATE[
                "architecture_closure_gate"
            ][
                "eligible_for_closure"
            ]
        )

    def test_architecture_not_closed_yet(
        self,
    ):

        self.assertFalse(
            GATE[
                "architecture_closure_gate"
            ][
                "architecture_closed"
            ]
        )

    def test_not_production_ready(
        self,
    ):

        self.assertFalse(
            GATE[
                "production_readiness"
            ][
                "ready"
            ]
        )

        self.assertFalse(
            GATE[
                "production_readiness"
            ][
                "claim_production_ready"
            ]
        )

    def test_matrix_is_still_truthful(
        self,
    ):

        self.assertEqual(
            20,
            MATRIX[
                "domain_count"
            ],
        )

        self.assertEqual(
            12,
            MATRIX[
                "summary"
            ][
                "ready"
            ],
        )

        self.assertEqual(
            8,
            MATRIX[
                "summary"
            ][
                "non_ready_total"
            ],
        )

    def test_zero_closure_blockers(
        self,
    ):

        self.assertEqual(
            0,
            GATE[
                "architecture_closure_gate"
            ][
                "closure_blockers"
            ],
        )

    def test_repository_integrity_resolved(
        self,
    ):

        repository = (
            GATE[
                "repository_integrity"
            ]
        )

        self.assertEqual(
            "ready",
            repository[
                "state"
            ],
        )

        self.assertTrue(
            repository[
                "stage_1c_recommendation_resolved"
            ]
        )

        self.assertEqual(
            0,
            repository[
                "absolute_machine_paths"
            ],
        )

    def test_final_frozen_is_new(
        self,
    ):

        self.assertEqual(
            "validated",
            PORTABLE[
                "state"
            ],
        )

        self.assertNotEqual(
            (
                "D386A244E70C75F2486BCD0FC8406249431677BA870084E1073B4223FC5A655D"
            ),
            PORTABLE[
                "sha256"
            ],
        )

        self.assertFalse(
            PORTABLE[
                "historical_sha_reused"
            ]
        )

    def test_frozen_registry_is_23_of_23(
        self,
    ):

        validation = (
            PORTABLE[
                "portable_validation"
            ]
        )

        self.assertEqual(
            23,
            validation[
                "registry_total"
            ],
        )

        self.assertEqual(
            23,
            validation[
                "registry_available"
            ],
        )

        self.assertEqual(
            0,
            validation[
                "registry_failed"
            ],
        )

    def test_frozen_agent_is_non_executable(
        self,
    ):

        validation = (
            PORTABLE[
                "portable_validation"
            ]
        )

        self.assertEqual(
            7,
            validation[
                "agent_read_actions"
            ],
        )

        self.assertEqual(
            0,
            validation[
                "state_mutations"
            ],
        )

        self.assertEqual(
            9,
            validation[
                "forbidden_actions_tested"
            ],
        )

        self.assertEqual(
            0,
            validation[
                "forbidden_actions_accepted"
            ],
        )

        self.assertFalse(
            validation[
                "execution_enabled"
            ]
        )

    def test_pre_gate_regression_passed(
        self,
    ):

        self.assertTrue(
            REGRESSION[
                "all_pre_gate_passed"
            ]
        )

        self.assertEqual(
            54,
            REGRESSION[
                "stage15_pre_gate_tests"
            ],
        )

        self.assertEqual(
            248,
            REGRESSION[
                "runtime_tests"
            ],
        )

        self.assertEqual(
            59,
            REGRESSION[
                "rachel_core_tests"
            ],
        )

    def test_frontend_and_cargo_passed(
        self,
    ):

        self.assertTrue(
            REGRESSION[
                "frontend_build"
            ]
        )

        self.assertTrue(
            REGRESSION[
                "cargo_check_locked_offline"
            ]
        )

    def test_safety_remains_disabled(
        self,
    ):

        for key, value in GATE[
            "safety"
        ].items():

            self.assertFalse(
                value,
                msg=key,
            )

    def test_next_is_final_closure(
        self,
    ):

        self.assertEqual(
            "15/1E",
            GATE[
                "next"
            ][
                "step"
            ],
        )


if __name__ == "__main__":
    unittest.main()
