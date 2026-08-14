from enum import StrEnum


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class RunState(StrEnum):
    RECEIVING = "receiving"
    CONTEXT_BUILDING = "context_building"
    GENERATING = "generating"
    STREAMING = "streaming"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    FAILED = "failed"


class PolicyEffect(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    CONFIRM = "confirm"


class RiskLevel(StrEnum):
    READ = "read"
    REVERSIBLE = "reversible"
    EXTERNAL = "external"
    PRIVILEGED = "privileged"

