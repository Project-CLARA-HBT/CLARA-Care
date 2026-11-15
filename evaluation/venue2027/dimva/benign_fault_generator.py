"""DIMVA venue2027 benign fault-session generator (task DIMVA-X03_benign_gen, phase P02).

Purpose
-------
Produce deterministic, PHI-free BENIGN fault sessions for the DIMVA 2027
"GovernanceTrace" study (``research/venue2027/VENUES/dimva/TASKS/DIMVA-X03_benign_gen.md``).
The study's falsification criterion demands a benign arm that is *hard*:
realistic nonmalicious retry bursts — rate-limit retries, network retries, UX
confusion retries, legitimate consent edits, delayed/deferred timestamps —
that superficially resemble authorization-boundary probing (repeated denials,
re-authorization churn, irregular pacing) while never violating an
authorization invariant. Each session is a
:class:`evaluation.venue2027.dimva.campaign_generator.Campaign` whose events
conform exactly to the frozen seven-field telemetry contract
``research/venue2027/dimva/protocols/event.schema.json`` (``actor``, ``tool``,
``scope``, ``allowed``, ``purpose``, ``ts``, ``campaign_id``; actor/scope are
opaque SHA-256 hex digests, purpose is a closed coarse enum, ``ts`` is a
60-second bucket index). LABELS EXIST ONLY AT CAMPAIGN LEVEL:
``campaign_label="BENIGN"`` and ``violated_invariant="NONE"`` live on the
Campaign object; the shared event builder structurally refuses any label-like
field, so no event ever carries the ground truth.

VOLUME PARITY (critical property)
---------------------------------
``generate_benign(seed, workload)`` accepts a target event-volume/cadence
profile (:class:`WorkloadProfile`) so benign and attack arms can be
volume-matched: the emitted campaign contains EXACTLY
``workload.target_events`` events (one baseline event plus the benign fault
repertoire filling the remaining budget) and every non-delayed inter-arrival
gap lies inside ``[workload.pace_bucket_lo, workload.pace_bucket_hi]``
60-second buckets. The generator NEVER over-produces: whenever the realizable
benign structure would exceed the requested volume budget (a budget below the
minimum realizable campaign of ``MIN_TARGET_EVENTS`` events), it refuses with
``VOLUME_BUDGET_EXCEEDED`` instead of trimming required fault types or
emitting an over-budget campaign — fail closed, so volume parity is enforced
mechanically rather than by convention.

Determinism
-----------
Every entropy source is a SHA-256 digest of stable coordinate strings
(generator version, seed, tenant, target volume, fault index) — no ``random``
module, no clock, no environment reads — so the same ``(seed, workload)``
always yields a byte-identical campaign. Campaign identifiers are opaque
(``camp-<16 hex>``) and never encode the fault mix, label or tenant,
preventing trivial template leakage across splits.

Allowed input
-------------
``generate_benign(seed, workload)`` with a non-negative integer ``seed`` and a
:class:`WorkloadProfile` (synthetic ``tenant`` matching
``^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$`` and free of PHI markers; integer
``target_events`` in ``[MIN_TARGET_EVENTS, MAX_TARGET_EVENTS]``; integer pace
bounds with ``1 <= pace_bucket_lo <= pace_bucket_hi <= MAX_PACE_GAP_BUCKETS``).
All outputs are JSON-serializable (``Campaign.to_dict()``).

Failure semantics
-----------------
Every error is a :class:`BenignFaultError` carrying a stable reason code:
``INVALID_SEED``, ``INVALID_TENANT``, ``INVALID_WORKLOAD``,
``VOLUME_BUDGET_EXCEEDED``, ``CADENCE_PROFILE_VIOLATED``, ``PHI_FIELD_PRESENT``,
``EVENT_LABEL_FIELD_FORBIDDEN``, ``EVENT_FIELD_MISMATCH``. The generator never
emits a per-event label, a PHI-named field/value, a clear-text principal, an
event outside the seven-field schema surface, or a campaign that exceeds the
requested volume budget; violations fail closed instead of being silently
repaired. No raw patient data, no rejection reason codes, no live provider.

Version
-------
``BENIGN_FAULT_GENERATOR_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Mapping
from typing import Any

from evaluation.venue2027.dimva import campaign_generator as cg

BENIGN_FAULT_GENERATOR_VERSION = "1.0.0"

VENUE = "dimva"

#: Stable reason codes carried by :class:`BenignFaultError`.
REASON_INVALID_SEED = "INVALID_SEED"
REASON_INVALID_TENANT = "INVALID_TENANT"
REASON_INVALID_WORKLOAD = "INVALID_WORKLOAD"
REASON_VOLUME_BUDGET_EXCEEDED = "VOLUME_BUDGET_EXCEEDED"
REASON_CADENCE_PROFILE_VIOLATED = "CADENCE_PROFILE_VIOLATED"
REASON_PHI_FIELD_PRESENT = "PHI_FIELD_PRESENT"
REASON_EVENT_LABEL_FIELD_FORBIDDEN = "EVENT_LABEL_FIELD_FORBIDDEN"
REASON_EVENT_FIELD_MISMATCH = "EVENT_FIELD_MISMATCH"

#: Campaign-level family token for benign fault sessions (never appears on events).
FAMILY_BENIGN_FAULTS = "benign_faults"

#: Registered benign fault types. Each type contributes at least one event to
#: every generated campaign (the volume budget is guaranteed to admit the full
#: repertoire) and is intentionally superficially similar to one attack family:
#: - ``rate_limit_retry``   — tight-pacing burst of identical denied attempts
#:   until the throttle admits the retry (resembles burst_probe pacing);
#: - ``network_retry``      — backoff-paced identical retries after transport
#:   failures until admitted (resembles replay probing);
#: - ``ux_confusion_retry`` — short run of mis-scoped purpose selections before
#:   the correct one is admitted (resembles purpose_probe);
#: - ``consent_edit``       — legitimate consent/epoch changes producing fresh
#:   authorized scopes (resembles scope rotation);
#: - ``delayed_timestamps`` — legitimate long stalls / deferred actions beyond
#:   the pacing profile (resembles low-and-slow horizons).
BENIGN_FAULT_TYPES: tuple[str, ...] = (
    "rate_limit_retry",
    "network_retry",
    "ux_confusion_retry",
    "consent_edit",
    "delayed_timestamps",
)

#: Minimum realizable event count per benign fault type: retry-type faults
#: contribute at least two attempts (a retry is a repeated attempt — a single
#: attempt would make the benign arm trivially easy), while consent edits and
#: delayed stalls contribute at least one event each.
MIN_FAULT_EVENTS: Mapping[str, int] = {
    "rate_limit_retry": 2,
    "network_retry": 2,
    "ux_confusion_retry": 2,
    "consent_edit": 1,
    "delayed_timestamps": 1,
}

#: Minimum realizable volume budget: one baseline event plus the minimum
#: repertoire above. A smaller budget cannot honor the required repertoire of
#: genuine retries without exceeding the requested volume, so it is refused.
MIN_TARGET_EVENTS = 1 + sum(MIN_FAULT_EVENTS.values())

#: Upper bound on the supported volume budget (single-session sanity cap).
MAX_TARGET_EVENTS = 4096

#: Upper bound on profile-admissible inter-arrival gaps (60 s buckets). Strictly
#: below :data:`DELAYED_GAP_MIN_BUCKETS` so delayed-timestamp stalls are
#: unambiguously classifiable by gap size alone.
MAX_PACE_GAP_BUCKETS = 12

#: Inclusive lower bound (60 s buckets) for delayed-timestamp fault events;
#: deliberate benign stalls (deferred actions, batch jobs, walked-away users).
DELAYED_GAP_MIN_BUCKETS = 30

_TENANT_PATTERN = cg._TENANT_PATTERN


class BenignFaultError(ValueError):
    """Fail-closed generator error with a stable, machine-checkable reason code."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(f"{reason_code}: {message}")
        self.reason_code = reason_code


@dataclasses.dataclass(frozen=True)
class WorkloadProfile:
    """Target event-volume/cadence profile for one benign session.

    ``target_events`` is the EXACT event budget the emitted campaign must meet
    (volume parity with the attack arms); ``pace_bucket_lo``/``pace_bucket_hi``
    bound every non-delayed inter-arrival gap in 60-second buckets (cadence
    parity with the attack arms' pacing windows).
    """

    tenant: str
    target_events: int
    pace_bucket_lo: int = 1
    pace_bucket_hi: int = cg.PACE_WINDOW_BUCKETS

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable representation."""

        return {
            "tenant": self.tenant,
            "target_events": self.target_events,
            "pace_bucket_lo": self.pace_bucket_lo,
            "pace_bucket_hi": self.pace_bucket_hi,
        }


@dataclasses.dataclass(frozen=True)
class _BenignContext:
    """Deterministic per-session constants derived once from (seed, workload)."""

    seed: int
    tenant: str
    target_events: int
    pace_lo: int
    pace_hi: int
    principal_identity: str
    actor: str
    purpose: str
    tool: str
    epoch: int
    origin_bucket: int
    baseline_scope: str
    campaign_id: str


def _entropy_int(*parts: object) -> int:
    """Stable 64-bit entropy from SHA-256 over coordinate strings (no randomness)."""

    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _campaign_id(seed: int, workload: WorkloadProfile) -> str:
    """Opaque campaign identifier; workload coordinates contribute only hash entropy."""

    digest = hashlib.sha256(
        f"benign-campaign|{BENIGN_FAULT_GENERATOR_VERSION}|{seed}|{workload.tenant}"
        f"|{workload.target_events}|{workload.pace_bucket_lo}|{workload.pace_bucket_hi}".encode()
    ).hexdigest()
    return f"camp-{digest[:16]}"


def _validate_seed(seed: int) -> None:
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise BenignFaultError(REASON_INVALID_SEED, "seed must be a non-negative integer")


def _validate_tenant(tenant: str) -> None:
    if not isinstance(tenant, str) or not _TENANT_PATTERN.fullmatch(tenant):
        raise BenignFaultError(
            REASON_INVALID_TENANT,
            f"tenant must match {_TENANT_PATTERN.pattern}, got {tenant!r}",
        )
    lowered = tenant.lower()
    if any(marker in lowered for marker in cg.PHI_SCAN_MARKERS):
        raise BenignFaultError(REASON_PHI_FIELD_PRESENT, f"tenant {tenant!r} looks like PHI/PII")


def _validate_workload(workload: WorkloadProfile) -> WorkloadProfile:
    """Validate the volume/cadence profile; refuse any budget that cannot be honored."""

    if not isinstance(workload, WorkloadProfile):
        raise BenignFaultError(
            REASON_INVALID_WORKLOAD,
            f"workload must be a WorkloadProfile, got {type(workload).__name__}",
        )
    _validate_tenant(workload.tenant)
    target = workload.target_events
    if isinstance(target, bool) or not isinstance(target, int):
        raise BenignFaultError(REASON_INVALID_WORKLOAD, "target_events must be an integer")
    if target < MIN_TARGET_EVENTS:
        raise BenignFaultError(
            REASON_VOLUME_BUDGET_EXCEEDED,
            f"requested volume budget {target} is below the minimum realizable benign "
            f"campaign of {MIN_TARGET_EVENTS} events (1 baseline + one event per benign "
            f"fault type {list(BENIGN_FAULT_TYPES)}); exceeding the requested volume "
            f"budget is refused (fail closed)",
        )
    if target > MAX_TARGET_EVENTS:
        raise BenignFaultError(
            REASON_INVALID_WORKLOAD,
            f"target_events {target} exceeds the supported maximum {MAX_TARGET_EVENTS}",
        )
    for name in ("pace_bucket_lo", "pace_bucket_hi"):
        value = getattr(workload, name)
        if isinstance(value, bool) or not isinstance(value, int):
            raise BenignFaultError(REASON_INVALID_WORKLOAD, f"{name} must be an integer")
    lo, hi = workload.pace_bucket_lo, workload.pace_bucket_hi
    if not 1 <= lo <= hi <= MAX_PACE_GAP_BUCKETS:
        raise BenignFaultError(
            REASON_INVALID_WORKLOAD,
            f"pace bounds must satisfy 1 <= lo <= hi <= {MAX_PACE_GAP_BUCKETS}, "
            f"got ({lo}, {hi})",
        )
    return workload


def _plan_context(seed: int, workload: WorkloadProfile) -> _BenignContext:
    plan = [
        _entropy_int(
            BENIGN_FAULT_GENERATOR_VERSION,
            seed,
            workload.tenant,
            workload.target_events,
            "plan",
            n,
        )
        for n in range(6)
    ]
    principal_identity = f"{workload.tenant}|principal:0"
    epoch = 1 + plan[3] % 8
    purpose = cg.PURPOSE_CLASSES[plan[1] % len(cg.PURPOSE_CLASSES)]
    return _BenignContext(
        seed=seed,
        tenant=workload.tenant,
        target_events=workload.target_events,
        pace_lo=workload.pace_bucket_lo,
        pace_hi=workload.pace_bucket_hi,
        principal_identity=principal_identity,
        actor=cg._actor_hash(seed, principal_identity),
        purpose=purpose,
        tool=cg.TOOL_CLASSES[plan[2] % len(cg.TOOL_CLASSES)],
        epoch=epoch,
        origin_bucket=1_000_000 + (plan[4] // 8) % 1_000_000,
        baseline_scope=cg._scope_hash(workload.tenant, principal_identity, purpose, epoch),
        campaign_id=_campaign_id(seed, workload),
    )


def _rotated_fault_types(rotation: int) -> tuple[str, ...]:
    """Deterministic fault-type execution order rotated by hash entropy."""

    count = len(BENIGN_FAULT_TYPES)
    offset = rotation % count
    return tuple(BENIGN_FAULT_TYPES[(offset + i) % count] for i in range(count))


def _plan_fault_allocation(
    ctx: _BenignContext,
) -> tuple[tuple[str, ...], Mapping[str, int]]:
    """Deterministic per-type event counts filling the volume budget exactly.

    Every registered fault type receives at least its minimum genuine-repertoire
    count (guaranteed by ``MIN_TARGET_EVENTS``); the remainder is spread over
    the seed-rotated execution order so the allocation sums to exactly
    ``ctx.target_events - 1`` fault events.
    """

    fault_slots = ctx.target_events - 1
    minimums = [MIN_FAULT_EVENTS[fault_type] for fault_type in BENIGN_FAULT_TYPES]
    remaining = fault_slots - sum(minimums)
    rotation = _entropy_int(ctx.seed, ctx.tenant, ctx.target_events, "fault-rotation")
    ordered = _rotated_fault_types(rotation)
    extra = [remaining // len(ordered)] * len(ordered)
    for i in range(remaining % len(ordered)):
        extra[i] += 1
    counts = {
        fault_type: MIN_FAULT_EVENTS[fault_type] + extra[i]
        for i, fault_type in enumerate(ordered)
    }
    return ordered, counts


def _profile_gap(ctx: _BenignContext, tag: str, index: int) -> int:
    """Deterministic inter-arrival gap inside the requested cadence profile."""

    span = ctx.pace_hi - ctx.pace_lo
    if span == 0:
        return ctx.pace_lo
    return ctx.pace_lo + _entropy_int(ctx.seed, ctx.tenant, ctx.target_events, tag, index) % (
        span + 1
    )


def _backoff_gap(ctx: _BenignContext, tag: str, index: int) -> int:
    """Profile-admissible backoff gap strictly above the tightest pacing bound."""

    span = ctx.pace_hi - ctx.pace_lo
    if span == 0:
        return ctx.pace_lo
    return ctx.pace_lo + 1 + _entropy_int(ctx.seed, ctx.tenant, ctx.target_events, tag, index) % span


def _make_benign_event(
    ctx: _BenignContext,
    *,
    ts: int,
    allowed: bool,
    purpose: str | None = None,
    scope: str | None = None,
) -> dict[str, Any]:
    """Build one minimal event via the shared label-refusing, schema-gated builder."""

    return cg._make_event(
        actor=ctx.actor,
        tool=ctx.tool,
        scope=ctx.baseline_scope if scope is None else scope,
        allowed=allowed,
        purpose=ctx.purpose if purpose is None else purpose,
        ts=ts,
        campaign_id=ctx.campaign_id,
    )


def _rate_limit_retry_events(
    ctx: _BenignContext, k: int, bucket: int
) -> tuple[list[dict[str, Any]], int]:
    """Tightest profile-admissible burst of identical attempts until admitted."""

    events: list[dict[str, Any]] = []
    for i in range(k):
        bucket += ctx.pace_lo
        events.append(_make_benign_event(ctx, ts=bucket, allowed=(i == k - 1)))
    return events, bucket


def _network_retry_events(
    ctx: _BenignContext, k: int, bucket: int
) -> tuple[list[dict[str, Any]], int]:
    """Backoff-paced identical retries after transport failures until admitted."""

    events: list[dict[str, Any]] = []
    for i in range(k):
        bucket += _backoff_gap(ctx, "network-gap", i)
        events.append(_make_benign_event(ctx, ts=bucket, allowed=(i == k - 1)))
    return events, bucket


def _ux_confusion_retry_events(
    ctx: _BenignContext, k: int, bucket: int
) -> tuple[list[dict[str, Any]], int]:
    """Mis-scoped purpose selections before the correct purpose is admitted."""

    events: list[dict[str, Any]] = []
    rotation = _entropy_int(ctx.seed, ctx.tenant, ctx.target_events, "ux-purpose-offset")
    other_purposes = [p for p in cg.PURPOSE_CLASSES if p != ctx.purpose]
    for i in range(k):
        bucket += _profile_gap(ctx, "ux-gap", i)
        if i < k - 1:
            wrong = other_purposes[(rotation + i) % len(other_purposes)]
            events.append(
                _make_benign_event(
                    ctx,
                    ts=bucket,
                    allowed=False,
                    purpose=wrong,
                    scope=cg._scope_hash(ctx.tenant, ctx.principal_identity, wrong, ctx.epoch),
                )
            )
        else:
            events.append(_make_benign_event(ctx, ts=bucket, allowed=True))
    return events, bucket


def _consent_edit_events(
    ctx: _BenignContext, k: int, bucket: int
) -> tuple[list[dict[str, Any]], int]:
    """Legitimate consent/epoch edits producing fresh authorized scopes (all admitted)."""

    events: list[dict[str, Any]] = []
    for i in range(k):
        bucket += _profile_gap(ctx, "consent-gap", i)
        fresh_scope = cg._scope_hash(
            ctx.tenant, ctx.principal_identity, ctx.purpose, ctx.epoch + 1 + i
        )
        events.append(_make_benign_event(ctx, ts=bucket, allowed=True, scope=fresh_scope))
    return events, bucket


def _delayed_timestamps_events(
    ctx: _BenignContext, k: int, bucket: int
) -> tuple[list[dict[str, Any]], int]:
    """Legitimate long stalls / deferred actions beyond the pacing profile."""

    events: list[dict[str, Any]] = []
    for i in range(k):
        bucket += DELAYED_GAP_MIN_BUCKETS + _entropy_int(
            ctx.seed, ctx.tenant, ctx.target_events, "delayed-gap", i
        ) % 4
        events.append(_make_benign_event(ctx, ts=bucket, allowed=True))
    return events, bucket


_FAULT_BUILDERS: Mapping[str, Any] = {
    "rate_limit_retry": _rate_limit_retry_events,
    "network_retry": _network_retry_events,
    "ux_confusion_retry": _ux_confusion_retry_events,
    "consent_edit": _consent_edit_events,
    "delayed_timestamps": _delayed_timestamps_events,
}


def _assert_volume_and_cadence(campaign: cg.Campaign, workload: WorkloadProfile) -> None:
    """Fail closed unless the campaign honors the requested volume budget exactly.

    The event count must equal ``workload.target_events`` (never exceed it) and
    every non-delayed inter-arrival gap must lie inside the requested cadence
    profile. Gaps of at least :data:`DELAYED_GAP_MIN_BUCKETS` are the deliberate
    benign delayed-timestamp stalls; because profile bounds are capped at
    :data:`MAX_PACE_GAP_BUCKETS` ``< DELAYED_GAP_MIN_BUCKETS`` the two classes
    are unambiguously separable by gap size.
    """

    if len(campaign.events) != workload.target_events:
        raise BenignFaultError(
            REASON_VOLUME_BUDGET_EXCEEDED,
            f"campaign {campaign.campaign_id} carries {len(campaign.events)} events, "
            f"exceeding the requested volume budget {workload.target_events}; "
            f"over-production is refused (fail closed)",
        )
    previous_ts: int | None = None
    for index, event in enumerate(campaign.events):
        ts = event["ts"]
        if previous_ts is not None:
            gap = ts - previous_ts
            if gap < DELAYED_GAP_MIN_BUCKETS and not (
                workload.pace_bucket_lo <= gap <= workload.pace_bucket_hi
            ):
                raise BenignFaultError(
                    REASON_CADENCE_PROFILE_VIOLATED,
                    f"event {index} of {campaign.campaign_id} has inter-arrival gap {gap} "
                    f"outside the requested cadence profile "
                    f"[{workload.pace_bucket_lo}, {workload.pace_bucket_hi}]",
                )
        previous_ts = ts


def generate_benign(seed: int, workload: WorkloadProfile) -> cg.Campaign:
    """Generate one deterministic BENIGN fault campaign for ``(seed, workload)``.

    The campaign contains exactly ``workload.target_events`` events — one
    baseline event plus the benign fault repertoire (rate-limit retries,
    network retries, UX confusion retries, legitimate consent edits, delayed
    timestamps) filling the remaining budget — so benign and attack arms can be
    volume-matched. Carries ``campaign_label="BENIGN"`` and
    ``violated_invariant="NONE"`` at campaign level only; events never carry
    labels, invariants, tenants, reason codes or PHI.

    Raises :class:`BenignFaultError` with a stable reason code on an invalid
    seed or tenant, a malformed workload, a volume budget that cannot be
    honored without over-production (``VOLUME_BUDGET_EXCEEDED``), a cadence
    profile violation, or any PHI/label/schema-shape violation.
    """

    _validate_seed(seed)
    _validate_workload(workload)
    ctx = _plan_context(seed, workload)
    ordered, counts = _plan_fault_allocation(ctx)
    events: list[dict[str, Any]] = [_make_benign_event(ctx, ts=ctx.origin_bucket, allowed=True)]
    bucket = ctx.origin_bucket
    for fault_type in ordered:
        produced, bucket = _FAULT_BUILDERS[fault_type](ctx, counts[fault_type], bucket)
        events.extend(produced)
    if len(events) != workload.target_events:
        raise BenignFaultError(
            REASON_VOLUME_BUDGET_EXCEEDED,
            f"planned event count {len(events)} does not match the requested volume "
            f"budget {workload.target_events}; over-production is refused (fail closed)",
        )
    campaign = cg.Campaign(
        campaign_id=ctx.campaign_id,
        tenant=ctx.tenant,
        family=FAMILY_BENIGN_FAULTS,
        events=tuple(events),
        campaign_label=cg.LABEL_BENIGN,
        violated_invariant=cg.INVARIANT_NONE,
        generator_version=BENIGN_FAULT_GENERATOR_VERSION,
    )
    cg._assert_schema_shaped(campaign)
    cg._assert_phi_free(campaign)
    _assert_volume_and_cadence(campaign, workload)
    return campaign
