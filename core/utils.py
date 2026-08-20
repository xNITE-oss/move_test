"""Kichik yordamchilar."""

from __future__ import annotations

import json
import re
from typing import Any

_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)


def extract_json(text: str) -> Any:
    """LLM javobidan JSON ajratib oladi (```json blok yoki xom JSON)."""
    if not text:
        raise ValueError("Bo'sh javob")

    match = _JSON_BLOCK.search(text)
    candidate = match.group(1) if match else None

    if candidate is None:
        start = min(
            (i for i in (text.find("{"), text.find("[")) if i != -1),
            default=-1,
        )
        if start == -1:
            raise ValueError(f"Javobda JSON topilmadi: {text[:200]!r}")
        end = max(text.rfind("}"), text.rfind("]"))
        candidate = text[start : end + 1]

    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON parse xatosi: {exc}. Xom javob: {text[:300]!r}") from exc


def truncate(text: str, limit: int) -> str:
    """Matnni chegaraga sig'diradi, so'z o'rtasidan kesmaydi."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in ("\n\n", "\n", ". ", " "):
        idx = cut.rfind(sep)
        if idx > limit * 0.6:
            return cut[:idx].rstrip()
    return cut.rstrip()


def normalize_hashtags(tags: list[str]) -> list[str]:
    out = []
    for tag in tags:
        tag = tag.strip()
        if not tag:
            continue
        out.append(tag if tag.startswith("#") else f"#{tag}")
    return out


def count_links(text: str) -> int:
    return len(re.findall(r"https?://", text))


def strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
    return text.strip()
