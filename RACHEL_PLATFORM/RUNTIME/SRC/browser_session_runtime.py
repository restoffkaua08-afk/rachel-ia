from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass
from threading import RLock
from typing import Any, Callable
from urllib.parse import urlparse


class BrowserSessionError(RuntimeError):
    pass


@dataclass(frozen=True)
class BrowserSessionSnapshot:
    session_id: str
    page_id: str
    current_url: str | None
    origin: str | None
    created_at_ms: int
    last_used_at_ms: int
    closed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _BrowserSessionState:
    session_id: str
    page_id: str
    current_url: str | None
    origin: str | None
    created_at_ms: int
    last_used_at_ms: int
    closed: bool = False

    def snapshot(self) -> BrowserSessionSnapshot:
        return BrowserSessionSnapshot(
            session_id=self.session_id,
            page_id=self.page_id,
            current_url=self.current_url,
            origin=self.origin,
            created_at_ms=self.created_at_ms,
            last_used_at_ms=self.last_used_at_ms,
            closed=self.closed,
        )


class BrowserSessionManager:
    """Owns browser-session metadata and lifecycle without bypassing URL policy.

    This module intentionally does not execute clicks/forms yet. It establishes the
    deterministic session contract required before effectful browser actions can be
    enabled: stable session/page identifiers, TTL eviction, explicit close, bounded
    session count and URL validation on every navigation update.
    """

    def __init__(
        self,
        *,
        validate_url: Callable[[str], str],
        ttl_seconds: int = 900,
        maximum_sessions: int = 8,
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        self._validate_url = validate_url
        self.ttl_seconds = max(30, int(ttl_seconds))
        self.maximum_sessions = max(1, min(int(maximum_sessions), 64))
        self._clock_ms = clock_ms or (lambda: int(time.time() * 1000))
        self._sessions: dict[str, _BrowserSessionState] = {}
        self._lock = RLock()

    @staticmethod
    def _origin(url: str) -> str:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if not host:
            raise BrowserSessionError("Validated browser URL has no hostname")
        port = parsed.port
        default_port = (parsed.scheme == "https" and port == 443) or (
            parsed.scheme == "http" and port == 80
        )
        authority = host if port is None or default_port else f"{host}:{port}"
        return f"{parsed.scheme}://{authority}"

    def _now(self) -> int:
        return int(self._clock_ms())

    def _expired(self, state: _BrowserSessionState, now_ms: int) -> bool:
        return (now_ms - state.last_used_at_ms) > (self.ttl_seconds * 1000)

    def _evict_expired_locked(self, now_ms: int) -> list[str]:
        expired = [
            session_id
            for session_id, state in self._sessions.items()
            if state.closed or self._expired(state, now_ms)
        ]
        for session_id in expired:
            self._sessions.pop(session_id, None)
        return expired

    def _evict_lru_locked(self) -> str | None:
        if len(self._sessions) < self.maximum_sessions:
            return None
        session_id, _ = min(
            self._sessions.items(),
            key=lambda item: (item[1].last_used_at_ms, item[1].created_at_ms, item[0]),
        )
        self._sessions.pop(session_id, None)
        return session_id

    def create(self, url: str | None = None) -> dict[str, Any]:
        now_ms = self._now()
        validated = self._validate_url(url) if url is not None else None
        with self._lock:
            self._evict_expired_locked(now_ms)
            evicted = self._evict_lru_locked()
            session_id = f"browser-session-{uuid.uuid4()}"
            page_id = f"browser-page-{uuid.uuid4()}"
            state = _BrowserSessionState(
                session_id=session_id,
                page_id=page_id,
                current_url=validated,
                origin=self._origin(validated) if validated else None,
                created_at_ms=now_ms,
                last_used_at_ms=now_ms,
            )
            self._sessions[session_id] = state
            result = state.snapshot().to_dict()
            result["evicted_session_id"] = evicted
            return result

    def get(self, session_id: str) -> dict[str, Any]:
        if not isinstance(session_id, str) or not session_id.strip():
            raise BrowserSessionError("session_id is required")
        now_ms = self._now()
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None or state.closed or self._expired(state, now_ms):
                self._sessions.pop(session_id, None)
                raise BrowserSessionError("Browser session is missing or expired")
            state.last_used_at_ms = now_ms
            return state.snapshot().to_dict()

    def navigate(self, session_id: str, url: str) -> dict[str, Any]:
        validated = self._validate_url(url)
        now_ms = self._now()
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None or state.closed or self._expired(state, now_ms):
                self._sessions.pop(session_id, None)
                raise BrowserSessionError("Browser session is missing or expired")
            state.current_url = validated
            state.origin = self._origin(validated)
            state.last_used_at_ms = now_ms
            return state.snapshot().to_dict()

    def close(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._sessions.pop(session_id, None)
            if state is None:
                return {"session_id": session_id, "closed": False, "already_absent": True}
            state.closed = True
            return {"session_id": session_id, "closed": True, "already_absent": False}

    def cleanup(self) -> dict[str, Any]:
        now_ms = self._now()
        with self._lock:
            removed = self._evict_expired_locked(now_ms)
            return {"removed": removed, "removed_count": len(removed), "active": len(self._sessions)}

    def status(self) -> dict[str, Any]:
        now_ms = self._now()
        with self._lock:
            self._evict_expired_locked(now_ms)
            return {
                "active_sessions": len(self._sessions),
                "maximum_sessions": self.maximum_sessions,
                "ttl_seconds": self.ttl_seconds,
                "persistent_metadata": True,
                "live_playwright_context_persistence": False,
                "effectful_actions_enabled": False,
            }
