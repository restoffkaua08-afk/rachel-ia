from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


_RECENT_TERMS = (
    "hoje",
    "agora",
    "atual",
    "atuais",
    "recente",
    "recentes",
    "latest",
    "today",
    "current",
    "esta semana",
    "este mes",
    "este mês",
)

_TECHNICAL_TERMS = (
    "api",
    "sdk",
    "documentacao",
    "documentação",
    "docs",
    "framework",
    "biblioteca",
    "library",
    "erro",
    "bug",
    "versao",
    "versão",
    "release",
    "changelog",
)

_COMPARE_TERMS = (
    "compare",
    "comparar",
    "comparacao",
    "comparação",
    "versus",
    " vs ",
    "diferença",
    "diferenca",
)


@dataclass(frozen=True)
class ResearchQueryPlan:
    original_query: str
    queries: tuple[str, ...]
    require_primary_source: bool
    freshness_required: bool
    freshness_window_days: int | None
    technical_query: bool
    comparison_query: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize(query: str) -> str:
    normalized = " ".join(str(query).strip().split())
    if not normalized:
        raise ValueError("Research query cannot be empty")
    return normalized


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    folded = f" {text.casefold()} "
    return any(term in folded for term in terms)


def _dedupe(items: list[str], maximum: int = 4) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = " ".join(item.split()).strip()
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
        if len(result) >= maximum:
            break
    return tuple(result)


def plan_research_queries(query: str) -> ResearchQueryPlan:
    original = _normalize(query)
    folded = original.casefold()

    freshness_required = _contains_any(folded, _RECENT_TERMS)
    technical_query = _contains_any(folded, _TECHNICAL_TERMS)
    comparison_query = _contains_any(folded, _COMPARE_TERMS)

    # Professional research should prefer primary evidence whenever the request
    # is technical, current, comparative, or phrased as a verification task.
    verification_query = bool(
        re.search(
            r"\b(?:verifique|validar|valide|confirme|confirmar|fonte|oficial)\b",
            folded,
        )
    )
    require_primary = (
        freshness_required
        or technical_query
        or comparison_query
        or verification_query
    )

    variants = [original]

    if require_primary:
        variants.append(f"{original} official primary source")

    if technical_query:
        variants.append(f"{original} official documentation release notes")

    if freshness_required:
        variants.append(f"{original} latest official update")

    if comparison_query:
        variants.append(f"{original} official specifications")

    freshness_window_days = 30 if freshness_required else None

    return ResearchQueryPlan(
        original_query=original,
        queries=_dedupe(variants),
        require_primary_source=require_primary,
        freshness_required=freshness_required,
        freshness_window_days=freshness_window_days,
        technical_query=technical_query,
        comparison_query=comparison_query,
    )
