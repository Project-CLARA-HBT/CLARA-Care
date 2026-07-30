"""Evidence-first runner for the privacy-safe CLARA-Eval VN foundation.

This runner deliberately separates *validation evidence* from clinical model
benchmarking.  The checked-in fixtures establish that manifests are complete,
checksum-locked and free of PHI/secrets; they cannot measure clinical quality,
model cost, or usability.  Those unavailable measures are emitted explicitly
as ``not_measured`` with the exact command needed to collect them later.

The module is stdlib-only so it runs in a pull-request job before optional
model, DrugBank, ASR, or clinician-review dependencies are provisioned.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import subprocess
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from statistics import NormalDist
from typing import Any

from .config import SuiteConfig, SuiteConfigError, load_suite_config
from .datasets.manifest import (
    DatasetManifest,
    ManifestValidationError,
    validate_dataset_manifest,
)
from .tracks import TRACK_METADATA, EvalTrack

REPORT_SCHEMA_VERSION = "clara-eval-vn.report.v1"
RUNNER_VERSION = "2026-07-30.1"
DEFAULT_MANIFEST = Path("evaluation/clara_eval/datasets/manifest.json")
TASK_CONTRACT_MANIFEST = Path("services/ml/config/task_contracts/contracts.json")

# The judge view has a deliberately fixed, decision-relevant headline set.
# Values are populated only when an approved execution supplies them; the
# offline foundation report renders ``not measured`` with its evidence gap.
JUDGE_HEADLINE_METRICS: tuple[tuple[str, str], ...] = (
    ("emergency_recall", "Emergency recall trên tiếng Việt nhiễu"),
    ("medication_normalization_top1", "Medication normalization top-1"),
    ("critical_ddi_recall", "Severe DDI recall với full DrugBank"),
    ("unsupported_claim_rate", "Research unsupported claim rate"),
    ("clinician_edit_time_reduction", "Scribe clinician edit-time reduction"),
    ("large_llm_cost_reduction", "Large-LLM token/cost reduction nhờ router"),
)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_dump(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _git_revision(root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = completed.stdout.strip()
    return value or None


def _wilson_interval(
    successes: int, total: int, confidence: float = 0.95
) -> dict[str, Any]:
    """Return a Wilson interval only for an actually observed binary result."""

    if total <= 0 or successes < 0 or successes > total:
        raise ValueError("invalid_observed_binary_measurement")
    z = NormalDist().inv_cdf(1 - (1 - confidence) / 2)
    proportion = successes / total
    denominator = 1 + (z * z) / total
    center = (proportion + (z * z) / (2 * total)) / denominator
    half_width = (
        z
        * ((proportion * (1 - proportion) / total) + (z * z) / (4 * total * total))
        ** 0.5
        / denominator
    )
    return {
        "method": "wilson",
        "confidence_level": confidence,
        "sample_size": total,
        "lower": max(0.0, center - half_width),
        "upper": min(1.0, center + half_width),
    }


def _not_measured(metric_id: str, reason: str, command: str) -> dict[str, Any]:
    return {
        "metric_id": metric_id,
        "state": "not_measured",
        "value": None,
        "confidence_interval": None,
        "reason": reason,
        "measurement_command": command,
    }


def _required_live_command(config: SuiteConfig) -> str:
    if config.suite == "release":
        return "make eval-release"
    return "make eval-nightly"


def _track_metrics(
    config: SuiteConfig, manifest: DatasetManifest
) -> list[dict[str, Any]]:
    """Project manifest declarations into report rows without inventing values."""

    entries = {entry.track_id: entry for entry in manifest.datasets}
    rows: list[dict[str, Any]] = []
    for configured_track in sorted(config.tracks, key=lambda item: item.track_id):
        track = configured_track.track_id
        entry = entries[track]
        declared_by_id = {
            declared.metric_id: declared for declared in entry.measurements
        }
        for metric_id in configured_track.required_metrics:
            declared = declared_by_id.get(metric_id)
            # Foundation fixtures intentionally declare all product quality
            # measures unavailable.  A runner must never turn that into 0/100.
            rows.append(
                _not_measured(
                    metric_id,
                    (
                        declared.reason
                        if declared is not None and declared.reason
                        else "No approved dataset, execution trace, or reviewer evidence is installed for this required metric."
                    ),
                    (
                        declared.command
                        if declared is not None and declared.command
                        else _required_live_command(config)
                    ),
                )
                | {
                    "track_id": track,
                    "track_label_vi": TRACK_METADATA[EvalTrack(track)]["label_vi"],
                    "dataset_id": entry.dataset_id,
                }
            )
    return rows


def _integrity_metric(manifest: DatasetManifest) -> dict[str, Any]:
    total = len(manifest.datasets)
    return {
        "metric_id": "dataset_manifest_integrity_pass_rate",
        "track_id": "evaluation_governance",
        "track_label_vi": "Quản trị đánh giá",
        "dataset_id": "all_checked_in_fixtures",
        "state": "measured",
        "value": 1.0,
        "unit": "proportion",
        "confidence_interval": _wilson_interval(total, total),
        "reason": "Đã kiểm tra checksum và số bản ghi của toàn bộ fixture được khai báo trong manifest.",
        "measurement_command": "python -m evaluation.clara_eval.datasets.validate --manifest evaluation/clara_eval/datasets/manifest.json --repository-root .",
    }


def _task_contract_snapshot(root: Path) -> dict[str, Any]:
    """Capture the checked-in model contract configuration without a model call.

    This is intentionally distinct from a runtime selection trace: it proves
    which reviewed contract/prompt versions were packaged with the evaluation
    revision, but never claims a provider used them or exposes credentials.
    """

    path = root / TASK_CONTRACT_MANIFEST
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return {
            "state": "unavailable",
            "reason": "Versioned ML task-contract manifest was not readable at this repository revision.",
            "path": str(TASK_CONTRACT_MANIFEST),
        }
    if not isinstance(value, dict) or not isinstance(value.get("schema_version"), str):
        return {
            "state": "invalid",
            "reason": "Versioned ML task-contract manifest did not match the expected top-level shape.",
            "path": str(TASK_CONTRACT_MANIFEST),
        }
    contracts = value.get("contracts")
    if not isinstance(contracts, dict):
        return {
            "state": "invalid",
            "reason": "Versioned ML task-contract manifest has no contract object.",
            "path": str(TASK_CONTRACT_MANIFEST),
        }
    rows: list[dict[str, Any]] = []
    for task, contract in sorted(contracts.items()):
        if not isinstance(task, str) or not isinstance(contract, dict):
            return {
                "state": "invalid",
                "reason": "Versioned ML task-contract manifest contains an invalid task entry.",
                "path": str(TASK_CONTRACT_MANIFEST),
            }
        prompt_version = contract.get("prompt_version")
        if not isinstance(prompt_version, str) or not prompt_version.strip():
            return {
                "state": "invalid",
                "reason": "Versioned ML task-contract manifest contains a task without a prompt version.",
                "path": str(TASK_CONTRACT_MANIFEST),
            }
        rows.append(
            {
                "task": task,
                "prompt_version": prompt_version,
                "risk_level": contract.get("risk_level"),
                "allowed_model_tiers": contract.get("allowed_model_tiers"),
                "output_contract": contract.get("output_contract"),
                "shadow_only": contract.get("shadow_only"),
            }
        )
    return {
        "state": "configured_not_executed",
        "path": str(TASK_CONTRACT_MANIFEST),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "schema_version": value["schema_version"],
        "contracts": rows,
        "reason": "Checked-in task contracts were captured; no provider invocation or runtime selection trace was executed.",
    }


def _model_manifest(root: Path, config: SuiteConfig, run_at: str) -> dict[str, Any]:
    """Describe observed configuration shape; never expose secret values."""

    environment_names = [
        "LLM_DEEPSEEK_ONLY",
        "CLARA_EVAL_API_BASE_URL",
        "CLARA_EVAL_ML_BASE_URL",
        "CLARA_EVAL_LOCKED_DATASET_REF",
        "CLARA_EVAL_RELEASE_REF",
    ]
    task_contracts = _task_contract_snapshot(root)
    configured = task_contracts["state"] == "configured_not_executed"
    return {
        "schema_version": "clara-eval-vn.model-manifest.v1",
        "generated_at": run_at,
        "repository_revision": _git_revision(root),
        "suite": config.suite,
        "runtime_environment_variables_present": {
            name: bool(os.environ.get(name)) for name in environment_names
        },
        "model_registry": {
            "state": "configured_not_executed" if configured else task_contracts["state"],
            "reason": (
                "Versioned task contracts were captured, but no runtime model-resolution event was executed."
                if configured
                else task_contracts["reason"]
            ),
            "measurement_command": _required_live_command(config),
        },
        "prompt_version": {
            "state": "configured_not_executed" if configured else task_contracts["state"],
            "reason": (
                "Prompt versions were read from versioned task contracts; no live prompt invocation was captured."
                if configured
                else task_contracts["reason"]
            ),
            "measurement_command": _required_live_command(config),
        },
        "task_contract_snapshot": task_contracts,
        "rollback": {
            "state": "documented",
            "method": "Select the prior registry/prompt configuration and disable the affected feature flag before redeploying.",
            "verification_command": "git log --oneline -- docs/architecture/adr && git diff -- .env.example",
        },
    }


def _retrieval_snapshot(config: SuiteConfig) -> dict[str, Any]:
    return {
        "schema_version": "clara-eval-vn.retrieval-snapshot.v1",
        "state": "not_measured",
        "reason": "The offline fixture suite does not call a RAG index and no immutable retrieval snapshot was supplied.",
        "measurement_command": _required_live_command(config),
        "suite": config.suite,
        "records": [],
    }


def _critical_error_rows(config: SuiteConfig) -> list[dict[str, str]]:
    command = _required_live_command(config)
    categories = (
        ("medical_qa_patient_communication", "unsafe_patient_guidance"),
        ("research_rag", "unsupported_or_misleading_claim"),
        ("careguard_drugbank", "missed_severe_ddi"),
        ("scribe_asr", "unsafe_clinical_transcription"),
        ("lifemap_invariants", "truth_state_or_provenance_violation"),
        ("council_ablation", "missed_red_flag"),
    )
    return [
        {
            "track_id": track,
            "critical_error_type": category,
            "state": "not_measured",
            "count": "",
            "reason": "No clinician-adjudicated or live execution evidence is installed; blank count is not a claim of zero errors.",
            "measurement_command": command,
        }
        for track, category in categories
    ]


def _ablation_rows(config: SuiteConfig) -> list[dict[str, str]]:
    command = _required_live_command(config)
    variants = (
        ("C0", "baseline policy and emergency hard guard"),
        ("C1", "C0 plus structured intake"),
        ("C2", "C1 plus specialist agents/tools"),
        ("C3", "C2 plus independent verifier"),
        ("C4", "C3 plus adjudicator and clinician review gate"),
    )
    return [
        {
            "variant": variant,
            "description": description,
            "metric_id": "red_flag_recall",
            "state": "not_measured",
            "value": "",
            "reason": "No clinician-adjudicated Council ablation corpus or execution trace is installed.",
            "measurement_command": command,
        }
        for variant, description in variants
    ]


def _write_csv(path: Path, rows: Iterable[dict[str, str]]) -> None:
    materialized = list(rows)
    if not materialized:
        raise ValueError("report_csv_requires_schema_row")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(materialized[0]))
        writer.writeheader()
        writer.writerows(materialized)


def _write_summary(path: Path, report: dict[str, Any]) -> None:
    metrics = report["metrics"]
    measured = sum(metric["state"] == "measured" for metric in metrics)
    unavailable = len(metrics) - measured
    lines = [
        "# CLARA-Eval VN — Judge Report",
        "",
        f"- Suite: `{report['suite']}`",
        f"- Generated at: `{report['generated_at']}`",
        f"- Dataset manifest integrity: **measured** ({report['integrity']['value']:.0%})",
        f"- Product-quality metrics: {measured - 1 if measured else 0} measured; {unavailable} not measured.",
        "- This report does not infer clinical quality from synthetic fixtures.",
        "",
        "## Required next measurement",
        "",
        "Run the appropriate credentialed/live suite after supplying the approved dataset, immutable retrieval snapshot, and model-routing telemetry:",
        "",
        f"```bash\n{report['next_measurement_command']}\n```",
        "",
        "## Sáu chỉ số chính cho BGK",
        "",
        "| Chỉ số | Trạng thái | Lý do | Lệnh đo |",
        "| --- | --- | --- | --- |",
    ]
    for metric in report["judge_headlines"]:
        lines.append(
            "| "
            f"{metric['label_vi']} | {metric['state']} | {metric['reason']} | "
            f"`{metric['measurement_command']}` |"
        )
    lines.extend(
        [
            "",
            "## Track status",
            "",
            "| Track | Status | Reason |",
            "| --- | --- | --- |",
        ]
    )
    for track in report["tracks"]:
        lines.append(f"| {track['label_vi']} | not measured | {track['reason']} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_html(path: Path, report: dict[str, Any]) -> None:
    headline_cards = "\n".join(
        '<article class="headline">'
        f"<h3>{html.escape(metric['label_vi'])}</h3>"
        f'<p class="status">{html.escape(metric["state"])}</p>'
        f"<p>{html.escape(metric['reason'])}</p>"
        f"<code>{html.escape(metric['measurement_command'])}</code>"
        "</article>"
        for metric in report["judge_headlines"]
    )
    table_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(track['label_vi'])}</td>"
        '<td><span class="status">not measured</span></td>'
        f"<td>{html.escape(track['reason'])}</td>"
        f"<td><code>{html.escape(track['measurement_command'])}</code></td>"
        "</tr>"
        for track in report["tracks"]
    )
    body = f"""<!doctype html>
<html lang=\"vi\">
<head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>CLARA-Eval VN Judge Report</title>
<style>body{{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#172033}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #d7deea;padding:.7rem;text-align:left;vertical-align:top}}th{{background:#eff5ff}}.headlines{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:1rem}}.headline{{border:1px solid #d7deea;border-radius:.5rem;padding:1rem}}.headline h3{{margin-top:0}}.status{{display:inline-block;background:#fff3cd;padding:.2rem .4rem;border-radius:.25rem}}code{{white-space:normal}}</style>
</head><body>
<h1>CLARA-Eval VN — Judge Report</h1>
<p>Suite <code>{html.escape(report["suite"])}</code> · generated {html.escape(report["generated_at"])}</p>
<p>Dataset manifest integrity was verified. Clinical/model quality is not inferred from the checked-in synthetic fixtures.</p>
<h2>Sáu chỉ số chính cho BGK</h2><section class="headlines">{headline_cards}</section>
<h2>Track status</h2><table><thead><tr><th>Track</th><th>Status</th><th>Why</th><th>How to measure</th></tr></thead><tbody>{table_rows}</tbody></table>
<h2>Artifacts</h2><p>Machine-readable metrics, dataset/model manifests, critical-error and ablation tables are adjacent to this file.</p>
</body></html>"""
    path.write_text(body, encoding="utf-8")


def _latency_cost_artifact(
    config: SuiteConfig, metric_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    routing_rows = [
        metric
        for metric in metric_rows
        if metric.get("track_id") == EvalTrack.MODEL_ROUTING_LATENCY_COST.value
    ]
    return {
        "schema_version": "clara-eval-vn.latency-cost.v1",
        "suite": config.suite,
        "state": "not_measured",
        "reason": "No approved model-routing telemetry snapshot or provider usage ledger was executed by this offline runner.",
        "measurement_command": _required_live_command(config),
        "metrics": routing_rows,
    }


def _summary_json(report: dict[str, Any]) -> dict[str, Any]:
    metrics = report["metrics"]
    return {
        "schema_version": "clara-eval-vn.summary.v1",
        "suite": report["suite"],
        "generated_at": report["generated_at"],
        "status": "evidence_only_not_a_clinical_benchmark",
        "measured_metric_count": sum(
            metric["state"] == "measured" for metric in metrics
        ),
        "not_measured_metric_count": sum(
            metric["state"] == "not_measured" for metric in metrics
        ),
        "integrity": report["integrity"],
        "judge_headlines": report["judge_headlines"],
        "next_measurement_command": report["next_measurement_command"],
    }


def build_report(
    *, config_path: Path, output: Path | None, repository_root: Path
) -> tuple[dict[str, Any], Path]:
    config = load_suite_config(config_path)
    manifest_path = repository_root / config.dataset_manifest
    manifest = validate_dataset_manifest(manifest_path, repository_root=repository_root)
    target = output or repository_root / config.output_dir
    if target.is_absolute() and output is None:
        raise ValueError("configured_output_must_be_relative")
    target.mkdir(parents=True, exist_ok=True)
    (target / "examples").mkdir(exist_ok=True)

    generated_at = _utc_now()
    metric_rows = [_integrity_metric(manifest), *_track_metrics(config, manifest)]
    tracks = [
        {
            "track_id": track.value,
            "label_vi": TRACK_METADATA[track]["label_vi"],
            "scope": TRACK_METADATA[track]["scope"],
            "state": "not_measured",
            "reason": next(
                metric["reason"]
                for metric in metric_rows
                if metric.get("track_id") == track.value
            ),
            "measurement_command": next(
                metric["measurement_command"]
                for metric in metric_rows
                if metric.get("track_id") == track.value
            ),
        }
        for track in EvalTrack
        if track.value in config.enabled_tracks
    ]
    metrics_by_id = {str(metric["metric_id"]): metric for metric in metric_rows}
    judge_headlines = [
        {
            "metric_id": metric_id,
            "label_vi": label_vi,
            "state": metrics_by_id[metric_id]["state"],
            "value": metrics_by_id[metric_id]["value"],
            "reason": metrics_by_id[metric_id]["reason"],
            "measurement_command": metrics_by_id[metric_id]["measurement_command"],
        }
        for metric_id, label_vi in JUDGE_HEADLINE_METRICS
    ]
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "runner_version": RUNNER_VERSION,
        "generated_at": generated_at,
        "suite": config.suite,
        "release_locked": config.release_locked,
        "integrity": metric_rows[0],
        "metrics": metric_rows,
        "tracks": tracks,
        "judge_headlines": judge_headlines,
        "live_dependencies_requested": config.requires_live_dependencies,
        "live_dependencies_executed": False,
        "next_measurement_command": _required_live_command(config),
    }
    _json_dump(target / "summary.json", _summary_json(report))
    _json_dump(target / "metrics.json", report)
    _json_dump(target / "dataset-manifest.json", manifest.as_dict())
    _json_dump(
        target / "model-manifest.json",
        _model_manifest(repository_root, config, generated_at),
    )
    _json_dump(target / "retrieval-snapshot.json", _retrieval_snapshot(config))
    _json_dump(
        target / "latency-cost.json",
        _latency_cost_artifact(config, metric_rows),
    )
    _json_dump(
        target / "confidence-intervals.json",
        {
            "schema_version": "clara-eval-vn.confidence-intervals.v1",
            "measured": [metric_rows[0]],
            "not_measured": [metric for metric in metric_rows[1:]],
        },
    )
    _write_csv(target / "critical-errors.csv", _critical_error_rows(config))
    _write_csv(target / "ablations.csv", _ablation_rows(config))
    _write_summary(target / "summary.md", report)
    _write_html(target / "index.html", report)
    _json_dump(
        target / "examples" / "README.json",
        {
            "state": "not_measured",
            "reason": "No approved live model outputs may be copied into a judge artifact from synthetic fixtures.",
            "measurement_command": _required_live_command(config),
        },
    )
    missing_required = [
        artifact
        for artifact in config.required_artifacts
        if not (target / artifact).exists()
    ]
    if missing_required:
        raise ValueError(
            f"required_report_artifacts_missing:{','.join(missing_required)}"
        )
    return report, target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run CLARA-Eval VN evidence-first suite"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    root = args.repository_root.resolve()
    try:
        report, target = build_report(
            config_path=args.config,
            output=args.output,
            repository_root=root,
        )
    except (ManifestValidationError, SuiteConfigError, OSError, ValueError) as exc:
        print(
            json.dumps({"ok": False, "reason": str(exc)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {"ok": True, "suite": report["suite"], "output": str(target)},
            ensure_ascii=False,
        )
    )
    if report["release_locked"] and not report["live_dependencies_executed"]:
        print(
            "release_locked_suite_blocked: no approved live, immutable evaluation evidence was executed; artifacts record not_measured.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(main())
