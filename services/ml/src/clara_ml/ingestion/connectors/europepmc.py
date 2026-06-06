"""Europe PMC REST search connector — task 3.4.

API-only. Queries the Europe PMC REST search endpoint
(``/europepmc/webservices/rest/search``) and maps each result into a
:class:`RawRecord`. Europe PMC pages with a 1-based ``page`` + ``pageSize``;
this connector converts the opaque base offset cursor into that page number so
paging is resumable through the standard ``decode_offset_cursor`` /
``next_offset_cursor`` helpers (Requirement 6.5). (Europe PMC also offers a
``cursorMark`` for very deep paging; offset/page is used here to stay aligned
with the shared cursor contract.)

``doc_type`` is best-effort from each result's ``pubTypeList``
(``'rct'``/``'review'``), and ``lang='en'``. ``trust_tier`` provenance is
stamped by ``make_record`` (Requirement 6.4).
"""

from __future__ import annotations

from typing import Any

from .base import BaseSourceConnector, FetchWindow, RawRecord
from .registry import coerce_iso_date, coerce_str, first_text, get_json

__all__ = ["EuropePmcConnector"]

_DEFAULT_BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"
_PUBMED_ARTICLE_URL = "https://pubmed.ncbi.nlm.nih.gov/{source_id}/"
_EUROPEPMC_ARTICLE_URL = "https://europepmc.org/article/{source}/{source_id}"


def _europepmc_doc_type(item: dict[str, Any]) -> str:
    """Map a Europe PMC ``pubTypeList`` to a best-effort ``doc_type``."""

    pub_type_list = item.get("pubTypeList")
    types: list[str] = []
    if isinstance(pub_type_list, dict):
        raw = pub_type_list.get("pubType")
        if isinstance(raw, list):
            types = [coerce_str(t).lower() for t in raw]
        else:
            types = [coerce_str(raw).lower()]
    if any("randomized controlled trial" in t for t in types):
        return "rct"
    if any("review" in t for t in types):
        return "review"
    return ""


class EuropePmcConnector(BaseSourceConnector):
    """Fetch Europe PMC search results with resumable page/offset paging."""

    def fetch(
        self,
        window: FetchWindow,
        cursor: str | None = None,
    ) -> tuple[list[RawRecord], str | None]:
        config = self.context.config_json or {}
        query = coerce_str(window.query) or coerce_str(config.get("default_query"))
        if not query:
            return [], None

        offset = self.decode_offset_cursor(cursor)
        page_size = self.resolve_page_size(window)
        # Europe PMC uses a 1-based page index; derive it from the offset cursor.
        page = offset // page_size + 1

        base = (self.context.base_url or _DEFAULT_BASE_URL).rstrip("/")
        params: dict[str, Any] = {
            "query": query,
            "format": "json",
            "pageSize": page_size,
            "page": page,
            "resultType": "core",
        }

        payload = get_json(self.http_client(), f"{base}/search", params)
        results = self._extract_results(payload)
        if not results:
            return [], None

        records: list[RawRecord] = []
        for item in results:
            built = self._build_record(item)
            if built is not None:
                records.append(built)

        next_cursor = self.next_offset_cursor(
            offset=offset, page_size=page_size, fetched=len(results)
        )
        return records, next_cursor

    @staticmethod
    def _extract_results(payload: Any) -> list[Any]:
        """Pull the result list out of a Europe PMC search response."""

        if not isinstance(payload, dict):
            return []
        result_list = payload.get("resultList")
        if not isinstance(result_list, dict):
            return []
        results = result_list.get("result")
        return results if isinstance(results, list) else []

    def _build_record(self, item: Any) -> RawRecord | None:
        """Map one Europe PMC result into a :class:`RawRecord` (skip on failure)."""

        if not isinstance(item, dict):
            return None
        try:
            source = coerce_str(item.get("source")).lower() or "europepmc"
            source_id = first_text(item.get("id"), item.get("pmid"))
            title = first_text(item.get("title"))
            if not source_id or not title:
                return None

            journal = first_text(item.get("journalTitle"))
            abstract = first_text(item.get("abstractText"))
            pub_date = first_text(item.get("firstPublicationDate"), item.get("pubYear"))
            parts = [title, journal, abstract, pub_date]
            raw_text = ". ".join(part for part in parts if part)

            if source == "med":
                url = _PUBMED_ARTICLE_URL.format(source_id=source_id)
            else:
                url = _EUROPEPMC_ARTICLE_URL.format(source=source.upper(), source_id=source_id)

            return self.make_record(
                external_id=f"{source.upper()}:{source_id}",
                raw_text=raw_text,
                title=title,
                url=url,
                lang="en",
                doc_type=_europepmc_doc_type(item),
                effective_date=coerce_iso_date(pub_date),
            )
        except Exception:
            return None
