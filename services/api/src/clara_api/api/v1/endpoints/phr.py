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

import secrets
from datetime import UTC, datetime, timedelta
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
from clara_api.core.consent import PHR_CONSENT_PURPOSES, PhrConsentService
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
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
    PhrConsentMutationRequest,
    PhrEnhancedRecordResponse,
    PhrEntryPatchRequest,
    PhrObservationCreateRequest,
    PhrOcrConfirmRequest,
    PhrRecordResponse,
    PhrRecordUpdateRequest,
    PhrReminderCreateRequest,
    PhrReminderDispatchRequest,
    PhrShareCreateRequest,
)

router = APIRouter()

USER_ROLE_DEP = Depends(require_roles("normal", "researcher", "doctor", "admin"))
SETTINGS_DEP = Depends(get_settings)


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

    expires_at = None
    if payload.expires_in_days is not None:
        expires_at = datetime.now(UTC) + timedelta(days=payload.expires_in_days)
    share = PhrShare(
        user_id=user.id,
        share_token=secrets.token_urlsafe(24),
        scope=payload.scope,
        is_active=True,
        expires_at=expires_at,
    )
    db.add(share)
    db.commit()
    return {
        "share_token": share.share_token,
        "scope": share.scope,
        "expires_at": share.expires_at.isoformat() if share.expires_at else None,
    }


@router.delete("/share/{token_value}")
def revoke_phr_share(
    token_value: str,
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    if not phr_features(settings).sharing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PHR sharing not enabled")
    user = _get_user_by_token(db, token)
    share = db.execute(
        select(PhrShare).where(PhrShare.share_token == token_value, PhrShare.user_id == user.id)
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
        select(PhrShare).where(PhrShare.share_token == token_value)
    ).scalar_one_or_none()
    if share is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")
    if not share.is_active:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Share has been revoked")
    if share.expires_at is not None and datetime.now(UTC) >= _aware(share.expires_at):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Share has expired")

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


# ---------------------------------------------------------------------------
# OCR import with mandatory human confirmation (Req 9)
# ---------------------------------------------------------------------------


@router.post("/import/ocr/scan")
async def scan_phr_ocr(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    token: TokenPayload = USER_ROLE_DEP,
    settings: Settings = SETTINGS_DEP,
) -> dict[str, Any]:
    """Return OCR candidate entries WITHOUT committing anything (Req 9.1, 9.6).

    Reuses the careguard OCR bridge. Nothing is written to the PHR here; the user
    must call ``/import/ocr/confirm`` to commit (Correctness Property 14).
    """

    if not phr_features(settings).ocr_import:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="PHR OCR import not enabled"
        )
    _get_user_by_token(db, token)

    # Lazy import keeps the careguard import cycle out of module load.
    from clara_api.api.v1.endpoints.careguard import (
        _detect_drugs_from_text,
        _enforce_low_confidence_manual_confirm,
        _scan_with_tgc_ocr,
    )

    file_name = file.filename or "uploaded-document"
    content_type = file.content_type or "application/octet-stream"
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file upload")
    extracted_text, _engine, _raw = _scan_with_tgc_ocr(file_bytes, file_name, content_type)
    detections = _enforce_low_confidence_manual_confirm(
        _detect_drugs_from_text(extracted_text, db=db)
    )
    candidates = [
        {
            "name": d.drug_name or d.normalized_name,
            "dose": d.dosage or "",
            "frequency": "",
            "ocr_confidence": d.confidence,
            "requires_manual_confirm": d.requires_manual_confirm,
        }
        for d in detections
    ]
    return {"committed": False, "candidates": candidates}


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
    profile = _get_or_create_profile(db, user.id)

    items = _clean_object_list(profile.medications_json)
    added: list[str] = []
    for candidate in payload.medications:
        if candidate.requires_manual_confirm:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Mục cần xác nhận thủ công trước khi lưu / candidate still requires "
                    f"manual confirmation: '{candidate.name}'"
                ),
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
