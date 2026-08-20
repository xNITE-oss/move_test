"""GeminiProvider.complete — "o'ylash" (thinking) budjeti bilan bog'liq holatlar.

Yangi Gemini modellari javobdan oldin ichki o'ylash bosqichini bajaradi va u ham
chiqish budjetidan yeyiladi. Budjet yetmasa model bo'sh matn + MAX_TOKENS qaytaradi.
Shu holatlar bu yerda tekshiriladi. Tarmoqqa chiqilmaydi.
"""

from __future__ import annotations

import dataclasses

import pytest

from config.settings import Settings
from providers import llm as llm_module
from providers.llm import GeminiProvider


@pytest.fixture
def settings() -> Settings:
    return dataclasses.replace(
        Settings.load(),
        llm_provider="gemini",
        gemini_api_key="AQ.test",
        gemini_text_model="gemini-3.6-flash",
    )


def reply(text: str = "", finish: str = "STOP") -> dict:
    parts = [{"text": text}] if text else []
    return {"candidates": [{"content": {"parts": parts}, "finishReason": finish}]}


def stub(monkeypatch, responses):
    """gemini_post o'rniga soxta funksiya qo'yadi va payloadlarni yozib boradi."""
    sent: list[dict] = []
    queue = list(responses)

    async def fake_post(url, payload, *, api_key, timeout=60, **kw):
        sent.append(payload)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(llm_module, "gemini_post", fake_post)
    return sent


async def test_thinking_is_disabled_on_first_attempt(monkeypatch, settings):
    sent = stub(monkeypatch, [reply("salom")])

    out = await GeminiProvider(settings).complete("test", max_tokens=800)

    assert out == "salom"
    assert len(sent) == 1
    assert sent[0]["generationConfig"]["thinkingConfig"]["thinkingBudget"] == 0


async def test_retries_with_bigger_budget_on_max_tokens(monkeypatch, settings):
    sent = stub(monkeypatch, [reply("", "MAX_TOKENS"), reply("tayyor post")])

    out = await GeminiProvider(settings).complete("test", max_tokens=800)

    assert out == "tayyor post"
    assert len(sent) == 2
    # ikkinchi urinishda o'ylash yoqiladi va budjet kattalashadi
    assert "thinkingConfig" not in sent[1]["generationConfig"]
    assert sent[1]["generationConfig"]["maxOutputTokens"] > sent[0]["generationConfig"]["maxOutputTokens"]


async def test_retries_when_model_rejects_thinking_budget(monkeypatch, settings):
    sent = stub(monkeypatch, [
        RuntimeError("400: thinkingBudget is not supported for this model"),
        reply("ishladi"),
    ])

    out = await GeminiProvider(settings).complete("test", max_tokens=800)

    assert out == "ishladi"
    assert len(sent) == 2


async def test_small_max_tokens_is_raised_to_floor(monkeypatch, settings):
    """20 ta token so'ralsa ham, o'ylash uchun minimal budjet qo'yiladi."""
    sent = stub(monkeypatch, [reply("ha")])

    await GeminiProvider(settings).complete("test", max_tokens=20)

    assert sent[0]["generationConfig"]["maxOutputTokens"] >= GeminiProvider.MIN_OUTPUT_TOKENS


async def test_blocked_prompt_gives_clear_error(monkeypatch, settings):
    stub(monkeypatch, [{"promptFeedback": {"blockReason": "SAFETY"}}])

    with pytest.raises(RuntimeError, match="SAFETY"):
        await GeminiProvider(settings).complete("test", max_tokens=800)


async def test_persistent_max_tokens_gives_actionable_error(monkeypatch, settings):
    stub(monkeypatch, [reply("", "MAX_TOKENS"), reply("", "MAX_TOKENS")])

    with pytest.raises(RuntimeError, match="max_tokens"):
        await GeminiProvider(settings).complete("test", max_tokens=800)


async def test_system_instruction_is_passed(monkeypatch, settings):
    sent = stub(monkeypatch, [reply("ok")])

    await GeminiProvider(settings).complete("test", system="Sen muharrirsan")

    assert sent[0]["systemInstruction"]["parts"][0]["text"] == "Sen muharrirsan"


# ── limit (429) bo'lganda zaxira modelga o'tish ─────────────────────────────
async def test_falls_back_to_lighter_model_on_rate_limit(monkeypatch, settings):
    """Asosiy modelning kunlik limiti tugasa, post yo'qolmasligi kerak."""
    used: list[str] = []

    async def fake_post(url, payload, *, api_key, timeout=60, **kw):
        model = url.rsplit("/", 1)[-1].split(":")[0]
        used.append(model)
        if model == "gemini-3.5-flash":
            raise RuntimeError("Gemini limiti tugadi (429). Bepul tarifda...")
        return reply("zaxira model javobi")

    monkeypatch.setattr(llm_module, "gemini_post", fake_post)
    s = dataclasses.replace(
        settings,
        gemini_text_model="gemini-3.5-flash",
        gemini_fallback_models=("gemini-3.5-flash-lite",),
    )

    out = await GeminiProvider(s).complete("test", max_tokens=800)

    assert out == "zaxira model javobi"
    assert used == ["gemini-3.5-flash", "gemini-3.5-flash-lite"]


async def test_explicit_model_overrides_default(monkeypatch, settings):
    used: list[str] = []

    async def fake_post(url, payload, *, api_key, timeout=60, **kw):
        used.append(url.rsplit("/", 1)[-1].split(":")[0])
        return reply("ok")

    monkeypatch.setattr(llm_module, "gemini_post", fake_post)

    await GeminiProvider(settings).complete("test", model="gemini-3.5-flash-lite")

    assert used[0] == "gemini-3.5-flash-lite"


async def test_rate_limit_is_not_treated_as_thinking_problem(monkeypatch, settings):
    """429 kelganda o'sha modelda ikkinchi marta urinilmaydi."""
    calls = 0

    async def fake_post(url, payload, *, api_key, timeout=60, **kw):
        nonlocal calls
        calls += 1
        raise RuntimeError("Gemini limiti tugadi (429)")

    monkeypatch.setattr(llm_module, "gemini_post", fake_post)
    s = dataclasses.replace(settings, gemini_fallback_models=())

    with pytest.raises(RuntimeError, match="429"):
        await GeminiProvider(s).complete("test", max_tokens=800)

    assert calls == 1, "limit xatosidan keyin behuda qayta urinildi"
