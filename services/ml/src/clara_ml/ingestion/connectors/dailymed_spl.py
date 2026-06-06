"""DailyMed SPL connector — task 3.4.

API-only. Uses DailyMed's public SPL web service (``/services/v2/spls.json``),
optionally filtered by ``drug_name`` (the fetch window's query). DailyMed pages
results with a 1-based ``page`` + ``pagesize``; this connector converts the
opaque base offset cursor into that page number so paging stays resumable
through the standard ``decode_offset_cursor``/``next_offset_cursor`` helpers
(Requirement 6.5).

Each SPL row's **setid** is captured as the :class:`RawRecord` ``external_id``
(the stable DailyMed document identity), and records emit ``doc_type='spl_label'``.
``trust_tier`` provenance is stamped by ``make_record`` (Requirement 6.4).
"""

from __future__ import annotations

from typing import Any

from .base import BaseSourceConnector, FetchWindow, RawRecord
from .registry import coerce_iso_date, coerce_str, first_text, get_json

__all__ = ["DailyMedSplConnector"]

_DEFAULT_BASE_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v2"
_DRUG_INFO_URL = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}"


class DailyMedSplConnector(BaseSourceConnector):
    """Fetch DailyMed SPL labels with resumable page/offset paging."""

    def fetch(
        self,
        window: FetchWindow,
        cursor: str | None = None,
    ) -> tuple[list[RawRecord], str | None]:
        config = self.context.config_json or {}
        offset = self.decode_offset_cursor(cursor)
        page_size = self.resolve_page_size(window)
        # Convert the opaque offset cursor into DailyMed's 1-based page number.
        page = offset // page_size + 1

        base = (self.context.base_url or _DEFAULT_BASE_URL).rstrip("/")
        params: dict[str, Any] = {
            "pagesize": page_size,
            "page": page,
        }
        drug_name = coerce_str(window.query) or coerce_str(config.get("default_query"))
        if drug_name:
            params["drug_name"] = drug_name

        payload = get_json(self.http_client(), f"{base}/spls.json", params)
        rows = self._extract_rows(payload)
        if not rows:
            return [], None

        records: list[RawRecord] = []
        for row in rows:
            built = self._build_record(row)
            if built is not None:
                records.append(built)

        next_cursor = self.next_offset_cursor(
            offset=offset, page_size=page_size, fetched=len(rows)
        )
        return records, next_cursor

    @staticmethod
    def _extract_rows(payload: Any) -> list[Any]:
        """Pull the SPL row list out of a DailyMed v2 response shape."""

        if not isinstance(payload, dict):
            return []
        rows = payload.get("data")
        if isinstance(rows, list):
            return rows
        # Some legacy responses uppercase the key.
        rows = payload.get("DATA")
        return rows if isinstance(rows, list) else []

    def _build_record(self, row: Any) -> RawRecord | None:
        """Map one SPL row into a :class:`RawRecord` (skip on failure)."""

        try:
            if isinstance(row, dict):
                set_id = first_text(row.get("setid"), row.get("set_id"))
                title = first_text(row.get("title"))
                version = first_text(row.get("spl_version"), row.get("version"))
                published = first_text(row.get("published_date"), row.get("published"))
            elif isinstance(row, (list, tuple)):
                # Legacy positional shape: [setid, title, version, published].
                set_id = coerce_str(row[0]) if len(row) > 0 else ""
                title = coerce_str(row[1]) if len(row) > 1 else ""
                version = coerce_str(row[2]) if len(row) > 2 else ""
                published = coerce_str(row[3]) if len(row) > 3 else ""
            else:
                return None

            if not set_id and not title:
                return None
            label = first_text(title, set_id)
            parts = [label, f"SPL version {version}" if version else "", published]
            raw_text = ". ".join(part for part in parts if part) or label
            url = _DRUG_INFO_URL.format(setid=set_id) if set_id else "https://dailymed.nlm.nih.gov/"
            return self.make_record(
                external_id=set_id or label,
                raw_text=raw_text,
                title=label,
                url=url,
                lang="en",
                doc_type="spl_label",
                effective_date=coerce_iso_date(published),
            )
        except Exception:
            return None
