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
                request_url = str(route.request.url)
                try:
                    validate_request(request_url)
                except Exception:
                    route.abort("blockedbyclient")
                    return
                route.continue_()

            page.route("**/*", guard)
            try:
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
            finally:
                context.close()
                browser.close()


class BrowserRuntime:
    """Governed browser boundary.

    Read-only navigation is enabled. Actions that mutate remote state are
    classified as Cyber `external` effects and remain disabled until a later
    sublot implements selectors/session state with explicit approval contracts.
    """

    READ_ONLY_ACTIONS = frozenset({"open", "title", "read"})
    EFFECTFUL_ACTIONS = frozenset({"click", "form", "login", "upload", "download"})

    def __init__(
        self,
        backend: Any | None = None,
        policy: WebPolicy | None = None,
        resolver: Any | None = None,
    ) -> None:
        self.backend = backend or PlaywrightBrowserBackend()
        self.policy = policy or WebPolicy()
        self.resolver = resolver

    def _validate(self, url: str) -> str:
        if self.resolver is None:
            return validate_url(url, self.policy)
        return validate_url(url, self.policy, resolver=self.resolver)

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
        return {
            "requested_url": page["requested_url"],
            "final_url": page["final_url"],
            "title": page["title"],
        }

    def read(self, url: str) -> dict[str, Any]:
        page = self.open(url)
        return {
            "requested_url": page["requested_url"],
            "final_url": page["final_url"],
            "title": page["title"],
            "text": page["text"],
            "text_characters": page["text_characters"],
        }

    def status(self) -> dict[str, Any]:
        return {
            "available": True,
            "backend": type(self.backend).__name__,
            "read_only_navigation": True,
            "request_guard": "web-policy-every-request",
            "effectful_actions_enabled": False,
            "actions": {
                "open": self.effect_for("open"),
                "title": self.effect_for("title"),
                "read": self.effect_for("read"),
                "click": self.effect_for("click"),
                "form": self.effect_for("form"),
                "login": self.effect_for("login"),
                "upload": self.effect_for("upload"),
                "download": self.effect_for("download"),
            },
        }
