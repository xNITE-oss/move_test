"""Telegram Bot API bilan ishlash."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import httpx

from config.settings import Settings, get_settings

log = logging.getLogger("provider.telegram")

TELEGRAM_TEXT_LIMIT = 4096
TELEGRAM_CAPTION_LIMIT = 1024


class TelegramClientBase(ABC):
    name = "base"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    async def send_message(self, chat_id: str, text: str, **kwargs: Any) -> dict:
        ...

    @abstractmethod
    async def send_photo(self, chat_id: str, photo: Path, caption: str = "", **kwargs: Any) -> dict:
        ...

    @abstractmethod
    async def send_audio(self, chat_id: str, audio: Path, caption: str = "", **kwargs: Any) -> dict:
        ...

    # -- tasdiq oqimi uchun (approval_bot ishlatadi) --------------------------
    async def get_updates(self, offset: int | None = None, timeout: int = 0) -> list[dict]:
        return []

    async def answer_callback(self, callback_id: str, text: str = "") -> None:
        return None

    async def clear_buttons(self, chat_id: str, message_id: int) -> None:
        return None

    async def set_my_commands(self, commands: list[dict[str, str]]) -> None:
        return None

    async def send_for_review(
        self,
        chat_id: str,
        text: str,
        run_id: str,
        *,
        delay_note: str = "5 daq.",
        instant_url: str | None = None,
        **kwargs: Any,
    ) -> dict:
        """Tasdiq uchun inline tugmalar bilan yuborish.

        Tugma bosilishi darhol emas, navbat orqali qayta ishlanadi — shuning uchun
        tugma matnida kutish vaqti yoziladi. `instant_url` berilsa, kutmaslik uchun
        qo'shimcha havola tugmasi chiqadi (GitHub'da qo'lda ishga tushirish sahifasi).
        """
        rows = [
            [{"text": f"✅ Chiqarish ({delay_note})", "callback_data": f"approve:{run_id}"}],
            [
                {"text": "✏️ Qayta yozish", "callback_data": f"rewrite:{run_id}"},
                {"text": "❌ Bekor", "callback_data": f"reject:{run_id}"},
            ],
        ]
        if instant_url:
            rows.append([{"text": "⚡️ Kutmasdan chiqarish", "url": instant_url}])

        return await self.send_message(
            chat_id, text, reply_markup={"inline_keyboard": rows}, **kwargs
        )


class TelegramClient(TelegramClientBase):
    name = "telegram"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        settings.require("telegram_bot_token")
        self.base_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}"

    async def _call(self, method: str, **payload: Any) -> dict:
        payload = {k: v for k, v in payload.items() if v is not None}
        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            resp = await client.post(f"{self.base_url}/{method}", json=payload)
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram xatosi ({method}): {data.get('description')}")
        return data["result"]

    async def _call_with_file(self, method: str, field: str, path: Path, **payload: Any) -> dict:
        payload = {k: str(v) if not isinstance(v, str) else v
                   for k, v in payload.items() if v is not None}
        async with httpx.AsyncClient(timeout=self.settings.request_timeout * 3) as client:
            with path.open("rb") as fh:
                resp = await client.post(
                    f"{self.base_url}/{method}", data=payload, files={field: fh}
                )
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram xatosi ({method}): {data.get('description')}")
        return data["result"]

    async def send_message(self, chat_id: str, text: str, **kwargs: Any) -> dict:
        return await self._call(
            "sendMessage",
            chat_id=chat_id,
            text=text[:TELEGRAM_TEXT_LIMIT],
            parse_mode=kwargs.get("parse_mode", "HTML"),
            disable_web_page_preview=kwargs.get("disable_web_page_preview", True),
            reply_markup=kwargs.get("reply_markup"),
        )

    async def send_photo(self, chat_id: str, photo: Path, caption: str = "", **kwargs: Any) -> dict:
        return await self._call_with_file(
            "sendPhoto",
            "photo",
            photo,
            chat_id=chat_id,
            caption=caption[:TELEGRAM_CAPTION_LIMIT],
            parse_mode=kwargs.get("parse_mode", "HTML"),
        )

    async def send_audio(self, chat_id: str, audio: Path, caption: str = "", **kwargs: Any) -> dict:
        return await self._call_with_file(
            "sendAudio",
            "audio",
            audio,
            chat_id=chat_id,
            caption=caption[:TELEGRAM_CAPTION_LIMIT],
            title=kwargs.get("title", "Move Space"),
        )

    async def get_updates(self, offset: int | None = None, timeout: int = 0) -> list[dict]:
        return await self._call(
            "getUpdates",
            offset=offset,
            timeout=timeout,
            allowed_updates=["callback_query", "message"],
        )

    async def set_my_commands(self, commands: list[dict[str, str]]) -> None:
        """Telegram'dagi buyruqlar menyusini ro'yxatdan o'tkazadi (bir marta yetadi)."""
        await self._call("setMyCommands", commands=commands)

    async def answer_callback(self, callback_id: str, text: str = "") -> None:
        await self._call("answerCallbackQuery", callback_query_id=callback_id, text=text or None)

    async def clear_buttons(self, chat_id: str, message_id: int) -> None:
        try:
            await self._call(
                "editMessageReplyMarkup",
                chat_id=chat_id,
                message_id=message_id,
                reply_markup={"inline_keyboard": []},
            )
        except RuntimeError as exc:  # xabar allaqachon tahrirlangan bo'lsa — muhim emas
            log.debug("Tugmalarni olib tashlab bo'lmadi: %s", exc)


class DryRunTelegramClient(TelegramClientBase):
    """Hech narsa yubormaydi — konsolga chiqaradi. DRY_RUN=true da ishlatiladi."""

    name = "dry-run"
    _counter = 0

    def _fake_result(self) -> dict:
        DryRunTelegramClient._counter += 1
        return {"message_id": DryRunTelegramClient._counter, "dry_run": True}

    async def send_message(self, chat_id: str, text: str, **kwargs: Any) -> dict:
        log.info("[DRY-RUN] → %s\n%s\n%s\n%s", chat_id, "-" * 50, text, "-" * 50)
        return self._fake_result()

    async def send_photo(self, chat_id: str, photo: Path, caption: str = "", **kwargs: Any) -> dict:
        log.info("[DRY-RUN] rasm → %s (%s)", chat_id, photo)
        return self._fake_result()

    async def send_audio(self, chat_id: str, audio: Path, caption: str = "", **kwargs: Any) -> dict:
        log.info("[DRY-RUN] audio → %s (%s)", chat_id, audio)
        return self._fake_result()


def get_telegram_client(
    settings: Settings | None = None, *, dry_run: bool | None = None
) -> TelegramClientBase:
    settings = settings or get_settings()
    use_dry = settings.dry_run if dry_run is None else dry_run
    if use_dry or not settings.telegram_bot_token:
        if not use_dry:
            log.warning("TELEGRAM_BOT_TOKEN yo'q — dry-run rejimiga o'tildi")
        return DryRunTelegramClient(settings)
    return TelegramClient(settings)
