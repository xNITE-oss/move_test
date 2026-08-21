"""Adminka kirishi — bitta admin, JWT token.

Parol `.env`dagi ADMIN_PASSWORD bilan solishtiriladi (constant-time), token
JWT_SECRET bilan imzolanadi. Ko'p admin kerak bo'lganda shu yerga users jadvali
qo'shiladi, endpointlar o'zgarmaydi.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.settings import Settings

_bearer = HTTPBearer(auto_error=False)
_ALG = "HS256"


class AuthError(HTTPException):
    def __init__(self, detail: str = "Ruxsat yo'q") -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def verify_credentials(settings: Settings, username: str, password: str) -> bool:
    """Login/parolni xavfsiz (constant-time) solishtiradi."""
    if not settings.admin_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_PASSWORD .env'da o'rnatilmagan",
        )
    user_ok = secrets.compare_digest(username or "", settings.admin_username)
    pass_ok = secrets.compare_digest(password or "", settings.admin_password)
    return user_ok and pass_ok


def create_token(settings: Settings, username: str) -> str:
    if not settings.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT_SECRET .env'da o'rnatilmagan",
        )
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(hours=settings.token_ttl_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALG)


def _decode(settings: Settings, token: str) -> dict:
    if not settings.jwt_secret:
        raise AuthError("Server sozlanmagan")
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[_ALG])
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Token muddati tugadi") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Token yaroqsiz") from exc


async def require_admin(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Himoyalangan endpointlar uchun bog'liqlik: to'g'ri token bo'lsa admin nomini qaytaradi."""
    if creds is None or not creds.credentials:
        raise AuthError("Token yuborilmadi")
    settings: Settings = request.app.state.settings
    payload = _decode(settings, creds.credentials)
    return str(payload.get("sub") or "admin")
