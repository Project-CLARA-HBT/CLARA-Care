"""RxNorm REST connector — task 3.4.

API-only. Seeds drug *concepts* from the public RxNorm REST service (RxNav).
A :meth:`fetch` call resolves the window query (a drug name) to RxNorm concept
groups via ``/drugs.json`` and flattens every ``conceptProperties`` entry
(``rxcui``, ``name``, ``synonym``, ``tty``) into :class:`RawRecord` items.

RxNorm concept lookups are not time-windowed and return the full concept set in
one response, so this connector materializes that set once and serves it in
resumable offset-cursor pages (Requirement 6.5) by slicing the flattened list —
``decode_offset_cursor`` selects the slice start and ``next_offset_cursor``
signals exhaustion when a short page is returned. ``trust_tier`` provenance is
stamped by ``make_record`` (Requirement 6.4).

``doc_type`` is best-effort: every record is a drug concept, so it emits
``doc_type='drug_concept'`` (these rows seed the entity layer, not prose docs).
"""

from __future__ import annotations

from typing import Any

from .base import BaseSourceConnector, FetchWindow, RawRecord
from .registry import coerce_str, first_text, get_json

__all__ = ["RxNormConnector"]

_DEFAULT_BASE_URL = "https://rxnav.nlm.nih.gov/REST"
_RXNAV_SEARCH_URL = "https://mor.nlm.nih.gov/RxNav/search?searchBy=RXCUI&searchTerm={rxcui}"


class RxNormConnector(BaseSourceConnector):
    """Fetch RxNorm drug concepts with resumable offset paging over a concept set."""

    def fetch(
        self,
        window: FetchWindow,
        cursor: str | None = None,
    ) -> tuple[list[RawRecord], str | None]:
        config = self.context.config_json or {}
        term = coerce_str(window.query) or coerce_str(config.get("default_query"))
        if not term:
            return [], None

        base = (self.context.base_url or _DEFAULT_BASE_URL).rstrip("/")
        concepts = self._fetch_concepts(base, term)
        if not concepts:
            return [], None

        offset = self.decode_offset_cursor(cursor)
        page_size = self.resolve_page_size(window)
        page = concepts[offset : offset + page_size]
        if not page:
            return [], None

        records: list[RawRecord] = []
        for concept in page:
            built = self._build_record(concept)
            if built is not None:
                records.append(built)

        next_cursor = self.next_offset_cursor(
            offset=offset, page_size=page_size, fetched=len(page)
        )
        return records, next_cursor

    def _fetch_concepts(self, base: str, term: str) -> list[dict[str, Any]]:
        """Resolve a drug name to a flat, de-duplicated RxNorm concept list."""

        payload = get_json(self.http_client(), f"{base}/drugs.json", {"name": term})
        if not isinstance(payload, dict):
            return []
        drug_group = payload.get("drugGroup")
        if not isinstance(drug_group, dict):
            return []
        groups = drug_group.get("conceptGroup")
        if not isinstance(groups, list):
            return []

        concepts: list[dict[str, Any]] = []
        seen: set[str] = set()
        for group in groups:
            if not isinstance(group, dict):
                continue
            tty = coerce_str(group.get("tty"))
            properties = group.get("conceptProperties")
            if not isinstance(properties, list):
                continue
            for prop in properties:
                if not isinstance(prop, dict):
                    continue
                rxcui = first_text(prop.get("rxcui"))
                name = first_text(prop.get("name"))
                if not rxcui and not name:
                    continue
                key = (rxcui or name).lower()
                if key in seen:
                    continue
                seen.add(key)
                concepts.append(
                    {
                        "rxcui": rxcui,
                        "name": name,
                        "synonym": first_text(prop.get("synonym")),
                        "tty": first_text(prop.get("tty"), tty),
                    }
                )
        return concepts

    def _build_record(self, concept: dict[str, Any]) -> RawRecord | None:
        """Map one RxNorm concept into a :class:`RawRecord` (skip on failure)."""

        try:
            rxcui = coerce_str(concept.get("rxcui"))
            name = coerce_str(concept.get("name"))
            synonym = coerce_str(concept.get("synonym"))
            tty = coerce_str(concept.get("tty"))
            if not rxcui and not name:
                return None

            label = first_text(name, synonym, rxcui)
            parts = [
                name,
                f"synonym {synonym}" if synonym and synonym.lower() != name.lower() else "",
                f"RxCUI {rxcui}" if rxcui else "",
                f"term type {tty}" if tty else "",
            ]
            raw_text = ". ".join(part for part in parts if part) or label
            url = (
                _RXNAV_SEARCH_URL.format(rxcui=rxcui)
                if rxcui
                else "https://lhncbc.nlm.nih.gov/RxNav/APIs/index.html"
            )
            return self.make_record(
                external_id=rxcui or label,
                raw_text=raw_text,
                title=label,
                url=url,
                lang="en",
                doc_type="drug_concept",
                effective_date=None,
            )
        except Exception:
            return None
