import logging
import secrets
from collections.abc import Mapping, Sequence

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from clara_api.api.router import api_router
from clara_api.api.v1.endpoints.research import start_research_job_recovery
from clara_api.core.bootstrap_admin import ensure_bootstrap_admin
from clara_api.core.config import get_settings
from clara_api.core.exceptions import ClaraAPIError
from clara_api.core.logging_config import CorrelationIdMiddleware, configure_logging
from clara_api.core.metrics import (
    APIMetricsMiddleware,
    format_metrics_prometheus,
    get_api_metrics_store,
)
from clara_api.core.rate_limit import RateLimiterMiddleware
from clara_api.core.rbac import AuthContextMiddleware, has_valid_explicit_bearer_token
from clara_api.core.readiness import evaluate_readiness
from clara_api.core.request_limits import RequestBodyLimitMiddleware
from clara_api.core.timeouts import TimeoutFloorError, assert_settings_timeout_floors
from clara_api.db import models as _db_models  # noqa: F401
from clara_api.db.base import Base
from clara_api.db.session import SessionLocal, engine
from clara_api.phr.migration_guard import (
    PhrMigrationGuardError,
    assert_engine_phr_profiles_migration_managed,
)

settings = get_settings()
logger = logging.getLogger(__name__)

# Structured JSON logging + PII redaction filter (Requirement 7.1, 7.2, 7.3),
# gated by HARDENING_STRUCTURED_LOGGING_ENABLED. Default-off: this is a no-op and
# the current logging configuration is preserved (Requirement 7.5, 11.1, 11.2).
configure_logging(settings)

app = FastAPI(title=settings.app_name, debug=settings.debug)
_CSRF_EXEMPT_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/login-otp/verify",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/api/v1/auth/verify-email",
    "/api/v1/auth/resend-verification",
}

# Public, unauthenticated read-only path prefixes. These register only GET, so an
# unsupported write verb must surface as 405 Method Not Allowed (not a 403 CSRF
# failure) even when the caller happens to carry a session cookie. Exempting them
# from CSRF is safe because no mutating route exists under these prefixes.
_CSRF_EXEMPT_PREFIXES = ("/api/v1/phr/shared/",)

# Default Content-Security-Policy emitted only when HARDENING_CSP_ENABLED is on
# (Requirement 7.4). Kept conservative and self-origin oriented: the API serves
# JSON, not HTML, so a restrictive policy adds defense-in-depth without breaking
# the API surface. When the flag is off this constant is never read, preserving
# the current response behavior (Requirement 11.1, 11.2).
_DEFAULT_CSP = (
    "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
)

# Obviously-insecure / placeholder secret values that must never reach a
# production deployment (Requirement 1.2). These include the historical
# plaintext compose defaults that task 2.1 removed from
# docker-compose.app.yml, plus common throwaway placeholders. The startup
# guards below reject any production secret whose value (case-insensitively)
# appears in these sets and emit a secret-value-free error. Stored lower-cased
# so the comparison is case-insensitive.
_INSECURE_JWT_SECRET_VALUES = frozenset(
    {
        "change-me",
        "change_me",
        "change_me_super_secret",
        "changeme",
        "secret",
        "jwt-secret",
        "your-secret-key",
        "dev",
        "development",
        "test",
    }
)
_INSECURE_ML_INTERNAL_KEY_VALUES = frozenset(
    {
        "clara_internal_key_default_2026",
        "change-me",
        "change_me",
        "changeme",
        "dev",
        "development",
        "test",
    }
)
# Insecure bootstrap-admin passwords, including the historical compose default
# (``Clara#Admin2026!``) and common weak placeholders.
_INSECURE_BOOTSTRAP_PASSWORDS = frozenset(
    {
        "wrongpass",
        "change-me",
        "admin",
        "password",
        "12345678",
        "clara#admin2026!",
    }
)

raw_origins = [
    origin.strip()
    for origin in settings.cors_allowed_origins.split(",")
    if origin.strip()
]
cors_allow_all_origins = "*" in raw_origins
cors_origins = ["*"] if cors_allow_all_origins else raw_origins
cors_methods = [
    method.strip().upper()
    for method in settings.cors_allowed_methods.split(",")
    if method.strip()
]
cors_headers = [
    header.strip()
    for header in settings.cors_allowed_headers.split(",")
    if header.strip()
]

if settings.environment.lower() == "production" and "*" in raw_origins:
    raise RuntimeError("CORS_ALLOWED_ORIGINS cannot contain wildcard in production.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["*"],
    allow_credentials=False if cors_allow_all_origins else settings.cors_allow_credentials,
    allow_methods=cors_methods or ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=cors_headers or ["Authorization", "Content-Type"],
)
app.add_middleware(AuthContextMiddleware)
app.add_middleware(RateLimiterMiddleware)
# Request body-size limit (gated by HARDENING_REQUEST_BODY_LIMIT_ENABLED; inert
# by default). Rejects over-limit bodies with a 413-class PII-free response. The
# audio-upload endpoints retain their own _MAX_AUDIO_BYTES limit (exempted in the
# middleware).
app.add_middleware(RequestBodyLimitMiddleware)
app.add_middleware(APIMetricsMiddleware)


@app.on_event("startup")
def init_db_schema() -> None:
    # Timeout-floor invariant (Requirement 2.4): the API ML request timeout must
    # never sit below the downstream CLARA_ML synthesis timeout. Validated in
    # every environment so a misconfiguration fails fast at startup.
    try:
        assert_settings_timeout_floors(
            ml_service_timeout_seconds=settings.ml_service_timeout_seconds,
            ml_research_timeout_seconds=settings.ml_research_timeout_seconds,
            deepseek_timeout_seconds=settings.deepseek_timeout_seconds,
        )
    except TimeoutFloorError as exc:
        raise RuntimeError(
            "ML request timeout misconfigured: "
            "ML_SERVICE_TIMEOUT_SECONDS must be >= DEEPSEEK_TIMEOUT_SECONDS "
            "and the sync-research path must stay >= ML_RESEARCH_TIMEOUT_SECONDS. "
            f"{exc}"
        ) from exc
    if settings.environment.lower() == "production":
        if settings.jwt_secret_key.strip().lower() in _INSECURE_JWT_SECRET_VALUES:
            raise RuntimeError(
                "JWT_SECRET_KEY uses an insecure/placeholder value; "
                "configure a strong, unique secret in production."
            )
        # Reject a previous-key rotation window that reuses a known-insecure
        # placeholder (Requirement 1.2, 1.7). An empty previous key is the
        # default and is always allowed (no overlap window).
        previous_jwt_key = settings.jwt_secret_key_previous.strip()
        if previous_jwt_key and previous_jwt_key.lower() in _INSECURE_JWT_SECRET_VALUES:
            raise RuntimeError(
                "JWT_SECRET_KEY_PREVIOUS uses an insecure/placeholder value; "
                "set it only to a real prior signing key during rotation, "
                "and clear it once prior-key tokens have expired."
            )
        if not settings.auth_cookie_secure:
            raise RuntimeError("AUTH_COOKIE_SECURE must be true in production.")
        if settings.auth_csrf_enabled and not settings.auth_cookie_secure:
            raise RuntimeError("CSRF protection requires AUTH_COOKIE_SECURE=true in production.")
        ml_internal_key = settings.ml_internal_api_key.strip()
        if not ml_internal_key:
            raise RuntimeError("ML_INTERNAL_API_KEY must be configured in production.")
        if ml_internal_key.lower() in _INSECURE_ML_INTERNAL_KEY_VALUES:
            raise RuntimeError(
                "ML_INTERNAL_API_KEY uses an insecure/placeholder value; "
                "configure a strong, unique secret in production."
            )
        if settings.auth_auto_provision_users:
            raise RuntimeError("AUTH_AUTO_PROVISION_USERS must be disabled in production.")
        bootstrap_password = settings.auth_bootstrap_admin_password.strip().lower()
        if (
            settings.auth_bootstrap_admin_enabled
            and bootstrap_password in _INSECURE_BOOTSTRAP_PASSWORDS
        ):
            raise RuntimeError(
                "AUTH_BOOTSTRAP_ADMIN_PASSWORD uses insecure default; configure a strong secret."
            )
        if (
            settings.rate_limit_distributed_enabled or settings.auth_login_distributed_enabled
        ) and not settings.redis_url.strip():
            raise RuntimeError(
                "REDIS_URL must be configured when distributed security limiters are enabled."
            )
    # Migration-management guard (Requirement 1.2): in production the PHR schema
    # must be created by Alembic migrations, never by the create_all fallback
    # below. This runs before create_all so the inspected table set reflects the
    # migration-produced schema. No-op outside production.
    try:
        assert_engine_phr_profiles_migration_managed(
            engine, environment=settings.environment
        )
    except PhrMigrationGuardError as exc:
        raise RuntimeError(str(exc)) from exc
    # Production schema changes are owned exclusively by Alembic. Keeping
    # create_all in local/test preserves their convenient empty-DB bootstrap
    # without allowing a production startup to race ahead of a migration.
    if settings.environment.strip().lower() != "production":
        Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        ensure_bootstrap_admin(db, settings)
    start_research_job_recovery()


@app.exception_handler(ClaraAPIError)
async def clara_error_handler(_request: Request, exc: ClaraAPIError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


def _json_safe(value: object) -> object:
    if isinstance(value, BaseException):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_safe(item) for item in value]
    return value


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": _json_safe(exc.errors())})


@app.exception_handler(Exception)
async def generic_exception_handler(_request: Request, exc: Exception):
    # Structured-logging hardening (Requirement 7.3): log only the error *type*
    # — never the traceback, the raw exception text, or the request body, any of
    # which can carry PII. Using ``logger.error`` (not ``logger.exception``)
    # keeps the stack trace and the raw exception message out of the logs in
    # every configuration, so no PII leaks even when structured logging is off.
    # When HARDENING_STRUCTURED_LOGGING_ENABLED is on, this record additionally
    # flows through the JSON formatter + RedactionFilter and carries the
    # per-request correlation id (surfaced automatically by the formatter). The
    # exception class name is a bounded, non-PII identifier and is safe to emit.
    logger.error("Unhandled API error (%s)", type(exc).__name__)
    # Client response is unchanged from the pre-hardening baseline: a detailed
    # message only under debug / non-secure-error-messages, and a generic,
    # PII-free message in production (Requirement 7.4, 11.2).
    if settings.debug or not settings.secure_error_messages:
        return JSONResponse(status_code=500, content={"detail": f"Lỗi hệ thống: {exc}"})
    return JSONResponse(status_code=500, content={"detail": "Lỗi hệ thống nội bộ"})


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    response.headers.setdefault("Cache-Control", "no-store")
    # Content-Security-Policy (Requirement 7.4), gated by HARDENING_CSP_ENABLED.
    # Default-off: the header is not added, preserving the pre-hardening response
    # shape (Requirement 11.1, 11.2). When enabled, emit a restrictive default
    # CSP; ``setdefault`` lets any upstream value take precedence.
    if settings.hardening_csp_enabled:
        response.headers.setdefault("Content-Security-Policy", _DEFAULT_CSP)
    if request.url.scheme == "https":
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
    return response


@app.middleware("http")
async def enforce_csrf_for_cookie_session(request: Request, call_next):
    if not settings.auth_csrf_enabled:
        return await call_next(request)

    if request.method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
        return await call_next(request)
    if request.url.path in _CSRF_EXEMPT_PATHS:
        return await call_next(request)
    if request.url.path.startswith(_CSRF_EXEMPT_PREFIXES):
        return await call_next(request)

    auth_cookie_present = bool(
        request.cookies.get(settings.auth_cookie_access_name)
        or request.cookies.get(settings.auth_cookie_refresh_name)
    )
    # CSRF is required only when session cookies are actually used for auth.
    # An Authorization header is not itself proof of Bearer authentication: it
    # must parse, verify and pass the revocation check through the same RBAC
    # helper used by route dependencies.  Otherwise a junk/mixed-case header
    # could bypass CSRF and then fall back to the caller's cookie session.
    if not auth_cookie_present or has_valid_explicit_bearer_token(request):
        return await call_next(request)

    csrf_cookie = request.cookies.get(settings.auth_csrf_cookie_name, "").strip()
    csrf_header = request.headers.get(settings.auth_csrf_header_name, "").strip()
    if not csrf_cookie or not csrf_header or not secrets.compare_digest(csrf_cookie, csrf_header):
        return JSONResponse(
            status_code=403,
            content={"detail": "CSRF validation failed"},
        )
    return await call_next(request)


@app.get("/health")
def root_health() -> dict[str, str]:
    return {"status": "ok", "service": "clara-api"}


@app.get("/health/ready")
def root_readiness() -> JSONResponse:
    # Dependency-aware readiness probe (Requirement 6.1, 6.2), gated by
    # HARDENING_READINESS_PROBE_ENABLED. Default-off returns the liveness shape
    # (always ready); enabled, it returns 503 with a no-PII reason code when a
    # critical dependency (DB, configured cache, downstream ML) is unreachable.
    # The root liveness /health above is unchanged (Requirement 6.3).
    result = evaluate_readiness()
    return JSONResponse(status_code=result.http_status, content=result.to_payload())


@app.get("/metrics", response_class=PlainTextResponse)
def root_metrics(request: Request) -> PlainTextResponse:
    expected = settings.metrics_access_token.strip()
    if settings.environment.lower() == "production" and not expected:
        raise HTTPException(status_code=404, detail="Not Found")
    if expected:
        # Query-string secrets leak into browser history, reverse-proxy access
        # logs and referrers. Metrics authentication is header-only.
        provided = request.headers.get("x-metrics-token", "").strip()
        if not provided or not secrets.compare_digest(provided, expected):
            raise HTTPException(status_code=403, detail="Forbidden")
    payload = format_metrics_prometheus(get_api_metrics_store().snapshot())
    return PlainTextResponse(content=payload, media_type="text/plain; version=0.0.4")


# Per-request correlation id (Requirement 7.1, 7.3), gated by
# HARDENING_STRUCTURED_LOGGING_ENABLED. Registered last so it is the outermost
# middleware: it binds the correlation id before any inner middleware logs and
# echoes it in the X-Correlation-ID response header. Default-off it is not
# registered, so response shapes match the pre-hardening baseline (11.1, 11.2).
if settings.hardening_structured_logging_enabled:
    app.add_middleware(CorrelationIdMiddleware)

app.include_router(api_router)
# Backward compatibility for stale frontend bundles that accidentally call
# double-prefixed paths like /api/v1/api/v1/*.
app.include_router(api_router, prefix="/api/v1")
