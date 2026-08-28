from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from samwell_dashboard import lightweight_status
from samwell_runtime import SamwellRuntime


class SamwellDashboardTests(unittest.TestCase):
    def test_lightweight_status_does_not_run_deep_audit(self):
        service = SamwellRuntime()
        with patch.object(service, "audit", side_effect=AssertionError("deep audit must not run")):
            status = lightweight_status(service)

        self.assertEqual(status["member"]["id"], "samwell")
        self.assertEqual(status["status_mode"], "lightweight")
        self.assertFalse(status["deep_audit_performed"])
        self.assertGreater(status["dependency_catalog"]["total"], 0)

    def test_lightweight_status_preserves_safety_contract(self):
        status = lightweight_status(SamwellRuntime())
        self.assertTrue(status["requires_cyber_for_mutation"])
        self.assertFalse(status["execution_enabled"])
        self.assertFalse(status["automatic_install"])
        self.assertFalse(status["automatic_update"])
        self.assertFalse(status["automatic_remove"])
        self.assertFalse(status["automatic_repair"])
        self.assertFalse(status["training_execution_enabled"])
        self.assertFalse(status["weights_modified"])


if __name__ == "__main__":
    unittest.main()
