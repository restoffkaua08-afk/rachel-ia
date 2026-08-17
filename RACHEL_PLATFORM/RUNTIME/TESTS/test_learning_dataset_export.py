from __future__ import annotations

import json
import sys
import tempfile
import unittest

from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)

sys.path.insert(
    0,
    str(
        ROOT
        / "RACHEL_PLATFORM"
        / "RUNTIME"
        / "SRC"
    ),
)

sys.path.insert(
    0,
    str(
        ROOT
        / "RACHEL_CORE"
        / "src"
    ),
)


from rachel_core.dataset_export import (
    DatasetExportFactory,
)

from rachel_core.dataset_factory import (
    DatasetFactory,
)

from learning_export_runtime import (
    LearningDatasetExportError,
    LearningDatasetExportService,
)

from security_runtime import (
    ApprovalError,
    ApprovalStore,
)


class LearningDatasetExportTests(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:

        self.temp = (
            tempfile
            .TemporaryDirectory()
        )

        self.root = Path(
            self.temp.name
        )

        self.factory = DatasetFactory(
            self.root
            / "datasets"
        )

        self.exporter = (
            DatasetExportFactory(
                self.root
                / "exports"
            )
        )

        policy = (
            self.root
            / "approval.policy.json"
        )

        policy.write_text(
            json.dumps(
                {
                    "default_ttl_seconds": 300,
                    "maximum_ttl_seconds": 1800,
                }
            ),
            encoding="utf-8",
        )

        self.approvals = (
            ApprovalStore(
                self.root
                / "cyber.db",
                policy,
            )
        )

        self.service = (
            LearningDatasetExportService(
                factory=self.factory,
                exporter=self.exporter,
                approvals=self.approvals,
            )
        )

    def tearDown(
        self,
    ) -> None:
        self.temp.cleanup()

    def version(
        self,
        *,
        approved: bool = True,
        count: int = 10,
    ):
        manifest = (
            self.factory
            .create_version(
                "conversation",
                [
                    {
                        "source_kind": (
                            "experience"
                        ),
                        "source_id": (
                            f"exp_{index}"
                        ),
                        "payload": {
                            "user": (
                                f"pergunta {index}"
                            ),
                            "assistant": (
                                f"resposta {index}"
                            ),
                        },
                        "provenance": {
                            "quality_score": 100,
                            "review_state": (
                                "user_accepted"
                            ),
                        },
                    }
                    for index
                    in range(count)
                ],
            )
        )

        version_id = (
            manifest[
                "version_id"
            ]
        )

        if approved:
            self.factory.record_review_transition(
                version_id,
                target_state=(
                    "approved-for-export"
                ),
                reviewer="test",
                dany_accepted=True,
                dany_score=100,
                dany_issues=[],
                dany_checks={
                    "test": True,
                },
                authorization=(
                    "cyber-consumed"
                ),
            )

        return version_id

    def test_candidate_cannot_request_export(
        self,
    ):
        version_id = self.version(
            approved=False
        )

        with self.assertRaises(
            LearningDatasetExportError
        ):
            self.service.request_local_export(
                version_id
            )

        self.assertEqual(
            [],
            self.approvals.list(
                status="pending"
            ),
        )

    def test_request_uses_cyber_write_approval(
        self,
    ):
        version_id = self.version()

        result = (
            self.service
            .request_local_export(
                version_id,
                eval_percent=20,
                split_seed="stable",
            )
        )

        self.assertEqual(
            "approval_required",
            result[
                "state"
            ],
        )

        self.assertEqual(
            "write",
            result[
                "approval"
            ][
                "effect"
            ],
        )

        self.assertEqual(
            "medium",
            result[
                "approval"
            ][
                "risk"
            ],
        )

        self.assertEqual(
            8,
            result[
                "plan"
            ][
                "train_count"
            ],
        )

        self.assertEqual(
            2,
            result[
                "plan"
            ][
                "eval_count"
            ],
        )

    def test_exact_split_parameters_are_bound(
        self,
    ):
        version_id = self.version()

        pending = (
            self.service
            .request_local_export(
                version_id,
                eval_percent=20,
                split_seed="seed-a",
            )
        )

        approval_id = (
            pending[
                "approval"
            ][
                "id"
            ]
        )

        self.approvals.decide(
            approval_id,
            True,
        )

        with self.assertRaises(
            ApprovalError
        ):
            self.service.export_local(
                version_id,
                approval_id,
                eval_percent=10,
                split_seed="seed-a",
            )

        self.assertEqual(
            0,
            self.exporter
            .status()[
                "exports"
            ],
        )

    def test_approved_request_creates_verified_local_export(
        self,
    ):
        version_id = self.version()

        pending = (
            self.service
            .request_local_export(
                version_id,
                eval_percent=20,
                split_seed="seed-b",
            )
        )

        approval_id = (
            pending[
                "approval"
            ][
                "id"
            ]
        )

        self.approvals.decide(
            approval_id,
            True,
        )

        result = (
            self.service
            .export_local(
                version_id,
                approval_id,
                eval_percent=20,
                split_seed="seed-b",
            )
        )

        self.assertEqual(
            "ready-local",
            result[
                "state"
            ],
        )

        self.assertEqual(
            "consumed",
            result[
                "cyber"
            ][
                "status"
            ],
        )

        self.assertTrue(
            result[
                "integrity"
            ][
                "integrity"
            ]
        )

        self.assertEqual(
            "approved-for-export",
            result[
                "source_state"
            ],
        )

        self.assertFalse(
            result[
                "automatic_training"
            ]
        )

        self.assertFalse(
            result[
                "external_export"
            ]
        )

    def test_export_approval_is_single_use(
        self,
    ):
        version_id = self.version()

        pending = (
            self.service
            .request_local_export(
                version_id
            )
        )

        approval_id = (
            pending[
                "approval"
            ][
                "id"
            ]
        )

        self.approvals.decide(
            approval_id,
            True,
        )

        self.service.export_local(
            version_id,
            approval_id,
        )

        with self.assertRaises(
            ApprovalError
        ):
            self.service.export_local(
                version_id,
                approval_id,
            )


if __name__ == "__main__":
    unittest.main()