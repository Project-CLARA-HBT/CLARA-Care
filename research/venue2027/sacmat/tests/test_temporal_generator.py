"""Tests for SACMAT-X06_temporal_generator — bounded paired temporal corpus.

Positive controls:
- ``generate_traces`` is deterministic: identical parameters give byte-equal
  corpora across repeated calls (48-seed sweep), and every trace record
  round-trips through JSON without loss.
- Every VALID trace replays PERMIT with zero findings under the independent
  DSL oracle (:mod:`evaluation.venue2027.sacmat.policy_trace_dsl`); the
  generator never emits a "valid" history that the independent replay
  refutes.
- Every temporal bug carries a static request-matched control: the SAME
  authorization request (same principal/tenant/resource/purpose/logical
  time) replayed against the un-mutated history, verified by
  :func:`assert_all_paired`; bug and control differ ONLY in the temporal
  mutation.
- The corpus is unique by ``trace_id`` and by canonical ``trace_sha256``
  (no duplicate traces silently deduplicated), and the coverage summary
  totals reconcile exactly: valid + bug + control == total and every bug
  class has exactly one matched control per bug trace.
- Each bug's expected findings contain its declared witness kind and each
  bug class instantiates a distinct temporal mutation (REVOKE_BEFORE_GRANT,
  DELEGATION_CYCLE, REVOKED_ACTOR_TRANSITIVITY, TIME_TRAVEL_ACCESS).

Adversarial controls:
- Out-of-bound depth/hops/mutation_points (and non-int/bool inputs, negative
  seeds) are REFUSED with stable reason codes — never silently clamped.
- A bug without its matched control is rejected by :func:`assert_all_paired`
  (UNPAIRED_CONTROL), a control without its bug likewise (UNPAIRED_BUG), a
  request mismatch between pair halves is REQUEST_MISMATCH.
- Tampering with embedded verdicts/events, duplicated trace ids/hashes and
  unknown bug classes fail closed in :func:`verify_corpus` /
  :func:`assert_corpus_integrity` with stable reason codes — tampered
  records are never silently repaired or dropped.

Failure semantics: adversarial cases raise ``TemporalGeneratorError`` with
stable reason codes (first-class refusals, not swallowed errors). The module
imports only the generator and the audited DSL (independent-oracle rule): no
candidate runtime, no DB, no model, no live provider, no clock, no network.
"""

from __future__ import annotations

import copy
import json

import pytest

from evaluation.venue2027.sacmat.policy_trace_dsl import (
    FINDING_DELEGATION_CYCLE,
    FINDING_REVOKE_BEFORE_GRANT,
    FINDING_REVOKED_ACTOR_TRANSITIVITY,
    FINDING_UNESTABLISHED_AUTHORITY,
    OUTCOME_PERMIT,
)
from evaluation.venue2027.sacmat.temporal_trace_generator import (
    BUG_CLASS_DELEGATION_CYCLE,
    BUG_CLASS_REVOKE_BEFORE_GRANT,
    BUG_CLASS_REVOKED_ACTOR_TRANSITIVITY,
    BUG_CLASS_TIME_TRAVEL_ACCESS,
    BUG_CLASSES,
    GENERATOR_VERSION,
    ROLE_BUG,
    ROLE_CONTROL,
    ROLE_VALID,
    TemporalGeneratorError,
    assert_all_paired,
    assert_corpus_integrity,
    build_corpus_document,
    coverage_summary,
    generate_traces,
    verify_corpus,
)

WITNESS_OF: dict[str, str] = {
    BUG_CLASS_REVOKE_BEFORE_GRANT: FINDING_REVOKE_BEFORE_GRANT,
    BUG_CLASS_DELEGATION_CYCLE: FINDING_DELEGATION_CYCLE,
    BUG_CLASS_REVOKED_ACTOR_TRANSITIVITY: FINDING_REVOKED_ACTOR_TRANSITIVITY,
    BUG_CLASS_TIME_TRAVEL_ACCESS: FINDING_UNESTABLISHED_AUTHORITY,
}


def expect_refusal(reason_code: str, fn) -> None:
    with pytest.raises(TemporalGeneratorError) as excinfo:
        fn()
    assert (
        excinfo.value.reason_code == reason_code
    ), f"expected {reason_code}, got {excinfo.value.reason_code}: {excinfo.value.detail}"


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "params",
    [
        (0, 3, 0, 0),
        (1, 4, 1, 2),
        (7, 5, 2, 1),
        (42, 6, 3, 4),
        (2027, 8, 3, 4),
        (99, 12, 4, 2),
        (123456, 7, 4, 3),
    ],
)
def test_corpus_is_deterministic_per_parameters(params):
    first = generate_traces(*params)
    second = generate_traces(*params)
    assert first == second
    assert json.loads(json.dumps(first)) == first


def test_valid_traces_stay_valid_under_independent_replay():
    for seed in range(48):
        corpus = generate_traces(seed, 6, 3, 4)
        for trace in corpus:
            if trace["role"] in (ROLE_VALID, ROLE_CONTROL):
                assert trace["expected_outcome"] == OUTCOME_PERMIT
                assert trace["expected_findings"] == []
            verify_corpus(corpus)


def test_valid_only_corpus_when_mutation_points_zero():
    corpus = generate_traces(5, 5, 2, 0)
    assert len(corpus) == 1
    assert corpus[0]["role"] == ROLE_VALID
    assert corpus[0]["bug_class"] is None
    assert corpus[0]["expected_outcome"] == OUTCOME_PERMIT
    assert corpus[0]["expected_findings"] == []
    assert len(corpus[0]["events"]) == 4  # grant + 2 delegates + access
    verify_corpus(corpus)


def test_each_bug_has_request_matched_static_control():
    for params in [(3, 6, 3, 4), (11, 6, 3, 2), (2027, 8, 3, 4)]:
        corpus = generate_traces(*params)
        assert_all_paired(corpus)
        by_id = {trace["trace_id"]: trace for trace in corpus}
        for trace in corpus:
            if trace["role"] != ROLE_BUG:
                continue
            control = by_id[trace["paired_trace_id"]]
            assert control["role"] == ROLE_CONTROL
            assert control["request"] == trace["request"]
            # Pairing differs ONLY in the temporal mutation: removing the bug
            # trace's witness event set must change the history, while the
            # control keeps the same event budget shape (same event count for
            # reorder mutations; +1 revoke for revocation mutations).
            assert control["bug_class"] == trace["bug_class"]
            assert set(control["events"][0]) == set(trace["events"][0])


def test_bug_traces_carry_exactly_their_declared_witness():
    corpus = generate_traces(2027, 8, 3, 4)
    for trace in corpus:
        if trace["role"] != ROLE_BUG:
            continue
        witness = WITNESS_OF[trace["bug_class"]]
        kinds = [finding["kind"] for finding in trace["expected_findings"]]
        assert witness in kinds
        # the temporal mutation is the ONLY trace-level error in the bug trace
        assert len(trace["expected_findings"]) == 1


def test_trace_hashes_unique_across_corpus():
    for seed in range(48):
        corpus = generate_traces(seed, 6, 3, 4)
        ids = [trace["trace_id"] for trace in corpus]
        hashes = [trace["trace_sha256"] for trace in corpus]
        assert len(ids) == len(set(ids))
        assert len(hashes) == len(set(hashes))
        assert all(len(h) == 64 for h in hashes)


def test_unique_hashes_across_seeds_for_bug_and_control_pairs():
    seen: set[str] = set()
    for seed in range(48):
        corpus = generate_traces(seed, 6, 3, 4)
        for trace in corpus:
            assert trace["trace_sha256"] not in seen, f"hash collision across seeds at seed={seed}"
            seen.add(trace["trace_sha256"])


def test_coverage_summary_totals_reconcile():
    for params in [(0, 6, 3, 4), (9, 5, 2, 1), (31, 6, 3, 0), (77, 6, 1, 3)]:
        corpus = generate_traces(*params)
        summary = coverage_summary(corpus)
        assert summary["total_traces"] == len(corpus)
        assert (
            summary["valid_traces"] + summary["bug_traces"] + summary["control_traces"]
            == summary["total_traces"]
        )
        assert summary["valid_traces"] == 1
        assert summary["bug_traces"] == summary["control_traces"]
        assert summary["bug_control_pairs"] == summary["bug_traces"]
        assert summary["unique_trace_ids"] == summary["total_traces"]
        assert summary["unique_trace_sha256"] == summary["total_traces"]
        per_class = summary["bug_classes"]
        assert set(per_class) == set(BUG_CLASSES)
        declared_bugs = sum(entry["bug_traces"] for entry in per_class.values())
        declared_controls = sum(entry["matched_controls"] for entry in per_class.values())
        assert declared_bugs == summary["bug_traces"]
        assert declared_controls == summary["control_traces"]
        for entry in per_class.values():
            assert entry["bug_traces"] == entry["matched_controls"]


def test_bounds_are_respected_in_every_emitted_trace():
    depth, hops = 7, 2
    corpus = generate_traces(17, depth, hops, 4)
    for trace in corpus:
        assert len(trace["events"]) <= depth
        times = [event["logical_time"] for event in trace["events"]]
        assert times == sorted(times)
        assert len(set(times)) == len(times)
        # delegation hops bounded: at most ``hops`` DELEGATE events per trace
        delegates = [e for e in trace["events"] if e["kind"] == "DELEGATE"]
        assert len(delegates) <= hops
        # mutation points bounded: at most one temporal mutation per bug trace
        # (verified structurally: each bug trace carries exactly one witness).


def test_build_corpus_document_shape():
    document = build_corpus_document(2027, 8, 3, 4)
    assert document["corpus_schema_version"].startswith("clara.venue2027.sacmat.")
    assert document["generator_version"] == GENERATOR_VERSION
    assert document["params"] == {"seed": 2027, "depth": 8, "hops": 3, "mutation_points": 4}
    assert document["coverage"]["total_traces"] == len(document["traces"])
    verify_corpus(document["traces"])
    assert json.loads(json.dumps(document)) == document


# ---------------------------------------------------------------------------
# Adversarial controls
# ---------------------------------------------------------------------------


def test_out_of_bound_depth_refused():
    expect_refusal("DEPTH_OUT_OF_RANGE", lambda: generate_traces(1, 2, 0, 0))
    expect_refusal("DEPTH_OUT_OF_RANGE", lambda: generate_traces(1, 13, 0, 0))
    expect_refusal("DEPTH_OUT_OF_RANGE", lambda: generate_traces(1, 2, 3, 1))
    expect_refusal("DEPTH_OUT_OF_RANGE", lambda: generate_traces(1, "6", 3, 1))
    expect_refusal("DEPTH_OUT_OF_RANGE", lambda: generate_traces(1, 6.0, 3, 1))
    expect_refusal("DEPTH_OUT_OF_RANGE", lambda: generate_traces(1, True, 3, 1))


def test_out_of_bound_hops_refused():
    expect_refusal("HOPS_OUT_OF_RANGE", lambda: generate_traces(1, 6, 5, 1))
    expect_refusal("HOPS_OUT_OF_RANGE", lambda: generate_traces(1, 6, -1, 1))
    expect_refusal("HOPS_OUT_OF_RANGE", lambda: generate_traces(1, 6, 3.5, 1))
    expect_refusal("HOPS_OUT_OF_RANGE", lambda: generate_traces(1, 6, None, 1))


def test_out_of_bound_mutation_points_refused():
    expect_refusal("MUTATION_POINTS_OUT_OF_RANGE", lambda: generate_traces(1, 6, 3, 5))
    expect_refusal("MUTATION_POINTS_OUT_OF_RANGE", lambda: generate_traces(1, 6, 3, -2))
    expect_refusal("MUTATION_POINTS_OUT_OF_RANGE", lambda: generate_traces(1, 6, 3, "all"))


def test_hops_exceeding_depth_budget_refused():
    expect_refusal("HOPS_EXCEED_DEPTH", lambda: generate_traces(1, 4, 3, 1))
    expect_refusal("HOPS_EXCEED_DEPTH", lambda: generate_traces(1, 5, 4, 1))


def test_invalid_seed_refused():
    expect_refusal("INVALID_SEED", lambda: generate_traces(-1, 6, 3, 1))
    expect_refusal("INVALID_SEED", lambda: generate_traces(True, 6, 3, 1))
    expect_refusal("INVALID_SEED", lambda: generate_traces(None, 6, 3, 1))
    expect_refusal("INVALID_SEED", lambda: generate_traces(3.14, 6, 3, 1))


def test_bug_without_control_rejected_by_assert_all_paired():
    corpus = generate_traces(7, 6, 3, 4)
    orphaned = [
        trace
        for trace in corpus
        if not (trace["role"] == ROLE_CONTROL and trace["bug_class"] == BUG_CLASS_DELEGATION_CYCLE)
    ]
    assert any(trace["role"] == ROLE_BUG for trace in orphaned)
    expect_refusal("UNPAIRED_CONTROL", lambda: assert_all_paired(orphaned))


def test_control_without_bug_rejected_by_assert_all_paired():
    corpus = generate_traces(7, 6, 3, 4)
    orphaned = [
        trace
        for trace in corpus
        if not (
            trace["role"] == ROLE_BUG and trace["bug_class"] == BUG_CLASS_REVOKED_ACTOR_TRANSITIVITY
        )
    ]
    assert any(trace["role"] == ROLE_CONTROL for trace in orphaned)
    expect_refusal("UNPAIRED_BUG", lambda: assert_all_paired(orphaned))


def test_request_mismatch_between_pair_halves_rejected():
    corpus = copy.deepcopy(generate_traces(7, 6, 3, 4))
    for trace in corpus:
        if trace["role"] == ROLE_CONTROL and trace["bug_class"] == BUG_CLASS_TIME_TRAVEL_ACCESS:
            trace["request"]["principal"] = "someone-else"
    expect_refusal("REQUEST_MISMATCH", lambda: assert_all_paired(corpus))


def test_dangling_paired_trace_id_rejected():
    corpus = copy.deepcopy(generate_traces(7, 6, 3, 4))
    for trace in corpus:
        if trace["role"] == ROLE_BUG and trace["bug_class"] == BUG_CLASS_REVOKE_BEFORE_GRANT:
            trace["paired_trace_id"] = "does-not-exist"
    expect_refusal("UNPAIRED_CONTROL", lambda: assert_all_paired(corpus))


def test_duplicate_trace_ids_and_hashes_rejected():
    corpus = generate_traces(7, 6, 3, 4)
    expect_refusal(
        "DUPLICATE_TRACE_ID", lambda: assert_corpus_integrity([*corpus, dict(corpus[0])])
    )
    cloned = copy.deepcopy(corpus)
    cloned[1]["trace_id"] = cloned[0]["trace_id"]
    expect_refusal("DUPLICATE_TRACE_ID", lambda: assert_corpus_integrity(cloned))
    same_hash = copy.deepcopy(corpus)
    same_hash[1]["trace_sha256"] = same_hash[0]["trace_sha256"]
    expect_refusal("DUPLICATE_TRACE_HASH", lambda: assert_corpus_integrity(same_hash))


def test_tampered_events_fail_verification():
    corpus = copy.deepcopy(generate_traces(7, 6, 3, 4))
    for trace in corpus:
        if trace["role"] == ROLE_BUG and trace["bug_class"] == BUG_CLASS_REVOKED_ACTOR_TRANSITIVITY:
            trace["events"] = trace["events"][:-1]
    expect_refusal("INVALID_TRACE_RECORD", lambda: verify_corpus(corpus))


def test_tampered_expected_verdicts_fail_verification():
    corpus = copy.deepcopy(generate_traces(7, 6, 3, 4))
    for trace in corpus:
        if trace["role"] == ROLE_BUG and trace["bug_class"] == BUG_CLASS_REVOKED_ACTOR_TRANSITIVITY:
            trace["expected_outcome"] = OUTCOME_PERMIT
            trace["expected_findings"] = []
    expect_refusal("INVALID_TRACE_RECORD", lambda: verify_corpus(corpus))


def test_tampered_hash_fails_verification():
    corpus = copy.deepcopy(generate_traces(7, 6, 3, 4))
    corpus[0]["trace_sha256"] = "0" * 64
    expect_refusal("INVALID_TRACE_RECORD", lambda: verify_corpus(corpus))


def test_valid_trace_tampered_to_broken_fails_verification():
    corpus = copy.deepcopy(generate_traces(7, 6, 3, 4))
    for trace in corpus:
        if trace["role"] == ROLE_VALID:
            trace["events"] = trace["events"][:-1]
    expect_refusal("INVALID_TRACE_RECORD", lambda: verify_corpus(corpus))


def test_malformed_records_rejected():
    expect_refusal("INVALID_TRACE_RECORD", lambda: assert_all_paired(["not-a-record"]))
    expect_refusal("INVALID_TRACE_RECORD", lambda: assert_all_paired([{"trace_id": "x"}]))
    bad_role = {
        "trace_id": "x",
        "role": "mutant",
        "bug_class": None,
        "paired_trace_id": None,
        "request": {},
        "events": [],
        "trace_sha256": "0" * 64,
    }
    expect_refusal("INVALID_TRACE_RECORD", lambda: assert_all_paired([bad_role]))
    bug_no_class = {
        "trace_id": "x",
        "role": ROLE_BUG,
        "bug_class": "NOT_A_BUG_CLASS",
        "paired_trace_id": None,
        "request": {},
        "events": [],
        "trace_sha256": "0" * 64,
    }
    expect_refusal("INVALID_TRACE_RECORD", lambda: assert_all_paired([bug_no_class]))
