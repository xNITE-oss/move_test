"""Tasdiq oqimi testlari — tarmoqqa chiqmaydi, soxta Telegram client ishlatiladi."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from config.settings import Settings
from core.context import PostContext, PostStatus
from core.storage import Storage
from scheduler.approval_bot import OFFSET_KEY, ApprovalBot

OWNER = "6121632867"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return dataclasses.replace(
        Settings.load(),
        llm_provider="fake",
        search_provider="fake",
        image_provider="none",
        tts_provider="none",
        telegram_bot_token="test-token",
        telegram_channel_id="@testkanal",
        telegram_review_chat_id=OWNER,
        dry_run=True,
        data_dir=tmp_path / "data",
    )


class FakeClient:
    def __init__(self, updates=None):
        self.updates = updates or []
        self.sent: list[tuple[str, str]] = []
        self.answers: list[str] = []
        self.cleared: list[int] = []

    async def get_updates(self, offset=None, timeout=0):
        self.last_offset = offset
        return self.updates

    async def answer_callback(self, callback_id, text=""):
        self.answers.append(text)

    async def clear_buttons(self, chat_id, message_id):
        self.cleared.append(message_id)

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text))
        return {"message_id": 777}

    async def send_photo(self, chat_id, photo, caption="", **kwargs):
        self.sent.append((chat_id, caption))
        return {"message_id": 778}

    async def send_audio(self, chat_id, audio, caption="", **kwargs):
        return {"message_id": 779}


def seed_post(settings: Settings, rubric: str = "running") -> PostContext:
    storage = Storage(settings)
    ctx = PostContext(rubric_key=rubric)
    ctx.post_text = "Tasdiq kutayotgan post matni."
    ctx.status = PostStatus.PENDING_APPROVAL
    ctx.meta["topic"] = "Test mavzu"
    storage.upsert_post(ctx)
    return ctx


def callback(action: str, run_id: str, from_id: str = OWNER) -> dict:
    return {
        "update_id": 100,
        "callback_query": {
            "id": "cb1",
            "data": f"{action}:{run_id}",
            "from": {"id": int(from_id)},
            "message": {"message_id": 42, "chat": {"id": int(from_id)}},
        },
    }


async def test_approve_publishes_post(settings):
    ctx = seed_post(settings)
    client = FakeClient([callback("approve", ctx.run_id)])
    bot = ApprovalBot(settings, client=client)

    handled = await bot.poll_once()

    assert handled == 1
    assert client.sent, "post kanalga yuborilmadi"
    assert client.sent[0][0] == "@testkanal"
    assert bot.storage.get_post(ctx.run_id)["status"] == PostStatus.PUBLISHED.value
    assert 42 in client.cleared


def to_channel(client: "FakeClient") -> list[tuple[str, str]]:
    """Kanalga ketgan xabarlar (tasdiq chatiga yozilgan izohlar hisobga olinmaydi)."""
    return [s for s in client.sent if s[0] == "@testkanal"]


async def test_reject_marks_post_rejected(settings):
    ctx = seed_post(settings)
    client = FakeClient([callback("reject", ctx.run_id)])
    bot = ApprovalBot(settings, client=client)

    await bot.poll_once()

    assert not to_channel(client)
    assert bot.storage.get_post(ctx.run_id)["status"] == PostStatus.REJECTED.value


async def test_stranger_cannot_publish(settings):
    ctx = seed_post(settings)
    client = FakeClient([callback("approve", ctx.run_id, from_id="999999")])
    bot = ApprovalBot(settings, client=client)

    await bot.poll_once()

    assert not client.sent, "begona odam postni chiqarib yubordi!"
    assert bot.storage.get_post(ctx.run_id)["status"] == PostStatus.PENDING_APPROVAL.value
    assert client.answers == ["Ruxsat yo'q"]


async def test_publishes_from_message_text_when_db_lost_the_post(settings):
    """Baza eskirgan bo'lsa ham ✅ ishlashi kerak — matn tasdiq xabarida turadi."""
    run_id = "20260820-194628-cf4e76"
    post_body = (
        "🏃 Issiqda yugurganda tezroq charchaganingizni sezganmisiz?\n\n"
        "Yozgi issiqda 20 daqiqada organizm 350 ml gacha suyuqlik yo'qotadi.\n\n"
        "Siz qanday ichasiz?"
    )
    update = callback("approve", run_id)
    update["callback_query"]["message"]["text"] = (
        f"🧪 Tasdiq kutilmoqda — 🏃 Running\nSifat bahosi: 9.5\n{run_id}\n\n{post_body}"
    )

    client = FakeClient([update])
    bot = ApprovalBot(settings, client=client)   # bazada bu run yo'q

    await bot.poll_once()

    sent = to_channel(client)
    assert len(sent) == 1, "post kanalga chiqmadi"
    assert sent[0][1].startswith("🏃 Issiqda yugurganda")
    assert "Tasdiq kutilmoqda" not in sent[0][1], "sarlavha ham chiqib ketdi"


async def test_unknown_post_without_text_is_reported(settings):
    client = FakeClient([callback("approve", "yo-q-run")])
    bot = ApprovalBot(settings, client=client)

    await bot.poll_once()

    assert not to_channel(client)
    assert client.answers == ["Post topilmadi"]


async def test_offset_is_remembered(settings):
    ctx = seed_post(settings)
    client = FakeClient([callback("reject", ctx.run_id)])
    bot = ApprovalBot(settings, client=client)

    await bot.poll_once()
    assert bot.storage.get_state(OFFSET_KEY) == "100"

    client.updates = []
    await bot.poll_once()
    assert client.last_offset == 101   # o'sha tugma ikkinchi marta o'qilmaydi


async def test_double_approve_does_not_publish_twice(settings):
    ctx = seed_post(settings)
    client = FakeClient([callback("approve", ctx.run_id)])
    bot = ApprovalBot(settings, client=client)
    await bot.poll_once()

    client.updates = [dict(callback("approve", ctx.run_id), update_id=101)]
    await bot.poll_once()

    assert len(to_channel(client)) == 1, "post ikki marta chiqib ketdi"
    assert "allaqachon" in client.answers[-1]
