"""Admin observability control endpoints (Requirements 8.4, 1.1).

This module exposes the admin-gated write surface for the observability alert
engine implemented in :mod:`clara_api.observability.alerts`. It declares a
single admin-gated ``POST`` route that acknowledges a firing alert by its
*stable* alert id (the dedupe key derived from ``rule + target``), delegating to
:meth:`clara_api.observability.alerts.AlertEngine.acknowledge`.

Like the other flag-gated admin surfaces (``admin_rag.py`` ingestion controls,
``admin_audit.py``, ``system.py`` analytics), the endpoint ships dark: when
``admin_observability_alerting_enabled`` is off it returns the project's standard
"feature-disabled" HTTP 404 shape rather than a partial/empty success, so the
surface is invisible until alerting is turned on (Requirements 12.2, 12.4). The
flag check runs inside the handler body so the ``require_roles("admin")``
dependency still authorizes the caller first (403 for non-admin, 401 for a
missing/invalid token — Requirement 1.1).

Every acknowledge — whether it succeeds or fails (unknown id) — is recorded
inline as an append-only admin-action audit row via
:func:`clara_api.observability.admin_audit.record_admin_action` with the
``alert.ack`` action and a success/failure outcome, so the mutation is audited
even when it does not change state (Requirements 9.1, 9.5). The actor reference
is the opaque hashed user id (never raw PII — Requirements 9.3, 11.3).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from clara_api.compliance.redaction import hash_user_ref
from clara_api.core.config import get_settings
from clara_api.core.rbac import require_roles
from clara_api.core.security import TokenPayload
from clara_api.db.session import get_db
from clara_api.observability.admin_audit import (
    ACTION_ALERT_ACK,
    OUTCOME_FAILURE,
    OUTCOME_SUCCESS,
    record_admin_action,
)
from clara_api.observability.alerts import AlertEngine

router = APIRouter()

# Single admin RBAC dependency reused by every route (Requirement 1.1), mirroring
# the ``ADMIN_ROLE_DEP`` convention used by ``admin_rag.py`` / ``admin_audit.py``.
ADMIN_ROLE_DEP = Depends(require_roles("admin"))


class AlertAckResponse(BaseModel):
    """The acknowledged alert's persisted state (PII-free by construction)."""

    model_config = ConfigDict(extra="allow")

    alert_id: str
    severity: str = ""
    state: str = ""
    acknowledged: bool = False
    first_fired_at: str | None = None
    last_evaluated_at: str | None = None
    last_delivered_at: str | None = None


class AlertAckResult(BaseModel):
    """Acknowledge result envelope."""

    acknowledged: bool = True
    alert: AlertAckResponse = Field(...)


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertAckResult)
def acknowledge_alert(
    alert_id: str = Path(
        ...,
        min_length=1,
        max_length=96,
        description="Stable alert id (rule + target dedupe key) to acknowledge.",
    ),
    _token: TokenPayload = ADMIN_ROLE_DEP,
    db: Session = Depends(get_db),
) -> AlertAckResult:
    """Acknowledge a firing alert by its stable id (Requirements 8.4, 1.1).

    Admin-only (403 non-admin / 401 no token). When
    ``admin_observability_alerting_enabled`` is off the endpoint returns the
    standard feature-disabled HTTP 404 shape so the surface ships dark
    (Requirements 12.2, 12.4). An unknown alert id yields HTTP 404. The
    acknowledge is recorded inline as an append-only admin-action audit row with
    a success/failure outcome (Requirements 9.1, 9.5).
    """

    if not get_settings().admin_observability_alerting_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cảnh báo quan trắc đã bị tắt.",
        )

    actor_ref = hash_user_ref(_token.sub)
    engine = AlertEngine()

    try:
        state = engine.acknowledge(db, alert_id)
    except Exception:
        # Record the failed mutation before re-raising so the audit trail still
        # captures the attempt (Requirement 9.5).
        record_admin_action(
            db,
            actor_ref=actor_ref,
            action=ACTION_ALERT_ACK,
            target=alert_id,
            outcome=OUTCOME_FAILURE,
        )
        db.commit()
        raise

    if state is None:
        # No firing/known alert for this stable id → audited failure + 404.
        record_admin_action(
            db,
            actor_ref=actor_ref,
            action=ACTION_ALERT_ACK,
            target=alert_id,
            outcome=OUTCOME_FAILURE,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy cảnh báo với mã đã cung cấp.",
        )

    # Successful acknowledge → audited success with coarse, PII-free meta.
    record_admin_action(
        db,
        actor_ref=actor_ref,
        action=ACTION_ALERT_ACK,
        target=alert_id,
        outcome=OUTCOME_SUCCESS,
        meta={"severity": state.severity, "state": state.state},
    )
    # ``get_db`` does not commit; persist both the ack and the audit row inline so
    # the mutation and its audit survive the request (Requirements 8.4, 9.1).
    db.commit()

    return AlertAckResult(
        acknowledged=True,
        alert=AlertAckResponse.model_validate(state.as_dict()),
    )
