from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class PublicationSignal:
    published_at: str | None
    source: str | None
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceClaim:
    id: str
    text: str
    source_url: str
    source_title: str
    authority: str
    published_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResearchConflict:
    marker: str
    values: tuple[str, ...]
    sources: tuple[str, ...]
    severity: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_ISO_DATE = re.compile(r"\b(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\b")
_URL_DATE = re.compile(r"/(20\d{2})/(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])(?:/|$)")
_PT_DATE = re.compile(
    r"\b([0-3]?\d)\s+de\s+(janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+(20\d{2})\b",
    re.I,
)
_EN_DATE = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+([0-3]?\d),\s*(20\d{2})\b",
    re.I,
)

_PT_MONTHS = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}
_EN_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

# These markers are intentionally conservative: they only flag conflicts for
# explicit, comparable factual values. Natural-language copulas are accepted
# so phrases such as "version is 3.13" and "versão é 3.13" are not missed.
_VALUE_LINK = r"(?:\s*(?::|=|is|was|é|e|era|foi)\s*|\s+)"
_FACT_MARKERS = {
    "version": re.compile(
        rf"\b(?:version|vers[aã]o|v){_VALUE_LINK}(\d+(?:\.\d+){{0,3}})\b",
        re.I,
    ),
    "release": re.compile(
        rf"\brelease{_VALUE_LINK}(\d+(?:\.\d+){{0,3}})\b",
        re.I,
    ),
    "limit": re.compile(
        rf"\b(?:limit|limite|maximum|m[aá]ximo){_VALUE_LINK}(\d+(?:[.,]\d+)?)\b",
        re.I,
    ),
}


def _iso_date(year: int, month: int, day: int) -> str | None:
    try:
        value = datetime(year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return None
    return value.date().isoformat()


def _stable_source_id(url: str) -> str:
    normalized = url.strip().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:16]


def extract_publication_signal(
    *,
    content: str,
    title: str = "",
    url: str = "",
    retrieved_at_ms: int | None = None,
) -> PublicationSignal:
    candidates: list[tuple[str, str, float]] = []

    url_match = _URL_DATE.search(url)
    if url_match:
        value = _iso_date(*(int(item) for item in url_match.groups()))
        if value:
            candidates.append((value, "url", 0.95))

    head = f"{title}\n{content[:4000]}"
    iso_match = _ISO_DATE.search(head)
    if iso_match:
        value = _iso_date(*(int(item) for item in iso_match.groups()))
        if value:
            candidates.append((value, "content-iso", 0.85))

    pt_match = _PT_DATE.search(head)
    if pt_match:
        day, month_name, year = pt_match.groups()
        value = _iso_date(int(year), _PT_MONTHS[month_name.casefold()], int(day))
        if value:
            candidates.append((value, "content-pt", 0.8))

    en_match = _EN_DATE.search(head)
    if en_match:
        month_name, day, year = en_match.groups()
        value = _iso_date(int(year), _EN_MONTHS[month_name.casefold()], int(day))
        if value:
            candidates.append((value, "content-en", 0.8))

    if not candidates:
        return PublicationSignal(None, None, 0.0)

    candidates.sort(key=lambda item: item[2], reverse=True)
    published_at, source, confidence = candidates[0]

    if retrieved_at_ms is not None:
        retrieved = datetime.fromtimestamp(retrieved_at_ms / 1000, tz=timezone.utc).date()
        parsed = datetime.fromisoformat(published_at).date()
        if parsed > retrieved:
            return PublicationSignal(None, None, 0.0)

    return PublicationSignal(published_at, source, confidence)


def publication_is_fresh(
    published_at: str | None,
    *,
    retrieved_at_ms: int,
    window_days: int | None,
) -> bool:
    if not published_at or window_days is None:
        return False
    try:
        published = datetime.fromisoformat(published_at).date()
    except ValueError:
        return False
    retrieved = datetime.fromtimestamp(retrieved_at_ms / 1000, tz=timezone.utc).date()
    age = (retrieved - published).days
    return 0 <= age <= max(0, int(window_days))


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    result: list[str] = []
    for part in parts:
        cleaned = " ".join(part.split()).strip()
        if 40 <= len(cleaned) <= 500:
            result.append(cleaned)
    return result


def build_evidence_claims(
    source: dict[str, Any],
    *,
    maximum: int = 5,
) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    url = str(source.get("url", ""))
    title = str(source.get("title", ""))
    authority = str(source.get("authority", "general"))
    published_at = source.get("published_at")
    source_id = _stable_source_id(url)

    for index, sentence in enumerate(
        _sentences(str(source.get("content", "")))[:maximum],
        start=1,
    ):
        claims.append(
            EvidenceClaim(
                id=f"source-{source_id}-claim-{index}",
                text=sentence,
                source_url=url,
                source_title=title,
                authority=authority,
                published_at=str(published_at) if published_at else None,
            ).to_dict()
        )
    return claims


def detect_conflicts(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observations: dict[str, dict[str, set[str]]] = {}

    for source in sources:
        url = str(source.get("url", ""))
        text = (
            f"{source.get('title', '')}\n"
            f"{source.get('description', '')}\n"
            f"{str(source.get('content', ''))[:6000]}"
        )
        for marker, pattern in _FACT_MARKERS.items():
            values = {
                match.group(1).replace(",", ".")
                for match in pattern.finditer(text)
            }
            for value in values:
                observations.setdefault(marker, {}).setdefault(
                    value,
                    set(),
                ).add(url)

    conflicts: list[dict[str, Any]] = []
    for marker, value_sources in observations.items():
        distinct = [
            value for value, urls in value_sources.items() if urls
        ]
        all_sources = {
            url
            for urls in value_sources.values()
            for url in urls
            if url
        }
        if len(distinct) < 2 or len(all_sources) < 2:
            continue
        conflicts.append(
            ResearchConflict(
                marker=marker,
                values=tuple(sorted(distinct)),
                sources=tuple(sorted(all_sources)),
                severity="warning",
            ).to_dict()
        )

    return conflicts
