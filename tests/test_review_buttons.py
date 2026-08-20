"""Tasdiq xabaridagi tugmalar: matn, tartib va "kutmasdan chiqarish" havolasi."""

from __future__ import annotations

import dataclasses

import pytest

from config.settings import Settings
from providers.telegram import DryRunTelegramClient


@pytest.fixture
def client() -> DryRunTelegramClient:
    return DryRunTelegramClient(Settings.load())


class Capturing(DryRunTelegramClient):
    """send_message chaqiruvini ushlab qoladi."""

    def __init__(self, settings):
        super().__init__(settings)
        self.last: dict = {}

    async def send_message(self, chat_id, text, **kwargs):
        self.last = {"chat_id": chat_id, "text": text, **kwargs}
        return {"message_id": 1}


def keyboard(client: Capturing) -> list[list[dict]]:
    return client.last["reply_markup"]["inline_keyboard"]


async def test_approve_button_shows_waiting_time():
    c = Capturing(Settings.load())
    await c.send_for_review("123", "post", "run-1", delay_note="5 daq.")

    approve = keyboard(c)[0][0]
    assert approve["callback_data"] == "approve:run-1"
    assert "5 daq." in approve["text"], "kutish vaqti tugmada ko'rinishi kerak"


async def test_instant_url_button_is_added_when_url_given():
    c = Capturing(Settings.load())
    url = "https://github.com/user/repo/actions/workflows/approve.yml"
    await c.send_for_review("123", "post", "run-1", instant_url=url)

    last_row = keyboard(c)[-1][0]
    assert last_row["url"] == url
    assert "callback_data" not in last_row


async def test_no_instant_button_without_url():
    c = Capturing(Settings.load())
    await c.send_for_review("123", "post", "run-1")

    assert all("url" not in b for row in keyboard(c) for b in row)


async def test_all_three_actions_present():
    c = Capturing(Settings.load())
    await c.send_for_review("123", "post", "run-1")

    actions = {b["callback_data"].split(":")[0]
               for row in keyboard(c) for b in row if "callback_data" in b}
    assert actions == {"approve", "rewrite", "reject"}


def test_approve_url_is_built_from_github_repository(monkeypatch):
    from config import settings as settings_module

    monkeypatch.setenv("GITHUB_REPOSITORY", "xNITE-oss/move_test")
    monkeypatch.delenv("APPROVE_WORKFLOW_URL", raising=False)
    s = settings_module.Settings.load()

    assert s.approve_workflow_url == (
        "https://github.com/xNITE-oss/move_test/actions/workflows/approve.yml"
    )


def test_explicit_url_wins(monkeypatch):
    from config import settings as settings_module

    monkeypatch.setenv("GITHUB_REPOSITORY", "a/b")
    monkeypatch.setenv("APPROVE_WORKFLOW_URL", "https://example.com/qo-lda")
    s = settings_module.Settings.load()

    assert s.approve_workflow_url == "https://example.com/qo-lda"
