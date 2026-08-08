from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware

from clara_api.core.config import get_settings
from clara_api.core.security import TokenPayload, decode_access_token
from clara_api.core.session_security import session_security

bearer_scheme = HTTPBearer(auto_error=False)


def _has_bearer_scheme(request: Request) -> bool:
    """Return whether the caller explicitly selected Bearer authentication.

    RFC 7235 authentication schemes are case-insensitive.  Keeping this parser
    shared with the CSRF boundary prevents a lowercase/malformed ``bearer``
    header from bypassing CSRF while authentication silently falls back to a
    cookie session.
    """

    header = request.headers.get("Authorization", "").strip()
    if not header:
        return False
    scheme, _, _ = header.partition(" ")
    return scheme.lower() == "bearer"


def extract_bearer_token(request: Request) -> str | None:
    """Extract an explicitly supplied Bearer credential without cookie fallback."""

    if not _has_bearer_scheme(request):
        return None
    _, _, raw_token = request.headers.get("Authorization", "").partition(" ")
    token = raw_token.strip()
    return token or None


def _reject_if_revoked(payload: TokenPayload) -> TokenPayload:
    """Reject a denylisted (revoked-at-logout) access token.

    Part of clara-platform-hardening Requirement 2.4 / Property 6. Consults the
    ``jti`` denylist via the shared ``session_security`` singleton. The consult
    is gated inside ``SessionSecurity.is_revoked`` by
    ``HARDENING_TOKEN_DENYLIST_ENABLED``: when the flag is off it short-circuits
    to ``False`` without touching the backend, so token resolution behaves
    exactly as the pre-hardening baseline (Requirements 2.7, 11.1, 11.2).
    """
    jti = str(payload.get("jti", ""))
    if jti and session_security.is_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token đã bị thu hồi",
        )
    return payload


class AuthContextMiddleware(BaseHTTPMiddleware):
    """Decode JWT once per request and attach to request.state.

    Routes can then enforce RBAC through dependencies without repeating decode logic.
    """

    async def dispatch(self, request: Request, call_next):
        request.state.token_payload = None
        request.state.token_error = None
        token = _extract_access_token(request)
        if token:
            try:
                request.state.token_payload = decode_access_token(token)
            except HTTPException as exc:
                # Preserve auth error for protected routes, but allow public endpoints
                # (login/refresh/logout) to proceed and self-handle expired/invalid tokens.
                request.state.token_error = exc
        return await call_next(request)


def _extract_access_token(request: Request) -> str:
    # An explicit Bearer attempt owns authentication for this request.  Never
    # downgrade a malformed/invalid bearer credential into cookie auth: callers
    # must receive an auth failure rather than unintentionally switching
    # transports (and CSRF policy remains aligned with this decision).
    if _has_bearer_scheme(request):
        return extract_bearer_token(request) or ""
    cookie_name = get_settings().auth_cookie_access_name
    token = request.cookies.get(cookie_name, "").strip()
    return token


def has_valid_explicit_bearer_token(request: Request) -> bool:
    """Whether this request will genuinely authenticate by Bearer token.

    CSRF exemption is safe only for a valid, non-revoked explicit credential.
    Invalid, expired, empty, or revoked headers deliberately return ``False``;
    a simultaneous cookie session must therefore satisfy the normal CSRF check.
    """

    token = extract_bearer_token(request)
    if not token:
        return False
    try:
        _reject_if_revoked(decode_access_token(token))
    except HTTPException:
        return False
    return True


async def get_current_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> TokenPayload:
    state_token = getattr(request.state, "token_payload", None)
    if state_token is not None:
        return _reject_if_revoked(state_token)
    state_error = getattr(request.state, "token_error", None)
    if isinstance(state_error, HTTPException):
        raise state_error
    if credentials is None:
        token = _extract_access_token(request)
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Thiếu token")
        return _reject_if_revoked(decode_access_token(token))
    return _reject_if_revoked(decode_access_token(credentials.credentials))


async def get_optional_current_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> TokenPayload | None:
    try:
        return await get_current_token(request=request, credentials=credentials)
    except HTTPException:
        return None


def require_roles(*roles: str) -> Callable[[TokenPayload], TokenPayload]:
    async def _checker(token: TokenPayload = Depends(get_current_token)) -> TokenPayload:
        if token.role == "admin":
            return token
        if token.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không đủ quyền truy cập",
            )
        return token

    return _checker
