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

from .privacy import redact


DATASET_SCHEMA_VERSION = 1

DATASET_TYPES = frozenset(
    {
        "conversation",
        "coding",
        "tool-use",
        "planning",
        "preference",
        "knowledge",
    }
)


class DatasetFactoryError(RuntimeError):
    pass


class DatasetFactory:
    """
    Fabrica local de datasets versionados da Rachel.

    Contrato:
    - nao altera o Learning Vault de origem;
    - nao promove material automaticamente;
    - nao treina modelo automaticamente;
    - nao exporta dados para fora da maquina;
    - cada versao e imutavel depois de criada;
    - cada item carrega proveniencia e hash;
    - payload, metadata e proveniencia passam pela
      camada de privacidade antes da persistencia.
    """

    def __init__(
        self,
        root: Path,
        registry_path: Path | None = None,
    ) -> None:
        self.root = (
            root
            .expanduser()
            .resolve()
        )

        self.registry_path = (
            registry_path
            .expanduser()
            .resolve()
            if registry_path is not None
            else self.root
            / "dataset-registry.db"
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
                dataset_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS
                dataset_versions (
                    id TEXT PRIMARY KEY,

                    dataset_type TEXT NOT NULL,

                    version_number INTEGER NOT NULL,

                    created_at TEXT NOT NULL,

                    item_count INTEGER NOT NULL,

                    content_hash TEXT NOT NULL,

                    state TEXT NOT NULL,

                    manifest_path TEXT NOT NULL,

                    data_path TEXT NOT NULL,

                    metadata_json TEXT NOT NULL,

                    UNIQUE(
                        dataset_type,
                        version_number
                    ),

                    UNIQUE(
                        dataset_type,
                        content_hash
                    )
                );

                CREATE INDEX IF NOT EXISTS
                    idx_dataset_versions_type
                ON dataset_versions(
                    dataset_type,
                    version_number DESC
                );

                CREATE TABLE IF NOT EXISTS
                dataset_items (
                    id TEXT PRIMARY KEY,

                    version_id TEXT NOT NULL,

                    position INTEGER NOT NULL,

                    source_kind TEXT NOT NULL,

                    source_id TEXT NOT NULL,

                    content_hash TEXT NOT NULL,

                    provenance_json TEXT NOT NULL,

                    FOREIGN KEY(version_id)
                        REFERENCES
                        dataset_versions(id)
                        ON DELETE RESTRICT,

                    UNIQUE(
                        version_id,
                        position
                    ),

                    UNIQUE(
                        version_id,
                        content_hash
                    )
                );

                CREATE INDEX IF NOT EXISTS
                    idx_dataset_items_version
                ON dataset_items(
                    version_id
                );

                CREATE INDEX IF NOT EXISTS
                    idx_dataset_items_source
                ON dataset_items(
                    source_kind,
                    source_id
                );
                """
            )

            connection.execute(
                """
                INSERT INTO dataset_meta(
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
                        DATASET_SCHEMA_VERSION
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
    def _sha256(
        cls,
        value: Any,
    ) -> str:
        payload = (
            cls
            ._canonical_json(
                value
            )
            .encode(
                "utf-8"
            )
        )

        return (
            hashlib
            .sha256(
                payload
            )
            .hexdigest()
        )

    @staticmethod
    def _dataset_type(
        value: str,
    ) -> str:
        selected = (
            str(value)
            .strip()
            .casefold()
        )

        if selected not in DATASET_TYPES:
            raise ValueError(
                "Dataset type invalido. "
                "Use conversation, coding, "
                "tool-use, planning, preference "
                "ou knowledge."
            )

        return selected

    @staticmethod
    def _required_text(
        value: Any,
        field: str,
        maximum: int,
    ) -> str:
        clean = str(
            value or ""
        ).strip()

        if not clean:
            raise ValueError(
                f"{field} e obrigatorio."
            )

        if len(clean) > maximum:
            raise ValueError(
                f"{field} excede "
                f"{maximum} caracteres."
            )

        return clean

    @classmethod
    def _prepare_item(
        cls,
        raw: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(
            raw,
            dict,
        ):
            raise TypeError(
                "Cada item de dataset "
                "deve ser objeto."
            )

        if "payload" not in raw:
            raise ValueError(
                "payload e obrigatorio."
            )

        source_kind = (
            cls._required_text(
                raw.get(
                    "source_kind"
                ),
                "source_kind",
                100,
            )
        )

        source_id = (
            cls._required_text(
                raw.get(
                    "source_id"
                ),
                "source_id",
                200,
            )
        )

        provenance_raw = (
            raw.get(
                "provenance"
            )
            or {}
        )

        if not isinstance(
            provenance_raw,
            dict,
        ):
            raise TypeError(
                "provenance deve ser objeto."
            )

        payload = redact(
            raw[
                "payload"
            ]
        )

        provenance = redact(
            {
                **provenance_raw,

                "source_kind": (
                    source_kind
                ),

                "source_id": (
                    source_id
                ),
            }
        )

        content_hash = (
            cls._sha256(
                {
                    "payload": (
                        payload
                    ),
                    "provenance": (
                        provenance
                    ),
                }
            )
        )

        return {
            "source_kind": (
                source_kind
            ),
            "source_id": (
                source_id
            ),
            "payload": (
                payload
            ),
            "provenance": (
                provenance
            ),
            "content_hash": (
                content_hash
            ),
        }

    def _next_version_number(
        self,
        dataset_type: str,
    ) -> int:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(
                    MAX(version_number),
                    0
                )
                FROM dataset_versions
                WHERE dataset_type = ?
                """,
                (
                    dataset_type,
                ),
            ).fetchone()

        return (
            int(
                row[0]
            )
            + 1
        )

    def create_version(
        self,
        dataset_type: str,
        items: list[
            dict[str, Any]
        ],
        *,
        metadata: dict[
            str,
            Any
        ] | None = None,
    ) -> dict[str, Any]:

        selected = (
            self._dataset_type(
                dataset_type
            )
        )

        if not isinstance(
            items,
            list,
        ):
            raise TypeError(
                "items deve ser lista."
            )

        if not items:
            raise ValueError(
                "Dataset precisa de "
                "pelo menos um item."
            )

        safe_metadata = redact(
            metadata or {}
        )

        prepared = [
            self._prepare_item(
                item
            )
            for item in items
        ]

        unique: list[
            dict[str, Any]
        ] = []

        seen_hashes: set[
            str
        ] = set()

        for item in prepared:
            digest = str(
                item[
                    "content_hash"
                ]
            )

            if digest in seen_hashes:
                continue

            seen_hashes.add(
                digest
            )

            unique.append(
                item
            )

        dataset_hash = (
            self._sha256(
                {
                    "dataset_type": (
                        selected
                    ),

                    "items": [
                        item[
                            "content_hash"
                        ]
                        for item
                        in unique
                    ],

                    "metadata": (
                        safe_metadata
                    ),
                }
            )
        )

        with self._connection() as connection:
            existing = connection.execute(
                """
                SELECT id
                FROM dataset_versions
                WHERE dataset_type = ?
                  AND content_hash = ?
                """,
                (
                    selected,
                    dataset_hash,
                ),
            ).fetchone()

        if existing is not None:
            raise DatasetFactoryError(
                "Versao identica ja existe: "
                + str(
                    existing[
                        "id"
                    ]
                )
            )

        version_number = (
            self._next_version_number(
                selected
            )
        )

        version_id = (
            f"{selected}-"
            f"v{version_number:06d}-"
            f"{dataset_hash[:12]}"
        )

        created_at = (
            datetime.now(
                timezone.utc
            )
            .isoformat()
        )

        version_dir = (
            self.root
            / selected
            / version_id
        )

        if version_dir.exists():
            raise DatasetFactoryError(
                "Diretorio de versao "
                f"ja existe: {version_dir}"
            )

        temp_dir = (
            version_dir.parent
            / (
                ".tmp-"
                + uuid.uuid4().hex
            )
        )

        temp_dir.mkdir(
            parents=True,
            exist_ok=False,
        )

        data_path = (
            version_dir
            / "data.jsonl"
        )

        manifest_path = (
            version_dir
            / "manifest.json"
        )

        rows: list[
            dict[str, Any]
        ] = []

        for position, item in enumerate(
            unique,
            start=1,
        ):
            item_id = (
                "item_"
                + self._sha256(
                    {
                        "version_id": (
                            version_id
                        ),

                        "content_hash": (
                            item[
                                "content_hash"
                            ]
                        ),
                    }
                )[:24]
            )

            rows.append(
                {
                    "id": (
                        item_id
                    ),

                    "dataset_type": (
                        selected
                    ),

                    "version_id": (
                        version_id
                    ),

                    "position": (
                        position
                    ),

                    "source_kind": (
                        item[
                            "source_kind"
                        ]
                    ),

                    "source_id": (
                        item[
                            "source_id"
                        ]
                    ),

                    "content_hash": (
                        item[
                            "content_hash"
                        ]
                    ),

                    "provenance": (
                        item[
                            "provenance"
                        ]
                    ),

                    "payload": (
                        item[
                            "payload"
                        ]
                    ),
                }
            )

        manifest = {
            "schema_version": (
                DATASET_SCHEMA_VERSION
            ),

            "dataset_type": (
                selected
            ),

            "version_number": (
                version_number
            ),

            "version_id": (
                version_id
            ),

            "created_at": (
                created_at
            ),

            "item_count": (
                len(
                    rows
                )
            ),

            "content_hash": (
                dataset_hash
            ),

            "state": (
                "candidate"
            ),

            "metadata": (
                safe_metadata
            ),

            "automatic_training": (
                False
            ),

            "automatic_promotion": (
                False
            ),

            "external_export": (
                False
            ),
        }

        try:
            temp_data = (
                temp_dir
                / "data.jsonl"
            )

            with temp_data.open(
                "w",
                encoding="utf-8",
                newline="\n",
            ) as handle:

                for row in rows:
                    handle.write(
                        json.dumps(
                            row,
                            ensure_ascii=False,
                            sort_keys=True,
                        )
                        + "\n"
                    )

            temp_manifest = (
                temp_dir
                / "manifest.json"
            )

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

            os.replace(
                temp_dir,
                version_dir,
            )

            with self._connection() as connection:

                connection.execute(
                    """
                    INSERT INTO dataset_versions(
                        id,
                        dataset_type,
                        version_number,
                        created_at,
                        item_count,
                        content_hash,
                        state,
                        manifest_path,
                        data_path,
                        metadata_json
                    )
                    VALUES(
                        ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?
                    )
                    """,
                    (
                        version_id,
                        selected,
                        version_number,
                        created_at,
                        len(
                            rows
                        ),
                        dataset_hash,
                        "candidate",
                        str(
                            manifest_path
                        ),
                        str(
                            data_path
                        ),
                        self._canonical_json(
                            safe_metadata
                        ),
                    ),
                )

                for row in rows:
                    connection.execute(
                        """
                        INSERT INTO dataset_items(
                            id,
                            version_id,
                            position,
                            source_kind,
                            source_id,
                            content_hash,
                            provenance_json
                        )
                        VALUES(
                            ?, ?, ?, ?, ?, ?, ?
                        )
                        """,
                        (
                            row[
                                "id"
                            ],

                            version_id,

                            row[
                                "position"
                            ],

                            row[
                                "source_kind"
                            ],

                            row[
                                "source_id"
                            ],

                            row[
                                "content_hash"
                            ],

                            self._canonical_json(
                                row[
                                    "provenance"
                                ]
                            ),
                        ),
                    )

        except Exception:
            shutil.rmtree(
                temp_dir,
                ignore_errors=True,
            )

            shutil.rmtree(
                version_dir,
                ignore_errors=True,
            )

            raise

        return manifest

    def get_version(
        self,
        version_id: str,
    ) -> dict[
        str,
        Any
    ] | None:

        with self._connection() as connection:

            row = connection.execute(
                """
                SELECT
                    id,
                    dataset_type,
                    version_number,
                    created_at,
                    item_count,
                    content_hash,
                    state,
                    manifest_path,
                    data_path,
                    metadata_json
                FROM dataset_versions
                WHERE id = ?
                """,
                (
                    version_id,
                ),
            ).fetchone()

        if row is None:
            return None

        result = dict(
            row
        )

        result[
            "metadata"
        ] = json.loads(
            result.pop(
                "metadata_json"
            )
        )

        return result

    def list_versions(
        self,
        dataset_type: str | None = None,
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

        selected = (
            self._dataset_type(
                dataset_type
            )
            if dataset_type
            is not None
            else None
        )

        query = """
            SELECT
                id,
                dataset_type,
                version_number,
                created_at,
                item_count,
                content_hash,
                state,
                manifest_path,
                data_path,
                metadata_json
            FROM dataset_versions
        """

        if selected is None:
            query += (
                " ORDER BY created_at DESC "
                "LIMIT ?"
            )

            parameters: tuple[
                Any,
                ...
            ] = (
                limit,
            )

        else:
            query += (
                " WHERE dataset_type = ? "
                "ORDER BY version_number DESC "
                "LIMIT ?"
            )

            parameters = (
                selected,
                limit,
            )

        with self._connection() as connection:

            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

        output: list[
            dict[str, Any]
        ] = []

        for row in rows:
            item = dict(
                row
            )

            item[
                "metadata"
            ] = json.loads(
                item.pop(
                    "metadata_json"
                )
            )

            output.append(
                item
            )

        return output

    def content_hash_for_item(
        self,
        item: dict[str, Any],
    ) -> str:
        return str(
            self._prepare_item(
                item
            )[
                "content_hash"
            ]
        )

    def contains_content_hash(
        self,
        content_hash: str,
    ) -> bool:
        digest = str(
            content_hash
        ).strip()

        if not digest:
            return False

        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM dataset_items
                WHERE content_hash = ?
                LIMIT 1
                """,
                (
                    digest,
                ),
            ).fetchone()

        return (
            row
            is not None
        )

    def contains_source(
        self,
        source_kind: str,
        source_id: str,
    ) -> bool:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM dataset_items
                WHERE source_kind = ?
                  AND source_id = ?
                LIMIT 1
                """,
                (
                    str(
                        source_kind
                    ).strip(),
                    str(
                        source_id
                    ).strip(),
                ),
            ).fetchone()

        return (
            row
            is not None
        )

    def status(
        self,
    ) -> dict[
        str,
        Any
    ]:

        with self._connection() as connection:

            versions = int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM dataset_versions
                    """
                ).fetchone()[0]
            )

            items = int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM dataset_items
                    """
                ).fetchone()[0]
            )

            rows = connection.execute(
                """
                SELECT
                    dataset_type,
                    COUNT(*) AS versions
                FROM dataset_versions
                GROUP BY dataset_type
                ORDER BY dataset_type
                """
            ).fetchall()

        return {
            "status": (
                "ok"
            ),

            "schema_version": (
                DATASET_SCHEMA_VERSION
            ),

            "root": str(
                self.root
            ),

            "registry_path": str(
                self.registry_path
            ),

            "dataset_types": sorted(
                DATASET_TYPES
            ),

            "versions": (
                versions
            ),

            "items": (
                items
            ),

            "versions_by_type": {
                str(
                    row[
                        "dataset_type"
                    ]
                ): int(
                    row[
                        "versions"
                    ]
                )
                for row
                in rows
            },

            "automatic_training": (
                False
            ),

            "automatic_promotion": (
                False
            ),

            "external_export": (
                False
            ),
        }