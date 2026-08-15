from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import platform
import statistics
import time
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT / "RACHEL_PLATFORM" / "CONFIG" / "voice.profiles.json"
SESSION_DIR = ROOT / "RACHEL_PLATFORM" / "STATE" / "VOICE_SESSIONS"


def percentile(values: Iterable[float], fraction: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("Calibration requires audio samples")
    position = max(0.0, min(1.0, fraction)) * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def recommend_threshold(samples: Iterable[float]) -> dict[str, float]:
    values = [max(0.0, float(value)) for value in samples]
    if len(values) < 5:
        raise ValueError("At least five calibration samples are required")
    median = statistics.median(values)
    p95 = percentile(values, 0.95)
    threshold = min(0.18, max(0.008, p95 * 1.85, median * 3.2))
    return {
        "sample_count": len(values),
        "median_rms": round(median, 6),
        "p95_rms": round(p95, 6),
        "recommended_capture_threshold": round(threshold, 6),
        "recommended_barge_threshold": round(min(0.25, max(threshold * 1.25, 0.012)), 6),
    }


def input_devices() -> list[dict[str, Any]]:
    import sounddevice as sd
    devices = []
    for index, item in enumerate(sd.query_devices()):
        inputs = int(item["max_input_channels"])
        if inputs > 0:
            devices.append({
                "id": index,
                "name": str(item["name"]),
                "input_channels": inputs,
                "default_sample_rate": float(item["default_samplerate"]),
            })
    return devices


def collect_ambient_samples(device: int | None, seconds: float, sample_rate: int, block_seconds: float = 0.05) -> list[float]:
    if not 1.0 <= seconds <= 15.0:
        raise ValueError("Calibration duration must be between 1 and 15 seconds")
    import numpy as np
    import sounddevice as sd
    blocksize = max(1, int(sample_rate * block_seconds))
    blocks = max(5, round(seconds / block_seconds))
    values = []
    with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32", blocksize=blocksize, device=device) as stream:
        for _ in range(blocks):
            data, _ = stream.read(blocksize)
            values.append(math.sqrt(float(np.mean(np.square(data)))))
    return values


def calibrate(device: int | None = None, seconds: float = 3.0) -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    sample_rate = int(config["capture"]["sample_rate"])
    print("Fique em silencio durante a calibracao do ambiente...", flush=True)
    result = recommend_threshold(collect_ambient_samples(device, seconds, sample_rate))
    config["capture"]["energy_threshold"] = result["recommended_capture_threshold"]
    config["barge_in"]["absolute_threshold"] = result["recommended_barge_threshold"]
    config.setdefault("diagnostics", {})["last_calibration"] = {
        **result,
        "device": device,
        "created_at_ms": int(time.time() * 1000),
    }
    temporary = CONFIG_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(CONFIG_PATH)
    return {"state": "calibrated", "device": device, **result}


def session_summary() -> dict[str, Any]:
    sessions = []
    if SESSION_DIR.exists():
        for path in sorted(SESSION_DIR.glob("voice_*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:25]:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                sessions.append({
                    "session_id": payload.get("session_id"),
                    "state": payload.get("state"),
                    "turn_count": int(payload.get("turn_count", 0)),
                    "interruptions": int(payload.get("interruptions", 0)),
                    "consecutive_errors": int(payload.get("consecutive_errors", 0)),
                    "started_at_ms": payload.get("started_at_ms"),
                })
            except (OSError, ValueError, TypeError):
                continue
    return {
        "stored_sessions": len(sessions),
        "total_turns": sum(item["turn_count"] for item in sessions),
        "total_interruptions": sum(item["interruptions"] for item in sessions),
        "recent": sessions,
    }


def doctor(include_hardware: bool = True) -> dict[str, Any]:
    modules = {
        name: importlib.util.find_spec(name) is not None
        for name in ("numpy", "sounddevice", "faster_whisper")
    }
    config_exists = CONFIG_PATH.exists()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8")) if config_exists else {}
    devices = []
    hardware_error = None
    if include_hardware and modules["sounddevice"]:
        try:
            devices = input_devices()
        except Exception as error:
            hardware_error = f"{type(error).__name__}: {error}"
    checks = {
        "windows": platform.system() == "Windows",
        "config": config_exists,
        "stt_configured": bool(config.get("stt", {}).get("model")),
        "tts_configured": bool(config.get("tts", {}).get("voice")),
        "continuous_session": bool(config.get("conversation", {}).get("preserve_context")),
        "barge_in": bool(config.get("barge_in", {}).get("enabled")),
        "numpy": modules["numpy"],
        "sounddevice": modules["sounddevice"],
        "faster_whisper": modules["faster_whisper"],
    }
    if include_hardware:
        checks["input_device"] = bool(devices)
    return {
        "available": all(checks.values()),
        "checks": checks,
        "input_devices": devices,
        "hardware_error": hardware_error,
        "configuration": {
            "voice": config.get("tts", {}).get("voice"),
            "stt_model": config.get("stt", {}).get("model"),
            "capture_threshold": config.get("capture", {}).get("energy_threshold"),
            "barge_threshold": config.get("barge_in", {}).get("absolute_threshold"),
        },
        "sessions": session_summary(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="voice-diagnostics")
    sub = parser.add_subparsers(dest="command", required=True)
    diagnostic = sub.add_parser("doctor")
    diagnostic.add_argument("--offline", action="store_true")
    calibration = sub.add_parser("calibrate")
    calibration.add_argument("--device", type=int)
    calibration.add_argument("--seconds", type=float, default=3.0)
    sub.add_parser("sessions")
    args = parser.parse_args()
    if args.command == "doctor":
        result = doctor(not args.offline)
    elif args.command == "calibrate":
        result = calibrate(args.device, args.seconds)
    else:
        result = session_summary()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if args.command != "doctor" or result["available"] or args.offline else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"state": "error", "error": f"{type(error).__name__}: {error}"}, ensure_ascii=False, indent=2))
        raise SystemExit(3)
