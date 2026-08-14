import json
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(
    0,
    str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"),
)

from docling_adapter import SUPPORTED_EXTENSIONS, status


class DoclingAdapterTests(unittest.TestCase):
    def test_engine_registry_is_portable(self):
        config = json.loads(
            (
                ROOT
                / "RACHEL_PLATFORM"
                / "CONFIG"
                / "document.engines.json"
            ).read_text(encoding="utf-8-sig")
        )
        engine = config["engines"]["docling"]
        self.assertTrue(engine["enabled"])
        self.assertEqual(engine["runtime"], "isolated")
        self.assertFalse(Path(engine["python"]).is_absolute())
        self.assertFalse(Path(engine["adapter"]).is_absolute())

    def test_expected_document_types_are_supported(self):
        expected = {".pdf", ".docx", ".pptx", ".xlsx", ".png"}
        self.assertTrue(expected <= SUPPORTED_EXTENSIONS)

    def test_status_has_stable_contract(self):
        result = status()
        self.assertIn("available", result)
        self.assertEqual(result["engine"], "docling")
        self.assertIn("supported_extensions", result)


if __name__ == "__main__":
    unittest.main()
