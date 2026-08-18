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
        if not base_url or not model_name:
            raise ModelError(
                "URL e modelo são obrigatórios para o provedor compatível."
            )

        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _payload_messages(
        self,
        messages: Sequence[Message],
        system_prompt: str | None,
    ) -> list[dict[str, str]]:
        payload_messages: list[dict[str, str]] = []
        if system_prompt:
            payload_messages.append(
                {
                    "role": "system",
                    "content": system_prompt,
                }
            )
        payload_messages.extend(
            {
                "role": message.role.value,
                "content": message.content,
            }
            for message in messages
        )
        return payload_messages

    def _request(
        self,
        messages: Sequence[Message],
        system_prompt: str | None,
        *,
        stream: bool,
    ) -> Request:
        payload = json.dumps(
            {
                "model": self.model_name,
                "messages": self._payload_messages(messages, system_prompt),
                "stream": stream,
            }
        ).encode("utf-8")
        return Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers=self._headers(),
            method="POST",
        )

    def health(self) -> dict[str, object]:
        request = Request(
            f"{self.base_url}/models",
            headers=self._headers(),
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return {
                "available": False,
                "reachable": True,
                "provider": self.provider_name,
                "model": self.model_name,
                "model_available": False,
                "error_type": "HTTPError",
                "http_status": exc.code,
            }
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            return {
                "available": False,
                "reachable": False,
                "provider": self.provider_name,
                "model": self.model_name,
                "model_available": False,
                "error_type": type(exc).__name__,
            }

        try:
            model_ids = {
                str(item["id"])
                for item in data["data"]
                if isinstance(item, dict) and "id" in item
            }
        except (KeyError, TypeError):
            return {
                "available": False,
                "reachable": True,
                "provider": self.provider_name,
                "model": self.model_name,
                "model_available": False,
                "error_type": "InvalidModelsResponse",
            }

        model_available = self.model_name in model_ids
        return {
            "available": model_available,
            "reachable": True,
            "provider": self.provider_name,
            "model": self.model_name,
            "model_available": model_available,
        }

    def generate(
        self,
        messages: Sequence[Message],
        system_prompt: str | None,
    ) -> ModelResponse:
        request = self._request(
            messages,
            system_prompt,
            stream=False,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read(500).decode("utf-8", errors="replace")
            raise ModelError(
                f"Provedor retornou HTTP {exc.code}: {body}"
            ) from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ModelError(f"Falha ao consultar o provedor: {exc}") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelError(
                "Resposta do provedor não segue o contrato esperado."
            ) from exc

        usage = data.get("usage", {})
        return ModelResponse(
            content=str(content),
            provider=self.provider_name,
            model=self.model_name,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )

    def generate_stream(
        self,
        messages: Sequence[Message],
        system_prompt: str | None,
    ) -> Iterable[str]:
        """Yield provider chunks as soon as they arrive.

        Ollama's OpenAI-compatible endpoint and standard OpenAI-compatible
        providers stream Server-Sent Events using ``data: {...}`` records.
        The parser also accepts one-JSON-object-per-line providers so the
        adapter remains portable across compatible local runtimes.
        """
        request = self._request(
            messages,
            system_prompt,
            stream=True,
        )
        yielded = False

        try:
            with urlopen(request, timeout=self.timeout) as response:
                for raw_line in response:
                    line = raw_line.decode(
                        "utf-8",
                        errors="replace",
                    ).strip()
                    if not line or line.startswith(":") or line.startswith("event:"):
                        continue
                    if line.startswith("data:"):
                        line = line[5:].strip()
                    if not line:
                        continue
                    if line == "[DONE]":
                        break

                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ModelError(
                            "Chunk de streaming do provedor não é JSON válido."
                        ) from exc

                    try:
                        choice = data["choices"][0]
                    except (KeyError, IndexError, TypeError):
                        continue

                    delta = choice.get("delta") if isinstance(choice, dict) else None
                    message = choice.get("message") if isinstance(choice, dict) else None
                    content = None
                    if isinstance(delta, dict):
                        content = delta.get("content")
                    if content is None and isinstance(message, dict):
                        content = message.get("content")

                    if content:
                        yielded = True
                        yield str(content)

        except HTTPError as exc:
            body = exc.read(500).decode("utf-8", errors="replace")
            raise ModelError(
                f"Provedor retornou HTTP {exc.code} durante streaming: {body}"
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise ModelError(
                f"Falha durante streaming do provedor: {exc}"
            ) from exc

        if not yielded:
            raise ModelError(
                "O provedor encerrou o streaming sem retornar conteúdo."
            )
