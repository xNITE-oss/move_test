"""Barcha sozlamalar faqat environment variable orqali o'qiladi.

Hech qanday API kalit kod ichida saqlanmaydi. `.env` fayli (agar mavjud bo'lsa)
avtomatik yuklanadi, lekin u `.gitignore` ichida bo'lishi shart.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

try:  # python-dotenv ixtiyoriy — bo'lmasa oddiy env ishlatiladi
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env", override=False)
except Exception:  # pragma: no cover
    pass


class ConfigError(RuntimeError):
    """Kerakli env o'zgaruvchi topilmaganda."""


def _get(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if value is not None:
        value = value.strip()
    return value or None


def _get_bool(name: str, default: bool = False) -> bool:
    raw = _get(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on", "ha"}


def _get_int(name: str, default: int) -> int:
    raw = _get(name)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # --- LLM ---------------------------------------------------------------
    llm_provider: str = "anthropic"          # anthropic | openai | fake
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-5"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    # --- Search ------------------------------------------------------------
    search_provider: str = "tavily"          # tavily | fake
    tavily_api_key: str | None = None

    # --- Gemini (matn uchun ham, rasm uchun ham bitta kalit) -----------------
    image_provider: str = "none"             # none | gemini | fake
    gemini_api_key: str | None = None
    gemini_text_model: str = "gemini-3.5-flash"
    gemini_image_model: str = "gemini-2.5-flash-image"

    # --- Audio (keyinroq) ---------------------------------------------------
    tts_provider: str = "none"               # none | elevenlabs | fake
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str | None = None
    elevenlabs_model: str = "eleven_multilingual_v2"

    # --- Telegram -----------------------------------------------------------
    telegram_bot_token: str | None = None
    telegram_channel_id: str | None = None    # @kanal yoki -100...
    telegram_review_chat_id: str | None = None  # tasdiq uchun shaxsiy chat

    # --- Umumiy -------------------------------------------------------------
    dry_run: bool = False
    timezone: str = "Asia/Tashkent"
    log_level: str = "INFO"
    request_timeout: int = 60
    data_dir: Path = field(default_factory=lambda: BASE_DIR / "data")

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "state.db"

    @classmethod
    def load(cls) -> "Settings":
        data_dir = Path(_get("DATA_DIR") or (BASE_DIR / "data"))
        return cls(
            llm_provider=(_get("LLM_PROVIDER") or "anthropic").lower(),
            anthropic_api_key=_get("ANTHROPIC_API_KEY"),
            anthropic_model=_get("ANTHROPIC_MODEL") or "claude-sonnet-4-5",
            openai_api_key=_get("OPENAI_API_KEY"),
            openai_model=_get("OPENAI_MODEL") or "gpt-4o-mini",
            search_provider=(_get("SEARCH_PROVIDER") or "tavily").lower(),
            tavily_api_key=_get("TAVILY_API_KEY"),
            image_provider=(_get("IMAGE_PROVIDER") or "none").lower(),
            gemini_api_key=_get("GEMINI_API_KEY"),
            gemini_text_model=_get("GEMINI_TEXT_MODEL") or "gemini-3.5-flash",
            gemini_image_model=_get("GEMINI_IMAGE_MODEL") or "gemini-2.5-flash-image",
            tts_provider=(_get("TTS_PROVIDER") or "none").lower(),
            elevenlabs_api_key=_get("ELEVENLABS_API_KEY"),
            elevenlabs_voice_id=_get("ELEVENLABS_VOICE_ID"),
            elevenlabs_model=_get("ELEVENLABS_MODEL") or "eleven_multilingual_v2",
            telegram_bot_token=_get("TELEGRAM_BOT_TOKEN"),
            telegram_channel_id=_get("TELEGRAM_CHANNEL_ID"),
            telegram_review_chat_id=_get("TELEGRAM_REVIEW_CHAT_ID"),
            dry_run=_get_bool("DRY_RUN", False),
            timezone=_get("TIMEZONE") or "Asia/Tashkent",
            log_level=(_get("LOG_LEVEL") or "INFO").upper(),
            request_timeout=_get_int("REQUEST_TIMEOUT", 60),
            data_dir=data_dir,
        )

    def require(self, *names: str) -> None:
        """Kerakli maydonlar bo'sh bo'lsa — tushunarli xato beradi."""
        missing = [n for n in names if not getattr(self, n, None)]
        if missing:
            env_names = ", ".join(n.upper() for n in missing)
            raise ConfigError(
                f"Quyidagi environment variable(lar) o'rnatilmagan: {env_names}. "
                f".env.example faylidan nusxa olib, .env ga to'ldiring."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.load()


def reload_settings() -> Settings:
    """Testlarda env o'zgartirilgandan keyin qayta o'qish uchun."""
    get_settings.cache_clear()
    return get_settings()
