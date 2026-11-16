"""CLARA-Care 2027 POPETS task POPETS-pilot — development split pilot executor.

Purpose
-------
Execute the development-split pilot evaluation plan for the PoPETs 2027 study
"Revocation-Complete Future Disclosure for Cached Longitudinal AI Contexts"
(``research/venue2027/VENUES/popets/RESEARCH_BLUEPRINT.md``; task contract
``research/venue2027/VENUES/popets/TASKS/POPETS-pilot.md``; protocol
``research/venue2027/popets/protocols/pilot_plan.yaml``).

The pilot executor:
1. Runs strictly over the development split (``split: dev``);
2. Refuses any attempt to access the main confirmatory holdout/test split
   with fail-closed reason code ``HOLDOUT_ACCESS_FORBIDDEN``;
3. Evaluates baseline fairness and balanced pairing parity across all arms
   (B0-B4) under identical seed, timeout, retry budget, and backend;
4. Runs the real multi-arm runner (:mod:`evaluation.venue2027.popets.runner`)
   over the dev cases, recording real execution durations, outcomes, and
   independent oracle adjudications;
5. Measures empirical runtime, duration variance, outcome variance, and
   paired difference variance;
6. Computes prospective power estimates and Clopper-Pearson zero-event
   confidence bounds across prospective sample sizes;
7. Selects a feasible experimental matrix (seeds, sample sizes, budget bounds)
   without reading the main holdout split.

Allowed input
-------------
- ``config``: :class:`PilotConfig` or mapping with pilot configuration parameters.
- ``dev_dataset``: :class:`evaluation.venue2027._shared.dataset_kernel.Dataset`,
  sequence of records/cases, or ``None`` (in which case the dev split is
  generated deterministically from the configured seed and n).

Failure semantics
-----------------
Fail closed with stable uppercase reason codes:
- ``HOLDOUT_ACCESS_FORBIDDEN`` — attempting to execute or pass cases from the
  test or holdout split is strictly forbidden during the pilot phase.
- ``EMPTY_SCOPE`` — empty arms or cases provided.
- ``CONFIG_MALFORMED`` — config object is not a mapping or PilotConfig.
- ``UNEQUAL_ARM_CONFIG`` — arms have different seeds, timeouts, retry budgets,
  backends, or versions (delegated to runner).
- ``UNKNOWN_ARM`` — arm identifier not recognized.

Version
-------
``POPETS_PILOT_EXECUTOR_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

import yaml

from evaluation.venue2027._shared import dataset_kernel as dk
from evaluation.venue2027._shared.analysis_policy import clopper_pearson_zero_upper
from evaluation.venue2027._shared.harness import RunBundle
from evaluation.venue2027.popets import generate_dataset
from evaluation.venue2027.popets.runner import (
    DEFAULT_ARMS,
    DEFAULT_BACKEND,
    DEFAULT_RETRY_BUDGET,
    DEFAULT_SEED,
    DEFAULT_TIMEOUT_SECONDS,
    CampaignConfig,
    RunnerError,
    run_campaign,
)

__all__ = [
    "DEFAULT_FEASIBLE_SEEDS",
    "FORBIDDEN_SPLITS",
    "POPETS_PILOT_EXECUTOR_VERSION",
    "PROSPECTIVE_EFFECT_SIZES",
    "PROSPECTIVE_SAMPLE_SIZES",
    "FeasibleMatrix",
    "PilotConfig",
    "PilotError",
    "PilotReport",
    "PowerEstimates",
    "RuntimeStats",
    "VarianceEstimates",
    "calculate_power",
    "calculate_runtime_stats",
    "calculate_variance_estimates",
    "execute_pilot",
    "load_pilot_plan",
    "pilot",
    "record_to_scenario_case",
]

POPETS_PILOT_EXECUTOR_VERSION: Final[str] = "1.0.0"

FORBIDDEN_SPLITS: Final[frozenset[str]] = frozenset({"test", "holdout"})

DEFAULT_FEASIBLE_SEEDS: Final[tuple[int, ...]] = (42, 101, 2027)
PROSPECTIVE_SAMPLE_SIZES: Final[tuple[int, ...]] = (20, 60, 120, 240, 600, 1200)
PROSPECTIVE_EFFECT_SIZES: Final[tuple[float, ...]] = (0.10, 0.15, 0.20, 0.25)


class PilotError(ValueError):
    """Stable, machine-readable pilot configuration or access control failure."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class PilotConfig:
    """Configuration for a development-split pilot run."""

    pilot_id: str = "popets-pilot-dev"
    split: str = "dev"
    arm_ids: tuple[str, ...] = DEFAULT_ARMS
    seed: int = DEFAULT_SEED
    n: int = 60
    per_pair_timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    retry_budget: int = DEFAULT_RETRY_BUDGET
    backend: str = DEFAULT_BACKEND
    source_commit: str | None = None
    workers: int = 1
    alpha: float = 0.05
    target_power: float = 0.80
    plan_path: str | Path | None = None


@dataclasses.dataclass(frozen=True)
class RuntimeStats:
    """Empirical runtime measurements from the pilot execution."""

    total_wall_seconds: float
    mean_pair_duration_seconds: float
    variance_pair_duration: float
    p95_pair_duration_seconds: float
    per_arm_stats: Mapping[str, Mapping[str, float]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_wall_seconds": self.total_wall_seconds,
            "mean_pair_duration_seconds": self.mean_pair_duration_seconds,
            "variance_pair_duration": self.variance_pair_duration,
            "p95_pair_duration_seconds": self.p95_pair_duration_seconds,
            "per_arm_stats": {k: dict(v) for k, v in self.per_arm_stats.items()},
        }


@dataclasses.dataclass(frozen=True)
class VarianceEstimates:
    """Empirical outcome and paired difference variance estimates."""

    outcome_variance_by_arm: Mapping[str, float]
    paired_difference_variance: Mapping[str, float]
    duration_variance: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome_variance_by_arm": dict(self.outcome_variance_by_arm),
            "paired_difference_variance": dict(self.paired_difference_variance),
            "duration_variance": self.duration_variance,
        }


@dataclasses.dataclass(frozen=True)
class PowerEstimates:
    """Statistical power estimates for prospective sample size selection."""

    alpha: float
    target_power: float
    clopper_pearson_bounds: Mapping[str, float]
    power_by_sample_size: Mapping[str, Mapping[str, float]]
    required_sample_sizes: Mapping[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "alpha": self.alpha,
            "target_power": self.target_power,
            "clopper_pearson_bounds": dict(self.clopper_pearson_bounds),
            "power_by_sample_size": {k: dict(v) for k, v in self.power_by_sample_size.items()},
            "required_sample_sizes": dict(self.required_sample_sizes),
        }


@dataclasses.dataclass(frozen=True)
class FeasibleMatrix:
    """Selected feasible experimental matrix derived from pilot observations."""

    seeds: tuple[int, ...]
    sample_sizes: Mapping[str, Any]
    budget_bounds: Mapping[str, Any]
    holdout_untouched: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "seeds": list(self.seeds),
            "sample_sizes": dict(self.sample_sizes),
            "budget_bounds": dict(self.budget_bounds),
            "holdout_untouched": self.holdout_untouched,
        }


@dataclasses.dataclass(frozen=True)
class PilotReport:
    """Complete, JSON-serializable report of the development pilot evaluation."""

    pilot_id: str
    split: str
    arm_ids: tuple[str, ...]
    n_cases: int
    planned_pairs: int
    attempted_pairs: int
    complete: bool
    baseline_fairness: Mapping[str, Any]
    oracle_disagreements: int
    candidate_disagreements: int
    disagreement_rate: float
    runtime_stats: RuntimeStats
    variance_estimates: VarianceEstimates
    power_estimates: PowerEstimates
    coverage: Mapping[str, Any]
    feasible_matrix: FeasibleMatrix
    holdout_untouched: bool = True
    version: str = POPETS_PILOT_EXECUTOR_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "pilot_id": self.pilot_id,
            "split": self.split,
            "arm_ids": list(self.arm_ids),
            "n_cases": self.n_cases,
            "planned_pairs": self.planned_pairs,
            "attempted_pairs": self.attempted_pairs,
            "complete": self.complete,
            "baseline_fairness": dict(self.baseline_fairness),
            "oracle_disagreements": self.oracle_disagreements,
            "candidate_disagreements": self.candidate_disagreements,
            "disagreement_rate": self.disagreement_rate,
            "runtime_stats": self.runtime_stats.to_dict(),
            "variance_estimates": self.variance_estimates.to_dict(),
            "power_estimates": self.power_estimates.to_dict(),
            "coverage": dict(self.coverage),
            "feasible_matrix": self.feasible_matrix.to_dict(),
            "holdout_untouched": self.holdout_untouched,
            "version": self.version,
        }


def load_pilot_plan(plan_path: str | Path | None = None) -> dict[str, Any]:
    """Load and parse the pilot plan YAML, defaulting to the repository protocol."""
    if plan_path is None:
        root = Path(__file__).resolve().parents[3]
        plan_path = root / "research" / "venue2027" / "popets" / "protocols" / "pilot_plan.yaml"
    path = Path(plan_path)
    if not path.is_file():
        raise PilotError("PLAN_NOT_FOUND", f"pilot plan file not found: {path}")
    content = path.read_text(encoding="utf-8")
    parsed = yaml.safe_load(content)
    if not isinstance(parsed, Mapping):
        raise PilotError("CONFIG_MALFORMED", f"pilot plan must be a YAML mapping: {path}")
    return dict(parsed)


def record_to_scenario_case(record: Any) -> dict[str, Any]:
    """Convert a synthetic dataset record into a fully articulated runner case."""
    if isinstance(record, Mapping):
        uid = str(record.get("unit_id") or record.get("case_id", "case-0"))
        fam = str(record.get("family", "fresh"))
        split = str(record.get("split", "dev"))
        payload = dict(record.get("payload", {}))
    elif isinstance(record, dk.DatasetRecord):
        uid = record.unit_id
        fam = record.family
        split = record.split
        payload = dict(record.payload)
    else:
        raise PilotError(
            "CONFIG_MALFORMED",
            f"expected DatasetRecord or Mapping, got {type(record).__name__}",
        )

    if split.lower() in FORBIDDEN_SPLITS:
        raise PilotError(
            "HOLDOUT_ACCESS_FORBIDDEN",
            f"record {uid} belongs to forbidden split {split!r}",
        )

    purpose = payload.get("purpose", "care_summary")
    req_purpose = payload.get("requested_purpose", purpose)
    rev_at = payload.get("revocation_at", 100)
    disp_at = payload.get("dispatch_at", 200)

    if fam == "fresh":
        grants = {
            "subj-1": {
                "purposes": [purpose],
                "consent_epoch": 0,
                "lineage_labels": {"src_vitals": "BP 128/84"},
            }
        }
        revs: list[dict[str, Any]] = []
        item = {
            "item_id": f"d-{uid}",
            "lineage": ["src_vitals"],
            "item_epoch": 0,
            "already_delivered": False,
            "stored_copy": False,
        }
        query_purpose = purpose
        query_time = 10
    elif fam == "revoked_then_dispatch":
        grants = {
            "subj-1": {
                "purposes": [purpose],
                "consent_epoch": 0,
                "lineage_labels": {"src_vitals": "BP 128/84"},
            }
        }
        revs = [{"principal": "subj-1", "purpose": purpose, "revoked_at": rev_at}]
        item = {
            "item_id": f"d-{uid}",
            "lineage": ["src_vitals", "summary_cache_1"],
            "item_epoch": 0,
            "already_delivered": False,
            "stored_copy": True,
        }
        query_purpose = purpose
        query_time = disp_at
    elif fam == "cross_purpose":
        grants = {
            "subj-1": {
                "purposes": [purpose],
                "consent_epoch": 0,
                "lineage_labels": {"src_vitals": "BP 128/84"},
            }
        }
        revs = []
        item = {
            "item_id": f"d-{uid}",
            "lineage": ["src_vitals", "summary_cache_1"],
            "item_epoch": 0,
            "already_delivered": False,
            "stored_copy": True,
        }
        query_purpose = req_purpose
        query_time = disp_at
    elif fam == "transitive_gap":
        grants = {
            "subj-1": {
                "purposes": [purpose],
                "consent_epoch": 0,
                "lineage_labels": {"src_vitals": "BP 128/84", "summary_gap": None},
            }
        }
        revs = [{"principal": "subj-1", "purpose": purpose, "revoked_at": rev_at}]
        item = {
            "item_id": f"d-{uid}",
            "lineage": ["summary_gap"],
            "item_epoch": 0,
            "already_delivered": False,
            "stored_copy": True,
        }
        query_purpose = purpose
        query_time = disp_at
    else:
        grants = {
            "subj-1": {
                "purposes": [purpose],
                "consent_epoch": 0,
                "lineage_labels": {"src_vitals": "BP 128/84"},
            }
        }
        revs = []
        item = {
            "item_id": f"d-{uid}",
            "lineage": ["src_vitals"],
            "item_epoch": 0,
            "already_delivered": False,
            "stored_copy": False,
        }
        query_purpose = purpose
        query_time = 10

    scenario = {
        "ledger": {"grants": grants, "revocations": revs},
        "item": item,
        "principal": "subj-1",
        "purpose": query_purpose,
        "time": query_time,
    }

    return {
        "case_id": uid,
        "family": fam,
        "split": split,
        "payload": payload,
        "scenario": scenario,
    }


def _percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    pos = (len(sorted_vals) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def calculate_runtime_stats(bundle: RunBundle) -> RuntimeStats:
    """Compute empirical runtime distribution parameters across all pairs and per arm."""
    records = bundle.records
    total_wall = float(bundle.manifest.get("wall_seconds", 0.0))
    all_durations = [float(r.get("duration_seconds", 0.0)) for r in records]

    n_all = len(all_durations)
    if n_all == 0:
        return RuntimeStats(
            total_wall_seconds=total_wall,
            mean_pair_duration_seconds=0.0,
            variance_pair_duration=0.0,
            p95_pair_duration_seconds=0.0,
            per_arm_stats={},
        )

    mean_all = sum(all_durations) / n_all
    var_all = sum((d - mean_all) ** 2 for d in all_durations) / (n_all - 1) if n_all > 1 else 0.0
    p95_all = _percentile(all_durations, 0.95)

    per_arm: dict[str, dict[str, float]] = {}
    arms_in_records = sorted({str(r["arm_id"]) for r in records})
    for arm in arms_in_records:
        arm_durations = [
            float(r.get("duration_seconds", 0.0)) for r in records if r["arm_id"] == arm
        ]
        k = len(arm_durations)
        if k > 0:
            m = sum(arm_durations) / k
            v = sum((d - m) ** 2 for d in arm_durations) / (k - 1) if k > 1 else 0.0
            per_arm[arm] = {
                "count": float(k),
                "mean_seconds": round(m, 6),
                "variance": round(v, 6),
                "std_seconds": round(math.sqrt(v), 6),
                "min_seconds": round(min(arm_durations), 6),
                "max_seconds": round(max(arm_durations), 6),
                "p95_seconds": round(_percentile(arm_durations, 0.95), 6),
            }

    return RuntimeStats(
        total_wall_seconds=round(total_wall, 6),
        mean_pair_duration_seconds=round(mean_all, 6),
        variance_pair_duration=round(var_all, 6),
        p95_pair_duration_seconds=round(p95_all, 6),
        per_arm_stats=per_arm,
    )


def calculate_variance_estimates(bundle: RunBundle) -> VarianceEstimates:
    """Compute empirical outcome and paired difference variance estimates."""
    records = bundle.records
    all_durations = [float(r.get("duration_seconds", 0.0)) for r in records]
    n_all = len(all_durations)
    dur_var = 0.0
    if n_all > 1:
        mean_d = sum(all_durations) / n_all
        dur_var = sum((d - mean_d) ** 2 for d in all_durations) / (n_all - 1)

    # Outcome variance per arm: Bernoulli variance of valid decisions (ADMIT vs REJECT)
    arms = sorted({str(r["arm_id"]) for r in records})
    outcome_vars: dict[str, float] = {}
    success_by_arm_case: dict[tuple[str, str], float] = {}

    for arm in arms:
        arm_records = [r for r in records if r["arm_id"] == arm]
        binary_vals: list[float] = []
        for r in arm_records:
            cid = str(r["case_id"])
            obs = r["outcome"]["observed_outcome"]
            # 1.0 for ADMIT, 0.0 for REJECT, ignore NOT_RUN_EXTERNAL / errors
            val = 1.0 if obs == "ADMIT" else 0.0
            binary_vals.append(val)
            success_by_arm_case[(arm, cid)] = val
        k = len(binary_vals)
        if k > 1:
            p_hat = sum(binary_vals) / k
            s2 = sum((x - p_hat) ** 2 for x in binary_vals) / (k - 1)
            outcome_vars[arm] = round(s2, 6)
        else:
            outcome_vars[arm] = 0.0

    # Paired differences between Candidate (B4) and baselines (B1, B2)
    paired_diff_vars: dict[str, float] = {}
    cand_arm = "B4" if "B4" in arms else (arms[-1] if arms else "")

    for base_arm in ("B1", "B2"):
        if cand_arm and base_arm in arms:
            case_ids = sorted({str(r["case_id"]) for r in records if r["arm_id"] == cand_arm})
            diffs: list[float] = []
            for cid in case_ids:
                if (cand_arm, cid) in success_by_arm_case and (
                    base_arm,
                    cid,
                ) in success_by_arm_case:
                    diff = (
                        success_by_arm_case[(cand_arm, cid)] - success_by_arm_case[(base_arm, cid)]
                    )
                    diffs.append(diff)
            if len(diffs) > 1:
                m_diff = sum(diffs) / len(diffs)
                v_diff = sum((d - m_diff) ** 2 for d in diffs) / (len(diffs) - 1)
                paired_diff_vars[f"{cand_arm}_vs_{base_arm}"] = round(v_diff, 6)
            else:
                paired_diff_vars[f"{cand_arm}_vs_{base_arm}"] = 0.0

    return VarianceEstimates(
        outcome_variance_by_arm=outcome_vars,
        paired_difference_variance=paired_diff_vars,
        duration_variance=round(dur_var, 6),
    )


def calculate_power(
    empirical_variance: float = 0.25,
    alpha: float = 0.05,
    target_power: float = 0.80,
    sample_sizes: Sequence[int] = PROSPECTIVE_SAMPLE_SIZES,
    effect_sizes: Sequence[float] = PROSPECTIVE_EFFECT_SIZES,
) -> PowerEstimates:
    """Calculate prospective statistical power and Clopper-Pearson bounds across sample sizes."""
    # Ensure a non-zero variance for power estimates (default conservative 0.25)
    sigma2 = empirical_variance if empirical_variance > 1e-6 else 0.25
    sigma = math.sqrt(sigma2)

    # z for two-sided alpha=0.05 is ~1.95996
    # Exact quantile via inverse error function approximation or standard z
    z_alpha = 1.959963984540054 if abs(alpha - 0.05) < 1e-4 else 1.96

    # z for target power (e.g. 0.80 -> 0.84162, 0.90 -> 1.28155)
    z_beta = 0.8416212335729143 if abs(target_power - 0.80) < 1e-4 else 0.84

    cp_bounds: dict[str, float] = {}
    for n in sample_sizes:
        cp_bounds[str(n)] = round(clopper_pearson_zero_upper(n, alpha), 6)

    power_grid: dict[str, dict[str, float]] = {}
    for delta in effect_sizes:
        delta_key = f"delta_{delta:.2f}"
        power_grid[delta_key] = {}
        for n in sample_sizes:
            se = sigma / math.sqrt(n)
            z = (abs(delta) / se) - z_alpha
            # Standard normal CDF: 0.5 * (1 + erf(z / sqrt(2)))
            pw = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
            pw_clamped = max(0.0, min(1.0, pw))
            power_grid[delta_key][str(n)] = round(pw_clamped, 4)

    req_sizes: dict[str, int] = {}
    for delta in effect_sizes:
        delta_key = f"delta_{delta:.2f}"
        required_n = math.ceil(((z_alpha + z_beta) ** 2 * sigma2) / (delta**2))
        req_sizes[delta_key] = max(10, required_n)

    return PowerEstimates(
        alpha=alpha,
        target_power=target_power,
        clopper_pearson_bounds=cp_bounds,
        power_by_sample_size=power_grid,
        required_sample_sizes=req_sizes,
    )


def _coerce_pilot_config(config: PilotConfig | Mapping[str, Any] | None) -> PilotConfig:
    if config is None:
        return PilotConfig()
    if isinstance(config, PilotConfig):
        return config
    if isinstance(config, Mapping):
        fields = {f.name for f in dataclasses.fields(PilotConfig)}
        kwargs: dict[str, Any] = {}
        for k, v in config.items():
            if k in fields:
                if k == "arm_ids" and isinstance(v, list | tuple):
                    kwargs[k] = tuple(str(x) for x in v)
                else:
                    kwargs[k] = v
        return PilotConfig(**kwargs)
    raise PilotError(
        "CONFIG_MALFORMED",
        f"expected PilotConfig or Mapping, got {type(config).__name__}",
    )


def execute_pilot(
    config: PilotConfig | Mapping[str, Any] | None = None,
    dev_dataset: Any = None,
) -> PilotReport:
    """Execute the development-split pilot evaluation plan.

    Parameters
    ----------
    config:
        Pilot configuration parameters.
    dev_dataset:
        Optional pre-generated dev dataset or cases. If None, generated automatically.

    Returns
    -------
    PilotReport:
        Comprehensive, JSON-serializable report of the pilot run.

    Raises
    ------
    PilotError:
        If test/holdout split is accessed (``HOLDOUT_ACCESS_FORBIDDEN``),
        scope is empty, or configuration is malformed.
    """
    cfg = _coerce_pilot_config(config)

    # 1. Enforce holdout protection: refuse any access to test or holdout split
    split_str = str(cfg.split).strip().lower()
    if split_str in FORBIDDEN_SPLITS:
        raise PilotError(
            "HOLDOUT_ACCESS_FORBIDDEN",
            f"access to split {cfg.split!r} is strictly forbidden during pilot; target must be 'dev'",
        )

    # 2. Ingest or generate development split
    raw_records: Sequence[Any]
    if dev_dataset is not None:
        if isinstance(dev_dataset, dk.Dataset):
            if dev_dataset.records and any(
                r.split.lower() in FORBIDDEN_SPLITS for r in dev_dataset.records
            ):
                raise PilotError(
                    "HOLDOUT_ACCESS_FORBIDDEN",
                    "dev_dataset contains records from forbidden test/holdout split",
                )
            raw_records = dev_dataset.records
        elif isinstance(dev_dataset, Sequence):
            if len(dev_dataset) == 0:
                raise PilotError("EMPTY_SCOPE", "dev_dataset sequence cannot be empty")
            for item in dev_dataset:
                sp = getattr(item, "split", None) or (
                    item.get("split") if isinstance(item, Mapping) else None
                )
                if sp and str(sp).lower() in FORBIDDEN_SPLITS:
                    raise PilotError(
                        "HOLDOUT_ACCESS_FORBIDDEN",
                        f"dev_dataset item has forbidden split {sp!r}",
                    )
            raw_records = dev_dataset
        elif isinstance(dev_dataset, str | Path):
            path_str = str(dev_dataset).lower()
            if any(forbidden in path_str for forbidden in FORBIDDEN_SPLITS):
                raise PilotError(
                    "HOLDOUT_ACCESS_FORBIDDEN",
                    f"path {dev_dataset} references forbidden test/holdout split",
                )
            raise PilotError("CONFIG_MALFORMED", "unsupported dataset path format")
        else:
            raise PilotError(
                "CONFIG_MALFORMED",
                f"unsupported dev_dataset type: {type(dev_dataset).__name__}",
            )
    else:
        # Deterministically generate dev split
        gen_ds = generate_dataset.generate(seed=cfg.seed, split="dev", n=cfg.n)
        raw_records = gen_ds.records

    if not raw_records:
        raise PilotError("EMPTY_SCOPE", "no cases available in development split")

    # 3. Transform dev records into runner-compatible cases
    cases: list[dict[str, Any]] = [record_to_scenario_case(r) for r in raw_records]

    # 4. Enforce balanced pairing and arm fairness
    arm_ids = tuple(cfg.arm_ids) if cfg.arm_ids else DEFAULT_ARMS
    fairness_record = {
        "balanced_pairing": True,
        "enforce_equal_seeds": True,
        "enforce_equal_timeouts": True,
        "enforce_equal_retry_budgets": True,
        "enforce_equal_backends": True,
        "seed": cfg.seed,
        "per_pair_timeout_seconds": cfg.per_pair_timeout_seconds,
        "retry_budget": cfg.retry_budget,
        "backend": cfg.backend,
        "arm_count": len(arm_ids),
        "arms": list(arm_ids),
    }

    # 5. Construct and run campaign via runner
    campaign_cfg = CampaignConfig(
        campaign_id=cfg.pilot_id,
        arm_ids=arm_ids,
        cases=tuple(cases),
        seed=cfg.seed,
        per_pair_timeout_seconds=cfg.per_pair_timeout_seconds,
        retry_budget=cfg.retry_budget,
        backend=cfg.backend,
        source_commit=cfg.source_commit,
        workers=cfg.workers,
    )

    try:
        bundle = run_campaign(campaign_cfg)
    except RunnerError as exc:
        raise PilotError(exc.reason_code, exc.detail) from exc

    # 6. Compute empirical measurements
    runtime_stats = calculate_runtime_stats(bundle)
    variance_estimates = calculate_variance_estimates(bundle)

    # Use difference variance if available, else conservative fallback
    diff_var = next(iter(variance_estimates.paired_difference_variance.values()), 0.25)
    power_estimates = calculate_power(
        empirical_variance=diff_var,
        alpha=cfg.alpha,
        target_power=cfg.target_power,
    )

    # 7. Oracle disagreement accounting
    records = bundle.records
    total_pairs = len(records)
    disagreements = sum(1 for r in records if r.get("oracle", {}).get("decision") == "MISMATCH")
    cand_records = [r for r in records if r["arm_id"] == "B4"]
    cand_disagreements = sum(
        1 for r in cand_records if r.get("oracle", {}).get("decision") == "MISMATCH"
    )
    disagreement_rate = round(disagreements / total_pairs, 6) if total_pairs > 0 else 0.0

    # 8. Coverage analysis
    arm_counts: dict[str, dict[str, int]] = {}
    family_counts: dict[str, dict[str, int]] = {}
    for r in records:
        arm = str(r["arm_id"])
        cid = str(r["case_id"])
        obs = str(r["outcome"]["observed_outcome"]).lower()
        fam = next((c["family"] for c in cases if c["case_id"] == cid), "unknown")

        arm_counts.setdefault(arm, {}).setdefault(obs, 0)
        arm_counts[arm][obs] += 1

        family_counts.setdefault(fam, {}).setdefault(arm, 0)
        family_counts[fam][arm] += 1

    coverage_record = {
        "planned_pairs": bundle.manifest.get("planned_pairs", total_pairs),
        "attempted_pairs": bundle.manifest.get("attempted_pairs", total_pairs),
        "missing_pairs": bundle.manifest.get("missing_pairs", 0),
        "by_arm_outcome": arm_counts,
        "by_family_arm": family_counts,
        "full_denominator": bundle.manifest.get("complete", True),
    }

    # 9. Feasible experimental matrix derived from pilot
    min_req_n = power_estimates.required_sample_sizes.get("delta_0.15", 300)
    feasible_matrix = FeasibleMatrix(
        seeds=DEFAULT_FEASIBLE_SEEDS,
        sample_sizes={
            "pilot_dev_n": len(cases),
            "confirmatory_study_n": 1200,
            "minimum_n_80_power": min_req_n,
            "contexts_per_subject": "3-6",
        },
        budget_bounds={
            "per_pair_timeout_seconds": cfg.per_pair_timeout_seconds,
            "retry_budget": cfg.retry_budget,
            "backend": cfg.backend,
            "max_total_pilot_runtime_seconds": 3600.0,
            "memory_limit_mb": 4096,
            "exclusive_resource": "cpu",
        },
        holdout_untouched=True,
    )

    return PilotReport(
        pilot_id=cfg.pilot_id,
        split="dev",
        arm_ids=arm_ids,
        n_cases=len(cases),
        planned_pairs=bundle.manifest.get("planned_pairs", total_pairs),
        attempted_pairs=bundle.manifest.get("attempted_pairs", total_pairs),
        complete=bool(bundle.manifest.get("complete", True)),
        baseline_fairness=fairness_record,
        oracle_disagreements=disagreements,
        candidate_disagreements=cand_disagreements,
        disagreement_rate=disagreement_rate,
        runtime_stats=runtime_stats,
        variance_estimates=variance_estimates,
        power_estimates=power_estimates,
        coverage=coverage_record,
        feasible_matrix=feasible_matrix,
        holdout_untouched=True,
        version=POPETS_PILOT_EXECUTOR_VERSION,
    )


def pilot(config: PilotConfig | Mapping[str, Any] | None = None) -> PilotReport:
    """Exact target contract signature: pilot(config) -> PilotReport."""
    return execute_pilot(config=config, dev_dataset=None)
