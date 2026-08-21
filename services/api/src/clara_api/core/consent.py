from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.core.config import get_settings
from clara_api.db.models import UserConsent

MEDICAL_CONSENT_TYPE = "medical_disclaimer"

# Typed/versioned PHR consent purposes (Req 2.1). Each grant/revoke is a new
# append-only ``UserConsent`` row distinguished by ``consent_type``; the ledger
# is never mutated in place.
PhrConsentPurpose = Literal["personalization", "research", "sharing"]

PHR_CONSENT_TYPES: dict[str, str] = {
    "personalization": "phr_personalization",
    "research": "phr_research",
    "sharing": "phr_sharing",
}

PHR_CONSENT_PURPOSES: tuple[str, ...] = tuple(PHR_CONSENT_TYPES.keys())

# Default version stamped on PHR consent grants when the caller does not supply
# one; mirrors the medical-disclaimer version convention.
DEFAULT_PHR_CONSENT_VERSION = "2026-04-v1"


def get_latest_user_consent(
    db: Session,
    *,
    user_id: int,
    consent_type: str = MEDICAL_CONSENT_TYPE,
) -> UserConsent | None:
    return (
        db.execute(
            select(UserConsent)
            .where(
                UserConsent.user_id == user_id,
                UserConsent.consent_type == consent_type,
            )
            .order_by(UserConsent.accepted_at.desc(), UserConsent.id.desc())
        )
        .scalars()
        .first()
    )


def required_medical_disclaimer_version() -> str:
    return get_settings().medical_disclaimer_version.strip() or "2026-04-v1"


def ensure_medical_disclaimer_consent(db: Session, *, user_id: int) -> UserConsent:
    required_version = required_medical_disclaimer_version()
    latest = get_latest_user_consent(
        db,
        user_id=user_id,
        consent_type=MEDICAL_CONSENT_TYPE,
    )
    if latest and latest.consent_version == required_version and latest.revoked_at is None:
        return latest

    raise HTTPException(
        status_code=status.HTTP_428_PRECONDITION_REQUIRED,
        detail=(
            "Bạn cần đồng ý tuyên bố miễn trừ trách nhiệm y tế "
            f"(phiên bản {required_version}) trước khi sử dụng tính năng này"
        ),
    )


def _phr_consent_type(purpose: str) -> str:
    consent_type = PHR_CONSENT_TYPES.get(purpose)
    if consent_type is None:
        raise ValueError(f"unknown PHR consent purpose: {purpose!r}")
    return consent_type


class PhrConsentService:
    """Typed/versioned PHR consent gate over the shared ``UserConsent`` ledger.

    A grant or revoke is always a *new* append-only row (the ledger is never
    mutated in place). "Currently granted" for a purpose is derived from the
    latest row per ``(user_id, consent_type)``: it must be a grant
    (``revoked_at IS NULL``). Revocation therefore takes effect on the next
    request because each request reads current consent (Req 2.1, 2.4, 2.6).
    """

    @staticmethod
    def _latest_row(
        db: Session,
        *,
        user_id: int,
        purpose: str,
        for_update: bool = False,
    ) -> UserConsent | None:
        consent_type = _phr_consent_type(purpose)
        stmt = (
            select(UserConsent)
            .where(
                UserConsent.user_id == user_id,
                UserConsent.consent_type == consent_type,
            )
            .order_by(UserConsent.accepted_at.desc(), UserConsent.id.desc())
        )
        if for_update:
            stmt = stmt.with_for_update()
        return (
            db.execute(stmt)
            .scalars()
            .first()
        )

    @classmethod
    def is_granted(cls, db: Session, *, user_id: int, purpose: str) -> bool:
        """True iff the latest PHR consent row for the purpose is an active grant."""

        if purpose not in PHR_CONSENT_TYPES:
            return False
        latest = cls._latest_row(db, user_id=user_id, purpose=purpose)
        return bool(latest and latest.revoked_at is None)

    @classmethod
    def grant(
        cls,
        db: Session,
        *,
        user_id: int,
        purpose: str,
        version: str = DEFAULT_PHR_CONSENT_VERSION,
    ) -> UserConsent:
        """Append a new typed/versioned grant row (Req 2.1, 2.6)."""

        row = UserConsent(
            user_id=user_id,
            consent_type=_phr_consent_type(purpose),
            consent_version=version or DEFAULT_PHR_CONSENT_VERSION,
        )
        db.add(row)
        db.flush()
        return row

    @classmethod
    def revoke(cls, db: Session, *, user_id: int, purpose: str) -> UserConsent:
        """Append a revoked row setting ``revoked_at`` — append-only (Req 2.4, 2.6)."""

        latest = cls._latest_row(db, user_id=user_id, purpose=purpose)
        version = latest.consent_version if latest else DEFAULT_PHR_CONSENT_VERSION
        row = UserConsent(
            user_id=user_id,
            consent_type=_phr_consent_type(purpose),
            consent_version=version,
            revoked_at=datetime.now(UTC),
        )
        db.add(row)
        db.flush()
        return row

    @classmethod
    def summary(cls, db: Session, *, user_id: int) -> dict[str, bool]:
        """Return ``{purpose: granted}`` for every PHR consent purpose."""

        return {
            purpose: cls.is_granted(db, user_id=user_id, purpose=purpose)
            for purpose in PHR_CONSENT_PURPOSES
        }
