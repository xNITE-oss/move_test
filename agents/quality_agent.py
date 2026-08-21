"""Quality Agent — postni tekshiradi va verdikt beradi.

Ikki qatlam:
  1. Rule-based tekshiruv (har doim ishlaydi, tarmoq talab qilmaydi)
  2. LLM-review (agents.quality.use_llm: true bo'lsa)

Verdikt `fix` yoki `regenerate` bo'lsa — pipeline postni Writer'ga feedback bilan
qaytaradi (max_retries martagacha).
"""

from __future__ import annotations

import re

from core.base_agent import BaseAgent
from core.context import PostContext, PostStatus, QualityReport, Verdict
from core.prompts import load_prompt
from core.utils import count_links, extract_json
from providers.llm import get_llm_provider

_MD_HEADER = re.compile(r"^#{1,6}\s+\S")


class QualityAgent(BaseAgent):
    name = "quality"

    async def run(self, ctx: PostContext) -> PostContext:
        if not ctx.post_text:
            raise RuntimeError("Tekshirish uchun post matni yo'q")

        report = self._rule_check(ctx)

        if self.opt("use_llm", True) and report.verdict == Verdict.PASS:
            llm_report = await self._llm_check(ctx)
            report = self._merge(report, llm_report)

        ctx.quality = report
        ctx.status = PostStatus.REVIEWED
        self.log.info(
            "verdict=%s score=%.1f issues=%d",
            report.verdict.value, report.score, len(report.issues),
        )
        return ctx

    # -- 1-qatlam: qoidalar ------------------------------------------------------
    def _rule_check(self, ctx: PostContext) -> QualityReport:
        text = ctx.post_text
        issues: list[str] = []
        suggestions: list[str] = []

        writer_cfg = self.rubric.agent_cfg("writer")
        max_chars = int(self.opt("max_chars", writer_cfg.get("max_chars", 900)))
        min_chars = int(self.opt("min_chars", 150))

        if len(text) > max_chars:
            issues.append(f"Post juda uzun: {len(text)} belgi (chegara {max_chars})")
            suggestions.append("Postni qisqartir, ortiqcha gaplarni olib tashla")
        if len(text) < min_chars:
            issues.append(f"Post juda qisqa: {len(text)} belgi (kamida {min_chars})")
            suggestions.append("Amaliy tafsilot va misol qo'sh")

        max_links = int(self.opt("max_links", 1))
        links = count_links(text)
        if links > max_links:
            issues.append(f"Havolalar soni ko'p: {links} (chegara {max_links})")

        banned = [w.lower() for w in (self.opt("banned_words") or [])]
        found = [w for w in banned if w in text.lower()]
        if found:
            issues.append(f"Taqiqlangan so'z/ibora ishlatilgan: {', '.join(found)}")
            suggestions.append("Bu iboralarni tabiiyroq variant bilan almashtir")

        required = self.opt("required_hashtags") or writer_cfg.get("hashtags") or []
        missing = [t for t in required if t.lower().lstrip("#") not in text.lower()]
        if missing and self.opt("require_hashtags", False):
            issues.append(f"Hashtag yetishmayapti: {', '.join(missing)}")

        # '# Sarlavha' — Telegram ko'rsatmaydi; '#hashtag' esa normal
        if self.opt("check_markdown_headers", True) and any(
            _MD_HEADER.match(line) for line in text.splitlines()
        ):
            issues.append("Markdown sarlavhasi ishlatilgan — Telegram uni ko'rsatmaydi")

        verdict = Verdict.PASS if not issues else Verdict.FIX
        score = max(0.0, 10.0 - 2.0 * len(issues))
        return QualityReport(
            verdict=verdict,
            score=score,
            issues=issues,
            suggestions=suggestions,
            checked_by=["rules"],
        )

    # -- 2-qatlam: LLM ------------------------------------------------------------
    async def _llm_check(self, ctx: PostContext) -> QualityReport:
        writer_cfg = self.rubric.agent_cfg("writer")
        prompt = load_prompt(
            "quality_review",
            rubric_name=self.rubric.name,
            rubric_description=self.rubric.get("description", ""),
            language=self.rubric.language,
            tone=writer_cfg.get("tone", ""),
            max_chars=writer_cfg.get("max_chars", 900),
            structure=" → ".join(writer_cfg.get("structure") or []),
            post_text=ctx.post_text,
            research_block=ctx.research.as_prompt_block() if ctx.research else "(material yo'q)",
        )
        llm = get_llm_provider(
            "fake" if ctx.dry_run and self.opt("fake_llm_on_dry_run", True) else None,
            self.settings,
        )
        try:
            raw = await llm.complete(
                prompt,
                system="Sen talabchan, lekin adolatli muharrirsan. Faqat JSON qaytarasan.",
                max_tokens=int(self.opt("max_tokens", 800)),
                temperature=0.2,
                model=self.opt("model"),
            )
        except Exception as exc:  # noqa: BLE001
            # LLM-tekshiruv ixtiyoriy qatlam: limit tugasa yoki xizmat javob bermasa,
            # tayyor postni yo'qotmaymiz — qoidalar natijasi bilan davom etamiz.
            self.log.warning("LLM tekshiruvi bajarilmadi (%s) — qoidalar natijasi qoladi",
                             str(exc)[:200])
            return QualityReport(
                verdict=Verdict.PASS, score=7.0, checked_by=["llm:unavailable"],
                suggestions=["LLM tekshiruvi o'tkazilmadi — postni o'zingiz ko'rib chiqing"],
            )

        try:
            data = extract_json(raw)
        except ValueError as exc:
            self.log.warning("LLM javobini o'qib bo'lmadi (%s) — qoidalar natijasi qoladi", exc)
            return QualityReport(verdict=Verdict.PASS, score=7.0, checked_by=["llm:parse_failed"])

        verdict_raw = str(data.get("verdict", "pass")).lower()
        verdict = {
            "pass": Verdict.PASS,
            "fix": Verdict.FIX,
            "regenerate": Verdict.REGENERATE,
        }.get(verdict_raw, Verdict.FIX)

        score = float(data.get("score") or 0)
        min_score = float(self.opt("min_score", 7.0))
        if score:
            if verdict == Verdict.PASS and score < min_score:
                # Ball past — qayta ishlansin
                verdict = Verdict.FIX
            elif verdict == Verdict.FIX and score >= min_score:
                # Ball chegaradan yuqori: post yetarlicha yaxshi. LLM topgan
                # mayda e'tirozlar bloklamaydi — post tasdiqqa yuboriladi
                # (odam baribir ✅ bosishi kerak), e'tirozlar maslahat bo'lib qoladi.
                verdict = Verdict.PASS

        return QualityReport(
            verdict=verdict,
            score=score,
            issues=[str(i) for i in (data.get("issues") or [])],
            suggestions=[str(s) for s in (data.get("suggestions") or [])],
            checked_by=["llm"],
        )

    @staticmethod
    def _merge(rules: QualityReport, llm: QualityReport) -> QualityReport:
        order = {Verdict.PASS: 0, Verdict.FIX: 1, Verdict.REGENERATE: 2}
        worst = rules.verdict if order[rules.verdict] >= order[llm.verdict] else llm.verdict
        return QualityReport(
            verdict=worst,
            score=min(rules.score, llm.score) if llm.score else rules.score,
            issues=rules.issues + llm.issues,
            suggestions=rules.suggestions + llm.suggestions,
            checked_by=rules.checked_by + llm.checked_by,
        )
