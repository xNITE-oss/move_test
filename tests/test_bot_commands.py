"""Telegram buyruqlari: "📝 Post tayyorlash", /holat, /rubrikalar.

Tarmoqqa chiqilmaydi — soxta Telegram client va fake LLM/qidiruv ishlatiladi.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from config.settings import Settings
from core.context import PostStatus
from scheduler.approval_bot import ApprovalBot

OWNER = "6121632867"
STRANGER = "999999"


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
        self.markups: list[dict] = []
        self.answers: list[str] = []
        self.commands: list[dict] = []

    async def get_updates(self, offset=None, timeout=0):
        return self.updates

    async def set_my_commands(self, commands):
        self.commands = commands

    async def answer_callback(self, callback_id, text=""):
        self.answers.append(text)

    async def clear_buttons(self, chat_id, message_id):
        pass

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text))
        self.markups.append(kwargs.get("reply_markup") or {})
        return {"message_id": 1}

    async def send_photo(self, chat_id, photo, caption="", **kwargs):
        return {"message_id": 2}

    async def send_audio(self, chat_id, audio, caption="", **kwargs):
        return {"message_id": 3}

    async def send_for_review(self, chat_id, text, run_id, **kwargs):
        self.sent.append((chat_id, text))
        self.markups.append({"review": run_id})
        return {"message_id": 4}


def msg(text: str, from_id: str = OWNER, update_id: int = 1) -> dict:
    return {
        "update_id": update_id,
        "message": {"message_id": 10, "text": text,
                    "chat": {"id": int(from_id)}, "from": {"id": int(from_id)}},
    }


def cb(data: str, update_id: int = 1) -> dict:
    return {
        "update_id": update_id,
        "callback_query": {"id": "cb", "data": data, "from": {"id": int(OWNER)},
                           "message": {"message_id": 11, "chat": {"id": int(OWNER)}}},
    }


def texts(client: FakeClient) -> str:
    return "\n".join(t for _, t in client.sent)


async def test_post_button_offers_rubric_choice(settings):
    client = FakeClient([msg("📝 Post tayyorlash")])
    await ApprovalBot(settings, client=client).poll_once()

    assert "Qaysi rubrika" in texts(client)
    buttons = [b for m in client.markups if "inline_keyboard" in m
               for row in m["inline_keyboard"] for b in row]
    keys = {b["callback_data"] for b in buttons}
    assert "make:running" in keys
    assert "make:move_uz" in keys


async def test_choosing_rubric_creates_post(settings):
    client = FakeClient([cb("make:running")])
    bot = ApprovalBot(settings, client=client)

    await bot.poll_once()

    # Pipeline o'z clientini yaratadi (dry-run), shuning uchun natijani bazadan tekshiramiz
    rows = bot.storage.history(limit=1)
    assert rows and rows[0]["rubric"] == "running"
    assert rows[0]["status"] == PostStatus.PENDING_APPROVAL.value


async def test_direct_command_with_rubric(settings):
    client = FakeClient([msg("/post camping")])
    bot = ApprovalBot(settings, client=client)

    await bot.poll_once()

    assert "tayyorlanmoqda" in texts(client)
    assert bot.storage.history(limit=1)[0]["rubric"] == "camping"


async def test_unknown_rubric_is_reported(settings):
    client = FakeClient([msg("/post yoq_rubrika")])
    await ApprovalBot(settings, client=client).poll_once()

    assert "yo'q" in texts(client)


async def test_status_command_lists_posts(settings):
    client = FakeClient([cb("make:running", 1), msg("📊 Holat", update_id=2)])
    await ApprovalBot(settings, client=client).poll_once()

    assert "Oxirgi postlar" in texts(client)
    assert "running" in texts(client)


async def test_rubrics_command(settings):
    client = FakeClient([msg("/rubrikalar")])
    await ApprovalBot(settings, client=client).poll_once()

    out = texts(client)
    assert "Running" in out and "Move UZ" in out


async def test_help_shows_menu_keyboard(settings):
    client = FakeClient([msg("/start")])
    await ApprovalBot(settings, client=client).poll_once()

    keyboards = [m for m in client.markups if "keyboard" in m]
    labels = [b["text"] for m in keyboards for row in m["keyboard"] for b in row]
    assert "📝 Post tayyorlash" in labels


async def test_stranger_is_ignored(settings):
    client = FakeClient([msg("📝 Post tayyorlash", from_id=STRANGER)])
    await ApprovalBot(settings, client=client).poll_once()

    assert "Qaysi rubrika" not in texts(client)


async def test_commands_are_registered_once(settings):
    client = FakeClient([])
    bot = ApprovalBot(settings, client=client)

    await bot.poll_once()
    assert [c["command"] for c in client.commands] == ["post", "holat", "rubrikalar"]

    client.commands = []
    await bot.poll_once()
    assert client.commands == [], "menyu har safar qayta ro'yxatdan o'tyapti"
