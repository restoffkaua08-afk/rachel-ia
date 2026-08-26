from __future__ import annotations

import json
from typing import Any

from project_context_provider import ProjectContextProvider


PROJECT_GOAL_KEYWORDS = (
    "projeto",
    "project",
    "repositorio",
    "repositório",
    "repository",
    "repo",
    "codigo",
    "código",
    "code",
    "bug",
    "feature",
    "refactor",
    "backend",
    "frontend",
    "api",
    "teste",
    "test",
    "build",
)


def is_project_goal(goal: str) -> bool:
    normalized = " ".join(str(goal).strip().casefold().split())
    if not normalized:
        return False
    return any(keyword in normalized for keyword in PROJECT_GOAL_KEYWORDS)


def build_project_planning_context(
    coordinator: Any,
    goal: str,
) -> dict[str, Any] | None:
    """Return bounded workspace context only for project-oriented planning goals."""

    if not is_project_goal(goal):
        return None

    projects = getattr(coordinator, "projects", None)
    if projects is None:
        return None

    try:
        return ProjectContextProvider(projects).build(
            scope="workspace",
            path=".",
            task=goal,
        )
    except (OSError, RuntimeError, ValueError):
        return None


def planning_message_content(goal: str, context: dict[str, Any] | None) -> str:
    clean_goal = " ".join(str(goal).strip().split())
    if not context:
        return clean_goal

    return (
        clean_goal
        + "\n\n[PROJECT_CONTEXT_BOUNDED]\n"
        + json.dumps(context, ensure_ascii=False, sort_keys=True)
        + "\n[/PROJECT_CONTEXT_BOUNDED]"
    )
