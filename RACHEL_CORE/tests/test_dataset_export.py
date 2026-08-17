from __future__ import annotations

import tempfile
import unittest

from pathlib import Path

from rachel_core.dataset_export import (
    DatasetExportError,
    DatasetExportFactory,
)


class DatasetExportFactoryTests(
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

    def tearDown(
        self,
    ) -> None:
        self.temp.cleanup()

    @staticmethod
    def source(
        count: int = 10,
    ):
        version = {
            "id": (
                "conversation-v000001-test"
            ),
            "dataset_type": (
                "conversation"
            ),
            "content_hash": (
                "a" * 64
            ),
            "item_count": count,
            "state": (
                "approved-for-export"
            ),
        }

        items = []

        for index in range(
            count
        ):
            items.append(
                {
                    "id": (
                        f"item_{index}"
                    ),
                    "content_hash": (
                        f"{index + 1:064x}"
                    ),
                    "payload": {
                        "user": (
                            f"q{index}"
                        ),
                        "assistant": (
                            f"a{index}"
                        ),
                    },
                    "provenance": {
                        "review_state": (
                            "user_accepted"
                        ),
                    },
                }
            )

        return version, items

    def test_split_plan_is_deterministic(
        self,
    ):
        version, items = (
            self.source(
                10
            )
        )

        first = (
            self.exporter
            .plan_export(
                version,
                items,
                eval_percent=20,
                split_seed="seed-a",
            )
        )

        second = (
            self.exporter
            .plan_export(
                version,
                items,
                eval_percent=20,
                split_seed="seed-a",
            )
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertEqual(
            8,
            first[
                "train_count"
            ],
        )

        self.assertEqual(
            2,
            first[
                "eval_count"
            ],
        )

    def test_small_dataset_keeps_train_sample(
        self,
    ):
        version, items = (
            self.source(
                2
            )
        )

        plan = (
            self.exporter
            .plan_export(
                version,
                items,
                eval_percent=50,
            )
        )

        self.assertEqual(
            1,
            plan[
                "train_count"
            ],
        )

        self.assertEqual(
            1,
            plan[
                "eval_count"
            ],
        )

    def test_candidate_source_is_rejected(
        self,
    ):
        version, items = (
            self.source()
        )

        version[
            "state"
        ] = "candidate"

        with self.assertRaises(
            DatasetExportError
        ):
            self.exporter.plan_export(
                version,
                items,
            )

    def test_create_and_verify_export(
        self,
    ):
        version, items = (
            self.source(
                10
            )
        )

        result = (
            self.exporter
            .create_export(
                version,
                items,
                eval_percent=20,
                split_seed="stable",
                metadata={
                    "stage": "11",
                },
            )
        )

        self.assertEqual(
            "ready-local",
            result[
                "state"
            ],
        )

        verify = (
            self.exporter
            .verify_export(
                result[
                    "id"
                ]
            )
        )

        self.assertTrue(
            verify[
                "integrity"
            ]
        )

        self.assertEqual(
            8,
            verify[
                "train_count"
            ],
        )

        self.assertEqual(
            2,
            verify[
                "eval_count"
            ],
        )

        self.assertFalse(
            verify[
                "automatic_training"
            ]
        )

        self.assertFalse(
            verify[
                "external_export"
            ]
        )

    def test_identical_export_is_rejected(
        self,
    ):
        version, items = (
            self.source(
                5
            )
        )

        self.exporter.create_export(
            version,
            items,
        )

        with self.assertRaises(
            DatasetExportError
        ):
            self.exporter.create_export(
                version,
                items,
            )


if __name__ == "__main__":
    unittest.main()