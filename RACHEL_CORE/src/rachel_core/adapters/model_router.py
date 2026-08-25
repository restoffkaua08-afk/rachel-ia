from __future__ import annotations

import json
import re
import threading
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..domain.enums import Role
from ..domain.errors import ModelError
from ..domain.models import Message, ModelResponse
from ..ports import ModelPort


SUPPORTED_PRIVACY_MODES = {"local-only", "hybrid", "cloud-enabled"}
SUPPORTED_TASK_TYPES = {"fast", "general", "reasoning", "coding", "vision"}


_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_CPF_RE = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?9?\d{4}[-\s]?\d{4}(?!\d)")
_CREDENTIAL_RE = re.compile(
    r"\b(?:password|passwd|senha|api[_ -]?key|access[_ -]?token|refresh[_ -]?token|secret)\b\s*[:=]",
    re.I,
)
_CODE_RE = re.compile(
    r"\b(?:c[oó]digo|code|programa(?:r|ção)?|implemente|refatore|debug|bug|"
    r"typescript|javascript|python|java|c#|\.net|react|next\.js|sql|git|build|lint|typecheck)\b",
    re.I,
)
_REASONING_RE = re.compile(
    r"\b(?:planeje|plano|arquitetura|analise profundamente|compare|estrat[eé]gia|"
    r"investigue|pesquise profundamente|multi[- ]?etapa|do come[cç]o ao fim|"
    r"passo a passo|decida|avalie)\b",
    re.I,
)
_VISION_RE = re.compile(r"\b(?:imagem|foto|screenshot|captura de tela|vis[aã]o|vision)\b", re.I)


@dataclass(frozen=True, slots=True)
class ModelProfile:
    name: str
    provider: str
    model_name: str | None = None
    task_types: tuple[str, ...] = ("general",)
    local: bool = True
    enabled: bool = True
    priority: int = 100
    max_tokens: int | None = None
    context_window: int | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ModelProfile":
        name = str(payload.get("name", "")).strip()
        provider = str(payload.get("provider", "")).strip()
        if not name or not provider:
            raise ValueError("ModelProfile exige name e provider.")

        raw_tasks = payload.get("task_types", ["general"])
        if not isinstance(raw_tasks, list) or not raw_tasks:
            raise ValueError(f"Perfil {name!r} precisa declarar task_types.")
        tasks = tuple(str(item).strip() for item in raw_tasks)
        invalid = sorted(set(tasks) - SUPPORTED_TASK_TYPES)
        if invalid:
            raise ValueError(f"Perfil {name!r} possui task_types inválidos: {invalid}")

        model_name = payload.get("model_name")
        return cls(
            name=name,
            provider=provider,
            model_name=str(model_name).strip() if model_name else None,
            task_types=tasks,
            local=bool(payload.get("local", True)),
            enabled=bool(payload.get("enabled", True)),
            priority=int(payload.get("priority", 100)),
            max_tokens=int(payload["max_tokens"]) if payload.get("max_tokens") is not None else None,
            context_window=(
                int(payload["context_window"])
                if payload.get("context_window") is not None
                else None
            ),
        )


@dataclass(frozen=True, slots=True)
class PrivacyPolicy:
    mode: str = "local-only"
    protect_pii: bool = True
    allow_cloud_for_sensitive_data: bool = False

    def __post_init__(self) -> None:
        if self.mode not in SUPPORTED_PRIVACY_MODES:
            raise ValueError(
                f"Modo de privacidade inválido: {self.mode}. "
                f"Use um de {sorted(SUPPORTED_PRIVACY_MODES)}."
            )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PrivacyPolicy":
        return cls(
            mode=str(payload.get("mode", "local-only")).strip().casefold(),
            protect_pii=bool(payload.get("protect_pii", True)),
            allow_cloud_for_sensitive_data=bool(
                payload.get("allow_cloud_for_sensitive_data", False)
            ),
        )


@dataclass(frozen=True, slots=True)
class RouteDecision:
    task_type: str
    profile: str
    provider: str
    model: str
    local: bool
    sensitive: bool
    privacy_mode: str


class ModelRouter:
    """ModelPort implementation with task routing, privacy and safe fallback.

    The router deliberately knows nothing about provider credentials. Concrete
    adapters are injected by the bootstrap layer. A profile may reference an
    unavailable optional provider; in that case it is skipped and a compatible
    fallback is selected without weakening the privacy policy.
    """

    def __init__(
        self,
        providers: dict[str, ModelPort],
        profiles: Sequence[ModelProfile],
        policy: PrivacyPolicy | None = None,
    ) -> None:
        if not providers:
            raise ValueError("ModelRouter exige pelo menos um provider.")
        self.providers = dict(providers)
        self.policy = policy or PrivacyPolicy()
        self.profiles = tuple(
            sorted(
                (profile for profile in profiles if profile.enabled),
                key=lambda item: (item.priority, item.name),
            )
        )
        if not self.profiles:
            raise ValueError("ModelRouter exige pelo menos um perfil habilitado.")
        if not any(profile.provider in self.providers for profile in self.profiles):
            raise ValueError("Nenhum perfil habilitado possui provider disponível.")
        self._local = threading.local()

    @classmethod
    def from_files(
        cls,
        providers: dict[str, ModelPort],
        profiles_path: Path,
        privacy_path: Path,
    ) -> "ModelRouter":
        profiles_payload = json.loads(profiles_path.read_text(encoding="utf-8"))
        raw_profiles = profiles_payload.get("profiles", [])
        if not isinstance(raw_profiles, list):
            raise ValueError("model.profiles.json deve conter uma lista profiles.")
        profiles = [ModelProfile.from_dict(item) for item in raw_profiles]

        policy_payload = json.loads(privacy_path.read_text(encoding="utf-8"))
        policy = PrivacyPolicy.from_dict(policy_payload)
        return cls(providers=providers, profiles=profiles, policy=policy)

    @classmethod
    def with_primary(cls, provider: ModelPort) -> "ModelRouter":
        profiles = (
            ModelProfile(
                name="fast",
                provider="primary",
                task_types=("fast",),
                local=True,
                priority=10,
            ),
            ModelProfile(
                name="general",
                provider="primary",
                task_types=("general", "reasoning", "coding", "vision"),
                local=True,
                priority=100,
            ),
        )
        return cls({"primary": provider}, profiles, PrivacyPolicy())

    @staticmethod
    def sensitive_content(text: str) -> bool:
        if not text:
            return False
        return any(
            pattern.search(text) is not None
            for pattern in (_EMAIL_RE, _CPF_RE, _PHONE_RE, _CREDENTIAL_RE)
        )

    @staticmethod
    def classify_task(
        messages: Sequence[Message],
        system_prompt: str | None = None,
    ) -> str:
        latest = next(
            (
                message.content
                for message in reversed(messages)
                if message.role == Role.USER
            ),
            "",
        )
        system = system_prompt or ""
        combined = f"{system}\n{latest}".strip()
        system_folded = system.casefold()

        if "planejador" in system_folded or "execution plan" in system_folded:
            return "reasoning"
        if _VISION_RE.search(combined):
            return "vision"
        if _CODE_RE.search(combined):
            return "coding"
        if _REASONING_RE.search(combined) or len(latest) >= 2_500:
            return "reasoning"
        if len(latest) <= 600:
            return "fast"
        return "general"

    def _eligible_profiles(self, task_type: str, sensitive: bool) -> list[ModelProfile]:
        available = [
            profile
            for profile in self.profiles
            if profile.provider in self.providers
            and (task_type in profile.task_types or "general" in profile.task_types)
        ]
        if not available:
            available = [
                profile for profile in self.profiles if profile.provider in self.providers
            ]

        must_be_local = self.policy.mode == "local-only" or (
            sensitive
            and self.policy.protect_pii
            and not self.policy.allow_cloud_for_sensitive_data
        )
        if must_be_local:
            local_profiles = [profile for profile in available if profile.local]
            if not local_profiles:
                raise ModelError(
                    "A política de privacidade exige modelo local, mas nenhum perfil local está disponível."
                )
            return local_profiles

        exact = [profile for profile in available if task_type in profile.task_types]
        fallback = [profile for profile in available if profile not in exact]

        if self.policy.mode == "hybrid":
            if task_type in {"fast", "general"}:
                exact.sort(key=lambda item: (not item.local, item.priority, item.name))
                fallback.sort(key=lambda item: (not item.local, item.priority, item.name))
            else:
                exact.sort(key=lambda item: (item.priority, item.local, item.name))
                fallback.sort(key=lambda item: (not item.local, item.priority, item.name))
        elif self.policy.mode == "cloud-enabled":
            exact.sort(key=lambda item: (item.local, item.priority, item.name))
            fallback.sort(key=lambda item: (item.local, item.priority, item.name))

        return exact + fallback

    def candidates(
        self,
        messages: Sequence[Message],
        system_prompt: str | None,
    ) -> tuple[str, bool, list[ModelProfile]]:
        task_type = self.classify_task(messages, system_prompt)
        text = "\n".join(message.content for message in messages)
        sensitive = self.sensitive_content(text)
        return task_type, sensitive, self._eligible_profiles(task_type, sensitive)

    def _remember_route(
        self,
        profile: ModelProfile,
        adapter: ModelPort,
        task_type: str,
        sensitive: bool,
    ) -> None:
        self._local.route = RouteDecision(
            task_type=task_type,
            profile=profile.name,
            provider=adapter.provider_name,
            model=profile.model_name or adapter.model_name,
            local=profile.local,
            sensitive=sensitive,
            privacy_mode=self.policy.mode,
        )

    @property
    def last_route(self) -> RouteDecision | None:
        return getattr(self._local, "route", None)

    def _default_adapter(self) -> ModelPort:
        profile = next(
            profile for profile in self.profiles if profile.provider in self.providers
        )
        return self.providers[profile.provider]

    @property
    def provider_name(self) -> str:
        route = self.last_route
        return route.provider if route else self._default_adapter().provider_name

    @property
    def model_name(self) -> str:
        route = self.last_route
        return route.model if route else self._default_adapter().model_name

    def health(self) -> dict[str, object]:
        checked: dict[str, dict[str, object]] = {}
        allowed_provider_keys = {
            profile.provider
            for profile in self.profiles
            if profile.provider in self.providers
            and (self.policy.mode != "local-only" or profile.local)
        }
        for key in sorted(allowed_provider_keys):
            adapter = self.providers[key]
            try:
                checked[key] = dict(adapter.health())
            except Exception as exc:
                checked[key] = {
                    "available": False,
                    "reachable": False,
                    "provider": adapter.provider_name,
                    "model": adapter.model_name,
                    "error_type": type(exc).__name__,
                }
        available = any(bool(item.get("available")) for item in checked.values())
        return {
            "available": available,
            "reachable": any(bool(item.get("reachable")) for item in checked.values()),
            "provider": "model-router",
            "model": "dynamic",
            "model_available": available,
            "privacy_mode": self.policy.mode,
            "providers": checked,
        }

    def generate(
        self,
        messages: Sequence[Message],
        system_prompt: str | None,
    ) -> ModelResponse:
        task_type, sensitive, candidates = self.candidates(messages, system_prompt)
        failures: list[str] = []
        for profile in candidates:
            adapter = self.providers[profile.provider]
            try:
                response = adapter.generate(messages, system_prompt)
            except Exception as exc:
                failures.append(f"{profile.name}:{type(exc).__name__}")
                continue
            self._remember_route(profile, adapter, task_type, sensitive)
            if profile.model_name and response.model != profile.model_name:
                return ModelResponse(
                    content=response.content,
                    provider=response.provider,
                    model=response.model,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                )
            return response
        raise ModelError(
            "Nenhum provider autorizado conseguiu gerar resposta. "
            f"Tentativas: {', '.join(failures) or 'nenhuma'}."
        )

    def generate_stream(
        self,
        messages: Sequence[Message],
        system_prompt: str | None,
    ) -> Iterable[str]:
        task_type, sensitive, candidates = self.candidates(messages, system_prompt)
        failures: list[str] = []
        for profile in candidates:
            adapter = self.providers[profile.provider]
            emitted = False
            try:
                stream = adapter.generate_stream(messages, system_prompt)
                for chunk in stream:
                    emitted = True
                    if self.last_route is None:
                        self._remember_route(profile, adapter, task_type, sensitive)
                    yield chunk
                if emitted:
                    self._remember_route(profile, adapter, task_type, sensitive)
                    return
                failures.append(f"{profile.name}:empty-stream")
            except Exception as exc:
                if emitted:
                    raise
                failures.append(f"{profile.name}:{type(exc).__name__}")
                continue
        raise ModelError(
            "Nenhum provider autorizado conseguiu iniciar streaming. "
            f"Tentativas: {', '.join(failures) or 'nenhuma'}."
        )
