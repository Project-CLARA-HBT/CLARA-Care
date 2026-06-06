"""PubMed connector over NCBI E-utilities (``esearch`` + ``esummary``) — task 3.4.

API-only (no HTML scraping). One :meth:`fetch` call runs ``esearch.fcgi`` to
page PMIDs for the window's query (with an optional ``mindate``/``maxdate``
publication-date filter derived from the fetch window), then ``esummary.fcgi``
to hydrate each PMID into a :class:`RawRecord`. Paging is resumable via the
base offset-cursor helpers (``retstart``/``retmax`` map directly onto the
``decode_offset_cursor``/``next_offset_cursor`` math), satisfying Requirement
6.5; provenance (``trust_tier``) is stamped by ``make_record`` (Requirement
6.4).

The NCBI API key is optional but, when configured, is attached to every request
(raising the per-IP rate limit from 3 to 10 req/s). It is resolved, in order,
from the connector's ``config_json`` (``ncbi_api_key``/``api_key``), then the ML
:mod:`clara_ml.config` settings (``ncbi_api_key`` — the same key wired in
``services/api``, env ``NCBI_API_KEY``), then the ``NCBI_API_KEY`` environment
variable directly. When unset, requests are sent anonymously.
"""

from __future__ import annotations

import os
from typing import Any

from clara_ml.config import settings

from .base import BaseSourceConnector, ConnectorContext, FetchWindow, RawRecord
from .registry import coerce_iso_date, coerce_str, first_text, get_json

__all__ = ["PubMedEutilsConnector"]

_DEFAULT_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_PUBMED_ARTICLE_URL = "https://pubmed.ncbi.nlm.nih.gov/{pmid}/"


def resolve_ncbi_api_key(context: ConnectorContext) -> str:
    """Resolve the NCBI E-utilities API key (see module docstring for order)."""

    config = context.config_json or {}
    for key in ("ncbi_api_key", "api_key"):
        candidate = coerce_str(config.get(key))
        if candidate:
            return candidate
    settings_value = coerce_str(getattr(settings, "ncbi_api_key", ""))
    if settings_value:
        return settings_value
    return coerce_str(os.environ.get("NCBI_API_KEY", ""))


def _to_ncbi_date(value: str | None) -> str:
    """Convert an ISO ``YYYY-MM-DD`` (or ``YYYY``) bound to NCBI ``YYYY/MM/DD``."""

    iso = coerce_iso_date(value)
    return iso.replace("-", "/") if iso else ""


def _pubmed_doc_type(pubtypes: Any) -> str:
    """Map E-utilities ``pubtype`` entries to a best-effort ``doc_type``."""

    if isinstance(pubtypes, (list, tuple)):
        lowered = [coerce_str(item).lower() for item in pubtypes]
    else:
        lowered = [coerce_str(pubtypes).lower()]
    if any("randomized controlled trial" in item for item in lowered):
        return "rct"
    if any("review" in item for item in lowered):
        return "review"
    return ""


class PubMedEutilsConnector(BaseSourceConnector):
    """Fetch PubMed records via NCBI E-utilities with resumable offset paging."""

    def fetch(
        self,
        window: FetchWindow,
        cursor: str | None = None,
    ) -> tuple[list[RawRecord], str | None]:
        term = coerce_str(window.query) or coerce_str(
            (self.context.config_json or {}).get("default_query")
        )
        if not term:
            return [], None

        offset = self.decode_offset_cursor(cursor)
        page_size = self.resolve_page_size(window)
        base = (self.context.base_url or _DEFAULT_BASE_URL).rstrip("/")
        api_key = resolve_ncbi_api_key(self.context)

        client = self.http_client()
        id_list = self._esearch(client, base, term, window, offset, page_size, api_key)
        if not id_list:
            return [], None

        records = self._esummary(client, base, id_list, api_key)
        next_cursor = self.next_offset_cursor(
            offset=offset, page_size=page_size, fetched=len(id_list)
        )
        return records, next_cursor

    def _esearch(
        self,
        client: Any,
        base: str,
        term: str,
        window: FetchWindow,
        offset: int,
        page_size: int,
        api_key: str,
    ) -> list[str]:
        params: dict[str, Any] = {
            "db": "pubmed",
            "retmode": "json",
            "retmax": page_size,
            "retstart": offset,
            "sort": "relevance",
            "term": term,
        }
        mindate = _to_ncbi_date(window.since)
        maxdate = _to_ncbi_date(window.until)
        if mindate:
            params["mindate"] = mindate
        if maxdate:
            params["maxdate"] = maxdate
        if mindate or maxdate:
            params["datetype"] = "pdat"
        if api_key:
            params["api_key"] = api_key

        payload = get_json(client, f"{base}/esearch.fcgi", params)
        if not isinstance(payload, dict):
            return []
        result = payload.get("esearchresult")
        if not isinstance(result, dict):
            return []
        id_list = result.get("idlist")
        if not isinstance(id_list, list):
            return []
        return [coerce_str(pmid) for pmid in id_list if coerce_str(pmid)]

    def _esummary(
        self,
        client: Any,
        base: str,
        id_list: list[str],
        api_key: str,
    ) -> list[RawRecord]:
        params: dict[str, Any] = {
            "db": "pubmed",
            "retmode": "json",
            "id": ",".join(id_list),
        }
        if api_key:
            params["api_key"] = api_key

        payload = get_json(client, f"{base}/esummary.fcgi", params)
        if not isinstance(payload, dict):
            return []
        result = payload.get("result")
        if not isinstance(result, dict):
            return []

        records: list[RawRecord] = []
        for pmid in id_list:
            record = result.get(pmid)
            if not isinstance(record, dict):
                continue
            built = self._build_record(pmid, record)
            if built is not None:
                records.append(built)
        return records

    def _build_record(self, pmid: str, record: dict[str, Any]) -> RawRecord | None:
        """Map one ``esummary`` record to a :class:`RawRecord` (skip on failure)."""

        try:
            title = coerce_str(record.get("title"))
            if not title:
                return None
            journal = first_text(record.get("fulljournalname"), record.get("source"))
            pubdate = first_text(record.get("sortpubdate"), record.get("pubdate"))
            authors_raw = record.get("authors")
            authors = ""
            if isinstance(authors_raw, list):
                names = [coerce_str(a.get("name")) for a in authors_raw if isinstance(a, dict)]
                authors = ", ".join(name for name in names if name)
            parts = [title, authors, journal, pubdate]
            raw_text = ". ".join(part for part in parts if part)
            return self.make_record(
                external_id=pmid,
                raw_text=raw_text,
                title=title,
                url=_PUBMED_ARTICLE_URL.format(pmid=pmid),
                lang="en",
                doc_type=_pubmed_doc_type(record.get("pubtype")),
                effective_date=coerce_iso_date(pubdate),
            )
        except Exception:
            # Be resilient: never crash the page on a single malformed record.
            return None
