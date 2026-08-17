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


EXPORT_SCHEMA_VERSION = 1
DEFAULT_EVAL_PERCENT = 10
DEFAULT_SPLIT_SEED = "rachel-dataset-split-v1"


class DatasetExportError(RuntimeError):
    pass


class DatasetExportFactory:
    """
    Exportador local e reproduzivel de datasets Rachel.

    Contrato:
    - recebe somente dados ja sanitizados pela DatasetFactory;
    - nao altera o dataset de origem;
    - nao executa treinamento;
    - nao envia dados para fora da maquina;
    - train/eval split e deterministico;
    - export possui manifest e hashes proprios;
    - export criado torna-se imutavel.
    """

    def __init__(
        self,
        root: Path,
        registry_path: Path | None = None,
    ) -> None:

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
            / "export-registry.db"
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
                export_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS
                dataset_exports (
                    id TEXT PRIMARY KEY,

                    source_version_id TEXT NOT NULL,
                    source_dataset_type TEXT NOT NULL,
                    source_content_hash TEXT NOT NULL,

                    created_at TEXT NOT NULL,

                    item_count INTEGER NOT NULL,
                    train_count INTEGER NOT NULL,
                    eval_count INTEGER NOT NULL,

                    eval_percent INTEGER NOT NULL,
                    split_seed TEXT NOT NULL,

                    train_sha256 TEXT NOT NULL,
                    eval_sha256 TEXT NOT NULL,
                    manifest_sha256 TEXT NOT NULL,

                    export_path TEXT NOT NULL,
                    train_path TEXT NOT NULL,
                    eval_path TEXT NOT NULL,
                    manifest_path TEXT NOT NULL,

                    state TEXT NOT NULL,

                    UNIQUE(
                        source_version_id,
                        source_content_hash,
                        eval_percent,
                        split_seed
                    )
                );

                CREATE INDEX IF NOT EXISTS
                    idx_dataset_exports_source
                ON dataset_exports(
                    source_version_id,
                    created_at DESC
                );
                """
            )

            connection.execute(
                """
                INSERT INTO export_meta(
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
                        EXPORT_SCHEMA_VERSION
                    ),
                ),
            )

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
    def _bytes_hash(
        value: bytes,
    ) -> str:

        return hashlib.sha256(
            value
        ).hexdigest()

    @staticmethod
    def _eval_percent(
        value: int,
    ) -> int:

        if (
            isinstance(value, bool)
            or not isinstance(value, int)
        ):
            raise ValueError(
                "eval_percent deve ser inteiro."
            )

        if value < 0 or value > 50:
            raise ValueError(
                "eval_percent deve estar "
                "entre 0 e 50."
            )

        return value

    @staticmethod
    def _seed(
        value: str,
    ) -> str:

        clean = str(
            value
            or ""
        ).strip()

        if not clean:
            raise ValueError(
                "split_seed nao pode ser vazio."
            )

        if len(clean) > 200:
            raise ValueError(
                "split_seed excede 200 caracteres."
            )

        return clean

    @classmethod
    def _rank(
        cls,
        content_hash: str,
        seed: str,
    ) -> str:

        return hashlib.sha256(
            (
                seed
                + ":"
                + str(
                    content_hash
                )
            ).encode(
                "utf-8"
            )
        ).hexdigest()

    @classmethod
    def _split(
        cls,
        items: list[
            dict[str, Any]
        ],
        *,
        eval_percent: int,
        split_seed: str,
    ) -> tuple[
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]:

        count = len(
            items
        )

        if count == 0:
            raise DatasetExportError(
                "Dataset nao pode ser vazio."
            )

        if (
            count < 2
            or eval_percent == 0
        ):
            return (
                list(items),
                [],
            )

        desired = round(
            count
            * eval_percent
            / 100
        )

        eval_count = max(
            1,
            min(
                count - 1,
                desired,
            ),
        )

        ranked = sorted(
            items,
            key=lambda item: (
                cls._rank(
                    str(
                        item[
                            "content_hash"
                        ]
                    ),
                    split_seed,
                ),
                str(
                    item[
                        "content_hash"
                    ]
                ),
            ),
        )

        eval_ids = {
            str(
                item[
                    "content_hash"
                ]
            )
            for item
            in ranked[
                :eval_count
            ]
        }

        train = []
        evaluation = []

        for item in items:
            if (
                str(
                    item[
                        "content_hash"
                    ]
                )
                in eval_ids
            ):
                evaluation.append(
                    item
                )
            else:
                train.append(
                    item
                )

        return (
            train,
            evaluation,
        )

    @staticmethod
    def _validate_source(
        source_version: dict[
            str,
            Any
        ],
        items: list[
            dict[str, Any]
        ],
    ) -> None:

        required = {
            "id",
            "dataset_type",
            "content_hash",
            "item_count",
            "state",
        }

        missing = [
            key
            for key
            in required
            if key not in source_version
        ]

        if missing:
            raise DatasetExportError(
                "Source version incompleta: "
                + ", ".join(
                    sorted(
                        missing
                    )
                )
            )

        if (
            source_version[
                "state"
            ]
            != "approved-for-export"
        ):
            raise DatasetExportError(
                "Dataset precisa estar "
                "approved-for-export."
            )

        if (
            int(
                source_version[
                    "item_count"
                ]
            )
            != len(
                items
            )
        ):
            raise DatasetExportError(
                "Source item_count nao confere."
            )

        if not items:
            raise DatasetExportError(
                "Source dataset vazio."
            )

        seen = set()

        for item in items:
            for key in (
                "id",
                "content_hash",
                "payload",
                "provenance",
            ):
                if key not in item:
                    raise DatasetExportError(
                        "Item sem campo obrigatorio: "
                        + key
                    )

            digest = str(
                item[
                    "content_hash"
                ]
            )

            if digest in seen:
                raise DatasetExportError(
                    "Content hash duplicado "
                    "no source dataset."
                )

            seen.add(
                digest
            )

    def plan_export(
        self,
        source_version: dict[
            str,
            Any
        ],
        items: list[
            dict[str, Any]
        ],
        *,
        eval_percent: int = DEFAULT_EVAL_PERCENT,
        split_seed: str = DEFAULT_SPLIT_SEED,
    ) -> dict[str, Any]:

        eval_percent = (
            self._eval_percent(
                eval_percent
            )
        )

        split_seed = (
            self._seed(
                split_seed
            )
        )

        self._validate_source(
            source_version,
            items,
        )

        train, evaluation = (
            self._split(
                items,
                eval_percent=(
                    eval_percent
                ),
                split_seed=(
                    split_seed
                ),
            )
        )

        source_hashes = [
            str(
                item[
                    "content_hash"
                ]
            )
            for item
            in items
        ]

        plan_hash = self._json_hash(
            {
                "schema_version": (
                    EXPORT_SCHEMA_VERSION
                ),
                "source_version_id": (
                    source_version[
                        "id"
                    ]
                ),
                "source_dataset_type": (
                    source_version[
                        "dataset_type"
                    ]
                ),
                "source_content_hash": (
                    source_version[
                        "content_hash"
                    ]
                ),
                "source_item_hashes": (
                    source_hashes
                ),
                "eval_percent": (
                    eval_percent
                ),
                "split_seed": (
                    split_seed
                ),
            }
        )

        export_id = (
            str(
                source_version[
                    "dataset_type"
                ]
            )
            + "-export-"
            + plan_hash[:16]
        )

        return {
            "export_id": export_id,
            "plan_hash": plan_hash,
            "source_version_id": (
                source_version[
                    "id"
                ]
            ),
            "source_dataset_type": (
                source_version[
                    "dataset_type"
                ]
            ),
            "source_content_hash": (
                source_version[
                    "content_hash"
                ]
            ),
            "item_count": len(
                items
            ),
            "train_count": len(
                train
            ),
            "eval_count": len(
                evaluation
            ),
            "eval_percent": (
                eval_percent
            ),
            "split_seed": (
                split_seed
            ),
            "train_item_hashes": [
                item[
                    "content_hash"
                ]
                for item
                in train
            ],
            "eval_item_hashes": [
                item[
                    "content_hash"
                ]
                for item
                in evaluation
            ],
        }

    @staticmethod
    def _export_row(
        source_version: dict[
            str,
            Any
        ],
        item: dict[
            str,
            Any
        ],
        split: str,
    ) -> dict[str, Any]:

        return {
            "dataset_type": (
                source_version[
                    "dataset_type"
                ]
            ),
            "source_version_id": (
                source_version[
                    "id"
                ]
            ),
            "source_item_id": (
                item[
                    "id"
                ]
            ),
            "source_content_hash": (
                item[
                    "content_hash"
                ]
            ),
            "split": split,
            "payload": (
                item[
                    "payload"
                ]
            ),
            "provenance": (
                item[
                    "provenance"
                ]
            ),
        }

    def create_export(
        self,
        source_version: dict[
            str,
            Any
        ],
        items: list[
            dict[str, Any]
        ],
        *,
        eval_percent: int = DEFAULT_EVAL_PERCENT,
        split_seed: str = DEFAULT_SPLIT_SEED,
        metadata: dict[
            str,
            Any
        ] | None = None,
    ) -> dict[str, Any]:

        plan = self.plan_export(
            source_version,
            items,
            eval_percent=(
                eval_percent
            ),
            split_seed=(
                split_seed
            ),
        )

        with self._connection() as connection:
            existing = connection.execute(
                """
                SELECT id
                FROM dataset_exports
                WHERE id = ?
                """,
                (
                    plan[
                        "export_id"
                    ],
                ),
            ).fetchone()

        if existing is not None:
            raise DatasetExportError(
                "Export identico ja existe: "
                + str(
                    existing[
                        "id"
                    ]
                )
            )

        train, evaluation = (
            self._split(
                items,
                eval_percent=(
                    plan[
                        "eval_percent"
                    ]
                ),
                split_seed=(
                    plan[
                        "split_seed"
                    ]
                ),
            )
        )

        export_dir = (
            self.root
            / str(
                source_version[
                    "dataset_type"
                ]
            )
            / plan[
                "export_id"
            ]
        )

        if export_dir.exists():
            raise DatasetExportError(
                "Diretorio de export ja existe."
            )

        temp_dir = (
            export_dir.parent
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
            export_dir
            / "train.jsonl"
        )

        eval_path = (
            export_dir
            / "eval.jsonl"
        )

        manifest_path = (
            export_dir
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
                for item in train:
                    handle.write(
                        json.dumps(
                            self._export_row(
                                source_version,
                                item,
                                "train",
                            ),
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
                for item in evaluation:
                    handle.write(
                        json.dumps(
                            self._export_row(
                                source_version,
                                item,
                                "eval",
                            ),
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                        + "\n"
                    )

            train_sha = (
                self._bytes_hash(
                    temp_train.read_bytes()
                )
            )

            eval_sha = (
                self._bytes_hash(
                    temp_eval.read_bytes()
                )
            )

            created_at = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

            manifest = {
                "schema_version": (
                    EXPORT_SCHEMA_VERSION
                ),
                "export_id": (
                    plan[
                        "export_id"
                    ]
                ),
                "created_at": (
                    created_at
                ),
                "state": (
                    "ready-local"
                ),
                "source": {
                    "version_id": (
                        source_version[
                            "id"
                        ]
                    ),
                    "dataset_type": (
                        source_version[
                            "dataset_type"
                        ]
                    ),
                    "content_hash": (
                        source_version[
                            "content_hash"
                        ]
                    ),
                    "item_count": (
                        len(
                            items
                        )
                    ),
                    "state": (
                        source_version[
                            "state"
                        ]
                    ),
                },
                "split": {
                    "method": (
                        "sha256-ranked-v1"
                    ),
                    "seed": (
                        plan[
                            "split_seed"
                        ]
                    ),
                    "eval_percent": (
                        plan[
                            "eval_percent"
                        ]
                    ),
                    "train_count": (
                        len(
                            train
                        )
                    ),
                    "eval_count": (
                        len(
                            evaluation
                        )
                    ),
                },
                "files": {
                    "train": {
                        "name": (
                            "train.jsonl"
                        ),
                        "sha256": (
                            train_sha
                        ),
                    },
                    "eval": {
                        "name": (
                            "eval.jsonl"
                        ),
                        "sha256": (
                            eval_sha
                        ),
                    },
                },
                "plan_hash": (
                    plan[
                        "plan_hash"
                    ]
                ),
                "metadata": (
                    metadata
                    or {}
                ),
                "automatic_training": (
                    False
                ),
                "external_export": (
                    False
                ),
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

            manifest_sha = (
                self._bytes_hash(
                    temp_manifest.read_bytes()
                )
            )

            os.replace(
                temp_dir,
                export_dir,
            )

            with self._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO dataset_exports(
                        id,
                        source_version_id,
                        source_dataset_type,
                        source_content_hash,
                        created_at,
                        item_count,
                        train_count,
                        eval_count,
                        eval_percent,
                        split_seed,
                        train_sha256,
                        eval_sha256,
                        manifest_sha256,
                        export_path,
                        train_path,
                        eval_path,
                        manifest_path,
                        state
                    )
                    VALUES(
                        ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        plan[
                            "export_id"
                        ],
                        source_version[
                            "id"
                        ],
                        source_version[
                            "dataset_type"
                        ],
                        source_version[
                            "content_hash"
                        ],
                        created_at,
                        len(
                            items
                        ),
                        len(
                            train
                        ),
                        len(
                            evaluation
                        ),
                        plan[
                            "eval_percent"
                        ],
                        plan[
                            "split_seed"
                        ],
                        train_sha,
                        eval_sha,
                        manifest_sha,
                        str(
                            export_dir
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
                        "ready-local",
                    ),
                )

        except Exception:
            shutil.rmtree(
                temp_dir,
                ignore_errors=True,
            )

            shutil.rmtree(
                export_dir,
                ignore_errors=True,
            )

            raise

        result = self.get_export(
            plan[
                "export_id"
            ]
        )

        if result is None:
            raise DatasetExportError(
                "Export nao registrado."
            )

        return result

    def get_export(
        self,
        export_id: str,
    ) -> dict[
        str,
        Any
    ] | None:

        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM dataset_exports
                WHERE id = ?
                """,
                (
                    export_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return dict(
            row
        )

    def list_exports(
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
                FROM dataset_exports
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

    def verify_export(
        self,
        export_id: str,
    ) -> dict[str, Any]:

        record = self.get_export(
            export_id
        )

        if record is None:
            raise DatasetExportError(
                "Export inexistente."
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
                raise DatasetExportError(
                    "Export path saiu "
                    "do root autorizado."
                )

            if not path.is_file():
                raise DatasetExportError(
                    "Arquivo de export ausente: "
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
            raise DatasetExportError(
                "train.jsonl alterado."
            )

        if (
            eval_sha
            != record[
                "eval_sha256"
            ]
        ):
            raise DatasetExportError(
                "eval.jsonl alterado."
            )

        if (
            manifest_sha
            != record[
                "manifest_sha256"
            ]
        ):
            raise DatasetExportError(
                "manifest.json alterado."
            )

        parsed = json.loads(
            manifest.read_text(
                encoding="utf-8"
            )
        )

        train_rows = [
            line
            for line
            in train.read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip()
        ]

        eval_rows = [
            line
            for line
            in evaluation.read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip()
        ]

        if (
            len(
                train_rows
            )
            != int(
                record[
                    "train_count"
                ]
            )
        ):
            raise DatasetExportError(
                "Train count invalido."
            )

        if (
            len(
                eval_rows
            )
            != int(
                record[
                    "eval_count"
                ]
            )
        ):
            raise DatasetExportError(
                "Eval count invalido."
            )

        if (
            parsed[
                "source"
            ][
                "content_hash"
            ]
            != record[
                "source_content_hash"
            ]
        ):
            raise DatasetExportError(
                "Source hash binding invalido."
            )

        return {
            "integrity": True,
            "export_id": (
                export_id
            ),
            "state": (
                record[
                    "state"
                ]
            ),
            "source_version_id": (
                record[
                    "source_version_id"
                ]
            ),
            "item_count": int(
                record[
                    "item_count"
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
            "automatic_training": (
                False
            ),
            "external_export": (
                False
            ),
        }

    def status(
        self,
    ) -> dict[str, Any]:

        with self._connection() as connection:
            exports = int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM dataset_exports
                    """
                ).fetchone()[0]
            )

            items = int(
                connection.execute(
                    """
                    SELECT COALESCE(
                        SUM(item_count),
                        0
                    )
                    FROM dataset_exports
                    """
                ).fetchone()[0]
            )

        return {
            "status": "ok",
            "schema_version": (
                EXPORT_SCHEMA_VERSION
            ),
            "root": str(
                self.root
            ),
            "registry_path": str(
                self.registry_path
            ),
            "exports": exports,
            "items": items,
            "split_method": (
                "sha256-ranked-v1"
            ),
            "automatic_training": False,
            "external_export": False,
        }