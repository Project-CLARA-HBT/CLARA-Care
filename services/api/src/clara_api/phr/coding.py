"""Seeded coding lookups for allergies (substance) and conditions (ICD-10/SNOMED).

These are deliberately small, deterministic, in-process lookups (Component D).
Coding is *offered* when a name matches a known entry; acceptance never blocks on
coding — an unmatched name is retained as free text and marked uncoded (Req 4.2,
4.4, 5.2, 5.3, Correctness Property 4). The maps mirror the spirit of the
careguard ``DRUG_RXCUI_MAP`` seed: a curated starter set, extensible later via a
DB-backed table without changing the call sites.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


# Allergy substance → coded substance id (RxNorm-style ingredient code). Keys are
# normalized substance/name tokens.
ALLERGY_SUBSTANCE_CODES: dict[str, str] = {
    "penicillin": "7980",
    "amoxicillin": "723",
    "aspirin": "1191",
    "ibuprofen": "5640",
    "sulfa": "10180",
    "sulfonamide": "10180",
    "peanut": "C0559470",
    "lactose": "6218",
    "latex": "C0023194",
    "paracetamol": "161",
    "acetaminophen": "161",
    "cephalosporin": "C0007713",
    "codeine": "2670",
    "morphine": "7052",
}


@dataclass(frozen=True)
class ConditionCode:
    icd10_code: str
    snomed_code: str


# Condition name → (ICD-10, SNOMED). Keys are normalized condition names/aliases.
CONDITION_CODES: dict[str, ConditionCode] = {
    "type 2 diabetes": ConditionCode("E11", "44054006"),
    "type 2 diabetes mellitus": ConditionCode("E11", "44054006"),
    "diabetes": ConditionCode("E11", "73211009"),
    "hypertension": ConditionCode("I10", "38341003"),
    "high blood pressure": ConditionCode("I10", "38341003"),
    "asthma": ConditionCode("J45", "195967001"),
    "hyperlipidemia": ConditionCode("E78.5", "55822004"),
    "high cholesterol": ConditionCode("E78.5", "55822004"),
    "copd": ConditionCode("J44.9", "13645005"),
    "gerd": ConditionCode("K21.9", "235595009"),
    "hypothyroidism": ConditionCode("E03.9", "40930008"),
    "migraine": ConditionCode("G43.909", "37796009"),
    "depression": ConditionCode("F32.9", "35489007"),
    "anxiety": ConditionCode("F41.9", "48694002"),
}


def code_allergy_substance(name: str) -> tuple[str, str, bool]:
    """Return ``(substance_display, coded_substance_id, is_coded)`` for an allergy.

    When the substance/name matches a known entry, the coded id is returned and
    ``is_coded`` is ``True``; otherwise the free-text value is retained and
    ``is_coded`` is ``False`` (Req 4.2, 4.4).
    """

    key = _normalize(name)
    if not key:
        return "", "", False
    code = ALLERGY_SUBSTANCE_CODES.get(key)
    if code:
        return key, code, True
    return key, "", False


def code_condition(name: str) -> tuple[str, str, bool]:
    """Return ``(icd10_code, snomed_code, is_coded)`` for a condition name.

    Offers ICD-10/SNOMED when the name matches a known entry; otherwise returns
    empty codes and ``is_coded=False`` (Req 5.2, 5.3).
    """

    key = _normalize(name)
    if not key:
        return "", "", False
    code = CONDITION_CODES.get(key)
    if code:
        return code.icd10_code, code.snomed_code, True
    return "", "", False
