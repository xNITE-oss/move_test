"""Writer Agent — research natijasi asosida Telegram post yozadi.

Uslub (`tone`, `structure`, `emoji`, `hashtags`) rubrika YAML'idan olinadi,
namunaviy postlar esa `config/style/*.md` faylidan — kodga tegish shart emas.
"""

from __future__ import annotations

from pathlib import Path

from config.settings import BASE_DIR
from core.base_agent import BaseAgent
from core.content import PostContent
from core.context import PostContext, PostStatus
from core.prompts import load_prompt
from core.render import render_telegram
from core.utils import extract_json, normalize_hashtags, strip_code_fence
from providers.llm import get_llm_provider

DEFAULT_STYLE_FILE = "config/style/samples.md"


class WriterAgent(BaseAgent):
    name = "writer"

    async def run(self, ctx: PostContext) -> PostContext:
        max_chars = int(self.opt("max_chars", 900))
        hashtags = normalize_hashtags(self.opt("hashtags") or [])

        prompt = load_prompt(
            "writer_post",
            rubric_name=self.rubric.name,
            rubric_description=self.rubric.get("description", ""),
            post_type=self.opt("post_type", "amaliy maslahat posti"),
            avoid_block=self._avoid_block(),
            language=self.opt("language", self.rubric.language),
            tone=self.opt("tone", "do'stona, sodda, amaliy"),
            address_form=self.opt("address_form", "siz-lab murojaat"),
            max_chars=max_chars,
            emoji_level=self.opt("emoji", "o'rtacha (2-4 ta)"),
            structure=" → ".join(self.opt("structure") or ["hook", "asosiy fikr", "amaliy qadamlar", "CTA"]),
            cta=self.opt("cta", "o'quvchini izohga yoki amalga chorlovchi bitta savol"),
            style_samples=self._style_samples(),
            research_block=ctx.research.as_prompt_block() if ctx.research else "(material yo'q)",
            feedback_block=self._feedback_block(ctx),
            hashtags=" ".join(hashtags) if hashtags else "(hashtag shart emas)",
        )

        llm = get_llm_provider(
            "fake" if ctx.dry_run and self.opt("fake_llm_on_dry_run", True) else None,
            self.settings,
        )
        raw = await llm.complete(
            prompt,
            system=(
                "Sen o'zbek tilida yozadigan tajribali SMM-muharrirsan. "
                "Faqat so'ralgan JSON'ni qaytarasan."
            ),
            max_tokens=int(self.opt("max_tokens", 1500)),
            temperature=float(self.opt("temperature", 0.8)),
            model=self.opt("model"),
        )

        content = self._parse(raw)
        if content.is_empty():
            raise RuntimeError("LLM bo'sh post qaytardi")
        self._repair(content)

        ctx.content = content
        ctx.post_text = render_telegram(content, max_chars=max_chars, hashtags=hashtags)
        ctx.status = PostStatus.DRAFTED
        ctx.feedback = ""  # feedback ishlatildi
        self.log.info(
            "post yozildi (%d belgi, urinish %d): %s",
            len(ctx.post_text), ctx.attempt + 1, content.title[:60],
        )
        return ctx

    def _repair(self, content: PostContent) -> None:
        """Model unutgan mayda narsalarni tiklaydi (qayta so'ramasdan)."""
        if not content.cta and content.body and content.body[-1].rstrip().endswith("?"):
            # savol body'ning oxirida qolib ketgan — CTA sifatida ajratamiz
            content.cta = content.body.pop().strip()
            self.log.info("CTA body oxiridan ajratib olindi")
        if not content.cta:
            self.log.warning("Model CTA qaytarmadi — Quality buni rad etishi mumkin")

    def _parse(self, raw: str) -> PostContent:
        """JSON kutamiz; kelmasa — matnni bo'laklarga ajratamiz (post yo'qolmasin)."""
        try:
            data = extract_json(raw)
            if isinstance(data, dict):
                return PostContent.from_dict(data)
            raise ValueError("JSON obyekt emas")
        except ValueError as exc:
            self.log.warning("JSON o'qilmadi (%s) — matn sifatida ajratilmoqda", exc)
            return PostContent.from_plain_text(strip_code_fence(raw))

    # -- ichki ------------------------------------------------------------------
    def _style_samples(self) -> str:
        rel = self.opt("style_file", DEFAULT_STYLE_FILE)
        path = Path(rel)
        if not path.is_absolute():
            path = BASE_DIR / rel
        if not path.exists():
            self.log.warning("Uslub namunalari fayli topilmadi: %s", path)
            return "(namuna berilmagan — umumiy do'stona ohangda yoz)"
        text = path.read_text(encoding="utf-8").strip()
        return text or "(namuna berilmagan)"

    def _avoid_block(self) -> str:
        """Rubrikaga xos qo'shimcha taqiqlar (`agents.writer.avoid`)."""
        items = self.opt("avoid") or []
        if not items:
            return ""
        return "## Shu rubrikada alohida qochiladigan narsalar\n" + "\n".join(
            f"- {item}" for item in items
        )

    def _feedback_block(self, ctx: PostContext) -> str:
        if not ctx.feedback:
            return ""
        return (
            "## QAYTA ISHLASH IZOHI\n"
            "Oldingi variant tasdiqdan o'tmadi. Quyidagilarni albatta tuzat:\n"
            f"{ctx.feedback}\n\n"
            "Oldingi variant:\n---\n"
            f"{ctx.post_text}\n---"
        )
