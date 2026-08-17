from collections.abc import Iterable, Sequence

from ..domain.enums import Role
from ..domain.models import Message, ModelResponse


class MockModelAdapter:
    provider_name = "mock"

    def __init__(
        self,
        model_name: str = "rachel-mock-v1",
    ) -> None:
        self.model_name = model_name

    def health(
        self,
    ) -> dict[str, object]:
        return {
            "available": True,
            "reachable": True,
            "provider": (
                self.provider_name
            ),
            "model": (
                self.model_name
            ),
            "model_available": True,
            "mock": True,
        }

    def generate(
        self,
        messages: Sequence[Message],
        system_prompt: str | None,
    ) -> ModelResponse:
        latest = next(
            (
                message.content
                for message in reversed(
                    messages
                )
                if message.role
                == Role.USER
            ),
            "",
        )

        content = (
            "Rachel Core está funcionando em modo de validação. "
            f"Recebi sua mensagem: {latest}"
        )

        return ModelResponse(
            content=content,
            provider=(
                self.provider_name
            ),
            model=(
                self.model_name
            ),
        )

    def generate_stream(
        self,
        messages: Sequence[Message],
        system_prompt: str | None,
    ) -> Iterable[str]:
        response = self.generate(
            messages,
            system_prompt,
        ).content

        words = response.split(
            " "
        )

        for index, word in enumerate(
            words
        ):
            yield (
                word
                if index
                == len(words) - 1
                else word + " "
            )

