"""DIMVA baseline fidelity adapters (task DIMVA-baselines, phase P03).

Purpose
-------
In-process reference implementations of the strong-baseline arms for the
DIMVA 2027 study "GovernanceTrace: Detecting Adaptive Authorization-Boundary
Probing from Minimal Agent Events"
(``research/venue2027/VENUES/dimva/RESEARCH_BLUEPRINT.md``, task contract
``research/venue2027/VENUES/dimva/TASKS/DIMVA-baselines.md``). Each arm
consumes a *sequence of minimal, leak-safe agent events* — ``(actor_id,
tool, scope, allowed, ts)`` in monotonic logical time, no raw content, no
rejection reason codes — and returns a detection decision plus an arm-local
evidence score:

- ``B0`` denied-request-count threshold: static operational baseline; alarm
  when the denied count in any sliding fixed-width window reaches the tuned
  threshold. Structurally blind to order, pacing and linkage: a low-and-slow
  campaign paced under the window produces the same per-window count as
  benign retry bursts (RQ1 falsification arm).
- ``B1`` static rule detection (cross-scope denial): deterministic
  finite-state-style signature with no learned parameters; alarm when a
  denied request in one scope is followed by requests in a *different* scope
  (purpose hopping). Blind to same-scope campaigns and to tool renames.
- ``B2`` statistical anomaly detector: z-score of leak-safe event-rate
  features (denied count, distinct tools, distinct scopes) against a frozen
  injected benign-population reference; alarm when the worst |z| reaches the
  threshold. Unsupervised comparator; sees rates, never campaign intent.
- ``B3`` candidate adaptive probing detection (campaign-level): links the
  whole session into one campaign and alarms only when ALL structural
  criteria hold — enough total denials, denials spread across enough
  distinct tools (cross-tool obfuscation / tool-rename evasion), long
  campaign span (low-and-slow horizon), per-window denied count still under
  the B0 operating point (pacing evades fixed-window counting) and activity
  continuity (one campaign, not disconnected one-offs). B3 is the arm that
  must detect the low-and-slow cross-tool campaign that B0 and B1 both miss.
- ``B2_ISOLATION_FOREST`` / ``B3_GBT`` — the pinned scikit-learn 1.8.0
  registry arms (``isolation-forest-privacy-minimized``,
  ``gradient-boosted-trees-controlled-features``). Their pinned parity
  fixtures (``evaluation/venue2027/dimva/fixtures/*.json``) and pinned
  configs are absent from this worktree, so they return ``NOT_RUN_EXTERNAL``
  with reason code ``BASELINE_UNAVAILABLE`` per execution contract rule 8
  (never replaced by a toy under the pinned name).

Allowed input
-------------
A JSON-serializable ``case`` mapping ``{"case_id": str, "events": [event,
...]}`` where each event is a mapping with exactly the five minimal-schema
keys ``actor_id`` (str), ``tool`` (str), ``scope`` (str), ``allowed`` (bool)
and ``ts`` (non-negative int, non-decreasing across the sequence). One case
is one session/campaign: exactly one ``actor_id`` is permitted. Any extra
event key fails closed — a ``reason_code``-like key is refused as a leak-safe
violation (RQ1 masking contract). Detector parameters and the frozen B2
reference statistics live on the injected :class:`DetectorContext`; no
hidden clock, no randomness, no network, no live provider, no real PHI/PII.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes. ``run_baseline`` returns a
first-class harness :class:`Outcome`: ``REJECT`` (detection alarm) /
``ADMIT`` (no alarm) carry ``counted_as_success=True``; malformed input
yields ``INDETERMINATE`` (never silently a safe rejection); the pinned
external arms yield ``NOT_RUN_EXTERNAL`` (never counted as a completion).
Unknown baseline ids, non-mapping cases and malformed contexts are wiring
errors raised as :class:`BaselineError`. ``precision_recall_auc`` computes a
real average-precision AUCPR and *refuses* tiny samples
(``AUC_SAMPLE_TOO_SMALL``), degenerate label sets, non-finite scores and
length mismatches rather than returning an unreliable number.
``refuse_constant_stub`` replays paired benign/attack probe sessions through
any candidate adapter and refuses detect-all / detect-none / constant-output
stubs with ``STUB_DETECT_ALL_REFUSED`` / ``STUB_DETECT_NONE_REFUSED`` /
``CONSTANT_STUB_REFUSED`` (EXECUTION_CONTRACT rule 8: no toy wearing a
baseline name).

Version
-------
``BASELINES_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from evaluation.venue2027._shared.harness import Outcome

BASELINES_VERSION = "1.0.0"

#: Blueprint / task-contract arm ids.
BASELINE_B0 = "B0"
BASELINE_B1 = "B1"
BASELINE_B2 = "B2"
BASELINE_B3 = "B3"

#: Pinned external scikit-learn arms (registry ORIGINAL_UPSTREAM rows).
BASELINE_B2_ISOLATION_FOREST = "B2_ISOLATION_FOREST"
BASELINE_B3_GBT = "B3_GBT"

#: Registry name -> arm id (mirrors research/venue2027/_shared/baselines/registry.yaml).
REGISTRY_BASELINE_NAMES: Mapping[str, str] = {
    "static-threshold-denied-per-window": BASELINE_B0,
    "temporal-rule-sequence-signature": BASELINE_B1,
    "statistical-zscore-event-rate": BASELINE_B2,
    "campaign-linkage-adaptive-probing": BASELINE_B3,
    "isolation-forest-privacy-minimized": BASELINE_B2_ISOLATION_FOREST,
    "gradient-boosted-trees-controlled-features": BASELINE_B3_GBT,
}

#: Baselines whose pinned upstream + parity fixture are not runnable in this
#: in-process module; they stay NOT_RUN_EXTERNAL (never a toy, rule 8).
EXTERNAL_PINNED_BASELINES: frozenset[str] = frozenset(
    {BASELINE_B2_ISOLATION_FOREST, BASELINE_B3_GBT}
)

# ---------------------------------------------------------------------------
# Stable reason codes (uppercase, machine-checkable).
# ---------------------------------------------------------------------------
RC_NO_ALARM = "NO_ALARM"
RC_B0_THRESHOLD_EXCEEDED = "DENIED_COUNT_THRESHOLD_EXCEEDED"
RC_B1_CROSS_SCOPE_RULE = "CROSS_SCOPE_DENIAL_RULE"
RC_B2_ZSCORE_ANOMALY = "EVENT_RATE_ZSCORE_ANOMALY"
RC_B3_CAMPAIGN_LINKAGE = "CAMPAIGN_LINKAGE_PROBING"
RC_BASELINE_UNAVAILABLE = "BASELINE_UNAVAILABLE"
RC_CASE_EVENTS_MISSING = "CASE_EVENTS_MISSING"
RC_CASE_EVENTS_NOT_A_LIST = "CASE_EVENTS_NOT_A_LIST"
RC_EVENT_SEQUENCE_EMPTY = "EVENT_SEQUENCE_EMPTY"
RC_EVENT_NOT_AN_OBJECT = "EVENT_NOT_AN_OBJECT"
RC_EVENT_MISSING_FIELD = "EVENT_MISSING_FIELD"
RC_EVENT_BAD_TYPE = "EVENT_BAD_TYPE"
RC_EVENT_UNKNOWN_FIELD = "EVENT_UNKNOWN_FIELD"
RC_EVENT_REASON_CODE_FORBIDDEN = "EVENT_REASON_CODE_FIELD_FORBIDDEN"
RC_EVENT_TS_NOT_MONOTONIC = "EVENT_TS_NOT_MONOTONIC"
RC_SESSION_MIXED_ACTORS = "SESSION_MIXED_ACTORS"
RC_REFERENCE_STATS_MISSING = "REFERENCE_STATS_MISSING"
RC_STUB_DETECT_ALL = "STUB_DETECT_ALL_REFUSED"
RC_STUB_DETECT_NONE = "STUB_DETECT_NONE_REFUSED"
RC_STUB_CONSTANT = "CONSTANT_STUB_REFUSED"
RC_STUB_RESULT_UNPARSEABLE = "STUB_RESULT_UNPARSEABLE"
RC_STUB_SEPARATION_OK = "STUB_SEPARATION_OK"
RC_CONTEXT_MALFORMED = "CONTEXT_MALFORMED"
RC_AUC_SAMPLE_TOO_SMALL = "AUC_SAMPLE_TOO_SMALL"
RC_AUC_LENGTH_MISMATCH = "AUC_LENGTH_MISMATCH"
RC_AUC_DEGENERATE_LABELS = "AUC_DEGENERATE_LABELS"
RC_AUC_SCORE_NOT_FINITE = "AUC_SCORE_NOT_FINITE"
RC_AUC_SCORE_NOT_NUMERIC = "AUC_SCORE_NOT_NUMERIC"
RC_AUC_LABEL_NOT_BINARY = "AUC_LABEL_NOT_BINARY"

#: Detection decision values (DetectionDecision.decision).
DETECT = "DETECT"
NO_DETECT = "NO_DETECT"
INDETERMINATE = "INDETERMINATE"

#: Minimum number of labelled cases before an AUCPR is considered reliable.
#: Below this floor the metric is refused instead of returned (tiny-sample
#: precision-recall estimates are unstable and invite over-claiming).
MIN_AUC_SAMPLE_SIZE = 30

#: The five minimal-schema event keys (leak-safe primary surface).
EVENT_KEYS: frozenset[str] = frozenset({"actor_id", "tool", "scope", "allowed", "ts"})

#: Keys whose presence constitutes rejection-reason leakage (RQ1 masking).
REASON_CODE_LEAK_KEYS: frozenset[str] = frozenset(
    {"reason_code", "reject_reason", "denial_reason", "rejection_code", "why"}
)


class BaselineError(ValueError):
    """Wiring/configuration error carrying a stable reason code (not an arm outcome)."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


class MetricError(ValueError):
    """Metric-refusal error carrying a stable reason code (AUC discipline)."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class RateReference:
    """Frozen benign-population reference statistics for the B2 z-score arm.

    Injected, never fitted on the evaluated case (no hidden randomness, no
    label leakage). ``std`` values must be strictly positive.
    """

    denied_count_mean: float
    denied_count_std: float
    distinct_tools_mean: float
    distinct_tools_std: float
    distinct_scopes_mean: float
    distinct_scopes_std: float

    def __post_init__(self) -> None:
        for name in ("denied_count", "distinct_tools", "distinct_scopes"):
            mean = getattr(self, f"{name}_mean")
            std = getattr(self, f"{name}_std")
            if (
                not isinstance(mean, int | float)
                or isinstance(mean, bool)
                or not math.isfinite(float(mean))
            ):
                raise BaselineError(RC_CONTEXT_MALFORMED, f"{name}_mean must be a finite number")
            if (
                not isinstance(std, int | float)
                or isinstance(std, bool)
                or not math.isfinite(float(std))
                or float(std) <= 0.0
            ):
                raise BaselineError(RC_CONTEXT_MALFORMED, f"{name}_std must be a finite number > 0")

    def z(self, feature: str, value: float) -> float:
        mean = getattr(self, f"{feature}_mean")
        std = getattr(self, f"{feature}_std")
        return (float(value) - float(mean)) / float(std)


#: Frozen synthetic benign-population reference (module default for ctx;
#: documented constants, not fitted on evaluated cases).
DEFAULT_RATE_REFERENCE = RateReference(
    denied_count_mean=1.5,
    denied_count_std=1.0,
    distinct_tools_mean=2.5,
    distinct_tools_std=1.2,
    distinct_scopes_mean=1.4,
    distinct_scopes_std=0.5,
)


@dataclasses.dataclass
class DetectorContext:
    """Injected execution context for one detector invocation.

    Carries the harness binding (``arm_id``, ``seed``, ``source_commit``,
    ``deadline_seconds``) plus the frozen per-arm operating points. All
    thresholds are explicit; nothing is read from the environment.

    ``upstream_available`` — whether the pinned external binaries + parity
    fixtures are wired for the external arms; ``False`` (the default) yields
    ``NOT_RUN_EXTERNAL`` for ``B2_ISOLATION_FOREST`` / ``B3_GBT``.
    """

    arm_id: str = ""
    seed: int = 0
    source_commit: str = ""
    deadline_seconds: float = 60.0
    b0_window_seconds: int = 3600
    b0_denied_threshold: int = 5
    b1_horizon_seconds: int = 86400
    b2_z_threshold: float = 3.0
    b2_reference: RateReference | None = DEFAULT_RATE_REFERENCE
    b3_min_denials: int = 5
    b3_min_distinct_tools: int = 3
    b3_min_span_seconds: int = 7200
    b3_max_gap_seconds: int = 7200
    upstream_available: bool = False

    def __post_init__(self) -> None:
        for name in (
            "b0_window_seconds",
            "b0_denied_threshold",
            "b1_horizon_seconds",
            "b3_min_denials",
            "b3_min_distinct_tools",
            "b3_min_span_seconds",
            "b3_max_gap_seconds",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise BaselineError(RC_CONTEXT_MALFORMED, f"{name} must be a positive int")
        for name in ("b2_z_threshold", "deadline_seconds"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
                raise BaselineError(RC_CONTEXT_MALFORMED, f"{name} must be a positive number")
        if self.b2_reference is not None and not isinstance(self.b2_reference, RateReference):
            raise BaselineError(RC_CONTEXT_MALFORMED, "b2_reference must be a RateReference")

    @classmethod
    def from_run_context(cls, run_ctx: Any, **overrides: Any) -> DetectorContext:
        """Build a context from a harness ``RunContext``-shaped object."""
        base = {
            "arm_id": str(getattr(run_ctx, "arm_id", "")),
            "seed": int(getattr(run_ctx, "seed", 0)),
            "source_commit": str(getattr(run_ctx, "source_commit", "")),
            "deadline_seconds": float(getattr(run_ctx, "deadline_seconds", 60.0)),
        }
        base.update(overrides)
        return cls(**base)


@dataclasses.dataclass(frozen=True)
class MinimalEvent:
    """One validated minimal-schema event (leak-safe, JSON-serializable)."""

    actor_id: str
    tool: str
    scope: str
    allowed: bool
    ts: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "tool": self.tool,
            "scope": self.scope,
            "allowed": self.allowed,
            "ts": self.ts,
        }


@dataclasses.dataclass(frozen=True)
class DetectionDecision:
    """Typed detection result for one case under one arm.

    ``score`` is an arm-local, monotone evidence magnitude (higher = more
    attack-like); it is NOT a calibrated probability. ``evidence`` carries
    the structural counts behind the decision (JSON-serializable).
    """

    baseline_id: str
    decision: str
    score: float
    reason_code: str
    evidence: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.decision not in (DETECT, NO_DETECT, INDETERMINATE):
            raise BaselineError(
                RC_CONTEXT_MALFORMED,
                f"decision {self.decision!r} not in DETECT/NO_DETECT/INDETERMINATE",
            )
        if not math.isfinite(float(self.score)):
            raise BaselineError(RC_CONTEXT_MALFORMED, "score must be finite")

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_id": self.baseline_id,
            "decision": self.decision,
            "score": float(self.score),
            "reason_code": self.reason_code,
            "evidence": dict(self.evidence),
        }


def event(actor_id: str, tool: str, scope: str, allowed: bool, ts: int) -> dict[str, Any]:
    """Build one minimal-schema event dict (fixture/test helper, no defaults hidden)."""
    return {
        "actor_id": actor_id,
        "tool": tool,
        "scope": scope,
        "allowed": allowed,
        "ts": ts,
    }


# ---------------------------------------------------------------------------
# Event validation — fail closed to INDETERMINATE, never to a safe rejection.
# ---------------------------------------------------------------------------


def _indeterminate(reason_code: str) -> DetectionDecision:
    return DetectionDecision(
        baseline_id="",
        decision=INDETERMINATE,
        score=0.0,
        reason_code=reason_code,
        evidence={},
    )


def _validate_events(case: Mapping[str, Any]) -> list[MinimalEvent] | DetectionDecision:
    """Validate the case's event sequence; return events or an INDETERMINATE decision."""
    if "events" not in case:
        return _indeterminate(RC_CASE_EVENTS_MISSING)
    raw_events = case["events"]
    if not isinstance(raw_events, list):
        return _indeterminate(RC_CASE_EVENTS_NOT_A_LIST)
    if not raw_events:
        return _indeterminate(RC_EVENT_SEQUENCE_EMPTY)

    events: list[MinimalEvent] = []
    actors: set[str] = set()
    previous_ts: int | None = None
    for raw in raw_events:
        if not isinstance(raw, Mapping):
            return _indeterminate(RC_EVENT_NOT_AN_OBJECT)
        unknown = [str(key) for key in raw if key not in EVENT_KEYS]
        leak = [key for key in unknown if key in REASON_CODE_LEAK_KEYS]
        if leak:
            # Leak-safe masking contract (RQ1): rejection reason codes never
            # reach the detector surface.
            return _indeterminate(RC_EVENT_REASON_CODE_FORBIDDEN)
        if unknown:
            return _indeterminate(RC_EVENT_UNKNOWN_FIELD)
        missing = [key for key in EVENT_KEYS if key not in raw]
        if missing:
            return _indeterminate(RC_EVENT_MISSING_FIELD)
        actor_id = raw["actor_id"]
        tool = raw["tool"]
        scope = raw["scope"]
        allowed = raw["allowed"]
        ts = raw["ts"]
        if not (isinstance(actor_id, str) and actor_id):
            return _indeterminate(RC_EVENT_BAD_TYPE)
        if not (isinstance(tool, str) and tool):
            return _indeterminate(RC_EVENT_BAD_TYPE)
        if not (isinstance(scope, str) and scope):
            return _indeterminate(RC_EVENT_BAD_TYPE)
        if not isinstance(allowed, bool):
            return _indeterminate(RC_EVENT_BAD_TYPE)
        if isinstance(ts, bool) or not isinstance(ts, int) or ts < 0:
            return _indeterminate(RC_EVENT_BAD_TYPE)
        if previous_ts is not None and ts < previous_ts:
            return _indeterminate(RC_EVENT_TS_NOT_MONOTONIC)
        previous_ts = ts
        actors.add(actor_id)
        events.append(
            MinimalEvent(actor_id=actor_id, tool=tool, scope=scope, allowed=allowed, ts=ts)
        )
    if len(actors) > 1:
        # The scientific unit is one session/campaign for one principal.
        return _indeterminate(RC_SESSION_MIXED_ACTORS)
    return events


# ---------------------------------------------------------------------------
# Shared window statistics (equal budget across arms).
# ---------------------------------------------------------------------------


def _denied_timestamps(events: Sequence[MinimalEvent]) -> list[int]:
    return [e.ts for e in events if not e.allowed]


def _max_denials_in_window(denied_ts: Sequence[int], window_seconds: int) -> int:
    """Max number of denials inside any sliding window of ``window_seconds``."""
    if not denied_ts:
        return 0
    best = 0
    left = 0
    for right, ts_r in enumerate(denied_ts):
        while ts_r - denied_ts[left] >= window_seconds:
            left += 1
        best = max(best, right - left + 1)
    return best


def _max_inter_arrival(denied_ts: Sequence[int]) -> int:
    if len(denied_ts) < 2:
        return 0
    return max(b - a for a, b in zip(denied_ts, denied_ts[1:]))


def _span_seconds(events: Sequence[MinimalEvent]) -> int:
    if not events:
        return 0
    return events[-1].ts - events[0].ts


# ---------------------------------------------------------------------------
# B0 — static threshold on denied-request counts per sliding window.
# ---------------------------------------------------------------------------


def _evaluate_b0(events: Sequence[MinimalEvent], ctx: DetectorContext) -> DetectionDecision:
    denied_ts = _denied_timestamps(events)
    max_window = _max_denials_in_window(denied_ts, ctx.b0_window_seconds)
    threshold = ctx.b0_denied_threshold
    evidence = {
        "max_window_denials": max_window,
        "window_seconds": ctx.b0_window_seconds,
        "threshold": threshold,
        "total_denials": len(denied_ts),
    }
    if max_window >= threshold:
        return DetectionDecision(
            baseline_id=BASELINE_B0,
            decision=DETECT,
            score=max_window / threshold,
            reason_code=RC_B0_THRESHOLD_EXCEEDED,
            evidence=evidence,
        )
    return DetectionDecision(
        baseline_id=BASELINE_B0,
        decision=NO_DETECT,
        score=max_window / threshold,
        reason_code=RC_NO_ALARM,
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# B1 — static rule detection: cross-scope denial signature (no learned params).
# ---------------------------------------------------------------------------


def _evaluate_b1(events: Sequence[MinimalEvent], ctx: DetectorContext) -> DetectionDecision:
    followups = 0
    total_denials = 0
    denials: list[MinimalEvent] = []
    for e in events:
        if not e.allowed:
            total_denials += 1
            denials.append(e)
            continue
        if any(e.scope != d.scope and 0 <= e.ts - d.ts <= ctx.b1_horizon_seconds for d in denials):
            followups += 1
    # A denial may itself probe another scope after an earlier denial.
    for e in denials:
        if any(e.scope != d.scope and 0 < e.ts - d.ts <= ctx.b1_horizon_seconds for d in denials):
            followups += 1
    evidence = {
        "cross_scope_followups": followups,
        "total_denials": total_denials,
        "horizon_seconds": ctx.b1_horizon_seconds,
    }
    score = min(1.0, followups / max(1, total_denials))
    if followups >= 1:
        return DetectionDecision(
            baseline_id=BASELINE_B1,
            decision=DETECT,
            score=score,
            reason_code=RC_B1_CROSS_SCOPE_RULE,
            evidence=evidence,
        )
    return DetectionDecision(
        baseline_id=BASELINE_B1,
        decision=NO_DETECT,
        score=score,
        reason_code=RC_NO_ALARM,
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# B2 — statistical anomaly detector: z-score over leak-safe rate features.
# ---------------------------------------------------------------------------


def _evaluate_b2(events: Sequence[MinimalEvent], ctx: DetectorContext) -> DetectionDecision:
    if ctx.b2_reference is None:
        return _indeterminate(RC_REFERENCE_STATS_MISSING)
    reference = ctx.b2_reference
    denied_count = sum(1 for e in events if not e.allowed)
    distinct_tools = len({e.tool for e in events})
    distinct_scopes = len({e.scope for e in events})
    values = {
        "denied_count": float(denied_count),
        "distinct_tools": float(distinct_tools),
        "distinct_scopes": float(distinct_scopes),
    }
    zscores = {name: reference.z(name, value) for name, value in values.items()}
    worst_feature = max(zscores, key=lambda name: (zscores[name], name))
    worst_z = zscores[worst_feature]
    evidence: dict[str, Any] = {
        "max_z": worst_z,
        "worst_feature": worst_feature,
        "z_threshold": ctx.b2_z_threshold,
        "zscores": {name: round(z, 6) for name, z in zscores.items()},
    }
    if worst_z >= ctx.b2_z_threshold:
        return DetectionDecision(
            baseline_id=BASELINE_B2,
            decision=DETECT,
            score=worst_z,
            reason_code=RC_B2_ZSCORE_ANOMALY,
            evidence=evidence,
        )
    return DetectionDecision(
        baseline_id=BASELINE_B2,
        decision=NO_DETECT,
        score=worst_z,
        reason_code=RC_NO_ALARM,
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# B3 — candidate campaign-level adaptive probing detection.
# ---------------------------------------------------------------------------


def _evaluate_b3(events: Sequence[MinimalEvent], ctx: DetectorContext) -> DetectionDecision:
    denied_ts = _denied_timestamps(events)
    denied_tools = {e.tool for e in events if not e.allowed}
    total_denials = len(denied_ts)
    distinct_denied_tools = len(denied_tools)
    span = _span_seconds(events)
    max_window = _max_denials_in_window(denied_ts, ctx.b0_window_seconds)
    max_gap = _max_inter_arrival(denied_ts)

    criteria = {
        "enough_denials": total_denials >= ctx.b3_min_denials,
        "cross_tool_obfuscation": distinct_denied_tools >= ctx.b3_min_distinct_tools,
        "long_horizon_span": span >= ctx.b3_min_span_seconds,
        "evades_fixed_window": max_window < ctx.b0_denied_threshold,
        "activity_continuity": max_gap <= ctx.b3_max_gap_seconds,
    }
    met = sum(1 for ok in criteria.values() if ok)
    score = met / len(criteria)
    evidence: dict[str, Any] = {
        "total_denials": total_denials,
        "distinct_denied_tools": distinct_denied_tools,
        "span_seconds": span,
        "max_window_denials": max_window,
        "max_gap_seconds": max_gap,
        "criteria": {name: bool(ok) for name, ok in criteria.items()},
        "criteria_met": met,
        "criteria_total": len(criteria),
    }
    if all(criteria.values()):
        return DetectionDecision(
            baseline_id=BASELINE_B3,
            decision=DETECT,
            score=score,
            reason_code=RC_B3_CAMPAIGN_LINKAGE,
            evidence=evidence,
        )
    return DetectionDecision(
        baseline_id=BASELINE_B3,
        decision=NO_DETECT,
        score=score,
        reason_code=RC_NO_ALARM,
        evidence=evidence,
    )


_EVALUATORS: Mapping[
    str, Callable[[Sequence[MinimalEvent], DetectorContext], DetectionDecision]
] = {
    BASELINE_B0: _evaluate_b0,
    BASELINE_B1: _evaluate_b1,
    BASELINE_B2: _evaluate_b2,
    BASELINE_B3: _evaluate_b3,
}


# ---------------------------------------------------------------------------
# Registry + dispatch.
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class BaselineSpec:
    """Registry row: provenance + runnability for one baseline arm."""

    baseline_id: str
    registry_name: str
    title: str
    algorithm_class: str
    runnable_in_process: bool
    upstream_url: str
    upstream_revision: str
    notes: str


BASELINE_REGISTRY: Mapping[str, BaselineSpec] = {
    spec.baseline_id: spec
    for spec in (
        BaselineSpec(
            baseline_id=BASELINE_B0,
            registry_name="static-threshold-denied-per-window",
            title="Static threshold on denied-request counts per sliding window",
            algorithm_class="counting detector over a fixed-width sliding window",
            runnable_in_process=True,
            upstream_url="https://github.com/Project-CLARA-HBT/CLARA-Care",
            upstream_revision="UNAVAILABLE",
            notes=(
                "Blueprint arm B0 (in-project operational baseline); RQ1 falsification "
                "arm: if this matches sequence models on family-held-out traces, no "
                "ML-necessity claim is made."
            ),
        ),
        BaselineSpec(
            baseline_id=BASELINE_B1,
            registry_name="temporal-rule-sequence-signature",
            title="Static rule detection (cross-scope denial signature)",
            algorithm_class="deterministic finite-state-style rule over ordered events; no learned parameters",
            runnable_in_process=True,
            upstream_url="https://github.com/Project-CLARA-HBT/CLARA-Care",
            upstream_revision="UNAVAILABLE",
            notes=(
                "Blueprint arm B1 (in-project interpretable baseline); leak-safe "
                "signature over the minimal event schema; blind to same-scope "
                "low-and-slow campaigns and tool renames."
            ),
        ),
        BaselineSpec(
            baseline_id=BASELINE_B2,
            registry_name="statistical-zscore-event-rate",
            title="Statistical anomaly detector (z-score over event-rate features)",
            algorithm_class="univariate z-score over leak-safe rate features vs frozen injected reference",
            runnable_in_process=True,
            upstream_url="https://github.com/Project-CLARA-HBT/CLARA-Care",
            upstream_revision="UNAVAILABLE",
            notes=(
                "Task-contract in-project statistical comparator (DIMVA-baselines "
                "deliverable). This is NOT the pinned IsolationForest arm: that arm "
                "stays separate below and is never replaced by this detector (rule 8)."
            ),
        ),
        BaselineSpec(
            baseline_id=BASELINE_B3,
            registry_name="campaign-linkage-adaptive-probing",
            title="Candidate adaptive probing detection (campaign-level linkage)",
            algorithm_class=(
                "campaign-level structural linkage: cross-tool obfuscation + low-and-slow "
                "pacing + fixed-window evasion criteria over the whole session"
            ),
            runnable_in_process=True,
            upstream_url="https://github.com/Project-CLARA-HBT/CLARA-Care",
            upstream_revision="UNAVAILABLE",
            notes=(
                "Task-contract candidate arm: must detect the low-and-slow cross-tool "
                "campaign that B0/B1 miss. The learned sequence-model candidate "
                "(blueprint B4) is a separate downstream task, not this arm."
            ),
        ),
        BaselineSpec(
            baseline_id=BASELINE_B2_ISOLATION_FOREST,
            registry_name="isolation-forest-privacy-minimized",
            title="Isolation Forest on privacy-minimized counts (pinned scikit-learn 1.8.0)",
            algorithm_class="unsupervised anomaly detection (sklearn.ensemble.IsolationForest)",
            runnable_in_process=False,
            upstream_url="https://github.com/scikit-learn/scikit-learn",
            upstream_revision="63acddb6de687f685b7323ad68fb2cf76cc3bd1a",
            notes=(
                "Pinned tag 1.8.0 (registry ORIGINAL_UPSTREAM). The registered parity "
                "fixture evaluation/venue2027/dimva/fixtures/isolation_forest_parity.json "
                "and pinned config are absent from this worktree, so the arm is honestly "
                "NOT_RUN_EXTERNAL; never replaced by a toy under the pinned name (rule 8)."
            ),
        ),
        BaselineSpec(
            baseline_id=BASELINE_B3_GBT,
            registry_name="gradient-boosted-trees-controlled-features",
            title="Gradient-boosted trees on controlled leak-safe features (pinned scikit-learn 1.8.0)",
            algorithm_class="supervised gradient-boosted decision trees (HistGradientBoostingClassifier)",
            runnable_in_process=False,
            upstream_url="https://github.com/scikit-learn/scikit-learn",
            upstream_revision="63acddb6de687f685b7323ad68fb2cf76cc3bd1a",
            notes=(
                "Pinned tag 1.8.0 (registry ORIGINAL_UPSTREAM). The registered parity "
                "fixture evaluation/venue2027/dimva/fixtures/gbt_parity.json and pinned "
                "config are absent from this worktree, so the arm is honestly "
                "NOT_RUN_EXTERNAL; never replaced by a toy under the pinned name (rule 8)."
            ),
        ),
    )
}


def run_baseline_detection(
    baseline_id: str, case: Mapping[str, Any], ctx: DetectorContext
) -> DetectionDecision:
    """Execute one detection arm on one case; return the typed decision.

    Wiring errors (unknown arm id, non-mapping case, malformed context) raise
    :class:`BaselineError`; malformed event payloads yield an INDETERMINATE
    :class:`DetectionDecision` with a stable reason code (never silently a
    safe rejection).
    """
    if not isinstance(case, Mapping):
        raise BaselineError("CASE_NOT_AN_OBJECT", f"case must be a mapping, got {type(case)}")
    if not isinstance(ctx, DetectorContext):
        raise BaselineError(RC_CONTEXT_MALFORMED, f"ctx must be a DetectorContext, got {type(ctx)}")
    spec = BASELINE_REGISTRY.get(baseline_id)
    if spec is None:
        known = sorted(BASELINE_REGISTRY)
        raise BaselineError(
            "BASELINE_UNKNOWN_ID", f"baseline_id {baseline_id!r} not in registry {known}"
        )
    if not spec.runnable_in_process or baseline_id in EXTERNAL_PINNED_BASELINES:
        # Handled by run_baseline (outcome-level status); detection has no
        # in-process semantics for the pinned external arms.
        raise BaselineError(
            "BASELINE_EXTERNAL_UNIMPLEMENTED",
            f"{baseline_id} is a pinned external arm; use run_baseline for its "
            "NOT_RUN_EXTERNAL status (rule 8)",
        )
    validated = _validate_events(case)
    if isinstance(validated, DetectionDecision):
        return DetectionDecision(
            baseline_id=baseline_id,
            decision=validated.decision,
            score=validated.score,
            reason_code=validated.reason_code,
            evidence=validated.evidence,
        )
    return _EVALUATORS[baseline_id](validated, ctx)


def run_baseline(baseline_id: str, case: Mapping[str, Any], ctx: DetectorContext) -> Outcome:
    """Execute one baseline arm on one case; returns a first-class harness Outcome.

    Mapping: DETECT -> ``REJECT`` (alarm raised), NO_DETECT -> ``ADMIT``
    (session passes as benign), both ``counted_as_success=True``; malformed
    input -> ``INDETERMINATE`` (never counted); pinned external arms whose
    parity fixtures are absent -> ``NOT_RUN_EXTERNAL`` / ``BASELINE_UNAVAILABLE``
    (never counted, never a toy substitution). The arm-local evidence score is
    carried in ``detail`` as ``"<REASON_CODE>|score=<float>"``; use
    :func:`run_baseline_detection` for the typed decision and evidence.
    """
    if not isinstance(case, Mapping):
        raise BaselineError("CASE_NOT_AN_OBJECT", f"case must be a mapping, got {type(case)}")
    spec = BASELINE_REGISTRY.get(baseline_id)
    if spec is None:
        known = sorted(BASELINE_REGISTRY)
        raise BaselineError(
            "BASELINE_UNKNOWN_ID", f"baseline_id {baseline_id!r} not in registry {known}"
        )
    if not spec.runnable_in_process or baseline_id in EXTERNAL_PINNED_BASELINES:
        if not ctx.upstream_available:
            return Outcome(
                observed_outcome="NOT_RUN_EXTERNAL",
                counted_as_success=False,
                retriable=True,
                detail=RC_BASELINE_UNAVAILABLE,
            )
        raise BaselineError(
            "BASELINE_EXTERNAL_UNIMPLEMENTED",
            f"{baseline_id} external pinned run requires its adapter + parity fixture task",
        )
    decision = run_baseline_detection(baseline_id, case, ctx)
    if decision.decision == INDETERMINATE:
        return Outcome(
            observed_outcome="INDETERMINATE",
            counted_as_success=False,
            retriable=False,
            detail=decision.reason_code,
        )
    detail = f"{decision.reason_code}|score={decision.score:.6f}"
    observed = "REJECT" if decision.decision == DETECT else "ADMIT"
    return Outcome(
        observed_outcome=observed,
        counted_as_success=True,
        retriable=False,
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Metrics — real average-precision AUCPR with tiny-sample refusal.
# ---------------------------------------------------------------------------


def precision_recall_auc(
    detections: Sequence[float | bool | int],
    labels: Sequence[bool | int],
    *,
    min_samples: int = MIN_AUC_SAMPLE_SIZE,
) -> float:
    """Campaign-level precision-recall AUC (average precision) over scored cases.

    ``detections`` are arm-local scores (or boolean decisions); ``labels``
    are independent oracle campaign labels (True = attack campaign). Ties are
    broken by input order for determinism. Refuses to return a number when
    the estimate would be unreliable: fewer than ``min_samples`` labelled
    cases, length mismatch, non-binary labels, non-numeric or non-finite
    scores, or a degenerate all-positive/all-negative label set.
    """
    if len(detections) != len(labels):
        raise MetricError(
            RC_AUC_LENGTH_MISMATCH,
            f"len(detections)={len(detections)} != len(labels)={len(labels)}",
        )
    if min_samples < 1:
        raise MetricError(RC_CONTEXT_MALFORMED, "min_samples must be >= 1")
    n = len(labels)
    if n < min_samples:
        raise MetricError(
            RC_AUC_SAMPLE_TOO_SMALL,
            f"n={n} < min_samples={min_samples}; precision-recall AUC on tiny "
            "samples is unreliable and refused",
        )
    scores: list[float] = []
    for i, raw in enumerate(detections):
        if isinstance(raw, bool):
            value = 1.0 if raw else 0.0
        elif isinstance(raw, int | float):
            value = float(raw)
        else:
            raise MetricError(
                RC_AUC_SCORE_NOT_NUMERIC,
                f"detections[{i}] is {type(raw).__name__}, expected number or bool",
            )
        if not math.isfinite(value):
            raise MetricError(RC_AUC_SCORE_NOT_FINITE, f"detections[{i}]={raw!r} is not finite")
        scores.append(value)
    binary: list[bool] = []
    for i, raw in enumerate(labels):
        if isinstance(raw, bool):
            binary.append(raw)
        elif isinstance(raw, int) and not isinstance(raw, bool) and raw in (0, 1):
            binary.append(bool(raw))
        else:
            raise MetricError(RC_AUC_LABEL_NOT_BINARY, f"labels[{i}]={raw!r} is not binary")
    positives = sum(binary)
    if positives == 0 or positives == n:
        raise MetricError(
            RC_AUC_DEGENERATE_LABELS,
            f"label set is degenerate (positives={positives}, n={n}); AUCPR undefined",
        )
    order = sorted(range(n), key=lambda i: (-scores[i], i))
    average_precision = 0.0
    true_positives = 0
    seen = 0
    recall_step = 1.0 / positives
    for index in order:
        seen += 1
        if binary[index]:
            true_positives += 1
            average_precision += (true_positives / seen) * recall_step
    return average_precision


# ---------------------------------------------------------------------------
# Paired probe fixtures + constant-stub refusal gate (EXECUTION_CONTRACT 8).
# ---------------------------------------------------------------------------


def benign_probe_sessions() -> tuple[dict[str, Any], ...]:
    """Paired clean-control sessions (oracle: BENIGN by construction)."""
    retry = {
        "case_id": "DIMVA-PROBE-BENIGN-RETRY",
        "events": [
            event("actor-clean-01", "med_schedule_read", "self_care", False, 100),
            event("actor-clean-01", "med_schedule_read", "self_care", True, 160),
        ],
    }
    burst_events = [
        event(
            "actor-clean-02",
            "med_schedule_read" if i % 2 == 0 else "vitals_read",
            "self_care",
            i not in (2, 6, 10),
            5000 + 2 * i,
        )
        for i in range(12)
    ]
    burst = {"case_id": "DIMVA-PROBE-BENIGN-BURST", "events": burst_events}
    exploration = {
        "case_id": "DIMVA-PROBE-BENIGN-EXPLORATION",
        "events": [
            event("actor-clean-03", "flag_read", "self_care", True, 100),
            event("actor-clean-03", "tool_list", "care_team", True, 300),
            event("actor-clean-03", "config_read", "self_care", True, 500),
            event("actor-clean-03", "tool_list", "care_team", True, 700),
            event("actor-clean-03", "flag_read", "self_care", True, 900),
        ],
    }
    return (retry, burst, exploration)


def attack_probe_sessions() -> tuple[dict[str, Any], ...]:
    """Paired adversarial-control sessions (oracle: ATTACK by construction)."""
    purpose_hop = {
        "case_id": "DIMVA-PROBE-ATTACK-PURPOSE-HOP",
        "events": [
            event("actor-adv-01", "tool_t1", "self_care", True, 100),
            event("actor-adv-01", "med_read", "self_care", False, 150),
            event("actor-adv-01", "billing_read", "billing", True, 300),
            event("actor-adv-01", "billing_read", "billing", False, 380),
            event("actor-adv-01", "records_export", "research_secondary", True, 500),
            event("actor-adv-01", "records_export", "research_secondary", False, 560),
        ],
    }
    low_slow_events = [
        event("actor-adv-02", f"probe_tool_{i:02d}", "self_care", False, 1000 + 1080 * i)
        for i in range(9)
    ]
    low_slow_events.append(event("actor-adv-02", "med_read", "self_care", True, 1500))
    low_slow_events.sort(key=lambda e: e["ts"])
    low_and_slow = {"case_id": "DIMVA-PROBE-ATTACK-LOW-AND-SLOW", "events": low_slow_events}
    return (purpose_hop, low_and_slow)


def _stub_flag(result: object) -> bool:
    if isinstance(result, Outcome):
        return result.observed_outcome == "REJECT"
    if isinstance(result, DetectionDecision):
        return result.decision == DETECT
    if isinstance(result, bool):
        return result
    if isinstance(result, str):
        return result.strip().upper() in {"DETECT", "REJECT", "TRUE", "1", "ATTACK"}
    raise BaselineError(RC_STUB_RESULT_UNPARSEABLE, f"candidate returned {type(result).__name__}")


def _stub_score(result: object) -> float:
    if isinstance(result, DetectionDecision):
        return float(result.score)
    if isinstance(result, bool):
        return 1.0 if result else 0.0
    if isinstance(result, int | float):
        return float(result)
    return float("nan")


def refuse_constant_stub(
    candidate: Callable[[Mapping[str, Any]], object],
    *,
    benign_probes: Sequence[Mapping[str, Any]] | None = None,
    attack_probes: Sequence[Mapping[str, Any]] | None = None,
) -> Outcome:
    """Refuse detect-all / detect-none / constant-output stubs (rule 8).

    Replays the paired probe sessions through ``candidate`` and refuses:
    - a candidate that flags EVERY probe, including the paired benign clean
      controls (``STUB_DETECT_ALL_REFUSED`` — the detect-all stub);
    - a candidate that flags NO probe at all (``STUB_DETECT_NONE_REFUSED``);
    - a candidate whose (decision, score) output is identical across the whole
      probe union (``CONSTANT_STUB_REFUSED`` — zero input sensitivity).

    Returns ``ADMIT`` / ``STUB_SEPARATION_OK`` when the candidate separates
    the paired controls. A registered weak baseline that legitimately misses
    both attack probes (e.g. B0 on the low-and-slow pacing) should NOT be
    forced through this gate — its miss is the measured RQ1 result, not a
    stub; the gate exists for candidate adapters claiming detection semantics.
    """
    benign = tuple(benign_probes) if benign_probes is not None else benign_probe_sessions()
    attack = tuple(attack_probes) if attack_probes is not None else attack_probe_sessions()
    if not benign or not attack:
        raise BaselineError(RC_CONTEXT_MALFORMED, "probe sets must be non-empty")
    results = [candidate(probe) for probe in (*benign, *attack)]
    flags = [_stub_flag(result) for result in results]
    signatures = [(_stub_flag(result), _stub_score(result)) for result in results]
    if len(set(signatures)) == 1:
        # Zero input sensitivity: identical (decision, score) for every probe.
        raise BaselineError(
            RC_STUB_CONSTANT,
            "candidate returns an identical (decision, score) pair for every probe",
        )
    if all(flags):
        raise BaselineError(
            RC_STUB_DETECT_ALL,
            "candidate flags every probe including paired benign clean controls",
        )
    if not any(flags):
        raise BaselineError(
            RC_STUB_DETECT_NONE, "candidate flags no probe at all (zero discrimination)"
        )
    return Outcome(
        observed_outcome="ADMIT",
        counted_as_success=True,
        retriable=False,
        detail=RC_STUB_SEPARATION_OK,
    )
