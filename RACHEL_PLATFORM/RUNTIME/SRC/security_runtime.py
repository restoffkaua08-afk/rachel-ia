from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "RACHEL_PLATFORM" / "CONFIG"
STATE = ROOT / "RACHEL_PLATFORM" / "STATE"
DEFAULT_DATABASE = STATE / "cyber-approvals.db"
DEFAULT_POLICY = CONFIG / "approval.policy.json"


class ApprovalError(RuntimeError):
    pass


def now_ms() -> int:
    return int(time.time() * 1000)


def canonical_arguments(arguments: dict[str, Any]) -> str:
    if not isinstance(arguments, dict):
        raise ApprovalError("Approval arguments must be an object")
    return json.dumps(arguments, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def arguments_hash(arguments: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_arguments(arguments).encode("utf-8")).hexdigest()


class ApprovalStore:
    def __init__(self, path: Path | None = None, policy_path: Path | None = None) -> None:
        self.path = Path(path or DEFAULT_DATABASE)
        self.policy_path = Path(policy_path or DEFAULT_POLICY)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.policy = json.loads(self.policy_path.read_text(encoding="utf-8"))
        connection = sqlite3.connect(self.path)
        try:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    tool TEXT NOT NULL,
                    effect TEXT NOT NULL,
                    risk TEXT NOT NULL,
                    arguments_hash TEXT NOT NULL,
                    arguments_summary TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    requested_at_ms INTEGER NOT NULL,
                    expires_at_ms INTEGER NOT NULL,
                    decided_at_ms INTEGER,
                    consumed_at_ms INTEGER
                )
            """)
            connection.commit()
        finally:
            connection.close()

    def _ttl(self, ttl_seconds: int | None) -> int:
        default = int(self.policy.get("default_ttl_seconds", 300))
        maximum = int(self.policy.get("maximum_ttl_seconds", 1800))
        value = default if ttl_seconds is None else int(ttl_seconds)
        if value < 15 or value > maximum:
            raise ApprovalError(f"Approval TTL must be between 15 and {maximum} seconds")
        return value

    @staticmethod
    def _summary(arguments: dict[str, Any]) -> str:
        summary = {key: {"type": type(value).__name__, "length": len(value) if hasattr(value, "__len__") else None} for key, value in arguments.items()}
        return json.dumps(summary, ensure_ascii=False, sort_keys=True)

    def request(self, tool: str, effect: str, risk: str, arguments: dict[str, Any], reason: str, ttl_seconds: int | None = None) -> dict[str, Any]:
        created = now_ms()
        approval = {
            "id": "approval_" + uuid.uuid4().hex,
            "tool": tool,
            "effect": effect,
            "risk": risk,
            "arguments_hash": arguments_hash(arguments),
            "arguments_summary": self._summary(arguments),
            "status": "pending",
            "reason": reason,
            "requested_at_ms": created,
            "expires_at_ms": created + self._ttl(ttl_seconds) * 1000,
            "decided_at_ms": None,
            "consumed_at_ms": None,
        }
        connection = sqlite3.connect(self.path)
        try:
            connection.execute("INSERT INTO approvals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", tuple(approval.values()))
            connection.commit()
        finally:
            connection.close()
        return self.public(approval)

    def _row(self, approval_id: str) -> dict[str, Any]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        finally:
            connection.close()
        if row is None:
            raise ApprovalError("Approval not found")
        return dict(row)

    def decide(self, approval_id: str, allow: bool) -> dict[str, Any]:
        current = self._row(approval_id)
        if current["status"] != "pending":
            raise ApprovalError(f"Approval is already {current['status']}")
        timestamp = now_ms()
        status = "expired" if timestamp > current["expires_at_ms"] else ("approved" if allow else "denied")
        connection = sqlite3.connect(self.path)
        try:
            connection.execute("UPDATE approvals SET status = ?, decided_at_ms = ? WHERE id = ? AND status = 'pending'", (status, timestamp, approval_id))
            connection.commit()
        finally:
            connection.close()
        result = self._row(approval_id)
        if status == "expired":
            raise ApprovalError("Approval expired before the decision")
        return self.public(result)

    def consume(self, approval_id: str, tool: str, effect: str, arguments: dict[str, Any]) -> dict[str, Any]:
        timestamp = now_ms()
        expected_hash = arguments_hash(arguments)
        connection = sqlite3.connect(self.path, timeout=10, isolation_level="IMMEDIATE")
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
            if row is None:
                raise ApprovalError("Approval not found")
            current = dict(row)
            if timestamp > current["expires_at_ms"]:
                connection.execute("UPDATE approvals SET status = 'expired' WHERE id = ? AND status IN ('pending','approved')", (approval_id,))
                connection.commit()
                raise ApprovalError("Approval expired")
            if current["status"] != "approved":
                raise ApprovalError(f"Approval cannot be used while {current['status']}")
            if current["tool"] != tool or current["effect"] != effect:
                raise ApprovalError("Approval scope does not match this tool")
            if current["arguments_hash"] != expected_hash:
                raise ApprovalError("Approval arguments do not match")
            updated = connection.execute("UPDATE approvals SET status = 'consumed', consumed_at_ms = ? WHERE id = ? AND status = 'approved'", (timestamp, approval_id))
            if updated.rowcount != 1:
                raise ApprovalError("Approval was already consumed")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return self.public(self._row(approval_id))

    def list(self, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            if status:
                rows = connection.execute("SELECT * FROM approvals WHERE status = ? ORDER BY requested_at_ms DESC LIMIT ?", (status, max(1, min(limit, 200)))).fetchall()
            else:
                rows = connection.execute("SELECT * FROM approvals ORDER BY requested_at_ms DESC LIMIT ?", (max(1, min(limit, 200)),)).fetchall()
        finally:
            connection.close()
        return [self.public(dict(row)) for row in rows]

    @staticmethod
    def public(record: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in record.items() if key not in {"arguments_hash"}}


def main() -> int:
    parser = argparse.ArgumentParser(prog="rachel-approval")
    sub = parser.add_subparsers(dest="action", required=True)
    listing = sub.add_parser("list"); listing.add_argument("--status"); listing.add_argument("--limit", type=int, default=50)
    approve = sub.add_parser("approve"); approve.add_argument("approval_id")
    deny = sub.add_parser("deny"); deny.add_argument("approval_id")
    show = sub.add_parser("show"); show.add_argument("approval_id")
    args = parser.parse_args()
    store = ApprovalStore()
    try:
        if args.action == "list": result = store.list(args.status, args.limit)
        elif args.action == "approve": result = store.decide(args.approval_id, True)
        elif args.action == "deny": result = store.decide(args.approval_id, False)
        else: result = store.public(store._row(args.approval_id))
    except (ApprovalError, OSError, ValueError) as error:
        print(json.dumps({"state": "rejected", "error": str(error)}, ensure_ascii=False, indent=2))
        return 3
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__": raise SystemExit(main())
