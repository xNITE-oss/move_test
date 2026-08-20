"""Matnni ovozga aylantirish (ElevenLabs).

Standart holatda TTS_PROVIDER=none. Yoqish uchun .env ga
TTS_PROVIDER=elevenlabs, ELEVENLABS_API_KEY va ELEVENLABS_VOICE_ID yozing.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from config.settings import Settings, get_settings

log = logging.getLogger("provider.tts")


class TTSProvider(ABC):
    name = "base"
    available = True

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    async def synthesize(self, text: str, out_path: Path, *, voice_id: str | None = None) -> Path | None:
        ...


class ElevenLabsProvider(TTSProvider):
    name = "elevenlabs"
    BASE_URL = "https://api.elevenlabs.io/v1/text-to-speech"

    async def synthesize(
        self, text: str, out_path: Path, *, voice_id: str | None = None
    ) -> Path | None:
        self.settings.require("elevenlabs_api_key")
        voice = voice_id or self.settings.elevenlabs_voice_id
        if not voice:
            raise ValueError("ELEVENLABS_VOICE_ID o'rnatilmagan")

        async with httpx.AsyncClient(timeout=self.settings.request_timeout * 3) as client:
            resp = await client.post(
                f"{self.BASE_URL}/{voice}",
                headers={
                    "xi-api-key": self.settings.elevenlabs_api_key or "",
                    "accept": "audio/mpeg",
                    "content-type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": self.settings.elevenlabs_model,
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                },
            )
            resp.raise_for_status()

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(resp.content)
        log.info("Audio saqlandi: %s", out_path)
        return out_path


class FakeTTSProvider(TTSProvider):
    name = "fake"

    async def synthesize(
        self, text: str, out_path: Path, *, voice_id: str | None = None
    ) -> Path | None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x00")  # bo'sh mp3 sarlavhasi
        return out_path


class NullTTSProvider(TTSProvider):
    name = "none"
    available = False

    async def synthesize(
        self, text: str, out_path: Path, *, voice_id: str | None = None
    ) -> Path | None:
        log.info("TTS provider o'chirilgan (TTS_PROVIDER=none)")
        return None


_REGISTRY: dict[str, type[TTSProvider]] = {
    "elevenlabs": ElevenLabsProvider,
    "fake": FakeTTSProvider,
    "none": NullTTSProvider,
}


def get_tts_provider(name: str | None = None, settings: Settings | None = None) -> TTSProvider:
    settings = settings or get_settings()
    key = (name or settings.tts_provider).lower()
    return _REGISTRY.get(key, NullTTSProvider)(settings)


def register_tts_provider(name: str, cls: type[TTSProvider]) -> None:
    _REGISTRY[name.lower()] = cls
