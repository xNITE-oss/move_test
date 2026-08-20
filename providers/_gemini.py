"""Gemini API uchun umumiy so'rov yuborgich (matn va rasm providerlari ishlatadi).

Nega alohida modul: Google 2026 yilda API kalit formatini `AIza...` dan `AQ....`
ga o'tkazdi va turli endpointlar turli autentifikatsiya usulini qabul qiladi.
Shuning uchun uchta usul ketma-ket sinaladi — qaysi biri ishlasa, o'sha ishlatiladi:

    1. x-goog-api-key sarlavhasi   (rasmiy SDK shu usulni ishlatadi)
    2. ?key=... so'rov parametri   (eski, lekin hali qo'llab-quvvatlanadi)
    3. Authorization: Bearer       (AQ. kalitlar uchun ba'zi yo'llarda kerak)

Bitta usul ishlagach, keyingi chaqiruvlarda o'sha usul birinchi bo'lib sinaladi.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger("provider.gemini")

#: qaysi usul oxirgi marta ishlagani (jarayon davomida eslab qolinadi)
_preferred: str | None = None

_METHODS = ("header", "query", "bearer")


def _build(method: str, url: str, api_key: str) -> tuple[str, dict[str, str]]:
    headers = {"content-type": "application/json"}
    if method == "header":
        headers["x-goog-api-key"] = api_key
        return url, headers
    if method == "query":
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}key={api_key}", headers
    headers["Authorization"] = f"Bearer {api_key}"
    return url, headers


def _order() -> list[str]:
    if _preferred and _preferred in _METHODS:
        return [_preferred] + [m for m in _METHODS if m != _preferred]
    return list(_METHODS)


async def gemini_post(
    url: str, payload: dict[str, Any], *, api_key: str, timeout: int = 60
) -> dict[str, Any]:
    """Gemini API'ga POST yuboradi va JSON qaytaradi.

    Autentifikatsiya xatosi (400/401/403) bo'lsa boshqa usulni sinaydi.
    Boshqa xatolar darhol ko'tariladi — ular kalit bilan bog'liq emas.
    """
    global _preferred
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY berilmagan")

    errors: list[str] = []
    async with httpx.AsyncClient(timeout=timeout) as client:
        for method in _order():
            target, headers = _build(method, url, api_key)
            resp = await client.post(target, headers=headers, json=payload)

            if resp.status_code < 400:
                if _preferred != method:
                    log.info("Gemini autentifikatsiyasi: '%s' usuli ishladi", method)
                    _preferred = method
                return resp.json()

            body = resp.text[:250].replace("\n", " ")
            errors.append(f"{method}: {resp.status_code} {body}")

            if resp.status_code not in (400, 401, 403):
                raise RuntimeError(f"Gemini xatosi {resp.status_code}: {body}")

    raise RuntimeError(
        "Gemini kaliti qabul qilinmadi. Sinalgan usullar:\n  " + "\n  ".join(errors)
    )


def reset_preferred() -> None:
    """Testlar uchun."""
    global _preferred
    _preferred = None
