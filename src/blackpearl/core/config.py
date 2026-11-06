import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]

load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    yandex_music_token: str


def load_settings() -> Settings:
    token = os.getenv("YANDEX_MUSIC_TOKEN", "").strip()

    return Settings(
        yandex_music_token=token,
    )


settings = load_settings()
