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
ACTIONS = ("approve", "rewrite", "reject", "make")

#: Telegram buyruqlar menyusi (setMyCommands orqali ro'yxatdan o'tadi)
BOT_COMMANDS = [
    {"command": "post", "description": "Post tayyorlash"},
    {"command": "holat", "description": "Oxirgi postlar holati"},
    {"command": "rubrikalar", "description": "Rubrikalar ro'yxati"},
]

#: Yozuv maydoni ostidagi doimiy tugmalar
MENU_KEYBOARD = {
    "keyboard": [[{"text": "📝 Post tayyorlash"}, {"text": "📊 Holat"}]],
    "resize_keyboard": True,
    "is_persistent": True,
}

MAKE_POST_TEXTS = {"📝 post tayyorlash", "post tayyorlash", "/post"}
STATUS_TEXTS = {"📊 holat", "holat", "/holat"}

HELP_TEXT = (
    "<b>Move Space kontent-boti</b>\n\n"
    "📝 <b>Post tayyorlash</b> — rubrikani tanlaysiz, bot material topib, "
    "post yozadi va shu yerga tasdiqqa yuboradi.\n"
    "📊 <b>Holat</b> — oxirgi postlar va ularning holati.\n\n"
    "Postlar jadval bo'yicha o'zi ham tayyorlanadi — /rubrikalar da ko'rasiz.\n\n"
    "<i>Eslatma: buyruqlar navbat orqali bajariladi, javob 5 daqiqagacha "
    "kechikishi mumkin.</i>"
)


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
    async def ensure_menu(self) -> None:
        """Buyruqlar menyusini bir marta ro'yxatdan o'tkazadi."""
        if self.storage.get_state("menu_registered"):
            return
        try:
            await self.client.set_my_commands(BOT_COMMANDS)
            if self.settings.telegram_review_chat_id:
                await self.client.send_message(
                    str(self.settings.telegram_review_chat_id),
                    HELP_TEXT, reply_markup=MENU_KEYBOARD,
                )
            self.storage.set_state("menu_registered", "1")
            log.info("Buyruqlar menyusi ro'yxatdan o'tdi")
        except Exception as exc:  # noqa: BLE001
            log.warning("Menyuni ro'yxatdan o'tkazib bo'lmadi: %s", exc)

    async def poll_once(self, timeout: int = 0) -> int:
        await self.ensure_menu()
        offset_raw = self.storage.get_state(OFFSET_KEY)
        offset = int(offset_raw) + 1 if offset_raw else None

        updates = await self.client.get_updates(offset=offset, timeout=timeout)
        handled = 0

        for update in updates:
            self.storage.set_state(OFFSET_KEY, update["update_id"])
            try:
                if update.get("callback_query"):
                    await self._handle(update["callback_query"])
                    handled += 1
                elif update.get("message"):
                    await self._handle_message(update["message"])
                    handled += 1
            except Exception as exc:  # noqa: BLE001
                log.error("update xatosi: %s", exc, exc_info=True)

        return handled

    # -- matnli buyruqlar -----------------------------------------------------
    async def _handle_message(self, message: dict) -> None:
        chat_id = str((message.get("chat") or {}).get("id", ""))
        if chat_id != str(self.settings.telegram_review_chat_id):
            log.warning("Begona chatdan xabar: %s", chat_id)
            return

        text = (message.get("text") or "").strip()
        low = text.lower()

        if low in MAKE_POST_TEXTS:
            await self._ask_rubric(chat_id)
        elif low.startswith("/post "):
            await self._make_post(chat_id, low.split(maxsplit=1)[1].strip())
        elif low in STATUS_TEXTS:
            await self._send_status(chat_id)
        elif low in {"/rubrikalar", "rubrikalar"}:
            await self._send_rubrics(chat_id)
        elif low in {"/start", "/help", "start", "help"}:
            await self.client.send_message(chat_id, HELP_TEXT, reply_markup=MENU_KEYBOARD)
        else:
            await self.client.send_message(
                chat_id, "Tushunmadim. Pastdagi tugmalardan foydalaning yoki /help yozing.",
                reply_markup=MENU_KEYBOARD,
            )

    async def _ask_rubric(self, chat_id: str) -> None:
        from core.rubric import load_all_rubrics

        rubrics = load_all_rubrics(only_enabled=True)
        if not rubrics:
            await self.client.send_message(chat_id, "Yoqilgan rubrika topilmadi.")
            return

        buttons = [{"text": r.name, "callback_data": f"make:{r.key}"} for r in rubrics]
        rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        await self.client.send_message(
            chat_id, "Qaysi rubrika bo'yicha post tayyorlansin?",
            reply_markup={"inline_keyboard": rows},
        )

    async def _send_status(self, chat_id: str) -> None:
        rows = self.storage.history(limit=5)
        if not rows:
            await self.client.send_message(chat_id, "Hali post tayyorlanmagan.")
            return
        icons = {"published": "✅", "pending_approval": "⏳", "rejected": "❌",
                 "failed": "⚠️", "needs_review": "👀"}
        lines = [
            f"{icons.get(r['status'], '•')} <b>{r['rubric']}</b> — "
            f"{(r['topic'] or 'mavzusiz')[:60]}\n<i>{r['created_at'][:16].replace('T', ' ')}</i>"
            for r in rows
        ]
        await self.client.send_message(chat_id, "<b>Oxirgi postlar</b>\n\n" + "\n\n".join(lines))

    async def _send_rubrics(self, chat_id: str) -> None:
        from core.rubric import load_all_rubrics

        lines = [f"• <b>{r.name}</b> — <code>{r.cron or 'jadvalsiz'}</code>"
                 for r in load_all_rubrics(only_enabled=True)]
        await self.client.send_message(
            chat_id,
            "<b>Rubrikalar</b>\n\n" + "\n".join(lines) +
            "\n\n<i>Vaqtlar Toshkent bo'yicha.</i>",
        )

    async def _make_post(self, chat_id: str, rubric_key: str) -> None:
        from core.rubric import list_rubric_keys

        if rubric_key not in list_rubric_keys():
            await self.client.send_message(
                chat_id,
                f"'{rubric_key}' rubrikasi yo'q. Mavjudlari: {', '.join(list_rubric_keys())}",
            )
            return

        await self.client.send_message(chat_id, f"⏳ <b>{rubric_key}</b> tayyorlanmoqda…")
        try:
            rubric = load_rubric(rubric_key)
            ctx = await Pipeline(rubric, self.settings).run()
        except Exception as exc:  # noqa: BLE001
            log.error("[%s] post tayyorlanmadi: %s", rubric_key, exc, exc_info=True)
            await self.client.send_message(chat_id, f"⚠️ Xato: {str(exc)[:400]}")
            return

        if ctx.status == PostStatus.PENDING_APPROVAL:
            return          # tasdiq xabari allaqachon yuborildi
        if ctx.status == PostStatus.PUBLISHED:
            await self.client.send_message(chat_id, "✅ Post kanalga chiqdi.")
        else:
            problems = "\n".join(ctx.errors[:3]) or "sabab noma'lum"
            await self.client.send_message(
                chat_id, f"⚠️ Post chiqmadi (holat: {ctx.status.value})\n{problems[:400]}"
            )

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

        if action == "make":
            # bu yerda run_id emas, rubrika kaliti keladi
            await self.client.answer_callback(callback_id, "⏳ Tayyorlanmoqda…")
            if chat_id and message_id:
                await self.client.clear_buttons(chat_id, message_id)
            await self._make_post(chat_id, run_id)
            return

        post = self.storage.get_post(run_id)
        if not post:
            # Baza eskirgan yoki yo'qolgan bo'lishi mumkin (GitHub'da state.db
            # runlar orasida ziddiyatga uchraydi). Bunday holda post matnini
            # tasdiq xabarining o'zidan olamiz — u yerda to'liq turibdi.
            post = self._post_from_message(message, run_id)
            if not post:
                await self.client.answer_callback(callback_id, "Post topilmadi")
                log.warning("[%s] bazada ham, xabarda ham post topilmadi", run_id)
                return
            log.warning("[%s] bazada yo'q — matn tasdiq xabaridan olindi", run_id)

        if post["status"] == PostStatus.PUBLISHED.value:
            await self.client.answer_callback(callback_id, "Bu post allaqachon chiqqan")
            return

        log.info("[%s] %s", run_id, action)

        note = ""
        if action == "approve":
            await self._publish(post)
            await self.client.answer_callback(callback_id, "✅ Kanalga chiqdi")
            note = "✅ Post kanalga chiqdi."
        elif action == "reject":
            self.storage.set_status(run_id, PostStatus.REJECTED.value)
            await self.client.answer_callback(callback_id, "❌ Bekor qilindi")
            note = "❌ Post bekor qilindi, kanalga chiqmadi."
        else:  # rewrite
            await self.client.answer_callback(callback_id, "✏️ Qayta yozilmoqda...")
            self.storage.set_status(run_id, PostStatus.REJECTED.value)
            await self._rewrite(post["rubric"])
            note = "✏️ Yangi variant tayyorlandi — yuqoriga qarang."

        if chat_id and message_id:
            await self.client.clear_buttons(chat_id, message_id)

        # Tugma bosilgani natijasini ko'rsatib qo'yamiz: bosgan paytda
        # hech narsa o'zgarmagandek tuyuladi, chunki javob navbat orqali keladi.
        if chat_id and note:
            try:
                await self.client.send_message(chat_id, note)
            except Exception as exc:  # noqa: BLE001
                log.debug("Tasdiq izohi yuborilmadi: %s", exc)

    # -- zaxira: postni tasdiq xabaridan tiklash ------------------------------
    def _post_from_message(self, message: dict, run_id: str) -> dict | None:
        """Tasdiq xabari matnidan post matnini ajratib oladi.

        Xabar ko'rinishi:
            🧪 Tasdiq kutilmoqda — <rubrika>
            Sifat bahosi: 9.5
            <run_id>
            <bo'sh qator>
            <postning o'zi>
        """
        text = message.get("text") or ""
        if run_id in text:
            body = text.split(run_id, 1)[1].lstrip("\n ")
        elif "\n\n" in text:
            body = text.split("\n\n", 1)[1]
        else:
            return None

        body = body.strip()
        if len(body) < 50:
            return None

        return {
            "run_id": run_id,
            "rubric": None,          # rubrika noma'lum — standart kanal ishlatiladi
            "status": PostStatus.PENDING_APPROVAL.value,
            "post_text": body,
            "image_path": None,
            "audio_path": None,
            "topic": None,
        }

    # -- amallar -------------------------------------------------------------
    async def _publish(self, post: dict) -> None:
        rubric = self._rubric_for(post)
        # Shu bir marta uchun "auto" rejimga o'tkazamiz
        rubric.raw.setdefault("agents", {}).setdefault("publisher", {})["mode"] = "auto"

        ctx = PostContext(rubric_key=post["rubric"] or "noma'lum", run_id=post["run_id"])
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

    def _rubric_for(self, post: dict):
        """Rubrika config'i. Noma'lum bo'lsa — standart kanalga chiqaradigan minimal config."""
        from core.rubric import RubricConfig

        key = post.get("rubric")
        if key:
            try:
                return load_rubric(key)
            except Exception as exc:  # noqa: BLE001
                log.warning("'%s' rubrikasi o'qilmadi (%s) — standart sozlama", key, exc)
        return RubricConfig(
            key=key or "noma'lum",
            raw={"name": key or "Noma'lum rubrika",
                 "agents": {"publisher": {"enabled": True, "mode": "auto"}}},
        )

    async def _rewrite(self, rubric_key: str | None) -> None:
        if not rubric_key:
            log.warning("Rubrika noma'lum — qayta yozib bo'lmaydi")
            return
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
