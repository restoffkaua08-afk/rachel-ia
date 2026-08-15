from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from runtime_paths import CONFIG, PLATFORM, ROOT, STATE


class MemoryError(ValueError):
    pass


@dataclass(frozen=True)
class MemoryProposal:
    content: str
    category: str
    source: str
    confidence: float
    importance: int
    sensitive: bool
    reason: str


class MemoryGovernance:
    SECRET_PATTERNS = (
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.I),
        re.compile(r"\b(?:ghp|github_pat|sk)-?[A-Za-z0-9_\-]{20,}\b", re.I),
        re.compile(r"\b(?:password|senha|secret|token|api[_ -]?key)\s*[:=]\s*\S+", re.I),
        re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b"),
    )
    CATEGORY_TERMS = {
        "preference": ("prefiro", "gosto", "quero sempre", "não gosto", "nao gosto"),
        "decision": ("decidi", "decisão", "decisao", "escolhi", "vamos usar"),
        "correction": ("correção", "correcao", "estava errado", "o correto"),
        "project": ("projeto", "repositório", "repositorio", "sistema", "aplicação", "aplicacao"),
        "instruction": ("sempre faça", "sempre faca", "nunca faça", "nunca faca", "regra"),
    }

    def __init__(self) -> None:
        self.policy = json.loads((CONFIG / "memory.policy.json").read_text(encoding="utf-8-sig"))

    def is_sensitive(self, content: str) -> bool:
        return any(pattern.search(content) for pattern in self.SECRET_PATTERNS)

    def classify(self, content: str) -> str:
        text = content.casefold()
        for category, terms in self.CATEGORY_TERMS.items():
            if any(term in text for term in terms):
                return category
        return "fact" if len(content.split()) <= 40 else "note"

    def propose(
        self, content: str, source: str = "user", category: str | None = None,
        confidence: float = 1.0, importance: int = 3,
    ) -> MemoryProposal:
        normalized = " ".join(content.strip().split())
        if not normalized:
            raise MemoryError("Memory content cannot be empty")
        if len(normalized) > int(self.policy["maximum_characters"]):
            raise MemoryError("Memory exceeds the configured size limit")
        sensitive = self.is_sensitive(normalized)
        selected = category or self.classify(normalized)
        if selected not in self.policy["allowed_categories"]:
            raise MemoryError(f"Unsupported memory category: {selected}")
        if isinstance(confidence, bool) or not 0.0 <= float(confidence) <= 1.0:
            raise MemoryError("Confidence must be between 0 and 1")
        if isinstance(importance, bool) or not 1 <= int(importance) <= 5:
            raise MemoryError("Importance must be between 1 and 5")
        reason = "Sensitive content is blocked." if sensitive else "Candidate memory requires explicit approval."
        return MemoryProposal(normalized, selected, source[:200], float(confidence), int(importance), sensitive, reason)


@contextmanager
def sqlite_connection(path: Path):
    connection = sqlite3.connect(path)

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


class CognitiveMemory:
    def __init__(self, path: Path | None = None) -> None:
        STATE.mkdir(parents=True, exist_ok=True)
        self.path = path or STATE / "bran-cognitive.db"
        self.governance = MemoryGovernance()
        with sqlite_connection(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cognitive_memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    normalized_hash TEXT NOT NULL UNIQUE,
                    category TEXT NOT NULL,
                    source TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    importance INTEGER NOT NULL,
                    consent TEXT NOT NULL,
                    status TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at_ms INTEGER NOT NULL,
                    updated_at_ms INTEGER NOT NULL,
                    last_accessed_ms INTEGER,
                    access_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_cognitive_status ON cognitive_memories(status)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_cognitive_category ON cognitive_memories(category)")
            connection.commit()

    def propose(self, content: str, **kwargs: Any) -> dict[str, Any]:
        return asdict(self.governance.propose(content, **kwargs))

    def remember(self, content: str, approved: bool = False, metadata: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        proposal = self.governance.propose(content, **kwargs)
        if proposal.sensitive:
            return {"state": "denied", "reason": proposal.reason, "proposal": asdict(proposal)}
        if not approved:
            return {"state": "approval_required", "reason": proposal.reason, "proposal": asdict(proposal)}
        now = int(time.time() * 1000)
        digest = hashlib.sha256(proposal.content.casefold().encode("utf-8")).hexdigest()
        memory_id = f"mem_{digest[:24]}"
        with sqlite_connection(self.path) as connection:
            existing = connection.execute("SELECT id, created_at_ms, access_count FROM cognitive_memories WHERE normalized_hash = ?", (digest,)).fetchone()
            created = int(existing[1]) if existing else now
            accesses = int(existing[2]) if existing else 0
            connection.execute(
                """INSERT OR REPLACE INTO cognitive_memories
                (id, content, normalized_hash, category, source, confidence, importance, consent, status, metadata,
                 created_at_ms, updated_at_ms, last_accessed_ms, access_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (memory_id, proposal.content, digest, proposal.category, proposal.source, proposal.confidence,
                 proposal.importance, "explicit", "active", json.dumps(metadata or {}, ensure_ascii=False),
                 created, now, None, accesses),
            )
            connection.commit()
        return {"state": "stored", "memory": self.get(memory_id), "duplicate_updated": existing is not None}

    def get(self, memory_id: str) -> dict[str, Any] | None:
        with sqlite_connection(self.path) as connection:
            row = connection.execute(
                "SELECT id, content, category, source, confidence, importance, consent, status, metadata, created_at_ms, updated_at_ms, last_accessed_ms, access_count FROM cognitive_memories WHERE id = ?",
                (memory_id,),
            ).fetchone()
        if not row:
            return None
        keys = ("id", "content", "category", "source", "confidence", "importance", "consent", "status", "metadata", "created_at_ms", "updated_at_ms", "last_accessed_ms", "access_count")
        result = dict(zip(keys, row)); result["metadata"] = json.loads(result["metadata"])
        return result

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        terms = {term for term in re.findall(r"[\wÀ-ÿ]+", query.casefold()) if len(term) >= 2}
        with sqlite_connection(self.path) as connection:
            rows = connection.execute(
                "SELECT id, content, category, source, confidence, importance, consent, status, metadata, created_at_ms, updated_at_ms, last_accessed_ms, access_count FROM cognitive_memories WHERE status = 'active'"
            ).fetchall()
            keys = ("id", "content", "category", "source", "confidence", "importance", "consent", "status", "metadata", "created_at_ms", "updated_at_ms", "last_accessed_ms", "access_count")
            scored = []
            for row in rows:
                item = dict(zip(keys, row)); item["metadata"] = json.loads(item["metadata"])
                haystack = item["content"].casefold()
                matches = sum(1 for term in terms if term in haystack)
                if matches:
                    item["relevance"] = round(matches + item["importance"] * 0.15 + item["confidence"] * 0.25, 3)
                    scored.append(item)
            scored.sort(key=lambda item: (item["relevance"], item["updated_at_ms"]), reverse=True)
            selected = scored[:max(1, min(int(limit), 100))]
            now = int(time.time() * 1000)
            for item in selected:
                connection.execute("UPDATE cognitive_memories SET last_accessed_ms = ?, access_count = access_count + 1 WHERE id = ?", (now, item["id"]))
            connection.commit()
        return selected

    def status(self) -> dict[str, Any]:
        with sqlite_connection(self.path) as connection:
            total = int(connection.execute("SELECT COUNT(*) FROM cognitive_memories").fetchone()[0])
            active = int(connection.execute("SELECT COUNT(*) FROM cognitive_memories WHERE status = 'active'").fetchone()[0])
        return {"available": True, "schema_version": "2.0", "total": total, "active": active, "explicit_consent": True, "sensitive_data": "deny"}


def main() -> int:
    parser = argparse.ArgumentParser(prog="bran-cognitive")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("status")
    proposal = sub.add_parser("propose"); proposal.add_argument("content")
    remember = sub.add_parser("remember"); remember.add_argument("content"); remember.add_argument("--approved", action="store_true")
    search = sub.add_parser("search"); search.add_argument("query"); search.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(); memory = CognitiveMemory()
    try:
        if args.action == "status": result = memory.status()
        elif args.action == "propose": result = memory.propose(args.content)
        elif args.action == "remember": result = memory.remember(args.content, approved=args.approved)
        else: result = memory.search(args.query, args.limit)
    except (OSError, ValueError, MemoryError) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr); return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if isinstance(result, dict) and result.get("state") == "approval_required": return 3
    if isinstance(result, dict) and result.get("state") == "denied": return 4
    return 0


if __name__ == "__main__": raise SystemExit(main())
