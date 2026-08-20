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
                f"🧪 <b>Tasdiq kutilmoqda</b>\n"
                f"Rubrika: {self.rubric.name}\nrun_id: <code>{ctx.run_id}</code>\n"
                f"Sifat: {ctx.quality.score if ctx.quality else '-'}\n\n"
            )
            result = await client.send_for_review(
                str(chat_id), header + ctx.post_text, ctx.run_id
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

        result = await self._send(client, str(channel), ctx)
        ctx.telegram_message_id = result.get("message_id")
        ctx.status = PostStatus.PUBLISHED
        storage.mark_published(ctx)
        self.log.info("post kanalga chiqdi: %s (msg_id=%s)", channel, ctx.telegram_message_id)
        return ctx

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
