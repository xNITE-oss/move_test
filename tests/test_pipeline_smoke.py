"""Tarmoqqa chiqmaydigan smoke testlar: fake providerlar bilan to'liq pipeline."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from config.settings import Settings
from core.context import PostContext, PostStatus, Verdict
from core.pipeline import Pipeline
from core.rubric import RubricConfig
from core.storage import Storage
from core.utils import extract_json, truncate


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return dataclasses.replace(
        Settings.load(),
        llm_provider="fake",
        search_provider="fake",
        image_provider="fake",
        tts_provider="fake",
        dry_run=True,
        data_dir=tmp_path / "data",
    )


def make_rubric(**overrides) -> RubricConfig:
    raw = {
        "name": "Test rubrika",
        "description": "Test uchun",
        "enabled": True,
        "pipeline": ["research", "writer", "quality", "publisher"],
        "max_retries": 1,
        "agents": {
            "research": {"enabled": True, "queries": ["test query"], "max_results": 3},
            "writer": {"enabled": True, "max_chars": 900, "hashtags": ["#test"]},
            "quality": {"enabled": True, "use_llm": False, "min_chars": 50},
            "publisher": {"enabled": True, "mode": "auto", "channel": "@test"},
        },
    }
    raw.update(overrides)
    return RubricConfig(key="test_rubrika", raw=raw)


# ── pipeline ────────────────────────────────────────────────────────────────
async def test_full_pipeline_dry_run(settings):
    ctx = await Pipeline(make_rubric(), settings).run(dry_run=True)

    assert ctx.status == PostStatus.PUBLISHED, ctx.errors
    assert ctx.research is not None
    assert ctx.research.topic
    assert ctx.post_text
    assert "#test" in ctx.post_text
    assert not ctx.errors


async def test_disabled_agents_are_skipped(settings):
    rubric = make_rubric()
    rubric.raw["agents"]["publisher"]["enabled"] = False
    ctx = await Pipeline(rubric, settings).run(dry_run=True)

    assert ctx.status != PostStatus.PUBLISHED
    steps = {t["agent"]: t["status"] for t in ctx.trace}
    assert steps["publisher"] == "disabled"
    assert steps["writer"] == "ok"


async def test_skeleton_agents_do_not_break_pipeline(settings):
    """image/audio yoqilgan, lekin provider yo'q — pipeline to'xtamasligi kerak."""
    rubric = make_rubric()
    rubric.raw["pipeline"] = ["research", "writer", "image", "audio", "quality", "publisher"]
    rubric.raw["agents"]["image"] = {"enabled": True, "fake_on_dry_run": False}
    rubric.raw["agents"]["audio"] = {"enabled": True, "fake_on_dry_run": False}

    none_settings = dataclasses.replace(settings, image_provider="none", tts_provider="none")
    ctx = await Pipeline(rubric, none_settings).run(dry_run=True)

    assert ctx.status == PostStatus.PUBLISHED, ctx.errors
    steps = {t["agent"]: t["status"] for t in ctx.trace}
    assert steps["image"] == "skipped"
    assert steps["audio"] == "skipped"


async def test_image_and_audio_produce_files_with_fake_providers(settings):
    rubric = make_rubric()
    rubric.raw["pipeline"] = ["research", "writer", "image", "audio", "quality", "publisher"]
    rubric.raw["agents"]["image"] = {"enabled": True}
    rubric.raw["agents"]["audio"] = {"enabled": True}

    ctx = await Pipeline(rubric, settings).run(dry_run=True)

    assert ctx.status == PostStatus.PUBLISHED, ctx.errors
    assert ctx.image_path and Path(ctx.image_path).exists()
    assert ctx.audio_path and Path(ctx.audio_path).exists()


async def test_quality_retry_loop(settings):
    """min_chars juda baland — quality 'fix' beradi, urinishlar tugagach NEEDS_REVIEW."""
    rubric = make_rubric()
    rubric.raw["agents"]["quality"] = {"enabled": True, "use_llm": False, "min_chars": 100_000}
    ctx = await Pipeline(rubric, settings).run(dry_run=True)

    assert ctx.status == PostStatus.NEEDS_REVIEW
    assert ctx.attempt == rubric.max_retries
    writer_runs = [t for t in ctx.trace if t["agent"] == "writer"]
    assert len(writer_runs) == rubric.max_retries + 1
    # publisher chaqirilmagan bo'lishi kerak
    assert not [t for t in ctx.trace if t["agent"] == "publisher" and t["status"] == "ok"]


async def test_manual_topic_is_used(settings):
    ctx = await Pipeline(make_rubric(), settings).run(topic="Qo'lda berilgan mavzu", dry_run=True)
    assert ctx.meta["topic"] == "Qo'lda berilgan mavzu"
    assert ctx.post_text


# ── storage ─────────────────────────────────────────────────────────────────
def test_storage_roundtrip(settings):
    storage = Storage(settings)
    ctx = PostContext(rubric_key="test_rubrika", post_text="salom")
    ctx.meta["topic"] = "Mavzu A"
    storage.upsert_post(ctx)
    storage.save_context(ctx)

    assert "Mavzu A" in storage.recent_topics("test_rubrika")
    assert (storage.run_dir(ctx) / "post.txt").read_text(encoding="utf-8") == "salom"
    assert storage.history("test_rubrika")[0]["run_id"] == ctx.run_id


# ── utils ───────────────────────────────────────────────────────────────────
def test_extract_json_variants():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('Mana javob:\n```json\n{"a": 2}\n```\nrahmat') == {"a": 2}
    with pytest.raises(ValueError):
        extract_json("hech qanday json yo'q")


def test_truncate_keeps_words():
    text = "Birinchi gap. Ikkinchi gap. Uchinchi gap."
    assert truncate(text, 100) == text
    assert len(truncate(text, 20)) <= 20


# ── quality qoidalari ───────────────────────────────────────────────────────
async def test_quality_rules_catch_banned_words(settings):
    from agents.quality_agent import QualityAgent

    rubric = make_rubric()
    rubric.raw["agents"]["quality"] = {
        "enabled": True,
        "use_llm": False,
        "min_chars": 10,
        "banned_words": ["shok"],
    }
    ctx = PostContext(rubric_key="test_rubrika", post_text="Bu shok natija haqida post matni.")
    ctx = await QualityAgent(settings, rubric).run(ctx)

    assert ctx.quality.verdict == Verdict.FIX
    assert any("shok" in i for i in ctx.quality.issues)
