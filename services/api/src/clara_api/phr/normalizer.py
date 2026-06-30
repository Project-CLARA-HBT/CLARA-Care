"""Structured + coded medication normalization (Component C, Req 3).

Reuses the careguard dictionary-normalization path
(``_resolve_dictionary_mapping_with_source`` → ``VnDrugMapping`` / alias /
``DRUG_RXCUI_MAP``) so the PHR and CareGuard share one normalization code path.
Exposed as a thin importable service that returns a normalized projection plus
the supported dose-unit set and a same-RXCUI duplicate flag for reconciliation.

This module imports the careguard resolver lazily inside the function to avoid a
circular import at module load (careguard imports many API-layer symbols).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

# Supported dose units (Req 3.5). Anything outside this set is rejected by the
# validator with a descriptive error naming the offending unit.
SUPPORTED_DOSE_UNITS: frozenset[str] = frozenset(
    {"mg", "g", "mcg", "ml", "iu", "%", "tablet", "capsule", "drop", "puff", "unit"}
)


@dataclass(frozen=True)
class NormalizedMedication:
    """Result of normalizing a medication name (Req 3.2, 3.3)."""

    display_name: str
    normalized_name: str
    rx_cui: str
    normalization_source: str  # db | candidate | fallback
    confidence: float
    is_normalized: bool


def normalize_medication_name(name: str, db: Session | None = None) -> NormalizedMedication:
    """Resolve a medication name to ``(display, normalized, rx_cui, source, …)``.

    When the name resolves through the ``VnDrugMapping``/alias path to a non-empty
    RXCUI, ``is_normalized`` is ``True``; otherwise ``rx_cui`` is ``""`` and
    ``is_normalized`` is ``False`` (Req 3.2, 3.3, Correctness Property 2).
    """

    # Lazy import keeps this module free of the API-layer import cycle.
    from clara_api.api.v1.endpoints.careguard import (
        _resolve_dictionary_mapping_with_source,
    )

    display_name, normalized_name, rx_cui, source, confidence = (
        _resolve_dictionary_mapping_with_source(name, db=db)
    )
    rx_cui = (rx_cui or "").strip()
    return NormalizedMedication(
        display_name=display_name,
        normalized_name=normalized_name,
        rx_cui=rx_cui,
        normalization_source=source,
        confidence=confidence,
        is_normalized=bool(rx_cui),
    )


def flag_duplicate_medications(medications: list[dict]) -> list[dict]:
    """Flag medications sharing a non-empty RXCUI as duplicates (Req 3.4, 15.4).

    The first occurrence of each RXCUI is treated as canonical; subsequent items
    with the same RXCUI get ``duplicate_of`` set to the canonical entry id. Items
    with an empty RXCUI are never flagged by this rule. The input is not mutated;
    a new list of (shallow-copied) dicts is returned (Correctness Property 3).
    """

    canonical_by_rxcui: dict[str, str] = {}
    out: list[dict] = []
    for item in medications:
        new_item = dict(item)
        rx_cui = str(new_item.get("rx_cui") or "").strip()
        if rx_cui:
            canonical = canonical_by_rxcui.get(rx_cui)
            if canonical is None:
                canonical_by_rxcui[rx_cui] = str(new_item.get("id") or "")
                new_item["duplicate_of"] = None
            else:
                new_item["duplicate_of"] = canonical
        else:
            new_item["duplicate_of"] = new_item.get("duplicate_of")
        out.append(new_item)
    return out
