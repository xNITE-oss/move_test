"""Postning tuzilgan ko'rinishi — bitta manba, ko'p chiqish formati.

Writer endi tayyor Telegram matnini emas, shu obyektni qaytaradi. Undan keyin
har bir kanal o'z formatiga o'giradi (core/render.py):

    PostContent ──┬──► Telegram matni (emoji, 900 belgi, hashtag)
                  └──► Sayt uchun Markdown/HTML (sarlavha, meta, teglar)

Shu sababli saytga chiqarish qo'shilganda Writer ham, promptlar ham, uslub
namunalari ham qayta yozilmaydi — faqat yangi renderer qo'shiladi.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any

# O'zbek lotin harflarini URL uchun soddalashtirish
_TRANSLIT = {
    "o'": "o", "g'": "g", "o‘": "o", "g‘": "g", "ʻ": "", "'": "", "’": "",
    "ch": "ch", "sh": "sh", "ng": "ng",
}


def slugify(text: str, max_length: int = 70) -> str:
    """Sarlavhadan URL uchun qisqa nom yasaydi."""
    value = text.lower().strip()
    for src, dst in _TRANSLIT.items():
        value = value.replace(src, dst)
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r"[^a-z0-9Ѐ-ӿ]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value[:max_length].rstrip("-") or "post"


@dataclass
class PostContent:
    """Kanalga bog'liq bo'lmagan post mazmuni."""

    title: str = ""
    lead: str = ""                                  # kirish: 1-2 gap
    body: list[str] = field(default_factory=list)   # asosiy qismlar/qadamlar
    takeaway: str = ""                              # eslatma yoki ogohlantirish
    cta: str = ""                                   # o'quvchiga savol
    tags: list[str] = field(default_factory=list)

    # -- yaratish -----------------------------------------------------------
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PostContent":
        def as_list(value: Any) -> list[str]:
            if isinstance(value, list):
                return [str(v).strip() for v in value if str(v).strip()]
            if isinstance(value, str) and value.strip():
                return [value.strip()]
            return []

        return cls(
            title=str(data.get("title") or "").strip(),
            lead=str(data.get("lead") or "").strip(),
            body=as_list(data.get("body")),
            takeaway=str(data.get("takeaway") or "").strip(),
            cta=str(data.get("cta") or "").strip(),
            tags=[t.lstrip("#").strip() for t in as_list(data.get("tags"))],
        )

    @classmethod
    def from_plain_text(cls, text: str) -> "PostContent":
        """Zaxira yo'l: model JSON qaytarmasa, matnni bo'laklarga ajratamiz.

        Sifat pasayadi, lekin post yo'qolmaydi.
        """
        blocks = [b.strip() for b in re.split(r"\n{2,}", text.strip()) if b.strip()]
        if not blocks:
            return cls()

        tags: list[str] = []
        if blocks and re.fullmatch(r"(#\S+\s*)+", blocks[-1]):
            tags = [t.lstrip("#") for t in blocks.pop().split()]

        title = blocks.pop(0) if blocks else ""
        lead = blocks.pop(0) if blocks else ""
        cta = blocks.pop() if blocks and blocks[-1].endswith("?") else ""
        return cls(title=title, lead=lead, body=blocks, cta=cta, tags=tags)

    # -- foydalanish ---------------------------------------------------------
    @property
    def slug(self) -> str:
        return slugify(self.title)

    def is_empty(self) -> bool:
        return not any([self.title, self.lead, self.body, self.cta])

    def plain_text(self) -> str:
        """Formatlashsiz matn — sifat tekshiruvi va audio uchun."""
        parts = [self.title, self.lead, *self.body, self.takeaway, self.cta]
        return "\n\n".join(p for p in parts if p)

    def word_count(self) -> int:
        return len(self.plain_text().split())

    def reading_minutes(self) -> int:
        return max(1, round(self.word_count() / 180))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
