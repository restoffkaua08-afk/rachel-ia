from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

from pathlib import Path


ROOT = Path(
    __file__
).resolve().parents[3]

SRC = (
    ROOT
    / "RACHEL_PLATFORM"
    / "RUNTIME"
    / "SRC"
)

CORE = (
    ROOT
    / "RACHEL_CORE"
    / "src"
)


if str(SRC) not in sys.path:
    sys.path.insert(
        0,
        str(SRC),
    )


class RuntimePathContractTests(
    unittest.TestCase
):

    def test_default_contract_preserves_legacy_layout(
        self,
    ) -> None:
        import runtime_paths

        self.assertEqual(
            runtime_paths.ROOT,
            ROOT,
        )

        self.assertEqual(
            runtime_paths.PLATFORM,
            ROOT / "RACHEL_PLATFORM",
        )

        self.assertEqual(
            runtime_paths.CONFIG,
            (
                ROOT
                / "RACHEL_PLATFORM"
                / "CONFIG"
            ),
        )

        self.assertEqual(
            runtime_paths.STATE,
            (
                ROOT
                / "RACHEL_PLATFORM"
                / "STATE"
            ),
        )

        self.assertEqual(
            runtime_paths.LOGS,
            (
                ROOT
                / "RACHEL_PLATFORM"
                / "LOGS"
            ),
        )

        self.assertEqual(
            runtime_paths.WORKSPACE,
            ROOT / "RACHEL_WORKSPACE",
        )


    def test_portable_contract_isolates_writable_state(
        self,
    ) -> None:
        original_voice = (
            ROOT
            / "RACHEL_PLATFORM"
            / "CONFIG"
            / "voice.profiles.json"
        )

        original_digest = hashlib.sha256(
            original_voice.read_bytes()
        ).hexdigest()


        script = textwrap.dedent(
            r"""
            import json
            import os

            from runtime_paths import (
                CONFIG,
                DATA_ROOT,
                LOGS,
                PORTABLE_MODE,
                ROOT,
                STATE,
                WORKSPACE,
                describe_paths,
            )

            from bran_cognitive import CognitiveMemory
            from cognitive_runtime import NedCognitiveBridge
            from project_workspace import ProjectWorkspace
            from security_runtime import ApprovalStore
            from voice_diagnostics import (
                CONFIG_PATH,
                SESSION_DIR,
            )


            approval = ApprovalStore()
            memory = CognitiveMemory()
            workspace = ProjectWorkspace()

            voice_config = json.loads(
                CONFIG_PATH.read_text(
                    encoding="utf-8"
                )
            )

            voice_config.setdefault(
                "diagnostics",
                {},
            )[
                "portable_contract_test"
            ] = True

            CONFIG_PATH.write_text(
                json.dumps(
                    voice_config,
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            status = (
                NedCognitiveBridge()
                .status()
            )

            print(
                json.dumps(
                    {
                        "paths": describe_paths(),
                        "portable": PORTABLE_MODE,
                        "root": str(ROOT),
                        "data_root": str(DATA_ROOT),
                        "state": str(STATE),
                        "config": str(CONFIG),
                        "logs": str(LOGS),
                        "workspace": str(WORKSPACE),
                        "approval_db": str(
                            approval.path
                        ),
                        "memory_db": str(
                            memory.path
                        ),
                        "project_root": str(
                            workspace.root
                        ),
                        "voice_config": str(
                            CONFIG_PATH
                        ),
                        "voice_sessions": str(
                            SESSION_DIR
                        ),
                        "home": os.getenv(
                            "RACHEL_HOME"
                        ),
                        "member": status.get(
                            "member"
                        ),
                    },
                    ensure_ascii=False,
                )
            )
            """
        )


        with tempfile.TemporaryDirectory() as temporary:
            data_root = Path(
                temporary
            ).resolve()

            state_root = (
                data_root
                / "STATE"
            )

            environment = os.environ.copy()

            environment[
                "RACHEL_RUNTIME_ROOT"
            ] = str(ROOT)

            environment[
                "RACHEL_STATE_ROOT"
            ] = str(state_root)

            environment[
                "RACHEL_MODEL_PROVIDER"
            ] = "mock"

            environment.pop(
                "RACHEL_HOME",
                None,
            )

            current_pythonpath = (
                environment.get(
                    "PYTHONPATH",
                    "",
                )
            )

            entries = [
                str(SRC),
                str(CORE),
            ]

            if current_pythonpath:
                entries.append(
                    current_pythonpath
                )

            environment[
                "PYTHONPATH"
            ] = os.pathsep.join(
                entries
            )


            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    script,
                ],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )


            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    result.stdout
                    + "\n"
                    + result.stderr
                ),
            )


            lines = [
                line.strip()
                for line
                in result.stdout.splitlines()
                if line.strip()
            ]

            self.assertTrue(
                lines,
                msg=result.stderr,
            )

            payload = json.loads(
                lines[-1]
            )


            self.assertTrue(
                payload["portable"]
            )

            self.assertEqual(
                Path(
                    payload["root"]
                ),
                ROOT,
            )

            self.assertEqual(
                Path(
                    payload["state"]
                ),
                state_root,
            )

            self.assertEqual(
                Path(
                    payload["data_root"]
                ),
                data_root,
            )

            self.assertEqual(
                Path(
                    payload["config"]
                ),
                data_root / "CONFIG",
            )

            self.assertEqual(
                Path(
                    payload["logs"]
                ),
                data_root / "LOGS",
            )

            self.assertEqual(
                Path(
                    payload["workspace"]
                ),
                data_root / "WORKSPACE",
            )

            self.assertEqual(
                Path(
                    payload["approval_db"]
                ),
                (
                    state_root
                    / "cyber-approvals.db"
                ),
            )

            self.assertEqual(
                Path(
                    payload["memory_db"]
                ),
                (
                    state_root
                    / "bran-cognitive.db"
                ),
            )

            self.assertEqual(
                Path(
                    payload["project_root"]
                ),
                (
                    data_root
                    / "WORKSPACE"
                    / "PROJECTS"
                ),
            )

            self.assertEqual(
                Path(
                    payload["voice_config"]
                ),
                (
                    data_root
                    / "CONFIG"
                    / "voice.profiles.json"
                ),
            )

            self.assertEqual(
                Path(
                    payload["voice_sessions"]
                ),
                (
                    state_root
                    / "VOICE_SESSIONS"
                ),
            )

            self.assertEqual(
                Path(
                    payload["home"]
                ),
                state_root / "core",
            )

            self.assertEqual(
                payload["member"],
                "ned",
            )

            self.assertTrue(
                (
                    data_root
                    / "CONFIG"
                    / "approval.policy.json"
                ).is_file()
            )

            self.assertTrue(
                (
                    data_root
                    / "CONFIG"
                    / "voice.profiles.json"
                ).is_file()
            )


        final_digest = hashlib.sha256(
            original_voice.read_bytes()
        ).hexdigest()

        self.assertEqual(
            original_digest,
            final_digest,
            "Portable config write leaked into runtime CONFIG.",
        )


if __name__ == "__main__":
    unittest.main()
