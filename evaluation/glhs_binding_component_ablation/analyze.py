"""Paired per-family/arm analysis and statistics for the 2^3 factorial component ablation (E01).

Endpoints:
1. Exact acceptance rate by arm x family with Wilson score 95% confidence intervals.
2. McNemar's exact two-sided test comparing B111 against each ablated arm (B000..B011).
3. 2^3 Factorial logistic regression estimating main effects (c_id, c_digest, c_evidence)
   and interaction terms (c_id x c_digest, etc.) on log-odds of invalid acceptance.
4. Claim eligibility audit verifying total schedule coverage and 100% clean control acceptance.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm

from evaluation.glhs_binding_component_ablation.binding_mask import ALL_ARMS, BindingMask

ANALYSIS_SCHEMA_VERSION = "glhs-binding-component-ablation-analysis.v1"


def _wilson_score_ci(k: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Compute 95% Wilson score confidence interval for a binomial proportion."""
    if n == 0:
        return (0.0, 0.0)
    z = float(norm.ppf(1.0 - (1.0 - confidence) / 2.0))
    p_hat = k / n
    denom = 1.0 + (z**2) / n
    center = (p_hat + (z**2) / (2.0 * n)) / denom
    margin = (z / denom) * math.sqrt(
        max(0.0, (p_hat * (1.0 - p_hat) / n) + (z**2) / (4.0 * (n**2)))
    )
    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return (lower, upper)


def _mcnemar_exact_two_sided(n10: int, n01: int) -> float:
    """Exact two-sided McNemar test p-value given discordant pair counts.

    n10: count where Arm A admitted & Arm B111 rejected
    n01: count where Arm A rejected & Arm B111 admitted
    """
    m = n10 + n01
    if m == 0:
        return 1.0
    k = max(n10, n01)
    tail = sum(math.comb(m, i) for i in range(k, m + 1)) * (0.5**m)
    return min(1.0, 2.0 * tail)


def _fit_factorial_logistic_regression(
    records: list[dict[str, Any]],
    adversarial_schedule_ids: set[str],
) -> dict[str, Any]:
    """Fit a 2^3 factorial logistic regression over adversarial executions.

    Log-odds of acceptance Y = 1:
    logit(P(Y=1)) = beta_0 + beta_1*c_id + beta_2*c_digest + beta_3*c_evidence
                    + beta_12*(c_id*c_digest) + beta_13*(c_id*c_evidence) + beta_23*(c_digest*c_evidence)
                    + beta_123*(c_id*c_digest*c_evidence)
    """
    adv_records = [r for r in records if str(r["schedule_id"]) in adversarial_schedule_ids]
    if not adv_records:
        return {"fitted": False, "reason": "no_adversarial_records"}

    feature_names = [
        "intercept",
        "c_id",
        "c_digest",
        "c_evidence",
        "c_id:c_digest",
        "c_id:c_evidence",
        "c_digest:c_evidence",
        "c_id:c_digest:c_evidence",
    ]

    rows = []
    y_vals = []
    for r in adv_records:
        arm = BindingMask.from_arm_name(str(r["arm"]))
        c1, c2, c3 = arm.vector
        row = [1, c1, c2, c3, c1 * c2, c1 * c3, c2 * c3, c1 * c2 * c3]
        rows.append(row)
        y_vals.append(1 if r["admitted"] else 0)

    X = np.array(rows, dtype=float)
    y = np.array(y_vals, dtype=float)
    n_samples, n_features = X.shape

    def loss(beta: np.ndarray) -> float:
        z = X @ beta
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        nll = -np.sum(y * np.log(p + 1e-12) + (1.0 - y) * np.log(1.0 - p + 1e-12))
        reg = 1e-5 * np.sum(beta[1:] ** 2)
        return nll + reg

    init_beta = np.zeros(n_features)
    res = minimize(loss, init_beta, method="L-BFGS-B")
    beta = res.x

    z_pred = X @ beta
    p_pred = 1.0 / (1.0 + np.exp(-np.clip(z_pred, -30, 30)))
    w = p_pred * (1.0 - p_pred) + 1e-6
    W = np.diag(w)
    Hessian = X.T @ W @ X + 1e-5 * np.eye(n_features)

    try:
        cov = np.linalg.inv(Hessian)
        se = np.sqrt(np.maximum(1e-12, np.diag(cov)))
    except np.linalg.LinAlgError:
        se = np.ones(n_features) * 999.0

    coefficients = {}
    for idx, name in enumerate(feature_names):
        b_val = float(beta[idx])
        se_val = float(se[idx])
        z_stat = b_val / se_val if se_val > 0 else 0.0
        p_val = float(2.0 * norm.sf(abs(z_stat)))
        or_val = float(np.exp(b_val))
        or_ci_low = float(np.exp(b_val - 1.96 * se_val))
        or_ci_high = float(np.exp(b_val + 1.96 * se_val))

        coefficients[name] = {
            "beta": b_val,
            "std_err": se_val,
            "z_statistic": z_stat,
            "p_value": p_val,
            "odds_ratio": or_val,
            "odds_ratio_ci95": [or_ci_low, or_ci_high],
        }

    return {
        "fitted": True,
        "n_samples": n_samples,
        "n_features": n_features,
        "converged": bool(res.success),
        "coefficients": coefficients,
    }


def analyze(
    schedules_document: dict[str, Any],
    records: list[dict[str, Any]],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    """Compute paired per-family, per-arm statistics and factorial regression."""
    schedules = schedules_document["schedules"]
    by_id = {str(s["schedule_id"]): s for s in schedules}
    adversarial_ids = {str(s["schedule_id"]) for s in schedules if s["kind"] == "adversarial"}
    control_ids = {str(s["schedule_id"]) for s in schedules if s["kind"] == "control"}

    records_by_schedule: dict[str, dict[str, dict[str, Any]]] = {}
    for record in records:
        sid = str(record["schedule_id"])
        arm = str(record["arm"])
        if sid in by_id:
            records_by_schedule.setdefault(sid, {})[arm] = record

    total_schedules = len(schedules)
    expected_executions = total_schedules * len(ALL_ARMS)
    actual_executions = len(records)

    # Clean positive controls analysis
    clean_acceptance_by_arm: dict[str, dict[str, Any]] = {}
    for arm in ALL_ARMS:
        k_clean = 0
        for sid in control_ids:
            rec = records_by_schedule.get(sid, {}).get(arm)
            if rec and rec.get("admitted"):
                k_clean += 1
        n_clean = len(control_ids)
        ci_low, ci_high = _wilson_score_ci(k_clean, n_clean)
        clean_acceptance_by_arm[arm] = {
            "accepted": k_clean,
            "total": n_clean,
            "acceptance_rate": k_clean / n_clean if n_clean > 0 else 0.0,
            "ci95_wilson": [ci_low, ci_high],
        }

    # Per-family and per-arm invalid acceptance analysis
    family_ids = sorted({s["family_id"] for s in schedules})
    per_family_stats: dict[str, Any] = {}

    for fid in family_ids:
        fam_schedules = [s for s in schedules if s["family_id"] == fid]
        fam_name = fam_schedules[0]["family_name"]
        fam_is_clean = fam_name == "CLEAN"
        fam_sids = [str(s["schedule_id"]) for s in fam_schedules]

        arm_stats: dict[str, Any] = {}
        for arm in ALL_ARMS:
            k_acc = 0
            for sid in fam_sids:
                rec = records_by_schedule.get(sid, {}).get(arm)
                if rec and rec.get("admitted"):
                    k_acc += 1
            n_fam = len(fam_sids)
            ci_low, ci_high = _wilson_score_ci(k_acc, n_fam)
            arm_stats[arm] = {
                "accepted": k_acc,
                "total": n_fam,
                "rate": k_acc / n_fam if n_fam > 0 else 0.0,
                "ci95_wilson": [ci_low, ci_high],
            }

        # Pairwise McNemar tests vs B111 for this family
        mcnemar_vs_b111: dict[str, Any] = {}
        for arm in ALL_ARMS:
            if arm == "B111":
                continue
            n10 = 0  # Arm admitted, B111 rejected
            n01 = 0  # Arm rejected, B111 admitted
            for sid in fam_sids:
                rec_arm = records_by_schedule.get(sid, {}).get(arm)
                rec_b111 = records_by_schedule.get(sid, {}).get("B111")
                if rec_arm and rec_b111:
                    adm_arm = bool(rec_arm.get("admitted"))
                    adm_b111 = bool(rec_b111.get("admitted"))
                    if adm_arm and not adm_b111:
                        n10 += 1
                    elif not adm_arm and adm_b111:
                        n01 += 1

            p_val = _mcnemar_exact_two_sided(n10, n01)
            mcnemar_vs_b111[arm] = {
                "n_arm_admit_b111_reject": n10,
                "n_arm_reject_b111_admit": n01,
                "mcnemar_p_value": p_val,
            }

        per_family_stats[str(fid)] = {
            "family_id": fid,
            "family_name": fam_name,
            "is_clean_control": fam_is_clean,
            "schedule_count": len(fam_sids),
            "arm_acceptance": arm_stats,
            "mcnemar_vs_b111": mcnemar_vs_b111,
        }

    # Aggregate McNemar tests across all 256 adversarial schedules
    aggregate_mcnemar: dict[str, Any] = {}
    for arm in ALL_ARMS:
        if arm == "B111":
            continue
        n10 = 0
        n01 = 0
        for sid in adversarial_ids:
            rec_arm = records_by_schedule.get(sid, {}).get(arm)
            rec_b111 = records_by_schedule.get(sid, {}).get("B111")
            if rec_arm and rec_b111:
                adm_arm = bool(rec_arm.get("admitted"))
                adm_b111 = bool(rec_b111.get("admitted"))
                if adm_arm and not adm_b111:
                    n10 += 1
                elif not adm_arm and adm_b111:
                    n01 += 1
        p_val = _mcnemar_exact_two_sided(n10, n01)
        aggregate_mcnemar[arm] = {
            "n_arm_admit_b111_reject": n10,
            "n_arm_reject_b111_admit": n01,
            "mcnemar_p_value": p_val,
        }

    # 2^3 Factorial Logistic Regression
    factorial_regression = _fit_factorial_logistic_regression(records, adversarial_ids)

    # Rejection reason code breakdown per arm
    reason_breakdown: dict[str, dict[str, int]] = {}
    for arm in ALL_ARMS:
        reasons = Counter(
            str(r.get("rejection_reason_code"))
            for r in records
            if str(r.get("arm")) == arm and not r.get("admitted")
        )
        reason_breakdown[arm] = dict(sorted(reasons.items()))

    # Verify claim eligibility
    all_schedules_covered = len(records_by_schedule) == total_schedules
    all_arms_covered = all(
        len(records_by_schedule.get(sid, {})) == len(ALL_ARMS) for sid in by_id
    )
    clean_controls_valid = all(
        v["acceptance_rate"] == 1.0 for v in clean_acceptance_by_arm.values()
    )
    claim_eligible = bool(
        all_schedules_covered and all_arms_covered and clean_controls_valid and actual_executions == expected_executions
    )

    return {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "freeze_id": protocol.get("freeze_id", "GLHS-E01-COMPONENT-ABLATION-FREEZE"),
        "total_schedules": total_schedules,
        "adversarial_schedules": len(adversarial_ids),
        "control_schedules": len(control_ids),
        "expected_executions": expected_executions,
        "actual_executions": actual_executions,
        "claim_eligible": claim_eligible,
        "clean_acceptance_by_arm": clean_acceptance_by_arm,
        "aggregate_mcnemar_vs_b111": aggregate_mcnemar,
        "factorial_logistic_regression": factorial_regression,
        "per_family_stats": per_family_stats,
        "rejection_reason_breakdown": reason_breakdown,
    }


def generate_summary_markdown(analysis: dict[str, Any]) -> str:
    """Generate human-readable summary Markdown for the sealed E01 experiment."""
    lines: list[str] = [
        f"# E01: Component-Wise Exact-Binding Ablation Summary Report",
        "",
        f"**Freeze ID:** `{analysis.get('freeze_id')}`  ",
        f"**Schema Version:** `{analysis.get('schema_version')}`  ",
        f"**Claim Eligible:** `{'YES' if analysis.get('claim_eligible') else 'NO'}`  ",
        f"**Total Logical Schedules:** `{analysis.get('total_schedules')}` (`{analysis.get('adversarial_schedules')}` adversarial + `{analysis.get('control_schedules')}` clean controls)  ",
        f"**Total Arm Executions:** `{analysis.get('actual_executions')}` / `{analysis.get('expected_executions')}`  ",
        "",
        "---",
        "",
        "## 1. Clean Controls Admissibility (100% Target)",
        "",
        "| Arm | Description | Accepted / Total | Acceptance Rate | 95% Wilson CI |",
        "|---|---|---:|---:|---:|",
    ]

    arm_descs = {
        "B000": "None (0,0,0)",
        "B100": "Snapshot Identity Only (1,0,0)",
        "B010": "Content Digest Only (0,1,0)",
        "B001": "Evidence Membership Only (0,0,1)",
        "B110": "Identity + Digest (1,1,0)",
        "B101": "Identity + Evidence (1,0,1)",
        "B011": "Digest + Evidence (0,1,1)",
        "B111": "Full Exact Binding (1,1,1)",
    }

    clean_data = analysis.get("clean_acceptance_by_arm", {})
    for arm in ALL_ARMS:
        c = clean_data.get(arm, {})
        ci = c.get("ci95_wilson", [0, 0])
        lines.append(
            f"| `{arm}` | {arm_descs.get(arm, arm)} | {c.get('accepted')}/{c.get('total')} | {c.get('acceptance_rate', 0.0):.1%} | [{ci[0]:.3f}, {ci[1]:.3f}] |"
        )

    lines.extend([
        "",
        "## 2. Invalid Acceptance Rate by Schedule Family × Arm",
        "",
        "| Family ID | Family Name | N | B000 | B100 | B010 | B001 | B110 | B101 | B011 | B111 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])

    fam_stats = analysis.get("per_family_stats", {})
    for fid in sorted(fam_stats.keys(), key=lambda x: int(x)):
        fam = fam_stats[fid]
        row = [
            f"`F{int(fid):02d}`",
            f"**{fam.get('family_name')}**",
            str(fam.get("schedule_count")),
        ]
        arm_acc = fam.get("arm_acceptance", {})
        for arm in ALL_ARMS:
            rate = arm_acc.get(arm, {}).get("rate", 0.0)
            row.append(f"{rate:.1%}")
        lines.append("| " + " | ".join(row) + " |")

    lines.extend([
        "",
        "## 3. Paired McNemar Discordance vs B111 (Full Exact Binding)",
        "",
        "| Arm | Discordant Pairs (Arm Admit / B111 Reject) | Discordant Pairs (Arm Reject / B111 Admit) | McNemar Exact p-value | Significant (p < 0.001) |",
        "|---|---:|---:|---:|---|",
    ])

    mcnemar = analysis.get("aggregate_mcnemar_vs_b111", {})
    for arm in ALL_ARMS:
        if arm == "B111":
            continue
        m = mcnemar.get(arm, {})
        n10 = m.get("n_arm_admit_b111_reject", 0)
        n01 = m.get("n_arm_reject_b111_admit", 0)
        p = m.get("mcnemar_p_value", 1.0)
        sig = "YES" if p < 0.001 else "NO"
        lines.append(f"| `{arm}` | {n10} | {n01} | {p:.2e} | **{sig}** |")

    lines.extend([
        "",
        "## 4. 2^3 Factorial Logistic Regression on Invalid Acceptance",
        "",
        "| Factor / Interaction | Coefficient (β) | Std Error | z-statistic | p-value | Odds Ratio | 95% CI (OR) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])

    reg = analysis.get("factorial_logistic_regression", {})
    if reg.get("fitted"):
        coeffs = reg.get("coefficients", {})
        for name, c in coeffs.items():
            ci_or = c.get("odds_ratio_ci95", [0, 0])
            lines.append(
                f"| `{name}` | {c.get('beta', 0.0):.4f} | {c.get('std_err', 0.0):.4f} | {c.get('z_statistic', 0.0):.2f} | {c.get('p_value', 1.0):.2e} | {c.get('odds_ratio', 1.0):.4f} | [{ci_or[0]:.3f}, {ci_or[1]:.3f}] |"
            )

    lines.extend(["", ""])
    return "\n".join(lines)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--schedules",
        type=Path,
        default=Path("evaluation/glhs_binding_component_ablation/schedules.json"),
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("evaluation/glhs_binding_component_ablation/protocol.json"),
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("research/glhs_journal/binding_component_ablation/results"),
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    schedules_doc = json.loads(args.schedules.read_text(encoding="utf-8"))
    protocol = json.loads(args.protocol.read_text(encoding="utf-8")) if args.protocol.exists() else {}

    raw_dir = args.results_dir / "raw"
    records: list[dict[str, Any]] = []
    if raw_dir.is_dir():
        for jsonl_file in sorted(raw_dir.glob("*.jsonl")):
            for line in jsonl_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    records.append(json.loads(line))

    analysis_result = analyze(schedules_doc, records, protocol)

    out_path = args.output or (args.results_dir / "analysis.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(analysis_result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(analysis_result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
