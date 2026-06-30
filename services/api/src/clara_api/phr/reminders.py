"""Medication reminder / refill / caregiver-nudge decision logic (Component L).

Pure decision functions (Req 14, Correctness Property 18). The notification
*dispatch* reuses the existing notification path at the endpoint layer; only the
decision logic lives here so it can be unit/property-tested in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ReminderDecision:
    fire_medication_reminder: bool
    fire_refill_reminder: bool
    notify_caregiver: bool
    reason: str


def should_fire_medication_reminder(
    *,
    is_current: bool,
    frequency: str,
    scheduled_time: datetime | None,
    now: datetime,
) -> bool:
    """A medication reminder fires iff the med is current with a defined
    frequency and a configured time has been reached (Req 14.1, 14.2)."""

    if not is_current:
        return False
    if not str(frequency or "").strip():
        return False
    if scheduled_time is None:
        return False
    return now >= scheduled_time


def should_fire_refill_reminder(
    *,
    remaining_supply: float | None,
    refill_threshold: float | None,
) -> bool:
    """A refill reminder fires iff ``remaining_supply <= refill_threshold`` and
    both are tracked (Req 14.3, 14.4)."""

    if remaining_supply is None or refill_threshold is None:
        return False
    return remaining_supply <= refill_threshold


def should_notify_caregiver(
    *,
    nudge_enabled: bool,
    caregiver_share_active: bool,
    dose_marked_taken: bool,
    within_window: bool,
) -> bool:
    """Caregiver is notified iff the missed-dose nudge is enabled, a caregiver
    share is active, and a dose is not marked taken past the configured window
    (Req 14.5)."""

    if not (nudge_enabled and caregiver_share_active):
        return False
    if dose_marked_taken:
        return False
    # ``within_window`` True ⇒ still inside the grace window ⇒ do not notify yet.
    return not within_window


def evaluate_reminder(
    *,
    is_current: bool,
    frequency: str,
    scheduled_time: datetime | None,
    now: datetime,
    remaining_supply: float | None = None,
    refill_threshold: float | None = None,
    nudge_enabled: bool = False,
    caregiver_share_active: bool = False,
    dose_marked_taken: bool = False,
    within_window: bool = True,
) -> ReminderDecision:
    """Compose the three independent reminder decisions (Correctness Property 18)."""

    med = should_fire_medication_reminder(
        is_current=is_current,
        frequency=frequency,
        scheduled_time=scheduled_time,
        now=now,
    )
    refill = should_fire_refill_reminder(
        remaining_supply=remaining_supply,
        refill_threshold=refill_threshold,
    )
    caregiver = should_notify_caregiver(
        nudge_enabled=nudge_enabled,
        caregiver_share_active=caregiver_share_active,
        dose_marked_taken=dose_marked_taken,
        within_window=within_window,
    )
    reasons = []
    if med:
        reasons.append("medication_due")
    if refill:
        reasons.append("refill_due")
    if caregiver:
        reasons.append("caregiver_nudge")
    return ReminderDecision(
        fire_medication_reminder=med,
        fire_refill_reminder=refill,
        notify_caregiver=caregiver,
        reason=",".join(reasons) or "none",
    )
