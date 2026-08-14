from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[3]
PLATFORM = ROOT / "RACHEL_PLATFORM"
CONFIG = PLATFORM / "CONFIG"
MEMBERS = PLATFORM / "MEMBROS"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def member_registry() -> list[dict[str, Any]]:
    return list(load_json(CONFIG / "members.registry.json").get("membros", []))


def organ_registry() -> list[dict[str, Any]]:
    return list(load_json(CONFIG / "organs.registry.json").get("orgaos", []))


def find_member(member_id: str) -> dict[str, Any]:
    wanted = member_id.casefold()
    for member in member_registry():
        if str(member.get("id", "")).casefold() == wanted or str(member.get("nome", "")).casefold() == wanted:
            return member
    raise SystemExit(f"Membro nao encontrado: {member_id}")


def team() -> int:
    for member in member_registry():
        print(f"{member['nome']:<8} | {member['cargo']} | {member['pasta']}")
    return 0


def member_status(member_id: str) -> int:
    member = find_member(member_id)
    folder = MEMBERS / str(member["pasta"])
    organ_root = folder / "ORGAOS"
    organs = sorted(p.name for p in organ_root.iterdir() if p.is_dir()) if organ_root.exists() else []
    linked = []
    missing = []
    for organ in organs:
        source = organ_root / organ / "fonte"
        (linked if source.exists() else missing).append(organ)
    payload = {
        "id": member["id"],
        "nome": member["nome"],
        "cargo": member["cargo"],
        "responsabilidade": member["responsabilidade"],
        "folder_exists": folder.exists(),
        "organs": linked,
        "missing_organs": missing,
        "status": "available" if folder.exists() and not missing else "degraded",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "available" else 1


def member_docs(member_id: str) -> int:
    member = find_member(member_id)
    readme = MEMBERS / str(member["pasta"]) / "README.md"
    if not readme.exists():
        raise SystemExit(f"Documentacao ausente: {readme}")
    print(readme.read_text(encoding="utf-8-sig"))
    return 0


def organ_list() -> int:
    organs = organ_registry()
    for organ in organs:
        organ_id = str(organ.get("alias") or organ.get("id") or organ.get("nome_original") or "unknown")
        print(organ_id)
    print(f"Total: {len(organs)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="rachel")
    sub = parser.add_subparsers(dest="domain", required=True)
    sub.add_parser("team")
    member = sub.add_parser("member")
    member_sub = member.add_subparsers(dest="action", required=True)
    for action in ("status", "docs"):
        command = member_sub.add_parser(action)
        command.add_argument("member_id")
    organ = sub.add_parser("organ")
    organ_sub = organ.add_subparsers(dest="action", required=True)
    organ_sub.add_parser("list")
    args = parser.parse_args()
    if args.domain == "team":
        return team()
    if args.domain == "member" and args.action == "status":
        return member_status(args.member_id)
    if args.domain == "member" and args.action == "docs":
        return member_docs(args.member_id)
    if args.domain == "organ" and args.action == "list":
        return organ_list()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
