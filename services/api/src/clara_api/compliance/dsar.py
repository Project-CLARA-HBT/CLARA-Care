"""Data Subject Access Request (DSAR) service (Req 3).

Append-only request log + machine-readable export + irreversible deletion. The
DSAR log itself stores only the request type, timestamps, status, and an opaque
hashed user reference — never free-text PII (Req 3.5, Correctness Property 4/5).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.compliance.redaction import hash_user_ref
from clara_api.compliance.service import EVENT_DSAR, ComplianceService
from clara_api.core.config import Settings, get_settings
from clara_api.db.models import (
    DsarRequest,
    MedicineCabinet,
    MedicineItem,
    PhrAudit,
    PhrObservation,
    PhrProfile,
    PhrReminder,
    PhrShare,
    PhrVersion,
    User,
    UserConsent,
)

DSAR_KINDS = frozenset({"export", "correct", "delete", "restrict", "withdraw"})

# Terminal statuses: once a request reaches one of these it is no longer counted
# against the statutory window (it has been resolved).
RESOLVED_STATUSES = frozenset({"fulfilled", "rejected"})

# Full set of admin-settable resolution statuses for a DSAR row.
_ALLOWED_STATUSES = frozenset({"received", "in_progress", "fulfilled", "rejected"})

# PDPD statutory response window (days). Tracked so the admin queue can flag
# overdue requests; configurable later if the regulation is clarified.
_STATUTORY_WINDOW_DAYS = 30


def _utcnow() -> datetime:
    return datetime.now(UTC)


def record_request(db: Session, *, user_id: int, kind: str) -> DsarRequest:
    """Append a DSAR row and a PII-free compliance event (Req 3.5, 3.6)."""

    if kind not in DSAR_KINDS:
        raise ValueError(f"unsupported DSAR kind: {kind}")
    now = _utcnow()
    row = DsarRequest(
        user_ref=hash_user_ref(user_id),
        kind=kind,
        status="received",
        created_at=now,
        due_at=now + timedelta(days=_STATUTORY_WINDOW_DAYS),
    )
    db.add(row)
    db.flush()
    ComplianceService(db).record_event(
        EVENT_DSAR,
        user_id=user_id,
        meta={"kind": kind, "status": "received"},
    )
    return row


def export_bundle(db: Session, *, user: User) -> dict[str, Any]:
    """Assemble a machine-readable export of the user's own rows (Req 3.1).

    Contains exactly the requesting subject's data and no other subject's
    (Correctness Property 3).
    """

    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    cabinet = db.execute(
        select(MedicineCabinet).where(MedicineCabinet.user_id == user.id)
    ).scalar_one_or_none()
    cabinet_items: list[MedicineItem] = []
    if cabinet is not None:
        cabinet_items = list(
            db.execute(select(MedicineItem).where(MedicineItem.cabinet_id == cabinet.id)).scalars()
        )
    consents = list(db.execute(select(UserConsent).where(UserConsent.user_id == user.id)).scalars())

    observations: list[PhrObservation] = []
    if profile is not None:
        observations = list(
            db.execute(
                select(PhrObservation).where(PhrObservation.profile_id == profile.id)
            ).scalars()
        )

    return {
        "schema": "clara.dsar.export.v1",
        "generated_at": _utcnow().isoformat(),
        "subject": {
            "user_id": user.id,
            "email": user.email,
            "role": user.role,
        },
        # PHR is sensitive personal data under PDPD Art. 2(4) (Req 19.1); the
        # complete PHR — profile, coded allergies/conditions/medications, and
        # observations — is included in the machine-readable export (Req 19.2).
        "phr_profile": _profile_dict(profile),
        "phr_observations": [_observation_dict(o) for o in observations],
        "data_classification": "sensitive_personal_data",
        "medicine_cabinet": [_cabinet_item_dict(item) for item in cabinet_items],
        "consents": [_consent_dict(row) for row in consents],
    }


def _profile_dict(profile: PhrProfile | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "full_name": profile.full_name,
        "date_of_birth": profile.date_of_birth.isoformat() if profile.date_of_birth else None,
        "gender": profile.gender,
        "blood_type": profile.blood_type,
        "height_cm": profile.height_cm,
        "weight_kg": profile.weight_kg,
        "phone": profile.phone,
        "address": profile.address,
        "emergency_contact_name": profile.emergency_contact_name,
        "emergency_contact_phone": profile.emergency_contact_phone,
        "insurance_id": profile.insurance_id,
        "notes": profile.notes,
        "allergies": profile.allergies_json or [],
        "conditions": profile.conditions_json or [],
        "medications": profile.medications_json or [],
    }


def _observation_dict(obs: PhrObservation) -> dict[str, Any]:
    return {
        "entry_id": obs.entry_id,
        "name": obs.name,
        "value": obs.value,
        "unit": obs.unit,
        "observed_on": obs.observed_on.isoformat() if obs.observed_on else None,
        "information_source": obs.information_source,
    }


def _cabinet_item_dict(item: MedicineItem) -> dict[str, Any]:
    return {
        "drug_name": item.drug_name,
        "normalized_name": item.normalized_name,
        "dosage": item.dosage,
        "dosage_form": item.dosage_form,
        "quantity": item.quantity,
        "rx_cui": item.rx_cui,
        "note": item.note,
    }


def _consent_dict(row: UserConsent) -> dict[str, Any]:
    return {
        "consent_type": row.consent_type,
        "consent_version": row.consent_version,
        "accepted_at": row.accepted_at.isoformat() if row.accepted_at else None,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
    }


def fulfil_deletion(db: Session, *, user: User) -> None:
    """Irreversibly anonymise the subject's data (Req 3.7).

    Transactional: the caller wraps this in a commit; a partial failure rolls
    back and the request stays ``in_progress`` (design Error Handling). The
    append-only DSAR/compliance rows survive (they contain no PII).
    """

    anon = f"anon-{hash_user_ref(user.id)[:16]}"

    profile = db.execute(
        select(PhrProfile).where(PhrProfile.user_id == user.id)
    ).scalar_one_or_none()
    if profile is not None:
        profile.full_name = ""
        profile.date_of_birth = None
        profile.gender = ""
        profile.blood_type = ""
        profile.height_cm = None
        profile.weight_kg = None
        profile.phone = ""
        profile.address = ""
        profile.emergency_contact_name = ""
        profile.emergency_contact_phone = ""
        profile.insurance_id = ""
        profile.notes = ""
        profile.allergies_json = []
        profile.conditions_json = []
        profile.medications_json = []
        # New structured PHR fields are sensitive too; clear them (Req 19.3).
        profile.emergency_card_prefs_json = None
        # PHR observations / reminders are deleted outright (no PII value to
        # retain). PHR version snapshots carry PHR data in snapshot_json, so they
        # are dropped, and phr_audit before/after JSON is scrubbed. The no-PII
        # compliance/DSAR event rows are preserved (Req 19.3).
        for obs in db.execute(
            select(PhrObservation).where(PhrObservation.profile_id == profile.id)
        ).scalars():
            db.delete(obs)
        for reminder in db.execute(
            select(PhrReminder).where(PhrReminder.profile_id == profile.id)
        ).scalars():
            db.delete(reminder)
        for version in db.execute(
            select(PhrVersion).where(PhrVersion.profile_id == profile.id)
        ).scalars():
            db.delete(version)
        profile.current_version_no = 0
        for audit_row in db.execute(
            select(PhrAudit).where(PhrAudit.profile_id == profile.id)
        ).scalars():
            audit_row.before_json = None
            audit_row.after_json = None

    for share in db.execute(select(PhrShare).where(PhrShare.user_id == user.id)).scalars():
        db.delete(share)

    cabinet = db.execute(
        select(MedicineCabinet).where(MedicineCabinet.user_id == user.id)
    ).scalar_one_or_none()
    if cabinet is not None:
        for item in db.execute(
            select(MedicineItem).where(MedicineItem.cabinet_id == cabinet.id)
        ).scalars():
            db.delete(item)

    # Tombstone the account: strip the identifier and disable login.
    user.email = f"{anon}@deleted.invalid"
    user.full_name = ""
    user.status = "deleted"


def update_status(db: Session, *, dsar: DsarRequest, status: str, user_id: int) -> DsarRequest:
    dsar.status = status
    if status in RESOLVED_STATUSES:
        dsar.resolved_at = _utcnow()
    db.flush()
    ComplianceService(db).record_event(
        EVENT_DSAR,
        user_id=user_id,
        meta={"kind": dsar.kind, "status": status},
    )
    return dsar


# ---------------------------------------------------------------------------
# DsarService — request orchestration, acknowledgement & due-date tracking
# (Req 3.5, 3.6 / task 6.1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DsarAcknowledgement:
    """Immediate, PII-free acknowledgement returned to a data subject (Req 3.6).

    Carries the opaque request id, the request kind/status, when it was received
    and the statutory deadline it is tracked against. It contains no free-text
    PII so it is safe to log and to return verbatim in an API envelope.
    """

    request_id: int
    kind: str
    status: str
    created_at: datetime
    due_at: datetime
    statutory_window_days: int

    def days_remaining(self, *, now: datetime | None = None) -> int:
        """Whole days left before the statutory deadline (negative if past)."""

        reference = now or _utcnow()
        return (self.due_at - reference).days

    def is_overdue(self, *, now: datetime | None = None) -> bool:
        """True iff unresolved and past the statutory deadline."""

        if self.status in RESOLVED_STATUSES:
            return False
        reference = now or _utcnow()
        return reference > self.due_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "kind": self.kind,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "due_at": self.due_at.isoformat(),
            "statutory_window_days": self.statutory_window_days,
        }


def _acknowledgement(row: DsarRequest) -> DsarAcknowledgement:
    """Project a persisted ``DsarRequest`` row into an acknowledgement.

    ``due_at`` is always populated by :func:`record_request`; for legacy rows
    that predate due-date tracking we derive it from ``created_at`` so the
    statutory window is always representable.
    """

    created_at = row.created_at or _utcnow()
    due_at = row.due_at or (created_at + timedelta(days=_STATUTORY_WINDOW_DAYS))
    return DsarAcknowledgement(
        request_id=row.id,
        kind=row.kind,
        status=row.status,
        created_at=created_at,
        due_at=due_at,
        statutory_window_days=_STATUTORY_WINDOW_DAYS,
    )


class DsarService:
    """Orchestrates Data Subject Access Requests (Req 3).

    Task 6.1 covers the intake path: appending an append-only ``DsarRequest``
    row, recording a PII-free compliance event, acknowledging the request
    immediately, and tracking it against the statutory response window. Export
    (6.2) and deletion (6.3) reuse the module-level :func:`export_bundle` /
    :func:`fulfil_deletion` helpers.
    """

    def __init__(self, db: Session, settings: Settings | None = None) -> None:
        self._db = db
        self._settings = settings or get_settings()

    @property
    def statutory_window_days(self) -> int:
        return _STATUTORY_WINDOW_DAYS

    def request(self, *, user_id: int, kind: str) -> DsarAcknowledgement:
        """Log a DSAR (append-only) and return an immediate acknowledgement.

        Writes one ``DsarRequest`` row plus a PII-free compliance event, sets the
        statutory ``due_at`` deadline, and returns a :class:`DsarAcknowledgement`
        (Req 3.5, 3.6). Never mutates a prior row — the log is append-only. The
        caller owns the transaction boundary (``db.commit()``), matching the
        existing endpoint flow.
        """

        if kind not in DSAR_KINDS:
            raise ValueError(f"unsupported DSAR kind: {kind}")
        row = record_request(self._db, user_id=user_id, kind=kind)
        return _acknowledgement(row)

    def acknowledgement_for(self, dsar: DsarRequest) -> DsarAcknowledgement:
        """Return the acknowledgement view of an existing request row."""

        return _acknowledgement(dsar)

    def export(self, *, user: User) -> dict[str, Any]:
        """Assemble the data subject's machine-readable export bundle (Req 3.1).

        Surfaces :func:`export_bundle`, which reads exclusively from the
        requesting user's own rows (profile, PHR, observations, medicine
        cabinet, consents). The bundle therefore contains exactly that
        subject's data and no other subject's (Correctness Property 3). This is
        a pure read; the caller owns the transaction boundary and is
        responsible for logging the originating DSAR via :meth:`request` or
        :func:`record_request`.
        """

        return export_bundle(self._db, user=user)

    def delete(
        self, *, user: User, request_id: int | None = None
    ) -> DsarAcknowledgement:
        """Irreversibly anonymise the subject's data, transactionally (Req 3.7).

        Surfaces the module-level :func:`fulfil_deletion`. Guarantees
        Correctness Property 4 (deletion irreversibility + audit survival):

        - The subject's PII is irreversibly anonymised/cleared on success, while
          the append-only DSAR/compliance rows (which contain no PII) survive.
        - The mutation is **transactional**. The anonymisation runs inside a
          SAVEPOINT; if any part fails the SAVEPOINT is rolled back so no
          partial anonymisation is persisted, and the originating DSAR request
          is left in ``in_progress`` — never silently ``fulfilled`` (design
          Error Handling). The error is re-raised for the caller to surface.

        A ``delete`` DSAR row is appended if one is not supplied so the action
        is always recorded in the append-only log. This method owns its
        transaction boundary (it commits on success and on the failure path so
        the ``in_progress`` status persists).
        """

        dsar = self._resolve_delete_request(user_id=user.id, request_id=request_id)
        # Move the request out of its initial state before mutating data, so a
        # crash mid-deletion leaves an auditable ``in_progress`` marker rather
        # than a stale ``received``. This update lives in the outer transaction,
        # outside the anonymisation SAVEPOINT, so it survives a rollback.
        update_status(self._db, dsar=dsar, status="in_progress", user_id=user.id)

        try:
            with self._db.begin_nested():
                fulfil_deletion(self._db, user=user)
        except Exception:
            # The SAVEPOINT rolled back, undoing any partial anonymisation. Keep
            # the request ``in_progress`` and persist that fact, then re-raise.
            self._db.commit()
            raise

        update_status(self._db, dsar=dsar, status="fulfilled", user_id=user.id)
        self._db.commit()
        return self.acknowledgement_for(dsar)

    def _resolve_delete_request(
        self, *, user_id: int, request_id: int | None
    ) -> DsarRequest:
        """Return the ``delete`` DSAR row to drive, appending one if needed.

        When ``request_id`` is supplied it must reference this subject's own
        ``delete`` request. Otherwise the most recent unresolved ``delete``
        request is reused, or a fresh append-only row is created.
        """

        if request_id is not None:
            row = self._db.get(DsarRequest, request_id)
            if (
                row is None
                or row.user_ref != hash_user_ref(user_id)
                or row.kind != "delete"
            ):
                raise ValueError("delete request not found for subject")
            return row

        existing = self._db.execute(
            select(DsarRequest)
            .where(
                DsarRequest.user_ref == hash_user_ref(user_id),
                DsarRequest.kind == "delete",
                DsarRequest.status.notin_(tuple(RESOLVED_STATUSES)),
            )
            .order_by(DsarRequest.created_at.desc(), DsarRequest.id.desc())
        ).scalars().first()
        if existing is not None:
            return existing
        return record_request(self._db, user_id=user_id, kind="delete")

    def open_requests(self, *, user_id: int) -> list[DsarRequest]:
        """Return this subject's not-yet-resolved requests (admin/self queue)."""

        rows = self._db.execute(
            select(DsarRequest)
            .where(DsarRequest.user_ref == hash_user_ref(user_id))
            .order_by(DsarRequest.created_at.desc(), DsarRequest.id.desc())
        ).scalars()
        return [row for row in rows if row.status not in RESOLVED_STATUSES]

    def list_for_user(self, *, user_id: int) -> list[DsarRequest]:
        """Return all of this subject's DSAR requests, newest first (Req 3.6).

        Powers the self-service "request history" view so a data subject can see
        every request they have filed and track each against its statutory
        deadline. The rows carry only the request type, timestamps, status and
        an opaque hashed reference — no free-text PII.
        """

        rows = self._db.execute(
            select(DsarRequest)
            .where(DsarRequest.user_ref == hash_user_ref(user_id))
            .order_by(DsarRequest.created_at.desc(), DsarRequest.id.desc())
        ).scalars()
        return list(rows)

    def admin_queue(self, *, limit: int = 200) -> list[DsarRequest]:
        """Return the global DSAR queue for the admin surface (Req 3.6).

        Unresolved requests are surfaced first (ordered by their statutory
        deadline, soonest first) so overdue items rise to the top, followed by
        resolved requests newest-first for audit context. RBAC is enforced at
        the endpoint (admin-only / Correctness Property 7). Rows contain no PII.
        """

        rows = list(
            self._db.execute(
                select(DsarRequest)
                .order_by(DsarRequest.created_at.desc(), DsarRequest.id.desc())
                .limit(limit)
            ).scalars()
        )

        def _sort_key(row: DsarRequest) -> tuple[int, float]:
            resolved = row.status in RESOLVED_STATUSES
            if not resolved:
                # Unresolved first (group 0), soonest statutory deadline first.
                due = row.due_at or row.created_at or _utcnow()
                return (0, due.timestamp())
            # Resolved after (group 1), most recently created first (negate ts).
            created = row.created_at or _utcnow()
            return (1, -created.timestamp())

        rows.sort(key=_sort_key)
        return rows

    def set_status(self, *, request_id: int, status: str) -> DsarRequest:
        """Update a request's resolution status (admin queue action, Req 3.6).

        Records a PII-free compliance event keyed on the row's existing opaque
        ``user_ref`` so the subject linkage is preserved without ever resolving
        the subject's identity. The caller owns the transaction boundary.
        """

        if status not in _ALLOWED_STATUSES:
            raise ValueError(f"unsupported DSAR status: {status}")
        row = self._db.get(DsarRequest, request_id)
        if row is None:
            raise ValueError("DSAR request not found")
        row.status = status
        if status in RESOLVED_STATUSES:
            row.resolved_at = _utcnow()
        else:
            row.resolved_at = None
        self._db.flush()
        ComplianceService(self._db).record_event(
            EVENT_DSAR,
            subject_ref=row.user_ref,
            meta={"kind": row.kind, "status": status, "actor": "admin"},
        )
        return row

    def overdue_requests(self, *, now: datetime | None = None) -> list[DsarRequest]:
        """Return all unresolved requests past their statutory deadline.

        Powers the admin queue's overdue flag (due-date tracking, Req 3.6).
        """

        reference = now or _utcnow()
        rows = self._db.execute(
            select(DsarRequest)
            .where(
                DsarRequest.status.notin_(tuple(RESOLVED_STATUSES)),
                DsarRequest.due_at.is_not(None),
                DsarRequest.due_at < reference,
            )
            .order_by(DsarRequest.due_at.asc())
        ).scalars()
        return list(rows)
