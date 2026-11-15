"""CLARA-Care 2027 shared task SH-analysis_policy — frozen inferential analysis.

Purpose
-------
Program-level preregistered analysis contract reused by all nine venue2027
studies (``research/venue2027/GATES/SCIENTIFIC_METRICS_CONTRACT.md`` rule 3:
a zero-event outcome has a finite Clopper-Pearson confidence bound; rule 4:
safety non-inferiority is never demonstrated by ``p > 0.05`` or by zero
observed errors;
``research/venue2027/GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md`` rules 5-6:
non-inferiority and benefit require **two separate gates** — a predeclared
one-sided safety bound that meets the margin AND a utility improvement that
meets its decision criterion — and 0 failures in ``n`` independent Bernoulli
units has one-sided 95% upper bound ``1 - 0.05**(1/n)``).

Components
----------
- :class:`PairedResult` — point estimate, two-sided exact McNemar p-value
  (exact binomial on discordant pairs), two-sided cluster bootstrap CI on the
  paired mean difference (seeded, deterministic; whole ``cluster_id`` groups
  are resampled so repeated events inside one patient/history are never
  treated as independent draws), plus the raw per-unit differences retained
  for recalculation (evidence protocol rule 8).
- :func:`mcnemar_exact` — exact McNemar on discordant pairs, stdlib only.
- :func:`clopper_pearson_zero_upper` — ``1 - alpha**(1/n)`` zero-event upper
  bound (N=598 gives ≈0.0050 per the scientific metrics contract).
- :func:`two_gate_non_inferiority` — the two-gate certificate: gate 1 is a
  one-sided safety bound that must meet the frozen margin; gate 2 is the
  utility improvement that must meet its frozen criterion. BOTH gates must
  pass; a non-significant safety difference is never a certificate, and the
  gates are evaluated independently of statistical significance labels.
- :func:`assert_frozen_analysis` — refuses post-hoc drift of endpoint, test,
  margin, unit, alpha or seed against the frozen plan (stable reason code
  ``ANALYSIS_DRIFT``).

Allowed input
-------------
JSON-serializable paired records (:class:`BinaryPair`) plus a
:class:`FrozenPlan` of plain scalars. No network, no database, no live
provider access; stdlib only (math, random, json, hashlib, dataclasses).

Failure semantics
-----------------
Fail closed with stable uppercase reason codes (``ANALYSIS_DRIFT``,
``INSUFFICIENT_PAIRS``, ``BAD_PAIR``, ``BAD_MARGIN``, ``BAD_ALPHA``,
``BAD_N``, ``BAD_SEED``, ``EMPTY_CLUSTERS``, ``BAD_ESTIMATOR``). An empty or
unusable analysis is refused, never reported as a null result; INDETERMINATE
inputs are the caller's exclusion problem and are never silently dropped or
coerced here.

Version
-------
``ANALYSIS_POLICY_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import random
from collections.abc import Mapping, Sequence
from typing import Any

ANALYSIS_POLICY_VERSION = "1.0.0"

REASON_CODE_ANALYSIS_DRIFT = "ANALYSIS_DRIFT"


class AnalysisPolicyError(ValueError):
    """Refusal with a stable, machine-checkable reason code."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(f"{reason_code}: {message}")
        self.reason_code = reason_code


# --------------------------------------------------------------------------
# Exact binomial tail helpers (stdlib only)
# --------------------------------------------------------------------------


def _binom_pmf(k: int, n: int, p: float) -> float:
    if not 0 <= k <= n:
        return 0.0
    log_pmf = (
        math.lgamma(n + 1)
        - math.lgamma(k + 1)
        - math.lgamma(n - k + 1)
        + k * math.log(p)
        + (n - k) * math.log1p(-p)
    )
    return math.exp(log_pmf)


def _binom_two_sided_p(k: int, n: int) -> float:
    """Two-sided exact binomial p-value at p=0.5, capped at 1.0.

    Doubles the tail at or beyond the observed count in the lesser direction;
    this is the exact McNemar statistic on discordant pairs.
    """

    if n == 0:
        return 1.0
    lesser = min(k, n - k)
    tail = sum(_binom_pmf(i, n, 0.5) for i in range(lesser + 1))
    return min(1.0, 2.0 * tail)


# --------------------------------------------------------------------------
# Paired binary records and result
# --------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class BinaryPair:
    """One paired binary outcome on an independent unit.

    ``candidate_success`` / ``baseline_success`` must be strict booleans;
    INDETERMINATE outcomes must be excluded by the caller (they are never
    coerced to a failure or a success here).
    """

    unit_id: str
    cluster_id: str
    candidate_success: bool
    baseline_success: bool

    def __post_init__(self) -> None:
        for name in ("candidate_success", "baseline_success"):
            value = getattr(self, name)
            if not isinstance(value, bool):
                raise AnalysisPolicyError(
                    "BAD_PAIR", f"{name} must be a bool, got {type(value).__name__}"
                )
        if not self.unit_id:
            raise AnalysisPolicyError("BAD_PAIR", "unit_id must be non-empty")


@dataclasses.dataclass(frozen=True)
class PairedResult:
    """Frozen output of the paired analysis on independent units.

    ``p_value`` is the two-sided exact McNemar p (exact binomial on
    discordant pairs). ``ci_low``/``ci_high`` bound the paired difference
    proportion (candidate − baseline) via a seeded cluster bootstrap that
    resamples whole ``cluster_id`` groups. ``differences`` and
    ``cluster_ids`` retain the raw per-unit evidence so any endpoint can be
    recalculated from raw events (evidence protocol rule 8).
    """

    n_pairs: int
    n_discordant: int
    n_candidate_better: int
    n_baseline_better: int
    difference: float
    p_value: float
    ci_low: float
    ci_high: float
    n_clusters: int
    bootstrap_resamples: int
    bootstrap_seed: int
    differences: tuple[float, ...]
    cluster_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def mcnemar_exact(pairs: Sequence[BinaryPair]) -> tuple[int, int, float]:
    """Exact two-sided McNemar test on discordant pairs.

    Returns ``(candidate_better, baseline_better, p_value)``. Pairs where both
    arms agree are concordant and carry no McNemar information.
    """

    better = sum(1 for p in pairs if p.candidate_success and not p.baseline_success)
    worse = sum(1 for p in pairs if not p.candidate_success and p.baseline_success)
    p = _binom_two_sided_p(better, better + worse)
    return better, worse, p


def _percentile(sorted_vals: Sequence[float], q: float) -> float:
    pos = (len(sorted_vals) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def cluster_bootstrap_ci(
    differences: Sequence[float],
    clusters: Sequence[str],
    *,
    resamples: int,
    seed: int,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Two-sided percentile bootstrap CI over whole-cluster resamples.

    Seeded and deterministic: the same inputs always produce the identical
    interval, and resampling a statistically identical cluster multiset is
    memoized so the RNG stream is consumed exactly once. Cluster ids are
    sorted before indexing so cluster order cannot perturb the stream.
    """

    if len(differences) != len(clusters):
        raise AnalysisPolicyError("BAD_PAIR", "differences/clusters length mismatch")
    if not 0.0 < alpha < 1.0:
        raise AnalysisPolicyError("BAD_ALPHA", "alpha must be in (0, 1)")
    if resamples < 1:
        raise AnalysisPolicyError("BAD_SEED", "resamples must be >= 1")
    n_clusters = len(set(clusters))
    if n_clusters == 0:
        raise AnalysisPolicyError("EMPTY_CLUSTERS", "no clusters to resample")
    by_cluster: dict[str, list[float]] = {}
    for cluster, value in zip(clusters, differences, strict=True):
        by_cluster.setdefault(cluster, []).append(value)
    ordered = sorted(by_cluster)
    unit_lists = [by_cluster[c] for c in ordered]
    stats: list[float] = []
    cache: dict[tuple[int, ...], float] = {}
    rng = random.Random(seed)
    for _ in range(resamples):
        picked = tuple(rng.randrange(n_clusters) for _ in range(n_clusters))
        stat = cache.get(picked)
        if stat is None:
            pooled = [v for idx in picked for v in unit_lists[idx]]
            stat = sum(pooled) / len(pooled)
            cache[picked] = stat
        stats.append(stat)
    stats.sort()
    lo_q = alpha / 2.0
    hi_q = 1.0 - alpha / 2.0
    return _percentile(stats, lo_q), _percentile(stats, hi_q)


def analyze_paired(
    pairs: Sequence[BinaryPair],
    *,
    bootstrap_resamples: int = 2000,
    bootstrap_seed: int = 2027,
) -> PairedResult:
    """Run the frozen paired analysis: exact McNemar + cluster bootstrap CI.

    Deterministic: the same inputs, seed and resample count always yield the
    identical :class:`PairedResult` (no hidden clock or OS randomness).
    """

    if len(pairs) < 2:
        raise AnalysisPolicyError(
            "INSUFFICIENT_PAIRS", f"need >= 2 paired units, got {len(pairs)}"
        )
    ids = [p.unit_id for p in pairs]
    if len(set(ids)) != len(ids):
        raise AnalysisPolicyError("BAD_PAIR", "duplicate unit_id in paired records")
    better, worse, p_value = mcnemar_exact(pairs)
    diffs = [float(p.candidate_success) - float(p.baseline_success) for p in pairs]
    clusters = [p.cluster_id for p in pairs]
    point = sum(diffs) / len(diffs)
    ci_low, ci_high = cluster_bootstrap_ci(
        diffs,
        clusters,
        resamples=bootstrap_resamples,
        seed=bootstrap_seed,
        alpha=0.05,
    )
    return PairedResult(
        n_pairs=len(pairs),
        n_discordant=better + worse,
        n_candidate_better=better,
        n_baseline_better=worse,
        difference=point,
        p_value=p_value,
        ci_low=ci_low,
        ci_high=ci_high,
        n_clusters=len(set(clusters)),
        bootstrap_resamples=bootstrap_resamples,
        bootstrap_seed=bootstrap_seed,
        differences=tuple(diffs),
        cluster_ids=tuple(clusters),
    )


# --------------------------------------------------------------------------
# Clopper-Pearson zero-event upper bound
# --------------------------------------------------------------------------


def clopper_pearson_zero_upper(n: int, alpha: float = 0.05) -> float:
    """One-sided Clopper-Pearson upper bound after 0 failures in ``n`` trials.

    Exactly ``1 - alpha**(1/n)`` (scientific metrics contract rule 3): 598
    independent units with zero forbidden events gives ≈0.0050.
    """

    if n < 1:
        raise AnalysisPolicyError("BAD_N", "n must be >= 1")
    if not 0.0 < alpha < 1.0:
        raise AnalysisPolicyError("BAD_ALPHA", "alpha must be in (0, 1)")
    return 1.0 - alpha ** (1.0 / n)


# --------------------------------------------------------------------------
# Frozen plan + two-gate non-inferiority certificate
# --------------------------------------------------------------------------

_SAFETY_ESTIMATORS = ("rate", "zero_event_bound")


@dataclasses.dataclass(frozen=True)
class FrozenPlan:
    """Preregistered analysis plan; every field is frozen before holdout.

    - ``endpoint``: name of the primary endpoint (frozen free text).
    - ``test``: inferential test label, e.g. ``"exact_mcnemar"``.
    - ``safety_margin``: one-sided upper bound the safety-event estimate must
      not exceed (gate 1 threshold). Strictly inside (0, 1).
    - ``utility_criterion``: minimum acceptable utility improvement
      (candidate − baseline) point estimate (gate 2 threshold).
    - ``safety_estimator``: ``"rate"`` uses the observed event rate;
      ``"zero_event_bound"`` requires zero events and uses the
      Clopper-Pearson upper bound at ``alpha``.
    - ``alpha``: one-sided confidence level for gate 1 (default 0.05).
    - ``unit`` / ``cluster``: independent-unit and cluster field names.
    - ``bootstrap_seed``: frozen seed; changing it is analysis drift.
    """

    endpoint: str
    test: str
    safety_margin: float
    utility_criterion: float
    safety_estimator: str = "rate"
    alpha: float = 0.05
    unit: str = "unit_id"
    cluster: str = "cluster_id"
    bootstrap_seed: int = 2027

    def __post_init__(self) -> None:
        if not 0.0 < self.safety_margin < 1.0:
            raise AnalysisPolicyError("BAD_MARGIN", "safety_margin must be in (0, 1)")
        if self.safety_estimator not in _SAFETY_ESTIMATORS:
            raise AnalysisPolicyError(
                "BAD_ESTIMATOR", f"safety_estimator must be one of {_SAFETY_ESTIMATORS}"
            )
        if not 0.0 < self.alpha < 1.0:
            raise AnalysisPolicyError("BAD_ALPHA", "alpha must be in (0, 1)")


def plan_digest(plan: FrozenPlan) -> str:
    """Stable SHA256 digest of the frozen plan (canonical JSON)."""

    payload = json.dumps(dataclasses.asdict(plan), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def assert_frozen_analysis(plan: FrozenPlan, actual: Mapping[str, Any]) -> None:
    """Refuse post-hoc analysis changes (stable reason code ANALYSIS_DRIFT).

    ``actual`` is the analysis actually performed, keyed by the same field
    names as :class:`FrozenPlan`. Every frozen field present in ``actual``
    must match the plan exactly; performing a different endpoint, test,
    margin, unit, alpha or seed than the frozen plan is drift and is refused.
    ``actual`` may omit fields (partial records are checked field by field),
    but any present mismatch fails closed.
    """

    frozen = dataclasses.asdict(plan)
    for key in sorted(frozen):
        if key not in actual:
            continue
        declared = frozen[key]
        performed = actual[key]
        if declared != performed:
            raise AnalysisPolicyError(
                REASON_CODE_ANALYSIS_DRIFT,
                f"frozen field {key!r}: plan {declared!r} != actual {performed!r}",
            )


# --------------------------------------------------------------------------
# Two-gate certificate
# --------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class GateOutcome:
    """One gate of the two-gate certificate."""

    gate: str
    passed: bool
    estimate: float
    threshold: float
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class CertificateResult:
    """Outcome of the two-gate non-inferiority evaluation.

    ``passed`` is True only when BOTH the safety gate and the utility gate
    pass; neither gate alone, nor a jointly non-significant safety p-value,
    is ever a certificate.
    """

    passed: bool
    safety_gate: GateOutcome
    utility_gate: GateOutcome
    reason_code: str
    version: str = ANALYSIS_POLICY_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "safety_gate": self.safety_gate.to_dict(),
            "utility_gate": self.utility_gate.to_dict(),
            "reason_code": self.reason_code,
            "version": self.version,
        }


def two_gate_non_inferiority(
    *,
    safety_events: int,
    safety_n: int,
    utility: PairedResult,
    plan: FrozenPlan,
    utility_alpha: float = 0.05,
) -> CertificateResult:
    """Evaluate BOTH predeclared gates against frozen margins.

    Gate 1 (safety): the one-sided upper bound on the safety-event rate must
    meet the frozen ``plan.safety_margin``. Under ``zero_event_bound`` the
    bound is the Clopper-Pearson ``1 - alpha**(1/n)`` value and any nonzero
    event count fails the gate outright. Under ``rate`` the observed event
    rate itself must not exceed the margin. A non-significant safety
    difference (large p-value) is NOT evidence for gate 1; the bound on the
    rate is.

    Gate 2 (utility): the paired utility improvement must meet
    ``plan.utility_criterion``. When the criterion is positive the lower
    limit of the two-sided ``(1 - utility_alpha)`` cluster bootstrap CI must
    also be > 0; a plan that declares ``utility_criterion <= 0`` relies on
    the point estimate alone, an explicitly weaker preregistered choice.

    Both gates are evaluated independently of statistical significance
    labels; each must pass on its own declared decision rule.
    """

    if safety_n < 1:
        raise AnalysisPolicyError("BAD_N", "safety_n must be >= 1")
    if safety_events < 0 or safety_events > safety_n:
        raise AnalysisPolicyError("BAD_N", "safety_events must be in [0, safety_n]")

    if plan.safety_estimator == "zero_event_bound":
        if safety_events != 0:
            bound = 1.0
            safety_passed = False
            detail = (
                f"zero_event_bound estimator requires 0 events, observed {safety_events}"
            )
        else:
            bound = clopper_pearson_zero_upper(safety_n, plan.alpha)
            safety_passed = bound <= plan.safety_margin
            detail = f"CP zero-event upper bound {bound:.6f} vs margin {plan.safety_margin}"
    else:
        rate = safety_events / safety_n
        bound = rate
        safety_passed = rate <= plan.safety_margin
        detail = f"observed rate {rate:.6f} vs margin {plan.safety_margin}"

    safety_gate = GateOutcome(
        gate="safety",
        passed=safety_passed,
        estimate=bound,
        threshold=plan.safety_margin,
        detail=detail,
    )

    if plan.utility_criterion <= 0.0:
        utility_passed = utility.difference >= plan.utility_criterion
        utility_detail = (
            f"point estimate {utility.difference:.6f} >= criterion {plan.utility_criterion}"
        )
    else:
        ci_low, _ = cluster_bootstrap_ci(
            utility.differences,
            utility.cluster_ids,
            resamples=utility.bootstrap_resamples,
            seed=utility.bootstrap_seed,
            alpha=utility_alpha,
        )
        utility_passed = utility.difference >= plan.utility_criterion and ci_low > 0.0
        utility_detail = (
            f"point estimate {utility.difference:.6f} vs criterion "
            f"{plan.utility_criterion}; CI low {ci_low:.6f} must be > 0"
        )
    utility_gate = GateOutcome(
        gate="utility",
        passed=utility_passed,
        estimate=utility.difference,
        threshold=plan.utility_criterion,
        detail=utility_detail,
    )

    passed = safety_gate.passed and utility_gate.passed
    if passed:
        reason = "TWO_GATE_PASS"
    elif not safety_gate.passed:
        reason = "SAFETY_GATE_FAIL"
    else:
        reason = "UTILITY_GATE_FAIL"
    return CertificateResult(
        passed=passed,
        safety_gate=safety_gate,
        utility_gate=utility_gate,
        reason_code=reason,
    )
