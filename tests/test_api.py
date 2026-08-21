"""Web API testlari — tarmoqqa chiqmaydi (fake providerlar, dry_run)."""

from __future__ import annotations

import dataclasses
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from config.settings import Settings

RUBRIC = "hiking"          # config/rubrics/hiking.yaml — haqiqiy rubrika


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    settings = dataclasses.replace(
        Settings.load(),
        llm_provider="fake",
        search_provider="fake",
        image_provider="fake",
        tts_provider="fake",
        telegram_bot_token="test-token",
        telegram_channel_id="@testkanal",
        telegram_review_chat_id="6121632867",
        dry_run=True,
        data_dir=tmp_path / "data",
        admin_username="admin",
        admin_password="secret",
        jwt_secret="test-jwt-secret-at-least-32-bytes-long-000",
        cors_origins=(),
    )
    return TestClient(create_app(settings))


def auth(client: TestClient) -> dict:
    r = client.post("/api/auth/login", json={"username": "admin", "password": "secret"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def wait_job(client: TestClient, headers: dict, job_id: str, timeout: float = 15.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/jobs/{job_id}", headers=headers)
        assert r.status_code == 200, r.text
        job = r.json()
        if job["status"] != "running":
            return job
        time.sleep(0.2)
    raise AssertionError("job tugamadi (timeout)")


# -- auth --------------------------------------------------------------------
def test_health_is_public(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_login_required(client: TestClient) -> None:
    assert client.get("/api/rubrics").status_code == 401
    assert client.get("/api/posts").status_code == 401


def test_wrong_password_rejected(client: TestClient) -> None:
    r = client.post("/api/auth/login", json={"username": "admin", "password": "xato"})
    assert r.status_code == 401


def test_login_and_me(client: TestClient) -> None:
    headers = auth(client)
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["username"] == "admin"


def test_rubrics_listed(client: TestClient) -> None:
    headers = auth(client)
    r = client.get("/api/rubrics", headers=headers)
    assert r.status_code == 200
    keys = {x["key"] for x in r.json()}
    assert RUBRIC in keys


# -- to'liq oqim: tayyorlash → chiqarish → saytda ko'rinishi ------------------
def test_create_publish_and_site_flow(client: TestClient) -> None:
    headers = auth(client)

    # 1) Post tayyorlash (fon vazifasi)
    r = client.post("/api/posts", json={"rubric": RUBRIC}, headers=headers)
    assert r.status_code == 202, r.text
    job = wait_job(client, headers, r.json()["id"])
    assert job["status"] == "done", job
    run_id = job["run_id"]
    assert run_id

    # 2) Tafsilot — tuzilgan kontent va HTML bo'lishi kerak
    r = client.get(f"/api/posts/{run_id}", headers=headers)
    assert r.status_code == 200, r.text
    detail = r.json()
    assert detail["content"] and detail["content"]["title"]
    assert detail["html"]

    # 3) Saytda hali ko'rinmasligi kerak (chiqarilmagan)
    assert client.get("/api/site/posts").json() == []

    # 4) Chiqarish → TG (dry_run) + sayt
    r = client.post(f"/api/posts/{run_id}/publish", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "published"

    # 5) Endi ochiq saytda ko'rinadi (tokensiz)
    site = client.get("/api/site/posts").json()
    assert len(site) == 1
    slug = site[0]["slug"]
    assert site[0]["title"]

    r = client.get(f"/api/site/posts/{slug}")
    assert r.status_code == 200, r.text
    assert r.json()["html"]

    # 6) Ikkinchi marta chiqarib bo'lmaydi
    assert client.post(f"/api/posts/{run_id}/publish", headers=headers).status_code == 409


def test_reject_flow(client: TestClient) -> None:
    headers = auth(client)
    r = client.post("/api/posts", json={"rubric": RUBRIC}, headers=headers)
    job = wait_job(client, headers, r.json()["id"])
    run_id = job["run_id"]

    r = client.post(f"/api/posts/{run_id}/reject", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"

    # bekor qilingan post saytda chiqmaydi
    assert client.get("/api/site/posts").json() == []


def test_unknown_rubric_rejected(client: TestClient) -> None:
    headers = auth(client)
    r = client.post("/api/posts", json={"rubric": "yoq-rubrika"}, headers=headers)
    assert r.status_code == 404
