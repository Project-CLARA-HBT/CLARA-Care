"""Analysis and metrics module for E04 randomized TOCTOU campaign.

Computes forbidden commit rates, Wilson confidence intervals (2-sided and 1-sided
upper bound), safe rejection rates, indeterminate rates, categorical breakdowns,
and classification stability across jitter repetitions.

Primary endpoint: forbidden_commit_rate (target = 0.0, zero forbidden commits).
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from evaluation.glhs_toctou_r2.grammar import ScheduleDescriptor

try:
    from scipy.stats import norm  # type: ignore
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

COMMITTED_OUTCOMES: frozenset[str] = frozenset({
    "transition_committed",
    "proposal_committed",
    "retried_committed",
})


def _z_critical(confidence: float, one_sided: bool) -> float:
    """Compute critical value z for normal distribution quantile."""
    if _HAS_SCIPY:
        if one_sided:
            return float(norm.ppf(confidence))
        return float(norm.ppf(1.0 - (1.0 - confidence) / 2.0))

    if one_sided:
        if abs(confidence - 0.95) < 1e-4:
            return 1.6448536269514722
        if abs(confidence - 0.99) < 1e-4:
            return 2.3263478740408408
        if abs(confidence - 0.90) < 1e-4:
            return 1.2815515655446004
    else:
        if abs(confidence - 0.95) < 1e-4:
            return 1.959963984540054
        if abs(confidence - 0.99) < 1e-4:
            return 2.5758293035489004
        if abs(confidence - 0.90) < 1e-4:
            return 1.6448536269514722

    p = confidence if one_sided else (1.0 - (1.0 - confidence) / 2.0)
    t = math.sqrt(-2.0 * math.log(1.0 - p))
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    return t - ((c2 * t + c1) * t + c0) / (((d3 * t + d2) * t + d1) * t + 1.0)


def compute_wilson_score_interval(
    k: int, n: int, confidence: float = 0.95, one_sided: bool = False
) -> tuple[float, float]:
    """Compute Wilson score confidence interval for a binomial proportion.

    Returns (lower_bound, upper_bound) rounded to 6 decimal places.
    """
    if n <= 0:
        return (0.0, 0.0)

    z = _z_critical(confidence, one_sided)
    p_hat = k / n
    denom = 1.0 + (z**2) / n
    center = (p_hat + (z**2) / (2.0 * n)) / denom
    margin = (z / denom) * math.sqrt(
        max(0.0, (p_hat * (1.0 - p_hat) / n) + (z**2) / (4.0 * (n**2)))
    )

    lower = 0.0 if one_sided else max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return (round(lower, 6), round(upper, 6))


def compute_one_sided_wilson_upper(
    k: int, n: int, confidence: float = 0.95
) -> float:
    """Compute the 1-sided Wilson score upper bound at the given confidence level."""
    _, upper = compute_wilson_score_interval(k, n, confidence=confidence, one_sided=True)
    return upper


@dataclass(frozen=True)
class CategoricalMetrics:
    """Metrics breakdown for a single category dimension."""

    category: str
    total_executed: int
    forbidden_count: int
    safe_rejection_count: int
    indeterminate_count: int
    operational_count: int
    admit_count: int
    forbidden_rate: float
    wilson_95_upper: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "total_executed": self.total_executed,
            "forbidden_count": self.forbidden_count,
            "safe_rejection_count": self.safe_rejection_count,
            "indeterminate_count": self.indeterminate_count,
            "operational_count": self.operational_count,
            "admit_count": self.admit_count,
            "forbidden_rate": round(self.forbidden_rate, 6),
            "wilson_95_upper": round(self.wilson_95_upper, 6),
        }


@dataclass(frozen=True)
class CampaignAnalysis:
    """Statistical summary of an E04 TOCTOU campaign run."""

    total_schedules: int
    executed_schedules: int
    forbidden_count: int
    safe_rejection_count: int
    indeterminate_count: int
    operational_count: int
    admit_count: int
    forbidden_commit_rate: float
    forbidden_commit_rate_ci_95: tuple[float, float]
    forbidden_commit_rate_upper_95: float
    safe_rejection_rate: float
    indeterminate_rate: float
    operational_rate: float
    admit_rate: float
    primary_endpoint_pass: bool
    timing_breakdown: dict[str, CategoricalMetrics] = field(default_factory=dict)
    mutation_breakdown: dict[str, CategoricalMetrics] = field(default_factory=dict)
    entity_breakdown: dict[str, CategoricalMetrics] = field(default_factory=dict)
    modifier_breakdown: dict[str, CategoricalMetrics] = field(default_factory=dict)
    classification_stability: float | None = None
    freeze_id: str = "GLHS-POSTGRES-TOCTOU-E04-20260928-01"
    total_executions: int = 0
    forbidden_commits_observed: int = 0
    primary_endpoint_met: bool = True
    overall_pass: bool = True
    outcomes_breakdown: dict[str, int] = field(default_factory=dict)
    per_timing_mode: dict[str, dict[str, int]] = field(default_factory=dict)
    per_entity_config: dict[str, dict[str, int]] = field(default_factory=dict)
    generated_at_utc: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "freeze_id": self.freeze_id,
            "total_schedules": self.total_schedules,
            "executed_schedules": self.executed_schedules,
            "total_executions": self.executed_schedules,
            "forbidden_count": self.forbidden_count,
            "forbidden_commits_observed": self.forbidden_count,
            "safe_rejection_count": self.safe_rejection_count,
            "indeterminate_count": self.indeterminate_count,
            "operational_count": self.operational_count,
            "admit_count": self.admit_count,
            "forbidden_commit_rate": round(self.forbidden_commit_rate, 6),
            "forbidden_commit_rate_ci_95": list(self.forbidden_commit_rate_ci_95),
            "forbidden_commit_rate_upper_95": round(self.forbidden_commit_rate_upper_95, 6),
            "safe_rejection_rate": round(self.safe_rejection_rate, 6),
            "indeterminate_rate": round(self.indeterminate_rate, 6),
            "operational_rate": round(self.operational_rate, 6),
            "admit_rate": round(self.admit_rate, 6),
            "primary_endpoint_pass": self.primary_endpoint_pass,
            "primary_endpoint_met": self.primary_endpoint_pass,
            "overall_pass": self.primary_endpoint_pass and self.executed_schedules >= 1024,
            "timing_breakdown": {k: v.to_dict() for k, v in self.timing_breakdown.items()},
            "mutation_breakdown": {k: v.to_dict() for k, v in self.mutation_breakdown.items()},
            "entity_breakdown": {k: v.to_dict() for k, v in self.entity_breakdown.items()},
            "modifier_breakdown": {k: v.to_dict() for k, v in self.modifier_breakdown.items()},
            "classification_stability": (
                round(self.classification_stability, 6)
                if self.classification_stability is not None
                else None
            ),
        }


def _breakdown_by_dimension(
    results: Sequence[Mapping[str, Any]], key_extractor: Any
) -> dict[str, CategoricalMetrics]:
    """Group results by a key dimension and compute CategoricalMetrics per group."""
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for r in results:
        keys = key_extractor(r)
        if isinstance(keys, (tuple, list, set)):
            for k in keys:
                groups[str(k)].append(r)
        else:
            groups[str(keys)].append(r)

    metrics_map: dict[str, CategoricalMetrics] = {}
    for group_key, items in sorted(groups.items()):
        total = len(items)
        forbidden = sum(
            1 for r in items if r.get("forbidden") or r.get("oracle_classification") == "FORBIDDEN_COMMIT" or r.get("oracle_classification") == "FORBIDDEN"
        )
        safe_rej = sum(
            1 for r in items
            if (r.get("oracle_classification") in ("SAFE", "SAFE_REJECTED_AFTER_GOVERNANCE_MUTATION"))
            and r.get("commit_outcome") not in COMMITTED_OUTCOMES
        )
        indet = sum(
            1 for r in items if r.get("indeterminate") or r.get("oracle_classification") in ("INDETERMINATE", "INDETERMINATE_ORDERING")
        )
        ops = sum(
            1 for r in items if r.get("operational") or r.get("oracle_classification") in ("OPERATIONAL", "OPERATIONAL_DEADLOCK")
        )
        admit = sum(
            1 for r in items
            if (r.get("oracle_classification") in ("SAFE", "COMMITTED_BEFORE_GOVERNANCE_MUTATION"))
            and r.get("commit_outcome") in COMMITTED_OUTCOMES
        )
        rate = forbidden / total if total > 0 else 0.0
        upper = compute_one_sided_wilson_upper(forbidden, total)

        metrics_map[group_key] = CategoricalMetrics(
            category=group_key,
            total_executed=total,
            forbidden_count=forbidden,
            safe_rejection_count=safe_rej,
            indeterminate_count=indet,
            operational_count=ops,
            admit_count=admit,
            forbidden_rate=rate,
            wilson_95_upper=upper,
        )

    return metrics_map


def compute_classification_stability(
    results_primary: Sequence[Mapping[str, Any]],
    results_repeat: Sequence[Mapping[str, Any]],
) -> float:
    """Compute classification stability (agreement rate) between two runs."""
    by_id_primary = {
        str(r["schedule_id"]): str(r.get("oracle_classification", r.get("commit_outcome", "")))
        for r in results_primary
        if "schedule_id" in r
    }
    by_id_repeat = {
        str(r["schedule_id"]): str(r.get("oracle_classification", r.get("commit_outcome", "")))
        for r in results_repeat
        if "schedule_id" in r
    }
    common = set(by_id_primary) & set(by_id_repeat)
    if not common:
        return 0.0
    matches = sum(1 for sid in common if by_id_primary[sid] == by_id_repeat[sid])
    return matches / len(common)


def analyze_campaign_results(
    run_record_or_schedules: Mapping[str, Any] | Sequence[ScheduleDescriptor],
    repeat_record_or_runs: Mapping[str, Any] | Sequence[dict[str, Any]] | None = None,
) -> CampaignAnalysis:
    """Analyze an E04 campaign run record and return a CampaignAnalysis."""
    if isinstance(run_record_or_schedules, Mapping):
        run_record = run_record_or_schedules
        results: list[Mapping[str, Any]] = list(run_record.get("results", []))
        executed_schedules = len(results)
        total_schedules = int(run_record.get("total_schedules", executed_schedules))

        repeat_record = repeat_record_or_runs if isinstance(repeat_record_or_runs, Mapping) else None
    else:
        schedules = list(run_record_or_schedules)
        runs = list(repeat_record_or_runs) if repeat_record_or_runs is not None else []
        results = runs
        executed_schedules = len(runs)
        total_schedules = len(schedules)
        repeat_record = None

    forbidden_count = sum(
        1 for r in results if r.get("forbidden") or r.get("oracle_classification") in ("FORBIDDEN", "FORBIDDEN_COMMIT") or r.get("forbidden_commit_observed") is True
    )
    safe_rejection_count = sum(
        1 for r in results
        if r.get("oracle_classification") in ("SAFE", "SAFE_REJECTED_AFTER_GOVERNANCE_MUTATION")
        and r.get("commit_outcome") not in COMMITTED_OUTCOMES
    )
    indeterminate_count = sum(
        1 for r in results if r.get("indeterminate") or r.get("oracle_classification") in ("INDETERMINATE", "INDETERMINATE_ORDERING")
    )
    operational_count = sum(
        1 for r in results if r.get("operational") or r.get("oracle_classification") in ("OPERATIONAL", "OPERATIONAL_DEADLOCK")
    )
    admit_count = sum(
        1 for r in results
        if r.get("oracle_classification") in ("SAFE", "COMMITTED_BEFORE_GOVERNANCE_MUTATION")
        and r.get("commit_outcome") in COMMITTED_OUTCOMES
    )

    forbidden_commit_rate = forbidden_count / executed_schedules if executed_schedules > 0 else 0.0
    ci_95 = compute_wilson_score_interval(forbidden_count, executed_schedules, confidence=0.95, one_sided=False)
    upper_95 = compute_one_sided_wilson_upper(forbidden_count, executed_schedules, confidence=0.95)

    safe_rejection_rate = safe_rejection_count / executed_schedules if executed_schedules > 0 else 0.0
    indeterminate_rate = indeterminate_count / executed_schedules if executed_schedules > 0 else 0.0
    operational_rate = operational_count / executed_schedules if executed_schedules > 0 else 0.0
    admit_rate = admit_count / executed_schedules if executed_schedules > 0 else 0.0

    primary_endpoint_pass = forbidden_count == 0

    timing_bd = _breakdown_by_dimension(results, lambda r: r.get("timing", "unknown"))
    mutation_bd = _breakdown_by_dimension(results, lambda r: r.get("mutations_applied", ["unknown"]))
    entity_bd = _breakdown_by_dimension(results, lambda r: r.get("entity", "unknown"))
    modifier_bd = _breakdown_by_dimension(results, lambda r: r.get("modifier", "unknown"))

    per_timing: dict[str, dict[str, int]] = {}
    for k, v in timing_bd.items():
        per_timing[k] = {"total": v.total_executed, "pass": v.total_executed - v.forbidden_count, "forbidden": v.forbidden_count}

    per_entity: dict[str, dict[str, int]] = {}
    for k, v in entity_bd.items():
        per_entity[k] = {"total": v.total_executed, "pass": v.total_executed - v.forbidden_count, "forbidden": v.forbidden_count}

    outcomes_ctr: Counter[str] = Counter()
    for r in results:
        outcomes_ctr[str(r.get("commit_outcome", r.get("actual_outcome", "UNKNOWN")))] += 1

    stability: float | None = None
    if repeat_record is not None and "results" in repeat_record:
        repeat_results = list(repeat_record["results"])
        stability = compute_classification_stability(results, repeat_results)

    return CampaignAnalysis(
        total_schedules=total_schedules,
        executed_schedules=executed_schedules,
        forbidden_count=forbidden_count,
        safe_rejection_count=safe_rejection_count,
        indeterminate_count=indeterminate_count,
        operational_count=operational_count,
        admit_count=admit_count,
        forbidden_commit_rate=forbidden_commit_rate,
        forbidden_commit_rate_ci_95=ci_95,
        forbidden_commit_rate_upper_95=upper_95,
        safe_rejection_rate=safe_rejection_rate,
        indeterminate_rate=indeterminate_rate,
        operational_rate=operational_rate,
        admit_rate=admit_rate,
        primary_endpoint_pass=primary_endpoint_pass,
        timing_breakdown=timing_bd,
        mutation_breakdown=mutation_bd,
        entity_breakdown=entity_bd,
        modifier_breakdown=modifier_bd,
        classification_stability=stability,
        total_executions=executed_schedules,
        forbidden_commits_observed=forbidden_count,
        primary_endpoint_met=primary_endpoint_pass,
        overall_pass=primary_endpoint_pass and executed_schedules >= 1024,
        outcomes_breakdown=dict(outcomes_ctr),
        per_timing_mode=per_timing,
        per_entity_config=per_entity,
    )


def analyze_e04_results(
    schedules: Sequence[ScheduleDescriptor],
    runs: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Backwards-compatible dict analyzer."""
    analysis = analyze_campaign_results(schedules, runs)
    return analysis.to_dict()


def generate_summary_report(analysis: CampaignAnalysis | dict[str, Any]) -> str:
    """Format a CampaignAnalysis into a human-readable summary report."""
    if isinstance(analysis, dict):
        primary_pass = analysis.get("primary_endpoint_met", False)
        total_sched = analysis.get("total_schedules", 0)
        exec_sched = analysis.get("total_executions", 0)
        forbid_cnt = analysis.get("forbidden_commits_observed", 0)
        forbid_rate = forbid_cnt / exec_sched if exec_sched > 0 else 0.0
        ci_95 = compute_wilson_score_interval(forbid_cnt, exec_sched)
        upper_95 = compute_one_sided_wilson_upper(forbid_cnt, exec_sched)
        safe_rej_cnt = 0
        safe_rej_rate = 0.0
        admit_cnt = 0
        admit_rate = 0.0
        indet_cnt = 0
        indet_rate = 0.0
        ops_cnt = 0
        ops_rate = 0.0
        stability = None
        timing_bd = {}
        entity_bd = {}
    else:
        primary_pass = analysis.primary_endpoint_pass
        total_sched = analysis.total_schedules
        exec_sched = analysis.executed_schedules
        forbid_cnt = analysis.forbidden_count
        forbid_rate = analysis.forbidden_commit_rate
        ci_95 = analysis.forbidden_commit_rate_ci_95
        upper_95 = analysis.forbidden_commit_rate_upper_95
        safe_rej_cnt = analysis.safe_rejection_count
        safe_rej_rate = analysis.safe_rejection_rate
        admit_cnt = analysis.admit_count
        admit_rate = analysis.admit_rate
        indet_cnt = analysis.indeterminate_count
        indet_rate = analysis.indeterminate_rate
        ops_cnt = analysis.operational_count
        ops_rate = analysis.operational_rate
        stability = analysis.classification_stability
        timing_bd = analysis.timing_breakdown
        entity_bd = analysis.entity_breakdown

    status_str = "PASS (0 Forbidden Commits)" if primary_pass else "FAIL (Forbidden Commits Detected)"
    lines = [
        "============================================================",
        "E04: Generated PostgreSQL TOCTOU Campaign Analysis Report",
        "============================================================",
        f"Primary Status:                 {status_str}",
        f"Total Schedules Generated:       {total_sched}",
        f"Executed Schedules:             {exec_sched}",
        f"Forbidden Commits:              {forbid_cnt}",
        f"Forbidden Commit Rate:          {forbid_rate:.6f}",
        f"95% Wilson CI (2-sided):        [{ci_95[0]:.6f}, {ci_95[1]:.6f}]",
        f"95% Wilson Upper Bound:         {upper_95:.6f}",
        f"Safe Rejection Rate:            {safe_rej_rate:.4f} ({safe_rej_cnt})",
        f"Admitted Control Rate:          {admit_rate:.4f} ({admit_cnt})",
        f"Indeterminate Rate:             {indet_rate:.4f} ({indet_cnt})",
        f"Operational Fault Rate:         {ops_rate:.4f} ({ops_cnt})",
    ]
    if stability is not None:
        lines.append(f"Classification Stability:       {stability:.4f}")
    if timing_bd:
        lines.append("------------------------------------------------------------")
        lines.append("Timing Mode Breakdown:")
        for key, metrics in timing_bd.items():
            lines.append(
                f"  - {key:<28}: N={metrics.total_executed:<4} | Forbidden={metrics.forbidden_count} | 95% UB={metrics.wilson_95_upper:.4f}"
            )
    if entity_bd:
        lines.append("------------------------------------------------------------")
        lines.append("Entity Config Breakdown:")
        for key, metrics in entity_bd.items():
            lines.append(
                f"  - {key:<28}: N={metrics.total_executed:<4} | Forbidden={metrics.forbidden_count} | 95% UB={metrics.wilson_95_upper:.4f}"
            )
    lines.append("============================================================")
    return "\n".join(lines)


def generate_summary_markdown(summary: dict[str, Any]) -> str:
    """Generate Markdown report for E04 campaign summary."""
    return generate_summary_report(summary)
