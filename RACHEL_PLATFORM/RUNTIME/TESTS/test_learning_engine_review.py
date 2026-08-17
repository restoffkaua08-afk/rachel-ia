from __future__ import annotations

import json
import sys
import tempfile
import unittest

from pathlib import Path
from types import SimpleNamespace


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


from rachel_core.dataset_factory import (
    DatasetFactory,
    DatasetFactoryError,
)

from learning_engine_runtime import (
    DatasetReviewError,
    LearningDatasetReviewService,
)

from security_runtime import (
    ApprovalError,
    ApprovalStore,
)


class RejectingDany:
    def evaluate(
        self,
        content: str,
    ):
        return SimpleNamespace(
            accepted=False,
            score=25,
            issues=(
                "TEST_REJECTED",
            ),
            checks={
                "test_gate": False,
            },
        )


class LearningDatasetReviewTests(
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
                / "approvals.db",
                policy,
            )
        )

        self.service = (
            LearningDatasetReviewService(
                factory=self.factory,
                approvals=self.approvals,
            )
        )

    def tearDown(
        self,
    ) -> None:
        self.temp.cleanup()

    def version(
        self,
        value: str,
    ) -> dict:

        return (
            self.factory
            .create_version(
                "conversation",
                [
                    {
                        "source_kind": (
                            "experience"
                        ),
                        "source_id": (
                            "exp_"
                            + value
                        ),
                        "payload": {
                            "user": (
                                "pergunta "
                                + value
                            ),
                            "assistant": (
                                "resposta "
                                + value
                            ),
                        },
                        "provenance": {
                            "dany_gate": (
                                "passed"
                            ),
                            "review_state": (
                                "user_accepted"
                            ),
                        },
                    }
                ],
                metadata={
                    "test": value,
                },
            )
        )

    def test_request_export_requires_high_risk_cyber_approval(
        self,
    ):
        version = self.version(
            "a"
        )

        result = (
            self.service
            .request_export(
                version[
                    "version_id"
                ]
            )
        )

        self.assertEqual(
            "approval_required",
            result["state"],
        )

        self.assertEqual(
            "high",
            result[
                "approval"
            ][
                "risk"
            ],
        )

        self.assertEqual(
            "publish",
            result[
                "approval"
            ][
                "effect"
            ],
        )

        stored = (
            self.factory
            .get_version(
                version[
                    "version_id"
                ]
            )
        )

        self.assertEqual(
            "candidate",
            stored["state"],
        )

    def test_cyber_approval_is_consumed_and_promotes(
        self,
    ):
        version = self.version(
            "b"
        )

        pending = (
            self.service
            .request_export(
                version[
                    "version_id"
                ]
            )
        )

        approval_id = (
            pending[
                "approval"
            ][
                "id"
            ]
        )

        with self.assertRaises(
            ApprovalError
        ):
            self.service.approve_export(
                version[
                    "version_id"
                ],
                approval_id,
            )

        self.approvals.decide(
            approval_id,
            True,
        )

        result = (
            self.service
            .approve_export(
                version[
                    "version_id"
                ],
                approval_id,
            )
        )

        self.assertEqual(
            "approved-for-export",
            result["state"],
        )

        self.assertEqual(
            "consumed",
            result[
                "cyber"
            ][
                "status"
            ],
        )

        stored = (
            self.factory
            .get_version(
                version[
                    "version_id"
                ]
            )
        )

        self.assertEqual(
            "approved-for-export",
            stored["state"],
        )

        history = (
            self.factory
            .review_history(
                version[
                    "version_id"
                ]
            )
        )

        self.assertEqual(
            1,
            len(history),
        )

        self.assertEqual(
            "cyber-consumed",
            history[0][
                "authorization"
            ],
        )

        raw_registry = (
            self.factory
            .registry_path
            .read_bytes()
        )

        self.assertNotIn(
            approval_id.encode(
                "utf-8"
            ),
            raw_registry,
        )

    def test_approval_is_bound_to_exact_dataset(
        self,
    ):
        first = self.version(
            "c1"
        )

        second = self.version(
            "c2"
        )

        pending = (
            self.service
            .request_export(
                first[
                    "version_id"
                ]
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
            self.service.approve_export(
                second[
                    "version_id"
                ],
                approval_id,
            )

        self.assertEqual(
            "candidate",
            self.factory
            .get_version(
                first[
                    "version_id"
                ]
            )["state"],
        )

        self.assertEqual(
            "candidate",
            self.factory
            .get_version(
                second[
                    "version_id"
                ]
            )["state"],
        )

    def test_dany_rejection_blocks_request(
        self,
    ):
        version = self.version(
            "d"
        )

        service = (
            LearningDatasetReviewService(
                factory=self.factory,
                approvals=self.approvals,
                evaluator=RejectingDany(),
            )
        )

        with self.assertRaises(
            DatasetReviewError
        ):
            service.request_export(
                version[
                    "version_id"
                ]
            )

        self.assertEqual(
            [],
            self.approvals.list(
                status="pending"
            ),
        )

    def test_tampering_blocks_review(
        self,
    ):
        version = self.version(
            "e"
        )

        registered = (
            self.factory
            .get_version(
                version[
                    "version_id"
                ]
            )
        )

        path = Path(
            registered["data_path"]
        )

        with path.open(
            "a",
            encoding="utf-8",
        ) as handle:
            handle.write(
                json.dumps(
                    {
                        "tampered": True,
                    }
                )
                + "\n"
            )

        with self.assertRaises(
            DatasetFactoryError
        ):
            self.service.request_export(
                version[
                    "version_id"
                ]
            )

        self.assertEqual(
            [],
            self.approvals.list(
                status="pending"
            ),
        )

    def test_factory_cannot_fake_export_gate(
        self,
    ):
        version = self.version(
            "f"
        )

        with self.assertRaises(
            DatasetFactoryError
        ):
            self.factory.record_review_transition(
                version[
                    "version_id"
                ],
                target_state=(
                    "approved-for-export"
                ),
                reviewer="fake",
                dany_accepted=False,
                dany_score=0,
                dany_issues=[
                    "missing",
                ],
                dany_checks={
                    "gate": False,
                },
                authorization="none",
            )


if __name__ == "__main__":
    unittest.main()