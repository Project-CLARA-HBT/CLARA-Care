from datetime import UTC, datetime, timedelta
import secrets
from typing import Any

from fastapi import HTTPException, status
from jose import JWTError, jwt

from clara_api.core.config import get_settings


class TokenPayload(dict):
    @property
    def sub(self) -> str:
        return str(self.get("sub", ""))

    @property
    def role(self) -> str:
        return str(self.get("role", "normal"))


def create_access_token(subject: str, role: str) -> str:
    settings = get_settings()
    now = datetime.now(tz=UTC)
    expires = now + timedelta(minutes=settings.jwt_access_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "exp": expires,
        "iat": now,
        "iss": settings.jwt_issuer,
        "jti": secrets.token_urlsafe(12),
        "typ": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str, role: str) -> str:
    settings = get_settings()
    now = datetime.now(tz=UTC)
    expires = now + timedelta(minutes=settings.jwt_refresh_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "exp": expires,
        "iat": now,
        "iss": settings.jwt_issuer,
        "jti": secrets.token_urlsafe(12),
        "typ": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> TokenPayload:
    settings = get_settings()
    try:
        data = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if data.get("typ") != "access":
            raise JWTError("Token type không hợp lệ")
        if data.get("iss") != settings.jwt_issuer:
            raise JWTError("Token issuer không hợp lệ")
        return TokenPayload(data)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn",
        ) from exc


def decode_refresh_token(token: str) -> TokenPayload:
    settings = get_settings()
    try:
        data = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if data.get("typ") != "refresh":
            raise JWTError("Refresh token không hợp lệ")
        if data.get("iss") != settings.jwt_issuer:
            raise JWTError("Refresh token issuer không hợp lệ")
        return TokenPayload(data)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token không hợp lệ hoặc đã hết hạn",
        ) from exc
