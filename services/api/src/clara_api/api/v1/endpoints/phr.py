# ruff: noqa: B008
"""Personal Health Record (PHR) HTTP surface under ``/api/v1/phr``.

The legacy ``GET/PUT /record`` path is preserved byte-for-byte: with the PHR
feature flag off it behaves exactly as before (Requirement 18.1, Correctness
Property 22). Every enhanced capability (coded fields, provenance, history,
consent, OCR import, observations, export, sharing, emergency card, reminders,
completeness) is additive and gated behind the relevant effective PHR flag
resolved by :func:`clara_api.phr.features.phr_features`.

The PHR remains self-declared, decision-support data only — not an EMR/EHR and
not legally binding. All PHR-derived decision-support output is hedged.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.compliance.consent import PURPOSE_SHARING
from clara_api.compliance.service import ComplianceService
from clara_api.core.auth_email import _send_via_smtp
from clara_api.core.config import Settings, get_settings
from clara_api.core.consent import (
    PHR_CONSENT_PURPOSES,
    PhrConsentService,
    ensure_medical_disclaimer_consent,
)
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.core.upload_safety import (
    UploadMalwareScannerUnavailable,
    UploadSafetyError,
    read_upload_bytes_with_limit,
    verify_upload,
)
from clara_api.db.models import (
    PhrObservation,
    PhrProfile,
    PhrReminder,
    PhrShare,
    User,
)
from clara_api.db.session import get_db
from clara_api.phr import audit as audit_svc
from clara_api.phr.completeness import completeness_telemetry, score_completeness
from clara_api.phr.emergency_card import build_emergency_card
from clara_api.phr.features import phr_features
from clara_api.phr.fhir_export import to_bundle
from clara_api.phr.normalizer import flag_duplicate_medications, normalize_medication_name
from clara_api.phr.provenance import hedge_text_bilingual, tag_provenance
from clara_api.phr.reminders import evaluate_reminder
from clara_api.phr.validator import (
    PhrValidationError,
    validate_allergy,
    validate_condition,
    validate_date_of_birth,
    validate_medication,
    validate_observation,
)
from clara_api.schemas import (
    PhrBodyMeasurementCreateRequest,
    PhrConsentMutationRequest,
    PhrEnhancedRecordResponse,
    PhrEntryPatchRequest,
    PhrObservationCreateRequest,
    PhrOcrConfirmRequest,
    PhrOcrScanResponse,
    PhrOnboardingResponse,
    PhrOnboardingUpdateRequest,
    PhrRecordResponse,
    PhrRecordUpdateRequest,
    PhrReminderCreateRequest,
    PhrReminderDispatchRequest,
    PhrShareCreateRequest,
)

router = APIRouter()

USER_ROLE_DEP = Depends(require_roles("normal", "researcher", "doctor", "admin"))
SETTINGS_DEP = Depends(get_settings)
PHR_ONBOARDING_VERSION = "2026-07-v1"
_OCR_REVIEW_TOKEN_VERSION = "phr-ocr-review.v1"
_OCR_REVIEW_TOKEN_TTL_SECONDS = 15 * 60
PHR_ONBOARDING_OPTIONAL_FIELDS = [
    "full_name",
    "date_of_birth",
    "gender",
    "blood_type",
    "height_cm",
    "weight_kg",
    "emergency_contact_name",
    "emergency_contact_phone",
    "allergies",
    "conditions",
    "medications",
]
_PUBLIC_PHR_SHARE_UNAVAILABLE = {"code": "public_share_unavailable"}


def _phr_share_token_hash(share_token: str) -> str:
    return hashlib.sha256(share_token.encode("utf-8")).hexdigest()


def _get_user_by_token(db: Session, token: TokenPayload) -> User:
    user = db.execute(select(User).where(User.email == token.sub)).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User does not exist",
        )
    return user


def _clean_object_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _serialize_profile(profile: PhrProfile | None) -> PhrRecordResponse:
    if profile is None:
        return PhrRecordResponse()

    return PhrRecordResponse(
        full_name=profile.full_name or "",
        date_of_birth=profile.date_of_birth,
        gender=profile.gender or "",
        blood_type=profile.blood_type or "",
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        phone=profile.phone or "",
        address=profile.address or "",
        emergency_contact_name=profile.emergency_contact_name or "",
        emergency_contact_phone=profile.emergency_contact_phone or "",
        insurance_id=profile.insurance_id or "",
        notes=profile.notes or "",
        allergies=_clean_object_list(profile.allergies_json),
        conditions=_clean_object_list(profile.conditions_json),
        medications=_clean_object_list(profile.medications_json),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _serialize_onboarding(
    db: Session, *, user: User, profile: PhrProfile
) -> PhrOnboardingResponse:
    onboarding_status = profile.onboarding_status or "pending"
    if onboarding_status not in {"pending", "completed", "skipped"}:
        onboarding_status = "pending"
    return PhrOnboardingResponse(
        status=onboarding_status,
        needs_onboarding=onboarding_status == "pending",
        version=profile.onboarding_version or PHR_ONBOARDING_VERSION,
        completed_at=profile.onboarding_completed_at,
        personalization_consent=PhrConsentService.is_granted(
            db, user_id=user.id, purpose="personalization"
        ),
        optional_fields=PHR_ONBOARDING_OPTIONAL_FIELDS,
        record=_serialize_profile(profile),
    )


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Vary"] = "Authorization"


@router.get("/onboarding", response_model=PhrOnboardingResponse)
def get_phr_onboarding(
    response: Response,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> PhrOnboardingResponse:
    """Return the durable first-run decision without inferring health facts."""

    user = _get_user_by_token(db, token)
    profile = _get_or_create_profile(db, user.id)
    if profile.id is None:
        db.commit()
        db.refresh(profile)
    _no_store(response)
    return _serialize_onboarding(db, user=user, profile=profile)


@router.patch("/onboarding", response_model=PhrOnboardingResponse)
def update_phr_onboarding(
    payload: PhrOnboardingUpdateRequest,
    response: Response,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> PhrOnboardingResponse:
    """Partially save, complete, or explicitly skip health-profile setup.

    No clinical answer is required. Omitted fields are preserved and consent is
    changed only when the caller sends ``personalization_consent``.
    """

    if payload.action == "complete" and not payload.confirm_self_declared:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Xác nhận dữ liệu sức khỏe là do bạn tự khai trước khi hoàn tất.",
        )

    user = _get_user_by_token(db, token)
    profile = _get_or_create_profile(db, user.id)
    db.flush()
    before = _record_dict(profile, db)

    supplied = payload.model_fields_set
    scalar_fields = (
        "full_name",
        "date_of_birth",
        "gender",
        "blood_type",
        "height_cm",
        "weight_kg",
        "emergency_contact_name",
        "emergency_contact_phone",
    )
    for field_name in scalar_fields:
        if field_name not in supplied:
            continue
        value = getattr(payload, field_name)
        if value is None and field_name in {
            "full_name",
            "gender",
            "blood_type",
            "emergency_contact_name",
            "emergency_contact_phone",
        }:
            value = ""
        if isinstance(value, str):
            value = value.strip()
            if field_name == "blood_type":
                value = value.upper()
        setattr(profile, field_name, value)

    if "date_of_birth" in supplied:
        try:
            validate_date_of_birth(profile.date_of_birth)
        except PhrValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message
            ) from exc

    list_fields = {
        "allergies": "allergies_json",
        "conditions": "conditions_json",
        "medications": "medications_json",
    }
    for request_field, model_field in list_fields.items():
        if request_field not in supplied:
            continue
        value = getattr(payload, request_field)
        setattr(
            profile,
            model_field,
            [item.model_dump(mode="json") for item in value] if value is not None else None,
        )

    # The enhanced validators remain authoritative when enabled, including the
    # future-date and medication normalization checks.
    if phr_features(settings).enhanced and supplied.intersection(
        {"date_of_birth", *list_fields.keys()}
    ):
        merged = _serialize_profile(profile).model_dump()
        merged.pop("created_at", None)
        merged.pop("updated_at", None)
        try:
            validated = PhrRecordUpdateRequest.model_validate(merged)
            allergies, conditions, medications = _enhanced_write_entries(validated, db)
        except PhrValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message
            ) from exc
        profile.allergies_json = allergies
        profile.conditions_json = conditions
        profile.medications_json = medications

    now = datetime.now(UTC)
    if payload.action == "complete":
        profile.onboarding_status = "completed"
        profile.onboarding_version = PHR_ONBOARDING_VERSION
        profile.onboarding_completed_at = now
    elif payload.action == "skip" and profile.onboarding_status != "completed":
        profile.onboarding_status = "skipped"
        profile.onboarding_version = PHR_ONBOARDING_VERSION
        profile.onboarding_completed_at = now

    if "personalization_consent" in supplied and payload.personalization_consent is not None:
        if payload.personalization_consent:
            PhrConsentService.grant(db, user_id=user.id, purpose="personalization")
        else:
            PhrConsentService.revoke(db, user_id=user.id, purpose="personalization")

    audit_svc.record_change(
        db,
        profile=profile,
        action=audit_svc.ACTION_UPDATE,
        entity="onboarding",
        actor_user_id=user.id,
        before=before,
        after={
            "status": profile.onboarding_status,
            "version": profile.onboarding_version,
            "fields_supplied": sorted(
                supplied.intersection(set(PHR_ONBOARDING_OPTIONAL_FIELDS))
            ),
            "personalization_consent_changed": "personalization_consent" in supplied,
        },
        snapshot=_record_dict(profile, db),
    )
    db.commit()
    db.refresh(profile)
    _no_store(response)
    return _serialize_onboarding(db, user=user, profile=profile)


@router.get("/record", response_model=PhrRecordResponse)
def get_phr_record(
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
) -> PhrRecordResponse:
    user = _get_user_by_token(db, token)
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    return _serialize_profile(profile)


@router.put("/record", response_model=PhrRecordResponse)
def upsert_phr_record(
    payload: PhrRecordUpdateRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> PhrRecordResponse:
    user = _get_user_by_token(db, token)
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        profile = PhrProfile(user_id=user.id)
        db.add(profile)

    enhanced = phr_features(settings).enhanced

    # When the master flag is on, run the shared validator / normalizer /
    # provenance tagger over the whole-profile write so coded + provenance fields
    # are assigned server-side (Req 3–6, 15). When off, the legacy upsert below is
    # byte-for-byte unchanged (Req 18.1, Correctness Property 22).
    if enhanced:
        try:
            allergies_json, conditions_json, medications_json = _enhanced_write_entries(
                payload, db
            )
        except PhrValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message
            ) from exc
    else:
        allergies_json = [item.model_dump(mode="json") for item in payload.allergies]
        conditions_json = [item.model_dump(mode="json") for item in payload.conditions]
        medications_json = [item.model_dump(mode="json") for item in payload.medications]

    profile.full_name = payload.full_name.strip()
    profile.date_of_birth = payload.date_of_birth
    profile.gender = payload.gender.strip()
    profile.blood_type = payload.blood_type.strip().upper()
    profile.height_cm = payload.height_cm
    profile.weight_kg = payload.weight_kg
    profile.phone = payload.phone.strip()
    profile.address = payload.address.strip()
    profile.emergency_contact_name = payload.emergency_contact_name.strip()
    profile.emergency_contact_phone = payload.emergency_contact_phone.strip()
    profile.insurance_id = payload.insurance_id.strip()
    profile.notes = payload.notes.strip()
    profile.allergies_json = allergies_json
    profile.conditions_json = conditions_json
    profile.medications_json = medications_json

    db.commit()
    db.refresh(profile)
    return _serialize_profile(profile)


def _enhanced_write_entries(
    payload: PhrRecordUpdateRequest, db: Session
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate + normalize + provenance-tag a whole-profile write (Req 3–6, 15).

    Runs server-side when ``phr_enhanced_enabled`` is on. Raises
    :class:`PhrValidationError` (mapped to HTTP 422 by the caller) on the first
    sanity violation. Every entry gets ``information_source="self-declared"`` and
    a server-assigned id; medications are normalized to RXCUI and duplicate-flagged.
    """

    # Profile-level sanity: reject a future date of birth (Req 15.1).
    validate_date_of_birth(payload.date_of_birth)

    allergies = [
        tag_provenance(
            validate_allergy(item.model_dump(mode="json")),
            information_source="self-declared",
        )
        for item in payload.allergies
    ]
    conditions = [
        tag_provenance(
            validate_condition(item.model_dump(mode="json")),
            information_source="self-declared",
        )
        for item in payload.conditions
    ]
    medications = [
        _normalize_medication_entry(item.model_dump(mode="json"), db)
        for item in payload.medications
    ]
    medications = flag_duplicate_medications(medications)
    return allergies, conditions, medications


# ---------------------------------------------------------------------------
# Enhanced surface (all flag-gated behind phr_enhanced_enabled)
# ---------------------------------------------------------------------------


def _require_enhanced(settings: Settings) -> None:
    if not phr_features(settings).enhanced:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PHR enhanced features are not enabled",
        )


def _get_or_create_profile(db: Session, user_id: int) -> PhrProfile:
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user_id)
    ).scalar_one_or_none()
    if profile is None:
        profile = PhrProfile(user_id=user_id)
        db.add(profile)
        db.flush()
    return profile


def _record_dict(profile: PhrProfile, db: Session | None = None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "profile": {
            "full_name": profile.full_name or "",
            "date_of_birth": (profile.date_of_birth.isoformat() if profile.date_of_birth else None),
            "gender": profile.gender or "",
            "blood_type": profile.blood_type or "",
            "emergency_contact_name": profile.emergency_contact_name or "",
            "emergency_contact_phone": profile.emergency_contact_phone or "",
        },
        "allergies": _clean_object_list(profile.allergies_json),
        "conditions": _clean_object_list(profile.conditions_json),
        "medications": _clean_object_list(profile.medications_json),
        "observations": [],
    }
    if db is not None:
        record["observations"] = [
            {
                "name": obs.name,
                "value": obs.value,
                "unit": obs.unit,
                "observed_on": obs.observed_on.isoformat() if obs.observed_on else None,
                "information_source": obs.information_source,
            }
            for obs in db.execute(
                select(PhrObservation).where(PhrObservation.profile_id == profile.id)
            ).scalars()
        ]
    return record


def _enhanced_response(profile: PhrProfile) -> PhrEnhancedRecordResponse:
    return PhrEnhancedRecordResponse(
        full_name=profile.full_name or "",
        date_of_birth=profile.date_of_birth,
        gender=profile.gender or "",
        blood_type=profile.blood_type or "",
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        phone=profile.phone or "",
        address=profile.address or "",
        emergency_contact_name=profile.emergency_contact_name or "",
        emergency_contact_phone=profile.emergency_contact_phone or "",
        insurance_id=profile.insurance_id or "",
        notes=profile.notes or "",
        allergies=_clean_object_list(profile.allergies_json),
        conditions=_clean_object_list(profile.conditions_json),
        medications=_clean_object_list(profile.medications_json),
        current_version_no=profile.current_version_no or 0,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _normalize_medication_entry(entry: dict, db: Session) -> dict:
    """Validate + normalize + tag a single self-declared medication entry."""

    validated = validate_medication(entry)
    norm = normalize_medication_name(str(validated.get("name") or ""), db=db)
    validated["normalized_name"] = norm.normalized_name
    validated["rx_cui"] = norm.rx_cui
    validated["normalization_source"] = norm.normalization_source
    validated["is_normalized"] = norm.is_normalized
    return tag_provenance(validated, information_source="self-declared")


@router.get("/capabilities")
def get_phr_capabilities(
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    """Project effective PHR flags for web/mobile (master AND sub)."""

    return {"flags": phr_features(settings).as_dict()}


@router.get("/record/enhanced", response_model=PhrEnhancedRecordResponse)
def get_phr_record_enhanced(
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> PhrEnhancedRecordResponse:
    _require_enhanced(settings)
    user = _get_user_by_token(db, token)
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        return PhrEnhancedRecordResponse()
    return _enhanced_response(profile)


_ENTRY_KINDS = {"allergy", "condition", "medication"}
_JSON_COLUMN = {
    "allergy": "allergies_json",
    "condition": "conditions_json",
    "medication": "medications_json",
}
_VALIDATOR = {
    "allergy": validate_allergy,
    "condition": validate_condition,
    "medication": validate_medication,
}


@router.post("/entries/{kind}", response_model=PhrEnhancedRecordResponse)
def create_phr_entry(
    kind: str,
    payload: PhrEntryPatchRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> PhrEnhancedRecordResponse:
    """Append a single validated, server-tagged entry (Req 6, 8, 15)."""

    _require_enhanced(settings)
    if kind not in _ENTRY_KINDS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown entry kind")
    user = _get_user_by_token(db, token)
    profile = _get_or_create_profile(db, user.id)

    try:
        if kind == "medication":
            new_entry = _normalize_medication_entry(dict(payload.fields), db)
        else:
            validated = _VALIDATOR[kind](dict(payload.fields))
            new_entry = tag_provenance(validated, information_source="self-declared")
    except PhrValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message
        ) from exc

    column = _JSON_COLUMN[kind]
    items = _clean_object_list(getattr(profile, column))
    items.append(new_entry)
    if kind == "medication":
        items = flag_duplicate_medications(items)
    setattr(profile, column, items)

    audit_svc.record_change(
        db,
        profile=profile,
        action=audit_svc.ACTION_CREATE,
        entity=kind,
        entity_id=str(new_entry.get("id") or new_entry.get("entry_id") or ""),
        actor_user_id=user.id,
        after=new_entry,
        snapshot=_record_dict(profile, db),
    )
    db.commit()
    db.refresh(profile)
    return _enhanced_response(profile)


@router.patch("/entries/{kind}/{entry_id}", response_model=PhrEnhancedRecordResponse)
def patch_phr_entry(
    kind: str,
    entry_id: str,
    payload: PhrEntryPatchRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> PhrEnhancedRecordResponse:
    """Targeted entry/field update — never overwrites the whole profile (Req 8.6)."""

    _require_enhanced(settings)
    if kind not in _ENTRY_KINDS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown entry kind")
    user = _get_user_by_token(db, token)
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PHR record not found")

    column = _JSON_COLUMN[kind]
    items = _clean_object_list(getattr(profile, column))
    target_idx = next((i for i, item in enumerate(items) if str(item.get("id")) == entry_id), None)
    if target_idx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    before = dict(items[target_idx])
    merged = {**before, **dict(payload.fields), "id": entry_id}
    try:
        if kind == "medication":
            validated = validate_medication(merged, assign_id=False)
            norm = normalize_medication_name(str(validated.get("name") or ""), db=db)
            validated["normalized_name"] = norm.normalized_name
            validated["rx_cui"] = norm.rx_cui
            validated["normalization_source"] = norm.normalization_source
            validated["is_normalized"] = norm.is_normalized
            updated = tag_provenance(validated, information_source="self-declared")
        else:
            validated = _VALIDATOR[kind](merged, assign_id=False)
            updated = tag_provenance(validated, information_source="self-declared")
    except PhrValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message
        ) from exc

    updated["id"] = entry_id
    items[target_idx] = updated
    if kind == "medication":
        items = flag_duplicate_medications(items)
    setattr(profile, column, items)

    audit_svc.record_change(
        db,
        profile=profile,
        action=audit_svc.ACTION_UPDATE,
        entity=kind,
        entity_id=entry_id,
        actor_user_id=user.id,
        before=before,
        after=updated,
        snapshot=_record_dict(profile, db),
    )
    db.commit()
    db.refresh(profile)
    return _enhanced_response(profile)


@router.delete("/entries/{kind}/{entry_id}", response_model=PhrEnhancedRecordResponse)
def delete_phr_entry(
    kind: str,
    entry_id: str,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> PhrEnhancedRecordResponse:
    _require_enhanced(settings)
    if kind not in _ENTRY_KINDS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown entry kind")
    user = _get_user_by_token(db, token)
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PHR record not found")

    column = _JSON_COLUMN[kind]
    items = _clean_object_list(getattr(profile, column))
    target = next((item for item in items if str(item.get("id")) == entry_id), None)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    items = [item for item in items if str(item.get("id")) != entry_id]
    setattr(profile, column, items)

    audit_svc.record_change(
        db,
        profile=profile,
        action=audit_svc.ACTION_DELETE,
        entity=kind,
        entity_id=entry_id,
        actor_user_id=user.id,
        before=target,
        snapshot=_record_dict(profile, db),
    )
    db.commit()
    db.refresh(profile)
    return _enhanced_response(profile)


@router.get("/history")
def get_phr_history(
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    """Return version snapshots in reverse-chronological order (Req 8.5)."""

    _require_enhanced(settings)
    user = _get_user_by_token(db, token)
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        return {"versions": []}
    versions = audit_svc.list_versions(db, profile_id=profile.id)
    return {
        "versions": [
            {
                "version_no": v.version_no,
                "snapshot": v.snapshot_json,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in versions
        ]
    }


# ---------------------------------------------------------------------------
# Consent (Req 2)
# ---------------------------------------------------------------------------


@router.get("/consent")
def get_phr_consent(
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    _require_enhanced(settings)
    user = _get_user_by_token(db, token)
    return {
        "purposes": list(PHR_CONSENT_PURPOSES),
        "consents": PhrConsentService.summary(db, user_id=user.id),
    }


@router.post("/consent")
def set_phr_consent(
    payload: PhrConsentMutationRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    _require_enhanced(settings)
    user = _get_user_by_token(db, token)
    if payload.granted:
        PhrConsentService.grant(db, user_id=user.id, purpose=payload.purpose)
    else:
        PhrConsentService.revoke(db, user_id=user.id, purpose=payload.purpose)
    db.commit()
    return {
        "purpose": payload.purpose,
        "granted": PhrConsentService.is_granted(db, user_id=user.id, purpose=payload.purpose),
    }


# ---------------------------------------------------------------------------
# Observations (Req 10)
# ---------------------------------------------------------------------------


_BODY_HEIGHT_OBSERVATION = "body_height_cm"
_BODY_WEIGHT_OBSERVATION = "body_weight_kg"


def _body_measurement_rows(profile: PhrProfile, db: Session) -> list[dict[str, Any]]:
    """Return only complete height/weight pairs, newest first.

    Generic observations deliberately do not imply that values on different
    dates belong together.  This projection accepts the two reserved body
    observation names only when both occur on the same date.
    """

    grouped: dict[date, dict[str, float]] = {}
    rows = db.execute(
        select(PhrObservation).where(
            PhrObservation.profile_id == profile.id,
            PhrObservation.name.in_((_BODY_HEIGHT_OBSERVATION, _BODY_WEIGHT_OBSERVATION)),
            PhrObservation.observed_on.is_not(None),
        )
    ).scalars()
    for row in rows:
        if row.observed_on is None:
            continue
        try:
            value = float(row.value)
        except (TypeError, ValueError):
            continue
        values = grouped.setdefault(row.observed_on, {})
        values[row.name] = value

    result: list[dict[str, Any]] = []
    for observed_on, values in grouped.items():
        height_cm = values.get(_BODY_HEIGHT_OBSERVATION)
        weight_kg = values.get(_BODY_WEIGHT_OBSERVATION)
        if height_cm is None or weight_kg is None:
            continue
        height_m = height_cm / 100
        result.append(
            {
                "observed_on": observed_on.isoformat(),
                "height_cm": height_cm,
                "weight_kg": weight_kg,
                "bmi": round(weight_kg / (height_m * height_m), 1),
                "information_source": "self-declared",
            }
        )
    return sorted(result, key=lambda item: str(item["observed_on"]), reverse=True)


@router.get("/body-measurements")
def list_phr_body_measurements(
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    if not phr_features(settings).observations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="PHR observations not enabled"
        )
    user = _get_user_by_token(db, token)
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        return {"measurements": []}
    return {"measurements": _body_measurement_rows(profile, db)}


@router.post("/body-measurements")
def create_phr_body_measurement(
    payload: PhrBodyMeasurementCreateRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    """Atomically record a paired body measurement and update current values."""

    if not phr_features(settings).observations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="PHR observations not enabled"
        )
    observed_on = payload.observed_on or date.today()
    try:
        validate_observation(
            {
                "name": _BODY_HEIGHT_OBSERVATION,
                "value": str(payload.height_cm),
                "unit": "cm",
                "observed_on": observed_on,
            }
        )
        validate_observation(
            {
                "name": _BODY_WEIGHT_OBSERVATION,
                "value": str(payload.weight_kg),
                "unit": "kg",
                "observed_on": observed_on,
            }
        )
    except PhrValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message
        ) from exc

    user = _get_user_by_token(db, token)
    profile = _get_or_create_profile(db, user.id)
    height = PhrObservation(
        profile_id=profile.id,
        entry_id=secrets.token_urlsafe(16),
        name=_BODY_HEIGHT_OBSERVATION,
        value=str(payload.height_cm),
        unit="cm",
        observed_on=observed_on,
        information_source="self-declared",
    )
    weight = PhrObservation(
        profile_id=profile.id,
        entry_id=secrets.token_urlsafe(16),
        name=_BODY_WEIGHT_OBSERVATION,
        value=str(payload.weight_kg),
        unit="kg",
        observed_on=observed_on,
        information_source="self-declared",
    )
    db.add_all((height, weight))
    profile.height_cm = payload.height_cm
    profile.weight_kg = payload.weight_kg
    audit_svc.record_change(
        db,
        profile=profile,
        action=audit_svc.ACTION_CREATE,
        entity="body_measurement",
        actor_user_id=user.id,
        # Audit metadata intentionally excludes sensitive measurement values.
        after={"observed_on": observed_on.isoformat(), "fields": ["height_cm", "weight_kg"]},
        snapshot=_record_dict(profile, db),
    )
    db.commit()
    height_m = payload.height_cm / 100
    return {
        "observed_on": observed_on.isoformat(),
        "height_cm": payload.height_cm,
        "weight_kg": payload.weight_kg,
        "bmi": round(payload.weight_kg / (height_m * height_m), 1),
        "information_source": "self-declared",
    }


@router.get("/observations")
def list_phr_observations(
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    if not phr_features(settings).observations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="PHR observations not enabled"
        )
    user = _get_user_by_token(db, token)
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        return {"observations": []}
    rows = db.execute(
        select(PhrObservation).where(PhrObservation.profile_id == profile.id)
    ).scalars()
    return {
        "observations": [
            {
                "entry_id": obs.entry_id,
                "name": obs.name,
                "value": obs.value,
                "unit": obs.unit,
                "observed_on": obs.observed_on.isoformat() if obs.observed_on else None,
                "information_source": obs.information_source,
                "ocr_confidence": obs.ocr_confidence,
            }
            for obs in rows
        ]
    }


@router.post("/observations")
def create_phr_observation(
    payload: PhrObservationCreateRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    if not phr_features(settings).observations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="PHR observations not enabled"
        )
    user = _get_user_by_token(db, token)
    profile = _get_or_create_profile(db, user.id)

    try:
        validated = validate_observation(
            {
                "name": payload.name,
                "value": payload.value,
                "unit": payload.unit,
                "observed_on": payload.observed_on,
            }
        )
    except PhrValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message
        ) from exc

    tagged = tag_provenance(validated, information_source="self-declared")
    obs = PhrObservation(
        profile_id=profile.id,
        entry_id=str(tagged.get("entry_id")),
        name=payload.name,
        value=payload.value,
        unit=payload.unit,
        observed_on=payload.observed_on,
        information_source="self-declared",
    )
    db.add(obs)
    audit_svc.record_change(
        db,
        profile=profile,
        action=audit_svc.ACTION_CREATE,
        entity="observation",
        entity_id=obs.entry_id,
        actor_user_id=user.id,
        after={"name": payload.name, "unit": payload.unit},
        snapshot=_record_dict(profile, db),
    )
    db.commit()
    return {
        "entry_id": obs.entry_id,
        "name": obs.name,
        "value": obs.value,
        "unit": obs.unit,
        "information_source": obs.information_source,
    }


# ---------------------------------------------------------------------------
# Completeness (Req 16)
# ---------------------------------------------------------------------------


@router.get("/completeness")
def get_phr_completeness(
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    if not phr_features(settings).completeness_meter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="PHR completeness meter not enabled"
        )
    user = _get_user_by_token(db, token)
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    record = _record_dict(profile, db) if profile is not None else {}
    result = score_completeness(record)
    # Telemetry projection is PII-free (counts/class names only).
    result["telemetry"] = completeness_telemetry(record)
    return result


# ---------------------------------------------------------------------------
# FHIR export (Req 11)
# ---------------------------------------------------------------------------


@router.get("/export")
def export_phr(
    resource: str = "all",
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> Response:
    if not phr_features(settings).export:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PHR export not enabled")
    user = _get_user_by_token(db, token)
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    record = _record_dict(profile, db) if profile is not None else {}
    try:
        bundle = to_bundle(record, resource=resource)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    if profile is not None:
        audit_svc.write_audit(
            db,
            profile_id=profile.id,
            action=audit_svc.ACTION_EXPORT,
            entity="profile",
            actor_user_id=user.id,
            scope=resource,
        )
        db.commit()
    import json

    return Response(
        content=json.dumps(bundle, ensure_ascii=False),
        media_type="application/fhir+json",
        headers={"Content-Disposition": f'attachment; filename="phr-export-{resource}.json"'},
    )


# ---------------------------------------------------------------------------
# Sharing + access logging (Req 12) + emergency card (Req 13)
# ---------------------------------------------------------------------------


@router.post("/share")
def create_phr_share(
    payload: PhrShareCreateRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    if not phr_features(settings).sharing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PHR sharing not enabled")
    user = _get_user_by_token(db, token)

    # Sharing consent is required when consent enforcement is on (Req 2.5, 12.6).
    if phr_features(settings).consent_enforcement and not PhrConsentService.is_granted(
        db, user_id=user.id, purpose="sharing"
    ):
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail=(
                "Cần đồng ý chia sẻ hồ sơ trước khi tạo liên kết / "
                "PHR sharing consent is required before creating a share link"
            ),
        )

    # Compliance granular-consent gate (Req 2.1, 2.3): when
    # COMPLIANCE_GRANULAR_CONSENT_ENABLED is on, also require the
    # compliance-ledger sharing grant. Flag off ⇒ has_consent returns True, so
    # legacy behavior is preserved exactly.
    if not ComplianceService(db, settings=settings).has_consent(
        user_id=user.id, purpose=PURPOSE_SHARING
    ):
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail=(
                "Cần đồng ý chia sẻ hồ sơ trước khi tạo liên kết / "
                "PHR sharing consent is required before creating a share link"
            ),
        )

    expires_at = datetime.now(UTC) + timedelta(days=payload.expires_in_days)
    share_token = secrets.token_urlsafe(24)
    share = PhrShare(
        user_id=user.id,
        token_hash=_phr_share_token_hash(share_token),
        scope=payload.scope,
        is_active=True,
        expires_at=expires_at,
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    return {
        "share_id": share.id,
        "share_token": share_token,
        "scope": share.scope,
        "expires_at": share.expires_at.isoformat() if share.expires_at else None,
    }


@router.delete("/share/{share_id}")
def revoke_phr_share(
    share_id: int,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    if not phr_features(settings).sharing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PHR sharing not enabled")
    user = _get_user_by_token(db, token)
    share = db.execute(
        select(PhrShare).where(PhrShare.id == share_id, PhrShare.user_id == user.id)
    ).scalar_one_or_none()
    if share is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")
    share.is_active = False
    db.commit()
    return {"revoked": True}


@router.get("/shared/{token_value}")
def read_shared_phr(
    token_value: str,
    db: Session = Depends(get_db),
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    """Public read-only share view. Revoked/expired tokens deny access (Req 12)."""

    if not phr_features(settings).sharing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PHR sharing not enabled")
    share = db.execute(
        select(PhrShare).where(PhrShare.token_hash == _phr_share_token_hash(token_value))
    ).scalar_one_or_none()
    if share is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_PUBLIC_PHR_SHARE_UNAVAILABLE,
        )
    if not share.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_PUBLIC_PHR_SHARE_UNAVAILABLE,
        )
    if share.expires_at is not None and datetime.now(UTC) >= _aware(share.expires_at):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_PUBLIC_PHR_SHARE_UNAVAILABLE,
        )

    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == share.user_id)
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PHR record not found")

    record = _record_dict(profile, db)
    # Access logging on share read (Req 8.3, 12.4).
    audit_svc.record_access(
        db,
        profile_id=profile.id,
        accessor_user_id=None,
        scope=share.scope,
        share_read=True,
    )
    db.commit()

    if share.scope == "emergency_card":
        return {
            "scope": "emergency_card",
            "emergency_card": build_emergency_card(record, profile.emergency_card_prefs_json),
        }
    return {
        "scope": "full",
        "record": record,
        "hedge": hedge_text_bilingual(),
    }


@router.get("/emergency-card")
def get_phr_emergency_card(
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    _require_enhanced(settings)
    user = _get_user_by_token(db, token)
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    record = _record_dict(profile, db) if profile is not None else {}
    prefs = profile.emergency_card_prefs_json if profile is not None else None
    # Append an access audit row for every emergency-card access (Req 13.2,
    # Correctness Property 12).
    if profile is not None:
        audit_svc.record_access(
            db,
            profile_id=profile.id,
            accessor_user_id=user.id,
            scope="emergency_card",
        )
        db.commit()
    return {"emergency_card": build_emergency_card(record, prefs)}


def _aware(value: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (SQLite may return naive)."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _ocr_review_candidate_ids(candidate_ids: list[str]) -> list[str]:
    """Validate opaque IDs; the token never carries OCR text or medications."""

    if (
        len(candidate_ids) != len(set(candidate_ids))
        or any(not isinstance(item, str) or not item.strip() for item in candidate_ids)
    ):
        raise ValueError("ocr_review_candidate_ids_invalid")
    return sorted(candidate_ids)


def _make_ocr_review_token(*, user_id: int, candidate_ids: list[str]) -> str:
    """Create a short-lived, owner-bound capability for review-only OCR rows."""

    expires_at = int(time.time()) + _OCR_REVIEW_TOKEN_TTL_SECONDS
    encoded_ids = base64.urlsafe_b64encode(
        json.dumps(_ocr_review_candidate_ids(candidate_ids), separators=(",", ":")).encode()
    ).decode().rstrip("=")
    message = f"{_OCR_REVIEW_TOKEN_VERSION}:{user_id}:{expires_at}:{encoded_ids}"
    signature = hmac.new(
        get_settings().jwt_secret_key.encode(), message.encode(), hashlib.sha256
    ).hexdigest()
    return f"{expires_at}.{encoded_ids}.{signature}"


def _verify_ocr_review_token(*, token: str, user_id: int, candidate_ids: list[str]) -> None:
    """Reject stale, cross-user or substituted OCR candidate sets without logging text."""

    try:
        raw_expiry, encoded_ids, supplied_signature = token.split(".", 2)
        expires_at = int(raw_expiry)
        padding = "=" * (-len(encoded_ids) % 4)
        allowed_ids = json.loads(
            base64.urlsafe_b64decode(f"{encoded_ids}{padding}").decode()
        )
        if not isinstance(allowed_ids, list):
            raise ValueError("ocr_review_candidate_ids_invalid")
        allowed_ids = _ocr_review_candidate_ids(allowed_ids)
        submitted_ids = _ocr_review_candidate_ids(candidate_ids)
        if not set(submitted_ids).issubset(set(allowed_ids)):
            raise ValueError("ocr_review_candidate_ids_invalid")
    except (
        AttributeError,
        TypeError,
        UnicodeDecodeError,
        ValueError,
        binascii.Error,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OCR review expired",
        ) from exc
    message = f"{_OCR_REVIEW_TOKEN_VERSION}:{user_id}:{expires_at}:{encoded_ids}"
    expected = hmac.new(
        get_settings().jwt_secret_key.encode(), message.encode(), hashlib.sha256
    ).hexdigest()
    if (
        expires_at < int(time.time())
        or not hmac.compare_digest(supplied_signature, expected)
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="OCR review expired")


# ---------------------------------------------------------------------------
# OCR import with mandatory human confirmation (Req 9)
# ---------------------------------------------------------------------------


@router.post("/import/ocr/scan", response_model=PhrOcrScanResponse)
async def scan_phr_ocr(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> PhrOcrScanResponse:
    """Return OCR candidate entries WITHOUT committing anything (Req 9.1, 9.6).

    Reuses the careguard OCR bridge. Nothing is written to the PHR here; the user
    must call ``/import/ocr/confirm`` to commit (Correctness Property 14).
    """

    if not phr_features(settings).ocr_import:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="PHR OCR import not enabled"
        )
    user = _get_user_by_token(db, token)
    ensure_medical_disclaimer_consent(db, user_id=user.id)

    # Lazy import keeps the careguard import cycle out of module load.
    from clara_api.api.v1.endpoints.careguard import (
        _apply_ocr_correction,
        _attach_ocr_source_coordinates,
        _detect_drugs_from_text,
        _enforce_low_confidence_manual_confirm,
        _reject_ocr_prompt_injection,
        _scan_with_tgc_ocr,
    )

    file_name = file.filename or "uploaded-document"
    content_type = file.content_type or "application/octet-stream"
    file_bytes = await read_upload_bytes_with_limit(file, max_bytes=20 * 1024 * 1024)
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file upload")
    try:
        verified = verify_upload(
            filename=file_name,
            content_type=content_type,
            data=file_bytes,
            fallback_filename="uploaded-document",
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
    file_name = verified.filename
    content_type = verified.media_type
    extracted_text, engine, _raw = _scan_with_tgc_ocr(file_bytes, file_name, content_type)
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
    candidates = [
        {
            "candidate_id": secrets.token_urlsafe(18),
            "name": d.drug_name or d.normalized_name,
            "dose": d.dosage or "",
            "frequency": "",
            "ocr_confidence": d.confidence,
            # Every OCR row is review-only. A displayed confidence is never a
            # substitute for the explicit acknowledgement on confirm.
            "requires_manual_confirm": True,
            "confirmed": False,
            "source_coordinates": d.source_coordinates,
        }
        for d in detections[:120]
    ]
    engine_value = str(engine or "").lower()
    provider_category = (
        "google_cloud_vision"
        if "google" in engine_value or "vision" in engine_value
        else "local_tesseract"
        if "tesseract" in engine_value
        else "configured_ocr_service"
    )
    candidate_ids = [str(candidate["candidate_id"]) for candidate in candidates]
    return PhrOcrScanResponse(
        candidates=candidates,
        review_token=_make_ocr_review_token(user_id=user.id, candidate_ids=candidate_ids),
        processing_disclosure={
            "processing_purpose": "medication_candidate_extraction",
            "provider_category": provider_category,
            "upload_persisted_by_clara": False,
            "raw_text_logged_by_clara": False,
            "human_confirmation_required": True,
        },
    )


@router.post("/import/ocr/confirm", response_model=PhrEnhancedRecordResponse)
def confirm_phr_ocr(
    payload: PhrOcrConfirmRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> PhrEnhancedRecordResponse:
    """Commit the user-edited candidate list as ``ocr``-sourced entries (Req 9.2, 9.4).

    Low-confidence candidates still flagged ``requires_manual_confirm`` are
    rejected so unconfirmed low-confidence rows are blocked from commit.
    """

    if not phr_features(settings).ocr_import:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="PHR OCR import not enabled"
        )
    user = _get_user_by_token(db, token)
    ensure_medical_disclaimer_consent(db, user_id=user.id)
    profile = _get_or_create_profile(db, user.id)

    candidate_ids = payload.review_candidate_ids
    _verify_ocr_review_token(
        token=payload.review_token,
        user_id=user.id,
        candidate_ids=candidate_ids,
    )
    confirmed_candidate_ids = [candidate.candidate_id for candidate in payload.medications]
    if (
        len(confirmed_candidate_ids) != len(set(confirmed_candidate_ids))
        or any(candidate_id not in set(candidate_ids) for candidate_id in confirmed_candidate_ids)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="OCR review candidates are invalid.",
        )

    items = _clean_object_list(profile.medications_json)
    added: list[str] = []
    for candidate in payload.medications:
        if not candidate.confirmed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Mỗi mục OCR cần được xác nhận trước khi lưu.",
            )
        try:
            validated = validate_medication(
                {
                    "name": candidate.name,
                    "dose": candidate.dose,
                    "frequency": candidate.frequency,
                }
            )
        except PhrValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message
            ) from exc
        norm = normalize_medication_name(candidate.name, db=db)
        validated["normalized_name"] = norm.normalized_name
        validated["rx_cui"] = norm.rx_cui
        validated["normalization_source"] = norm.normalization_source
        validated["is_normalized"] = norm.is_normalized
        tagged = tag_provenance(
            validated,
            information_source="ocr",
            ocr_confidence=candidate.ocr_confidence,
        )
        items.append(tagged)
        added.append(str(tagged.get("id")))

    items = flag_duplicate_medications(items)
    profile.medications_json = items
    audit_svc.record_change(
        db,
        profile=profile,
        action=audit_svc.ACTION_CREATE,
        entity="medication",
        entity_id=",".join(added),
        actor_user_id=user.id,
        after={"ocr_imported_count": len(added)},
        snapshot=_record_dict(profile, db),
    )
    db.commit()
    db.refresh(profile)
    return _enhanced_response(profile)


# ---------------------------------------------------------------------------
# Reminders / refill / caregiver nudge (Req 14)
# ---------------------------------------------------------------------------


def _parse_scheduled_time(schedule: dict[str, Any]) -> datetime | None:
    """Parse the next scheduled dose time from a reminder's ``schedule_json``.

    Accepts an ISO-8601 ``next_time`` value; returns ``None`` when absent or
    unparseable so the medication-reminder decision simply does not fire.
    """

    raw = schedule.get("next_time") if isinstance(schedule, dict) else None
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _caregiver_share_active(db: Session, user_id: int) -> bool:
    """A caregiver share is active when the owner has at least one active,
    unexpired share link (Req 14.5)."""

    now = datetime.now(UTC)
    shares = db.execute(
        select(PhrShare).where(PhrShare.user_id == user_id, PhrShare.is_active.is_(True))
    ).scalars()
    for share in shares:
        if share.expires_at is None or share.expires_at > now:
            return True
    return False


def _dispatch_reminder_notification(
    settings: Settings, *, recipient: str, subject: str, body: str
) -> str:
    """Reuse the existing notification (SMTP) path for reminder dispatch.

    Mirrors the auth email delivery modes so reminders never attempt a real send
    in ``preview``/``disabled`` environments (e.g. tests, local dev)."""

    mode = settings.auth_email_delivery_mode
    if mode == "disabled":
        return "disabled"
    if mode == "preview":
        return "preview"
    return _send_via_smtp(settings, recipient=recipient, subject=subject, body=body)


@router.get("/reminders")
def list_phr_reminders(
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    if not phr_features(settings).reminders:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="PHR reminders not enabled"
        )
    user = _get_user_by_token(db, token)
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        return {"reminders": []}
    rows = db.execute(select(PhrReminder).where(PhrReminder.profile_id == profile.id)).scalars()
    meds_by_id = {str(m.get("id")): m for m in _clean_object_list(profile.medications_json)}
    caregiver_active = _caregiver_share_active(db, user.id)
    now = datetime.now(UTC)
    out = []
    for r in rows:
        schedule = r.schedule_json or {}
        med = meds_by_id.get(str(r.medication_entry_id), {})
        decision = evaluate_reminder(
            is_current=bool(med.get("is_current", True)),
            frequency=str(schedule.get("frequency") or med.get("frequency") or ""),
            scheduled_time=_parse_scheduled_time(schedule),
            now=now,
            remaining_supply=r.remaining_supply,
            refill_threshold=r.refill_threshold,
            nudge_enabled=bool(r.caregiver_nudge_enabled),
            caregiver_share_active=caregiver_active,
            dose_marked_taken=False,
            within_window=True,
        )
        out.append(
            {
                "id": r.id,
                "medication_entry_id": r.medication_entry_id,
                "schedule": r.schedule_json,
                "remaining_supply": r.remaining_supply,
                "refill_threshold": r.refill_threshold,
                "caregiver_nudge_enabled": r.caregiver_nudge_enabled,
                "medication_due": decision.fire_medication_reminder,
                "refill_due": decision.fire_refill_reminder,
            }
        )
    return {"reminders": out}


@router.post("/reminders")
def create_phr_reminder(
    payload: PhrReminderCreateRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    if not phr_features(settings).reminders:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="PHR reminders not enabled"
        )
    user = _get_user_by_token(db, token)
    profile = _get_or_create_profile(db, user.id)

    # Reminders are configurable only for current meds with a defined frequency.
    meds = _clean_object_list(profile.medications_json)
    target = next(
        (m for m in meds if str(m.get("id")) == payload.medication_entry_id),
        None,
    )
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Medication entry not found"
        )
    if not target.get("is_current", True) or not str(target.get("frequency") or "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Chỉ đặt nhắc cho thuốc đang dùng có tần suất / reminders require a current "
                "medication with a defined frequency"
            ),
        )

    reminder = PhrReminder(
        profile_id=profile.id,
        medication_entry_id=payload.medication_entry_id,
        schedule_json=payload.schedule,
        remaining_supply=payload.remaining_supply,
        refill_threshold=payload.refill_threshold,
        caregiver_nudge_enabled=payload.caregiver_nudge_enabled,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return {
        "id": reminder.id,
        "medication_entry_id": reminder.medication_entry_id,
        "caregiver_nudge_enabled": reminder.caregiver_nudge_enabled,
    }


@router.post("/reminders/dispatch")
def dispatch_phr_reminders(
    payload: PhrReminderDispatchRequest,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    """Evaluate the owner's reminders and wire firing decisions to the existing
    notification dispatch path.

    Medication-due (Req 14.2) and refill (Req 14.4) reminders are issued to the
    owner; the caregiver missed-dose nudge (Req 14.5) is issued only when the
    nudge is enabled, an active caregiver share exists, and the dose was not
    marked taken past the configured window. The pure firing logic lives in
    :func:`clara_api.phr.reminders.evaluate_reminder`; only dispatch happens
    here, reusing the existing notification path.
    """

    if not phr_features(settings).reminders:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="PHR reminders not enabled"
        )
    user = _get_user_by_token(db, token)
    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is None:
        return {"dispatched": []}

    rows = db.execute(select(PhrReminder).where(PhrReminder.profile_id == profile.id)).scalars()
    meds_by_id = {str(m.get("id")): m for m in _clean_object_list(profile.medications_json)}
    caregiver_active = _caregiver_share_active(db, user.id)
    now = payload.now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    dispatched: list[dict[str, Any]] = []
    for r in rows:
        schedule = r.schedule_json or {}
        med = meds_by_id.get(str(r.medication_entry_id), {})
        dose_state = payload.dose_states.get(str(r.medication_entry_id))
        decision = evaluate_reminder(
            is_current=bool(med.get("is_current", True)),
            frequency=str(schedule.get("frequency") or med.get("frequency") or ""),
            scheduled_time=_parse_scheduled_time(schedule),
            now=now,
            remaining_supply=r.remaining_supply,
            refill_threshold=r.refill_threshold,
            nudge_enabled=bool(r.caregiver_nudge_enabled),
            caregiver_share_active=caregiver_active,
            dose_marked_taken=bool(dose_state.dose_marked_taken) if dose_state else False,
            within_window=bool(dose_state.within_window) if dose_state else True,
        )

        notifications: list[str] = []
        med_name = str(med.get("name") or med.get("display") or r.medication_entry_id)
        if decision.fire_medication_reminder:
            _dispatch_reminder_notification(
                settings,
                recipient=user.email,
                subject="[CLARA] Nhac uong thuoc / Medication reminder",
                body=(
                    f"Da den gio dung thuoc: {med_name}.\n"
                    "Day la nhac nho tu thong tin ban tu khai / based on your self-entered "
                    "information. Vui long trao doi voi bac si khi can."
                ),
            )
            notifications.append("medication")
        if decision.fire_refill_reminder:
            _dispatch_reminder_notification(
                settings,
                recipient=user.email,
                subject="[CLARA] Nhac mua them thuoc / Refill reminder",
                body=(
                    f"Thuoc {med_name} sap het (con {r.remaining_supply}). "
                    "Vui long chuan bi mua them / time to refill."
                ),
            )
            notifications.append("refill")
        if decision.notify_caregiver:
            # Caregiver notification reuses the same dispatch path. Caregiver
            # access is link-based (no stored caregiver address), so the
            # missed-dose nudge is routed to the owner's contact channel.
            _dispatch_reminder_notification(
                settings,
                recipient=user.email,
                subject="[CLARA] Nhac nguoi cham soc / Caregiver nudge",
                body=(
                    f"Lieu thuoc {med_name} chua duoc xac nhan trong khung gio quy dinh. "
                    "Nguoi cham soc da duoc thong bao / caregiver has been notified."
                ),
            )
            notifications.append("caregiver")

        dispatched.append(
            {
                "id": r.id,
                "medication_entry_id": r.medication_entry_id,
                "medication_due": decision.fire_medication_reminder,
                "refill_due": decision.fire_refill_reminder,
                "caregiver_nudge": decision.notify_caregiver,
                "reason": decision.reason,
                "notifications": notifications,
            }
        )

    return {"dispatched": dispatched}
