from __future__ import annotations

import json
import sys

from typing import Any

from runtime_paths import CORE_SRC, STATE

if str(CORE_SRC) not in sys.path:
    sys.path.insert(
        0,
        str(CORE_SRC),
    )

from rachel_core.dataset_factory import (
    DatasetFactory,
)

from cognitive_runtime import (
    DanyEvaluator,
)

from security_runtime import (
    ApprovalStore,
)

from team_runtime import (
    CyberPolicy,
)


DATASET_EXPORT_TOOL = (
    "learning.dataset.approve_export"
)

DATASET_EXPORT_EFFECT = (
    "publish"
)


class DatasetReviewError(
    RuntimeError
):
    pass


class LearningDatasetReviewService:
    """
    Gate Dany + Cyber para datasets.

    Nenhuma operacao deste servico
    executa treinamento ou exportacao.
    """

    def __init__(
        self,
        *,
        factory: DatasetFactory | None = None,
        approvals: ApprovalStore | None = None,
        evaluator: Any | None = None,
        cyber: CyberPolicy | None = None,
    ) -> None:

        self.factory = (
            factory
            or DatasetFactory(
                STATE
                / "learning-datasets"
            )
        )

        self.approvals = (
            approvals
            or ApprovalStore()
        )

        self.evaluator = (
            evaluator
            or DanyEvaluator()
        )

        self.cyber = (
            cyber
            or CyberPolicy()
        )

    def _version(
        self,
        version_id: str,
    ) -> dict[str, Any]:

        version = (
            self.factory
            .get_version(
                version_id
            )
        )

        if version is None:
            raise DatasetReviewError(
                "Dataset version nao encontrada."
            )

        return version

    @staticmethod
    def _arguments(
        version: dict[str, Any],
    ) -> dict[str, Any]:

        return {
            "version_id": (
                version["id"]
            ),
            "dataset_type": (
                version["dataset_type"]
            ),
            "content_hash": (
                version["content_hash"]
            ),
            "item_count": int(
                version["item_count"]
            ),
            "target_state": (
                "approved-for-export"
            ),
        }

    def review(
        self,
        version_id: str,
    ) -> dict[str, Any]:

        version = self._version(
            version_id
        )

        integrity = (
            self.factory
            .verify_version(
                version_id
            )
        )

        items = (
            self.factory
            .load_version_items(
                version_id
            )
        )

        reports = []

        for item in items:
            payload = json.dumps(
                item.get(
                    "payload"
                ),
                ensure_ascii=False,
                sort_keys=True,
            )

            reports.append(
                self.evaluator
                .evaluate(
                    payload
                )
            )

        accepted = (
            bool(reports)
            and all(
                bool(
                    report.accepted
                )
                for report
                in reports
            )
        )

        scores = [
            int(report.score)
            for report
            in reports
        ]

        issues = sorted(
            {
                str(issue)
                for report
                in reports
                for issue
                in report.issues
            }
        )

        checks: dict[
            str,
            bool
        ] = {}

        for report in reports:
            for name, passed in (
                report.checks.items()
            ):
                key = str(name)

                checks[key] = (
                    checks.get(
                        key,
                        True,
                    )
                    and bool(passed)
                )

        minimum_score = (
            min(scores)
            if scores
            else 0
        )

        average_score = (
            round(
                sum(scores)
                / len(scores)
            )
            if scores
            else 0
        )

        return {
            "version_id": version_id,
            "dataset_type": (
                version["dataset_type"]
            ),
            "state": (
                version["state"]
            ),
            "content_hash": (
                version["content_hash"]
            ),
            "item_count": (
                len(items)
            ),
            "integrity": integrity,
            "dany": {
                "accepted": accepted,
                "minimum_score": (
                    minimum_score
                ),
                "average_score": (
                    average_score
                ),
                "issues": issues,
                "checks": checks,
            },
            "automatic_training": False,
            "automatic_promotion": False,
            "external_export": False,
        }

    def request_export(
        self,
        version_id: str,
    ) -> dict[str, Any]:

        version = self._version(
            version_id
        )

        if (
            version["state"]
            != "candidate"
        ):
            raise DatasetReviewError(
                "Somente dataset candidate "
                "pode solicitar promocao."
            )

        review = self.review(
            version_id
        )

        if not review["dany"]["accepted"]:
            raise DatasetReviewError(
                "Dany rejeitou "
                "a versao do dataset."
            )

        decision = self.cyber.check(
            DATASET_EXPORT_EFFECT
        )

        if (
            decision.allowed
            or not decision.approval_required
        ):
            raise DatasetReviewError(
                "Cyber policy inesperada "
                "para publish."
            )

        approval = (
            self.approvals
            .request(
                DATASET_EXPORT_TOOL,
                DATASET_EXPORT_EFFECT,
                decision.risk,
                self._arguments(
                    version
                ),
                (
                    "Autorizar promocao "
                    "de dataset candidate "
                    "para approved-for-export."
                ),
            )
        )

        return {
            "state": (
                "approval_required"
            ),
            "version_id": (
                version_id
            ),
            "review": review,
            "approval": approval,
            "automatic_promotion": False,
            "external_export": False,
        }

    def approve_export(
        self,
        version_id: str,
        approval_id: str,
    ) -> dict[str, Any]:

        version = self._version(
            version_id
        )

        if (
            version["state"]
            != "candidate"
        ):
            raise DatasetReviewError(
                "Dataset nao esta "
                "mais em candidate."
            )

        review = self.review(
            version_id
        )

        if not review["dany"]["accepted"]:
            raise DatasetReviewError(
                "Dany rejeitou a versao."
            )

        consumed = (
            self.approvals
            .consume(
                approval_id,
                DATASET_EXPORT_TOOL,
                DATASET_EXPORT_EFFECT,
                self._arguments(
                    version
                ),
            )
        )

        transition = (
            self.factory
            .record_review_transition(
                version_id,
                target_state=(
                    "approved-for-export"
                ),
                reviewer="dany+cyber",
                dany_accepted=True,
                dany_score=int(
                    review[
                        "dany"
                    ][
                        "minimum_score"
                    ]
                ),
                dany_issues=list(
                    review[
                        "dany"
                    ][
                        "issues"
                    ]
                ),
                dany_checks=dict(
                    review[
                        "dany"
                    ][
                        "checks"
                    ]
                ),
                authorization=(
                    "cyber-consumed"
                ),
            )
        )

        return {
            "state": (
                "approved-for-export"
            ),
            "version": (
                transition["version"]
            ),
            "review": review,
            "cyber": {
                "status": (
                    consumed["status"]
                ),
                "effect": (
                    consumed["effect"]
                ),
                "risk": (
                    consumed["risk"]
                ),
            },
            "automatic_training": False,
            "external_export": False,
        }

    def status(
        self,
        limit: int = 100,
    ) -> dict[str, Any]:

        versions = (
            self.factory
            .list_versions(
                limit=limit
            )
        )

        states: dict[
            str,
            int
        ] = {}

        for version in versions:
            state = str(
                version["state"]
            )

            states[state] = (
                states.get(
                    state,
                    0,
                )
                + 1
            )

        return {
            "status": "ok",
            "versions": len(
                versions
            ),
            "states": states,
            "automatic_training": False,
            "automatic_promotion": False,
            "external_export": False,
        }