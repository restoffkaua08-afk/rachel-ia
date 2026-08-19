from __future__ import annotations

import time
from collections.abc import Callable

from .domain.enums import Role, RunState
from .domain.errors import ValidationError
from .domain.models import ChatRequest, ChatResult, Message, new_id
from .ports import AuditPort, KnowledgePort, LearningPort, MemoryPort, ModelPort


DEFAULT_SYSTEM_PROMPT = """Você é Rachel, uma assistente técnica cuidadosa, competente e objetiva.
Responda em português claro. Não invente fatos. Diferencie fatos, inferências e recomendações.
Ferramentas e ações externas são orquestradas pelo runtime governado da RACHEL; o usuário não precisa
conhecer nomes internos de membros ou ferramentas. Nunca alegue que uma ação foi executada apenas porque
ela foi planejada ou autorizada. Só trate uma execução como concluída quando o runtime fornecer evidência
explícita de conclusão. Quando não houver evidência suficiente, diga claramente o que não foi verificado."""


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

    @staticmethod
    def _validated_content(request: ChatRequest) -> str:
        content = request.content.strip()
        if not content:
            raise ValidationError("A mensagem não pode estar vazia.")
        if len(content) > 50_000:
            raise ValidationError("A mensagem excede o limite de 50.000 caracteres.")
        return content

    def _conversation_for(
        self,
        content: str,
        conversation_id: str | None,
    ):
        conversation = None
        if conversation_id:
            conversation = self.memory.get_conversation(conversation_id)
            if conversation is None:
                raise ValidationError("Conversa não encontrada.")
        if conversation is None:
            conversation = self.memory.create_conversation(content[:80])
        return conversation

    def _system_prompt(
        self,
        content: str,
        requested: str | None,
    ) -> str:
        system_prompt = requested or DEFAULT_SYSTEM_PROMPT
        evidence = self.knowledge.search(content, limit=5)
        if evidence:
            system_prompt += "\n\nEvidências recuperadas:\n" + "\n".join(
                f"- {item}" for item in evidence
            )
        return system_prompt

    def _capture_learning(
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
        source: str,
    ) -> str | None:
        if self.learning is None:
            return None
        return self.learning.capture_chat(
            conversation_id=conversation_id,
            run_id=run_id,
            user_content=user_content,
            assistant_content=assistant_content,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_ms=duration_ms,
            metadata={
                "source": source,
                "automatic_training": False,
            },
        )

    def chat(self, request: ChatRequest) -> ChatResult:
        content = self._validated_content(request)
        run_id = new_id("run")
        started = time.perf_counter()
        conversation = self._conversation_for(content, request.conversation_id)

        user_message = Message(
            conversation_id=conversation.id,
            role=Role.USER,
            content=content,
        )
        self.memory.add_message(user_message)
        self.audit.record(
            "chat.received",
            run_id,
            {"conversation_id": conversation.id, "characters": len(content)},
        )

        history = self.memory.list_messages(
            conversation.id,
            max(2, min(request.max_context_messages, 100)),
        )
        system_prompt = self._system_prompt(content, request.system_prompt)

        try:
            response = self.model.generate(history, system_prompt)
        except Exception as exc:
            self.audit.record(
                "chat.failed",
                run_id,
                {
                    "conversation_id": conversation.id,
                    "error_type": type(exc).__name__,
                },
            )
            raise

        duration_ms = int((time.perf_counter() - started) * 1000)
        learning_experience_id = self._capture_learning(
            conversation_id=conversation.id,
            run_id=run_id,
            user_content=content,
            assistant_content=response.content,
            provider=response.provider,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            duration_ms=duration_ms,
            source="chat-service",
        )

        message_metadata = {
            "provider": response.provider,
            "model": response.model,
            "streamed": False,
        }
        if learning_experience_id:
            message_metadata["learning_experience_id"] = learning_experience_id

        assistant_message = Message(
            conversation_id=conversation.id,
            role=Role.ASSISTANT,
            content=response.content,
            metadata=message_metadata,
        )
        self.memory.add_message(assistant_message)
        self.audit.record(
            "chat.completed",
            run_id,
            {
                "conversation_id": conversation.id,
                "duration_ms": duration_ms,
                "provider": response.provider,
                "model": response.model,
                "streamed": False,
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

    def chat_stream(
        self,
        request: ChatRequest,
        on_chunk: Callable[[str], None],
        is_cancelled: Callable[[], bool] | None = None,
    ) -> ChatResult:
        """Stream a chat response while preserving normal persistence contracts.

        The user message is persisted when the request begins. Assistant content is
        persisted only after a complete stream. If cancellation happens, partial
        assistant text is intentionally not committed to conversation memory.
        """
        content = self._validated_content(request)
        run_id = new_id("run")
        started = time.perf_counter()
        conversation = self._conversation_for(content, request.conversation_id)

        user_message = Message(
            conversation_id=conversation.id,
            role=Role.USER,
            content=content,
        )
        self.memory.add_message(user_message)
        self.audit.record(
            "chat.received",
            run_id,
            {
                "conversation_id": conversation.id,
                "characters": len(content),
                "streamed": True,
            },
        )

        history = self.memory.list_messages(
            conversation.id,
            max(2, min(request.max_context_messages, 100)),
        )
        system_prompt = self._system_prompt(content, request.system_prompt)
        chunks: list[str] = []
        first_token_ms: int | None = None
        stream = None

        def cancelled() -> bool:
            return bool(is_cancelled and is_cancelled())

        try:
            if cancelled():
                duration_ms = int((time.perf_counter() - started) * 1000)
                self.audit.record(
                    "chat.cancelled",
                    run_id,
                    {
                        "conversation_id": conversation.id,
                        "duration_ms": duration_ms,
                        "partial_characters": 0,
                    },
                )
                transient = Message(
                    conversation_id=conversation.id,
                    role=Role.ASSISTANT,
                    content="",
                    metadata={"cancelled": True, "streamed": True},
                )
                return ChatResult(
                    conversation_id=conversation.id,
                    run_id=run_id,
                    message=transient,
                    state=RunState.CANCELLED,
                    provider=self.model.provider_name,
                    model=self.model.model_name,
                    duration_ms=duration_ms,
                )

            stream = self.model.generate_stream(history, system_prompt)
            for chunk in stream:
                if cancelled():
                    close = getattr(stream, "close", None)
                    if callable(close):
                        close()
                    duration_ms = int((time.perf_counter() - started) * 1000)
                    self.audit.record(
                        "chat.cancelled",
                        run_id,
                        {
                            "conversation_id": conversation.id,
                            "duration_ms": duration_ms,
                            "partial_characters": sum(len(item) for item in chunks),
                        },
                    )
                    transient = Message(
                        conversation_id=conversation.id,
                        role=Role.ASSISTANT,
                        content="".join(chunks),
                        metadata={"cancelled": True, "streamed": True},
                    )
                    return ChatResult(
                        conversation_id=conversation.id,
                        run_id=run_id,
                        message=transient,
                        state=RunState.CANCELLED,
                        provider=self.model.provider_name,
                        model=self.model.model_name,
                        duration_ms=duration_ms,
                    )

                text = str(chunk)
                if not text:
                    continue
                if first_token_ms is None:
                    first_token_ms = int((time.perf_counter() - started) * 1000)
                chunks.append(text)
                on_chunk(text)

        except Exception as exc:
            self.audit.record(
                "chat.failed",
                run_id,
                {
                    "conversation_id": conversation.id,
                    "error_type": type(exc).__name__,
                    "streamed": True,
                    "partial_characters": sum(len(item) for item in chunks),
                },
            )
            raise

        if cancelled():
            duration_ms = int((time.perf_counter() - started) * 1000)
            transient = Message(
                conversation_id=conversation.id,
                role=Role.ASSISTANT,
                content="".join(chunks),
                metadata={"cancelled": True, "streamed": True},
            )
            self.audit.record(
                "chat.cancelled",
                run_id,
                {
                    "conversation_id": conversation.id,
                    "duration_ms": duration_ms,
                    "partial_characters": len(transient.content),
                },
            )
            return ChatResult(
                conversation_id=conversation.id,
                run_id=run_id,
                message=transient,
                state=RunState.CANCELLED,
                provider=self.model.provider_name,
                model=self.model.model_name,
                duration_ms=duration_ms,
            )

        assistant_content = "".join(chunks)
        if not assistant_content.strip():
            raise ValidationError("O modelo não retornou conteúdo durante o streaming.")

        duration_ms = int((time.perf_counter() - started) * 1000)
        learning_experience_id = self._capture_learning(
            conversation_id=conversation.id,
            run_id=run_id,
            user_content=content,
            assistant_content=assistant_content,
            provider=self.model.provider_name,
            model=self.model.model_name,
            input_tokens=None,
            output_tokens=None,
            duration_ms=duration_ms,
            source="chat-service-stream",
        )

        message_metadata = {
            "provider": self.model.provider_name,
            "model": self.model.model_name,
            "streamed": True,
            "ttft_ms": first_token_ms,
        }
        if learning_experience_id:
            message_metadata["learning_experience_id"] = learning_experience_id

        assistant_message = Message(
            conversation_id=conversation.id,
            role=Role.ASSISTANT,
            content=assistant_content,
            metadata=message_metadata,
        )
        self.memory.add_message(assistant_message)
        self.audit.record(
            "chat.completed",
            run_id,
            {
                "conversation_id": conversation.id,
                "duration_ms": duration_ms,
                "ttft_ms": first_token_ms,
                "provider": self.model.provider_name,
                "model": self.model.model_name,
                "streamed": True,
            },
        )
        return ChatResult(
            conversation_id=conversation.id,
            run_id=run_id,
            message=assistant_message,
            state=RunState.COMPLETED,
            provider=self.model.provider_name,
            model=self.model.model_name,
            duration_ms=duration_ms,
        )

    def status(self) -> dict[str, object]:
        try:
            provider_health = self.model.health()
        except Exception as exc:
            provider_health = {
                "available": False,
                "reachable": False,
                "provider": self.model.provider_name,
                "model": self.model.model_name,
                "model_available": False,
                "error_type": type(exc).__name__,
            }

        available = bool(provider_health.get("available"))
        return {
            "status": "ok" if available else "degraded",
            "provider": self.model.provider_name,
            "model": self.model.model_name,
            "provider_health": provider_health,
            "capabilities": {
                "chat": True,
                "streaming": True,
                "cancellable_generation": True,
                "persistence": True,
                "export_delete": True,
                "tools": False,
                "voice": False,
                "knowledge": False,
            },
        }
