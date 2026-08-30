from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

from web_runtime import WebPolicy, validate_url


class BrowserError(RuntimeError):
    pass


class BrowserUnavailableError(BrowserError):
    pass


@dataclass(frozen=True)
class BrowserPageEvidence:
    requested_url: str
    final_url: str
    title: str
    text: str
    html_characters: int
    text_characters: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PlaywrightBrowserBackend:
    """Lazy Playwright backend guarded by the same web SSRF policy."""

    def open_page(
        self,
        url: str,
        *,
        timeout_seconds: int,
        validate_request: Callable[[str], str],
        maximum_text_characters: int,
    ) -> BrowserPageEvidence:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise BrowserUnavailableError(
                "Playwright is not installed. Install the governed browser runtime before enabling browser tools."
            ) from error

        requested = validate_request(url)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
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
            try:
                page.goto(requested, wait_until="domcontentloaded", timeout=max(1, int(timeout_seconds)) * 1000)
                final_url = validate_request(str(page.url))
                title = str(page.title() or "").strip()
                html = str(page.content() or "")
                try:
                    text = str(page.locator("body").inner_text() or "")
                except Exception:
                    text = ""
                text = text[:maximum_text_characters]
                return BrowserPageEvidence(requested, final_url, title, text, len(html), len(text))
            finally:
                context.close()
                browser.close()


class BrowserRuntime:
    """Canonical governed browser boundary.

    Stateless read-only calls remain available for compatibility. Persistent read-only
    sessions are now part of the official runtime contract and are created lazily.
    Remote-state effects remain disabled until their Cyber-bound executors are enabled.
    """

    READ_ONLY_ACTIONS = frozenset({"open", "title", "read"})
    EFFECTFUL_ACTIONS = frozenset({"click", "form", "login", "upload", "download"})

    def __init__(
        self,
        backend: Any | None = None,
        policy: WebPolicy | None = None,
        resolver: Any | None = None,
        live_sessions: Any | None = None,
    ) -> None:
        self.backend = backend or PlaywrightBrowserBackend()
        self.policy = policy or WebPolicy()
        self.resolver = resolver
        self._live_sessions = live_sessions

    def _validate(self, url: str) -> str:
        if self.resolver is None:
            return validate_url(url, self.policy)
        return validate_url(url, self.policy, resolver=self.resolver)

    def _sessions(self) -> Any:
        if self._live_sessions is None:
            from browser_live_session_runtime import BrowserLiveSessionRuntime
            self._live_sessions = BrowserLiveSessionRuntime(
                validate_url=self._validate,
                timeout_seconds=self.policy.timeout_seconds,
                maximum_text_characters=self.policy.maximum_text_characters,
            )
        return self._live_sessions

    @classmethod
    def effect_for(cls, action: str) -> str:
        normalized = str(action).strip().casefold()
        if normalized in cls.READ_ONLY_ACTIONS:
            return "read"
        if normalized in cls.EFFECTFUL_ACTIONS:
            return "external"
        raise BrowserError(f"Unknown browser action: {action}")

    def open(self, url: str) -> dict[str, Any]:
        evidence = self.backend.open_page(
            url,
            timeout_seconds=self.policy.timeout_seconds,
            validate_request=self._validate,
            maximum_text_characters=self.policy.maximum_text_characters,
        )
        if not isinstance(evidence, BrowserPageEvidence):
            raise BrowserError("Browser backend returned invalid page evidence")
        return evidence.to_dict()

    def title(self, url: str) -> dict[str, Any]:
        page = self.open(url)
        return {"requested_url": page["requested_url"], "final_url": page["final_url"], "title": page["title"]}

    def read(self, url: str) -> dict[str, Any]:
        page = self.open(url)
        return {
            "requested_url": page["requested_url"], "final_url": page["final_url"],
            "title": page["title"], "text": page["text"], "text_characters": page["text_characters"],
        }

    def session_open(self, url: str | None = None) -> dict[str, Any]:
        return self._sessions().create(url)

    def session_navigate(self, session_id: str, url: str) -> dict[str, Any]:
        return self._sessions().navigate(session_id, url)

    def session_get(self, session_id: str) -> dict[str, Any]:
        return self._sessions().get(session_id)

    def session_close(self, session_id: str) -> dict[str, Any]:
        return self._sessions().close(session_id)

    def cleanup(self) -> dict[str, Any]:
        if self._live_sessions is None:
            return {"removed": [], "removed_count": 0, "active": 0, "live_contexts": 0}
        return self._live_sessions.cleanup()

    def status(self) -> dict[str, Any]:
        session_status = {
            "live_playwright_context_persistence": self._live_sessions is not None,
            "live_contexts": 0,
            "mode": "stateless-read-only" if self._live_sessions is None else "persistent-read-only",
        }
        if self._live_sessions is not None:
            session_status.update(self._live_sessions.status())
        return {
            "available": True,
            "backend": type(self.backend).__name__,
            "read_only_navigation": True,
            "persistent_sessions_available": True,
            "request_guard": "web-policy-every-request",
            "effectful_actions_enabled": False,
            "session": session_status,
            "actions": {action: self.effect_for(action) for action in sorted(self.READ_ONLY_ACTIONS | self.EFFECTFUL_ACTIONS)},
        }
