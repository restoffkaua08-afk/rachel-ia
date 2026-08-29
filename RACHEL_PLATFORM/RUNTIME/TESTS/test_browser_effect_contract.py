from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from browser_effect_contract import (
    BrowserEffectContractError,
    approval_bound_arguments,
    normalize_effect_target,
)
from security_runtime import arguments_hash


class BrowserEffectContractTests(unittest.TestCase):
    def base(self) -> dict:
        return {
            "session_id": "browser-session-1",
            "page_id": "browser-page-1",
            "selector": "button#save",
            "expected_text": "Salvo",
        }

    def test_click_requires_bound_session_page_selector_and_postcondition(self) -> None:
        target = normalize_effect_target("click", self.base())
        self.assertEqual("browser-session-1", target.session_id)
        self.assertEqual("browser-page-1", target.page_id)
        self.assertEqual("button#save", target.selector)
        self.assertEqual("Salvo", target.expected_text)

    def test_missing_postcondition_is_rejected(self) -> None:
        payload = self.base()
        payload.pop("expected_text")
        with self.assertRaises(BrowserEffectContractError):
            normalize_effect_target("click", payload)

    def test_control_character_in_selector_is_rejected(self) -> None:
        payload = self.base()
        payload["selector"] = "button\nscript"
        with self.assertRaises(BrowserEffectContractError):
            normalize_effect_target("click", payload)

    def test_form_fields_are_part_of_approval_payload(self) -> None:
        payload = self.base()
        payload["fields"] = {"email": "user@example.com", "name": "Rachel"}
        bound = approval_bound_arguments("form", payload)
        self.assertEqual(payload["fields"], bound["fields"])

    def test_upload_binds_file_path(self) -> None:
        payload = self.base()
        payload["file_path"] = "workspace/report.pdf"
        bound = approval_bound_arguments("upload", payload)
        self.assertEqual("workspace/report.pdf", bound["file_path"])

    def test_changing_target_changes_cyber_arguments_hash(self) -> None:
        first = approval_bound_arguments("click", self.base())
        changed = self.base()
        changed["selector"] = "button#delete"
        second = approval_bound_arguments("click", changed)
        self.assertNotEqual(arguments_hash(first), arguments_hash(second))

    def test_changing_page_changes_cyber_arguments_hash(self) -> None:
        first = approval_bound_arguments("click", self.base())
        changed = self.base()
        changed["page_id"] = "browser-page-2"
        second = approval_bound_arguments("click", changed)
        self.assertNotEqual(arguments_hash(first), arguments_hash(second))


if __name__ == "__main__":
    unittest.main()
