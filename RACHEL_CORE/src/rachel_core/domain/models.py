from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from .enums import PolicyEffect, RiskLevel, Role, RunState


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class Message:
    conversation_id: str
    role: Role
    content: str
    id: str = field(default_factory=lambda: new_id("msg"))
    created_at: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["role"] = self.role.value
        return data


@dataclass(frozen=True, slots=True)
class Conversation:
    id: str = field(default_factory=lambda: new_id("conv"))
    title: str = "Nova conversa"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class ChatRequest:
    content: str
    conversation_id: str | None = None
    system_prompt: str | None = None
    max_context_messages: int = 20


@dataclass(frozen=True, slots=True)
class ChatResult:
    conversation_id: str
    run_id: str
    message: Message
    state: RunState
    provider: str
    model: str
    duration_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "run_id": self.run_id,
            "message": self.message.to_dict(),
            "state": self.state.value,
            "provider": self.provider,
            "model": self.model,
            "duration_ms": self.duration_ms,
        }


@dataclass(frozen=True, slots=True)
class ModelResponse:
    content: str
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]
    risk: RiskLevel
    reason: str
    id: str = field(default_factory=lambda: new_id("tool"))


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    effect: PolicyEffect
    reason: str
    requires_user_confirmation: bool = False

