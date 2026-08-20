"""Orchestrator: agentlarni ketma-ket yuritadi va quality retry loop'ini boshqaradi."""

from __future__ import annotations

import logging
from typing import Any

from config.settings import Settings, get_settings
from core.base_agent import AgentError, BaseAgent
from core.context import PostContext, PostStatus, Verdict
from core.registry import build_agent
from core.rubric import RubricConfig, load_rubric
from core.storage import Storage

log = logging.getLogger("pipeline")


class Pipeline:
    """Rubrika config'idagi `pipeline` ro'yxati bo'yicha agentlarni ishga tushiradi."""

    def __init__(
        self,
        rubric: RubricConfig,
        settings: Settings | None = None,
        storage: Storage | None = None,
    ) -> None:
        self.rubric = rubric
        self.settings = settings or get_settings()
        self.storage = storage or Storage(self.settings)
        self.steps: list[str] = rubric.pipeline
        self.agents: dict[str, BaseAgent] = {
            name: build_agent(name, self.settings, rubric) for name in self.steps
        }

    # -- asosiy ---------------------------------------------------------------
    async def run(self, *, topic: str | None = None, dry_run: bool | None = None) -> PostContext:
        ctx = PostContext(rubric_key=self.rubric.key)
        ctx.dry_run = self.settings.dry_run if dry_run is None else dry_run
        if topic:
            ctx.meta["topic"] = topic          # qo'lda berilgan mavzu
            ctx.meta["topic_source"] = "manual"

        log.info(
            "▶ '%s' rubrikasi ishga tushdi | run_id=%s | dry_run=%s",
            self.rubric.name, ctx.run_id, ctx.dry_run,
        )
        self.storage.upsert_post(ctx)

        index = 0
        guard = 0
        max_guard = len(self.steps) * (self.rubric.max_retries + 2) + 10

        while index < len(self.steps):
            guard += 1
            if guard > max_guard:
                ctx.add_error("pipeline", "Cheksiz sikl himoyasi ishga tushdi")
                ctx.status = PostStatus.NEEDS_REVIEW
                break

            step = self.steps[index]
            agent = self.agents[step]

            try:
                ctx = await agent.execute(ctx)
            except AgentError as exc:
                log.error("Pipeline to'xtadi: %s", exc)
                ctx.status = PostStatus.FAILED
                self._persist(ctx)
                return ctx

            self._persist(ctx)

            # Quality agent qaytarganda — kerak bo'lsa orqaga qaytamiz
            rewind_to = self._maybe_rewind(step, ctx)
            if rewind_to is not None:
                index = rewind_to
                continue

            index += 1

        if ctx.status not in {PostStatus.PUBLISHED, PostStatus.FAILED, PostStatus.NEEDS_REVIEW,
                              PostStatus.PENDING_APPROVAL}:
            ctx.status = PostStatus.REVIEWED

        self._persist(ctx)
        self.storage.remember_sources(ctx)
        log.info("■ tugadi | status=%s | urinishlar=%d", ctx.status.value, ctx.attempt + 1)
        return ctx

    # -- quality loop ----------------------------------------------------------
    def _maybe_rewind(self, step: str, ctx: PostContext) -> int | None:
        if step != "quality" or not ctx.quality:
            return None
        if ctx.quality.verdict == Verdict.PASS:
            return None

        if ctx.attempt >= self.rubric.max_retries:
            log.warning(
                "Quality '%s' dedi, lekin urinishlar tugadi (%d). Post qo'lda ko'rikka qoldi.",
                ctx.quality.verdict.value, self.rubric.max_retries,
            )
            ctx.status = PostStatus.NEEDS_REVIEW
            # publisher'ni o'tkazib yuborish uchun pipeline oxiriga sakraymiz
            return len(self.steps)

        ctx.attempt += 1
        ctx.feedback = ctx.quality.feedback_text()

        target = "writer"
        if ctx.quality.verdict == Verdict.REGENERATE:
            target = self.rubric.agent_cfg("quality").get("regenerate_from", "writer")

        if target not in self.steps:
            target = "writer" if "writer" in self.steps else self.steps[0]

        log.info(
            "↻ qayta ishlash: '%s' (urinish %d/%d) — verdict=%s",
            target, ctx.attempt, self.rubric.max_retries, ctx.quality.verdict.value,
        )
        ctx.quality = None
        return self.steps.index(target)

    # -- saqlash ---------------------------------------------------------------
    def _persist(self, ctx: PostContext) -> None:
        try:
            self.storage.save_context(ctx)
            self.storage.upsert_post(ctx)
        except Exception as exc:  # noqa: BLE001
            log.warning("Saqlashda xato: %s", exc)


async def run_rubric(
    rubric_key: str,
    *,
    topic: str | None = None,
    dry_run: bool | None = None,
    settings: Settings | None = None,
) -> PostContext:
    """Qulay yordamchi: rubrika kaliti bo'yicha to'liq pipeline."""
    settings = settings or get_settings()
    rubric = load_rubric(rubric_key)
    return await Pipeline(rubric, settings).run(topic=topic, dry_run=dry_run)


async def run_all_rubrics(**kwargs: Any) -> list[PostContext]:
    from core.rubric import load_all_rubrics

    results = []
    for rubric in load_all_rubrics(only_enabled=True):
        results.append(await Pipeline(rubric).run(**kwargs))
    return results
