from __future__ import annotations

import sys

from typing import Any

from runtime_paths import (
    CORE_SRC,
    STATE,
)

if str(CORE_SRC) not in sys.path:
    sys.path.insert(
        0,
        str(CORE_SRC),
    )


from rachel_core.dataset_export import (
    DatasetExportFactory,
)

from rachel_core.training_dataset_compiler import (
    TrainingDatasetCompiler,
)

from security_runtime import (
    ApprovalStore,
)

from team_runtime import (
    CyberPolicy,
)


TRAINING_COMPILE_TOOL = (
    "learning.training_dataset.compile"
)

TRAINING_COMPILE_EFFECT = (
    "write"
)


class TrainingDatasetRuntimeError(
    RuntimeError
):
    pass


class TrainingDatasetService:
    """
    Gate Cyber para compilacao de datasets treinaveis.

    A compilacao e preparacao de dados.
    Nao e treinamento.
    """

    def __init__(
        self,
        *,
        exporter: DatasetExportFactory | None = None,
        compiler: TrainingDatasetCompiler | None = None,
        approvals: ApprovalStore | None = None,
        cyber: CyberPolicy | None = None,
    ) -> None:

        self.exporter = (
            exporter
            or DatasetExportFactory(
                STATE
                / "training-exports"
            )
        )

        self.compiler = (
            compiler
            or TrainingDatasetCompiler(
                self.exporter,
                STATE
                / "compiled-training",
            )
        )

        self.approvals = (
            approvals
            or ApprovalStore()
        )

        self.cyber = (
            cyber
            or CyberPolicy()
        )

    @staticmethod
    def _arguments(
        plan: dict[
            str,
            Any
        ],
    ) -> dict[str, Any]:

        return {
            "compiled_id": (
                plan[
                    "compiled_id"
                ]
            ),
            "source_export_id": (
                plan[
                    "source_export_id"
                ]
            ),
            "source_version_id": (
                plan[
                    "source_version_id"
                ]
            ),
            "source_dataset_type": (
                plan[
                    "source_dataset_type"
                ]
            ),
            "training_format": (
                plan[
                    "training_format"
                ]
            ),
            "compiler_version": (
                plan[
                    "compiler_version"
                ]
            ),
            "train_count": (
                plan[
                    "train_count"
                ]
            ),
            "eval_count": (
                plan[
                    "eval_count"
                ]
            ),
            "destination": (
                "compiled-training"
            ),
        }

    def plan(
        self,
        export_id: str,
        *,
        training_format: str | None = None,
    ) -> dict[str, Any]:

        return (
            self.compiler
            .plan(
                export_id,
                training_format=(
                    training_format
                ),
            )
        )

    def request_compile(
        self,
        export_id: str,
        *,
        training_format: str | None = None,
    ) -> dict[str, Any]:

        plan = self.plan(
            export_id,
            training_format=(
                training_format
            ),
        )

        decision = self.cyber.check(
            TRAINING_COMPILE_EFFECT
        )

        if (
            decision.allowed
            or not decision
            .approval_required
        ):
            raise TrainingDatasetRuntimeError(
                "Cyber policy inesperada "
                "para write."
            )

        approval = (
            self.approvals
            .request(
                TRAINING_COMPILE_TOOL,
                TRAINING_COMPILE_EFFECT,
                decision.risk,
                self._arguments(
                    plan
                ),
                (
                    "Autorizar compilacao local "
                    "de dataset para formato "
                    "de treinamento."
                ),
            )
        )

        return {
            "state": (
                "approval_required"
            ),
            "plan": plan,
            "approval": approval,
            "automatic_training": False,
            "checkpoint_created": False,
            "external_export": False,
        }

    def compile(
        self,
        export_id: str,
        approval_id: str,
        *,
        training_format: str | None = None,
    ) -> dict[str, Any]:

        plan = self.plan(
            export_id,
            training_format=(
                training_format
            ),
        )

        consumed = (
            self.approvals
            .consume(
                approval_id,
                TRAINING_COMPILE_TOOL,
                TRAINING_COMPILE_EFFECT,
                self._arguments(
                    plan
                ),
            )
        )

        result = (
            self.compiler
            .compile(
                export_id,
                training_format=(
                    training_format
                ),
            )
        )

        verification = (
            self.compiler
            .verify(
                result[
                    "id"
                ]
            )
        )

        return {
            "state": (
                "compiled-local"
            ),
            "compiled": result,
            "integrity": verification,
            "cyber": {
                "status": (
                    consumed[
                        "status"
                    ]
                ),
                "effect": (
                    consumed[
                        "effect"
                    ]
                ),
                "risk": (
                    consumed[
                        "risk"
                    ]
                ),
            },
            "automatic_training": False,
            "checkpoint_created": False,
            "external_export": False,
        }

    def status(
        self,
    ) -> dict[str, Any]:

        return (
            self.compiler
            .status()
        )