import secrets
from datetime import UTC, datetime, timedelta
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


def _signing_keys(settings) -> list[str]:
    """Ordered candidate keys for *verification*.

    The current ``jwt_secret_key`` is always tried first (and is the only key
    used for *signing*). During a rotation key-overlap window an operator sets
    ``JWT_SECRET_KEY_PREVIOUS`` to the prior signing key; it is appended here so
    tokens minted before the rotation still verify until their natural expiry,
    avoiding a forced mass logout (Requirement 1.7). When the previous key is
    unset (the default) only the current key is used, so verification behavior is
    identical to the pre-hardening baseline.
    """
    keys = [settings.jwt_secret_key]
    previous = settings.jwt_secret_key_previous.strip()
    if previous and previous != settings.jwt_secret_key:
        keys.append(previous)
    return keys


def _decode_with_keys(token: str, settings) -> dict[str, Any]:
    """Decode ``token`` against the current key, then the previous key if set.

    Each candidate key is tried in turn; the first that yields a valid signature
    (and passes JWT's own expiry/claim checks) wins. If every candidate fails,
    the final ``JWTError`` is propagated so the caller maps it to a 401. With no
    previous key configured this collapses to a single ``jwt.decode`` call,
    preserving current behavior exactly.
    """
    last_error: JWTError | None = None
    for key in _signing_keys(settings):
        try:
            return jwt.decode(token, key, algorithms=[settings.jwt_algorithm])
        except JWTError as exc:
            last_error = exc
    raise last_error if last_error is not None else JWTError("Token không hợp lệ")


def decode_access_token(token: str) -> TokenPayload:
    settings = get_settings()
    try:
        data = _decode_with_keys(token, settings)
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
        data = _decode_with_keys(token, settings)
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
