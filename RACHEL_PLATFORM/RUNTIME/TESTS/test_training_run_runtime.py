from __future__ import annotations

import sys
import unittest

from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)

for path in (
    ROOT
    / "RACHEL_CORE"
    / "src",
    ROOT
    / "RACHEL_PLATFORM"
    / "RUNTIME"
    / "SRC",
):
    if str(path) not in sys.path:
        sys.path.insert(
            0,
            str(path),
        )


from training_run_runtime import (
    TrainingRunRuntime,
)


class TrainingRunRuntimeTests(
    unittest.TestCase
):

    def service(
        self,
    ) -> TrainingRunRuntime:
        return TrainingRunRuntime()

    def test_status_is_planner_only(
        self,
    ):
        status = (
            self.service()
            .status()
        )

        self.assertTrue(
            status[
                "planner"
            ][
                "planner_only"
            ]
        )

        self.assertFalse(
            status[
                "can_train_weights"
            ]
        )

    def test_current_machine_is_not_minimum_eligible(
        self,
    ):
        status = (
            self.service()
            .status()
        )

        self.assertFalse(
            status[
                "current_machine_minimum_eligible"
            ]
        )

    def test_current_machine_is_not_recommended_eligible(
        self,
    ):
        status = (
            self.service()
            .status()
        )

        self.assertFalse(
            status[
                "current_machine_recommended_eligible"
            ]
        )

    def test_preview_contains_lora_sft_recipe(
        self,
    ):
        preview = (
            self.service()
            .preview()
        )

        recipe = preview[
            "template"
        ][
            "recipe"
        ]

        self.assertEqual(
            "lora",
            recipe[
                "method"
            ],
        )

        self.assertEqual(
            "sft",
            recipe[
                "training_format"
            ],
        )

        self.assertEqual(
            8,
            recipe[
                "lora_r"
            ],
        )

        self.assertEqual(
            1337,
            recipe[
                "seed"
            ],
        )

    def test_runtime_never_executes_training(
        self,
    ):
        preview = (
            self.service()
            .preview()
        )

        self.assertFalse(
            preview[
                "can_create_executable_plan"
            ]
        )

        self.assertFalse(
            preview[
                "can_train_weights"
            ]
        )

        self.assertFalse(
            preview[
                "automatic_install"
            ]
        )

        self.assertFalse(
            preview[
                "automatic_download"
            ]
        )

        self.assertFalse(
            preview[
                "automatic_training"
            ]
        )

        self.assertFalse(
            preview[
                "checkpoint_created"
            ]
        )

        self.assertFalse(
            preview[
                "weights_modified"
            ]
        )


if __name__ == "__main__":
    unittest.main()