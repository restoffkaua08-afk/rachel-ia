from __future__ import annotations

import argparse
import hashlib
import html
import ipaddress
import json
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[3]
PLATFORM = ROOT / "RACHEL_PLATFORM"
CONFIG = PLATFORM / "CONFIG"
STATE = PLATFORM / "STATE"
CACHE = STATE / "WEB_CACHE"


class WebError(RuntimeError):
    pass


class WebSecurityError(WebError):
    pass


@dataclass(frozen=True)
class WebEvidence:
    url: str
    final_url: str
    title: str
    content: str
    content_type: str
    status_code: int
    retrieved_at_ms: int
    sha256: str
    from_cache: bool


class WebPolicy:
    def __init__(self, path: Path | None = None) -> None:
        policy_path = path or CONFIG / "web.policy.json"
        self.data = json.loads(
            policy_path.read_text(encoding="utf-8-sig")
        )
        self.blocked_networks = tuple(
            ipaddress.ip_network(item)
            for item in self.data["blocked_networks"]
        )

    @property
    def allowed_schemes(self) -> set[str]:
        return {
            str(item).casefold()
            for item in self.data["allowed_schemes"]
        }

    @property
    def blocked_hosts(self) -> set[str]:
        return {
            str(item).casefold()
            for item in self.data["blocked_hosts"]
        }

    @property
    def allowed_content_types(self) -> set[str]:
        return {
            str(item).casefold()
            for item in self.data["allowed_content_types"]
        }

    @property
    def maximum_response_bytes(self) -> int:
        return int(self.data["maximum_response_bytes"])

    @property
    def maximum_text_characters(self) -> int:
        return int(self.data["maximum_text_characters"])

    @property
    def timeout_seconds(self) -> int:
        return int(self.data["timeout_seconds"])

    @property
    def cache_ttl_seconds(self) -> int:
        return int(self.data["cache_ttl_seconds"])

    @property
    def user_agent(self) -> str:
        return str(self.data["user_agent"])


class ContentParser(HTMLParser):
    IGNORED_TAGS = {
        "script",
        "style",
        "noscript",
        "svg",
        "canvas",
        "template",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.links: list[dict[str, str]] = []
        self._ignored_depth = 0
        self._inside_title = False

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        normalized = tag.casefold()

        if normalized in self.IGNORED_TAGS:
            self._ignored_depth += 1
            return

        if normalized == "title":
            self._inside_title = True

        if normalized == "a" and not self._ignored_depth:
            attributes = dict(attrs)
            href = attributes.get("href")
            if href:
                self.links.append(
                    {
                        "url": href.strip(),
                        "text": "",
                    }
                )

        if normalized in {
            "p",
            "div",
            "section",
            "article",
            "header",
            "footer",
            "main",
            "aside",
            "li",
            "tr",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "br",
        }:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.casefold()

        if normalized in self.IGNORED_TAGS:
            self._ignored_depth = max(
                0,
                self._ignored_depth - 1,
            )
            return

        if normalized == "title":
            self._inside_title = False

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return

        cleaned = " ".join(data.split())

        if not cleaned:
            return

        if self._inside_title:
            self.title_parts.append(cleaned)
        else:
            self.text_parts.append(cleaned)

        if self.links:
            current = self.links[-1]
            if not current["text"]:
                current["text"] = cleaned

    def result(self) -> tuple[str, str, list[dict[str, str]]]:
        title = " ".join(self.title_parts).strip()
        text = " ".join(self.text_parts)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return title, text.strip(), self.links


def normalize_url(url: str) -> str:
    value = url.strip()

    if not value:
        raise WebSecurityError("URL cannot be empty")

    parsed = urllib.parse.urlsplit(value)

    if not parsed.scheme:
        value = "https://" + value
        parsed = urllib.parse.urlsplit(value)

    host = parsed.hostname
    if not host:
        raise WebSecurityError("URL must include a valid host")

    normalized_host = host.encode("idna").decode("ascii")
    port = f":{parsed.port}" if parsed.port else ""

    path = parsed.path or "/"
    path = urllib.parse.quote(
        urllib.parse.unquote(path),
        safe="/:@-._~!$&'()*+,;=",
    )

    return urllib.parse.urlunsplit(
        (
            parsed.scheme.casefold(),
            normalized_host + port,
            path,
            parsed.query,
            "",
        )
    )


def validate_url(
    url: str,
    policy: WebPolicy,
    resolver: Any = socket.getaddrinfo,
) -> str:
    normalized = normalize_url(url)
    parsed = urllib.parse.urlsplit(normalized)

    if parsed.scheme.casefold() not in policy.allowed_schemes:
        raise WebSecurityError(
            f"Blocked URL scheme: {parsed.scheme}"
        )

    host = (parsed.hostname or "").casefold()

    if host in policy.blocked_hosts:
        raise WebSecurityError(f"Blocked host: {host}")

    try:
        direct_ip = ipaddress.ip_address(host)
        addresses = {direct_ip}
    except ValueError:
        try:
            records = resolver(
                host,
                parsed.port or (
                    443 if parsed.scheme == "https" else 80
                ),
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as error:
            raise WebSecurityError(
                f"Host resolution failed: {host}"
            ) from error

        addresses = {
            ipaddress.ip_address(record[4][0])
            for record in records
        }

    if not addresses:
        raise WebSecurityError(
            f"Host resolved to no address: {host}"
        )

    for address in addresses:
        if any(
            address in network
            for network in policy.blocked_networks
        ):
            raise WebSecurityError(
                f"Host resolves to blocked address: {address}"
            )

    return normalized


def decode_body(
    body: bytes,
    content_type_header: str,
) -> str:
    charset_match = re.search(
        r"charset=([A-Za-z0-9._-]+)",
        content_type_header,
        re.I,
    )
    encodings = []

    if charset_match:
        encodings.append(charset_match.group(1))

    encodings.extend(["utf-8-sig", "utf-8", "cp1252"])

    for encoding in encodings:
        try:
            return body.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue

    return body.decode("utf-8", errors="replace")


def parse_content(
    body: bytes,
    content_type_header: str,
) -> tuple[str, str]:
    decoded = decode_body(body, content_type_header)
    base_type = content_type_header.split(";", 1)[0].casefold()

    if base_type == "application/json":
        payload = json.loads(decoded)
        return "", json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )

    if base_type in {
        "application/xml",
        "text/xml",
        "text/plain",
    }:
        return "", decoded.strip()

    parser = ContentParser()
    parser.feed(decoded)
    title, text, _ = parser.result()
    return html.unescape(title), html.unescape(text)


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, policy: WebPolicy) -> None:
        super().__init__()
        self.policy = policy
        self.redirects = 0

    def redirect_request(
        self,
        request: urllib.request.Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> urllib.request.Request | None:
        self.redirects += 1

        if self.redirects > int(
            self.policy.data["maximum_redirects"]
        ):
            raise WebSecurityError("Too many redirects")

        validated = validate_url(
            urllib.parse.urljoin(
                request.full_url,
                new_url,
            ),
            self.policy,
        )

        return super().redirect_request(
            request,
            file_pointer,
            code,
            message,
            headers,
            validated,
        )


class WebCache:
    def __init__(
        self,
        directory: Path | None = None,
        ttl_seconds: int = 1800,
    ) -> None:
        self.directory = directory or CACHE
        self.ttl_seconds = ttl_seconds
        self.directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(url: str) -> str:
        return hashlib.sha256(
            url.encode("utf-8")
        ).hexdigest()

    def get(self, url: str) -> dict[str, Any] | None:
        path = self.directory / f"{self.key(url)}.json"

        if not path.exists():
            return None

        try:
            payload = json.loads(
                path.read_text(encoding="utf-8-sig")
            )
        except (OSError, json.JSONDecodeError):
            return None

        age_ms = int(time.time() * 1000) - int(
            payload.get("retrieved_at_ms", 0)
        )

        if age_ms > self.ttl_seconds * 1000:
            return None

        return payload

    def set(self, url: str, payload: dict[str, Any]) -> None:
        path = self.directory / f"{self.key(url)}.json"
        temporary = path.with_suffix(".tmp")

        temporary.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(path)


class WebClient:
    def __init__(
        self,
        policy: WebPolicy | None = None,
        cache: WebCache | None = None,
    ) -> None:
        self.policy = policy or WebPolicy()
        self.cache = cache or WebCache(
            ttl_seconds=self.policy.cache_ttl_seconds
        )

    def fetch(
        self,
        url: str,
        use_cache: bool = True,
    ) -> WebEvidence:
        validated = validate_url(url, self.policy)

        if use_cache:
            cached = self.cache.get(validated)

            if cached:
                cached["from_cache"] = True
                return WebEvidence(**cached)

        request = urllib.request.Request(
            validated,
            headers={
                "User-Agent": self.policy.user_agent,
                "Accept": (
                    "text/html,application/json,text/plain,"
                    "application/xml;q=0.9,*/*;q=0.1"
                ),
            },
            method="GET",
        )

        opener = urllib.request.build_opener(
            SafeRedirectHandler(self.policy)
        )

        try:
            response = opener.open(
                request,
                timeout=self.policy.timeout_seconds,
            )
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
        ) as error:
            raise WebError(
                f"Request failed: {error}"
            ) from error

        with response:
            content_type_header = response.headers.get(
                "Content-Type",
                "application/octet-stream",
            )
            base_type = content_type_header.split(
                ";",
                1,
            )[0].casefold()

            if base_type not in self.policy.allowed_content_types:
                raise WebError(
                    f"Unsupported content type: {base_type}"
                )

            limit = self.policy.maximum_response_bytes
            body = response.read(limit + 1)

            if len(body) > limit:
                raise WebError(
                    "Response exceeds configured byte limit"
                )

            title, content = parse_content(
                body,
                content_type_header,
            )
            content = content[
                : self.policy.maximum_text_characters
            ].strip()

            if not content:
                raise WebError(
                    "Response contains no extractable text"
                )

            evidence = WebEvidence(
                url=validated,
                final_url=response.geturl(),
                title=title,
                content=content,
                content_type=base_type,
                status_code=int(
                    getattr(response, "status", 200)
                ),
                retrieved_at_ms=int(time.time() * 1000),
                sha256=hashlib.sha256(body).hexdigest(),
                from_cache=False,
            )

            cache_control = response.headers.get(
                "Cache-Control",
                "",
            ).casefold()

            if not (
                self.policy.data["respect_no_store"]
                and "no-store" in cache_control
            ):
                self.cache.set(
                    validated,
                    asdict(evidence),
                )

            return evidence


def evidence_summary(
    evidence: WebEvidence,
    include_content: bool = False,
) -> dict[str, Any]:
    payload = asdict(evidence)

    if not include_content:
        payload.pop("content", None)
        payload["content_characters"] = len(
            evidence.content
        )

    payload["citation"] = {
        "title": evidence.title or evidence.final_url,
        "url": evidence.final_url,
        "retrieved_at_ms": evidence.retrieved_at_ms,
        "sha256": evidence.sha256,
    }

    return payload


def status() -> dict[str, Any]:
    policy = WebPolicy()

    return {
        "available": True,
        "secure_transport": True,
        "ssrf_protection": True,
        "redirect_validation": True,
        "response_limit_bytes": (
            policy.maximum_response_bytes
        ),
        "cache_ttl_seconds": policy.cache_ttl_seconds,
        "citations": True,
        "search": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="rachel-web")
    sub = parser.add_subparsers(dest="action", required=True)

    sub.add_parser("status")

    fetch_parser = sub.add_parser("fetch")
    fetch_parser.add_argument("url")
    fetch_parser.add_argument(
        "--include-content",
        action="store_true",
    )
    fetch_parser.add_argument(
        "--no-cache",
        action="store_true",
    )

    args = parser.parse_args()

    try:
        if args.action == "status":
            payload = status()
        else:
            evidence = WebClient().fetch(
                args.url,
                use_cache=not args.no_cache,
            )
            payload = evidence_summary(
                evidence,
                include_content=args.include_content,
            )
    except (
        OSError,
        ValueError,
        WebError,
        WebSecurityError,
    ) as error:
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
