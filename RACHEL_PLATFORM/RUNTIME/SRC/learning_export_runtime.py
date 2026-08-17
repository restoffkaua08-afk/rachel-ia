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
    DEFAULT_EVAL_PERCENT,
    DEFAULT_SPLIT_SEED,
    DatasetExportFactory,
)

from rachel_core.dataset_factory import (
    DatasetFactory,
)

from security_runtime import (
    ApprovalStore,
)

from team_runtime import (
    CyberPolicy,
)


DATASET_LOCAL_EXPORT_TOOL = (
    "learning.dataset.export_local"
)

DATASET_LOCAL_EXPORT_EFFECT = (
    "write"
)


class LearningDatasetExportError(
    RuntimeError
):
    pass


class LearningDatasetExportService:
    """
    Materializacao local de dataset treinavel.

    approved-for-export significa elegivel.
    A gravacao train/eval exige um novo
    approval Cyber single-use.

    Nenhum metodo inicia treinamento.
    Nenhum metodo realiza export externo.
    """

    def __init__(
        self,
        *,
        factory: DatasetFactory | None = None,
        exporter: DatasetExportFactory | None = None,
        approvals: ApprovalStore | None = None,
        cyber: CyberPolicy | None = None,
    ) -> None:

        self.factory = (
            factory
            or DatasetFactory(
                STATE
                / "learning-datasets"
            )
        )

        self.exporter = (
            exporter
            or DatasetExportFactory(
                STATE
                / "training-exports"
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

    def _source(
        self,
        version_id: str,
    ) -> tuple[
        dict[str, Any],
        list[dict[str, Any]],
    ]:

        version = (
            self.factory
            .get_version(
                version_id
            )
        )

        if version is None:
            raise LearningDatasetExportError(
                "Dataset version nao encontrada."
            )

        if (
            version[
                "state"
            ]
            != "approved-for-export"
        ):
            raise LearningDatasetExportError(
                "Dataset precisa estar "
                "approved-for-export."
            )

        self.factory.verify_version(
            version_id
        )

        items = (
            self.factory
            .load_version_items(
                version_id
            )
        )

        return (
            version,
            items,
        )

    @staticmethod
    def _arguments(
        plan: dict[
            str,
            Any
        ],
    ) -> dict[str, Any]:

        return {
            "export_id": (
                plan[
                    "export_id"
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
            "source_content_hash": (
                plan[
                    "source_content_hash"
                ]
            ),
            "item_count": (
                plan[
                    "item_count"
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
            "eval_percent": (
                plan[
                    "eval_percent"
                ]
            ),
            "split_seed": (
                plan[
                    "split_seed"
                ]
            ),
            "destination": (
                "local-training-exports"
            ),
        }

    def plan(
        self,
        version_id: str,
        *,
        eval_percent: int = (
            DEFAULT_EVAL_PERCENT
        ),
        split_seed: str = (
            DEFAULT_SPLIT_SEED
        ),
    ) -> dict[str, Any]:

        version, items = (
            self._source(
                version_id
            )
        )

        plan = (
            self.exporter
            .plan_export(
                version,
                items,
                eval_percent=(
                    eval_percent
                ),
                split_seed=(
                    split_seed
                ),
            )
        )

        return {
            **plan,
            "destination": (
                "local-training-exports"
            ),
            "automatic_training": False,
            "external_export": False,
        }

    def request_local_export(
        self,
        version_id: str,
        *,
        eval_percent: int = (
            DEFAULT_EVAL_PERCENT
        ),
        split_seed: str = (
            DEFAULT_SPLIT_SEED
        ),
    ) -> dict[str, Any]:

        plan = self.plan(
            version_id,
            eval_percent=(
                eval_percent
            ),
            split_seed=(
                split_seed
            ),
        )

        decision = self.cyber.check(
            DATASET_LOCAL_EXPORT_EFFECT
        )

        if (
            decision.allowed
            or not decision
            .approval_required
        ):
            raise LearningDatasetExportError(
                "Cyber policy inesperada "
                "para write."
            )

        approval = (
            self.approvals
            .request(
                DATASET_LOCAL_EXPORT_TOOL,
                DATASET_LOCAL_EXPORT_EFFECT,
                decision.risk,
                self._arguments(
                    plan
                ),
                (
                    "Autorizar materializacao "
                    "local de train/eval "
                    "para dataset aprovado."
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
            "external_export": False,
        }

    def export_local(
        self,
        version_id: str,
        approval_id: str,
        *,
        eval_percent: int = (
            DEFAULT_EVAL_PERCENT
        ),
        split_seed: str = (
            DEFAULT_SPLIT_SEED
        ),
    ) -> dict[str, Any]:

        version, items = (
            self._source(
                version_id
            )
        )

        plan = (
            self.exporter
            .plan_export(
                version,
                items,
                eval_percent=(
                    eval_percent
                ),
                split_seed=(
                    split_seed
                ),
            )
        )

        consumed = (
            self.approvals
            .consume(
                approval_id,
                DATASET_LOCAL_EXPORT_TOOL,
                DATASET_LOCAL_EXPORT_EFFECT,
                self._arguments(
                    plan
                ),
            )
        )

        exported = (
            self.exporter
            .create_export(
                version,
                items,
                eval_percent=(
                    eval_percent
                ),
                split_seed=(
                    split_seed
                ),
                metadata={
                    "source": (
                        "rachel-learning-engine"
                    ),
                    "authorization": (
                        "cyber-consumed"
                    ),
                },
            )
        )

        integrity = (
            self.exporter
            .verify_export(
                exported[
                    "id"
                ]
            )
        )

        return {
            "state": (
                "ready-local"
            ),
            "export": exported,
            "integrity": integrity,
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
            "source_state": (
                version[
                    "state"
                ]
            ),
            "automatic_training": False,
            "external_export": False,
        }

    def status(
        self,
    ) -> dict[str, Any]:

        return (
            self.exporter
            .status()
        )