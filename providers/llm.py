"""LLM provayderlari. Agentlar hech qachon API'ni to'g'ridan-to'g'ri chaqirmaydi."""

from __future__ import annotations

import json
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
        model: str | None = None,
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
        model: str | None = None,
    ) -> str:
        self.settings.require("anthropic_api_key")
        payload = {
            "model": model or self.settings.anthropic_model,
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
        model: str | None = None,
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
                    "model": model or self.settings.openai_model,
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

    #: Eng kam chiqish budjeti — "o'ylash" yoqilganda matnga joy qolishi uchun
    MIN_OUTPUT_TOKENS = 512

    async def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 1500,
        temperature: float = 0.7,
        model: str | None = None,
    ) -> str:
        """Gemini'dan matn oladi.

        Ikki xil muammoni o'zi hal qiladi:

        1. **O'ylash budjeti.** Yangi modellar javobdan oldin ichki "thinking"
           bosqichini bajaradi va u ham chiqish budjetidan yeyiladi. Shuning uchun
           avval o'ylash o'chirilgan holda, keyin katta budjet bilan uriniladi.
        2. **Limit (429).** Bepul tarifda har bir modelning alohida kunlik limiti
           bor. Asosiy model tugasa, `GEMINI_FALLBACK_MODELS` dagi yengilroq
           modelga o'tadi — post yo'qolmaydi.
        """
        self.settings.require("gemini_api_key")
        models = [model or self.settings.gemini_text_model]
        models += [m for m in self.settings.gemini_fallback_models if m not in models]

        last_error: Exception | None = None
        for i, candidate in enumerate(models):
            try:
                return await self._complete_with_model(
                    candidate, prompt, system=system,
                    max_tokens=max_tokens, temperature=temperature,
                )
            except RuntimeError as exc:
                last_error = exc
                if "429" not in str(exc) or i + 1 >= len(models):
                    raise
                log.warning(
                    "'%s' limiti tugadi — '%s' modeliga o'tilmoqda",
                    candidate, models[i + 1],
                )
        raise last_error or RuntimeError("Gemini javob bermadi")

    async def _complete_with_model(
        self,
        model: str,
        prompt: str,
        *,
        system: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        url = f"{self.BASE_URL}/{model}:generateContent"
        budget = max(max_tokens, self.MIN_OUTPUT_TOKENS)

        attempts = [
            {"thinking": 0, "tokens": budget},
            {"thinking": None, "tokens": budget * 4},
        ]
        last_problem = ""

        for i, attempt in enumerate(attempts):
            payload: dict = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": attempt["tokens"],
                    "temperature": temperature,
                },
            }
            if attempt["thinking"] is not None:
                payload["generationConfig"]["thinkingConfig"] = {
                    "thinkingBudget": attempt["thinking"]
                }
            if system:
                payload["systemInstruction"] = {"parts": [{"text": system}]}

            try:
                data = await gemini_post(
                    url,
                    payload,
                    api_key=self.settings.gemini_api_key or "",
                    timeout=self.settings.request_timeout,
                )
            except RuntimeError as exc:
                # Limit xatosi bo'lsa qayta urinish foydasiz — yuqoriga uzatamiz,
                # u yerda boshqa modelga o'tiladi.
                if "429" in str(exc):
                    raise
                # Ba'zi modellar thinkingConfig'ni umuman qabul qilmaydi va buni
                # umumiy "invalid argument" xatosi bilan aytadi. Shuning uchun
                # o'ylash yuborilgan urinish xato bersa — usiz qayta uramiz.
                if attempt["thinking"] is not None and i + 1 < len(attempts):
                    last_problem = str(exc)[:200]
                    log.info("Model thinkingConfig'ni qabul qilmadi — usiz qayta urinilmoqda")
                    continue
                raise

            text, problem = self._extract(data)
            if text:
                return text

            last_problem = problem
            if "MAX_TOKENS" not in problem or i + 1 >= len(attempts):
                break
            log.info("Budjet yetmadi (%s) — kattaroq budjet bilan qayta urinilmoqda", problem)

        raise RuntimeError(
            f"Gemini matn qaytarmadi: {last_problem}. "
            f"Agar bu takrorlansa, rubrika YAML'ida writer.max_tokens ni oshiring."
        )

    @staticmethod
    def _extract(data: dict) -> tuple[str, str]:
        """(matn, muammo tavsifi) qaytaradi. Matn bo'sh bo'lsa sabab tushuntiriladi."""
        candidates = data.get("candidates") or []
        if not candidates:
            reason = (data.get("promptFeedback") or {}).get("blockReason", "noma'lum sabab")
            return "", f"javob bo'sh (blockReason={reason})"

        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        if text:
            return text, ""
        return "", f"bo'sh matn (finishReason={candidates[0].get('finishReason', '?')})"


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
        model: str | None = None,
    ) -> str:
        self.calls.append({"prompt": prompt, "system": system, "model": model})
        if self.responses:
            return self.responses.pop(0)
        # Prompt turiga qarab minimal, lekin to'g'ri formatdagi javob
        if '"topic"' in prompt or "source_indexes" in prompt:
            return (
                '{"topic": "Test mavzu", "angle": "amaliy", '
                '"summary": "Qisqa xulosa", "key_points": ["birinchi fakt", "ikkinchi fakt"], '
                '"source_indexes": [1]}'
            )
        if '"verdict"' in prompt:
            return '{"verdict": "pass", "score": 8.5, "issues": [], "suggestions": []}'
        # Writer: tuzilgan post. Uzunligi haqiqiy postga yaqin, shunda sifat
        # tekshiruvi dry-run paytida ham mazmunli ishlaydi.
        return json.dumps({
            "title": "🏃 Birinchi haftada eng ko'p qilinadigan xato — kerakdan tez yugurish.",
            "lead": (
                "Bu matnni fake provider yozdi: tarmoqqa chiqilmadi, kalit sarflanmadi. "
                "Haqiqiy LLM ulanganda aynan shu joyda tayyor post turadi."
            ),
            "body": [
                "1. Birinchi hafta — 20 daqiqa, gaplashib yugura oladigan tezlikda",
                "2. Har hafta masofani 10 foizdan ko'p oshirmang",
                "3. Haftada kamida bir kun to'liq dam oling",
            ],
            "takeaway": "Og'riq paydo bo'lsa — davom etmang, dam bering.",
            "cta": "Siz haftasiga necha marta chiqasiz?",
            "tags": ["running", "movespace"],
        }, ensure_ascii=False)

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
