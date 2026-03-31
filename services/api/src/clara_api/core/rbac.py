from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from clara_api.core.config import get_settings
from clara_api.core.security import TokenPayload, decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


class AuthContextMiddleware(BaseHTTPMiddleware):
    """Decode JWT once per request and attach to request.state.

    Routes can then enforce RBAC through dependencies without repeating decode logic.
    """

    async def dispatch(self, request: Request, call_next):
        request.state.token_payload = None
        token = _extract_access_token(request)
        if token:
            try:
                request.state.token_payload = decode_access_token(token)
            except HTTPException as exc:
                return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        return await call_next(request)


def _extract_access_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ").strip()
        if token:
            return token
    cookie_name = get_settings().auth_cookie_access_name
    token = request.cookies.get(cookie_name, "").strip()
    return token


async def get_current_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> TokenPayload:
    state_token = getattr(request.state, "token_payload", None)
    if state_token is not None:
        return state_token
    if credentials is None:
        token = _extract_access_token(request)
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Thiếu token")
        return decode_access_token(token)
    return decode_access_token(credentials.credentials)


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
