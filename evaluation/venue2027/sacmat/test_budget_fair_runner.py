"""Tests for SACMAT-X08_budget_runner — Equal-budget competitor benchmark.

Positive controls:
- All four competitor strategies (sequence-aware, MC/DC static, random,
  coverage-guided) execute under strictly EQUAL query budgets and limits.
- Every strategy consumes queries <= allocated query budget.
- Sequence-aware (PolicyTrace candidate) discovers temporal faults that random
  misses under the exact same query budget.
- MC/DC static kills static obligation mutants but misses temporal ordering
  precedence faults (MUT_SWAP_GRANT_REVOKE).
- Detailed query traces are faithfully recorded for every executed query.
- Cumulative fault discovery curves are monotonically non-decreasing.
- assert_budget_fairness passes on all valid runs.
- JSON serialization of BudgetRunResult round-trips cleanly.
- Determinism: identical seeds yield identical query traces and metrics.

Adversarial controls:
- Budget overrun: strategy consuming > allocated budget is detected and
  refused with BUDGET_OVERRUN.
- Unequal budget allocations rejected in budget_config and assert_budget_fairness
  with UNEQUAL_BUDGET_ALLOCATION.
- Invalid budgets (zero, negative, non-int, bool, or malformed limits)
  fail closed with INVALID_BUDGET.
- Unknown strategies rejected with UNKNOWN_STRATEGY.
- Empty campaigns (no id, no mutants, no strategies) fail closed with EMPTY_CAMPAIGN.
- Timeout / CPU limits are enforced and recorded.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from evaluation.venue2027.sacmat.budget_fair_runner import (
    DEFAULT_STRATEGIES,
    RC_BUDGET_OVERRUN,
    RC_EMPTY_CAMPAIGN,
    RC_INVALID_BUDGET,
    RC_UNEQUAL_BUDGET,
    RC_UNKNOWN_STRATEGY,
    STRATEGY_COVERAGE_GUIDED,
    STRATEGY_MCDC_STATIC,
    STRATEGY_RANDOM,
    STRATEGY_SEQUENCE_AWARE,
    BudgetCampaign,
    BudgetConfig,
    BudgetFairnessError,
    BudgetRunResult,
    DiscoveryPoint,
    QueryRecord,
    StrategyRunResult,
    assert_budget_fairness,
    build_default_campaign,
    build_default_mutant_suite,
    canonicalize_strategy,
    run,
    run_budget_fair,
)
from evaluation.venue2027.sacmat.mutation_ops import (
    MUT_DROP_OBLIGATION,
    MUT_REMOVE_REVOKE,
    MUT_SWAP_GRANT_REVOKE,
)


class TestPositiveControls:
    """Positive test controls for budget-fair execution."""

    def test_all_strategies_run_within_equal_budget(self) -> None:
        campaign = build_default_campaign(seed=42)
        budget = 20
        config = BudgetConfig(query_budget=budget, cpu_limit_seconds=5.0, timeout_seconds=10.0)

        result = run_budget_fair(campaign, config)

        assert isinstance(result, BudgetRunResult)
        assert result.budget_fairness_verified is True
        assert result.status == "COMPLETED"

        # assert_budget_fairness must pass
        assert_budget_fairness(result)

        # Check each strategy
        for strat in DEFAULT_STRATEGIES:
            s_res = result.strategy_results[strat]
            assert s_res.budget_allocated == budget
            assert s_res.queries_consumed <= budget
            assert s_res.queries_consumed > 0
            assert s_res.timed_out is False

    def test_sequence_aware_outperforms_random_on_temporal_faults(self) -> None:
        campaign = build_default_campaign(seed=101)
        budget = 25
        config = BudgetConfig(query_budget=budget)

        result = run_budget_fair(campaign, config)
        seq_res = result.strategy_results[STRATEGY_SEQUENCE_AWARE]
        rnd_res = result.strategy_results[STRATEGY_RANDOM]

        # Equal budget verification
        assert seq_res.budget_allocated == rnd_res.budget_allocated == budget
        assert seq_res.queries_consumed <= budget
        assert rnd_res.queries_consumed <= budget

        # Sequence-aware must find strictly more faults than random
        assert seq_res.faults_discovered > rnd_res.faults_discovered

        # Specifically, check temporal ordering faults (MUT_SWAP_GRANT_REVOKE, MUT_REMOVE_REVOKE)
        seq_killed_ops = {mid.split("-")[1] for mid in seq_res.fault_ids}
        rnd_killed_ops = {mid.split("-")[1] for mid in rnd_res.fault_ids}

        assert MUT_REMOVE_REVOKE in seq_killed_ops
        assert MUT_SWAP_GRANT_REVOKE in seq_killed_ops
        assert MUT_SWAP_GRANT_REVOKE not in rnd_killed_ops

    def test_mcdc_static_kills_static_misses_temporal_swap(self) -> None:
        campaign = build_default_campaign(seed=202)
        budget = 20
        config = BudgetConfig(query_budget=budget)

        result = run_budget_fair(campaign, config)
        mcdc_res = result.strategy_results[STRATEGY_MCDC_STATIC]

        mcdc_killed_ops = {mid.split("-")[1] for mid in mcdc_res.fault_ids}
        # Kills static obligation mutation
        assert MUT_DROP_OBLIGATION in mcdc_killed_ops
        # Misses temporal order precedence mutation
        assert MUT_SWAP_GRANT_REVOKE not in mcdc_killed_ops

    def test_coverage_guided_saturation_properties(self) -> None:
        campaign = build_default_campaign(seed=303)
        budget = 20
        config = BudgetConfig(query_budget=budget)

        result = run_budget_fair(campaign, config)
        cov_res = result.strategy_results[STRATEGY_COVERAGE_GUIDED]

        cov_killed_ops = {mid.split("-")[1] for mid in cov_res.fault_ids}
        assert MUT_DROP_OBLIGATION in cov_killed_ops
        assert MUT_SWAP_GRANT_REVOKE not in cov_killed_ops

    def test_query_trace_recording_integrity(self) -> None:
        campaign = build_default_campaign(seed=404)
        budget = 10
        config = BudgetConfig(query_budget=budget)

        result = run_budget_fair(campaign, config)

        for strat in DEFAULT_STRATEGIES:
            s_res = result.strategy_results[strat]
            assert len(s_res.query_trace) == s_res.queries_consumed
            for idx, q in enumerate(s_res.query_trace, start=1):
                assert isinstance(q, QueryRecord)
                assert q.query_id == idx
                assert q.strategy == strat
                assert q.verdict in ("KILLED", "SURVIVED")
                assert isinstance(q.query_payload, dict)
                assert q.elapsed_ms >= 0.0

    def test_fault_discovery_curve_monotonicity(self) -> None:
        campaign = build_default_campaign(seed=505)
        budget = 20
        config = BudgetConfig(query_budget=budget)

        result = run_budget_fair(campaign, config)

        for strat in DEFAULT_STRATEGIES:
            s_res = result.strategy_results[strat]
            curve = s_res.fault_discovery_curve
            assert len(curve) == s_res.queries_consumed

            prev_faults = 0
            for idx, point in enumerate(curve, start=1):
                assert isinstance(point, DiscoveryPoint)
                assert point.query_index == idx
                assert point.cumulative_faults >= prev_faults
                prev_faults = point.cumulative_faults

            assert curve[-1].cumulative_faults == s_res.faults_discovered

    def test_json_serializability(self) -> None:
        campaign = build_default_campaign(seed=606)
        config = BudgetConfig(query_budget=15)

        result = run_budget_fair(campaign, config)
        data = result.to_dict()

        encoded = json.dumps(data)
        decoded = json.loads(encoded)
        assert decoded["campaign_id"] == campaign.campaign_id
        assert decoded["budget_fairness_verified"] is True
        assert len(decoded["strategy_results"]) == len(DEFAULT_STRATEGIES)

    def test_deterministic_repeatability(self) -> None:
        campaign1 = build_default_campaign(seed=777)
        campaign2 = build_default_campaign(seed=777)
        config = BudgetConfig(query_budget=15)

        res1 = run_budget_fair(campaign1, config)
        res2 = run_budget_fair(campaign2, config)

        for strat in DEFAULT_STRATEGIES:
            r1 = res1.strategy_results[strat]
            r2 = res2.strategy_results[strat]
            assert r1.queries_consumed == r2.queries_consumed
            assert r1.faults_discovered == r2.faults_discovered
            assert r1.fault_ids == r2.fault_ids

    def test_convenience_run_function(self) -> None:
        mutants = build_default_mutant_suite()
        methods = ["sequence_aware", "random"]
        budget = 12

        result = run(methods=methods, mutants=mutants, budget=budget)
        assert isinstance(result, BudgetRunResult)
        assert len(result.strategy_results) == 2
        assert "sequence_aware" in result.strategy_results
        assert "random" in result.strategy_results
        assert_budget_fairness(result)


class TestAdversarialControls:
    """Adversarial test controls for budget fairness violations and edge cases."""

    def test_budget_overrun_rejected_by_assert(self) -> None:
        # Create a result where one strategy overran its allocated budget
        overrun_strat = StrategyRunResult(
            strategy="sequence_aware",
            budget_allocated=20,
            queries_consumed=21,  # OVERRUN!
            cpu_limit_seconds=10.0,
            cpu_time_seconds=0.1,
            wall_time_seconds=0.1,
            timed_out=False,
            faults_discovered=2,
            fault_ids=("MUTANT-1", "MUTANT-2"),
            query_trace=(),
            fault_discovery_curve=(),
        )
        compliant_strat = StrategyRunResult(
            strategy="random",
            budget_allocated=20,
            queries_consumed=20,
            cpu_limit_seconds=10.0,
            cpu_time_seconds=0.1,
            wall_time_seconds=0.1,
            timed_out=False,
            faults_discovered=0,
            fault_ids=(),
            query_trace=(),
            fault_discovery_curve=(),
        )

        with pytest.raises(BudgetFairnessError) as exc_info:
            assert_budget_fairness([overrun_strat, compliant_strat])
        assert exc_info.value.reason_code == RC_BUDGET_OVERRUN

    def test_unequal_budget_allocations_rejected_in_config(self) -> None:
        # BudgetConfig specifies unequal budgets across strategies
        with pytest.raises(BudgetFairnessError) as exc_info:
            BudgetConfig(
                query_budget=20,
                per_strategy_budget={
                    "sequence_aware": 20,
                    "random": 10,  # Unequal!
                },
            )
        assert exc_info.value.reason_code == RC_UNEQUAL_BUDGET

    def test_unequal_budget_allocations_rejected_by_assert(self) -> None:
        strat1 = StrategyRunResult(
            strategy="sequence_aware",
            budget_allocated=25,
            queries_consumed=20,
            cpu_limit_seconds=10.0,
            cpu_time_seconds=0.1,
            wall_time_seconds=0.1,
            timed_out=False,
            faults_discovered=2,
            fault_ids=(),
            query_trace=(),
            fault_discovery_curve=(),
        )
        strat2 = StrategyRunResult(
            strategy="random",
            budget_allocated=20,  # Unequal allocation!
            queries_consumed=20,
            cpu_limit_seconds=10.0,
            cpu_time_seconds=0.1,
            wall_time_seconds=0.1,
            timed_out=False,
            faults_discovered=0,
            fault_ids=(),
            query_trace=(),
            fault_discovery_curve=(),
        )

        with pytest.raises(BudgetFairnessError) as exc_info:
            assert_budget_fairness([strat1, strat2])
        assert exc_info.value.reason_code == RC_UNEQUAL_BUDGET

    @pytest.mark.parametrize(
        ("query_budget", "cpu_limit", "timeout"),
        [
            (0, 10.0, 30.0),
            (-5, 10.0, 30.0),
            (True, 10.0, 30.0),
            ("20", 10.0, 30.0),
            (20, 0.0, 30.0),
            (20, -1.0, 30.0),
            (20, True, 30.0),
            (20, 10.0, 0.0),
            (20, 10.0, -2.0),
        ],
    )
    def test_invalid_budget_parameters(
        self, query_budget: Any, cpu_limit: Any, timeout: Any
    ) -> None:
        with pytest.raises(BudgetFairnessError) as exc_info:
            BudgetConfig(
                query_budget=query_budget,
                cpu_limit_seconds=cpu_limit,
                timeout_seconds=timeout,
            )
        assert exc_info.value.reason_code == RC_INVALID_BUDGET

    def test_empty_campaign_rejected(self) -> None:
        with pytest.raises(BudgetFairnessError) as exc_info:
            camp = BudgetCampaign(campaign_id="", mutants=["m1"])
            camp.validate()
        assert exc_info.value.reason_code == RC_EMPTY_CAMPAIGN

        with pytest.raises(BudgetFairnessError) as exc_info:
            camp = BudgetCampaign(campaign_id="test", mutants=[])
            camp.validate()
        assert exc_info.value.reason_code == RC_EMPTY_CAMPAIGN

        with pytest.raises(BudgetFairnessError) as exc_info:
            camp = BudgetCampaign(campaign_id="test", mutants=["m1"], strategies=())
            camp.validate()
        assert exc_info.value.reason_code == RC_EMPTY_CAMPAIGN

    def test_unknown_strategy_rejected(self) -> None:
        with pytest.raises(BudgetFairnessError) as exc_info:
            canonicalize_strategy("unregistered_magic_strategy")
        assert exc_info.value.reason_code == RC_UNKNOWN_STRATEGY

    def test_empty_results_assert_budget_fairness(self) -> None:
        with pytest.raises(BudgetFairnessError) as exc_info:
            assert_budget_fairness([])
        assert exc_info.value.reason_code == RC_EMPTY_CAMPAIGN

    def test_timeout_enforcement(self) -> None:
        campaign = build_default_campaign(seed=999)
        # Allocate huge budget but microscopic timeout so execution aborts
        config = BudgetConfig(query_budget=1000, timeout_seconds=0.0001)

        result = run_budget_fair(campaign, config)
        # All strategies must stop within budget and flag timed_out
        for strat in DEFAULT_STRATEGIES:
            s_res = result.strategy_results[strat]
            assert s_res.queries_consumed <= 1000
            assert s_res.timed_out is True
        assert_budget_fairness(result)
