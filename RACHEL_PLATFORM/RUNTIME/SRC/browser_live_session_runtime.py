from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable

from browser_runtime import BrowserPageEvidence, BrowserUnavailableError
from browser_session_runtime import BrowserSessionError, BrowserSessionManager


class BrowserLiveSessionError(RuntimeError):
    pass


@dataclass
class _LiveHandle:
    context: Any
    page: Any


class PlaywrightSessionBackend:
    """Lazy persistent Playwright backend keyed by governed session_id.

    The browser process is created on first use. A dedicated BrowserContext/Page is
    kept for each logical session and is explicitly closed when the session closes.
    Every main-frame navigation and every request/subrequest is validated through
    the caller-provided URL policy.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._playwright_manager: Any | None = None
        self._playwright: Any | None = None
        self._browser: Any | None = None
        self._handles: dict[str, _LiveHandle] = {}

    def _ensure_browser(self) -> Any:
        with self._lock:
            if self._browser is not None:
                return self._browser
            try:
                from playwright.sync_api import sync_playwright
            except ImportError as error:
                raise BrowserUnavailableError(
                    "Playwright is not installed. Install the governed browser runtime before enabling persistent browser sessions."
                ) from error
            self._playwright_manager = sync_playwright()
            self._playwright = self._playwright_manager.start()
            self._browser = self._playwright.chromium.launch(headless=True)
            return self._browser

    def create(
        self,
        session_id: str,
        *,
        validate_request: Callable[[str], str],
    ) -> None:
        with self._lock:
            if session_id in self._handles:
                raise BrowserLiveSessionError("Live browser session already exists")
            browser = self._ensure_browser()
            context = browser.new_context()
            page = context.new_page()

            def guard(route: Any) -> None:
                try:
                    validate_request(str(route.request.url))
                except Exception:
                    route.abort("blockedbyclient")
                    return
                route.continue_()

            page.route("**/*", guard)
            self._handles[session_id] = _LiveHandle(context=context, page=page)

    def navigate(
        self,
        session_id: str,
        url: str,
        *,
        timeout_seconds: int,
        validate_request: Callable[[str], str],
        maximum_text_characters: int,
    ) -> BrowserPageEvidence:
        requested = validate_request(url)
        with self._lock:
            handle = self._handles.get(session_id)
            if handle is None:
                raise BrowserLiveSessionError("Live browser session is missing")
            page = handle.page
            page.goto(
                requested,
                wait_until="domcontentloaded",
                timeout=max(1, int(timeout_seconds)) * 1000,
            )
            final_url = validate_request(str(page.url))
            title = str(page.title() or "").strip()
            html = str(page.content() or "")
            try:
                text = str(page.locator("body").inner_text() or "")
            except Exception:
                text = ""
            text = text[:maximum_text_characters]
            return BrowserPageEvidence(
                requested_url=requested,
                final_url=final_url,
                title=title,
                text=text,
                html_characters=len(html),
                text_characters=len(text),
            )

    def close(self, session_id: str) -> bool:
        with self._lock:
            handle = self._handles.pop(session_id, None)
            if handle is None:
                return False
            try:
                handle.context.close()
            finally:
                return True

    def shutdown(self) -> None:
        with self._lock:
            for session_id in list(self._handles):
                self.close(session_id)
            if self._browser is not None:
                self._browser.close()
            self._browser = None
            if self._playwright_manager is not None:
                self._playwright_manager.stop()
            self._playwright_manager = None
            self._playwright = None

    def active(self) -> int:
        with self._lock:
            return len(self._handles)


class BrowserLiveSessionRuntime:
    """Binds logical governed sessions to persistent browser contexts.

    This runtime remains read-only. It creates/navigates/closes persistent browser
    sessions but intentionally does not expose click/form/login/upload/download.
    Effectful actions remain behind the separate Cyber-bound effect contract.
    """

    def __init__(
        self,
        *,
        validate_url: Callable[[str], str],
        timeout_seconds: int,
        maximum_text_characters: int,
        backend: Any | None = None,
        sessions: BrowserSessionManager | None = None,
    ) -> None:
        self._validate_url = validate_url
        self.timeout_seconds = max(1, int(timeout_seconds))
        self.maximum_text_characters = max(1, int(maximum_text_characters))
        self.backend = backend or PlaywrightSessionBackend()
        self.sessions = sessions or BrowserSessionManager(validate_url=validate_url)
        self._lock = RLock()

    def create(self, url: str | None = None) -> dict[str, Any]:
        with self._lock:
            logical = self.sessions.create(None)
            session_id = logical["session_id"]
            try:
                self.backend.create(session_id, validate_request=self._validate_url)
                evidence = None
                if url is not None:
                    evidence = self.navigate(session_id, url)
                return {
                    "session": self.sessions.get(session_id),
                    "evidence": evidence,
                    "live_context": True,
                }
            except Exception:
                self.backend.close(session_id)
                self.sessions.close(session_id)
                raise

    def navigate(self, session_id: str, url: str) -> dict[str, Any]:
        # Validate before touching live or logical state.
        requested = self._validate_url(url)
        with self._lock:
            self.sessions.get(session_id)
            evidence = self.backend.navigate(
                session_id,
                requested,
                timeout_seconds=self.timeout_seconds,
                validate_request=self._validate_url,
                maximum_text_characters=self.maximum_text_characters,
            )
            if not isinstance(evidence, BrowserPageEvidence):
                raise BrowserLiveSessionError("Persistent backend returned invalid page evidence")
            session = self.sessions.navigate(session_id, evidence.final_url)
            return {"session": session, "evidence": evidence.to_dict(), "live_context": True}

    def get(self, session_id: str) -> dict[str, Any]:
        return {
            "session": self.sessions.get(session_id),
            "live_context": True,
        }

    def close(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            live_closed = bool(self.backend.close(session_id))
            logical = self.sessions.close(session_id)
            return {"session": logical, "live_context_closed": live_closed}

    def cleanup(self) -> dict[str, Any]:
        # Logical cleanup may expire sessions. Close corresponding live contexts by
        # comparing the active logical IDs through get() failures conservatively.
        logical = self.sessions.cleanup()
        for session_id in logical.get("removed", []):
            self.backend.close(session_id)
        return {
            **logical,
            "live_contexts": int(self.backend.active()),
        }

    def status(self) -> dict[str, Any]:
        logical = self.sessions.status()
        return {
            **logical,
            "live_playwright_context_persistence": True,
            "live_contexts": int(self.backend.active()),
            "effectful_actions_enabled": False,
            "mode": "persistent-read-only",
        }
