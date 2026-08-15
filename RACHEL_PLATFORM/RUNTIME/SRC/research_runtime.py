from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from runtime_paths import ROOT

from search_runtime import SearchEngine
from web_runtime import WebClient, WebEvidence


class ResearchError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchQuality:
    accepted: bool
    score: int
    issues: tuple[str, ...]
    source_count: int
    domain_count: int
    authoritative_sources: int
    citations_valid: bool


class ResearchQualityEvaluator:
    def evaluate(
        self,
        sources: list[dict[str, Any]],
    ) -> ResearchQuality:
        domains = {
            urllib.parse.urlsplit(
                str(source.get("url", ""))
            ).hostname
            for source in sources
            if source.get("url")
        }
        domains.discard(None)

        authoritative = sum(
            1
            for source in sources
            if source.get("authority") in {
                "primary",
                "technical",
            }
        )

        citations_valid = all(
            isinstance(source.get("citation"), dict)
            and bool(source["citation"].get("url"))
            and bool(source["citation"].get("title"))
            for source in sources
        )

        checks = {
            "has_sources": len(sources) >= 1,
            "source_diversity": (
                len(domains) >= 2
                if len(sources) >= 2
                else True
            ),
            "has_authoritative_source": authoritative >= 1,
            "citations_valid": citations_valid,
            "content_available": all(
                bool(str(source.get("content", "")).strip())
                for source in sources
            ),
        }

        issues = tuple(
            key.upper()
            for key, passed in checks.items()
            if not passed
        )
        score = round(
            100 * sum(checks.values()) / len(checks)
        )

        return ResearchQuality(
            accepted=(
                checks["has_sources"]
                and checks["citations_valid"]
                and checks["content_available"]
            ),
            score=score,
            issues=issues,
            source_count=len(sources),
            domain_count=len(domains),
            authoritative_sources=authoritative,
            citations_valid=citations_valid,
        )


class ResearchEngine:
    def __init__(
        self,
        search_engine: Any | None = None,
        web_client: Any | None = None,
    ) -> None:
        self.search_engine = (
            search_engine or SearchEngine()
        )
        self.web_client = web_client or WebClient()
        self.quality = ResearchQualityEvaluator()

    def research(
        self,
        query: str,
        max_sources: int = 3,
        maximum_characters_per_source: int = 12000,
    ) -> dict[str, Any]:
        selected_sources = max(
            1,
            min(int(max_sources), 5),
        )
        character_limit = max(
            1000,
            min(
                int(maximum_characters_per_source),
                30000,
            ),
        )

        search_payload = self.search_engine.search(
            query,
            limit=max(selected_sources * 3, 8),
        )

        sources: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        used_domains: set[str] = set()

        candidates = sorted(
            search_payload["results"],
            key=lambda item: (
                item["authority_score"],
                item["score"],
            ),
            reverse=True,
        )

        for result in candidates:
            if len(sources) >= selected_sources:
                break

            url = result["url"]
            domain = (
                urllib.parse.urlsplit(url).hostname
                or ""
            ).casefold()

            if domain in used_domains and len(candidates) > selected_sources:
                continue

            try:
                evidence: WebEvidence = (
                    self.web_client.fetch(url)
                )
            except Exception as error:
                errors.append(
                    {
                        "url": url,
                        "error": (
                            f"{type(error).__name__}: {error}"
                        ),
                    }
                )
                continue

            used_domains.add(domain)

            sources.append(
                {
                    "title": (
                        evidence.title
                        or result["title"]
                    ),
                    "url": evidence.final_url,
                    "description": result["description"],
                    "content": evidence.content[
                        :character_limit
                    ],
                    "content_characters": min(
                        len(evidence.content),
                        character_limit,
                    ),
                    "provider": result["provider"],
                    "authority": result["authority"],
                    "authority_score": (
                        result["authority_score"]
                    ),
                    "search_score": result["score"],
                    "retrieved_at_ms": (
                        evidence.retrieved_at_ms
                    ),
                    "sha256": evidence.sha256,
                    "from_cache": evidence.from_cache,
                    "citation": {
                        "title": (
                            evidence.title
                            or result["title"]
                        ),
                        "url": evidence.final_url,
                        "retrieved_at_ms": (
                            evidence.retrieved_at_ms
                        ),
                        "sha256": evidence.sha256,
                    },
                }
            )

        if not sources:
            raise ResearchError(
                "No search result could be retrieved"
            )

        quality = self.quality.evaluate(sources)

        return {
            "query": search_payload["query"],
            "state": (
                "completed"
                if quality.accepted
                else "completed_with_warnings"
            ),
            "sources": sources,
            "source_errors": errors,
            "search": {
                "providers_used": (
                    search_payload["providers_used"]
                ),
                "provider_errors": (
                    search_payload["provider_errors"]
                ),
                "candidate_count": (
                    search_payload["result_count"]
                ),
            },
            "quality": asdict(quality),
            "instructions_for_model": [
                "Use only claims supported by the supplied sources.",
                "Cite the source URL near every factual claim.",
                "Distinguish confirmed facts from inference.",
                "Mention disagreements or missing evidence.",
                "Do not claim that a source was read if retrieval failed."
            ],
            "memory": {
                "stored_automatically": False,
                "explicit_approval_required": True,
            },
        }


def status() -> dict[str, Any]:
    return {
        "available": True,
        "search": True,
        "source_retrieval": True,
        "source_diversity": True,
        "authority_ranking": True,
        "quality_review": True,
        "citations": True,
        "automatic_memory": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="rachel-research"
    )
    sub = parser.add_subparsers(
        dest="action",
        required=True,
    )

    sub.add_parser("status")

    research_parser = sub.add_parser("research")
    research_parser.add_argument("query")
    research_parser.add_argument(
        "--max-sources",
        type=int,
        default=3,
    )
    research_parser.add_argument(
        "--maximum-characters",
        type=int,
        default=12000,
    )

    args = parser.parse_args()

    try:
        if args.action == "status":
            payload = status()
        else:
            payload = ResearchEngine().research(
                args.query,
                args.max_sources,
                args.maximum_characters,
            )
    except Exception as error:
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
