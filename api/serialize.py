"""Bazadagi post yozuvini API javob shakliga o'giradi."""

from __future__ import annotations

import json
import logging
from typing import Any

from core.content import PostContent
from core.render import render_html

log = logging.getLogger("api.serialize")

_SUMMARY_FIELDS = (
    "run_id", "rubric", "topic", "status", "quality_score",
    "created_at", "updated_at", "published_at", "telegram_message_id",
)


def content_of(post: dict[str, Any]) -> PostContent | None:
    """Post yozuvidan tuzilgan kontentni tiklaydi (content_json yoki matndan)."""
    raw = post.get("content_json")
    if raw:
        try:
            return PostContent.from_dict(json.loads(raw))
        except (ValueError, TypeError) as exc:
            log.warning("[%s] content_json o'qilmadi: %s", post.get("run_id"), exc)
    if post.get("post_text"):
        return PostContent.from_plain_text(post["post_text"])
    return None


def post_summary(post: dict[str, Any]) -> dict[str, Any]:
    return {k: post.get(k) for k in _SUMMARY_FIELDS}


def post_detail(post: dict[str, Any]) -> dict[str, Any]:
    content = content_of(post)
    data = post_summary(post)
    data.update(
        {
            "post_text": post.get("post_text"),
            "content": content.to_dict() if content else None,
            "html": render_html(content) if content else None,
            "web_path": post.get("web_path"),
            "image_path": post.get("image_path"),
            "audio_path": post.get("audio_path"),
        }
    )
    return data


def public_summary(post: dict[str, Any]) -> dict[str, Any] | None:
    content = content_of(post)
    if content is None or not content.title:
        return None
    return {
        "slug": content.slug,
        "run_id": post["run_id"],
        "rubric": post.get("rubric"),
        "title": content.title,
        "lead": content.lead,
        "tags": content.tags,
        "reading_minutes": content.reading_minutes(),
        "published_at": post.get("published_at") or post.get("created_at"),
    }


def public_detail(post: dict[str, Any]) -> dict[str, Any] | None:
    content = content_of(post)
    if content is None or not content.title:
        return None
    summary = public_summary(post)
    assert summary is not None
    summary.update(
        {
            "html": render_html(content),
            "body": content.body,
            "takeaway": content.takeaway,
            "cta": content.cta,
        }
    )
    return summary
