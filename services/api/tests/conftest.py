from __future__ import annotations

import os
from collections.abc import Generator

import pytest

from clara_api.core.bootstrap_admin import ensure_bootstrap_admin
from clara_api.core.config import get_settings
from clara_api.db import models as _db_models  # noqa: F401
from clara_api.db.base import Base
from clara_api.db.session import SessionLocal, engine


@pytest.fixture(scope="session", autouse=True)
def _configure_test_bootstrap_admin() -> Generator[None, None, None]:
    previous = {
        "AUTH_BOOTSTRAP_ADMIN_ENABLED": os.environ.get("AUTH_BOOTSTRAP_ADMIN_ENABLED"),
        "AUTH_BOOTSTRAP_ADMIN_EMAIL": os.environ.get("AUTH_BOOTSTRAP_ADMIN_EMAIL"),
        "AUTH_BOOTSTRAP_ADMIN_PASSWORD": os.environ.get("AUTH_BOOTSTRAP_ADMIN_PASSWORD"),
        "AUTH_BOOTSTRAP_ADMIN_FORCE_RESET_PASSWORD": os.environ.get("AUTH_BOOTSTRAP_ADMIN_FORCE_RESET_PASSWORD"),
    }
    os.environ["AUTH_BOOTSTRAP_ADMIN_ENABLED"] = "true"
    os.environ["AUTH_BOOTSTRAP_ADMIN_EMAIL"] = "admin@example.com"
    os.environ["AUTH_BOOTSTRAP_ADMIN_PASSWORD"] = "test-admin-pass-123"
    os.environ["AUTH_BOOTSTRAP_ADMIN_FORCE_RESET_PASSWORD"] = "false"
    get_settings.cache_clear()
    yield
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def _prepare_database_schema() -> Generator[None, None, None]:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        ensure_bootstrap_admin(db, get_settings())
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _reset_database_rows() -> Generator[None, None, None]:
    with SessionLocal() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
        ensure_bootstrap_admin(db, get_settings())
    yield
