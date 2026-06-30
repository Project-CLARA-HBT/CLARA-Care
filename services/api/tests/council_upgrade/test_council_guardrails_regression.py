"""Guardrail regression + migration-reversibility verification (task 9.3).

This module re-asserts the existing Council guardrails are preserved on the
new and existing Council endpoints after the upgrade lands its persistence and
streaming seams, and that the upgrade's Alembic migration
(``20260421_0017_council_upgrade_runs_oversight``) is additive and reversible.

It anchors the design's Correctness Properties at the guardrail layer:

* **P4 — Owner isolation**: a doctor cannot read or run another doctor's case
  (always 404), on every owner-scoped Council endpoint (Req 2.5, 3.4, 4.3).
* **P7 — Authorization soundness / RBAC**: every Council case/run endpoint stays
  behind authentication and ``doctor``-role authorization; a non-doctor is
  rejected with 403 before any side effect (Req 4.1, 4.2, 4.5).
* **P13 — CSRF preserved**: a cookie-authenticated mutating Council endpoint
  rejects a missing/invalid CSRF token (403), while the Bearer-token path is
  unaffected (Req 4.4, 9.6).
* **Additive + reversible migration**: ``upgrade`` creates exactly
  ``council_runs`` / ``council_oversight_actions`` and the additive nullable
  ``council_cases.oversight_state`` column; ``downgrade`` removes exactly those,
  leaving the pre-existing schema untouched (Req 9.7).

All endpoint tests authenticate with Bearer tokens (so they bypass the CSRF
browser vector) except the dedicated CSRF test, which deliberately uses a
session cookie. The ML proxy is never reached in these tests because every
negative path is rejected by authz/ownership before the proxy call.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient

from clara_api.core.config import get_settings
from clara_api.main import app

client = TestClient(app)

_RUN_PAYLOAD: dict[str, Any] = {
    "symptoms": ["polypharmacy", "fatigue"],
    "labs": {"creatinine": 1.2},
    "medications": ["warfarin"],
    "history": "htn",
    "specialist_count": 2,
    "specialists": ["pharmacology", "nephrology"],
}


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_case(token: str) -> int:
    response = client.post(
        "/api/v1/council/cases",
        headers=_auth(token),
        json={"title": "guardrail case", "request": _RUN_PAYLOAD},
    )
    assert response.status_code == 200, response.text
    return int(response.json()["id"])


# ---------------------------------------------------------------------------
# P7 — RBAC: doctor-role required on Council case/run endpoints
# ---------------------------------------------------------------------------


def test_non_doctor_rejected_on_case_collection_endpoints() -> None:
    """A researcher (non-doctor) is rejected 403 on the case collection routes."""
    token = _login("alice@research.clara")

    assert client.get("/api/v1/council/cases", headers=_auth(token)).status_code == 403
    assert (
        client.post(
            "/api/v1/council/cases",
            headers=_auth(token),
            json={"title": "x", "request": _RUN_PAYLOAD},
        ).status_code
        == 403
    )
    assert client.get("/api/v1/council/cases/latest", headers=_auth(token)).status_code == 403


def test_non_doctor_rejected_on_case_scoped_endpoints() -> None:
    """RBAC fires (403) before any ownership lookup or side effect on a case id."""
    token = _login("alice@research.clara")

    assert client.get("/api/v1/council/cases/1", headers=_auth(token)).status_code == 403
    assert (
        client.post(
            "/api/v1/council/cases/1/run", headers=_auth(token), json={}
        ).status_code
        == 403
    )
    assert (
        client.patch(
            "/api/v1/council/cases/1", headers=_auth(token), json={"title": "y"}
        ).status_code
        == 403
    )


def test_non_doctor_rejected_on_streaming_run(set_flags) -> None:
    """The streaming run stays behind ``doctor`` RBAC even with the flag on (Req 1.6).

    RBAC is a dependency, so it is evaluated before the in-body streaming flag
    check; a non-doctor is rejected 403 whether the flag is on or off.
    """
    set_flags(council_streaming_enabled=True)
    token = _login("alice@research.clara")

    assert (
        client.post(
            "/api/v1/council/cases/1/run/stream", headers=_auth(token), json={}
        ).status_code
        == 403
    )


def test_unauthenticated_rejected_before_side_effect() -> None:
    """An unauthenticated caller is rejected (401) before any side effect (Req 4.5).

    Cookies are cleared so the request carries no session cookie left over from
    prior logins on the shared client; a truly credential-less mutation is
    rejected 401 by the auth dependency (no CSRF cookie vector applies).
    """
    client.cookies.clear()
    try:
        assert client.post("/api/v1/council/cases", json={"title": "x"}).status_code == 401
        assert client.post("/api/v1/council/cases/1/run", json={}).status_code == 401
    finally:
        client.cookies.clear()


# ---------------------------------------------------------------------------
# P4 — Owner isolation: a doctor cannot touch another doctor's case
# ---------------------------------------------------------------------------


def test_owner_isolation_read_run_patch_return_404() -> None:
    """A second doctor cannot read, run, or patch the first doctor's case (404)."""
    owner = _login("owner@doctor.clara")
    case_id = _create_case(owner)

    intruder = _login("intruder@doctor.clara")

    # Read isolation.
    assert (
        client.get(f"/api/v1/council/cases/{case_id}", headers=_auth(intruder)).status_code == 404
    )
    # Run isolation — 404 happens at ownership lookup, before the ML proxy.
    assert (
        client.post(
            f"/api/v1/council/cases/{case_id}/run", headers=_auth(intruder), json={}
        ).status_code
        == 404
    )
    # Write isolation.
    assert (
        client.patch(
            f"/api/v1/council/cases/{case_id}",
            headers=_auth(intruder),
            json={"title": "hijack"},
        ).status_code
        == 404
    )

    # The owner can still read their own case — isolation is directional.
    assert (
        client.get(f"/api/v1/council/cases/{case_id}", headers=_auth(owner)).status_code == 200
    )


def test_owner_isolation_on_streaming_run(set_flags) -> None:
    """With streaming on, a non-owner doctor cannot stream another's case (404)."""
    set_flags(council_streaming_enabled=True)
    owner = _login("owner@doctor.clara")
    case_id = _create_case(owner)

    intruder = _login("intruder@doctor.clara")
    response = client.post(
        f"/api/v1/council/cases/{case_id}/run/stream", headers=_auth(intruder), json={}
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# P13 — CSRF preserved on cookie-authenticated mutations
# ---------------------------------------------------------------------------


def test_csrf_rejected_for_cookie_auth_council_mutation() -> None:
    """A cookie-authenticated Council mutation without a CSRF token is rejected (403).

    The global CSRF middleware enforces this uniformly; the Council mutation
    inherits the protection (Correctness Property 13). CSRF protection is enabled
    by default (``AUTH_CSRF_ENABLED`` defaults true).
    """
    settings = get_settings()
    assert settings.auth_csrf_enabled is True  # default-on contract

    client.cookies.clear()
    client.cookies.set(settings.auth_cookie_access_name, "fake-session-cookie")
    try:
        response = client.post(
            "/api/v1/council/cases",
            json={"title": "csrf", "request": _RUN_PAYLOAD},
        )
    finally:
        client.cookies.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_bearer_auth_council_mutation_bypasses_csrf() -> None:
    """The Bearer-token path is unaffected by CSRF (no browser cookie vector)."""
    client.cookies.clear()
    token = _login("dr@doctor.clara")
    response = client.post(
        "/api/v1/council/cases",
        headers=_auth(token),
        json={"title": "bearer ok", "request": _RUN_PAYLOAD},
    )
    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# Additive + reversible migration (20260421_0017)
# ---------------------------------------------------------------------------

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260421_0017_council_upgrade_runs_oversight.py"
)

_NEW_TABLES = {"council_runs", "council_oversight_actions"}


def _load_migration():
    spec = importlib.util.spec_from_file_location("council_migration_0017", _MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_prereq_tables(engine: sa.Engine) -> None:
    """Pre-create the tables the migration attaches to.

    ``council_cases`` must exist for the additive ``oversight_state`` column-add;
    ``users`` is the FK target referenced by ``council_runs`` (SQLite records the
    FK without requiring enforcement).
    """
    meta = sa.MetaData()
    sa.Table(
        "users",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    sa.Table(
        "council_cases",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False, server_default="New Case"),
    )
    meta.create_all(bind=engine)


@pytest.fixture
def migration_engine(tmp_path) -> Generator[sa.Engine, None, None]:
    db_path = tmp_path / "council_migration_roundtrip.db"
    eng = sa.create_engine(f"sqlite+pysqlite:///{db_path}")
    try:
        _create_prereq_tables(eng)
        yield eng
    finally:
        eng.dispose()


def test_council_migration_upgrade_downgrade_roundtrip(migration_engine: sa.Engine) -> None:
    migration = _load_migration()

    # --- upgrade: new tables created + additive nullable column added ---
    with migration_engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            migration.upgrade()
        conn.commit()

        inspector = sa.inspect(conn)
        tables = set(inspector.get_table_names())
        assert _NEW_TABLES.issubset(tables), f"missing after upgrade: {tables}"

        case_cols = {c["name"]: c for c in inspector.get_columns("council_cases")}
        assert "oversight_state" in case_cols
        # Additive column must be nullable so existing rows are untouched.
        assert case_cols["oversight_state"]["nullable"] is True

    # --- downgrade: removes exactly what upgrade created ---
    with migration_engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            migration.downgrade()
        conn.commit()

        inspector = sa.inspect(conn)
        tables = set(inspector.get_table_names())
        assert not (_NEW_TABLES & tables), f"new tables survived downgrade: {tables}"
        # Pre-existing tables survive; only the added column is dropped.
        assert "council_cases" in tables
        assert "users" in tables
        case_cols = {c["name"] for c in inspector.get_columns("council_cases")}
        assert "oversight_state" not in case_cols
