import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))

import voice_diagnostics
from voice_diagnostics import percentile, recommend_threshold


class VoiceDiagnosticsTests(unittest.TestCase):
    def test_percentile_is_interpolated(self):
        self.assertAlmostEqual(percentile([1, 2, 3, 4, 5], 0.5), 3.0)

    def test_threshold_is_above_ambient_noise(self):
        result = recommend_threshold([0.003, 0.004, 0.004, 0.005, 0.006, 0.005])
        self.assertGreater(result["recommended_capture_threshold"], result["p95_rms"])
        self.assertGreater(result["recommended_barge_threshold"], result["recommended_capture_threshold"])

    def test_too_few_samples_are_rejected(self):
        with self.assertRaises(ValueError):
            recommend_threshold([0.1, 0.2])

    def test_session_summary_ignores_invalid_files(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = voice_diagnostics.SESSION_DIR
            try:
                voice_diagnostics.SESSION_DIR = Path(directory)
                (Path(directory) / "voice_valid.json").write_text(json.dumps({"session_id": "one", "state": "stopped", "turn_count": 2, "interruptions": 1}), encoding="utf-8")
                (Path(directory) / "voice_broken.json").write_text("not-json", encoding="utf-8")
                result = voice_diagnostics.session_summary()
                self.assertEqual(result["stored_sessions"], 1)
                self.assertEqual(result["total_turns"], 2)
                self.assertEqual(result["total_interruptions"], 1)
            finally:
                voice_diagnostics.SESSION_DIR = previous


if __name__ == "__main__": unittest.main()
