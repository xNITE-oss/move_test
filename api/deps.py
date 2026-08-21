"""FastAPI bog'liqliklari — app.state'dagi obyektlarga qulay kirish."""

from __future__ import annotations

from fastapi import Request

from api.jobs import JobManager
from config.settings import Settings
from core.service import ContentService


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_service(request: Request) -> ContentService:
    return request.app.state.service


def get_jobs(request: Request) -> JobManager:
    return request.app.state.jobs
