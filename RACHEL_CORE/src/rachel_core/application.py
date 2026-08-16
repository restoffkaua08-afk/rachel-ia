from __future__ import annotations

import time

from .domain.enums import Role, RunState
from .domain.errors import ValidationError
from .domain.models import ChatRequest, ChatResult, Message, new_id
from .ports import AuditPort, KnowledgePort, LearningPort, MemoryPort, ModelPort


DEFAULT_SYSTEM_PROMPT = """Você é Rachel, uma assistente técnica cuidadosa e objetiva.
Responda em português claro. Não invente fatos. Diferencie fatos, inferências e recomendações.
Não alegue ter executado ações que não foram realmente executadas. Ferramentas estão desativadas
nesta versão; quando uma ação externa for necessária, explique o próximo passo ao usuário."""


class ChatService:
    def __init__(
        self,
        model: ModelPort,
        memory: MemoryPort,
        audit: AuditPort,
        knowledge: KnowledgePort,
        learning: LearningPort | None = None,
    ) -> None:
        self.model = model
        self.memory = memory
        self.audit = audit
        self.knowledge = knowledge
        self.learning = learning

    def chat(self, request: ChatRequest) -> ChatResult:
        content = request.content.strip()
        if not content:
            raise ValidationError("A mensagem não pode estar vazia.")
        if len(content) > 50_000:
            raise ValidationError("A mensagem excede o limite de 50.000 caracteres.")

        run_id = new_id("run")
        started = time.perf_counter()
        conversation = None
        if request.conversation_id:
            conversation = self.memory.get_conversation(request.conversation_id)
            if conversation is None:
                raise ValidationError("Conversa não encontrada.")
        if conversation is None:
            conversation = self.memory.create_conversation(content[:80])

        user_message = Message(
            conversation_id=conversation.id, role=Role.USER, content=content
        )
        self.memory.add_message(user_message)
        self.audit.record(
            "chat.received",
            run_id,
            {"conversation_id": conversation.id, "characters": len(content)},
        )

        history = self.memory.list_messages(
            conversation.id, max(2, min(request.max_context_messages, 100))
        )
        evidence = self.knowledge.search(content, limit=5)
        system_prompt = request.system_prompt or DEFAULT_SYSTEM_PROMPT
        if evidence:
            system_prompt += "\n\nEvidências recuperadas:\n" + "\n".join(
                f"- {item}" for item in evidence
            )

        try:
            response = self.model.generate(history, system_prompt)
        except Exception as exc:
            self.audit.record(
                "chat.failed",
                run_id,
                {"conversation_id": conversation.id, "error_type": type(exc).__name__},
            )
            raise

        duration_ms = int(
            (time.perf_counter() - started)
            * 1000
        )

        learning_experience_id = None

        if self.learning is not None:
            learning_experience_id = (
                self.learning.capture_chat(
                    conversation_id=conversation.id,
                    run_id=run_id,
                    user_content=content,
                    assistant_content=response.content,
                    provider=response.provider,
                    model=response.model,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    duration_ms=duration_ms,
                    metadata={
                        "source": "chat-service",
                        "automatic_training": False,
                    },
                )
            )

        message_metadata = {
            "provider": response.provider,
            "model": response.model,
        }

        if learning_experience_id:
            message_metadata[
                "learning_experience_id"
            ] = learning_experience_id

        assistant_message = Message(
            conversation_id=conversation.id,
            role=Role.ASSISTANT,
            content=response.content,
            metadata=message_metadata,
        )

        self.memory.add_message(
            assistant_message
        )
        self.audit.record(
            "chat.completed",
            run_id,
            {
                "conversation_id": conversation.id,
                "duration_ms": duration_ms,
                "provider": response.provider,
                "model": response.model,
                "usage": {
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                },
            },
        )
        return ChatResult(
            conversation_id=conversation.id,
            run_id=run_id,
            message=assistant_message,
            state=RunState.COMPLETED,
            provider=response.provider,
            model=response.model,
            duration_ms=duration_ms,
        )

    def status(self) -> dict[str, object]:
        return {
            "status": "ok",
            "provider": self.model.provider_name,
            "model": self.model.model_name,
            "capabilities": {
                "chat": True,
                "persistence": True,
                "export_delete": True,
                "tools": False,
                "voice": False,
                "knowledge": False,
            },
        }
