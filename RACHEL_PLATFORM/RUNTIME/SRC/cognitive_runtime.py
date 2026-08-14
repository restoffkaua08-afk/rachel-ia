from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[3]
STATE = ROOT / "RACHEL_PLATFORM" / "STATE"
STATE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("RACHEL_HOME", str(STATE / "core"))

from rachel_core.bootstrap import build_container
from rachel_core.domain.models import ChatRequest


@dataclass(frozen=True)
class QualityReport:
    accepted: bool
    score: int
    issues: tuple[str, ...]
    checks: dict[str, bool]


class DanyEvaluator:
    def evaluate(self, content: str) -> QualityReport:
        text = content.strip()
        checks = {
            "not_empty": bool(text),
            "valid_size": 0 < len(text) <= 100_000,
            "no_null_character": "\x00" not in text,
            "not_only_whitespace": bool(text.split()),
        }
        issues = tuple(name.upper() for name, passed in checks.items() if not passed)
        score = round(100 * sum(checks.values()) / len(checks))
        return QualityReport(not issues, score, issues, checks)


class NedCognitiveBridge:
    def __init__(self) -> None:
        self.container = build_container()

    def status(self) -> dict[str, Any]:
        status = self.container.chat.status()
        status["member"] = "ned"
        status["quality_member"] = "dany"
        return status

    def chat(self, content: str, conversation_id: str | None = None) -> dict[str, Any]:
        result = self.container.chat.chat(ChatRequest(content=content, conversation_id=conversation_id))
        report = DanyEvaluator().evaluate(result.message.content)
        if not report.accepted:
            raise RuntimeError(f"Dany rejected the response: {report.issues}")
        payload = result.to_dict()
        payload["quality"] = asdict(report)
        return payload


def main() -> int:
    parser = argparse.ArgumentParser(prog="rachel-cognitive")
    sub = parser.add_subparsers(dest="domain", required=True)
    cognitive = sub.add_parser("cognitive")
    cognitive_sub = cognitive.add_subparsers(dest="action", required=True)
    cognitive_sub.add_parser("status")
    chat = cognitive_sub.add_parser("chat")
    chat.add_argument("content")
    chat.add_argument("--conversation-id")
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("content")
    args = parser.parse_args()
    if args.domain == "cognitive" and args.action == "status":
        print(json.dumps(NedCognitiveBridge().status(), ensure_ascii=False, indent=2))
        return 0
    if args.domain == "cognitive" and args.action == "chat":
        try:
            payload = NedCognitiveBridge().chat(args.content, args.conversation_id)
        except Exception as error:
            print(f"{type(error).__name__}: {error}", file=sys.stderr)
            return 2
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if args.domain == "evaluate":
        report = DanyEvaluator().evaluate(args.content)
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
        return 0 if report.accepted else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
