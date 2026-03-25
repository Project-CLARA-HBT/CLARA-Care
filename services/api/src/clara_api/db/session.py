from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from clara_api.core.config import get_settings

settings = get_settings()


def _engine_kwargs_for(url: str) -> dict[str, object]:
    kwargs: dict[str, object] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return kwargs


def _build_engine():
    primary_url = settings.database_url
    primary_engine = create_engine(primary_url, **_engine_kwargs_for(primary_url))
    try:
        with primary_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return primary_engine
    except Exception:
        fallback_url = "sqlite+pysqlite:////data/clara.db"
        fallback_engine = create_engine(fallback_url, **_engine_kwargs_for(fallback_url))
        return fallback_engine


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, class_=Session, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
