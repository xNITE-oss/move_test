"""PostContent'ni kanal formatlariga o'giradi.

Yangi kanal qo'shilsa (Instagram, email, RSS) — shu yerga bitta funksiya
qo'shiladi, Writer va promptlarga tegilmaydi.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any

from core.content import PostContent
from core.utils import normalize_hashtags, truncate


def render_telegram(
    content: PostContent,
    *,
    max_chars: int = 900,
    hashtags: list[str] | None = None,
) -> str:
    """Telegram posti: qisqa, emoji bilan, oxirida hashtaglar."""
    parts: list[str] = []
    if content.title:
        parts.append(content.title)
    if content.lead:
        parts.append(content.lead)
    if content.body:
        parts.append("\n".join(content.body) if _looks_like_list(content.body)
                     else "\n\n".join(content.body))
    if content.takeaway:
        parts.append(content.takeaway)
    if content.cta:
        parts.append(content.cta)

    text = "\n\n".join(p for p in parts if p).strip()

    tags = normalize_hashtags(hashtags or [t for t in content.tags])
    if tags:
        tail = " ".join(dict.fromkeys(tags))          # takrorlanmasin
        text = f"{truncate(text, max_chars - len(tail) - 2)}\n\n{tail}"

    return truncate(text, max_chars)


def render_markdown(content: PostContent, *, meta: dict[str, Any] | None = None) -> str:
    """Sayt uchun front-matter'li Markdown (statik generatorlar shuni kutadi)."""
    meta = dict(meta or {})
    meta.setdefault("title", content.title)
    meta.setdefault("slug", content.slug)
    meta.setdefault("date", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    meta.setdefault("tags", content.tags)
    meta.setdefault("reading_minutes", content.reading_minutes())
    if content.lead:
        meta.setdefault("description", content.lead)

    front = "\n".join(f"{k}: {_yaml_value(v)}" for k, v in meta.items())

    blocks = [f"---\n{front}\n---", f"# {content.title}" if content.title else ""]
    if content.lead:
        blocks.append(f"**{content.lead}**")
    blocks.extend(content.body)
    if content.takeaway:
        blocks.append(f"> {content.takeaway}")
    if content.cta:
        blocks.append(f"_{content.cta}_")

    return "\n\n".join(b for b in blocks if b).strip() + "\n"


def render_html(content: PostContent) -> str:
    """Oddiy HTML bo'lagi — adminka ko'rinishi yoki sayt shabloni uchun."""
    def esc(value: str) -> str:
        return html.escape(value, quote=False)

    parts = [f"<h1>{esc(content.title)}</h1>"] if content.title else []
    if content.lead:
        parts.append(f'<p class="lead">{esc(content.lead)}</p>')
    for block in content.body:
        parts.append(f"<p>{esc(block)}</p>")
    if content.takeaway:
        parts.append(f"<blockquote>{esc(content.takeaway)}</blockquote>")
    if content.cta:
        parts.append(f'<p class="cta">{esc(content.cta)}</p>')
    if content.tags:
        tags = " ".join(f'<span class="tag">#{esc(t)}</span>' for t in content.tags)
        parts.append(f'<p class="tags">{tags}</p>')
    return "\n".join(parts)


# -- ichki ------------------------------------------------------------------
def _looks_like_list(body: list[str]) -> bool:
    """'1. ...', '- ...' kabi qatorlar orasiga bo'sh qator qo'yilmaydi."""
    numbered = sum(1 for b in body if b[:2].strip(".").strip().isdigit()
                   or b.startswith(("- ", "• ")))
    return numbered >= max(2, len(body) - 1)


def _yaml_value(value: Any) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(f'"{v}"' for v in value) + "]"
    text = str(value)
    return f'"{text}"' if any(c in text for c in ':#"\n') else text
