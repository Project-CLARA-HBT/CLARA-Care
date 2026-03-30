from __future__ import annotations

from collections.abc import Generator

import pytest

from clara_api.core.bootstrap_admin import ensure_bootstrap_admin
from clara_api.core.config import get_settings
from clara_api.db import models as _db_models  # noqa: F401
from clara_api.db.base import Base
from clara_api.db.session import SessionLocal, engine


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
