"""Audio Agent — postni ovozli formatga aylantiradi (ElevenLabs).

HOLAT: skeleton. Yoqish uchun:
  1. .env → TTS_PROVIDER=elevenlabs, ELEVENLABS_API_KEY=..., ELEVENLABS_VOICE_ID=...
  2. rubrika YAML → agents.audio.enabled: true
"""

from __future__ import annotations

import re

from core.base_agent import AgentSkip, BaseAgent
from core.context import PostContext, PostStatus
from core.storage import Storage
from providers.tts import get_tts_provider

_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF←-⇿⬀-⯿]+"
)
_HASHTAG = re.compile(r"#\S+")
_URL = re.compile(r"https?://\S+")


class AudioAgent(BaseAgent):
    name = "audio"

    @property
    def optional(self) -> bool:  # type: ignore[override]
        """`audio_required: true` bo'lsa — audiosiz post chiqmaydi."""
        return not self.rubric.audio_required

    async def run(self, ctx: PostContext) -> PostContext:
        provider = get_tts_provider(
            "fake" if ctx.dry_run and self.opt("fake_on_dry_run", True) else None,
            self.settings,
        )
        if not provider.available:
            message = "TTS provider o'chirilgan (TTS_PROVIDER=none)"
            if self.rubric.audio_required:
                raise RuntimeError(f"{message}, lekin rubrikada audio_required: true")
            raise AgentSkip(message)
        if not ctx.post_text:
            raise AgentSkip("Post matni yo'q")

        text = self._prepare_text(ctx.post_text)
        max_chars = int(self.opt("max_chars", 2500))
        if len(text) > max_chars:
            raise AgentSkip(f"Matn juda uzun ({len(text)} > {max_chars})")

        storage = Storage(self.settings)
        out_path = storage.media_path(ctx, "audio.mp3")
        result = await provider.synthesize(
            text, out_path, voice_id=self.opt("voice_id")
        )
        if result is None:
            raise AgentSkip("Provider audio qaytarmadi")

        ctx.audio_path = str(result)
        ctx.status = PostStatus.MEDIA_READY
        return ctx

    def _prepare_text(self, text: str) -> str:
        """Ovoz uchun matnni tozalash: emoji, hashtag, havolalar o'qilmasin."""
        if self.opt("strip_emoji", True):
            text = _EMOJI.sub("", text)
        if self.opt("strip_hashtags", True):
            text = _HASHTAG.sub("", text)
        if self.opt("strip_urls", True):
            text = _URL.sub("", text)
        intro = self.opt("intro", "")
        outro = self.opt("outro", "")
        parts = [p for p in (intro, text.strip(), outro) if p]
        return re.sub(r"\n{3,}", "\n\n", "\n\n".join(parts)).strip()
