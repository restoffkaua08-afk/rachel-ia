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

from rachel_core.training_dataset_compiler import (
    TrainingDatasetCompiler,
)

from security_runtime import (
    ApprovalError,
    ApprovalStore,
)

from training_dataset_runtime import (
    TrainingDatasetService,
)


class TrainingDatasetRuntimeTests(
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

        self.exporter = (
            DatasetExportFactory(
                self.root
                / "exports"
            )
        )

        self.compiler = (
            TrainingDatasetCompiler(
                self.exporter,
                self.root
                / "compiled"
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
            TrainingDatasetService(
                exporter=self.exporter,
                compiler=self.compiler,
                approvals=self.approvals,
            )
        )

    def tearDown(
        self,
    ) -> None:
        self.temp.cleanup()

    def export(
        self,
        suffix: str,
    ) -> str:

        version = {
            "id": (
                "conversation-v1-"
                + suffix
            ),
            "dataset_type": (
                "conversation"
            ),
            "content_hash": (
                "a" * 64
            ),
            "item_count": 4,
            "state": (
                "approved-for-export"
            ),
        }

        items = [
            {
                "id": (
                    f"item_{suffix}_{index}"
                ),
                "content_hash": (
                    f"{index + 1:064x}"
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
                    "review_state": (
                        "user_accepted"
                    ),
                },
            }
            for index
            in range(4)
        ]

        result = (
            self.exporter
            .create_export(
                version,
                items,
                eval_percent=25,
                split_seed=(
                    "runtime-"
                    + suffix
                ),
            )
        )

        return str(
            result[
                "id"
            ]
        )

    def test_compile_request_requires_cyber(
        self,
    ):
        export_id = self.export(
            "request"
        )

        result = (
            self.service
            .request_compile(
                export_id
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
            0,
            self.compiler
            .status()[
                "compiled_datasets"
            ],
        )

    def test_approved_compile_is_consumed(
        self,
    ):
        export_id = self.export(
            "compile"
        )

        pending = (
            self.service
            .request_compile(
                export_id
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
            .compile(
                export_id,
                approval_id,
            )
        )

        self.assertEqual(
            "compiled-local",
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

        self.assertFalse(
            result[
                "automatic_training"
            ]
        )

        self.assertFalse(
            result[
                "checkpoint_created"
            ]
        )

    def test_approval_is_bound_to_training_format(
        self,
    ):
        export_id = self.export(
            "binding"
        )

        pending = (
            self.service
            .request_compile(
                export_id,
                training_format="sft",
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
            Exception
        ):
            self.service.compile(
                export_id,
                approval_id,
                training_format=(
                    "preference"
                ),
            )

        self.assertEqual(
            0,
            self.compiler
            .status()[
                "compiled_datasets"
            ],
        )

    def test_compile_approval_is_single_use(
        self,
    ):
        export_id = self.export(
            "single"
        )

        pending = (
            self.service
            .request_compile(
                export_id
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

        self.service.compile(
            export_id,
            approval_id,
        )

        with self.assertRaises(
            ApprovalError
        ):
            self.service.compile(
                export_id,
                approval_id,
            )


if __name__ == "__main__":
    unittest.main()