"""DIMVA venue2027 synthetic adaptive attack-campaign generator (task DIMVA-X02_campaign_gen, phase P02).

Purpose
-------
Produce deterministic, PHI-free multi-stage attack CAMPAIGNS for the DIMVA 2027
"GovernanceTrace" study (``research/venue2027/VENUES/dimva/TASKS/DIMVA-X02_campaign_gen.md``).
Each campaign is a sequence of minimal agent events whose fields conform to the
frozen telemetry contract ``research/venue2027/dimva/protocols/event.schema.json``
(exactly seven fields: ``actor``, ``tool``, ``scope``, ``allowed``, ``purpose``,
``ts``, ``campaign_id``; actor/scope are opaque SHA-256 hex digests, purpose is a
closed coarse enum, ``ts`` is a 60-second bucket index). The registered stage
sequences cover purpose probing, cross-principal retries, expired-token replays,
cadence (pacing) changes and a harmless control. LABELS EXIST ONLY AT CAMPAIGN
LEVEL: ``campaign_label`` (``ATTACK``/``BENIGN``) and ``violated_invariant`` live
on the :class:`Campaign` object; per-event labels are structurally refused (the
event builder rejects any label-like field and the seven-field gate fails closed),
so no event ever carries the ground truth. Every entropy source is a SHA-256
digest of stable coordinate strings — no ``random`` module, no clock, no
environment reads — so the same ``(seed, family, tenant)`` always yields a
byte-identical campaign. Campaign identifiers are opaque (``camp-<16 hex>``) and
never encode the family or label, preventing trivial template leakage across
splits. No raw patient data, no rejection reason codes, no live provider.

Allowed input
-------------
``generate(seed, family, tenant)`` with a non-negative integer ``seed``, a
registered ``family`` (see ``FAMILY_SPECS``) and a synthetic ``tenant`` matching
``^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$``. All outputs are JSON-serializable
(``Campaign.to_dict()``).

Failure semantics
-----------------
Every error is a :class:`CampaignError` carrying a stable reason code:
``INVALID_SEED``, ``INVALID_TENANT``, ``UNKNOWN_FAMILY``, ``PHI_FIELD_PRESENT``,
``EVENT_LABEL_FIELD_FORBIDDEN``, ``EVENT_FIELD_MISMATCH``. The generator never
emits a per-event label, a PHI-named field/value, a clear-text principal, or an
event outside the seven-field schema surface; violations fail closed instead of
being silently repaired.

Version
-------
``CAMPAIGN_GENERATOR_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from evaluation.venue2027._shared import dataset_kernel as _kernel

CAMPAIGN_GENERATOR_VERSION = "1.0.0"

VENUE = "dimva"

#: Stable reason codes carried by :class:`CampaignError`.
REASON_INVALID_SEED = "INVALID_SEED"
REASON_INVALID_TENANT = "INVALID_TENANT"
REASON_UNKNOWN_FAMILY = "UNKNOWN_FAMILY"
REASON_PHI_FIELD_PRESENT = "PHI_FIELD_PRESENT"
REASON_EVENT_LABEL_FIELD_FORBIDDEN = "EVENT_LABEL_FIELD_FORBIDDEN"
REASON_EVENT_FIELD_MISMATCH = "EVENT_FIELD_MISMATCH"


class CampaignError(ValueError):
    """Fail-closed generator error with a stable, machine-checkable reason code."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(f"{reason_code}: {message}")
        self.reason_code = reason_code


#: Coarse purpose classes; mirrors the closed enum in event.schema.json.
PURPOSE_CLASSES: tuple[str, ...] = (
    "self_care",
    "care_delivery",
    "care_team_handoff",
    "administration",
    "audit",
)

#: Coarse tool/action classes (snake_case tokens, no argument payload).
TOOL_CLASSES: tuple[str, ...] = (
    "record_read",
    "record_write",
    "record_export",
    "schedule_read",
    "message_send",
    "audit_query",
)

#: The exact minimal event surface; anything else fails closed.
EVENT_FIELDS: frozenset[str] = frozenset(
    {"actor", "tool", "scope", "allowed", "purpose", "ts", "campaign_id"}
)

#: Label-like field names that must never appear on an event.
EVENT_LABEL_FIELDS: frozenset[str] = frozenset(
    {"label", "campaign_label", "violated_invariant", "attacker_label", "is_attack"}
)

LABEL_ATTACK = "ATTACK"
LABEL_BENIGN = "BENIGN"
INVARIANT_NONE = "NONE"
INVARIANT_PURPOSE_SCOPE_AUTHORIZATION = "PURPOSE_SCOPE_AUTHORIZATION"
INVARIANT_PRINCIPAL_SCOPE_BINDING = "PRINCIPAL_SCOPE_BINDING"
INVARIANT_CREDENTIAL_EPOCH_FRESHNESS = "CREDENTIAL_EPOCH_FRESHNESS"
INVARIANT_PACING_BASELINE_STABILITY = "PACING_BASELINE_STABILITY"

#: Fixed synthetic pacing window (in 60 s buckets) of the benign baseline;
#: cadence-shift campaigns push inter-arrival gaps strictly beyond it.
PACE_WINDOW_BUCKETS = 5

#: Fixed synthetic credential/consent freshness horizon (in 60 s buckets);
#: expired-token replays resume only after this offset from the baseline event.
TOKEN_EXPIRY_HORIZON_BUCKETS = 10

_TENANT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$")
_TOOL_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_CAMPAIGN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
_HEX64_PATTERN = re.compile(r"^[0-9a-f]{64}$")

#: Canonical PHI/PII markers (shared kernel list plus extra clinical markers)
#: used for the fail-closed serialization scan.
PHI_SCAN_MARKERS: tuple[str, ...] = _kernel.PHI_FIELD_MARKERS + (
    "patient",
    "diagnosis",
    "ssn",
    "symptom",
    "prescription",
)


@dataclasses.dataclass(frozen=True)
class FamilySpec:
    """Campaign-level contract for one registered attack family.

    ``campaign_label`` and ``violated_invariant`` are campaign-level only.
    ``stage_events`` is the inclusive ``[lo, hi]`` range of violating-stage
    events for attack families and of total events for the harmless control.
    """

    campaign_label: str
    violated_invariant: str
    stage_events: tuple[int, int]


#: Registered families. The control is the only BENIGN family and the only one
#: whose violated invariant is ``NONE``.
FAMILY_SPECS: Mapping[str, FamilySpec] = {
    "purpose_probe": FamilySpec(
        campaign_label=LABEL_ATTACK,
        violated_invariant=INVARIANT_PURPOSE_SCOPE_AUTHORIZATION,
        stage_events=(4, 8),
    ),
    "cross_principal_retry": FamilySpec(
        campaign_label=LABEL_ATTACK,
        violated_invariant=INVARIANT_PRINCIPAL_SCOPE_BINDING,
        stage_events=(3, 6),
    ),
    "expired_token_replay": FamilySpec(
        campaign_label=LABEL_ATTACK,
        violated_invariant=INVARIANT_CREDENTIAL_EPOCH_FRESHNESS,
        stage_events=(3, 6),
    ),
    "cadence_shift": FamilySpec(
        campaign_label=LABEL_ATTACK,
        violated_invariant=INVARIANT_PACING_BASELINE_STABILITY,
        stage_events=(4, 8),
    ),
    "harmless_control": FamilySpec(
        campaign_label=LABEL_BENIGN,
        violated_invariant=INVARIANT_NONE,
        stage_events=(3, 6),
    ),
}


@dataclasses.dataclass(frozen=True)
class Campaign:
    """A labeled multi-stage campaign of minimal agent events.

    The label pair (``campaign_label``, ``violated_invariant``) is campaign-level
    metadata only; the contained ``events`` carry exactly the seven schema fields
    and never any label, invariant, tenant, reason code or PHI.
    """

    campaign_id: str
    tenant: str
    family: str
    events: tuple[dict[str, Any], ...]
    campaign_label: str
    violated_invariant: str
    generator_version: str = CAMPAIGN_GENERATOR_VERSION

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable representation with copied event dicts."""

        return {
            "campaign_id": self.campaign_id,
            "tenant": self.tenant,
            "family": self.family,
            "events": [dict(event) for event in self.events],
            "campaign_label": self.campaign_label,
            "violated_invariant": self.violated_invariant,
            "generator_version": self.generator_version,
        }


@dataclasses.dataclass(frozen=True)
class _PlanContext:
    """Deterministic per-campaign constants derived once from (seed, family, tenant)."""

    seed: int
    tenant: str
    family: str
    stage_count: int
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


def _actor_hash(seed: int, principal_identity: str) -> str:
    """Opaque principal: SHA-256 of the synthetic actor identifier (never clear text)."""

    return hashlib.sha256(f"actor|{seed}|{principal_identity}".encode()).hexdigest()


def _scope_hash(tenant: str, principal_identity: str, purpose: str, epoch: int) -> str:
    """Hashed authorization scope over the (tenant, principal, purpose, epoch) tuple."""

    return hashlib.sha256(
        f"scope|{tenant}|{principal_identity}|{purpose}|{epoch}".encode()
    ).hexdigest()


def _campaign_id(seed: int, family: str, tenant: str) -> str:
    """Opaque campaign identifier; the family contributes only hash entropy."""

    digest = hashlib.sha256(
        f"campaign|{CAMPAIGN_GENERATOR_VERSION}|{seed}|{tenant}|{family}".encode()
    ).hexdigest()
    return f"camp-{digest[:16]}"


def _make_event(**fields: Any) -> dict[str, Any]:
    """Build one minimal event; refuse labels and any off-schema field fail closed."""

    label_hits = sorted(EVENT_LABEL_FIELDS & fields.keys())
    if label_hits:
        raise CampaignError(
            REASON_EVENT_LABEL_FIELD_FORBIDDEN,
            f"per-event labels are forbidden, refused fields: {label_hits}",
        )
    if set(fields) != EVENT_FIELDS:
        raise CampaignError(
            REASON_EVENT_FIELD_MISMATCH,
            f"event fields must be exactly {sorted(EVENT_FIELDS)}, got {sorted(fields)}",
        )
    return dict(fields)


def _validate_seed(seed: int) -> None:
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise CampaignError(REASON_INVALID_SEED, "seed must be a non-negative integer")


def _validate_tenant(tenant: str) -> None:
    if not isinstance(tenant, str) or not _TENANT_PATTERN.fullmatch(tenant):
        raise CampaignError(
            REASON_INVALID_TENANT,
            f"tenant must match {_TENANT_PATTERN.pattern}, got {tenant!r}",
        )
    lowered = tenant.lower()
    if any(marker in lowered for marker in PHI_SCAN_MARKERS):
        raise CampaignError(REASON_PHI_FIELD_PRESENT, f"tenant {tenant!r} looks like PHI/PII")


def _baseline_event(ctx: _PlanContext, *, ts: int, allowed: bool = True) -> dict[str, Any]:
    return _make_event(
        actor=ctx.actor,
        tool=ctx.tool,
        scope=ctx.baseline_scope,
        allowed=allowed,
        purpose=ctx.purpose,
        ts=ts,
        campaign_id=ctx.campaign_id,
    )


def _purpose_probe_events(ctx: _PlanContext) -> list[dict[str, Any]]:
    """Same principal re-attempts the same operation under unauthorized purposes."""

    events = [_baseline_event(ctx, ts=ctx.origin_bucket)]
    bucket = ctx.origin_bucket
    rotation = _entropy_int(ctx.seed, ctx.tenant, ctx.family, "purpose-offset")
    other_purposes = [p for p in PURPOSE_CLASSES if p != ctx.purpose]
    for i in range(ctx.stage_count):
        bucket += 1 + _entropy_int(ctx.seed, ctx.tenant, ctx.family, "gap", i) % 2
        purpose = other_purposes[(rotation + i) % len(other_purposes)]
        events.append(
            _make_event(
                actor=ctx.actor,
                tool=ctx.tool,
                scope=_scope_hash(ctx.tenant, ctx.principal_identity, purpose, ctx.epoch),
                allowed=False,
                purpose=purpose,
                ts=bucket,
                campaign_id=ctx.campaign_id,
            )
        )
    return events


def _cross_principal_retry_events(ctx: _PlanContext) -> list[dict[str, Any]]:
    """Rotating unbound principals retry the same operation and are denied."""

    events = [_baseline_event(ctx, ts=ctx.origin_bucket)]
    bucket = ctx.origin_bucket
    for i in range(ctx.stage_count):
        bucket += 1 + _entropy_int(ctx.seed, ctx.tenant, ctx.family, "gap", i) % 3
        principal = f"{ctx.tenant}|principal:{i + 1}"
        events.append(
            _make_event(
                actor=_actor_hash(ctx.seed, principal),
                tool=ctx.tool,
                scope=_scope_hash(ctx.tenant, principal, ctx.purpose, ctx.epoch),
                allowed=False,
                purpose=ctx.purpose,
                ts=bucket,
                campaign_id=ctx.campaign_id,
            )
        )
    return events


def _expired_token_replay_events(ctx: _PlanContext) -> list[dict[str, Any]]:
    """Identical operation replayed after the freshness horizon; denied each time."""

    events = [_baseline_event(ctx, ts=ctx.origin_bucket)]
    jitter = _entropy_int(ctx.seed, ctx.tenant, ctx.family, "expiry-jitter") % 3
    bucket = ctx.origin_bucket + TOKEN_EXPIRY_HORIZON_BUCKETS + jitter
    for i in range(ctx.stage_count):
        events.append(
            _make_event(
                actor=ctx.actor,
                tool=ctx.tool,
                scope=ctx.baseline_scope,
                allowed=False,
                purpose=ctx.purpose,
                ts=bucket,
                campaign_id=ctx.campaign_id,
            )
        )
        bucket += 1 + _entropy_int(ctx.seed, ctx.tenant, ctx.family, "replay-gap", i) % 2
    return events


def _cadence_shift_events(ctx: _PlanContext) -> list[dict[str, Any]]:
    """Same-scope probes with inter-arrival gaps pushed beyond the pacing window."""

    events = [_baseline_event(ctx, ts=ctx.origin_bucket)]
    bucket = ctx.origin_bucket
    other_tools = [t for t in TOOL_CLASSES if t != ctx.tool]
    for i in range(ctx.stage_count):
        bucket += PACE_WINDOW_BUCKETS + 1 + 2 * i + _entropy_int(
            ctx.seed, ctx.tenant, ctx.family, "shift", i
        ) % 2
        tool = other_tools[
            _entropy_int(ctx.seed, ctx.tenant, ctx.family, "tool", i) % len(other_tools)
        ]
        events.append(
            _make_event(
                actor=ctx.actor,
                tool=tool,
                scope=ctx.baseline_scope,
                allowed=False,
                purpose=ctx.purpose,
                ts=bucket,
                campaign_id=ctx.campaign_id,
            )
        )
    return events


def _harmless_control_events(ctx: _PlanContext) -> list[dict[str, Any]]:
    """Short steady session: one transient denial followed by an authorized retry."""

    total = ctx.stage_count
    denial_at = 1 + _entropy_int(ctx.seed, ctx.tenant, ctx.family, "denial-at") % (total - 2)
    events: list[dict[str, Any]] = []
    bucket = ctx.origin_bucket
    for i in range(total):
        if i > 0:
            bucket += 1 + _entropy_int(ctx.seed, ctx.tenant, ctx.family, "pace", i) % (
                PACE_WINDOW_BUCKETS
            )
        events.append(
            _make_event(
                actor=ctx.actor,
                tool=ctx.tool,
                scope=ctx.baseline_scope,
                allowed=i != denial_at,
                purpose=ctx.purpose,
                ts=bucket,
                campaign_id=ctx.campaign_id,
            )
        )
    return events


_EVENT_BUILDERS: Mapping[str, Any] = {
    "purpose_probe": _purpose_probe_events,
    "cross_principal_retry": _cross_principal_retry_events,
    "expired_token_replay": _expired_token_replay_events,
    "cadence_shift": _cadence_shift_events,
    "harmless_control": _harmless_control_events,
}


def _plan_context(seed: int, family: str, tenant: str, spec: FamilySpec) -> _PlanContext:
    plan = [
        _entropy_int(CAMPAIGN_GENERATOR_VERSION, seed, tenant, family, "plan", n) for n in range(4)
    ]
    lo, hi = spec.stage_events
    stage_count = lo + plan[0] % (hi - lo + 1)
    principal_identity = f"{tenant}|principal:0"
    epoch = 1 + plan[3] % 8
    purpose = PURPOSE_CLASSES[plan[1] % len(PURPOSE_CLASSES)]
    return _PlanContext(
        seed=seed,
        tenant=tenant,
        family=family,
        stage_count=stage_count,
        principal_identity=principal_identity,
        actor=_actor_hash(seed, principal_identity),
        purpose=purpose,
        tool=TOOL_CLASSES[plan[2] % len(TOOL_CLASSES)],
        epoch=epoch,
        origin_bucket=1_000_000 + (plan[3] // 8) % 1_000_000,
        baseline_scope=_scope_hash(tenant, principal_identity, purpose, epoch),
        campaign_id=_campaign_id(seed, family, tenant),
    )


def _assert_schema_shaped(campaign: Campaign) -> None:
    """Fail closed unless every event is exactly the seven-field schema surface."""

    for index, event in enumerate(campaign.events):
        if set(event) != EVENT_FIELDS:
            raise CampaignError(
                REASON_EVENT_FIELD_MISMATCH,
                f"event {index} of {campaign.campaign_id} has fields {sorted(event)}",
            )
        if not (_HEX64_PATTERN.fullmatch(event["actor"]) and _HEX64_PATTERN.fullmatch(event["scope"])):
            raise CampaignError(
                REASON_EVENT_FIELD_MISMATCH,
                f"event {index} of {campaign.campaign_id} has a non-digest actor/scope",
            )
        if not isinstance(event["tool"], str) or not _TOOL_PATTERN.fullmatch(event["tool"]):
            raise CampaignError(
                REASON_EVENT_FIELD_MISMATCH,
                f"event {index} of {campaign.campaign_id} has a malformed tool token",
            )
        if not isinstance(event["allowed"], bool):
            raise CampaignError(
                REASON_EVENT_FIELD_MISMATCH,
                f"event {index} of {campaign.campaign_id} has a non-boolean allowed flag",
            )
        if event["purpose"] not in PURPOSE_CLASSES:
            raise CampaignError(
                REASON_EVENT_FIELD_MISMATCH,
                f"event {index} of {campaign.campaign_id} has purpose {event['purpose']!r}",
            )
        ts = event["ts"]
        if isinstance(ts, bool) or not isinstance(ts, int) or ts < 0:
            raise CampaignError(
                REASON_EVENT_FIELD_MISMATCH,
                f"event {index} of {campaign.campaign_id} has a malformed ts bucket",
            )
        if not isinstance(event["campaign_id"], str) or not _CAMPAIGN_ID_PATTERN.fullmatch(
            event["campaign_id"]
        ):
            raise CampaignError(
                REASON_EVENT_FIELD_MISMATCH,
                f"event {index} of {campaign.campaign_id} has a malformed campaign_id",
            )


def _assert_phi_free(campaign: Campaign) -> None:
    """Fail closed if any serialized campaign content carries a PHI/PII marker."""

    serialized = json.dumps(campaign.to_dict(), sort_keys=True).lower()
    for marker in PHI_SCAN_MARKERS:
        if marker in serialized:
            raise CampaignError(
                REASON_PHI_FIELD_PRESENT,
                f"serialized campaign {campaign.campaign_id} carries PHI marker {marker!r}",
            )


def generate(seed: int, family: str, tenant: str) -> Campaign:
    """Generate one deterministic campaign for ``(seed, family, tenant)``.

    Raises :class:`CampaignError` with a stable reason code on invalid seed or
    tenant, an unknown family, or any PHI/label/schema-shape violation. Control
    campaigns carry ``campaign_label="BENIGN"`` and ``violated_invariant="NONE"``;
    attack campaigns carry ``"ATTACK"`` and their violated invariant. Labels are
    attached only at campaign level and never appear on events.
    """

    _validate_seed(seed)
    _validate_tenant(tenant)
    spec = FAMILY_SPECS.get(family)
    if spec is None:
        raise CampaignError(
            REASON_UNKNOWN_FAMILY,
            f"family {family!r} is not registered; expected one of {sorted(FAMILY_SPECS)}",
        )
    ctx = _plan_context(seed, family, tenant, spec)
    builder = _EVENT_BUILDERS[family]
    campaign = Campaign(
        campaign_id=ctx.campaign_id,
        tenant=tenant,
        family=family,
        events=tuple(builder(ctx)),
        campaign_label=spec.campaign_label,
        violated_invariant=spec.violated_invariant,
    )
    _assert_schema_shaped(campaign)
    _assert_phi_free(campaign)
    return campaign
