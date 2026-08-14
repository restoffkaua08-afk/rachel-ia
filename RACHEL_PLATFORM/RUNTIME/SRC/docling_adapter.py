from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


class AdapterError(RuntimeError):
    pass


SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".html",
    ".htm",
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".tif",
    ".bmp",
    ".webp",
}


def status() -> dict[str, Any]:
    try:
        import docling
        from docling.document_converter import DocumentConverter

        version = getattr(docling, "__version__", "unknown")
        available = DocumentConverter is not None
    except Exception as error:
        return {
            "available": False,
            "engine": "docling",
            "version": None,
            "error": f"{type(error).__name__}: {error}",
            "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
        }

    return {
        "available": available,
        "engine": "docling",
        "version": version,
        "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
        "multimodal_documents": True,
        "ocr_capable": True,
        "tables": True,
        "document_structure": True,
    }


def extract(path: Path, maximum_characters: int) -> dict[str, Any]:
    resolved = path.expanduser().resolve()

    if not resolved.exists():
        raise FileNotFoundError(resolved)
    if not resolved.is_file():
        raise AdapterError("Path must reference a file")
    if resolved.suffix.casefold() not in SUPPORTED_EXTENSIONS:
        raise AdapterError(
            f"Unsupported extension: {resolved.suffix.casefold()}"
        )

    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    conversion = converter.convert(str(resolved))
    markdown = conversion.document.export_to_markdown().strip()

    if not markdown:
        raise AdapterError("Docling extracted no textual content")
    if len(markdown) > maximum_characters:
        raise AdapterError(
            "Extracted document exceeds configured character limit"
        )

    raw = resolved.read_bytes()

    return {
        "content": markdown,
        "metadata": {
            "path": str(resolved),
            "name": resolved.name,
            "extension": resolved.suffix.casefold(),
            "size_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "characters": len(markdown),
            "lines": markdown.count("\n") + 1,
            "engine": "docling",
            "structure_preserved": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="rachel-docling-adapter")
    sub = parser.add_subparsers(dest="action", required=True)

    sub.add_parser("status")

    extract_parser = sub.add_parser("extract")
    extract_parser.add_argument("path")
    extract_parser.add_argument(
        "--maximum-characters",
        type=int,
        default=2_000_000,
    )

    args = parser.parse_args()

    try:
        if args.action == "status":
            payload = status()
            code = 0 if payload["available"] else 2
        else:
            payload = extract(
                Path(args.path),
                args.maximum_characters,
            )
            code = 0
    except Exception as error:
        payload = {
            "available": False,
            "error": f"{type(error).__name__}: {error}",
        }
        code = 2

    stream = sys.stdout if code == 0 else sys.stderr
    print(
        json.dumps(payload, ensure_ascii=False, indent=2),
        file=stream,
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
