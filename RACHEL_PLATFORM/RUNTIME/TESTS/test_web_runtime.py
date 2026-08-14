import json
import tempfile
import time
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(
    0,
    str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"),
)

from web_runtime import (
    ContentParser,
    WebCache,
    WebPolicy,
    WebSecurityError,
    normalize_url,
    parse_content,
    validate_url,
)


class WebRuntimeTests(unittest.TestCase):
    def test_normalizes_url_and_removes_fragment(self):
        result = normalize_url(
            "https://example.com/docs?q=1#section"
        )
        self.assertEqual(
            result,
            "https://example.com/docs?q=1",
        )

    def test_adds_https_when_scheme_is_missing(self):
        result = normalize_url("example.com")
        self.assertEqual(result, "https://example.com/")

    def test_blocks_localhost(self):
        policy = WebPolicy()

        with self.assertRaises(WebSecurityError):
            validate_url(
                "http://localhost/admin",
                policy,
            )

    def test_blocks_private_ip_resolution(self):
        policy = WebPolicy()

        def private_resolver(*args, **kwargs):
            return [
                (
                    2,
                    1,
                    6,
                    "",
                    ("192.168.1.10", 443),
                )
            ]

        with self.assertRaises(WebSecurityError):
            validate_url(
                "https://private.example",
                policy,
                resolver=private_resolver,
            )

    def test_accepts_public_ip_resolution(self):
        policy = WebPolicy()

        def public_resolver(*args, **kwargs):
            return [
                (
                    2,
                    1,
                    6,
                    "",
                    ("93.184.216.34", 443),
                )
            ]

        result = validate_url(
            "https://example.com",
            policy,
            resolver=public_resolver,
        )
        self.assertEqual(result, "https://example.com/")

    def test_html_parser_ignores_scripts(self):
        body = b"""
        <html>
          <head>
            <title>Rachel Docs</title>
            <style>hidden style</style>
          </head>
          <body>
            <main>
              <h1>Documentacao</h1>
              <p>Conteudo confiavel.</p>
              <script>hidden script</script>
            </main>
          </body>
        </html>
        """

        title, content = parse_content(
            body,
            "text/html; charset=utf-8",
        )

        self.assertEqual(title, "Rachel Docs")
        self.assertIn("Conteudo confiavel", content)
        self.assertNotIn("hidden script", content)
        self.assertNotIn("hidden style", content)

    def test_json_is_normalized(self):
        title, content = parse_content(
            b'{"name":"Rachel","active":true}',
            "application/json",
        )
        self.assertEqual(title, "")
        self.assertIn('"name": "Rachel"', content)

    def test_cache_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = WebCache(
                Path(directory),
                ttl_seconds=60,
            )
            payload = {
                "url": "https://example.com/",
                "final_url": "https://example.com/",
                "title": "Example",
                "content": "Evidence",
                "content_type": "text/html",
                "status_code": 200,
                "retrieved_at_ms": int(time.time() * 1000),
                "sha256": "a" * 64,
                "from_cache": False,
            }
            cache.set(payload["url"], payload)
            loaded = cache.get(payload["url"])
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["content"], "Evidence")

    def test_policy_requires_citations(self):
        policy = WebPolicy()
        self.assertTrue(policy.data["require_citations"])


if __name__ == "__main__":
    unittest.main()
