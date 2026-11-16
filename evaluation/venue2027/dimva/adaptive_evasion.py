"""DIMVA-X07_adaptive_evasion — Low-and-slow and metadata-tampering evaluation.

Purpose
-------
Task DIMVA-X07_adaptive_evasion (Phase P05, venue ``dimva``): adaptive evasion
and low-and-slow probing evaluation for "GovernanceTrace: Detecting Adaptive
Authorization-Boundary Probing from Minimal Agent Events"
(``research/venue2027/VENUES/dimva/RESEARCH_BLUEPRINT.md``, RQ3; task contract
``research/venue2027/VENUES/dimva/TASKS/DIMVA-X07_adaptive_evasion.md``).

An adaptive adversary attempts to evade detection by manipulating the observable
agent event stream along several tactical axes:
1. Pacing (inter-arrival delay manipulation): spreading out requests across time
   so that denial counts inside sliding fixed-width windows stay strictly under
   operational rate thresholds (evading B0 window count).
2. Benign interleaving (padding with legitimate tool actions): injecting allowed,
   legitimate tool calls to dilute denial ratios and suppress event-rate anomalies
   (evading simple rate-based comparators and rate anomalies).
3. Field scrambling and minimal-field projection: reordering serialized event
   fields or omitting non-essential optional metadata while preserving the minimal
   leak-safe schema surface.
4. Composite evasion: simultaneously applying pacing, interleaving, and structural
   scrambling.

ATTACKER BOUNDARY CONTRACT:
--------------------------
The attacker controls ONLY permitted observable events (requests they emit
under their authenticated principal: tooling, requested scope, and logical time).
The attacker DOES NOT have access to or control over backend infrastructure:
- Tampering with signed backend audit logs or server logs is refused outright
  (:class:`PrivilegedTamperingError`);
- Overwriting ground truth or oracle labels is refused;
- Injecting forbidden rejection reason codes (e.g. ``reason_code``,
  ``denial_reason``) violates the RQ1 leak-safe masking contract and fails closed;
- Cross-actor event forging / impersonation (mixed actors in a single session)
  fails closed;
- Non-monotonic timestamps are refused.

Core API
--------
- :func:`generate_evasive_campaign` — ``generate_evasive_campaign(base_campaign, strategy) -> EvasiveCampaign``
- :func:`evaluate_adaptation` — ``evaluate_adaptation(model, campaigns) -> Metrics`` (exact contract)
- :func:`evaluate_arms_evasion` — evaluates evasion impact across B0, B1, B2, and candidate
- :func:`fixed_test_campaign_families` — deterministic reference base campaigns
- :func:`refuse_privileged_tampering` — guards against privileged attacker assumptions

Determinism & Conventions
-------------------------
Pure functions over JSON-serializable structures; sorted iterations; no clock,
no network, no database, no hidden randomness. Conforms to Python >= 3.11,
ruff, and repository testing conventions.

Version
-------
``ADAPTIVE_EVASION_VERSION = "1.0.0"``
``MODULE_ID = "clara.dimva.adaptive-evasion"``
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Final

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.dimva import baselines, candidate

ADAPTIVE_EVASION_VERSION: Final[str] = "1.0.0"
MODULE_ID: Final[str] = "clara.dimva.adaptive-evasion"
TASK_ID: Final[str] = "DIMVA-X07_adaptive_evasion"

# ---------------------------------------------------------------------------
# Evasion strategies (closed, stable enum).
# ---------------------------------------------------------------------------
STRATEGY_PACING: Final[str] = "pacing"
STRATEGY_BENIGN_INTERLEAVING: Final[str] = "benign_interleaving"
STRATEGY_FIELD_SCRAMBLING: Final[str] = "field_scrambling"
STRATEGY_MISSING_OPTIONAL_FIELDS: Final[str] = "missing_optional_fields"
STRATEGY_COMPOSITE: Final[str] = "composite"

SUPPORTED_STRATEGIES: Final[frozenset[str]] = frozenset(
    {
        STRATEGY_PACING,
        STRATEGY_BENIGN_INTERLEAVING,
        STRATEGY_FIELD_SCRAMBLING,
        STRATEGY_MISSING_OPTIONAL_FIELDS,
        STRATEGY_COMPOSITE,
    }
)

# ---------------------------------------------------------------------------
# Reason codes (stable, uppercase, machine-checkable).
# ---------------------------------------------------------------------------
RC_ADAPTATION_EVALUATED: Final[str] = "ADAPTATION_EVALUATED"
RC_EVASIVE_CAMPAIGN_GENERATED: Final[str] = "EVASIVE_CAMPAIGN_GENERATED"
RC_UNKNOWN_STRATEGY: Final[str] = "UNKNOWN_STRATEGY"
RC_INVALID_BASE_CAMPAIGN: Final[str] = "INVALID_BASE_CAMPAIGN"
RC_EMPTY_EVENTS: Final[str] = "EMPTY_EVENTS"
RC_PRIVILEGED_LOG_TAMPERING: Final[str] = "PRIVILEGED_LOG_TAMPERING_REFUSED"
RC_UNPERMITTED_EVENT_FIELD: Final[str] = "UNPERMITTED_EVENT_FIELD_REFUSED"
RC_EVENT_REASON_CODE_FORBIDDEN: Final[str] = "EVENT_REASON_CODE_FIELD_FORBIDDEN"
RC_SESSION_MIXED_ACTORS: Final[str] = "SESSION_MIXED_ACTORS"
RC_EVENT_TS_NOT_MONOTONIC: Final[str] = "EVENT_TS_NOT_MONOTONIC"
RC_EVENT_MISSING_FIELD: Final[str] = "EVENT_MISSING_FIELD"
RC_EVENT_BAD_TYPE: Final[str] = "EVENT_BAD_TYPE"
RC_CONTEXT_MALFORMED: Final[str] = "CONTEXT_MALFORMED"
RC_ATTACKER_CAPABILITY_EXCEEDED: Final[str] = "ATTACKER_CAPABILITY_EXCEEDED"

# ---------------------------------------------------------------------------
# Event schema constants (leak-safe minimal schema).
# ---------------------------------------------------------------------------
EVENT_KEYS: Final[frozenset[str]] = frozenset({"actor_id", "tool", "scope", "allowed", "ts"})

REASON_CODE_LEAK_KEYS: Final[frozenset[str]] = frozenset(
    {"reason_code", "reject_reason", "denial_reason", "rejection_code", "why"}
)

PRIVILEGED_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "server_signature",
        "audit_log_id",
        "internal_status",
        "oracle_truth",
        "tampered_by_attacker",
        "backend_tamper_flag",
    }
)


# ---------------------------------------------------------------------------
# Exceptions.
# ---------------------------------------------------------------------------
class EvasionError(ValueError):
    """Base error for evasion generation and evaluation failures."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


class PrivilegedTamperingError(EvasionError):
    """Refusal of privileged attacker assumptions (e.g. backend log tampering)."""


# ---------------------------------------------------------------------------
# Typed Data Models.
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class EvasionConfig:
    """Configurable parameters for evasion transformations.

    All parameters are positive and explicit; no environment reads.
    """

    pacing_delay_seconds: int = 1800
    interleave_ratio: int = 3
    interleave_tools: tuple[str, ...] = ("med_schedule_read", "vitals_read", "config_read")
    interleave_scope: str = "self_care"
    min_campaign_span_seconds: int = 7200
    scramble_key_order: tuple[str, ...] = ("ts", "allowed", "scope", "actor_id", "tool")

    def __post_init__(self) -> None:
        if self.pacing_delay_seconds <= 0:
            raise EvasionError(RC_CONTEXT_MALFORMED, "pacing_delay_seconds must be positive")
        if self.interleave_ratio <= 0:
            raise EvasionError(RC_CONTEXT_MALFORMED, "interleave_ratio must be positive")
        if not self.interleave_tools:
            raise EvasionError(RC_CONTEXT_MALFORMED, "interleave_tools must be non-empty")
        if self.min_campaign_span_seconds <= 0:
            raise EvasionError(RC_CONTEXT_MALFORMED, "min_campaign_span_seconds must be positive")


DEFAULT_EVASION_CONFIG = EvasionConfig()


@dataclasses.dataclass(frozen=True)
class EvasiveCampaign:
    """An evasively modified campaign carrying leak-safe observable events.

    The attacker manipulates only observable events emitted by their principal.
    Ground truth and metadata are retained outside the event stream.
    """

    campaign_id: str
    base_campaign_id: str
    strategy: str
    events: tuple[dict[str, Any], ...]
    family: str = "adaptive_probing"
    campaign_label: str = "ATTACK"
    metadata: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.campaign_id:
            raise EvasionError(RC_CONTEXT_MALFORMED, "campaign_id must be non-empty")
        if not self.strategy:
            raise EvasionError(RC_CONTEXT_MALFORMED, "strategy must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "base_campaign_id": self.base_campaign_id,
            "strategy": self.strategy,
            "events": [dict(e) for e in self.events],
            "family": self.family,
            "campaign_label": self.campaign_label,
            "metadata": dict(self.metadata),
        }


@dataclasses.dataclass(frozen=True)
class Metrics:
    """Quantitative evaluation metrics for detector adaptation under evasion.

    Matches exact target contract ``evaluate_adaptation(model, campaigns) -> Metrics``.
    """

    total_campaigns: int
    base_detections: int
    evasive_detections: int
    evasion_success_count: int
    evasion_success_rate: float
    detection_retention_rate: float
    average_score_before: float
    average_score_after: float
    per_strategy: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_campaigns": self.total_campaigns,
            "base_detections": self.base_detections,
            "evasive_detections": self.evasive_detections,
            "evasion_success_count": self.evasion_success_count,
            "evasion_success_rate": round(float(self.evasion_success_rate), 6),
            "detection_retention_rate": round(float(self.detection_retention_rate), 6),
            "average_score_before": round(float(self.average_score_before), 6),
            "average_score_after": round(float(self.average_score_after), 6),
            "per_strategy": dict(self.per_strategy),
        }


@dataclasses.dataclass(frozen=True)
class ArmEvasionResult:
    """Comparative outcome for one detector arm on one campaign under evasion."""

    arm_id: str
    strategy: str
    base_detected: bool
    evasive_detected: bool
    evaded: bool
    base_score: float
    evasive_score: float
    reason_before: str
    reason_after: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm_id": self.arm_id,
            "strategy": self.strategy,
            "base_detected": self.base_detected,
            "evasive_detected": self.evasive_detected,
            "evaded": self.evaded,
            "base_score": round(self.base_score, 6),
            "evasive_score": round(self.evasive_score, 6),
            "reason_before": self.reason_before,
            "reason_after": self.reason_after,
        }


@dataclasses.dataclass(frozen=True)
class CrossArmEvasionReport:
    """Comprehensive evasion evaluation report comparing B0, B1, B2, and candidate."""

    total_cases: int
    results: tuple[ArmEvasionResult, ...]
    summary: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_cases": self.total_cases,
            "results": [r.to_dict() for r in self.results],
            "summary": dict(self.summary),
        }


# ---------------------------------------------------------------------------
# Attacker Boundaries & Validation.
# ---------------------------------------------------------------------------
def refuse_privileged_tampering(action_or_payload: Any) -> None:
    """Refuse privileged attacker assumptions (e.g. backend log tampering).

    The threat model allows the attacker to emit only permitted client-side
    tool requests. An adversary cannot modify signed server logs, overwrite
    audit tables, or forge backend security reason codes.
    """
    if isinstance(action_or_payload, str):
        lowered = action_or_payload.lower()
        if any(
            pattern in lowered
            for pattern in (
                "tamper_log",
                "tamper_backend",
                "overwrite_log",
                "overwrite_server_log",
                "signed_server_log",
                "audit_log",
                "oracle_tamper",
            )
        ):
            raise PrivilegedTamperingError(
                RC_PRIVILEGED_LOG_TAMPERING,
                f"unrealistic attacker action {action_or_payload!r} refused: "
                "attacker cannot tamper with backend logs",
            )
    elif isinstance(action_or_payload, Mapping):
        for key in action_or_payload:
            key_str = str(key)
            if key_str in PRIVILEGED_FIELDS or "tamper" in key_str.lower():
                raise PrivilegedTamperingError(
                    RC_PRIVILEGED_LOG_TAMPERING,
                    f"privileged field {key_str!r} refused: attacker cannot modify server state",
                )


def tamper_backend_logs(action: str = "overwrite_audit_log") -> None:
    """Explicit negative control: simulated attempt to overwrite signed server logs.

    Always raises PrivilegedTamperingError with stable reason code.
    """
    refuse_privileged_tampering(action)
    raise PrivilegedTamperingError(
        RC_PRIVILEGED_LOG_TAMPERING,
        "direct backend log tampering is impossible under the trusted collector model",
    )


def _validate_observable_events(raw_events: Any) -> list[dict[str, Any]]:
    """Validate observable event sequence against leak-safe minimal schema."""
    if not isinstance(raw_events, list | tuple):
        raise EvasionError(RC_INVALID_BASE_CAMPAIGN, "events must be a sequence")
    if not raw_events:
        raise EvasionError(RC_EMPTY_EVENTS, "event sequence cannot be empty")

    validated: list[dict[str, Any]] = []
    actors: set[str] = set()
    prev_ts: int | None = None

    for idx, raw in enumerate(raw_events):
        if not isinstance(raw, Mapping):
            raise EvasionError(RC_INVALID_BASE_CAMPAIGN, f"event {idx} is not an object")

        refuse_privileged_tampering(raw)

        # Check for reason code leak fields (RQ1 masking)
        for key in raw:
            if str(key) in REASON_CODE_LEAK_KEYS:
                raise EvasionError(
                    RC_EVENT_REASON_CODE_FORBIDDEN,
                    f"event {idx} contains forbidden reason code key {key!r}",
                )

        # Normalize actor / actor_id
        actor = raw.get("actor_id", raw.get("actor"))
        if not (isinstance(actor, str) and actor):
            raise EvasionError(RC_EVENT_BAD_TYPE, f"event {idx} actor must be a non-empty string")

        tool = raw.get("tool")
        if not (isinstance(tool, str) and tool):
            raise EvasionError(RC_EVENT_BAD_TYPE, f"event {idx} tool must be a non-empty string")

        scope = raw.get("scope")
        if not (isinstance(scope, str) and scope):
            raise EvasionError(RC_EVENT_BAD_TYPE, f"event {idx} scope must be a non-empty string")

        allowed = raw.get("allowed")
        if not isinstance(allowed, bool):
            raise EvasionError(RC_EVENT_BAD_TYPE, f"event {idx} allowed must be a boolean")

        ts = raw.get("ts")
        if isinstance(ts, bool) or not isinstance(ts, int) or ts < 0:
            raise EvasionError(RC_EVENT_BAD_TYPE, f"event {idx} ts must be a non-negative integer")

        if prev_ts is not None and ts < prev_ts:
            raise EvasionError(
                RC_EVENT_TS_NOT_MONOTONIC,
                f"event {idx} ts={ts} is less than previous ts={prev_ts}",
            )
        prev_ts = ts

        # Check unknown keys outside 5-field schema (except optional 7-field telemetry keys)
        allowed_keys = EVENT_KEYS | {"actor", "purpose", "campaign_id"}
        unknown = [k for k in raw if k not in allowed_keys]
        if unknown:
            raise EvasionError(
                RC_UNPERMITTED_EVENT_FIELD,
                f"event {idx} contains unpermitted keys: {sorted(unknown)}",
            )

        actors.add(actor)
        validated.append(
            {
                "actor_id": actor,
                "tool": tool,
                "scope": scope,
                "allowed": allowed,
                "ts": ts,
            }
        )

    if len(actors) > 1:
        raise EvasionError(
            RC_SESSION_MIXED_ACTORS,
            f"session contains multiple actors {sorted(actors)}; cross-actor tampering refused",
        )

    return validated


# ---------------------------------------------------------------------------
# Evasion Generation Logic.
# ---------------------------------------------------------------------------
def _apply_pacing(events: Sequence[dict[str, Any]], config: EvasionConfig) -> list[dict[str, Any]]:
    """Spread out denied requests across time to evade fixed-window counting.

    Inter-denial delay is stretched by at least ``config.pacing_delay_seconds``,
    ensuring that max denials per 3600 s window drops below the B0 threshold
    while campaign span extends beyond ``config.min_campaign_span_seconds``.
    """
    paced: list[dict[str, Any]] = []
    current_ts = events[0]["ts"]

    for idx, e in enumerate(events):
        ev = dict(e)
        if idx == 0:
            ev["ts"] = current_ts
        else:
            if not e["allowed"]:
                current_ts += config.pacing_delay_seconds
            else:
                current_ts += max(10, config.pacing_delay_seconds // (config.interleave_ratio + 1))
            ev["ts"] = current_ts
        paced.append(ev)

    # Ensure total span reaches min_campaign_span_seconds if needed
    if len(paced) >= 2:
        span = paced[-1]["ts"] - paced[0]["ts"]
        if span < config.min_campaign_span_seconds:
            shortfall = config.min_campaign_span_seconds - span
            step = shortfall // (len(paced) - 1) + 1
            start = paced[0]["ts"]
            for i in range(1, len(paced)):
                paced[i]["ts"] = start + i * (paced[i]["ts"] - paced[i - 1]["ts"] + step)
                start = paced[i]["ts"]

    return paced


def _apply_benign_interleaving(
    events: Sequence[dict[str, Any]], config: EvasionConfig
) -> list[dict[str, Any]]:
    """Pad the event sequence with legitimate, allowed tool requests.

    Dilutes denial ratio and manipulates rate metrics without removing the
    underlying attack denials.
    """
    interleaved: list[dict[str, Any]] = []
    actor_id = events[0]["actor_id"]
    scope = config.interleave_scope
    tool_idx = 0

    for i, e in enumerate(events):
        interleaved.append(dict(e))

        # Insert benign padding requests after each attack event
        ts_base = e["ts"]
        next_ts = events[i + 1]["ts"] if i + 1 < len(events) else ts_base + 300
        time_slot = max(1, (next_ts - ts_base) // (config.interleave_ratio + 1))

        for k in range(config.interleave_ratio):
            benign_tool = config.interleave_tools[tool_idx % len(config.interleave_tools)]
            tool_idx += 1
            pad_ts = min(
                ts_base + (k + 1) * time_slot, next_ts - 1 if next_ts > ts_base else ts_base + 1
            )
            interleaved.append(
                {
                    "actor_id": actor_id,
                    "tool": benign_tool,
                    "scope": scope,
                    "allowed": True,
                    "ts": pad_ts,
                }
            )

    interleaved.sort(key=lambda ev: ev["ts"])
    # Resolve identical timestamps to enforce strict monotonicity
    for i in range(1, len(interleaved)):
        if interleaved[i]["ts"] <= interleaved[i - 1]["ts"]:
            interleaved[i]["ts"] = interleaved[i - 1]["ts"] + 1

    return interleaved


def _apply_field_scrambling(
    events: Sequence[dict[str, Any]], config: EvasionConfig
) -> list[dict[str, Any]]:
    """Reorder serialized dict keys to verify schema permutation invariance."""
    order = config.scramble_key_order
    scrambled: list[dict[str, Any]] = []
    for e in events:
        reordered = {k: e[k] for k in order if k in e}
        # Add any remaining keys
        for k, v in e.items():
            if k not in reordered:
                reordered[k] = v
        scrambled.append(reordered)
    return scrambled


def _apply_missing_optional_fields(
    events: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Project events onto strictly the 5 minimal schema keys."""
    projected: list[dict[str, Any]] = []
    for e in events:
        clean = {k: e[k] for k in EVENT_KEYS if k in e}
        projected.append(clean)
    return projected


def generate_evasive_campaign(
    base_campaign: Mapping[str, Any] | Any,
    strategy: str,
    *,
    config: EvasionConfig | None = None,
) -> EvasiveCampaign:
    """Generate an evasive attack campaign under a specified tactical strategy.

    Parameters
    ----------
    base_campaign:
        A mapping carrying ``case_id`` / ``campaign_id`` and ``events`` list,
        or an object with matching attributes.
    strategy:
        One of ``pacing``, ``benign_interleaving``, ``field_scrambling``,
        ``missing_optional_fields``, ``composite``.
    config:
        Explicit evasion parameters; defaults to :data:`DEFAULT_EVASION_CONFIG`.

    Returns
    -------
    EvasiveCampaign
        Typed evasive campaign containing modified minimal-schema events.

    Raises
    ------
    EvasionError
        On invalid base campaign, unsupported strategy, or malformed events.
    PrivilegedTamperingError
        If privileged actions or backend tampering are attempted.
    """
    refuse_privileged_tampering(strategy)

    if strategy not in SUPPORTED_STRATEGIES:
        raise EvasionError(
            RC_UNKNOWN_STRATEGY,
            f"strategy {strategy!r} not supported; must be one of {sorted(SUPPORTED_STRATEGIES)}",
        )

    conf = config if config is not None else DEFAULT_EVASION_CONFIG
    if not isinstance(conf, EvasionConfig):
        raise EvasionError(RC_CONTEXT_MALFORMED, "config must be EvasionConfig")

    if isinstance(base_campaign, Mapping):
        case_id = str(base_campaign.get("case_id", base_campaign.get("campaign_id", "CAMPAIGN-01")))
        raw_events = base_campaign.get("events")
        family = str(base_campaign.get("family", "adaptive_probing"))
        label = str(base_campaign.get("campaign_label", "ATTACK"))
    else:
        case_id = str(
            getattr(base_campaign, "campaign_id", getattr(base_campaign, "case_id", "CAMPAIGN-01"))
        )
        raw_events = getattr(base_campaign, "events", None)
        family = str(getattr(base_campaign, "family", "adaptive_probing"))
        label = str(getattr(base_campaign, "campaign_label", "ATTACK"))

    refuse_privileged_tampering(case_id)
    validated = _validate_observable_events(raw_events)

    # Apply selected strategy
    if strategy == STRATEGY_PACING:
        modified = _apply_pacing(validated, conf)
    elif strategy == STRATEGY_BENIGN_INTERLEAVING:
        modified = _apply_benign_interleaving(validated, conf)
    elif strategy == STRATEGY_FIELD_SCRAMBLING:
        modified = _apply_field_scrambling(validated, conf)
    elif strategy == STRATEGY_MISSING_OPTIONAL_FIELDS:
        modified = _apply_missing_optional_fields(validated)
    elif strategy == STRATEGY_COMPOSITE:
        paced = _apply_pacing(validated, conf)
        interleaved = _apply_benign_interleaving(paced, conf)
        modified = _apply_field_scrambling(interleaved, conf)
    else:
        raise EvasionError(RC_UNKNOWN_STRATEGY, f"unhandled strategy {strategy}")

    new_id = f"{case_id}-evasive-{strategy}"
    base_dict = {
        "case_id": case_id,
        "campaign_id": case_id,
        "events": [dict(e) for e in validated],
        "family": family,
        "campaign_label": label,
    }

    metadata = {
        "base_campaign": base_dict,
        "base_event_count": len(validated),
        "evasive_event_count": len(modified),
        "base_span_seconds": validated[-1]["ts"] - validated[0]["ts"],
        "evasive_span_seconds": modified[-1]["ts"] - modified[0]["ts"],
        "pacing_delay_seconds": conf.pacing_delay_seconds,
        "interleave_ratio": conf.interleave_ratio,
    }

    return EvasiveCampaign(
        campaign_id=new_id,
        base_campaign_id=case_id,
        strategy=strategy,
        events=tuple(modified),
        family=family,
        campaign_label=label,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Simple Rate Features & Helper Detectors.
# ---------------------------------------------------------------------------
def compute_denial_rate(events: Sequence[Mapping[str, Any]]) -> float:
    """Compute the fraction of requests that were denied."""
    if not events:
        return 0.0
    denials = sum(1 for e in events if not bool(e.get("allowed", True)))
    return denials / len(events)


def evaluate_simple_rate_detector(
    events: Sequence[Mapping[str, Any]], threshold: float = 0.5
) -> dict[str, Any]:
    """Simple rate-based anomaly detector (alarm if denial fraction >= threshold)."""
    rate = compute_denial_rate(events)
    detected = rate >= threshold
    return {
        "detected": detected,
        "decision": "DETECT" if detected else "NO_DETECT",
        "score": rate,
        "threshold": threshold,
        "reason": "HIGH_DENIAL_RATE" if detected else "NORMAL_RATE",
    }


# ---------------------------------------------------------------------------
# Fixed Test Campaign Families.
# ---------------------------------------------------------------------------
def fixed_test_campaign_families() -> dict[str, dict[str, Any]]:
    """Reproducible base attack campaigns for evasion benchmarking."""
    # 1. rapid_denial_burst: 6 denials in 500 s across 6 tools in 1 scope.
    # Caught by B0 (6 denials in 3600s window >= 5).
    rapid_burst_events = [
        baselines.event("actor-adv-01", f"probe_tool_{i:02d}", "self_care", False, 100 + 80 * i)
        for i in range(6)
    ]
    rapid_burst = {
        "case_id": "DIMVA-BASE-RAPID-BURST",
        "family": "burst_probe",
        "campaign_label": "ATTACK",
        "events": rapid_burst_events,
    }

    # 2. cross_tool_probe: 6 denials across 6 tools in self_care.
    cross_tool_events = [
        baselines.event("actor-adv-02", f"tool_audit_{i}", "self_care", False, 200 + 100 * i)
        for i in range(6)
    ]
    cross_tool = {
        "case_id": "DIMVA-BASE-CROSS-TOOL",
        "family": "cross_tool_obfuscation",
        "campaign_label": "ATTACK",
        "events": cross_tool_events,
    }

    # 3. single_scope_probe: 6 denials in single scope self_care.
    # Naturally evades B1 because no cross-scope transition exists.
    single_scope_events = [
        baselines.event("actor-adv-03", f"med_action_{i}", "self_care", False, 500 + 60 * i)
        for i in range(6)
    ]
    single_scope = {
        "case_id": "DIMVA-BASE-SINGLE-SCOPE",
        "family": "single_scope_recon",
        "campaign_label": "ATTACK",
        "events": single_scope_events,
    }

    # 4. low_and_slow_probe: 6 denials already spaced at 1800 s.
    low_slow_events = [
        baselines.event("actor-adv-04", f"probe_tool_{i:02d}", "self_care", False, 1000 + 1800 * i)
        for i in range(6)
    ]
    low_and_slow = {
        "case_id": "DIMVA-BASE-LOW-AND-SLOW",
        "family": "low_and_slow",
        "campaign_label": "ATTACK",
        "events": low_slow_events,
    }

    return {
        "rapid_denial_burst": rapid_burst,
        "cross_tool_probe": cross_tool,
        "single_scope_probe": single_scope,
        "low_and_slow_probe": low_and_slow,
    }


# ---------------------------------------------------------------------------
# Adaptation Evaluation: Target Contract.
# ---------------------------------------------------------------------------
def _extract_score_from_detail(detail: str) -> float:
    match = re.search(r"score=([0-9eE\.\+\-]+)", detail)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return 0.0


def _invoke_detector(
    model: str | Callable[[Any], Any],
    case: Mapping[str, Any],
    ctx: baselines.DetectorContext | None = None,
) -> tuple[bool, float, str]:
    """Execute model on case; returns (detected: bool, score: float, reason: str)."""
    c = ctx if ctx is not None else baselines.DetectorContext()
    events = case.get("events", [])

    if isinstance(model, str):
        arm = model.strip().upper()
        if arm in ("CANDIDATE", "C0", "DIMVA-CANDIDATE"):
            det = candidate.detect(events)
            detected = det.decision == candidate.DETECT
            return detected, float(det.score), det.reason
        if arm in baselines.BASELINE_REGISTRY:
            res = baselines.run_baseline_detection(arm, case, c)
            detected = res.decision == baselines.DETECT
            return detected, float(res.score), res.reason_code
        if arm == "RATE_DETECTOR":
            res_rate = evaluate_simple_rate_detector(events)
            return bool(res_rate["detected"]), float(res_rate["score"]), str(res_rate["reason"])
        raise EvasionError(RC_UNKNOWN_STRATEGY, f"unknown arm name {model!r}")

    if callable(model):
        try:
            raw = model(case)
        except Exception:
            raw = model(events)

        if isinstance(raw, candidate.Detection):
            return raw.decision == candidate.DETECT, float(raw.score), raw.reason
        if isinstance(raw, baselines.DetectionDecision):
            return raw.decision == baselines.DETECT, float(raw.score), raw.reason_code
        if isinstance(raw, Outcome):
            detected = raw.observed_outcome == "REJECT"
            score = _extract_score_from_detail(raw.detail)
            return detected, score, raw.detail
        if isinstance(raw, Mapping):
            detected = bool(raw.get("detected", raw.get("decision") in ("DETECT", "REJECT")))
            score = float(raw.get("score", 1.0 if detected else 0.0))
            reason = str(raw.get("reason", raw.get("reason_code", "")))
            return detected, score, reason
        if isinstance(raw, bool):
            return raw, 1.0 if raw else 0.0, "BOOL_VERDICT"

    raise EvasionError(RC_CONTEXT_MALFORMED, f"cannot invoke model of type {type(model)}")


def evaluate_adaptation(
    model: str | Callable[[Any], Any],
    campaigns: Sequence[Mapping[str, Any] | EvasiveCampaign] | Mapping[str, Any],
    *,
    base_campaigns: Sequence[Mapping[str, Any]] | None = None,
    ctx: baselines.DetectorContext | None = None,
) -> Metrics:
    """Evaluate detector adaptation under evasion.

    Exact target contract: ``evaluate_adaptation(model, campaigns) -> Metrics``.

    Parameters
    ----------
    model:
        Detector callable or arm identifier string (``candidate``, ``B0``, ``B1``, ``B2``).
    campaigns:
        Sequence of :class:`EvasiveCampaign` objects or paired cases.
    base_campaigns:
        Optional matching sequence of base unevaded campaigns.
    ctx:
        Injected detector execution context.

    Returns
    -------
    Metrics
        Quantitative evaluation metrics describing evasion impact and retention.
    """
    if isinstance(campaigns, Mapping) and not isinstance(campaigns, EvasiveCampaign):
        campaigns_seq: Sequence[Any] = [campaigns]
    else:
        campaigns_seq = list(campaigns)

    if not campaigns_seq:
        raise EvasionError(RC_EMPTY_EVENTS, "campaigns sequence cannot be empty")

    base_map: dict[str, Mapping[str, Any]] = {}
    if base_campaigns:
        for b in base_campaigns:
            cid = str(b.get("case_id", b.get("campaign_id", "")))
            if cid:
                base_map[cid] = b

    total = len(campaigns_seq)
    base_detected_count = 0
    evasive_detected_count = 0
    evasion_success_count = 0
    scores_before: list[float] = []
    scores_after: list[float] = []
    per_strat: dict[str, dict[str, int]] = {}

    for item in campaigns_seq:
        if isinstance(item, EvasiveCampaign):
            evasive_case = item.to_dict()
            strat = item.strategy
            base_case = item.metadata.get("base_campaign") or base_map.get(item.base_campaign_id)
        elif isinstance(item, Mapping):
            evasive_case = dict(item)
            strat = str(item.get("strategy", "unknown"))
            base_case = item.get("base_campaign") or base_map.get(
                str(item.get("base_campaign_id", ""))
            )
        else:
            raise EvasionError(RC_INVALID_BASE_CAMPAIGN, f"unsupported campaign item {type(item)}")

        if base_case is None:
            # If no explicit base case provided, use evasive case itself as identity baseline
            base_case = evasive_case

        base_det, base_sc, _ = _invoke_detector(model, base_case, ctx)
        evasive_det, evasive_sc, _ = _invoke_detector(model, evasive_case, ctx)

        scores_before.append(base_sc)
        scores_after.append(evasive_sc)

        if base_det:
            base_detected_count += 1
        if evasive_det:
            evasive_detected_count += 1
        if base_det and not evasive_det:
            evasion_success_count += 1

        if strat not in per_strat:
            per_strat[strat] = {"total": 0, "base_detected": 0, "evasive_detected": 0, "evaded": 0}
        per_strat[strat]["total"] += 1
        if base_det:
            per_strat[strat]["base_detected"] += 1
        if evasive_det:
            per_strat[strat]["evasive_detected"] += 1
        if base_det and not evasive_det:
            per_strat[strat]["evaded"] += 1

    evasion_rate = (
        evasion_success_count / max(1, base_detected_count) if base_detected_count > 0 else 0.0
    )
    retention_rate = (
        evasive_detected_count / max(1, base_detected_count) if base_detected_count > 0 else 1.0
    )
    avg_before = sum(scores_before) / len(scores_before) if scores_before else 0.0
    avg_after = sum(scores_after) / len(scores_after) if scores_after else 0.0

    return Metrics(
        total_campaigns=total,
        base_detections=base_detected_count,
        evasive_detections=evasive_detected_count,
        evasion_success_count=evasion_success_count,
        evasion_success_rate=evasion_rate,
        detection_retention_rate=retention_rate,
        average_score_before=avg_before,
        average_score_after=avg_after,
        per_strategy=per_strat,
    )


# ---------------------------------------------------------------------------
# Cross-Arm Evasion Impact Evaluation (B0, B1, B2, Candidate).
# ---------------------------------------------------------------------------
def evaluate_arms_evasion(
    base_campaigns: Sequence[Mapping[str, Any]] | None = None,
    strategies: Sequence[str] | None = None,
    ctx: baselines.DetectorContext | None = None,
) -> CrossArmEvasionReport:
    """Evaluate evasion impact across B0, B1, B2, and the candidate detector.

    Demonstrates:
    - Pacing evades B0 (window count) while candidate maintains detection;
    - Benign interleaving evades simple rates;
    - Candidate maintains structural detection across all permitted evasion axes.
    """
    if base_campaigns is None:
        families = fixed_test_campaign_families()
        base_campaigns = list(families.values())

    eval_strategies = (
        strategies
        if strategies is not None
        else (
            STRATEGY_PACING,
            STRATEGY_BENIGN_INTERLEAVING,
            STRATEGY_FIELD_SCRAMBLING,
            STRATEGY_COMPOSITE,
        )
    )

    arms = (
        baselines.BASELINE_B0,
        baselines.BASELINE_B1,
        baselines.BASELINE_B2,
        "candidate",
    )

    c = ctx if ctx is not None else baselines.DetectorContext()
    results: list[ArmEvasionResult] = []
    summary_by_arm: dict[str, dict[str, Any]] = {
        arm: {"total": 0, "evaded": 0, "detected_base": 0, "detected_evasive": 0} for arm in arms
    }

    for base_case in base_campaigns:
        for strat in eval_strategies:
            evasive_camp = generate_evasive_campaign(base_case, strat)
            evasive_case = evasive_camp.to_dict()

            for arm in arms:
                base_det, base_sc, r_before = _invoke_detector(arm, base_case, c)
                evasive_det, evasive_sc, r_after = _invoke_detector(arm, evasive_case, c)

                evaded = base_det and not evasive_det

                summary_by_arm[arm]["total"] += 1
                if base_det:
                    summary_by_arm[arm]["detected_base"] += 1
                if evasive_det:
                    summary_by_arm[arm]["detected_evasive"] += 1
                if evaded:
                    summary_by_arm[arm]["evaded"] += 1

                results.append(
                    ArmEvasionResult(
                        arm_id=arm,
                        strategy=strat,
                        base_detected=base_det,
                        evasive_detected=evasive_det,
                        evaded=evaded,
                        base_score=base_sc,
                        evasive_score=evasive_sc,
                        reason_before=r_before,
                        reason_after=r_after,
                    )
                )

    return CrossArmEvasionReport(
        total_cases=len(results),
        results=tuple(results),
        summary=summary_by_arm,
    )
