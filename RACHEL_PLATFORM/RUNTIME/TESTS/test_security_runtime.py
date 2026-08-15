import json
import tempfile
import time
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))
from security_runtime import ApprovalError, ApprovalStore, arguments_hash


class ApprovalTests(unittest.TestCase):
    def store(self):
        temp = tempfile.TemporaryDirectory()
        policy = Path(temp.name) / "policy.json"
        policy.write_text(json.dumps({"default_ttl_seconds": 300, "maximum_ttl_seconds": 1800}), encoding="utf-8")
        return temp, ApprovalStore(Path(temp.name) / "approvals.db", policy)

    def test_arguments_hash_is_deterministic(self):
        self.assertEqual(arguments_hash({"b": 2, "a": 1}), arguments_hash({"a": 1, "b": 2}))

    def test_approval_is_single_use(self):
        temp, store = self.store()
        try:
            request = store.request("arya.run", "execute", "medium", {"command": "python"}, "test")
            store.decide(request["id"], True)
            result = store.consume(request["id"], "arya.run", "execute", {"command": "python"})
            self.assertEqual(result["status"], "consumed")
            with self.assertRaises(ApprovalError): store.consume(request["id"], "arya.run", "execute", {"command": "python"})
        finally: temp.cleanup()

    def test_arguments_cannot_change(self):
        temp, store = self.store()
        try:
            request = store.request("arya.run", "execute", "medium", {"command": "python"}, "test")
            store.decide(request["id"], True)
            with self.assertRaises(ApprovalError): store.consume(request["id"], "arya.run", "execute", {"command": "powershell"})
        finally: temp.cleanup()

    def test_denied_approval_cannot_be_used(self):
        temp, store = self.store()
        try:
            request = store.request("bran.remember", "write", "medium", {"content": "x"}, "test")
            store.decide(request["id"], False)
            with self.assertRaises(ApprovalError): store.consume(request["id"], "bran.remember", "write", {"content": "x"})
        finally: temp.cleanup()

    def test_request_does_not_store_argument_values(self):
        temp, store = self.store()
        try:
            secret = "private-value"
            store.request("tool", "write", "medium", {"content": secret}, "test")
            raw = Path(temp.name, "approvals.db").read_bytes()
            self.assertNotIn(secret.encode(), raw)
        finally: temp.cleanup()


if __name__ == "__main__": unittest.main()
