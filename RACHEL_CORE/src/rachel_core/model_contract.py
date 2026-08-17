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
            base.get(
                "selection_state"
            )
            == "selected"
        ):
            required_base = {
                "provider": "huggingface",
                "repository": "Qwen/Qwen3-1.7B-Base",
                "family": "Qwen3",
                "architecture": "qwen3",
                "variant": "base",
                "license": "apache-2.0",
                "training_checkpoint_format": "litgpt-native",
            }

            for key, expected in required_base.items():
                if base.get(key) != expected:
                    raise ModelContractError(
                        "Training base invalida: "
                        f"{key}."
                    )

            if float(
                base.get(
                    "parameter_scale_b",
                    0,
                )
            ) != 1.7:
                raise ModelContractError(
                    "Parameter scale da base invalida."
                )

            support = base.get(
                "litgpt_support"
            )

            if not isinstance(
                support,
                dict,
            ):
                raise ModelContractError(
                    "LitGPT support ausente."
                )

            if not bool(
                support.get(
                    "verified"
                )
            ):
                raise ModelContractError(
                    "LitGPT support nao verificado."
                )

            if (
                support.get(
                    "pinned_commit"
                )
                != (
                    "7bf2960dfb26bae8e815c9a16a22732974824ac1"
                )
            ):
                raise ModelContractError(
                    "LitGPT pinned commit invalido."
                )

            weights_state = base.get(
                "source_weights_state"
            )

            checkpoint_state = base.get(
                "checkpoint_state"
            )

            if weights_state not in {
                "not-downloaded",
                "downloaded",
            }:
                raise ModelContractError(
                    "source_weights_state invalido."
                )

            if checkpoint_state not in {
                "not-created",
                "litgpt-ready",
            }:
                raise ModelContractError(
                    "checkpoint_state invalido."
                )

            if (
                weights_state
                == "not-downloaded"
                and base.get(
                    "training_checkpoint"
                )
                is not None
            ):
                raise ModelContractError(
                    "Pesos nao baixados nao podem "
                    "ter training checkpoint."
                )

            if (
                checkpoint_state
                == "litgpt-ready"
                and not base.get(
                    "training_checkpoint"
                )
            ):
                raise ModelContractError(
                    "Checkpoint litgpt-ready precisa "
                    "de caminho."
                )

            if bool(
                base.get(
                    "weights_download_allowed"
                )
            ):
                raise ModelContractError(
                    "Download de pesos precisa "
                    "permanecer bloqueado no 1C."
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
            "base_model_repository": (
                base.get(
                    "repository"
                )
            ),
            "base_model_family": (
                base.get(
                    "family"
                )
            ),
            "base_model_variant": (
                base.get(
                    "variant"
                )
            ),
            "base_model_license": (
                base.get(
                    "license"
                )
            ),
            "base_model_parameter_scale_b": (
                base.get(
                    "parameter_scale_b"
                )
            ),
            "source_weights_state": (
                base.get(
                    "source_weights_state"
                )
            ),
            "checkpoint_state": (
                base.get(
                    "checkpoint_state"
                )
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