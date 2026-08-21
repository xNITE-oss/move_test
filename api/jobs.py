"""Fon vazifalari — post tayyorlash uzoq (1-2 daqiqa) davom etadi.

HTTP so'rov kutib turmasligi uchun tayyorlash asyncio task'da fonda ishlaydi;
API darrov `job_id` qaytaradi, adminka esa holatni so'rab turadi.

Bir jarayonli web xizmat uchun xotiradagi ro'yxat yetarli. Jarayon qayta
ishga tushsa yugurayotgan job yo'qoladi, lekin post yozuvi bazada qoladi.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable

from core.context import PostContext

log = logging.getLogger("api.jobs")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Job:
    def __init__(self, kind: str, rubric: str | None) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.kind = kind                 # "create" | "rewrite"
        self.rubric = rubric
        self.status = "running"          # running | done | error
        self.run_id: str | None = None
        self.post_status: str | None = None
        self.error: str | None = None
        self.created_at = _now()
        self.finished_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "rubric": self.rubric,
            "run_id": self.run_id,
            "post_status": self.post_status,
            "error": self.error,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }


class JobManager:
    #: eng ko'pi bilan shuncha job xotirada saqlanadi (eskisi tozalanadi)
    MAX_JOBS = 200

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._tasks: set[asyncio.Task] = set()

    def start(
        self,
        kind: str,
        rubric: str | None,
        coro_factory: Callable[[], Awaitable[PostContext]],
    ) -> Job:
        job = Job(kind, rubric)
        self._jobs[job.id] = job
        self._prune()

        task = asyncio.create_task(self._run(job, coro_factory))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job

    async def _run(
        self, job: Job, coro_factory: Callable[[], Awaitable[PostContext]]
    ) -> None:
        try:
            ctx = await coro_factory()
            job.run_id = ctx.run_id
            job.post_status = ctx.status.value
            job.status = "done"
        except Exception as exc:  # noqa: BLE001
            log.error("[job %s] xato: %s", job.id, exc, exc_info=True)
            job.error = str(exc)[:500]
            job.status = "error"
        finally:
            job.finished_at = _now()

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def _prune(self) -> None:
        if len(self._jobs) <= self.MAX_JOBS:
            return
        for job in sorted(self._jobs.values(), key=lambda j: j.created_at)[
            : len(self._jobs) - self.MAX_JOBS
        ]:
            self._jobs.pop(job.id, None)
