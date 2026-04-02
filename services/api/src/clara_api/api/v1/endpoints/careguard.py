# ruff: noqa: E501
from __future__ import annotations

import base64
import re
import unicodedata
from datetime import UTC, datetime
from difflib import SequenceMatcher
from time import perf_counter
from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from clara_api.api.v1.endpoints.ml_proxy import proxy_ml_post
from clara_api.core.attribution import (
    attach_attribution,
    build_attribution,
    normalize_source_errors,
    normalize_source_used,
)
from clara_api.core.config import get_settings
from clara_api.core.consent import ensure_medical_disclaimer_consent
from clara_api.core.control_tower import get_control_tower_config_service
from clara_api.core.ocr_correction import OcrCorrectionResult, correct_ocr_text
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.models import (
    MedicineCabinet,
    MedicineItem,
    User,
    VnDrugMapping,
    VnDrugMappingAlias,
    VnDrugMappingAudit,
)
from clara_api.db.session import get_db
from clara_api.schemas import (
    CabinetAutoDdiRequest,
    CabinetImportRequest,
    CabinetScanDetection,
    CabinetScanTextRequest,
    CabinetScanTextResponse,
    MedicineCabinetItemCreate,
    MedicineCabinetItemResponse,
    MedicineCabinetItemUpdate,
    MedicineCabinetResponse,
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
_CANDIDATE_DB_LIMIT = 120
_CANDIDATE_MIN_SCORE = 0.78
_CANDIDATE_MIN_MARGIN = 0.05

_CAREGUARD_SOURCE_CATALOG: dict[str, dict[str, str]] = {
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
    query_fold = _ascii_fold(query)
    candidate_fold = _ascii_fold(candidate)
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
    candidates = _collect_db_candidate_mappings(db, normalized_input)
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
            best_score = max(best_score, _compute_candidate_similarity(normalized_input, name))
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
            display_name = db_mapping.brand_name.strip() or _to_title_case(db_mapping.normalized_name)
            normalized_name = db_mapping.normalized_name.strip() or normalized_input
            rx_cui = db_mapping.rx_cui.strip()
            if not rx_cui:
                rx_cui = DRUG_RXCUI_MAP.get(normalized_name, "")
            return display_name, normalized_name, rx_cui, "db", 1.0

        candidate_mapping, candidate_score, _, _ = _find_db_mapping_candidate(db, normalized_input)
        if candidate_mapping is not None:
            display_name = candidate_mapping.brand_name.strip() or _to_title_case(candidate_mapping.normalized_name)
            normalized_name = candidate_mapping.normalized_name.strip() or normalized_input
            rx_cui = candidate_mapping.rx_cui.strip()
            if not rx_cui:
                rx_cui = DRUG_RXCUI_MAP.get(normalized_name, "")
            return display_name, normalized_name, rx_cui, "candidate", max(min(candidate_score, 1.0), 0.0)

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
    display_name, normalized_name, rx_cui, _mapping_source, _mapping_confidence = _resolve_dictionary_mapping_with_source(
        drug_name=drug_name,
        db=db,
    )
    return display_name, normalized_name, rx_cui


def _to_title_case(value: str) -> str:
    return " ".join(token.capitalize() for token in value.split(" ") if token)


def _to_item_response(
    item: MedicineItem,
    *,
    normalization_source: str | None = None,
    normalization_confidence: float | None = None,
) -> MedicineCabinetItemResponse:
    return MedicineCabinetItemResponse(
        id=item.id,
        drug_name=item.drug_name,
        normalized_name=item.normalized_name,
        normalization_source=normalization_source,
        normalization_confidence=normalization_confidence,
        dosage=item.dosage,
        dosage_form=item.dosage_form,
        quantity=item.quantity,
        source=item.source,
        rx_cui=item.rx_cui,
        ocr_confidence=item.ocr_confidence,
        expires_on=item.expires_on,
        note=item.note,
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
    mapping = db.execute(select(VnDrugMapping).where(VnDrugMapping.id == mapping_id)).scalar_one_or_none()
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
    sources = _resolve_careguard_sources(
        source_used=source_used,
        external_ddi_enabled=external_ddi_enabled,
    )
    has_external_source = any(source.get("id") not in {"local_rules"} for source in sources)
    mode = "external_plus_local" if has_external_source else "local_only"
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


def _apply_ocr_correction(text: str) -> OcrCorrectionResult:
    return correct_ocr_text(
        text,
        vocabulary=OCR_DRUG_VOCABULARY,
        cutoff=OCR_CORRECTION_CUTOFF,
        max_events=24,
    )


def _detect_drugs_from_text(
    text: str,
    db: Session | None = None,
    *,
    skip_ocr_correction: bool = False,
) -> list[CabinetScanDetection]:
    candidate_text = text if skip_ocr_correction else _apply_ocr_correction(text).corrected_text
    normalized_text = candidate_text.lower()
    detections: list[CabinetScanDetection] = []

    for canonical, aliases in DRUG_ALIAS_MAP.items():
        for alias in aliases:
            escaped_alias = re.escape(alias)
            pattern = rf"(^|[^a-z0-9]){escaped_alias}([^a-z0-9]|$)"
            if not re.search(pattern, normalized_text, flags=re.IGNORECASE):
                continue

            display_name, normalized_name, _rx_cui, mapping_source, mapping_confidence = (
                _resolve_dictionary_mapping_with_source(canonical, db=db)
            )
            confidence = 0.94 if alias == canonical else 0.82
            requires_manual_confirm = confidence < LOW_CONFIDENCE_OCR_THRESHOLD
            detections.append(
                CabinetScanDetection(
                    drug_name=display_name,
                    normalized_name=normalized_name,
                    confidence=confidence,
                    evidence=alias,
                    mapping_source=mapping_source,
                    mapping_confidence=mapping_confidence,
                    requires_manual_confirm=requires_manual_confirm,
                    confirmed=not requires_manual_confirm,
                )
            )
            break

    detections.sort(key=lambda item: (-item.confidence, item.drug_name))
    return detections


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
) -> httpx.Response:
    files = {"file": (file_name, file_bytes, content_type)}
    return httpx.post(url, files=files, headers=headers, timeout=timeout_seconds)


def _post_tgc_ocr_json(
    url: str,
    file_bytes: bytes,
    timeout_seconds: float,
    headers: dict[str, str],
) -> httpx.Response:
    encoded = base64.b64encode(file_bytes).decode("utf-8")
    payload = {"image": encoded, "lang": "vi"}
    return httpx.post(url, json=payload, headers=headers, timeout=timeout_seconds)


def _scan_with_tgc_ocr(
    file_bytes: bytes,
    file_name: str,
    content_type: str,
) -> tuple[str, str, str]:
    settings = get_settings()
    endpoints = _parse_ocr_endpoints(settings.tgc_ocr_endpoints)
    if not endpoints:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Chưa cấu hình TGC_OCR_ENDPOINTS",
        )

    base_url = settings.tgc_ocr_base_url.rstrip("/")
    headers: dict[str, str] = {}
    if settings.tgc_ocr_api_key.strip():
        headers["x-api-key"] = settings.tgc_ocr_api_key.strip()

    last_error = "Không lấy được văn bản OCR từ TGC service"
    for endpoint in endpoints:
        url = f"{base_url}{endpoint}"
        try:
            response = _post_tgc_ocr_multipart(
                url=url,
                file_bytes=file_bytes,
                file_name=file_name,
                content_type=content_type,
                timeout_seconds=settings.tgc_ocr_timeout_seconds,
                headers=headers,
            )
        except (httpx.ConnectError, httpx.NetworkError, httpx.TimeoutException) as exc:
            last_error = f"Không kết nối được OCR service: {exc.__class__.__name__}"
            continue
        except httpx.HTTPError as exc:
            last_error = f"OCR request lỗi: {exc}"
            continue

        # Some OCR services expose `/ocr` with JSON (base64 image), not multipart.
        if response.status_code in {400, 415, 422} and endpoint.endswith("/ocr"):
            try:
                response = _post_tgc_ocr_json(
                    url=url,
                    file_bytes=file_bytes,
                    timeout_seconds=settings.tgc_ocr_timeout_seconds,
                    headers=headers,
                )
            except (httpx.ConnectError, httpx.NetworkError, httpx.TimeoutException) as exc:
                last_error = f"Không kết nối được OCR service: {exc.__class__.__name__}"
                continue
            except httpx.HTTPError as exc:
                last_error = f"OCR request lỗi: {exc}"
                continue

        if response.status_code >= 500:
            last_error = f"OCR upstream error: status={response.status_code}"
            continue
        if response.status_code >= 400:
            last_error = f"OCR endpoint từ chối request: status={response.status_code}"
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
    )


@router.post("/cabinet/items", response_model=MedicineCabinetItemResponse)
def add_cabinet_item(
    payload: MedicineCabinetItemCreate,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> MedicineCabinetItemResponse:
    user = _require_user(token, db)
    cabinet = _get_or_create_cabinet(db, user.id)

    _, normalized, mapped_rxcui, mapping_source, mapping_confidence = _resolve_dictionary_mapping_with_source(
        payload.drug_name,
        db=db,
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
        note=payload.note.strip(),
        updated_at=datetime.now(tz=UTC),
    )
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
        item.expires_on = payload.expires_on
    if "note" in provided:
        item.note = (payload.note or "").strip()

    item.updated_at = datetime.now(tz=UTC)
    db.add(item)
    db.commit()
    db.refresh(item)
    if response_mapping_source is None or response_mapping_confidence is None:
        _, _, _, response_mapping_source, response_mapping_confidence = _resolve_dictionary_mapping_with_source(
            item.drug_name,
            db=db,
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


@router.post("/cabinet/scan-text", response_model=CabinetScanTextResponse)
def scan_cabinet_text(
    payload: CabinetScanTextRequest,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> CabinetScanTextResponse:
    _require_user(token, db)
    correction = _apply_ocr_correction(payload.text)
    return CabinetScanTextResponse(
        detections=_detect_drugs_from_text(
            correction.corrected_text,
            db=db,
            skip_ocr_correction=True,
        ),
        extracted_text=correction.corrected_text[:4000],
        ocr_provider="ocr-postprocess",
        ocr_endpoint="local-ocr-correction",
    )


@router.post("/cabinet/scan-file", response_model=CabinetScanTextResponse)
async def scan_cabinet_file(
    file: UploadFile = File(...),
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> CabinetScanTextResponse:
    _require_user(token, db)
    file_name = file.filename or "uploaded-receipt"
    content_type = file.content_type or "application/octet-stream"
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File upload rỗng")
    if len(file_bytes) > 20 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File vượt quá 20MB",
        )

    extracted_text, used_endpoint, ocr_provider = _scan_with_tgc_ocr(
        file_bytes=file_bytes,
        file_name=file_name,
        content_type=content_type,
    )
    correction = _apply_ocr_correction(extracted_text)
    detections = _detect_drugs_from_text(
        correction.corrected_text,
        db=db,
        skip_ocr_correction=True,
    )
    return CabinetScanTextResponse(
        detections=detections,
        extracted_text=correction.corrected_text[:4000],
        ocr_provider=ocr_provider,
        ocr_endpoint=used_endpoint,
    )


@router.post("/cabinet/import-detections")
def import_detections(
    payload: CabinetImportRequest,
    token: TokenPayload = Depends(require_roles("normal", "researcher", "doctor")),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    user = _require_user(token, db)
    cabinet = _get_or_create_cabinet(db, user.id)

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
            detection.requires_manual_confirm
            or detection.confidence < LOW_CONFIDENCE_OCR_THRESHOLD
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
    for detection in payload.detections:
        _, normalized, mapped_rxcui, _mapping_source, _mapping_confidence = _resolve_dictionary_mapping_with_source(
            detection.normalized_name or detection.drug_name,
            db=db,
        )
        if not normalized or normalized in existing_names:
            continue
        item = MedicineItem(
            cabinet_id=cabinet.id,
            drug_name=detection.drug_name.strip(),
            normalized_name=normalized,
            source="ocr",
            rx_cui=mapped_rxcui,
            ocr_confidence=detection.confidence,
            note=(
                f"Phát hiện OCR: {detection.evidence}"
                + (" (manual confirmed)" if detection.confidence < LOW_CONFIDENCE_OCR_THRESHOLD else "")
            ),
            updated_at=datetime.now(tz=UTC),
        )
        db.add(item)
        existing_names.add(normalized)
        inserted += 1

    db.commit()
    return {"inserted": inserted}


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
        db.execute(
            select(MedicineItem).where(MedicineItem.cabinet_id == cabinet.id)
        )
        .scalars()
        .all()
    )
    medication_names = [item.normalized_name for item in medication_items if item.normalized_name]
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

    request_payload: dict[str, Any] = {
        "symptoms": payload.symptoms,
        "labs": payload.labs,
        "medications": sorted(set(medication_names)),
        "medications_with_meta": medications_with_meta,
        "allergies": payload.allergies,
        "external_ddi_enabled": control_tower.careguard_runtime.external_ddi_enabled,
    }
    result = proxy_ml_post("/v1/careguard/analyze", request_payload)
    return _attach_careguard_attribution(
        result,
        external_ddi_enabled=control_tower.careguard_runtime.external_ddi_enabled,
    )


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
            select(func.count(VnDrugMappingAudit.id)).where(VnDrugMappingAudit.mapping_id == mapping_id)
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
    display_name, normalized_name, rx_cui, source, mapping_confidence = _resolve_dictionary_mapping_with_source(
        payload.drug_name,
        db=db,
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
    request_payload = dict(payload)
    request_payload["external_ddi_enabled"] = control_tower.careguard_runtime.external_ddi_enabled
    result = proxy_ml_post("/v1/careguard/analyze", request_payload)
    return _attach_careguard_attribution(
        result,
        external_ddi_enabled=control_tower.careguard_runtime.external_ddi_enabled,
    )
