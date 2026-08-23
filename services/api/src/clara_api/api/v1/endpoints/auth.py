from __future__ import annotations

import hashlib
import logging
import secrets
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Literal, cast

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from clara_api.core.auth_email import dispatch_action_email, should_expose_action_token_preview
from clara_api.core.config import get_settings
from clara_api.core.consent import (
    MEDICAL_CONSENT_TYPE,
    get_latest_user_consent,
    required_medical_disclaimer_version,
)
from clara_api.core.login_guard import login_guard
from clara_api.core.passwords import hash_password, verify_password
from clara_api.core.rbac import get_current_token, get_optional_current_token
from clara_api.core.security import (
    TokenPayload,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from clara_api.core.session_security import session_security
from clara_api.db.models import AuthToken, PhrProfile, User, UserConsent
from clara_api.db.session import get_db
from clara_api.glhs.lock_hierarchy import acquire_consent_lock_anchor
from clara_api.schemas import (
    ChangePasswordRequest,
    ConsentAcceptRequest,
    ConsentAcceptResponse,
    ConsentStatusResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginOtpVerifyRequest,
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
    ResetPasswordRequest,
    Role,
    VerifyEmailRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()
_auth_action_attempts: dict[str, deque[float]] = defaultdict(deque)
_auth_action_attempts_lock = Lock()


def _infer_role_from_email(email: str) -> Role:
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
    raw_token: str | None = None,
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

    token_value = (raw_token or "").strip() or secrets.token_urlsafe(32)
    expires_at = now + timedelta(minutes=ttl_minutes)
    db.add(
        AuthToken(
            user_id=user_id,
            token_type=token_type,
            token_hash=_hash_action_token(token_value),
            expires_at=expires_at,
        )
    )
    db.commit()
    return token_value


def _consume_action_token(
    db: Session,
    *,
    raw_token: str,
    token_type: str,
    user_id: int | None = None,
) -> AuthToken | None:
    now = datetime.now(tz=UTC)
    token_hash = _hash_action_token(raw_token)
    conditions = [
        AuthToken.token_hash == token_hash,
        AuthToken.token_type == token_type,
        AuthToken.used_at.is_(None),
        AuthToken.expires_at >= now,
    ]
    if user_id is not None:
        conditions.append(AuthToken.user_id == user_id)
    record = db.execute(select(AuthToken).where(*conditions)).scalar_one_or_none()
    if not record:
        return None
    record.used_at = now
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _issue_refresh_session_token(db: Session, *, user: User, raw_token: str | None = None) -> str:
    settings = get_settings()
    token_value = raw_token or create_refresh_token(subject=user.email, role=user.role)
    expires_at = datetime.now(tz=UTC) + timedelta(minutes=settings.jwt_refresh_minutes)
    db.add(
        AuthToken(
            user_id=user.id,
            token_type="refresh_jwt",
            token_hash=_hash_action_token(token_value),
            expires_at=expires_at,
        )
    )
    db.commit()
    return token_value


def _revoke_token_jti(token_payload: TokenPayload | dict[str, object]) -> None:
    """Denylist a token's ``jti`` for its remaining lifetime (logout revocation).

    No-op when the denylist flag is off (``SessionSecurity.revoke`` is itself
    gated), when the payload lacks a ``jti``/``exp``, or when the token has
    already expired. The TTL is derived from the token's own ``exp`` claim so
    the denylist entry disappears at the token's natural expiry (Requirement
    2.4). No PII is read or stored — only the opaque ``jti``.
    """
    jti = str(token_payload.get("jti", "")).strip()
    exp = token_payload.get("exp")
    if not jti or exp is None:
        return
    if not isinstance(exp, str | int | float):
        return
    try:
        remaining_seconds = int(exp) - int(time.time())
    except (TypeError, ValueError):
        return
    if remaining_seconds <= 0:
        return
    session_security.revoke(jti, remaining_seconds)


def _resolve_auto_provision_role(email: str) -> Role:
    inferred = _infer_role_from_email(email)
    if inferred == "admin":
        return "normal"
    return inferred


def _parse_login_otp_roles(raw_value: str) -> set[str]:
    parsed = {item.strip().lower() for item in raw_value.split(",") if item.strip()}
    if not parsed:
        return {"doctor", "admin"}
    return parsed


def _role_requires_login_otp(*, role: str, settings) -> bool:
    if not settings.auth_login_otp_enabled:
        return False
    allowed_roles = _parse_login_otp_roles(settings.auth_login_otp_roles)
    return role.strip().lower() in allowed_roles


def _issue_login_otp_code(db: Session, *, user_id: int, ttl_minutes: int) -> str:
    otp_code = f"{secrets.randbelow(1_000_000):06d}"
    return _issue_action_token(
        db,
        user_id=user_id,
        token_type="login_otp",
        ttl_minutes=ttl_minutes,
        raw_token=otp_code,
    )


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


def _resolve_cookie_samesite(raw_value: str) -> Literal["lax", "strict", "none"]:
    normalized = raw_value.strip().lower()
    if normalized in {"lax", "strict", "none"}:
        return cast(Literal["lax", "strict", "none"], normalized)
    return "lax"


def _set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
) -> None:
    settings = get_settings()
    secure = bool(settings.auth_cookie_secure)
    same_site = _resolve_cookie_samesite(settings.auth_cookie_samesite)
    domain = settings.auth_cookie_domain.strip() or None
    path = settings.auth_cookie_path.strip() or "/"
    response.set_cookie(
        key=settings.auth_cookie_access_name,
        value=access_token,
        httponly=True,
        secure=secure,
        samesite=same_site,
        domain=domain,
        path=path,
        max_age=int(settings.jwt_access_minutes * 60),
    )
    response.set_cookie(
        key=settings.auth_cookie_refresh_name,
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite=same_site,
        domain=domain,
        path=path,
        max_age=int(settings.jwt_refresh_minutes * 60),
    )
    if settings.auth_csrf_enabled:
        csrf_token = secrets.token_urlsafe(32)
        response.set_cookie(
            key=settings.auth_csrf_cookie_name,
            value=csrf_token,
            httponly=False,
            secure=secure,
            samesite=same_site,
            domain=domain,
            path=path,
            max_age=int(settings.jwt_refresh_minutes * 60),
        )


def _clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    domain = settings.auth_cookie_domain.strip() or None
    path = settings.auth_cookie_path.strip() or "/"
    response.delete_cookie(
        key=settings.auth_cookie_access_name,
        domain=domain,
        path=path,
    )
    response.delete_cookie(
        key=settings.auth_cookie_refresh_name,
        domain=domain,
        path=path,
    )
    if settings.auth_csrf_enabled:
        response.delete_cookie(
            key=settings.auth_csrf_cookie_name,
            domain=domain,
            path=path,
        )


def _extract_refresh_token_candidates(
    *,
    request: Request,
    payload: RefreshTokenRequest | None,
) -> list[str]:
    settings = get_settings()
    cookie_key = settings.auth_cookie_refresh_name
    cookie_token = request.cookies.get(cookie_key, "").strip()
    payload_token = payload.refresh_token.strip() if payload and payload.refresh_token else ""

    if payload_token and cookie_token and not secrets.compare_digest(payload_token, cookie_token):
        if settings.auth_refresh_reject_conflict:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token conflict between cookie and payload",
            )
        # Graceful mode for mobile/webview cookie skew: prefer HttpOnly cookie, then payload.
        return [cookie_token, payload_token]
    if payload_token:
        return [payload_token]
    if cookie_token:
        return [cookie_token]
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Thiếu refresh token",
    )


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
    if settings.environment.lower() == "production" and not (
        payload.accepted_terms and payload.accepted_privacy and payload.accepted_medical_consent
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Bạn cần xác nhận đầy đủ Điều khoản sử dụng, Chính sách quyền riêng tư "
                "và Đồng thuận sử dụng y tế trước khi tạo tài khoản."
            ),
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
    try:
        db.add(user)
        db.flush()
        # Provision only the empty identity boundary required by LifeMap.  This
        # contains no inferred conditions, medicines, measurements, or other
        # synthetic health data; users remain the sole source of clinical facts.
        db.add(PhrProfile(user_id=user.id, full_name=user.full_name))
        if payload.accepted_medical_consent:
            acquire_consent_lock_anchor(db, user_id=user.id)
            db.add(
                UserConsent(
                    user_id=user.id,
                    consent_type=MEDICAL_CONSENT_TYPE,
                    consent_version=required_medical_disclaimer_version(),
                )
            )
        db.commit()
        db.refresh(user)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chưa thể tạo tài khoản lúc này. Vui lòng thử lại sau ít phút.",
        ) from exc

    verification_token_preview: str | None = None
    email_delivery_status: str | None = None
    if not user.is_email_verified:
        try:
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
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.warning("Failed to dispatch verification email during registration: %s", exc)
            email_delivery_status = "failed"

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
    response: Response,
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

    if _role_requires_login_otp(role=user.role, settings=settings):
        otp_code = _issue_login_otp_code(
            db,
            user_id=user.id,
            ttl_minutes=settings.auth_login_otp_ttl_minutes,
        )
        otp_delivery_status = dispatch_action_email(
            settings,
            action="login_otp",
            recipient=user.email,
            token=otp_code,
        )
        otp_preview = otp_code if should_expose_action_token_preview(settings) else None
        return LoginResponse(
            role=user.role,  # type: ignore[arg-type]
            otp_required=True,
            otp_delivery_status=otp_delivery_status,
            otp_code_preview=otp_preview,
            otp_expires_in_seconds=settings.auth_login_otp_ttl_minutes * 60,
        )

    token = create_access_token(subject=user.email, role=user.role)
    refresh_token = _issue_refresh_session_token(db, user=user)
    user.last_login_at = datetime.now(tz=UTC)
    db.add(user)
    db.commit()
    _set_auth_cookies(response, access_token=token, refresh_token=refresh_token)
    return LoginResponse(
        access_token=token,
        refresh_token=refresh_token,
        role=user.role,  # type: ignore[arg-type]
    )


@router.post("/login-otp/verify", response_model=LoginResponse)
def verify_login_otp(
    payload: LoginOtpVerifyRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
    _cleanup_auth_tokens(db)
    normalized_email = _normalize_email(payload.email)
    _ensure_action_rate_limit(
        "login_otp_verify",
        f"{normalized_email}|{_extract_client_ip(request)}",
    )

    user = db.execute(select(User).where(User.email == normalized_email)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mã OTP không hợp lệ hoặc đã hết hạn",
        )
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đang bị khóa hoặc chưa sẵn sàng",
        )

    otp_code = payload.otp_code.strip()
    if not otp_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thiếu mã OTP")

    token_record = _consume_action_token(
        db,
        raw_token=otp_code,
        token_type="login_otp",
        user_id=user.id,
    )
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mã OTP không hợp lệ hoặc đã hết hạn",
        )

    role = cast(
        Role,
        user.role if user.role in {"normal", "researcher", "doctor", "admin"} else "normal",
    )
    access_token = create_access_token(subject=user.email, role=role)
    refresh_token = _issue_refresh_session_token(db, user=user)
    user.last_login_at = datetime.now(tz=UTC)
    db.add(user)
    db.commit()
    _set_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        role=role,
    )


@router.post("/refresh", response_model=LoginResponse)
def refresh_token(
    request: Request,
    response: Response,
    payload: RefreshTokenRequest | None = Body(default=None),
    db: Session = Depends(get_db),
) -> LoginResponse:
    _cleanup_auth_tokens(db)
    settings = get_settings()
    refresh_candidates = _extract_refresh_token_candidates(request=request, payload=payload)
    token_payload: TokenPayload | None = None
    session_token: AuthToken | None = None
    selected_token: str | None = None

    for candidate in refresh_candidates:
        try:
            decoded = decode_refresh_token(candidate)
        except HTTPException:
            continue
        # Refresh-rotation reuse detection (Requirements 2.3): when rotation is
        # enabled, a refresh jti that was already rotated must never be honored.
        # Reject the replay and record a no-PII reuse-detection event. Gated by
        # the flag, so behavior is unchanged when rotation is off.
        candidate_jti = str(decoded.get("jti", "")).strip()
        if (
            settings.hardening_refresh_rotation_enabled
            and candidate_jti
            and session_security.is_refresh_reused(candidate_jti)
        ):
            session_security.record_reuse(candidate_jti)
            _clear_auth_cookies(response)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token đã bị thu hồi do phát hiện tái sử dụng",
            )
        consumed = _consume_refresh_session_token(db, raw_token=candidate)
        if consumed:
            token_payload = decoded
            session_token = consumed
            selected_token = candidate
            break

    if not session_token or not token_payload or not selected_token:
        _clear_auth_cookies(response)
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

    role = cast(
        Role,
        user.role if user.role in {"normal", "researcher", "doctor", "admin"} else "normal",
    )
    access_token = create_access_token(subject=user.email, role=role)
    if settings.hardening_refresh_rotation_enabled:
        # Rotate: mint a new refresh token and invalidate the presented jti so a
        # later replay is detected (Requirements 2.2, 2.3). The DB session record
        # is still written for the new token to preserve the existing
        # single-use/consume flow.
        old_jti = str(token_payload.get("jti", "")).strip()
        rotated_refresh, _new_jti = session_security.rotate_refresh(old_jti, user.email, role)
        refresh_token = _issue_refresh_session_token(db, user=user, raw_token=rotated_refresh)
    else:
        refresh_token = _issue_refresh_session_token(db, user=user)
    _set_auth_cookies(response, access_token=access_token, refresh_token=refresh_token)
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
    return ForgotPasswordResponse(
        accepted=True,
        email_delivery_status=email_delivery_status,
        reset_token_preview=None,
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
    request: Request,
    response: Response,
    token_payload: TokenPayload | None = Depends(get_optional_current_token),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    settings = get_settings()
    user = None
    if token_payload and token_payload.sub:
        user = db.execute(select(User).where(User.email == token_payload.sub)).scalar_one_or_none()
    revoked_count = 0
    if user:
        revoked_count = _revoke_refresh_sessions(db, user_id=user.id)
    # Denylist the presented access + refresh jti(s) for their remaining TTL so
    # they are rejected on subsequent requests until natural expiry
    # (Requirement 2.4). Gated by the flag; a no-op when the denylist is off.
    if settings.hardening_token_denylist_enabled:
        if token_payload:
            _revoke_token_jti(token_payload)
        refresh_cookie = request.cookies.get(settings.auth_cookie_refresh_name, "").strip()
        if refresh_cookie:
            try:
                refresh_payload = decode_refresh_token(refresh_cookie)
            except HTTPException:
                refresh_payload = None
            if refresh_payload is not None:
                _revoke_token_jti(refresh_payload)
    _clear_auth_cookies(response)
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
    accepted = bool(
        latest and latest.consent_version == required_version and latest.revoked_at is None
    )
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

    acquire_consent_lock_anchor(db, user_id=user.id)

    latest = get_latest_user_consent(db, user_id=user.id, consent_type=MEDICAL_CONSENT_TYPE)
    if latest and latest.consent_version == required_version and latest.revoked_at is None:
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
