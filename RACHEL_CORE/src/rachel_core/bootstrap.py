from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .adapters.audit_jsonl import JsonlAuditAdapter
from .adapters.knowledge_sqlite import SQLiteKnowledgeAdapter
from .adapters.learning_sqlite import SQLiteLearningAdapter
from .adapters.memory_sqlite import SQLiteMemoryAdapter
from .adapters.model_mock import MockModelAdapter
from .adapters.model_openai_compatible import OpenAICompatibleAdapter
from .adapters.model_router import ModelRouter
from .adapters.policy import DenyByDefaultPolicy
from .application import ChatService
from .config import Settings
from .ports import KnowledgePort, LearningPort, MemoryPort, ModelPort, PolicyPort


@dataclass(slots=True)
class Container:
    settings: Settings
    chat: ChatService
    memory: MemoryPort
    knowledge: KnowledgePort
    learning: LearningPort
    policy: PolicyPort


def _primary_model(settings: Settings) -> ModelPort:
    if settings.model_provider == "mock":
        return MockModelAdapter(settings.model_name)
    if settings.model_provider == "openai-compatible":
        return OpenAICompatibleAdapter(
            base_url=settings.model_base_url,
            api_key=settings.model_api_key,
            model_name=settings.model_name,
            timeout=settings.model_timeout_seconds,
        )
    raise ValueError(f"Provedor não suportado: {settings.model_provider}")


def _model_router(settings: Settings) -> ModelPort:
    primary = _primary_model(settings)
    enabled = os.getenv("RACHEL_MODEL_ROUTER_ENABLED", "1").strip().casefold()
    if enabled in {"0", "false", "no", "off"}:
        return primary

    providers: dict[str, ModelPort] = {"primary": primary}
    cloud_base_url = os.getenv("RACHEL_CLOUD_MODEL_BASE_URL", "").strip().rstrip("/")
    cloud_model_name = os.getenv("RACHEL_CLOUD_MODEL_NAME", "").strip()
    if cloud_base_url and cloud_model_name:
        providers["cloud"] = OpenAICompatibleAdapter(
            base_url=cloud_base_url,
            api_key=os.getenv("RACHEL_CLOUD_MODEL_API_KEY", ""),
            model_name=cloud_model_name,
            timeout=int(
                os.getenv(
                    "RACHEL_CLOUD_MODEL_TIMEOUT_SECONDS",
                    str(settings.model_timeout_seconds),
                )
            ),
        )

    repo_root = Path(__file__).resolve().parents[3]
    profiles_path = Path(
        os.getenv(
            "RACHEL_MODEL_PROFILES_PATH",
            str(repo_root / "RACHEL_PLATFORM" / "CONFIG" / "model.profiles.json"),
        )
    ).expanduser()
    privacy_path = Path(
        os.getenv(
            "RACHEL_PRIVACY_POLICY_PATH",
            str(repo_root / "RACHEL_PLATFORM" / "CONFIG" / "privacy.policy.json"),
        )
    ).expanduser()

    if profiles_path.exists() and privacy_path.exists():
        return ModelRouter.from_files(
            providers=providers,
            profiles_path=profiles_path,
            privacy_path=privacy_path,
        )
    return ModelRouter.with_primary(primary)


def _knowledge_adapter(settings: Settings) -> SQLiteKnowledgeAdapter:
    configured = os.getenv("RACHEL_KNOWLEDGE_DB_PATH", "").strip()
    path = (
        Path(configured).expanduser().resolve()
        if configured
        else (settings.home.parent / "bran-cognitive.db").resolve()
    )
    return SQLiteKnowledgeAdapter(path)


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or Settings.from_env()
    settings.ensure_directories()
    model = _model_router(settings)

    memory = SQLiteMemoryAdapter(settings.home / "rachel.db")
    learning = SQLiteLearningAdapter(settings.home / "learning.db")
    audit = JsonlAuditAdapter(settings.home / "audit.jsonl")
    knowledge = _knowledge_adapter(settings)
    policy = DenyByDefaultPolicy()

    return Container(
        settings=settings,
        chat=ChatService(
            model=model,
            memory=memory,
            audit=audit,
            knowledge=knowledge,
            learning=learning,
        ),
        memory=memory,
        knowledge=knowledge,
        learning=learning,
        policy=policy,
    )
