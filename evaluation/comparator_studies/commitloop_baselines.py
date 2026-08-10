"""Frozen, non-GLHS adapters for simple CommitLoop baseline contexts."""

from __future__ import annotations

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
