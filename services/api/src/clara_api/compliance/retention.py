"""Retention policy + scheduled anonymization sweep (Req 7).

The retention policy is declared in code (and mirrored in ``docs/compliance/ropa.md``)
so the ROPA, the admin records manifest, and the sweep all derive from a single
source of truth. The sweep itself is gated by ``COMPLIANCE_RETENTION_JOB_ENABLED``:
with the flag off it is a no-op that touches nothing, preserving current behavior
(Requirement 8.1, 8.2 / Correctness Property 6).

The sweep is exposed as a plain callable so an ops cron under ``scripts/ops`` can
invoke it without the compliance package taking a scheduler dependency.

Design guarantees:

* **Idempotent.** Running the sweep repeatedly is safe: an already-anonymized
  row is detected and skipped (no write, not re-counted), and anonymizing a row
  bumps its ``updated_at`` so it falls outside the retention window on the next
  pass.
* **Audit survival.** Categories whose action is ``retain`` (the append-only,
  PII-free ``compliance_events`` and ``dsar_requests`` rows) are never selected,
  deleted, or mutated — they are kept for legal defensibility (Req 7.4 /
  Correctness Property 4).
* **No-PII output.** The sweep returns counts only, never row contents, so the
  summary is safe to write to a cron log (Req 7.3).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.core.config import Settings, get_settings
from clara_api.db.models import (
    PhrAudit,
    PhrObservation,
    PhrProfile,
    PhrReminder,
    PhrVersion,
)

# Retention actions a category may declare.
ACTION_ANONYMIZE = "anonymize"
ACTION_DELETE = "delete"
ACTION_RETAIN = "retain"


@dataclass(frozen=True)
class RetentionCategory:
    """Per-category retention declaration (Req 7.1)."""

    category: str
    retention_days: int
    basis: str
    action: str  # "anonymize" | "delete" | "retain"


# Declared retention periods per data category. Audit/compliance rows are kept
# longer for legal defensibility and carry no PII (Req 7.4).
RETENTION_POLICY: tuple[RetentionCategory, ...] = (
    RetentionCategory(
        category="phr_profile",
        retention_days=1095,
        basis="health-record self-management; consent-based",
        action=ACTION_ANONYMIZE,
    ),
    RetentionCategory(
        category="medicine_cabinet",
        retention_days=1095,
        basis="health-record self-management; consent-based",
        action=ACTION_ANONYMIZE,
    ),
    RetentionCategory(
        category="query_log",
        retention_days=365,
        basis="service operation; data minimization",
        action=ACTION_DELETE,
    ),
    RetentionCategory(
        category="session_token",
        retention_days=90,
        basis="authentication security",
        action=ACTION_DELETE,
    ),
    RetentionCategory(
        category="compliance_event",
        retention_days=3650,
        basis="legal defensibility; contains no PII",
        action=ACTION_RETAIN,
    ),
    RetentionCategory(
        category="dsar_request",
        retention_days=3650,
        basis="legal defensibility; contains no PII",
        action=ACTION_RETAIN,
    ),
)


class RetentionPolicy:
    """Queryable view over the declared per-category retention rules (Req 7.1).

    Wraps the :data:`RETENTION_POLICY` declarations so the sweep, the admin
    records manifest, and the ROPA all derive cutoffs and actions from one
    source of truth. Pure/stateless: every method is a deterministic function of
    the declared categories and the supplied ``now`` reference.
    """

    def __init__(self, categories: tuple[RetentionCategory, ...] = RETENTION_POLICY) -> None:
        self._by_name: dict[str, RetentionCategory] = {c.category: c for c in categories}

    @property
    def categories(self) -> tuple[RetentionCategory, ...]:
        return tuple(self._by_name.values())

    def get(self, category: str) -> RetentionCategory | None:
        """Return the declaration for ``category`` (or ``None`` if undeclared)."""

        return self._by_name.get(category)

    def is_retained(self, category: str) -> bool:
        """True iff the category is kept for legal defensibility (never swept).

        Unknown categories are treated as retained (fail-safe: the sweep will
        not touch a category it does not understand).
        """

        rule = self._by_name.get(category)
        return rule is None or rule.action == ACTION_RETAIN

    def cutoff(self, category: str, *, now: datetime | None = None) -> datetime | None:
        """Return the timestamp before which rows of ``category`` are expired.

        Rows whose retention timestamp is strictly older than this cutoff are
        past their window. Returns ``None`` for retained/unknown categories,
        signalling "never sweep".
        """

        rule = self._by_name.get(category)
        if rule is None or rule.action == ACTION_RETAIN:
            return None
        reference = now or datetime.now(UTC)
        return reference - timedelta(days=rule.retention_days)

    def is_expired(
        self, category: str, ts: datetime, *, now: datetime | None = None
    ) -> bool:
        """True iff a row of ``category`` last touched at ``ts`` is past its window."""

        cutoff = self.cutoff(category, now=now)
        if cutoff is None:
            return False
        return _as_aware(ts) < cutoff

    def manifest(self) -> list[dict[str, object]]:
        """Return the policy as plain dicts for the records manifest."""

        return [
            {
                "category": c.category,
                "retention_days": c.retention_days,
                "basis": c.basis,
                "action": c.action,
            }
            for c in self.categories
        ]


# Default policy instance (the single source of truth callers should reuse).
DEFAULT_POLICY = RetentionPolicy()


def policy_manifest() -> list[dict[str, object]]:
    """Return the retention policy as plain dicts for the records manifest."""

    return DEFAULT_POLICY.manifest()


def _as_aware(ts: datetime) -> datetime:
    """Normalize a possibly-naive datetime to UTC for safe comparison.

    SQLite round-trips ``DateTime(timezone=True)`` columns as naive datetimes, so
    a naive value is assumed to already be UTC.
    """

    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts


def _is_anonymized_profile(profile: PhrProfile) -> bool:
    """True iff a PHR profile already holds no PII (idempotency guard).

    A profile that is already anonymized (or never carried any data) is skipped
    by the sweep so re-running performs no writes and does not re-count it.
    """

    return (
        not profile.full_name
        and not profile.phone
        and not profile.address
        and not profile.notes
        and not profile.emergency_contact_name
        and not profile.emergency_contact_phone
        and not profile.insurance_id
        and not (profile.allergies_json or [])
        and not (profile.conditions_json or [])
        and not (profile.medications_json or [])
    )


def _anonymize_profile(db: Session, profile: PhrProfile) -> None:
    """Irreversibly anonymize a single PHR profile and its dependent PII.

    Mirrors the DSAR deletion projection but is scoped to the profile (it does
    not tombstone the user account): identifying/sensitive fields are cleared,
    dependent observation/reminder/version rows are dropped, and the append-only
    ``phr_audit`` before/after JSON is scrubbed. The audit rows themselves
    survive (they retain no PII after scrubbing).
    """

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
    profile.emergency_card_prefs_json = None

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


def _sweep_phr_profiles(
    db: Session, policy: RetentionPolicy, *, now: datetime
) -> int:
    """Anonymize PHR profiles inactive past their retention window.

    Selects profiles whose ``updated_at`` is older than the ``phr_profile``
    cutoff and that still carry PII, then anonymizes each. Returns the count of
    profiles anonymized in this pass (already-anonymized ones are skipped, which
    is what makes the sweep idempotent).
    """

    cutoff = policy.cutoff("phr_profile", now=now)
    if cutoff is None:
        return 0

    swept = 0
    for profile in db.execute(select(PhrProfile)).scalars():
        if _is_anonymized_profile(profile):
            continue
        if _as_aware(profile.updated_at) >= cutoff:
            continue
        _anonymize_profile(db, profile)
        swept += 1
    if swept:
        db.flush()
    return swept


def run_retention_sweep(
    db: Session,
    settings: Settings | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    """Anonymize/delete rows past their retention window (Req 7.2).

    Returns a no-PII summary of counts only. When the retention flag is off the
    sweep is an inert no-op (Property 6), returning ``{"swept": 0, "enabled": 0}``
    without touching the database. When enabled it applies the
    :class:`RetentionPolicy`, anonymizing expired PHR data while leaving the
    retained, append-only, PII-free compliance/DSAR audit rows untouched. The
    sweep is idempotent — safe to run on any cadence.

    The caller owns the transaction boundary (the ops cron commits after a
    successful sweep and rolls back on failure).
    """

    settings = settings or get_settings()
    if not settings.compliance_retention_job_enabled:
        return {"swept": 0, "enabled": 0}

    reference = now or datetime.now(UTC)
    policy = DEFAULT_POLICY
    phr_profiles = _sweep_phr_profiles(db, policy, now=reference)

    return {
        "enabled": 1,
        "swept": phr_profiles,
        "phr_profile": phr_profiles,
    }
