import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(
    0,
    str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"),
)

from document_runtime import (
    DocumentError,
    DocumentExtractor,
    DocumentPolicy,
    chunk_text,
    normalize_text,
)


class DocumentRuntimeTests(unittest.TestCase):
    def test_normalizes_line_endings_and_nulls(self):
        result = normalize_text("Linha 1\r\nLinha 2\x00\r\n")
        self.assertEqual(result, "Linha 1\nLinha 2")

    def test_extracts_text_with_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "document.md"
            path.write_text(
                "# Rachel\n\nDocumento técnico.",
                encoding="utf-8",
            )
            result = DocumentExtractor().extract(path)
            self.assertIn("Documento técnico", result.content)
            self.assertEqual(result.metadata["extension"], ".md")
            self.assertEqual(result.metadata["engine"], "stdlib-text")
            self.assertEqual(len(result.metadata["sha256"]), 64)
            self.assertGreaterEqual(len(result.chunks), 1)

    def test_extracts_normalized_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            path.write_text(
                json.dumps(
                    {"nome": "Rachel", "ativa": True},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            result = DocumentExtractor().extract(path)
            self.assertIn('"nome": "Rachel"', result.content)
            self.assertEqual(result.metadata["engine"], "stdlib-json")

    def test_extracts_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.csv"
            path.write_text(
                "nome,status\nRachel,ativa\n",
                encoding="utf-8",
            )
            result = DocumentExtractor().extract(path)
            self.assertIn("Rachel | ativa", result.content)
            self.assertEqual(result.metadata["engine"], "stdlib-csv")

    def test_chunks_preserve_content_regions(self):
        content = " ".join(f"palavra-{index}" for index in range(400))
        chunks = chunk_text(content, size=500, overlap=50)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[0].index, 0)
        self.assertTrue(all(chunk.content for chunk in chunks))
        self.assertTrue(
            all(len(chunk.sha256) == 64 for chunk in chunks)
        )

    def test_policy_accepts_docling_extensions(self):
        policy = DocumentPolicy()
        self.assertIn(".pdf", policy.allowed_extensions)
        self.assertIn(".docx", policy.allowed_extensions)
        self.assertIn(".pptx", policy.allowed_extensions)
        self.assertIn(".xlsx", policy.allowed_extensions)

    def test_rejects_unsupported_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "program.exe"
            path.write_bytes(b"not-an-executable")
            with self.assertRaises(DocumentError):
                DocumentExtractor().extract(path)

    def test_rejects_file_above_policy_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            policy_path = base / "policy.json"
            policy_path.write_text(
                json.dumps(
                    {
                        "maximum_file_bytes": 4,
                        "maximum_extracted_characters": 1000,
                        "chunk_characters": 200,
                        "chunk_overlap_characters": 20,
                        "allowed_extensions": [".txt"],
                        "structured_extensions": [],
                    }
                ),
                encoding="utf-8",
            )
            source = base / "large.txt"
            source.write_text("conteúdo grande", encoding="utf-8")

            with self.assertRaises(DocumentError):
                DocumentExtractor(
                    DocumentPolicy(policy_path)
                ).extract(source)


if __name__ == "__main__":
    unittest.main()
