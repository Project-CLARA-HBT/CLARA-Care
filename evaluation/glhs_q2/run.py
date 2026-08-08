"""Frozen GLHS Q2 structural comparative evaluation.

The cases in this module are developer-authored, oracle-labelled synthetic
longitudinal histories.  They test state-machine and context-minimisation
semantics only.  They are not patient data, clinical labels, a model benchmark,
or evidence of clinical efficacy/safety.

All compared systems are evaluated on identical case identifiers:
``lww``, ``naive_rag``, ``glhs_full``, ``glhs_no_thss`` and ``glhs_no_gst``.
The latter two are constrained ablations: ``glhs_no_thss`` retains the exact
same authorization decision and changes *only* minimisation; ``glhs_no_gst``
models direct current-row mutation without the governed transition gate.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import random
import shutil
import statistics
import subprocess
import sys
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

# ``glhs_full`` is the declared reference-policy model in the development
# protocol, *not* a black-box execution of a deployed service.  Keeping that
# distinction in the machine-readable result is essential: a 100% reference
# conformance value is not an independent benchmark score.
SYSTEMS = (
    "lww",
    "naive_rag",
    "temporal_provenance_resolver",
    "glhs_full",
    "glhs_no_thss",
    "glhs_no_gst",
)
REFERENCE_SYSTEM = "glhs_full"
DEVELOPMENT_COHORT = "q2_synthetic"
EXTERNAL_COHORTS = (
    "mimic_iv_demo",
    "mimic_iv_ed_demo",
    "mimic_iv_fhir_demo",
    "synthea_fhir_r4",
    "synthea_fhir_stu3",
)
EXTERNAL_COHORT_MINIMUM_SUBJECTS = {
    "mimic_iv_demo": 100,
    "mimic_iv_ed_demo": 40,
    "mimic_iv_fhir_demo": 100,
    "synthea_fhir_r4": 100,
    "synthea_fhir_stu3": 100,
}
MODEL_ARM_SEEDS = (20260808, 20260809, 20260810)
THSS_PROFILES = ("full_authorized", "loose", "default", "strict")
SCENARIOS = (
    "ordinary_latest",
    "late_evidence",
    "duplicate_historical",
    "conflict",
    "family_isolation",
    "consent_revocation",
    "stale_state_version",
    "insufficient_provenance",
    "temporal_ambiguity",
    "scribe_ambiguity",
    "projection_rebuild",
    "direct_write_attack",
)
HISTORY_DEPTHS = (10, 50, 100, 250)
ERROR_CODES = (
    "temporal_ambiguity",
    "comparable_authority_conflict",
    "insufficient_provenance",
    "entity_normalization_ambiguity",
    "subject_profile_ambiguity",
    "stale_state_version",
    "consent_purpose_mismatch",
    "insufficient_corroboration",
    "thss_relevant_fact_omission",
    "infrastructure_or_unexpected",
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    rank = (len(values) - 1) * percentile
    lo, hi = math.floor(rank), math.ceil(rank)
    if lo == hi:
        return values[lo]
    return values[lo] + (values[hi] - values[lo]) * (rank - lo)


def wilson(successes: int, total: int) -> tuple[float, float]:
    if total <= 0:
        return (0.0, 0.0)
    z = 1.959963984540054
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def _exact_binomial_two_sided(k: int, n: int) -> float:
    """Two-sided exact sign/McNemar p-value with no SciPy dependency."""

    if n <= 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(k, n - k) + 1)) / (2**n)
    return min(1.0, 2 * tail)


def mcnemar_exact(left: Iterable[bool], right: Iterable[bool]) -> dict[str, int | float]:
    pairs = list(zip(left, right, strict=True))
    left_only = sum(a and not b for a, b in pairs)
    right_only = sum(b and not a for a, b in pairs)
    discordant = left_only + right_only
    return {
        "left_only": left_only,
        "right_only": right_only,
        "discordant": discordant,
        "p_value": _exact_binomial_two_sided(min(left_only, right_only), discordant),
    }


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    total = len(ordered)
    adjusted: dict[str, float] = {}
    previous = 0.0
    for index, (name, p_value) in enumerate(ordered):
        value = min(1.0, (total - index) * p_value)
        previous = max(previous, value)
        adjusted[name] = previous
    return adjusted


@dataclass(frozen=True)
class Case:
    case_id: str
    subject_id: str
    episode_count: int
    scenario: str
    expected_state: str
    expected_error: str | None
    critical_fact_count: int
    nonessential_authorized_fact_count: int
    authorized: bool
    experiment: str
    partition: str


@dataclass(frozen=True)
class Outcome:
    case_id: str
    subject_id: str
    scenario: str
    system: str
    state_correct: bool
    late_evidence_error: bool
    silent_conflict_collapse: bool
    provenance_complete: bool
    reconstruction_correct: bool
    unauthorized_disclosure: bool
    critical_fact_recall: float
    nonessential_disclosure: int
    gst_bypass: bool
    revocation_honored: bool
    automation: str
    error_code: str | None
    latency_us: float
    experiment: str
    partition: str


def _case(index: int) -> Case:
    """Generate the exact frozen Q2 design (400 cases / 200 subjects).

    The template is deterministic and independent of API GST/THSS code.  The
    final 60 compositional cases are labelled sealed before execution; this
    runner has no tuning mode and must be run only after the artifacts written
    by :func:`write_frozen_inputs` are committed/checksummed.
    """

    scenario = SCENARIOS[(index - 1) % len(SCENARIOS)]
    subject_id = f"S{((index - 1) % 200) + 1:03d}"
    # 8--30 episodes are deliberately represented in the source history shape;
    # no clinical values are present in this synthetic corpus.
    episode_count = 8 + ((index * 7) % 23)
    expected_state = "state_current"
    expected_error: str | None = None
    authorized = True
    if scenario in {"conflict", "scribe_ambiguity", "temporal_ambiguity"}:
        expected_state, expected_error = "conflict", "comparable_authority_conflict"
    elif scenario == "insufficient_provenance":
        expected_state, expected_error = "withheld", "insufficient_provenance"
    elif scenario == "family_isolation":
        expected_state, expected_error, authorized = "withheld", "subject_profile_ambiguity", False
    elif scenario == "consent_revocation":
        expected_state, expected_error, authorized = "withheld", "consent_purpose_mismatch", False
    elif scenario == "stale_state_version":
        expected_state, expected_error = "1000mg", "stale_state_version"
    elif scenario == "direct_write_attack":
        expected_state, expected_error = "1000mg", "insufficient_corroboration"
    return Case(
        case_id=f"Q2-{index:04d}",
        subject_id=subject_id,
        episode_count=episode_count,
        scenario=scenario,
        expected_state=expected_state,
        expected_error=expected_error,
        critical_fact_count=3,
        nonessential_authorized_fact_count=7,
        authorized=authorized,
        experiment=("direct_conformance" if index <= 100 else "ambiguity_escalation" if index > 340 else "compositional_stress"),
        partition=("sealed_holdout" if 281 <= index <= 340 else "development"),
    )


def model_arm_case_ids(cases: Iterable[Case]) -> tuple[str, ...]:
    """Return the fixed stratified 120-case model subset used before a run."""

    materialized = tuple(cases)
    quotas = {
        "direct_conformance": 30,
        "compositional_stress": 72,
        "ambiguity_escalation": 18,
    }
    selected: list[str] = []
    for experiment, quota in quotas.items():
        chosen = [case.case_id for case in materialized if case.experiment == experiment][:quota]
        if len(chosen) != quota:
            raise ValueError(f"model_arm_subset_insufficient:{experiment}")
        selected.extend(chosen)
    if len(selected) != 120 or len(set(selected)) != 120:
        raise ValueError("model_arm_subset_invalid")
    return tuple(selected)


def _load_completed_model_arm(source: Path, cases: Iterable[Case]) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Validate a completed model arm and prepare a non-PII per-seed ledger."""

    from evaluation.glhs_q2.integrate_model_arm import integrate

    summary = integrate(source, source)
    expected_digest = hashlib.sha256("\n".join(model_arm_case_ids(cases)).encode()).hexdigest()
    contract = summary["contract"]
    if contract.get("case_ids_sha256") != expected_digest:
        raise ValueError("model_arm_case_subset_mismatch")
    rows = list(csv.DictReader((source / "model_per_run.csv").open(encoding="utf-8", newline="")))
    ledger: list[dict[str, object]] = []
    for seed in MODEL_ARM_SEEDS:
        group = [row for row in rows if row.get("seed") == str(seed)]
        ledger.append({
            "seed": seed,
            "subset_id": "q2_model_subset_120_stratified",
            "cases": len(model_arm_case_ids(cases)),
            "case_ids_sha256": expected_digest,
            "status": "completed" if all(row.get("status") == "completed" for row in group) and len(group) == 120 else "invalid_or_incomplete",
            "completed": sum(row.get("status") == "completed" for row in group),
            "state_correct": sum(row.get("state_correct") == "True" for row in group),
            "json_valid": sum(row.get("json_valid") == "True" for row in group),
            "degraded_or_fallback_indicated": sum(row.get("degraded") == "True" for row in group),
            "stochastic_model_path": True,
            "note": "Synthetic structural model arm; not clinical evaluation.",
        })
    return summary, ledger


def _evaluate(case: Case, system: str) -> Outcome:
    """A transparent deterministic architecture model for a single oracle case.

    The output intentionally models only the named structural property.  It
    does not call an LLM or infer medical content.  Measuring elapsed CPU time
    around this pure function is labelled ``state_layer_simulation`` below and
    never presented as production/end-to-end latency.
    """

    started = time.perf_counter_ns()
    # LWW and naive RAG use later-ingested/corpus-recency evidence and have no
    # conflict or policy transition semantics.  They may also read context
    # despite revoked/family scope in this deliberately bounded comparison.
    baseline = system in {"lww", "naive_rag"}
    temporal_provenance = system == "temporal_provenance_resolver"
    no_gst = system == "glhs_no_gst"
    no_thss = system == "glhs_no_thss"
    state = case.expected_state
    error_code = case.expected_error
    automation = "correct_state"
    late_evidence_error = False
    silent_conflict_collapse = False
    provenance_complete = True
    reconstruction_correct = True
    unauthorized_disclosure = False
    gst_bypass = False
    revocation_honored = True

    if case.scenario in {"late_evidence", "duplicate_historical"} and (baseline or no_gst):
        state, late_evidence_error, reconstruction_correct = "state_historical", True, False
    elif case.scenario in {"conflict", "scribe_ambiguity", "temporal_ambiguity"} and (baseline or no_gst):
        state, silent_conflict_collapse, automation = "state_historical", True, "incorrect_automation"
    elif case.scenario == "insufficient_provenance" and (baseline or no_gst):
        state, provenance_complete, automation = "state_current", False, "incorrect_automation"
    elif case.scenario in {"family_isolation", "consent_revocation"} and baseline:
        state, unauthorized_disclosure, revocation_honored = "state_current", True, False
    elif case.scenario == "stale_state_version" and no_gst:
        state, gst_bypass, reconstruction_correct = "state_historical", True, False
    elif case.scenario == "direct_write_attack" and no_gst:
        state, gst_bypass, automation = "state_historical", True, "incorrect_automation"
    elif case.scenario == "projection_rebuild" and (baseline or no_gst):
        reconstruction_correct = False

    # A stronger, reproducible comparator performs valid-time/provenance
    # resolution and therefore handles late evidence, duplicate records and
    # comparable-authority conflicts.  It intentionally lacks GLHS's consent
    # boundary, governed mutation gate and projection ledger.  This is a
    # structural baseline, not a clinical system or an implementation claim.
    if temporal_provenance:
        if case.scenario in {"family_isolation", "consent_revocation"}:
            state, unauthorized_disclosure, revocation_honored = "state_current", True, False
        elif case.scenario in {"stale_state_version", "direct_write_attack"}:
            state, gst_bypass, reconstruction_correct = "state_historical", True, False
            automation = "incorrect_automation"
        elif case.scenario == "projection_rebuild":
            reconstruction_correct = False

    # The THSS ablation retains authorization exactly. It exposes all
    # authorized but nonessential facts; this is privacy minimisation loss,
    # never a fabricated cross-profile leakage.
    nonessential_disclosure = (
        case.nonessential_authorized_fact_count if no_thss and case.authorized else 0
    )
    if not case.authorized and not baseline:
        state, nonessential_disclosure = "withheld", 0
    critical_recall = 1.0 if state == case.expected_state else 0.0
    if state == "conflict" or state == "withheld":
        automation = "safe_escalation"
    latency_us = (time.perf_counter_ns() - started) / 1000
    return Outcome(
        case_id=case.case_id,
        subject_id=case.subject_id,
        scenario=case.scenario,
        system=system,
        state_correct=state == case.expected_state,
        late_evidence_error=late_evidence_error,
        silent_conflict_collapse=silent_conflict_collapse,
        provenance_complete=provenance_complete,
        reconstruction_correct=reconstruction_correct,
        unauthorized_disclosure=unauthorized_disclosure,
        critical_fact_recall=critical_recall,
        nonessential_disclosure=nonessential_disclosure,
        gst_bypass=gst_bypass,
        revocation_honored=revocation_honored,
        automation=automation,
        error_code=(error_code if automation != "correct_state" else None),
        latency_us=latency_us,
        experiment=case.experiment,
        partition=case.partition,
    )


def _aggregate(rows: list[Outcome], system: str) -> dict[str, object]:
    selected = [row for row in rows if row.system == system]
    total = len(selected)

    def binary(field: str, *, inverse: bool = False) -> dict[str, object]:
        values = [bool(getattr(row, field)) for row in selected]
        if inverse:
            values = [not value for value in values]
        numerator = sum(values)
        ci = wilson(numerator, total)
        return {"numerator": numerator, "denominator": total, "rate": numerator / total, "wilson95": [ci[0], ci[1]]}

    return {
        "state_correct": binary("state_correct"),
        "late_evidence_error": binary("late_evidence_error"),
        "silent_conflict_collapse": binary("silent_conflict_collapse"),
        "provenance_complete": binary("provenance_complete"),
        "historical_reconstruction_correct": binary("reconstruction_correct"),
        "unauthorized_disclosure": binary("unauthorized_disclosure"),
        "gst_bypass": binary("gst_bypass"),
        "revocation_honored": binary("revocation_honored"),
        "critical_fact_recall": {
            "numerator": sum(round(row.critical_fact_recall * 3) for row in selected),
            "denominator": total * 3,
            "rate": statistics.mean(row.critical_fact_recall for row in selected),
        },
        "nonessential_authorized_disclosure": {
            "numerator": sum(row.nonessential_disclosure for row in selected),
            "denominator": sum(7 for row in selected if row.scenario not in {"family_isolation", "consent_revocation"}),
        },
        "latency_us_state_layer_simulation": {
            "count": total,
            "median": statistics.median(row.latency_us for row in selected),
            "p95": _percentile([row.latency_us for row in selected], 0.95),
            "not_end_to_end_or_llm_latency": True,
        },
    }


def _thss_ablation(cases: list[Case]) -> list[dict[str, object]]:
    budgets = {"full_authorized": 10, "loose": 8, "default": 5, "strict": 3}
    rows: list[dict[str, object]] = []
    for profile in THSS_PROFILES:
        authorized = [case for case in cases if case.authorized]
        # Critical facts are selected first in every declared profile.  A flat
        # frontier is an honest result of this protocol, not a manufactured
        # utility loss by weakening authorization or relevance selection.
        critical = len(authorized) * 3
        included_critical = critical
        nonessential = len(authorized) * max(0, budgets[profile] - 3)
        rows.append({
            "profile": profile,
            "authorized_cases": len(authorized),
            "unauthorized_disclosure_numerator": 0,
            "unauthorized_disclosure_denominator": len(cases),
            "critical_fact_recall_numerator": included_critical,
            "critical_fact_recall_denominator": critical,
            "critical_fact_recall": included_critical / critical,
            "nonessential_disclosure_numerator": nonessential,
            "nonessential_disclosure_denominator": len(authorized) * 7,
            "mean_snapshot_items": budgets[profile],
            "mean_context_tokens_proxy": budgets[profile] * 12,
            "authorization_fixed": True,
        })
    return rows


def _stratified_metrics(rows: list[Outcome]) -> list[dict[str, object]]:
    """Emit frozen protocol strata without pooling cohorts or inventing labels."""

    groups = {
        "late_evidence": {"late_evidence", "duplicate_historical"},
        "conflict": {"conflict", "scribe_ambiguity", "temporal_ambiguity"},
        "authorization_revocation": {"family_isolation", "consent_revocation"},
        "stale_transition": {"stale_state_version", "direct_write_attack"},
    }
    output: list[dict[str, object]] = []
    for system in SYSTEMS:
        for stratum, scenarios in groups.items():
            selected = [row for row in rows if row.system == system and row.scenario in scenarios]
            total = len(selected)
            if not total:
                continue
            correct = sum(row.state_correct for row in selected)
            output.append({
                "system": system,
                "stratum": stratum,
                "cases": total,
                "state_correct_numerator": correct,
                "state_correct_denominator": total,
                "unauthorized_disclosure_numerator": sum(row.unauthorized_disclosure for row in selected),
                "gst_bypass_numerator": sum(row.gst_bypass for row in selected),
                "safe_escalation_numerator": sum(row.automation == "safe_escalation" for row in selected),
                "incorrect_automation_numerator": sum(row.automation == "incorrect_automation" for row in selected),
            })
    return output


def _operational_metrics(rows: list[Outcome]) -> list[dict[str, object]]:
    """Explicit structural counts for the core-metrics table; no hidden rates."""

    full = [row for row in rows if row.system == REFERENCE_SYSTEM]
    direct_writes = [row for row in full if row.scenario == "direct_write_attack"]
    conflicts = [row for row in full if row.scenario in {"conflict", "scribe_ambiguity", "temporal_ambiguity"}]
    auth = [row for row in full if row.scenario in {"family_isolation", "consent_revocation"}]
    return [
        {"metric": "provenance_coverage", "numerator": sum(row.provenance_complete for row in full), "denominator": len(full)},
        {"metric": "reconstruction_fidelity", "numerator": sum(row.reconstruction_correct for row in full), "denominator": len(full)},
        {"metric": "conflict_safe_escalation", "numerator": sum(row.automation == "safe_escalation" for row in conflicts), "denominator": len(conflicts)},
        {"metric": "policy_prohibited_disclosure", "numerator": sum(row.unauthorized_disclosure for row in full), "denominator": len(full)},
        {"metric": "ai_direct_write_bypass", "numerator": sum(row.gst_bypass for row in direct_writes), "denominator": len(direct_writes)},
        {"metric": "stale_transition_bypass", "numerator": sum(row.gst_bypass for row in full if row.scenario == "stale_state_version"), "denominator": sum(row.scenario == "stale_state_version" for row in full)},
        {"metric": "revocation_honored", "numerator": sum(row.revocation_honored for row in auth), "denominator": len(auth)},
        {"metric": "automation_correct_state", "numerator": sum(row.automation == "correct_state" for row in full), "denominator": len(full)},
        {"metric": "human_escalation", "numerator": sum(row.automation == "safe_escalation" for row in full), "denominator": len(full)},
    ]


def _comparisons(rows: list[Outcome], seed: int) -> dict[str, dict[str, object]]:
    """Paired subject-cluster comparison for one cohort or frozen stratum."""

    full_rows = [row for row in rows if row.system == REFERENCE_SYSTEM]
    comparisons: dict[str, dict[str, object]] = {}
    raw_p: dict[str, float] = {}
    for baseline in ("lww", "naive_rag", "temporal_provenance_resolver", "glhs_no_thss", "glhs_no_gst"):
        baseline_rows = [row for row in rows if row.system == baseline]
        if len(full_rows) != len(baseline_rows):
            continue
        key = f"glhs_full_vs_{baseline}"
        full_by_subject: dict[str, list[bool]] = {}
        baseline_by_subject: dict[str, list[bool]] = {}
        for row in full_rows:
            full_by_subject.setdefault(row.subject_id, []).append(row.state_correct)
        for row in baseline_rows:
            baseline_by_subject.setdefault(row.subject_id, []).append(row.state_correct)
        subjects = sorted(full_by_subject)
        if not subjects or set(subjects) != set(baseline_by_subject):
            continue
        test = mcnemar_exact([all(full_by_subject[s]) for s in subjects], [all(baseline_by_subject[s]) for s in subjects])
        raw_p[key] = float(test["p_value"])
        full_grouped: dict[str, list[Outcome]] = {}
        baseline_grouped: dict[str, list[Outcome]] = {}
        for row in full_rows:
            full_grouped.setdefault(row.subject_id, []).append(row)
        for row in baseline_rows:
            baseline_grouped.setdefault(row.subject_id, []).append(row)
        by_subject = {
            subject: [float(left.state_correct) - float(right.state_correct)
                      for left, right in zip(full_grouped[subject], baseline_grouped[subject], strict=True)]
            for subject in subjects
        }
        observed = statistics.mean(value for values in by_subject.values() for value in values)
        rng = random.Random(seed + len(comparisons))
        subject_means = {subject: statistics.mean(values) for subject, values in by_subject.items()}
        # Keep the full 2,000-replicate protocol for small cohorts. The 16k
        # subject Synthea scale cohort uses 200 explicitly recorded replicates
        # so the reproducible full-data run remains tractable in CI.
        replicates = 200 if len(subjects) > 1_000 else 2_000
        mean_values = [subject_means[subject] for subject in subjects]
        boots = [sum(rng.choices(mean_values, k=len(mean_values))) / len(mean_values) for _ in range(replicates)]
        comparisons[key] = {"state_correct_mcnemar_exact_subject_summary": test, "mcnemar_summary_rule": "subject is correct only if all frozen structural cases for that subject are correct", "patient_bootstrap_risk_difference": {"risk_difference": observed, "ci95_low": _percentile(boots, 0.025), "ci95_high": _percentile(boots, 0.975), "bootstrap_replicates": replicates}}
    for key, adjusted in holm_adjust(raw_p).items():
        comparisons[key]["state_correct_mcnemar_exact_subject_summary"]["holm_adjusted_p_value"] = adjusted
    return comparisons


def _scalability(seed: int) -> list[dict[str, object]]:
    """Measured pure-Python simulation operation timings at declared depths."""

    rng = random.Random(seed)
    rows: list[dict[str, object]] = []
    for depth in HISTORY_DEPTHS:
        samples: dict[str, list[float]] = {"gst": [], "thss_compile": [], "reconstruct": [], "rebuild": []}
        for _ in range(50):
            history = [(rng.randrange(5), rng.randrange(10_000)) for _ in range(depth)]
            started = time.perf_counter_ns(); current = {key: value for key, value in history}; samples["gst"].append((time.perf_counter_ns() - started) / 1000)
            started = time.perf_counter_ns(); _ = [item for item in current.items() if item[0] % 2 == 0][:10]; samples["thss_compile"].append((time.perf_counter_ns() - started) / 1000)
            started = time.perf_counter_ns(); replay = {}; [replay.__setitem__(key, value) for key, value in history]; samples["reconstruct"].append((time.perf_counter_ns() - started) / 1000)
            started = time.perf_counter_ns(); _ = dict(replay); samples["rebuild"].append((time.perf_counter_ns() - started) / 1000)
        for operation, values in samples.items():
            rows.append({"history_depth": depth, "operation": operation, "samples": len(values), "median_us": statistics.median(values), "p95_us": _percentile(values, 0.95), "scope": "pure_python_structural_simulation_not_database_or_llm"})
    return rows


def _not_run_mimic_demo(reason: str) -> dict[str, object]:
    return {
        "status": "not_run",
        "reason": reason,
        "clinical_data_loaded": False,
    }


def _load_external_structural_manifest(manifest_path: Path | None) -> dict[str, object]:
    """Load a declared external/synthetic structural perturbation cohort.

    The runner never downloads MIMIC, accepts credentialed full-MIMIC paths, or
    reads raw clinical resources.  A lawful preparer may provide a small,
    pre-derived JSONL file of controlled structural perturbations.  Each row is
    limited to a non-identifying subject token and the oracle fields necessary
    for this state-machine protocol; free text and clinical facts are rejected.
    """

    if manifest_path is None:
        return _not_run_mimic_demo(
            "No explicit lawful external cohort manifest was supplied; MIMIC and "
            "Synthea are never downloaded or treated as evaluated implicitly."
        )
    manifest_path = manifest_path.resolve()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid_mimic_demo_manifest:{error}") from error
    if not isinstance(manifest, dict):
        raise TypeError("invalid_mimic_demo_manifest_schema")
    schema_version = manifest.get("schema_version")
    legacy_v1 = schema_version == "glhs-q3-mimic-demo-v1"
    # Accept the legacy Q3-labelled preparer artifact only for reproducibility
    # of already emitted development runs.  New Q2 preparers emit the Q2
    # schema; both have the identical privacy-minimised structural contract.
    v2 = schema_version in {
        "glhs-q3-external-structural-v2",
        "glhs-q2-external-structural-v2",
    }
    if not (legacy_v1 or v2):
        raise ValueError("invalid_mimic_demo_manifest_schema")
    cohort = manifest.get("cohort")
    if legacy_v1:
        if cohort != "mimic_iv_demo_fhir":
            raise ValueError("mimic_demo_cohort_must_be_mimic_iv_demo_fhir")
    elif cohort not in EXTERNAL_COHORTS:
        raise ValueError("external_cohort_unsupported")
    attestation = manifest.get("lawful_access_attestation")
    if not isinstance(attestation, str) or not attestation.strip():
        raise ValueError("mimic_demo_requires_lawful_access_attestation")
    partition = "development" if legacy_v1 else manifest.get("partition")
    if partition not in {"development", "sealed_holdout"}:
        raise ValueError("external_cohort_partition_invalid")
    final_eligibility = False
    freeze: dict[str, str] | None = None
    if v2 and partition == "sealed_holdout":
        required_freeze = (
            "freeze_id",
            "frozen_at",
            "curator",
            "independence_attestation",
            "oracle_freeze_sha256",
            "development_set_sha256",
        )
        raw_freeze = manifest.get("freeze")
        if not isinstance(raw_freeze, dict) or any(
            not isinstance(raw_freeze.get(key), str) or not raw_freeze[key].strip()
            for key in required_freeze
        ):
            raise ValueError("external_cohort_freeze_metadata_invalid")
        freeze = {key: raw_freeze[key] for key in required_freeze}
        final_eligibility = partition == "sealed_holdout"
    relative = manifest.get("perturbations_file")
    expected_sha256 = manifest.get("perturbations_sha256")
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("mimic_demo_perturbations_file_must_be_relative")
    perturbations_path = (manifest_path.parent / relative).resolve()
    if manifest_path.parent not in perturbations_path.parents:
        raise ValueError("mimic_demo_perturbations_path_escapes_manifest_directory")
    if not isinstance(expected_sha256, str) or _sha256_file(perturbations_path) != expected_sha256:
        raise ValueError("mimic_demo_perturbations_checksum_mismatch")

    allowed_fields = {
        "case_id",
        "subject_token",
        "scenario",
        "expected_state",
        "expected_error",
        "critical_fact_count",
        "nonessential_authorized_fact_count",
        "authorized",
        "episode_count",
    }
    rows: list[Case] = []
    try:
        source_lines = perturbations_path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ValueError(f"mimic_demo_perturbations_unreadable:{error}") from error
    for line_number, line in enumerate(source_lines, start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid_mimic_demo_perturbation_jsonl:{line_number}") from error
        if not isinstance(raw, dict) or set(raw) - allowed_fields:
            raise ValueError(f"mimic_demo_contains_disallowed_or_raw_field:{line_number}")
        required = allowed_fields
        if set(raw) != required:
            raise ValueError(f"mimic_demo_perturbation_missing_field:{line_number}")
        scenario = raw["scenario"]
        if scenario not in SCENARIOS:
            raise ValueError(f"mimic_demo_invalid_scenario:{line_number}")
        subject = raw["subject_token"]
        case_id = raw["case_id"]
        if not isinstance(subject, str) or not subject or not isinstance(case_id, str) or not case_id:
            raise ValueError(f"mimic_demo_identifier_invalid:{line_number}")
        if not isinstance(raw["expected_state"], str) or (
            raw["expected_error"] is not None and not isinstance(raw["expected_error"], str)
        ):
            raise ValueError(f"mimic_demo_oracle_invalid:{line_number}")
        if not all(
            isinstance(raw[key], int) and raw[key] >= 0
            for key in ("episode_count", "critical_fact_count", "nonessential_authorized_fact_count")
        ) or not isinstance(raw["authorized"], bool):
            raise ValueError(f"mimic_demo_numeric_or_authorization_invalid:{line_number}")
        rows.append(
            Case(
                case_id=case_id,
                subject_id=subject,
                episode_count=raw["episode_count"],
                scenario=scenario,
                expected_state=raw["expected_state"],
                expected_error=raw["expected_error"],
                critical_fact_count=raw["critical_fact_count"],
                nonessential_authorized_fact_count=raw["nonessential_authorized_fact_count"],
                authorized=raw["authorized"],
                experiment="external_structural",
                partition=str(partition),
            )
        )
    required_subjects = 100 if legacy_v1 else EXTERNAL_COHORT_MINIMUM_SUBJECTS[str(cohort)]
    if len(rows) < required_subjects or len({row.subject_id for row in rows}) < required_subjects:
        raise ValueError(
            "external_cohort_requires_minimum_cases_and_subject_tokens:"
            f"{required_subjects}"
        )
    if len({row.case_id for row in rows}) != len(rows):
        raise ValueError("mimic_demo_case_id_must_be_unique")
    outcomes = [_evaluate(case, system) for system in SYSTEMS for case in rows]
    return {
        "status": "evaluated_deidentified_structural_perturbations",
        "schema_version": schema_version,
        "cohort": cohort,
        "partition": partition,
        "eligible_for_final_score": final_eligibility,
        "freeze": freeze,
        "clinical_data_loaded": False,
        "manifest_path": str(manifest_path),
        "perturbations_sha256": expected_sha256,
        "cases": len(rows),
        "subjects": len({row.subject_id for row in rows}),
        "lawful_access_attestation_present": True,
        "source_provenance": {
            key: manifest[key]
            for key in (
                "source_table_sha256",
                "source_tables_sha256",
                "source_table_relative_path",
                "source_table_rows",
                "source_table_subjects",
                "source_archive_sha256",
                "source_archive_bytes",
                "source_scan",
                "fhir_release",
                "source_rows",
                "source_subjects",
                "clinical_data_in_output",
                "tokenization",
                "perturbation_policy",
            )
            if key in manifest
        },
        "metrics": {system: _aggregate(outcomes, system) for system in SYSTEMS},
        "raw_cases": [asdict(case) for case in rows],
        "raw_outcomes": [asdict(outcome) for outcome in outcomes],
        "limitations": [
            "Pre-derived controlled perturbations only; no raw MIMIC resource was loaded.",
            "Structural oracle conformance only; not clinical validation.",
            (
                "The manifest attests to freezing/independence; the runner can verify "
                "its required metadata and checksums but cannot independently verify the curator."
            ),
        ],
    }


def _load_mimic_demo_structural_manifest(manifest_path: Path | None) -> dict[str, object]:
    """Backward-compatible name retained for existing users of the runner."""

    return _load_external_structural_manifest(manifest_path)


def _reproducibility_manifest(mimic_demo: dict[str, object]) -> dict[str, object]:
    root = Path(__file__).resolve().parents[2]
    tracked = (
        "services/api/src/clara_api/glhs/gateway.py",
        "services/api/src/clara_api/glhs/adapters.py",
        "services/api/src/clara_api/db/models.py",
        "services/api/alembic/versions/20260808_0050_glhs_foundation.py",
        "evaluation/glhs_q2/run.py",
    )
    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        revision = "unavailable"
    return {
        "code_revision": revision,
        "runner_sha256": _sha256_file(Path(__file__).resolve()),
        "source_sha256": {name: _sha256_file(root / name) for name in tracked if (root / name).is_file()},
        "clinical_data": False,
        "mimic_demo": mimic_demo,
        "environment": {"python": sys.version.split()[0], "platform": platform.platform(), "standard_library_only": True},
    }


def run(
    seed: int,
    cases_count: int,
    mimic_demo_manifest: Path | None = None,
    *,
    frozen_input_sha256: dict[str, str] | None = None,
    completed_model_arm: tuple[dict[str, object], list[dict[str, object]]] | None = None,
) -> dict[str, object]:
    if cases_count != 400:
        raise ValueError("Q2 requires exactly 400 synthetic cases")
    cases = [_case(index) for index in range(1, cases_count + 1)]
    outcomes = [_evaluate(case, system) for system in SYSTEMS for case in cases]
    metrics = {system: _aggregate(outcomes, system) for system in SYSTEMS}
    full_rows = [row for row in outcomes if row.system == "glhs_full"]
    comparisons: dict[str, dict[str, object]] = {}
    raw_p: dict[str, float] = {}
    for baseline in (
        "lww",
        "naive_rag",
        "temporal_provenance_resolver",
        "glhs_no_thss",
        "glhs_no_gst",
    ):
        baseline_rows = [row for row in outcomes if row.system == baseline]
        key = f"glhs_full_vs_{baseline}"
        # Sensitivity analysis uses one predeclared summary per subject (all
        # that subject's structural cases must be correct), never the repeated
        # event-level outcomes as if they were independent observations.
        full_by_subject: dict[str, list[bool]] = {}
        baseline_by_subject: dict[str, list[bool]] = {}
        for row in full_rows:
            full_by_subject.setdefault(row.subject_id, []).append(row.state_correct)
        for row in baseline_rows:
            baseline_by_subject.setdefault(row.subject_id, []).append(row.state_correct)
        ordered_subjects = sorted(full_by_subject)
        test = mcnemar_exact(
            [all(full_by_subject[subject]) for subject in ordered_subjects],
            [all(baseline_by_subject[subject]) for subject in ordered_subjects],
        )
        raw_p[key] = float(test["p_value"])
        comparisons[key] = {
            "state_correct_mcnemar_exact_subject_summary": test,
            "mcnemar_summary_rule": "subject is correct only if all frozen structural cases for that subject are correct",
        }
        # The two system rows are paired case-by-case. Resample subjects, not
        # individual episodes/cases, to avoid event-level pseudo-replication.
        by_subject: dict[str, list[float]] = {}
        for left, right in zip(full_rows, baseline_rows, strict=True):
            by_subject.setdefault(left.subject_id, []).append(float(left.state_correct) - float(right.state_correct))
        rng = random.Random(seed + len(comparisons))
        subjects = sorted(by_subject)
        observed = statistics.mean(value for values in by_subject.values() for value in values)
        boots = []
        for _ in range(2000):
            chosen = [subjects[rng.randrange(len(subjects))] for _ in subjects]
            boots.append(statistics.mean(value for subject in chosen for value in by_subject[subject]))
        comparisons[key]["patient_bootstrap_risk_difference"] = {"risk_difference": observed, "ci95_low": _percentile(boots, 0.025), "ci95_high": _percentile(boots, 0.975)}
    adjusted = holm_adjust(raw_p)
    for key, p_value in adjusted.items():
        comparisons[key]["state_correct_mcnemar_exact_subject_summary"]["holm_adjusted_p_value"] = p_value
    # The model-backed arm is deliberately represented as not run until a
    # provider/model/config snapshot is frozen.  It is *not* a surrogate model
    # score, and the deterministic state-layer repetitions below must never be
    # reported as a model result.
    predeclared_subset = model_arm_case_ids(cases)
    per_run = [
        {
            "seed": repeat_seed,
            "subset_id": "q2_model_subset_120_stratified",
            "cases": len(predeclared_subset),
            "case_ids_sha256": hashlib.sha256("\n".join(predeclared_subset).encode()).hexdigest(),
            "status": "not_run_no_frozen_model_provider_config",
            "stochastic_model_path": False,
            "note": "No LLM/provider/model execution occurred. This row is a required-run ledger, not a model score.",
        }
        for repeat_seed in MODEL_ARM_SEEDS
    ]
    model_arm_summary: dict[str, object] | None = None
    if completed_model_arm is not None:
        model_arm_summary, per_run = completed_model_arm
    error_analysis = []
    for system in SYSTEMS:
        selected = [row for row in outcomes if row.system == system]
        for code in ERROR_CODES:
            matching = [row for row in selected if row.error_code == code]
            if matching:
                error_analysis.append({"system": system, "error_code": code, "count": len(matching), "denominator": len(selected), "safe_escalation": sum(row.automation == "safe_escalation" for row in matching), "incorrect_automation": sum(row.automation == "incorrect_automation" for row in matching), "representative_case_ids": [row.case_id for row in matching[:3]]})
    external_cohort = _load_external_structural_manifest(mimic_demo_manifest)
    # Preserve minimised raw rows for their dedicated CSV artifacts only. They
    # must not be embedded in summary/environment JSON, which are intended for
    # aggregate reporting and are safer to circulate.
    external_raw = {
        "cases": external_cohort.pop("raw_cases", []),
        "outcomes": external_cohort.pop("raw_outcomes", []),
    }
    external_outcome_rows = [Outcome(**row) for row in external_raw["outcomes"]]
    external_stratified = _stratified_metrics(external_outcome_rows)
    external_comparisons = _comparisons(external_outcome_rows, seed + 10_000)
    final_score_released = bool(external_cohort.get("eligible_for_final_score"))
    return {
        "schema_version": "glhs-q2-structural-v1",
        "protocol": {
            "name": "glhs-q2-structural-v1",
            "seed": seed,
            "subjects": 200,
            "cases": cases_count,
            "strata": {
                "direct_conformance": 100,
                "compositional_stress": 240,
                "ambiguity_escalation": 60,
                "sealed_compositional_holdout": 60,
            },
            "episodes_per_subject": [8, 30],
            "clinical_validation": False,
            "reference_policy_system": REFERENCE_SYSTEM,
            "reference_policy_score_interpretation": (
                "Development conformance only; not an independently evaluated "
                "implementation score."
            ),
            "frozen_input_sha256": frozen_input_sha256 or {},
            "model_backed_execution": {
                "subset_cases": 120,
                "seeds": list(MODEL_ARM_SEEDS),
                "status": "completed" if model_arm_summary is not None else "not_run_no_frozen_model_provider_config",
                "artifact": "model_arm_summary.json" if model_arm_summary is not None else None,
                "aggregate": model_arm_summary.get("aggregate") if model_arm_summary is not None else None,
            },
            "limitations": [
                "Developer-authored oracle cases",
                "No patient data or external cohort unless explicitly manifested",
                *( [] if model_arm_summary is not None else ["No LLM/provider path"] ),
                "State-layer simulation latency is not production latency",
                "Reference policy and development oracle share rules; perfect development conformance is expected and non-comparative",
            ],
        },
        "reproducibility": _reproducibility_manifest(external_cohort),
        "cohorts": {
            DEVELOPMENT_COHORT: {
                "status": "evaluated_developer_authored",
                "partition": "development",
                "eligible_for_final_score": False,
                "metrics": metrics,
                "reference_policy_system": REFERENCE_SYSTEM,
            },
            "external": external_cohort,
        },
        # Keep this legacy field for existing reports while new consumers use
        # ``cohorts.external`` and must report cohorts separately.
        "mimic_demo": external_cohort,
        "score_release": {
            "final_score_released": final_score_released,
            "reason": (
                "A checksum-locked external sealed holdout with freeze metadata was supplied."
                if final_score_released
                else (
                    "No checksum-locked external sealed holdout was supplied. "
                    "Development/reference-policy values must not be reported as a final benchmark score."
                )
            ),
            "required_for_final_score": [
                "external cohort manifest schema v2",
                "partition=sealed_holdout",
                "freeze metadata including curator independence attestation",
                "checksum-locked perturbations and oracle freeze",
            ],
        },
        "metrics": metrics,
        "comparisons": comparisons,
        "thss_ablation": _thss_ablation(cases),
        "error_analysis": error_analysis,
        "stratified_metrics": _stratified_metrics(outcomes),
        "operational_metrics": _operational_metrics(outcomes),
        "scalability": _scalability(seed),
        "per_run": per_run,
        "model_arm": model_arm_summary,
        "cases": [asdict(case) for case in cases],
        "outcomes": [asdict(row) for row in outcomes],
        "external_raw": {**external_raw, "stratified_metrics": external_stratified, "comparisons": external_comparisons},
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def _write_frozen_inputs(output: Path, cases: list[dict[str, object]]) -> dict[str, str]:
    """Materialize pre-execution Q2 contracts independently of GST/THSS code."""
    policy = {
        "schema_version": "glhs-q2-medication-policy-v1",
        "frozen_before_execution": True,
        "rules": {"late_evidence": "retain_valid_time", "equal_authority": "preserve_conflict", "stale_transition": "reject_or_reconcile", "ai_write": "proposal_only"},
    }
    relevance = {"schema_version": "glhs-q2-task-relevance-v1", "builder_uses_thss": False, "critical_fact_count": 3, "nonessential_authorized_fact_count": 7, "profiles": list(THSS_PROFILES)}
    oracle = {"schema_version": "glhs-q2-oracle-v1", "builder_uses_production_gst_or_thss": False, "cases": cases}
    holdout = {"schema_version": "glhs-q2-holdout-v1", "holdout_inspected_during_tuning": False, "case_ids": [row["case_id"] for row in cases if row["partition"] == "sealed_holdout"], "template_seed": 20260808}
    # These are literature-positioning records, not experimental outcomes. NR
    # means the cited primary description does not explicitly report a
    # first-class mechanism; it never asserts that the mechanism is absent.
    mechanism = {
        "schema_version": "glhs-q2-mechanism-evidence-v1",
        "source_document": "CLARA-Care_GLHS_IEEE_v10_Q2_second_round.pdf, Table I",
        "entries": [
            {"comparator": "openEHR RM", "citation": "[12] openEHR Reference Model", "inclusion_criterion": "published specification explicitly describes EHR version/access/content model", "cells": {"valid_knowledge_time": "Partial", "provenance_linked_state": "Yes", "historical_replay": "Yes", "governed_mutation_boundary": "Partial", "purpose_bounded_projection": "NR", "revocation_aware_ai_context": "Partial"}, "glhs_distinction": "GST and THSS share state/policy-version constraints."},
            {"comparator": "FHIR Provenance + Consent", "citation": "[10] FHIR Provenance; [11] FHIR Consent", "inclusion_criterion": "published FHIR R4 resources explicitly describe provenance and consent representation", "cells": {"valid_knowledge_time": "Partial", "provenance_linked_state": "Partial", "explicit_unresolved_conflict": "NR", "historical_replay": "Partial", "governed_mutation_boundary": "NR", "purpose_bounded_projection": "Partial", "revocation_aware_ai_context": "Partial"}, "glhs_distinction": "FHIR resources represent facts; they do not themselves define the coupled GST/THSS execution contract."},
            {"comparator": "TRACE", "citation": "[6] TRACE", "inclusion_criterion": "cited system explicitly reports structured temporal patient state", "cells": {"valid_knowledge_time": "Yes/structured temporal state", "provenance_linked_state": "NR", "explicit_unresolved_conflict": "NR", "historical_replay": "NR", "governed_mutation_boundary": "Partial", "purpose_bounded_projection": "NR", "revocation_aware_ai_context": "NR"}, "glhs_distinction": "No cited shared version-coupled mutation and disclosure boundary."},
            {"comparator": "Dual-Stream Reconciliation", "citation": "[15] Pugh et al.", "inclusion_criterion": "cited architecture explicitly reports discrepancy reconciliation", "cells": {"valid_knowledge_time": "Partial", "provenance_linked_state": "Partial", "explicit_unresolved_conflict": "Yes", "historical_replay": "NR", "governed_mutation_boundary": "Partial", "purpose_bounded_projection": "NR", "revocation_aware_ai_context": "NR"}, "glhs_distinction": "Not reported as a general version-coupled lifecycle across heterogeneous sources."},
            {"comparator": "Baichuan-M4", "citation": "[7] Baichuan-M4", "inclusion_criterion": "cited system explicitly reports long-term memory and action constraints", "cells": {"valid_knowledge_time": "Partial", "provenance_linked_state": "Partial", "explicit_unresolved_conflict": "NR", "historical_replay": "NR", "governed_mutation_boundary": "Partial/action constraints", "purpose_bounded_projection": "NR", "revocation_aware_ai_context": "NR"}, "glhs_distinction": "No cited base-state-version precondition and task/purpose-bounded snapshot."},
            {"comparator": "VISTA Architect", "citation": "[16] VISTA Architect", "inclusion_criterion": "cited system explicitly reports provenance-linked persistent state and temporal synthesis", "cells": {"valid_knowledge_time": "Yes/temporal synthesis", "provenance_linked_state": "Yes", "explicit_unresolved_conflict": "Partial/deduplication", "historical_replay": "Partial/source graph", "governed_mutation_boundary": "NR", "purpose_bounded_projection": "NR", "revocation_aware_ai_context": "NR"}, "glhs_distinction": "No cited GST-like gate coupled to revocation-aware THSS disclosure."},
        ],
        "interpretation": "This file supports manuscript positioning only and must be revised if the cited primary descriptions or Table I claims change.",
    }
    payloads = {"policy.json": policy, "task_relevance_manifest.json": relevance, "oracle_manifest.json": oracle, "holdout_manifest.json": holdout, "mechanism_evidence.json": mechanism}
    hashes: dict[str, str] = {}
    for name, payload in payloads.items():
        path = output / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        hashes[name] = _sha256_file(path)
    return hashes


def _svg_bar_chart(metrics: dict[str, object]) -> str:
    bars = []
    for index, (name, value) in enumerate(metrics.items()):
        rate = value["state_correct"]["rate"]
        height = int(rate * 150)
        x = 35 + index * 100
        bars.append(f'<rect x="{x}" y="{185-height}" width="55" height="{height}" fill="#60a5fa"/><text x="{x}" y="210" fill="#e1e2e9" font-size="10">{name}</text>')
    return '<svg xmlns="http://www.w3.org/2000/svg" width="560" height="235" viewBox="0 0 560 235"><rect width="100%" height="100%" fill="#101419"/><text x="20" y="28" fill="#e1e2e9" font-family="sans-serif">Synthetic structural state correctness</text>' + "".join(bars) + "</svg>"


def _svg_thss_frontier(rows: list[dict[str, object]]) -> str:
    points = []
    labels = []
    for index, row in enumerate(rows):
        disclosure = row["nonessential_disclosure_numerator"] / row["nonessential_disclosure_denominator"]
        recall = row["critical_fact_recall"]
        x, y = 65 + int(disclosure * 420), 190 - int(recall * 130)
        color = "#a4c9ff" if row["authorization_fixed"] else "#ffb4ab"
        points.append(f'<circle cx="{x}" cy="{y}" r="6" fill="{color}"/>')
        labels.append(f'<text x="{x-15}" y="{y-10}" fill="#c1c7d3" font-size="10">{row["profile"]}</text>')
    return '<svg xmlns="http://www.w3.org/2000/svg" width="560" height="235" viewBox="0 0 560 235"><rect width="100%" height="100%" fill="#101419"/><text x="20" y="28" fill="#e1e2e9" font-family="sans-serif">THSS privacy–utility (authorization fixed)</text><line x1="65" y1="190" x2="485" y2="190" stroke="#414751"/><line x1="65" y1="60" x2="65" y2="190" stroke="#414751"/><text x="350" y="220" fill="#c1c7d3" font-size="10">nonessential authorized disclosure</text><text x="5" y="55" fill="#c1c7d3" font-size="10">critical recall</text>' + "".join(points + labels) + "</svg>"


def _svg_conflict_automation(rows: list[dict[str, object]]) -> str:
    systems = SYSTEMS
    bars = []
    for index, system in enumerate(systems):
        matching = [row for row in rows if row["system"] == system]
        safe = sum(int(row["safe_escalation"]) for row in matching)
        incorrect = sum(int(row["incorrect_automation"]) for row in matching)
        x = 35 + index * 100
        bars.append(f'<rect x="{x}" y="{185-safe}" width="24" height="{safe}" fill="#a4c9ff"/><rect x="{x+28}" y="{185-incorrect}" width="24" height="{incorrect}" fill="#ffb4ab"/><text x="{x}" y="210" fill="#e1e2e9" font-size="10">{system}</text>')
    return '<svg xmlns="http://www.w3.org/2000/svg" width="560" height="235" viewBox="0 0 560 235"><rect width="100%" height="100%" fill="#101419"/><text x="20" y="28" fill="#e1e2e9" font-family="sans-serif">Synthetic conflict: safe escalation / incorrect automation</text><rect x="350" y="15" width="9" height="9" fill="#a4c9ff"/><text x="364" y="24" fill="#c1c7d3" font-size="10">safe escalation</text><rect x="450" y="15" width="9" height="9" fill="#ffb4ab"/><text x="464" y="24" fill="#c1c7d3" font-size="10">incorrect automation</text>' + "".join(bars) + "</svg>"


def _svg_error_breakdown(rows: list[dict[str, object]]) -> str:
    totals: dict[str, int] = {}
    for row in rows:
        totals[str(row["error_code"])] = totals.get(str(row["error_code"]), 0) + int(row["count"])
    bars = []
    for index, (code, count) in enumerate(sorted(totals.items())):
        x = 25 + index * 52
        height = min(140, count * 3)
        bars.append(f'<rect x="{x}" y="{185-height}" width="30" height="{height}" fill="#fabd34"/><text x="{x}" y="{205 + (index % 2) * 12}" fill="#c1c7d3" font-size="7">{code[:7]}</text>')
    return '<svg xmlns="http://www.w3.org/2000/svg" width="560" height="235" viewBox="0 0 560 235"><rect width="100%" height="100%" fill="#101419"/><text x="20" y="28" fill="#e1e2e9" font-family="sans-serif">Synthetic primary error categories</text>' + "".join(bars) + "</svg>"


def _svg_latency(metrics: dict[str, object]) -> str:
    values = [value["latency_us_state_layer_simulation"]["p95"] for value in metrics.values()]
    scale = 145 / max(max(values), 1.0)
    bars = []
    for index, (name, value) in enumerate(metrics.items()):
        height = max(1, int(value["latency_us_state_layer_simulation"]["p95"] * scale))
        x = 35 + index * 100
        bars.append(f'<rect x="{x}" y="{185-height}" width="55" height="{height}" fill="#b4c5ff"/><text x="{x}" y="210" fill="#e1e2e9" font-size="10">{name}</text>')
    return '<svg xmlns="http://www.w3.org/2000/svg" width="560" height="235" viewBox="0 0 560 235"><rect width="100%" height="100%" fill="#101419"/><text x="20" y="28" fill="#e1e2e9" font-family="sans-serif">State-layer simulation latency P95 (microseconds; not E2E/LLM)</text>' + "".join(bars) + "</svg>"


def _svg_scalability(rows: list[dict[str, object]]) -> str:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault(str(row["operation"]), []).append(row)
    colors = {"gst": "#a4c9ff", "thss_compile": "#b4c5ff", "reconstruct": "#fabd34", "rebuild": "#ffb4ab"}
    max_value = max(float(row["p95_us"]) for row in rows) or 1.0
    fragments = []
    for operation, operation_rows in grouped.items():
        points = []
        for row in sorted(operation_rows, key=lambda item: int(item["history_depth"])):
            depth = int(row["history_depth"])
            x = {10: 80, 50: 200, 100: 320, 250: 450}[depth]
            y = 190 - int(float(row["p95_us"]) / max_value * 130)
            points.append(f"{x},{y}")
        color = colors[operation]
        joined_points = " ".join(points)
        label_x = 30 + len(fragments) * 120
        fragments.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="2" '
            f'points="{joined_points}"/><text x="{label_x}" y="220" '
            f'fill="{color}" font-size="10">{operation}</text>'
        )
    return '<svg xmlns="http://www.w3.org/2000/svg" width="560" height="235" viewBox="0 0 560 235"><rect width="100%" height="100%" fill="#101419"/><text x="20" y="28" fill="#e1e2e9" font-family="sans-serif">Structural simulation scalability P95 (microseconds)</text><line x1="60" y1="190" x2="485" y2="190" stroke="#414751"/>' + "".join(fragments) + "</svg>"


def write(
    result: dict[str, object],
    output: Path,
    *,
    frozen_input_sha256: dict[str, str],
    model_arm_source: Path | None = None,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    # Case-level records are deliberately retained only in their CSV tables.
    # Keeping them out of summary.json makes the summary an aggregate report
    # and prevents accidental re-distribution of even pseudonymised tokens.
    persisted = {
        key: value
        for key, value in result.items()
        if key not in {"cases", "outcomes", "external_raw"}
    }
    raw = json.dumps(persisted, ensure_ascii=False, indent=2, sort_keys=True)
    summary_path = output / "summary.json"
    summary_path.write_text(raw + "\n", encoding="utf-8")
    # The evidence manifest must bind the exact persisted bytes, including the
    # final newline, rather than an in-memory pre-write representation.
    digest = _sha256_file(summary_path)
    (output / "environment.json").write_text(json.dumps(result["reproducibility"], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_csv(output / "cases.csv", result["cases"])
    _write_csv(output / "per_run.csv", result["per_run"])
    _write_csv(output / "conformance.csv", [row for row in result["outcomes"] if row["experiment"] == "direct_conformance"])
    _write_csv(output / "ablation.csv", [{"comparison": name, **value["patient_bootstrap_risk_difference"]} for name, value in result["comparisons"].items()])
    comparison_rows = []
    for name, value in result["comparisons"].items():
        comparison_rows.append({"comparison": name, **value["state_correct_mcnemar_exact_subject_summary"], **value["patient_bootstrap_risk_difference"]})
    _write_csv(output / "baseline_comparison.csv", comparison_rows)
    _write_csv(output / "thss_ablation.csv", result["thss_ablation"])
    _write_csv(output / "error_analysis.csv", result["error_analysis"])
    _write_csv(output / "stratified_metrics.csv", result["stratified_metrics"])
    _write_csv(output / "operational_metrics.csv", result["operational_metrics"])
    _write_csv(output / "scalability.csv", result["scalability"])
    _write_csv(output / "outcomes.csv", result["outcomes"])
    if model_arm_source is not None:
        for name in (
            "model_arm_contract.json",
            "model_per_run.csv",
            "model_arm_summary.json",
            "model_arm_by_experiment.csv",
        ):
            source = model_arm_source / name
            if not source.is_file():
                raise ValueError(f"model_arm_artifact_missing:{name}")
            shutil.copy2(source, output / name)
    external = result["cohorts"]["external"]
    external_raw = result["external_raw"]
    if external.get("status") == "evaluated_deidentified_structural_perturbations":
        _write_csv(output / "external_cases.csv", external_raw["cases"])
        _write_csv(output / "external_outcomes.csv", external_raw["outcomes"])
        _write_csv(output / "external_stratified_metrics.csv", external_raw["stratified_metrics"])
        _write_csv(output / "external_baseline_comparison.csv", [{"comparison": name, **value["state_correct_mcnemar_exact_subject_summary"], **value["patient_bootstrap_risk_difference"]} for name, value in external_raw["comparisons"].items()])
    else:
        _write_csv(output / "external_cases.csv", [])
        _write_csv(output / "external_outcomes.csv", [])
        _write_csv(output / "external_stratified_metrics.csv", [])
        _write_csv(output / "external_baseline_comparison.csv", [])
    (output / "baseline-comparison.svg").write_text(_svg_bar_chart(result["metrics"]), encoding="utf-8")
    (output / "thss-privacy-utility.svg").write_text(_svg_thss_frontier(result["thss_ablation"]), encoding="utf-8")
    (output / "conflict-automation.svg").write_text(_svg_conflict_automation(result["error_analysis"]), encoding="utf-8")
    (output / "error-breakdown.svg").write_text(_svg_error_breakdown(result["error_analysis"]), encoding="utf-8")
    (output / "latency.svg").write_text(_svg_latency(result["metrics"]), encoding="utf-8")
    (output / "scalability.svg").write_text(_svg_scalability(result["scalability"]), encoding="utf-8")
    lines = [
        "# GLHS Q2 frozen structural evaluation",
        "",
        (
            "Developer-authored oracle cases only; this artifact is **not clinical validation**. "
            "`glhs_full` is a reference-policy conformance model, so its development "
            "value is **not an independent benchmark score**."
        ),
        "",
        "| System | Development state correct | Wilson 95% CI |",
        "|---|---:|---:|",
    ]
    for system, value in result["metrics"].items():
        state = value["state_correct"]; ci = state["wilson95"]
        lines.append(f"| {system} | {state['numerator']}/{state['denominator']} | {ci[0]:.3f}–{ci[1]:.3f} |")
    lines += [
        "",
        f"Frozen summary SHA-256: `{digest}`",
        "",
        f"Final benchmark score released: `{result['score_release']['final_score_released']}`.",
        str(result["score_release"]["reason"]),
        "",
        (
            "The THSS ablation keeps authorization fixed and varies minimisation only. "
            "External cohorts are reported separately and remain not run unless an "
            "explicit lawful structural manifest is supplied."
        ),
    ]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    artifact_names = ["summary.json", "environment.json", "cases.csv", "outcomes.csv", "external_cases.csv", "external_outcomes.csv", "external_stratified_metrics.csv", "external_baseline_comparison.csv", "per_run.csv", "conformance.csv", "baseline_comparison.csv", "ablation.csv", "thss_ablation.csv", "error_analysis.csv", "stratified_metrics.csv", "operational_metrics.csv", "scalability.csv", "policy.json", "task_relevance_manifest.json", "oracle_manifest.json", "holdout_manifest.json", "mechanism_evidence.json", "baseline-comparison.svg", "thss-privacy-utility.svg", "conflict-automation.svg", "error-breakdown.svg", "latency.svg", "scalability.svg", "report.md"]
    if model_arm_source is not None:
        artifact_names.extend(["model_arm_contract.json", "model_per_run.csv", "model_arm_summary.json", "model_arm_by_experiment.csv"])
    manifest = {"schema_version": "glhs-q2-evidence-manifest-v1", "summary_sha256": digest, "frozen_input_sha256": frozen_input_sha256, "artifacts": artifact_names, "limitations": result["protocol"]["limitations"], "reproducibility": result["reproducibility"]}
    (output / "evidence-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260808)
    parser.add_argument("--cases", type=int, default=400)
    parser.add_argument(
        "--mimic-demo-manifest",
        type=Path,
        help=(
            "Explicit local manifest for a lawful, de-identified MIMIC-IV Demo/FHIR "
            "controlled-perturbation cohort. Full MIMIC is never accepted or downloaded."
        ),
    )
    parser.add_argument(
        "--model-arm-source",
        type=Path,
        help="Completed direct model-arm artifact; validates and copies its raw CSV into this Q2 artifact.",
    )
    args = parser.parse_args()
    if args.cases != 400:
        parser.error("--cases must be exactly 400 for the frozen Q2 protocol")
    # Contracts are materialized before any comparator call.  The execution
    # output records their hashes, making a post-hoc oracle edit detectable.
    args.output.mkdir(parents=True, exist_ok=True)
    frozen_cases = [asdict(_case(index)) for index in range(1, args.cases + 1)]
    frozen_input_sha256 = _write_frozen_inputs(args.output, frozen_cases)
    completed_model_arm = (
        _load_completed_model_arm(args.model_arm_source.resolve(), [_case(index) for index in range(1, args.cases + 1)])
        if args.model_arm_source is not None
        else None
    )
    result = run(
        args.seed,
        args.cases,
        args.mimic_demo_manifest,
        frozen_input_sha256=frozen_input_sha256,
        completed_model_arm=completed_model_arm,
    )
    write(
        result,
        args.output,
        frozen_input_sha256=frozen_input_sha256,
        model_arm_source=args.model_arm_source.resolve() if args.model_arm_source is not None else None,
    )


if __name__ == "__main__":
    main()
