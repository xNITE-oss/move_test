"""Tuzilgan kontent va renderer'lar.

Asosiy g'oya: Writer bitta PostContent qaytaradi, undan Telegram matni ham,
sayt uchun Markdown ham chiqadi. Shu bog'liqlik shu yerda qulflanadi.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from config.settings import Settings
from core.content import PostContent, slugify
from core.pipeline import Pipeline
from core.render import render_html, render_markdown, render_telegram
from core.rubric import RubricConfig
from core.service import ContentService


SAMPLE = PostContent(
    title="🏃 Issiqda yugurishning asosiy xatosi",
    lead="Ko'pchilik suvni noto'g'ri ichadi.",
    body=["1. Chanqoqqa qarab iching", "2. Soatiga 300-800 ml", "3. Elektrolit qo'shing"],
    takeaway="Kuchli suvsizlanish sezilsa, to'xtang.",
    cta="Siz qanday ichasiz?",
    tags=["running", "movespace"],
)


# ── slug ────────────────────────────────────────────────────────────────────
def test_slugify_handles_uzbek_letters():
    assert slugify("O'zbekistonda yugurish — 5 ta maslahat") == "ozbekistonda-yugurish-5-ta-maslahat"
    assert slugify("G'ijduvon") == "gijduvon"
    assert slugify("!!!") == "post"


# ── Telegram renderer ───────────────────────────────────────────────────────
def test_telegram_render_has_all_parts():
    text = render_telegram(SAMPLE, max_chars=900, hashtags=["#running", "#movespace"])

    assert text.startswith("🏃 Issiqda")
    assert "Chanqoqqa qarab" in text
    assert "Siz qanday ichasiz?" in text
    assert text.rstrip().endswith("#running #movespace")


def test_telegram_render_respects_limit():
    long_content = dataclasses.replace(SAMPLE, body=["juda uzun matn " * 200])

    text = render_telegram(long_content, max_chars=400, hashtags=["#run"])

    assert len(text) <= 400
    assert "#run" in text


def test_telegram_render_does_not_duplicate_tags():
    text = render_telegram(SAMPLE, max_chars=900, hashtags=["#running", "#running"])
    assert text.count("#running") == 1


def test_numbered_list_stays_compact():
    """Raqamli qadamlar orasiga bo'sh qator qo'yilmaydi."""
    text = render_telegram(SAMPLE, max_chars=900)
    assert "1. Chanqoqqa qarab iching\n2. Soatiga" in text


# ── Sayt renderer ───────────────────────────────────────────────────────────
def test_markdown_has_front_matter():
    md = render_markdown(SAMPLE, meta={"rubric": "🏃 Running"})

    assert md.startswith("---\n")
    assert "slug: issiqda-yugurishning-asosiy-xatosi" in md
    assert 'tags: ["running", "movespace"]' in md
    assert "# 🏃 Issiqda yugurishning asosiy xatosi" in md
    assert "> Kuchli suvsizlanish" in md


def test_html_escapes_dangerous_characters():
    content = dataclasses.replace(SAMPLE, title="5 < 10 & <script>")
    out = render_html(content)

    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_reading_time_is_at_least_one_minute():
    assert SAMPLE.reading_minutes() >= 1


# ── zaxira yo'l: JSON kelmasa ───────────────────────────────────────────────
def test_plain_text_fallback_splits_blocks():
    raw = (
        "🏃 Sarlavha shu yerda\n\n"
        "Kirish gapi.\n\n"
        "Asosiy paragraf.\n\n"
        "Savolmi?\n\n"
        "#run #movespace"
    )
    content = PostContent.from_plain_text(raw)

    assert content.title == "🏃 Sarlavha shu yerda"
    assert content.lead == "Kirish gapi."
    assert content.cta == "Savolmi?"
    assert content.tags == ["run", "movespace"]


def test_from_dict_tolerates_string_body():
    content = PostContent.from_dict({"title": "T", "body": "bitta paragraf", "tags": "#run"})
    assert content.body == ["bitta paragraf"]
    assert content.tags == ["run"]


# ── pipeline: kontent saqlanadi va sayt fayli yoziladi ──────────────────────
@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return dataclasses.replace(
        Settings.load(),
        llm_provider="fake", search_provider="fake",
        image_provider="none", tts_provider="none",
        dry_run=True, data_dir=tmp_path / "data",
    )


def rubric(publish_to: list[str]) -> RubricConfig:
    return RubricConfig(key="test_rubrika", raw={
        "name": "Test", "description": "test", "publish_to": publish_to,
        "pipeline": ["research", "writer", "quality", "publisher"],
        "max_retries": 1,
        "agents": {
            "research": {"enabled": True, "queries": ["q"]},
            "writer": {"enabled": True, "max_chars": 900, "hashtags": ["#test"]},
            "quality": {"enabled": True, "use_llm": False, "min_chars": 50},
            "publisher": {"enabled": True, "mode": "auto", "channel": "@t"},
        },
    })


async def test_pipeline_stores_structured_content(settings):
    ctx = await Pipeline(rubric(["telegram"]), settings).run(dry_run=True)

    assert ctx.content is not None
    assert ctx.content.title
    assert ctx.content.body
    # bazada ham JSON ko'rinishida turadi
    service = ContentService(settings)
    stored = service.get_content(ctx.run_id)
    assert stored is not None and stored.title == ctx.content.title


async def test_web_target_writes_markdown_file(settings):
    ctx = await Pipeline(rubric(["telegram", "web"]), settings).run(dry_run=True)

    web_path = ctx.meta.get("web_path")
    assert web_path, f"sayt fayli yozilmadi: {ctx.errors}"
    text = Path(web_path).read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert ctx.content.title in text


async def test_unknown_target_does_not_break_publishing(settings):
    ctx = await Pipeline(rubric(["telegram", "instagram"]), settings).run(dry_run=True)

    assert ctx.status.value == "published"
    assert ctx.telegram_message_id is not None
