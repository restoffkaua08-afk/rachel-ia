import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))

from research_evidence import build_evidence_claims, detect_conflicts


class ResearchEvidenceTests(unittest.TestCase):
    def test_claim_id_is_stable_and_url_derived(self):
        url = "https://docs.python.org/3/"
        source = {
            "url": url,
            "title": "Python Documentation",
            "authority": "primary",
            "content": (
                "The documented version is 3.13 and this sentence contains "
                "enough material to become an auditable evidence claim."
            ),
        }
        claims = build_evidence_claims(source)
        self.assertEqual(len(claims), 1)
        expected = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        self.assertEqual(claims[0]["id"], f"source-{expected}-claim-1")
        self.assertEqual(build_evidence_claims(source)[0]["id"], claims[0]["id"])

    def test_natural_language_version_conflict_is_detected(self):
        conflicts = detect_conflicts(
            [
                {
                    "url": "https://docs.example/",
                    "title": "Official docs",
                    "content": "The documented version is 3.13 for this release.",
                },
                {
                    "url": "https://release.example/",
                    "title": "Release page",
                    "content": "The documented version is 3.14 for this release.",
                },
            ]
        )
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["marker"], "version")
        self.assertEqual(conflicts[0]["values"], ("3.13", "3.14"))


if __name__ == "__main__":
    unittest.main()
