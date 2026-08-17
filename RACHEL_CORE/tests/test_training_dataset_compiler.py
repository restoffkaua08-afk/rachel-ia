from __future__ import annotations

import json
import tempfile
import unittest

from pathlib import Path

from rachel_core.dataset_export import (
    DatasetExportFactory,
)

from rachel_core.training_dataset_compiler import (
    TrainingDatasetCompiler,
    TrainingDatasetCompilerError,
)


class TrainingDatasetCompilerTests(
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
                / "compiled",
            )
        )

    def tearDown(
        self,
    ) -> None:
        self.temp.cleanup()

    def export(
        self,
        dataset_type: str,
        payloads: list[dict],
    ) -> str:

        version = {
            "id": (
                f"{dataset_type}-v1-test"
            ),
            "dataset_type": (
                dataset_type
            ),
            "content_hash": (
                "a" * 64
            ),
            "item_count": (
                len(payloads)
            ),
            "state": (
                "approved-for-export"
            ),
        }

        items = [
            {
                "id": (
                    f"item_{index}"
                ),
                "content_hash": (
                    f"{index + 1:064x}"
                ),
                "payload": payload,
                "provenance": {
                    "kind": (
                        "planner_decision"
                        if dataset_type
                        == "planning"
                        else dataset_type
                    ),
                },
            }
            for index, payload
            in enumerate(
                payloads
            )
        ]

        result = (
            self.exporter
            .create_export(
                version,
                items,
                eval_percent=(
                    50
                    if len(items) > 1
                    else 0
                ),
                split_seed=(
                    "compiler-test"
                ),
            )
        )

        return str(
            result[
                "id"
            ]
        )

    def test_format_mapping(
        self,
    ):
        self.assertEqual(
            "sft",
            self.compiler
            .infer_format(
                "conversation"
            ),
        )

        self.assertEqual(
            "sft",
            self.compiler
            .infer_format(
                "coding"
            ),
        )

        self.assertEqual(
            "preference",
            self.compiler
            .infer_format(
                "preference"
            ),
        )

        self.assertEqual(
            "tool-use",
            self.compiler
            .infer_format(
                "tool-use"
            ),
        )

        self.assertEqual(
            "tool-use",
            self.compiler
            .infer_format(
                "planning"
            ),
        )

    def test_sft_compilation(
        self,
    ):
        export_id = self.export(
            "conversation",
            [
                {
                    "user": "Pergunta 1",
                    "assistant": "Resposta 1",
                },
                {
                    "user": "Pergunta 2",
                    "assistant": "Resposta 2",
                },
            ],
        )

        result = (
            self.compiler
            .compile(
                export_id
            )
        )

        self.assertEqual(
            "sft",
            result[
                "training_format"
            ],
        )

        train_path = Path(
            result[
                "train_path"
            ]
        )

        rows = [
            json.loads(line)
            for line
            in train_path
            .read_text(
                encoding="utf-8"
            )
            .splitlines()
            if line.strip()
        ]

        self.assertEqual(
            1,
            len(rows),
        )

        self.assertEqual(
            "user",
            rows[0][
                "messages"
            ][0][
                "role"
            ],
        )

        self.assertEqual(
            "assistant",
            rows[0][
                "messages"
            ][1][
                "role"
            ],
        )

        verified = (
            self.compiler
            .verify(
                result[
                    "id"
                ]
            )
        )

        self.assertTrue(
            verified[
                "integrity"
            ]
        )

    def test_preference_compilation(
        self,
    ):
        export_id = self.export(
            "preference",
            [
                {
                    "prompt": "Pergunta",
                    "rejected_response": (
                        "Resposta ruim"
                    ),
                    "preferred_response": (
                        "Resposta boa"
                    ),
                }
            ],
        )

        result = (
            self.compiler
            .compile(
                export_id
            )
        )

        row = json.loads(
            Path(
                result[
                    "train_path"
                ]
            )
            .read_text(
                encoding="utf-8"
            )
            .strip()
        )

        self.assertEqual(
            "Pergunta",
            row[
                "prompt"
            ],
        )

        self.assertEqual(
            "Resposta boa",
            row[
                "chosen"
            ],
        )

        self.assertEqual(
            "Resposta ruim",
            row[
                "rejected"
            ],
        )

    def test_tool_use_compilation(
        self,
    ):
        export_id = self.export(
            "planning",
            [
                {
                    "action": "tool",
                    "tool": "tyrion.health",
                    "arguments": {},
                }
            ],
        )

        result = (
            self.compiler
            .compile(
                export_id
            )
        )

        row = json.loads(
            Path(
                result[
                    "train_path"
                ]
            )
            .read_text(
                encoding="utf-8"
            )
            .strip()
        )

        self.assertEqual(
            "tool-use",
            result[
                "training_format"
            ],
        )

        self.assertEqual(
            "planner_decision",
            row[
                "event_kind"
            ],
        )

        self.assertEqual(
            "tyrion.health",
            row[
                "payload"
            ][
                "tool"
            ],
        )

    def test_wrong_training_format_is_rejected(
        self,
    ):
        export_id = self.export(
            "conversation",
            [
                {
                    "user": "A",
                    "assistant": "B",
                }
            ],
        )

        with self.assertRaises(
            TrainingDatasetCompilerError
        ):
            self.compiler.plan(
                export_id,
                training_format=(
                    "preference"
                ),
            )

    def test_compilation_does_not_enable_training(
        self,
    ):
        export_id = self.export(
            "conversation",
            [
                {
                    "user": "A",
                    "assistant": "B",
                }
            ],
        )

        result = (
            self.compiler
            .compile(
                export_id
            )
        )

        verify = (
            self.compiler
            .verify(
                result[
                    "id"
                ]
            )
        )

        self.assertFalse(
            verify[
                "automatic_training"
            ]
        )

        self.assertFalse(
            verify[
                "checkpoint_created"
            ]
        )

        self.assertFalse(
            verify[
                "external_export"
            ]
        )


if __name__ == "__main__":
    unittest.main()