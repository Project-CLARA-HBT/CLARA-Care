from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.core.config import get_settings
from clara_api.db.models import UserConsent

MEDICAL_CONSENT_TYPE = "medical_disclaimer"


def get_latest_user_consent(
    db: Session,
    *,
    user_id: int,
    consent_type: str = MEDICAL_CONSENT_TYPE,
) -> UserConsent | None:
    return db.execute(
        select(UserConsent)
        .where(
            UserConsent.user_id == user_id,
            UserConsent.consent_type == consent_type,
        )
        .order_by(UserConsent.accepted_at.desc(), UserConsent.id.desc())
    ).scalar_one_or_none()


def required_medical_disclaimer_version() -> str:
    return get_settings().medical_disclaimer_version.strip() or "2026-04-v1"


def ensure_medical_disclaimer_consent(db: Session, *, user_id: int) -> UserConsent:
    required_version = required_medical_disclaimer_version()
    latest = get_latest_user_consent(
        db,
        user_id=user_id,
        consent_type=MEDICAL_CONSENT_TYPE,
    )
    if latest and latest.consent_version == required_version:
        return latest

    raise HTTPException(
        status_code=status.HTTP_428_PRECONDITION_REQUIRED,
        detail=(
            "Bạn cần đồng ý tuyên bố miễn trừ trách nhiệm y tế "
            f"(phiên bản {required_version}) trước khi sử dụng tính năng này"
        ),
    )
