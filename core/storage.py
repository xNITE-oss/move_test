"""Natijalarni saqlash: fayllar (data/runs/...) + SQLite holat bazasi."""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from config.settings import Settings
from core.context import PostContext

log = logging.getLogger("storage")

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    run_id              TEXT PRIMARY KEY,
    rubric              TEXT NOT NULL,
    topic               TEXT,
    status              TEXT NOT NULL,
    post_text           TEXT,
    image_path          TEXT,
    audio_path          TEXT,
    quality_score       REAL,
    telegram_message_id INTEGER,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    published_at        TEXT
);
CREATE INDEX IF NOT EXISTS idx_posts_rubric_created ON posts (rubric, created_at DESC);

CREATE TABLE IF NOT EXISTS bot_state (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS used_sources (
    url        TEXT NOT NULL,
    rubric     TEXT NOT NULL,
    run_id     TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (url, rubric)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Storage:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.runs_dir = settings.runs_dir
        self.db_path = settings.db_path
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # -- DB ------------------------------------------------------------------
    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # -- fayllar --------------------------------------------------------------
    def run_dir(self, ctx: PostContext) -> Path:
        path = self.runs_dir / ctx.rubric_key / ctx.run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def media_path(self, ctx: PostContext, filename: str) -> Path:
        return self.run_dir(ctx) / filename

    def save_context(self, ctx: PostContext) -> Path:
        path = self.run_dir(ctx) / "context.json"
        path.write_text(
            json.dumps(ctx.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if ctx.post_text:
            (self.run_dir(ctx) / "post.txt").write_text(ctx.post_text, encoding="utf-8")
        return path

    # -- holat ---------------------------------------------------------------
    def upsert_post(self, ctx: PostContext) -> None:
        score = ctx.quality.score if ctx.quality else None
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO posts (run_id, rubric, topic, status, post_text, image_path,
                                   audio_path, quality_score, telegram_message_id,
                                   created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(run_id) DO UPDATE SET
                    topic=excluded.topic,
                    status=excluded.status,
                    post_text=excluded.post_text,
                    image_path=excluded.image_path,
                    audio_path=excluded.audio_path,
                    quality_score=excluded.quality_score,
                    telegram_message_id=excluded.telegram_message_id,
                    updated_at=excluded.updated_at
                """,
                (
                    ctx.run_id,
                    ctx.rubric_key,
                    ctx.topic or None,
                    ctx.status.value,
                    ctx.post_text or None,
                    ctx.image_path,
                    ctx.audio_path,
                    score,
                    ctx.telegram_message_id,
                    ctx.created_at,
                    _now(),
                ),
            )

    def mark_published(self, ctx: PostContext) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE posts SET status=?, published_at=?, telegram_message_id=?, updated_at=? "
                "WHERE run_id=?",
                (ctx.status.value, _now(), ctx.telegram_message_id, _now(), ctx.run_id),
            )

    def remember_sources(self, ctx: PostContext) -> None:
        if not ctx.research:
            return
        rows = [
            (s.url, ctx.rubric_key, ctx.run_id, _now())
            for s in ctx.research.sources
            if s.url
        ]
        if not rows:
            return
        with self._conn() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO used_sources (url, rubric, run_id, created_at) "
                "VALUES (?,?,?,?)",
                rows,
            )

    # -- o'qish ---------------------------------------------------------------
    def recent_topics(self, rubric_key: str, limit: int = 25) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT topic FROM posts WHERE rubric=? AND topic IS NOT NULL "
                "ORDER BY created_at DESC LIMIT ?",
                (rubric_key, limit),
            ).fetchall()
        return [r["topic"] for r in rows]

    def used_urls(self, rubric_key: str, limit: int = 300) -> set[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT url FROM used_sources WHERE rubric=? ORDER BY created_at DESC LIMIT ?",
                (rubric_key, limit),
            ).fetchall()
        return {r["url"] for r in rows}

    def get_post(self, run_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM posts WHERE run_id=?", (run_id,)).fetchone()
        return dict(row) if row else None

    def set_status(self, run_id: str, status: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE posts SET status=?, updated_at=? WHERE run_id=?",
                (status, _now(), run_id),
            )

    # -- bot holati (Telegram getUpdates offset va h.k.) -----------------------
    def get_state(self, key: str, default: str | None = None) -> str | None:
        with self._conn() as conn:
            row = conn.execute("SELECT value FROM bot_state WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_state(self, key: str, value: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO bot_state (key, value) VALUES (?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)),
            )

    def history(self, rubric_key: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        query = "SELECT * FROM posts"
        params: tuple = ()
        if rubric_key:
            query += " WHERE rubric=?"
            params = (rubric_key,)
        query += " ORDER BY created_at DESC LIMIT ?"
        params += (limit,)
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(query, params).fetchall()]
