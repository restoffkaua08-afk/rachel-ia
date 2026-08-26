from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


DEFAULT_MAX_CONTEXT_TOKENS = 8_000
DEFAULT_MAX_CONTEXT_FILES = 19
CHARS_PER_TOKEN_ESTIMATE = 3


@dataclass(frozen=True)
class ContextBudget:
    max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS
    max_files: int = DEFAULT_MAX_CONTEXT_FILES

    @property
    def max_chars(self) -> int:
        return max(1, int(self.max_tokens)) * CHARS_PER_TOKEN_ESTIMATE


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return (len(text) + CHARS_PER_TOKEN_ESTIMATE - 1) // CHARS_PER_TOKEN_ESTIMATE


def bound_context_items(
    items: Iterable[dict[str, Any]],
    budget: ContextBudget | None = None,
) -> dict[str, Any]:
    """Fit ranked project-context items inside conservative file/token budgets."""

    active = budget or ContextBudget()
    max_files = max(1, min(int(active.max_files), DEFAULT_MAX_CONTEXT_FILES))
    max_chars = active.max_chars

    selected: list[dict[str, Any]] = []
    used_chars = 0
    truncated = False

    for raw in items:
        if len(selected) >= max_files:
            truncated = True
            break

        item = dict(raw)
        content = str(item.get("content", ""))
        remaining = max_chars - used_chars
        if remaining <= 0:
            truncated = True
            break

        if len(content) > remaining:
            content = content[:remaining]
            truncated = True

        item["content"] = content
        item["estimated_tokens"] = estimate_tokens(content)
        selected.append(item)
        used_chars += len(content)

        if used_chars >= max_chars:
            break

    combined = "".join(str(item.get("content", "")) for item in selected)
    return {
        "items": selected,
        "file_count": len(selected),
        "estimated_tokens": estimate_tokens(combined),
        "max_tokens": max(1, int(active.max_tokens)),
        "max_files": max_files,
        "truncated": truncated,
        "strategy": "conservative-char-budget",
    }
