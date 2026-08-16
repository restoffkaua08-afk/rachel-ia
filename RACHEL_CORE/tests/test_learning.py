import sqlite3
from contextlib import closing
import tempfile
import unittest

from pathlib import Path

from rachel_core.adapters.audit_jsonl import JsonlAuditAdapter
from rachel_core.adapters.knowledge_null import NullKnowledgeAdapter
from rachel_core.adapters.learning_sqlite import SQLiteLearningAdapter
from rachel_core.adapters.memory_sqlite import SQLiteMemoryAdapter
from rachel_core.adapters.model_mock import MockModelAdapter
from rachel_core.application import ChatService
from rachel_core.domain.models import ChatRequest


class RachelLearningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)

        self.learning_path = (
            root
            / "learning.db"
        )

        self.learning = SQLiteLearningAdapter(
            self.learning_path
        )

        self.memory = SQLiteMemoryAdapter(
            root
            / "rachel.db"
        )

        self.audit = JsonlAuditAdapter(
            root
            / "audit.jsonl"
        )

        self.service = ChatService(
            model=MockModelAdapter(),
            memory=self.memory,
            audit=self.audit,
            knowledge=NullKnowledgeAdapter(),
            learning=self.learning,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_chat_creates_learning_experience(self) -> None:
        result = self.service.chat(
            ChatRequest(
                content="Teste de aprendizado"
            )
        )

        experience_id = (
            result
            .message
            .metadata
            .get("learning_experience_id")
        )

        self.assertTrue(
            experience_id
        )

        status = self.learning.status()

        self.assertEqual(
            1,
            status["experiences"],
        )

        self.assertFalse(
            status["automatic_training"]
        )

    def test_learning_redacts_known_secret(self) -> None:
        self.service.chat(
            ChatRequest(
                content=(
                    "api_key="
                    "super-secret-value"
                )
            )
        )

        with closing(
            sqlite3.connect(
                self.learning_path
            )
        ) as connection:
            value = connection.execute(
                """
                SELECT user_content
                FROM experiences
                LIMIT 1
                """
            ).fetchone()[0]

        self.assertNotIn(
            "super-secret-value",
            value,
        )

        self.assertIn(
            "[REDACTED]",
            value,
        )

    def test_quality_can_be_attached(self) -> None:
        result = self.service.chat(
            ChatRequest(
                content="Qualidade"
            )
        )

        experience_id = (
            result
            .message
            .metadata[
                "learning_experience_id"
            ]
        )

        self.learning.update_quality(
            experience_id,
            accepted=True,
            score=100,
            issues=[],
            checks={
                "not_empty": True,
            },
        )

        with closing(
            sqlite3.connect(
                self.learning_path
            )
        ) as connection:
            row = connection.execute(
                """
                SELECT
                    quality_accepted,
                    quality_score
                FROM experiences
                WHERE id = ?
                """,
                (experience_id,),
            ).fetchone()

        self.assertEqual(
            (1, 100),
            row,
        )

    def test_nothing_is_approved_for_training_automatically(self) -> None:
        self.service.chat(
            ChatRequest(
                content="Nao treine automaticamente"
            )
        )

        status = self.learning.status()

        self.assertEqual(
            0,
            status[
                "approved_for_training"
            ],
        )


if __name__ == "__main__":
    unittest.main()