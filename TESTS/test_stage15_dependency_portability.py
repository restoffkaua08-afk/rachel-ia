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


class Stage15DependencyPortabilityTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(
        cls,
    ):

        cls.dependencies = json.loads(
            (
                REPORTS
                / "dependency-integrity.json"
            ).read_text(
                encoding="utf-8-sig"
            )
        )

        cls.environment = json.loads(
            (
                REPORTS
                / "environment-audit.json"
            ).read_text(
                encoding="utf-8-sig"
            )
        )

        cls.portability = json.loads(
            (
                REPORTS
                / "portability-audit.json"
            ).read_text(
                encoding="utf-8-sig"
            )
        )

        cls.reconciliation = json.loads(
            (
                REPORTS
                / "readiness-reconciliation-1c.json"
            ).read_text(
                encoding="utf-8-sig"
            )
        )

    def test_submodule_inventory_is_exact(
        self,
    ):

        submodules = (
            self.dependencies[
                "submodules"
            ]
        )

        self.assertEqual(
            23,
            submodules[
                "expected"
            ],
        )

        self.assertEqual(
            23,
            submodules[
                "declared"
            ],
        )

        self.assertEqual(
            23,
            submodules[
                "observed"
            ],
        )

        self.assertEqual(
            0,
            submodules[
                "uninitialized"
            ],
        )

        self.assertEqual(
            0,
            submodules[
                "diverged"
            ],
        )

        self.assertEqual(
            0,
            submodules[
                "conflicted"
            ],
        )

        self.assertTrue(
            submodules[
                "healthy"
            ]
        )

    def test_required_manifests_exist(
        self,
    ):

        manifests = (
            self.dependencies[
                "manifests"
            ]
        )

        self.assertTrue(
            manifests[
                "required_present"
            ]
        )

        for item in manifests[
            "required"
        ]:

            self.assertTrue(
                item[
                    "exists"
                ],
                msg=item[
                    "path"
                ],
            )

    def test_dependency_locks_recorded(
        self,
    ):

        manifests = (
            self.dependencies[
                "manifests"
            ]
        )

        self.assertIsInstance(
            manifests[
                "node_lock_available"
            ],
            bool,
        )

        self.assertIsInstance(
            manifests[
                "rust_lock_available"
            ],
            bool,
        )

        self.assertIsInstance(
            manifests[
                "dependency_locking_ready"
            ],
            bool,
        )

    def test_runtime_python_exists(
        self,
    ):

        runtime = (
            self.environment[
                "runtime_python"
            ]
        )

        self.assertTrue(
            runtime[
                "exists"
            ]
        )

        self.assertIsNotNone(
            runtime[
                "version"
            ]
        )

    def test_packaging_python_exists(
        self,
    ):

        packaging = (
            self.environment[
                "desktop_sidecar_python"
            ]
        )

        self.assertTrue(
            packaging[
                "exists"
            ]
        )

        self.assertTrue(
            packaging[
                "pyinstaller"
            ][
                "available"
            ]
        )

    def test_training_not_implicitly_created(
        self,
    ):

        self.assertFalse(
            self.environment[
                "training_runtime_provisioned"
            ]
        )

        self.assertFalse(
            self.environment[
                "training_execution_enabled"
            ]
        )

        self.assertFalse(
            self.environment[
                "weights_modified"
            ]
        )

    def test_portable_hash_is_final_stage14_hash(
        self,
    ):

        portable = (
            self.portability[
                "portable_runtime"
            ]
        )

        self.assertTrue(
            portable[
                "exists"
            ]
        )

        self.assertTrue(
            portable[
                "hash_valid"
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

    def test_packaging_contract_is_present(
        self,
    ):

        packaging = (
            self.portability[
                "packaging_contract"
            ]
        )

        self.assertTrue(
            packaging[
                "tauri_config_exists"
            ]
        )

        self.assertTrue(
            packaging[
                "tauri_sidecar_declared"
            ]
        )

        self.assertTrue(
            packaging[
                "pyinstaller_spec_exists"
            ]
        )

        self.assertTrue(
            packaging[
                "runtime_bundle_declared"
            ]
        )

        self.assertTrue(
            packaging[
                "agent_config_bundle_declared"
            ]
        )

    def test_machine_path_scan_is_recorded(
        self,
    ):

        scan = (
            self.portability[
                "machine_path_scan"
            ]
        )

        self.assertIsInstance(
            scan[
                "count"
            ],
            int,
        )

        self.assertGreaterEqual(
            scan[
                "count"
            ],
            0,
        )

    def test_repository_hygiene_is_recorded(
        self,
    ):

        hygiene = (
            self.portability[
                "repository_hygiene"
            ]
        )

        self.assertIsInstance(
            hygiene[
                "suspicious_count"
            ],
            int,
        )

    def test_reconciliation_does_not_auto_change_matrix(
        self,
    ):

        self.assertFalse(
            self.reconciliation[
                "classification_changes_applied"
            ]
        )

        self.assertFalse(
            self.reconciliation[
                "rules"
            ][
                "automatic_upgrade_to_ready"
            ]
        )

        self.assertFalse(
            self.reconciliation[
                "rules"
            ][
                "automatic_downgrade"
            ]
        )

        self.assertTrue(
            self.reconciliation[
                "rules"
            ][
                "evidence_only"
            ]
        )

    def test_architecture_still_open(
        self,
    ):

        state = (
            self.reconciliation[
                "stage15_state"
            ]
        )

        self.assertTrue(
            state[
                "dependency_audit_completed"
            ]
        )

        self.assertTrue(
            state[
                "environment_audit_completed"
            ]
        )

        self.assertTrue(
            state[
                "portability_audit_completed"
            ]
        )

        self.assertFalse(
            state[
                "architecture_closed"
            ]
        )

        self.assertFalse(
            state[
                "production_ready"
            ]
        )


if __name__ == "__main__":
    unittest.main()
