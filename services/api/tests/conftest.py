from __future__ import annotations

import os
from pathlib import Path

import pytest


TEST_DB_PATH = Path(__file__).with_name(".pytest_clara_api.db")
os.environ.setdefault("DATABASE_URL", f"sqlite+pysqlite:///{TEST_DB_PATH}")
os.environ.setdefault("AUTH_AUTO_PROVISION_USERS", "true")
os.environ.setdefault("AUTH_REQUIRE_EMAIL_VERIFICATION", "false")
os.environ.setdefault("AUTH_BOOTSTRAP_ADMIN_ENABLED", "true")

from clara_api.core.bootstrap_admin import ensure_bootstrap_admin
from clara_api.core.config import get_settings
from clara_api.db import models as _db_models  # noqa: F401
from clara_api.db.base import Base
from clara_api.db.session import SessionLocal, engine


@pytest.fixture(scope="session", autouse=True)
def _cleanup_test_db_file() -> None:
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    yield
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture(autouse=True)
def _reset_database_schema() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        ensure_bootstrap_admin(db, get_settings())
    yield

