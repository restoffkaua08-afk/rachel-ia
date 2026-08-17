from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..domain.errors import ModelError
from ..domain.models import Message, ModelResponse


class OpenAICompatibleAdapter:
    provider_name = "openai-compatible"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model_name: str,
        timeout: int = 60,
    ) -> None:
        if (
            not base_url
            or not model_name
        ):
            raise ModelError(
                "URL e modelo são obrigatórios para o provedor compatível."
            )

        self.base_url = (
            base_url.rstrip("/")
        )

        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout

    def _headers(
        self,
    ) -> dict[str, str]:
        headers = {
            "Content-Type": (
                "application/json"
            )
        }

        if self.api_key:
            headers[
                "Authorization"
            ] = (
                f"Bearer {self.api_key}"
            )

        return headers

    def health(
        self,
    ) -> dict[str, object]:
        request = Request(
            f"{self.base_url}/models",
            headers=self._headers(),
            method="GET",
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                data = json.loads(
                    response
                    .read()
                    .decode("utf-8")
                )

        except HTTPError as exc:
            return {
                "available": False,
                "reachable": True,
                "provider": (
                    self.provider_name
                ),
                "model": (
                    self.model_name
                ),
                "model_available": False,
                "error_type": (
                    "HTTPError"
                ),
                "http_status": (
                    exc.code
                ),
            }

        except (
            URLError,
            TimeoutError,
            json.JSONDecodeError,
        ) as exc:
            return {
                "available": False,
                "reachable": False,
                "provider": (
                    self.provider_name
                ),
                "model": (
                    self.model_name
                ),
                "model_available": False,
                "error_type": (
                    type(exc).__name__
                ),
            }

        try:
            model_ids = {
                str(item["id"])
                for item in data["data"]
                if isinstance(
                    item,
                    dict,
                )
                and "id" in item
            }

        except (
            KeyError,
            TypeError,
        ):
            return {
                "available": False,
                "reachable": True,
                "provider": (
                    self.provider_name
                ),
                "model": (
                    self.model_name
                ),
                "model_available": False,
                "error_type": (
                    "InvalidModelsResponse"
                ),
            }

        model_available = (
            self.model_name
            in model_ids
        )

        return {
            "available": (
                model_available
            ),
            "reachable": True,
            "provider": (
                self.provider_name
            ),
            "model": (
                self.model_name
            ),
            "model_available": (
                model_available
            ),
        }

    def generate(
        self,
        messages: Sequence[Message],
        system_prompt: str | None,
    ) -> ModelResponse:
        payload_messages = []

        if system_prompt:
            payload_messages.append(
                {
                    "role": "system",
                    "content": (
                        system_prompt
                    ),
                }
            )

        payload_messages.extend(
            {
                "role": (
                    message.role.value
                ),
                "content": (
                    message.content
                ),
            }
            for message in messages
        )

        payload = json.dumps(
            {
                "model": (
                    self.model_name
                ),
                "messages": (
                    payload_messages
                ),
                "stream": False,
            }
        ).encode(
            "utf-8"
        )

        request = Request(
            (
                f"{self.base_url}"
                "/chat/completions"
            ),
            data=payload,
            headers=self._headers(),
            method="POST",
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                data = json.loads(
                    response
                    .read()
                    .decode("utf-8")
                )

        except HTTPError as exc:
            body = (
                exc.read(500)
                .decode(
                    "utf-8",
                    errors="replace",
                )
            )

            raise ModelError(
                f"Provedor retornou HTTP {exc.code}: {body}"
            ) from exc

        except (
            URLError,
            TimeoutError,
            json.JSONDecodeError,
        ) as exc:
            raise ModelError(
                f"Falha ao consultar o provedor: {exc}"
            ) from exc

        try:
            content = (
                data[
                    "choices"
                ][0][
                    "message"
                ][
                    "content"
                ]
            )

        except (
            KeyError,
            IndexError,
            TypeError,
        ) as exc:
            raise ModelError(
                "Resposta do provedor não segue o contrato esperado."
            ) from exc

        usage = data.get(
            "usage",
            {},
        )

        return ModelResponse(
            content=str(
                content
            ),
            provider=(
                self.provider_name
            ),
            model=(
                self.model_name
            ),
            input_tokens=(
                usage.get(
                    "prompt_tokens"
                )
            ),
            output_tokens=(
                usage.get(
                    "completion_tokens"
                )
            ),
        )

    def generate_stream(
        self,
        messages: Sequence[Message],
        system_prompt: str | None,
    ) -> Iterable[str]:
        yield self.generate(
            messages,
            system_prompt,
        ).content

