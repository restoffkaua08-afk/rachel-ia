from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Callable, Sequence


@dataclass(frozen=True)
class BargeInConfig:
    sample_rate: int = 16000
    block_seconds: float = 0.05
    warmup_seconds: float = 0.65
    absolute_threshold: float = 0.024
    noise_multiplier: float = 2.8
    consecutive_blocks: int = 4
    maximum_seconds: float = 180.0

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "BargeInConfig":
        return cls(
            sample_rate=int(data.get("sample_rate", 16000)),
            block_seconds=float(data.get("block_seconds", 0.05)),
            warmup_seconds=float(data.get("warmup_seconds", 0.65)),
            absolute_threshold=float(data.get("absolute_threshold", 0.024)),
            noise_multiplier=float(data.get("noise_multiplier", 2.8)),
            consecutive_blocks=int(data.get("consecutive_blocks", 4)),
            maximum_seconds=float(data.get("maximum_seconds", 180.0)),
        )

    def validate(self) -> None:
        if self.sample_rate < 8000 or self.sample_rate > 192000:
            raise ValueError("Invalid barge-in sample rate")
        if not 0.01 <= self.block_seconds <= 0.25:
            raise ValueError("Invalid barge-in block duration")
        if not 0.0 <= self.warmup_seconds <= 5.0:
            raise ValueError("Invalid barge-in warmup")
        if not 0.001 <= self.absolute_threshold <= 1.0:
            raise ValueError("Invalid barge-in threshold")
        if not 1.1 <= self.noise_multiplier <= 10.0:
            raise ValueError("Invalid noise multiplier")
        if not 1 <= self.consecutive_blocks <= 30:
            raise ValueError("Invalid consecutive block count")


class AdaptiveVoiceDetector:
    def __init__(self, config: BargeInConfig) -> None:
        config.validate()
        self.config = config
        self.noise_floor = config.absolute_threshold / config.noise_multiplier
        self.active_blocks = 0
        self.samples_seen = 0

    @property
    def warmup_blocks(self) -> int:
        return max(1, round(self.config.warmup_seconds / self.config.block_seconds))

    @property
    def threshold(self) -> float:
        return max(self.config.absolute_threshold, self.noise_floor * self.config.noise_multiplier)

    def observe_rms(self, rms: float) -> bool:
        value = max(0.0, float(rms))
        self.samples_seen += 1
        if self.samples_seen <= self.warmup_blocks:
            self.noise_floor = (self.noise_floor * 0.82) + (value * 0.18)
            self.active_blocks = 0
            return False
        if value >= self.threshold:
            self.active_blocks += 1
        else:
            self.active_blocks = 0
            self.noise_floor = (self.noise_floor * 0.97) + (value * 0.03)
        return self.active_blocks >= self.config.consecutive_blocks


def array_rms(data: Any) -> float:
    import numpy as np
    return math.sqrt(float(np.mean(np.square(data))))


def terminate_process_tree(process: Any) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=2)
    except Exception:
        process.kill()
        process.wait(timeout=2)


def monitor_process_for_barge_in(
    process: Any,
    device: int | None,
    config: BargeInConfig,
    stream_factory: Callable[..., Any] | None = None,
    rms_function: Callable[[Any], float] = array_rms,
) -> dict[str, Any]:
    config.validate()
    if stream_factory is None:
        import sounddevice as sd
        stream_factory = sd.InputStream
    detector = AdaptiveVoiceDetector(config)
    blocksize = max(1, int(config.sample_rate * config.block_seconds))
    started = time.monotonic()
    interrupted = False
    with stream_factory(
        samplerate=config.sample_rate,
        channels=1,
        dtype="float32",
        blocksize=blocksize,
        device=device,
    ) as stream:
        while process.poll() is None:
            if time.monotonic() - started > config.maximum_seconds:
                terminate_process_tree(process)
                raise TimeoutError("Speech playback exceeded its time limit")
            data, _ = stream.read(blocksize)
            if detector.observe_rms(rms_function(data)):
                interrupted = True
                terminate_process_tree(process)
                break
    return {
        "interrupted": interrupted,
        "threshold": detector.threshold,
        "noise_floor": detector.noise_floor,
        "duration_ms": round((time.monotonic() - started) * 1000),
    }
