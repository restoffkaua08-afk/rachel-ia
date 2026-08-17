from __future__ import annotations

import sys
import unittest

from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
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


from training_backend_provisioning import (
    TrainingBackendProvisioning,
)


class TrainingBackendProvisioningTests(
    unittest.TestCase
):

    def service(self):
        return (
            TrainingBackendProvisioning()
        )

    def test_owner_is_samwell(self):

        self.assertEqual(
            "samwell",
            self.service()
            .status()[
                "contract"
            ][
                "owner"
            ],
        )

    def test_training_environment_is_isolated(self):

        environment = (
            self.service()
            .status()[
                "environment"
            ]
        )

        self.assertEqual(
            (
                "AMBIENTES/training/"
                "Scripts/python.exe"
            ),
            environment[
                "python_relative"
            ],
        )

        self.assertFalse(
            environment[
                "use_packaging_python"
            ]
        )

        self.assertFalse(
            environment[
                "use_packaging_torch"
            ]
        )

    def test_litgpt_is_pinned(self):

        litgpt = (
            self.service()
            .status()[
                "litgpt"
            ]
        )

        self.assertEqual(
            "0.5.13",
            litgpt[
                "version"
            ],
        )

        self.assertEqual(
            (
                "7bf2960dfb26bae8e815c9a16a22732974824ac1"
            ),
            litgpt[
                "commit"
            ],
        )

        self.assertIn(
            "torch>=2.7",
            litgpt[
                "core_constraints"
            ],
        )

        self.assertIn(
            "lightning>=2.6.1",
            litgpt[
                "core_constraints"
            ],
        )

    def test_jsonargparse_marker_matches_pinned_source(self):

        constraints = (
            self.service()
            .status()[
                "litgpt"
            ][
                "core_constraints"
            ]
        )

        self.assertIn(
            (
                "jsonargparse[signatures]>=4.37,<=4.41; "
                "python_version>='3.10'"
            ),
            constraints,
        )

    def test_local_litgpt_source_matches_contract(self):

        source = (
            self.service()
            .litgpt_source_status()
        )

        if source[
            "available"
        ]:

            self.assertTrue(
                source[
                    "version_match"
                ],
                msg=source,
            )

            self.assertTrue(
                source[
                    "python_requirement_match"
                ],
                msg=source,
            )

            self.assertTrue(
                source[
                    "core_constraints_match"
                ],
                msg=source,
            )

            self.assertEqual(
                [],
                source[
                    "missing_constraints"
                ],
            )

    def test_exact_gpu_versions_are_not_invented(self):

        host = (
            self.service()
            .status()[
                "target_host"
            ]
        )

        self.assertEqual(
            "unselected",
            host[
                "selection_state"
            ],
        )

        self.assertIsNone(
            host[
                "gpu_model"
            ]
        )

        self.assertIsNone(
            host[
                "cuda_version"
            ]
        )

        self.assertIsNone(
            host[
                "torch_version"
            ]
        )

        self.assertFalse(
            host[
                "exact_versions_locked"
            ]
        )

    def test_weights_and_checkpoint_absent(self):

        artifacts = (
            self.service()
            .status()[
                "artifacts"
            ]
        )

        self.assertEqual(
            "not-downloaded",
            artifacts[
                "source_weights"
            ][
                "state"
            ],
        )

        self.assertEqual(
            "not-created",
            artifacts[
                "checkpoint"
            ][
                "state"
            ],
        )

    def test_checkpoint_is_litgpt_native(self):

        checkpoint = (
            self.service()
            .status()[
                "artifacts"
            ][
                "checkpoint"
            ]
        )

        self.assertEqual(
            "litgpt-native",
            checkpoint[
                "format"
            ],
        )

        self.assertIn(
            "model_config.yaml",
            checkpoint[
                "required_files"
            ],
        )

        self.assertIn(
            "lit_model.pth",
            checkpoint[
                "required_files"
            ],
        )

    def test_plan_stays_blocked(self):

        plan = (
            self.service()
            .plan()
        )

        self.assertEqual(
            "blocked",
            plan[
                "state"
            ],
        )

        for blocker in (
            "training-host-unselected",
            "training-environment-not-created",
            "training-dependencies-unavailable",
            "training-versions-not-locked",
            "base-weights-not-downloaded",
            "litgpt-checkpoint-not-created",
            "training-execution-disabled",
        ):

            self.assertIn(
                blocker,
                plan[
                    "blockers"
                ],
            )

        self.assertNotIn(
            "litgpt-source-contract-mismatch",
            plan[
                "blockers"
            ],
        )

    def test_mutations_require_cyber(self):

        phases = (
            self.service()
            .plan()[
                "phases"
            ]
        )

        for phase in phases:
            if phase[
                "mutation"
            ]:
                self.assertTrue(
                    phase[
                        "requires_cyber"
                    ]
                )

    def test_no_executor_exists(self):

        service = self.service()

        for method in (
            "provision",
            "install",
            "download",
            "convert",
            "train",
            "execute_training",
        ):
            self.assertFalse(
                hasattr(
                    service,
                    method,
                )
            )

    def test_execution_is_disabled(self):

        status = (
            self.service()
            .status()
        )

        self.assertTrue(
            status[
                "contract_only"
            ]
        )

        for key in (
            "provisioning_execution_enabled",
            "command_generation_enabled",
            "automatic_install",
            "automatic_download",
            "automatic_conversion",
            "automatic_training",
            "training_execution_enabled",
            "checkpoint_created",
            "weights_modified",
        ):
            self.assertFalse(
                status[
                    key
                ],
                msg=key,
            )


if __name__ == "__main__":
    unittest.main()
