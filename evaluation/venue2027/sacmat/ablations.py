"""SACMAT-ablation — preregistered causal mechanism ablation variants.

Purpose
-------
P04 ablation registry for "PolicyTrace: Temporal Conformance Testing of
Delegated Consent across Heterogeneous Policy Engines"
(``research/venue2027/VENUES/sacmat/RESEARCH_BLUEPRINT.md``, RQ1-RQ3; task
contract ``research/venue2027/VENUES/sacmat/TASKS/SACMAT-ablation.md``). The
P04 candidate (:mod:`evaluation.venue2027.sacmat.candidate`) replays ONE
delegated-consent trace through MULTIPLE heterogeneous policy-engine models
over logical time and reports the first cross-engine divergence. This module
runs the candidate against ITSELF with EXACTLY ONE mechanism removed per
variant, over the SAME frozen synthetic fault families, so each mechanism's
causal contribution to detection is measurable (development-scale mechanism
causality on frozen synthetic cases — never confirmatory results).

Preregistered variants (``ABLATION_REGISTRY``; each is a real callable reusing
the candidate's own components and declares the single ablated mechanism):

- ``static_only`` — baseline WITHOUT the temporal dimension: the trace is
  collapsed to its terminal policy state and every engine evaluates ONCE
  (the candidate's own ``ablation_no_time`` hook). Divergence the terminal
  state has healed is structurally invisible.
- ``no_differential`` — candidate WITHOUT the multi-engine differential: the
  identical temporal replay runs with ONE engine model (the candidate's own
  ``ablation_single_engine`` hook). With no second engine there is no
  pairwise comparison, so cross-engine divergence is unobservable. Its
  predicted blindness on divergence families IS the causal evidence that the
  differential comparison is load-bearing (not a toy: it reuses the
  candidate's preregistered ablation hook verbatim).
- ``no_expiry_check`` — candidate WITHOUT the delegation-expiry check: the
  replay, the three engine models and the pairwise comparison are untouched,
  but every event's ``expiry`` is stripped before replay, so no delegation
  ever lapses. Expiry-family divergence becomes undetectable;
  revocation-family divergence survives (it does not depend on expiry).
- ``common_safety_gate`` — the candidate's pairwise conformance detection is
  REPLACED by the common safety gate every engine already shares: flag
  (REJECT) iff the history contains an explicit REVOKE — context-free,
  engine-free, no temporal reasoning. Catches revocation-family faults,
  misses expiry-family faults, and false-flags clean histories whose
  authority was revoked and then legitimately restored.

The reference row (the unmodified full candidate) is deliberately NOT a
registered variant: a variant that removes nothing is not an ablation.
:func:`refuse_unregistered_variant` refuses unknown ids with
``UNKNOWN_ABLATION_VARIANT`` and nothing-removing identities (the full
candidate) with ``VARIANT_REMOVES_NOTHING`` — fail closed, never silently run
as a degraded or full arm. The mechanistic inference matrix
(:func:`mechanistic_inference_matrix`,
:func:`verify_mechanistic_inference_matrix`) pins every
variant x fault-family verdict against its preregistered prediction.

Allowed input
-------------
:func:`run_ablation(name, case)` (task-manifest signature
``run_ablation(name, case) -> Outcome``): ``name`` is a registered variant id
from :data:`ABLATION_REGISTRY`; ``case`` is one JSON-serializable mapping
``{"case_id": <non-empty str>, "trace": {...}}`` shaped exactly like the
candidate's :func:`candidate.run_candidate` input (or a bare
``{"case_id", "events"}`` mapping, which is itself the trace). The frozen
fault-family fixtures :func:`fault_family_fixtures` build the synthetic
delegated-consent histories (PHI-free; logical-time traces only). All
timestamps are non-negative ints in strictly ascending logical order.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes; no unhandled exception is
ever miscounted as a safe rejection:
- unknown / nothing-removing variant -> ``Outcome(EXECUTION_ERROR)`` carrying
  ``UNKNOWN_ABLATION_VARIANT`` / ``VARIANT_REMOVES_NOTHING`` (the raising
  guard :func:`refuse_unregistered_variant` exposes the same codes).
- malformed case (non-mapping, missing/ill-typed case id, missing trace) ->
  ``EXECUTION_ERROR`` / ``INDETERMINATE`` outcomes, never ``ADMIT`` or
  ``REJECT``.
- data-level trace faults (empty trace, missing logical time,
  unordered/duplicate timestamps, unsupported constructs, malformed
  DELEGATE) surface as the candidate's own ``INDETERMINATE`` conformance
  results, mapped to ``Outcome(INDETERMINATE, counted_as_success=False)``.
- DIVERGENCE -> ``REJECT`` and NO_DIVERGENCE -> ``ADMIT`` (both
  ``counted_as_success=True``).
No wall clock, randomness, network or I/O anywhere; identical inputs give
identical results.

Version
-------
``ABLATIONS_VERSION = "clara.sacmat.ablations-v1"`` (additive-only within 1.x).
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable, Mapping
from typing import Any, Final

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.sacmat import candidate as cand

ABLATIONS_VERSION: Final[str] = "clara.sacmat.ablations-v1"

#: Preregistered ablation variant ids (one mechanism removed each).
VARIANT_STATIC_ONLY: Final[str] = "static_only"
VARIANT_NO_DIFFERENTIAL: Final[str] = "no_differential"
VARIANT_NO_EXPIRY_CHECK: Final[str] = "no_expiry_check"
VARIANT_COMMON_SAFETY_GATE: Final[str] = "common_safety_gate"

#: Reference row: the unmodified candidate. Deliberately NOT registered as an
#: ablation — a variant that removes nothing is not an ablation.
REFERENCE_VARIANT_ID: Final[str] = "full_candidate"

#: Identities known to remove nothing (refused, not guessed).
NON_ABLATION_IDENTITIES: Final[frozenset[str]] = frozenset(
    {REFERENCE_VARIANT_ID, cand.CANDIDATE_ID}
)

#: Stable reason codes (fail closed).
RC_UNKNOWN_ABLATION_VARIANT: Final[str] = "UNKNOWN_ABLATION_VARIANT"
RC_VARIANT_REMOVES_NOTHING: Final[str] = "VARIANT_REMOVES_NOTHING"
RC_CASE_NOT_AN_OBJECT: Final[str] = "CASE_NOT_AN_OBJECT"
RC_CASE_ID_MISSING: Final[str] = "CASE_ID_MISSING"
RC_CASE_ID_NOT_STRING: Final[str] = "CASE_ID_NOT_STRING"
RC_TRACE_MISSING: Final[str] = "TRACE_MISSING"
RC_COMMON_SAFETY_GATE_FLAG: Final[str] = "COMMON_SAFETY_GATE_REVOCATION_FLAG"

#: Frozen fault-family ids (the same suite every variant executes).
FAMILY_HEALED_EXPIRY_DIVERGENCE: Final[str] = "healed_expiry_divergence"
FAMILY_REVOKED_REPLAY_DIVERGENCE: Final[str] = "revoked_replay_divergence"
FAMILY_CLEAN_CONFORMANT: Final[str] = "clean_conformant"
FAMILY_CLEAN_RESTORED_AUTHORITY: Final[str] = "clean_restored_authority"
FAULT_FAMILY_IDS: Final[tuple[str, ...]] = (
    FAMILY_HEALED_EXPIRY_DIVERGENCE,
    FAMILY_REVOKED_REPLAY_DIVERGENCE,
    FAMILY_CLEAN_CONFORMANT,
    FAMILY_CLEAN_RESTORED_AUTHORITY,
)

VERDICT_REJECT: Final[str] = "REJECT"
VERDICT_ADMIT: Final[str] = "ADMIT"

ABLATED_TEMPORAL_DIMENSION: Final[str] = "logical_time_replay"
ABLATED_MULTI_ENGINE_DIFFERENTIAL: Final[str] = "multi_engine_differential_comparison"
ABLATED_EXPIRY_CHECK: Final[str] = "delegation_expiry_check"
ABLATED_CONFORMANCE_DETECTION: Final[str] = "pairwise_conformance_detection"


class AblationError(ValueError):
    """Fail-closed ablation registry error with a stable reason code."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class VariantSpec:
    """One preregistered ablation variant.

    ``ablated_mechanism`` is the DECLARED single mechanism removed; a spec
    that declares no ablated mechanism (empty string) is refused at
    construction — a variant removing nothing is not an ablation.
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


ABLATION_REGISTRY: Final[Mapping[str, VariantSpec]] = {
    spec.variant_id: spec
    for spec in (
        VariantSpec(
            variant_id=VARIANT_STATIC_ONLY,
            title="Baseline without the temporal dimension (static only)",
            ablated_mechanism=ABLATED_TEMPORAL_DIMENSION,
            description=(
                "The trace is collapsed to its TERMINAL policy state and every "
                "engine model evaluates ONCE at the terminal tick (candidate "
                "hook candidate.ablation_no_time); the access request's "
                "decision time and all intermediate ticks are discarded, so a "
                "divergence the terminal state has healed is invisible"
            ),
            expected_effect="misses_healed_temporal_divergence",
            reuses=(
                "candidate.ablation_no_time",
                "candidate.ENGINE_DECIDERS (cedar/openfga/opa models)",
                "candidate._normalize_trace validation",
            ),
            applied_by="candidate_ablation_hook",
        ),
        VariantSpec(
            variant_id=VARIANT_NO_DIFFERENTIAL,
            title="Candidate without the multi-engine differential",
            ablated_mechanism=ABLATED_MULTI_ENGINE_DIFFERENTIAL,
            description=(
                "The identical temporal replay runs with ONE engine model "
                "(candidate hook candidate.ablation_single_engine, pinned to "
                "cedar); with no second engine there is no pairwise "
                "comparison, so cross-engine divergence is structurally "
                "unobservable on every fault family"
            ),
            expected_effect="misses_all_cross_engine_divergence",
            reuses=(
                "candidate.ablation_single_engine",
                "candidate._replay temporal replay",
                "candidate._normalize_trace validation",
            ),
            applied_by="candidate_ablation_hook",
        ),
        VariantSpec(
            variant_id=VARIANT_NO_EXPIRY_CHECK,
            title="Candidate without the delegation-expiry check",
            ablated_mechanism=ABLATED_EXPIRY_CHECK,
            description=(
                "Replay, engine models and pairwise comparison untouched, but "
                "every event's expiry is stripped before replay so no "
                "delegation ever lapses (the candidate's _in_force check "
                "always holds); expiry-family divergence becomes "
                "undetectable while revocation-family divergence survives"
            ),
            expected_effect="misses_expiry_family_divergence",
            reuses=(
                "candidate._normalize_trace validation",
                "candidate._replay temporal replay",
                "candidate.ENGINE_DECIDERS (cedar/openfga/opa models)",
            ),
            applied_by="harness_input_mutation",
        ),
        VariantSpec(
            variant_id=VARIANT_COMMON_SAFETY_GATE,
            title="Candidate replaced by the common safety gate",
            ablated_mechanism=ABLATED_CONFORMANCE_DETECTION,
            description=(
                "Pairwise conformance detection REPLACED by the common safety "
                "gate every engine already shares: REJECT iff the history "
                "contains an explicit REVOKE, else ADMIT — context-free, "
                "engine-free, no temporal reasoning; catches "
                "revocation-family faults, misses expiry-family faults, and "
                "false-flags clean histories whose authority was revoked and "
                "then legitimately restored"
            ),
            expected_effect=("misses_expiry_family_and_false_flags_restored_authority"),
            reuses=("candidate._normalize_trace validation",),
            applied_by="harness_modeled_gate",
        ),
    )
}


def refuse_unregistered_variant(name: str) -> VariantSpec:
    """Guard: return the registered spec for ``name`` or refuse fail-closed.

    Refuses (raises :class:`AblationError`):
    - any id not in :data:`ABLATION_REGISTRY` and not a known nothing-removing
      identity -> ``UNKNOWN_ABLATION_VARIANT`` (never guessed, never silently
      run as the full candidate);
    - known nothing-removing identities (the unmodified full candidate and the
      candidate id itself) -> ``VARIANT_REMOVES_NOTHING``: a variant that
      removes no mechanism is not an ablation.
    """
    spec = ABLATION_REGISTRY.get(name)
    if spec is not None:
        return spec
    if name in NON_ABLATION_IDENTITIES:
        raise AblationError(
            RC_VARIANT_REMOVES_NOTHING,
            f"{name!r} is the unmodified candidate and removes no mechanism; "
            "run candidate.conformance_test directly for the reference row",
        )
    raise AblationError(
        RC_UNKNOWN_ABLATION_VARIANT,
        f"variant {name!r} not in registry {sorted(ABLATION_REGISTRY)}",
    )


def variant_ids() -> tuple[str, ...]:
    """Registered ablation variant ids in canonical (registry) order."""
    return tuple(ABLATION_REGISTRY)


# ---------------------------------------------------------------------------
# Frozen fault-family fixtures (synthetic delegated-consent histories).
# ---------------------------------------------------------------------------


def _fixture_healed_expiry_divergence() -> dict[str, Any]:
    """Divergence ONLY at the access tick, healed by a later grant.

    patient-d's care_team delegation from patient-e lapses at tick 2000; the
    ACCESS at tick 2500 falls AFTER expiry (cedar permits — expiry is
    caller-encoded — while openfga's read-time walk finds the expired tuple
    absent and denies). A direct grant at tick 3000 heals the terminal state,
    so every terminal-state evaluation sees all engines agree.
    """
    return {
        "trace_id": "SACMAT-ABL-HEALED-EXPIRY",
        "events": [
            {
                "kind": "GRANT",
                "principal": "patient-e",
                "tenant": "t1",
                "resource": "record-1",
                "purpose": "care_team",
                "logical_time": 100,
                "expiry": 9000,
            },
            {
                "kind": "DELEGATE",
                "principal": "patient-d",
                "tenant": "t1",
                "resource": "record-1",
                "purpose": "care_team",
                "policy_state": "patient-e",
                "logical_time": 200,
                "expiry": 2000,
            },
            {
                "kind": "ACCESS",
                "principal": "patient-d",
                "tenant": "t1",
                "resource": "record-1",
                "purpose": "care_team",
                "logical_time": 2500,
            },
            {
                "kind": "GRANT",
                "principal": "patient-d",
                "tenant": "t1",
                "resource": "record-1",
                "purpose": "care_team",
                "logical_time": 3000,
                "expiry": 9000,
            },
        ],
    }


def _fixture_revoked_replay_divergence() -> dict[str, Any]:
    """Access AFTER the delegating source was revoked: unhealed divergence.

    cedar treats a delegation from a revoked source as NOT_APPLICABLE while
    openfga/opa deny the dangling walk — a semantic divergence still visible
    in the terminal state (no healing grant exists).
    """
    return {
        "trace_id": "SACMAT-ABL-REVOKED-REPLAY",
        "events": [
            {
                "kind": "GRANT",
                "principal": "patient-f",
                "tenant": "t1",
                "resource": "record-1",
                "purpose": "self_care",
                "logical_time": 100,
                "expiry": 9000,
            },
            {
                "kind": "REVOKE",
                "principal": "patient-f",
                "tenant": "t1",
                "resource": "record-1",
                "purpose": "self_care",
                "logical_time": 500,
            },
            {
                "kind": "DELEGATE",
                "principal": "nurse-g",
                "tenant": "t1",
                "resource": "record-1",
                "purpose": "self_care",
                "policy_state": "patient-f",
                "logical_time": 600,
            },
            {
                "kind": "ACCESS",
                "principal": "nurse-g",
                "tenant": "t1",
                "resource": "record-1",
                "purpose": "self_care",
                "logical_time": 1000,
            },
        ],
    }


def _fixture_clean_conformant() -> dict[str, Any]:
    """Conformant history: every engine agrees at every evaluated tick."""
    return {
        "trace_id": "SACMAT-ABL-CLEAN-CONFORMANT",
        "events": [
            {
                "kind": "GRANT",
                "principal": "patient-a",
                "tenant": "t1",
                "resource": "record-1",
                "purpose": "self_care",
                "logical_time": 100,
                "expiry": 9000,
            },
            {
                "kind": "GRANT",
                "principal": "patient-b",
                "tenant": "t1",
                "resource": "record-1",
                "purpose": "care_team",
                "logical_time": 110,
                "expiry": 9000,
            },
            {
                "kind": "DELEGATE",
                "principal": "nurse-c",
                "tenant": "t1",
                "resource": "record-1",
                "purpose": "care_team",
                "policy_state": "patient-b",
                "logical_time": 120,
            },
            {
                "kind": "ACCESS",
                "principal": "patient-a",
                "tenant": "t1",
                "resource": "record-1",
                "purpose": "self_care",
                "logical_time": 500,
            },
            {
                "kind": "ACCESS",
                "principal": "nurse-c",
                "tenant": "t1",
                "resource": "record-1",
                "purpose": "care_team",
                "logical_time": 502,
            },
        ],
    }


def _fixture_clean_restored_authority() -> dict[str, Any]:
    """Conformant history whose authority was revoked then re-granted.

    The terminal state is a grant in force at the access tick, so the full
    candidate ADMITs (all engines agree PERMIT) — but the common safety gate,
    which keys on the mere presence of a REVOKE, false-flags it.
    """
    return {
        "trace_id": "SACMAT-ABL-CLEAN-RESTORED",
        "events": [
            {
                "kind": "GRANT",
                "principal": "patient-h",
                "tenant": "t1",
                "resource": "record-1",
                "purpose": "self_care",
                "logical_time": 100,
                "expiry": 9000,
            },
            {
                "kind": "REVOKE",
                "principal": "patient-h",
                "tenant": "t1",
                "resource": "record-1",
                "purpose": "self_care",
                "logical_time": 1500,
            },
            {
                "kind": "GRANT",
                "principal": "patient-h",
                "tenant": "t1",
                "resource": "record-1",
                "purpose": "self_care",
                "logical_time": 1600,
                "expiry": 9000,
            },
            {
                "kind": "ACCESS",
                "principal": "patient-h",
                "tenant": "t1",
                "resource": "record-1",
                "purpose": "self_care",
                "logical_time": 2000,
            },
        ],
    }


def fault_family_fixtures() -> Mapping[str, Callable[[], dict[str, Any]]]:
    """Frozen fault-family fixture builders (fresh dict per call)."""
    return {
        FAMILY_HEALED_EXPIRY_DIVERGENCE: _fixture_healed_expiry_divergence,
        FAMILY_REVOKED_REPLAY_DIVERGENCE: _fixture_revoked_replay_divergence,
        FAMILY_CLEAN_CONFORMANT: _fixture_clean_conformant,
        FAMILY_CLEAN_RESTORED_AUTHORITY: _fixture_clean_restored_authority,
    }


# ---------------------------------------------------------------------------
# Preregistered mechanistic inference matrix (predictions BEFORE execution).
# ---------------------------------------------------------------------------

#: (variant_id, family_id) -> preregistered verdict. Derived from each
#: variant's declared mechanism semantics; pinned before any run. The
#: reference row (full candidate) is the detection ceiling the ablations are
#: compared against.
PREDICTED_VERDICTS: Final[Mapping[tuple[str, str], str]] = {
    (REFERENCE_VARIANT_ID, FAMILY_HEALED_EXPIRY_DIVERGENCE): VERDICT_REJECT,
    (REFERENCE_VARIANT_ID, FAMILY_REVOKED_REPLAY_DIVERGENCE): VERDICT_REJECT,
    (REFERENCE_VARIANT_ID, FAMILY_CLEAN_CONFORMANT): VERDICT_ADMIT,
    (REFERENCE_VARIANT_ID, FAMILY_CLEAN_RESTORED_AUTHORITY): VERDICT_ADMIT,
    (VARIANT_STATIC_ONLY, FAMILY_HEALED_EXPIRY_DIVERGENCE): VERDICT_ADMIT,
    (VARIANT_STATIC_ONLY, FAMILY_REVOKED_REPLAY_DIVERGENCE): VERDICT_REJECT,
    (VARIANT_STATIC_ONLY, FAMILY_CLEAN_CONFORMANT): VERDICT_ADMIT,
    (VARIANT_STATIC_ONLY, FAMILY_CLEAN_RESTORED_AUTHORITY): VERDICT_ADMIT,
    (VARIANT_NO_DIFFERENTIAL, FAMILY_HEALED_EXPIRY_DIVERGENCE): VERDICT_ADMIT,
    (VARIANT_NO_DIFFERENTIAL, FAMILY_REVOKED_REPLAY_DIVERGENCE): VERDICT_ADMIT,
    (VARIANT_NO_DIFFERENTIAL, FAMILY_CLEAN_CONFORMANT): VERDICT_ADMIT,
    (VARIANT_NO_DIFFERENTIAL, FAMILY_CLEAN_RESTORED_AUTHORITY): VERDICT_ADMIT,
    (VARIANT_NO_EXPIRY_CHECK, FAMILY_HEALED_EXPIRY_DIVERGENCE): VERDICT_ADMIT,
    (VARIANT_NO_EXPIRY_CHECK, FAMILY_REVOKED_REPLAY_DIVERGENCE): VERDICT_REJECT,
    (VARIANT_NO_EXPIRY_CHECK, FAMILY_CLEAN_CONFORMANT): VERDICT_ADMIT,
    (VARIANT_NO_EXPIRY_CHECK, FAMILY_CLEAN_RESTORED_AUTHORITY): VERDICT_ADMIT,
    (VARIANT_COMMON_SAFETY_GATE, FAMILY_HEALED_EXPIRY_DIVERGENCE): VERDICT_ADMIT,
    (VARIANT_COMMON_SAFETY_GATE, FAMILY_REVOKED_REPLAY_DIVERGENCE): VERDICT_REJECT,
    (VARIANT_COMMON_SAFETY_GATE, FAMILY_CLEAN_CONFORMANT): VERDICT_ADMIT,
    (VARIANT_COMMON_SAFETY_GATE, FAMILY_CLEAN_RESTORED_AUTHORITY): VERDICT_REJECT,
}


# ---------------------------------------------------------------------------
# Variant runners (each reuses candidate components; one mechanism removed).
# ---------------------------------------------------------------------------


def _run_static_only(trace: Any) -> cand.ConformanceResult:
    """Ablated mechanism: logical-time replay (temporal dimension)."""
    result = cand.ablation_no_time(trace)
    return dataclasses.replace(result, ablation=VARIANT_STATIC_ONLY)


def _run_no_differential(trace: Any) -> cand.ConformanceResult:
    """Ablated mechanism: multi-engine differential comparison."""
    result = cand.ablation_single_engine(trace, engine=cand.ENGINE_CEDAR)
    return dataclasses.replace(result, ablation=VARIANT_NO_DIFFERENTIAL)


def _run_no_expiry_check(trace: Any) -> cand.ConformanceResult:
    """Ablated mechanism: delegation-expiry check (expiries stripped)."""
    trace_id, events, error = cand._normalize_trace(trace)
    if error:
        return cand.ConformanceResult(
            candidate_id=cand.CANDIDATE_ID,
            candidate_version=cand.CANDIDATE_VERSION,
            status=cand.STATUS_INDETERMINATE,
            reason_code=error,
            trace_id=trace_id,
            engines=cand.ENGINE_MODELS,
            ablation=VARIANT_NO_EXPIRY_CHECK,
            detail=f"fail_closed|{error}",
        )
    stripped = [dict(entry, expiry=None) for entry in events]
    replayed = cand._replay(stripped, cand.ENGINE_MODELS, trace_id)
    return dataclasses.replace(replayed, ablation=VARIANT_NO_EXPIRY_CHECK)


def _run_common_safety_gate(trace: Any) -> cand.ConformanceResult:
    """Ablated mechanism: pairwise conformance detection (common gate instead).

    The gate is the explicit-revocation deny every engine model already
    implements, evaluated ONCE over the validated history: any REVOKE on
    record -> REJECT, else ADMIT. No replay, no engines, no temporal
    reasoning. A trace that fails validation is INDETERMINATE (the gate must
    never silently admit an unvalidatable history).
    """
    trace_id, events, error = cand._normalize_trace(trace)
    if error:
        return cand.ConformanceResult(
            candidate_id=cand.CANDIDATE_ID,
            candidate_version=cand.CANDIDATE_VERSION,
            status=cand.STATUS_INDETERMINATE,
            reason_code=error,
            trace_id=trace_id,
            engines=(),
            ablation=VARIANT_COMMON_SAFETY_GATE,
            detail=f"fail_closed|{error}",
        )
    witnesses = tuple(
        entry["logical_time"] for entry in events if entry["kind"] == cand.EVENT_REVOKE
    )
    if witnesses:
        return cand.ConformanceResult(
            candidate_id=cand.CANDIDATE_ID,
            candidate_version=cand.CANDIDATE_VERSION,
            status=cand.STATUS_DIVERGENCE,
            reason_code=RC_COMMON_SAFETY_GATE_FLAG,
            trace_id=trace_id,
            engines=(),
            divergence_time=witnesses[0],
            ablation=VARIANT_COMMON_SAFETY_GATE,
            detail=f"common_gate|explicit_revocation_at={list(witnesses)}",
        )
    return cand.ConformanceResult(
        candidate_id=cand.CANDIDATE_ID,
        candidate_version=cand.CANDIDATE_VERSION,
        status=cand.STATUS_NO_DIVERGENCE,
        reason_code=cand.RC_NO_DIVERGENCE,
        trace_id=trace_id,
        engines=(),
        ablation=VARIANT_COMMON_SAFETY_GATE,
        detail="common_gate|no_explicit_revocation_on_record",
    )


_VARIANT_RUNNERS: Final[Mapping[str, Callable[[Any], cand.ConformanceResult]]] = {
    VARIANT_STATIC_ONLY: _run_static_only,
    VARIANT_NO_DIFFERENTIAL: _run_no_differential,
    VARIANT_NO_EXPIRY_CHECK: _run_no_expiry_check,
    VARIANT_COMMON_SAFETY_GATE: _run_common_safety_gate,
}


def run_variant_trace(variant_id: str, trace: Any) -> cand.ConformanceResult:
    """Run ONE registered ablation variant on ONE trace (no Outcome mapping).

    The variant guard :func:`refuse_unregistered_variant` is applied first, so
    unknown ids and nothing-removing identities raise :class:`AblationError`
    with a stable reason code. Candidate wiring errors
    (:class:`candidate.TemporalConformanceError`) propagate unchanged.
    """
    refuse_unregistered_variant(variant_id)
    return _VARIANT_RUNNERS[variant_id](trace)


# ---------------------------------------------------------------------------
# Task-manifest signature adapter: run_ablation(name, case) -> Outcome.
# ---------------------------------------------------------------------------


def _outcome(observed_outcome: str, counted_as_success: bool, detail: str) -> Outcome:
    return Outcome(
        observed_outcome=observed_outcome,
        counted_as_success=counted_as_success,
        retriable=False,
        detail=detail,
    )


def _refusal_outcome(exc: AblationError) -> Outcome:
    return _outcome("EXECUTION_ERROR", False, f"{exc.reason_code}: {exc.detail}")


def _extract_trace(case: Mapping[str, Any]) -> tuple[Any, str | None]:
    """Extract the trace payload from a case mapping (run_candidate shape)."""
    if "trace" in case:
        return case["trace"], None
    if "events" in case:
        return case, None
    return None, RC_TRACE_MISSING


def run_ablation(name: str, case: Mapping[str, Any]) -> Outcome:
    """Task-manifest signature: run ONE ablation variant on ONE case.

    - Determined outcomes: DIVERGENCE -> ``REJECT`` and NO_DIVERGENCE ->
      ``ADMIT`` (both ``counted_as_success=True``); the ``detail`` JSON carries
      the variant id, the declared ablated mechanism, the conformance status,
      the reason code and the divergence time.
    - Fail closed: unknown variant or nothing-removing identity ->
      ``EXECUTION_ERROR`` with ``UNKNOWN_ABLATION_VARIANT`` /
      ``VARIANT_REMOVES_NOTHING``; malformed case -> ``EXECUTION_ERROR`` /
      ``INDETERMINATE`` (never ``ADMIT``/``REJECT``, never counted);
      candidate wiring errors surface as ``EXECUTION_ERROR`` carrying the
      candidate's stable reason code.
    """
    try:
        spec = refuse_unregistered_variant(name)
    except AblationError as exc:
        return _refusal_outcome(exc)
    if not isinstance(case, Mapping):
        return _outcome(
            "EXECUTION_ERROR",
            False,
            f"{RC_CASE_NOT_AN_OBJECT}: case must be a mapping, got {type(case).__name__}",
        )
    case_id = case.get("case_id")
    if case_id is None:
        return _outcome("INDETERMINATE", False, f"{ABLATIONS_VERSION}|{RC_CASE_ID_MISSING}")
    if not isinstance(case_id, str) or not case_id:
        return _outcome("INDETERMINATE", False, f"{ABLATIONS_VERSION}|{RC_CASE_ID_NOT_STRING}")
    trace, error = _extract_trace(case)
    if error is not None:
        return _outcome("INDETERMINATE", False, f"{ABLATIONS_VERSION}|{error}")
    try:
        result = _VARIANT_RUNNERS[name](trace)
    except cand.TemporalConformanceError as exc:
        return _outcome(
            "EXECUTION_ERROR", False, f"{ABLATIONS_VERSION}|{exc.reason_code}: {exc.detail}"
        )
    if result.status == cand.STATUS_DIVERGENCE:
        observed, counted = VERDICT_REJECT, True
    elif result.status == cand.STATUS_NO_DIVERGENCE:
        observed, counted = VERDICT_ADMIT, True
    else:
        observed, counted = "INDETERMINATE", False
    detail = json.dumps(
        {
            "ablations_version": ABLATIONS_VERSION,
            "variant_id": name,
            "ablated_mechanism": spec.ablated_mechanism,
            "case_id": case_id,
            "status": result.status,
            "reason_code": result.reason_code,
            "divergence_time": result.divergence_time,
            "engines": list(result.engines),
        },
        sort_keys=True,
    )
    return _outcome(observed, counted, detail)


# ---------------------------------------------------------------------------
# Mechanistic inference matrix: preregistered predictions + verification run.
# ---------------------------------------------------------------------------


def _run_reference(trace: Any) -> cand.ConformanceResult:
    """The unmodified candidate (reference row; not an ablation)."""
    return cand.conformance_test(trace)


def _observed_verdict(result: cand.ConformanceResult) -> str:
    if result.status == cand.STATUS_DIVERGENCE:
        return VERDICT_REJECT
    if result.status == cand.STATUS_NO_DIVERGENCE:
        return VERDICT_ADMIT
    return "INDETERMINATE"


def _degradation_summary(predicted: Mapping[tuple[str, str], str]) -> dict[str, Any]:
    """Families where an ablation's verdict degrades vs the reference row."""
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
    """Preregistered DESIGN RECORD: variant x family predicted verdicts.

    Predictions are frozen constants (:data:`PREDICTED_VERDICTS`) derived from
    each variant's declared mechanism semantics BEFORE any execution
    (prespecified, per the task contract). No results live here.
    """
    return {
        "ablations_version": ABLATIONS_VERSION,
        "reference_variant": REFERENCE_VARIANT_ID,
        "fault_families": list(FAULT_FAMILY_IDS),
        "variants": {vid: spec.to_dict() for vid, spec in ABLATION_REGISTRY.items()},
        "predicted_verdicts": {
            variant_id: {
                family: PREDICTED_VERDICTS[(variant_id, family)] for family in FAULT_FAMILY_IDS
            }
            for variant_id in (REFERENCE_VARIANT_ID, *ABLATION_REGISTRY)
        },
        "degradation_axes": _degradation_summary(PREDICTED_VERDICTS),
        "scale": "DEVELOPMENT (mechanism causality; NOT confirmatory)",
    }


def verify_mechanistic_inference_matrix() -> dict[str, Any]:
    """Run EVERY variant over EVERY frozen fault family and compare.

    Each cell executes the variant on the family fixture (fresh dict per
    call), maps the conformance verdict to REJECT/ADMIT/INDETERMINATE and
    compares against the preregistered prediction. Any mismatch means the
    mechanistic story is falsified and must be resolved before the ablation
    registry may be used — never repaired post hoc to match an observed run.
    """
    fixtures = fault_family_fixtures()
    cells: list[dict[str, Any]] = []
    all_match = True
    runners: dict[str, Callable[[Any], cand.ConformanceResult]] = {
        REFERENCE_VARIANT_ID: _run_reference,
        **_VARIANT_RUNNERS,
    }
    observed_verdicts: dict[tuple[str, str], str] = {}
    for variant_id, runner in runners.items():
        for family in FAULT_FAMILY_IDS:
            result = runner(fixtures[family]())
            observed = _observed_verdict(result)
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
                    "status": result.status,
                    "reason_code": result.reason_code,
                    "divergence_time": result.divergence_time,
                }
            )
    observed_degradation = _degradation_summary(observed_verdicts)
    return {
        "ablations_version": ABLATIONS_VERSION,
        "all_cells_match": all_match,
        "cell_count": len(cells),
        "cells": cells,
        "observed_verdicts": {
            variant_id: {
                family: observed_verdicts[(variant_id, family)] for family in FAULT_FAMILY_IDS
            }
            for variant_id in runners
        },
        "observed_degradation": observed_degradation,
        "predicted_degradation": _degradation_summary(PREDICTED_VERDICTS),
        "scale": "DEVELOPMENT (mechanism causality; NOT confirmatory)",
    }


def describe_ablations() -> dict[str, Any]:
    """Machine-readable ablation design record (no empirical results here)."""
    return {
        "ablations_version": ABLATIONS_VERSION,
        "task_id": "SACMAT-ablation",
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
    "AblationError",
    "FAULT_FAMILY_IDS",
    "PREDICTED_VERDICTS",
    "REFERENCE_VARIANT_ID",
    "RC_UNKNOWN_ABLATION_VARIANT",
    "RC_VARIANT_REMOVES_NOTHING",
    "VARIANT_COMMON_SAFETY_GATE",
    "VARIANT_NO_DIFFERENTIAL",
    "VARIANT_NO_EXPIRY_CHECK",
    "VARIANT_STATIC_ONLY",
    "VariantSpec",
    "describe_ablations",
    "fault_family_fixtures",
    "mechanistic_inference_matrix",
    "refuse_unregistered_variant",
    "run_ablation",
    "run_variant_trace",
    "variant_ids",
    "verify_mechanistic_inference_matrix",
]
