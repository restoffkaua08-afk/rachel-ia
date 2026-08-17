from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import uuid

from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .dataset_export import (
    DatasetExportFactory,
)


COMPILER_SCHEMA_VERSION = 1
COMPILER_VERSION = "rachel-training-compiler-v1"

TRAINING_FORMATS = frozenset(
    {
        "sft",
        "preference",
        "tool-use",
    }
)

DEFAULT_FORMAT_BY_DATASET = {
    "conversation": "sft",
    "coding": "sft",
    "knowledge": "sft",
    "preference": "preference",
    "planning": "tool-use",
    "tool-use": "tool-use",
}


class TrainingDatasetCompilerError(
    RuntimeError
):
    pass


class TrainingDatasetCompiler:
    """
    Compila exports locais validados para formatos
    canonicos de treinamento da Rachel.

    Nao executa treinamento.
    Nao altera pesos.
    Nao gera checkpoint.
    Nao envia dados externamente.
    """

    def __init__(
        self,
        exporter: DatasetExportFactory,
        root: Path,
        registry_path: Path | None = None,
    ) -> None:

        self.exporter = exporter

        self.root = (
            Path(root)
            .expanduser()
            .resolve()
        )

        self.registry_path = (
            Path(registry_path)
            .expanduser()
            .resolve()
            if registry_path is not None
            else self.root
            / "compiler-registry.db"
        )

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.registry_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._initialize()

    def _connect(
        self,
    ) -> sqlite3.Connection:

        connection = sqlite3.connect(
            self.registry_path,
            timeout=30,
        )

        connection.row_factory = (
            sqlite3.Row
        )

        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        connection.execute(
            "PRAGMA journal_mode = WAL"
        ).fetchone()

        return connection

    @contextmanager
    def _connection(
        self,
    ) -> Iterator[
        sqlite3.Connection
    ]:

        with closing(
            self._connect()
        ) as connection:
            with connection:
                yield connection

    def _initialize(
        self,
    ) -> None:

        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS
                compiler_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS
                compiled_datasets (
                    id TEXT PRIMARY KEY,

                    source_export_id TEXT NOT NULL,
                    source_version_id TEXT NOT NULL,
                    source_dataset_type TEXT NOT NULL,

                    training_format TEXT NOT NULL,
                    compiler_version TEXT NOT NULL,

                    created_at TEXT NOT NULL,

                    train_count INTEGER NOT NULL,
                    eval_count INTEGER NOT NULL,

                    train_sha256 TEXT NOT NULL,
                    eval_sha256 TEXT NOT NULL,
                    manifest_sha256 TEXT NOT NULL,

                    compiled_path TEXT NOT NULL,
                    train_path TEXT NOT NULL,
                    eval_path TEXT NOT NULL,
                    manifest_path TEXT NOT NULL,

                    state TEXT NOT NULL,

                    UNIQUE(
                        source_export_id,
                        training_format,
                        compiler_version
                    )
                );

                CREATE INDEX IF NOT EXISTS
                    idx_compiled_source
                ON compiled_datasets(
                    source_export_id,
                    created_at DESC
                );
                """
            )

            connection.execute(
                """
                INSERT INTO compiler_meta(
                    key,
                    value
                )
                VALUES(
                    'schema_version',
                    ?
                )
                ON CONFLICT(key)
                DO UPDATE SET
                    value = excluded.value
                """,
                (
                    str(
                        COMPILER_SCHEMA_VERSION
                    ),
                ),
            )

            connection.execute(
                """
                INSERT INTO compiler_meta(
                    key,
                    value
                )
                VALUES(
                    'compiler_version',
                    ?
                )
                ON CONFLICT(key)
                DO UPDATE SET
                    value = excluded.value
                """,
                (
                    COMPILER_VERSION,
                ),
            )

    @staticmethod
    def _bytes_hash(
        value: bytes,
    ) -> str:

        return hashlib.sha256(
            value
        ).hexdigest()

    @staticmethod
    def _canonical_json(
        value: Any,
    ) -> str:

        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
        )

    @classmethod
    def _json_hash(
        cls,
        value: Any,
    ) -> str:

        return hashlib.sha256(
            cls._canonical_json(
                value
            ).encode(
                "utf-8"
            )
        ).hexdigest()

    @staticmethod
    def _required_text(
        value: Any,
        field: str,
        maximum: int = 100_000,
    ) -> str:

        if not isinstance(
            value,
            str,
        ):
            raise TrainingDatasetCompilerError(
                f"{field} precisa ser texto."
            )

        clean = value.strip()

        if not clean:
            raise TrainingDatasetCompilerError(
                f"{field} nao pode ser vazio."
            )

        if len(clean) > maximum:
            raise TrainingDatasetCompilerError(
                f"{field} excede {maximum} caracteres."
            )

        return clean

    @staticmethod
    def infer_format(
        dataset_type: str,
    ) -> str:

        selected = str(
            dataset_type
        ).strip().casefold()

        target = (
            DEFAULT_FORMAT_BY_DATASET
            .get(
                selected
            )
        )

        if target is None:
            raise TrainingDatasetCompilerError(
                "Dataset type sem formato "
                "de treinamento conhecido: "
                + selected
            )

        return target

    @classmethod
    def _target_format(
        cls,
        dataset_type: str,
        requested: str | None,
    ) -> str:

        inferred = cls.infer_format(
            dataset_type
        )

        if requested is None:
            return inferred

        selected = str(
            requested
        ).strip().casefold()

        if selected not in TRAINING_FORMATS:
            raise TrainingDatasetCompilerError(
                "Training format invalido."
            )

        if selected != inferred:
            raise TrainingDatasetCompilerError(
                "Formato solicitado nao corresponde "
                "ao tipo do dataset. "
                f"{dataset_type} exige {inferred}."
            )

        return selected

    @staticmethod
    def _load_jsonl(
        path: Path,
    ) -> list[
        dict[str, Any]
    ]:

        rows = []

        for line in path.read_text(
            encoding="utf-8"
        ).splitlines():

            if not line.strip():
                continue

            value = json.loads(
                line
            )

            if not isinstance(
                value,
                dict,
            ):
                raise TrainingDatasetCompilerError(
                    "Linha de export precisa "
                    "ser objeto JSON."
                )

            rows.append(
                value
            )

        return rows

    @classmethod
    def _source_binding(
        cls,
        row: dict[str, Any],
    ) -> dict[str, Any]:

        return {
            "source_version_id": (
                row.get(
                    "source_version_id"
                )
            ),
            "source_item_id": (
                row.get(
                    "source_item_id"
                )
            ),
            "source_content_hash": (
                row.get(
                    "source_content_hash"
                )
            ),
            "dataset_type": (
                row.get(
                    "dataset_type"
                )
            ),
        }

    @classmethod
    def _compile_sft(
        cls,
        row: dict[str, Any],
    ) -> dict[str, Any]:

        payload = row.get(
            "payload"
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise TrainingDatasetCompilerError(
                "SFT payload precisa ser objeto."
            )

        user = cls._required_text(
            payload.get(
                "user"
            ),
            "payload.user",
        )

        assistant = cls._required_text(
            payload.get(
                "assistant"
            ),
            "payload.assistant",
        )

        return {
            "messages": [
                {
                    "role": "user",
                    "content": user,
                },
                {
                    "role": "assistant",
                    "content": assistant,
                },
            ],
            "source": (
                cls._source_binding(
                    row
                )
            ),
        }

    @classmethod
    def _compile_preference(
        cls,
        row: dict[str, Any],
    ) -> dict[str, Any]:

        payload = row.get(
            "payload"
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise TrainingDatasetCompilerError(
                "Preference payload precisa ser objeto."
            )

        prompt = cls._required_text(
            payload.get(
                "prompt"
            ),
            "payload.prompt",
        )

        rejected = cls._required_text(
            payload.get(
                "rejected_response"
            ),
            "payload.rejected_response",
        )

        chosen = cls._required_text(
            payload.get(
                "preferred_response"
            ),
            "payload.preferred_response",
        )

        return {
            "prompt": prompt,
            "chosen": chosen,
            "rejected": rejected,
            "source": (
                cls._source_binding(
                    row
                )
            ),
        }

    @classmethod
    def _compile_tool_use(
        cls,
        row: dict[str, Any],
    ) -> dict[str, Any]:

        payload = row.get(
            "payload"
        )

        provenance = (
            row.get(
                "provenance"
            )
            or {}
        )

        if not isinstance(
            payload,
            dict,
        ):
            raise TrainingDatasetCompilerError(
                "Tool-use payload precisa ser objeto."
            )

        if not isinstance(
            provenance,
            dict,
        ):
            raise TrainingDatasetCompilerError(
                "Tool-use provenance precisa ser objeto."
            )

        kind = str(
            provenance.get(
                "kind"
            )
            or row.get(
                "dataset_type"
            )
            or "tool-use"
        ).strip()

        if not kind:
            kind = "tool-use"

        return {
            "event_kind": kind,
            "payload": payload,
            "source": (
                cls._source_binding(
                    row
                )
            ),
        }

    @classmethod
    def _compile_row(
        cls,
        row: dict[str, Any],
        training_format: str,
    ) -> dict[str, Any]:

        if training_format == "sft":
            return cls._compile_sft(
                row
            )

        if training_format == "preference":
            return cls._compile_preference(
                row
            )

        if training_format == "tool-use":
            return cls._compile_tool_use(
                row
            )

        raise TrainingDatasetCompilerError(
            "Training format nao suportado."
        )

    def _source(
        self,
        export_id: str,
    ) -> tuple[
        dict[str, Any],
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]:

        verification = (
            self.exporter
            .verify_export(
                export_id
            )
        )

        if not verification[
            "integrity"
        ]:
            raise TrainingDatasetCompilerError(
                "Export source sem integridade."
            )

        record = (
            self.exporter
            .get_export(
                export_id
            )
        )

        if record is None:
            raise TrainingDatasetCompilerError(
                "Export source inexistente."
            )

        if (
            record[
                "state"
            ]
            != "ready-local"
        ):
            raise TrainingDatasetCompilerError(
                "Export precisa estar ready-local."
            )

        train = self._load_jsonl(
            Path(
                record[
                    "train_path"
                ]
            )
        )

        evaluation = self._load_jsonl(
            Path(
                record[
                    "eval_path"
                ]
            )
        )

        if (
            len(train)
            != int(
                record[
                    "train_count"
                ]
            )
        ):
            raise TrainingDatasetCompilerError(
                "Train count source invalido."
            )

        if (
            len(evaluation)
            != int(
                record[
                    "eval_count"
                ]
            )
        ):
            raise TrainingDatasetCompilerError(
                "Eval count source invalido."
            )

        return (
            record,
            train,
            evaluation,
        )

    def plan(
        self,
        export_id: str,
        *,
        training_format: str | None = None,
    ) -> dict[str, Any]:

        record, train, evaluation = (
            self._source(
                export_id
            )
        )

        selected = (
            self._target_format(
                str(
                    record[
                        "source_dataset_type"
                    ]
                ),
                training_format,
            )
        )

        compiled_train = [
            self._compile_row(
                row,
                selected,
            )
            for row
            in train
        ]

        compiled_eval = [
            self._compile_row(
                row,
                selected,
            )
            for row
            in evaluation
        ]

        plan_hash = self._json_hash(
            {
                "compiler_version": (
                    COMPILER_VERSION
                ),
                "source_export_id": (
                    export_id
                ),
                "source_version_id": (
                    record[
                        "source_version_id"
                    ]
                ),
                "source_dataset_type": (
                    record[
                        "source_dataset_type"
                    ]
                ),
                "source_train_sha256": (
                    record[
                        "train_sha256"
                    ]
                ),
                "source_eval_sha256": (
                    record[
                        "eval_sha256"
                    ]
                ),
                "training_format": (
                    selected
                ),
                "train": (
                    compiled_train
                ),
                "eval": (
                    compiled_eval
                ),
            }
        )

        compiled_id = (
            selected
            + "-compiled-"
            + plan_hash[:16]
        )

        return {
            "compiled_id": (
                compiled_id
            ),
            "plan_hash": (
                plan_hash
            ),
            "compiler_version": (
                COMPILER_VERSION
            ),
            "source_export_id": (
                export_id
            ),
            "source_version_id": (
                record[
                    "source_version_id"
                ]
            ),
            "source_dataset_type": (
                record[
                    "source_dataset_type"
                ]
            ),
            "training_format": (
                selected
            ),
            "train_count": (
                len(
                    compiled_train
                )
            ),
            "eval_count": (
                len(
                    compiled_eval
                )
            ),
            "automatic_training": (
                False
            ),
            "checkpoint_created": (
                False
            ),
            "external_export": (
                False
            ),
        }

    def compile(
        self,
        export_id: str,
        *,
        training_format: str | None = None,
    ) -> dict[str, Any]:

        record, train, evaluation = (
            self._source(
                export_id
            )
        )

        plan = self.plan(
            export_id,
            training_format=(
                training_format
            ),
        )

        with self._connection() as connection:
            existing = connection.execute(
                """
                SELECT id
                FROM compiled_datasets
                WHERE source_export_id = ?
                  AND training_format = ?
                  AND compiler_version = ?
                """,
                (
                    export_id,
                    plan[
                        "training_format"
                    ],
                    COMPILER_VERSION,
                ),
            ).fetchone()

        if existing is not None:
            raise TrainingDatasetCompilerError(
                "Compilacao identica ja existe: "
                + str(
                    existing[
                        "id"
                    ]
                )
            )

        compiled_train = [
            self._compile_row(
                row,
                plan[
                    "training_format"
                ],
            )
            for row
            in train
        ]

        compiled_eval = [
            self._compile_row(
                row,
                plan[
                    "training_format"
                ],
            )
            for row
            in evaluation
        ]

        compiled_dir = (
            self.root
            / plan[
                "training_format"
            ]
            / plan[
                "compiled_id"
            ]
        )

        if compiled_dir.exists():
            raise TrainingDatasetCompilerError(
                "Diretorio compiled ja existe."
            )

        temp_dir = (
            compiled_dir.parent
            / (
                ".tmp-"
                + uuid.uuid4().hex
            )
        )

        temp_dir.mkdir(
            parents=True,
            exist_ok=False,
        )

        train_path = (
            compiled_dir
            / "train.jsonl"
        )

        eval_path = (
            compiled_dir
            / "eval.jsonl"
        )

        manifest_path = (
            compiled_dir
            / "manifest.json"
        )

        try:
            temp_train = (
                temp_dir
                / "train.jsonl"
            )

            temp_eval = (
                temp_dir
                / "eval.jsonl"
            )

            temp_manifest = (
                temp_dir
                / "manifest.json"
            )

            with temp_train.open(
                "w",
                encoding="utf-8",
                newline="\n",
            ) as handle:

                for row in compiled_train:
                    handle.write(
                        json.dumps(
                            row,
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                        + "\n"
                    )

            with temp_eval.open(
                "w",
                encoding="utf-8",
                newline="\n",
            ) as handle:

                for row in compiled_eval:
                    handle.write(
                        json.dumps(
                            row,
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                        + "\n"
                    )

            train_sha = self._bytes_hash(
                temp_train.read_bytes()
            )

            eval_sha = self._bytes_hash(
                temp_eval.read_bytes()
            )

            created_at = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

            manifest = {
                "schema_version": (
                    COMPILER_SCHEMA_VERSION
                ),
                "compiler_version": (
                    COMPILER_VERSION
                ),
                "compiled_id": (
                    plan[
                        "compiled_id"
                    ]
                ),
                "created_at": (
                    created_at
                ),
                "state": (
                    "compiled-local"
                ),
                "training_format": (
                    plan[
                        "training_format"
                    ]
                ),
                "source": {
                    "export_id": (
                        export_id
                    ),
                    "version_id": (
                        record[
                            "source_version_id"
                        ]
                    ),
                    "dataset_type": (
                        record[
                            "source_dataset_type"
                        ]
                    ),
                    "train_sha256": (
                        record[
                            "train_sha256"
                        ]
                    ),
                    "eval_sha256": (
                        record[
                            "eval_sha256"
                        ]
                    ),
                },
                "output": {
                    "train_count": (
                        len(
                            compiled_train
                        )
                    ),
                    "eval_count": (
                        len(
                            compiled_eval
                        )
                    ),
                    "train_sha256": (
                        train_sha
                    ),
                    "eval_sha256": (
                        eval_sha
                    ),
                },
                "plan_hash": (
                    plan[
                        "plan_hash"
                    ]
                ),
                "automatic_training": False,
                "checkpoint_created": False,
                "external_export": False,
            }

            temp_manifest.write_text(
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )

            manifest_sha = self._bytes_hash(
                temp_manifest.read_bytes()
            )

            os.replace(
                temp_dir,
                compiled_dir,
            )

            with self._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO compiled_datasets(
                        id,
                        source_export_id,
                        source_version_id,
                        source_dataset_type,
                        training_format,
                        compiler_version,
                        created_at,
                        train_count,
                        eval_count,
                        train_sha256,
                        eval_sha256,
                        manifest_sha256,
                        compiled_path,
                        train_path,
                        eval_path,
                        manifest_path,
                        state
                    )
                    VALUES(
                        ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        plan[
                            "compiled_id"
                        ],
                        export_id,
                        record[
                            "source_version_id"
                        ],
                        record[
                            "source_dataset_type"
                        ],
                        plan[
                            "training_format"
                        ],
                        COMPILER_VERSION,
                        created_at,
                        len(
                            compiled_train
                        ),
                        len(
                            compiled_eval
                        ),
                        train_sha,
                        eval_sha,
                        manifest_sha,
                        str(
                            compiled_dir
                        ),
                        str(
                            train_path
                        ),
                        str(
                            eval_path
                        ),
                        str(
                            manifest_path
                        ),
                        "compiled-local",
                    ),
                )

        except Exception:
            shutil.rmtree(
                temp_dir,
                ignore_errors=True,
            )

            shutil.rmtree(
                compiled_dir,
                ignore_errors=True,
            )

            raise

        result = self.get(
            plan[
                "compiled_id"
            ]
        )

        if result is None:
            raise TrainingDatasetCompilerError(
                "Compilacao nao registrada."
            )

        return result

    def get(
        self,
        compiled_id: str,
    ) -> dict[
        str,
        Any
    ] | None:

        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM compiled_datasets
                WHERE id = ?
                """,
                (
                    compiled_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return dict(
            row
        )

    def list(
        self,
        limit: int = 50,
    ) -> list[
        dict[
            str,
            Any
        ]
    ]:

        limit = max(
            1,
            min(
                200,
                int(
                    limit
                ),
            ),
        )

        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM compiled_datasets
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (
                    limit,
                ),
            ).fetchall()

        return [
            dict(row)
            for row
            in rows
        ]

    def verify(
        self,
        compiled_id: str,
    ) -> dict[str, Any]:

        record = self.get(
            compiled_id
        )

        if record is None:
            raise TrainingDatasetCompilerError(
                "Compiled dataset inexistente."
            )

        root = self.root.resolve()

        train = Path(
            record[
                "train_path"
            ]
        ).resolve()

        evaluation = Path(
            record[
                "eval_path"
            ]
        ).resolve()

        manifest = Path(
            record[
                "manifest_path"
            ]
        ).resolve()

        for path in (
            train,
            evaluation,
            manifest,
        ):
            if not path.is_relative_to(
                root
            ):
                raise TrainingDatasetCompilerError(
                    "Compiled path saiu "
                    "do root autorizado."
                )

            if not path.is_file():
                raise TrainingDatasetCompilerError(
                    "Arquivo compiled ausente: "
                    + path.name
                )

        train_sha = self._bytes_hash(
            train.read_bytes()
        )

        eval_sha = self._bytes_hash(
            evaluation.read_bytes()
        )

        manifest_sha = self._bytes_hash(
            manifest.read_bytes()
        )

        if (
            train_sha
            != record[
                "train_sha256"
            ]
        ):
            raise TrainingDatasetCompilerError(
                "Compiled train alterado."
            )

        if (
            eval_sha
            != record[
                "eval_sha256"
            ]
        ):
            raise TrainingDatasetCompilerError(
                "Compiled eval alterado."
            )

        if (
            manifest_sha
            != record[
                "manifest_sha256"
            ]
        ):
            raise TrainingDatasetCompilerError(
                "Compiled manifest alterado."
            )

        parsed = json.loads(
            manifest.read_text(
                encoding="utf-8"
            )
        )

        if (
            parsed[
                "source"
            ][
                "export_id"
            ]
            != record[
                "source_export_id"
            ]
        ):
            raise TrainingDatasetCompilerError(
                "Source export binding invalido."
            )

        if (
            parsed[
                "training_format"
            ]
            != record[
                "training_format"
            ]
        ):
            raise TrainingDatasetCompilerError(
                "Training format binding invalido."
            )

        return {
            "integrity": True,
            "compiled_id": (
                compiled_id
            ),
            "state": (
                record[
                    "state"
                ]
            ),
            "training_format": (
                record[
                    "training_format"
                ]
            ),
            "train_count": int(
                record[
                    "train_count"
                ]
            ),
            "eval_count": int(
                record[
                    "eval_count"
                ]
            ),
            "train_sha256": (
                train_sha
            ),
            "eval_sha256": (
                eval_sha
            ),
            "manifest_sha256": (
                manifest_sha
            ),
            "automatic_training": False,
            "checkpoint_created": False,
            "external_export": False,
        }

    def status(
        self,
    ) -> dict[str, Any]:

        with self._connection() as connection:
            total = int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM compiled_datasets
                    """
                ).fetchone()[0]
            )

            rows = connection.execute(
                """
                SELECT
                    training_format,
                    COUNT(*) AS total
                FROM compiled_datasets
                GROUP BY training_format
                ORDER BY training_format
                """
            ).fetchall()

        return {
            "status": "ok",
            "schema_version": (
                COMPILER_SCHEMA_VERSION
            ),
            "compiler_version": (
                COMPILER_VERSION
            ),
            "training_formats": sorted(
                TRAINING_FORMATS
            ),
            "compiled_datasets": (
                total
            ),
            "by_format": {
                str(
                    row[
                        "training_format"
                    ]
                ): int(
                    row[
                        "total"
                    ]
                )
                for row
                in rows
            },
            "automatic_training": False,
            "checkpoint_created": False,
            "external_export": False,
        }