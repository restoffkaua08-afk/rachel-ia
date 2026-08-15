from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from runtime_paths import CORE_SRC, ROOT, STATE

if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

STATE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("RACHEL_HOME", str(STATE / "core"))

from rachel_core.bootstrap import build_container
from rachel_core.domain.enums import Role
from rachel_core.domain.models import Message
from project_workspace import ProjectWorkspace, WorkspaceError
from project_quality import ProjectQuality


class GenerationError(RuntimeError):
    pass


class ProjectGenerator:
    def __init__(self, workspace=None, model=None):
        self.workspace = workspace or ProjectWorkspace()
        self.model = model or build_container().chat.model

    def _parse(self, text: str) -> dict[str, Any]:
        match = re.search(r"\{.*\}", text.strip(), re.S)
        try:
            payload = json.loads(match.group(0) if match else text)
        except json.JSONDecodeError as error:
            raise GenerationError(f"Model returned invalid JSON: {error}") from error
        if not isinstance(payload, dict) or not isinstance(payload.get("files"), list):
            raise GenerationError("Model response must contain a files list.")
        return payload

    def specifications(self, goal: str, project_type: str = "auto") -> dict[str, Any]:
        clean_goal = " ".join(goal.strip().split())
        if not clean_goal or len(clean_goal) > 8000:
            raise GenerationError("Invalid project goal.")
        system = (
            "Voce e Arya, engenheira de software da Rachel. Produza um projeto funcional e coerente. "
            "Responda SOMENTE JSON valido no formato "
            '{"summary":"...","architecture":"...","files":[{"path":"index.html","content":"..."}]}. '
            "Cada arquivo deve conter codigo completo, sem reticencias, sem blocos Markdown e sem segredos. "
            "Use caminhos relativos. Nao inclua binarios, node_modules, .env ou credenciais. "
            f"Tipo solicitado: {project_type}."
        )
        response = self.model.generate(
            [Message(conversation_id="project-generator", role=Role.USER, content=clean_goal)],
            system,
        )
        payload = self._parse(response.content)
        files = payload["files"]
        if not files:
            raise GenerationError("The generated project has no files.")
        normalized = []
        for position, item in enumerate(files, start=1):
            if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("content"), str):
                raise GenerationError(f"Invalid generated file at position {position}.")
            normalized.append({"path": item["path"].strip(), "content": item["content"]})
        return {
            "goal": clean_goal,
            "project_type": project_type,
            "summary": str(payload.get("summary", "Generated project")).strip(),
            "architecture": str(payload.get("architecture", "")).strip(),
            "files": normalized,
            "file_count": len(normalized),
        }

    def create(self, project: str, goal: str, project_type: str, approved: bool) -> dict[str, Any]:
        if not approved:
            raise PermissionError("Cyber requires approval to generate a project.")
        specification = self.specifications(goal, project_type)
        created = self.workspace.create_project(project, approved=True)
        written = self.workspace.write_files(project, specification["files"], approved=True)
        quality = ProjectQuality(self.workspace).review(project)
        return {
            "state": "completed",
            "quality": quality,
            "project": project,
            "path": created["path"],
            "goal": specification["goal"],
            "project_type": specification["project_type"],
            "summary": specification["summary"],
            "architecture": specification["architecture"],
            "file_count": written["file_count"],
            "files": written["files"],
            "operation_id": written["operation_id"],
        }
