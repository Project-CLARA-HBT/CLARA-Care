"""Central compliance enforcement facade.

A single object that answers "may I process X for purpose Y for user Z?" and
records PII-free compliance events, so every caller is consistent (design
principle 4). Every method is flag-aware: when the relevant ``COMPLIANCE_*``
flag is off the method is a no-op that preserves current behavior (Requirement
8.1, 8.2 / Correctness Property 6).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from clara_api.compliance import consent as consent_ledger
from clara_api.compliance.notice import model_disclosure as _build_model_disclosure
from clara_api.compliance.redaction import hash_user_ref, redact_meta
from clara_api.compliance.transfer import list_processors
from clara_api.core.config import Settings, get_settings
from clara_api.db.models import ComplianceEvent

# Event-type vocabulary for ``compliance_events.event_type``.
EVENT_CONSENT_GRANT = "consent_grant"
EVENT_CONSENT_WITHDRAW = "consent_withdraw"
EVENT_DSAR = "dsar"
EVENT_TRANSFER = "transfer"
EVENT_INCIDENT = "incident"
EVENT_TRANSPARENCY_ACK = "transparency_ack"


@dataclass(frozen=True)
class TransferDecision:
    """Outcome of the cross-border outbound guard."""

    # True ⇒ the caller may transmit to the offshore processor as today.
    allow_cross_border: bool
    # Human/audit label of why; bounded enum, safe for logs.
    reason: str


class ComplianceService:
    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self._db = db
        self._settings = settings or get_settings()

    # --- flags ----------------------------------------------------------
    @property
    def settings(self) -> Settings:
        return self._settings

    # --- consent --------------------------------------------------------
    def has_consent(self, *, user_id: int, purpose: str) -> bool:
        """Single source of truth for purpose consent.

        When granular consent is disabled, returns ``True`` so callers behave
        exactly as today (no enforcement) — Property 6.
        """

        if not self._settings.compliance_granular_consent_enabled:
            return True
        return consent_ledger.has_consent(self._db, user_id=user_id, purpose=purpose)

    def grant_consent(self, *, user_id: int, purpose: str, version: str) -> None:
        consent_ledger.grant(self._db, user_id=user_id, purpose=purpose, version=version)
        self.record_event(
            EVENT_CONSENT_GRANT,
            user_id=user_id,
            meta={"purpose": purpose, "policy_version": version},
        )

    def withdraw_consent(self, *, user_id: int, purpose: str, version: str = "") -> None:
        consent_ledger.withdraw(self._db, user_id=user_id, purpose=purpose, version=version)
        self.record_event(
            EVENT_CONSENT_WITHDRAW,
            user_id=user_id,
            meta={"purpose": purpose},
        )

    # --- cross-border transfer gate ------------------------------------
    def outbound_guard(self, *, user_id: int | None) -> TransferDecision:
        """Decide whether an offshore model call may proceed (Req 4.2).

        Flag off ⇒ always allow (today's behavior). Flag on ⇒ allow only when
        the user granted ``cross_border_processing`` consent; otherwise the
        caller must use an in-country path or degrade to the local fallback
        (Correctness Property 2).
        """

        if not self._settings.compliance_cross_border_gating_enabled:
            return TransferDecision(allow_cross_border=True, reason="gating_disabled")
        if user_id is None:
            return TransferDecision(allow_cross_border=False, reason="no_subject")
        if consent_ledger.has_consent(
            self._db, user_id=user_id, purpose=consent_ledger.PURPOSE_CROSS_BORDER
        ):
            return TransferDecision(allow_cross_border=True, reason="consent_present")
        return TransferDecision(allow_cross_border=False, reason="consent_absent")

    def record_transfer(
        self, *, user_id: int | None, processor: str, purpose: str, allowed: bool
    ) -> None:
        """Record a no-PII outbound transfer event (Req 4.4)."""

        self.record_event(
            EVENT_TRANSFER,
            user_id=user_id,
            processor=processor,
            meta={"purpose": purpose, "outcome": "sent" if allowed else "blocked"},
        )

    def transfer_registry(self) -> list[dict[str, object]]:
        return list_processors(self._db)

    # --- model disclosure (Req 1.3, 1.4 / Property P8) ------------------
    def model_disclosure(self, model_used: str | None) -> dict[str, object] | None:
        """Build the response-envelope ``ai_disclosure`` field (Req 1.3, 1.4).

        Flag off ⇒ returns ``None`` so the caller omits the field entirely and
        the response envelope is byte-equivalent to today (Property 6). Flag on
        ⇒ returns ``{model_family, model_version, is_fallback}`` derived from
        ``model_used``, where ``is_fallback`` is true iff the answer came from
        the local deterministic synthesiser ``local-synth-*`` (Property 8).
        """

        if not self._settings.compliance_model_disclosure_enabled:
            return None
        return _build_model_disclosure(model_used)

    # --- event log (append-only, PII-free) ------------------------------
    def record_event(
        self,
        event_type: str,
        *,
        user_id: int | None = None,
        subject_ref: str | None = None,
        processor: str | None = None,
        severity: str | None = None,
        meta: dict | None = None,
    ) -> ComplianceEvent:
        """Append a PII-free compliance event row.

        ``meta`` is passed through :func:`redact_meta` so the persisted
        projection can never contain free-text/identifiers (Property 5).

        The subject is identified by the opaque, already-hashed ``subject_ref``
        when supplied (e.g. an admin acting on a DSAR row that only carries the
        hashed reference, never the subject's id), otherwise it is derived from
        ``user_id``. Both paths persist only the opaque hash — never PII.
        """

        if subject_ref is None:
            subject_ref = hash_user_ref(user_id) if user_id is not None else None
        row = ComplianceEvent(
            event_type=event_type,
            subject_ref=subject_ref,
            processor=processor,
            severity=severity,
            meta_json=redact_meta(meta),
        )
        self._db.add(row)
        self._db.flush()
        return row
