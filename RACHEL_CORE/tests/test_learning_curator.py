import tempfile
import unittest

from pathlib import Path

from rachel_core.adapters.learning_sqlite import (
    SQLiteLearningAdapter,
)
from rachel_core.dataset_factory import (
    DatasetFactory,
)
from rachel_core.learning_curator import (
    LearningCurator,
)


class LearningCuratorTests(
    unittest.TestCase
):
    def setUp(
        self,
    ) -> None:
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

        self.factory = (
            DatasetFactory(
                root
                / "datasets"
            )
        )

        self.curator = (
            LearningCurator(
                self.learning,
                self.factory,
                minimum_quality_score=80,
            )
        )

    def tearDown(
        self,
    ) -> None:
        self.temp.cleanup()

    def capture_chat(
        self,
        *,
        user: str = "entrada",
        assistant: str = "saida",
        score: int = 100,
        accepted: bool = True,
        verdict: str | None = "accepted",
        correction: str | None = None,
    ) -> str:
        experience_id = (
            self.learning
            .capture_chat(
                conversation_id=(
                    "conv_test"
                ),
                run_id=(
                    "run_test"
                ),
                user_content=user,
                assistant_content=assistant,
                provider=(
                    "openai-compatible"
                ),
                model=(
                    "qwen3:1.7b"
                ),
                input_tokens=10,
                output_tokens=10,
                duration_ms=25,
                metadata={},
            )
        )

        self.learning.update_quality(
            experience_id,
            accepted=accepted,
            score=score,
            issues=[],
            checks={
                "not_empty": True,
            },
        )

        if verdict is not None:
            self.learning.capture_feedback(
                experience_id=(
                    experience_id
                ),
                verdict=verdict,
                correction_text=(
                    correction
                ),
            )

        return experience_id

    def test_dany_and_user_gate_accept_conversation(
        self,
    ):
        self.capture_chat()

        curated = (
            self.curator
            .collect()
        )

        self.assertEqual(
            1,
            len(
                curated[
                    "buckets"
                ][
                    "conversation"
                ]
            ),
        )

        self.assertEqual(
            1,
            curated[
                "stats"
            ][
                "candidates"
            ],
        )

    def test_dany_rejection_blocks_conversation(
        self,
    ):
        self.capture_chat(
            score=40,
            accepted=False,
        )

        curated = (
            self.curator
            .collect()
        )

        self.assertEqual(
            0,
            len(
                curated[
                    "buckets"
                ][
                    "conversation"
                ]
            ),
        )

        self.assertEqual(
            1,
            curated[
                "stats"
            ][
                "dany_rejected"
            ],
        )

    def test_unreviewed_chat_is_not_curated(
        self,
    ):
        self.capture_chat(
            verdict=None,
        )

        curated = (
            self.curator
            .collect()
        )

        self.assertEqual(
            0,
            curated[
                "stats"
            ][
                "candidates"
            ],
        )

        self.assertEqual(
            1,
            curated[
                "stats"
            ][
                "user_not_approved"
            ],
        )

    def test_corrected_feedback_creates_preference_and_corrected_conversation(
        self,
    ):
        self.capture_chat(
            assistant=(
                "resposta antiga"
            ),
            verdict=(
                "corrected"
            ),
            correction=(
                "resposta corrigida"
            ),
        )

        curated = (
            self.curator
            .collect()
        )

        conversation = (
            curated[
                "buckets"
            ][
                "conversation"
            ][0]
        )

        preference = (
            curated[
                "buckets"
            ][
                "preference"
            ][0]
        )

        self.assertEqual(
            "resposta corrigida",
            conversation[
                "payload"
            ][
                "assistant"
            ],
        )

        self.assertEqual(
            "resposta antiga",
            preference[
                "payload"
            ][
                "rejected_response"
            ],
        )

        self.assertEqual(
            "resposta corrigida",
            preference[
                "payload"
            ][
                "preferred_response"
            ],
        )

    def test_structured_events_are_classified_but_not_auto_promoted(
        self,
    ):
        self.learning.capture_event(
            kind=(
                "planner_decision"
            ),
            payload={
                "plan": {
                    "action": "tool",
                }
            },
            provider=(
                "openai-compatible"
            ),
            model=(
                "qwen3:1.7b"
            ),
        )

        curated = (
            self.curator
            .collect()
        )

        self.assertEqual(
            "planning",
            self.curator
            .classify_event_kind(
                "planner_decision"
            ),
        )

        self.assertEqual(
            "tool-use",
            self.curator
            .classify_event_kind(
                "tool_result"
            ),
        )

        self.assertEqual(
            0,
            len(
                curated[
                    "buckets"
                ][
                    "planning"
                ]
            ),
        )

        self.assertEqual(
            1,
            curated[
                "stats"
            ][
                "events_not_approved"
            ],
        )

        self.assertFalse(
            curated[
                "automatic_promotion"
            ]
        )

    def test_materialization_is_explicit_and_global_dedup_blocks_repeat(
        self,
    ):
        self.capture_chat()

        first = (
            self.curator
            .collect()
        )

        versions = (
            self.curator
            .materialize(
                first,
                metadata={
                    "test": True,
                },
            )
        )

        self.assertIn(
            "conversation",
            versions,
        )

        second = (
            self.curator
            .collect()
        )

        self.assertEqual(
            0,
            len(
                second[
                    "buckets"
                ][
                    "conversation"
                ]
            ),
        )

        self.assertGreaterEqual(
            second[
                "stats"
            ][
                "duplicates"
            ],
            1,
        )

        status = (
            self.factory
            .status()
        )

        self.assertEqual(
            1,
            status[
                "versions"
            ],
        )

        self.assertFalse(
            status[
                "automatic_training"
            ]
        )


if __name__ == "__main__":
    unittest.main()
