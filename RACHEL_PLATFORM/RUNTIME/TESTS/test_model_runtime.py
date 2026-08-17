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


from model_runtime import (
    RachelModelRuntime,
)


CONTRACT = (
    ROOT
    / "RACHEL_PLATFORM"
    / "CONFIG"
    / "rachel-model-v0.1.json"
)


class FakePreflight:
    def __init__(
        self,
        *,
        data: bool = False,
        backend: bool = True,
        pipeline: bool = True,
    ) -> None:

        self.data = data
        self.backend = backend
        self.pipeline = pipeline

    def report(
        self,
        limit: int = 200,
    ):
        return {
            "status": "fake",
            "pipeline_ready": (
                self.pipeline
            ),
            "training_data_available": (
                self.data
            ),
            "training_backend_available": (
                self.backend
            ),
            "stage12_execution_enabled": False,
            "automatic_training": False,
            "checkpoint_created": False,
            "weights_modified": False,
            "external_export": False,
        }


class RachelModelRuntimeTests(
    unittest.TestCase
):

    def service(
        self,
        *,
        data: bool = False,
        backend: bool = True,
    ) -> RachelModelRuntime:

        return RachelModelRuntime(
            contract_path=CONTRACT,
            preflight=FakePreflight(
                data=data,
                backend=backend,
            ),
        )

    def test_model_runtime_is_blocked_by_default(
        self,
    ):
        status = (
            self.service()
            .status()
        )

        self.assertFalse(
            status[
                "can_train_weights"
            ]
        )

        self.assertFalse(
            status[
                "training_execution_enabled"
            ]
        )

    def test_required_blockers_are_present(
        self,
    ):
        blockers = (
            self.service()
            .blockers()
        )

        self.assertIn(
            "base-model-unselected",
            blockers,
        )

        self.assertIn(
            "training-data-unavailable",
            blockers,
        )

        self.assertIn(
            "ml-stack-not-provisioned",
            blockers,
        )

        self.assertIn(
            (
                "current-hardware-"
                "weight-training-blocked"
            ),
            blockers,
        )

        self.assertIn(
            "training-execution-disabled",
            blockers,
        )

    def test_backend_blocker_is_reported(
        self,
    ):
        blockers = (
            self.service(
                backend=False
            )
            .blockers()
        )

        self.assertIn(
            "training-backend-unavailable",
            blockers,
        )

    def test_data_pipeline_can_remain_ready_while_training_blocked(
        self,
    ):
        status = (
            self.service()
            .status()
        )

        self.assertTrue(
            status[
                "can_prepare_datasets"
            ]
        )

        self.assertFalse(
            status[
                "can_train_weights"
            ]
        )

    def test_qwen_ollama_is_temporary_runtime_only(
        self,
    ):
        status = (
            self.service()
            .status()
        )

        model = status[
            "model"
        ]

        self.assertEqual(
            "qwen3:1.7b",
            model[
                "current_inference_model"
            ],
        )

        self.assertEqual(
            "temporary-inference-provider",
            model[
                "current_inference_role"
            ],
        )


if __name__ == "__main__":
    unittest.main()