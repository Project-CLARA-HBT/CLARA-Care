from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from clara_api.api.router import api_router
from clara_api.core.config import get_settings
from clara_api.core.exceptions import ClaraAPIError
from clara_api.core.metrics import APIMetricsMiddleware
from clara_api.core.rate_limit import RateLimiterMiddleware
from clara_api.core.rbac import AuthContextMiddleware
from clara_api.db.base import Base
from clara_api.db import models as _db_models  # noqa: F401
from clara_api.db.session import engine

settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthContextMiddleware)
app.add_middleware(RateLimiterMiddleware)
app.add_middleware(APIMetricsMiddleware)


@app.on_event("startup")
def init_db_schema() -> None:
    Base.metadata.create_all(bind=engine)


@app.exception_handler(ClaraAPIError)
async def clara_error_handler(_request: Request, exc: ClaraAPIError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def generic_exception_handler(_request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": f"Lỗi hệ thống: {exc}"})


@app.get("/health")
def root_health() -> dict[str, str]:
    return {"status": "ok", "service": "clara-api"}


app.include_router(api_router)
