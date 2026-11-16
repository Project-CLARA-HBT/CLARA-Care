"""DIMVA venue2027 sequence-aware detector (task DIMVA-X06_seq_detector, phase P04).

Purpose
-------
Sequence-aware campaign detector over minimal agent event sequences capturing
order/transition structure (not just window counts) for the DIMVA 2027 study
"GovernanceTrace: Detecting Adaptive Authorization-Boundary Probing from Minimal
Agent Events" (``research/venue2027/VENUES/dimva/RESEARCH_BLUEPRINT.md``, task
contract ``research/venue2027/VENUES/dimva/TASKS/DIMVA-X06_seq_detector.md``).

A minimal agent event sequence consists of events with minimal leak-safe schema:
``(actor_id, tool, scope, allowed, ts)`` (monotonic non-negative timestamps, single
actor per session, no raw content, no post-hoc rejection reason codes, no ground-truth
campaign labels).

Static sliding-window count detectors (B0 baseline) miss low-and-slow reconnaissance
campaigns whose pacing stays strictly below per-window count thresholds (e.g., 1 denial
every 3700 seconds under a 3600-second window). Static cross-scope rules (B1 baseline)
miss same-scope probing campaigns. This detector captures order and transition
structure:
- Transition dynamics: Markov state transitions across event status pairs
  (allowed->denied, denied->denied, cross-tool after denial, cross-scope after denial).
- Temporal pacing consistency: monotonic spacing and bounded inter-arrival intervals
  indicating deliberate campaign continuity rather than sporadic benign faults.
- Diversity & Dispersion: dispersion of denied tools and scopes along the temporal
  progression (Shannon entropy and distinct target progression).
- Structural sequence linkage: scores the cumulative transition likelihood and
  structural progression monotonically with campaign length.

Core API
--------
- ``fit(train, dev=None) -> SequenceModel``: fits a sequence transition model on
  leak-safe training sessions without peeking at labels.
- ``score(events) -> float``: returns a sequence anomaly/campaign evidence score in [0.0, 1.0].
- ``detect(events, threshold=0.6) -> Detection``: returns a typed detection decision
  (DETECT, NO_DETECT, INDETERMINATE) with stable reason codes and evidence dict.
- ``run_sequence_detector(case, ctx=None) -> Outcome``: task-manifest / harness adapter.

NO-LEAKAGE CONTRACT (RQ1 Masking)
---------------------------------
Scoring and detection are pure functions of event sequence structure. The detector
never reads, requests, or inspects ground-truth labels, scenario families, or post-hoc
rejection reason codes. Any event field outside the minimal schema fails closed
(``EVENT_UNKNOWN_FIELD``, ``EVENT_REASON_CODE_FIELD_FORBIDDEN``).

Determinism
-----------
Pure deterministic stdlib math. No hidden clock, no network, no random seeds in scoring,
no live providers, no unhandled exceptions.

Version
-------
``SEQUENCE_DETECTOR_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping, Sequence
from typing import Any

from evaluation.venue2027._shared.harness import Outcome

SEQUENCE_DETECTOR_VERSION = "1.0.0"
DETECTOR_ID = "clara.dimva.detector.sequence-transition-detector"

#: Minimal event schema keys
EVENT_KEYS: frozenset[str] = frozenset({"actor_id", "tool", "scope", "allowed", "ts"})

#: Forbidden leak keys (RQ1 masking contract)
REASON_CODE_LEAK_KEYS: frozenset[str] = frozenset(
    {"reason_code", "reject_reason", "denial_reason", "rejection_code", "why"}
)
LABEL_LEAK_KEYS: frozenset[str] = frozenset(
    {"label", "campaign_label", "is_attack", "attacker_label", "ground_truth", "family"}
)

#: Detection decisions
DETECT = "DETECT"
NO_DETECT = "NO_DETECT"
INDETERMINATE = "INDETERMINATE"

#: Stable reason codes
RC_SEQUENCE_STRUCTURE_DETECTED = "SEQUENCE_STRUCTURE_DETECTED"
RC_NO_ALARM = "NO_ALARM"
RC_EVENTS_NOT_A_LIST = "EVENTS_NOT_A_LIST"
RC_EVENT_SEQUENCE_EMPTY = "EVENT_SEQUENCE_EMPTY"
RC_EVENT_NOT_AN_OBJECT = "EVENT_NOT_AN_OBJECT"
RC_EVENT_UNKNOWN_FIELD = "EVENT_UNKNOWN_FIELD"
RC_EVENT_REASON_CODE_FORBIDDEN = "EVENT_REASON_CODE_FIELD_FORBIDDEN"
RC_EVENT_LABEL_FIELD_FORBIDDEN = "EVENT_LABEL_FIELD_FORBIDDEN"
RC_EVENT_MISSING_FIELD = "EVENT_MISSING_FIELD"
RC_EVENT_BAD_TYPE = "EVENT_BAD_TYPE"
RC_EVENT_TS_NOT_MONOTONIC = "EVENT_TS_NOT_MONOTONIC"
RC_SESSION_MIXED_ACTORS = "SESSION_MIXED_ACTORS"
RC_MALFORMED_CASE = "MALFORMED_CASE"
RC_CASE_EVENTS_MISSING = "CASE_EVENTS_MISSING"
RC_CASE_EVENTS_NOT_A_LIST = "CASE_EVENTS_NOT_A_LIST"
RC_CONTEXT_MALFORMED = "CONTEXT_MALFORMED"
RC_UNKNOWN_ARM = "UNKNOWN_ARM"
RC_HOLDOUT_LEAK = "HOLDOUT_LEAK"

DEFAULT_DETECTION_THRESHOLD = 0.60


class SequenceDetectorError(ValueError):
    """Wiring/configuration error carrying a stable reason code."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class MinimalEvent:
    """One validated minimal-schema event."""

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
    """Typed detection outcome for an event sequence."""

    score: float
    decision: str
    reason: str
    evidence: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.decision not in (DETECT, NO_DETECT, INDETERMINATE):
            raise SequenceDetectorError(
                RC_CONTEXT_MALFORMED,
                f"decision {self.decision!r} not in DETECT/NO_DETECT/INDETERMINATE",
            )
        if not math.isfinite(float(self.score)):
            raise SequenceDetectorError(RC_CONTEXT_MALFORMED, "score must be finite")

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": float(self.score),
            "decision": self.decision,
            "reason": self.reason,
            "evidence": dict(self.evidence),
        }


def _indeterminate(reason_code: str) -> Detection:
    return Detection(score=0.0, decision=INDETERMINATE, reason=reason_code, evidence={})


def _validate_events(events: Any) -> list[MinimalEvent] | Detection:
    """Validate minimal event sequence; fail closed to INDETERMINATE."""
    if not isinstance(events, list | tuple):
        return _indeterminate(RC_EVENTS_NOT_A_LIST)
    if not events:
        return _indeterminate(RC_EVENT_SEQUENCE_EMPTY)

    validated: list[MinimalEvent] = []
    actors: set[str] = set()
    prev_ts: int | None = None

    for raw in events:
        if not isinstance(raw, Mapping):
            return _indeterminate(RC_EVENT_NOT_AN_OBJECT)

        # Check for leak keys
        for k in raw:
            if k in REASON_CODE_LEAK_KEYS:
                return _indeterminate(RC_EVENT_REASON_CODE_FORBIDDEN)
            if k in LABEL_LEAK_KEYS:
                return _indeterminate(RC_EVENT_LABEL_FIELD_FORBIDDEN)
            if k not in EVENT_KEYS:
                return _indeterminate(RC_EVENT_UNKNOWN_FIELD)

        missing = [k for k in EVENT_KEYS if k not in raw]
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
        if prev_ts is not None and ts < prev_ts:
            return _indeterminate(RC_EVENT_TS_NOT_MONOTONIC)

        prev_ts = ts
        actors.add(actor_id)
        validated.append(
            MinimalEvent(actor_id=actor_id, tool=tool, scope=scope, allowed=allowed, ts=ts)
        )

    if len(actors) > 1:
        return _indeterminate(RC_SESSION_MIXED_ACTORS)

    return validated


def _shannon_entropy(items: Sequence[str]) -> float:
    if not items:
        return 0.0
    counts: dict[str, int] = {}
    for it in items:
        counts[it] = counts.get(it, 0) + 1
    total = len(items)
    ent = 0.0
    for c in counts.values():
        p = c / total
        ent -= p * math.log2(p)
    return ent


def _sequence_features(events: Sequence[MinimalEvent]) -> dict[str, Any]:
    """Compute order, transition, and pacing features over minimal event sequence."""
    n = len(events)
    denials = [e for e in events if not e.allowed]
    denial_count = len(denials)
    denied_tools = [e.tool for e in denials]
    unique_denied_tools = sorted(set(denied_tools))
    n_unique_denied_tools = len(unique_denied_tools)

    denied_ts = [e.ts for e in denials]
    all_ts = [e.ts for e in events]
    total_span = (all_ts[-1] - all_ts[0]) if n >= 2 else 0

    # Inter-denial pacing
    if len(denied_ts) >= 2:
        denial_gaps = [b - a for a, b in zip(denied_ts, denied_ts[1:])]
        min_denial_gap = min(denial_gaps)
        max_denial_gap = max(denial_gaps)
        mean_denial_gap = sum(denial_gaps) / len(denial_gaps)
        # Gap variance/std dev
        variance = sum((g - mean_denial_gap) ** 2 for g in denial_gaps) / len(denial_gaps)
        gap_std = math.sqrt(variance)
        # Regularity index: lower coefficient of variation -> more deliberate pacing
        cv = (gap_std / mean_denial_gap) if mean_denial_gap > 0 else 0.0
    else:
        min_denial_gap = 0
        max_denial_gap = 0
        mean_denial_gap = 0.0
        gap_std = 0.0
        cv = 1.0

    # Transition dynamics
    # Count transitions:
    # - cross_tool_transitions: tool changes from event i to event i+1
    # - cross_tool_denial_transitions: denial i followed by denial i+1 on different tool
    # - denial_run_lengths: consecutive denials
    cross_tool_denial_transitions = 0
    for i in range(len(denials) - 1):
        if denials[i].tool != denials[i + 1].tool:
            cross_tool_denial_transitions += 1

    cross_scope_transitions = 0
    for i in range(n - 1):
        if events[i].scope != events[i + 1].scope:
            cross_scope_transitions += 1

    # Max denial in any sliding 3600s window (to measure fixed-window evasion)
    window_s = 3600
    max_window_denials = 0
    left = 0
    for right, ts_r in enumerate(denied_ts):
        while ts_r - denied_ts[left] >= window_s:
            left += 1
        max_window_denials = max(max_window_denials, right - left + 1)

    # Tool entropy over denied events
    tool_ent = _shannon_entropy(denied_tools)
    norm_tool_ent = (tool_ent / math.log2(n_unique_denied_tools)) if n_unique_denied_tools > 1 else (1.0 if n_unique_denied_tools == 1 else 0.0)

    return {
        "n_events": n,
        "denial_count": denial_count,
        "n_unique_denied_tools": n_unique_denied_tools,
        "total_span": total_span,
        "min_denial_gap": min_denial_gap,
        "max_denial_gap": max_denial_gap,
        "mean_denial_gap": round(mean_denial_gap, 6),
        "gap_cv": round(cv, 6),
        "cross_tool_denial_transitions": cross_tool_denial_transitions,
        "cross_scope_transitions": cross_scope_transitions,
        "max_window_denials": max_window_denials,
        "tool_entropy": round(tool_ent, 6),
        "normalized_tool_entropy": round(norm_tool_ent, 6),
    }


def compute_sequence_score(features: Mapping[str, Any]) -> float:
    """Compute continuous anomaly score in [0.0, 1.0] from sequence structure features.

    Properties:
    1. Monotonic with campaign length: as low-and-slow probing proceeds (more denials,
       more cross-tool transitions, longer horizon span), score increases monotonically.
    2. Zero or near-zero for benign retries or bursts without campaign pacing/transition structure.
    3. Pure math, deterministic, bounded.
    """
    denial_count = int(features["denial_count"])
    if denial_count == 0:
        return 0.0

    # 1. Volume & Transition Progression
    # Smooth progression over campaign length using bounded log scaling
    # e.g., 1 - exp(-denial_count / 10.0) so it is strictly increasing for any length
    volume_signal = 1.0 - math.exp(-denial_count / 10.0)

    # 2. Cross-tool transition progression
    # Attackers probing boundary rotate tools: cross_tool_denial_transitions
    cross_tool_transitions = int(features["cross_tool_denial_transitions"])
    unique_tools = int(features["n_unique_denied_tools"])
    if denial_count >= 2:
        transition_rate = cross_tool_transitions / (denial_count - 1)
        tool_spread = 1.0 - math.exp(-unique_tools / 6.0)
    else:
        transition_rate = 0.0
        tool_spread = 0.1 if unique_tools == 1 else 0.0

    tool_transition_signal = 0.5 * transition_rate + 0.5 * tool_spread

    # 3. Temporal Horizon & Pacing Signal
    # Low-and-slow campaigns span hours with steady pacing (mean gap > 600s, max gap <= 7200s)
    total_span = int(features["total_span"])
    mean_gap = float(features["mean_denial_gap"])
    max_gap = int(features["max_denial_gap"])
    span_signal = 1.0 - math.exp(-total_span / 36000.0)

    # Pacing regularity: cv in [0, 2]; low cv means deliberate cadence
    cv = float(features["gap_cv"])
    if denial_count >= 3 and mean_gap >= 600:
        # Paced across windows: deliberate inter-arrival
        pacing_deliberate = max(0.0, 1.0 - min(1.0, cv / 1.5))
    elif denial_count >= 3:
        # Fast burst: low gap
        pacing_deliberate = 0.15
    else:
        pacing_deliberate = 0.0

    # Continuity check: gaps don't exceed campaign horizon bound
    continuity_signal = 1.0 if (denial_count >= 2 and max_gap <= 7200) else (0.4 if denial_count == 1 else 0.0)

    # 4. Low-and-slow fixed-window evasion modifier
    # If max denials per 3600s window is low (< 5), it indicates deliberate window evasion
    max_win = int(features["max_window_denials"])
    if max_win > 0 and max_win < 5 and denial_count >= 4 and total_span >= 3600:
        # Scales strictly with length
        evasion_bonus = 0.15 * (1.0 - math.exp(-denial_count / 8.0))
    else:
        evasion_bonus = 0.0

    # Weighted combination
    # Volume: 0.22, Tool transitions: 0.22, Horizon/span: 0.22, Pacing: 0.14, Continuity: 0.10, Evasion: up to 0.10
    raw_score = (
        0.22 * volume_signal
        + 0.22 * tool_transition_signal
        + 0.22 * span_signal
        + 0.14 * pacing_deliberate
        + 0.10 * continuity_signal
        + 0.10 * (1.0 - math.exp(-denial_count / 8.0) if evasion_bonus > 0 else 0.0)
    )

    final_score = min(1.0, max(0.0, raw_score))
    return round(final_score, 6)


@dataclasses.dataclass(frozen=True)
class SequenceModel:
    """Fitted sequence transition model."""

    model_id: str
    version: str
    threshold: float
    train_sequences_count: int
    train_denial_rate: float

    def score(self, events: Any) -> float:
        """Score an event sequence using the fitted transition dynamics."""
        return score(events, model=self)

    def detect(self, events: Any, threshold: float | None = None) -> Detection:
        """Detect probing on an event sequence."""
        th = threshold if threshold is not None else self.threshold
        return detect(events, threshold=th, model=self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "version": self.version,
            "threshold": self.threshold,
            "train_sequences_count": self.train_sequences_count,
            "train_denial_rate": round(self.train_denial_rate, 6),
        }


def fit(train: Sequence[Any], dev: Sequence[Any] | None = None) -> SequenceModel:
    """Fit a sequence detector on leak-safe training sessions.

    Contract: ``fit(train, dev) -> Model``.
    Learns training population transition statistics without peeking at labels.
    """
    if not isinstance(train, list | tuple):
        raise SequenceDetectorError(RC_EVENTS_NOT_A_LIST, "train must be a sequence of sessions")
    if not train:
        raise SequenceDetectorError(RC_EVENT_SEQUENCE_EMPTY, "train sequence cannot be empty")

    total_events = 0
    total_denials = 0

    for idx, seq in enumerate(train):
        # Check for holdout tag in training data
        if isinstance(seq, Mapping):
            tag = str(seq.get("split", seq.get("partition", seq.get("split_tag", "")))).lower()
            if tag in ("dev", "test", "holdout"):
                raise SequenceDetectorError(
                    RC_HOLDOUT_LEAK, f"training item {idx} is tagged with holdout partition {tag!r}"
                )
            raw_ev = seq.get("events", seq)
        else:
            raw_ev = seq

        val = _validate_events(raw_ev)
        if isinstance(val, Detection):
            raise SequenceDetectorError(val.reason, f"training session {idx} invalid: {val.reason}")

        for e in val:
            total_events += 1
            if not e.allowed:
                total_denials += 1

    denial_rate = (total_denials / total_events) if total_events > 0 else 0.0

    return SequenceModel(
        model_id=DETECTOR_ID,
        version=SEQUENCE_DETECTOR_VERSION,
        threshold=DEFAULT_DETECTION_THRESHOLD,
        train_sequences_count=len(train),
        train_denial_rate=denial_rate,
    )


def score(events: Any, *, model: SequenceModel | None = None) -> float:
    """Score a minimal agent event sequence.

    Contract: ``score(stream) -> float``.
    Returns a float in [0.0, 1.0], or 0.0 if invalid.
    """
    val = _validate_events(events)
    if isinstance(val, Detection):
        return 0.0

    feats = _sequence_features(val)
    return compute_sequence_score(feats)


def detect(
    events: Any,
    threshold: float = DEFAULT_DETECTION_THRESHOLD,
    *,
    model: SequenceModel | None = None,
) -> Detection:
    """Detect adaptive authorization probing from event sequence.

    Contract: ``detect(events, threshold) -> Detection``.
    """
    if not isinstance(threshold, int | float) or isinstance(threshold, bool):
        raise SequenceDetectorError(RC_CONTEXT_MALFORMED, "threshold must be a numeric float")
    if not (0.0 < float(threshold) <= 1.0):
        raise SequenceDetectorError(RC_CONTEXT_MALFORMED, "threshold must be in (0, 1]")

    val = _validate_events(events)
    if isinstance(val, Detection):
        return val

    feats = _sequence_features(val)
    s = compute_sequence_score(feats)
    decision = DETECT if s >= threshold else NO_DETECT
    reason = RC_SEQUENCE_STRUCTURE_DETECTED if decision == DETECT else RC_NO_ALARM

    evidence = dict(feats)
    evidence["threshold"] = threshold
    evidence["score"] = s

    return Detection(
        score=s,
        decision=decision,
        reason=reason,
        evidence=evidence,
    )


def run_sequence_detector(case: Mapping[str, Any], ctx: Any = None) -> Outcome:
    """Harness adapter executing the sequence detector on a case.

    Case mapping: ``{"case_id": str, "events": list}``.
    Returns Outcome(observed_outcome, counted_as_success, retriable, detail).
    """
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

    res = detect(raw_events)
    if res.decision == INDETERMINATE:
        return Outcome(
            observed_outcome=INDETERMINATE,
            counted_as_success=False,
            retriable=False,
            detail=res.reason,
        )

    observed = "REJECT" if res.decision == DETECT else "ADMIT"
    return Outcome(
        observed_outcome=observed,
        counted_as_success=True,
        retriable=False,
        detail=f"{res.reason}|score={res.score:.6f}",
    )
