import json
import sys
import tempfile
import unittest

from pathlib import Path


ROOT = Path(
    __file__
).resolve().parents[3]

sys.path.insert(
    0,
    str(
        ROOT
        / "RACHEL_CORE"
        / "src"
    ),
)

sys.path.insert(
    0,
    str(
        ROOT
        / "RACHEL_PLATFORM"
        / "RUNTIME"
        / "SRC"
    ),
)


from bran_cognitive import CognitiveMemory
from cognitive_runtime import NedCognitiveBridge
from rachel_core.adapters.learning_sqlite import SQLiteLearningAdapter


class NedLearningCaptureTests(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.temp = (
            tempfile
            .TemporaryDirectory()
        )

        root = Path(
            self.temp.name
        )

        self.learning = (
            SQLiteLearningAdapter(
                root / "learning.db"
            )
        )

        self.memory = (
            CognitiveMemory(
                root / "bran.db"
            )
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def bridge(self):
        return NedCognitiveBridge(
            memory=self.memory,
            learning=self.learning,
        )

    def test_completed_tool_captures_plan_and_result(
        self,
    ):
        bridge = self.bridge()

        result = bridge.assist(
            "Verifique a saude dos orgaos"
        )

        self.assertEqual(
            "completed",
            result["state"],
        )

        agent = result[
            "agent_learning"
        ]

        self.assertTrue(
            agent["plan_event_id"]
        )

        self.assertTrue(
            agent["tool_event_id"]
        )

        events = (
            self.learning
            .recent_events(20)
        )

        kinds = {
            item["kind"]
            for item in events
        }

        self.assertIn(
            "planner_decision",
            kinds,
        )

        self.assertIn(
            "tool_result",
            kinds,
        )

    def test_approval_id_is_not_saved(
        self,
    ):
        bridge = self.bridge()

        result = bridge.assist(
            "Lembre que eu prefiro relatorios tecnicos"
        )

        self.assertEqual(
            "approval_required",
            result["state"],
        )

        approval = (
            result[
                "tool_result"
            ]["approval"]
        )

        self.assertIsNotNone(
            approval
        )

        approval_id = approval["id"]

        events = (
            self.learning
            .recent_events(20)
        )

        tool_events = [
            item
            for item in events
            if item["kind"] == "tool_result"
        ]

        self.assertTrue(
            tool_events
        )

        serialized = json.dumps(
            tool_events,
            ensure_ascii=False,
        )

        self.assertNotIn(
            approval_id,
            serialized,
        )

        result_payload = (
            tool_events[0]
            ["payload"]
            ["result"]
        )

        self.assertNotIn(
            "approval",
            result_payload,
        )

        self.assertTrue(
            result_payload[
                "approval_present"
            ]
        )

    def test_failure_stores_type_not_message(
        self,
    ):
        bridge = self.bridge()

        def fail(*args, **kwargs):
            raise RuntimeError(
                "segredo-na-mensagem"
            )

        bridge.tools.invoke = fail

        with self.assertRaises(
            RuntimeError
        ):
            bridge.assist(
                "Verifique a saude dos orgaos"
            )

        events = (
            self.learning
            .recent_events(20)
        )

        failures = [
            item
            for item in events
            if item["kind"] == "tool_failed"
        ]

        self.assertEqual(
            1,
            len(failures),
        )

        serialized = json.dumps(
            failures[0],
            ensure_ascii=False,
        )

        self.assertIn(
            "RuntimeError",
            serialized,
        )

        self.assertNotIn(
            "segredo-na-mensagem",
            serialized,
        )


if __name__ == "__main__":
    unittest.main()
