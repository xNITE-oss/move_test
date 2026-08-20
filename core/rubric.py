"""Rubrika konfiguratsiyasi: config/rubrics/*.yaml.

Har bir rubrika alohida YAML fayl. Yangi rubrika qo'shish = yangi fayl yaratish,
kodga tegish shart emas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from config.settings import BASE_DIR

RUBRICS_DIR = BASE_DIR / "config" / "rubrics"

DEFAULT_PIPELINE = ["research", "writer", "image", "audio", "quality", "publisher"]


class RubricNotFound(FileNotFoundError):
    pass


@dataclass
class RubricConfig:
    key: str
    raw: dict[str, Any] = field(default_factory=dict)

    # -- asosiy maydonlar ---------------------------------------------------
    @property
    def name(self) -> str:
        return self.raw.get("name", self.key)

    @property
    def enabled(self) -> bool:
        return bool(self.raw.get("enabled", True))

    @property
    def language(self) -> str:
        return self.raw.get("language", "uz")

    @property
    def pipeline(self) -> list[str]:
        return list(self.raw.get("pipeline") or DEFAULT_PIPELINE)

    @property
    def max_retries(self) -> int:
        return int(self.raw.get("max_retries", 2))

    @property
    def image_required(self) -> bool:
        """True — rasmsiz post chiqmasin (ImageAgent xatosi pipeline'ni to'xtatadi)."""
        return bool(self.raw.get("image_required", False))

    @property
    def audio_required(self) -> bool:
        """True — audiosiz post chiqmasin."""
        return bool(self.raw.get("audio_required", False))

    @property
    def schedule(self) -> dict[str, Any]:
        return dict(self.raw.get("schedule") or {})

    @property
    def cron(self) -> str | None:
        return self.schedule.get("cron")

    # -- agent sozlamalari ---------------------------------------------------
    def agent_cfg(self, agent_name: str) -> dict[str, Any]:
        return dict((self.raw.get("agents") or {}).get(agent_name) or {})

    def is_agent_enabled(self, agent_name: str) -> bool:
        cfg = self.agent_cfg(agent_name)
        # Sozlama umuman yozilmagan bo'lsa — agent o'chirilgan hisoblanadi.
        if not cfg:
            return False
        return bool(cfg.get("enabled", True))

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)


def rubric_path(key: str) -> Path:
    return RUBRICS_DIR / f"{key}.yaml"


def load_rubric(key: str) -> RubricConfig:
    path = rubric_path(key)
    if not path.exists():
        available = ", ".join(list_rubric_keys()) or "(bo'sh)"
        raise RubricNotFound(
            f"'{key}' rubrikasi topilmadi: {path}. Mavjudlari: {available}"
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return RubricConfig(key=key, raw=data)


def list_rubric_keys() -> list[str]:
    if not RUBRICS_DIR.exists():
        return []
    return sorted(p.stem for p in RUBRICS_DIR.glob("*.yaml"))


def load_all_rubrics(only_enabled: bool = True) -> list[RubricConfig]:
    out = []
    for key in list_rubric_keys():
        rubric = load_rubric(key)
        if only_enabled and not rubric.enabled:
            continue
        out.append(rubric)
    return out
