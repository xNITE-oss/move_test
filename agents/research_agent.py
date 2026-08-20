"""Research Agent — rubrika bo'yicha internetdan mavzu va faktlarni topadi.

Bosqichlar:
  1. rubrika YAML'idagi `queries` bo'yicha qidiruv (parallel)
  2. takroriy va oldin ishlatilgan URL'larni filtrlash
  3. LLM yordamida bitta aniq mavzu tanlash + faktlarni JSON'ga yig'ish
"""

from __future__ import annotations

import asyncio

from core.base_agent import AgentSkip, BaseAgent
from core.context import PostContext, PostStatus, ResearchResult, Source
from core.prompts import load_prompt
from core.storage import Storage
from core.utils import extract_json
from providers.llm import get_llm_provider
from providers.search import get_search_provider


class ResearchAgent(BaseAgent):
    name = "research"

    async def run(self, ctx: PostContext) -> PostContext:
        queries: list[str] = self.opt("queries") or [self.rubric.name]
        max_results = int(self.opt("max_results", 5))
        recency_days = self.opt("recency_days")
        storage = Storage(self.settings)

        provider_name = self.opt("provider") or ("fake" if ctx.dry_run else None)
        search = get_search_provider(provider_name, self.settings)

        self.log.info("qidiruv: %d ta so'rov (%s)", len(queries), search.name)
        results = await asyncio.gather(
            *(
                search.search(q, max_results=max_results, recency_days=recency_days)
                for q in queries
            ),
            return_exceptions=True,
        )

        sources: list[Source] = []
        seen: set[str] = set()
        used = storage.used_urls(ctx.rubric_key) if self.opt("avoid_used_sources", True) else set()

        for query, result in zip(queries, results):
            if isinstance(result, Exception):
                self.log.warning("'%s' so'rovi xato berdi: %s", query, result)
                continue
            for src in result:
                if not src.url or src.url in seen or src.url in used:
                    continue
                seen.add(src.url)
                sources.append(src)

        if not sources:
            message = "Qidiruvdan yangi manba topilmadi (hammasi oldin ishlatilgan bo'lishi mumkin)"
            if self.opt("skip_if_empty", False):
                raise AgentSkip(message)
            raise RuntimeError(message)

        limit = int(self.opt("max_sources_to_llm", 12))
        sources = sources[:limit]
        self.log.info("%d ta noyob manba topildi", len(sources))

        research = await self._pick_topic(ctx, sources, storage)
        ctx.research = research
        ctx.status = PostStatus.RESEARCHED
        self.log.info("mavzu: %s", research.topic)
        return ctx

    # -- ichki -----------------------------------------------------------------
    async def _pick_topic(
        self, ctx: PostContext, sources: list[Source], storage: Storage
    ) -> ResearchResult:
        sources_block = "\n\n".join(
            f"[{i + 1}] {s.title}\nURL: {s.url}\n{s.snippet[:800]}"
            for i, s in enumerate(sources)
        )
        recent = storage.recent_topics(ctx.rubric_key, limit=int(self.opt("avoid_last_n", 25)))
        recent_block = "\n".join(f"- {t}" for t in recent) or "(hali post chiqmagan)"

        manual_topic = ctx.meta.get("topic")
        manual_block = (
            f"## MAJBURIY MAVZU\nFoydalanuvchi aynan shu mavzuni so'radi: «{manual_topic}». "
            f"Mavzuni o'zgartirma, faqat shu bo'yicha material yig'."
            if manual_topic
            else ""
        )

        prompt = load_prompt(
            "research_topic",
            rubric_name=self.rubric.name,
            rubric_description=self.rubric.get("description", ""),
            recent_topics=recent_block,
            sources_block=sources_block,
            manual_topic_block=manual_block,
        )

        llm = get_llm_provider("fake" if ctx.dry_run and self.opt("fake_llm_on_dry_run", True) else None,
                              self.settings)
        raw = await llm.complete(
            prompt,
            system="Sen aniq, faktlarga tayanadigan kontent-tadqiqotchisan. Faqat JSON qaytarasan.",
            max_tokens=int(self.opt("max_tokens", 1200)),
            temperature=float(self.opt("temperature", 0.4)),
            model=self.opt("model"),
        )
        data = extract_json(raw)

        picked_idx = data.get("source_indexes") or list(range(1, min(len(sources), 5) + 1))
        picked = [sources[i - 1] for i in picked_idx if 1 <= int(i) <= len(sources)]

        return ResearchResult(
            topic=str(data.get("topic") or manual_topic or "").strip(),
            angle=str(data.get("angle") or "").strip(),
            summary=str(data.get("summary") or "").strip(),
            key_points=[str(p) for p in (data.get("key_points") or [])],
            sources=picked or sources[:5],
        )
