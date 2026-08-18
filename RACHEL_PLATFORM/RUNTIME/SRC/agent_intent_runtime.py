from __future__ import annotations

import re


PLAN_ONLY = re.compile(
    r"^\s*(?:rachel[, ]+)?(?:planeje|crie\s+um\s+plano|monte\s+um\s+plano|elabore\s+um\s+plano)\b",
    re.I,
)

ACTION_GROUPS = {
    "inspect": re.compile(
        r"\b(?:analise|revise|verifique|investigue|descubra|inspecione|diagnostique)\b",
        re.I,
    ),
    "change": re.compile(
        r"\b(?:corrija|conserte|refatore|implemente|edite|altere|ajuste|melhore|atualize)\b",
        re.I,
    ),
    "validate": re.compile(
        r"\b(?:teste|testes|testar|valide|validar|build|compile|compilar|lint|typecheck)\b",
        re.I,
    ),
    "project": re.compile(
        r"\b(?:projeto|repositorio|repositório|codebase|sistema|aplicacao|aplicação)\b",
        re.I,
    ),
}

EXPLICIT_AGENT_PHRASES = (
    re.compile(r"\bdo\s+come[cç]o\s+ao\s+fim\b", re.I),
    re.compile(r"\bat[eé]\s+(?:funcionar|resolver|ficar\s+pronto|passar\s+nos\s+testes)\b", re.I),
    re.compile(r"\bcontinue\s+at[eé]\b", re.I),
    re.compile(r"\bresolva\s+(?:isso|este|esse)\b", re.I),
    re.compile(r"\btrabalhe\s+(?:neste|nesse|no)\s+(?:projeto|repositorio|repositório)\b", re.I),
)


def should_route_to_agent(content: str) -> bool:
    """Detect goals that materially benefit from a multi-step agent loop.

    Single actions such as creating one directory should continue through the
    normal one-tool planner. Multi-stage project work is routed to the agent.
    The user never needs to name Ned, Arya, Cyber or any internal tool.
    """
    text = " ".join(str(content).strip().split())
    if not text or PLAN_ONLY.search(text):
        return False
    if any(pattern.search(text) for pattern in EXPLICIT_AGENT_PHRASES):
        return True

    groups = {
        name
        for name, pattern in ACTION_GROUPS.items()
        if pattern.search(text)
    }

    # A project noun alone is not enough. Two operational categories, or a
    # project plus both change/validation intent, is a real multi-step goal.
    operational = groups - {"project"}
    if len(operational) >= 2:
        return True
    if "project" in groups and "change" in groups and len(text) >= 40:
        return True
    return False
