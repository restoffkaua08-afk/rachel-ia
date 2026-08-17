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

from training_preflight_runtime import (
    TrainingPreflight,
)


class RachelModelRuntime:
    """
    Estado e guardrails do Rachel Model v0.1.

    Este service nao executa treino.
    """

    def __init__(
        self,
        *,
        contract_path: Path | None = None,
        preflight: Any | None = None,
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

        self.contract = (
            ModelContract
            .from_path(
                self.contract_path
            )
        )

        self.preflight = (
            preflight
            or TrainingPreflight()
        )

    def blockers(
        self,
    ) -> list[str]:

        value = self.contract.value

        base = value[
            "base_model"
        ]

        audit = value[
            "current_machine_audit"
        ]

        execution = value[
            "execution_policy"
        ]

        report = (
            self.preflight
            .report(
                limit=200
            )
        )

        blockers: list[str] = []

        if (
            base[
                "selection_state"
            ]
            != "selected"
        ):
            blockers.append(
                "base-model-unselected"
            )

        if not bool(
            report[
                "training_data_available"
            ]
        ):
            blockers.append(
                "training-data-unavailable"
            )

        if not bool(
            report[
                "training_backend_available"
            ]
        ):
            blockers.append(
                "training-backend-unavailable"
            )

        if not bool(
            audit[
                "torch_installed"
            ]
        ):
            blockers.append(
                "ml-stack-not-provisioned"
            )

        if not bool(
            audit[
                "local_weight_training_allowed"
            ]
        ):
            blockers.append(
                "current-hardware-weight-training-blocked"
            )

        if not bool(
            execution[
                "training_execution_enabled"
            ]
        ):
            blockers.append(
                "training-execution-disabled"
            )

        return blockers

    def status(
        self,
    ) -> dict[str, Any]:

        contract_status = (
            self.contract
            .status()
        )

        preflight = (
            self.preflight
            .report(
                limit=200
            )
        )

        blockers = self.blockers()

        return {
            "model": (
                contract_status
            ),
            "contract_path": (
                str(
                    self.contract_path
                )
            ),
            "training_preflight": (
                preflight
            ),
            "blockers": (
                blockers
            ),
            "can_prepare_datasets": (
                bool(
                    preflight[
                        "pipeline_ready"
                    ]
                )
            ),
            "can_train_weights": (
                len(blockers) == 0
            ),
            "training_execution_enabled": (
                False
            ),
            "automatic_training": (
                False
            ),
            "checkpoint_created": (
                False
            ),
            "weights_modified": (
                False
            ),
            "external_export": (
                False
            ),
        }