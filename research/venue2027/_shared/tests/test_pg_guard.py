"""SH-postgres_isolation: adversarial + positive vectors for pg_guard.

Must not require Docker or psycopg; the guard is a pure function over strings.
Truth is derived from the declared isolation contract (compose network host
``pg_research``, DB name ``clara_research``), never from the candidate's own
reason strings beyond the stable contract codes.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import pg_guard  # noqa: E402


# ---------------------------------------------------------------- positive
@pytest.mark.parametrize(
    "url",
    [
        "postgresql://research_app:pw@pg_research:5432/clara_research",
        "postgres://research_app@pg_research/clara_research",
        "postgresql://research_app:pw@pg_research:5432/clara_research?sslmode=disable",
    ],
)
def test_accepts_isolated_research_url(url: str) -> None:
    ok, reason = pg_guard.check_database_url(url)
    assert ok is True
    assert reason == "OK"


def test_assert_passes_for_valid_url() -> None:
    pg_guard.assert_isolated_database_url(
        "postgresql://research_app:pw@pg_research:5432/clara_research"
    )


# --------------------------------------------------- scheme adversarial
@pytest.mark.parametrize(
    "url",
    [
        "sqlite:////tmp/clara_api_ci.db",
        "sqlite+pysqlite:////tmp/clara_api_ci.db",
        "mysql://root:pw@pg_research/clara_research",
        "mongodb://localhost:27017/clara_research",
        "//pg_research/clara_research",  # scheme-less: no postgres scheme
        "postgresql+psycopg2://research_app@pg_research/clara_research",
    ],
)
def test_refuses_non_postgres_schemes(url: str) -> None:
    with pytest.raises(pg_guard.PgGuardError) as exc:
        pg_guard.assert_isolated_database_url(url)
    # scheme-less URLs are refused as UNPARSEABLE; known schemes as NON_POSTGRES_SCHEME
    assert exc.value.reason_code in ("NON_POSTGRES_SCHEME", "UNPARSEABLE_URL")


# ------------------------------------------------ prod-like host adversarial
@pytest.mark.parametrize(
    "url,expected",
    [
        ("postgresql://u:p@db.prod.clara-care.internal:5432/clara", "PROD_LIKE_HOST"),
        ("postgresql://u:p@prod-db.internal:5432/clara", "PROD_LIKE_HOST"),
        ("postgresql://u:p@production:5432/x", "PROD_LIKE_HOST"),
        ("postgresql://u:p@staging-db:5432/clara_research", "PROD_LIKE_HOST"),
        ("postgresql://u:p@clara-api.internal:5432/clara_research", "PROD_LIKE_HOST"),
        ("postgresql://u:p@db:5432/clara_research", "PROD_LIKE_HOST"),
    ],
)
def test_refuses_prod_like_hosts(url: str, expected: str) -> None:
    with pytest.raises(pg_guard.PgGuardError) as exc:
        pg_guard.assert_isolated_database_url(url)
    assert exc.value.reason_code == expected


# ------------------------------------------- localhost non-isolated adversarial
@pytest.mark.parametrize(
    "url",
    [
        "postgresql://clara:clara@localhost:5432/clara",  # default dev DSN
        "postgresql://clara:clara@127.0.0.1:5432/clara",
        "postgresql://clara:clara@::1:5432/clara_research",
        "postgresql://u:p@0.0.0.0:5432/clara_research",
        "postgresql://u:p@10.0.0.5:5432/clara_research",  # remote LAN/VPN
        # "db"-prefixed host also matches the prod-like pattern; either stable
        # refusal code is fail-closed, precedence asserted here.
        "postgresql://u:p@db.internal:5432/clara_research",
        "postgresql://u:p@some-other-container:5432/clara_research",
        # even a *correct* db name on localhost is refused: isolation is
        # provided by the compose network, not by the DB name.
        "postgresql://u:p@localhost:55433/clara_research",
    ],
)
def test_refuses_localhost_and_non_isolated_hosts(url: str) -> None:
    with pytest.raises(pg_guard.PgGuardError) as exc:
        pg_guard.assert_isolated_database_url(url)
    # db.internal matches the prod-like pattern first; both codes are refusals.
    assert exc.value.reason_code in ("NON_ISOLATED_HOST", "PROD_LIKE_HOST")


# --------------------------------------------------- dbname adversarial
@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:p@pg_research:5432/clara",  # prod-shaped name
        "postgresql://u:p@pg_research:5432/postgres",
        "postgresql://u:p@pg_research:5432/clara_research_prod",
        "postgresql://u:p@pg_research:5432/",
    ],
)
def test_refuses_non_research_dbnames(url: str) -> None:
    with pytest.raises(pg_guard.PgGuardError) as exc:
        pg_guard.assert_isolated_database_url(url)
    assert exc.value.reason_code == "NON_RESEARCH_DBNAME"


# --------------------------------------------------- unparseable adversarial
@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        "not a url",
        "postgresclara_research",
    ],
)
def test_refuses_unparseable(url: str) -> None:
    with pytest.raises(pg_guard.PgGuardError) as exc:
        pg_guard.assert_isolated_database_url(url)
    assert exc.value.reason_code == "UNPARSEABLE_URL"


def test_non_string_refused_not_crash() -> None:
    ok, reason = pg_guard.check_database_url(None)  # type: ignore[arg-type]
    assert ok is False and reason == "UNPARSEABLE_URL"


def test_error_is_stable_and_typed() -> None:
    try:
        pg_guard.assert_isolated_database_url("sqlite:////tmp/x.db")
    except pg_guard.PgGuardError as exc:
        assert exc.reason_code == "NON_POSTGRES_SCHEME"
        assert "NON_POSTGRES_SCHEME" in str(exc)
    else:
        pytest.fail("PgGuardError not raised")


def test_valid_url_regression_isolated_host_constant() -> None:
    # Contract constants must stay aligned with docker-compose.pg.yaml.
    assert pg_guard.ISOLATED_HOST == "pg_research"
    assert pg_guard.ISOLATED_DBNAME == "clara_research"
    assert pg_guard.COMPOSE_PROJECT == "clara-research-pg"
