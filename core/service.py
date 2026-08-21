"""Xizmat qatlami — biznes-mantiqning yagona kirish nuqtasi.

Telegram boti ham, keyingi web-adminka ham aynan shu metodlarni chaqiradi.
Shu sababli adminka yozilganda mantiq qayta yozilmaydi — ustiga yupqa HTTP
qobiq kiyiladi:

    Telegram bot ──┐
                   ├──► ContentService ──► Pipeline / Storage
    Web adminka ───┘
"""

from __future__ import annotations

import json
import logging
from typing import Any

from config.settings import Settings, get_settings
from core.content import PostContent
from core.context import PostContext, PostStatus
from core.pipeline import Pipeline
from core.registry import build_agent
from core.rubric import RubricConfig, load_all_rubrics, load_rubric
from core.storage import Storage

log = logging.getLogger("service")


class ContentService:
    def __init__(self, settings: Settings | None = None, storage: Storage | None = None) -> None:
        self.settings = settings or get_settings()
        self.storage = storage or Storage(self.settings)

    # -- rubrikalar -----------------------------------------------------------
    def list_rubrics(self, only_enabled: bool = True) -> list[RubricConfig]:
        return load_all_rubrics(only_enabled=only_enabled)

    def rubric_keys(self) -> list[str]:
        return [r.key for r in self.list_rubrics()]

    # -- postlar --------------------------------------------------------------
    async def create_post(
        self,
        rubric_key: str,
        *,
        topic: str | None = None,
        dry_run: bool | None = None,
        publisher_mode: str | None = None,
    ) -> PostContext:
        """To'liq pipeline: material izlash → yozish → tekshirish → chiqarish.

        `publisher_mode` berilsa (masalan "off"), rubrikadagi publisher rejimi
        shu chaqiruv uchun almashtiriladi — adminka postni Telegram'ga tasdiq
        xabari yubormasdan tayyorlab, panelning o'zida ko'rib chiqishi uchun.
        """
        rubric = load_rubric(rubric_key)
        if publisher_mode:
            rubric.raw.setdefault("agents", {}).setdefault("publisher", {})[
                "mode"
            ] = publisher_mode
        return await Pipeline(rubric, self.settings, self.storage).run(
            topic=topic, dry_run=dry_run
        )

    def list_posts(self, rubric_key: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        return self.storage.history(rubric_key, limit=limit)

    def list_published(
        self, rubric_key: str | None = None, limit: int = 30, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Ochiq sayt uchun: chiqarilgan postlar ro'yxati."""
        return self.storage.published_posts(rubric_key, limit=limit, offset=offset)

    def get_post(self, run_id: str) -> dict[str, Any] | None:
        return self.storage.get_post(run_id)

    def get_content(self, run_id: str) -> PostContent | None:
        """Postning tuzilgan ko'rinishi (sayt va adminka shu bilan ishlaydi)."""
        post = self.storage.get_post(run_id)
        if not post or not post.get("content_json"):
            return None
        try:
            return PostContent.from_dict(json.loads(post["content_json"]))
        except (ValueError, TypeError) as exc:
            log.warning("[%s] kontent o'qilmadi: %s", run_id, exc)
            return None

    # -- tasdiqlash -----------------------------------------------------------
    async def publish(self, post: dict[str, Any], *, client: Any = None) -> PostContext:
        """Tasdiqlangan postni barcha kanallarga chiqaradi."""
        rubric = self._rubric_for(post)
        rubric.raw.setdefault("agents", {}).setdefault("publisher", {})["mode"] = "auto"

        ctx = PostContext(
            rubric_key=post.get("rubric") or "noma'lum",
            run_id=post["run_id"],
        )
        ctx.dry_run = self.settings.dry_run     # DRY_RUN=true bo'lsa hech narsa yuborilmaydi
        ctx.post_text = post.get("post_text") or ""
        ctx.image_path = post.get("image_path")
        ctx.audio_path = post.get("audio_path")
        ctx.status = PostStatus.REVIEWED
        ctx.meta["topic"] = post.get("topic") or ""

        if post.get("content_json"):
            try:
                ctx.content = PostContent.from_dict(json.loads(post["content_json"]))
            except (ValueError, TypeError):
                pass
        if ctx.content is None and ctx.post_text:
            ctx.content = PostContent.from_plain_text(ctx.post_text)

        agent = build_agent("publisher", self.settings, rubric)
        if client is not None:
            agent.client_override = client
        await agent.execute(ctx)

        self.storage.upsert_post(ctx)
        self.storage.mark_published(ctx)
        log.info("[%s] chiqarildi: %s", ctx.run_id, ", ".join(rubric.publish_to))
        return ctx

    def reject(self, run_id: str) -> None:
        self.storage.set_status(run_id, PostStatus.REJECTED.value)

    # -- ichki ----------------------------------------------------------------
    def _rubric_for(self, post: dict[str, Any]) -> RubricConfig:
        key = post.get("rubric")
        if key:
            try:
                return load_rubric(key)
            except Exception as exc:  # noqa: BLE001
                log.warning("'%s' rubrikasi o'qilmadi (%s) — standart sozlama", key, exc)
        return RubricConfig(
            key=key or "noma'lum",
            raw={
                "name": key or "Noma'lum rubrika",
                "publish_to": ["telegram"],
                "agents": {"publisher": {"enabled": True, "mode": "auto"}},
            },
        )
