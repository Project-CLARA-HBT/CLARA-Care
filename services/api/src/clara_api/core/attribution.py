from __future__ import annotations

import re
from typing import Any


def normalize_citations(citations_payload: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not isinstance(citations_payload, list):
        return rows

    for idx, item in enumerate(citations_payload, start=1):
        if isinstance(item, str):
            source = item.strip()
            if source:
                rows.append({"source": source})
            continue

        if not isinstance(item, dict):
            continue

        raw_source = item.get("source") or item.get("title") or item.get("id")
        source = str(raw_source).strip() if raw_source is not None else ""
        if not source:
            source = f"reference-{idx}"
        citation: dict[str, str] = {"source": source}

        raw_url = item.get("url") or item.get("link")
        if raw_url is not None:
            url = str(raw_url).strip()
            if url:
                citation["url"] = url

        rows.append(citation)
    return rows


def normalize_source_used(raw_source_used: Any) -> list[str]:
    if isinstance(raw_source_used, str):
        chunks = re.split(r"[,;\n]+", raw_source_used)
        normalized_values: list[str] = []
        for chunk in chunks:
            normalized = chunk.strip().lower()
            if normalized and normalized not in normalized_values:
                normalized_values.append(normalized)
        return normalized_values
    if not isinstance(raw_source_used, list):
        return []

    source_used: list[str] = []
    for item in raw_source_used:
        if not isinstance(item, str):
            continue
        normalized = item.strip().lower()
        if normalized and normalized not in source_used:
            source_used.append(normalized)
    return source_used


def normalize_source_errors(raw_source_errors: Any) -> dict[str, list[str]]:
    if not isinstance(raw_source_errors, dict):
        return {}

    source_errors: dict[str, list[str]] = {}
    for source_name, values in raw_source_errors.items():
        source_key = str(source_name).strip().lower()
        if not source_key:
            continue
        if isinstance(values, list):
            normalized_values = [str(value).strip() for value in values if str(value).strip()]
        elif values is None:
            normalized_values = []
        else:
            normalized_values = [str(values).strip()] if str(values).strip() else []
        source_errors[source_key] = normalized_values
    return source_errors


def normalize_sources(sources_payload: Any) -> list[dict[str, str]]:
    if not isinstance(sources_payload, list):
        return []

    normalized_sources: list[dict[str, str]] = []
    seen: set[str] = set()

    for index, source in enumerate(sources_payload, start=1):
        if isinstance(source, str):
            source_id = source.strip().lower()
            source_name = source.strip()
            category = None
            source_type = None
        elif isinstance(source, dict):
            raw_id = source.get("id")
            source_id = str(raw_id).strip().lower() if raw_id is not None else ""
            raw_name = source.get("name")
            source_name = str(raw_name).strip() if raw_name is not None else ""
            raw_category = source.get("category")
            category = str(raw_category).strip() if raw_category is not None else ""
            raw_type = source.get("type")
            source_type = str(raw_type).strip() if raw_type is not None else ""
        else:
            continue

        if not source_id and source_name:
            source_id = source_name.lower().replace(" ", "_")
        if not source_id:
            source_id = f"source_{index}"
        if not source_name:
            source_name = source_id.replace("_", " ").title()

        if source_id in seen:
            continue
        seen.add(source_id)

        item: dict[str, str] = {"id": source_id, "name": source_name}
        if category:
            item["category"] = category
        if source_type:
            item["type"] = source_type
        normalized_sources.append(item)

    return normalized_sources


def build_attribution(
    *,
    channel: str,
    mode: str | None = None,
    sources: Any = None,
    citations_payload: Any = None,
    source_used: Any = None,
    source_errors: Any = None,
    fallback_used: bool | None = None,
) -> dict[str, Any]:
    normalized_sources = normalize_sources(sources)
    citations = normalize_citations(citations_payload)
    normalized_source_used = normalize_source_used(source_used)
    normalized_source_errors = normalize_source_errors(source_errors)

    attribution: dict[str, Any] = {
        "channel": channel,
        "mode": mode,
        "source_count": len(normalized_sources),
        "citation_count": len(citations),
        "sources": normalized_sources,
        "citations": citations,
        "source_used": normalized_source_used,
        "source_errors": normalized_source_errors,
    }
    if fallback_used is not None:
        attribution["fallback_used"] = bool(fallback_used)
    return attribution


def attach_attribution(
    payload: dict[str, Any],
    *,
    attribution: dict[str, Any],
) -> dict[str, Any]:
    response = dict(payload)
    response["attribution"] = attribution
    response["attributions"] = [attribution]
    response["citations"] = attribution.get("citations", [])
    return response
