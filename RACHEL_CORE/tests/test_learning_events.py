import json
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


class LearningEventsTests(
    unittest.TestCase
):
    def setUp(
        self,
    ):
        self.temp = (
            tempfile
            .TemporaryDirectory()
        )

        root = Path(
            self.temp.name
        )

        self.learning = (
            SQLiteLearningAdapter(
                root
                / "learning.db"
            )
        )

        self.service = ChatService(
            model=MockModelAdapter(),
            memory=SQLiteMemoryAdapter(
                root
                / "rachel.db"
            ),
            audit=JsonlAuditAdapter(
                root
                / "audit.jsonl"
            ),
            knowledge=NullKnowledgeAdapter(),
            learning=self.learning,
        )

    def tearDown(
        self,
    ):
        self.temp.cleanup()

    def experience(
        self,
    ) -> str:
        result = (
            self.service
            .chat(
                ChatRequest(
                    content=(
                        "Experiencia de teste"
                    )
                )
            )
        )

        return (
            result
            .message
            .metadata[
                "learning_experience_id"
            ]
        )

    def test_schema_v2(
        self,
    ):
        status = (
            self.learning
            .status()
        )

        self.assertEqual(
            2,
            status[
                "schema_version"
            ],
        )

        self.assertEqual(
            0,
            status["events"],
        )

        self.assertEqual(
            0,
            status["feedback"],
        )

    def test_event_is_redacted_and_not_promoted(
        self,
    ):
        self.learning.capture_event(
            kind="tool_result",
            payload={
                "tool": "teste",
                "secret": (
                    "token="
                    "super-secret-value"
                ),
            },
            correlation_id="run_test",
            provider="mock",
            model="mock",
        )

        event = (
            self.learning
            .recent_events(1)[0]
        )

        serialized = json.dumps(
            event,
            ensure_ascii=False,
        )

        self.assertNotIn(
            "super-secret-value",
            serialized,
        )

        self.assertEqual(
            "captured",
            event[
                "training_state"
            ],
        )

        self.assertEqual(
            "unreviewed",
            event[
                "review_state"
            ],
        )

    def test_feedback_updates_review_only(
        self,
    ):
        experience_id = (
            self.experience()
        )

        feedback_id = (
            self.learning
            .capture_feedback(
                experience_id=(
                    experience_id
                ),
                verdict="accepted",
                note=(
                    "Resposta aprovada."
                ),
            )
        )

        self.assertTrue(
            feedback_id.startswith(
                "fb_"
            )
        )

        experience = (
            self.learning
            .recent(1)[0]
        )

        status = (
            self.learning
            .status()
        )

        self.assertEqual(
            "user_accepted",
            experience[
                "review_state"
            ],
        )

        self.assertEqual(
            "captured",
            experience[
                "training_state"
            ],
        )

        self.assertEqual(
            0,
            status[
                "approved_for_training"
            ],
        )

    def test_corrected_requires_correction_text(
        self,
    ):
        experience_id = (
            self.experience()
        )

        with self.assertRaises(
            ValueError
        ):
            self.learning.capture_feedback(
                experience_id=(
                    experience_id
                ),
                verdict="corrected",
            )


if __name__ == "__main__":
    unittest.main()
