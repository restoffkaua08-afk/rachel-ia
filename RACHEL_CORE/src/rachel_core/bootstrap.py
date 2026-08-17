from dataclasses import dataclass

from .adapters.audit_jsonl import JsonlAuditAdapter
from .adapters.knowledge_null import NullKnowledgeAdapter
from .adapters.learning_sqlite import SQLiteLearningAdapter
from .adapters.memory_sqlite import SQLiteMemoryAdapter
from .adapters.model_mock import MockModelAdapter
from .adapters.model_openai_compatible import OpenAICompatibleAdapter
from .adapters.policy import DenyByDefaultPolicy
from .application import ChatService
from .config import Settings
from .ports import LearningPort, MemoryPort, PolicyPort


@dataclass(slots=True)
class Container:
    settings: Settings
    chat: ChatService
    memory: MemoryPort
    learning: LearningPort
    policy: PolicyPort


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or Settings.from_env()
    settings.ensure_directories()
    if settings.model_provider == "mock":
        model = MockModelAdapter(settings.model_name)
    elif settings.model_provider == "openai-compatible":
        model = OpenAICompatibleAdapter(
            base_url=settings.model_base_url,
            api_key=settings.model_api_key,
            model_name=settings.model_name,
            timeout=settings.model_timeout_seconds,
        )
    else:
        raise ValueError(f"Provedor não suportado: {settings.model_provider}")
    memory = SQLiteMemoryAdapter(
        settings.home / "rachel.db"
    )

    learning = SQLiteLearningAdapter(
        settings.home / "learning.db"
    )

    audit = JsonlAuditAdapter(
        settings.home / "audit.jsonl"
    )

    knowledge = NullKnowledgeAdapter()
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
        learning=learning,
        policy=policy,
    )

