import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from rachel_core.api import RachelRequestHandler, ThreadingHTTPServer
from rachel_core.bootstrap import build_container
from rachel_core.config import Settings


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        settings = Settings(
            home=Path(self.temp.name),
            model_provider="mock",
            model_name="test-model",
            model_base_url="",
            model_api_key="",
            model_timeout_seconds=5,
            api_host="127.0.0.1",
            api_port=0,
            api_token="test-token",
            log_level="INFO",
        )
        container = build_container(settings)
        handler = type("TestHandler", (RachelRequestHandler,), {"container": container})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, path: str, method: str = "GET", payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=data,
            method=method,
            headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
        )
        with urlopen(request, timeout=3) as response:
            return response.status, json.loads(response.read())

    def test_health_and_chat(self) -> None:
        status, health = self.request("/health")
        self.assertEqual(200, status)
        self.assertEqual("ok", health["status"])
        status, chat = self.request("/v1/chat", "POST", {"content": "Olá Rachel"})
        self.assertEqual(200, status)
        self.assertEqual("completed", chat["state"])

    def test_animated_web_interface(self) -> None:
        request = Request(f"http://127.0.0.1:{self.port}/")
        with urlopen(request, timeout=3) as response:
            content = response.read().decode("utf-8")
        self.assertIn("Rachel IA", content)
        self.assertIn('id="coreCanvas"', content)
        self.assertNotIn('<img src="/assets/rachel-heart.png"', content)
        self.assertIn('id="particles"', content)
        self.assertIn("/v1/chat", content)

    def test_heart_asset_is_served(self) -> None:
        request = Request(f"http://127.0.0.1:{self.port}/assets/rachel-heart.png")
        with urlopen(request, timeout=3) as response:
            content = response.read()
            content_type = response.headers.get_content_type()
        self.assertEqual("image/png", content_type)
        self.assertTrue(content.startswith(b"\x89PNG\r\n\x1a\n"))


if __name__ == "__main__":
    unittest.main()
