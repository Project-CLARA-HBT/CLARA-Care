"""DIMVA-ablation — causal mechanism ablation variants for GovernanceTrace.

Purpose
-------
Task DIMVA-ablation (Phase P04, venue dimva): causal mechanism ablation
registry for "GovernanceTrace: Detecting Adaptive Authorization-Boundary
Probing from Minimal Agent Events"
(``research/venue2027/VENUES/dimva/RESEARCH_BLUEPRINT.md``, RQ1-RQ3; task
contract ``research/venue2027/VENUES/dimva/TASKS/DIMVA-ablation.md``). The
candidate detector (:mod:`evaluation.venue2027.dimva.candidate`) links minimal,
leak-safe agent events into a multi-step reconnaissance campaign and alarms
only when all structural criteria hold:
1. enough denial volume (volume >= min_denials);
2. cross-tool obfuscation (distinct denied tools >= 3, Shannon entropy);
3. long horizon span (span >= min_span_seconds);
4. low-and-slow pacing (max per-window denials < fixed-window operating point);
5. activity continuity (bounded inter-denial gaps).

This module runs the candidate against ITSELF with EXACTLY ONE mechanism
removed per variant, over the same frozen synthetic event streams, so each
mechanism's causal contribution to detection is measurable (development-scale
mechanism causality on frozen synthetic cases — never confirmatory results).

Preregistered variants (``ABLATION_REGISTRY``):
- ``without_campaign_linkage`` — candidate WITHOUT cross-window campaign linkage:
  events are evaluated per isolated window of probe_window_seconds without
  linking denials across extended time intervals into a unified campaign.
  The low-and-slow campaign (denials spaced beyond the window) is missed.
- ``without_cross_tool_feature`` — candidate WITHOUT cross-tool feature:
  tool identities are masked to a constant, so the detector cannot evaluate
  distinct-tool spread or tool entropy (cross-tool obfuscation fails).
- ``without_pacing_feature`` — candidate WITHOUT pacing evasion feature:
  the tolerance window threshold is ablated (probe_window_threshold=1) so
  the pacing evasion criterion is never satisfied.
- ``with_only_per_window_counts`` — candidate with ONLY per-window counts:
  static operational counting baseline (B0 semantics); all campaign linkage,
  cross-tool, pacing, and continuity features are removed, leaving only the
  fixed-window count threshold. Misses low-and-slow campaigns and false-alarms
  on benign bursts.
- ``full_candidate`` — the unmodified candidate (safety reference row);
  omits nothing (``ablated_mechanism = "none"``).

Allowed input
-------------
``run_ablation(name, case) -> Outcome`` (task-manifest signature):
- ``name``: registered variant id in :data:`ABLATION_REGISTRY`.
- ``case``: JSON-serializable mapping ``{"case_id": str, "events": [...]}``
  conforming to the DIMVA minimal event schema: ``(actor_id, tool, scope,
  allowed, ts)``. No network, DB, clock, or live provider.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes:
- Unknown variant id -> ``EXECUTION_ERROR`` with ``UNKNOWN_ABLATION_VARIANT``.
- Identity removing no mechanism (other than the preregistered full candidate
  row) -> ``EXECUTION_ERROR`` with ``VARIANT_REMOVES_NOTHING``.
- Malformed case / missing events -> ``INDETERMINATE`` (never counted).
- Candidate validation failures -> ``INDETERMINATE`` carrying candidate reason codes.
- Determined verdicts: DETECT -> ``REJECT``, NO_DETECT -> ``ADMIT`` (both
  ``counted_as_success=True``).

Version
-------
``ABLATIONS_VERSION = "clara.dimva.ablations-v1"`` (additive-only 1.x).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Final

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.dimva import candidate as cand

ABLATIONS_VERSION: Final[str] = "clara.dimva.ablations-v1"
ABLATION_TASK_ID: Final[str] = "DIMVA-ablation"

#: Registered variant ids.
VARIANT_WITHOUT_CAMPAIGN_LINKAGE: Final[str] = "without_campaign_linkage"
VARIANT_WITHOUT_CROSS_TOOL_FEATURE: Final[str] = "without_cross_tool_feature"
VARIANT_WITHOUT_PACING_FEATURE: Final[str] = "without_pacing_feature"
VARIANT_WITH_ONLY_PER_WINDOW_COUNTS: Final[str] = "with_only_per_window_counts"
VARIANT_FULL_CANDIDATE: Final[str] = "full_candidate"

REFERENCE_VARIANT_ID: Final[str] = VARIANT_FULL_CANDIDATE

#: Non-ablation identities that claim to remove nothing (refused by guard).
NON_ABLATION_IDENTITIES: Final[frozenset[str]] = frozenset(
    {
        cand.CANDIDATE_ID,
        "DIMVA-candidate",
        "candidate",
        "unablated_candidate",
        "none",
        "removes_nothing",
    }
)

#: Ablated mechanism axis identifiers.
ABLATED_CAMPAIGN_LINKAGE: Final[str] = "campaign_linkage"
ABLATED_CROSS_TOOL_FEATURE: Final[str] = "cross_tool_feature"
ABLATED_PACING_FEATURE: Final[str] = "pacing_feature"
ABLATED_STRUCTURAL_CRITERIA: Final[str] = "multi_signal_structural_criteria"
ABLATED_NONE: Final[str] = "none"

#: Stable reason codes.
RC_UNKNOWN_ABLATION_VARIANT: Final[str] = "UNKNOWN_ABLATION_VARIANT"
RC_VARIANT_REMOVES_NOTHING: Final[str] = "VARIANT_REMOVES_NOTHING"
RC_MALFORMED_CASE: Final[str] = "MALFORMED_CASE"
RC_CASE_EVENTS_MISSING: Final[str] = "CASE_EVENTS_MISSING"
RC_CASE_EVENTS_NOT_A_LIST: Final[str] = "CASE_EVENTS_NOT_A_LIST"
RC_WINDOW_COUNT_THRESHOLD_REACHED: Final[str] = "WINDOW_COUNT_THRESHOLD_REACHED"

#: Verdict constants.
VERDICT_REJECT: Final[str] = "REJECT"
VERDICT_ADMIT: Final[str] = "ADMIT"
VERDICT_INDETERMINATE: Final[str] = "INDETERMINATE"
VERDICT_EXECUTION_ERROR: Final[str] = "EXECUTION_ERROR"

#: Synthetic fault/control family ids for mechanistic adjudication.
FAMILY_LOW_AND_SLOW_CROSS_TOOL: Final[str] = "low_and_slow_cross_tool"
FAMILY_BENIGN_BURST: Final[str] = "benign_burst"
FAMILY_BENIGN_RETRY: Final[str] = "benign_retry"
FAMILY_BENIGN_HANDOFF: Final[str] = "benign_handoff"

FAULT_FAMILY_IDS: Final[tuple[str, ...]] = (
    FAMILY_LOW_AND_SLOW_CROSS_TOOL,
    FAMILY_BENIGN_BURST,
    FAMILY_BENIGN_RETRY,
    FAMILY_BENIGN_HANDOFF,
)


class AblationError(ValueError):
    """Wiring or configuration error carrying a stable reason code."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class VariantSpec:
    """One registered ablation variant specification.

    Each variant declares exactly one ablated mechanism (or ``none`` for the
    unmodified full candidate reference row). Any variant declaring an empty
    mechanism or an impostor 'none' is refused at construction.
    """

    variant_id: str
    title: str
    ablated_mechanism: str
    description: str
    expected_effect: str
    reuses: tuple[str, ...]
    applied_by: str

    def __post_init__(self) -> None:
        if not isinstance(self.ablated_mechanism, str) or not self.ablated_mechanism.strip():
            raise AblationError(
                RC_VARIANT_REMOVES_NOTHING,
                f"variant {self.variant_id!r} declares no ablated mechanism; "
                "a variant removing nothing is not an ablation",
            )
        if self.ablated_mechanism == ABLATED_NONE and self.variant_id != VARIANT_FULL_CANDIDATE:
            raise AblationError(
                RC_VARIANT_REMOVES_NOTHING,
                f"variant {self.variant_id!r} declares ablated_mechanism='none'; "
                f"only {VARIANT_FULL_CANDIDATE!r} is the permitted reference row",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "title": self.title,
            "ablated_mechanism": self.ablated_mechanism,
            "description": self.description,
            "expected_effect": self.expected_effect,
            "reuses": list(self.reuses),
            "applied_by": self.applied_by,
        }


#: Preregistered ABLATION_REGISTRY (frozen design contract).
ABLATION_REGISTRY: Final[Mapping[str, VariantSpec]] = {
    spec.variant_id: spec
    for spec in (
        VariantSpec(
            variant_id=VARIANT_WITHOUT_CAMPAIGN_LINKAGE,
            title="Candidate without cross-window campaign linkage",
            ablated_mechanism=ABLATED_CAMPAIGN_LINKAGE,
            description=(
                "The multi-window temporal campaign linkage is removed: events "
                "are evaluated per isolated window of probe_window_seconds "
                "without linking denials across extended time intervals into a "
                "unified campaign. Denials paced beyond the window are missed."
            ),
            expected_effect="misses_low_and_slow_campaign",
            reuses=(
                "candidate._validate_events",
                "candidate._structure_signals",
                "candidate.DEFAULT_PARAMS",
            ),
            applied_by="window_scoped_segmentation",
        ),
        VariantSpec(
            variant_id=VARIANT_WITHOUT_CROSS_TOOL_FEATURE,
            title="Candidate without cross-tool feature",
            ablated_mechanism=ABLATED_CROSS_TOOL_FEATURE,
            description=(
                "The cross-tool obfuscation mechanism is removed: tool "
                "identities are masked to a constant before detection, so "
                "distinct-tool count collapses to 1 and entropy drops to 0. "
                "Cross-tool obfuscation criterion is never satisfied."
            ),
            expected_effect="misses_cross_tool_obfuscation",
            reuses=(
                "candidate._validate_events",
                "candidate.detect",
            ),
            applied_by="tool_dimension_masking",
        ),
        VariantSpec(
            variant_id=VARIANT_WITHOUT_PACING_FEATURE,
            title="Candidate without pacing feature",
            ablated_mechanism=ABLATED_PACING_FEATURE,
            description=(
                "The low-and-slow pacing evasion mechanism is removed: the "
                "operating point is configured with probe_window_threshold=1, "
                "so any denial inside a window prevents evades_fixed_window "
                "from ever holding."
            ),
            expected_effect="misses_pacing_evasion",
            reuses=(
                "candidate.DetectionParams",
                "candidate.detect",
            ),
            applied_by="pacing_parameter_mutation",
        ),
        VariantSpec(
            variant_id=VARIANT_WITH_ONLY_PER_WINDOW_COUNTS,
            title="Candidate with only per-window counts (B0 counting baseline)",
            ablated_mechanism=ABLATED_STRUCTURAL_CRITERIA,
            description=(
                "All structural criteria (cross-tool, horizon, pacing evasion, "
                "continuity) are removed, leaving ONLY the static sliding-window "
                "denial count threshold (B0 operational baseline). Misses "
                "low-and-slow campaigns and false-alarms on dense benign bursts."
            ),
            expected_effect="misses_low_and_slow_and_false_alarms_on_bursts",
            reuses=(
                "candidate._validate_events",
                "candidate._max_denials_in_window",
                "candidate.DEFAULT_PARAMS",
            ),
            applied_by="fixed_window_count_filter",
        ),
        VariantSpec(
            variant_id=VARIANT_FULL_CANDIDATE,
            title="Full GovernanceTrace candidate detector (reference row)",
            ablated_mechanism=ABLATED_NONE,
            description=(
                "The unmodified candidate: links multi-step minimal events "
                "across the session horizon, checking volume, cross-tool "
                "obfuscation, horizon span, window-evading pacing, and "
                "continuity."
            ),
            expected_effect="catches_low_and_slow_and_admits_benign_controls",
            reuses=(
                "candidate.detect",
                "candidate.DEFAULT_PARAMS",
            ),
            applied_by="unmodified_candidate_pipeline",
        ),
    )
}


def refuse_unregistered_variant(name: str) -> VariantSpec:
    """Guard: return the registered spec for ``name`` or refuse fail-closed.

    Refuses (raises :class:`AblationError`):
    - any id not in :data:`ABLATION_REGISTRY` and not a known nothing-removing
      identity -> ``UNKNOWN_ABLATION_VARIANT`` (never guessed safe);
    - known nothing-removing identities (e.g. candidate id itself, generic
      unregistered aliases) -> ``VARIANT_REMOVES_NOTHING``: a variant that
      removes no mechanism is not an ablation.
    """
    spec = ABLATION_REGISTRY.get(name)
    if spec is not None:
        return spec
    if name in NON_ABLATION_IDENTITIES:
        raise AblationError(
            RC_VARIANT_REMOVES_NOTHING,
            f"{name!r} is not an ablation variant; run candidate directly "
            "or use the registered 'full_candidate' reference row",
        )
    raise AblationError(
        RC_UNKNOWN_ABLATION_VARIANT,
        f"variant {name!r} not in registry {sorted(ABLATION_REGISTRY)}",
    )


def variant_ids() -> tuple[str, ...]:
    """Registered ablation variant ids in canonical order."""
    return tuple(ABLATION_REGISTRY)


# ---------------------------------------------------------------------------
# Individual variant detector callables (each reuses candidate components).
# ---------------------------------------------------------------------------


def detect_full_candidate(
    events: Sequence[Mapping[str, Any]], *, params: cand.DetectionParams | None = None
) -> cand.Detection:
    """The unmodified full candidate detector (reference row)."""
    return cand.detect(events, params=params)


def detect_without_campaign_linkage(
    events: Sequence[Mapping[str, Any]], *, params: cand.DetectionParams | None = None
) -> cand.Detection:
    """Candidate without cross-window campaign linkage.

    Evaluates events in isolated windows of width ``probe_window_seconds``
    without linking events across windows into an extended campaign.
    Low-and-slow denials (spaced beyond probe_window_seconds) never accumulate
    within any single window, so the campaign is missed.
    """
    params = params if params is not None else cand.DEFAULT_PARAMS
    validated = cand._validate_events(events)
    if isinstance(validated, cand.Detection):
        return validated

    window_sec = params.probe_window_seconds
    start_ts = validated[0].ts
    end_ts = validated[-1].ts

    best_score = 0.0
    best_evidence: dict[str, Any] = {}

    # Slide by window increments across the session
    current_start = start_ts
    while current_start <= end_ts:
        current_end = current_start + window_sec
        window_events = [e.to_dict() for e in validated if current_start <= e.ts < current_end]
        if window_events:
            det = cand.detect(window_events, params=params)
            if det.decision == cand.DETECT:
                return det
            if det.score > best_score:
                best_score = det.score
                best_evidence = dict(det.evidence)
        current_start += window_sec

    return cand.Detection(
        score=best_score,
        decision=cand.NO_DETECT,
        reason=cand.RC_NO_ALARM,
        evidence=best_evidence or {"window_count": 0, "linkage_ablated": True},
    )


def detect_without_cross_tool_feature(
    events: Sequence[Mapping[str, Any]], *, params: cand.DetectionParams | None = None
) -> cand.Detection:
    """Candidate without cross-tool feature.

    Tool names are masked to a constant, so the detector cannot measure tool
    spread or tool entropy. Cross-tool obfuscation criterion fails.
    """
    params = params if params is not None else cand.DEFAULT_PARAMS
    validated = cand._validate_events(events)
    if isinstance(validated, cand.Detection):
        return validated

    masked_events = [
        {
            "actor_id": e.actor_id,
            "tool": "masked_tool",
            "scope": e.scope,
            "allowed": e.allowed,
            "ts": e.ts,
        }
        for e in validated
    ]
    return cand.detect(masked_events, params=params)


def detect_without_pacing_feature(
    events: Sequence[Mapping[str, Any]], *, params: cand.DetectionParams | None = None
) -> cand.Detection:
    """Candidate without pacing evasion feature.

    probe_window_threshold is set to 1, so any denial causes max_window >= 1,
    making max_window < probe_window_threshold impossible. Pacing evasion
    criterion fails.
    """
    base_params = params if params is not None else cand.DEFAULT_PARAMS
    mutated_params = dataclasses.replace(base_params, probe_window_threshold=1)
    return cand.detect(events, params=mutated_params)


def detect_with_only_per_window_counts(
    events: Sequence[Mapping[str, Any]], *, params: cand.DetectionParams | None = None
) -> cand.Detection:
    """Candidate with ONLY per-window counts (static B0 counting baseline).

    Strips all structural linkage, cross-tool, and pacing criteria, alarming
    solely when the denied count in any sliding window reaches the threshold.
    """
    params = params if params is not None else cand.DEFAULT_PARAMS
    validated = cand._validate_events(events)
    if isinstance(validated, cand.Detection):
        return validated

    denials = [e for e in validated if not e.allowed]
    denied_ts = [e.ts for e in denials]
    max_window = cand._max_denials_in_window(denied_ts, params.probe_window_seconds)

    if max_window >= params.probe_window_threshold:
        return cand.Detection(
            score=1.0,
            decision=cand.DETECT,
            reason=RC_WINDOW_COUNT_THRESHOLD_REACHED,
            evidence={
                "max_window_denials": max_window,
                "probe_window_threshold": params.probe_window_threshold,
                "probe_window_seconds": params.probe_window_seconds,
                "structural_criteria_ablated": True,
            },
        )
    score = round(min(1.0, max_window / params.probe_window_threshold), 12)
    return cand.Detection(
        score=score,
        decision=cand.NO_DETECT,
        reason=cand.RC_NO_ALARM,
        evidence={
            "max_window_denials": max_window,
            "probe_window_threshold": params.probe_window_threshold,
            "probe_window_seconds": params.probe_window_seconds,
            "structural_criteria_ablated": True,
        },
    )


_VARIANT_DETECTORS: Mapping[str, Callable[..., cand.Detection]] = {
    VARIANT_WITHOUT_CAMPAIGN_LINKAGE: detect_without_campaign_linkage,
    VARIANT_WITHOUT_CROSS_TOOL_FEATURE: detect_without_cross_tool_feature,
    VARIANT_WITHOUT_PACING_FEATURE: detect_without_pacing_feature,
    VARIANT_WITH_ONLY_PER_WINDOW_COUNTS: detect_with_only_per_window_counts,
    VARIANT_FULL_CANDIDATE: detect_full_candidate,
}


def detect_variant(
    name: str,
    events: Sequence[Mapping[str, Any]],
    *,
    params: cand.DetectionParams | None = None,
) -> cand.Detection:
    """Run a specific registered ablation variant on an event sequence."""
    refuse_unregistered_variant(name)
    detector = _VARIANT_DETECTORS[name]
    return detector(events, params=params)


# ---------------------------------------------------------------------------
# Task-manifest adapter: run_ablation(name, case) -> Outcome.
# ---------------------------------------------------------------------------


def run_ablation(name: str, case: Mapping[str, Any], ctx: Any = None) -> Outcome:
    """Adapter ``run_ablation(name, case) -> Outcome`` (task-manifest contract).

    DETECT -> ``REJECT`` (alarm raised), NO_DETECT -> ``ADMIT`` (both
    counted_as_success=True); malformed case / invalid events ->
    ``INDETERMINATE``; unregistered variant / nothing-removing identity ->
    ``EXECUTION_ERROR`` with stable reason code.
    """
    try:
        refuse_unregistered_variant(name)
    except AblationError as exc:
        return Outcome(
            observed_outcome=VERDICT_EXECUTION_ERROR,
            counted_as_success=False,
            retriable=False,
            detail=f"{exc.reason_code}: {exc.detail}",
        )

    if not isinstance(case, Mapping):
        return Outcome(
            observed_outcome=VERDICT_INDETERMINATE,
            counted_as_success=False,
            retriable=False,
            detail=RC_MALFORMED_CASE,
        )
    if "events" not in case:
        return Outcome(
            observed_outcome=VERDICT_INDETERMINATE,
            counted_as_success=False,
            retriable=False,
            detail=RC_CASE_EVENTS_MISSING,
        )
    raw_events = case["events"]
    if not isinstance(raw_events, list):
        return Outcome(
            observed_outcome=VERDICT_INDETERMINATE,
            counted_as_success=False,
            retriable=False,
            detail=RC_CASE_EVENTS_NOT_A_LIST,
        )

    detection = detect_variant(name, raw_events)
    if detection.decision == cand.INDETERMINATE:
        return Outcome(
            observed_outcome=VERDICT_INDETERMINATE,
            counted_as_success=False,
            retriable=False,
            detail=detection.reason,
        )
    observed = VERDICT_REJECT if detection.decision == cand.DETECT else VERDICT_ADMIT
    return Outcome(
        observed_outcome=observed,
        counted_as_success=True,
        retriable=False,
        detail=f"{detection.reason}|score={detection.score:.6f}",
    )


# ---------------------------------------------------------------------------
# Frozen fault/control family fixtures (synthetic minimal event streams).
# ---------------------------------------------------------------------------


def _event(actor_id: str, tool: str, scope: str, allowed: bool, ts: int) -> dict[str, Any]:
    return {
        "actor_id": actor_id,
        "tool": tool,
        "scope": scope,
        "allowed": allowed,
        "ts": ts,
    }


def fixture_low_and_slow_cross_tool() -> dict[str, Any]:
    """Crafted low-and-slow cross-tool campaign (ATTACK target).

    9 denials across 9 distinct tools over ~8h logical time, 3700s gaps
    exceeding the 3600s probe window (max 1 denial/window).
    """
    events = [
        _event("actor-adv", f"probe_tool_{i:02d}", "self_care", False, 1000 + 3700 * i)
        for i in range(9)
    ]
    events.append(_event("actor-adv", "med_read", "self_care", True, 1500))
    events.sort(key=lambda e: e["ts"])
    return {"case_id": "DIMVA-CASE-03", "events": events}


def fixture_benign_burst() -> dict[str, Any]:
    """Same-scope denied burst: trips fixed-window count, clean control."""
    events = [
        _event(
            "actor-busy",
            "med_schedule_read" if i % 2 == 0 else "vitals_read",
            "self_care",
            i % 2 == 1,
            5000 + 2 * i,
        )
        for i in range(10)
    ]
    return {"case_id": "DIMVA-CASE-08", "events": events}


def fixture_benign_retry() -> dict[str, Any]:
    """Single legitimate retry after transient failure (BENIGN target)."""
    return {
        "case_id": "DIMVA-CASE-01",
        "events": [
            _event("actor-clean", "med_schedule_read", "self_care", False, 100),
            _event("actor-clean", "med_schedule_read", "self_care", True, 160),
            _event("actor-clean", "vitals_read", "self_care", True, 300),
        ],
    }


def fixture_benign_handoff() -> dict[str, Any]:
    """Authorized care-team handoff across scopes, no denials (BENIGN target)."""
    return {
        "case_id": "DIMVA-CASE-04",
        "events": [
            _event("actor-clinician", "med_schedule_read", "self_care", True, 100),
            _event("actor-clinician", "care_plan_read", "care_team_handoff", True, 200),
            _event("actor-clinician", "care_plan_write", "care_team_handoff", True, 300),
            _event("actor-clinician", "vitals_read", "self_care", True, 400),
        ],
    }


def case_fixtures() -> dict[str, Callable[[], dict[str, Any]]]:
    """Frozen fixture generator mapping for mechanistic verification."""
    return {
        FAMILY_LOW_AND_SLOW_CROSS_TOOL: fixture_low_and_slow_cross_tool,
        FAMILY_BENIGN_BURST: fixture_benign_burst,
        FAMILY_BENIGN_RETRY: fixture_benign_retry,
        FAMILY_BENIGN_HANDOFF: fixture_benign_handoff,
    }


# ---------------------------------------------------------------------------
# Mechanistic inference matrix: preregistered predictions + verification run.
# ---------------------------------------------------------------------------

PREDICTED_VERDICTS: Final[Mapping[tuple[str, str], str]] = {
    # Full candidate (reference row): detects low-and-slow, admits all benign
    (VARIANT_FULL_CANDIDATE, FAMILY_LOW_AND_SLOW_CROSS_TOOL): VERDICT_REJECT,
    (VARIANT_FULL_CANDIDATE, FAMILY_BENIGN_BURST): VERDICT_ADMIT,
    (VARIANT_FULL_CANDIDATE, FAMILY_BENIGN_RETRY): VERDICT_ADMIT,
    (VARIANT_FULL_CANDIDATE, FAMILY_BENIGN_HANDOFF): VERDICT_ADMIT,
    # Without campaign linkage: misses low-and-slow (denials isolated in windows)
    (VARIANT_WITHOUT_CAMPAIGN_LINKAGE, FAMILY_LOW_AND_SLOW_CROSS_TOOL): VERDICT_ADMIT,
    (VARIANT_WITHOUT_CAMPAIGN_LINKAGE, FAMILY_BENIGN_BURST): VERDICT_ADMIT,
    (VARIANT_WITHOUT_CAMPAIGN_LINKAGE, FAMILY_BENIGN_RETRY): VERDICT_ADMIT,
    (VARIANT_WITHOUT_CAMPAIGN_LINKAGE, FAMILY_BENIGN_HANDOFF): VERDICT_ADMIT,
    # Without cross-tool feature: misses low-and-slow (tools masked, distinct=1 < 3)
    (VARIANT_WITHOUT_CROSS_TOOL_FEATURE, FAMILY_LOW_AND_SLOW_CROSS_TOOL): VERDICT_ADMIT,
    (VARIANT_WITHOUT_CROSS_TOOL_FEATURE, FAMILY_BENIGN_BURST): VERDICT_ADMIT,
    (VARIANT_WITHOUT_CROSS_TOOL_FEATURE, FAMILY_BENIGN_RETRY): VERDICT_ADMIT,
    (VARIANT_WITHOUT_CROSS_TOOL_FEATURE, FAMILY_BENIGN_HANDOFF): VERDICT_ADMIT,
    # Without pacing feature: misses low-and-slow (threshold=1 makes max_window < 1 fail)
    (VARIANT_WITHOUT_PACING_FEATURE, FAMILY_LOW_AND_SLOW_CROSS_TOOL): VERDICT_ADMIT,
    (VARIANT_WITHOUT_PACING_FEATURE, FAMILY_BENIGN_BURST): VERDICT_ADMIT,
    (VARIANT_WITHOUT_PACING_FEATURE, FAMILY_BENIGN_RETRY): VERDICT_ADMIT,
    (VARIANT_WITHOUT_PACING_FEATURE, FAMILY_BENIGN_HANDOFF): VERDICT_ADMIT,
    # With only per-window counts: misses low-and-slow AND false-alarms on benign burst
    (VARIANT_WITH_ONLY_PER_WINDOW_COUNTS, FAMILY_LOW_AND_SLOW_CROSS_TOOL): VERDICT_ADMIT,
    (VARIANT_WITH_ONLY_PER_WINDOW_COUNTS, FAMILY_BENIGN_BURST): VERDICT_REJECT,
    (VARIANT_WITH_ONLY_PER_WINDOW_COUNTS, FAMILY_BENIGN_RETRY): VERDICT_ADMIT,
    (VARIANT_WITH_ONLY_PER_WINDOW_COUNTS, FAMILY_BENIGN_HANDOFF): VERDICT_ADMIT,
}


def _degradation_summary(predicted: Mapping[tuple[str, str], str]) -> dict[str, Any]:
    """Summarize missed and false-flagged families per variant relative to reference."""
    summary: dict[str, Any] = {}
    for variant_id in ABLATION_REGISTRY:
        missed = sorted(
            family
            for family in FAULT_FAMILY_IDS
            if predicted[(variant_id, family)] == VERDICT_ADMIT
            and predicted[(REFERENCE_VARIANT_ID, family)] == VERDICT_REJECT
        )
        false_flagged = sorted(
            family
            for family in FAULT_FAMILY_IDS
            if predicted[(variant_id, family)] == VERDICT_REJECT
            and predicted[(REFERENCE_VARIANT_ID, family)] == VERDICT_ADMIT
        )
        summary[variant_id] = {
            "missed_families": missed,
            "false_flagged_families": false_flagged,
            "measurably_degraded": bool(missed or false_flagged),
        }
    return summary


def mechanistic_inference_matrix() -> dict[str, Any]:
    """Preregistered DESIGN RECORD: variant x family predicted verdicts."""
    return {
        "ablations_version": ABLATIONS_VERSION,
        "task_id": ABLATION_TASK_ID,
        "reference_variant": REFERENCE_VARIANT_ID,
        "fault_families": list(FAULT_FAMILY_IDS),
        "variants": {vid: spec.to_dict() for vid, spec in ABLATION_REGISTRY.items()},
        "predicted_verdicts": {
            variant_id: {
                family: PREDICTED_VERDICTS[(variant_id, family)] for family in FAULT_FAMILY_IDS
            }
            for variant_id in ABLATION_REGISTRY
        },
        "degradation_axes": _degradation_summary(PREDICTED_VERDICTS),
        "scale": "DEVELOPMENT (mechanism causality; NOT confirmatory)",
    }


def verify_mechanistic_inference_matrix() -> dict[str, Any]:
    """Run EVERY variant over EVERY frozen fixture family and compare against prediction.

    Any mismatch between observed and predicted verdicts indicates that the
    mechanistic causal narrative is falsified.
    """
    fixtures = case_fixtures()
    cells: list[dict[str, Any]] = []
    all_match = True
    observed_verdicts: dict[tuple[str, str], str] = {}

    for variant_id in ABLATION_REGISTRY:
        for family in FAULT_FAMILY_IDS:
            case = fixtures[family]()
            outcome = run_ablation(variant_id, case)
            observed = outcome.observed_outcome
            predicted = PREDICTED_VERDICTS[(variant_id, family)]
            match = observed == predicted
            all_match = all_match and match
            observed_verdicts[(variant_id, family)] = observed
            cells.append(
                {
                    "variant_id": variant_id,
                    "family_id": family,
                    "predicted": predicted,
                    "observed": observed,
                    "match": match,
                    "detail": outcome.detail,
                }
            )

    return {
        "ablations_version": ABLATIONS_VERSION,
        "all_cells_match": all_match,
        "cell_count": len(cells),
        "cells": cells,
        "observed_verdicts": {
            variant_id: {
                family: observed_verdicts[(variant_id, family)] for family in FAULT_FAMILY_IDS
            }
            for variant_id in ABLATION_REGISTRY
        },
        "observed_degradation": _degradation_summary(observed_verdicts),
        "predicted_degradation": _degradation_summary(PREDICTED_VERDICTS),
        "scale": "DEVELOPMENT (mechanism causality; NOT confirmatory)",
    }


def describe_ablations() -> dict[str, Any]:
    """Machine-readable ablation design record (no empirical results here)."""
    return {
        "ablations_version": ABLATIONS_VERSION,
        "task_id": ABLATION_TASK_ID,
        "phase": "P04 (development-scale mechanism ablation)",
        "candidate_id": cand.CANDIDATE_ID,
        "reference_variant": REFERENCE_VARIANT_ID,
        "registry": {vid: spec.to_dict() for vid, spec in ABLATION_REGISTRY.items()},
        "fault_families": list(FAULT_FAMILY_IDS),
        "manifest_signature": "run_ablation(name: str, case: Mapping) -> Outcome",
        "refusal_codes": [RC_UNKNOWN_ABLATION_VARIANT, RC_VARIANT_REMOVES_NOTHING],
    }


__all__ = [
    "ABLATIONS_VERSION",
    "ABLATION_REGISTRY",
    "ABLATION_TASK_ID",
    "AblationError",
    "FAULT_FAMILY_IDS",
    "PREDICTED_VERDICTS",
    "RC_CASE_EVENTS_MISSING",
    "RC_CASE_EVENTS_NOT_A_LIST",
    "RC_MALFORMED_CASE",
    "RC_UNKNOWN_ABLATION_VARIANT",
    "RC_VARIANT_REMOVES_NOTHING",
    "RC_WINDOW_COUNT_THRESHOLD_REACHED",
    "REFERENCE_VARIANT_ID",
    "VARIANT_FULL_CANDIDATE",
    "VARIANT_WITHOUT_CAMPAIGN_LINKAGE",
    "VARIANT_WITHOUT_CROSS_TOOL_FEATURE",
    "VARIANT_WITHOUT_PACING_FEATURE",
    "VARIANT_WITH_ONLY_PER_WINDOW_COUNTS",
    "VERDICT_ADMIT",
    "VERDICT_EXECUTION_ERROR",
    "VERDICT_INDETERMINATE",
    "VERDICT_REJECT",
    "VariantSpec",
    "case_fixtures",
    "describe_ablations",
    "detect_full_candidate",
    "detect_variant",
    "detect_with_only_per_window_counts",
    "detect_without_campaign_linkage",
    "detect_without_cross_tool_feature",
    "detect_without_pacing_feature",
    "mechanistic_inference_matrix",
    "refuse_unregistered_variant",
    "run_ablation",
    "variant_ids",
    "verify_mechanistic_inference_matrix",
]
