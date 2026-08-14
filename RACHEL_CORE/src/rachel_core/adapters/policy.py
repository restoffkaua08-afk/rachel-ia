from ..domain.enums import PolicyEffect
from ..domain.models import PolicyDecision, ToolCall


class DenyByDefaultPolicy:
    def evaluate(self, call: ToolCall) -> PolicyDecision:
        return PolicyDecision(
            effect=PolicyEffect.DENY,
            reason=f"A ferramenta '{call.name}' não está autorizada nesta versão do núcleo.",
            requires_user_confirmation=False,
        )

