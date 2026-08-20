"""Prompt shablonlari `prompts/*.md` ichida — kodga tegmasdan tahrirlanadi."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from config.settings import BASE_DIR

PROMPTS_DIR = BASE_DIR / "prompts"

_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


@lru_cache(maxsize=32)
def _read(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt shabloni topilmadi: {path}")
    return path.read_text(encoding="utf-8")


def load_prompt(name: str, **values: object) -> str:
    """`{{var}}` placeholderlarni almashtiradi. Berilmaganlari bo'sh qoladi."""
    text = _read(name)
    return _PLACEHOLDER.sub(lambda m: str(values.get(m.group(1), "")), text)


def clear_cache() -> None:
    _read.cache_clear()
