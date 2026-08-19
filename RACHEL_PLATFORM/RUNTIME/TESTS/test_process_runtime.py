from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_CORE" / "src"))
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))

from filesystem_runtime import FilesystemRuntime
from process_runtime import ProcessRuntime, ProcessRuntimeError
from security_runtime import ApprovalStore
from tools_runtime import ToolCoordinator


class ProcessRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.workspace = root / "workspace"
        self.desktop = root / "desktop"
        self.documents = root / "documents"
        self.downloads = root / "downloads"
        for item in (self.workspace, self.desktop, self.documents, self.downloads):
            item.mkdir(parents=True)

        project = self.workspace / "service"
        project.mkdir()
        (project / "__main__.py").write_text(
            "import time\n"
            "print('RACHEL_PROCESS_READY', flush=True)\n"
            "time.sleep(30)\n",
            encoding="utf-8",
        )

        filesystem = FilesystemRuntime(
            scopes={
                "workspace": self.workspace,
                "desktop": self.desktop,
                "documents": self.documents,
                "downloads": self.downloads,
            },
            backup_root=root / "backups",
        )
        approvals = ApprovalStore(root / "approvals.db")
        processes = ProcessRuntime(filesystem, root / "process-logs")
        self.approvals = approvals
        self.processes = processes
        self.tools = ToolCoordinator(
            filesystem=filesystem,
            approvals=approvals,
            processes=processes,
        )

    def tearDown(self) -> None:
        try:
            for item in self.processes.list()["items"]:
                if item["running"]:
                    self.processes.stop(item["process_id"], approved=True)
        finally:
            self.temp.cleanup()

    def approve(self, pending: dict) -> str:
        approval_id = pending["approval"]["id"]
        self.approvals.decide(approval_id, True)
        return approval_id

    def test_process_start_status_logs_and_stop_are_governed(self) -> None:
        start_args = {
            "scope": "workspace",
            "path": "service",
            "profile": "python.module",
        }
        pending = self.tools.invoke("process.start", start_args)
        self.assertEqual("approval_required", pending["state"])
        self.assertEqual("execute", pending["approval"]["effect"])

        started = self.tools.invoke(
            "process.start",
            start_args,
            approval_id=self.approve(pending),
        )
        process_id = started["result"]["process_id"]
        self.assertTrue(started["result"]["owned_by_rachel"])
        self.assertTrue(started["result"]["running"])

        time.sleep(0.1)
        status = self.tools.invoke(
            "process.status",
            {"process_id": process_id},
        )
        self.assertTrue(status["result"]["running"])
        self.assertTrue(status["result"]["owned_by_rachel"])

        logs = self.tools.invoke(
            "process.logs",
            {"process_id": process_id, "maximum_bytes": 20_000},
        )
        self.assertIn("RACHEL_PROCESS_READY", logs["result"]["stdout"])

        stop_args = {"process_id": process_id}
        stop_pending = self.tools.invoke("process.stop", stop_args)
        self.assertEqual("approval_required", stop_pending["state"])
        stopped = self.tools.invoke(
            "process.stop",
            stop_args,
            approval_id=self.approve(stop_pending),
        )
        self.assertTrue(stopped["result"]["verified_stopped"])
        self.assertFalse(stopped["result"]["running"])

    def test_unknown_pid_or_process_id_cannot_be_targeted(self) -> None:
        with self.assertRaises(ProcessRuntimeError):
            self.processes.status("process_not_owned_by_rachel")

    def test_process_list_contains_only_owned_registry(self) -> None:
        result = self.tools.invoke("process.list", {})
        self.assertEqual("completed", result["state"])
        self.assertEqual("rachel-owned-only", result["result"]["scope"])
        self.assertEqual(0, result["result"]["count"])


if __name__ == "__main__":
    unittest.main()
