from __future__ import annotations

import hashlib
import json

from pathlib import Path
from typing import Any


MODEL_CONTRACT_SCHEMA_VERSION = 1
RACHEL_MODEL_ID = "rachel-model-v0.1"


class ModelContractError(
    RuntimeError
):
    pass


def canonical_json(
    value: Any,
) -> str:

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    )


def contract_sha256(
    value: dict[str, Any],
) -> str:

    return hashlib.sha256(
        canonical_json(
            value
        ).encode(
            "utf-8"
        )
    ).hexdigest()


class ModelContract:
    def __init__(
        self,
        value: dict[str, Any],
    ) -> None:

        self.value = value
        self.validate()

    @classmethod
    def from_path(
        cls,
        path: Path,
    ) -> "ModelContract":

        path = (
            Path(path)
            .expanduser()
            .resolve()
        )

        if not path.is_file():
            raise ModelContractError(
                "Model contract inexistente."
            )

        try:
            value = json.loads(
                path.read_text(
                    encoding="utf-8-sig"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            raise ModelContractError(
                "Model contract JSON invalido."
            ) from error

        if not isinstance(
            value,
            dict,
        ):
            raise ModelContractError(
                "Model contract precisa "
                "ser objeto JSON."
            )

        return cls(
            value
        )

    @staticmethod
    def _dict(
        value: dict[str, Any],
        key: str,
    ) -> dict[str, Any]:

        selected = value.get(
            key
        )

        if not isinstance(
            selected,
            dict,
        ):
            raise ModelContractError(
                f"{key} precisa ser objeto."
            )

        return selected

    def validate(
        self,
    ) -> None:

        value = self.value

        if (
            value.get(
                "schema_version"
            )
            != MODEL_CONTRACT_SCHEMA_VERSION
        ):
            raise ModelContractError(
                "Schema version invalida."
            )

        if (
            value.get(
                "model_id"
            )
            != RACHEL_MODEL_ID
        ):
            raise ModelContractError(
                "Model ID invalido."
            )

        if (
            value.get(
                "model_kind"
            )
            != "specialized-adapter"
        ):
            raise ModelContractError(
                "Rachel v0.1 precisa ser "
                "specialized-adapter."
            )

        base = self._dict(
            value,
            "base_model",
        )

        inference = self._dict(
            value,
            "current_inference_runtime",
        )

        backend = self._dict(
            value,
            "training_backend",
        )

        specialization = self._dict(
            value,
            "specialization",
        )

        dataset = self._dict(
            value,
            "dataset_policy",
        )

        execution = self._dict(
            value,
            "execution_policy",
        )

        hardware = self._dict(
            value,
            "current_machine_audit",
        )

        invariants = self._dict(
            value,
            "safety_invariants",
        )

        if (
            base.get(
                "selection_state"
            )
            not in {
                "unselected",
                "selected",
            }
        ):
            raise ModelContractError(
                "Base model selection_state invalido."
            )

        if (
            base.get(
                "selection_state"
            )
            == "unselected"
            and base.get(
                "training_checkpoint"
            )
            is not None
        ):
            raise ModelContractError(
                "Base nao selecionada nao pode "
                "ter checkpoint definido."
            )

        if (
            inference.get(
                "role"
            )
            != "temporary-inference-provider"
        ):
            raise ModelContractError(
                "Runtime atual precisa permanecer "
                "provider temporario."
            )

        if bool(
            inference.get(
                "is_rachel_model"
            )
        ):
            raise ModelContractError(
                "Modelo Ollama atual nao pode ser "
                "marcado como Rachel Model."
            )

        if bool(
            inference.get(
                "is_training_base"
            )
        ):
            raise ModelContractError(
                "Runtime Ollama nao pode ser "
                "assumido como training base."
            )

        if (
            backend.get(
                "primary_method"
            )
            != "lora"
        ):
            raise ModelContractError(
                "Metodo primario v0.1 precisa ser LoRA."
            )

        if bool(
            backend.get(
                "full_finetune_allowed"
            )
        ):
            raise ModelContractError(
                "Full fine-tuning precisa "
                "permanecer bloqueado no v0.1."
            )

        if (
            specialization.get(
                "strategy"
            )
            != "adapter-first"
        ):
            raise ModelContractError(
                "Estrategia v0.1 precisa ser adapter-first."
            )

        phase_1 = self._dict(
            specialization,
            "phase_1",
        )

        if (
            phase_1.get(
                "training_format"
            )
            != "sft"
        ):
            raise ModelContractError(
                "Primeira fase precisa usar SFT."
            )

        if bool(
            phase_1.get(
                "enabled"
            )
        ):
            raise ModelContractError(
                "Fase de treino nao pode "
                "estar habilitada ainda."
            )

        phase_formats = (
            dataset.get(
                "phase_1_trainable_formats"
            )
        )

        if phase_formats != [
            "sft"
        ]:
            raise ModelContractError(
                "Phase 1 trainable formats "
                "precisa ser somente SFT."
            )

        forbidden_execution_flags = (
            "stage12_execution_enabled",
            "training_execution_enabled",
            "automatic_training",
            "automatic_checkpoint_creation",
            "automatic_weight_merge",
            "automatic_model_promotion",
            "automatic_external_export",
        )

        for key in forbidden_execution_flags:
            if bool(
                execution.get(
                    key
                )
            ):
                raise ModelContractError(
                    f"{key} precisa permanecer false."
                )

        if not bool(
            execution.get(
                "cyber_approval_required_for_training"
            )
        ):
            raise ModelContractError(
                "Cyber precisa ser obrigatorio para treino."
            )

        if not bool(
            execution.get(
                "dany_preflight_required"
            )
        ):
            raise ModelContractError(
                "Dany preflight precisa ser obrigatorio."
            )

        if bool(
            hardware.get(
                "local_weight_training_allowed"
            )
        ):
            raise ModelContractError(
                "Hardware audit atual bloqueia treino local."
            )

        required_invariants = (
            "ollama_runtime_is_not_rachel_model",
            "memory_is_not_training",
            "rag_is_not_training",
            "dataset_compilation_is_not_training",
            "no_raw_hidden_chain_of_thought_training",
        )

        for key in required_invariants:
            if not bool(
                invariants.get(
                    key
                )
            ):
                raise ModelContractError(
                    f"Invariante obrigatoria ausente: {key}"
                )

    @property
    def digest(
        self,
    ) -> str:

        return contract_sha256(
            self.value
        )

    def status(
        self,
    ) -> dict[str, Any]:

        base = self.value[
            "base_model"
        ]

        inference = self.value[
            "current_inference_runtime"
        ]

        backend = self.value[
            "training_backend"
        ]

        specialization = self.value[
            "specialization"
        ]

        execution = self.value[
            "execution_policy"
        ]

        hardware = self.value[
            "current_machine_audit"
        ]

        return {
            "model_id": (
                self.value[
                    "model_id"
                ]
            ),
            "schema_version": (
                self.value[
                    "schema_version"
                ]
            ),
            "status": (
                self.value[
                    "status"
                ]
            ),
            "model_kind": (
                self.value[
                    "model_kind"
                ]
            ),
            "contract_sha256": (
                self.digest
            ),
            "base_model_selection": (
                base[
                    "selection_state"
                ]
            ),
            "training_checkpoint": (
                base[
                    "training_checkpoint"
                ]
            ),
            "current_inference_model": (
                inference[
                    "model"
                ]
            ),
            "current_inference_role": (
                inference[
                    "role"
                ]
            ),
            "primary_training_method": (
                backend[
                    "primary_method"
                ]
            ),
            "strategy": (
                specialization[
                    "strategy"
                ]
            ),
            "phase_1_format": (
                specialization[
                    "phase_1"
                ][
                    "training_format"
                ]
            ),
            "local_weight_training_allowed": (
                hardware[
                    "local_weight_training_allowed"
                ]
            ),
            "training_execution_enabled": (
                execution[
                    "training_execution_enabled"
                ]
            ),
            "automatic_training": (
                execution[
                    "automatic_training"
                ]
            ),
            "checkpoint_created": False,
            "weights_modified": False,
        }