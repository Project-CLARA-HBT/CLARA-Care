"""Tests for SACMAT-candidate — temporal conformance testing mechanism.

Positive controls (the mechanism runs end to end on synthetic traces):
- A conformant trace (grant in force at the access tick, one delegation
  chain, no expiry race) yields NO_DIVERGENCE: every heterogeneous engine
  model agrees at every evaluated tick.
- An expiry-divergence trace (grant expiring strictly between the grant tick
  and the access tick, healed by a later revoke) yields DIVERGENCE at the
  EXACT logical tick of the access request, naming the disagreeing engine
  pair (cedar vs openfga) and both decisions.
- A revoked-before-replay trace (access after revoke) also diverges at its
  exact tick (cedar DENYs via compiled forbid; cedar-permit semantics differ
  from openfga's two-valued walk — every pairwise disagreement is a witness).
- run_candidate maps DIVERGENCE -> REJECT and NO_DIVERGENCE -> ADMIT (both
  counted_as_success=True); NOT_RUN_EXTERNAL / BASELINE_UNAVAILABLE under
  simulate_unavailable_upstream; malformed cases -> INDETERMINATE.
- Determinism: identical inputs give identical results (dict-free iteration
  order, fixed engine comparison order).

Adversarial controls (each ablation proves one mechanism component is
load-bearing):
- ablation_single_engine: the SAME expiry-divergence trace replayed with ONE
  engine MISSES the divergence (NO_DIVERGENCE) — no pairwise comparison, no
  conformance property.
- ablation_no_time: all engines but evaluated ONLY on the terminal state —
  the healed expiry divergence is MISSED (NO_DIVERGENCE), because the
  terminal revoke has already removed the tuple the engines disagree about.
- INDETERMINATE fail-closed: empty trace, missing logical time, unordered /
  duplicate timestamps, unknown event kind, unsupported construct, malformed
  DELEGATE payload — never a silent safe verdict.
- Wiring errors fail closed with stable reason codes: unknown engine id,
  non-sequence engines, insufficient engines (< 2), unrecognized trace input,
  non-mapping case.

Failure semantics: every adversarial result is a first-class
ConformanceResult / Outcome, never an unhandled exception miscounted as a
safe rejection (wiring errors are the documented exception and raise).
"""

from __future__ import annotations

import dataclasses

import pytest

from evaluation.venue2027.sacmat.candidate import (
    ABLATION_NO_TIME,
    ABLATION_SINGLE_ENGINE,
    CANDIDATE_ID,
    CANDIDATE_VERSION,
    DECISION_DENY,
    DECISION_NOT_APPLICABLE,
    DECISION_PERMIT,
    ENGINE_CEDAR,
    ENGINE_MODELS,
    ENGINE_OPA,
    ENGINE_OPENFGA,
    RC_ABLATION_NO_TIME,
    RC_ABLATION_SINGLE_ENGINE,
    RC_BASELINE_UNAVAILABLE,
    RC_CASE_ID_MISSING,
    RC_CASE_NOT_AN_OBJECT,
    RC_DUPLICATE_TIMESTAMP,
    RC_EMPTY_TRACE,
    RC_ENGINES_NOT_A_SEQUENCE,
    RC_INSUFFICIENT_ENGINES,
    RC_MISSING_LOGICAL_TIME,
    RC_NO_DIVERGENCE,
    RC_TEMPORAL_CONFORMANCE_DIVERGENCE,
    RC_TRACE_INPUT_UNRECOGNIZED,
    RC_TRACE_MISSING,
    RC_UNKNOWN_ENGINE,
    RC_UNORDERED_TIMESTAMPS,
    RC_UNSUPPORTED_CONSTRUCT,
    TemporalConformanceError,
    ablation_no_time,
    ablation_single_engine,
    conformance_test,
    describe_mechanism,
    run_candidate,
)

# ---------------------------------------------------------------------------
# Trace fixtures (synthetic delegated-consent histories in logical time).
# ---------------------------------------------------------------------------


def _grant(
    tick: int,
    principal: str,
    purpose: str = "self_care",
    tenant: str = "t1",
    resource: str = "record-1",
    expiry: int | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "kind": "GRANT",
        "principal": principal,
        "tenant": tenant,
        "resource": resource,
        "purpose": purpose,
        "logical_time": tick,
    }
    if expiry is not None:
        payload["expiry"] = expiry
    return payload


def _revoke(
    tick: int,
    principal: str,
    purpose: str = "self_care",
    tenant: str = "t1",
    resource: str = "record-1",
) -> dict[str, object]:
    return {
        "kind": "REVOKE",
        "principal": principal,
        "tenant": tenant,
        "resource": resource,
        "purpose": purpose,
        "logical_time": tick,
    }


def _delegate(
    tick: int,
    principal: str,
    source: str,
    purpose: str = "self_care",
    tenant: str = "t1",
    resource: str = "record-1",
    expiry: int | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "kind": "DELEGATE",
        "principal": principal,
        "tenant": tenant,
        "resource": resource,
        "purpose": purpose,
        "policy_state": source,
        "logical_time": tick,
    }
    if expiry is not None:
        payload["expiry"] = expiry
    return payload


def _access(
    tick: int,
    principal: str,
    purpose: str = "self_care",
    tenant: str = "t1",
    resource: str = "record-1",
) -> dict[str, object]:
    return {
        "kind": "ACCESS",
        "principal": principal,
        "tenant": tenant,
        "resource": resource,
        "purpose": purpose,
        "logical_time": tick,
    }


def _conformant_trace() -> dict[str, object]:
    """Grant in force at the access tick plus an intact delegation chain."""
    return {
        "trace_id": "SACMAT-CT-CONFORMANT",
        "events": [
            _grant(100, "patient-a", expiry=9000),
            _grant(110, "patient-b", purpose="care_team", expiry=9000),
            _delegate(120, "nurse-c", "patient-b", purpose="care_team"),
            _access(500, "patient-a"),
            _access(501, "patient-b", purpose="care_team"),
            _access(502, "nurse-c", purpose="care_team"),
        ],
    }


def _expiry_divergence_trace() -> dict[str, object]:
    """Divergence ONLY at the exact access tick, healed in the terminal state.

    patient-d's care_team delegation from patient-e lapses at tick 2000. The
    ACCESS at tick 2500 falls AFTER expiry: cedar permits (expiry is
    caller-encoded, the delegation tuple still exists) while openfga's
    read-time walk finds the expired tuple absent and DENIES. A later GRANT
    restoring patient-d directly at tick 3000 heals the terminal state — the
    healed grant is in force at the terminal tick under every model, so any
    terminal-state evaluation sees all three engines agree (invisible to
    every static diff and every no-time ablation).
    """
    return {
        "trace_id": "SACMAT-CT-EXPIRY-DIVERGENCE",
        "events": [
            _grant(100, "patient-e", purpose="care_team", expiry=9000),
            _delegate(200, "patient-d", "patient-e", purpose="care_team", expiry=2000),
            _access(2500, "patient-d", purpose="care_team"),
            _grant(3000, "patient-d", purpose="care_team", expiry=9000),
        ],
    }


def _revoked_replay_trace() -> dict[str, object]:
    """Access AFTER the delegating source was revoked: divergence at the tick.

    cedar treats a delegation from a revoked source as NOT_APPLICABLE (the
    inherited authority simply does not exist in the compiled policy set),
    while openfga/opa deny the dangling walk — a semantic portability
    divergence materialized at the exact access tick.
    """
    return {
        "trace_id": "SACMAT-CT-REVOKED-REPLAY",
        "events": [
            _grant(100, "patient-f", expiry=9000),
            _revoke(500, "patient-f"),
            _delegate(600, "nurse-g", "patient-f"),
            _access(1000, "nurse-g"),
        ],
    }


# ---------------------------------------------------------------------------
# Positive controls.
# ---------------------------------------------------------------------------


def test_conformant_trace_reports_no_divergence() -> None:
    result = conformance_test(_conformant_trace())
    assert result.status == "NO_DIVERGENCE"
    assert result.reason_code == RC_NO_DIVERGENCE
    assert result.divergence_time is None
    assert result.engine_a is None and result.engine_b is None
    assert result.engines == ENGINE_MODELS
    assert len(result.timeline) == 3
    for entry in result.timeline:
        assert len(set(entry["decisions"].values())) == 1


def test_expiry_divergence_detected_at_exact_tick() -> None:
    result = conformance_test(_expiry_divergence_trace())
    assert result.status == "DIVERGENCE"
    assert result.reason_code == RC_TEMPORAL_CONFORMANCE_DIVERGENCE
    assert result.divergence_time == 2500
    assert {result.engine_a, result.engine_b} == {ENGINE_CEDAR, ENGINE_OPENFGA}
    assert result.decision_a == DECISION_PERMIT and result.decision_b == DECISION_DENY
    assert result.timeline[-1]["decisions"][ENGINE_CEDAR] == DECISION_PERMIT
    assert result.timeline[-1]["decisions"][ENGINE_OPENFGA] == DECISION_DENY


def test_revoked_replay_divergence_detected_at_exact_tick() -> None:
    result = conformance_test(_revoked_replay_trace())
    assert result.status == "DIVERGENCE"
    assert result.divergence_time == 1000
    assert {result.engine_a, result.engine_b} == {ENGINE_CEDAR, ENGINE_OPENFGA}
    assert result.decision_a == DECISION_NOT_APPLICABLE
    assert result.decision_b == DECISION_DENY


def test_delegation_chain_permit_agreement() -> None:
    """A delegate whose source grant is in force permits under all models."""
    trace = {
        "trace_id": "SACMAT-CT-CHAIN",
        "events": [
            _grant(100, "patient-e", purpose="care_team", expiry=9000),
            _delegate(200, "patient-d", "patient-e", purpose="care_team"),
            _access(300, "patient-d", purpose="care_team"),
        ],
    }
    result = conformance_test(trace)
    assert result.status == "NO_DIVERGENCE"
    assert result.timeline[0]["decisions"] == {engine: DECISION_PERMIT for engine in ENGINE_MODELS}


def test_run_candidate_maps_reject_admit_indeterminate() -> None:
    reject = run_candidate({"case_id": "C1", "trace": _expiry_divergence_trace()})
    assert reject.observed_outcome == "REJECT" and reject.counted_as_success is True
    admit = run_candidate({"case_id": "C2", "trace": _conformant_trace()})
    assert admit.observed_outcome == "ADMIT" and admit.counted_as_success is True


def test_run_candidate_not_run_external_when_upstream_unavailable() -> None:
    class Ctx:
        simulate_unavailable_upstream = True

    outcome = run_candidate({"case_id": "C3", "trace": _conformant_trace()}, Ctx())
    assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
    assert outcome.counted_as_success is False
    assert outcome.retriable is True
    assert RC_BASELINE_UNAVAILABLE in outcome.detail


def test_run_candidate_malformed_cases_fail_closed() -> None:
    assert run_candidate({"trace": _conformant_trace()}).detail.endswith(RC_CASE_ID_MISSING)
    assert run_candidate({"case_id": "", "trace": _conformant_trace()}).detail.endswith(
        "CASE_ID_NOT_STRING"
    )
    assert run_candidate({"case_id": "C4"}).detail.endswith(RC_TRACE_MISSING)
    assert run_candidate({"case_id": "C5", "trace": {"events": []}}).detail.endswith(RC_EMPTY_TRACE)


def test_determinism_byte_identical_results() -> None:
    first = conformance_test(_expiry_divergence_trace())
    second = conformance_test(_expiry_divergence_trace())
    assert first == second
    assert dataclasses.asdict(first) == dataclasses.asdict(second)
    clean_first = conformance_test(_conformant_trace())
    clean_second = conformance_test(_conformant_trace())
    assert clean_first.to_dict() == clean_second.to_dict()


def test_describe_mechanism_is_serializable_and_complete() -> None:
    description = describe_mechanism()
    assert description["candidate_id"] == CANDIDATE_ID
    assert description["candidate_version"] == CANDIDATE_VERSION
    assert set(ABLATION_SINGLE_ENGINE and description["ablations"]) == {
        ABLATION_SINGLE_ENGINE,
        ABLATION_NO_TIME,
    }
    assert set(description["engine_models"]) == set(ENGINE_MODELS)
    assert "PERMIT" in description["decision_vocabulary"]


# ---------------------------------------------------------------------------
# Adversarial controls — ablations prove each mechanism component.
# ---------------------------------------------------------------------------


def test_ablation_single_engine_misses_expiry_divergence() -> None:
    """Without a second engine there is no pairwise comparison: MISS."""
    trace = _expiry_divergence_trace()
    full = conformance_test(trace)
    assert full.status == "DIVERGENCE" and full.divergence_time == 2500
    for engine in ENGINE_MODELS:
        ablated = ablation_single_engine(trace, engine=engine)
        assert ablated.status == "NO_DIVERGENCE"
        assert ablated.reason_code == RC_ABLATION_SINGLE_ENGINE
        assert ablated.ablation == ABLATION_SINGLE_ENGINE
        assert ablated.engines == (engine,)
        assert ablated.divergence_time is None


def test_ablation_no_time_misses_expiry_divergence() -> None:
    """All engines, terminal state only: the healed divergence is MISSED."""
    trace = _expiry_divergence_trace()
    full = conformance_test(trace)
    assert full.status == "DIVERGENCE" and full.divergence_time == 2500
    ablated = ablation_no_time(trace)
    assert ablated.status == "NO_DIVERGENCE"
    assert ablated.reason_code == RC_ABLATION_NO_TIME
    assert ablated.ablation == ABLATION_NO_TIME
    assert ablated.engines == ENGINE_MODELS
    assert ablated.divergence_time is None
    # The terminal view evaluates at the last event's tick (3000), not the
    # access's decision time (2500) — the temporal fact is discarded.
    assert ablated.timeline[0]["logical_time"] == 3000
    # And every engine agrees PERMIT on the healed terminal grant.
    assert set(ablated.timeline[0]["decisions"].values()) == {DECISION_PERMIT}


def test_ablation_no_time_still_catches_unhealed_divergence() -> None:
    """A divergence the terminal state has NOT healed is caught even ablated."""
    trace = {
        "trace_id": "SACMAT-CT-UNHEALED",
        "events": [
            _grant(100, "patient-e", purpose="care_team", expiry=9000),
            _delegate(200, "patient-d", "patient-e", purpose="care_team", expiry=2000),
            _access(2500, "patient-d", purpose="care_team"),
        ],
    }
    ablated = ablation_no_time(trace)
    assert ablated.status == "DIVERGENCE"
    assert ablated.detail.startswith("terminal_view|")


def test_single_engine_and_no_time_together_still_miss() -> None:
    """The composed ablation (one engine, terminal view) also misses."""
    trace = _expiry_divergence_trace()
    single = ablation_single_engine(trace, engine=ENGINE_OPA)
    assert single.status == "NO_DIVERGENCE"
    terminal = ablation_no_time(trace)
    assert terminal.status == "NO_DIVERGENCE"


def test_insufficient_engines_fail_closed_indeterminate() -> None:
    result = conformance_test(_conformant_trace(), engines=(ENGINE_CEDAR,))
    assert result.status == "INDETERMINATE"
    assert result.reason_code == RC_INSUFFICIENT_ENGINES


def test_duplicate_engine_ids_deduplicated_still_conforms() -> None:
    result = conformance_test(_conformant_trace(), engines=(ENGINE_CEDAR, ENGINE_CEDAR))
    assert result.status == "INDETERMINATE"
    assert result.reason_code == RC_INSUFFICIENT_ENGINES


# ---------------------------------------------------------------------------
# Fail-closed data validation battery (INDETERMINATE, never a safe verdict).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("trace", "expected_reason_suffix"),
    [
        ({"trace_id": "T", "events": []}, RC_EMPTY_TRACE),
        (
            {"trace_id": "T", "events": [{"kind": "GRANT", "principal": "p"}]},
            RC_MISSING_LOGICAL_TIME,
        ),
        (
            {
                "trace_id": "T",
                "events": [
                    _grant(200, "p"),
                    _grant(100, "p"),
                ],
            },
            RC_UNORDERED_TIMESTAMPS,
        ),
        (
            {
                "trace_id": "T",
                "events": [
                    _grant(100, "p"),
                    _grant(100, "p"),
                ],
            },
            RC_DUPLICATE_TIMESTAMP,
        ),
        (
            {
                "trace_id": "T",
                "events": [
                    {"kind": "DEMOTE", "principal": "p", "logical_time": 100},
                ],
            },
            RC_UNSUPPORTED_CONSTRUCT,
        ),
        (
            {
                "trace_id": "T",
                "events": [
                    {
                        "kind": "DELEGATE",
                        "principal": "q",
                        "tenant": "t1",
                        "resource": "r",
                        "purpose": "self_care",
                        "logical_time": 100,
                    },
                ],
            },
            "MALFORMED_EVENT",
        ),
    ],
)
def test_malformed_traces_fail_closed_indeterminate(
    trace: dict[str, object], expected_reason_suffix: str
) -> None:
    result = conformance_test(trace)
    assert result.status == "INDETERMINATE"
    assert result.reason_code.startswith(expected_reason_suffix)


# ---------------------------------------------------------------------------
# Wiring errors fail closed with stable reason codes.
# ---------------------------------------------------------------------------


def test_unknown_engine_raises_stable_reason() -> None:
    with pytest.raises(TemporalConformanceError) as excinfo:
        conformance_test(_conformant_trace(), engines=(ENGINE_CEDAR, "llm"))
    assert excinfo.value.reason_code == RC_UNKNOWN_ENGINE


def test_engines_not_a_sequence_raises_stable_reason() -> None:
    with pytest.raises(TemporalConformanceError) as excinfo:
        conformance_test(_conformant_trace(), engines={"cedar": True})  # type: ignore[arg-type]
    assert excinfo.value.reason_code == RC_ENGINES_NOT_A_SEQUENCE


def test_trace_input_unrecognized_raises_stable_reason() -> None:
    with pytest.raises(TemporalConformanceError) as excinfo:
        conformance_test("not-a-trace")  # type: ignore[arg-type]
    assert excinfo.value.reason_code == RC_TRACE_INPUT_UNRECOGNIZED


def test_case_not_an_object_raises_stable_reason() -> None:
    with pytest.raises(TemporalConformanceError) as excinfo:
        run_candidate(["not", "a", "case"])  # type: ignore[arg-type]
    assert excinfo.value.reason_code == RC_CASE_NOT_AN_OBJECT


def test_result_to_dict_round_trip() -> None:
    result = conformance_test(_expiry_divergence_trace())
    payload = result.to_dict()
    assert payload["candidate_id"] == CANDIDATE_ID
    assert payload["divergence_time"] == 2500
    assert payload["decision_a"] == DECISION_PERMIT
    assert payload["decision_b"] == DECISION_DENY
    assert isinstance(payload["engines"], list)
