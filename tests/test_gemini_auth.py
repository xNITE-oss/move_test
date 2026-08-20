"""Gemini autentifikatsiyasi: `AIza...` va yangi `AQ....` kalitlari uchun fallback.

Google 2026 yilda kalit formatini o'zgartirdi va turli yo'llar turli usulni
qabul qiladi. gemini_post uchta usulni ketma-ket sinaydi — shu yerda tekshiriladi.
Tarmoqqa chiqilmaydi: httpx.AsyncClient soxta klass bilan almashtiriladi.
"""

from __future__ import annotations

import pytest

from providers import _gemini


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or str(payload or "")

    def json(self):
        return self._payload


class FakeClient:
    """POST chaqiruvlarini yozib boradi va oldindan berilgan javoblarni qaytaradi."""

    calls: list[dict] = []

    def __init__(self, responses):
        self.responses = list(responses)

    def __call__(self, *a, **kw):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, json=None):
        FakeClient.calls.append({"url": url, "headers": headers or {}})
        return self.responses.pop(0)


@pytest.fixture(autouse=True)
def reset():
    _gemini.reset_preferred()
    FakeClient.calls = []
    yield
    _gemini.reset_preferred()


def install(monkeypatch, responses):
    client = FakeClient(responses)
    monkeypatch.setattr(_gemini.httpx, "AsyncClient", client)


URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
OK = {"candidates": [{"content": {"parts": [{"text": "salom"}]}}]}


async def test_header_method_works_first(monkeypatch):
    install(monkeypatch, [FakeResponse(200, OK)])

    data = await _gemini.gemini_post(URL, {}, api_key="AQ.test")

    assert data == OK
    assert len(FakeClient.calls) == 1
    assert FakeClient.calls[0]["headers"]["x-goog-api-key"] == "AQ.test"


async def test_falls_back_to_query_param(monkeypatch):
    install(monkeypatch, [FakeResponse(401, text="ACCESS_TOKEN_TYPE_UNSUPPORTED"),
                          FakeResponse(200, OK)])

    data = await _gemini.gemini_post(URL, {}, api_key="AQ.test")

    assert data == OK
    assert len(FakeClient.calls) == 2
    assert "key=AQ.test" in FakeClient.calls[1]["url"]


async def test_falls_back_to_bearer(monkeypatch):
    install(monkeypatch, [FakeResponse(401), FakeResponse(403), FakeResponse(200, OK)])

    data = await _gemini.gemini_post(URL, {}, api_key="AQ.test")

    assert data == OK
    assert FakeClient.calls[2]["headers"]["Authorization"] == "Bearer AQ.test"


async def test_successful_method_is_remembered(monkeypatch):
    install(monkeypatch, [FakeResponse(401), FakeResponse(200, OK)])
    await _gemini.gemini_post(URL, {}, api_key="AQ.test")

    # ikkinchi chaqiruvda darhol ishlagan usul ishlatiladi
    install(monkeypatch, [FakeResponse(200, OK)])
    await _gemini.gemini_post(URL, {}, api_key="AQ.test")

    assert "key=AQ.test" in FakeClient.calls[-1]["url"]


async def test_all_methods_fail_gives_clear_error(monkeypatch):
    install(monkeypatch, [FakeResponse(401, text="bad key")] * 3)

    with pytest.raises(RuntimeError) as exc:
        await _gemini.gemini_post(URL, {}, api_key="AQ.bad")

    message = str(exc.value)
    assert "header" in message and "query" in message and "bearer" in message


async def test_server_error_is_not_retried(monkeypatch):
    install(monkeypatch, [FakeResponse(500, text="internal")])

    with pytest.raises(RuntimeError, match="500"):
        await _gemini.gemini_post(URL, {}, api_key="AQ.test")

    assert len(FakeClient.calls) == 1


async def test_outdated_model_switches_to_suggested_one(monkeypatch):
    """Google eski modelni yopganda, javobdagi yangi model bilan qayta uriladi."""
    err = (
        '{"error":{"code":404,"message":"This model models/gemini-2.5-flash is no '
        'longer available to new users. Please update your code to use '
        'models/gemini-3.6-flash for the latest features","status":"NOT_FOUND"}}'
    )
    install(monkeypatch, [FakeResponse(404, text=err), FakeResponse(200, OK)])

    data = await _gemini.gemini_post(URL, {}, api_key="AQ.test")

    assert data == OK
    assert "gemini-2.5-flash" in FakeClient.calls[0]["url"]
    assert "gemini-3.6-flash" in FakeClient.calls[1]["url"]


async def test_404_without_suggestion_raises(monkeypatch):
    install(monkeypatch, [FakeResponse(404, text='{"error":"not found"}')])

    with pytest.raises(RuntimeError, match="404"):
        await _gemini.gemini_post(URL, {}, api_key="AQ.test")


async def test_model_swap_happens_only_once(monkeypatch):
    """Yangi model ham 404 bersa — cheksiz sikl bo'lmasin."""
    err = ('{"error":{"message":"models/x is no longer available. '
           'Please update your code to use models/gemini-9-flash"}}')
    install(monkeypatch, [FakeResponse(404, text=err)] * 4)

    with pytest.raises(RuntimeError, match="404"):
        await _gemini.gemini_post(URL, {}, api_key="AQ.test")

    assert len(FakeClient.calls) == 2


async def test_empty_key_is_rejected():
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        await _gemini.gemini_post(URL, {}, api_key="")
