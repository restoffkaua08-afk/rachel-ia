import json
import tempfile
import unittest
from pathlib import Path

from rachel_core.adapters.audit_jsonl import JsonlAuditAdapter
from rachel_core.adapters.knowledge_null import NullKnowledgeAdapter
from rachel_core.adapters.memory_sqlite import SQLiteMemoryAdapter
from rachel_core.adapters.model_mock import MockModelAdapter
from rachel_core.adapters.policy import DenyByDefaultPolicy
from rachel_core.application import ChatService
from rachel_core.domain.enums import PolicyEffect, RiskLevel
from rachel_core.domain.errors import ValidationError
from rachel_core.domain.models import ChatRequest, ToolCall
from rachel_core.privacy import redact_text


class RachelCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.memory = SQLiteMemoryAdapter(root / "rachel.db")
        self.audit = JsonlAuditAdapter(root / "audit.jsonl")
        self.audit_path = root / "audit.jsonl"
        self.service = ChatService(
            model=MockModelAdapter(),
            memory=self.memory,
            audit=self.audit,
            knowledge=NullKnowledgeAdapter(),
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_chat_persists_and_continues_conversation(self) -> None:
        first = self.service.chat(ChatRequest(content="Olá"))
        second = self.service.chat(
            ChatRequest(content="Continue", conversation_id=first.conversation_id)
        )
        self.assertEqual(first.conversation_id, second.conversation_id)
        messages = self.memory.list_messages(first.conversation_id)
        self.assertEqual(4, len(messages))
        self.assertIn("Continue", second.message.content)

    def test_empty_message_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.chat(ChatRequest(content="   "))

    def test_export_and_delete(self) -> None:
        result = self.service.chat(ChatRequest(content="Teste"))
        exported = self.memory.export_conversation(result.conversation_id)
        self.assertEqual("rachel-conversation-v1", exported["format"])
        self.assertEqual(2, len(exported["messages"]))
        self.assertTrue(self.memory.delete_conversation(result.conversation_id))
        self.assertIsNone(self.memory.get_conversation(result.conversation_id))

    def test_policy_denies_tools_by_default(self) -> None:
        decision = DenyByDefaultPolicy().evaluate(
            ToolCall(name="terminal.execute", arguments={}, risk=RiskLevel.PRIVILEGED, reason="x")
        )
        self.assertEqual(PolicyEffect.DENY, decision.effect)

    def test_audit_redacts_secrets(self) -> None:
        self.audit.record("test", "run_1", {"value": "api_key=secret-value"})
        content = self.audit_path.read_text(encoding="utf-8")
        self.assertNotIn("secret-value", content)
        json.loads(content)

    def test_redaction(self) -> None:
        self.assertNotIn("abc123456789012", redact_text("token=abc123456789012"))


if __name__ == "__main__":
    unittest.main()

