"""Adminka endpointlari — token bilan himoyalangan.

Hammasi core/service.py:ContentService ni chaqiradi. Botdagi har bir amal
(post tayyorlash, ro'yxat, tasdiqlash, bekor, qayta yozish) shu yerda bor.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from api import serialize
from api.deps import get_jobs, get_service, get_settings_dep
from api.jobs import JobManager
from api.schemas import (
    CreatePostRequest,
    JobOut,
    LoginRequest,
    PostDetail,
    PostSummary,
    RubricOut,
    TokenResponse,
)
from api.security import create_token, require_admin, verify_credentials
from config.settings import Settings
from core.service import ContentService

log = logging.getLogger("api.admin")

router = APIRouter(prefix="/api", tags=["admin"])


# -- auth --------------------------------------------------------------------
@router.post("/auth/login", response_model=TokenResponse)
async def login(
    body: LoginRequest, settings: Settings = Depends(get_settings_dep)
) -> TokenResponse:
    if not verify_credentials(settings, body.username, body.password):
        raise HTTPException(status_code=401, detail="Login yoki parol noto'g'ri")
    token = create_token(settings, body.username)
    return TokenResponse(access_token=token, expires_in_hours=settings.token_ttl_hours)


@router.get("/auth/me")
async def me(admin: str = Depends(require_admin)) -> dict:
    return {"username": admin}


# -- rubrikalar --------------------------------------------------------------
@router.get("/rubrics", response_model=list[RubricOut])
async def rubrics(
    _: str = Depends(require_admin), service: ContentService = Depends(get_service)
) -> list[RubricOut]:
    return [
        RubricOut(key=r.key, name=r.name, cron=r.cron, publish_to=r.publish_to)
        for r in service.list_rubrics()
    ]


# -- postlar -----------------------------------------------------------------
@router.post("/posts", response_model=JobOut, status_code=202)
async def create_post(
    body: CreatePostRequest,
    _: str = Depends(require_admin),
    service: ContentService = Depends(get_service),
    jobs: JobManager = Depends(get_jobs),
) -> JobOut:
    """Post tayyorlashni fonda boshlaydi (uzoq davom etadi) va job qaytaradi."""
    if body.rubric not in service.rubric_keys():
        raise HTTPException(status_code=404, detail=f"'{body.rubric}' rubrikasi yo'q")

    # Adminka postni panelda ko'rib chiqadi — Telegram'ga tasdiq xabari yubormaymiz.
    job = jobs.start(
        "create",
        body.rubric,
        lambda: service.create_post(
            body.rubric, topic=body.topic, publisher_mode="off"
        ),
    )
    return JobOut(**job.to_dict())


@router.get("/posts", response_model=list[PostSummary])
async def list_posts(
    _: str = Depends(require_admin),
    service: ContentService = Depends(get_service),
    rubric: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=200),
) -> list[PostSummary]:
    rows = service.list_posts(rubric_key=rubric, limit=limit)
    return [PostSummary(**serialize.post_summary(r)) for r in rows]


@router.get("/posts/{run_id}", response_model=PostDetail)
async def get_post(
    run_id: str,
    _: str = Depends(require_admin),
    service: ContentService = Depends(get_service),
) -> PostDetail:
    post = service.get_post(run_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post topilmadi")
    return PostDetail(**serialize.post_detail(post))


@router.post("/posts/{run_id}/publish", response_model=PostSummary)
async def publish_post(
    run_id: str,
    _: str = Depends(require_admin),
    service: ContentService = Depends(get_service),
) -> PostSummary:
    """Tasdiqlangan postni Telegram kanalga chiqaradi (va sayt ro'yxatiga qo'shadi)."""
    post = service.get_post(run_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post topilmadi")
    if post["status"] == "published":
        raise HTTPException(status_code=409, detail="Post allaqachon chiqarilgan")

    ctx = await service.publish(post)
    updated = service.get_post(run_id) or {}
    log.info("[%s] adminka orqali chiqarildi: %s", run_id, ctx.status.value)
    return PostSummary(**serialize.post_summary(updated))


@router.post("/posts/{run_id}/reject")
async def reject_post(
    run_id: str,
    _: str = Depends(require_admin),
    service: ContentService = Depends(get_service),
) -> dict:
    if not service.get_post(run_id):
        raise HTTPException(status_code=404, detail="Post topilmadi")
    service.reject(run_id)
    return {"ok": True, "run_id": run_id, "status": "rejected"}


@router.post("/posts/{run_id}/rewrite", response_model=JobOut, status_code=202)
async def rewrite_post(
    run_id: str,
    _: str = Depends(require_admin),
    service: ContentService = Depends(get_service),
    jobs: JobManager = Depends(get_jobs),
) -> JobOut:
    """Eski postni bekor qiladi va o'sha rubrika bo'yicha yangisini tayyorlaydi."""
    post = service.get_post(run_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post topilmadi")
    rubric_key = post.get("rubric")
    if not rubric_key or rubric_key not in service.rubric_keys():
        raise HTTPException(status_code=400, detail="Rubrika noma'lum — qayta yozib bo'lmaydi")

    service.reject(run_id)
    job = jobs.start(
        "rewrite",
        rubric_key,
        lambda: service.create_post(rubric_key, publisher_mode="off"),
    )
    return JobOut(**job.to_dict())


# -- fon vazifalari (job) ----------------------------------------------------
@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(
    job_id: str, _: str = Depends(require_admin), jobs: JobManager = Depends(get_jobs)
) -> JobOut:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job topilmadi")
    return JobOut(**job.to_dict())


@router.get("/jobs", response_model=list[JobOut])
async def list_jobs(
    _: str = Depends(require_admin), jobs: JobManager = Depends(get_jobs)
) -> list[JobOut]:
    return [JobOut(**j.to_dict()) for j in jobs.list()]
