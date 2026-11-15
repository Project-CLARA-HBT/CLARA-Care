"""DIMVA-candidate — GovernanceTrace adaptive probing-detection candidate (isolated).

Purpose
-------
Task DIMVA-candidate (Phase P04, venue ``dimva``): the isolated candidate
detector for "GovernanceTrace: Detecting Adaptive Authorization-Boundary
Probing from Minimal Agent Events"
(``research/venue2027/VENUES/dimva/RESEARCH_BLUEPRINT.md``, task contract
``research/venue2027/VENUES/dimva/TASKS/DIMVA-candidate.md``). It reads ONLY
a session's minimal, leak-safe agent events — ``(actor_id, tool, scope,
allowed, ts)`` in monotonic logical time, no raw content, no rejection
reason codes — and decides whether the session carries the campaign-level
STRUCTURE of deliberate multi-step authorization-boundary reconnaissance:

- cross-tool obfuscation: denials spread over many tools, quantified by both
  a distinct-tool count and the normalized Shannon entropy of the denied-tool
  distribution, so tool-rename evasion does not defeat linkage;
- low-and-slow pacing: a long campaign horizon whose maximum per-window
  denial count stays under the static fixed-window operating point — the
  pacing itself evades count-based alarms instead of tripping them;
- activity continuity: bounded inter-denial gaps — one linked campaign, not
  disconnected one-offs.

The decision is a pure function of event structure. The detector never reads
a label, a scenario family, an expected verdict, or a rejection reason code:
any event key beyond the minimal schema fails closed (RQ1 masking contract),
so no post-hoc failure annotation can flow into the score. The module is
deliberately self-contained — it imports nothing from the truth oracle, the
scenario generators, or any detector-arm module — so it can be adjudicated
by the independent oracle and compared against the arms in ``baselines.py``
without circularity (blueprint falsification rule preserved).

Core API
--------
- :func:`detect` — ``detect(events) -> Detection(score, decision, reason)``:
  the typed detection boundary over one session's minimal events.
- :func:`run_candidate` — the task-manifest adapter
  ``run_candidate(case, ctx) -> Outcome`` (DETECT -> ``REJECT`` alarm,
  NO_DETECT -> ``ADMIT``, malformed -> ``INDETERMINATE``).
- :func:`describe_mechanism` — machine-readable design record.
- :func:`DetectionParams` — the explicit frozen operating point (injected,
  never read from the environment).

Allowed input
-------------
``detect(events)`` accepts a non-empty, JSON-serializable sequence of event
mappings carrying exactly the five minimal-schema keys: ``actor_id``
(non-empty str), ``tool`` (non-empty str), ``scope`` (non-empty str),
``allowed`` (bool) and ``ts`` (non-negative int, non-decreasing across the
sequence). One call is one session/campaign: exactly one ``actor_id`` is
permitted. ``run_candidate`` wraps a case mapping
``{"case_id": str, "events": [...]}``. No network, no database, no provider,
no hidden clock, no randomness; synthetic fixtures only, no real PHI/PII.

Failure semantics
-----------------
Fail closed to INDETERMINATE with stable uppercase reason codes on malformed
input — a first-class outcome, never silently a safe rejection and never an
unhandled exception: ``EVENTS_NOT_A_LIST``, ``EVENT_SEQUENCE_EMPTY``,
``EVENT_NOT_AN_OBJECT``, ``EVENT_UNKNOWN_FIELD``,
``EVENT_REASON_CODE_FIELD_FORBIDDEN`` (leak-safe masking),
``EVENT_MISSING_FIELD``, ``EVENT_BAD_TYPE``, ``EVENT_TS_NOT_MONOTONIC``,
``SESSION_MIXED_ACTORS``; at the adapter boundary additionally
``MALFORMED_CASE``, ``CASE_EVENTS_MISSING``, ``CASE_EVENTS_NOT_A_LIST`` and
``UNKNOWN_ARM``. ``DetectionParams`` with a non-positive bound or an
out-of-range threshold raises :class:`CandidateError` (wiring error, raised
rather than guessed).

Determinism
-----------
Pure functions over the input; sorted iteration everywhere; the score is
rounded to 12 decimal places for byte-stable serialization. No ``random``
module, no clock, no environment reads.

Version
-------
``CANDIDATE_ID = "clara.dimva.candidate.governance-trace-probing-detector"``,
``CANDIDATE_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping, Sequence
from typing import Any

from evaluation.venue2027._shared.harness import Outcome

CANDIDATE_ID = "clara.dimva.candidate.governance-trace-probing-detector"
CANDIDATE_VERSION = "1.0.0"

#: The five minimal-schema event keys (leak-safe primary surface; mirrors the
#: frozen DIMVA minimal event contract — restated locally, never imported from
#: a detector-arm or truth module).
EVENT_KEYS: frozenset[str] = frozenset({"actor_id", "tool", "scope", "allowed", "ts"})

#: Keys whose presence constitutes rejection-reason leakage (RQ1 masking).
REASON_CODE_LEAK_KEYS: frozenset[str] = frozenset(
    {"reason_code", "reject_reason", "denial_reason", "rejection_code", "why"}
)

#: Detection decision values (Detection.decision).
DETECT = "DETECT"
NO_DETECT = "NO_DETECT"
INDETERMINATE = "INDETERMINATE"

#: Stable reason codes (uppercase, machine-checkable).
RC_CAMPAIGN_STRUCTURE_DETECTED = "CAMPAIGN_STRUCTURE_DETECTED"
RC_NO_ALARM = "NO_ALARM"
RC_EVENTS_NOT_A_LIST = "EVENTS_NOT_A_LIST"
RC_EVENT_SEQUENCE_EMPTY = "EVENT_SEQUENCE_EMPTY"
RC_EVENT_NOT_AN_OBJECT = "EVENT_NOT_AN_OBJECT"
RC_EVENT_UNKNOWN_FIELD = "EVENT_UNKNOWN_FIELD"
RC_EVENT_REASON_CODE_FORBIDDEN = "EVENT_REASON_CODE_FIELD_FORBIDDEN"
RC_EVENT_MISSING_FIELD = "EVENT_MISSING_FIELD"
RC_EVENT_BAD_TYPE = "EVENT_BAD_TYPE"
RC_EVENT_TS_NOT_MONOTONIC = "EVENT_TS_NOT_MONOTONIC"
RC_SESSION_MIXED_ACTORS = "SESSION_MIXED_ACTORS"
RC_MALFORMED_CASE = "MALFORMED_CASE"
RC_CASE_EVENTS_MISSING = "CASE_EVENTS_MISSING"
RC_CASE_EVENTS_NOT_A_LIST = "CASE_EVENTS_NOT_A_LIST"
RC_UNKNOWN_ARM = "UNKNOWN_ARM"
RC_CONTEXT_MALFORMED = "CONTEXT_MALFORMED"

#: Criterion names surfaced in Detection.evidence (stable, machine-checkable).
CRITERION_ENOUGH_DENIALS = "enough_denials"
CRITERION_CROSS_TOOL_OBFUSCATION = "cross_tool_obfuscation"
CRITERION_LONG_HORIZON_SPAN = "long_horizon_span"
CRITERION_EVADES_FIXED_WINDOW = "evades_fixed_window"
CRITERION_ACTIVITY_CONTINUITY = "activity_continuity"

#: Evidence subscore weights (frozen operating point; sum to 1.0).
SIGNAL_WEIGHTS: Mapping[str, float] = {
    "denial_volume": 0.15,
    "tool_spread": 0.15,
    "tool_entropy": 0.15,
    "pacing_evasion": 0.20,
    "horizon": 0.20,
    "continuity": 0.15,
}

#: Adapter arm ids that may invoke :func:`run_candidate`.
_ALLOWED_ARMS: frozenset[str] = frozenset({CANDIDATE_ID, "DIMVA-candidate", "candidate", ""})


class CandidateError(ValueError):
    """Wiring/configuration error carrying a stable reason code (not an outcome)."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class DetectionParams:
    """Explicit frozen operating point; injected, never read from the environment.

    ``probe_window_seconds`` / ``probe_window_threshold`` reproduce the static
    fixed-window count operating point that low-and-slow pacing must stay
    under (the evasion axis measured against the strongest counting alarm).
    """

    min_denials: int = 5
    min_distinct_denied_tools: int = 3
    min_span_seconds: int = 7200
    probe_window_seconds: int = 3600
    probe_window_threshold: int = 5
    max_gap_seconds: int = 7200
    detect_threshold: float = 0.6

    def __post_init__(self) -> None:
        for name in (
            "min_denials",
            "min_distinct_denied_tools",
            "min_span_seconds",
            "probe_window_seconds",
            "probe_window_threshold",
            "max_gap_seconds",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise CandidateError(RC_CONTEXT_MALFORMED, f"{name} must be a positive int")
        threshold = self.detect_threshold
        if (
            isinstance(threshold, bool)
            or not isinstance(threshold, int | float)
            or not math.isfinite(float(threshold))
            or not 0.0 < float(threshold) <= 1.0
        ):
            raise CandidateError(RC_CONTEXT_MALFORMED, "detect_threshold must be in (0, 1]")


#: Frozen default operating point (documented constants, not fitted on data).
DEFAULT_PARAMS = DetectionParams()


@dataclasses.dataclass(frozen=True)
class AgentEvent:
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
class Detection:
    """Typed detection result for one session.

    ``score`` is an arm-local, monotone evidence magnitude in [0, 1] (higher
    = more campaign-like); it is NOT a calibrated probability. ``decision``
    is one of DETECT / NO_DETECT / INDETERMINATE. ``reason`` carries the
    stable reason code. ``evidence`` carries the structural counts behind the
    decision (JSON-serializable; never contains event payloads).
    """

    score: float
    decision: str
    reason: str
    evidence: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.decision not in (DETECT, NO_DETECT, INDETERMINATE):
            raise CandidateError(
                RC_CONTEXT_MALFORMED,
                f"decision {self.decision!r} not in DETECT/NO_DETECT/INDETERMINATE",
            )
        if not math.isfinite(float(self.score)):
            raise CandidateError(RC_CONTEXT_MALFORMED, "score must be finite")

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": float(self.score),
            "decision": self.decision,
            "reason": self.reason,
            "evidence": dict(self.evidence),
        }


# ---------------------------------------------------------------------------
# Event validation — fail closed to INDETERMINATE, never to a safe rejection.
# ---------------------------------------------------------------------------


def _indeterminate(reason_code: str) -> Detection:
    return Detection(score=0.0, decision=INDETERMINATE, reason=reason_code, evidence={})


def _validate_events(events: Sequence[Mapping[str, Any]]) -> list[AgentEvent] | Detection:
    """Validate the minimal event sequence; return events or an INDETERMINATE."""
    if not isinstance(events, list | tuple):
        return _indeterminate(RC_EVENTS_NOT_A_LIST)
    if not events:
        return _indeterminate(RC_EVENT_SEQUENCE_EMPTY)

    validated: list[AgentEvent] = []
    actors: set[str] = set()
    previous_ts: int | None = None
    for raw in events:
        if not isinstance(raw, Mapping):
            return _indeterminate(RC_EVENT_NOT_AN_OBJECT)
        unknown = [str(key) for key in raw if key not in EVENT_KEYS]
        if any(key in REASON_CODE_LEAK_KEYS for key in unknown):
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
        validated.append(
            AgentEvent(actor_id=actor_id, tool=tool, scope=scope, allowed=allowed, ts=ts)
        )
    if len(actors) > 1:
        # The scientific unit is one session/campaign for one principal.
        return _indeterminate(RC_SESSION_MIXED_ACTORS)
    return validated


# ---------------------------------------------------------------------------
# Structural signals (pure functions of event structure; no labels anywhere).
# ---------------------------------------------------------------------------


def _shannon_entropy_bits(counter: Mapping[str, int]) -> float:
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    entropy = 0.0
    for count in sorted(counter.values()):
        p = count / total
        entropy -= p * math.log2(p)
    return entropy


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


def _structure_signals(
    events: Sequence[AgentEvent], params: DetectionParams
) -> tuple[float, dict[str, Any]]:
    """Compute the weighted structural score and its full evidence record."""
    denials = [e for e in events if not e.allowed]
    denied_ts = [e.ts for e in denials]
    tool_counter: dict[str, int] = {}
    for e in denials:
        tool_counter[e.tool] = tool_counter.get(e.tool, 0) + 1
    distinct_tools = len(tool_counter)
    total_denials = len(denials)
    span = events[-1].ts - events[0].ts
    max_window = _max_denials_in_window(denied_ts, params.probe_window_seconds)
    max_gap = _max_inter_arrival(denied_ts)

    volume = min(1.0, total_denials / params.min_denials)
    tool_spread = min(1.0, distinct_tools / params.min_distinct_denied_tools)
    if distinct_tools >= 2:
        tool_entropy = _shannon_entropy_bits(tool_counter) / math.log2(distinct_tools)
    elif distinct_tools == 1:
        tool_entropy = 1.0
    else:
        tool_entropy = 0.0
    pacing_evasion = 1.0 if max_window < params.probe_window_threshold else 0.0
    horizon = min(1.0, span / params.min_span_seconds)
    continuity = 1.0 if max_gap <= params.max_gap_seconds else 0.0

    subscores = {
        "denial_volume": volume,
        "tool_spread": tool_spread,
        "tool_entropy": tool_entropy,
        "pacing_evasion": pacing_evasion,
        "horizon": horizon,
        "continuity": continuity,
    }
    score = 0.0
    for name in sorted(SIGNAL_WEIGHTS):
        score += SIGNAL_WEIGHTS[name] * subscores[name]
    score = round(score, 12)

    criteria = {
        CRITERION_ENOUGH_DENIALS: total_denials >= params.min_denials,
        CRITERION_CROSS_TOOL_OBFUSCATION: distinct_tools >= params.min_distinct_denied_tools,
        CRITERION_LONG_HORIZON_SPAN: span >= params.min_span_seconds,
        CRITERION_EVADES_FIXED_WINDOW: max_window < params.probe_window_threshold,
        CRITERION_ACTIVITY_CONTINUITY: max_gap <= params.max_gap_seconds,
    }
    evidence: dict[str, Any] = {
        "total_denials": total_denials,
        "distinct_denied_tools": distinct_tools,
        "denied_tool_entropy_bits": round(_shannon_entropy_bits(tool_counter), 12),
        "span_seconds": span,
        "max_window_denials": max_window,
        "probe_window_seconds": params.probe_window_seconds,
        "probe_window_threshold": params.probe_window_threshold,
        "max_gap_seconds": max_gap,
        "subscores": {name: round(subscores[name], 12) for name in sorted(subscores)},
        "criteria": {name: bool(ok) for name, ok in criteria.items()},
        "criteria_met": sum(1 for ok in criteria.values() if ok),
        "criteria_total": len(criteria),
        "detect_threshold": params.detect_threshold,
    }
    return score, evidence


def detect(
    events: Sequence[Mapping[str, Any]], *, params: DetectionParams | None = None
) -> Detection:
    """Detect adaptive authorization-boundary probing from minimal agent events.

    One call is one session/campaign for one principal. Deterministic and
    fail-closed: malformed input yields an INDETERMINATE :class:`Detection`
    with a stable reason code (never a safe rejection, never an exception).
    """
    params = params if params is not None else DEFAULT_PARAMS
    if not isinstance(params, DetectionParams):
        raise CandidateError(
            RC_CONTEXT_MALFORMED, f"params must be DetectionParams, got {type(params)}"
        )
    validated = _validate_events(events)
    if isinstance(validated, Detection):
        return validated
    score, evidence = _structure_signals(validated, params)
    all_criteria = all(evidence["criteria"].values())
    if all_criteria and score >= params.detect_threshold:
        return Detection(
            score=score,
            decision=DETECT,
            reason=RC_CAMPAIGN_STRUCTURE_DETECTED,
            evidence=evidence,
        )
    return Detection(score=score, decision=NO_DETECT, reason=RC_NO_ALARM, evidence=evidence)


# ---------------------------------------------------------------------------
# Task-manifest adapter: run_candidate(case, ctx) -> Outcome.
# ---------------------------------------------------------------------------


def _arm_id(ctx: Any) -> str:
    if isinstance(ctx, Mapping):
        return str(ctx.get("arm_id", "") or "")
    return str(getattr(ctx, "arm_id", "") or "")


def run_candidate(case: Mapping[str, Any], ctx: Any = None) -> Outcome:
    """Adapter ``run_candidate(case, ctx) -> Outcome`` (task-manifest contract).

    DETECT -> ``REJECT`` (alarm raised), NO_DETECT -> ``ADMIT`` (session
    passes as benign), both ``counted_as_success=True``; malformed case ->
    ``INDETERMINATE`` (never counted, never silently a safe rejection); an
    unregistered ``ctx.arm_id`` -> ``INVALID_RESULT`` / ``UNKNOWN_ARM`` (a
    constant-allow stub can never masquerade as the candidate arm). The
    arm-local evidence score is carried in ``detail`` as
    ``"<REASON>|score=<float>"``; use :func:`detect` for the typed decision.
    """
    arm = _arm_id(ctx)
    if arm not in _ALLOWED_ARMS:
        return Outcome(
            observed_outcome="INVALID_RESULT",
            counted_as_success=False,
            retriable=False,
            detail=f"{RC_UNKNOWN_ARM}|arm={arm!r}",
        )
    if not isinstance(case, Mapping):
        return Outcome(
            observed_outcome=INDETERMINATE,
            counted_as_success=False,
            retriable=False,
            detail=RC_MALFORMED_CASE,
        )
    if "events" not in case:
        return Outcome(
            observed_outcome=INDETERMINATE,
            counted_as_success=False,
            retriable=False,
            detail=RC_CASE_EVENTS_MISSING,
        )
    raw_events = case["events"]
    if not isinstance(raw_events, list):
        return Outcome(
            observed_outcome=INDETERMINATE,
            counted_as_success=False,
            retriable=False,
            detail=RC_CASE_EVENTS_NOT_A_LIST,
        )
    detection = detect(raw_events)
    if detection.decision == INDETERMINATE:
        return Outcome(
            observed_outcome=INDETERMINATE,
            counted_as_success=False,
            retriable=False,
            detail=detection.reason,
        )
    observed = "REJECT" if detection.decision == DETECT else "ADMIT"
    return Outcome(
        observed_outcome=observed,
        counted_as_success=True,
        retriable=False,
        detail=f"{detection.reason}|score={detection.score:.6f}",
    )


def describe_mechanism() -> dict[str, Any]:
    """Machine-readable design record (isolated candidate, no oracle linkage)."""
    return {
        "candidate_id": CANDIDATE_ID,
        "candidate_version": CANDIDATE_VERSION,
        "venue": "dimva",
        "task_id": "DIMVA-candidate",
        "mechanism_class": (
            "campaign-level structural linkage over minimal leak-safe agent events"
        ),
        "input_surface": sorted(EVENT_KEYS),
        "signals": dict(SIGNAL_WEIGHTS),
        "criteria": [
            CRITERION_ENOUGH_DENIALS,
            CRITERION_CROSS_TOOL_OBFUSCATION,
            CRITERION_LONG_HORIZON_SPAN,
            CRITERION_EVADES_FIXED_WINDOW,
            CRITERION_ACTIVITY_CONTINUITY,
        ],
        "operating_point": dataclasses.asdict(DEFAULT_PARAMS),
        "decision_rule": (
            "DETECT iff every structural criterion holds and the weighted "
            "subscore reaches detect_threshold; NO_DETECT otherwise; "
            "INDETERMINATE on malformed input (fail closed)"
        ),
        "label_usage": (
            "none: the decision is a pure function of event structure; no "
            "truth oracle, no scenario-family registry, no expected verdict "
            "and no rejection reason code is ever read"
        ),
        "determinism": "pure functions; sorted iteration; score rounded to 12 decimals",
    }
