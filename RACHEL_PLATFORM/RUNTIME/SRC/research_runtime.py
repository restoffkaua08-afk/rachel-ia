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

from research_evidence import (
    build_evidence_claims,
    detect_conflicts,
    extract_publication_signal,
    publication_is_fresh,
)
from research_strategy import ResearchQueryPlan, plan_research_queries
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
    primary_sources: int
    citations_valid: bool
    freshness_required: bool
    freshness_verified: bool


class ResearchQualityEvaluator:
    def evaluate(
        self,
        sources: list[dict[str, Any]],
        *,
        require_primary_source: bool = False,
        freshness_required: bool = False,
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
        primary = sum(
            1
            for source in sources
            if source.get("authority") == "primary"
        )

        citations_valid = all(
            isinstance(source.get("citation"), dict)
            and bool(source["citation"].get("url"))
            and bool(source["citation"].get("title"))
            for source in sources
        )

        freshness_verified = (
            not freshness_required
            or any(
                source.get("freshness_verified") is True
                for source in sources
            )
        )

        checks = {
            "has_sources": len(sources) >= 1,
            "source_diversity": (
                len(domains) >= 2
                if len(sources) >= 2
                else True
            ),
            "has_authoritative_source": authoritative >= 1,
            "has_required_primary_source": (
                primary >= 1
                if require_primary_source
                else True
            ),
            "citations_valid": citations_valid,
            "content_available": all(
                bool(str(source.get("content", "")).strip())
                for source in sources
            ),
            "freshness_verified": freshness_verified,
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
                and checks["has_required_primary_source"]
            ),
            score=score,
            issues=issues,
            source_count=len(sources),
            domain_count=len(domains),
            authoritative_sources=authoritative,
            primary_sources=primary,
            citations_valid=citations_valid,
            freshness_required=freshness_required,
            freshness_verified=freshness_verified,
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

    @staticmethod
    def _merge_candidates(
        payloads: list[tuple[str, dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}

        for query, payload in payloads:
            for item in payload.get("results", []):
                url = str(item.get("url", "")).strip()
                if not url:
                    continue

                candidate = dict(item)
                candidate["matched_query"] = query
                previous = merged.get(url)

                if previous is None:
                    merged[url] = candidate
                    continue

                current_key = (
                    float(candidate.get("authority_score", 0.0)),
                    float(candidate.get("score", 0.0)),
                )
                previous_key = (
                    float(previous.get("authority_score", 0.0)),
                    float(previous.get("score", 0.0)),
                )
                if current_key > previous_key:
                    merged[url] = candidate

        return sorted(
            merged.values(),
            key=lambda item: (
                item.get("authority_score", 0.0),
                item.get("score", 0.0),
            ),
            reverse=True,
        )

    @staticmethod
    def _synthesis_contract(
        *,
        plan: ResearchQueryPlan,
        quality: ResearchQuality,
        claims: list[dict[str, Any]],
        conflicts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        disclosures: list[str] = []
        if conflicts:
            disclosures.append("source_conflicts")
        if plan.freshness_required and not quality.freshness_verified:
            disclosures.append("freshness_unverified")
        if plan.require_primary_source and quality.primary_sources == 0:
            disclosures.append("primary_source_missing")

        supported_claims = [
            {
                "claim_id": str(claim.get("id", "")),
                "text": str(claim.get("text", "")),
                "citation": str(claim.get("source_url", "")),
                "authority": str(claim.get("authority", "general")),
                "published_at": claim.get("published_at"),
            }
            for claim in claims
            if claim.get("id") and claim.get("source_url")
        ]

        return {
            "mode": "claim-evidence",
            "citation_policy": "near-claim",
            "supported_claims": supported_claims,
            "supported_claim_count": len(supported_claims),
            "conflicts": conflicts,
            "required_disclosures": disclosures,
            "must_not_invent_claims": True,
            "must_not_hide_conflicts": True,
            "must_not_fake_freshness": True,
        }

    def _search_plan(
        self,
        plan: ResearchQueryPlan,
        selected_sources: int,
    ) -> tuple[
        list[dict[str, Any]],
        list[str],
        list[dict[str, str]],
    ]:
        payloads: list[tuple[str, dict[str, Any]]] = []
        providers_used: list[str] = []
        provider_errors: list[dict[str, str]] = []

        for query in plan.queries:
            try:
                payload = self.search_engine.search(
                    query,
                    limit=max(selected_sources * 3, 8),
                )
            except Exception as error:
                provider_errors.append(
                    {
                        "query": query,
                        "provider": "search-engine",
                        "error": f"{type(error).__name__}: {error}",
                    }
                )
                continue

            payloads.append((query, payload))
            for provider in payload.get("providers_used", []):
                if provider not in providers_used:
                    providers_used.append(provider)
            for item in payload.get("provider_errors", []):
                normalized = dict(item)
                normalized["query"] = query
                provider_errors.append(normalized)

        if not payloads:
            raise ResearchError("All planned search queries failed")

        return (
            self._merge_candidates(payloads),
            providers_used,
            provider_errors,
        )

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

        plan = plan_research_queries(query)
        candidates, providers_used, provider_errors = self._search_plan(
            plan,
            selected_sources,
        )

        sources: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        used_domains: set[str] = set()

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
            title = evidence.title or result["title"]
            publication = extract_publication_signal(
                content=evidence.content,
                title=title,
                url=evidence.final_url,
                retrieved_at_ms=evidence.retrieved_at_ms,
            )
            freshness_verified = publication_is_fresh(
                publication.published_at,
                retrieved_at_ms=evidence.retrieved_at_ms,
                window_days=plan.freshness_window_days,
            )

            sources.append(
                {
                    "title": title,
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
                    "matched_query": result.get(
                        "matched_query",
                        plan.original_query,
                    ),
                    "retrieved_at_ms": (
                        evidence.retrieved_at_ms
                    ),
                    "published_at": publication.published_at,
                    "publication_source": publication.source,
                    "publication_confidence": publication.confidence,
                    "freshness_verified": freshness_verified,
                    "sha256": evidence.sha256,
                    "from_cache": evidence.from_cache,
                    "citation": {
                        "title": title,
                        "url": evidence.final_url,
                        "retrieved_at_ms": (
                            evidence.retrieved_at_ms
                        ),
                        "published_at": publication.published_at,
                        "sha256": evidence.sha256,
                    },
                }
            )

        if not sources:
            raise ResearchError(
                "No search result could be retrieved"
            )

        claims = [
            claim
            for source in sources
            for claim in build_evidence_claims(source)
        ]
        conflicts = detect_conflicts(sources)

        quality = self.quality.evaluate(
            sources,
            require_primary_source=plan.require_primary_source,
            freshness_required=plan.freshness_required,
        )
        synthesis = self._synthesis_contract(
            plan=plan,
            quality=quality,
            claims=claims,
            conflicts=conflicts,
        )

        return {
            "query": plan.original_query,
            "state": (
                "completed"
                if quality.accepted and not quality.issues and not conflicts
                else "completed_with_warnings"
            ),
            "research_plan": plan.to_dict(),
            "sources": sources,
            "source_errors": errors,
            "evidence": {
                "claims": claims,
                "claim_count": len(claims),
                "conflicts": conflicts,
                "conflict_count": len(conflicts),
            },
            "synthesis": synthesis,
            "search": {
                "queries": list(plan.queries),
                "query_count": len(plan.queries),
                "providers_used": providers_used,
                "provider_errors": provider_errors,
                "candidate_count": len(candidates),
            },
            "quality": asdict(quality),
            "instructions_for_model": [
                "Synthesize only from synthesis.supported_claims.",
                "Keep each factual claim linked to its source URL.",
                "Use only claims supported by the supplied sources.",
                "Cite the source URL near every factual claim.",
                "Prefer primary sources over secondary summaries.",
                "Distinguish confirmed facts from inference.",
                "Mention disagreements or missing evidence.",
                "Treat evidence.conflicts as unresolved until reconciled.",
                "Respect synthesis.required_disclosures.",
                "Do not claim freshness unless freshness_verified is true.",
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
        "multi_query": True,
        "query_planning": True,
        "source_retrieval": True,
        "source_diversity": True,
        "authority_ranking": True,
        "primary_source_gate": True,
        "freshness_awareness": True,
        "freshness_verification": True,
        "publication_signal_extraction": True,
        "claim_evidence": True,
        "conflict_detection": True,
        "structured_synthesis_contract": True,
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
