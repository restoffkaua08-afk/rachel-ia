from __future__ import annotations

import sys

from pathlib import Path
from typing import Any


from runtime_paths import (
    CONFIG,
    CORE_SRC,
)

if str(CORE_SRC) not in sys.path:
    sys.path.insert(
        0,
        str(CORE_SRC),
    )


from rachel_core.model_contract import (
    ModelContract,
)

from rachel_core.training_run_planner import (
    TrainingRunPlanner,
)

from model_runtime import (
    RachelModelRuntime,
)


class TrainingRunRuntime:
    """
    Runtime somente leitura para planejamento
    da futura execucao de treinamento.
    """

    def __init__(
        self,
        *,
        contract_path: Path | None = None,
        profiles_path: Path | None = None,
        model_runtime: Any | None = None,
    ) -> None:
        self.contract_path = (
            Path(
                contract_path
                or (
                    CONFIG
                    / "rachel-model-v0.1.json"
                )
            )
            .expanduser()
            .resolve()
        )

        self.profiles_path = (
            Path(
                profiles_path
                or (
                    CONFIG
                    / "training-hardware-profiles.json"
                )
            )
            .expanduser()
            .resolve()
        )

        self.contract = (
            ModelContract.from_path(
                self.contract_path
            )
        )

        self.planner = (
            TrainingRunPlanner(
                contract=self.contract,
                profiles_path=(
                    self.profiles_path
                ),
            )
        )

        self.model_runtime = (
            model_runtime
            or RachelModelRuntime(
                contract_path=(
                    self.contract_path
                )
            )
        )

    def preview(
        self,
        profile_id: str = (
            "qwen3-1.7b-lora-minimum"
        ),
    ) -> dict[str, Any]:
        model_status = (
            self.model_runtime.status()
        )

        return {
            "template": (
                self.planner.template(
                    profile_id
                )
            ),
            "model_blockers": (
                model_status[
                    "blockers"
                ]
            ),
            "training_data_available": (
                model_status[
                    "training_preflight"
                ][
                    "training_data_available"
                ]
            ),
            "can_create_executable_plan": (
                False
            ),
            "can_train_weights": (
                False
            ),
            "planner_only": True,
            "automatic_install": False,
            "automatic_download": False,
            "automatic_training": False,
            "checkpoint_created": False,
            "weights_modified": False,
        }

    def status(
        self,
    ) -> dict[str, Any]:
        planner_status = (
            self.planner.status()
        )

        model_status = (
            self.model_runtime.status()
        )

        return {
            "planner": planner_status,
            "model": (
                model_status[
                    "model"
                ]
            ),
            "model_blockers": (
                model_status[
                    "blockers"
                ]
            ),
            "pipeline_ready": (
                model_status[
                    "training_preflight"
                ][
                    "pipeline_ready"
                ]
            ),
            "training_data_available": (
                model_status[
                    "training_preflight"
                ][
                    "training_data_available"
                ]
            ),
            "current_machine_minimum_eligible": (
                planner_status[
                    "minimum_profile"
                ][
                    "eligible"
                ]
            ),
            "current_machine_recommended_eligible": (
                planner_status[
                    "recommended_profile"
                ][
                    "eligible"
                ]
            ),
            "can_train_weights": False,
            "training_execution_enabled": False,
            "automatic_install": False,
            "automatic_download": False,
            "automatic_training": False,
            "checkpoint_created": False,
            "weights_modified": False,
            "external_export": False,
        }