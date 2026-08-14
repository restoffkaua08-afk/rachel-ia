from typing import Any


class NullKnowledgeAdapter:
    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        return []

