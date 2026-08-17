import json
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from rachel_core.dataset_factory import (
    DATASET_TYPES,
    DatasetFactory,
    DatasetFactoryError,
)


class DatasetFactoryTests(
    unittest.TestCase
):
    def setUp(
        self,
    ) -> None:
        self.temp = (
            tempfile
            .TemporaryDirectory()
        )

        self.root = (
            Path(
                self.temp.name
            )
            / "datasets"
        )

        self.factory = (
            DatasetFactory(
                self.root
            )
        )

    def tearDown(
        self,
    ) -> None:
        self.temp.cleanup()

    @staticmethod
    def item(
        source_id: str = "exp_1",
        value: str = "alpha",
    ):
        return {
            "source_kind": (
                "experience"
            ),

            "source_id": (
                source_id
            ),

            "payload": {
                "input": value,
                "output": (
                    value.upper()
                ),
            },

            "provenance": {
                "provider": (
                    "openai-compatible"
                ),

                "model": (
                    "qwen3:1.7b"
                ),

                "review_state": (
                    "user_accepted"
                ),
            },
        }

    def test_supports_official_dataset_types(
        self,
    ):
        self.assertEqual(
            {
                "conversation",
                "coding",
                "tool-use",
                "planning",
                "preference",
                "knowledge",
            },
            set(
                DATASET_TYPES
            ),
        )

        status = (
            self.factory
            .status()
        )

        self.assertEqual(
            1,
            status[
                "schema_version"
            ],
        )

        self.assertFalse(
            status[
                "automatic_training"
            ]
        )

        self.assertFalse(
            status[
                "automatic_promotion"
            ]
        )

        self.assertFalse(
            status[
                "external_export"
            ]
        )

    def test_create_version_deduplicates_and_writes_manifest(
        self,
    ):
        item = self.item()

        manifest = (
            self.factory
            .create_version(
                "conversation",
                [
                    item,
                    item,
                ],
                metadata={
                    "purpose": (
                        "stage-11-test"
                    ),
                },
            )
        )

        self.assertEqual(
            1,
            manifest[
                "version_number"
            ],
        )

        self.assertEqual(
            1,
            manifest[
                "item_count"
            ],
        )

        self.assertEqual(
            "candidate",
            manifest[
                "state"
            ],
        )

        self.assertFalse(
            manifest[
                "automatic_training"
            ]
        )

        registered = (
            self.factory
            .get_version(
                manifest[
                    "version_id"
                ]
            )
        )

        self.assertIsNotNone(
            registered
        )

        assert registered is not None

        manifest_path = Path(
            registered[
                "manifest_path"
            ]
        )

        data_path = Path(
            registered[
                "data_path"
            ]
        )

        self.assertTrue(
            manifest_path.is_file()
        )

        self.assertTrue(
            data_path.is_file()
        )

        disk_manifest = json.loads(
            manifest_path.read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(
            manifest[
                "content_hash"
            ],
            disk_manifest[
                "content_hash"
            ],
        )

        rows = [
            json.loads(
                line
            )
            for line
            in data_path
            .read_text(
                encoding="utf-8"
            )
            .splitlines()
            if line.strip()
        ]

        self.assertEqual(
            1,
            len(
                rows
            ),
        )

        self.assertEqual(
            "experience",
            rows[0][
                "provenance"
            ][
                "source_kind"
            ],
        )

        self.assertEqual(
            "exp_1",
            rows[0][
                "provenance"
            ][
                "source_id"
            ],
        )

        self.assertEqual(
            64,
            len(
                rows[0][
                    "content_hash"
                ]
            ),
        )

    def test_versions_are_monotonic_and_identical_version_is_rejected(
        self,
    ):
        first = (
            self.factory
            .create_version(
                "coding",
                [
                    self.item(
                        "exp_a",
                        "one",
                    )
                ],
            )
        )

        second = (
            self.factory
            .create_version(
                "coding",
                [
                    self.item(
                        "exp_b",
                        "two",
                    )
                ],
            )
        )

        self.assertEqual(
            1,
            first[
                "version_number"
            ],
        )

        self.assertEqual(
            2,
            second[
                "version_number"
            ],
        )

        with self.assertRaises(
            DatasetFactoryError
        ):
            self.factory.create_version(
                "coding",
                [
                    self.item(
                        "exp_a",
                        "one",
                    )
                ],
            )

        versions = (
            self.factory
            .list_versions(
                "coding"
            )
        )

        self.assertEqual(
            [
                2,
                1,
            ],
            [
                item[
                    "version_number"
                ]
                for item
                in versions
            ],
        )

    def test_all_six_types_can_have_independent_v1(
        self,
    ):
        for dataset_type in sorted(
            DATASET_TYPES
        ):
            manifest = (
                self.factory
                .create_version(
                    dataset_type,
                    [
                        self.item(
                            (
                                "src_"
                                + dataset_type
                            ),
                            dataset_type,
                        )
                    ],
                )
            )

            self.assertEqual(
                1,
                manifest[
                    "version_number"
                ],
            )

            self.assertTrue(
                manifest[
                    "version_id"
                ].startswith(
                    (
                        dataset_type
                        + "-v000001-"
                    )
                )
            )

        status = (
            self.factory
            .status()
        )

        self.assertEqual(
            6,
            status[
                "versions"
            ],
        )

        self.assertEqual(
            6,
            status[
                "items"
            ],
        )

        self.assertEqual(
            6,
            len(
                status[
                    "versions_by_type"
                ]
            ),
        )

    def test_privacy_layer_is_applied_before_hash_and_persistence(
        self,
    ):
        def fake_redact(
            value,
        ):
            if isinstance(
                value,
                dict,
            ):
                return {
                    "sanitized": True
                }

            return value

        with patch(
            "rachel_core.dataset_factory.redact",
            side_effect=fake_redact,
        ):
            manifest = (
                self.factory
                .create_version(
                    "preference",
                    [
                        {
                            "source_kind": (
                                "feedback"
                            ),

                            "source_id": (
                                "fb_1"
                            ),

                            "payload": {
                                "secret": (
                                    "raw-value"
                                ),
                            },

                            "provenance": {
                                "private": (
                                    "raw-value"
                                ),
                            },
                        }
                    ],

                    metadata={
                        "private": (
                            "raw-value"
                        ),
                    },
                )
            )

        registered = (
            self.factory
            .get_version(
                manifest[
                    "version_id"
                ]
            )
        )

        assert registered is not None

        data = Path(
            registered[
                "data_path"
            ]
        ).read_text(
            encoding="utf-8"
        )

        manifest_text = Path(
            registered[
                "manifest_path"
            ]
        ).read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            "raw-value",
            data,
        )

        self.assertNotIn(
            "raw-value",
            manifest_text,
        )

        self.assertIn(
            '"sanitized": true',
            manifest_text,
        )


if __name__ == "__main__":
    unittest.main()