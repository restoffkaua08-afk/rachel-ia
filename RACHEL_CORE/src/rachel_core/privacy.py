import re
from typing import Any


_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"\b(?:sk|ghp|github_pat|xoxb|AIza)[A-Za-z0-9_\-]{12,}\b"),
    re.compile(r"(?i)authorization:\s*bearer\s+[^\s]+"),
)


def redact_text(value: str) -> str:
    output = value
    for pattern in _PATTERNS:
        output = pattern.sub("[REDACTED]", output)
    return output


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {str(k): redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value

