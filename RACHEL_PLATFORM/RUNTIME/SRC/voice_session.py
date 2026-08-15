from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class VoiceState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"
    STOPPED = "stopped"
    ERROR = "error"


ALLOWED_TRANSITIONS = {
    VoiceState.IDLE: {VoiceState.LISTENING, VoiceState.STOPPED},
    VoiceState.LISTENING: {VoiceState.TRANSCRIBING, VoiceState.LISTENING, VoiceState.STOPPED, VoiceState.ERROR},
    VoiceState.TRANSCRIBING: {VoiceState.THINKING, VoiceState.LISTENING, VoiceState.STOPPED, VoiceState.ERROR},
    VoiceState.THINKING: {VoiceState.SPEAKING, VoiceState.LISTENING, VoiceState.STOPPED, VoiceState.ERROR},
    VoiceState.SPEAKING: {VoiceState.LISTENING, VoiceState.STOPPED, VoiceState.ERROR},
    VoiceState.ERROR: {VoiceState.LISTENING, VoiceState.STOPPED},
    VoiceState.STOPPED: set(),
}


@dataclass
class VoiceTurn:
    index: int
    transcript: str
    answer: str
    started_at_ms: int
    completed_at_ms: int
    quality: dict[str, Any] | None = None


@dataclass
class VoiceSession:
    state_dir: Path
    profile: str = "natural"
    device: int | None = None
    session_id: str = field(default_factory=lambda: "voice_" + uuid.uuid4().hex)
    conversation_id: str | None = None
    state: VoiceState = VoiceState.IDLE
    turns: list[VoiceTurn] = field(default_factory=list)
    consecutive_errors: int = 0
    silence_timeouts: int = 0
    started_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    stopped_at_ms: int | None = None

    def __post_init__(self) -> None:
        self.state_dir = Path(self.state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.persist()

    @property
    def path(self) -> Path:
        return self.state_dir / f"{self.session_id}.json"

    def transition(self, target: VoiceState, reason: str | None = None) -> None:
        target = VoiceState(target)
        if target not in ALLOWED_TRANSITIONS[self.state]:
            raise ValueError(f"Invalid voice transition: {self.state.value} -> {target.value}")
        self.state = target
        if target == VoiceState.STOPPED:
            self.stopped_at_ms = int(time.time() * 1000)
        self.persist(reason=reason)

    def register_silence(self) -> None:
        self.silence_timeouts += 1
        self.persist(reason="silence-timeout")

    def register_error(self, error: Exception | str) -> None:
        self.consecutive_errors += 1
        if self.state != VoiceState.ERROR:
            self.transition(VoiceState.ERROR, reason=str(error))
        else:
            self.persist(reason=str(error))

    def recover(self) -> None:
        if self.state != VoiceState.ERROR:
            raise ValueError("Only an errored session can recover")
        self.transition(VoiceState.LISTENING, reason="automatic-recovery")

    def add_turn(
        self,
        transcript: str,
        answer: str,
        started_at_ms: int,
        quality: dict[str, Any] | None = None,
        conversation_id: str | None = None,
    ) -> VoiceTurn:
        clean_transcript = " ".join(transcript.strip().split())
        clean_answer = " ".join(answer.strip().split())
        if not clean_transcript or not clean_answer:
            raise ValueError("Voice turns require transcript and answer")
        if conversation_id:
            self.conversation_id = conversation_id
        turn = VoiceTurn(
            index=len(self.turns) + 1,
            transcript=clean_transcript,
            answer=clean_answer,
            started_at_ms=started_at_ms,
            completed_at_ms=int(time.time() * 1000),
            quality=quality,
        )
        self.turns.append(turn)
        self.consecutive_errors = 0
        self.persist(reason="turn-completed")
        return turn

    def snapshot(self, reason: str | None = None) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "session_id": self.session_id,
            "conversation_id": self.conversation_id,
            "profile": self.profile,
            "device": self.device,
            "state": self.state.value,
            "turn_count": len(self.turns),
            "consecutive_errors": self.consecutive_errors,
            "silence_timeouts": self.silence_timeouts,
            "started_at_ms": self.started_at_ms,
            "stopped_at_ms": self.stopped_at_ms,
            "reason": reason,
            "turns": [asdict(turn) for turn in self.turns],
        }

    def persist(self, reason: str | None = None) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self.snapshot(reason), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)
