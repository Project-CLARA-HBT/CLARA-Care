"""Shared helpers and a small connector factory/registry (task 3.4 support).

This module hosts the tiny, network-free utilities the API-first connectors
(``pubmed_eutils``/``openfda``/``dailymed_spl``/``rxnorm``/``europepmc``) all
need — a defensive JSON ``GET`` wrapper, string/date coercion, and a
``source_key`` → connector-class factory the orchestrator (task 3.16) can use
to build a connector from a ``kb_source_registry`` row.

Design constraints honoured here:

* **Import-safe / no network at import.** Importing this module opens no socket
  and constructs no HTTP client. The connector classes are imported *lazily*
  inside :func:`connector_classes` / :func:`build_connector`, so this module
  has no import-time dependency on the connectors (and the connectors can
  freely import these helpers without a circular import).
* **Resilient parsing.** :func:`get_json` treats a configured set of "soft"
  HTTP statuses (``404`` by default) and any JSON-decode failure as an empty
  result (``None``) rather than an exception, while genuine transport / 5xx
  errors propagate so the orchestrator can record a failure (Requirement 6.1).
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids runtime import cycle
    import httpx

    from .base import BaseSourceConnector, ConnectorContext

__all__ = [
    "get_json",
    "coerce_str",
    "first_text",
    "coerce_iso_date",
    "connector_classes",
    "build_connector",
]


# ---------------------------------------------------------------------------
# HTTP / parsing helpers
# ---------------------------------------------------------------------------


def get_json(
    client: httpx.Client,
    url: str,
    params: dict[str, Any] | None = None,
    *,
    soft_statuses: tuple[int, ...] = (400, 404),
) -> Any | None:
    """``GET`` ``url`` and return parsed JSON, or ``None`` on a soft failure.

    ``soft_statuses`` (e.g. a not-found / bad-query) and any JSON-decode error
    return ``None`` so a connector treats them as "no records this page". Other
    HTTP status errors and transport errors raise (``response.raise_for_status``
    / ``httpx`` exceptions) so the orchestrator can record the failure cleanly
    rather than silently treating the source as exhausted.
    """

    response = client.get(url, params=params or {})
    if response.status_code in soft_statuses:
        return None
    response.raise_for_status()
    try:
        return response.json()
    except (ValueError, json.JSONDecodeError):
        return None


def coerce_str(value: Any) -> str:
    """Coerce ``value`` to a trimmed string, taking the first item of a list.

    Returns ``""`` for ``None``/empty so callers can compose ``raw_text`` from
    heterogeneous API fields without ``None`` leaking into the output.
    """

    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return coerce_str(value[0]) if value else ""
    return str(value).strip()


def first_text(*values: Any) -> str:
    """Return the first non-empty :func:`coerce_str` result among ``values``."""

    for value in values:
        text = coerce_str(value)
        if text:
            return text
    return ""


_YEAR_RE = re.compile(r"(19|20)\d{2}")
_ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_SLASH_RE = re.compile(r"\b(\d{4})/(\d{2})/(\d{2})\b")
_COMPACT_RE = re.compile(r"\b(\d{4})(\d{2})(\d{2})\b")


def _valid_ymd(year: str, month: str, day: str) -> str | None:
    """Return ``YYYY-MM-DD`` when month/day are in range, else ``None``."""

    if 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
        return f"{year}-{month}-{day}"
    return None


def coerce_iso_date(value: Any) -> str | None:
    """Best-effort parse of a publication date into an ISO ``YYYY-MM-DD`` string.

    Handles the common shapes these APIs emit — ``"2020-01-05"``,
    ``"2020/01/05 12:00"`` (PubMed ``sortpubdate``), ``"20200105"`` (openFDA
    ``effective_time``), ``"2020 Jan"`` and bare ``"2020"`` — and falls back to
    ``YYYY-01-01`` when only a year is present. Returns ``None`` when no
    plausible year can be found (kept as an optional recency signal at this
    stage, normalized to a real ``date`` only on persist).
    """

    text = coerce_str(value)
    if not text:
        return None
    iso = _ISO_RE.search(text)
    if iso:
        return f"{iso.group(1)}-{iso.group(2)}-{iso.group(3)}"
    slash = _SLASH_RE.search(text)
    if slash:
        return f"{slash.group(1)}-{slash.group(2)}-{slash.group(3)}"
    compact = _COMPACT_RE.search(text)
    if compact:
        ymd = _valid_ymd(compact.group(1), compact.group(2), compact.group(3))
        if ymd:
            return ymd
    year = _YEAR_RE.search(text)
    if year:
        return f"{year.group(0)}-01-01"
    return None


# ---------------------------------------------------------------------------
# Connector factory / registry (lazy import to avoid an import cycle)
# ---------------------------------------------------------------------------


def connector_classes() -> dict[str, type[BaseSourceConnector]]:
    """Return the ``source_key`` → connector-class map (imported lazily).

    The imports live inside the function so importing :mod:`registry` never
    imports the connector modules at module load — keeping both this module and
    the connectors import-safe and free of circular imports.
    """

    from .dailymed_spl import DailyMedSplConnector
    from .europepmc import EuropePmcConnector
    from .openfda import OpenFdaConnector
    from .pubmed_eutils import PubMedEutilsConnector
    from .rxnorm import RxNormConnector
    from .vn_crawl import VnCrawlConnector

    return {
        "pubmed": PubMedEutilsConnector,
        "openfda": OpenFdaConnector,
        "dailymed": DailyMedSplConnector,
        "rxnorm": RxNormConnector,
        "europepmc": EuropePmcConnector,
        "vn_crawl": VnCrawlConnector,
    }


def build_connector(
    source_key: str,
    context: ConnectorContext,
    **kwargs: Any,
) -> BaseSourceConnector:
    """Construct the connector registered for ``source_key``.

    Raises :class:`KeyError` for an unknown source key. Extra ``kwargs`` (e.g.
    an injected ``http_client_factory`` for tests) flow through to the
    connector constructor.
    """

    classes = connector_classes()
    key = (source_key or "").strip().lower()
    try:
        connector_cls = classes[key]
    except KeyError as exc:
        known = ", ".join(sorted(classes)) or "<none>"
        raise KeyError(
            f"no API connector registered for source_key {source_key!r} (known: {known})"
        ) from exc
    return connector_cls(context, **kwargs)
