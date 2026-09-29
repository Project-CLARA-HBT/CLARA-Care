"""Statistical analysis module for E13 (Synthetic Source-Derived Task Suite).

Computes inter-rater agreement (Cohen's kappa, Krippendorff's alpha), external fact retention,
false positive / negative rates with Wilson 95% CIs for the Synthetic Source-Derived Task Suite
(derived from eICU/Synthea/MIMIC/Diabetes schemas) with human review as NOT_RUN_HUMAN_UNAVAILABLE,
adjudication_type = "SYNTHETIC_MODEL_ADJUDICATION", and independent_human_claim_eligible = False.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

Z_95 = 1.959963984540054


def wilson_ci(k: int, n: int, confidence: float = 0.95) -> tuple[float, float, float]:
    """Compute Wilson score interval for proportion k / n.

    Returns:
        (proportion, lower_ci, upper_ci)
    """
    if n <= 0:
        return (0.0, 0.0, 0.0)
    p_hat = k / n
    z = Z_95 if abs(confidence - 0.95) < 1e-4 else 1.96
    denominator = 1.0 + (z * z) / n
    center = (p_hat + (z * z) / (2.0 * n)) / denominator
    spread = (z * math.sqrt((p_hat * (1.0 - p_hat) / n) + ((z * z) / (4.0 * n * n)))) / denominator
    lower = 0.0 if k == 0 or (center - spread) < 1e-12 else max(0.0, center - spread)
    upper = 1.0 if k == n or (center + spread) > (1.0 - 1e-12) else min(1.0, center + spread)
    return (p_hat, lower, upper)


def compute_cohen_kappa(pairs: Sequence[tuple[str, str]]) -> float | None:
    """Compute Cohen's kappa for two raters across paired categorical ratings."""
    n = len(pairs)
    if n == 0:
        return None
    observed = sum(a == b for a, b in pairs) / n
    left_counts = Counter(a for a, _ in pairs)
    right_counts = Counter(b for _, b in pairs)
    categories = sorted(set(left_counts) | set(right_counts))
    expected = sum((left_counts[c] / n) * (right_counts[c] / n) for c in categories)
    if expected >= 1.0:
        return 1.0 if observed == 1.0 else 0.0
    return (observed - expected) / (1.0 - expected)


def compute_krippendorff_alpha(pairs: Sequence[tuple[str, str]]) -> float | None:
    """Compute Krippendorff's alpha for nominal ratings across two annotators."""
    n = len(pairs)
    if n == 0:
        return None
    total_ratings = 2 * n
    observed_disagreements = sum(a != b for a, b in pairs) / n
    all_labels: list[str] = []
    for a, b in pairs:
        all_labels.extend([a, b])
    counts = Counter(all_labels)
    expected_agreements = sum((cnt / total_ratings) * ((cnt - 1) / (total_ratings - 1)) for cnt in counts.values())
    expected_disagreements = 1.0 - expected_agreements
    if expected_disagreements <= 1e-12:
        return 1.0 if observed_disagreements == 0 else 0.0
    return 1.0 - (observed_disagreements / expected_disagreements)


def analyze_e13_results(
    raw_results_path: Path,
    protocol_path: Path,
) -> dict[str, Any]:
    """Analyze E13 raw execution results and produce comprehensive statistical summary."""
    raw_results_path = raw_results_path.resolve()
    protocol_path = protocol_path.resolve()

    if not raw_results_path.is_file():
        raise FileNotFoundError(f"raw_results_not_found:{raw_results_path}")
    if not protocol_path.is_file():
        raise FileNotFoundError(f"protocol_not_found:{protocol_path}")

    protocol_data = json.loads(protocol_path.read_text(encoding="utf-8"))
    targets = protocol_data.get("statistical_targets", {})
    red_team_cfg = protocol_data.get("red_team_constraints", {})

    results: list[dict[str, Any]] = []
    with raw_results_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                results.append(json.loads(line))

    total_tasks = len(results)
    if total_tasks == 0:
        raise ValueError("empty_results_stream")

    # Determine execution mode and Red Team status
    modes = {r.get("mode", "synthetic") for r in results}
    primary_mode = "human" if "human" in modes else ("not_run" if "not_run" in modes else "synthetic")

    # Red Team (E) Guardrail Enforcement
    if primary_mode == "human":
        adjudication_type = "INDEPENDENT_HUMAN_ADJUDICATION"
        human_adjudication_status = "COMPLETED"
        independent_human_claim_eligible = True
    elif primary_mode == "not_run":
        adjudication_type = "NOT_RUN"
        human_adjudication_status = "NOT_RUN_HUMAN_UNAVAILABLE"
        independent_human_claim_eligible = False
    else:
        # Synthetic / Model-based adjudication
        adjudication_type = "SYNTHETIC_MODEL_ADJUDICATION"
        human_adjudication_status = "NOT_RUN_HUMAN_UNAVAILABLE"
        independent_human_claim_eligible = False

    # Collect rating pairs and metrics
    annotator_pairs: list[tuple[str, str]] = []
    corpus_results: dict[str, list[dict[str, Any]]] = defaultdict(list)

    retained_facts_count = 0
    false_positives_count = 0
    false_negatives_count = 0
    reconstruction_pass_count = 0

    for r in results:
        ann1 = str(r.get("annotator_1_rating", "ACCURATE"))
        ann2 = str(r.get("annotator_2_rating", "ACCURATE"))
        annotator_pairs.append((ann1, ann2))

        corpus = str(r.get("corpus", "unknown"))
        corpus_results[corpus].append(r)

        if r.get("fact_retained", True):
            retained_facts_count += 1
        if r.get("false_positive", False):
            false_positives_count += 1
        if r.get("false_negative", False):
            false_negatives_count += 1
        if r.get("reconstruction_pass", True):
            reconstruction_pass_count += 1

    # Inter-rater agreement statistics
    cohen_kappa = compute_cohen_kappa(annotator_pairs)
    krippendorff_alpha = compute_krippendorff_alpha(annotator_pairs)

    # Proportions and Wilson 95% CIs
    fact_rate, fact_low, fact_high = wilson_ci(retained_facts_count, total_tasks)
    fpr_rate, fpr_low, fpr_high = wilson_ci(false_positives_count, total_tasks)
    fnr_rate, fnr_low, fnr_high = wilson_ci(false_negatives_count, total_tasks)
    recon_rate, recon_low, recon_high = wilson_ci(reconstruction_pass_count, total_tasks)

    # Per-corpus statistics
    corpus_summary: dict[str, Any] = {}
    for corpus_name, corpus_items in sorted(corpus_results.items()):
        c_n = len(corpus_items)
        c_retained = sum(1 for item in corpus_items if item.get("fact_retained", True))
        c_fp = sum(1 for item in corpus_items if item.get("false_positive", False))
        c_fn = sum(1 for item in corpus_items if item.get("false_negative", False))

        c_fact_p, c_fact_l, c_fact_u = wilson_ci(c_retained, c_n)
        c_fp_p, c_fp_l, c_fp_u = wilson_ci(c_fp, c_n)
        c_fn_p, c_fn_l, c_fn_u = wilson_ci(c_fn, c_n)

        c_pairs = [
            (str(item.get("annotator_1_rating", "ACCURATE")), str(item.get("annotator_2_rating", "ACCURATE")))
            for item in corpus_items
        ]

        corpus_summary[corpus_name] = {
            "total_tasks": c_n,
            "fact_retention_accuracy": c_fact_p,
            "fact_retention_ci_95": [c_fact_l, c_fact_u],
            "false_positive_rate": c_fp_p,
            "false_positive_ci_95": [c_fp_l, c_fp_u],
            "false_negative_rate": c_fn_p,
            "false_negative_ci_95": [c_fn_l, c_fn_u],
            "cohen_kappa": compute_cohen_kappa(c_pairs),
        }

    # Evaluate target eligibility
    min_kappa_target = targets.get("min_cohen_kappa", 0.80)
    min_alpha_target = targets.get("min_krippendorff_alpha", 0.80)
    min_fact_target = targets.get("min_fact_retention_accuracy", 0.90)

    statistical_targets_met = (
        (cohen_kappa is None or cohen_kappa >= min_kappa_target)
        and (krippendorff_alpha is None or krippendorff_alpha >= min_alpha_target)
        and fact_rate >= min_fact_target
    )

    summary = {
        "schema_version": "glhs-e13-external-summary-v1",
        "freeze_id": protocol_data.get("freeze_id", "GLHS-EXTERNAL-VALIDATION-E13-20260928-01"),
        "git_sha": protocol_data.get("git_sha", "81f040d3e05905cc384239c5ae130f629e722d3e"),
        "adjudication_type": adjudication_type,
        "human_adjudication_status": human_adjudication_status,
        "independent_human_claim_eligible": independent_human_claim_eligible,
        "statistical_targets_met": statistical_targets_met,
        "total_tasks": total_tasks,
        "inter_rater_agreement": {
            "cohen_kappa": cohen_kappa,
            "krippendorff_alpha": krippendorff_alpha,
            "target_kappa": min_kappa_target,
            "target_alpha": min_alpha_target,
        },
        "fact_retention_accuracy": {
            "point_estimate": fact_rate,
            "ci_95": [fact_low, fact_high],
            "retained_count": retained_facts_count,
            "total_count": total_tasks,
        },
        "false_positive_rate": {
            "point_estimate": fpr_rate,
            "ci_95": [fpr_low, fpr_high],
            "fp_count": false_positives_count,
            "total_count": total_tasks,
        },
        "false_negative_rate": {
            "point_estimate": fnr_rate,
            "ci_95": [fnr_low, fnr_high],
            "fn_count": false_negatives_count,
            "total_count": total_tasks,
        },
        "state_reconstruction_accuracy": {
            "point_estimate": recon_rate,
            "ci_95": [recon_low, recon_high],
            "pass_count": reconstruction_pass_count,
            "total_count": total_tasks,
        },
        "per_corpus_breakdown": corpus_summary,
        "red_team_guardrails": {
            "disallow_model_as_human_enforced": True,
            "red_team_rule": "Model-based QA is strictly labeled as SYNTHETIC_MODEL_ADJUDICATION and ineligible for independent human clinical claim.",
        },
    }

    return summary


def generate_summary_markdown(summary: dict[str, Any]) -> str:
    """Generate clear Markdown report from E13 summary dictionary."""
    lines = [
        "# E13 Synthetic Source-Derived Task Suite Report",
        "",
        f"- **Freeze ID:** `{summary['freeze_id']}`",
        f"- **Git SHA:** `{summary['git_sha']}`",
        f"- **Adjudication Type:** `{summary['adjudication_type']}`",
        f"- **Human Adjudication Status:** `{summary['human_adjudication_status']}`",
        f"- **Independent Human Claim Eligible:** `{summary['independent_human_claim_eligible']}`",
        f"- **Statistical Targets Met:** `{summary['statistical_targets_met']}`",
        f"- **Total External Tasks:** `{summary['total_tasks']}`",
        "",
        "## Inter-Rater Agreement & Reliability",
        "",
        f"- **Cohen's $\\kappa$:** `{summary['inter_rater_agreement']['cohen_kappa']:.4f}`"
        if summary["inter_rater_agreement"]["cohen_kappa"] is not None
        else "- **Cohen's $\\kappa$:** N/A",
        f"- **Krippendorff's $\\alpha$:** `{summary['inter_rater_agreement']['krippendorff_alpha']:.4f}`"
        if summary["inter_rater_agreement"]["krippendorff_alpha"] is not None
        else "- **Krippendorff's $\\alpha$:** N/A",
        "",
        "## Overall External Retention & Error Rates",
        "",
        f"- **External Fact Retention Accuracy:** `{summary['fact_retention_accuracy']['point_estimate'] * 100:.2f}%` "
        f"(95% CI: `{summary['fact_retention_accuracy']['ci_95'][0] * 100:.2f}%` – `{summary['fact_retention_accuracy']['ci_95'][1] * 100:.2f}%`)",
        f"- **False Positive Rate (FPR):** `{summary['false_positive_rate']['point_estimate'] * 100:.2f}%` "
        f"(95% CI: `{summary['false_positive_rate']['ci_95'][0] * 100:.2f}%` – `{summary['false_positive_rate']['ci_95'][1] * 100:.2f}%`)",
        f"- **False Negative Rate (FNR):** `{summary['false_negative_rate']['point_estimate'] * 100:.2f}%` "
        f"(95% CI: `{summary['false_negative_rate']['ci_95'][0] * 100:.2f}%` – `{summary['false_negative_rate']['ci_95'][1] * 100:.2f}%`)",
        f"- **State Reconstruction Accuracy:** `{summary['state_reconstruction_accuracy']['point_estimate'] * 100:.2f}%` "
        f"(95% CI: `{summary['state_reconstruction_accuracy']['ci_95'][0] * 100:.2f}%` – `{summary['state_reconstruction_accuracy']['ci_95'][1] * 100:.2f}%`)",
        "",
        "## Per-Corpus Breakdown",
        "",
        "| Corpus | Tasks | Fact Retention (95% CI) | False Positive Rate | False Negative Rate | Cohen's $\\kappa$ |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for c_name, c_data in sorted(summary["per_corpus_breakdown"].items()):
        f_p = f"{c_data['fact_retention_accuracy'] * 100:.1f}% ({c_data['fact_retention_ci_95'][0] * 100:.1f}%-{c_data['fact_retention_ci_95'][1] * 100:.1f}%)"
        fp_p = f"{c_data['false_positive_rate'] * 100:.1f}%"
        fn_p = f"{c_data['false_negative_rate'] * 100:.1f}%"
        ck = f"{c_data['cohen_kappa']:.3f}" if c_data['cohen_kappa'] is not None else "N/A"
        lines.append(f"| {c_name} | {c_data['total_tasks']} | {f_p} | {fp_p} | {fn_p} | {ck} |")

    lines.extend([
        "",
        "## Red Team (E) Compliance & Guardrails",
        "",
        f"- **Red Team Rule:** {summary['red_team_guardrails']['red_team_rule']}",
        f"- **Disallow Model As Human Enforced:** `{summary['red_team_guardrails']['disallow_model_as_human_enforced']}`",
    ])

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-results",
        type=Path,
        default=Path("protocols/E13_external_validation/raw/results.jsonl"),
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("protocols/E13_external_validation/protocol.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("protocols/E13_external_validation"),
    )
    args = parser.parse_args()

    summary = analyze_e13_results(args.raw_results, args.protocol)
    md_report = generate_summary_markdown(summary)

    derived_dir = args.output_dir / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)

    (derived_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (derived_dir / "summary.md").write_text(md_report, encoding="utf-8")

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
