from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

from security_runtime import ApprovalError, ApprovalStore


RISK_ORDER = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

RISK_LABELS = {
    "low": ("LOW", "Baixo impacto."),
    "medium": ("MEDIUM", "Pode alterar estado ou criar recursos."),
    "high": ("HIGH", "Pode modificar dados, arquivos ou configuracoes relevantes."),
    "critical": ("CRITICAL", "Pode causar impacto amplo ou irreversivel."),
}


def now_ms() -> int:
    return int(time.time() * 1000)


def _argument_fields(summary: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(summary or "{}")
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, dict):
        return []

    fields: list[dict[str, Any]] = []
    for name, metadata in sorted(parsed.items()):
        safe = metadata if isinstance(metadata, dict) else {}
        fields.append(
            {
                "name": str(name),
                "type": safe.get("type"),
                "length": safe.get("length"),
            }
        )
    return fields


def _remaining_seconds(record: dict[str, Any], timestamp_ms: int | None = None) -> int:
    current = now_ms() if timestamp_ms is None else int(timestamp_ms)
    expires = int(record.get("expires_at_ms") or current)
    return max(0, (expires - current + 999) // 1000)


class SecurityPanel:
    def __init__(self, store: ApprovalStore | None = None) -> None:
        self.store = store or ApprovalStore()

    def card(self, record: dict[str, Any], timestamp_ms: int | None = None) -> dict[str, Any]:
        public = self.store.public(record)
        risk = str(public.get("risk") or "unknown").lower()
        label, warning = RISK_LABELS.get(
            risk,
            (risk.upper() if risk else "UNKNOWN", "Risco nao classificado."),
        )
        approval_id = str(public.get("id") or "")
        return {
            "id": approval_id,
            "tool": public.get("tool"),
            "effect": public.get("effect"),
            "risk": risk,
            "risk_label": label,
            "warning": warning,
            "status": public.get("status"),
            "reason": public.get("reason"),
            "argument_fields": _argument_fields(str(public.get("arguments_summary") or "{}")),
            "requested_at_ms": public.get("requested_at_ms"),
            "expires_at_ms": public.get("expires_at_ms"),
            "seconds_remaining": _remaining_seconds(public, timestamp_ms),
            "confirmation": {
                "approve": f"APROVAR {approval_id}",
                "deny": f"NEGAR {approval_id}",
            },
        }

    def snapshot(self, status: str | None = "pending", limit: int = 50) -> dict[str, Any]:
        generated = now_ms()
        records = self.store.list(status=status, limit=limit)
        cards = [self.card(record, generated) for record in records]
        cards.sort(
            key=lambda item: (
                RISK_ORDER.get(str(item.get("risk") or "").lower(), 0),
                int(item.get("requested_at_ms") or 0),
            ),
            reverse=True,
        )
        counts: dict[str, int] = {}
        for card in cards:
            risk = str(card.get("risk") or "unknown")
            counts[risk] = counts.get(risk, 0) + 1
        return {
            "state": "ready",
            "generated_at_ms": generated,
            "status_filter": status,
            "total": len(cards),
            "risk_counts": counts,
            "items": cards,
        }

    def show(self, approval_id: str) -> dict[str, Any]:
        return self.card(self.store._row(approval_id))

    def decide(self, approval_id: str, allow: bool) -> dict[str, Any]:
        return self.card(self.store.decide(approval_id, allow))

    @staticmethod
    def render_card(card: dict[str, Any]) -> str:
        fields = card.get("argument_fields") or []
        if fields:
            field_text = ", ".join(
                f"{item['name']}:{item.get('type') or '?'}"
                + (f"[{item['length']}]" if item.get("length") is not None else "")
                for item in fields
            )
        else:
            field_text = "(nenhum)"

        return "\n".join(
            [
                f"[{card.get('risk_label', 'UNKNOWN')}] {card.get('tool')} ({card.get('effect')})",
                f"ID: {card.get('id')}",
                f"Status: {card.get('status')}",
                f"Motivo: {card.get('reason')}",
                f"Campos: {field_text}",
                f"Expira em: {card.get('seconds_remaining')}s",
                f"Atencao: {card.get('warning')}",
            ]
        )

    @classmethod
    def render_snapshot(cls, snapshot: dict[str, Any]) -> str:
        lines = [
            "=== CYBER | PAINEL DE RISCOS ===",
            f"Solicitacoes: {snapshot.get('total', 0)}",
        ]
        counts = snapshot.get("risk_counts") or {}
        if counts:
            ordered = sorted(
                counts.items(),
                key=lambda item: RISK_ORDER.get(item[0], 0),
                reverse=True,
            )
            lines.append("Riscos: " + " | ".join(f"{risk}={count}" for risk, count in ordered))
        else:
            lines.append("Riscos: nenhum")

        items = snapshot.get("items") or []
        if not items:
            lines.append("")
            lines.append("Nenhuma solicitacao encontrada.")
            return "\n".join(lines)

        for card in items:
            lines.extend(["", cls.render_card(card)])
        return "\n".join(lines)


def _confirm(card: dict[str, Any], allow: bool) -> bool:
    expected = card["confirmation"]["approve" if allow else "deny"]
    print(SecurityPanel.render_card(card))
    print("")
    print("Confirmacao obrigatoria.")
    print(f"Digite exatamente: {expected}")
    typed = input("> ").strip()
    return typed == expected


def main() -> int:
    parser = argparse.ArgumentParser(prog="rachel-security")
    sub = parser.add_subparsers(dest="action", required=True)

    listing = sub.add_parser("list")
    listing.add_argument("--status", default="pending")
    listing.add_argument("--all", action="store_true")
    listing.add_argument("--limit", type=int, default=50)
    listing.add_argument("--json", action="store_true")

    show = sub.add_parser("show")
    show.add_argument("approval_id")
    show.add_argument("--json", action="store_true")

    approve = sub.add_parser("approve")
    approve.add_argument("approval_id")
    approve.add_argument("--yes", action="store_true")
    approve.add_argument("--json", action="store_true")

    deny = sub.add_parser("deny")
    deny.add_argument("approval_id")
    deny.add_argument("--yes", action="store_true")
    deny.add_argument("--json", action="store_true")

    args = parser.parse_args()
    panel = SecurityPanel()

    try:
        if args.action == "list":
            status = None if args.all else args.status
            result = panel.snapshot(status=status, limit=args.limit)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(panel.render_snapshot(result))
            return 0

        if args.action == "show":
            result = panel.show(args.approval_id)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(panel.render_card(result))
            return 0

        allow = args.action == "approve"
        card = panel.show(args.approval_id)
        if card.get("status") != "pending":
            raise ApprovalError(f"Approval is already {card.get('status')}")

        if not args.yes and not _confirm(card, allow):
            print(json.dumps({"state": "cancelled", "id": args.approval_id}, ensure_ascii=False))
            return 4

        result = panel.decide(args.approval_id, allow)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(panel.render_card(result))
        return 0

    except (ApprovalError, OSError, ValueError) as error:
        print(json.dumps({"state": "rejected", "error": str(error)}, ensure_ascii=False, indent=2))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
