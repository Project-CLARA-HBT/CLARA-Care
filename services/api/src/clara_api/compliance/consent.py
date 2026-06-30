"""Purpose-typed, append-only consent ledger for the compliance layer.

Extends the existing ``UserConsent`` model (consent_type free-text column) with
the broadened purpose vocabulary required by PDPD Art. 13/17 and the AI Law
cross-border obligation. The ledger is append-only: a withdrawal appends a new
row (status recorded via ``revoked_at``) and never deletes the prior grant
(Correctness Property 1).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.db.models import UserConsent

# Purpose vocabulary (Requirement 2.1). Stored in ``UserConsent.consent_type``
# with a ``compliance:`` namespace prefix so it never collides with the legacy
# ``medical_disclaimer`` / ``phr_*`` consent types.
PURPOSE_CORE_SERVICE = "core_service"
PURPOSE_PERSONALIZATION = "personalization"
PURPOSE_RESEARCH = "research"
PURPOSE_CROSS_BORDER = "cross_border_processing"
PURPOSE_SHARING = "sharing"
PURPOSE_AI_TRANSPARENCY = "ai_transparency"

COMPLIANCE_PURPOSES = frozenset(
    {
        PURPOSE_CORE_SERVICE,
        PURPOSE_PERSONALIZATION,
        PURPOSE_RESEARCH,
        PURPOSE_CROSS_BORDER,
        PURPOSE_SHARING,
        PURPOSE_AI_TRANSPARENCY,
    }
)

_CONSENT_TYPE_PREFIX = "compliance:"


def consent_type_for(purpose: str) -> str:
    return f"{_CONSENT_TYPE_PREFIX}{purpose}"


def is_valid_purpose(purpose: str) -> bool:
    return purpose in COMPLIANCE_PURPOSES


def _latest_row(db: Session, *, user_id: int, purpose: str) -> UserConsent | None:
    # The ledger is append-only, so several rows can exist for one purpose; take
    # the most recent (``.first()``, never ``scalar_one_or_none`` which would
    # raise on >1 row).
    consent_type = consent_type_for(purpose)
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


def has_consent(db: Session, *, user_id: int, purpose: str) -> bool:
    """True iff the latest ledger row for the purpose is an active grant.

    "Active" = a row exists whose ``revoked_at`` is null (Property 1).
    """

    if not is_valid_purpose(purpose):
        return False
    latest = _latest_row(db, user_id=user_id, purpose=purpose)
    return bool(latest and latest.revoked_at is None)


def acknowledged_version(db: Session, *, user_id: int, purpose: str) -> str | None:
    """Return the version of the latest *active* grant for the purpose.

    Returns ``None`` when there is no active grant (never granted or withdrawn).
    Used by the AI Transparency Notice endpoint to detect that a newer notice
    version has not yet been re-acknowledged (Requirement 1.6).
    """

    if not is_valid_purpose(purpose):
        return None
    latest = _latest_row(db, user_id=user_id, purpose=purpose)
    if latest and latest.revoked_at is None:
        return latest.consent_version
    return None


def grant(db: Session, *, user_id: int, purpose: str, version: str) -> UserConsent:
    """Append a new grant row to the ledger (never mutates a prior row)."""

    row = UserConsent(
        user_id=user_id,
        consent_type=consent_type_for(purpose),
        consent_version=version,
    )
    db.add(row)
    db.flush()
    return row


def withdraw(db: Session, *, user_id: int, purpose: str, version: str = "") -> UserConsent:
    """Append a withdrawal row (``revoked_at`` set) — append-only (Property 1)."""

    latest = _latest_row(db, user_id=user_id, purpose=purpose)
    effective_version = version or (latest.consent_version if latest else "")
    row = UserConsent(
        user_id=user_id,
        consent_type=consent_type_for(purpose),
        consent_version=effective_version,
        revoked_at=datetime.now(UTC),
    )
    db.add(row)
    db.flush()
    return row


def consent_summary(db: Session, *, user_id: int) -> dict[str, bool]:
    """Return ``{purpose: granted}`` for every compliance purpose."""

    return {
        purpose: has_consent(db, user_id=user_id, purpose=purpose)
        for purpose in sorted(COMPLIANCE_PURPOSES)
    }
