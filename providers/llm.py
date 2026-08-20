"""LLM provayderlari. Agentlar hech qachon API'ni to'g'ridan-to'g'ri chaqirmaydi."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import httpx

from config.settings import Settings, get_settings
from providers._gemini import gemini_post

log = logging.getLogger("provider.llm")


class LLMProvider(ABC):
    name = "base"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 1500,
        temperature: float = 0.7,
    ) -> str:
        ...


class AnthropicProvider(LLMProvider):
    name = "anthropic"
    API_URL = "https://api.anthropic.com/v1/messages"

    async def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 1500,
        temperature: float = 0.7,
    ) -> str:
        self.settings.require("anthropic_api_key")
        payload = {
            "model": self.settings.anthropic_model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            resp = await client.post(
                self.API_URL,
                headers={
                    "x-api-key": self.settings.anthropic_api_key or "",
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
        return "".join(parts).strip()


class OpenAIProvider(LLMProvider):
    name = "openai"
    API_URL = "https://api.openai.com/v1/chat/completions"

    async def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 1500,
        temperature: float = 0.7,
    ) -> str:
        self.settings.require("openai_api_key")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            resp = await client.post(
                self.API_URL,
                headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
                json={
                    "model": self.settings.openai_model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        return (data["choices"][0]["message"]["content"] or "").strip()


class GeminiProvider(LLMProvider):
    """Google Gemini — bepul tarifi bor (aistudio.google.com dan kalit olinadi).

    Bitta kalit bilan ham matn, ham rasm ishlaydi: LLM_PROVIDER=gemini va
    IMAGE_PROVIDER=gemini uchun aynan shu GEMINI_API_KEY ishlatiladi.
    """

    name = "gemini"
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    async def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 1500,
        temperature: float = 0.7,
    ) -> str:
        self.settings.require("gemini_api_key")
        payload: dict = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        url = f"{self.BASE_URL}/{self.settings.gemini_text_model}:generateContent"
        data = await gemini_post(
            url,
            payload,
            api_key=self.settings.gemini_api_key or "",
            timeout=self.settings.request_timeout,
        )

        candidates = data.get("candidates") or []
        if not candidates:
            reason = (data.get("promptFeedback") or {}).get("blockReason", "noma'lum sabab")
            raise RuntimeError(f"Gemini javob qaytarmadi ({reason})")

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            finish = candidates[0].get("finishReason", "?")
            raise RuntimeError(f"Gemini bo'sh matn qaytardi (finishReason={finish})")
        return text


class FakeLLMProvider(LLMProvider):
    """Test/dry-run uchun: tarmoqqa chiqmaydi."""

    name = "fake"

    def __init__(self, settings: Settings, responses: list[str] | None = None) -> None:
        super().__init__(settings)
        self.responses = responses or []
        self.calls: list[dict] = []

    async def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 1500,
        temperature: float = 0.7,
    ) -> str:
        self.calls.append({"prompt": prompt, "system": system})
        if self.responses:
            return self.responses.pop(0)
        # Prompt turiga qarab minimal, lekin to'g'ri formatdagi javob
        if "JSON" in prompt and "topic" in prompt:
            return (
                '{"topic": "Test mavzu", "angle": "amaliy", '
                '"summary": "Qisqa xulosa", "key_points": ["birinchi fakt", "ikkinchi fakt"], '
                '"source_indexes": [1]}'
            )
        # Uzunligi haqiqiy postga yaqin — shunda Quality Agent qoidalari
        # dry-run paytida ham mazmunli ishlaydi.
        return (
            "🏃 Birinchi haftada eng ko'p qilinadigan xato — kerakdan tez yugurish.\n\n"
            "Bu matnni fake provider yozdi: tarmoqqa chiqilmadi, kalit sarflanmadi. "
            "Haqiqiy LLM ulanganda aynan shu joyda tayyor post turadi va uzunligi "
            "ham shunga yaqin bo'ladi, shuning uchun sifat tekshiruvi hozir ham "
            "haqiqiy sharoitdagidek ishlaydi.\n\n"
            "1. Birinchi hafta — 20 daqiqa, gaplashib yugura oladigan tezlikda\n"
            "2. Har hafta masofani 10 foizdan ko'p oshirmang\n"
            "3. Haftada kamida bir kun to'liq dam oling\n\n"
            "Og'riq paydo bo'lsa — davom etmang, dam bering.\n\n"
            "Siz haftasiga necha marta chiqasiz?"
        )


_REGISTRY: dict[str, type[LLMProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "fake": FakeLLMProvider,
}


def get_llm_provider(name: str | None = None, settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    key = (name or settings.llm_provider).lower()
    if key not in _REGISTRY:
        raise ValueError(
            f"Noma'lum LLM provider: '{key}'. Mavjudlari: {', '.join(_REGISTRY)}"
        )
    return _REGISTRY[key](settings)


def register_llm_provider(name: str, cls: type[LLMProvider]) -> None:
    _REGISTRY[name.lower()] = cls
