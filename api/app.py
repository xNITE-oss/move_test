"""FastAPI ilovasi — ContentService ustidagi HTTP qobiq.

Ishga tushirish (mahalliy):
    uvicorn api.app:app --reload
Serverda:
    uvicorn api.app:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.jobs import JobManager
from api.routes_admin import router as admin_router
from api.routes_public import router as public_router
from config.settings import Settings, get_settings
from core.logging_setup import setup_logging
from core.service import ContentService
from core.storage import Storage

log = logging.getLogger("api")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(
        title="Move Space API",
        version="1.0",
        summary="Kontent-bot uchun adminka va sayt API'si",
    )

    storage = Storage(settings)
    app.state.settings = settings
    app.state.service = ContentService(settings, storage)
    app.state.jobs = JobManager()

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(admin_router)
    app.include_router(public_router)

    @app.get("/api/health", tags=["service"])
    async def health() -> dict:
        return {"status": "ok"}

    log.info(
        "Move Space API tayyor | rubrikalar=%d | CORS=%s",
        len(app.state.service.rubric_keys()),
        ",".join(settings.cors_origins) or "(o'chiq)",
    )
    return app


# uvicorn api.app:app uchun
app = create_app()
