from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Any

from ..domain.enums import Role
from ..domain.errors import StorageError
from ..domain.models import Conversation, Message, utc_now


class SQLiteMemoryAdapter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._migrate()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _migrate(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_messages_conversation
                    ON messages(conversation_id, created_at);
                INSERT OR IGNORE INTO schema_version(version, applied_at) VALUES (1, CURRENT_TIMESTAMP);
                """
            )

    def create_conversation(self, title: str) -> Conversation:
        conversation = Conversation(title=title.strip()[:120] or "Nova conversa")
        try:
            with self._lock, self._connection() as connection:
                connection.execute(
                    "INSERT INTO conversations(id,title,created_at,updated_at) VALUES(?,?,?,?)",
                    (
                        conversation.id,
                        conversation.title,
                        conversation.created_at,
                        conversation.updated_at,
                    ),
                )
        except sqlite3.Error as exc:
            raise StorageError(f"Falha ao criar conversa: {exc}") from exc
        return conversation

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
        return Conversation(**dict(row)) if row else None

    def list_conversations(self, limit: int = 50) -> list[Conversation]:
        limit = max(1, min(limit, 200))
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [Conversation(**dict(row)) for row in rows]

    def add_message(self, message: Message) -> None:
        try:
            with self._lock, self._connection() as connection:
                connection.execute(
                    """INSERT INTO messages
                    (id,conversation_id,role,content,created_at,metadata_json)
                    VALUES(?,?,?,?,?,?)""",
                    (
                        message.id,
                        message.conversation_id,
                        message.role.value,
                        message.content,
                        message.created_at,
                        json.dumps(message.metadata, ensure_ascii=False),
                    ),
                )
                connection.execute(
                    "UPDATE conversations SET updated_at = ? WHERE id = ?",
                    (utc_now(), message.conversation_id),
                )
        except sqlite3.Error as exc:
            raise StorageError(f"Falha ao salvar mensagem: {exc}") from exc

    def list_messages(self, conversation_id: str, limit: int = 100) -> list[Message]:
        limit = max(1, min(limit, 1000))
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT * FROM (
                    SELECT * FROM messages WHERE conversation_id = ?
                    ORDER BY created_at DESC LIMIT ?
                ) ORDER BY created_at ASC""",
                (conversation_id, limit),
            ).fetchall()
        return [
            Message(
                id=row["id"],
                conversation_id=row["conversation_id"],
                role=Role(row["role"]),
                content=row["content"],
                created_at=row["created_at"],
                metadata=json.loads(row["metadata_json"]),
            )
            for row in rows
        ]

    def delete_conversation(self, conversation_id: str) -> bool:
        with self._lock, self._connection() as connection:
            cursor = connection.execute(
                "DELETE FROM conversations WHERE id = ?", (conversation_id,)
            )
        return cursor.rowcount > 0

    def export_conversation(self, conversation_id: str) -> dict[str, Any]:
        conversation = self.get_conversation(conversation_id)
        if conversation is None:
            raise StorageError("Conversa não encontrada.")
        return {
            "format": "rachel-conversation-v1",
            "exported_at": utc_now(),
            "conversation": {
                "id": conversation.id,
                "title": conversation.title,
                "created_at": conversation.created_at,
                "updated_at": conversation.updated_at,
            },
            "messages": [m.to_dict() for m in self.list_messages(conversation_id, 1000)],
        }
