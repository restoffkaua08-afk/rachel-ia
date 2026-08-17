from __future__ import annotations

import unittest

from pathlib import Path

from rachel_core.model_contract import (
    ModelContract,
)

from rachel_core.training_run_planner import (
    TRAINING_RUN_PLANNER_VERSION,
    TrainingRunPlanner,
    TrainingRunPlannerError,
)


ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

CONTRACT_PATH = (
    ROOT
    / "RACHEL_PLATFORM"
    / "CONFIG"
    / "rachel-model-v0.1.json"
)

PROFILES_PATH = (
    ROOT
    / "RACHEL_PLATFORM"
    / "CONFIG"
    / "training-hardware-profiles.json"
)


class TrainingRunPlannerTests(
    unittest.TestCase
):

    def planner(
        self,
    ) -> TrainingRunPlanner:
        return TrainingRunPlanner(
            contract=ModelContract.from_path(
                CONTRACT_PATH
            ),
            profiles_path=PROFILES_PATH,
        )

    @staticmethod
    def dataset():
        return {
            "id": "sft-compiled-test",
            "state": "compiled-local",
            "training_format": "sft",
            "integrity": True,
            "train_count": 80,
            "eval_count": 20,
            "train_sha256": "a" * 64,
            "eval_sha256": "b" * 64,
        }

    @staticmethod
    def capable_hardware():
        return {
            "nvidia_cuda": True,
            "torch_cuda": True,
            "vram_gb": 24.0,
            "ram_gb": 32.0,
            "free_disk_gb": 120.0,
            "weight_training_allowed": True,
        }

    def test_profiles_are_available(
        self,
    ):
        planner = self.planner()

        profiles = {
            item["id"]
            for item in planner.list_profiles()
        }

        self.assertIn(
            "qwen3-1.7b-lora-minimum",
            profiles,
        )

        self.assertIn(
            "qwen3-1.7b-lora-recommended",
            profiles,
        )

    def test_current_machine_fails_minimum_profile(
        self,
    ):
        planner = self.planner()

        result = planner.evaluate_hardware(
            "qwen3-1.7b-lora-minimum",
            planner.current_hardware(),
        )

        self.assertFalse(
            result["eligible"]
        )

        self.assertIn(
            "nvidia-cuda-required",
            result["blockers"],
        )

        self.assertIn(
            "ram-below-policy",
            result["blockers"],
        )

    def test_capable_hardware_passes_minimum_profile(
        self,
    ):
        planner = self.planner()

        result = planner.evaluate_hardware(
            "qwen3-1.7b-lora-minimum",
            self.capable_hardware(),
        )

        self.assertTrue(
            result["eligible"]
        )

        self.assertEqual(
            [],
            result["blockers"],
        )

    def test_plan_is_deterministic(
        self,
    ):
        planner = self.planner()

        first = planner.plan(
            self.dataset(),
            observed_hardware=(
                self.capable_hardware()
            ),
        )

        second = planner.plan(
            self.dataset(),
            observed_hardware=(
                self.capable_hardware()
            ),
        )

        self.assertEqual(
            first["run_id"],
            second["run_id"],
        )

        self.assertEqual(
            first["plan_sha256"],
            second["plan_sha256"],
        )

        self.assertEqual(
            TRAINING_RUN_PLANNER_VERSION,
            first["planner_version"],
        )

    def test_phase_one_rejects_non_sft_dataset(
        self,
    ):
        planner = self.planner()

        dataset = self.dataset()

        dataset[
            "training_format"
        ] = "preference"

        with self.assertRaises(
            TrainingRunPlannerError
        ):
            planner.plan(
                dataset,
                observed_hardware=(
                    self.capable_hardware()
                ),
            )

    def test_plan_stays_blocked_without_weights_and_execution(
        self,
    ):
        planner = self.planner()

        result = planner.plan(
            self.dataset(),
            observed_hardware=(
                self.capable_hardware()
            ),
        )

        self.assertEqual(
            "planned-blocked",
            result["state"],
        )

        self.assertIn(
            "base-weights-not-downloaded",
            result["blockers"],
        )

        self.assertIn(
            "base-checkpoint-not-ready",
            result["blockers"],
        )

        self.assertIn(
            "training-execution-disabled",
            result["blockers"],
        )

        self.assertFalse(
            result["execution_allowed"]
        )

    def test_planner_never_starts_training(
        self,
    ):
        planner = self.planner()

        result = planner.plan(
            self.dataset(),
            observed_hardware=(
                self.capable_hardware()
            ),
        )

        self.assertTrue(
            result["planner_only"]
        )

        self.assertFalse(
            result["files_written"]
        )

        self.assertFalse(
            result["weights_downloaded"]
        )

        self.assertFalse(
            result["training_started"]
        )

        self.assertFalse(
            result["checkpoint_created"]
        )

        self.assertFalse(
            result["weights_modified"]
        )


if __name__ == "__main__":
    unittest.main()