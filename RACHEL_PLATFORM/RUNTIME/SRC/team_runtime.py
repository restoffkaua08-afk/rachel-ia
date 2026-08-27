from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from runtime_paths import CONFIG, LOGS, PLATFORM, ROOT, STATE

ORGAN_ROOT = PLATFORM / "ORGAOS"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def now_ms() -> int:
    return int(time.time() * 1000)


class JhonLogger:
    def __init__(self, path: Path | None = None) -> None:
        LOGS.mkdir(parents=True, exist_ok=True)
        self.path = path or LOGS / "rachel-runtime.jsonl"

    def write(self, level: str, source: str, event: str, **data: Any) -> dict[str, Any]:
        record = {"timestamp_ms": now_ms(), "level": level, "source": source, "event": event, "data": data}
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record


class KingEventBus:
    def __init__(self, path: Path | None = None) -> None:
        STATE.mkdir(parents=True, exist_ok=True)
        self.path = path or STATE / "king-events.db"
        connection = sqlite3.connect(self.path)
        try:
            connection.execute("""CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, topic TEXT NOT NULL, sender TEXT NOT NULL, recipient TEXT, payload TEXT NOT NULL, created_at_ms INTEGER NOT NULL)""")
            connection.commit()
        finally:
            connection.close()

    def publish(self, topic: str, payload: dict[str, Any], sender: str = "rachel", recipient: str | None = None) -> dict[str, Any]:
        event = {"id": str(uuid.uuid4()), "topic": topic, "sender": sender, "recipient": recipient, "payload": payload, "created_at_ms": now_ms()}
        connection = sqlite3.connect(self.path)
        try:
            connection.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)", (event["id"], event["topic"], event["sender"], event["recipient"], json.dumps(payload, ensure_ascii=False), event["created_at_ms"]))
            connection.commit()
        finally:
            connection.close()
        return event

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        connection = sqlite3.connect(self.path)
        try:
            rows = connection.execute("SELECT id, topic, sender, recipient, payload, created_at_ms FROM events ORDER BY created_at_ms DESC LIMIT ?", (max(1, min(limit, 200)),)).fetchall()
        finally:
            connection.close()
        return [{"id": row[0], "topic": row[1], "sender": row[2], "recipient": row[3], "payload": json.loads(row[4]), "created_at_ms": row[5]} for row in rows]


@dataclass(frozen=True)
class PolicyDecision:
    effect: str
    risk: str
    allowed: bool
    approval_required: bool
    reason: str


class CyberPolicy:
    LOW = {"read", "inspect", "list", "status", "search"}
    MEDIUM = {"write", "create", "edit", "install", "execute", "external"}
    HIGH = {"delete", "admin", "credentials", "publish", "payment"}

    def check(self, effect: str, approved: bool = False) -> PolicyDecision:
        normalized = effect.strip().lower()
        if normalized in self.LOW:
            return PolicyDecision(normalized, "low", True, False, "Operacao somente leitura.")
        if normalized in self.MEDIUM:
            return PolicyDecision(normalized, "medium", approved, not approved, "Operacao modifica estado e exige autorizacao." if not approved else "Autorizacao confirmada.")
        if normalized in self.HIGH:
            return PolicyDecision(normalized, "high", approved, True, "Operacao sensivel exige autorizacao explicita." if not approved else "Autorizacao explicita confirmada.")
        return PolicyDecision(normalized, "unknown", False, True, "Efeito desconhecido bloqueado por padrao.")


class TyrionSupervisor:
    def __init__(self) -> None:
        self.registry = list(load_json(CONFIG / "organs.registry.json").get("orgaos", []))

    @staticmethod
    def organ_id(item: dict[str, Any]) -> str:
        value = str(item.get("alias") or item.get("id") or item.get("nome_original") or "unknown")
        return value.removeprefix("rachel.")

    def health(self, organ_id: str | None = None) -> dict[str, Any]:
        results = []
        for item in self.registry:
            current_id = self.organ_id(item)
            if organ_id and current_id != organ_id.removeprefix("rachel."):
                continue
            folder = ORGAN_ROOT / current_id
            source = folder / "fonte"
            manifest = folder / "organ.json"
            results.append({"id": current_id, "folder": folder.exists(), "source": source.exists(), "manifest": manifest.exists(), "status": "available" if folder.exists() and source.exists() and manifest.exists() else "failed"})
        if organ_id and not results:
            raise ValueError(f"Orgao nao encontrado: {organ_id}")
        return {"total": len(results), "available": sum(item["status"] == "available" for item in results), "failed": sum(item["status"] == "failed" for item in results), "organs": results}


class NedRouter:
    ROUTES = {
        "stella": {"voz", "audio", "microfone", "falar", "transcrever"},
        "visao": {"pdf", "documento", "imagem", "arquivo", "planilha"},
        "arya": {"codigo", "terminal", "programar", "navegador", "browser", "site", "pagina", "página", "url", "link", "clicar", "clique", "formulario", "formulário", "login", "download", "upload", "automacao"},
        "bran": {"lembrar", "memoria", "conhecimento", "recordar", "buscar"},
        "cyber": {"seguranca", "permissao", "privacidade", "risco", "credencial"},
        "samwell": {"dependencia", "dependencias", "dependência", "dependências", "ambiente", "ambientes", "python", "node", "rust", "cargo", "ffmpeg", "ollama", "portable", "frozen", "empacotamento", "pyinstaller", "cuda", "pytorch", "torch", "instalacao"},
        "dany": {"teste", "avaliar", "qualidade", "comparar", "feedback"},
        "jhon": {"erro", "log", "status", "desempenho", "diagnostico"},
        "tyrion": {"iniciar", "parar", "reiniciar", "orgao", "servico"},
    }
    BROWSER_URL_RE = re.compile(r"https?://[^\s<>'\"]+", re.IGNORECASE)
    BROWSER_INTENTS = (
        ("browser.title", ("titulo", "título", "title")),
        ("browser.read", ("leia", "ler", "conteudo", "conteúdo", "texto", "resuma", "resumir")),
        ("browser.open", ("abra", "abrir", "acesse", "acessar", "navegue", "navegar", "visite", "visitar")),
    )

    def route(self, task: str) -> list[str]:
        words = {word.strip(".,:;!?()[]{}\"").casefold() for word in task.split()}
        members = [name for name, keywords in self.ROUTES.items() if words & keywords]
        return members or ["ned"]

    def browser_intent(self, task: str) -> dict[str, Any] | None:
        normalized = " ".join(str(task).casefold().split())
        url_match = self.BROWSER_URL_RE.search(str(task))
        browser_context = bool(url_match) or any(token in normalized for token in ("site", "pagina", "página", "browser", "navegador", "url", "link"))
        if not browser_context:
            return None
        for tool, markers in self.BROWSER_INTENTS:
            if any(marker in normalized for marker in markers):
                return {"tool": tool, "arguments": {"url": url_match.group(0).rstrip(".,;!?)") if url_match else None}, "effect": "read", "member": "arya"}
        if url_match:
            return {"tool": "browser.open", "arguments": {"url": url_match.group(0).rstrip(".,;!?)")}, "effect": "read", "member": "arya"}
        return None


def doctor() -> dict[str, Any]:
    health = TyrionSupervisor().health()
    checks = {"king": True, "tyrion": health["failed"] == 0 and health["total"] == 23, "jhon": LOGS.exists(), "cyber": True, "organs": health}
    checks["healthy"] = all(checks[name] for name in ("king", "tyrion", "jhon", "cyber"))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(prog="rachel-runtime")
    sub = parser.add_subparsers(dest="domain", required=True)
    runtime = sub.add_parser("runtime")
    runtime_sub = runtime.add_subparsers(dest="action", required=True)
    runtime_sub.add_parser("doctor")
    event = sub.add_parser("event")
    event_sub = event.add_subparsers(dest="action", required=True)
    emit = event_sub.add_parser("emit")
    emit.add_argument("topic")
    emit.add_argument("payload")
    recent = event_sub.add_parser("list")
    recent.add_argument("--limit", type=int, default=20)
    policy = sub.add_parser("policy")
    policy_sub = policy.add_subparsers(dest="action", required=True)
    check = policy_sub.add_parser("check")
    check.add_argument("effect")
    check.add_argument("--approved", action="store_true")
    organ = sub.add_parser("organ-health")
    organ.add_argument("organ_id", nargs="?")
    route = sub.add_parser("route")
    route.add_argument("task")
    args = parser.parse_args()

    logger = JhonLogger()
    if args.domain == "runtime" and args.action == "doctor":
        result = doctor()
        logger.write("info", "jhon", "runtime.doctor", healthy=result["healthy"])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["healthy"] else 1
    if args.domain == "event" and args.action == "emit":
        try:
            payload = json.loads(args.payload)
        except json.JSONDecodeError:
            payload = {"message": args.payload}
        result = KingEventBus().publish(args.topic, payload)
        logger.write("info", "king", "event.published", topic=args.topic, event_id=result["id"])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.domain == "event" and args.action == "list":
        print(json.dumps(KingEventBus().recent(args.limit), ensure_ascii=False, indent=2))
        return 0
    if args.domain == "policy" and args.action == "check":
        decision = CyberPolicy().check(args.effect, args.approved)
        logger.write("info", "cyber", "policy.checked", **asdict(decision))
        print(json.dumps(asdict(decision), ensure_ascii=False, indent=2))
        return 0 if decision.allowed else 3
    if args.domain == "organ-health":
        try:
            result = TyrionSupervisor().health(args.organ_id)
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 2
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["failed"] == 0 else 1
    if args.domain == "route":
        router = NedRouter()
        members = router.route(args.task)
        browser_intent = router.browser_intent(args.task)
        payload = {"task": args.task, "members": members, "browser_intent": browser_intent}
        event = KingEventBus().publish("task.routed", payload, sender="ned")
        print(json.dumps({"members": members, "browser_intent": browser_intent, "event_id": event["id"]}, ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())