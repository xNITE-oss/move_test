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
import re
from typing import Any

import httpx

log = logging.getLogger("provider.gemini")

#: Google eski modelni yopganda javobda yangisini aytadi:
#: "This model models/X is no longer available … Please update your code to use models/Y"
_SUGGESTED_MODEL = re.compile(r"use\s+models/([A-Za-z0-9._-]+)")

#: 400 xatosi ham kalit, ham noto'g'ri so'rov sababli bo'lishi mumkin.
#: Faqat kalitga o'xshagan xabar bo'lsa boshqa autentifikatsiya usuli sinaladi.
_AUTH_HINT = re.compile(r"api[ _-]?key|credential|authentic|unauthorized", re.I)

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
    url: str,
    payload: dict[str, Any],
    *,
    api_key: str,
    timeout: int = 60,
    _model_retry: bool = True,
) -> dict[str, Any]:
    """Gemini API'ga POST yuboradi va JSON qaytaradi.

    - Autentifikatsiya xatosi (400/401/403) bo'lsa boshqa usulni sinaydi.
    - 404 "model endi mavjud emas" bo'lsa, Google taklif qilgan modelga
      avtomatik o'tib, bir marta qayta uradi (Google modellarni tez-tez yangilaydi).
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

            body = resp.text[:400].replace("\n", " ")
            errors.append(f"{method}: {resp.status_code} {body}")

            if resp.status_code == 404 and _model_retry:
                new_url = _swap_model(url, body)
                if new_url:
                    log.warning(
                        "Model eskirgan. Google taklifi bo'yicha qayta urinilmoqda: %s\n"
                        "Doimiy yechim: GEMINI_TEXT_MODEL ni yangilang.",
                        new_url.rsplit("/", 1)[-1].split(":")[0],
                    )
                    return await gemini_post(
                        new_url, payload, api_key=api_key,
                        timeout=timeout, _model_retry=False,
                    )

            auth_problem = resp.status_code in (401, 403) or (
                resp.status_code == 400 and bool(_AUTH_HINT.search(body))
            )
            if not auth_problem:
                # So'rovning o'zida muammo — boshqa kalit usuli yordam bermaydi
                raise RuntimeError(f"Gemini xatosi {resp.status_code}: {body}")

    raise RuntimeError(
        "Gemini kaliti qabul qilinmadi. Sinalgan usullar:\n  " + "\n  ".join(errors)
    )


def _swap_model(url: str, error_body: str) -> str | None:
    """Xato matnidan taklif qilingan modelni olib, URL'dagi model nomini almashtiradi."""
    match = _SUGGESTED_MODEL.search(error_body)
    if not match:
        return None
    suggested = match.group(1)
    current = url.rsplit("/models/", 1)[-1].split(":")[0] if "/models/" in url else ""
    if not current or suggested == current:
        return None
    return url.replace(f"/models/{current}", f"/models/{suggested}", 1)


def reset_preferred() -> None:
    """Testlar uchun."""
    global _preferred
    _preferred = None
