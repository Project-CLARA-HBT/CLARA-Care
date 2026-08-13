"""Frozen, non-GLHS adapters for simple CommitLoop baseline contexts."""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime
from typing import Any


def long_context(events: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(
        events,
        key=lambda item: (
            str(item.get("valid_at") or item.get("known_at") or ""),
            str(item.get("evidence_id", "")),
        ),
    )
    return {
        "representation": "chronological_long_context",
        "events": ordered,
        "narrative_boundaries": True,
        "governance_status": "UNSUPPORTED_BY_METHOD",
    }


def naive_rag(
    events: list[dict[str, Any]], *, system: str, code: str, limit: int = 5
) -> dict[str, Any]:
    if not 1 <= limit <= 20:
        raise ValueError("invalid_naive_rag_limit")
    target = [system, code]
    retrieved = [item for item in events if target in item.get("codes", [])][:limit]
    return {
        "representation": "frozen_exact_code_top5",
        "events": retrieved,
        "retrieval_query": {"system": system, "code": code},
        "governance_status": "UNSUPPORTED_BY_METHOD",
    }


def _terms(value: object) -> list[str]:
    """Tokenize only already-visible structured evidence fields."""

    return re.findall(r"[a-z0-9]+", str(value).lower())


def _event_terms(event: dict[str, Any]) -> list[str]:
    terms = _terms(event.get("resource_type", ""))
    terms.extend(_terms(event.get("status", "")))
    terms.extend(_terms(event.get("relation", "")))
    terms.extend(_terms(event.get("encounter_reference", "")))
    for pair in event.get("codes", []):
        if isinstance(pair, list) and len(pair) == 2:
            terms.extend(_terms(pair[0]))
            terms.extend(_terms(pair[1]))
    return terms


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def temporal_bm25(
    events: list[dict[str, Any]],
    *,
    query_terms: list[str],
    valid_cutoff: str,
    limit: int = 5,
) -> dict[str, Any]:
    """Rank visible evidence with BM25 plus a declared temporal tie-break.

    This intentionally contains no GLHS governance, state reconstruction, or
    oracle-derived lifecycle feature.  It is a deterministic retrieval
    baseline for a *future* protocol version, rather than a retroactive change
    to the frozen exact-code baseline used by V21/V22.
    """

    if not 1 <= limit <= 20:
        raise ValueError("invalid_temporal_bm25_limit")
    normalized_query = [term for value in query_terms for term in _terms(value)]
    if not normalized_query:
        raise ValueError("temporal_bm25_query_required")
    cutoff = _timestamp(valid_cutoff)
    if cutoff is None:
        raise ValueError("temporal_bm25_valid_cutoff_required")

    documents = [_event_terms(event) for event in events]
    document_count = len(documents)
    if document_count == 0:
        return {
            "representation": "temporal_bm25_top5_v1",
            "events": [],
            "retrieval_query_terms": normalized_query,
            "governance_status": "UNSUPPORTED_BY_METHOD",
        }
    average_length = sum(len(document) for document in documents) / document_count
    document_frequency = Counter(
        term for document in documents for term in set(document)
    )
    k1, b = 1.2, 0.75
    ranked: list[tuple[float, str, str, dict[str, Any]]] = []
    for event, document in zip(events, documents, strict=True):
        counts = Counter(document)
        lexical_score = 0.0
        for term in normalized_query:
            frequency = counts.get(term, 0)
            if not frequency:
                continue
            inverse_frequency = math.log(
                1 + (document_count - document_frequency[term] + 0.5)
                / (document_frequency[term] + 0.5)
            )
            lexical_score += inverse_frequency * (
                frequency * (k1 + 1)
                / (frequency + k1 * (1 - b + b * len(document) / average_length))
            )
        event_time = _timestamp(event.get("valid_at"))
        age_days = (
            max(0.0, (cutoff - event_time).total_seconds() / 86400.0)
            if event_time is not None
            else float("inf")
        )
        # A bounded temporal contribution cannot overcome a clear lexical
        # mismatch; it is only a transparent preference among relevant facts.
        temporal_score = 0.25 / (1.0 + age_days / 30.0)
        ranked.append(
            (
                lexical_score + temporal_score,
                str(event.get("valid_at") or ""),
                str(event.get("evidence_id") or ""),
                event,
            )
        )
    ranked.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    return {
        "representation": "temporal_bm25_top5_v1",
        "events": [item[3] for item in ranked[:limit]],
        "retrieval_query_terms": normalized_query,
        "ranking": {
            "lexical": "BM25(k1=1.2,b=0.75)",
            "temporal_tiebreak": "0.25/(1+age_days/30)",
            "valid_cutoff": valid_cutoff,
        },
        "governance_status": "UNSUPPORTED_BY_METHOD",
    }


def last_write_wins(events: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(
        events,
        key=lambda item: (
            str(item.get("valid_at") or item.get("known_at") or ""),
            str(item.get("evidence_id", "")),
        ),
    )
    latest: dict[tuple[str, tuple[tuple[str, str], ...]], dict[str, Any]] = {}
    for item in ordered:
        raw_codes = item.get("codes", [])
        codes = tuple(
            (str(pair[0]), str(pair[1]))
            for pair in raw_codes
            if isinstance(pair, list) and len(pair) == 2
        )
        latest[(str(item.get("resource_type", "")), codes)] = item
    retained = sorted(latest.values(), key=lambda item: str(item.get("evidence_id", "")))
    return {
        "representation": "last_write_per_resource_code",
        "events": retained,
        "discarded_versions": len(events) - len(retained),
        "governance_status": "UNSUPPORTED_BY_METHOD",
    }
