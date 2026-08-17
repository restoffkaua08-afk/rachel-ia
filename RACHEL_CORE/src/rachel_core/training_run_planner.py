from __future__ import annotations

import hashlib
import json

from pathlib import Path
from typing import Any

from rachel_core.model_contract import (
    ModelContract,
)


TRAINING_RUN_SCHEMA_VERSION = 1
TRAINING_RUN_PLANNER_VERSION = "rachel-training-run-planner-v1"


class TrainingRunPlannerError(
    RuntimeError
):
    pass


def _canonical_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256(
    value: Any,
) -> str:
    return hashlib.sha256(
        _canonical_json(
            value
        ).encode("utf-8")
    ).hexdigest()


class TrainingRunPlanner:
    """
    Planeja uma futura execucao de treinamento.

    Nao instala dependencias.
    Nao baixa pesos.
    Nao cria checkpoint.
    Nao executa LitGPT.
    Nao altera pesos.
    """

    def __init__(
        self,
        *,
        contract: ModelContract,
        profiles_path: Path,
    ) -> None:
        self.contract = contract

        self.profiles_path = (
            Path(profiles_path)
            .expanduser()
            .resolve()
        )

        self.profiles = (
            self._load_profiles()
        )

    def _load_profiles(
        self,
    ) -> dict[str, Any]:
        if not self.profiles_path.is_file():
            raise TrainingRunPlannerError(
                "Hardware profiles ausentes."
            )

        try:
            value = json.loads(
                self.profiles_path.read_text(
                    encoding="utf-8-sig"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            raise TrainingRunPlannerError(
                "Hardware profiles invalidos."
            ) from error

        if not isinstance(value, dict):
            raise TrainingRunPlannerError(
                "Hardware profiles precisam ser objeto."
            )

        if value.get("schema_version") != 1:
            raise TrainingRunPlannerError(
                "Hardware profile schema invalido."
            )

        profiles = value.get("profiles")

        if not isinstance(profiles, dict):
            raise TrainingRunPlannerError(
                "Profiles ausentes."
            )

        required = {
            "current-cpu-blocked",
            "qwen3-1.7b-lora-minimum",
            "qwen3-1.7b-lora-recommended",
        }

        if not required.issubset(
            set(profiles)
        ):
            raise TrainingRunPlannerError(
                "Hardware profiles obrigatorios ausentes."
            )

        return value

    def profile(
        self,
        profile_id: str,
    ) -> dict[str, Any]:
        profiles = self.profiles[
            "profiles"
        ]

        value = profiles.get(
            profile_id
        )

        if not isinstance(value, dict):
            raise TrainingRunPlannerError(
                "Hardware profile desconhecido."
            )

        return value

    def list_profiles(
        self,
    ) -> list[dict[str, Any]]:
        result = []

        for profile_id in sorted(
            self.profiles["profiles"]
        ):
            value = self.profile(
                profile_id
            )

            result.append(
                {
                    "id": profile_id,
                    "kind": value.get("kind"),
                    "description": value.get(
                        "description"
                    ),
                    "training_candidate": bool(
                        value.get(
                            "training_candidate"
                        )
                    ),
                    "requirements": value.get(
                        "requirements"
                    ),
                    "recipe": value.get(
                        "recipe"
                    ),
                }
            )

        return result

    def current_hardware(
        self,
    ) -> dict[str, Any]:
        audit = self.contract.value[
            "current_machine_audit"
        ]

        return {
            "nvidia_cuda": bool(
                audit.get(
                    "nvidia_cuda_gpu"
                )
            ),
            "torch_cuda": bool(
                audit.get(
                    "torch_cuda_available"
                )
            ),
            "vram_gb": 0.0,
            "ram_gb": float(
                audit.get(
                    "ram_gb",
                    0.0,
                )
            ),
            "free_disk_gb": float(
                audit.get(
                    "disk_free_gb_at_audit",
                    0.0,
                )
            ),
            "weight_training_allowed": bool(
                audit.get(
                    "local_weight_training_allowed"
                )
            ),
        }

    def evaluate_hardware(
        self,
        profile_id: str,
        observed: dict[str, Any],
    ) -> dict[str, Any]:
        profile = self.profile(
            profile_id
        )

        requirements = profile.get(
            "requirements"
        )

        if not isinstance(
            requirements,
            dict,
        ):
            raise TrainingRunPlannerError(
                "Profile requirements invalidos."
            )

        blockers: list[str] = []

        if bool(
            requirements.get(
                "nvidia_cuda"
            )
        ) and not bool(
            observed.get(
                "nvidia_cuda"
            )
        ):
            blockers.append(
                "nvidia-cuda-required"
            )

        if bool(
            requirements.get(
                "torch_cuda"
            )
        ) and not bool(
            observed.get(
                "torch_cuda"
            )
        ):
            blockers.append(
                "torch-cuda-required"
            )

        if float(
            observed.get(
                "vram_gb",
                0.0,
            )
        ) < float(
            requirements.get(
                "min_vram_gb",
                0.0,
            )
        ):
            blockers.append(
                "vram-below-policy"
            )

        if float(
            observed.get(
                "ram_gb",
                0.0,
            )
        ) < float(
            requirements.get(
                "min_ram_gb",
                0.0,
            )
        ):
            blockers.append(
                "ram-below-policy"
            )

        if float(
            observed.get(
                "free_disk_gb",
                0.0,
            )
        ) < float(
            requirements.get(
                "min_free_disk_gb",
                0.0,
            )
        ):
            blockers.append(
                "disk-below-policy"
            )

        return {
            "profile_id": profile_id,
            "training_candidate": bool(
                profile.get(
                    "training_candidate"
                )
            ),
            "requirements": requirements,
            "observed": observed,
            "blockers": blockers,
            "eligible": (
                bool(
                    profile.get(
                        "training_candidate"
                    )
                )
                and len(blockers) == 0
            ),
        }

    @staticmethod
    def _validate_dataset(
        compiled_dataset: dict[str, Any],
    ) -> None:
        if not isinstance(
            compiled_dataset,
            dict,
        ):
            raise TrainingRunPlannerError(
                "Compiled dataset invalido."
            )

        if not str(
            compiled_dataset.get(
                "id"
            )
            or ""
        ).strip():
            raise TrainingRunPlannerError(
                "Compiled dataset ID ausente."
            )

        if (
            compiled_dataset.get(
                "state"
            )
            != "compiled-local"
        ):
            raise TrainingRunPlannerError(
                "Dataset precisa estar compiled-local."
            )

        if (
            compiled_dataset.get(
                "training_format"
            )
            != "sft"
        ):
            raise TrainingRunPlannerError(
                "Rachel Model v0.1 Phase 1 aceita somente SFT."
            )

        if not bool(
            compiled_dataset.get(
                "integrity"
            )
        ):
            raise TrainingRunPlannerError(
                "Dataset integrity precisa estar valida."
            )

        if int(
            compiled_dataset.get(
                "train_count",
                0,
            )
        ) <= 0:
            raise TrainingRunPlannerError(
                "Dataset precisa conter itens de treino."
            )

        if int(
            compiled_dataset.get(
                "eval_count",
                0,
            )
        ) < 0:
            raise TrainingRunPlannerError(
                "eval_count invalido."
            )

    def template(
        self,
        profile_id: str = (
            "qwen3-1.7b-lora-minimum"
        ),
    ) -> dict[str, Any]:
        profile = self.profile(
            profile_id
        )

        base = self.contract.value[
            "base_model"
        ]

        return {
            "schema_version": (
                TRAINING_RUN_SCHEMA_VERSION
            ),
            "planner_version": (
                TRAINING_RUN_PLANNER_VERSION
            ),
            "model_id": (
                self.contract.value[
                    "model_id"
                ]
            ),
            "base_model": (
                base.get(
                    "repository"
                )
            ),
            "base_weights_state": (
                base.get(
                    "source_weights_state"
                )
            ),
            "checkpoint_state": (
                base.get(
                    "checkpoint_state"
                )
            ),
            "profile_id": profile_id,
            "requirements": profile.get(
                "requirements"
            ),
            "recipe": profile.get(
                "recipe"
            ),
            "training_format": "sft",
            "planner_only": True,
            "training_started": False,
            "checkpoint_created": False,
            "weights_modified": False,
        }

    def plan(
        self,
        compiled_dataset: dict[str, Any],
        *,
        profile_id: str = (
            "qwen3-1.7b-lora-minimum"
        ),
        observed_hardware: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._validate_dataset(
            compiled_dataset
        )

        profile = self.profile(
            profile_id
        )

        if not bool(
            profile.get(
                "training_candidate"
            )
        ):
            raise TrainingRunPlannerError(
                "Profile nao pode executar treino."
            )

        recipe = profile.get(
            "recipe"
        )

        if not isinstance(
            recipe,
            dict,
        ):
            raise TrainingRunPlannerError(
                "Recipe ausente."
            )

        observed = (
            observed_hardware
            or self.current_hardware()
        )

        hardware = self.evaluate_hardware(
            profile_id,
            observed,
        )

        base = self.contract.value[
            "base_model"
        ]

        execution = self.contract.value[
            "execution_policy"
        ]

        blockers = list(
            hardware[
                "blockers"
            ]
        )

        if (
            base.get(
                "source_weights_state"
            )
            != "downloaded"
        ):
            blockers.append(
                "base-weights-not-downloaded"
            )

        if (
            base.get(
                "checkpoint_state"
            )
            != "litgpt-ready"
            or not base.get(
                "training_checkpoint"
            )
        ):
            blockers.append(
                "base-checkpoint-not-ready"
            )

        if not bool(
            execution.get(
                "training_execution_enabled"
            )
        ):
            blockers.append(
                "training-execution-disabled"
            )

        if not bool(
            execution.get(
                "dany_preflight_required"
            )
        ):
            blockers.append(
                "dany-preflight-policy-missing"
            )

        if not bool(
            execution.get(
                "cyber_approval_required_for_training"
            )
        ):
            blockers.append(
                "cyber-training-policy-missing"
            )

        unique_blockers = sorted(
            set(blockers)
        )

        plan_identity = {
            "planner_version": (
                TRAINING_RUN_PLANNER_VERSION
            ),
            "model_id": (
                self.contract.value[
                    "model_id"
                ]
            ),
            "contract_sha256": (
                self.contract.digest
            ),
            "base_model": (
                base.get(
                    "repository"
                )
            ),
            "compiled_dataset_id": (
                compiled_dataset[
                    "id"
                ]
            ),
            "compiled_dataset_hash": (
                compiled_dataset.get(
                    "train_sha256"
                )
            ),
            "profile_id": profile_id,
            "recipe": recipe,
        }

        plan_hash = _sha256(
            plan_identity
        )

        run_id = (
            "rachel-model-v0.1-run-"
            + plan_hash[:16]
        )

        return {
            "schema_version": (
                TRAINING_RUN_SCHEMA_VERSION
            ),
            "planner_version": (
                TRAINING_RUN_PLANNER_VERSION
            ),
            "run_id": run_id,
            "plan_sha256": plan_hash,
            "state": (
                "planned-ready"
                if len(unique_blockers) == 0
                else "planned-blocked"
            ),
            "model_id": (
                self.contract.value[
                    "model_id"
                ]
            ),
            "base_model": (
                base.get(
                    "repository"
                )
            ),
            "compiled_dataset": {
                "id": compiled_dataset[
                    "id"
                ],
                "training_format": (
                    compiled_dataset[
                        "training_format"
                    ]
                ),
                "train_count": int(
                    compiled_dataset[
                        "train_count"
                    ]
                ),
                "eval_count": int(
                    compiled_dataset[
                        "eval_count"
                    ]
                ),
                "train_sha256": (
                    compiled_dataset.get(
                        "train_sha256"
                    )
                ),
                "eval_sha256": (
                    compiled_dataset.get(
                        "eval_sha256"
                    )
                ),
            },
            "hardware": hardware,
            "profile_id": profile_id,
            "recipe": recipe,
            "blockers": unique_blockers,
            "execution_allowed": (
                len(unique_blockers) == 0
            ),
            "planner_only": True,
            "files_written": False,
            "weights_downloaded": False,
            "training_started": False,
            "checkpoint_created": False,
            "weights_modified": False,
            "external_export": False,
        }

    def status(
        self,
    ) -> dict[str, Any]:
        current = self.current_hardware()

        minimum = self.evaluate_hardware(
            "qwen3-1.7b-lora-minimum",
            current,
        )

        recommended = self.evaluate_hardware(
            "qwen3-1.7b-lora-recommended",
            current,
        )

        return {
            "schema_version": (
                TRAINING_RUN_SCHEMA_VERSION
            ),
            "planner_version": (
                TRAINING_RUN_PLANNER_VERSION
            ),
            "model_id": (
                self.contract.value[
                    "model_id"
                ]
            ),
            "profiles": (
                self.list_profiles()
            ),
            "current_hardware": current,
            "minimum_profile": minimum,
            "recommended_profile": recommended,
            "planner_only": True,
            "automatic_install": False,
            "automatic_download": False,
            "automatic_training": False,
            "checkpoint_created": False,
            "weights_modified": False,
        }