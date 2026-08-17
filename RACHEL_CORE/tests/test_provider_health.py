import json
import unittest

from unittest.mock import patch
from urllib.error import URLError

from rachel_core.adapters.model_mock import MockModelAdapter
from rachel_core.adapters.model_openai_compatible import OpenAICompatibleAdapter
from rachel_core.application import ChatService
from rachel_core.domain.errors import ModelError


class FakeResponse:
    def __init__(
        self,
        payload,
    ):
        self.payload = payload

    def __enter__(
        self,
    ):
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False

    def read(
        self,
    ):
        return json.dumps(
            self.payload
        ).encode(
            "utf-8"
        )


class ProviderHealthTests(
    unittest.TestCase
):
    def test_mock_health_is_explicit(
        self,
    ):
        health = (
            MockModelAdapter()
            .health()
        )

        self.assertTrue(
            health["available"]
        )

        self.assertTrue(
            health["mock"]
        )

    def test_openai_health_detects_model(
        self,
    ):
        adapter = (
            OpenAICompatibleAdapter(
                base_url=(
                    "http://localhost:11434/v1"
                ),
                api_key="",
                model_name="qwen3:1.7b",
            )
        )

        response = FakeResponse(
            {
                "data": [
                    {
                        "id": (
                            "qwen3:1.7b"
                        )
                    }
                ]
            }
        )

        with patch(
            (
                "rachel_core.adapters."
                "model_openai_compatible."
                "urlopen"
            ),
            return_value=response,
        ):
            health = (
                adapter.health()
            )

        self.assertTrue(
            health["reachable"]
        )

        self.assertTrue(
            health[
                "model_available"
            ]
        )

        self.assertTrue(
            health["available"]
        )

    def test_unavailable_provider_is_degraded(
        self,
    ):
        adapter = (
            OpenAICompatibleAdapter(
                base_url=(
                    "http://127.0.0.1:1/v1"
                ),
                api_key="",
                model_name="qwen3:1.7b",
                timeout=1,
            )
        )

        service = ChatService(
            model=adapter,
            memory=None,
            audit=None,
            knowledge=None,
        )

        with patch(
            (
                "rachel_core.adapters."
                "model_openai_compatible."
                "urlopen"
            ),
            side_effect=URLError(
                "offline"
            ),
        ):
            status = (
                service.status()
            )

        self.assertEqual(
            "degraded",
            status["status"],
        )

        self.assertFalse(
            status[
                "provider_health"
            ][
                "available"
            ]
        )

    def test_generate_fails_instead_of_using_mock(
        self,
    ):
        adapter = (
            OpenAICompatibleAdapter(
                base_url=(
                    "http://127.0.0.1:1/v1"
                ),
                api_key="",
                model_name="qwen3:1.7b",
                timeout=1,
            )
        )

        with patch(
            (
                "rachel_core.adapters."
                "model_openai_compatible."
                "urlopen"
            ),
            side_effect=URLError(
                "offline"
            ),
        ):
            with self.assertRaises(
                ModelError
            ):
                adapter.generate(
                    [],
                    None,
                )


if __name__ == "__main__":
    unittest.main()
