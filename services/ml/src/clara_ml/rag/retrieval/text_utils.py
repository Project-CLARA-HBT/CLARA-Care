from __future__ import annotations

import re
import unicodedata
from typing import Any, Sequence

from .domain import Document, TRUST_TIER_FACTOR


_INTERACTION_SIGNALS = {
    "tuong",
    "tac",
    "tuongtac",
    "interaction",
    "ddi",
    "contraindication",
    "bleeding",
    "inr",
    "interact",
    "uong",
    "chung",
}

_MEDICATION_ALIASES: dict[str, tuple[str, ...]] = {
    "warfarin": ("warfarin", "coumadin", "jantoven"),
    "ibuprofen": ("ibuprofen", "advil", "motrin"),
    "naproxen": ("naproxen", "aleve"),
    "diclofenac": ("diclofenac", "voltaren"),
    "aspirin": ("aspirin", "asa", "acetylsalicylic"),
    "paracetamol": ("paracetamol", "acetaminophen", "tylenol"),
    "nsaid": (
        "nsaid",
        "nonsteroidal",
        "anti-inflammatory",
        "khang_viem",
        "khang",
        "viem",
        "giam_dau",
        "analgesic",
        "painkiller",
    ),
    "clopidogrel": ("clopidogrel", "plavix"),
    "omeprazole": ("omeprazole", "prilosec"),
    "simvastatin": ("simvastatin",),
    "atorvastatin": ("atorvastatin",),
    "clarithromycin": ("clarithromycin",),
}

_GENERIC_ANALGESIC_MARKERS = {
    "giam dau",
    "thuoc giam dau",
    "painkiller",
    "analgesic",
    "nsaid",
    "khang viem",
    "nonsteroidal",
}


def safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_weight(value: Any, default: float = 1.0) -> float:
    return max(0.0, min(2.0, safe_float(value, default)))


def normalize_tags(tags: Any) -> list[str]:
    if isinstance(tags, str):
        normalized = [tag.strip().lower() for tag in re.split(r"[,;|]", tags) if tag.strip()]
        return list(dict.fromkeys(normalized))
    if isinstance(tags, list):
        normalized = [str(tag).strip().lower() for tag in tags if str(tag).strip()]
        return list(dict.fromkeys(normalized))
    return []


def normalize_trust_tier(value: Any) -> str:
    raw = str(value or "").strip().lower().replace(" ", "_")
    if not raw:
        return "tier_3"
    aliases = {
        "1": "tier_1",
        "t1": "tier_1",
        "a": "tier_1",
        "official": "tier_1",
        "gov": "tier_1",
        "government": "tier_1",
        "2": "tier_2",
        "t2": "tier_2",
        "b": "tier_2",
        "clinical": "tier_2",
        "3": "tier_3",
        "t3": "tier_3",
        "c": "tier_3",
        "community": "tier_3",
        "4": "tier_4",
        "t4": "tier_4",
        "d": "tier_4",
        "low": "tier_4",
    }
    normalized = aliases.get(raw, raw)
    if normalized not in TRUST_TIER_FACTOR:
        return "tier_3"
    return normalized


def trust_tier_factor(trust_tier: Any) -> float:
    normalized = normalize_trust_tier(trust_tier)
    return TRUST_TIER_FACTOR.get(normalized, 1.0)


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def first_text(*values: Any) -> str:
    for value in values:
        text = clean_text(value)
        if text:
            return text
    return ""


def _ascii_fold(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    without_marks = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return without_marks.lower()


def _tokenize_terms(text: str) -> set[str]:
    lowered = text.lower()
    folded = _ascii_fold(text)
    raw = re.findall(r"[0-9a-zA-ZÀ-ỹ]{2,}", lowered)
    terms: set[str] = set(raw)
    terms.update(re.findall(r"[0-9a-z]{2,}", folded))
    return {item for item in terms if item}


def query_terms(query: str) -> list[str]:
    lowered = query.lower()
    folded = _ascii_fold(query)
    tokens = re.findall(r"[0-9a-zA-ZÀ-ỹ]{2,}", lowered)
    stopwords = {
        "cho",
        "cua",
        "voi",
        "nhung",
        "benh",
        "dieu",
        "tri",
        "nguoi",
        "sanh",
        "la",
        "va",
        "hay",
        "nao",
    }
    filtered = [token for token in tokens if token not in stopwords]

    expanded: list[str] = list(filtered)
    expansions: dict[str, list[str]] = {
        "dash": [
            "dash diet",
            "dietary approaches to stop hypertension",
            "hypertension diet",
        ],
        "mediterranean": [
            "mediterranean diet",
            "med diet cardiovascular",
            "olive oil cardiovascular outcomes",
        ],
        "tim mach": [
            "cardiovascular",
            "heart disease",
            "cvd prevention",
        ],
        "huyet ap": [
            "blood pressure",
            "hypertension",
            "systolic pressure",
        ],
        "dai thao duong": [
            "diabetes",
            "type 2 diabetes",
            "glycemic control",
        ],
        "cholesterol": [
            "lipid profile",
            "ldl cholesterol",
            "dyslipidemia",
        ],
        "tuong tac": [
            "drug interaction",
            "drug-drug interaction",
            "ddi",
            "adverse interaction",
            "contraindication",
        ],
        "drug interaction": [
            "drug-drug interaction",
            "ddi",
            "contraindication",
        ],
        "warfarin": [
            "warfarin",
            "coumadin",
            "inr bleeding risk",
            "anticoagulant interaction",
        ],
        "giam dau": [
            "painkiller",
            "analgesic",
            "nsaid",
            "ibuprofen",
            "naproxen",
            "diclofenac",
            "aspirin",
            "acetaminophen",
            "paracetamol",
        ],
        "thuoc giam dau": [
            "painkiller",
            "analgesic",
            "nsaid",
            "ibuprofen",
            "naproxen",
            "diclofenac",
            "aspirin",
            "acetaminophen",
            "paracetamol",
        ],
        "nsaid": [
            "ibuprofen",
            "naproxen",
            "diclofenac",
            "aspirin",
            "nonsteroidal anti-inflammatory",
        ],
    }

    for marker, extra_terms in expansions.items():
        if marker in lowered or marker in folded:
            expanded.extend(extra_terms)

    if ("dia trung hai" in folded or "địa trung hải" in lowered) and "mediterranean diet" not in expanded:
        expanded.extend(["mediterranean diet", "mediterranean dietary pattern"])

    if "dash" in lowered and "mediterranean" in lowered:
        expanded.extend(
            [
                "dash vs mediterranean diet",
                "diet comparison cardiovascular outcomes",
                "hypertension diet comparative trial",
            ]
        )

    if "warfarin" in lowered and any(
        marker in folded
        for marker in (
            "tuong tac",
            "drug interaction",
            "ddi",
            "giam dau",
            "thuoc giam dau",
            "painkiller",
            "analgesic",
            "nsaid",
            "ibuprofen",
            "naproxen",
            "diclofenac",
            "aspirin",
            "paracetamol",
            "acetaminophen",
        )
    ):
        expanded.extend(
            [
                "warfarin nsaid interaction",
                "warfarin ibuprofen bleeding risk",
                "warfarin analgesic interaction inr",
            ]
        )

    deduped: list[str] = []
    seen: set[str] = set()
    for token in expanded:
        clean = token.strip().lower()
        if len(clean) < 2 or clean in seen:
            continue
        seen.add(clean)
        deduped.append(clean)

    deduped.sort(key=len, reverse=True)
    return deduped[:8]


def analyze_query_profile(query: str) -> dict[str, Any]:
    lowered = query.lower()
    folded = _ascii_fold(query)
    terms = _tokenize_terms(query)

    normalized_drugs: list[str] = []
    for canonical, aliases in _MEDICATION_ALIASES.items():
        if any(alias in terms for alias in aliases):
            normalized_drugs.append(canonical)

    is_ddi_query = bool(terms.intersection(_INTERACTION_SIGNALS)) and bool(normalized_drugs)
    if "tuong tac" in folded and normalized_drugs:
        is_ddi_query = True
    if "drug interaction" in lowered and normalized_drugs:
        is_ddi_query = True
    if "uong chung" in folded and normalized_drugs:
        is_ddi_query = True

    primary_drug = (
        "warfarin" if "warfarin" in normalized_drugs else (normalized_drugs[0] if normalized_drugs else "")
    )
    co_drugs = [item for item in normalized_drugs if item != primary_drug]
    has_generic_analgesic = any(marker in folded for marker in _GENERIC_ANALGESIC_MARKERS)
    if primary_drug == "warfarin" and has_generic_analgesic and "nsaid" not in co_drugs:
        co_drugs.append("nsaid")
    if is_ddi_query and primary_drug == "warfarin" and not co_drugs:
        co_drugs = ["ibuprofen", "naproxen", "diclofenac", "aspirin", "paracetamol", "nsaid"]

    primary_aliases = sorted(
        {primary_drug, *_MEDICATION_ALIASES.get(primary_drug, ())} if primary_drug else set()
    )
    co_drug_aliases = {
        drug: sorted({drug, *_MEDICATION_ALIASES.get(drug, ())}) for drug in co_drugs
    }

    return {
        "query": query,
        "query_terms": query_terms(query),
        "is_ddi_query": is_ddi_query,
        "primary_drug": primary_drug,
        "co_drugs": co_drugs,
        "primary_aliases": primary_aliases,
        "co_drug_aliases": co_drug_aliases,
        "interaction_signals": sorted(list(_INTERACTION_SIGNALS.intersection(terms))),
    }


def tag_relevance_factor(query: str, tags: Any) -> float:
    tag_values = normalize_tags(tags)
    if not tag_values:
        return 1.0
    query_tokens = set(query_terms(query))
    if not query_tokens:
        return 1.0

    matches = 0
    for tag in tag_values:
        tag_tokens = {token for token in re.findall(r"[0-9a-zA-ZÀ-ỹ]{3,}", tag)}
        if query_tokens.intersection(tag_tokens):
            matches += 1

    if matches == 0:
        return 1.0
    return min(1.2, 1.0 + (0.06 * matches))


def dedupe_documents(documents: Sequence[Document]) -> list[Document]:
    deduped: list[Document] = []
    seen: set[str] = set()
    for doc in documents:
        if doc.id in seen:
            continue
        deduped.append(doc)
        seen.add(doc.id)
    return deduped
