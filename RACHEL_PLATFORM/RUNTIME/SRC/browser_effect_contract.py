from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


class BrowserEffectContractError(ValueError):
    pass


_SELECTOR_RE = re.compile(r"^[^\x00-\x1f]{1,500}$")
_ALLOWED_ACTIONS = frozenset({"click", "form", "login", "upload", "download"})


@dataclass(frozen=True)
class BrowserEffectTarget:
    session_id: str
    page_id: str
    action: str
    selector: str | None
    expected_url_prefix: str | None
    expected_text: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _required_text(arguments: dict[str, Any], key: str, maximum: int) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BrowserEffectContractError(f"{key} is required")
    clean = value.strip()
    if len(clean) > maximum:
        raise BrowserEffectContractError(f"{key} exceeds {maximum} characters")
    return clean


def _optional_text(arguments: dict[str, Any], key: str, maximum: int) -> str | None:
    value = arguments.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise BrowserEffectContractError(f"{key} must be a string or null")
    clean = value.strip()
    if not clean:
        return None
    if len(clean) > maximum:
        raise BrowserEffectContractError(f"{key} exceeds {maximum} characters")
    return clean


def normalize_effect_target(action: str, arguments: dict[str, Any]) -> BrowserEffectTarget:
    normalized_action = str(action).strip().casefold()
    if normalized_action not in _ALLOWED_ACTIONS:
        raise BrowserEffectContractError(f"Unsupported browser effect: {action}")
    if not isinstance(arguments, dict):
        raise BrowserEffectContractError("Browser effect arguments must be an object")

    session_id = _required_text(arguments, "session_id", 200)
    page_id = _required_text(arguments, "page_id", 200)
    selector = _optional_text(arguments, "selector", 500)
    expected_url_prefix = _optional_text(arguments, "expected_url_prefix", 2_000)
    expected_text = _optional_text(arguments, "expected_text", 2_000)

    if normalized_action in {"click", "form", "login", "upload"}:
        if selector is None:
            raise BrowserEffectContractError("selector is required for this browser effect")
        if _SELECTOR_RE.fullmatch(selector) is None:
            raise BrowserEffectContractError("selector contains invalid control characters or is too long")

    if normalized_action == "download" and selector is None:
        raise BrowserEffectContractError("selector is required to bind the download trigger")

    if expected_url_prefix is None and expected_text is None:
        raise BrowserEffectContractError(
            "At least one postcondition is required: expected_url_prefix or expected_text"
        )

    return BrowserEffectTarget(
        session_id=session_id,
        page_id=page_id,
        action=normalized_action,
        selector=selector,
        expected_url_prefix=expected_url_prefix,
        expected_text=expected_text,
    )


def approval_bound_arguments(action: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Return the canonical subset that must be covered by Cyber approval.

    ApprovalStore already hashes the complete arguments object. This helper makes the
    browser contract explicit and ensures session/page/selector/postconditions are
    present before an approval can be requested or consumed.
    """
    target = normalize_effect_target(action, arguments)
    payload = target.to_dict()

    if target.action in {"form", "login"}:
        fields = arguments.get("fields")
        if not isinstance(fields, dict) or not fields:
            raise BrowserEffectContractError("fields must be a non-empty object")
        if len(fields) > 50:
            raise BrowserEffectContractError("fields exceeds 50 entries")
        sanitized_fields: dict[str, str] = {}
        for key, value in fields.items():
            if not isinstance(key, str) or not key.strip() or len(key) > 200:
                raise BrowserEffectContractError("field names must be non-empty strings up to 200 chars")
            if not isinstance(value, str) or len(value) > 20_000:
                raise BrowserEffectContractError("field values must be strings up to 20000 chars")
            sanitized_fields[key.strip()] = value
        payload["fields"] = sanitized_fields

    if target.action == "upload":
        payload["file_path"] = _required_text(arguments, "file_path", 2_000)

    if target.action == "download":
        payload["suggested_name"] = _optional_text(arguments, "suggested_name", 300)

    return payload
