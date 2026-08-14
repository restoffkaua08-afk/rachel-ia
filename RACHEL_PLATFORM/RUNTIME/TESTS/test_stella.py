import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))
from stella_runtime import load_config, speech_text

class StellaTests(unittest.TestCase):
    def test_profiles_exist(self):
        config = load_config()
        self.assertIn("natural", config["profiles"])
        self.assertIn("tecnica", config["profiles"])
        self.assertIn("objetiva", config["profiles"])
    def test_markdown_is_prepared_for_speech(self):
        result = speech_text("## Titulo **forte** com `codigo` e https://example.com")
        self.assertNotIn("##", result)
        self.assertNotIn("https://", result)
        self.assertIn("codigo", result)
    def test_capture_has_safety_limits(self):
        capture = load_config()["capture"]
        self.assertLessEqual(capture["maximum_utterance_seconds"], 60)

if __name__ == "__main__": unittest.main()
