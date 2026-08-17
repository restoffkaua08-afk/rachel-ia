from __future__ import annotations

import copy
import json
import tempfile
import unittest

from pathlib import Path

from rachel_core.model_contract import (
    ModelContract,
    ModelContractError,
)


ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

CONTRACT = (
    ROOT
    / "RACHEL_PLATFORM"
    / "CONFIG"
    / "rachel-model-v0.1.json"
)


class ModelContractTests(
    unittest.TestCase
):

    def load(
        self,
    ) -> ModelContract:

        return ModelContract.from_path(
            CONTRACT
        )

    def test_official_contract_is_valid(
        self,
    ):
        contract = self.load()

        self.assertEqual(
            "rachel-model-v0.1",
            contract.status()[
                "model_id"
            ],
        )

    def test_contract_digest_is_stable(
        self,
    ):
        first = self.load()
        second = self.load()

        self.assertEqual(
            first.digest,
            second.digest,
        )

        self.assertEqual(
            64,
            len(
                first.digest
            ),
        )

    def test_ollama_model_is_not_rachel_model(
        self,
    ):
        contract = self.load()

        runtime = contract.value[
            "current_inference_runtime"
        ]

        self.assertEqual(
            "qwen3:1.7b",
            runtime[
                "model"
            ],
        )

        self.assertFalse(
            runtime[
                "is_rachel_model"
            ]
        )

        self.assertFalse(
            runtime[
                "is_training_base"
            ]
        )

    def test_training_base_is_unselected(
        self,
    ):
        contract = self.load()

        base = contract.value[
            "base_model"
        ]

        self.assertEqual(
            "unselected",
            base[
                "selection_state"
            ],
        )

        self.assertIsNone(
            base[
                "training_checkpoint"
            ]
        )

    def test_adapter_first_lora_contract(
        self,
    ):
        contract = self.load()

        self.assertEqual(
            "adapter-first",
            contract.value[
                "specialization"
            ][
                "strategy"
            ],
        )

        self.assertEqual(
            "lora",
            contract.value[
                "training_backend"
            ][
                "primary_method"
            ],
        )

        self.assertFalse(
            contract.value[
                "training_backend"
            ][
                "full_finetune_allowed"
            ]
        )

    def test_phase_one_is_sft_only(
        self,
    ):
        contract = self.load()

        self.assertEqual(
            [
                "sft"
            ],
            contract.value[
                "dataset_policy"
            ][
                "phase_1_trainable_formats"
            ],
        )

    def test_current_machine_blocks_weight_training(
        self,
    ):
        contract = self.load()

        audit = contract.value[
            "current_machine_audit"
        ]

        self.assertFalse(
            audit[
                "local_weight_training_allowed"
            ]
        )

        self.assertFalse(
            audit[
                "torch_cuda_available"
            ]
        )

    def test_enabling_automatic_training_is_rejected(
        self,
    ):
        value = copy.deepcopy(
            self.load().value
        )

        value[
            "execution_policy"
        ][
            "automatic_training"
        ] = True

        with self.assertRaises(
            ModelContractError
        ):
            ModelContract(
                value
            )


if __name__ == "__main__":
    unittest.main()