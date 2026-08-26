from __future__ import annotations

from typing import Any, Protocol

from context_budget import DEFAULT_MAX_CONTEXT_FILES, DEFAULT_MAX_CONTEXT_TOKENS


class ProjectContextRuntime(Protocol):
    def context_for(
        self,
        scope: str,
        path: str,
        task: str,
        max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
        max_files: int = DEFAULT_MAX_CONTEXT_FILES,
    ) -> dict[str, Any]: ...


class ProjectContextProvider:
    """Small boundary used by planning/agent execution to request bounded project context."""

    def __init__(self, runtime: ProjectContextRuntime) -> None:
        self.runtime = runtime

    def build(
        self,
        *,
        scope: str,
        path: str,
        task: str,
        max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
        max_files: int = DEFAULT_MAX_CONTEXT_FILES,
    ) -> dict[str, Any]:
        clean_scope = str(scope).strip().casefold()
        clean_path = str(path).strip() or "."
        clean_task = " ".join(str(task).strip().split())

        if not clean_scope:
            raise ValueError("Project context scope is required")
        if not clean_task:
            raise ValueError("Project context task is required")

        token_limit = max(256, min(int(max_tokens), DEFAULT_MAX_CONTEXT_TOKENS))
        file_limit = max(1, min(int(max_files), DEFAULT_MAX_CONTEXT_FILES))

        context = self.runtime.context_for(
            clean_scope,
            clean_path,
            clean_task,
            max_tokens=token_limit,
            max_files=file_limit,
        )

        return {
            "scope": clean_scope,
            "path": clean_path,
            "task": clean_task,
            "context": context,
            "budget": {
                "max_tokens": token_limit,
                "max_files": file_limit,
            },
            "provider": "project-intelligence",
        }
