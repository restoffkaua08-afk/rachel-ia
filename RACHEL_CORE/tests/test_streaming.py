import tempfile
import unittest
from pathlib import Path

from rachel_core.adapters.audit_jsonl import JsonlAuditAdapter
from rachel_core.adapters.knowledge_null import NullKnowledgeAdapter
from rachel_core.adapters.memory_sqlite import SQLiteMemoryAdapter
from rachel_core.adapters.model_mock import MockModelAdapter
from rachel_core.application import ChatService, DEFAULT_SYSTEM_PROMPT
from rachel_core.domain.enums import RunState
from rachel_core.domain.models import ChatRequest


class RachelStreamingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.memory = SQLiteMemoryAdapter(root / "rachel.db")
        self.service = ChatService(
            model=MockModelAdapter(),
            memory=self.memory,
            audit=JsonlAuditAdapter(root / "audit.jsonl"),
            knowledge=NullKnowledgeAdapter(),
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_stream_emits_multiple_chunks_and_persists_complete_answer(self) -> None:
        chunks: list[str] = []
        result = self.service.chat_stream(
            ChatRequest(content="Olá streaming"),
            chunks.append,
        )

        self.assertEqual(RunState.COMPLETED, result.state)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(result.message.content, "".join(chunks))
        self.assertTrue(result.message.metadata["streamed"])

        messages = self.memory.list_messages(result.conversation_id)
        self.assertEqual(2, len(messages))
        self.assertEqual(result.message.content, messages[-1].content)

    def test_cancelled_stream_does_not_persist_partial_assistant_message(self) -> None:
        chunks: list[str] = []
        calls = 0

        def cancelled() -> bool:
            nonlocal calls
            calls += 1
            return calls >= 3

        result = self.service.chat_stream(
            ChatRequest(content="Cancele esta resposta"),
            chunks.append,
            cancelled,
        )

        self.assertEqual(RunState.CANCELLED, result.state)
        self.assertTrue(chunks)
        self.assertEqual("".join(chunks), result.message.content)

        messages = self.memory.list_messages(result.conversation_id)
        self.assertEqual(1, len(messages))
        self.assertEqual("user", messages[0].role.value)

    def test_default_prompt_does_not_claim_tools_are_disabled(self) -> None:
        self.assertNotIn("Ferramentas estão desativadas", DEFAULT_SYSTEM_PROMPT)
        self.assertIn("runtime governado", DEFAULT_SYSTEM_PROMPT)
        self.assertIn("evidência", DEFAULT_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
