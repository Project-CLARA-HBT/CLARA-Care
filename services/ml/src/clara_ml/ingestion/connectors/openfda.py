"""openFDA drug connector (label / event) — task 3.4.

API-only. Reuses the openFDA access patterns from
:mod:`clara_ml.clients.drug_sources` (the existing CareGuard caller) but adapts
them to the ingestion contract: one :meth:`fetch` call queries an openFDA drug
endpoint (``label.json`` by default, ``event.json`` optionally) with
``search``/``limit``/``skip`` paging and maps each result into a
:class:`RawRecord`. openFDA's ``skip``/``limit`` map cleanly onto the base
offset-cursor helpers, so paging is resumable (Requirement 6.5); ``trust_tier``
provenance is stamped by ``make_record`` (Requirement 6.4).

Drug **labels** are SPL documents, so they emit ``doc_type='spl_label'``. An
optional openFDA API key (``config_json['api_key']``) is attached when present.
"""

from __future__ import annotations

from typing import Any

from .base import BaseSourceConnector, FetchWindow, RawRecord
from .registry import coerce_iso_date, coerce_str, first_text, get_json

__all__ = ["OpenFdaConnector"]

_DEFAULT_BASE_URL = "https://api.fda.gov/drug"
# openFDA caps skip + limit at 26000 and limit at 1000 for the basic endpoints.
_MAX_SKIP = 26000


def _build_label_search(window: FetchWindow, config: dict[str, Any]) -> str:
    """Build the openFDA ``search`` expression for a label query.

    Prefers an explicit ``config_json['search']`` override; otherwise turns the
    window query (a drug name) into a generic/brand-name OR clause, mirroring
    :mod:`clara_ml.clients.drug_sources`.
    """

    override = coerce_str(config.get("search"))
    if override:
        return override
    term = coerce_str(window.query) or coerce_str(config.get("default_query"))
    if not term:
        return ""
    return f'openfda.generic_name:"{term}" OR openfda.brand_name:"{term}"'


class OpenFdaConnector(BaseSourceConnector):
    """Fetch openFDA drug records with resumable ``skip``/``limit`` paging."""

    def fetch(
        self,
        window: FetchWindow,
        cursor: str | None = None,
    ) -> tuple[list[RawRecord], str | None]:
        config = self.context.config_json or {}
        endpoint = coerce_str(config.get("endpoint")).lower() or "label"
        search_expr = _build_label_search(window, config)
        if not search_expr:
            return [], None

        offset = self.decode_offset_cursor(cursor)
        page_size = self.resolve_page_size(window)
        if offset >= _MAX_SKIP:
            # openFDA refuses skip beyond its window; stop cleanly.
            return [], None

        base = (self.context.base_url or _DEFAULT_BASE_URL).rstrip("/")
        params: dict[str, Any] = {
            "search": search_expr,
            "limit": page_size,
            "skip": offset,
        }
        api_key = coerce_str(config.get("api_key"))
        if api_key:
            params["api_key"] = api_key

        payload = get_json(self.http_client(), f"{base}/{endpoint}.json", params)
        if not isinstance(payload, dict):
            return [], None
        results = payload.get("results")
        if not isinstance(results, list) or not results:
            return [], None

        doc_type = "spl_label" if endpoint == "label" else coerce_str(config.get("doc_type"))
        records: list[RawRecord] = []
        for idx, item in enumerate(results):
            built = self._build_record(item, idx + offset, doc_type)
            if built is not None:
                records.append(built)

        next_cursor = self.next_offset_cursor(
            offset=offset, page_size=page_size, fetched=len(results)
        )
        return records, next_cursor

    def _build_record(
        self,
        item: Any,
        index: int,
        doc_type: str,
    ) -> RawRecord | None:
        """Map one openFDA result into a :class:`RawRecord` (skip on failure)."""

        if not isinstance(item, dict):
            return None
        try:
            openfda_raw = item.get("openfda")
            openfda: dict[str, Any] = openfda_raw if isinstance(openfda_raw, dict) else {}
            generic = first_text(openfda.get("generic_name"))
            brand = first_text(openfda.get("brand_name"))
            set_id = first_text(item.get("set_id"), item.get("id"))
            external_id = set_id or f"openfda-{index + 1}"

            usage = first_text(
                item.get("indications_and_usage"),
                item.get("purpose"),
                item.get("description"),
            )
            interactions = first_text(item.get("drug_interactions"))
            label = first_text(generic, brand, external_id)
            parts = [label, usage, interactions]
            raw_text = ". ".join(part for part in parts if part) or label

            effective_date = coerce_iso_date(
                first_text(item.get("effective_time"), openfda.get("effective_time"))
            )
            url = (
                f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={set_id}"
                if set_id
                else "https://open.fda.gov/apis/drug/label/"
            )
            return self.make_record(
                external_id=external_id,
                raw_text=raw_text,
                title=label,
                url=url,
                lang="en",
                doc_type=doc_type,
                effective_date=effective_date,
            )
        except Exception:
            return None
