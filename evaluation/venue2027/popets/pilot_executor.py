"""PoPETs development pilot v2. Measure case decisions, retaining every planned cell.

The pilot takes synthetic development records and refuses other splits. Its runner
exposes family-level decisions and adapter timings. Primary dispatch outcomes
require independent observations at the outbound boundary.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from evaluation.venue2027._shared import dataset_kernel as dk
from evaluation.venue2027._shared.analysis_policy import clopper_pearson_zero_upper
from evaluation.venue2027._shared.harness import COUNTABLE_OUTCOMES, HarnessError, RunBundle
from evaluation.venue2027.popets import generate_dataset as generator
from evaluation.venue2027.popets.runner import (
    DEFAULT_ARMS,
    DEFAULT_BACKEND,
    DEFAULT_RETRY_BUDGET,
    DEFAULT_SEED,
    DEFAULT_TIMEOUT_SECONDS,
    CampaignConfig,
    resolve_source_commit,
    run_campaign,
)

POPETS_PILOT_EXECUTOR_VERSION = "2.0.0"
PLAN = Path(__file__).resolve().parents[3] / "research/venue2027/popets/protocols/pilot_plan.yaml"
PROSPECTIVE_SAMPLE_SIZES = (20, 60, 120, 240, 600, 1200)


class PilotError(ValueError):
    def __init__(self, reason_code: str, detail: str):
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code


@dataclasses.dataclass(frozen=True)
class PilotConfig:
    pilot_id: str = "popets-pilot-dev"
    split: str = "dev"
    arm_ids: tuple[str, ...] = DEFAULT_ARMS
    seed: int = DEFAULT_SEED
    n: int = 60  # Full sampling frame size, before selecting the development indices.
    per_pair_timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    retry_budget: int = DEFAULT_RETRY_BUDGET
    backend: str = DEFAULT_BACKEND
    source_commit: str | None = None
    workers: int = 1
    alpha: float = 0.05
    target_power: float = 0.80
    plan_path: str | Path | None = None


@dataclasses.dataclass(frozen=True)
class PilotReport:
    pilot_id: str
    split: str
    arm_ids: tuple[str, ...]
    n_cases: int
    planned_pairs: int
    attempted_pairs: int
    complete: bool
    baseline_fairness: dict
    oracle_disagreements: int | None
    candidate_disagreements: int | None
    disagreement_rate: float | None
    runtime_stats: dict
    variance_estimates: dict
    power_estimates: dict
    coverage: dict
    feasible_matrix: dict
    dispatch_metrics: dict
    provenance: dict
    holdout_untouched: bool = True
    version: str = POPETS_PILOT_EXECUTOR_VERSION

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def load_pilot_plan(plan_path: str | Path | None = None) -> dict:
    path = Path(plan_path or PLAN)
    if not path.is_file():
        raise PilotError("PLAN_NOT_FOUND", str(path))
    plan = yaml.safe_load(path.read_text())
    if not isinstance(plan, dict) or plan.get("split") != "dev":
        raise PilotError("CONFIG_MALFORMED", "expected development pilot plan")
    return plan


def _require_dev(label: Any) -> None:
    if not isinstance(label, str) or label.strip().lower() != "dev":
        raise PilotError("HOLDOUT_ACCESS_FORBIDDEN", "explicit dev provenance required")


def development_records(seed: int, n: int) -> tuple[dk.DatasetRecord, ...]:
    """Use the kernel split assignment without constructing any other split's payloads."""
    spec = dk.DatasetSpec(venue="popets", seed=seed, n=n)
    spec.validate()
    records = []
    families = generator.POPETS_FAMILIES
    for idx, split in enumerate(dk._split_assignment(n, spec)):
        if split == "dev":
            family = families[idx % len(families)]
            records.append(
                dk.DatasetRecord(
                    unit_id=f"{dk.VENUE_UNIT_PREFIX['popets']}-{seed}-{idx:05d}",
                    family=family,
                    split=split,
                    payload=generator.revocation_payload(seed, family, idx),
                )
            )
    return tuple(records)


def record_to_scenario_case(record: Any) -> dict:
    if isinstance(record, dk.DatasetRecord):
        record = record.to_dict()
    if not isinstance(record, Mapping):
        raise PilotError("CONFIG_MALFORMED", "expected synthetic development record")
    _require_dev(record.get("split"))
    uid = record.get("unit_id") or record.get("case_id")
    if not isinstance(uid, str) or not uid.strip():
        raise PilotError("CONFIG_MALFORMED", "a nonempty subject history ID is required")
    family = record.get("family")
    if family not in generator.POPETS_FAMILIES:
        raise PilotError("UNKNOWN_FAMILY", str(family))
    payload = record.get("payload")
    if not isinstance(payload, Mapping) or payload.get("synthetic_only") is not True:
        raise PilotError("CONFIG_MALFORMED", "expected a synthetic revocation payload")
    try:
        purpose = payload["purpose"]
        requested = payload["requested_purpose"] if family == "cross_purpose" else purpose
        at = payload["dispatch_at"]
        revocation = payload["revocation_at"]
    except KeyError as exc:
        raise PilotError("CONFIG_MALFORMED", f"missing payload field {exc}") from exc
    labels = {"src_vitals": "synthetic-value"}
    lineage = ["src_vitals"]
    if family == "transitive_gap":
        labels["summary_gap"] = None
        lineage = ["summary_gap"]
    elif family != "fresh":
        lineage += ["summary_cache_1"]
    revocations = []
    if family in {"revoked_then_dispatch", "transitive_gap"}:
        revocations.append({"principal": uid, "purpose": purpose, "revoked_at": revocation})
    grant = {"purposes": [purpose], "consent_epoch": 0, "lineage_labels": labels}
    return {
        "case_id": uid,
        "family": family,
        "split": "dev",
        "payload": dict(payload),
        "scenario": {
            "principal": uid,
            "purpose": requested,
            "time": at,
            "ledger": {"grants": {uid: grant}, "revocations": revocations},
            "item": {
                "item_id": f"d-{uid}",
                "lineage": lineage,
                "item_epoch": 0,
                "already_delivered": False,
                "stored_copy": family != "fresh",
            },
        },
    }


def calculate_power(alpha=0.05, target_power=0.8, sample_sizes=PROSPECTIVE_SAMPLE_SIZES) -> dict:
    """Conditional design illustrations only. Primary RQ variances are unavailable."""
    if (
        not 0 < alpha < 1
        or not 0 < target_power < 1
        or any(type(n) is not int or n < 1 for n in sample_sizes)
    ):
        raise PilotError("CONFIG_MALFORMED", "invalid probability or prospective sample size")
    return {
        "alpha": alpha,
        "target_power": target_power,
        "status": "BLOCKED",
        "required_sample_size": None,
        "primary_endpoint_power": None,
        "zero_event_upper_if_independent": {
            str(n): clopper_pearson_zero_upper(n, alpha) for n in sample_sizes
        },
        "assumptions": "One-sided binomial bounds assume zero observed events in N independent "
        "units. They illustrate possible designs. Decisions from this pilot cannot "
        "estimate variance of the clustered, dispatch-level primary endpoints.",
    }


def _stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "mean": None, "variance": None, "p95": None}
    ordered = sorted(values)
    return {
        "n": len(values),
        "mean": statistics.mean(values),
        "variance": statistics.variance(values) if len(values) >= 2 else None,
        "p95": ordered[math.ceil(0.95 * len(values)) - 1],
    }


def summarize(cfg: PilotConfig, cases: Sequence[dict], bundle: RunBundle) -> PilotReport:
    """Reduce a released development bundle against its original case-by-arm plan."""
    ids = {c["case_id"] for c in cases}
    expected = {(a, c) for a in cfg.arm_ids for c in ids}
    seen = set()
    outcomes = {a: Counter() for a in cfg.arm_ids}
    by_family = {c["case_id"]: c["family"] for c in cases}
    family_counts = defaultdict(Counter)
    decision_values = {a: {} for a in cfg.arm_ids}
    timings = defaultdict(list)
    adjudicated = Counter()
    disagreements = Counter()
    for row in bundle.records:
        arm, case = key = (row["arm_id"], row["case_id"])
        if key in seen or key not in expected:
            raise PilotError("UNEXPECTED_PAIR", str(key))
        seen.add(key)
        outcome = row["outcome"]["observed_outcome"]
        outcomes[arm][outcome.lower()] += 1
        family_counts[by_family[case]][arm] += 1
        if outcome not in COUNTABLE_OUTCOMES:
            continue
        timings[arm].append(row["duration_seconds"])
        decision_values[arm][case] = int(outcome == "ADMIT")
        reference = row["oracle"].get("expected_outcome")
        if reference in COUNTABLE_OUTCOMES and not row["oracle"].get("oracle_error"):
            adjudicated[arm] += 1
            disagreements[arm] += outcome != reference

    comparable = adjudicated.total()
    complete_decisions = sum(len(values) for values in decision_values.values())
    totals = sum(outcomes.values(), Counter())
    coverage = {
        "planned": len(expected),
        "recorded": len(seen),
        "missing": len(expected - seen),
        "executed": len(seen) - totals["not_run_external"],
        "decision_returned": complete_decisions,
        "comparable": comparable,
        "oracle_unassessed": complete_decisions - comparable,
        "outcomes": dict(totals),
        "by_arm_outcome": {a: dict(v) for a, v in outcomes.items()},
        "comparable_by_arm": {a: adjudicated[a] for a in cfg.arm_ids},
        "by_family_arm": {f: dict(v) for f, v in family_counts.items()},
    }
    per_arm_variance = {
        a: _stats(list(vals.values()))["variance"] for a, vals in decision_values.items()
    }
    paired_variance = {}
    candidate = decision_values.get("B4", {})
    for arm in ("B1", "B2"):
        if arm in decision_values and candidate:
            control = decision_values[arm]
            diffs = [candidate[i] - control[i] for i in sorted(candidate.keys() & control.keys())]
            paired_variance[f"B4_vs_{arm}"] = {
                "n": len(diffs),
                "variance": _stats(diffs)["variance"],
            }
    durations = [d for values in timings.values() for d in values]
    runtime = {
        "total_wall_seconds": bundle.manifest["wall_seconds"],
        "mean_pair_duration_seconds": _stats(durations)["mean"],
        "per_arm": {a: _stats(v) for a, v in timings.items()},
        "scope": "Adapter duration for ADMIT/REJECT pairs; excludes unavailable and failed decisions.",
    }
    plan = load_pilot_plan(cfg.plan_path)
    return PilotReport(
        pilot_id=cfg.pilot_id,
        split="dev",
        arm_ids=cfg.arm_ids,
        n_cases=len(ids),
        planned_pairs=len(expected),
        attempted_pairs=len(seen),
        complete=False,
        baseline_fairness={
            "balanced_pairing": seen == expected,
            "seed": cfg.seed,
            "retry_budget": cfg.retry_budget,
            "backend": cfg.backend,
            "per_pair_timeout_seconds": cfg.per_pair_timeout_seconds,
            "semantic_parity": "UNVERIFIED",
        },
        oracle_disagreements=disagreements.total() if comparable else None,
        candidate_disagreements=disagreements["B4"] if adjudicated["B4"] else None,
        disagreement_rate=disagreements.total() / comparable if comparable else None,
        runtime_stats=runtime,
        variance_estimates={
            "admission_indicator_by_arm": per_arm_variance,
            "paired_admission_difference": paired_variance,
        },
        power_estimates=calculate_power(cfg.alpha, cfg.target_power, plan["power"]["sample_sizes"]),
        coverage=coverage,
        feasible_matrix={
            "confirmatory_study_n": None,
            "blueprint_target_subjects": plan["design_target_subjects"],
            "status": "BLOCKED",
        },
        dispatch_metrics={
            "independently_observed_dispatches": 0,
            "unauthorized_bytes": None,
            "future_unauthorized_disclosure_rate": None,
            "reason": "The runner returns family-oracle comparisons of aggregate decisions. "
            "It has no independent byte interceptor or reconciled cancellation journal.",
        },
        provenance={
            "source_commit": bundle.source_commit,
            "seed": bundle.seed,
            "python_version": bundle.python_version,
            "harness_version": bundle.harness_version,
            "observation_unit": "single synthetic decision scenario per subject ID",
            "families": dict(Counter(by_family.values())),
            "plan_sha256": hashlib.sha256(Path(cfg.plan_path or PLAN).read_bytes()).hexdigest(),
            "cases_sha256": hashlib.sha256(serialize_cases(cases).encode()).hexdigest(),
            "raw_sha256": hashlib.sha256(bundle.to_jsonl().encode()).hexdigest(),
        },
    )


def serialize_cases(cases: Sequence[dict]) -> str:
    return "".join(json.dumps(c, sort_keys=True, separators=(",", ":")) + "\n" for c in cases)


def run_development(config=None, dev_dataset=None) -> tuple[PilotReport, RunBundle, list[dict]]:
    if config is None:
        cfg = PilotConfig()
    elif isinstance(config, PilotConfig):
        cfg = config
    elif isinstance(config, Mapping):
        try:
            cfg = PilotConfig(**config)
        except TypeError as exc:
            raise PilotError("CONFIG_MALFORMED", "unknown field") from exc
    else:
        raise PilotError("CONFIG_MALFORMED", "expected pilot config")
    _require_dev(cfg.split)
    if not cfg.arm_ids:
        raise PilotError("EMPTY_SCOPE", "no arms")
    if not isinstance(cfg.arm_ids, (list, tuple)) or set(cfg.arm_ids) - set(DEFAULT_ARMS):
        raise PilotError("UNKNOWN_ARM", "expected registered PoPETs arms")
    if cfg.backend != DEFAULT_BACKEND or cfg.retry_budget != 0:
        raise PilotError(
            "CONFIG_MALFORMED", "pilot supports only in-process execution without retries"
        )
    load_pilot_plan(cfg.plan_path)
    if dev_dataset is None:
        records = development_records(cfg.seed, cfg.n)
    elif isinstance(dev_dataset, dk.Dataset):
        if dev_dataset.venue != "popets" or dev_dataset.seed != cfg.seed:
            raise PilotError("CONFIG_MALFORMED", "development input venue or seed mismatch")
        records = dev_dataset.records
    elif isinstance(dev_dataset, Sequence) and not isinstance(dev_dataset, (str, bytes)):
        records = dev_dataset
    else:
        raise PilotError("CONFIG_MALFORMED", "expected an in-memory development dataset")
    if not records:
        raise PilotError("EMPTY_SCOPE", "no development records")
    cases = [record_to_scenario_case(r) for r in records]
    if len(set(c["case_id"] for c in cases)) != len(cases):
        raise PilotError("DUPLICATE_ID", "one decision scenario per distinct subject ID")
    sha = resolve_source_commit()
    if cfg.source_commit is not None and cfg.source_commit != sha:
        raise PilotError("SOURCE_MISMATCH", "requested source differs from executing checkout")
    campaign = CampaignConfig(
        campaign_id=cfg.pilot_id,
        arm_ids=tuple(cfg.arm_ids),
        cases=tuple(cases),
        seed=cfg.seed,
        per_pair_timeout_seconds=cfg.per_pair_timeout_seconds,
        workers=cfg.workers,
        source_commit=sha,
        retry_budget=cfg.retry_budget,
        backend=cfg.backend,
    )
    try:
        bundle = run_campaign(campaign)
    except HarnessError as exc:
        raise PilotError(exc.reason_code, exc.detail) from exc
    return summarize(cfg, cases, bundle), bundle, cases


def execute_pilot(config=None, dev_dataset=None) -> PilotReport:
    return run_development(config, dev_dataset)[0]


def pilot(config=None) -> PilotReport:
    return execute_pilot(config)
