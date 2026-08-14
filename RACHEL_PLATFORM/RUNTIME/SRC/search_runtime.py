from __future__ import annotations

import argparse
import json
import math
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[3]
PLATFORM = ROOT / "RACHEL_PLATFORM"
CONFIG = PLATFORM / "CONFIG"

from web_runtime import WebClient, WebError


class SearchError(RuntimeError):
    pass


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    description: str
    provider: str
    position: int
    authority: str
    authority_score: float
    query_coverage: float
    score: float
    citation: dict[str, Any]


class SearchProvider(Protocol):
    id: str

    def search(
        self,
        query: str,
        limit: int,
    ) -> list[dict[str, str]]:
        ...


class SearchPolicy:
    def __init__(self, path: Path | None = None) -> None:
        policy_path = path or CONFIG / "search.policy.json"
        self.data = json.loads(
            policy_path.read_text(encoding="utf-8-sig")
        )

    @property
    def maximum_query_characters(self) -> int:
        return int(self.data["maximum_query_characters"])

    @property
    def default_result_limit(self) -> int:
        return int(self.data["default_result_limit"])

    @property
    def maximum_result_limit(self) -> int:
        return int(self.data["maximum_result_limit"])

    @property
    def weights(self) -> dict[str, float]:
        return {
            key: float(value)
            for key, value in self.data[
                "ranking_weights"
            ].items()
        }


def normalize_query(query: str, maximum: int = 500) -> str:
    normalized = " ".join(query.strip().split())

    if not normalized:
        raise SearchError("Search query cannot be empty")
    if len(normalized) > maximum:
        raise SearchError(
            f"Search query exceeds {maximum} characters"
        )

    return normalized


def canonical_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url.strip())

    if parsed.scheme.casefold() not in {"http", "https"}:
        raise SearchError("Search result has invalid URL scheme")
    if not parsed.hostname:
        raise SearchError("Search result has no hostname")

    query = urllib.parse.parse_qsl(
        parsed.query,
        keep_blank_values=True,
    )
    tracking_prefixes = (
        "utm_",
        "fbclid",
        "gclid",
        "mc_",
    )
    clean_query = [
        (key, value)
        for key, value in query
        if not key.casefold().startswith(
            tracking_prefixes
        )
    ]

    path = parsed.path or "/"

    if path != "/":
        path = path.rstrip("/")

    return urllib.parse.urlunsplit(
        (
            parsed.scheme.casefold(),
            parsed.netloc.casefold(),
            path,
            urllib.parse.urlencode(clean_query),
            "",
        )
    )


def query_terms(query: str) -> set[str]:
    return {
        term
        for term in re.findall(
            r"[A-Za-zÀ-ÿ0-9_-]+",
            query.casefold(),
        )
        if len(term) >= 2
    }


def coverage_score(
    query: str,
    title: str,
    description: str,
) -> float:
    terms = query_terms(query)

    if not terms:
        return 0.0

    haystack = f"{title} {description}".casefold()
    matched = sum(
        1
        for term in terms
        if term in haystack
    )

    return round(matched / len(terms), 4)


def classify_authority(
    url: str,
    policy: SearchPolicy,
) -> tuple[str, float]:
    hostname = (
        urllib.parse.urlsplit(url).hostname
        or ""
    ).casefold()

    rules = policy.data["authority_rules"]

    for pattern in rules["primary"]:
        if hostname == pattern or hostname.endswith(pattern):
            return "primary", 1.0

    for pattern in rules["technical"]:
        if hostname == pattern or hostname.endswith(
            "." + pattern
        ):
            return "technical", 0.85

    for pattern in rules["encyclopedic"]:
        if hostname == pattern or hostname.endswith(
            "." + pattern
        ):
            return "encyclopedic", 0.7

    return "general", 0.5


def clean_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class BingRssProvider:
    id = "bing-rss"

    def __init__(self, client: WebClient) -> None:
        self.client = client

    @staticmethod
    def parse(
        content: str,
        limit: int,
    ) -> list[dict[str, str]]:
        root = ET.fromstring(content)
        items: list[dict[str, str]] = []

        for element in root.findall(".//item"):
            title = clean_text(
                element.findtext("title", "")
            )
            url = element.findtext("link", "").strip()
            description = clean_text(
                element.findtext("description", "")
            )

            if title and url:
                items.append(
                    {
                        "title": title,
                        "url": url,
                        "description": description,
                    }
                )

            if len(items) >= limit:
                break

        return items

    def search(
        self,
        query: str,
        limit: int,
    ) -> list[dict[str, str]]:
        url = (
            "https://www.bing.com/search?format=rss&q="
            + urllib.parse.quote_plus(query)
            + f"&count={limit}"
        )
        evidence = self.client.fetch(url)
        return self.parse(evidence.content, limit)


class WikipediaProvider:
    id = "wikipedia-opensearch"

    def __init__(self, client: WebClient) -> None:
        self.client = client

    @staticmethod
    def parse(
        content: str,
        limit: int,
    ) -> list[dict[str, str]]:
        payload = json.loads(content)

        if not isinstance(payload, list) or len(payload) < 4:
            raise SearchError(
                "Wikipedia returned an invalid response"
            )

        titles = payload[1]
        descriptions = payload[2]
        urls = payload[3]

        items = []

        for title, description, url in zip(
            titles,
            descriptions,
            urls,
        ):
            if not title or not url:
                continue

            items.append(
                {
                    "title": clean_text(str(title)),
                    "url": str(url).strip(),
                    "description": clean_text(
                        str(description)
                    ),
                }
            )

            if len(items) >= limit:
                break

        return items

    def search(
        self,
        query: str,
        limit: int,
    ) -> list[dict[str, str]]:
        params = urllib.parse.urlencode(
            {
                "action": "opensearch",
                "search": query,
                "limit": limit,
                "namespace": 0,
                "format": "json",
                "origin": "*",
            }
        )
        url = (
            "https://en.wikipedia.org/w/api.php?"
            + params
        )
        evidence = self.client.fetch(url)
        return self.parse(evidence.content, limit)


class SearchEngine:
    def __init__(
        self,
        policy: SearchPolicy | None = None,
        client: WebClient | None = None,
        providers: list[SearchProvider] | None = None,
    ) -> None:
        self.policy = policy or SearchPolicy()
        self.client = client or WebClient()
        self.providers = providers or [
            BingRssProvider(self.client),
            WikipediaProvider(self.client),
        ]

    def rank(
        self,
        query: str,
        raw_results: list[dict[str, Any]],
        limit: int,
    ) -> list[SearchResult]:
        weights = self.policy.weights
        ranked: list[SearchResult] = []
        seen: set[str] = set()

        for raw in raw_results:
            try:
                url = canonical_url(
                    str(raw.get("url", ""))
                )
            except SearchError:
                continue

            if url in seen:
                continue

            title = clean_text(
                str(raw.get("title", ""))
            )
            description = clean_text(
                str(raw.get("description", ""))
            )

            if not title:
                continue

            seen.add(url)
            provider = str(
                raw.get("provider", "unknown")
            )
            position = max(
                1,
                int(raw.get("position", 1)),
            )
            authority, authority_value = (
                classify_authority(url, self.policy)
            )
            coverage = coverage_score(
                query,
                title,
                description,
            )
            provider_score = (
                1.0
                if provider == "bing-rss"
                else 0.8
            )
            position_score = 1.0 / math.sqrt(position)

            score = (
                weights["provider"] * provider_score
                + weights["authority"] * authority_value
                + weights["query_coverage"] * coverage
                + weights["position"] * position_score
            )

            score = round(
                max(0.0, min(score, 1.0)),
                4,
            )

            ranked.append(
                SearchResult(
                    title=title,
                    url=url,
                    description=description,
                    provider=provider,
                    position=position,
                    authority=authority,
                    authority_score=authority_value,
                    query_coverage=coverage,
                    score=score,
                    citation={
                        "title": title,
                        "url": url,
                        "provider": provider,
                    },
                )
            )

        ranked.sort(
            key=lambda item: (
                item.score,
                item.authority_score,
                item.query_coverage,
            ),
            reverse=True,
        )

        return ranked[:limit]

    def search(
        self,
        query: str,
        limit: int | None = None,
    ) -> dict[str, Any]:
        normalized = normalize_query(
            query,
            self.policy.maximum_query_characters,
        )
        selected_limit = (
            self.policy.default_result_limit
            if limit is None
            else int(limit)
        )
        selected_limit = max(
            1,
            min(
                selected_limit,
                self.policy.maximum_result_limit,
            ),
        )

        raw_results: list[dict[str, Any]] = []
        providers_used: list[str] = []
        provider_errors: list[dict[str, str]] = []

        for provider in self.providers:
            try:
                items = provider.search(
                    normalized,
                    selected_limit,
                )
            except Exception as error:
                provider_errors.append(
                    {
                        "provider": provider.id,
                        "error": (
                            f"{type(error).__name__}: {error}"
                        ),
                    }
                )
                continue

            if items:
                providers_used.append(provider.id)

            for position, item in enumerate(
                items,
                start=1,
            ):
                raw_results.append(
                    {
                        **item,
                        "provider": provider.id,
                        "position": position,
                    }
                )

        ranked = self.rank(
            normalized,
            raw_results,
            selected_limit,
        )

        if not ranked and provider_errors:
            raise SearchError(
                "All search providers failed: "
                + "; ".join(
                    item["provider"]
                    for item in provider_errors
                )
            )

        return {
            "query": normalized,
            "result_count": len(ranked),
            "providers_used": providers_used,
            "provider_errors": provider_errors,
            "results": [
                asdict(item)
                for item in ranked
            ],
            "citations_required": True,
        }


def status() -> dict[str, Any]:
    policy = SearchPolicy()

    return {
        "available": True,
        "providers": [
            item["id"]
            for item in policy.data["providers"]
            if item["enabled"]
        ],
        "ranking": True,
        "deduplication": True,
        "authority_classification": True,
        "citations": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="rachel-search"
    )
    sub = parser.add_subparsers(
        dest="action",
        required=True,
    )

    sub.add_parser("status")

    search_parser = sub.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument(
        "--limit",
        type=int,
        default=None,
    )

    args = parser.parse_args()

    try:
        if args.action == "status":
            payload = status()
        else:
            payload = SearchEngine().search(
                args.query,
                args.limit,
            )
    except (
        OSError,
        ValueError,
        SearchError,
        WebError,
    ) as error:
        print(
            f"{type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return 2

    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
