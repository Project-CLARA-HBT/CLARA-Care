"""CLARA-Care 2027 shared task SH-postgres_isolation: fail-closed DATABASE_URL guard.

Purpose
-------
Every research tool that touches PostgreSQL must connect to the disposable,
docker-compose-isolated research cluster (``infra/research/venue2027/docker-compose.pg.yaml``)
and never to a production, staging, or arbitrary developer-local database.
This module is the single fail-closed authority for that decision. It refuses:

* non-postgres connection schemes (sqlite, mysql, mongodb, plain ``//`` URLs);
* hosts that look like production, staging, or shared infrastructure
  (``prod*``, ``staging*``, ``clara*``, ``db.*``);
* non-research database names (the cluster provisions exactly one DB,
  ``clara_research``);
* research clusters that are *not* running on the dedicated internal docker
  network — i.e. a "localhost non-isolated" database is refused even if the
  name matches, because a research process running on the host (or in another
  compose network namespace) cannot be considered isolated.

Allowed input
-------------
A single PostgreSQL connection string (libpq URL form). Both ``postgresql://``
and ``postgres://`` schemes are accepted.

Failure semantics
-----------------
``assert_isolated_database_url(url)`` raises :class:`PgGuardError` carrying a
stable ``reason_code`` on every refusal. It never mutates the URL, never
retries, and never falls back to a permissive mode. ``check_database_url``
returns ``(ok, reason_code)`` for callers that prefer return codes over
exceptions. Unparseable input is refused with ``UNPARSEABLE_URL`` — a
malformed URL is never treated as a safe rejection target to guess at.

Isolation contract
------------------
The research compose file publishes **no host port**; the service is reachable
only from inside the dedicated compose network (project
``clara-research-pg``), by hostname ``pg_research``. Therefore any host other
than ``pg_research`` (including ``localhost``/``127.0.0.1``) cannot be the
isolated cluster as seen from a research process on the host or in another
namespace, and is refused with ``NON_ISOLATED_HOST``.

Version
-------
``PG_GUARD_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
from typing import Literal
from urllib.parse import urlsplit

PG_GUARD_VERSION = "1.0.0"

ReasonCode = Literal[
    "OK",
    "UNPARSEABLE_URL",
    "NON_POSTGRES_SCHEME",
    "PROD_LIKE_HOST",
    "NON_ISOLATED_HOST",
    "NON_RESEARCH_DBNAME",
]
"""Stable refusal reason codes.

``NON_ISOLATED_HOST`` covers the "localhost non-isolated DB" vector: the only
permitted host is the compose-network hostname ``pg_research`` (docker-network
internal DNS), because the research cluster publishes no host port by design.
"""

# Hostnames that look like shared/production infrastructure.
_PROD_LIKE_HOST_PARTS: frozenset[str] = frozenset(
    {
        "prod",
        "production",
        "staging",
        "stage",
        "clara",
        "clara-api",
        "clara-db",
        "clara-postgres",
        "db",
        "database",
    }
)

# The only host the isolated research cluster is reachable at.
ISOLATED_HOST = "pg_research"
# The only database name the isolated research cluster provisions.
ISOLATED_DBNAME = "clara_research"
# Docker-network alias of the research compose project.
COMPOSE_PROJECT = "clara-research-pg"


@dataclasses.dataclass(frozen=True)
class PgGuardError(Exception):
    """Raised/refused with a stable reason code; never guessed."""

    reason_code: ReasonCode
    message: str

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"{self.reason_code}: {self.message}"


def _parse(url: str) -> tuple[str, str]:
    """Return ``(host, dbname)`` or raise ``PgGuardError(UNPARSEABLE_URL)``.

    Uses the stdlib URL splitter (no I/O). Rejects empty/non-string input and
    URLs that yield neither a host nor a unix-socket path.
    """
    if not isinstance(url, str) or not url.strip():
        raise PgGuardError("UNPARSEABLE_URL", "DATABASE_URL must be a non-empty string")
    try:
        parts = urlsplit(url)
    except ValueError as exc:
        raise PgGuardError("UNPARSEABLE_URL", f"invalid URL syntax: {exc}") from exc
    if parts.scheme == "":
        # Allow the libpq keyword/value form? No: keep the guard fail-closed on
        # URL form only; keyword strings have no parseable scheme.
        raise PgGuardError(
            "UNPARSEABLE_URL", "URL has no scheme; postgresql:// scheme required"
        )
    host = (parts.hostname or "").lower()
    dbname = (parts.path or "").lstrip("/")
    if not host and not parts.path:
        raise PgGuardError("UNPARSEABLE_URL", "URL has neither host nor path")
    return host, dbname.split("?")[0]


def check_database_url(url: str) -> tuple[bool, ReasonCode]:
    """Fail-closed check. Returns ``(True, "OK")`` only for the isolated research DSN shape."""
    try:
        host, dbname = _parse(url)
    except PgGuardError as exc:
        return False, exc.reason_code

    scheme = urlsplit(url).scheme.lower()
    if scheme not in ("postgresql", "postgres"):
        return False, "NON_POSTGRES_SCHEME"

    if host.split(".")[0] in _PROD_LIKE_HOST_PARTS or (
        host.startswith(("prod", "staging", "clara"))
    ):
        return False, "PROD_LIKE_HOST"

    # localhost non-isolated DBs are refused: the isolated cluster has no host
    # port and is reachable only via the compose network hostname.
    if host != ISOLATED_HOST:
        return False, "NON_ISOLATED_HOST"

    # Extra defense in depth: an IPv6/bracketed or IP-shaped "pg_research"
    # cannot occur (hostname check above is exact), so only the exact name
    # remains; still verify the DB name is the research one.
    if dbname != ISOLATED_DBNAME:
        return False, "NON_RESEARCH_DBNAME"

    return True, "OK"


def assert_isolated_database_url(url: str) -> None:
    """Refuse anything that is not the isolated research DSN shape.

    Raises :class:`PgGuardError` with a stable reason code; returns ``None``
    on success. Callers must treat an exception as "do not connect", not as
    "retry with another URL".
    """
    ok, reason = check_database_url(url)
    if not ok:
        raise PgGuardError(reason, f"refused DATABASE_URL host/dbname (reason={reason})")
