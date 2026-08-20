"""Tasdiq tugmalarini eshituvchi bot.

Publisher `mode: review` da postni sizga inline tugmalar bilan yuboradi:
    ✅ Chiqarish  |  ✏️ Qayta yozish  |  ❌ Bekor

Bu modul o'sha tugma bosilishini o'qiydi va tegishli amalni bajaradi.

Ishga tushirish:
    python -m scheduler.approval_bot --once     # bir marta tekshirib chiqadi (GitHub Actions)
    python -m scheduler.approval_bot            # doimiy long-polling (VPS)

Xavfsizlik: faqat TELEGRAM_REVIEW_CHAT_ID egasining bosishi qabul qilinadi.
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from config.settings import Settings, get_settings
from core.context import PostContext, PostStatus
from core.logging_setup import setup_logging
from core.pipeline import Pipeline
from core.registry import build_agent
from core.rubric import load_rubric
from core.storage import Storage

log = logging.getLogger("approval-bot")

OFFSET_KEY = "telegram_update_offset"
ACTIONS = ("approve", "rewrite", "reject")


class ApprovalBot:
    def __init__(self, settings: Settings | None = None, client=None) -> None:
        self.settings = settings or get_settings()
        self.storage = Storage(self.settings)
        if client is not None:          # testlarda o'rniga soxta client beriladi
            self.client = client
            return
        self.settings.require("telegram_bot_token", "telegram_review_chat_id")
        from providers.telegram import get_telegram_client

        self.client = get_telegram_client(self.settings, dry_run=False)

    # -- asosiy sikl ---------------------------------------------------------
    async def poll_once(self, timeout: int = 0) -> int:
        offset_raw = self.storage.get_state(OFFSET_KEY)
        offset = int(offset_raw) + 1 if offset_raw else None

        updates = await self.client.get_updates(offset=offset, timeout=timeout)
        handled = 0

        for update in updates:
            self.storage.set_state(OFFSET_KEY, update["update_id"])
            query = update.get("callback_query")
            if not query:
                continue
            try:
                await self._handle(query)
                handled += 1
            except Exception as exc:  # noqa: BLE001
                log.error("callback xatosi: %s", exc, exc_info=True)

        return handled

    async def run_forever(self, interval: int = 25) -> None:
        log.info("Tasdiq boti ishga tushdi. To'xtatish: Ctrl+C")
        while True:
            try:
                await self.poll_once(timeout=interval)
            except Exception as exc:  # noqa: BLE001
                log.error("polling xatosi: %s", exc)
                await asyncio.sleep(5)

    # -- callback ------------------------------------------------------------
    async def _handle(self, query: dict) -> None:
        data = query.get("data") or ""
        callback_id = query["id"]
        message = query.get("message") or {}
        chat_id = str((message.get("chat") or {}).get("id", ""))
        message_id = message.get("message_id")
        from_id = str((query.get("from") or {}).get("id", ""))

        # Faqat egasining bosishi
        if from_id != str(self.settings.telegram_review_chat_id):
            await self.client.answer_callback(callback_id, "Ruxsat yo'q")
            log.warning("Begona foydalanuvchi tugma bosdi: %s", from_id)
            return

        if ":" not in data:
            await self.client.answer_callback(callback_id, "Noma'lum buyruq")
            return

        action, run_id = data.split(":", 1)
        if action not in ACTIONS:
            await self.client.answer_callback(callback_id, "Noma'lum buyruq")
            return

        post = self.storage.get_post(run_id)
        if not post:
            await self.client.answer_callback(callback_id, "Post topilmadi (baza tozalangan?)")
            return

        if post["status"] == PostStatus.PUBLISHED.value:
            await self.client.answer_callback(callback_id, "Bu post allaqachon chiqqan")
            return

        log.info("[%s] %s", run_id, action)

        if action == "approve":
            await self._publish(post)
            await self.client.answer_callback(callback_id, "✅ Kanalga chiqdi")
        elif action == "reject":
            self.storage.set_status(run_id, PostStatus.REJECTED.value)
            await self.client.answer_callback(callback_id, "❌ Bekor qilindi")
        else:  # rewrite
            await self.client.answer_callback(callback_id, "✏️ Qayta yozilmoqda...")
            self.storage.set_status(run_id, PostStatus.REJECTED.value)
            await self._rewrite(post["rubric"])

        if chat_id and message_id:
            await self.client.clear_buttons(chat_id, message_id)

    # -- amallar -------------------------------------------------------------
    async def _publish(self, post: dict) -> None:
        rubric = load_rubric(post["rubric"])
        # Shu bir marta uchun "auto" rejimga o'tkazamiz
        rubric.raw.setdefault("agents", {}).setdefault("publisher", {})["mode"] = "auto"

        ctx = PostContext(rubric_key=post["rubric"], run_id=post["run_id"])
        ctx.post_text = post["post_text"] or ""
        ctx.image_path = post["image_path"]
        ctx.audio_path = post["audio_path"]
        ctx.status = PostStatus.REVIEWED
        ctx.meta["topic"] = post["topic"] or ""

        agent = build_agent("publisher", self.settings, rubric)
        agent.client_override = self.client   # bir xil client (va testlarda soxta client)
        await agent.execute(ctx)
        self.storage.upsert_post(ctx)
        self.storage.mark_published(ctx)
        log.info("[%s] kanalga chiqdi", ctx.run_id)

    async def _rewrite(self, rubric_key: str) -> None:
        try:
            rubric = load_rubric(rubric_key)
            ctx = await Pipeline(rubric, self.settings).run()
            log.info("[%s] qayta yozildi: %s", rubric_key, ctx.status.value)
        except Exception as exc:  # noqa: BLE001
            log.error("[%s] qayta yozishda xato: %s", rubric_key, exc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true",
                        help="Bir marta tekshirib chiqadi va chiqadi (cron/GitHub Actions uchun)")
    parser.add_argument("--timeout", type=int, default=25, help="long-polling kutish vaqti")
    args = parser.parse_args(argv)

    settings = get_settings()
    setup_logging(settings.log_level)

    bot = ApprovalBot(settings)
    if args.once:
        handled = asyncio.run(bot.poll_once(timeout=0))
        log.info("%d ta tugma bosilishi qayta ishlandi", handled)
        return 0

    try:
        asyncio.run(bot.run_forever(interval=args.timeout))
    except KeyboardInterrupt:
        log.info("To'xtatildi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
