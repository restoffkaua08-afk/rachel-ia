from __future__ import annotations

import argparse
import json
import platform
import sys

from . import __version__
from .api import serve
from .bootstrap import build_container
from .domain.errors import RachelError
from .domain.models import ChatRequest


def doctor(container) -> int:
    report = {
        "rachel_core": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "home": str(container.settings.home),
        "database": str(container.settings.home / "rachel.db"),
        "provider": container.chat.model.provider_name,
        "model": container.chat.model.model_name,
        "api_host": container.settings.api_host,
        "api_port": container.settings.api_port,
        "api_token_configured": bool(container.settings.api_token),
        "status": "ok",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def interactive_chat(container) -> int:
    print("Rachel Core 0.1 — digite /sair para encerrar, /nova para reiniciar a conversa.")
    conversation_id = None
    while True:
        try:
            content = input("Você> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if content.lower() in {"/sair", "/exit", "/quit"}:
            return 0
        if content.lower() == "/nova":
            conversation_id = None
            print("Nova conversa iniciada.")
            continue
        if not content:
            continue
        try:
            result = container.chat.chat(
                ChatRequest(content=content, conversation_id=conversation_id)
            )
            conversation_id = result.conversation_id
            print(f"Rachel> {result.message.content}")
        except RachelError as exc:
            print(f"Erro [{exc.code}]: {exc}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rachel", description="Rachel Core")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Valida configuração e armazenamento")
    sub.add_parser("chat", help="Abre chat local no terminal")
    serve_parser = sub.add_parser("serve", help="Inicia API HTTP local")
    serve_parser.add_argument("--host", default=None)
    serve_parser.add_argument("--port", type=int, default=None)
    export_parser = sub.add_parser("export", help="Exporta uma conversa")
    export_parser.add_argument("conversation_id")
    delete_parser = sub.add_parser("delete", help="Apaga uma conversa")
    delete_parser.add_argument("conversation_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    container = build_container()
    if args.command == "doctor":
        return doctor(container)
    if args.command == "chat":
        return interactive_chat(container)
    if args.command == "serve":
        serve(container, args.host, args.port)
        return 0
    if args.command == "export":
        print(
            json.dumps(
                container.memory.export_conversation(args.conversation_id),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "delete":
        deleted = container.memory.delete_conversation(args.conversation_id)
        print(json.dumps({"deleted": deleted}))
        return 0 if deleted else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

