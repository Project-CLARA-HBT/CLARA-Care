"""Paired per-family/aggregate analysis for the GLHS exact-binding ablation.

Primary endpoint (GLHS-A06): paired invalid-commit acceptance on the 256
adversarial schedules.  Reports per arm numerator/denominator, paired absolute
risk difference (arm A minus arm B) with a 95% paired bootstrap CI on a
deterministic seed, discordant counts, and the exact two-sided McNemar test.
Per-family results are reported identically over each family's 32 schedules.
Controls report valid-commit acceptance per arm plus the rejection-reason
distribution.  No adaptive sample-size increase after result inspection
(GLHS-A06): N is fixed at freeze time.

The analysis never fabricates results: it reads the append-only observer
stream, re-verifies its hash chain, and audits arm-B outcomes against the
frozen expected admissibility (claim eligibility).  The measured ablation
quantity is arm-A invalid-commit acceptance; arm-B is the production
composition control.
"""

from __future__ import annotations

import json
import math
import random
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation.glhs_binding_only_ablation.adapter import (
    FULL_GOVERNANCE_NO_EXACT_BINDING,
    GLHS_EXACT_BINDING,
)
from evaluation.glhs_binding_only_ablation.observer import read_records
from evaluation.glhs_binding_only_ablation.validate import (
    validate_arm_diff,
    validate_execution_against_expected,
)

ANALYSIS_SCHEMA_VERSION = "glhs-binding-ablation-analysis.v1"
BOOTSTRAP_ITERATIONS = 10_000


def _mcnemar_exact_two_sided(a: int, b: int) -> float:
    """Exact two-sided McNemar p-value over discordant cells a and b.

    With n = a + b discordant pairs, X ~ Binomial(n, 0.5): the two-sided p is
    twice the probability of the observed tail on the larger cell, capped at 1.
    """
    n = a + b
    if n == 0:
        return 1.0
    k = max(a, b)
    tail = sum(math.comb(n, i) for i in range(k, n + 1)) * 0.5**n
    return min(1.0, 2.0 * tail)


def _paired_bootstrap_ci(
    pairs: list[tuple[bool, bool]], *, seed: int, iterations: int = BOOTSTRAP_ITERATIONS
) -> dict[str, float]:
    """Paired bootstrap 95% CI for the absolute risk difference (arm A - arm B)."""
    rng = random.Random(seed)
    n = len(pairs)
    differences: list[float] = []
    for _ in range(iterations):
        sample = [pairs[rng.randrange(n)] for _ in range(n)]
        accepted_a = sum(1 for a, b in sample if a and not b)
        accepted_b = sum(1 for a, b in sample if not a and b)
        differences.append((accepted_a - accepted_b) / n)
    differences.sort()
    return {
        "lower": differences[int(0.025 * iterations)],
        "upper": differences[int(0.975 * iterations)],
        "iterations": iterations,
    }


def _block_statistics(pairs: list[tuple[bool, bool]], *, seed: int) -> dict[str, Any]:
    n = len(pairs)
    admitted_a = sum(1 for a, _ in pairs if a)
    admitted_b = sum(1 for _, b in pairs if b)
    a_cell = sum(1 for a, b in pairs if a and not b)
    b_cell = sum(1 for a, b in pairs if not a and b)
    rd = (a_cell - b_cell) / n
    ci = _paired_bootstrap_ci(pairs, seed=seed)
    return {
        "numerator_arm_a": admitted_a,
        "numerator_arm_b": admitted_b,
        "denominator": n,
        "invalid_commit_acceptance_arm_a": admitted_a / n,
        "invalid_commit_acceptance_arm_b": admitted_b / n,
        "risk_difference_arm_a_minus_arm_b": rd,
        "ci95_paired_bootstrap": [ci["lower"], ci["upper"]],
        "bootstrap_seed": seed,
        "bootstrap_iterations": ci["iterations"],
        "discordant_arm_a_admitted_arm_b_rejected": a_cell,
        "discordant_arm_a_rejected_arm_b_admitted": b_cell,
        "mcnemar_exact_two_sided_p": _mcnemar_exact_two_sided(a_cell, b_cell),
    }


def _paired_records(
    schedules: list[dict[str, Any]], records: list[dict[str, Any]]
) -> dict[str, dict[str, dict[str, Any]]]:
    paired: dict[str, dict[str, dict[str, Any]]] = {}
    by_id = {str(schedule["schedule_id"]): schedule for schedule in schedules}
    for record in records:
        schedule_id = str(record["schedule_id"])
        if schedule_id not in by_id:
            continue
        paired.setdefault(schedule_id, {})[str(record["arm"])] = record
    for schedule_id, arms in list(paired.items()):
        if set(arms) != {FULL_GOVERNANCE_NO_EXACT_BINDING, GLHS_EXACT_BINDING}:
            paired.pop(schedule_id)
    return paired


def analyze(
    schedules_document: dict[str, Any],
    records: list[dict[str, Any]],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    """Compute the frozen primary/control analysis from observed executions."""
    schedules = schedules_document["schedules"]
    paired = _paired_records(schedules, records)
    seed = int(protocol["primary_analysis"]["bootstrap_seed"])
    freeze_id = str(protocol["freeze_id"])
    run_ids = sorted({str(record["run_id"]) for record in records})
    expected_schedule_ids = {str(schedule["schedule_id"]) for schedule in schedules}
    gate_c = validate_arm_diff(records, expected_schedule_ids=expected_schedule_ids)
    if len(run_ids) != 1:
        raise ValueError("analysis_requires_one_run_id")
    if len(records) != len(schedules) * 2 or not gate_c["valid"]:
        raise ValueError("analysis_requires_complete_valid_arm_pairs")

    adversarial = [schedule for schedule in schedules if schedule["kind"] == "adversarial"]
    controls = [schedule for schedule in schedules if schedule["kind"] == "control"]

    adversarial_pairs: list[tuple[bool, bool]] = []
    family_blocks: dict[str, dict[str, Any]] = {}
    for family_id in sorted({int(schedule["family_id"]) for schedule in adversarial}):
        family_schedules = [s for s in adversarial if int(s["family_id"]) == family_id]
        family_pairs: list[tuple[bool, bool]] = []
        for schedule in family_schedules:
            arms = paired.get(str(schedule["schedule_id"]))
            if arms is None:
                continue
            admitted_a = bool(arms[FULL_GOVERNANCE_NO_EXACT_BINDING]["admitted"])
            admitted_b = bool(arms[GLHS_EXACT_BINDING]["admitted"])
            pair = (admitted_a, admitted_b)
            adversarial_pairs.append(pair)
            family_pairs.append(pair)
        family_blocks[str(family_id)] = _block_statistics(family_pairs, seed=seed)

    control_blocks: dict[str, Any] = {}
    for arm in (FULL_GOVERNANCE_NO_EXACT_BINDING, GLHS_EXACT_BINDING):
        accepted = 0
        for schedule in controls:
            arms = paired.get(str(schedule["schedule_id"]))
            if arms is not None and bool(arms[arm]["admitted"]):
                accepted += 1
        control_blocks[arm] = {
            "valid_commit_acceptance_numerator": accepted,
            "valid_commit_acceptance_denominator": len(controls),
            "valid_commit_acceptance": accepted / len(controls) if controls else None,
        }
    reason_distribution: dict[str, dict[str, int]] = {}
    for arm in (FULL_GOVERNANCE_NO_EXACT_BINDING, GLHS_EXACT_BINDING):
        reasons = Counter(
            str(record["rejection_reason_code"])
            for record in records
            if record["arm"] == arm and not record["admitted"]
        )
        reason_distribution[arm] = dict(sorted(reasons.items()))

    expected_audit = validate_execution_against_expected(records)
    return {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "freeze_id": freeze_id,
        "run_ids": run_ids,
        "execution_count": len(records),
        "adversarial_schedule_count": len(adversarial_pairs),
        "control_schedule_count": len(controls),
        "primary": _block_statistics(adversarial_pairs, seed=seed),
        "per_family": family_blocks,
        "controls": {
            "acceptance": control_blocks,
            "rejection_reason_distribution": reason_distribution,
        },
        "gate_c_arm_diff": gate_c,
        "expected_admissibility_audit": expected_audit,
        "claim_eligible": bool(
            len(adversarial_pairs) == 256 and gate_c["valid"] and expected_audit["valid"]
        ),
        "note": (
            "N fixed at freeze time (256 adversarial + 64 controls); no adaptive "
            "sample-size increase (GLHS-A06)."
        ),
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--schedules",
        type=Path,
        default=Path("evaluation/glhs_binding_only_ablation/schedules.json"),
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("evaluation/glhs_binding_only_ablation/protocol.json"),
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("research/glhs_journal/binding_only_ablation/results"),
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    schedules_document = json.loads(args.schedules.read_text(encoding="utf-8"))
    raw_dir = args.results_dir / "raw"
    records: list[dict[str, Any]] = []
    if raw_dir.is_dir():
        paths = sorted(raw_dir.glob("executions_*.jsonl"))
        if args.run_id is not None:
            paths = [raw_dir / f"executions_{args.run_id}.jsonl"]
        if len(paths) != 1:
            raise RuntimeError("analysis_requires_one_raw_stream_or_run_id")
        for path in paths:
            if not path.exists():
                raise RuntimeError(f"analysis_raw_stream_missing:{path}")
            records.extend(read_records(path))
    analysis = analyze(schedules_document, records, protocol)
    output = args.output or (args.results_dir / "analysis.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(analysis, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
