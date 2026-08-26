from __future__ import annotations

from dataclasses import asdict
from typing import Any

from dany_professional import DanyProfessional, EvalContext, QualityReport


_CODE_VALIDATION_TOOLS = {
    "arya.project.generate",
    "arya.command.execute",
    "shell.execute",
    "terminal.execute",
}


def _source_urls(tool_result: dict[str, Any] | None) -> tuple[str, ...]:
    if not isinstance(tool_result, dict):
        return ()
    sources = tool_result.get("sources")
    if not isinstance(sources, list):
        return ()
    urls: list[str] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        url = source.get("url")
        if isinstance(url, str) and url.strip():
            urls.append(url.strip())
    return tuple(dict.fromkeys(urls))


def _primary_source_count(tool_result: dict[str, Any] | None) -> int | None:
    if not isinstance(tool_result, dict):
        return None
    sources = tool_result.get("sources")
    if not isinstance(sources, list):
        return None
    return sum(
        1
        for source in sources
        if isinstance(source, dict)
        and str(source.get("authority", "")).casefold() == "primary"
    )


def _code_checks(tool_result: dict[str, Any] | None) -> tuple[str, ...]:
    if not isinstance(tool_result, dict):
        return ()

    found: list[str] = []
    stack: list[Any] = [tool_result]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, value in current.items():
                folded = str(key).casefold()
                if folded in {"pytest", "tests", "test", "lint", "typecheck", "build", "cargo_check"}:
                    if value not in {None, False, "", "not_run", "skipped"}:
                        found.append(folded)
                stack.append(value)
        elif isinstance(current, (list, tuple)):
            stack.extend(current)

    return tuple(dict.fromkeys(found))


def tool_result_failed(tool_result: dict[str, Any] | None) -> bool:
    """Public runtime helper for conservative fallback summaries."""
    if not isinstance(tool_result, dict):
        return False
    return DanyProfessional._tool_failed(tool_result)


def build_eval_context(
    request: str,
    *,
    tool_name: str | None = None,
    tool_result: dict[str, Any] | None = None,
    factuality_verified: bool | None = None,
) -> EvalContext:
    research = tool_name == "web.research"
    citations = _source_urls(tool_result) if research else ()
    primary_source_count = _primary_source_count(tool_result) if research else None
    checks = _code_checks(tool_result)
    code_validation_required = bool(
        tool_name in _CODE_VALIDATION_TOOLS
        or any(
            term in request.casefold()
            for term in ("teste", "testes", "build", "lint", "typecheck", "valide", "validar")
        )
    )

    return EvalContext(
        request=request,
        tool_result=tool_result,
        evidence=tool_result,
        citations=citations,
        research=research,
        primary_source_count=primary_source_count,
        code_validation_required=code_validation_required,
        code_checks_run=checks,
        factuality_verified=factuality_verified,
    )


def evaluate_runtime_response(
    response: str,
    request: str,
    *,
    tool_name: str | None = None,
    tool_result: dict[str, Any] | None = None,
    factuality_verified: bool | None = None,
    evaluator: DanyProfessional | None = None,
) -> QualityReport:
    context = build_eval_context(
        request,
        tool_name=tool_name,
        tool_result=tool_result,
        factuality_verified=factuality_verified,
    )
    return (evaluator or DanyProfessional()).evaluate(response, context)


def quality_payload(report: QualityReport) -> dict[str, Any]:
    payload = asdict(report)
    payload["validator"] = "dany-professional"
    return payload
