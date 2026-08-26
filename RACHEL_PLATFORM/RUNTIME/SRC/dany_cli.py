from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from typing import Any

from dany_professional import DanyProfessional, EvalContext


def _json_object(value: str | None) -> dict[str, Any] | None:
    if value is None:
        return None
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise argparse.ArgumentTypeError("JSON deve ser um objeto")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(prog="rachel-dany")
    parser.add_argument("content")
    parser.add_argument("--request", default="")
    parser.add_argument("--tool-result-json")
    parser.add_argument("--evidence-json")
    parser.add_argument("--research", action="store_true")
    parser.add_argument("--citation", action="append", default=[])
    parser.add_argument("--primary-source-count", type=int)
    parser.add_argument("--factuality-verified", choices=("true", "false", "unknown"), default="unknown")
    args = parser.parse_args()

    factuality = None
    if args.factuality_verified == "true":
        factuality = True
    elif args.factuality_verified == "false":
        factuality = False

    try:
        tool_result = _json_object(args.tool_result_json)
        evidence = _json_object(args.evidence_json)
    except (json.JSONDecodeError, argparse.ArgumentTypeError) as error:
        parser.error(str(error))

    report = DanyProfessional().evaluate(
        args.content,
        EvalContext(
            request=args.request,
            tool_result=tool_result,
            evidence=evidence,
            citations=tuple(args.citation),
            research=args.research,
            primary_source_count=args.primary_source_count,
            factuality_verified=factuality,
        ),
    )
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    return 0 if report.accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
