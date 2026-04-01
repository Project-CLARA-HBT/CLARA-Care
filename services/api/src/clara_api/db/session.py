import logging
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from clara_api.core.config import get_settings

logger = logging.getLogger(__name__)
_DEFAULT_FALLBACK_DATABASE_URL = "sqlite+pysqlite:////data/clara.db"
_TRUE_VALUES = {"1", "true", "yes", "on"}


def _engine_kwargs_for(url: str) -> dict[str, object]:
    kwargs: dict[str, object] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return kwargs


def _bool_from_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE_VALUES


def _fallback_enabled() -> bool:
    if "DATABASE_FALLBACK_ENABLED" in os.environ:
        return _bool_from_env("DATABASE_FALLBACK_ENABLED", default=False)
    if "DB_ALLOW_SQLITE_FALLBACK" in os.environ:
        return _bool_from_env("DB_ALLOW_SQLITE_FALLBACK", default=False)
    return False


def _is_production_environment(environment: str) -> bool:
    return environment.strip().lower() in {"prod", "production"}


def _probe_connection(engine_obj) -> None:
    with engine_obj.connect() as conn:
        conn.execute(text("SELECT 1"))


def _resolve_fallback_url() -> str:
    configured = os.getenv("DATABASE_FALLBACK_URL", "").strip()
    return configured or _DEFAULT_FALLBACK_DATABASE_URL


def _build_engine():
    settings = get_settings()
    primary_url = settings.database_url
    primary_engine = create_engine(primary_url, **_engine_kwargs_for(primary_url))
    try:
        _probe_connection(primary_engine)
        return primary_engine
    except Exception as exc:
        is_production = _is_production_environment(settings.environment)
        fallback_enabled = _fallback_enabled()
        if is_production and not fallback_enabled:
            raise RuntimeError(
                "Primary database is unavailable in production. "
                "Refusing implicit fallback; set DATABASE_FALLBACK_ENABLED=true "
                "to enable explicit fallback."
            ) from exc

        if not fallback_enabled:
            raise RuntimeError(
                "Primary database is unavailable and DATABASE_FALLBACK_ENABLED is false."
            ) from exc

        fallback_url = _resolve_fallback_url()
        if fallback_url == primary_url:
            raise RuntimeError("DATABASE_FALLBACK_URL must differ from DATABASE_URL.") from exc

        fallback_engine = create_engine(fallback_url, **_engine_kwargs_for(fallback_url))
        try:
            _probe_connection(fallback_engine)
        except Exception as fallback_exc:
            raise RuntimeError(
                "Primary database failed and fallback database is also unavailable."
            ) from fallback_exc

        logger.warning(
            "Primary database unavailable (%s). Falling back to %s because "
            "DATABASE_FALLBACK_ENABLED=true.",
            exc.__class__.__name__,
            fallback_url,
        )
        return fallback_engine


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
