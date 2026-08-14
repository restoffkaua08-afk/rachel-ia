from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from urllib.parse import urlparse

from .bootstrap import Container
from .domain.errors import RachelError, ValidationError
from .domain.models import ChatRequest
from .web import WEB_APP


class RachelRequestHandler(BaseHTTPRequestHandler):
    container: Container
    server_version = "RachelCore/0.1"

    def log_message(self, format: str, *args: object) -> None:
        return

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _html(self, status: int, content: str) -> None:
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'")
        self.end_headers()
        self.wfile.write(body)

    def _bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        token = self.container.settings.api_token
        return not token or self.headers.get("Authorization") == f"Bearer {token}"

    def _require_auth(self) -> bool:
        if self._authorized():
            return True
        self._json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
        return False

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 1_000_000:
            raise ValidationError("Corpo ausente ou maior que 1 MB.")
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError("JSON inválido.") from exc
        if not isinstance(value, dict):
            raise ValidationError("O corpo deve ser um objeto JSON.")
        return value

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/":
            self._html(HTTPStatus.OK, WEB_APP)
            return
        if path == "/assets/rachel-heart.png":
            body = files("rachel_core").joinpath("assets/rachel-heart.png").read_bytes()
            self._bytes(HTTPStatus.OK, body, "image/png")
            return
        if not self._require_auth():
            return
        if path == "/health":
            self._json(HTTPStatus.OK, self.container.chat.status())
            return
        if path == "/v1/conversations":
            items = [
                {
                    "id": c.id,
                    "title": c.title,
                    "created_at": c.created_at,
                    "updated_at": c.updated_at,
                }
                for c in self.container.memory.list_conversations()
            ]
            self._json(HTTPStatus.OK, {"items": items})
            return
        prefix, suffix = "/v1/conversations/", "/export"
        if path.startswith(prefix) and path.endswith(suffix):
            conversation_id = path[len(prefix) : -len(suffix)]
            try:
                self._json(
                    HTTPStatus.OK, self.container.memory.export_conversation(conversation_id)
                )
            except RachelError as exc:
                self._json(HTTPStatus.NOT_FOUND, {"error": exc.code, "message": str(exc)})
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if not self._require_auth():
            return
        if urlparse(self.path).path != "/v1/chat":
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        try:
            data = self._read_json()
            result = self.container.chat.chat(
                ChatRequest(
                    content=str(data.get("content", "")),
                    conversation_id=(
                        str(data["conversation_id"]) if data.get("conversation_id") else None
                    ),
                )
            )
            self._json(HTTPStatus.OK, result.to_dict())
        except ValidationError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": exc.code, "message": str(exc)})
        except RachelError as exc:
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR, {"error": exc.code, "message": str(exc)}
            )
        except Exception:
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "INTERNAL_ERROR", "message": "Erro interno do Rachel Core."},
            )

    def do_DELETE(self) -> None:  # noqa: N802
        if not self._require_auth():
            return
        prefix = "/v1/conversations/"
        path = urlparse(self.path).path
        if not path.startswith(prefix):
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        deleted = self.container.memory.delete_conversation(path[len(prefix) :])
        self._json(HTTPStatus.OK if deleted else HTTPStatus.NOT_FOUND, {"deleted": deleted})


def serve(container: Container, host: str | None = None, port: int | None = None) -> None:
    host = host or container.settings.api_host
    port = port or container.settings.api_port
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Por segurança, o Rachel Core aceita apenas endereço loopback.")
    handler = type("ConfiguredRachelHandler", (RachelRequestHandler,), {"container": container})
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Rachel Core em http://{host}:{port} — Ctrl+C para encerrar")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
