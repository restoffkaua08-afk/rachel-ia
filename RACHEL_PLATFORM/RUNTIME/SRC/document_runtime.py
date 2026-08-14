from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[3]
PLATFORM = ROOT / "RACHEL_PLATFORM"
CONFIG = PLATFORM / "CONFIG"


class DocumentError(ValueError):
    pass


@dataclass(frozen=True)
class DocumentChunk:
    index: int
    content: str
    start_character: int
    end_character: int
    character_count: int
    sha256: str


@dataclass(frozen=True)
class DocumentResult:
    content: str
    chunks: tuple[DocumentChunk, ...]
    metadata: dict[str, Any]


class DocumentPolicy:
    def __init__(self, path: Path | None = None) -> None:
        policy_path = path or CONFIG / "document.policy.json"
        self.data = json.loads(
            policy_path.read_text(encoding="utf-8-sig")
        )

    @property
    def allowed_extensions(self) -> set[str]:
        return {
            str(item).casefold()
            for item in self.data["allowed_extensions"]
        }

    @property
    def maximum_file_bytes(self) -> int:
        return int(self.data["maximum_file_bytes"])

    @property
    def maximum_extracted_characters(self) -> int:
        return int(self.data["maximum_extracted_characters"])

    @property
    def chunk_characters(self) -> int:
        return int(self.data["chunk_characters"])

    @property
    def chunk_overlap_characters(self) -> int:
        return int(self.data["chunk_overlap_characters"])


def normalize_text(content: str) -> str:
    text = content.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.splitlines())
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def calculate_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def chunk_text(
    content: str,
    size: int,
    overlap: int,
) -> tuple[DocumentChunk, ...]:
    if size < 100:
        raise DocumentError("Chunk size must be at least 100 characters")
    if overlap < 0 or overlap >= size:
        raise DocumentError(
            "Chunk overlap must be non-negative and smaller than size"
        )

    text = content.strip()
    if not text:
        return ()

    chunks: list[DocumentChunk] = []
    start = 0

    while start < len(text):
        expected_end = min(start + size, len(text))
        end = expected_end

        if expected_end < len(text):
            lower_bound = start + max(100, size // 2)
            candidates = [
                text.rfind("\n\n", lower_bound, expected_end),
                text.rfind("\n", lower_bound, expected_end),
                text.rfind(". ", lower_bound, expected_end),
                text.rfind(" ", lower_bound, expected_end),
            ]
            boundary = max(candidates)
            if boundary > start:
                end = boundary + (
                    1 if text[boundary:boundary + 2] != ". " else 1
                )

        chunk_content = text[start:end].strip()

        if chunk_content:
            chunks.append(
                DocumentChunk(
                    index=len(chunks),
                    content=chunk_content,
                    start_character=start,
                    end_character=end,
                    character_count=len(chunk_content),
                    sha256=hashlib.sha256(
                        chunk_content.encode("utf-8")
                    ).hexdigest(),
                )
            )

        if end >= len(text):
            break

        next_start = max(0, end - overlap)
        if next_start <= start:
            next_start = end
        start = next_start

    return tuple(chunks)


class DocumentExtractor:
    def __init__(self, policy: DocumentPolicy | None = None) -> None:
        self.policy = policy or DocumentPolicy()

    def validate(self, path: Path) -> dict[str, Any]:
        resolved = path.expanduser().resolve()

        if not resolved.exists():
            raise FileNotFoundError(resolved)
        if not resolved.is_file():
            raise DocumentError("Document path must reference a file")

        suffix = resolved.suffix.casefold()
        if suffix not in self.policy.allowed_extensions:
            raise DocumentError(
                f"Unsupported document extension: {suffix or '[none]'}"
            )

        size = resolved.stat().st_size
        if size > self.policy.maximum_file_bytes:
            raise DocumentError(
                f"Document exceeds {self.policy.maximum_file_bytes} bytes"
            )

        return {
            "path": str(resolved),
            "name": resolved.name,
            "extension": suffix,
            "size_bytes": size,
            "mime_type": (
                mimetypes.guess_type(resolved.name)[0]
                or "application/octet-stream"
            ),
        }

    @staticmethod
    def _read_text(path: Path) -> str:
        raw = path.read_bytes()

        for encoding in ("utf-8-sig", "utf-8", "cp1252"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue

        return raw.decode("utf-8", errors="replace")

    def _extract_json(self, path: Path) -> str:
        payload = json.loads(self._read_text(path))
        return json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )

    def _extract_csv(self, path: Path) -> str:
        source = self._read_text(path)
        rows = list(csv.reader(source.splitlines()))
        return "\n".join(
            " | ".join(cell.strip() for cell in row)
            for row in rows
        )

    def extract(self, path: Path) -> DocumentResult:
        metadata = self.validate(path)
        resolved = Path(metadata["path"])
        suffix = metadata["extension"]
        raw = resolved.read_bytes()

        if suffix == ".json":
            content = self._extract_json(resolved)
            engine = "stdlib-json"
        elif suffix == ".csv":
            content = self._extract_csv(resolved)
            engine = "stdlib-csv"
        else:
            content = self._read_text(resolved)
            engine = "stdlib-text"

        normalized = normalize_text(content)

        if not normalized:
            raise DocumentError("Document contains no extractable text")

        if len(normalized) > self.policy.maximum_extracted_characters:
            raise DocumentError(
                "Extracted document exceeds the configured character limit"
            )

        chunks = chunk_text(
            normalized,
            self.policy.chunk_characters,
            self.policy.chunk_overlap_characters,
        )

        metadata.update(
            {
                "sha256": calculate_sha256(raw),
                "engine": engine,
                "characters": len(normalized),
                "lines": normalized.count("\n") + 1,
                "chunk_count": len(chunks),
                "normalized": True,
            }
        )

        return DocumentResult(
            content=normalized,
            chunks=chunks,
            metadata=metadata,
        )


def result_summary(result: DocumentResult) -> dict[str, Any]:
    return {
        "metadata": result.metadata,
        "chunks": [
            {
                "index": chunk.index,
                "start_character": chunk.start_character,
                "end_character": chunk.end_character,
                "character_count": chunk.character_count,
                "sha256": chunk.sha256,
            }
            for chunk in result.chunks
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="rachel-document")
    sub = parser.add_subparsers(dest="action", required=True)

    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("path")

    extract_parser = sub.add_parser("extract")
    extract_parser.add_argument("path")
    extract_parser.add_argument(
        "--include-content",
        action="store_true",
    )

    args = parser.parse_args()
    extractor = DocumentExtractor()

    try:
        result = extractor.extract(Path(args.path))
    except (OSError, ValueError, DocumentError) as error:
        print(
            f"{type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return 2

    payload = result_summary(result)

    if args.action == "extract" and args.include_content:
        payload["content"] = result.content

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
