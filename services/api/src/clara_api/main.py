import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from clara_api.api.router import api_router
from clara_api.core.bootstrap_admin import ensure_bootstrap_admin
from clara_api.core.config import get_settings
from clara_api.core.exceptions import ClaraAPIError
from clara_api.core.metrics import (
    APIMetricsMiddleware,
    format_metrics_prometheus,
    get_api_metrics_store,
)
from clara_api.core.rate_limit import RateLimiterMiddleware
from clara_api.core.rbac import AuthContextMiddleware
from clara_api.db import models as _db_models  # noqa: F401
from clara_api.db.base import Base
from clara_api.db.session import SessionLocal, engine

settings = get_settings()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name, debug=settings.debug)

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["*"],
    allow_credentials=False if cors_allow_all_origins else settings.cors_allow_credentials,
    allow_methods=cors_methods or ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=cors_headers or ["Authorization", "Content-Type"],
)
app.add_middleware(AuthContextMiddleware)
app.add_middleware(RateLimiterMiddleware)
app.add_middleware(APIMetricsMiddleware)


@app.on_event("startup")
def init_db_schema() -> None:
    if settings.environment.lower() == "production":
        if settings.jwt_secret_key.strip() == "change-me":
            raise RuntimeError("JWT_SECRET_KEY must be configured in production.")
        if not settings.auth_cookie_secure:
            raise RuntimeError("AUTH_COOKIE_SECURE must be true in production.")
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        ensure_bootstrap_admin(db, settings)


@app.exception_handler(ClaraAPIError)
async def clara_error_handler(_request: Request, exc: ClaraAPIError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def generic_exception_handler(_request: Request, exc: Exception):
    logger.exception("Unhandled API error")
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
    if request.url.scheme == "https":
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
    return response


@app.get("/health")
def root_health() -> dict[str, str]:
    return {"status": "ok", "service": "clara-api"}


@app.get("/metrics", response_class=PlainTextResponse)
def root_metrics() -> PlainTextResponse:
    payload = format_metrics_prometheus(get_api_metrics_store().snapshot())
    return PlainTextResponse(content=payload, media_type="text/plain; version=0.0.4")


app.include_router(api_router)
