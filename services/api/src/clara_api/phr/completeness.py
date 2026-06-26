"""USCDI-aligned completeness scorer with PII-free telemetry (Component N).

A pure, deterministic scorer over USCDI-aligned data classes →
``{score, present, missing}`` (Req 16.1). Adding data to a previously-missing
class strictly increases the score (Req 16.3, Correctness Property 19). The
telemetry projection emits only the numeric score and class *names* — never
values, names, codes, or free text (Req 16.4, Correctness Property 20).
"""

from __future__ import annotations

from typing import Any

# USCDI-aligned data classes scored for completeness. Equal-weighted.
COMPLETENESS_CLASSES: tuple[str, ...] = (
    "patient_demographics",
    "allergies",
    "medications",
    "problems",
    "immunizations",
    "procedures",
    "labs",
)


def _has_demographics(record: dict) -> bool:
    profile = record.get("profile") or {}
    return bool(
        str(profile.get("full_name") or "").strip()
        or profile.get("date_of_birth")
        or str(profile.get("blood_type") or "").strip()
    )


def _non_empty(record: dict, key: str) -> bool:
    value = record.get(key)
    return bool(isinstance(value, list) and len(value) > 0)


def _present_classes(record: dict) -> list[str]:
    present: list[str] = []
    if _has_demographics(record):
        present.append("patient_demographics")
    if _non_empty(record, "allergies"):
        present.append("allergies")
    if _non_empty(record, "medications"):
        present.append("medications")
    if _non_empty(record, "conditions"):
        present.append("problems")
    if _non_empty(record, "immunizations"):
        present.append("immunizations")
    if _non_empty(record, "procedures"):
        present.append("procedures")
    if _non_empty(record, "observations"):
        present.append("labs")
    return present


def score_completeness(record: dict) -> dict[str, Any]:
    """Compute ``{score, present, missing}`` for the PHR record (Req 16.1).

    ``score`` is the fraction of USCDI classes present, in ``[0, 1]``.
    """

    present = _present_classes(record)
    present_set = set(present)
    missing = [c for c in COMPLETENESS_CLASSES if c not in present_set]
    score = round(len(present) / len(COMPLETENESS_CLASSES), 4)
    return {"score": score, "present": present, "missing": missing}


def completeness_telemetry(record: dict) -> dict[str, Any]:
    """PII-free projection for telemetry (Req 16.4, Correctness Property 20).

    Emits only the numeric score and class-name lists — never values, names,
    codes, or free text.
    """

    result = score_completeness(record)
    return {
        "phr_completeness_score": result["score"],
        "present_class_count": len(result["present"]),
        "missing_class_count": len(result["missing"]),
        "present_classes": list(result["present"]),
        "missing_classes": list(result["missing"]),
    }
