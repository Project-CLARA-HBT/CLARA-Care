from fastapi import APIRouter, Depends, HTTPException, status

from clara_api.core.rbac import get_current_token
from clara_api.core.security import (
    TokenPayload,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from clara_api.schemas import LoginRequest, LoginResponse, RefreshTokenRequest

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    """P0 placeholder auth logic.

    Any email/password pair is accepted for scaffold. Role is inferred by email suffix.
    """
    role = "normal"
    if payload.email.endswith("@research.clara"):
        role = "researcher"
    elif payload.email.endswith("@doctor.clara"):
        role = "doctor"

    if not payload.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thiếu mật khẩu")

    token = create_access_token(subject=payload.email, role=role)
    refresh_token = create_refresh_token(subject=payload.email, role=role)
    return LoginResponse(access_token=token, refresh_token=refresh_token, role=role)


@router.post("/refresh", response_model=LoginResponse)
def refresh_token(payload: RefreshTokenRequest) -> LoginResponse:
    token_payload = decode_refresh_token(payload.refresh_token)
    role = token_payload.role if token_payload.role in {"normal", "researcher", "doctor"} else "normal"
    access_token = create_access_token(subject=token_payload.sub, role=role)
    refresh_token = create_refresh_token(subject=token_payload.sub, role=role)
    return LoginResponse(access_token=access_token, refresh_token=refresh_token, role=role)


@router.get("/me")
def me(token_payload: TokenPayload = Depends(get_current_token)) -> dict[str, str]:
    return {"subject": token_payload.sub, "role": token_payload.role}
