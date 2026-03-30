from __future__ import annotations

import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

from clara_api.core.auth_email import dispatch_action_email, should_expose_action_token_preview
from clara_api.core.config import get_settings
from clara_api.core.consent import (
    MEDICAL_CONSENT_TYPE,
    get_latest_user_consent,
    required_medical_disclaimer_version,
)
from clara_api.core.passwords import hash_password, verify_password
from clara_api.core.login_guard import login_guard
from clara_api.core.rbac import get_current_token
from clara_api.core.security import (
    TokenPayload,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from clara_api.db.models import AuthToken, User, UserConsent
from clara_api.db.session import get_db
from clara_api.schemas import (
    ChangePasswordRequest,
    ConsentAcceptRequest,
    ConsentAcceptResponse,
    ConsentStatusResponse,
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
_auth_action_attempts: dict[str, deque[float]] = defaultdict(deque)
_auth_action_attempts_lock = Lock()


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


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _ensure_password_policy(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mật khẩu phải có ít nhất 8 ký tự",
        )
    if password != password.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mật khẩu không được chứa khoảng trắng ở đầu/cuối",
        )
    has_alpha = any(char.isalpha() for char in password)
    has_digit = any(char.isdigit() for char in password)
    if not (has_alpha and has_digit):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mật khẩu phải chứa tối thiểu 1 chữ cái và 1 chữ số",
        )


def _issue_action_token(
    db: Session,
    *,
    user_id: int,
    token_type: str,
    ttl_minutes: int,
) -> str:
    now = datetime.now(tz=UTC)
    existing_tokens = (
        db.execute(
            select(AuthToken).where(
                AuthToken.user_id == user_id,
                AuthToken.token_type == token_type,
                AuthToken.used_at.is_(None),
                AuthToken.expires_at >= now,
            )
        )
        .scalars()
        .all()
    )
    for token in existing_tokens:
        token.used_at = now
        db.add(token)

    raw_token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(minutes=ttl_minutes)
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


def _issue_refresh_session_token(db: Session, *, user: User) -> str:
    settings = get_settings()
    raw_token = create_refresh_token(subject=user.email, role=user.role)
    expires_at = datetime.now(tz=UTC) + timedelta(minutes=settings.jwt_refresh_minutes)
    db.add(
        AuthToken(
            user_id=user.id,
            token_type="refresh_jwt",
            token_hash=_hash_action_token(raw_token),
            expires_at=expires_at,
        )
    )
    db.commit()
    return raw_token


def _resolve_auto_provision_role(email: str) -> str:
    inferred = _infer_role_from_email(email)
    if inferred == "admin":
        return "normal"
    return inferred


def _consume_refresh_session_token(db: Session, *, raw_token: str) -> AuthToken | None:
    return _consume_action_token(db, raw_token=raw_token, token_type="refresh_jwt")


def _revoke_refresh_sessions(db: Session, *, user_id: int) -> int:
    now = datetime.now(tz=UTC)
    rows = (
        db.execute(
            select(AuthToken).where(
                AuthToken.user_id == user_id,
                AuthToken.token_type == "refresh_jwt",
                AuthToken.used_at.is_(None),
                AuthToken.expires_at >= now,
            )
        )
        .scalars()
        .all()
    )
    for row in rows:
        row.used_at = now
        db.add(row)
    db.commit()
    return len(rows)


def _cleanup_auth_tokens(db: Session) -> None:
    now = datetime.now(tz=UTC)
    retention_cutoff = now - timedelta(days=30)
    db.execute(
        delete(AuthToken).where(
            or_(
                AuthToken.expires_at < now,
                and_(AuthToken.used_at.is_not(None), AuthToken.used_at < retention_cutoff),
            )
        )
    )
    db.commit()


def _extract_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        return forwarded.split(",", maxsplit=1)[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _ensure_action_rate_limit(action: str, key: str) -> None:
    settings = get_settings()
    now = time.time()
    composite_key = f"{action}:{key}"
    cutoff = now - settings.auth_action_rate_limit_window_seconds
    with _auth_action_attempts_lock:
        attempts = _auth_action_attempts[composite_key]
        while attempts and attempts[0] < cutoff:
            attempts.popleft()
        if len(attempts) >= settings.auth_action_rate_limit_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Quá số lần thử cho thao tác xác thực. Vui lòng thử lại sau.",
            )
        attempts.append(now)


@router.post("/register", response_model=RegisterResponse)
def register(
    payload: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> RegisterResponse:
    normalized_email = _normalize_email(payload.email)
    _ensure_action_rate_limit("register", f"{normalized_email}|{_extract_client_ip(request)}")
    _ensure_password_policy(payload.password)
    if payload.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Không thể tự đăng ký vai trò admin"
        )

    settings = get_settings()
    if settings.environment.lower() == "production" and payload.role != "normal":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Đăng ký công khai chỉ hỗ trợ vai trò normal",
        )

    existing = db.execute(select(User).where(User.email == normalized_email)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email đã tồn tại")

    role = payload.role or _infer_role_from_email(normalized_email)
    is_verified = not settings.auth_require_email_verification
    user = User(
        email=normalized_email,
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
def verify_email(
    payload: VerifyEmailRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _ensure_action_rate_limit("verify_email", _extract_client_ip(request))
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
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> LoginResponse:
    _cleanup_auth_tokens(db)
    if not payload.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thiếu mật khẩu")

    settings = get_settings()
    normalized_email = _normalize_email(payload.email)
    login_key = f"{normalized_email}|{_extract_client_ip(request)}"
    blocked_seconds = login_guard.is_blocked(login_key)
    if blocked_seconds > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Tạm khóa đăng nhập do quá nhiều lần thử sai. Thử lại sau {blocked_seconds}s",
        )

    user = db.execute(select(User).where(User.email == normalized_email)).scalar_one_or_none()

    auto_provision_enabled = (
        settings.auth_auto_provision_users and settings.environment.lower() != "production"
    )
    if user is None and auto_provision_enabled:
        inferred_role = _resolve_auto_provision_role(normalized_email)
        user = User(
            email=normalized_email,
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
        login_guard.register_failure(login_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai email hoặc mật khẩu",
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đang bị khóa hoặc chưa sẵn sàng",
        )

    if settings.auth_require_email_verification and not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Email chưa được xác thực"
        )

    login_guard.register_success(login_key)
    user.last_login_at = datetime.now(tz=UTC)
    db.add(user)
    db.commit()

    token = create_access_token(subject=user.email, role=user.role)
    refresh_token = _issue_refresh_session_token(db, user=user)
    return LoginResponse(
        access_token=token,
        refresh_token=refresh_token,
        role=user.role,  # type: ignore[arg-type]
    )


@router.post("/refresh", response_model=LoginResponse)
def refresh_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)) -> LoginResponse:
    _cleanup_auth_tokens(db)
    settings = get_settings()
    token_payload = decode_refresh_token(payload.refresh_token)
    session_token = _consume_refresh_session_token(db, raw_token=payload.refresh_token)
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token không hợp lệ hoặc đã bị thu hồi",
        )

    user = db.get(User, session_token.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Người dùng không tồn tại"
        )
    if user.email != token_payload.sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token không khớp với người dùng hiện tại",
        )
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đang bị khóa hoặc chưa sẵn sàng",
        )
    if settings.auth_require_email_verification and not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email chưa được xác thực",
        )

    role = user.role if user.role in {"normal", "researcher", "doctor", "admin"} else "normal"
    access_token = create_access_token(subject=user.email, role=role)
    refresh_token = _issue_refresh_session_token(db, user=user)
    return LoginResponse(access_token=access_token, refresh_token=refresh_token, role=role)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ForgotPasswordResponse:
    settings = get_settings()
    normalized_email = _normalize_email(payload.email)
    _ensure_action_rate_limit(
        "forgot_password", f"{normalized_email}|{_extract_client_ip(request)}"
    )
    user = db.execute(select(User).where(User.email == normalized_email)).scalar_one_or_none()
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
    request: Request,
    db: Session = Depends(get_db),
) -> ResendVerificationResponse:
    settings = get_settings()
    normalized_email = _normalize_email(payload.email)
    _ensure_action_rate_limit(
        "resend_verification", f"{normalized_email}|{_extract_client_ip(request)}"
    )
    user = db.execute(select(User).where(User.email == normalized_email)).scalar_one_or_none()
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
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    _ensure_action_rate_limit("reset_password", _extract_client_ip(request))
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
    _ensure_password_policy(payload.new_password)
    if verify_password(payload.new_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu mới phải khác mật khẩu hiện tại",
        )

    user.hashed_password = hash_password(payload.new_password)
    db.add(user)
    db.commit()
    _revoke_refresh_sessions(db, user_id=user.id)
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
    _ensure_password_policy(payload.new_password)
    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu mới phải khác mật khẩu hiện tại",
        )

    user.hashed_password = hash_password(payload.new_password)
    db.add(user)
    db.commit()
    _revoke_refresh_sessions(db, user_id=user.id)
    return {"changed": True}


@router.post("/logout")
def logout(
    token_payload: TokenPayload = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user = db.execute(select(User).where(User.email == token_payload.sub)).scalar_one_or_none()
    revoked_count = 0
    if user:
        revoked_count = _revoke_refresh_sessions(db, user_id=user.id)
    return {"logged_out": True, "revoked_refresh_sessions": revoked_count}


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


@router.get("/consent-status", response_model=ConsentStatusResponse)
def get_consent_status(
    token_payload: TokenPayload = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> ConsentStatusResponse:
    user = db.execute(select(User).where(User.email == token_payload.sub)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Người dùng không tồn tại"
        )

    required_version = required_medical_disclaimer_version()
    latest = get_latest_user_consent(db, user_id=user.id, consent_type=MEDICAL_CONSENT_TYPE)
    accepted = bool(latest and latest.consent_version == required_version)
    return ConsentStatusResponse(
        consent_type=MEDICAL_CONSENT_TYPE,
        required_version=required_version,
        accepted=accepted,
        user_id=user.id,
        consent_version=latest.consent_version if latest else None,
        accepted_version=latest.consent_version if latest else None,
        accepted_at=latest.accepted_at if latest else None,
    )


@router.post("/consent", response_model=ConsentAcceptResponse)
def accept_consent(
    payload: ConsentAcceptRequest,
    token_payload: TokenPayload = Depends(get_current_token),
    db: Session = Depends(get_db),
) -> ConsentAcceptResponse:
    if not payload.accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bạn cần xác nhận đồng ý để tiếp tục",
        )

    required_version = required_medical_disclaimer_version()
    if payload.consent_version != required_version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Phiên bản consent không hợp lệ. Yêu cầu: {required_version}",
        )

    user = db.execute(select(User).where(User.email == token_payload.sub)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Người dùng không tồn tại"
        )

    latest = get_latest_user_consent(db, user_id=user.id, consent_type=MEDICAL_CONSENT_TYPE)
    if latest and latest.consent_version == required_version:
        return ConsentAcceptResponse(
            consent_type=MEDICAL_CONSENT_TYPE,
            user_id=user.id,
            consent_version=latest.consent_version,
            accepted_at=latest.accepted_at,
        )

    consent = UserConsent(
        user_id=user.id,
        consent_type=MEDICAL_CONSENT_TYPE,
        consent_version=required_version,
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)
    return ConsentAcceptResponse(
        consent_type=consent.consent_type,
        user_id=consent.user_id,
        consent_version=consent.consent_version,
        accepted_at=consent.accepted_at,
    )
