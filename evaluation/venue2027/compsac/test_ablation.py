"""Tests for COMPSAC-ablation (causal mechanism ablation harness).

Positive controls (must pass):
- Every registered ablation variant runs over the SAME frozen suite and
  produces a typed AblationRow with internally consistent tallies.
- The full candidate has ZERO forbidden commits on the frozen suite.
- no_dependency_closure produces >0 forbidden commits (it admits the canonical
  omitted-dependency write skew) — the causal-mechanism evidence (RQ2).
- no_epoch_validation produces >0 forbidden commits (it admits the epoch-race
  write whose consent was revoked concurrently).
- global_version_coarse stays safe (0 forbidden commits) but inflates
  false-stale aborts and commits strictly fewer ops than the full candidate
  (RQ1: coarse fence is the false-stale upper bound).
- no_lock_ordering is byte-identical to the full candidate (the canonical
  lock order is a built-in total order; COMPSAC-CASE-06 order-invariance).
- run_ablation(name, case) obeys the task-manifest signature on every
  registered variant, including the canonical contrast pairs on single cases.

Adversarial controls (must fail closed):
- An unknown variant id is refused (UNKNOWN_ABLATION_VARIANT) by run_variant,
  run_ablation and run_ablation_suite paths — never silently run as the full
  candidate.
- The frozen case suite is identical across variants (same unit ids, same
  seed) — seeds are equal across variants by construction.
- Determinism: re-running a variant yields a byte-identical row; suite digest
  is stable across calls.
- Malformed / unknown-family case payloads are refused with stable reason
  codes, never coerced into safe rejections.
- Candidate ERROR outcomes are never counted as safe rejections or forbidden
  commits.
"""

from __future__ import annotations

import json

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.compsac import ablation as abl
from evaluation.venue2027.compsac import candidate as cand
from evaluation.venue2027.compsac.ablation import (
    ABLATION_VARIANTS,
    AblationCase,
    AblationError,
    build_frozen_cases,
    describe_ablation,
    run_ablation,
    run_ablation_suite,
    run_variant,
    variant_ids,
)

# ---------------------------------------------------------------------------
# Frozen suite fixture (built once; shared across variants by construction)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def frozen_cases() -> tuple[AblationCase, ...]:
    return build_frozen_cases(abl.ABLATION_SUITE_SEED)


@pytest.fixture(scope="module")
def suite_rows(frozen_cases: tuple[AblationCase, ...]) -> dict[str, abl.AblationRow]:
    return {vid: run_variant(vid, frozen_cases) for vid in variant_ids()}


def _payload_of(case: AblationCase) -> dict[str, object]:
    return case.to_payload()


def _first_case_of_family(
    cases: tuple[AblationCase, ...], family: str, *, arm_test
) -> AblationCase:
    for case in cases:
        if case.family == family and arm_test(case):
            return case
    raise AssertionError(f"no {family} case with the requested arm in the frozen suite")


# ---------------------------------------------------------------------------
# Positive: every variant runs and produces consistent typed rows
# ---------------------------------------------------------------------------


def test_every_registered_variant_runs_over_the_frozen_suite(suite_rows) -> None:
    assert set(suite_rows) == set(variant_ids())
    assert set(suite_rows) == set(ABLATION_VARIANTS)
    for row in suite_rows.values():
        assert isinstance(row, abl.AblationRow)
        d = row.to_dict()
        assert d["case_count"] == len(d["suite_unit_ids"]) == abl.ABLATION_SUITE_SIZE
        # Tally conservation: every case lands in exactly one bucket.
        assert d["committed_ops"] + d["rejected_ops"] + d["error_ops"] == d["case_count"]
        # Internal consistency of the sub-buckets.
        assert d["forbidden_commits"] <= d["committed_ops"]
        assert d["aborted_ops"] <= d["rejected_ops"]
        assert d["false_stale_aborts"] <= d["rejected_ops"]
        assert len(d["variant_digest"]) == 64
        # Typed rows are JSON-serializable.
        json.dumps(d)


def test_full_candidate_has_zero_forbidden_commits(suite_rows) -> None:
    full = suite_rows[abl.VARIANT_FULL]
    assert full.forbidden_commits == 0
    assert full.error_ops == 0


def test_no_dependency_closure_admits_the_write_skew(suite_rows) -> None:
    """THE causal-mechanism evidence: dropping the closure admits write skew."""
    full = suite_rows[abl.VARIANT_FULL]
    no_closure = suite_rows[abl.VARIANT_NO_CLOSURE]
    assert no_closure.forbidden_commits > 0
    assert no_closure.forbidden_commits > full.forbidden_commits


def test_no_epoch_validation_admits_the_epoch_race(suite_rows) -> None:
    full = suite_rows[abl.VARIANT_FULL]
    no_epoch = suite_rows[abl.VARIANT_NO_EPOCH]
    assert no_epoch.forbidden_commits > 0
    assert no_epoch.forbidden_commits > full.forbidden_commits


def test_global_version_coarse_is_safe_but_false_stale(suite_rows) -> None:
    full = suite_rows[abl.VARIANT_FULL]
    global_version = suite_rows[abl.VARIANT_GLOBAL_VERSION]
    assert global_version.forbidden_commits == 0
    assert global_version.false_stale_aborts > full.false_stale_aborts
    assert global_version.committed_ops < full.committed_ops


def test_no_lock_ordering_matches_full_candidate_exactly(suite_rows) -> None:
    full = suite_rows[abl.VARIANT_FULL]
    no_lock = suite_rows[abl.VARIANT_NO_LOCK_ORDER]
    # Behavior is byte-identical (shared decision-record digest and tallies);
    # only the variant metadata (id/description/provenance) legitimately differs.
    assert no_lock.variant_digest == full.variant_digest
    for field in (
        "forbidden_commits",
        "false_stale_aborts",
        "committed_ops",
        "rejected_ops",
        "aborted_ops",
        "error_ops",
        "case_count",
        "suite_seed",
        "suite_unit_ids",
    ):
        assert getattr(no_lock, field) == getattr(full, field), field


def test_suite_comparison_flags_all_causal_mechanisms(frozen_cases) -> None:
    suite = run_ablation_suite(abl.ABLATION_SUITE_SEED)
    comparison = suite["comparison"]["causal_mechanism"]
    assert comparison["full_candidate_zero_forbidden_commits"] is True
    assert comparison["no_dependency_closure_admits_write_skew"] is True
    assert comparison["no_epoch_validation_admits_epoch_race"] is True
    assert comparison["global_version_false_stales"] is True
    assert comparison["global_version_commits_less"] is True
    assert comparison["lock_order_invariance_confirmed"] is True
    assert suite["comparison"]["same_cases_across_variants"] is True
    assert suite["scale"] == "DEVELOPMENT (mechanism causality; NOT confirmatory)"
    assert sorted(suite["suite_families"]) == sorted(
        {"clean", "omitted_dependency", "epoch_race", "stale_readset"}
    )


def test_manifest_signature_run_ablation_on_every_variant(frozen_cases) -> None:
    """run_ablation(name, case) -> Outcome works for every registered variant."""
    for name in variant_ids():
        case = frozen_cases[0]
        outcome = run_ablation(name, _payload_of(case))
        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome in {"ADMIT", "REJECT"}
        assert outcome.counted_as_success is True
        detail = json.loads(outcome.detail)
        assert detail["variant_id"] == name
        assert detail["ablation_version"] == abl.ABLATION_VERSION
        assert detail["reason_code"] == cand.REASON_OK or detail["reason_code"] in {
            cand.REASON_REQUIRED_EDGE_STALE,
            cand.REASON_WRITE_TARGET_SUPERSEDED,
            cand.REASON_GLOBAL_EPOCH_STALE,
            cand.REASON_CONSENT_EPOCH_STALE,
            cand.REASON_POLICY_EPOCH_STALE,
            cand.REASON_GOVERNANCE_EPOCH_STALE,
        }
        json.dumps(outcome.to_dict())


def test_single_case_contrast_closure_is_the_mechanism(frozen_cases) -> None:
    """On the identical single write-skew case, only the closure differs."""
    case = _first_case_of_family(
        frozen_cases,
        "omitted_dependency",
        arm_test=lambda c: c.determinant % 2 == 0,
    )
    payload = _payload_of(case)
    full = run_ablation(abl.VARIANT_FULL, payload)
    no_closure = run_ablation(abl.VARIANT_NO_CLOSURE, payload)
    assert full.observed_outcome == "REJECT"
    assert json.loads(full.detail)["reason_code"] in {
        cand.REASON_REQUIRED_EDGE_STALE,
        cand.REASON_WRITE_TARGET_SUPERSEDED,
    }
    assert no_closure.observed_outcome == "ADMIT"
    assert json.loads(no_closure.detail)["forbidden_commits"] == 1


def test_single_case_contrast_coarse_fence_false_stale(frozen_cases) -> None:
    """On the identical unrelated-write case, only the version fence differs.

    The clean family's odd arm applies an UNRELATED concurrent write (outside
    the closure): the scope-local candidate admits, while the coarse
    global-epoch fence cannot tell unrelated from required and false-stales
    (COMPSAC-CASE-01). A quiet case cannot witness this: its global epoch
    never moved, so both fences admit.
    """
    case = _first_case_of_family(
        frozen_cases, "clean", arm_test=lambda c: c.concurrent_entity != ""
    )
    payload = _payload_of(case)
    full = run_ablation(abl.VARIANT_FULL, payload)
    coarse = run_ablation(abl.VARIANT_GLOBAL_VERSION, payload)
    assert full.observed_outcome == "ADMIT"
    assert coarse.observed_outcome == "REJECT"
    assert json.loads(coarse.detail)["reason_code"] == cand.REASON_GLOBAL_EPOCH_STALE
    assert json.loads(coarse.detail)["false_stale_aborts"] == 1


def test_single_case_contrast_epoch_validation_is_the_mechanism(frozen_cases) -> None:
    """On the identical consent-revocation case, only the epoch checks differ."""
    case = _first_case_of_family(
        frozen_cases,
        "epoch_race",
        arm_test=lambda c: c.concurrent_entity == "@revoke_consent",
    )
    payload = _payload_of(case)
    full = run_ablation(abl.VARIANT_FULL, payload)
    no_epoch = run_ablation(abl.VARIANT_NO_EPOCH, payload)
    assert full.observed_outcome == "REJECT"
    assert json.loads(full.detail)["reason_code"] == cand.REASON_CONSENT_EPOCH_STALE
    assert no_epoch.observed_outcome == "ADMIT"
    assert json.loads(no_epoch.detail)["forbidden_commits"] == 1


# ---------------------------------------------------------------------------
# Adversarial: unknown variants, seed equality, determinism, malformed input
# ---------------------------------------------------------------------------


def test_unknown_variant_refused_by_run_variant(frozen_cases) -> None:
    with pytest.raises(AblationError) as excinfo:
        run_variant("ghost_variant", frozen_cases)
    assert excinfo.value.reason_code == "UNKNOWN_ABLATION_VARIANT"


def test_unknown_variant_refused_by_run_ablation(frozen_cases) -> None:
    outcome = run_ablation("ghost_variant", _payload_of(frozen_cases[0]))
    assert outcome.observed_outcome == "EXECUTION_ERROR"
    assert outcome.counted_as_success is False
    assert "UNKNOWN_ABLATION_VARIANT" in outcome.detail


def test_unknown_variant_refused_inside_suite_path(frozen_cases, monkeypatch) -> None:
    """A poisoned registry entry (unknown id leaked in) must fail the tally."""
    poisoned = dict(ABLATION_VARIANTS)
    poisoned["ghost_variant"] = poisoned[abl.VARIANT_FULL]
    monkeypatch.setattr(abl, "ABLATION_VARIANTS", poisoned, raising=True)
    # _tally consults the registry again and must refuse the unknown id
    # rather than silently running it as the full candidate.
    from evaluation.venue2027.compsac import ablation as fresh

    with pytest.raises(AblationError) as excinfo:
        fresh._tally("ghost_variant", frozen_cases)
    assert excinfo.value.reason_code == "UNKNOWN_ABLATION_VARIANT"


def test_seeds_are_equal_across_variants_same_cases(frozen_cases, suite_rows) -> None:
    """Same frozen cases, same seed for every variant (same-cases invariant)."""
    unit_ids = {row.suite_unit_ids for row in suite_rows.values()}
    assert len(unit_ids) == 1
    assert next(iter(unit_ids)) == tuple(case.unit_id for case in frozen_cases)
    seeds = {row.suite_seed for row in suite_rows.values()}
    assert seeds == {abl.ABLATION_SUITE_SEED}
    # And rebuilding the suite is byte-stable (frozen means frozen).
    assert build_frozen_cases(abl.ABLATION_SUITE_SEED) == frozen_cases


def test_determinism_rows_are_byte_identical_on_rerun(frozen_cases) -> None:
    first = run_variant(abl.VARIANT_NO_CLOSURE, frozen_cases)
    second = run_variant(abl.VARIANT_NO_CLOSURE, frozen_cases)
    assert first.to_dict() == second.to_dict()
    assert first.variant_digest == second.variant_digest


def test_determinism_suite_is_stable_across_calls() -> None:
    first = run_ablation_suite(abl.ABLATION_SUITE_SEED)
    second = run_ablation_suite(abl.ABLATION_SUITE_SEED)
    assert first["rows"] == second["rows"]
    assert first["suite_unit_ids"] == second["suite_unit_ids"]


def test_malformed_case_payload_refused() -> None:
    for payload in ({}, {"case_id": "only"}, {"case_id": "x", "family": "clean"}):
        outcome = run_ablation(abl.VARIANT_FULL, payload)
        assert outcome.observed_outcome == "EXECUTION_ERROR"
        assert outcome.counted_as_success is False
        assert "CASE_MALFORMED" in outcome.detail


def test_unknown_case_family_refused() -> None:
    base = build_frozen_cases(abl.ABLATION_SUITE_SEED)[0].to_payload()
    base["family"] = "not_a_compsac_family"
    outcome = run_ablation(abl.VARIANT_FULL, base)
    assert outcome.observed_outcome == "EXECUTION_ERROR"
    assert outcome.counted_as_success is False
    assert "UNKNOWN_CASE_FAMILY" in outcome.detail


def test_case_payload_round_trip_is_lossless(frozen_cases) -> None:
    case = frozen_cases[3]
    rebuilt = AblationCase.from_payload(_payload_of(case))
    assert rebuilt == case
    # And the rebuilt case produces the identical outcome.
    direct = run_ablation(abl.VARIANT_FULL, _payload_of(case))
    round_trip = run_ablation(abl.VARIANT_FULL, _payload_of(rebuilt))
    assert direct.to_dict() == round_trip.to_dict()


def test_error_admissions_never_counted_as_safe_rejections(frozen_cases) -> None:
    """A candidate ERROR (e.g. oracle missing) is error_ops, never REJECT."""
    from evaluation.venue2027.compsac import ablation as mod

    original = mod._full_closure_oracle
    mod._full_closure_oracle = lambda op: None  # type: ignore[assignment]
    try:
        row = run_variant(abl.VARIANT_FULL, frozen_cases)
    finally:
        mod._full_closure_oracle = original  # type: ignore[assignment]
    assert row.error_ops == row.case_count
    assert row.committed_ops == 0
    assert row.rejected_ops == 0
    assert row.forbidden_commits == 0


def test_variant_scope_is_shared_and_snapshots_are_frozen(frozen_cases) -> None:
    """Every variant builds the same snapshot for a case; only the toggle differs."""
    case = frozen_cases[0]
    base = abl._variant_scope(case, abl.VARIANT_FULL)
    for variant in (abl.VARIANT_NO_CLOSURE, abl.VARIANT_GLOBAL_VERSION):
        derived = abl._variant_scope(case, variant)
        assert derived.snapshot_versions == base.snapshot_versions
        assert derived.consent_epoch == base.consent_epoch
        assert derived.policy_epoch == base.policy_epoch
        assert derived.snapshot_global_epoch == base.snapshot_global_epoch


def test_describe_ablation_is_a_complete_design_record() -> None:
    record = describe_ablation()
    assert record["ablation_version"] == abl.ABLATION_VERSION
    assert record["task_id"] == "COMPSAC-ablation"
    assert record["candidate_id"] == cand.CANDIDATE_ID
    assert set(record["variants"]) == set(variant_ids())
    assert record["manifest_signature"] == "run_ablation(name: str, case: Mapping) -> Outcome"
    assert "confirmatory" in record["scale_note"]
    json.dumps(record)


def test_variant_registry_provenance_is_typed() -> None:
    for vid, spec in ABLATION_VARIANTS.items():
        assert spec.variant_id == vid
        assert spec.description
        assert spec.mechanism_axis
        assert spec.expected_effect
        assert spec.applied_by in {abl.APPLIED_BY_CANDIDATE_HOOK, abl.APPLIED_BY_HARNESS}
