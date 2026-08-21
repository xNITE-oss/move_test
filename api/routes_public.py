"""Ochiq sayt endpointlari — tokensiz, faqat chiqarilgan postlar.

Sayt shu API'dan o'qiydi. Post yozish/tasdiqlash bu yerda yo'q — faqat ko'rsatish.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from api import serialize
from api.deps import get_service
from api.schemas import PublicPostDetail, PublicPostSummary
from core.service import ContentService

router = APIRouter(prefix="/api/site", tags=["site"])


@router.get("/posts", response_model=list[PublicPostSummary])
async def site_posts(
    service: ContentService = Depends(get_service),
    rubric: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[PublicPostSummary]:
    rows = service.list_published(rubric_key=rubric, limit=limit, offset=offset)
    out = [serialize.public_summary(r) for r in rows]
    return [PublicPostSummary(**s) for s in out if s]


@router.get("/posts/{slug}", response_model=PublicPostDetail)
async def site_post(
    slug: str, service: ContentService = Depends(get_service)
) -> PublicPostDetail:
    # slug sarlavhadan hosil bo'ladi (bazada saqlanmaydi), shuning uchun
    # chiqarilgan postlar ichidan mos slug'ni topamiz. Bir xil slug bo'lsa,
    # eng yangisi olinadi (ro'yxat yangi birinchi tartibda keladi).
    for row in service.list_published(limit=200):
        detail = serialize.public_detail(row)
        if detail and detail["slug"] == slug:
            return PublicPostDetail(**detail)
    raise HTTPException(status_code=404, detail="Sahifa topilmadi")
