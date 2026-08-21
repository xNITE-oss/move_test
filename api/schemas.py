"""Pydantic modellar — so'rov/javob shakllari."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


# -- auth --------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_hours: int


# -- rubrikalar --------------------------------------------------------------
class RubricOut(BaseModel):
    key: str
    name: str
    cron: str | None = None
    publish_to: list[str] = []


# -- postlar -----------------------------------------------------------------
class CreatePostRequest(BaseModel):
    rubric: str
    topic: str | None = None


class PostSummary(BaseModel):
    run_id: str
    rubric: str | None = None
    topic: str | None = None
    status: str
    quality_score: float | None = None
    created_at: str | None = None
    updated_at: str | None = None
    published_at: str | None = None
    telegram_message_id: int | None = None


class PostDetail(PostSummary):
    post_text: str | None = None
    content: dict[str, Any] | None = None   # PostContent (title, lead, body, ...)
    html: str | None = None                 # sayt/adminka preview uchun
    web_path: str | None = None
    image_path: str | None = None
    audio_path: str | None = None


# -- fon vazifasi (job) ------------------------------------------------------
class JobOut(BaseModel):
    id: str
    kind: str                 # "create" | "rewrite"
    status: str               # "running" | "done" | "error"
    rubric: str | None = None
    run_id: str | None = None
    post_status: str | None = None
    error: str | None = None
    created_at: str
    finished_at: str | None = None


# -- ochiq sayt --------------------------------------------------------------
class PublicPostSummary(BaseModel):
    slug: str
    run_id: str
    rubric: str | None = None
    title: str
    lead: str = ""
    tags: list[str] = []
    reading_minutes: int = 1
    published_at: str | None = None


class PublicPostDetail(PublicPostSummary):
    html: str
    body: list[str] = []
    takeaway: str = ""
    cta: str = ""
