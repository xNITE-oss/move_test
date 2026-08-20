"""Publisher Agent — tayyor postni Telegram'ga chiqaradi.

Rejimlar (rubrika YAML → agents.publisher.mode):
  review  — post tasdiq uchun TELEGRAM_REVIEW_CHAT_ID ga tugmalar bilan yuboriladi
            (standart; kanalga faqat siz ✅ bosgandan keyin chiqadi)
  auto    — to'g'ridan-to'g'ri kanalga
  off     — hech qayerga yubormaydi (faqat saqlaydi)

DRY_RUN=true bo'lsa hech narsa yuborilmaydi, faqat konsolga chiqadi.
Tasdiq tugmalarini eshitish uchun: `python -m scheduler.approval_bot` (skeleton).
"""

from __future__ import annotations

from pathlib import Path

from core.base_agent import AgentSkip, BaseAgent
from core.context import PostContext, PostStatus
from core.render import render_markdown
from core.storage import Storage
from providers.telegram import TELEGRAM_CAPTION_LIMIT, get_telegram_client


class PublisherAgent(BaseAgent):
    name = "publisher"

    #: tashqaridan client berish uchun (approval_bot va testlar ishlatadi)
    client_override = None

    async def run(self, ctx: PostContext) -> PostContext:
        if not ctx.post_text:
            raise RuntimeError("Chiqarish uchun post matni yo'q")

        if ctx.status == PostStatus.NEEDS_REVIEW:
            raise AgentSkip("Post sifat tekshiruvidan o'tmadi — chiqarilmaydi")

        mode = str(self.opt("mode", "review")).lower()
        if mode == "off":
            raise AgentSkip("Publisher rejimi 'off'")

        client = self.client_override or get_telegram_client(
            self.settings, dry_run=ctx.dry_run
        )
        storage = Storage(self.settings)

        if mode == "review":
            chat_id = self.opt("review_chat_id") or self.settings.telegram_review_chat_id
            if not chat_id:
                if not ctx.dry_run:
                    raise RuntimeError(
                        "TELEGRAM_REVIEW_CHAT_ID o'rnatilmagan (mode: review uchun kerak)"
                    )
                chat_id = "<review-chat>"  # dry-run'da kalitsiz ham sinash mumkin
            header = (
                f"🧪 <b>Tasdiq kutilmoqda</b> — {self.rubric.name}\n"
                f"Sifat bahosi: {ctx.quality.score if ctx.quality else '-'}\n"
                f"<code>{ctx.run_id}</code>\n\n"
            )
            result = await client.send_for_review(
                str(chat_id),
                header + ctx.post_text,
                ctx.run_id,
                delay_note=self.opt("delay_note", self.settings.approve_delay_note),
                instant_url=self.opt("instant_url", self.settings.approve_workflow_url),
            )
            ctx.telegram_message_id = result.get("message_id")
            ctx.status = PostStatus.PENDING_APPROVAL
            storage.upsert_post(ctx)
            self.log.info("post tasdiqqa yuborildi (chat=%s)", chat_id)
            return ctx

        if mode != "auto":
            raise RuntimeError(f"Noma'lum publisher rejimi: '{mode}'")

        channel = self.opt("channel") or self.settings.telegram_channel_id
        if not channel:
            if not ctx.dry_run:
                raise RuntimeError("TELEGRAM_CHANNEL_ID o'rnatilmagan")
            channel = "<kanal>"

        await self._publish_all(client, ctx, str(channel))
        ctx.status = PostStatus.PUBLISHED
        storage.upsert_post(ctx)
        storage.mark_published(ctx)
        return ctx

    # -- chiqarish manzillari -----------------------------------------------------
    async def _publish_all(self, client, ctx: PostContext, channel: str) -> None:
        """`publish_to` ro'yxatidagi har bir kanalga chiqaradi.

        Yangi kanal qo'shish uchun `_target_<nom>` metodini yozib, rubrikada
        `publish_to` ga nomini qo'shish kifoya.
        """
        for target in self.rubric.publish_to:
            handler = getattr(self, f"_target_{target}", None)
            if handler is None:
                self.log.warning("'%s' chiqarish manzili noma'lum — o'tkazib yuborildi", target)
                continue
            try:
                await handler(client, ctx, channel)
            except Exception as exc:  # noqa: BLE001
                if target == "telegram":
                    raise
                ctx.add_error(f"publisher:{target}", str(exc))
                self.log.error("'%s' ga chiqmadi: %s", target, exc)

    async def _target_telegram(self, client, ctx: PostContext, channel: str) -> None:
        result = await self._send(client, channel, ctx)
        ctx.telegram_message_id = result.get("message_id")
        self.log.info("Telegram: %s (msg_id=%s)", channel, ctx.telegram_message_id)

    async def _target_web(self, client, ctx: PostContext, channel: str) -> None:
        """Sayt uchun front-matter'li Markdown fayl yozadi.

        Hozircha fayl `data/site/` ichida turadi — statik generator yoki keyingi
        backend shu papkadan o'qiydi. Sayt API'si paydo bo'lganda shu metod
        HTTP so'roviga almashtiriladi, boshqa joyga tegilmaydi.
        """
        if not ctx.content:
            raise RuntimeError("Tuzilgan kontent yo'q — saytga chiqarib bo'lmaydi")

        out_dir = Path(self.opt("web_dir", str(self.settings.data_dir / "site"))) / ctx.rubric_key
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{ctx.created_at[:10]}-{ctx.content.slug}.md"

        path.write_text(
            render_markdown(
                ctx.content,
                meta={"rubric": self.rubric.name, "run_id": ctx.run_id,
                      "cover": ctx.image_path or ""},
            ),
            encoding="utf-8",
        )
        ctx.meta["web_path"] = str(path)
        self.log.info("Sayt: %s", path)

    # -- ichki -------------------------------------------------------------------
    async def _send(self, client, chat_id: str, ctx: PostContext) -> dict:
        image = Path(ctx.image_path) if ctx.image_path else None

        if image and image.exists() and len(ctx.post_text) <= TELEGRAM_CAPTION_LIMIT:
            result = await client.send_photo(chat_id, image, caption=ctx.post_text)
        elif image and image.exists():
            # matn caption'ga sig'masa: avval rasm, keyin matn alohida
            await client.send_photo(chat_id, image, caption="")
            result = await client.send_message(chat_id, ctx.post_text)
        else:
            result = await client.send_message(chat_id, ctx.post_text)

        if ctx.audio_path and Path(ctx.audio_path).exists() and self.opt("send_audio", True):
            try:
                await client.send_audio(chat_id, Path(ctx.audio_path), caption="🎧 Audio versiya")
            except Exception as exc:  # noqa: BLE001
                self.log.warning("Audio yuborilmadi: %s", exc)

        return result
