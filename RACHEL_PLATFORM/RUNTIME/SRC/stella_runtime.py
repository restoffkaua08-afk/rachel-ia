from __future__ import annotations

import argparse
import base64
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT / "RACHEL_PLATFORM" / "CONFIG" / "voice.profiles.json"
WRAPPER = ROOT / "RACHEL_PLATFORM" / "SCRIPTS" / "rachel.ps1"


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(config: dict[str, Any]) -> None:
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def speech_text(text: str) -> str:
    text = re.sub(r"```.*?```", " Trecho de codigo omitido na fala. ", text, flags=re.S)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"https?://\S+", " link disponivel na tela ", text)
    text = re.sub(r"[#>*_~|]", " ", text)
    text = re.sub(r"\[(.*?)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()

    pronunciations = {
        r"\bRachel\b": "Rêitchel",
        r"\bRACHEL\b": "Rêitchel",
        r"\bGitHub\b": "Guít Rãb",
        r"\bREADME\b": "Rídmi",
        r"\bAPI\b": "A P I",
        r"\bIA\b": "I A",
    }

    for pattern, pronunciation in pronunciations.items():
        text = re.sub(pattern, pronunciation, text)

    return text[:6000]


def encoded_powershell(script: str) -> list[str]:
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]


def windows_voices() -> list[dict[str, str]]:
    script = r'''
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.GetInstalledVoices() | ForEach-Object {
  [PSCustomObject]@{
    name = $_.VoiceInfo.Name
    culture = $_.VoiceInfo.Culture.Name
    gender = $_.VoiceInfo.Gender.ToString()
    age = $_.VoiceInfo.Age.ToString()
  }
} | ConvertTo-Json -Compress
'''
    result = subprocess.run(encoded_powershell(script), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Windows speech voices unavailable")
    payload = json.loads(result.stdout.strip() or "[]")
    return payload if isinstance(payload, list) else [payload]


def select_voice(name: str) -> dict[str, Any]:
    voices = windows_voices()
    if name not in {voice["name"] for voice in voices}:
        raise ValueError(f"Voice not installed: {name}")
    config = load_config()
    config["tts"]["voice"] = name
    save_config(config)
    return {"selected": name}


def speak(text: str, profile_name: str | None = None) -> None:
    config = load_config()
    profile_name = profile_name or config["default_profile"]
    profile = config["profiles"][profile_name]
    voice = config["tts"].get("voice")
    clean = speech_text(text)
    with tempfile.TemporaryDirectory(prefix="rachel-stella-") as directory:
        text_path = Path(directory) / "speech.txt"
        text_path.write_text(clean, encoding="utf-8")
        escaped_path = str(text_path).replace("'", "''")
        escaped_voice = str(voice or "").replace("'", "''")
        script = f'''
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Rate = {int(profile['rate'])}
$s.Volume = {int(profile['volume'])}
$voice = '{escaped_voice}'
if ($voice) {{ $s.SelectVoice($voice) }}
$text = [System.IO.File]::ReadAllText('{escaped_path}', [System.Text.Encoding]::UTF8)
$s.Speak($text)
$s.Dispose()
'''
        result = subprocess.run(encoded_powershell(script), capture_output=True, timeout=180)
        if result.returncode != 0:
            raise RuntimeError("Speech synthesis failed")


def devices() -> list[dict[str, Any]]:
    import sounddevice as sd
    output = []
    for index, device in enumerate(sd.query_devices()):
        if int(device["max_input_channels"]) > 0:
            output.append({"id": index, "name": device["name"], "inputs": int(device["max_input_channels"]), "sample_rate": float(device["default_samplerate"])})
    return output


def capture_utterance(device: int | None = None) -> Path:
    import numpy as np
    import sounddevice as sd

    config = load_config()["capture"]
    rate = int(config["sample_rate"])
    threshold = float(config["energy_threshold"])
    block_seconds = 0.1
    blocksize = int(rate * block_seconds)
    max_blocks = int(float(config["maximum_utterance_seconds"]) / block_seconds)
    start_blocks = int(float(config["start_timeout_seconds"]) / block_seconds)
    silence_blocks = int(float(config["silence_seconds"]) / block_seconds)
    frames: list[Any] = []
    speaking = False
    silent = 0
    waited = 0

    print("Stella ouvindo...", file=sys.stderr)
    with sd.InputStream(samplerate=rate, channels=1, dtype="float32", blocksize=blocksize, device=device) as stream:
        while len(frames) < max_blocks:
            data, overflowed = stream.read(blocksize)
            if overflowed:
                print("Aviso: audio overflow", file=sys.stderr)
            rms = math.sqrt(float(np.mean(np.square(data))))
            if not speaking:
                waited += 1
                if rms >= threshold:
                    speaking = True
                    frames.append(data.copy())
                elif waited >= start_blocks:
                    raise TimeoutError("No speech detected")
                continue
            frames.append(data.copy())
            silent = silent + 1 if rms < threshold else 0
            if silent >= silence_blocks:
                break

    if not frames:
        raise RuntimeError("No audio captured")
    audio = np.concatenate(frames, axis=0)
    pcm = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
    handle = tempfile.NamedTemporaryFile(prefix="rachel-stella-", suffix=".wav", delete=False)
    handle.close()
    path = Path(handle.name)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(rate); wav.writeframes(pcm.tobytes())
    return path


_model = None


def transcribe(path: Path) -> str:
    global _model
    from faster_whisper import WhisperModel
    stt = load_config()["stt"]
    if _model is None:
        print(f"Carregando Whisper {stt['model']}...", file=sys.stderr)
        _model = WhisperModel(stt["model"], device=stt["device"], compute_type=stt["compute_type"])
    segments, _ = _model.transcribe(str(path), language=stt["language"], vad_filter=True, beam_size=5)
    return " ".join(segment.text.strip() for segment in segments).strip()


def ask_ned(text: str) -> dict[str, Any]:
    instruction = load_config()["profiles"][load_config()["default_profile"]]["instruction"]
    prompt = f"{instruction}\nResponda para uma conversa falada. Evite Markdown desnecessario.\nUsuario: {text}"
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(WRAPPER), "cognitive", "chat", prompt],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Ned did not answer")
    payload = json.loads(result.stdout)
    return payload


def listen_once(device: int | None, profile: str | None, speak_answer: bool = True) -> dict[str, Any]:
    path = capture_utterance(device)
    try:
        text = transcribe(path)
    finally:
        path.unlink(missing_ok=True)
    if not text:
        raise RuntimeError("Speech could not be transcribed")
    print(f"Voce: {text}", file=sys.stderr)
    response = ask_ned(text)
    answer = response["message"]["content"]
    print(f"Rachel: {answer}", file=sys.stderr)
    if speak_answer:
        speak(answer, profile)
    return {"transcript": text, "answer": answer, "conversation_id": response.get("conversation_id"), "quality": response.get("quality")}


def conversation(device: int | None, profile: str | None) -> int:
    stop_commands = {item.casefold() for item in load_config()["commands"]["stop"]}
    speak("Stella ativada. Pode falar.", profile)
    while True:
        try:
            path = capture_utterance(device)
            try:
                text = transcribe(path)
            finally:
                path.unlink(missing_ok=True)
            if not text:
                continue
            print(f"Voce: {text}")
            normalized = re.sub(r"[^a-zÃ¡Ã Ã¢Ã£Ã©ÃªÃ­Ã³Ã´ÃµÃºÃ§ ]", "", text.casefold()).strip()
            if normalized in stop_commands:
                speak("Conversa encerrada.", profile)
                return 0
            response = ask_ned(text)
            answer = response["message"]["content"]
            print(f"Rachel: {answer}")
            speak(answer, profile)
            time.sleep(0.25)
        except TimeoutError:
            continue
        except KeyboardInterrupt:
            print("Conversa interrompida.")
            return 130


def main() -> int:
    parser = argparse.ArgumentParser(prog="stella")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("devices")
    sub.add_parser("voices")
    choose = sub.add_parser("select-voice"); choose.add_argument("name")
    sample = sub.add_parser("sample"); sample.add_argument("--voice"); sample.add_argument("--profile", default="natural"); sample.add_argument("--text", default="OlÃ¡, KauÃ£. Eu sou Rachel. Minha voz estÃ¡ pronta para acompanhar nossos projetos.")
    once = sub.add_parser("listen-once"); once.add_argument("--device", type=int); once.add_argument("--profile", default="natural"); once.add_argument("--no-speech", action="store_true")
    talk = sub.add_parser("conversation"); talk.add_argument("--device", type=int); talk.add_argument("--profile", default="natural")
    args = parser.parse_args()
    try:
        if args.action == "devices": output = devices()
        elif args.action == "voices": output = windows_voices()
        elif args.action == "select-voice": output = select_voice(args.name)
        elif args.action == "sample":
            if args.voice: select_voice(args.voice)
            speak(args.text, args.profile); output = {"spoken": True, "profile": args.profile, "voice": load_config()["tts"]["voice"]}
        elif args.action == "listen-once": output = listen_once(args.device, args.profile, not args.no_speech)
        else: return conversation(args.device, args.profile)
    except Exception as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 3
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
