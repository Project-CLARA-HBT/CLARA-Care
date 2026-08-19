# ruff: noqa: E501
from __future__ import annotations

import base64
import math
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from time import perf_counter
from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from clara_api.api.v1.endpoints.ml_proxy import proxy_ml_get, proxy_ml_post
from clara_api.compliance.consent import PURPOSE_PERSONALIZATION
from clara_api.compliance.service import ComplianceService
from clara_api.compliance.transfer import LLM_PROCESSOR, LLM_PURPOSE
from clara_api.core.attribution import (
    attach_attribution,
    build_attribution,
    normalize_source_errors,
    normalize_source_used,
)
from clara_api.core.careguard_metrics import (
    get_careguard_metrics_store,
    record_careguard_check,
)
from clara_api.core.config import get_settings
from clara_api.core.consent import PhrConsentService, ensure_medical_disclaimer_consent
from clara_api.core.control_tower import get_control_tower_config_service
from clara_api.core.ocr_correction import OcrCorrectionResult, correct_ocr_text
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.core.upload_safety import (
    UploadMalwareScannerUnavailable,
    UploadSafetyError,
    VerifiedUpload,
    read_upload_bytes_with_limit,
    verify_upload,
)
from clara_api.db.models import (
    LifeMapCaptureCandidate,
    LifeMapCaptureReviewAction,
    LifeMapCaptureSession,
    MedicationCourse,
    MedicationCourseChange,
    MedicineCabinet,
    MedicineItem,
    PhrProfile,
    User,
    VnDrugMapping,
    VnDrugMappingAlias,
    VnDrugMappingAudit,
)
from clara_api.db.session import get_db
from clara_api.glhs.adapters import ingest_medication_course, owner_profile_scope
from clara_api.glhs.gateway import compile_thss
from clara_api.phr.audit import write_audit
from clara_api.phr.features import phr_features
from clara_api.phr.provenance import hedge_text_bilingual
from clara_api.phr.reconciler import find_allergy_conflicts, reconcile
from clara_api.schemas import (
    CabinetAutoDdiRequest,
    CabinetDrugBankResolution,
    CabinetExpirySummary,
    CabinetImportRequest,
    CabinetImportResponse,
    CabinetPrioritizedField,
    CabinetScanDetection,
    CabinetScanTextRequest,
    CabinetScanTextResponse,
    MedicineCabinetItemCreate,
    MedicineCabinetItemResponse,
    MedicineCabinetItemUpdate,
    MedicineCabinetResponse,
    OcrConfirmGate,
    OcrSourceCoordinate,
    VnDrugMappingAuditListResponse,
    VnDrugMappingAuditResponse,
    VnDrugMappingCreateRequest,
    VnDrugMappingCurationRequest,
    VnDrugMappingListResponse,
    VnDrugMappingResponse,
    VnDrugMappingUpdateRequest,
    VnDrugResolveRequest,
    VnDrugResolveResponse,
)

router = APIRouter()

_MAX_CAREGUARD_MEDICATION_TEXT_CHARS = 2_000


def _bounded_medication_text_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the optional free-text medicine field before ML proxying.

    The ML service repeats this bound because it also has internal callers.
    Keeping an API boundary prevents an authenticated public request from using
    the generic CareGuard payload as an unbounded text transport.  The field is
    deliberately not transformed or split here: deterministic clinical NLP and
    exact DrugBank identity resolution remain inside the ML safety pipeline.
    """

    if "medication_text" not in payload:
        return dict(payload)
    value = payload.get("medication_text")
    if not isinstance(value, str) or len(value.strip()) > _MAX_CAREGUARD_MEDICATION_TEXT_CHARS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="medication_text_invalid",
        )
    prepared = dict(payload)
    prepared["medication_text"] = value.strip()
    return prepared


@router.get("/drugbank/status")
def drugbank_status(
    token: TokenPayload = Depends(require_roles("doctor", "researcher")),
) -> dict[str, Any]:
    """Content-free readiness and licensed artifact version for clinical audit."""

    _ = token
    details = proxy_ml_get("/health/details", timeout_seconds=10.0)
    readiness = details.get("drugbank")
    if not isinstance(readiness, dict):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DrugBank readiness is not reported by the ML service",
        )
    if readiness.get("required") is True and (
        readiness.get("state") != "ready"
        or readiness.get("manifest_matches_index") is not True
        or readiness.get("integrity_verified") is not True
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "drugbank_required_unavailable",
                "readiness": readiness,
            },
        )
    return readiness

DRUG_ALIAS_MAP: dict[str, list[str]] = {
    "paracetamol": [
        "paracetamol",
        "acetaminophen",
        "panadol",
        "panadol xanh",
        "hapacol",
        "efferalgan",
        "paracetamol stada",
        "paracetamol dhg",
        "paracetamol mekophar",
        "acetamin",
        "tylenol",
        "pamol",
        "adol",
        "pamin",
    ],
    "paracetamol caffeine": [
        "panadol extra",
        "paracetamol caffeine",
        "paracetamol + caffeine",
        "cafetin",
        "efferalgan codein",
        "decolgen",
        "tiffy",
        "cảm xuyên hương",
    ],
    "ibuprofen": ["ibuprofen", "advil", "brufen", "motrin", "ibuprofen stella", "ibuprofen dhg"],
    "diclofenac": ["diclofenac", "voltaren", "cataflam", "diclofenac stada", "diclofenac dhg"],
    "naproxen": ["naproxen", "naprosyn", "nalgesin", "naproxen stada"],
    "aspirin": ["aspirin", "aspirin cardio", "aspirin protect", "aspilet", "baby aspirin"],
    "warfarin": ["warfarin", "coumadin", "warfarex"],
    "rivaroxaban": ["rivaroxaban", "xarelto"],
    "apixaban": ["apixaban", "eliquis"],
    "clopidogrel": ["clopidogrel", "plavix", "clopidogrel stada", "clopidogrel dhg"],
    "lisinopril": ["lisinopril", "zestril", "lisinopril stada"],
    "losartan": ["losartan", "cozaar", "losartan stada", "losartan dhg"],
    "amlodipine": ["amlodipine", "norvasc", "amlodipin stada", "amlodipin dhg"],
    "bisoprolol": ["bisoprolol", "concor", "bisoprolol stada", "bisoprolol hasan"],
    "metoprolol": ["metoprolol", "betaloc", "metoprolol stella"],
    "spironolactone": ["spironolactone", "aldactone", "spironolacton stada"],
    "furosemide": ["furosemide", "lasix", "furosemid stada", "furosemid dhg"],
    "digoxin": ["digoxin", "lanoxin"],
    "amiodarone": ["amiodarone", "cordarone", "amiodaron stella"],
    "verapamil": ["verapamil", "isoptin"],
    "metformin": ["metformin", "glucophage", "metformin stada", "metformin dhg", "metformin hasan"],
    "gliclazide": ["gliclazide", "diamicron", "gliclazid stada"],
    "glimepiride": ["glimepiride", "amaryl", "glimepirid stada"],
    "insulin": ["insulin", "insulatard", "novorapid", "humalog", "mixtard", "lantus", "levemir"],
    "atorvastatin": ["atorvastatin", "lipitor", "atorvastatin stada", "atorvastatin dhg"],
    "simvastatin": ["simvastatin", "zocor", "simvastatin stada", "simvastatin dhg"],
    "rosuvastatin": ["rosuvastatin", "crestor", "rosuvastatin stada", "rosuvastatin dhg"],
    "omeprazole": ["omeprazole", "losec", "omeprazol stada", "omeprazol dhg"],
    "esomeprazole": ["esomeprazole", "nexium", "esomeprazol stada"],
    "pantoprazole": ["pantoprazole", "pantoloc", "pantozol", "pantoprazol stada"],
    "amoxicillin": ["amoxicillin", "amox", "amoxicillin stada", "amoxicillin dhg", "amoxil"],
    "amoxicillin clavulanate": [
        "amoxicillin clavulanate",
        "augmentin",
        "klamentin",
        "bidiclav",
        "amoclav",
        "clavam",
    ],
    "clarithromycin": ["clarithromycin", "klacid", "clarithromycin stada"],
    "erythromycin": ["erythromycin", "erythrocin", "erythromycin stella"],
    "ciprofloxacin": ["ciprofloxacin", "cipro", "ciprobay", "ciprofloxacin stada"],
    "trimethoprim": ["trimethoprim", "cotrimoxazole", "bactrim", "septrin"],
    "fluconazole": ["fluconazole", "diflucan", "fluconazole stada", "fluconazole dhg"],
    "ketoconazole": ["ketoconazole", "nizoral", "ketoconazol stada"],
    "linezolid": ["linezolid", "zyvox"],
    "methotrexate": ["methotrexate", "methotrexat ebewe", "methotrexat"],
    "allopurinol": ["allopurinol", "zyloric", "allopurinol stada"],
    "azathioprine": ["azathioprine", "imuran"],
    "tacrolimus": ["tacrolimus", "prograf"],
    "sertraline": ["sertraline", "zoloft", "sertralin stada"],
    "fluoxetine": ["fluoxetine", "prozac", "fluoxetin stada"],
    "diazepam": ["diazepam", "valium", "seduxen", "diazepam stella"],
    "tramadol": ["tramadol", "ultram", "tramadol stada", "tramadol dhg"],
    "tizanidine": ["tizanidine", "sirdalud"],
    "sildenafil": ["sildenafil", "viagra", "sildenafil stada"],
    "nitroglycerin": ["nitroglycerin", "nitromint", "nitrostat"],
    "loratadine": ["loratadine", "claritin", "loratadin stada", "loratadin dhg", "allerclear"],
    "cetirizine": ["cetirizine", "zyrtec", "cetirizin stada", "cetirizin dhg"],
    "prednisone": ["prednisone", "prednisolon", "medrol", "methylprednisolone"],
    "cimetidine": ["cimetidine", "tagamet"],
    "potassium chloride": ["potassium chloride", "kali clorid", "kcl", "kaliorid"],
    "vitamin c": ["vitamin c", "ascorbic acid", "vitamin-c", "ceelin", "upsavit c", "redoxon"],
}

DRUG_RXCUI_MAP: dict[str, str] = {
    "paracetamol": "161",
    "ibuprofen": "5640",
    "aspirin": "1191",
    "warfarin": "11289",
    "metformin": "6809",
    "amoxicillin": "723",
    "simvastatin": "36567",
    "loratadine": "28889",
    "cetirizine": "20610",
    "omeprazole": "7646",
    "lisinopril": "29046",
    "losartan": "52175",
    "amlodipine": "17767",
    "clopidogrel": "32968",
    "rivaroxaban": "1114195",
    "apixaban": "1364430",
    "spironolactone": "9997",
    "furosemide": "4603",
    "digoxin": "3407",
    "amiodarone": "703",
    "verapamil": "11170",
    "atorvastatin": "83367",
    "rosuvastatin": "301542",
    "gliclazide": "4815",
    "glimepiride": "25789",
    "clarithromycin": "21212",
    "ciprofloxacin": "2551",
    "fluconazole": "4450",
    "diazepam": "3322",
    "tramadol": "10689",
    "sildenafil": "136411",
    "nitroglycerin": "4917",
    "diclofenac": "3355",
    "naproxen": "7258",
}

LOW_CONFIDENCE_OCR_THRESHOLD = 0.9
OCR_CORRECTION_CUTOFF = 0.86
OCR_CORRECTION_MAX_CHARS = 12000
# Normalization "needs review" threshold (Req 2.5, 2.6). A normalization whose
# confidence falls below this is retained (never dropped) but flagged
# ``needs_review`` so the user can confirm/correct it. The dictionary path
# returns confidence 1.0 for an exact db hit, >= 0.78 for a fuzzy candidate, and
# 0.72 for an alias-map hit; only the unmatched fallback (0.35, name not in the
# alias map) sits below this threshold, which is exactly the "needs review"
# case. Purely derived — no persisted state — so flags-off byte-equivalence of
# the existing response fields is preserved (P12).
NORMALIZATION_REVIEW_CONFIDENCE_THRESHOLD = 0.5
# Cabinet quantity/expiry validation bounds (Req 1.7). Validation only rejects
# clearly-invalid input (negative/non-finite quantity, absurd magnitude, or an
# expiry date far outside any plausible range); all previously-valid inputs are
# accepted unchanged so flags-off byte-equivalence (P12) is preserved.
_MAX_CABINET_QUANTITY = 1_000_000.0
_MIN_EXPIRY_DATE = datetime(1900, 1, 1, tzinfo=UTC)
_MAX_EXPIRY_DATE = datetime(2200, 1, 1, tzinfo=UTC)
# Expiry "expiring soon" window (Req 10.1). An item whose ``expires_on`` is in
# the past is ``expired``; one within this many days is ``expiring_soon``;
# anything further out is ``ok``; a missing ``expires_on`` is "no expiry data"
# (status ``None``) and is excluded from the cabinet rollup counts (Req 10.5).
# Purely derived from ``expires_on`` with no persisted state, so the existing
# response fields remain byte-equivalent (P12).
EXPIRY_SOON_WINDOW_DAYS = 30
_CANDIDATE_DB_LIMIT = 120
_CANDIDATE_MIN_SCORE = 0.78
_CANDIDATE_MIN_MARGIN = 0.05
_CANDIDATE_MAX_INPUT_LENGTH = 255
_ITEM_NOTE_META_PREFIX = "[meta]"
_OCR_NOISY_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("paracetarnol", "paracetamol"),
    ("1buprofen", "ibuprofen"),
    ("arnoxicillin", "amoxicillin"),
    ("metforrnin", "metformin"),
    ("warfarrn", "warfarin"),
)
_OCR_NOISY_CHAR_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("0", "o"),
    ("1", "i"),
    ("5", "s"),
    ("8", "b"),
)
_OCR_FUZZY_STOPWORDS: set[str] = {
    "toa",
    "thuoc",
    "uong",
    "sang",
    "trua",
    "chieu",
    "toi",
    "ngay",
    "lan",
    "vien",
    "sau",
    "an",
    "truoc",
    "hop",
    "sieu",
    "am",
}
_MANUFACTURER_HINTS: tuple[str, ...] = (
    "stada",
    "dhg",
    "hasan",
    "stella",
    "mekophar",
    "pymepharco",
    "traphaco",
    "imexpharm",
    "sanofi",
    "gsk",
    "bayer",
    "pfizer",
)

_CAREGUARD_SOURCE_CATALOG: dict[str, dict[str, str]] = {
    "drugbank": {
        "id": "drugbank",
        "name": "DrugBank Drug-Drug Interactions",
        "type": "licensed_knowledge_base",
    },
    "local_rules": {
        "id": "local_rules",
        "name": "CLARA Local DDI Rules",
        "type": "deterministic",
    },
    "rxnav": {
        "id": "rxnav",
        "name": "RxNav / RxNorm (NLM)",
        "type": "knowledge_base",
    },
    "rxnorm": {
        "id": "rxnav",
        "name": "RxNav / RxNorm (NLM)",
        "type": "knowledge_base",
    },
    "openfda": {
        "id": "openfda",
        "name": "openFDA Drug Label",
        "type": "safety_signal",
    },
}


def _build_alias_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for canonical, aliases in DRUG_ALIAS_MAP.items():
        lookup[_normalize_text(canonical)] = canonical
        for alias in aliases:
            lookup[_normalize_text(alias)] = canonical
    return lookup


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


_DRUGBANK_ALIAS_DOSAGE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(mg|g|mcg|μg|ml|iu|%)\b",
    flags=re.IGNORECASE,
)
_DRUGBANK_ALIAS_COUNT = re.compile(
    r"\bx\s*\d+\b",
    flags=re.IGNORECASE,
)
_DRUGBANK_ALIAS_FORMS = {
    "tablet", "tablets", "tab", "tabs", "capsule", "capsules", "cap", "caps",
    "syrup", "suspension", "solution", "cream", "ointment", "gel", "patch",
    "injection", "injectable", "sl", "iv", "im", "po", "bid", "tid", "qid",
    "od", "hs", "vien", "ống", "ong",
}


def _canonicalize_drugbank_alias(value: str) -> str:
    """Bound a returned choice to its owner-scoped cabinet input.

    This mirrors the internal ML alias cleanup only for request binding. It
    never chooses a DrugBank record or produces a DDI conclusion; ML validates
    the chosen source identifier against the current licensed index.
    """

    cleaned = _DRUGBANK_ALIAS_DOSAGE.sub(" ", _normalize_text(value))
    cleaned = _DRUGBANK_ALIAS_COUNT.sub(" ", cleaned)
    cleaned = re.sub(r"[/(),;+]", " ", cleaned)
    return " ".join(
        part for part in cleaned.split() if part and part not in _DRUGBANK_ALIAS_FORMS
    )


DRUG_ALIAS_LOOKUP = _build_alias_lookup()
OCR_DRUG_VOCABULARY: tuple[str, ...] = tuple(
    sorted({alias for aliases in DRUG_ALIAS_MAP.values() for alias in aliases})
)


def _ascii_fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _tokenize_terms(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def _normalize_aliases(raw_aliases: list[str], brand_name: str) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for candidate in [brand_name, *raw_aliases]:
        cleaned = " ".join(str(candidate or "").split()).strip()
        if not cleaned:
            continue
        key = _normalize_text(cleaned)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
    return normalized


def _find_db_mapping_by_alias(db: Session, normalized_input: str) -> VnDrugMapping | None:
    mapping = (
        db.execute(
            select(VnDrugMapping)
            .join(VnDrugMappingAlias, VnDrugMappingAlias.mapping_id == VnDrugMapping.id)
            .where(
                VnDrugMapping.is_active.is_(True),
                VnDrugMappingAlias.normalized_alias == normalized_input,
            )
            .order_by(VnDrugMappingAlias.is_primary.desc(), VnDrugMapping.id.desc())
        )
        .scalars()
        .first()
    )
    if mapping is not None:
        return mapping

    return db.execute(
        select(VnDrugMapping).where(
            VnDrugMapping.is_active.is_(True),
            VnDrugMapping.normalized_brand == normalized_input,
        )
    ).scalar_one_or_none()


def _compute_candidate_similarity(query: str, candidate: str) -> float:
    query_fold = _ascii_fold(query)[:_CANDIDATE_MAX_INPUT_LENGTH]
    candidate_fold = _ascii_fold(candidate)[:_CANDIDATE_MAX_INPUT_LENGTH]
    sequence_ratio = SequenceMatcher(a=query_fold, b=candidate_fold).ratio()
    query_terms = _tokenize_terms(query_fold)
    candidate_terms = _tokenize_terms(candidate_fold)
    if not query_terms:
        return sequence_ratio

    overlap = len(query_terms & candidate_terms) / len(query_terms)
    union = query_terms | candidate_terms
    jaccard = len(query_terms & candidate_terms) / len(union) if union else 0.0
    contains_bonus = 0.08 if query_fold in candidate_fold or candidate_fold in query_fold else 0.0
    score = (sequence_ratio * 0.55) + (overlap * 0.35) + (jaccard * 0.10) + contains_bonus
    return min(score, 1.0)


def _collect_db_candidate_mappings(db: Session, normalized_input: str) -> list[VnDrugMapping]:
    terms = [term for term in normalized_input.split(" ") if term]
    first_term = terms[0] if terms else normalized_input
    second_term = terms[1] if len(terms) > 1 else ""
    like_conditions = [
        VnDrugMapping.normalized_brand.like(f"{normalized_input}%"),
        VnDrugMappingAlias.normalized_alias.like(f"{normalized_input}%"),
        VnDrugMapping.normalized_brand.like(f"%{first_term}%"),
        VnDrugMappingAlias.normalized_alias.like(f"%{first_term}%"),
    ]
    if second_term:
        like_conditions.extend(
            [
                VnDrugMapping.normalized_brand.like(f"%{second_term}%"),
                VnDrugMappingAlias.normalized_alias.like(f"%{second_term}%"),
            ]
        )

    return (
        db.execute(
            select(VnDrugMapping)
            .options(selectinload(VnDrugMapping.aliases))
            .outerjoin(VnDrugMappingAlias, VnDrugMappingAlias.mapping_id == VnDrugMapping.id)
            .where(
                VnDrugMapping.is_active.is_(True),
                or_(*like_conditions),
            )
            .order_by(VnDrugMapping.id.desc())
            .limit(_CANDIDATE_DB_LIMIT)
        )
        .unique()
        .scalars()
        .all()
    )


def _find_db_mapping_candidate(
    db: Session,
    normalized_input: str,
) -> tuple[VnDrugMapping | None, float, int, int]:
    started_at = perf_counter()
    bounded_input = normalized_input[:_CANDIDATE_MAX_INPUT_LENGTH].strip()
    if not bounded_input:
        elapsed = int((perf_counter() - started_at) * 1000)
        return None, 0.0, 0, elapsed

    candidates = _collect_db_candidate_mappings(db, bounded_input)
    if not candidates:
        elapsed = int((perf_counter() - started_at) * 1000)
        return None, 0.0, 0, elapsed

    ranked: list[tuple[float, VnDrugMapping]] = []
    for mapping in candidates:
        names = [mapping.normalized_brand, *(alias.normalized_alias for alias in mapping.aliases)]
        best_score = 0.0
        for name in names:
            if not name:
                continue
            best_score = max(best_score, _compute_candidate_similarity(bounded_input, name))
        ranked.append((best_score, mapping))

    ranked.sort(key=lambda entry: entry[0], reverse=True)
    best_score, best_mapping = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else 0.0
    elapsed_ms = int((perf_counter() - started_at) * 1000)

    if best_score < _CANDIDATE_MIN_SCORE:
        return None, best_score, len(candidates), elapsed_ms
    if best_score < 0.9 and (best_score - second_score) < _CANDIDATE_MIN_MARGIN:
        return None, best_score, len(candidates), elapsed_ms

    return best_mapping, best_score, len(candidates), elapsed_ms


def _resolve_dictionary_mapping_with_source(
    drug_name: str,
    db: Session | None = None,
) -> tuple[str, str, str, str, float]:
    normalized_input = _normalize_text(drug_name)
    if db is not None:
        db_mapping = _find_db_mapping_by_alias(db, normalized_input)
        if db_mapping is not None:
            display_name = db_mapping.brand_name.strip() or _to_title_case(
                db_mapping.normalized_name
            )
            normalized_name = db_mapping.normalized_name.strip() or normalized_input
            rx_cui = db_mapping.rx_cui.strip()
            if not rx_cui:
                rx_cui = DRUG_RXCUI_MAP.get(normalized_name, "")
            return display_name, normalized_name, rx_cui, "db", 1.0

        candidate_mapping, candidate_score, _, _ = _find_db_mapping_candidate(db, normalized_input)
        if candidate_mapping is not None:
            display_name = candidate_mapping.brand_name.strip() or _to_title_case(
                candidate_mapping.normalized_name
            )
            normalized_name = candidate_mapping.normalized_name.strip() or normalized_input
            rx_cui = candidate_mapping.rx_cui.strip()
            if not rx_cui:
                rx_cui = DRUG_RXCUI_MAP.get(normalized_name, "")
            return (
                display_name,
                normalized_name,
                rx_cui,
                "candidate",
                max(min(candidate_score, 1.0), 0.0),
            )

    canonical = DRUG_ALIAS_LOOKUP.get(normalized_input, normalized_input)
    display_name = _to_title_case(canonical)
    rx_cui = DRUG_RXCUI_MAP.get(canonical, "")
    if canonical != normalized_input:
        fallback_confidence = 0.72
    else:
        fallback_confidence = 0.35
    return display_name, canonical, rx_cui, "fallback", fallback_confidence


def _resolve_dictionary_mapping(
    drug_name: str,
    db: Session | None = None,
) -> tuple[str, str, str]:
    display_name, normalized_name, rx_cui, _mapping_source, _mapping_confidence = (
        _resolve_dictionary_mapping_with_source(
            drug_name=drug_name,
            db=db,
        )
    )
    return display_name, normalized_name, rx_cui


def _derive_normalization_status(
    normalization_source: str | None,
    normalization_confidence: float | None,
) -> str | None:
    """Map a dictionary mapping_source + confidence to a user-facing status.

    Returns one of ``matched`` (exact db hit), ``candidate`` (fuzzy db
    candidate), ``fallback`` (alias-map hit), or ``needs_review`` (unmatched or
    below ``NORMALIZATION_REVIEW_CONFIDENCE_THRESHOLD``). ``None`` is returned
    only when no source was resolved (status unknown). The user-entered name is
    always retained by callers regardless of status (Req 2.5).
    """

    if normalization_source is None:
        return None
    if (
        normalization_confidence is not None
        and normalization_confidence < NORMALIZATION_REVIEW_CONFIDENCE_THRESHOLD
    ):
        return "needs_review"
    return {
        "db": "matched",
        "candidate": "candidate",
        "fallback": "fallback",
    }.get(normalization_source, "needs_review")


def _compute_expiry_status(
    expires_on: datetime | None,
    *,
    now: datetime | None = None,
) -> str | None:
    """Derive an expiry status from ``expires_on`` (Req 10.1, 10.5).

    Returns ``expired`` when the date is at/before ``now``, ``expiring_soon``
    when it falls within ``EXPIRY_SOON_WINDOW_DAYS`` of ``now``, ``ok`` when it
    is further out, or ``None`` when there is no expiry data. A naive datetime
    is interpreted as UTC. A missing/unset ``expires_on`` is treated as "no
    expiry data" without error (Req 10.5).
    """

    if expires_on is None:
        return None
    reference = now or datetime.now(tz=UTC)
    moment = expires_on if expires_on.tzinfo is not None else expires_on.replace(tzinfo=UTC)
    if moment <= reference:
        return "expired"
    if moment <= reference + timedelta(days=EXPIRY_SOON_WINDOW_DAYS):
        return "expiring_soon"
    return "ok"


def _to_title_case(value: str) -> str:
    return " ".join(token.capitalize() for token in value.split(" ") if token)


def _sanitize_meta_value(value: str) -> str:
    return " ".join(str(value or "").replace("|", " ").replace("\n", " ").split()).strip()


def _encode_item_note(note: str, *, brand_name: str = "", manufacturer: str = "") -> str:
    clean_note = (note or "").strip()
    clean_brand = _sanitize_meta_value(brand_name)
    clean_manufacturer = _sanitize_meta_value(manufacturer)
    if not clean_brand and not clean_manufacturer:
        return clean_note
    meta = f"{_ITEM_NOTE_META_PREFIX}brand={clean_brand}|manufacturer={clean_manufacturer}".strip()
    if clean_note:
        return f"{meta}\n{clean_note}".strip()
    return meta


def _decode_item_note(note: str) -> tuple[str, str | None, str | None]:
    raw = str(note or "").strip()
    if not raw:
        return "", None, None
    first_line, _, remaining = raw.partition("\n")
    first = first_line.strip().lower()
    if not first.startswith(_ITEM_NOTE_META_PREFIX):
        return raw, None, None
    payload = first_line[len(_ITEM_NOTE_META_PREFIX) :].strip()
    if not payload or "=" not in payload:
        return raw, None, None
    brand_name: str | None = None
    manufacturer: str | None = None
    for part in payload.split("|"):
        key, _, value = part.partition("=")
        key_norm = key.strip().lower()
        val_norm = _sanitize_meta_value(value)
        if key_norm == "brand" and val_norm:
            brand_name = val_norm
        elif key_norm == "manufacturer" and val_norm:
            manufacturer = val_norm
    return remaining.strip(), brand_name, manufacturer


def _infer_manufacturer_from_text(text: str) -> str:
    lowered = text.lower()
    for name in _MANUFACTURER_HINTS:
        pattern = rf"(^|[^a-z0-9]){re.escape(name)}([^a-z0-9]|$)"
        if re.search(pattern, lowered):
            return name.upper()
    return ""


def _infer_brand_name(
    *,
    alias: str,
    canonical: str,
    display_name: str,
) -> str:
    alias_clean = _sanitize_meta_value(alias)
    canonical_clean = _sanitize_meta_value(canonical)
    display_clean = _sanitize_meta_value(display_name)
    if alias_clean and alias_clean.lower() != canonical_clean.lower():
        return _to_title_case(alias_clean)
    if display_clean and display_clean.lower() != canonical_clean.lower():
        return display_clean
    return ""


def _to_item_response(
    item: MedicineItem,
    *,
    normalization_source: str | None = None,
    normalization_confidence: float | None = None,
) -> MedicineCabinetItemResponse:
    # Dual-read (Req 1.4): the legacy ``[meta]`` note encoding is ALWAYS decoded
    # so pre-existing items remain readable regardless of the structured-fields
    # flag. When the structured columns are populated (writes made while
    # SELFMED_CABINET_STRUCTURED_FIELDS_ENABLED was on) they take precedence; an
    # unset column (None) falls back to the decoded legacy note value, so no
    # brand/manufacturer data is ever lost across a flag flip.
    clean_note, note_brand_name, note_manufacturer = _decode_item_note(item.note)
    brand_name = item.brand_name if item.brand_name is not None else note_brand_name
    manufacturer = (
        item.manufacturer if item.manufacturer is not None else note_manufacturer
    )
    normalization_status = _derive_normalization_status(
        normalization_source,
        normalization_confidence,
    )
    # Expiry status (Req 10.1) is purely derived from ``expires_on`` and is
    # always surfaced; a missing/unset ``expires_on`` yields ``None`` (no expiry
    # data, Req 10.5). The persisted reminder state (Req 10.3) is exposed ONLY
    # when SELFMED_EXPIRY_REMINDERS_ENABLED is on; when off it stays ``None`` so
    # behavior matches today (Req 10.4).
    expiry_status = _compute_expiry_status(item.expires_on)
    expiry_reminder: dict[str, Any] | None = None
    if get_settings().selfmed_expiry_reminders_enabled:
        stored_reminder = item.expiry_reminder_json
        if isinstance(stored_reminder, dict):
            expiry_reminder = stored_reminder
    return MedicineCabinetItemResponse(
        id=item.id,
        drug_name=item.drug_name,
        brand_name=brand_name,
        manufacturer=manufacturer,
        normalized_name=item.normalized_name,
        normalization_source=normalization_source,
        normalization_confidence=normalization_confidence,
        normalization_status=normalization_status,
        needs_review=normalization_status == "needs_review",
        dosage=item.dosage,
        dosage_form=item.dosage_form,
        quantity=item.quantity,
        source=item.source,
        rx_cui=item.rx_cui,
        ocr_confidence=item.ocr_confidence,
        expires_on=item.expires_on,
        expiry_status=expiry_status,
        expiry_reminder=expiry_reminder,
        note=clean_note,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _to_mapping_response(mapping: VnDrugMapping) -> VnDrugMappingResponse:
    aliases_sorted = sorted(
        mapping.aliases,
        key=lambda alias: (not alias.is_primary, alias.alias_name.lower()),
    )
    return VnDrugMappingResponse(
        id=mapping.id,
        brand_name=mapping.brand_name,
        aliases=[alias.alias_name for alias in aliases_sorted],
        active_ingredients=mapping.active_ingredients,
        normalized_name=mapping.normalized_name,
        rx_cui=mapping.rx_cui,
        mapping_source=mapping.mapping_source,
        notes=mapping.notes,
        is_active=mapping.is_active,
        created_by_user_id=mapping.created_by_user_id,
        created_at=mapping.created_at,
        updated_at=mapping.updated_at,
    )


def _mapping_snapshot(mapping: VnDrugMapping) -> dict[str, Any]:
    aliases_sorted = sorted(
        [alias.alias_name for alias in mapping.aliases],
        key=lambda alias_name: alias_name.lower(),
    )
    return {
        "id": mapping.id,
        "brand_name": mapping.brand_name,
        "aliases": aliases_sorted,
        "active_ingredients": mapping.active_ingredients,
        "normalized_name": mapping.normalized_name,
        "rx_cui": mapping.rx_cui,
        "mapping_source": mapping.mapping_source,
        "notes": mapping.notes,
        "is_active": mapping.is_active,
        "created_by_user_id": mapping.created_by_user_id,
        "updated_at": mapping.updated_at.isoformat() if mapping.updated_at else None,
    }


def _to_mapping_audit_response(audit: VnDrugMappingAudit) -> VnDrugMappingAuditResponse:
    return VnDrugMappingAuditResponse(
        id=audit.id,
        mapping_id=audit.mapping_id,
        actor_user_id=audit.actor_user_id,
        actor_email=audit.actor.email if audit.actor else None,
        action=audit.action,
        reason=audit.reason,
        before_json=audit.before_json,
        after_json=audit.after_json,
        metadata_json=audit.metadata_json,
        created_at=audit.created_at,
    )


def _create_mapping_audit(
    db: Session,
    *,
    mapping: VnDrugMapping,
    action: str,
    actor_user_id: int | None,
    reason: str = "",
    before_snapshot: dict[str, Any] | None = None,
    after_snapshot: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> VnDrugMappingAudit:
    audit = VnDrugMappingAudit(
        mapping_id=mapping.id,
        action=action,
        reason=reason.strip(),
        before_json=before_snapshot,
        after_json=after_snapshot,
        actor_user_id=actor_user_id,
        metadata_json=metadata,
    )
    db.add(audit)
    return audit


def _get_mapping_or_404(db: Session, mapping_id: int) -> VnDrugMapping:
    mapping = db.execute(
        select(VnDrugMapping).where(VnDrugMapping.id == mapping_id)
    ).scalar_one_or_none()
    if mapping is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy mapping")
    return mapping


def _validate_alias_conflicts(
    db: Session,
    aliases: list[str],
    *,
    exclude_mapping_id: int | None = None,
) -> None:
    normalized_aliases = [_normalize_text(alias) for alias in aliases]
    if not normalized_aliases:
        return
    existing_aliases = (
        db.execute(
            select(VnDrugMappingAlias)
            .join(VnDrugMapping, VnDrugMapping.id == VnDrugMappingAlias.mapping_id)
            .where(
                VnDrugMappingAlias.normalized_alias.in_(normalized_aliases),
                VnDrugMapping.is_active.is_(True),
            )
        )
        .scalars()
        .all()
    )
    for alias in existing_aliases:
        if exclude_mapping_id is not None and alias.mapping_id == exclude_mapping_id:
            continue
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Alias đã tồn tại trong mapping khác: {alias.alias_name}",
        )


def _replace_mapping_aliases(db: Session, mapping: VnDrugMapping, aliases: list[str]) -> None:
    mapping.aliases.clear()
    db.flush()
    for index, alias in enumerate(aliases):
        mapping.aliases.append(
            VnDrugMappingAlias(
                alias_name=alias,
                normalized_alias=_normalize_text(alias),
                is_primary=index == 0,
            ),
        )


def _default_careguard_sources(external_ddi_enabled: bool) -> list[dict[str, str]]:
    sources = [dict(_CAREGUARD_SOURCE_CATALOG["local_rules"])]
    if external_ddi_enabled:
        sources.extend(
            [
                dict(_CAREGUARD_SOURCE_CATALOG["rxnav"]),
                dict(_CAREGUARD_SOURCE_CATALOG["openfda"]),
            ]
        )
    return sources


def _resolve_careguard_sources(
    *,
    source_used: list[str],
    external_ddi_enabled: bool,
) -> list[dict[str, str]]:
    if not source_used:
        return _default_careguard_sources(external_ddi_enabled)

    sources: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for source_name in source_used:
        source = _CAREGUARD_SOURCE_CATALOG.get(source_name)
        if source is None:
            source = {
                "id": source_name,
                "name": source_name.replace("_", " ").title(),
                "type": "external",
            }
        source_id = source.get("id", source_name)
        if source_id in seen_ids:
            continue
        seen_ids.add(source_id)
        sources.append(dict(source))
    return sources


def _attach_careguard_attribution(
    payload: dict[str, Any],
    *,
    external_ddi_enabled: bool,
) -> dict[str, Any]:
    response = dict(payload)
    metadata = response.get("metadata")
    metadata_obj = metadata if isinstance(metadata, dict) else {}
    source_used = normalize_source_used(metadata_obj.get("source_used"))
    source_errors = normalize_source_errors(metadata_obj.get("source_errors"))
    ddi_status = response.get("ddi_status")
    if not isinstance(ddi_status, dict):
        metadata_ddi_status = metadata_obj.get("ddi_status")
        ddi_status = metadata_ddi_status if isinstance(metadata_ddi_status, dict) else {}
    ddi_unavailable = (
        ddi_status.get("state") == "unavailable"
        and ddi_status.get("conclusion_available") is False
    )
    sources = (
        []
        if ddi_unavailable
        else _resolve_careguard_sources(
            source_used=source_used,
            external_ddi_enabled=external_ddi_enabled,
        )
    )
    source_ids = {str(source.get("id") or "") for source in sources}
    if ddi_unavailable:
        mode = "unavailable"
    elif source_ids == {"drugbank"}:
        mode = "drugbank_only"
    elif "local_rules" in source_ids and len(source_ids) > 1:
        mode = "external_plus_local"
    elif "local_rules" in source_ids:
        mode = "local_only"
    else:
        mode = "external_only"
    fallback_used = bool(response.get("fallback_used") or metadata_obj.get("fallback_used"))

    attribution = build_attribution(
        channel="careguard",
        mode=mode,
        sources=sources,
        citations_payload=response.get("citations"),
        source_used=source_used,
        source_errors=source_errors,
        fallback_used=fallback_used,
    )
    return attach_attribution(response, attribution=attribution)


def _require_user(
    token: TokenPayload,
    db: Session,
) -> User:
    user = db.execute(select(User).where(User.email == token.sub)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Không tìm thấy người dùng",
        )
    ensure_medical_disclaimer_consent(db, user_id=user.id)
    return user


def _require_admin_user(
    token: TokenPayload,
    db: Session,
) -> User:
    user = _require_user(token, db)
    if token.role != "admin" and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ admin mới được thực hiện thao tác này",
        )
    return user


def _get_or_create_cabinet(db: Session, user_id: int) -> MedicineCabinet:
    cabinet = db.execute(
        select(MedicineCabinet).where(MedicineCabinet.user_id == user_id)
    ).scalar_one_or_none()
    if cabinet:
        return cabinet

    cabinet = MedicineCabinet(user_id=user_id, label="Tủ thuốc cá nhân")
    db.add(cabinet)
    db.commit()
    db.refresh(cabinet)
    return cabinet


def _validate_cabinet_quantity(quantity: float | None) -> None:
    """Reject malformed/out-of-range cabinet quantities (Req 1.7).

    A quantity must be a finite, non-negative number within a sane upper bound.
    ``None`` is treated as "not provided" by callers and skipped. Error messages
    are Vietnamese and PII-free.
    """

    if quantity is None:
        return
    if not isinstance(quantity, (int, float)) or isinstance(quantity, bool):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Số lượng không hợp lệ",
        )
    if not math.isfinite(quantity):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Số lượng không hợp lệ",
        )
    if quantity < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Số lượng phải là số không âm",
        )
    if quantity > _MAX_CABINET_QUANTITY:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Số lượng vượt quá giới hạn cho phép",
        )


def _validate_cabinet_expiry(expires_on: datetime | None) -> None:
    """Reject an expiry date far outside any plausible range (Req 1.7).

    Pydantic already guarantees a well-formed ``datetime``; here we only reject
    dates absurdly far in the past or future. A naive datetime is interpreted as
    UTC for comparison. ``None`` (no expiry data) is always allowed (Req 10.5).
    """

    if expires_on is None:
        return
    moment = expires_on if expires_on.tzinfo is not None else expires_on.replace(tzinfo=UTC)
    if moment < _MIN_EXPIRY_DATE or moment > _MAX_EXPIRY_DATE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Ngày hết hạn không hợp lệ",
        )


def _apply_ocr_correction(text: str) -> OcrCorrectionResult:
    bounded_text = str(text or "")[:OCR_CORRECTION_MAX_CHARS]
    return correct_ocr_text(
        bounded_text,
        vocabulary=OCR_DRUG_VOCABULARY,
        cutoff=OCR_CORRECTION_CUTOFF,
        max_events=24,
    )


def _normalize_prescription_ocr_text(text: str) -> str:
    normalized = " ".join(str(text or "").split())
    lowered = normalized.lower()
    for raw, replacement in _OCR_NOISY_REPLACEMENTS:
        lowered = lowered.replace(raw, replacement)
    lowered = lowered.replace("μg", "mcg")
    return lowered


def _extract_dosage_near_alias(text: str, alias: str) -> str:
    lowered = str(text or "").lower()
    alias_norm = str(alias or "").strip().lower()
    if not lowered or not alias_norm:
        return ""
    match = re.search(re.escape(alias_norm), lowered)
    if not match:
        return ""
    start = max(0, match.start() - 28)
    end = min(len(lowered), match.end() + 42)
    window = lowered[start:end]
    dosage_match = re.search(r"\b\d+(?:[.,]\d+)?\s*(mg|g|mcg|ml|iu|%)\b", window)
    if dosage_match:
        return dosage_match.group(0).strip()
    return ""


def _build_prioritized_fields(
    detections: list[CabinetScanDetection],
) -> list[CabinetPrioritizedField]:
    rows: list[CabinetPrioritizedField] = []
    for detection in detections:
        rows.append(
            CabinetPrioritizedField(
                drug_name=detection.drug_name,
                brand_name=detection.brand_name or "",
                manufacturer=detection.manufacturer or "",
                dosage=detection.dosage or "",
            )
        )
    return rows


def _normalize_ocr_token_for_fuzzy_match(token: str) -> str:
    normalized = _ascii_fold(_normalize_text(token))
    normalized = normalized.replace("rn", "m").replace("vv", "w")
    for src, dst in _OCR_NOISY_CHAR_REPLACEMENTS:
        normalized = normalized.replace(src, dst)
    return re.sub(r"[^a-z0-9]+", "", normalized)


def _compute_ocr_fuzzy_score(token: str, alias: str) -> float:
    raw_score = SequenceMatcher(None, token, alias.lower()).ratio()
    normalized_token = _normalize_ocr_token_for_fuzzy_match(token)
    normalized_alias = _normalize_ocr_token_for_fuzzy_match(alias)
    if not normalized_token or not normalized_alias:
        return raw_score
    normalized_score = SequenceMatcher(None, normalized_token, normalized_alias).ratio()
    return max(raw_score, normalized_score)


def _detect_drugs_from_text(
    text: str,
    db: Session | None = None,
    *,
    skip_ocr_correction: bool = False,
) -> list[CabinetScanDetection]:
    candidate_text = text if skip_ocr_correction else _apply_ocr_correction(text).corrected_text
    normalized_text = _normalize_prescription_ocr_text(candidate_text)
    detections: list[CabinetScanDetection] = []
    detected_normalized_names: set[str] = set()
    manufacturer_hint = _infer_manufacturer_from_text(normalized_text)

    for canonical, aliases in DRUG_ALIAS_MAP.items():
        for alias in aliases:
            escaped_alias = re.escape(alias)
            pattern = rf"(^|[^a-z0-9]){escaped_alias}([^a-z0-9]|$)"
            if not re.search(pattern, normalized_text, flags=re.IGNORECASE):
                continue

            display_name, normalized_name, _rx_cui, mapping_source, mapping_confidence = (
                _resolve_dictionary_mapping_with_source(canonical, db=db)
            )
            if normalized_name in detected_normalized_names:
                break
            confidence = 0.94 if alias == canonical else 0.82
            dosage = _extract_dosage_near_alias(normalized_text, alias)
            if dosage:
                confidence = min(0.97, confidence + 0.04)
            requires_manual_confirm = confidence < LOW_CONFIDENCE_OCR_THRESHOLD
            detections.append(
                CabinetScanDetection(
                    drug_name=display_name,
                    normalized_name=normalized_name,
                    dosage=dosage or None,
                    brand_name=_infer_brand_name(
                        alias=alias,
                        canonical=canonical,
                        display_name=display_name,
                    )
                    or None,
                    manufacturer=manufacturer_hint or None,
                    confidence=confidence,
                    evidence=alias,
                    mapping_source=mapping_source,
                    mapping_confidence=mapping_confidence,
                    normalization_status=_derive_normalization_status(
                        mapping_source, mapping_confidence
                    ),
                    requires_manual_confirm=requires_manual_confirm,
                    confirmed=not requires_manual_confirm,
                )
            )
            detected_normalized_names.add(normalized_name)
            break

    # Handwriting/noisy fallback: attempt fuzzy single-token matching.
    token_candidates = [
        token
        for token in re.split(r"[^a-z0-9+]+", normalized_text)
        if len(token) >= 4
        and token not in _OCR_FUZZY_STOPWORDS
        and sum(char.isalpha() for char in token) >= 3
    ]
    fuzzy_threshold = 0.9 if detections else 0.86
    fuzzy_limit = 2 if detections else 4
    fuzzy_added = 0
    for token in token_candidates[:120]:
        if fuzzy_added >= fuzzy_limit:
            break
        best_canonical = ""
        best_alias = ""
        best_score = 0.0
        for canonical, aliases in DRUG_ALIAS_MAP.items():
            for alias in aliases:
                score = _compute_ocr_fuzzy_score(token, alias)
                if score > best_score:
                    best_score = score
                    best_canonical = canonical
                    best_alias = alias
        if best_score < fuzzy_threshold or not best_canonical:
            continue
        display_name, normalized_name, _rx_cui, mapping_source, mapping_confidence = (
            _resolve_dictionary_mapping_with_source(best_canonical, db=db)
        )
        if normalized_name in detected_normalized_names:
            continue
        detection_confidence = max(0.58, min(0.78, best_score))
        detections.append(
            CabinetScanDetection(
                drug_name=display_name,
                normalized_name=normalized_name,
                dosage=_extract_dosage_near_alias(normalized_text, best_alias) or None,
                brand_name=_infer_brand_name(
                    alias=best_alias,
                    canonical=best_canonical,
                    display_name=display_name,
                )
                or None,
                manufacturer=manufacturer_hint or None,
                confidence=detection_confidence,
                evidence=f"fuzzy:{token}->{best_alias}",
                mapping_source=mapping_source,
                mapping_confidence=mapping_confidence,
                normalization_status=_derive_normalization_status(
                    mapping_source, mapping_confidence
                ),
                requires_manual_confirm=True,
                confirmed=False,
            )
        )
        detected_normalized_names.add(normalized_name)
        fuzzy_added += 1

    detections.sort(key=lambda item: (-item.confidence, item.drug_name))
    return detections


def _enforce_low_confidence_manual_confirm(
    detections: list[CabinetScanDetection],
) -> list[CabinetScanDetection]:
    enforced: list[CabinetScanDetection] = []
    for detection in detections:
        requires_manual_confirm = (
            detection.requires_manual_confirm or detection.confidence < LOW_CONFIDENCE_OCR_THRESHOLD
        )
        if requires_manual_confirm:
            enforced.append(
                detection.model_copy(
                    update={
                        "requires_manual_confirm": True,
                        "confirmed": False,
                    }
                )
            )
            continue
        enforced.append(
            detection.model_copy(
                update={
                    "requires_manual_confirm": False,
                    "confirmed": True,
                }
            )
        )
    return enforced


def _build_ocr_confirm_gate(detections: list[CabinetScanDetection]) -> OcrConfirmGate:
    """Summarize the low-confidence OCR manual-confirm gate for clients (Req 2.2, 2.6).

    Pure projection over already-enforced detections: counts how many require
    manual confirmation, how many are confirmed, and how many normalized to a
    ``needs_review`` status. Surfaces the active ``LOW_CONFIDENCE_OCR_THRESHOLD``
    so the UI can render the confirm gate explicitly before import.
    """

    requires_confirmation = 0
    confirmed = 0
    needs_review = 0
    for detection in detections:
        gated = (
            detection.requires_manual_confirm
            or detection.confidence < LOW_CONFIDENCE_OCR_THRESHOLD
        )
        if gated:
            requires_confirmation += 1
        if detection.confirmed:
            confirmed += 1
        if detection.normalization_status == "needs_review":
            needs_review += 1
    return OcrConfirmGate(
        threshold=LOW_CONFIDENCE_OCR_THRESHOLD,
        total_detections=len(detections),
        requires_confirmation=requires_confirmation,
        confirmed=confirmed,
        needs_review=needs_review,
    )


def _parse_ocr_endpoints(raw: str) -> list[str]:
    entries = [entry.strip() for entry in raw.split(",")]
    return [entry if entry.startswith("/") else f"/{entry}" for entry in entries if entry]


def _collect_text_candidates(payload: Any) -> list[str]:
    candidates: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            text = value.strip()
            if len(text) >= 2:
                candidates.append(text)
            return

        if isinstance(value, list):
            for item in value:
                walk(item)
            return

        if not isinstance(value, dict):
            return

        for key, nested in value.items():
            lowered = key.lower()
            if lowered in {
                "text",
                "ocr_text",
                "full_text",
                "plain_text",
                "combined_ocr",
                "content",
            }:
                walk(nested)
                continue
            if lowered == "lines" and isinstance(nested, list):
                lines = [line.strip() for line in nested if isinstance(line, str) and line.strip()]
                if lines:
                    candidates.append("\n".join(lines))
                continue
            if lowered in {"chunks", "items", "elements", "fields"} and isinstance(nested, list):
                for item in nested:
                    if isinstance(item, dict):
                        for inner_key in ("text", "value"):
                            inner_value = item.get(inner_key)
                            if isinstance(inner_value, str) and inner_value.strip():
                                candidates.append(inner_value.strip())
                continue
            walk(nested)

    walk(payload)
    return candidates


def _extract_ocr_text(payload: Any) -> str:
    raw_candidates = _collect_text_candidates(payload)
    unique_candidates: list[str] = []
    seen: set[str] = set()
    for candidate in raw_candidates:
        normalized = _normalize_text(candidate)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_candidates.append(candidate.strip())

    if not unique_candidates:
        return ""

    unique_candidates.sort(key=lambda value: len(value), reverse=True)
    longest = unique_candidates[0]
    if len(longest) >= 120:
        return longest
    return "\n".join(unique_candidates[:20]).strip()


def _post_tgc_ocr_multipart(
    url: str,
    file_bytes: bytes,
    file_name: str,
    content_type: str,
    timeout_seconds: float,
    headers: dict[str, str],
    field_name: str = "file",
) -> httpx.Response:
    files = {field_name: (file_name, file_bytes, content_type)}
    return httpx.post(url, files=files, headers=headers, timeout=timeout_seconds)


def _post_tgc_ocr_json(
    url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
    headers: dict[str, str],
) -> httpx.Response:
    return httpx.post(url, json=payload, headers=headers, timeout=timeout_seconds)


def _build_tgc_ocr_json_payloads(
    file_bytes: bytes,
    file_name: str,
    content_type: str,
) -> list[dict[str, Any]]:
    encoded = base64.b64encode(file_bytes).decode("utf-8")
    return [
        {"image": encoded, "lang": "vi"},
        {"image_base64": encoded, "lang": "vi"},
        {"file": encoded, "lang": "vi"},
        {"base64": encoded, "mime_type": content_type, "filename": file_name, "lang": "vi"},
        {"content": encoded, "content_type": content_type, "filename": file_name, "lang": "vi"},
    ]


def _scan_with_google_vision(
    file_bytes: bytes,
) -> tuple[str, str, str] | None:
    """Try Google Cloud Vision OCR. Returns (text, endpoint, provider) or None on failure."""
    settings = get_settings()
    if not settings.google_vision_enabled:
        return None
    api_key = settings.google_vision_api_key.strip()
    sa_json = settings.google_vision_service_account_json.strip()
    # Need at least one credential path (simple API key OR a service account).
    if not api_key and not sa_json:
        return None
    try:
        from clara_api.core.google_vision_ocr import (
            detect_text,
            detect_text_with_api_key,
        )

        language_hints = [
            lang.strip()
            for lang in settings.google_vision_language_hints.split(",")
            if lang.strip()
        ] or ["vi", "en"]
        # Prefer the simple API-key path when a key is configured (no billing-
        # coupled OAuth service-account exchange); fall back to the SA JWT path.
        if api_key:
            text = detect_text_with_api_key(
                image_bytes=file_bytes,
                api_key=api_key,
                language_hints=language_hints,
                timeout_seconds=settings.google_vision_timeout_seconds,
            )
        else:
            text = detect_text(
                image_bytes=file_bytes,
                service_account_json=sa_json,
                language_hints=language_hints,
                timeout_seconds=settings.google_vision_timeout_seconds,
            )
        if text and len(text.strip()) >= 3:
            return text.strip(), "/v1/images:annotate", "google-cloud-vision"
    except Exception:
        pass
    return None


def _scan_with_tesseract(
    file_bytes: bytes,
) -> tuple[str, str, str] | None:
    """Try local Tesseract OCR. Returns (text, endpoint, provider) or None on failure."""
    settings = get_settings()
    if not settings.tesseract_ocr_enabled:
        return None
    try:
        from clara_api.core.tesseract_ocr import detect_text

        text = detect_text(
            image_bytes=file_bytes,
            languages=settings.tesseract_ocr_languages,
            psm=settings.tesseract_ocr_psm,
        )
        if text and len(text.strip()) >= 3:
            return text.strip(), "local-tesseract", "tesseract-ocr"
    except Exception:
        pass
    return None


def _scan_with_tgc_ocr(
    file_bytes: bytes,
    file_name: str,
    content_type: str,
) -> tuple[str, str, str]:
    # Try Google Vision first if configured
    google_result = _scan_with_google_vision(file_bytes)
    if google_result is not None:
        return google_result

    # Try local Tesseract OCR if enabled
    tesseract_result = _scan_with_tesseract(file_bytes)
    if tesseract_result is not None:
        return tesseract_result

    settings = get_settings()
    endpoints = _parse_ocr_endpoints(settings.tgc_ocr_endpoints)
    if not endpoints:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Chưa cấu hình TGC_OCR_ENDPOINTS",
        )

    base_url = settings.tgc_ocr_base_url.rstrip("/")
    headers: dict[str, str] = {}
    api_key = settings.tgc_ocr_api_key.strip()
    if api_key:
        # Shared TGC OCR service may accept either x-api-key or Bearer auth.
        headers["x-api-key"] = api_key
        headers["authorization"] = f"Bearer {api_key}"

    last_error = "Không lấy được văn bản OCR từ TGC service"
    for endpoint in endpoints:
        url = f"{base_url}{endpoint}"
        response: httpx.Response | None = None
        request_succeeded = False

        # Try common multipart field names used by OCR providers.
        for field_name in ("file", "image", "document", "upload_file"):
            try:
                response = _post_tgc_ocr_multipart(
                    url=url,
                    file_bytes=file_bytes,
                    file_name=file_name,
                    content_type=content_type,
                    timeout_seconds=settings.tgc_ocr_timeout_seconds,
                    headers=headers,
                    field_name=field_name,
                )
            except (httpx.ConnectError, httpx.NetworkError, httpx.TimeoutException) as exc:
                last_error = f"Không kết nối được OCR service: {exc.__class__.__name__}"
                response = None
                break
            except httpx.HTTPError as exc:
                last_error = f"OCR request lỗi: {exc}"
                response = None
                break

            if response.status_code < 400:
                request_succeeded = True
                break
            if response.status_code >= 500:
                last_error = f"OCR upstream error: status={response.status_code}"
                response = None
                break
            if response.status_code not in {400, 405, 415, 422}:
                last_error = f"OCR endpoint từ chối request: status={response.status_code}"
                response = None
                break

        # Some deployments expose /ocr as JSON(base64) instead of multipart.
        if (not request_succeeded) and endpoint.endswith("/ocr"):
            for payload in _build_tgc_ocr_json_payloads(
                file_bytes=file_bytes,
                file_name=file_name,
                content_type=content_type,
            ):
                try:
                    response = _post_tgc_ocr_json(
                        url=url,
                        payload=payload,
                        timeout_seconds=settings.tgc_ocr_timeout_seconds,
                        headers=headers,
                    )
                except (httpx.ConnectError, httpx.NetworkError, httpx.TimeoutException) as exc:
                    last_error = f"Không kết nối được OCR service: {exc.__class__.__name__}"
                    response = None
                    break
                except httpx.HTTPError as exc:
                    last_error = f"OCR request lỗi: {exc}"
                    response = None
                    break

                if response.status_code < 400:
                    request_succeeded = True
                    break
                if response.status_code >= 500:
                    last_error = f"OCR upstream error: status={response.status_code}"
                    response = None
                    break
                if response.status_code not in {400, 405, 415, 422}:
                    last_error = f"OCR endpoint từ chối request: status={response.status_code}"
                    response = None
                    break

        if response is None or not request_succeeded:
            continue

        try:
            payload = response.json()
        except ValueError:
            last_error = "OCR endpoint trả về JSON không hợp lệ"
            continue

        extracted_text = _extract_ocr_text(payload)
        if not extracted_text:
            last_error = "OCR endpoint không trả về text hữu ích"
            continue

        return extracted_text, endpoint, "tgc-transhub"

    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=last_error)


def _verify_careguard_ocr_upload(
    *, file_name: str, content_type: str, file_bytes: bytes
) -> VerifiedUpload:
    """Fail closed before a medication image leaves the API boundary.

    Cabinet OCR historically called its providers immediately after a byte-size
    check. That accepted a client-claimed MIME type and bypassed the shared
    malware policy used by PHR and Research uploads. The OCR provider must only
    receive a file whose bytes, filename and declared media type agree; when a
    configured malware scanner cannot return a clean verdict, no provider call
    is made.
    """

    settings = get_settings()
    try:
        return verify_upload(
            filename=file_name,
            content_type=content_type,
            data=file_bytes,
            fallback_filename="medication-label",
            malware_scan_required=settings.upload_malware_scan_required,
            clamav_host=settings.upload_malware_clamav_host,
            clamav_port=settings.upload_malware_clamav_port,
        )
    except UploadMalwareScannerUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không thể kiểm tra an toàn tệp lúc này. Vui lòng thử lại sau.",
        ) from exc
    except UploadSafetyError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Tệp tải lên không khớp định dạng được phép.",
        ) from exc


@router.get("/cabinet", response_model=MedicineCabinetResponse)
def get_cabinet(
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> MedicineCabinetResponse:
    user = _require_user(token, db)
    cabinet = _get_or_create_cabinet(db, user.id)
    items = (
        db.execute(
            select(MedicineItem)
            .where(MedicineItem.cabinet_id == cabinet.id)
            .order_by(MedicineItem.updated_at.desc(), MedicineItem.id.desc())
        )
        .scalars()
        .all()
    )
    resolved_items = []
    for item in items:
        _, _, _, mapping_source, mapping_confidence = _resolve_dictionary_mapping_with_source(
            item.drug_name,
            db=db,
        )
        resolved_items.append(
            _to_item_response(
                item,
                normalization_source=mapping_source,
                normalization_confidence=mapping_confidence,
            )
        )
    return MedicineCabinetResponse(
        cabinet_id=cabinet.id,
        label=cabinet.label,
        items=resolved_items,
        expiry_summary=CabinetExpirySummary(
            expired_count=sum(
                1 for entry in resolved_items if entry.expiry_status == "expired"
            ),
            expiring_soon_count=sum(
                1 for entry in resolved_items if entry.expiry_status == "expiring_soon"
            ),
            expiry_window_days=EXPIRY_SOON_WINDOW_DAYS,
        ),
    )


@router.post("/cabinet/items", response_model=MedicineCabinetItemResponse)
def add_cabinet_item(
    payload: MedicineCabinetItemCreate,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> MedicineCabinetItemResponse:
    user = _require_user(token, db)
    cabinet = _get_or_create_cabinet(db, user.id)

    _validate_cabinet_quantity(payload.quantity)
    _validate_cabinet_expiry(payload.expires_on)

    _, normalized, mapped_rxcui, mapping_source, mapping_confidence = (
        _resolve_dictionary_mapping_with_source(
            payload.drug_name,
            db=db,
        )
    )
    existing = db.execute(
        select(MedicineItem).where(
            MedicineItem.cabinet_id == cabinet.id,
            MedicineItem.normalized_name == normalized,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Thuốc đã tồn tại trong tủ thuốc",
        )

    item = MedicineItem(
        cabinet_id=cabinet.id,
        drug_name=payload.drug_name.strip(),
        normalized_name=normalized,
        dosage=payload.dosage.strip(),
        dosage_form=payload.dosage_form.strip(),
        quantity=payload.quantity,
        source=payload.source,
        rx_cui=payload.rx_cui.strip() or mapped_rxcui,
        ocr_confidence=payload.ocr_confidence,
        expires_on=payload.expires_on,
        updated_at=datetime.now(tz=UTC),
    )
    # Dual-write (Req 1.2, 1.3): when SELFMED_CABINET_STRUCTURED_FIELDS_ENABLED
    # is on, persist brand/manufacturer in first-class columns and store a clean
    # note; when off, reproduce the legacy ``[meta]`` note encoding byte-for-byte
    # and leave the structured columns null.
    if get_settings().selfmed_cabinet_structured_fields_enabled:
        item.brand_name = _sanitize_meta_value(payload.brand_name) or None
        item.manufacturer = _sanitize_meta_value(payload.manufacturer) or None
        item.note = payload.note.strip()
    else:
        item.note = _encode_item_note(
            payload.note.strip(),
            brand_name=payload.brand_name,
            manufacturer=payload.manufacturer,
        )
    # Reminder-state persistence (Req 10.3) is gated on
    # SELFMED_EXPIRY_REMINDERS_ENABLED; when off the field is ignored and no
    # state is persisted, matching today's behavior (Req 10.4).
    if (
        get_settings().selfmed_expiry_reminders_enabled
        and payload.expiry_reminder is not None
    ):
        item.expiry_reminder_json = payload.expiry_reminder
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_item_response(
        item,
        normalization_source=mapping_source,
        normalization_confidence=mapping_confidence,
    )


@router.patch("/cabinet/items/{item_id}", response_model=MedicineCabinetItemResponse)
@router.put("/cabinet/items/{item_id}", response_model=MedicineCabinetItemResponse)
def update_cabinet_item(
    item_id: int,
    payload: MedicineCabinetItemUpdate,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> MedicineCabinetItemResponse:
    user = _require_user(token, db)
    cabinet = _get_or_create_cabinet(db, user.id)
    item = db.execute(
        select(MedicineItem).where(
            MedicineItem.id == item_id,
            MedicineItem.cabinet_id == cabinet.id,
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy thuốc")

    provided = set(payload.model_fields_set)
    if not provided:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload cập nhật rỗng",
        )

    response_mapping_source: str | None = None
    response_mapping_confidence: float | None = None
    # Dual-read effective brand/manufacturer (Req 1.4): structured columns win
    # when set, else fall back to the decoded legacy ``[meta]`` note so updates
    # never drop data written under either scheme.
    note_value, note_brand, note_manufacturer = _decode_item_note(item.note)
    brand_value = item.brand_name if item.brand_name is not None else note_brand
    manufacturer_value = (
        item.manufacturer if item.manufacturer is not None else note_manufacturer
    )

    if "drug_name" in provided:
        if payload.drug_name is None or not payload.drug_name.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Tên thuốc không hợp lệ",
            )
        updated_name = payload.drug_name.strip()
        _, normalized_name, mapped_rxcui, mapping_source, mapping_confidence = (
            _resolve_dictionary_mapping_with_source(updated_name, db=db)
        )
        duplicate = db.execute(
            select(MedicineItem).where(
                MedicineItem.cabinet_id == cabinet.id,
                MedicineItem.normalized_name == normalized_name,
                MedicineItem.id != item.id,
            )
        ).scalar_one_or_none()
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Thuốc đã tồn tại trong tủ thuốc",
            )
        item.drug_name = updated_name
        item.normalized_name = normalized_name
        response_mapping_source = mapping_source
        response_mapping_confidence = mapping_confidence
        if "rx_cui" not in provided:
            item.rx_cui = mapped_rxcui

    if "dosage" in provided:
        item.dosage = (payload.dosage or "").strip()
    if "dosage_form" in provided:
        item.dosage_form = (payload.dosage_form or "").strip()
    if "quantity" in provided:
        if payload.quantity is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Số lượng không hợp lệ",
            )
        _validate_cabinet_quantity(payload.quantity)
        item.quantity = payload.quantity
    if "source" in provided:
        if payload.source is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Nguồn nhập thuốc không hợp lệ",
            )
        item.source = payload.source
    if "rx_cui" in provided:
        rx_cui = (payload.rx_cui or "").strip()
        if rx_cui:
            item.rx_cui = rx_cui
        elif "drug_name" in provided:
            _, _, mapped_rxcui = _resolve_dictionary_mapping(item.drug_name, db=db)
            item.rx_cui = mapped_rxcui
        else:
            item.rx_cui = ""
    if "ocr_confidence" in provided:
        item.ocr_confidence = payload.ocr_confidence
    if "expires_on" in provided:
        _validate_cabinet_expiry(payload.expires_on)
        item.expires_on = payload.expires_on
    # Reminder-state persistence (Req 10.3): only mutate ``expiry_reminder_json``
    # when SELFMED_EXPIRY_REMINDERS_ENABLED is on. When off, the field is
    # silently ignored (no persistence), matching today's behavior (Req 10.4).
    if "expiry_reminder" in provided and get_settings().selfmed_expiry_reminders_enabled:
        item.expiry_reminder_json = payload.expiry_reminder
    if "note" in provided:
        note_value = (payload.note or "").strip()
    if "brand_name" in provided:
        brand_value = _sanitize_meta_value(payload.brand_name or "") or None
    if "manufacturer" in provided:
        manufacturer_value = _sanitize_meta_value(payload.manufacturer or "") or None
    # Dual-write (Req 1.2, 1.3): structured columns + clean note when the flag is
    # on; legacy ``[meta]`` note encoding (byte-for-byte) when off.
    if get_settings().selfmed_cabinet_structured_fields_enabled:
        item.brand_name = brand_value
        item.manufacturer = manufacturer_value
        item.note = note_value
    else:
        item.note = _encode_item_note(
            note_value,
            brand_name=brand_value or "",
            manufacturer=manufacturer_value or "",
        )

    item.updated_at = datetime.now(tz=UTC)
    db.add(item)
    db.commit()
    db.refresh(item)
    if response_mapping_source is None or response_mapping_confidence is None:
        _, _, _, response_mapping_source, response_mapping_confidence = (
            _resolve_dictionary_mapping_with_source(
                item.drug_name,
                db=db,
            )
        )
    return _to_item_response(
        item,
        normalization_source=response_mapping_source,
        normalization_confidence=response_mapping_confidence,
    )


@router.delete("/cabinet/items/{item_id}")
def delete_cabinet_item(
    item_id: int,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    user = _require_user(token, db)
    cabinet = _get_or_create_cabinet(db, user.id)
    item = db.execute(
        select(MedicineItem).where(
            MedicineItem.id == item_id,
            MedicineItem.cabinet_id == cabinet.id,
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy thuốc")

    db.delete(item)
    db.commit()
    return {"deleted": True}


_CAPTURE_INJECTION = re.compile(
    r"(ignore (all|previous|prior) instructions|system prompt|developer message|"
    r"jailbreak|do anything now|b[oỏ] qua (mọi|tất cả) (chỉ dẫn|hướng dẫn)|"
    r"bo qua (moi|tat ca) (chi dan|huong dan))",
    re.IGNORECASE,
)


def _capture_span(text: str, value: str) -> dict[str, int] | None:
    if not value or value == "unknown":
        return None
    start = text.casefold().find(value.casefold())
    if start < 0:
        return None
    return {"start": start, "end": start + len(value)}


def _attach_ocr_source_coordinates(
    detections: list[CabinetScanDetection], *, corrected_text: str
) -> list[CabinetScanDetection]:
    """Attach exact, reviewable OCR text offsets without inventing image boxes."""

    annotated: list[CabinetScanDetection] = []
    for detection in detections:
        evidence = (detection.evidence or "").strip()
        # Fuzzy evidence is a diagnostic label (``fuzzy:x->y``), not an OCR
        # span. Prefer the observed token; otherwise do not claim a location.
        if evidence.startswith("fuzzy:"):
            observed = evidence[6:].split("->", 1)[0].strip()
            probe = observed
        else:
            probe = evidence
        span = _capture_span(corrected_text, probe)
        coordinates: list[OcrSourceCoordinate] = (
            [
                OcrSourceCoordinate(
                    coordinate_system="corrected_text_codepoint_offset",
                    start=span["start"],
                    end=span["end"],
                )
            ]
            if span is not None
            else []
        )
        annotated.append(detection.model_copy(update={"source_coordinates": coordinates}))
    return annotated


def _reject_ocr_prompt_injection(source_text: str) -> None:
    """Fail closed before OCR text becomes an extraction/model instruction."""

    if _CAPTURE_INJECTION.search(source_text or ""):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "ocr_prompt_injection_suspected",
                "message": "Nội dung OCR có chỉ dẫn không an toàn; không thể trích xuất thuốc.",
            },
        )


def _persist_cabinet_capture_drafts(
    db: Session,
    *,
    user: User,
    source_text: str,
    detections: list[CabinetScanDetection],
    extractor_version: str,
) -> tuple[str, list[CabinetScanDetection]]:
    """Mirror OCR rows into profile-scoped Capture drafts, never truth."""

    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        profile = PhrProfile(user_id=user.id)
        db.add(profile)
        db.flush()
    now = datetime.now(UTC)
    session = LifeMapCaptureSession(
        profile_id=profile.id,
        created_by_user_id=user.id,
        input_kind="medication_label",
        schema_version="lifemap.capture.v1",
        locale="vi",
        expires_at=now + timedelta(days=7),
    )
    db.add(session)
    db.flush()
    mirrored: list[CabinetScanDetection] = []
    findings = (
        ["prompt_injection_source"] if _CAPTURE_INJECTION.search(source_text) else []
    )
    for detection in detections:
        strength = (detection.dosage or "").strip() or "unknown"
        value = {
            "medication_name": detection.drug_name.strip(),
            "strength": strength,
            "route": "unknown",
        }
        spans = {
            field: span
            for field, span in {
                "medication_name": _capture_span(
                    source_text, value["medication_name"]
                ),
                "strength": _capture_span(source_text, strength),
            }.items()
            if span is not None
        }
        field_confidence = {
            "medication_name": detection.confidence,
            "strength": detection.confidence if strength != "unknown" else 0.0,
            "route": 0.0,
        }
        candidate = LifeMapCaptureCandidate(
            session_id=session.id,
            profile_id=profile.id,
            candidate_type="medication_label",
            field_path="medication_label",
            value_json=value,
            confidence=min(field_confidence.values()),
            field_confidence_json=field_confidence,
            source_span_json={
                "kind": "text_fields",
                "fields": spans,
                "source": "careguard_ocr",
            },
            missing_critical_fields_json=[],
            extraction_schema_version="lifemap.capture.v1",
            extractor_version=extractor_version[:96],
            security_findings_json=findings,
            status="draft",
        )
        db.add(candidate)
        db.flush()
        mirrored.append(
            detection.model_copy(
                update={
                    "capture_candidate_id": candidate.public_id,
                    "requires_manual_confirm": True,
                    "confirmed": False,
                }
            )
        )
    write_audit(
        db,
        profile_id=profile.id,
        action="create",
        entity="capture_session",
        entity_id=session.public_id,
        actor_user_id=user.id,
        scope="owner:self_care",
    )
    return session.public_id, mirrored


@router.post("/cabinet/scan-text", response_model=CabinetScanTextResponse)
def scan_cabinet_text(
    payload: CabinetScanTextRequest,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> CabinetScanTextResponse:
    user = _require_user(token, db)
    correction = _apply_ocr_correction(payload.text)
    _reject_ocr_prompt_injection(correction.corrected_text)
    detections = _enforce_low_confidence_manual_confirm(
        _detect_drugs_from_text(
            correction.corrected_text,
            db=db,
            skip_ocr_correction=True,
        )
    )
    detections = _attach_ocr_source_coordinates(
        detections, corrected_text=correction.corrected_text
    )
    capture_session_id: str | None = None
    if get_settings().lifemap_capture_enabled:
        ensure_medical_disclaimer_consent(db, user_id=user.id)
        capture_session_id, detections = _persist_cabinet_capture_drafts(
            db,
            user=user,
            source_text=correction.corrected_text,
            detections=detections,
            extractor_version="careguard-ocr-postprocess-v1",
        )
        db.commit()
    return CabinetScanTextResponse(
        detections=detections,
        extracted_text=correction.corrected_text[:4000],
        ocr_provider="ocr-postprocess",
        ocr_endpoint="local-ocr-correction",
        prioritized_fields=_build_prioritized_fields(detections),
        confirm_gate=_build_ocr_confirm_gate(detections),
        capture_session_id=capture_session_id,
    )


@router.post("/cabinet/scan-file", response_model=CabinetScanTextResponse)
async def scan_cabinet_file(
    file: UploadFile = File(...),
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> CabinetScanTextResponse:
    user = _require_user(token, db)
    file_name = file.filename or "uploaded-receipt"
    content_type = file.content_type or "application/octet-stream"
    file_bytes = await read_upload_bytes_with_limit(file, max_bytes=20 * 1024 * 1024)
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File upload rỗng")
    verified_upload = _verify_careguard_ocr_upload(
        file_name=file_name,
        content_type=content_type,
        file_bytes=file_bytes,
    )
    file_name = verified_upload.filename
    content_type = verified_upload.media_type

    extracted_text, used_endpoint, ocr_provider = _scan_with_tgc_ocr(
        file_bytes=file_bytes,
        file_name=file_name,
        content_type=content_type,
    )
    correction = _apply_ocr_correction(extracted_text)
    _reject_ocr_prompt_injection(correction.corrected_text)
    detections = _enforce_low_confidence_manual_confirm(
        _detect_drugs_from_text(
            correction.corrected_text,
            db=db,
            skip_ocr_correction=True,
        )
    )
    detections = _attach_ocr_source_coordinates(
        detections, corrected_text=correction.corrected_text
    )
    capture_session_id: str | None = None
    if get_settings().lifemap_capture_enabled:
        ensure_medical_disclaimer_consent(db, user_id=user.id)
        capture_session_id, detections = _persist_cabinet_capture_drafts(
            db,
            user=user,
            source_text=correction.corrected_text,
            detections=detections,
            extractor_version=f"careguard-{ocr_provider}-v1",
        )
        db.commit()
    return CabinetScanTextResponse(
        detections=detections,
        extracted_text=correction.corrected_text[:4000],
        ocr_provider=ocr_provider,
        ocr_endpoint=used_endpoint,
        prioritized_fields=_build_prioritized_fields(detections),
        confirm_gate=_build_ocr_confirm_gate(detections),
        capture_session_id=capture_session_id,
    )


@router.post("/cabinet/import-detections", response_model=CabinetImportResponse)
def import_detections(
    payload: CabinetImportRequest,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> CabinetImportResponse:
    user = _require_user(token, db)
    cabinet = _get_or_create_cabinet(db, user.id)
    capture_candidates: dict[str, LifeMapCaptureCandidate] = {}
    profile: PhrProfile | None = None
    if get_settings().lifemap_capture_enabled:
        ensure_medical_disclaimer_consent(db, user_id=user.id)
        profile = db.execute(
            select(PhrProfile).where(PhrProfile.user_id == user.id)
        ).scalar_one_or_none()
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "health_profile_required"},
            )
        candidate_ids = [
            str(item.capture_candidate_id or "") for item in payload.detections
        ]
        if any(not candidate_id for candidate_id in candidate_ids):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "capture_candidate_required"},
            )
        rows = list(
            db.execute(
                select(LifeMapCaptureCandidate).where(
                    LifeMapCaptureCandidate.public_id.in_(candidate_ids),
                    LifeMapCaptureCandidate.profile_id == profile.id,
                )
            ).scalars()
        )
        capture_candidates = {row.public_id: row for row in rows}
        if len(capture_candidates) != len(set(candidate_ids)):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "capture_candidate_not_found"},
            )
        for detection in payload.detections:
            candidate = capture_candidates[str(detection.capture_candidate_id)]
            candidate_name = str(
                (candidate.value_json or {}).get("medication_name", "")
            ).strip()
            candidate_strength = str(
                (candidate.value_json or {}).get("strength", "")
            ).strip()
            expected_strength = (detection.dosage or "").strip() or "unknown"
            if (
                candidate.status != "draft"
                or candidate.security_findings_json
                or not detection.confirmed
                or candidate_name.casefold() != detection.drug_name.strip().casefold()
                or candidate_strength.casefold() != expected_strength.casefold()
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"code": "capture_candidate_review_mismatch"},
                )

    existing_names = set(
        db.execute(
            select(MedicineItem.normalized_name).where(MedicineItem.cabinet_id == cabinet.id)
        )
        .scalars()
        .all()
    )

    blocked_unconfirmed: list[dict[str, Any]] = []
    for index, detection in enumerate(payload.detections):
        needs_manual_confirm = (
            detection.requires_manual_confirm or detection.confidence < LOW_CONFIDENCE_OCR_THRESHOLD
        )
        if needs_manual_confirm and not detection.confirmed:
            blocked_unconfirmed.append(
                {
                    "index": index,
                    "drug_name": detection.drug_name,
                    "normalized_name": detection.normalized_name,
                    "confidence": detection.confidence,
                    "evidence": detection.evidence,
                    "reason": "manual_confirm_required_for_low_confidence_detection",
                }
            )

    if blocked_unconfirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "manual_confirmation_required",
                "message": (
                    "Có phát hiện OCR độ tin cậy thấp chưa được xác nhận thủ công. "
                    "Vui lòng đánh dấu confirmed=true cho các mục này trước khi import."
                ),
                "threshold": LOW_CONFIDENCE_OCR_THRESHOLD,
                "blocked_detections": blocked_unconfirmed,
            },
        )

    inserted = 0
    prioritized_fields: list[CabinetPrioritizedField] = []
    for detection in payload.detections:
        _, normalized, mapped_rxcui, _mapping_source, _mapping_confidence = (
            _resolve_dictionary_mapping_with_source(
                detection.normalized_name or detection.drug_name,
                db=db,
            )
        )
        if not normalized or normalized in existing_names:
            continue
        item = MedicineItem(
            cabinet_id=cabinet.id,
            drug_name=detection.drug_name.strip(),
            normalized_name=normalized,
            dosage=(detection.dosage or "").strip(),
            source="ocr",
            rx_cui=mapped_rxcui,
            ocr_confidence=detection.confidence,
            note=_encode_item_note(
                (
                    f"Phát hiện OCR: {detection.evidence}"
                    + (
                        " (manual confirmed)"
                        if detection.confidence < LOW_CONFIDENCE_OCR_THRESHOLD
                        else ""
                    )
                ),
                brand_name=detection.brand_name or "",
                manufacturer=detection.manufacturer or "",
            ),
            updated_at=datetime.now(tz=UTC),
        )
        db.add(item)
        if profile is not None:
            candidate = capture_candidates[str(detection.capture_candidate_id)]
            candidate.status = "confirmed"
            db.add(
                LifeMapCaptureReviewAction(
                    candidate_id=candidate.id,
                    profile_id=profile.id,
                    actor_user_id=user.id,
                    action="confirm",
                    reason_code="medicine_import_explicit_confirmation",
                )
            )
            course = MedicationCourse(
                profile_id=profile.id,
                medication_name=detection.drug_name.strip(),
                original_text=detection.evidence.strip(),
                normalized_name=normalized,
                normalization_system="careguard_dictionary",
                normalization_code=mapped_rxcui or "",
                reconciliation_status=(
                    "matched" if mapped_rxcui else "unknown"
                ),
                dose_text=(detection.dosage or "").strip(),
                route_text="unknown",
                truth_state="confirmed",
                provenance_json={
                    "source": "capture_review",
                    "capture_candidate_id": candidate.public_id,
                    "confirmation": "explicit_medicine_import",
                },
                created_by_user_id=user.id,
            )
            db.add(course)
            db.flush()
            db.add(
                MedicationCourseChange(
                    course_id=course.id,
                    profile_id=profile.id,
                    version_no=1,
                    action="confirmed_create",
                    snapshot_json={
                        "medication_name": course.medication_name,
                        "normalized_name": course.normalized_name,
                        "dose_text": course.dose_text,
                        "route_text": course.route_text,
                        "truth_state": course.truth_state,
                    },
                    reason_code="capture_explicit_user_confirmation",
                    actor_user_id=user.id,
                )
            )
            # The OCR result only becomes health state after the user's
            # explicit import confirmation.  Mirror that immutable evidence
            # into GLHS instead of allowing the cabinet/import side effect to
            # remain a parallel, ungoverned medication truth.  The adapter
            # deliberately keeps entries without an exact DrugBank identity
            # as unresolved candidates, so this call cannot cause a fuzzy OCR
            # match or the local mapping dictionary to feed DDI automatically.
            ingest_medication_course(
                db,
                scope=owner_profile_scope(profile=profile, actor=user),
                course=course,
                idempotency_key=(
                    "careguard-capture-import:"
                    f"{candidate.public_id}:{course.public_id}:v{course.version_no}"
                ),
            )
        existing_names.add(normalized)
        inserted += 1
        prioritized_fields.append(
            CabinetPrioritizedField(
                drug_name=detection.drug_name.strip(),
                brand_name=(detection.brand_name or "").strip(),
                manufacturer=(detection.manufacturer or "").strip(),
                dosage=(detection.dosage or "").strip(),
            )
        )

    db.commit()
    return CabinetImportResponse(inserted=inserted, prioritized_fields=prioritized_fields)


@router.post("/cabinet/auto-ddi-check")
def run_auto_ddi_check(
    payload: CabinetAutoDdiRequest,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = _require_user(token, db)
    cabinet = _get_or_create_cabinet(db, user.id)
    control_tower = get_control_tower_config_service().load(db)
    medication_items = (
        db.execute(select(MedicineItem).where(MedicineItem.cabinet_id == cabinet.id))
        .scalars()
        .all()
    )
    clarification_enabled = get_settings().careguard_medication_clarification_enabled
    resolutions_by_item: dict[int, CabinetDrugBankResolution] = {}
    if clarification_enabled:
        items_by_id = {item.id: item for item in medication_items}
        for resolution in payload.resolutions:
            item = items_by_id.get(resolution.cabinet_item_id)
            # Do not disclose another person's item existence. The selection
            # must bind to a current item in this user's cabinet and to its
            # unmodified raw alias before ML can revalidate DrugBank identity.
            if item is None or resolution.cabinet_item_id in resolutions_by_item:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"code": "invalid_cabinet_medication_resolution"},
                )
            if _canonicalize_drugbank_alias(resolution.input_alias) != _canonicalize_drugbank_alias(item.drug_name):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"code": "invalid_cabinet_medication_resolution"},
                )
            resolutions_by_item[item.id] = resolution

    # The default-off rollout preserves the prior canonical cabinet payload.
    # In strict clarification mode only, retain the user's raw cabinet label so
    # ML can bind it to an exact licensed DrugBank alias rather than a local
    # fuzzy/legacy normalization.
    medication_names = [
        (item.drug_name if clarification_enabled else item.normalized_name)
        for item in medication_items
        if (item.drug_name if clarification_enabled else item.normalized_name)
    ]
    medications_with_meta = []
    for item in medication_items:
        display_name, normalized_name, rx_cui, mapping_source, mapping_confidence = (
            _resolve_dictionary_mapping_with_source(item.drug_name, db=db)
        )
        medications_with_meta.append(
            {
                "drug_name": item.drug_name,
                "display_name": display_name,
                "normalized_name": normalized_name or item.normalized_name,
                "rx_cui": item.rx_cui or rx_cui,
                "mapping_source": mapping_source,
                "mapping_confidence": mapping_confidence,
            }
        )
        if clarification_enabled:
            medications_with_meta[-1]["cabinet_item_id"] = item.id
            # Keep this exact raw alias aligned and ordered with ``medications``.
            # ML uses it only to bind a returned clarification to this owner-
            # scoped item; the licensed DrugBank index remains the identity
            # authority and does not trust this metadata as a selection.
            medications_with_meta[-1]["input_alias"] = item.drug_name

    request_payload: dict[str, Any] = {
        "symptoms": payload.symptoms,
        "labs": payload.labs,
        "medications": sorted(set(medication_names)),
        "medications_with_meta": medications_with_meta,
        "allergies": payload.allergies,
        # The ML renderer uses this only after deterministic DrugBank/risk
        # policy has produced its final facts. It cannot change the conclusion.
        "locale": payload.locale,
        "external_ddi_enabled": control_tower.careguard_runtime.external_ddi_enabled,
    }
    if clarification_enabled:
        request_payload["medication_resolutions"] = [
            {
                "cabinet_item_id": resolution.cabinet_item_id,
                "input_alias": resolution.input_alias,
                "drugbank_id": resolution.drugbank_id,
                "drugbank_version": resolution.drugbank_version,
            }
            for resolution in payload.resolutions
        ]

    # --- PHR reconciliation + allergy-aware DDI (flag-gated, Req 7) ----------
    # Flag OFF ⇒ cabinet-only payload above, byte-for-byte legacy (Req 7.5,
    # Correctness Property 22). Both stores are always preserved; reconciliation
    # is a read-time projection that never mutates the cabinet or PHR (Req 7.6).
    flags = phr_features(settings=None)
    phr_derived = False
    allergy_conflicts: list[dict[str, Any]] = []
    thss_metadata: dict[str, Any] | None = None
    if flags.reconciliation:
        profile = db.execute(
            select(PhrProfile).where(PhrProfile.user_id == user.id)
        ).scalar_one_or_none()
        phr_meds: list[dict[str, Any]] = []
        phr_allergies: list[dict[str, Any]] = []
        if profile is not None:
            # Do not use legacy profile JSON as AI input.  THSS binds the
            # personal projection to one profile, one purpose, allowed data
            # classes, current governed state, and an opaque audit manifest.
            # In particular, ``medications_unresolved`` is not requested here:
            # a self-declared or OCR-derived name without deterministic
            # DrugBank identity cannot influence automated DDI reasoning.
            snapshot = compile_thss(
                db,
                scope=owner_profile_scope(profile=profile, actor=user),
                task="careguard_reconciliation",
                purpose="self_care",
                allowed_data_classes=frozenset({"medications", "allergies"}),
                selection_policy="strict",
                consumed_for_inference=True,
            )
            thss_metadata = {
                "snapshot_id": snapshot.snapshot_id,
                "state_version": snapshot.state_version,
                "policy_version": snapshot.policy_version,
                "consent_version": snapshot.consent_version,
                "risk": snapshot.risk,
                "inference_context_binding_id": snapshot.inference_context_binding_id,
            }
            for assertion in snapshot.assertions:
                value = assertion.get("value")
                if not isinstance(value, dict):
                    continue
                if assertion["type"] == "medications":
                    drugbank_id = str(value.get("drugbank_id") or "").strip()
                    if not drugbank_id:
                        # Defensive in case an older projection violated the
                        # type boundary; never send it downstream.
                        continue
                    name = str(value.get("medication_name") or "").strip()
                    phr_meds.append(
                        {
                            "id": str(assertion["id"]),
                            "rx_cui": "",
                            "normalized_name": name,
                            "name": name,
                            "drugbank_id": drugbank_id,
                        }
                    )
                elif assertion["type"] == "allergies":
                    phr_allergies.append(value)
        cabinet_payload = [
            {
                "id": str(item.id),
                "rx_cui": item.rx_cui or "",
                "normalized_name": item.normalized_name or "",
                "drug_name": item.drug_name or "",
            }
            for item in medication_items
        ]
        reconciled = reconcile(phr_meds, cabinet_payload)
        request_payload["reconciled_medications"] = reconciled.as_dict()["medications"]
        phr_derived = bool(phr_meds or phr_allergies)

        # Allergy-aware DDI requires personalization consent (Req 7.3, 7.4).
        if flags.allergy_aware_ddi and phr_allergies:
            consent_ok = not flags.consent_enforcement or PhrConsentService.is_granted(
                db, user_id=user.id, purpose="personalization"
            )
            # Compliance granular-consent gate (Req 2.1, 2.3): when
            # COMPLIANCE_GRANULAR_CONSENT_ENABLED is on, also require the
            # compliance-ledger personalization grant. Flag off ⇒ has_consent
            # returns True, so legacy behavior is preserved exactly.
            consent_ok = consent_ok and ComplianceService(db).has_consent(
                user_id=user.id, purpose=PURPOSE_PERSONALIZATION
            )
            if consent_ok:
                request_payload["coded_allergies"] = phr_allergies
                allergy_conflicts = find_allergy_conflicts(reconciled, phr_allergies)
                phr_derived = True
        if thss_metadata is not None:
            # Metadata is non-clinical governance context; it tells the model
            # whether the bounded state is usable without exposing ledger rows
            # or allowing model output to change the selection.
            request_payload["thss_governance"] = thss_metadata

    # --- Cross-border guard (Req 19.4) --------------------------------------
    # When cross-border gating is on and the user has not granted cross-border
    # consent, strip identifiable PHR-derived fields from the offshore call.
    transfer = ComplianceService(db).outbound_guard(user_id=user.id)
    if not transfer.allow_cross_border:
        request_payload.pop("reconciled_medications", None)
        request_payload.pop("coded_allergies", None)
    # No-PII transfer event (Req 4.4 / Property P5): record processor identity,
    # purpose, and an opaque user ref for the offshore call decision — never the
    # reconciled medications or allergies. Gated by the flag so flags-off side
    # effects stay byte-equivalent to baseline (Property P6).
    _compliance = ComplianceService(db)
    if _compliance.settings.compliance_cross_border_gating_enabled:
        _compliance.record_transfer(
            user_id=user.id,
            processor=LLM_PROCESSOR,
            purpose=LLM_PURPOSE,
            allowed=transfer.allow_cross_border,
        )

    observability_enabled = get_settings().careguard_observability_enabled
    started_at = perf_counter() if observability_enabled else 0.0
    result = proxy_ml_post("/v1/careguard/analyze", request_payload)
    attributed = _attach_careguard_attribution(
        result,
        external_ddi_enabled=control_tower.careguard_runtime.external_ddi_enabled,
    )
    if allergy_conflicts:
        attributed["allergy_conflicts"] = allergy_conflicts
    if phr_derived:
        # Hedge any PHR-derived decision-support output (Req 6.6, 18.5).
        attributed["phr_hedge"] = hedge_text_bilingual()
    # No-PII observability (Req 9.3, 9.4, 9.5). Recorded ONLY when the flag is on
    # so behavior stays byte-equivalent to baseline when off (Req 12.1, 12.2).
    # Only enum/number signals are folded in; the per-medicine normalization
    # confidences come from the dictionary mapping (numbers only, no names).
    if observability_enabled:
        latency_ms = (perf_counter() - started_at) * 1000
        normalization_confidences = [
            meta["mapping_confidence"]
            for meta in medications_with_meta
            if isinstance(meta.get("mapping_confidence"), (int, float))
        ]
        record_careguard_check(
            result,
            latency_ms=latency_ms,
            normalization_confidences=normalization_confidences,
        )
    return attributed


@router.get("/dictionary", response_model=VnDrugMappingListResponse)
def list_vn_drug_mappings(
    q: str = "",
    limit: int = 100,
    offset: int = 0,
    token: TokenPayload = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> VnDrugMappingListResponse:
    _require_user(token, db)
    safe_limit = min(max(limit, 1), 200)
    safe_offset = max(offset, 0)
    query = select(VnDrugMapping)
    count_query = select(func.count(VnDrugMapping.id))

    keyword = " ".join(q.split()).strip()
    if keyword:
        pattern = f"%{keyword.lower()}%"
        filters = or_(
            func.lower(VnDrugMapping.brand_name).like(pattern),
            func.lower(VnDrugMapping.normalized_name).like(pattern),
            func.lower(VnDrugMapping.active_ingredients).like(pattern),
        )
        query = query.where(filters)
        count_query = count_query.where(filters)

    total = int(db.execute(count_query).scalar_one() or 0)
    mappings = (
        db.execute(
            query.order_by(VnDrugMapping.updated_at.desc(), VnDrugMapping.id.desc())
            .limit(safe_limit)
            .offset(safe_offset)
        )
        .scalars()
        .all()
    )
    return VnDrugMappingListResponse(
        total=total,
        items=[_to_mapping_response(mapping) for mapping in mappings],
    )


@router.post("/dictionary", response_model=VnDrugMappingResponse)
def create_vn_drug_mapping(
    payload: VnDrugMappingCreateRequest,
    token: TokenPayload = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> VnDrugMappingResponse:
    user = _require_user(token, db)
    brand_name = " ".join(payload.brand_name.split()).strip()
    normalized_brand = _normalize_text(brand_name)
    normalized_name = _normalize_text(payload.normalized_name)
    aliases = _normalize_aliases(payload.aliases, brand_name)

    existing_brand = db.execute(
        select(VnDrugMapping).where(VnDrugMapping.normalized_brand == normalized_brand)
    ).scalar_one_or_none()
    if existing_brand is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Brand đã tồn tại trong dictionary",
        )

    _validate_alias_conflicts(db, aliases)

    mapping = VnDrugMapping(
        brand_name=brand_name,
        normalized_brand=normalized_brand,
        active_ingredients=payload.active_ingredients.strip(),
        normalized_name=normalized_name,
        rx_cui=payload.rx_cui.strip(),
        mapping_source=payload.mapping_source,
        notes=payload.notes.strip(),
        is_active=payload.is_active,
        created_by_user_id=user.id,
        updated_at=datetime.now(tz=UTC),
    )
    db.add(mapping)
    db.flush()
    _replace_mapping_aliases(db, mapping, aliases)
    _create_mapping_audit(
        db,
        mapping=mapping,
        action="create",
        actor_user_id=user.id,
        reason=payload.notes,
        before_snapshot=None,
        after_snapshot=_mapping_snapshot(mapping),
    )
    db.commit()
    db.refresh(mapping)
    return _to_mapping_response(mapping)


@router.patch("/dictionary/{mapping_id}", response_model=VnDrugMappingResponse)
@router.put("/dictionary/{mapping_id}", response_model=VnDrugMappingResponse)
def update_vn_drug_mapping(
    mapping_id: int,
    payload: VnDrugMappingUpdateRequest,
    token: TokenPayload = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> VnDrugMappingResponse:
    user = _require_user(token, db)
    mapping = _get_mapping_or_404(db, mapping_id)
    before_snapshot = _mapping_snapshot(mapping)
    provided = set(payload.model_fields_set)
    if not provided:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload cập nhật rỗng",
        )

    if "brand_name" in provided:
        brand_name = " ".join((payload.brand_name or "").split()).strip()
        if not brand_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="brand_name không hợp lệ",
            )
        normalized_brand = _normalize_text(brand_name)
        existing_brand = db.execute(
            select(VnDrugMapping).where(
                VnDrugMapping.normalized_brand == normalized_brand,
                VnDrugMapping.id != mapping.id,
            )
        ).scalar_one_or_none()
        if existing_brand is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Brand đã tồn tại trong dictionary",
            )
        mapping.brand_name = brand_name
        mapping.normalized_brand = normalized_brand

    if "active_ingredients" in provided:
        mapping.active_ingredients = (payload.active_ingredients or "").strip()
    if "normalized_name" in provided:
        normalized_name = _normalize_text(payload.normalized_name or "")
        if not normalized_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="normalized_name không hợp lệ",
            )
        mapping.normalized_name = normalized_name
    if "rx_cui" in provided:
        mapping.rx_cui = (payload.rx_cui or "").strip()
    if "mapping_source" in provided and payload.mapping_source is not None:
        mapping.mapping_source = payload.mapping_source
    if "notes" in provided:
        mapping.notes = (payload.notes or "").strip()
    if "is_active" in provided and payload.is_active is not None:
        mapping.is_active = payload.is_active

    if "aliases" in provided:
        aliases = _normalize_aliases(payload.aliases or [], mapping.brand_name)
        _validate_alias_conflicts(db, aliases, exclude_mapping_id=mapping.id)
        _replace_mapping_aliases(db, mapping, aliases)

    mapping.updated_at = datetime.now(tz=UTC)
    db.add(mapping)
    _create_mapping_audit(
        db,
        mapping=mapping,
        action="update",
        actor_user_id=user.id,
        reason=payload.notes or "",
        before_snapshot=before_snapshot,
        after_snapshot=_mapping_snapshot(mapping),
    )
    db.commit()
    db.refresh(mapping)
    return _to_mapping_response(mapping)


@router.delete("/dictionary/{mapping_id}")
def deactivate_vn_drug_mapping(
    mapping_id: int,
    token: TokenPayload = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    user = _require_user(token, db)
    mapping = _get_mapping_or_404(db, mapping_id)
    before_snapshot = _mapping_snapshot(mapping)
    mapping.is_active = False
    mapping.updated_at = datetime.now(tz=UTC)
    db.add(mapping)
    _create_mapping_audit(
        db,
        mapping=mapping,
        action="deactivate",
        actor_user_id=user.id,
        reason="Deactivate mapping",
        before_snapshot=before_snapshot,
        after_snapshot=_mapping_snapshot(mapping),
    )
    db.commit()
    return {"deleted": True}


@router.post("/dictionary/{mapping_id}/curation", response_model=VnDrugMappingResponse)
def curate_vn_drug_mapping(
    mapping_id: int,
    payload: VnDrugMappingCurationRequest,
    token: TokenPayload = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> VnDrugMappingResponse:
    admin_user = _require_admin_user(token, db)
    mapping = _get_mapping_or_404(db, mapping_id)
    before_snapshot = _mapping_snapshot(mapping)
    provided = set(payload.model_fields_set)
    mutable_fields = {
        "brand_name",
        "aliases",
        "active_ingredients",
        "normalized_name",
        "rx_cui",
        "notes",
        "is_active",
    }
    if not provided.intersection(mutable_fields):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload curation rỗng",
        )

    if "brand_name" in provided:
        brand_name = " ".join((payload.brand_name or "").split()).strip()
        if not brand_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="brand_name không hợp lệ",
            )
        normalized_brand = _normalize_text(brand_name)
        existing_brand = db.execute(
            select(VnDrugMapping).where(
                VnDrugMapping.normalized_brand == normalized_brand,
                VnDrugMapping.id != mapping.id,
            )
        ).scalar_one_or_none()
        if existing_brand is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Brand đã tồn tại trong dictionary",
            )
        mapping.brand_name = brand_name
        mapping.normalized_brand = normalized_brand

    if "active_ingredients" in provided:
        mapping.active_ingredients = (payload.active_ingredients or "").strip()
    if "normalized_name" in provided:
        normalized_name = _normalize_text(payload.normalized_name or "")
        if not normalized_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="normalized_name không hợp lệ",
            )
        mapping.normalized_name = normalized_name
    if "rx_cui" in provided:
        mapping.rx_cui = (payload.rx_cui or "").strip()
    if "notes" in provided:
        mapping.notes = (payload.notes or "").strip()
    if "is_active" in provided and payload.is_active is not None:
        mapping.is_active = payload.is_active
    if "aliases" in provided:
        aliases = _normalize_aliases(payload.aliases or [], mapping.brand_name)
        _validate_alias_conflicts(db, aliases, exclude_mapping_id=mapping.id)
        _replace_mapping_aliases(db, mapping, aliases)

    mapping.mapping_source = "curated"
    mapping.updated_at = datetime.now(tz=UTC)
    db.add(mapping)
    _create_mapping_audit(
        db,
        mapping=mapping,
        action="curate",
        actor_user_id=admin_user.id,
        reason=payload.reason,
        before_snapshot=before_snapshot,
        after_snapshot=_mapping_snapshot(mapping),
        metadata={"fields_updated": sorted(provided.intersection(mutable_fields))},
    )
    db.commit()
    db.refresh(mapping)
    return _to_mapping_response(mapping)


@router.get("/dictionary/{mapping_id}/audit", response_model=VnDrugMappingAuditListResponse)
def list_vn_drug_mapping_audits(
    mapping_id: int,
    limit: int = 50,
    offset: int = 0,
    token: TokenPayload = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> VnDrugMappingAuditListResponse:
    _require_admin_user(token, db)
    _get_mapping_or_404(db, mapping_id)
    safe_limit = min(max(limit, 1), 200)
    safe_offset = max(offset, 0)

    total = int(
        db.execute(
            select(func.count(VnDrugMappingAudit.id)).where(
                VnDrugMappingAudit.mapping_id == mapping_id
            )
        ).scalar_one()
        or 0
    )
    audits = (
        db.execute(
            select(VnDrugMappingAudit)
            .options(selectinload(VnDrugMappingAudit.actor))
            .where(VnDrugMappingAudit.mapping_id == mapping_id)
            .order_by(VnDrugMappingAudit.id.desc())
            .limit(safe_limit)
            .offset(safe_offset)
        )
        .scalars()
        .all()
    )
    return VnDrugMappingAuditListResponse(
        total=total,
        items=[_to_mapping_audit_response(audit) for audit in audits],
    )


@router.post("/dictionary/resolve", response_model=VnDrugResolveResponse)
def resolve_vn_drug_mapping(
    payload: VnDrugResolveRequest,
    token: TokenPayload = Depends(require_roles("doctor")),
    db: Session = Depends(get_db),
) -> VnDrugResolveResponse:
    _require_user(token, db)
    display_name, normalized_name, rx_cui, source, mapping_confidence = (
        _resolve_dictionary_mapping_with_source(
            payload.drug_name,
            db=db,
        )
    )
    return VnDrugResolveResponse(
        input_name=payload.drug_name.strip(),
        display_name=display_name,
        normalized_name=normalized_name,
        rx_cui=rx_cui,
        mapping_source=source,
        mapping_confidence=mapping_confidence,
    )


@router.post("/analyze")
def careguard_analyze(
    payload: dict[str, Any],
    token: TokenPayload = Depends(require_roles("normal", "doctor")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_user(token, db)
    control_tower = get_control_tower_config_service().load(db)
    request_payload = _bounded_medication_text_payload(payload)
    request_payload["external_ddi_enabled"] = control_tower.careguard_runtime.external_ddi_enabled
    observability_enabled = get_settings().careguard_observability_enabled
    started_at = perf_counter() if observability_enabled else 0.0
    result = proxy_ml_post("/v1/careguard/analyze", request_payload)
    attributed = _attach_careguard_attribution(
        result,
        external_ddi_enabled=control_tower.careguard_runtime.external_ddi_enabled,
    )
    # No-PII observability (Req 9.3, 9.4, 9.5); recorded only when the flag is on
    # so flags-off behavior is byte-equivalent (Req 12.1, 12.2).
    if observability_enabled:
        latency_ms = (perf_counter() - started_at) * 1000
        record_careguard_check(result, latency_ms=latency_ms)
    return attributed


@router.get("/metrics")
def get_careguard_metrics(
    _token: TokenPayload = Depends(require_roles("admin")),
) -> dict[str, Any]:
    """Admin-only aggregate read of no-PII CareGuard observability metrics (Req 9.5).

    Gated by ``CAREGUARD_OBSERVABILITY_ENABLED``: when the flag is off the
    surface returns 404 (consistent with the other flag-gated analytics
    surfaces) and no metrics are collected, so the feature ships dark. The
    returned aggregate carries only counts, rates, enum distributions, the
    active rule-set version label, and latency percentiles — never drug names,
    notes, or any user identifier (Req 9.2, 9.3, 11.4). Access is restricted to
    the admin role (Req 9.5, 12.4).
    """

    if not get_settings().careguard_observability_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CareGuard observability đã bị tắt.",
        )
    return get_careguard_metrics_store().snapshot()
