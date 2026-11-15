"""Tests for SH-analysis_policy (frozen inferential analysis contract).

Positive controls reproduce hand-computed references: the exact McNemar
p-values for (1, 9) and (6, 14) discordant pairs, the 0/598 Clopper-Pearson
zero-event upper bound (≈0.0050), and a seeded cluster bootstrap CI on a
five-unit fixture whose point estimate is 0.12. Adversarial controls refuse
analysis drift, refuse a non-significant safety difference presented as a
two-gate certificate, and refuse the pseudo-replication of 200 same-patient
events treated as independent draws.
"""

from __future__ import annotations

import math

import pytest

from evaluation.venue2027._shared.analysis_policy import (
    ANALYSIS_POLICY_VERSION,
    AnalysisPolicyError,
    BinaryPair,
    FrozenPlan,
    PairedResult,
    analyze_paired,
    assert_frozen_analysis,
    clopper_pearson_zero_upper,
    cluster_bootstrap_ci,
    mcnemar_exact,
    plan_digest,
    two_gate_non_inferiority,
)

# --------------------------------------------------------------------------
# Positive: exact McNemar references
# --------------------------------------------------------------------------


def _pairs_from_discordant(
    candidate_better: int,
    baseline_better: int,
    concordant_success: int = 0,
    concordant_failure: int = 0,
) -> list[BinaryPair]:
    pairs: list[BinaryPair] = []
    uid = 0
    for _ in range(candidate_better):
        pairs.append(BinaryPair(f"u{uid}", f"c{uid}", True, False))
        uid += 1
    for _ in range(baseline_better):
        pairs.append(BinaryPair(f"u{uid}", f"c{uid}", False, True))
        uid += 1
    for _ in range(concordant_success):
        pairs.append(BinaryPair(f"u{uid}", f"c{uid}", True, True))
        uid += 1
    for _ in range(concordant_failure):
        pairs.append(BinaryPair(f"u{uid}", f"c{uid}", False, False))
        uid += 1
    return pairs


def test_mcnemar_exact_known_reference_1_of_9() -> None:
    # 1 baseline-better vs 9 candidate-better discordant pairs:
    # two-sided exact p = 2 * sum_{i<=1} C(10,i)/2^10 = 22/1024.
    better, worse, p = mcnemar_exact(_pairs_from_discordant(9, 1))
    assert (better, worse) == (9, 1)
    assert p == pytest.approx(22 / 1024)


def test_mcnemar_exact_known_reference_6_of_14() -> None:
    # 6 vs 14 discordant pairs: p = 2 * sum_{i<=6} C(20,i)/2^20.
    expected = 2 * sum(math.comb(20, i) for i in range(7)) / 2**20
    _, _, p = mcnemar_exact(_pairs_from_discordant(14, 6))
    assert p == pytest.approx(expected)


def test_mcnemar_exact_perfectly_balanced_is_one() -> None:
    # 5 vs 5: doubled tail exceeds 1 and must be capped at 1.0.
    _, _, p = mcnemar_exact(_pairs_from_discordant(5, 5))
    assert p == 1.0


def test_mcnemar_ignores_concordant_pairs() -> None:
    # Adding concordant pairs must not move the McNemar statistic.
    _, _, p_discordant = mcnemar_exact(_pairs_from_discordant(1, 4))
    _, _, p_with_concordant = mcnemar_exact(_pairs_from_discordant(1, 4, 5, 2))
    assert p_discordant == pytest.approx(0.375)
    assert p_with_concordant == p_discordant


# --------------------------------------------------------------------------
# Positive: zero-event Clopper-Pearson bound
# --------------------------------------------------------------------------


def test_zero_event_bound_598_matches_contract_reference() -> None:
    # Scientific metrics contract rule 3: 0/598 at alpha=0.05 gives ~0.0050.
    bound = clopper_pearson_zero_upper(598)
    assert bound == pytest.approx(1 - 0.05 ** (1 / 598))
    assert 0.0049 < bound < 0.0051


def test_zero_event_bound_10_and_20_exact_values() -> None:
    assert clopper_pearson_zero_upper(10) == pytest.approx(1 - 0.05**0.1)
    assert clopper_pearson_zero_upper(20) == pytest.approx(1 - 0.05**0.05)
    assert clopper_pearson_zero_upper(10) > clopper_pearson_zero_upper(20)


def test_zero_event_bound_rejects_bad_inputs() -> None:
    with pytest.raises(AnalysisPolicyError) as zero_n:
        clopper_pearson_zero_upper(0)
    assert zero_n.value.reason_code == "BAD_N"
    with pytest.raises(AnalysisPolicyError) as bad_alpha:
        clopper_pearson_zero_upper(10, alpha=1.5)
    assert bad_alpha.value.reason_code == "BAD_ALPHA"


# --------------------------------------------------------------------------
# Positive: seeded deterministic cluster bootstrap
# --------------------------------------------------------------------------


def _utility_fixture() -> tuple[list[float], list[str]]:
    # Five independent units; one unit carries two clustered measurements.
    diffs = [0.2, -0.1, 0.1, 0.4, 0.0]
    clusters = ["patient-A", "patient-B", "patient-C", "patient-D", "patient-E"]
    return diffs, clusters


def test_cluster_bootstrap_point_estimate_and_determinism() -> None:
    diffs, clusters = _utility_fixture()
    lo1, hi1 = cluster_bootstrap_ci(diffs, clusters, resamples=2000, seed=2027)
    lo2, hi2 = cluster_bootstrap_ci(diffs, clusters, resamples=2000, seed=2027)
    assert (lo1, hi1) == (lo2, hi2)
    assert sum(diffs) / len(diffs) == pytest.approx(0.12)
    assert lo1 <= 0.12 <= hi1


def test_cluster_bootstrap_seeds_and_cluster_structure_matter() -> None:
    diffs, clusters = _utility_fixture()
    # Same diffs spread over one giant cluster vs five units: intervals differ.
    lo_single, hi_single = cluster_bootstrap_ci(diffs, ["p"] * 5, resamples=2000, seed=2027)
    lo_multi, hi_multi = cluster_bootstrap_ci(diffs, clusters, resamples=2000, seed=2027)
    assert (lo_single, hi_single) != (lo_multi, hi_multi)


def test_analyze_paired_end_to_end_and_json_roundtrip() -> None:
    pairs = _pairs_from_discordant(9, 1)
    result = analyze_paired(pairs, bootstrap_resamples=400, bootstrap_seed=7)
    assert isinstance(result, PairedResult)
    assert result.n_pairs == 10
    assert result.n_discordant == 10
    assert result.p_value == pytest.approx(22 / 1024)
    assert result.difference == pytest.approx(0.8)
    assert result.n_clusters == 10
    assert ANALYSIS_POLICY_VERSION == "1.0.0"
    # JSON-serializable typed output.
    assert result.to_dict()["bootstrap_seed"] == 7


def test_analyze_paired_clusters_pseudo_replication() -> None:
    # 200 events from ONE patient: as a single cluster the CI is degenerate at
    # the point estimate and the effective unit count stays 1 cluster.
    pairs = [BinaryPair(f"e{i}", "patient-X", True, False) for i in range(200)]
    result = analyze_paired(pairs, bootstrap_resamples=300, bootstrap_seed=3)
    assert result.n_clusters == 1
    assert result.ci_low == result.ci_high == result.difference


def test_analyze_paired_refuses_degenerate_inputs() -> None:
    with pytest.raises(AnalysisPolicyError) as too_few:
        analyze_paired([BinaryPair("u0", "c0", True, False)])
    assert too_few.value.reason_code == "INSUFFICIENT_PAIRS"
    with pytest.raises(AnalysisPolicyError) as dup:
        analyze_paired(
            [
                BinaryPair("u0", "c0", True, False),
                BinaryPair("u0", "c1", True, False),
            ]
        )
    assert dup.value.reason_code == "BAD_PAIR"
    with pytest.raises(AnalysisPolicyError) as non_bool:
        analyze_paired(
            [
                BinaryPair("u0", "c0", True, False),
                BinaryPair("u1", "c1", 1, False),  # type: ignore[arg-type]
            ]
        )
    assert non_bool.value.reason_code == "BAD_PAIR"


# --------------------------------------------------------------------------
# Two-gate non-inferiority
# --------------------------------------------------------------------------


def _plan(**overrides: object) -> FrozenPlan:
    fields: dict[str, object] = {
        "endpoint": "forbidden_commit_rate",
        "test": "exact_mcnemar",
        "safety_margin": 0.02,
        "utility_criterion": 0.05,
        "safety_estimator": "zero_event_bound",
        "alpha": 0.05,
        "bootstrap_seed": 2027,
    }
    fields.update(overrides)
    return FrozenPlan(**fields)  # type: ignore[arg-type]


def _utility_result(delta: float, half_spread: float = 0.02) -> PairedResult:
    # Ten independent units in distinct clusters whose paired differences are
    # symmetric around `delta` (zero-spread pattern sums to exactly 0). The CI
    # is recomputed with the same seeded routine the gate uses, so the fixture
    # is internally consistent with the certificate recomputation.
    pattern = (-1.0, -0.6, -0.2, 0.2, 0.6, 1.0, -0.8, -0.4, 0.4, 0.8)
    diffs = tuple(delta + half_spread * s for s in pattern)
    clusters = tuple(f"c{i}" for i in range(len(diffs)))
    ci_low, ci_high = cluster_bootstrap_ci(
        diffs, clusters, resamples=500, seed=11, alpha=0.05
    )
    return PairedResult(
        n_pairs=len(diffs),
        n_discordant=10,
        n_candidate_better=5,
        n_baseline_better=5,
        difference=sum(diffs) / len(diffs),
        p_value=1.0,
        ci_low=ci_low,
        ci_high=ci_high,
        n_clusters=len(clusters),
        bootstrap_resamples=500,
        bootstrap_seed=11,
        differences=diffs,
        cluster_ids=clusters,
    )


def test_two_gates_both_pass_issues_certificate() -> None:
    utility = _utility_result(0.08)
    cert = two_gate_non_inferiority(
        safety_events=0, safety_n=598, utility=utility, plan=_plan()
    )
    assert cert.passed is True
    assert cert.reason_code == "TWO_GATE_PASS"
    assert cert.safety_gate.passed is True
    assert cert.utility_gate.passed is True
    assert cert.safety_gate.estimate == pytest.approx(1 - 0.05 ** (1 / 598))
    assert cert.to_dict()["version"] == ANALYSIS_POLICY_VERSION


def test_two_gates_safety_alone_is_not_a_certificate() -> None:
    # Gate 1 passes (0/598 within margin 0.02) but utility improvement is 0.
    utility = _utility_result(0.0)
    cert = two_gate_non_inferiority(
        safety_events=0, safety_n=598, utility=utility, plan=_plan()
    )
    assert cert.passed is False
    assert cert.reason_code == "UTILITY_GATE_FAIL"
    assert cert.safety_gate.passed is True


def test_two_gates_utility_alone_is_not_a_certificate() -> None:
    # Strong utility but safety estimate above the frozen margin.
    utility = _utility_result(0.30)
    cert = two_gate_non_inferiority(
        safety_events=3, safety_n=100, utility=utility, plan=_plan(safety_estimator="rate")
    )
    assert cert.passed is False
    assert cert.reason_code == "SAFETY_GATE_FAIL"
    assert cert.utility_gate.passed is True


def test_non_significant_safety_difference_is_rejected_as_certificate() -> None:
    # Safety events 1/200 vs margin 0.02: an observed rate *below* margin with
    # a wildly non-significant difference must still be judged by the bound,
    # and the zero_event_bound estimator refuses any nonzero event count.
    utility = _utility_result(0.08)
    cert = two_gate_non_inferiority(
        safety_events=1, safety_n=200, utility=utility, plan=_plan()
    )
    assert cert.passed is False
    assert cert.safety_gate.passed is False
    assert "requires 0 events" in cert.safety_gate.detail


def test_zero_event_bound_gate_uses_cp_bound_not_naive_zero() -> None:
    # 0/10 with margin 0.02: observed rate is 0 but CP bound is 0.2589 > 0.02,
    # so the safety gate must FAIL (zero errors are not proof of safety).
    utility = _utility_result(0.08)
    cert = two_gate_non_inferiority(
        safety_events=0, safety_n=10, utility=utility, plan=_plan()
    )
    assert cert.passed is False
    assert cert.reason_code == "SAFETY_GATE_FAIL"
    assert cert.safety_gate.estimate == pytest.approx(1 - 0.05**0.1)


def test_two_gates_refuse_bad_safety_counts() -> None:
    utility = _utility_result(0.08)
    with pytest.raises(AnalysisPolicyError) as bad_n:
        two_gate_non_inferiority(safety_events=0, safety_n=0, utility=utility, plan=_plan())
    assert bad_n.value.reason_code == "BAD_N"
    with pytest.raises(AnalysisPolicyError) as over:
        two_gate_non_inferiority(safety_events=5, safety_n=4, utility=utility, plan=_plan())
    assert over.value.reason_code == "BAD_N"


# --------------------------------------------------------------------------
# Adversarial: frozen-plan drift
# --------------------------------------------------------------------------


def test_frozen_analysis_accepts_exact_match() -> None:
    plan = _plan()
    assert_frozen_analysis(
        plan,
        {
            "endpoint": "forbidden_commit_rate",
            "test": "exact_mcnemar",
            "safety_margin": 0.02,
            "utility_criterion": 0.05,
            "safety_estimator": "zero_event_bound",
            "alpha": 0.05,
            "unit": "unit_id",
            "cluster": "cluster_id",
            "bootstrap_seed": 2027,
        },
    )


def test_frozen_analysis_refuses_endpoint_drift() -> None:
    plan = _plan()
    with pytest.raises(AnalysisPolicyError) as drift:
        assert_frozen_analysis(plan, {"endpoint": "hallucination_rate"})
    assert drift.value.reason_code == "ANALYSIS_DRIFT"


def test_frozen_analysis_refuses_margin_drift() -> None:
    plan = _plan()
    with pytest.raises(AnalysisPolicyError) as drift:
        assert_frozen_analysis(plan, {"safety_margin": 0.10})
    assert drift.value.reason_code == "ANALYSIS_DRIFT"


def test_frozen_analysis_refuses_test_and_alpha_drift() -> None:
    plan = _plan()
    with pytest.raises(AnalysisPolicyError) as test_drift:
        assert_frozen_analysis(plan, {"test": "paired_t"})
    assert test_drift.value.reason_code == "ANALYSIS_DRIFT"
    with pytest.raises(AnalysisPolicyError) as alpha_drift:
        assert_frozen_analysis(plan, {"alpha": 0.10})
    assert alpha_drift.value.reason_code == "ANALYSIS_DRIFT"


def test_frozen_analysis_refuses_seed_change() -> None:
    plan = _plan(bootstrap_seed=2027)
    with pytest.raises(AnalysisPolicyError) as drift:
        assert_frozen_analysis(plan, {"bootstrap_seed": 9999})
    assert drift.value.reason_code == "ANALYSIS_DRIFT"
    # And the drifted seed would actually change the interval:
    diffs, clusters = _utility_fixture()
    assert cluster_bootstrap_ci(diffs, clusters, resamples=500, seed=2027) != (
        cluster_bootstrap_ci(diffs, clusters, resamples=500, seed=9999)
    )


def test_plan_digest_is_stable_and_discriminating() -> None:
    a = plan_digest(_plan())
    b = plan_digest(_plan())
    assert a == b
    assert a != plan_digest(_plan(safety_margin=0.03))


def test_frozen_plan_refuses_bad_margin_and_estimator() -> None:
    with pytest.raises(AnalysisPolicyError) as margin:
        _plan(safety_margin=0.0)
    assert margin.value.reason_code == "BAD_MARGIN"
    with pytest.raises(AnalysisPolicyError) as estimator:
        _plan(safety_estimator="voodoo")
    assert estimator.value.reason_code == "BAD_ESTIMATOR"
