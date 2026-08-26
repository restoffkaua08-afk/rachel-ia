from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


_FAILURE_WORDS = (
    "falhou",
    "falha",
    "erro",
    "não foi conclu",
    "nao foi conclu",
    "não executou",
    "nao executou",
    "não passou",
    "nao passou",
)

_SUCCESS_WORDS = (
    "executado com sucesso",
    "concluído com sucesso",
    "concluido com sucesso",
    "funcionou corretamente",
    "passou com sucesso",
    "foi validado com sucesso",
)

_LOW_CONFIDENCE_WORDS = (
    "baixa confiança",
    "baixa confianca",
    "confiança limitada",
    "confianca limitada",
    "evidência limitada",
    "evidencia limitada",
    "não encontrei fonte primária",
    "nao encontrei fonte primaria",
    "sem fonte primária",
    "sem fonte primaria",
)

_UNCERTAINTY_WORDS = (
    "não foi verificado",
    "nao foi verificado",
    "não verifiquei",
    "nao verifiquei",
    "não posso confirmar",
    "nao posso confirmar",
    "não tenho evidência",
    "nao tenho evidencia",
    "validei apenas",
    "validei só",
    "validei so",
    "estrutura, não factualidade",
    "estrutura, nao factualidade",
)

_URL_PATTERN = re.compile(r"https?://[^\s)\]>]+", re.I)
_NUMBER_PATTERN = re.compile(r"(?<![A-Za-z])\d+(?:[.,]\d+)?(?:%|ms|s|mb|gb|kb)?", re.I)
_COMMAND_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:\$|>|PS>|C:\\[^>]*>)?\s*"
    r"((?:npm|pnpm|yarn|pip|python|pytest|cargo|git|docker|uv|node)\s+[^\n`]+)",
    re.I,
)


@dataclass(frozen=True)
class EvalContext:
    request: str = ""
    tool_result: dict[str, Any] | None = None
    evidence: Any | None = None
    citations: tuple[str, ...] = ()
    research: bool = False
    primary_source_count: int | None = None
    code_validation_required: bool = False
    code_checks_run: tuple[str, ...] = ()
    factuality_verified: bool | None = None


@dataclass(frozen=True)
class QualityReport:
    accepted: bool
    score: int
    issues: tuple[str, ...]
    checks: dict[str, bool]
    scope: str


class DanyProfessional:
    """Deterministic quality gate for grounding and execution consistency.

    Dany does not pretend to prove factual truth from text alone. It verifies
    structural quality, consistency with concrete runtime evidence, citation
    obligations and explicit uncertainty when evidence is insufficient.
    """

    def evaluate(self, response: str, context: EvalContext | None = None) -> QualityReport:
        ctx = context or EvalContext()
        text = str(response).strip()

        checks = {
            "not_empty": bool(text),
            "valid_size": 0 < len(text) <= 100_000,
            "no_null_character": "\x00" not in text,
            "request_fulfilled": self._check_request_fulfilled(text, ctx.request),
            "tool_result_consistent": self._check_tool_result(text, ctx.tool_result),
            "citations_present": self._check_citations(text, ctx),
            "grounded_in_evidence": self._check_grounding(text, ctx),
            "no_obvious_hallucination": self._check_obvious_hallucination(text, ctx),
            "admits_uncertainty": self._check_uncertainty(text, ctx),
            "code_validation_consistent": self._check_code_validation(text, ctx),
        }

        issues = tuple(name.upper() for name, passed in checks.items() if not passed)
        score = round(100 * sum(checks.values()) / len(checks))

        critical = {
            "not_empty",
            "valid_size",
            "no_null_character",
            "tool_result_consistent",
            "citations_present",
            "grounded_in_evidence",
            "no_obvious_hallucination",
            "code_validation_consistent",
        }
        accepted = all(checks[name] for name in critical)

        scope = "grounded"
        if ctx.factuality_verified is not True:
            scope = "structural-and-evidence-consistency"
        if ctx.tool_result is None and ctx.evidence is None and not ctx.research:
            scope = "structural"

        return QualityReport(
            accepted=accepted,
            score=score,
            issues=issues,
            checks=checks,
            scope=scope,
        )

    @staticmethod
    def _check_request_fulfilled(response: str, request: str) -> bool:
        if not response:
            return False
        request_terms = {
            token.casefold()
            for token in re.findall(r"[A-Za-zÀ-ÿ0-9_+-]{4,}", request)
            if token.casefold() not in {
                "para", "como", "qual", "quais", "sobre", "esta", "esse",
                "essa", "isso", "uma", "uns", "com", "sem", "mais", "pode",
                "quero", "preciso", "rachel",
            }
        }
        if not request_terms:
            return True
        response_folded = response.casefold()
        matches = sum(1 for term in request_terms if term in response_folded)
        return matches >= min(1, len(request_terms))

    @classmethod
    def _check_tool_result(cls, response: str, tool_result: dict[str, Any] | None) -> bool:
        if tool_result is None:
            return True
        failed = cls._tool_failed(tool_result)
        folded = response.casefold()
        claims_success = any(term in folded for term in _SUCCESS_WORDS)
        admits_failure = any(term in folded for term in _FAILURE_WORDS)
        if failed:
            return admits_failure and not claims_success
        return True

    @staticmethod
    def _tool_failed(value: Any) -> bool:
        if isinstance(value, dict):
            state = str(value.get("state", "")).casefold()
            if state in {"failed", "error", "denied", "cancelled"}:
                return True
            returncode = value.get("returncode")
            if isinstance(returncode, int) and returncode != 0:
                return True
            if value.get("successful") is False:
                return True
            if value.get("verified") is False and state == "completed":
                return True
            return any(DanyProfessional._tool_failed(item) for item in value.values())
        if isinstance(value, (list, tuple)):
            return any(DanyProfessional._tool_failed(item) for item in value)
        return False

    @staticmethod
    def _check_citations(response: str, ctx: EvalContext) -> bool:
        if not ctx.research:
            return True
        if ctx.primary_source_count == 0:
            folded = response.casefold()
            return any(term in folded for term in _LOW_CONFIDENCE_WORDS)
        if not ctx.citations:
            return False
        return any(citation in response for citation in ctx.citations)

    @staticmethod
    def _check_grounding(response: str, ctx: EvalContext) -> bool:
        if ctx.evidence is None and ctx.tool_result is None:
            return True
        if not response:
            return False
        evidence_text = json.dumps(
            ctx.evidence if ctx.evidence is not None else ctx.tool_result,
            ensure_ascii=False,
            sort_keys=True,
        ).casefold()
        response_terms = {
            token.casefold()
            for token in re.findall(r"[A-Za-zÀ-ÿ0-9_./:-]{5,}", response)
        }
        if not response_terms:
            return True
        evidence_matches = sum(1 for term in response_terms if term in evidence_text)
        if evidence_matches >= 1:
            return True
        if any(term in response.casefold() for term in _UNCERTAINTY_WORDS):
            return True

        # A neutral acknowledgement that makes no concrete factual/execution
        # claim is allowed to pass this check. Request fulfillment remains an
        # advisory score signal, while URLs/numbers/commands and explicit
        # success claims are governed by the stricter checks below.
        makes_concrete_claim = bool(
            _URL_PATTERN.search(response)
            or _NUMBER_PATTERN.search(response)
            or _COMMAND_PATTERN.search(response)
            or any(term in response.casefold() for term in _SUCCESS_WORDS)
        )
        return not makes_concrete_claim

    @staticmethod
    def _check_obvious_hallucination(response: str, ctx: EvalContext) -> bool:
        if ctx.evidence is None and ctx.tool_result is None:
            return True
        evidence_text = json.dumps(
            ctx.evidence if ctx.evidence is not None else ctx.tool_result,
            ensure_ascii=False,
            sort_keys=True,
        )

        for url in _URL_PATTERN.findall(response):
            if url.rstrip(".,") not in evidence_text:
                return False

        evidence_numbers = set(_NUMBER_PATTERN.findall(evidence_text))
        for number in _NUMBER_PATTERN.findall(response):
            if number not in evidence_numbers and len(number) >= 2:
                return False

        for command in _COMMAND_PATTERN.findall(response):
            command = " ".join(command.split())
            if command and command not in evidence_text:
                return False

        return True

    @staticmethod
    def _check_uncertainty(response: str, ctx: EvalContext) -> bool:
        needs_admission = (
            ctx.factuality_verified is False
            or (ctx.research and ctx.primary_source_count == 0)
        )
        if not needs_admission:
            return True
        folded = response.casefold()
        return any(term in folded for term in _UNCERTAINTY_WORDS + _LOW_CONFIDENCE_WORDS)

    @staticmethod
    def _check_code_validation(response: str, ctx: EvalContext) -> bool:
        if not ctx.code_validation_required:
            return True
        folded = response.casefold()
        claims_validation = any(
            phrase in folded
            for phrase in (
                "testes passaram",
                "build passou",
                "lint passou",
                "typecheck passou",
                "validado com sucesso",
            )
        )
        if not claims_validation:
            return True
        return bool(ctx.code_checks_run)
