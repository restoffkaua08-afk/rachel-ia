from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True, slots=True)
class Settings:
    home: Path
    model_provider: str
    model_name: str
    model_base_url: str
    model_api_key: str
    model_timeout_seconds: int
    api_host: str
    api_port: int
    api_token: str
    log_level: str

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "Settings":
        load_dotenv(env_file or Path(".env"))
        return cls(
            home=Path(os.getenv("RACHEL_HOME", ".rachel")).expanduser().resolve(),
            model_provider=os.getenv("RACHEL_MODEL_PROVIDER", "mock"),
            model_name=os.getenv("RACHEL_MODEL_NAME", "rachel-mock-v1"),
            model_base_url=os.getenv("RACHEL_MODEL_BASE_URL", "").rstrip("/"),
            model_api_key=os.getenv("RACHEL_MODEL_API_KEY", ""),
            model_timeout_seconds=int(os.getenv("RACHEL_MODEL_TIMEOUT_SECONDS", "60")),
            api_host=os.getenv("RACHEL_API_HOST", "127.0.0.1"),
            api_port=int(os.getenv("RACHEL_API_PORT", "8765")),
            api_token=os.getenv("RACHEL_API_TOKEN", ""),
            log_level=os.getenv("RACHEL_LOG_LEVEL", "INFO"),
        )

    def ensure_directories(self) -> None:
        self.home.mkdir(parents=True, exist_ok=True)

