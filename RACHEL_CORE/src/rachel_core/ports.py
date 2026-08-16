from __future__ import annotations

from typing import Any, Iterable, Protocol, Sequence

from .domain.models import Conversation, Message, ModelResponse, PolicyDecision, ToolCall


class ModelPort(Protocol):
    provider_name: str
    model_name: str

    def generate(self, messages: Sequence[Message], system_prompt: str | None) -> ModelResponse: ...

    def generate_stream(
        self, messages: Sequence[Message], system_prompt: str | None
    ) -> Iterable[str]: ...


class MemoryPort(Protocol):
    def create_conversation(self, title: str) -> Conversation: ...
    def get_conversation(self, conversation_id: str) -> Conversation | None: ...
    def list_conversations(self, limit: int = 50) -> list[Conversation]: ...
    def add_message(self, message: Message) -> None: ...
    def list_messages(self, conversation_id: str, limit: int = 100) -> list[Message]: ...
    def delete_conversation(self, conversation_id: str) -> bool: ...
    def export_conversation(self, conversation_id: str) -> dict[str, Any]: ...


class PolicyPort(Protocol):
    def evaluate(self, call: ToolCall) -> PolicyDecision: ...


class AuditPort(Protocol):
    def record(self, event: str, correlation_id: str, data: dict[str, Any]) -> None: ...


class KnowledgePort(Protocol):
    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]: ...


class LearningPort(Protocol):
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
    ) -> str: ...

    def update_quality(
        self,
        experience_id: str,
        *,
        accepted: bool,
        score: int,
        issues: list[str] | tuple[str, ...],
        checks: dict[str, bool],
    ) -> None: ...

    def status(self) -> dict[str, Any]: ...

    def recent(
        self,
        limit: int = 20,
    ) -> list[dict[str, Any]]: ...

