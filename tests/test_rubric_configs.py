"""config/rubrics/*.yaml fayllarining butunligini tekshiradi.

Bu testlar tarmoqqa chiqmaydi — faqat config to'g'ri yozilganini kafolatlaydi,
shunda noto'g'ri YAML tungi cron paytida emas, hoziroq bilinadi.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from config.settings import Settings
from core.pipeline import Pipeline
from core.registry import AGENT_REGISTRY
from core.rubric import list_rubric_keys, load_all_rubrics, load_rubric

EXPECTED_KEYS = {
    "running", "race", "hiking", "camping", "cycling", "active_life", "move_uz",
}


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


def test_all_move_space_rubrics_exist():
    assert EXPECTED_KEYS.issubset(set(list_rubric_keys()))


@pytest.mark.parametrize("key", sorted(EXPECTED_KEYS))
def test_rubric_is_well_formed(key: str):
    rubric = load_rubric(key)

    assert rubric.name and rubric.description if False else rubric.name
    assert rubric.get("description"), f"{key}: description bo'sh"
    assert rubric.language == "uz"
    assert rubric.max_retries >= 1
    assert rubric.cron, f"{key}: schedule.cron ko'rsatilmagan"

    # pipeline'dagi har bir nom registry'da bo'lishi shart
    for step in rubric.pipeline:
        assert step in AGENT_REGISTRY, f"{key}: '{step}' agenti registry'da yo'q"

    # media bayroqlari bool bo'lsin
    assert isinstance(rubric.image_required, bool)
    assert isinstance(rubric.audio_required, bool)

    writer = rubric.agent_cfg("writer")
    assert writer.get("enabled") is True, f"{key}: writer o'chirilgan"
    assert writer.get("max_chars", 0) <= 4096, f"{key}: Telegram chegarasidan oshgan"
    assert writer.get("hashtags"), f"{key}: hashtag berilmagan"
    assert writer.get("tone"), f"{key}: tone berilmagan"
    assert writer.get("post_type"), f"{key}: post_type berilmagan"

    research = rubric.agent_cfg("research")
    assert research.get("queries"), f"{key}: research.queries bo'sh"

    quality = rubric.agent_cfg("quality")
    assert quality.get("enabled") is True, f"{key}: quality o'chirilgan"
    assert quality.get("min_chars", 0) < writer.get("max_chars", 0), (
        f"{key}: min_chars max_chars dan katta — post hech qachon o'tmaydi"
    )

    publisher = rubric.agent_cfg("publisher")
    assert publisher.get("mode") in {"review", "auto", "off"}


@pytest.mark.parametrize("key", sorted(EXPECTED_KEYS))
def test_cron_is_parseable(key: str):
    apscheduler = pytest.importorskip("apscheduler")
    from apscheduler.triggers.cron import CronTrigger

    rubric = load_rubric(key)
    CronTrigger.from_crontab(rubric.cron, timezone=rubric.schedule.get("timezone", "UTC"))


@pytest.mark.parametrize("key", sorted(EXPECTED_KEYS))
async def test_rubric_runs_end_to_end_dry(key: str, settings: Settings):
    """Har bir rubrika fake providerlar bilan uchidan-uchiga o'tishi kerak."""
    ctx = await Pipeline(load_rubric(key), settings).run(dry_run=True)
    assert not ctx.errors, ctx.errors
    assert ctx.post_text
    assert ctx.status.value in {"pending_approval", "published"}


def test_no_duplicate_cron_slots():
    """Ikki rubrika bir vaqtda ishga tushmasin (LLM limitiga urilmaslik uchun)."""
    slots = [r.cron for r in load_all_rubrics()]
    assert len(slots) == len(set(slots)), f"Bir xil cron: {slots}"


# ── image_required / audio_required semantikasi ─────────────────────────────
async def test_image_required_stops_pipeline_when_provider_off(settings: Settings):
    rubric = load_rubric("hiking")
    rubric.raw["image_required"] = True
    rubric.raw["agents"]["image"]["enabled"] = True
    rubric.raw["agents"]["image"]["fake_on_dry_run"] = False

    off = dataclasses.replace(settings, image_provider="none")
    ctx = await Pipeline(rubric, off).run(dry_run=True)

    assert ctx.status.value == "failed"
    assert any("image" in e for e in ctx.errors)


async def test_image_not_required_lets_pipeline_continue(settings: Settings):
    rubric = load_rubric("hiking")
    rubric.raw["image_required"] = False
    rubric.raw["agents"]["image"]["enabled"] = True
    rubric.raw["agents"]["image"]["fake_on_dry_run"] = False

    off = dataclasses.replace(settings, image_provider="none")
    ctx = await Pipeline(rubric, off).run(dry_run=True)

    assert ctx.status.value == "pending_approval"
    assert ctx.post_text


async def test_audio_required_stops_pipeline_when_provider_off(settings: Settings):
    rubric = load_rubric("running")
    rubric.raw["audio_required"] = True
    rubric.raw["agents"]["audio"]["enabled"] = True
    rubric.raw["agents"]["audio"]["fake_on_dry_run"] = False

    off = dataclasses.replace(settings, tts_provider="none")
    ctx = await Pipeline(rubric, off).run(dry_run=True)

    assert ctx.status.value == "failed"
