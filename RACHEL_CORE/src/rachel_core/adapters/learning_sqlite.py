from __future__ import annotations

import json
import sqlite3
import uuid

from contextlib import closing, contextmanager

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from ..privacy import redact, redact_text


SCHEMA_VERSION = 1


class SQLiteLearningAdapter:
    """
    Armazena experiencias candidatas a aprendizado.

    IMPORTANTE:
    - nao treina modelo automaticamente;
    - nao promove dados automaticamente;
    - nao substitui Bran;
    - segredos conhecidos sao sanitizados antes da persistencia.
    """

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=30,
        )
        connection.row_factory = sqlite3.Row
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
    ) -> Iterator[sqlite3.Connection]:
        """
        SQLite Connection.__exit__ commits or rolls back,
        but does not close the connection.

        On Windows an unclosed SQLite handle prevents
        TemporaryDirectory cleanup. This wrapper guarantees
        both transaction finalization and handle closure.
        """
        with closing(
            self._connect()
        ) as connection:
            with connection:
                yield connection

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS learning_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS experiences (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,

                    conversation_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,

                    kind TEXT NOT NULL,

                    user_content TEXT NOT NULL,
                    assistant_content TEXT NOT NULL,

                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,

                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    duration_ms INTEGER NOT NULL,

                    quality_accepted INTEGER,
                    quality_score INTEGER,
                    quality_issues_json TEXT,
                    quality_checks_json TEXT,

                    metadata_json TEXT NOT NULL,

                    training_state TEXT NOT NULL
                        DEFAULT 'captured',

                    review_state TEXT NOT NULL
                        DEFAULT 'unreviewed'
                );

                CREATE INDEX IF NOT EXISTS
                    idx_experiences_created
                ON experiences(created_at DESC);

                CREATE INDEX IF NOT EXISTS
                    idx_experiences_conversation
                ON experiences(conversation_id);

                CREATE INDEX IF NOT EXISTS
                    idx_experiences_training_state
                ON experiences(training_state);

                CREATE INDEX IF NOT EXISTS
                    idx_experiences_review_state
                ON experiences(review_state);
                """
            )

            connection.execute(
                """
                INSERT INTO learning_meta(key, value)
                VALUES('schema_version', ?)
                ON CONFLICT(key)
                DO UPDATE SET value = excluded.value
                """,
                (str(SCHEMA_VERSION),),
            )

    def capture_chat(
        self,
        *,
        conversation_id: str,
        run_id: str,
        user_content: str,
        assistant_content: str,
        provider: str,
        model: str,
        input_tokens: int | None,
        output_tokens: int | None,
        duration_ms: int,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        experience_id = (
            "exp_"
            + uuid.uuid4().hex
        )

        created_at = datetime.now(
            timezone.utc
        ).isoformat()

        safe_metadata = redact(
            metadata or {}
        )

        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO experiences(
                    id,
                    created_at,
                    conversation_id,
                    run_id,
                    kind,
                    user_content,
                    assistant_content,
                    provider,
                    model,
                    input_tokens,
                    output_tokens,
                    duration_ms,
                    metadata_json,
                    training_state,
                    review_state
                )
                VALUES(
                    ?, ?, ?, ?, 'chat',
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, 'captured', 'unreviewed'
                )
                """,
                (
                    experience_id,
                    created_at,
                    conversation_id,
                    run_id,
                    redact_text(user_content),
                    redact_text(assistant_content),
                    provider,
                    model,
                    input_tokens,
                    output_tokens,
                    duration_ms,
                    json.dumps(
                        safe_metadata,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                ),
            )

        return experience_id

    def update_quality(
        self,
        experience_id: str,
        *,
        accepted: bool,
        score: int,
        issues: list[str] | tuple[str, ...],
        checks: dict[str, bool],
    ) -> None:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE experiences
                SET
                    quality_accepted = ?,
                    quality_score = ?,
                    quality_issues_json = ?,
                    quality_checks_json = ?
                WHERE id = ?
                """,
                (
                    1 if accepted else 0,
                    int(score),
                    json.dumps(
                        list(issues),
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        checks,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    experience_id,
                ),
            )

            if cursor.rowcount != 1:
                raise KeyError(
                    f"Experiencia inexistente: {experience_id}"
                )

    def status(self) -> dict[str, Any]:
        with self._connection() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM experiences"
            ).fetchone()[0]

            reviewed = connection.execute(
                """
                SELECT COUNT(*)
                FROM experiences
                WHERE review_state != 'unreviewed'
                """
            ).fetchone()[0]

            trainable = connection.execute(
                """
                SELECT COUNT(*)
                FROM experiences
                WHERE training_state = 'approved'
                """
            ).fetchone()[0]

        return {
            "status": "ok",
            "schema_version": SCHEMA_VERSION,
            "path": str(self.path),
            "experiences": total,
            "reviewed": reviewed,
            "approved_for_training": trainable,
            "automatic_training": False,
        }

    def recent(
        self,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        limit = max(
            1,
            min(
                100,
                int(limit),
            ),
        )

        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    created_at,
                    conversation_id,
                    run_id,
                    kind,
                    provider,
                    model,
                    duration_ms,
                    quality_accepted,
                    quality_score,
                    training_state,
                    review_state
                FROM experiences
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]