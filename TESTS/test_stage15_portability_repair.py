from __future__ import annotations

import json
import re
import unittest

from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

REGISTRY = json.loads(
    (
        ROOT
        / "RACHEL_PLATFORM"
        / "CONFIG"
        / "organs.registry.json"
    ).read_text(
        encoding="utf-8-sig"
    )
)

REPORTS = (
    ROOT
    / "RELATORIOS"
    / "STAGE-15"
)

COMPATIBILITY = json.loads(
    (
        REPORTS
        / "registry-consumer-compatibility.json"
    ).read_text(
        encoding="utf-8-sig"
    )
)

REPAIR = json.loads(
    (
        REPORTS
        / "portability-repair-1db2.json"
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


DRIVE_START = re.compile(
    r"(?i)^[a-z]:[\\/]"
)


def strings(
    value,
):

    if isinstance(
        value,
        dict,
    ):

        for item in value.values():

            yield from strings(
                item
            )

    elif isinstance(
        value,
        list,
    ):

        for item in value:

            yield from strings(
                item
            )

    elif isinstance(
        value,
        str,
    ):

        yield value


class Stage15PortabilityRepairTests(
    unittest.TestCase
):

    def test_registry_has_23_organs(
        self,
    ):

        self.assertEqual(
            23,
            REGISTRY[
                "total"
            ],
        )

        self.assertEqual(
            23,
            len(
                REGISTRY[
                    "orgaos"
                ]
            ),
        )

    def test_registry_relative_contract(
        self,
    ):

        self.assertEqual(
            "repository-root",
            REGISTRY[
                "path_base"
            ],
        )

        self.assertEqual(
            "posix-relative",
            REGISTRY[
                "path_format"
            ],
        )

        self.assertTrue(
            REGISTRY[
                "portable_paths"
            ]
        )

    def test_zero_absolute_windows_strings(
        self,
    ):

        offenders = [
            value
            for value
            in strings(
                REGISTRY
            )
            if DRIVE_START.match(
                value
            )
        ]

        self.assertEqual(
            [],
            offenders,
        )

    def test_https_is_not_drive(
        self,
    ):

        self.assertIsNone(
            DRIVE_START.match(
                "https://github.com/example/repository"
            )
        )

    def test_zero_mojibake(
        self,
    ):

        self.assertNotIn(
            "KauÃ",
            json.dumps(
                REGISTRY,
                ensure_ascii=False,
            ),
        )

    def test_sources_resolve(
        self,
    ):

        self.assertEqual(
            23,
            REPAIR[
                "registry"
            ][
                "source_paths_resolved"
            ],
        )

    def test_junctions_resolve(
        self,
    ):

        self.assertEqual(
            23,
            REPAIR[
                "registry"
            ][
                "junction_paths_resolved"
            ],
        )

    def test_environments_resolve(
        self,
    ):

        self.assertEqual(
            23,
            REPAIR[
                "registry"
            ][
                "environment_paths_present"
            ],
        )

    def test_four_consumers(
        self,
    ):

        self.assertEqual(
            4,
            COMPATIBILITY[
                "consumer_count"
            ],
        )

    def test_no_path_field_consumers(
        self,
    ):

        self.assertEqual(
            0,
            COMPATIBILITY[
                "path_field_access_count"
            ],
        )

        self.assertTrue(
            COMPATIBILITY[
                "all_consumers_compatible"
            ]
        )

        self.assertFalse(
            COMPATIBILITY[
                "runtime_changes_required"
            ]
        )

    def test_functional_metadata_preserved(
        self,
    ):

        self.assertTrue(
            REPAIR[
                "registry"
            ][
                "functional_metadata_preserved"
            ]
        )

    def test_repository_integrity_cause_resolved(
        self,
    ):

        readiness = (
            REPAIR[
                "readiness"
            ]
        )

        self.assertTrue(
            readiness[
                "cause_resolved"
            ]
        )

        self.assertEqual(
            "ready",
            readiness[
                "post_repair_repository_integrity_recommendation"
            ],
        )

    def test_matrix_not_auto_changed(
        self,
    ):

        self.assertFalse(
            REPAIR[
                "readiness"
            ][
                "matrix_changed"
            ]
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

    def test_timeout_was_not_reproduced(
        self,
    ):

        diagnostic = (
            REPAIR[
                "timeout_diagnostic"
            ]
        )

        self.assertEqual(
            3,
            diagnostic[
                "isolated_dashboard_passed"
            ],
        )

        self.assertTrue(
            diagnostic[
                "agent_bridge_passed"
            ]
        )

        self.assertLess(
            diagnostic[
                "isolated_dashboard_max_seconds"
            ],
            120,
        )

    def test_frozen_requires_rebuild(
        self,
    ):

        frozen = (
            REPAIR[
                "frozen"
            ]
        )

        self.assertFalse(
            frozen[
                "artifact_modified"
            ]
        )

        self.assertEqual(
            "stale-after-config-change",
            frozen[
                "current_source_frozen_state"
            ],
        )

        self.assertTrue(
            frozen[
                "rebuild_required"
            ]
        )

    def test_execution_remains_disabled(
        self,
    ):

        for key, value in REPAIR[
            "safety"
        ].items():

            self.assertFalse(
                value,
                msg=key,
            )


if __name__ == "__main__":
    unittest.main()
