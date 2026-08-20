"""Image Agent — post uchun rasm generatsiya qiladi (Gemini / Nano Banana).

HOLAT: skeleton. Tuzilma tayyor, provider qatlami ulangan.
Yoqish uchun:
  1. .env → IMAGE_PROVIDER=gemini, GEMINI_API_KEY=...
  2. rubrika YAML → agents.image.enabled: true
Provider o'chirilgan bo'lsa, agent jim o'tkazib yuboriladi (pipeline to'xtamaydi).
"""

from __future__ import annotations

from core.base_agent import AgentSkip, BaseAgent
from core.context import PostContext, PostStatus
from core.prompts import load_prompt
from core.storage import Storage
from core.utils import strip_code_fence
from providers.image import get_image_provider
from providers.llm import get_llm_provider


class ImageAgent(BaseAgent):
    name = "image"

    @property
    def optional(self) -> bool:  # type: ignore[override]
        """`image_required: true` bo'lsa — rasmsiz post chiqmaydi."""
        return not self.rubric.image_required

    async def run(self, ctx: PostContext) -> PostContext:
        provider = get_image_provider(
            "fake" if ctx.dry_run and self.opt("fake_on_dry_run", True) else None,
            self.settings,
        )
        if not provider.available:
            message = "Image provider o'chirilgan (IMAGE_PROVIDER=none)"
            if self.rubric.image_required:
                raise RuntimeError(f"{message}, lekin rubrikada image_required: true")
            raise AgentSkip(message)

        if not ctx.post_text:
            raise AgentSkip("Post matni yo'q — rasm uchun asos yo'q")

        ctx.image_prompt = await self._build_prompt(ctx)
        self.log.debug("image prompt: %s", ctx.image_prompt[:200])

        storage = Storage(self.settings)
        out_path = storage.media_path(ctx, "image.png")
        result = await provider.generate(ctx.image_prompt, out_path)

        if result is None:
            raise AgentSkip("Provider rasm qaytarmadi")

        ctx.image_path = str(result)
        ctx.status = PostStatus.MEDIA_READY
        return ctx

    async def _build_prompt(self, ctx: PostContext) -> str:
        # Tayyor prompt shabloni rubrikada bo'lsa — LLM'ga umuman murojaat qilmaymiz
        static = self.opt("static_prompt")
        if static:
            return str(static)

        prompt = load_prompt(
            "image_prompt",
            post_text=ctx.post_text,
            image_style=self.opt(
                "style",
                "clean editorial photography, natural light, outdoor active lifestyle, warm tones",
            ),
            aspect_ratio=self.opt("aspect_ratio", "16:9"),
        )
        llm = get_llm_provider(
            "fake" if ctx.dry_run and self.opt("fake_llm_on_dry_run", True) else None,
            self.settings,
        )
        raw = await llm.complete(
            prompt,
            system="You write concise, concrete image-generation prompts in English.",
            max_tokens=400,
            temperature=0.7,
        )
        return strip_code_fence(raw)
