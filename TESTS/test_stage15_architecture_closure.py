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

CLOSURE = json.loads(
    (
        REPORTS
        / "architecture-closure.json"
    ).read_text(
        encoding="utf-8-sig"
    )
)

STATUS = json.loads(
    (
        REPORTS
        / "final-system-status.json"
    ).read_text(
        encoding="utf-8-sig"
    )
)

GATE = json.loads(
    (
        REPORTS
        / "system-readiness-gate.json"
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

README = (
    ROOT
    / "README.md"
).read_text(
    encoding="utf-8-sig"
)


class Stage15ArchitectureClosureTests(
    unittest.TestCase
):

    def test_all_fifteen_stages_are_closed(
        self,
    ):

        self.assertTrue(
            CLOSURE[
                "architecture"
            ][
                "closed"
            ]
        )

        self.assertEqual(
            15,
            CLOSURE[
                "architecture"
            ][
                "stages_closed"
            ],
        )

        self.assertEqual(
            15,
            CLOSURE[
                "architecture"
            ][
                "stages_total"
            ],
        )

    def test_final_state_is_architecture_closed(
        self,
    ):

        self.assertEqual(
            "architecture-closed-production-not-ready",
            CLOSURE[
                "state"
            ],
        )

        self.assertEqual(
            "architecture-closed-production-not-ready",
            STATUS[
                "overall_state"
            ],
        )

    def test_gate_was_passed_before_closure(
        self,
    ):

        self.assertTrue(
            GATE[
                "architecture_closure_gate"
            ][
                "pass"
            ]
        )

        self.assertEqual(
            "pass-for-architecture-closure",
            GATE[
                "state"
            ],
        )

    def test_production_ready_remains_false(
        self,
    ):

        self.assertFalse(
            CLOSURE[
                "production"
            ][
                "ready"
            ]
        )

        self.assertFalse(
            STATUS[
                "production_ready"
            ]
        )

        self.assertFalse(
            GATE[
                "production_readiness"
            ][
                "ready"
            ]
        )

    def test_readiness_matrix_remains_12_of_20(
        self,
    ):

        self.assertEqual(
            20,
            CLOSURE[
                "readiness"
            ][
                "domain_count"
            ],
        )

        self.assertEqual(
            12,
            CLOSURE[
                "readiness"
            ][
                "ready"
            ],
        )

        self.assertEqual(
            8,
            len(
                CLOSURE[
                    "readiness"
                ][
                    "non_ready"
                ]
            ),
        )

    def test_eight_non_ready_domains_are_exact(
        self,
    ):

        actual = {
            item[
                "id"
            ]: item[
                "state"
            ]
            for item
            in CLOSURE[
                "readiness"
            ][
                "non_ready"
            ]
        }

        expected = {
            "memory": "reserved",
            "model": "blocked",
            "learning": "deferred",
            "evaluation-promotion": "blocked",
            "agent-runtime": "blocked",
            "browser": "reserved",
            "privacy": "reserved",
            "training-runtime": "unavailable",
        }

        self.assertEqual(
            expected,
            actual,
        )

    def test_zero_closure_blockers(
        self,
    ):

        self.assertEqual(
            0,
            CLOSURE[
                "architecture"
            ][
                "closure_blockers"
            ],
        )

    def test_eight_production_blockers(
        self,
    ):

        self.assertEqual(
            8,
            CLOSURE[
                "production"
            ][
                "blocker_count"
            ],
        )

    def test_final_frozen_sha_is_preserved(
        self,
    ):

        self.assertEqual(
            (
                "7CA02072E67E60871A2D6ED06BBEAEFE4637875B44A216362D44CFE97C6F7AA9"
            ),
            CLOSURE[
                "portable_runtime"
            ][
                "sha256"
            ],
        )

        self.assertEqual(
            (
                "4964412ccde5b4cb1f9db2b60aad03088bcd4314"
            ),
            CLOSURE[
                "portable_runtime"
            ][
                "source_commit"
            ],
        )

    def test_final_regression_is_passed(
        self,
    ):

        regression = (
            CLOSURE[
                "regression"
            ]
        )

        self.assertTrue(
            regression[
                "all_passed"
            ]
        )

        self.assertEqual(
            248,
            regression[
                "runtime_tests"
            ],
        )

        self.assertEqual(
            59,
            regression[
                "rachel_core_tests"
            ],
        )

    def test_agent_and_browser_remain_disabled(
        self,
    ):

        safety = (
            CLOSURE[
                "execution_safety"
            ]
        )

        self.assertFalse(
            safety[
                "agent_execution"
            ]
        )

        self.assertFalse(
            safety[
                "browser_execution"
            ]
        )

        self.assertFalse(
            safety[
                "background_execution"
            ]
        )

        self.assertFalse(
            safety[
                "unattended_execution"
            ]
        )

    def test_training_and_weights_remain_disabled(
        self,
    ):

        safety = (
            CLOSURE[
                "execution_safety"
            ]
        )

        self.assertFalse(
            safety[
                "training_execution"
            ]
        )

        self.assertFalse(
            safety[
                "model_promotion"
            ]
        )

        self.assertFalse(
            safety[
                "weights_modified"
            ]
        )

    def test_closure_is_evidence_only(
        self,
    ):

        scope = (
            CLOSURE[
                "closure_scope"
            ]
        )

        self.assertTrue(
            scope[
                "evidence_only"
            ]
        )

        self.assertFalse(
            scope[
                "runtime_source_changed"
            ]
        )

        self.assertFalse(
            scope[
                "platform_config_changed"
            ]
        )

        self.assertFalse(
            scope[
                "frozen_payload_changed_after_validation"
            ]
        )

    def test_no_automatic_stage_16(
        self,
    ):

        lifecycle = (
            CLOSURE[
                "next_lifecycle"
            ]
        )

        self.assertTrue(
            lifecycle[
                "architecture_program_complete"
            ]
        )

        self.assertTrue(
            lifecycle[
                "future_work_requires_new_explicit_scope"
            ]
        )

        self.assertFalse(
            lifecycle[
                "automatic_stage_16"
            ]
        )

    def test_readme_reports_truthful_final_status(
        self,
    ):

        self.assertIn(
            "<!-- RACHEL_STAGE15_STATUS_START -->",
            README,
        )

        self.assertIn(
            "Arquitetura: 15/15 etapas fechadas",
            README,
        )

        self.assertIn(
            "nao esta declarada",
            README,
        )

        self.assertIn(
            (
                "7CA02072E67E60871A2D6ED06BBEAEFE4637875B44A216362D44CFE97C6F7AA9"
            ),
            README,
        )


if __name__ == "__main__":
    unittest.main()
