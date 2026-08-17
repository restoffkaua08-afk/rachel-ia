import json
import os
import subprocess
import sys
import tempfile
import unittest

from pathlib import Path


ROOT = Path(
    __file__
).resolve().parents[3]

CORE_SRC = (
    ROOT
    / "RACHEL_CORE"
    / "src"
)

RUNTIME_SRC = (
    ROOT
    / "RACHEL_PLATFORM"
    / "RUNTIME"
    / "SRC"
)

sys.path.insert(
    0,
    str(CORE_SRC),
)

sys.path.insert(
    0,
    str(RUNTIME_SRC),
)


from cognitive_runtime import NedCognitiveBridge
from rachel_core.adapters.learning_sqlite import SQLiteLearningAdapter
from task_runtime import TaskOrchestrator


class TaskLearningTests(
    unittest.TestCase
):
    def setUp(
        self,
    ) -> None:
        self.temp = (
            tempfile
            .TemporaryDirectory()
        )

        self.root = Path(
            self.temp.name
        )

        self.learning = (
            SQLiteLearningAdapter(
                self.root
                / "learning.db"
            )
        )

    def tearDown(
        self,
    ) -> None:
        self.temp.cleanup()

    def test_task_plan_and_execution_are_captured(
        self,
    ) -> None:
        bridge = NedCognitiveBridge(
            learning=self.learning
        )

        orchestrator = (
            TaskOrchestrator(
                database=(
                    self.root
                    / "plans.db"
                ),
                coordinator=(
                    bridge.tools
                ),
                model=(
                    bridge
                    .container
                    .chat
                    .model
                ),
                learning=(
                    self.learning
                ),
            )
        )

        plan = (
            orchestrator
            .create_plan(
                goal="Consultar saude",
                specifications=[
                    {
                        "id": "health",
                        "title": (
                            "Consultar saude"
                        ),
                        "description": (
                            "Ler estado atual"
                        ),
                        "tool": (
                            "tyrion.health"
                        ),
                        "arguments": {},
                        "depends_on": [],
                    }
                ],
                source="test",
            )
        )

        self.assertTrue(
            plan.get(
                "learning_event_id"
            )
        )

        result = (
            orchestrator
            .execute(
                plan["id"]
            )
        )

        self.assertEqual(
            "completed",
            result["state"],
        )

        self.assertTrue(
            result.get(
                "learning_event_id"
            )
        )

        kinds = {
            item["kind"]
            for item in (
                self.learning
                .recent_events(
                    20
                )
            )
        }

        self.assertIn(
            "task_plan",
            kinds,
        )

        self.assertIn(
            "task_execution",
            kinds,
        )

    def test_task_learning_strips_approval_ids_and_raw_error(
        self,
    ) -> None:
        safe = (
            TaskOrchestrator
            ._safe_learning_payload(
                {
                    "approval": {
                        "id": (
                            "approval_secret123"
                        )
                    },
                    "approval_id": (
                        "approval_secret456"
                    ),
                    "nested": {
                        "token": (
                            "approval_secret789"
                        ),
                        "error": (
                            "RuntimeError: segredo-bruto"
                        ),
                    },
                }
            )
        )

        serialized = json.dumps(
            safe,
            ensure_ascii=False,
        )

        self.assertNotIn(
            "approval_secret123",
            serialized,
        )

        self.assertNotIn(
            "approval_secret456",
            serialized,
        )

        self.assertNotIn(
            "approval_secret789",
            serialized,
        )

        self.assertNotIn(
            "segredo-bruto",
            serialized,
        )

        self.assertTrue(
            safe[
                "approval_present"
            ]
        )

        self.assertEqual(
            "RuntimeError",
            safe[
                "nested"
            ][
                "error_type"
            ],
        )


class LearningBridgeTests(
    unittest.TestCase
):
    def setUp(
        self,
    ) -> None:
        self.temp = (
            tempfile
            .TemporaryDirectory()
        )

        self.root = Path(
            self.temp.name
        )

        self.state = (
            self.root
            / "STATE"
        )

        self.home = (
            self.state
            / "core"
        )

        self.home.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.bridge = (
            ROOT
            / "APP"
            / "bridge"
            / "rachel_bridge.py"
        )

        self.python = Path(
            sys.executable
        )

        self.environment = (
            os.environ.copy()
        )

        self.environment[
            "RACHEL_STATE_ROOT"
        ] = str(
            self.state
        )

        self.environment[
            "RACHEL_HOME"
        ] = str(
            self.home
        )

        self.environment[
            "RACHEL_MODEL_PROVIDER"
        ] = "mock"

        self.environment[
            "RACHEL_MODEL_NAME"
        ] = "rachel-mock-v1"

        self.environment[
            "PYTHONUTF8"
        ] = "1"

        self.environment[
            "PYTHONIOENCODING"
        ] = "utf-8"

        self.environment.pop(
            "RACHEL_MODEL_BASE_URL",
            None,
        )

        self.environment.pop(
            "RACHEL_MODEL_API_KEY",
            None,
        )

    def tearDown(
        self,
    ) -> None:
        self.temp.cleanup()

    def call(
        self,
        name: str,
        payload: dict,
    ) -> dict:
        request = (
            self.root
            / f"{name}.json"
        )

        request.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        process = subprocess.run(
            [
                str(self.python),
                "-X",
                "utf8",
                str(self.bridge),
                "--request-file",
                str(request),
            ],
            env=self.environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
        )

        if process.returncode != 0:
            self.fail(
                process.stderr
                + process.stdout
            )

        response = json.loads(
            process.stdout
        )

        self.assertTrue(
            response["ok"]
        )

        return response[
            "payload"
        ]

    def test_bridge_feedback_and_recent(
        self,
    ) -> None:
        chat = self.call(
            "chat",
            {
                "action": "chat",
                "content": (
                    "Teste de feedback "
                    "do bridge."
                ),
            },
        )

        experience_id = (
            chat[
                "message"
            ][
                "metadata"
            ][
                "learning_experience_id"
            ]
        )

        feedback = self.call(
            "feedback",
            {
                "action": (
                    "learning_feedback"
                ),
                "experience_id": (
                    experience_id
                ),
                "verdict": (
                    "accepted"
                ),
                "note": (
                    "Resposta aprovada."
                ),
            },
        )

        self.assertTrue(
            feedback[
                "feedback_id"
            ].startswith(
                "fb_"
            )
        )

        recent = self.call(
            "recent",
            {
                "action": (
                    "learning_recent"
                ),
                "limit": 20,
            },
        )

        self.assertEqual(
            2,
            recent[
                "status"
            ][
                "schema_version"
            ],
        )

        self.assertGreaterEqual(
            recent[
                "status"
            ][
                "feedback"
            ],
            1,
        )

        self.assertEqual(
            0,
            recent[
                "status"
            ][
                "approved_for_training"
            ],
        )

        matches = [
            item
            for item in recent[
                "experiences"
            ]
            if item["id"]
            == experience_id
        ]

        self.assertEqual(
            1,
            len(matches),
        )

        self.assertEqual(
            "user_accepted",
            matches[0][
                "review_state"
            ],
        )

        self.assertEqual(
            "captured",
            matches[0][
                "training_state"
            ],
        )


if __name__ == "__main__":
    unittest.main()
