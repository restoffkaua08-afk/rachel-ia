from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rachel_core.adapters.knowledge_sqlite import SQLiteKnowledgeAdapter
from rachel_core.bootstrap import build_container
from rachel_core.config import Settings
from rachel_core.knowledge_service import KnowledgeEnabledChatService


class KnowledgeBootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def settings(self) -> Settings:
        return Settings(
            home=self.root / "core",
            model_provider="mock",
            model_name="rachel-mock-v1",
            model_base_url="",
            model_api_key="",
            model_timeout_seconds=10,
            api_host="127.0.0.1",
            api_port=8765,
            api_token="",
            log_level="INFO",
        )

    def test_bootstrap_uses_real_knowledge_adapter(self):
        knowledge_db = self.root / "knowledge.db"
        with patch.dict(
            os.environ,
            {
                "RACHEL_KNOWLEDGE_DB_PATH": str(knowledge_db),
                "RACHEL_MODEL_ROUTER_ENABLED": "0",
            },
            clear=False,
        ):
            container = build_container(self.settings())

        self.assertIsInstance(container.knowledge, SQLiteKnowledgeAdapter)
        self.assertIsInstance(container.chat, KnowledgeEnabledChatService)
        self.assertEqual(container.knowledge.path, knowledge_db.resolve())

    def test_status_reports_knowledge_backend_truthfully(self):
        knowledge_db = self.root / "knowledge.db"
        with patch.dict(
            os.environ,
            {
                "RACHEL_KNOWLEDGE_DB_PATH": str(knowledge_db),
                "RACHEL_MODEL_ROUTER_ENABLED": "0",
            },
            clear=False,
        ):
            container = build_container(self.settings())
            status = container.chat.status()

        self.assertTrue(status["capabilities"]["knowledge"])
        self.assertEqual(status["knowledge"]["backend"], "sqlite")
        self.assertFalse(status["knowledge"]["database_exists"])
        self.assertEqual(status["knowledge"]["document_chunks"], 0)

    def test_default_knowledge_path_is_sibling_of_core_home(self):
        with patch.dict(
            os.environ,
            {
                "RACHEL_KNOWLEDGE_DB_PATH": "",
                "RACHEL_MODEL_ROUTER_ENABLED": "0",
            },
            clear=False,
        ):
            container = build_container(self.settings())

        self.assertEqual(
            container.knowledge.path,
            (self.root / "bran-cognitive.db").resolve(),
        )


if __name__ == "__main__":
    unittest.main()
