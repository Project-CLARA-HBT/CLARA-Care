from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.core.auth_email import dispatch_action_email, should_expose_action_token_preview
from clara_api.core.config import get_settings
from clara_api.core.passwords import hash_password, verify_password
from clara_api.core.rbac import get_current_token
from clara_api.core.security import (
    TokenPayload,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from clara_api.db.models import AuthToken, User
from clara_api.db.session import get_db
from clara_api.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
    ResetPasswordRequest,
    VerifyEmailRequest,
)

router = APIRouter()


def _infer_role_from_email(email: str) -> str:
    if email.endswith("@admin.clara") or email.startswith("admin@"):
        return "admin"
    if email.endswith("@research.clara"):
        return "researcher"
    if email.endswith("@doctor.clara"):
        return "doctor"
    return "normal"


def _hash_action_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _issue_action_token(
    db: Session,
    *,
    user_id: int,
    token_type: str,
    ttl_minutes: int,
) -> str:
    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(tz=UTC) + timedelta(minutes=ttl_minutes)
    db.add(
        AuthToken(
            user_id=user_id,
            token_type=token_type,
            token_hash=_hash_action_token(raw_token),
            expires_at=expires_at,
        )
    )
    db.commit()
    return raw_token


def _consume_action_token(db: Session, *, raw_token: str, token_type: str) -> AuthToken | None:
    now = datetime.now(tz=UTC)
    token_hash = _hash_action_token(raw_token)
    record = db.execute(
        select(AuthToken).where(
            AuthToken.token_hash == token_hash,
            AuthToken.token_type == token_type,
            AuthToken.used_at.is_(None),
            AuthToken.expires_at >= now,
        )
    ).scalar_one_or_none()
    if not record:
        return None
    record.used_at = now
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.post("/register", response_model=RegisterResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    if payload.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Không thể tự đăng ký vai trò admin"
        )

    existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email đã tồn tại")

    settings = get_settings()
    role = payload.role or _infer_role_from_email(payload.email)
    is_verified = not settings.auth_require_email_verification
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=role,
        full_name=payload.full_name.strip(),
        is_email_verified=is_verified,
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    verification_token_preview: str | None = None
    email_delivery_status: str | None = None
    if not user.is_email_verified:
        verification_token = _issue_action_token(
            db,
            user_id=user.id,
            token_type="verify_email",
            ttl_minutes=settings.auth_action_token_ttl_minutes,
        )
        email_delivery_status = dispatch_action_email(
            settings,
            action="verify_email",
            recipient=user.email,
            token=verification_token,
        )
        if should_expose_action_token_preview(settings):
            verification_token_preview = verification_token

    return RegisterResponse(
        user_id=user.id,
        email=user.email,
        role=user.role,  # type: ignore[arg-type]
        is_email_verified=user.is_email_verified,
        email_delivery_status=email_delivery_status,
        verification_token_preview=verification_token_preview,
    )


@router.post("/verify-email")
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    record = _consume_action_token(db, raw_token=payload.token, token_type="verify_email")
    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token xác thực không hợp lệ hoặc đã hết hạn",
        )

    user = db.get(User, record.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Người dùng không tồn tại"
        )
    user.is_email_verified = True
    db.add(user)
    db.commit()
    return {"verified": True, "email": user.email}


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    if not payload.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thiếu mật khẩu")

    settings = get_settings()
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()

    auto_provision_enabled = (
        settings.auth_auto_provision_users and settings.environment.lower() != "production"
    )
    if user is None and auto_provision_enabled:
        inferred_role = _infer_role_from_email(payload.email)
        user = User(
            email=payload.email,
            hashed_password=hash_password(payload.password),
            role=inferred_role,
            full_name="",
            is_email_verified=True,
            status="active",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai email hoặc mật khẩu",
        )

    if settings.auth_require_email_verification and not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Email chưa được xác thực"
        )

    user.last_login_at = datetime.now(tz=UTC)
    db.add(user)
    db.commit()

    token = create_access_token(subject=user.email, role=user.role)
    refresh_token = create_refresh_token(subject=user.email, role=user.role)
    return LoginResponse(access_token=token, refresh_token=refresh_token, role=user.role)  # type: ignore[arg-type]


@router.post("/refresh", response_model=LoginResponse)
def refresh_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)) -> LoginResponse:
    token_payload = decode_refresh_token(payload.refresh_token)
    user = db.execute(select(User).where(User.email == token_payload.sub)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Người dùng không tồn tại"
        )

    role = user.role if user.role in {"normal", "researcher", "doctor", "admin"} else "normal"
    access_token = create_access_token(subject=user.email, role=role)
    refresh_token = create_refresh_token(subject=user.email, role=role)
    return LoginResponse(access_token=access_token, refresh_token=refresh_token, role=role)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> ForgotPasswordResponse:
    settings = get_settings()
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if not user:
        return ForgotPasswordResponse(
            accepted=True, email_delivery_status="noop", reset_token_preview=None
        )

    reset_token = _issue_action_token(
        db,
        user_id=user.id,
        token_type="reset_password",
        ttl_minutes=settings.auth_action_token_ttl_minutes,
    )
    email_delivery_status = dispatch_action_email(
        settings,
        action="reset_password",
        recipient=user.email,
        token=reset_token,
    )
    reset_token_preview = reset_token if should_expose_action_token_preview(settings) else None
    return ForgotPasswordResponse(
        accepted=True,
        email_delivery_status=email_delivery_status,
        reset_token_preview=reset_token_preview,
    )


@router.post("/resend-verification", response_model=ResendVerificationResponse)
def resend_verification(
    payload: ResendVerificationRequest,
    db: Session = Depends(get_db),
) -> ResendVerificationResponse:
    settings = get_settings()
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if not user or user.is_email_verified:
        return ResendVerificationResponse(
            accepted=True,
            email_delivery_status="noop",
            verification_token_preview=None,
        )

    verification_token = _issue_action_token(
        db,
        user_id=user.id,
        token_type="verify_email",
        ttl_minutes=settings.auth_action_token_ttl_minutes,
    )
    email_delivery_status = dispatch_action_email(
        settings,
        action="verify_email",
        recipient=user.email,
        token=verification_token,
    )
    verification_token_preview = (
        verification_token if should_expose_action_token_preview(settings) else None
    )
    return ResendVerificationResponse(
        accepted=True,
        email_delivery_status=email_delivery_status,
        verification_token_preview=verification_token_preview,
    )


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> dict[str, bool]:
    token = _consume_action_token(db, raw_token=payload.token, token_type="reset_password")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Token đặt lại mật khẩu không hợp lệ"
        )

    user = db.get(User, token.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Người dùng không tồn tại"
        )

    user.hashed_password = hash_password(payload.new_password)
    db.add(user)
    db.commit()
    return {"reset": True}


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    token_payload: TokenPayload = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    user = db.execute(select(User).where(User.email == token_payload.sub)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Người dùng không tồn tại"
        )
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Mật khẩu hiện tại không đúng"
        )

    user.hashed_password = hash_password(payload.new_password)
    db.add(user)
    db.commit()
    return {"changed": True}


@router.post("/logout")
def logout(_token_payload: TokenPayload = Depends(get_current_token)) -> dict[str, bool]:
    return {"logged_out": True}


@router.get("/me")
def me(
    token_payload: TokenPayload = Depends(get_current_token), db: Session = Depends(get_db)
) -> dict[str, object]:
    user = db.execute(select(User).where(User.email == token_payload.sub)).scalar_one_or_none()
    if not user:
        return {"subject": token_payload.sub, "role": token_payload.role}
    return {
        "subject": user.email,
        "role": user.role,
        "full_name": user.full_name,
        "is_email_verified": user.is_email_verified,
        "status": user.status,
    }
