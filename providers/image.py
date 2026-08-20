"""Rasm generatsiya provayderlari (Gemini / Nano Banana).

DIQQAT: GeminiImageProvider skeleton sifatida yozilgan. Endpoint va model nomi
o'zgarishi mumkin — ishlatishdan oldin Google AI hujjatlari bilan solishtiring.
Standart holatda IMAGE_PROVIDER=none, ya'ni bu qatlam umuman chaqirilmaydi.
"""

from __future__ import annotations

import base64
import logging
from abc import ABC, abstractmethod
from pathlib import Path

from config.settings import Settings, get_settings
from providers._gemini import gemini_post

log = logging.getLogger("provider.image")


class ImageProvider(ABC):
    name = "base"
    available = True

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    async def generate(self, prompt: str, out_path: Path) -> Path | None:
        """Rasm yaratib, `out_path` ga yozadi va yo'lni qaytaradi."""


class GeminiImageProvider(ImageProvider):
    name = "gemini"
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    async def generate(self, prompt: str, out_path: Path) -> Path | None:
        self.settings.require("gemini_api_key")
        model = self.settings.gemini_image_model
        url = f"{self.BASE_URL}/{model}:generateContent"

        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        data = await gemini_post(
            url,
            payload,
            api_key=self.settings.gemini_api_key or "",
            timeout=self.settings.request_timeout,
        )

        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_bytes(base64.b64decode(inline["data"]))
                    log.info("Rasm saqlandi: %s", out_path)
                    return out_path

        log.warning("Gemini javobida rasm ma'lumoti topilmadi")
        return None


class FakeImageProvider(ImageProvider):
    """1x1 PNG qaytaradi — pipeline'ni tarmoqsiz sinash uchun."""

    name = "fake"
    _PNG = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )

    async def generate(self, prompt: str, out_path: Path) -> Path | None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(self._PNG)
        return out_path


class NullImageProvider(ImageProvider):
    """IMAGE_PROVIDER=none — rasm bosqichi butunlay o'tkazib yuboriladi."""

    name = "none"
    available = False

    async def generate(self, prompt: str, out_path: Path) -> Path | None:
        log.info("Image provider o'chirilgan (IMAGE_PROVIDER=none)")
        return None


_REGISTRY: dict[str, type[ImageProvider]] = {
    "gemini": GeminiImageProvider,
    "fake": FakeImageProvider,
    "none": NullImageProvider,
}


def get_image_provider(name: str | None = None, settings: Settings | None = None) -> ImageProvider:
    settings = settings or get_settings()
    key = (name or settings.image_provider).lower()
    return _REGISTRY.get(key, NullImageProvider)(settings)


def register_image_provider(name: str, cls: type[ImageProvider]) -> None:
    _REGISTRY[name.lower()] = cls
