"""Pipeline bo'ylab yuruvchi yagona holat obyekti."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from core.content import PostContent


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{uuid.uuid4().hex[:6]}"


class PostStatus(str, Enum):
    CREATED = "created"
    RESEARCHED = "researched"
    DRAFTED = "drafted"
    MEDIA_READY = "media_ready"
    REVIEWED = "reviewed"
    PENDING_APPROVAL = "pending_approval"
    PUBLISHED = "published"
    NEEDS_REVIEW = "needs_review"   # quality loop tugadi, odam ko'rishi kerak
    REJECTED = "rejected"           # odam ❌ bosdi
    FAILED = "failed"


class Verdict(str, Enum):
    PASS = "pass"            # chiqarish mumkin
    FIX = "fix"              # kichik tuzatish — Writer'ga feedback bilan qaytadi
    REGENERATE = "regenerate"  # butunlay qayta yozilsin


@dataclass
class Source:
    title: str = ""
    url: str = ""
    snippet: str = ""
    published_at: str | None = None
    score: float | None = None


@dataclass
class ResearchResult:
    topic: str = ""
    angle: str = ""
    summary: str = ""
    key_points: list[str] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)

    def as_prompt_block(self) -> str:
        lines = [f"MAVZU: {self.topic}"]
        if self.angle:
            lines.append(f"YONDASHUV: {self.angle}")
        if self.summary:
            lines.append(f"XULOSA: {self.summary}")
        if self.key_points:
            lines.append("ASOSIY FAKTLAR:")
            lines += [f"- {p}" for p in self.key_points]
        if self.sources:
            lines.append("MANBALAR:")
            lines += [f"- {s.title} ({s.url})" for s in self.sources[:8]]
        return "\n".join(lines)


@dataclass
class QualityReport:
    verdict: Verdict = Verdict.PASS
    score: float = 0.0
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    checked_by: list[str] = field(default_factory=list)

    def feedback_text(self) -> str:
        parts = []
        if self.issues:
            parts.append("Topilgan kamchiliklar:\n" + "\n".join(f"- {i}" for i in self.issues))
        if self.suggestions:
            parts.append("Tavsiyalar:\n" + "\n".join(f"- {s}" for s in self.suggestions))
        return "\n\n".join(parts)


@dataclass
class PostContext:
    """Har bir agent shu obyektni o'qiydi va boyitib qaytaradi."""

    rubric_key: str
    run_id: str = field(default_factory=new_run_id)
    status: PostStatus = PostStatus.CREATED

    # Research -> Writer
    research: ResearchResult | None = None

    # Writer -> renderer'lar (Telegram, sayt, ...)
    content: PostContent | None = None

    # Writer -> Image/Audio/Quality
    post_text: str = ""
    image_prompt: str = ""
    image_path: str | None = None
    audio_path: str | None = None

    # Quality loop
    quality: QualityReport | None = None
    feedback: str = ""          # Writer'ga qayta yozish uchun izoh
    attempt: int = 0            # nechinchi urinish

    # Publisher
    publish_at: str | None = None
    telegram_message_id: int | None = None

    # Xizmat maydonlari
    dry_run: bool = False
    errors: list[str] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)

    # -- yordamchilar ------------------------------------------------------
    @property
    def topic(self) -> str:
        return self.research.topic if self.research else self.meta.get("topic", "")

    def add_error(self, agent: str, message: str) -> None:
        self.errors.append(f"[{agent}] {message}")

    def log_step(self, agent: str, status: str, duration_ms: int, note: str = "") -> None:
        self.trace.append(
            {
                "agent": agent,
                "status": status,
                "duration_ms": duration_ms,
                "note": note,
                "at": _now(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        if self.quality:
            data["quality"]["verdict"] = self.quality.verdict.value
        return data
