from __future__ import annotations

from typing import Any

from .application import ChatService


class KnowledgeEnabledChatService(ChatService):
    """ChatService with truthful knowledge capability reporting.

    The base service remains protocol-compatible; this production composition
    exposes the health of the configured KnowledgePort instead of advertising a
    hard-coded capability value.
    """

    def knowledge_status(self) -> dict[str, Any]:
        status_method = getattr(self.knowledge, "status", None)
        if not callable(status_method):
            return {
                "available": False,
                "backend": type(self.knowledge).__name__,
                "reason": "knowledge adapter does not expose status",
            }
        try:
            payload = status_method()
        except Exception as error:
            return {
                "available": False,
                "backend": type(self.knowledge).__name__,
                "error_type": type(error).__name__,
            }
        if not isinstance(payload, dict):
            return {
                "available": False,
                "backend": type(self.knowledge).__name__,
                "reason": "invalid knowledge status payload",
            }
        return dict(payload)

    def status(self) -> dict[str, object]:
        payload = super().status()
        knowledge = self.knowledge_status()
        capabilities = payload.get("capabilities")
        if isinstance(capabilities, dict):
            capabilities["knowledge"] = bool(knowledge.get("available"))
        payload["knowledge"] = knowledge
        return payload
