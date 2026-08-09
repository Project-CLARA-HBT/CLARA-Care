"""Generate a bounded report for the MIMIC Demo no-annotation run."""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("expected_json_object")
    return value


def generate(run_dir: Path) -> None:
    cohort = _json(run_dir / "fhir-source-derived/cohort_manifest.json")
    domain = _json(run_dir / "domain-source-derived/summary.json")
    clinical = _json(run_dir / "q3-mimic-clinical-run/summary.json")
    ed = _json(run_dir / "q3-mimic-ed-run/summary.json")
    time_text = (run_dir / "fhir-source-derived/preparation-time.txt").read_text(encoding="utf-8")
    elapsed = re.search(r"Elapsed .*: (.+)", time_text)
    rss = re.search(r"Maximum resident set size \(kbytes\): (\d+)", time_text)
    junit_root = ET.parse(run_dir / "assurance/junit.xml").getroot()
    suites = [junit_root] if junit_root.tag == "testsuite" else list(junit_root.findall("testsuite"))
    test_count = sum(int(suite.attrib.get("tests", "0")) for suite in suites)
    failures = sum(
        int(suite.attrib.get("failures", "0")) + int(suite.attrib.get("errors", "0"))
        for suite in suites
    )
    fullstack_manifest_path = run_dir / "fullstack-postgresql-vps/fullstack_manifest.json"
    fullstack_metrics_path = run_dir / "fullstack-postgresql-vps/fullstack_metrics.csv"
    fullstack = _json(fullstack_manifest_path) if fullstack_manifest_path.is_file() else None
    gov_transport_path = run_dir / "governance-vps-transport/transport.json"
    gov_transport = _json(gov_transport_path) if gov_transport_path.is_file() else None
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, text=True, capture_output=True
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"], check=True, text=True, capture_output=True
        ).stdout.strip()
    )
    status = {
        "schema_version": "mimic-demo-no-annotation-run-status-v1",
        "release_class": "sealed_nonheadline_not_claim_eligible",
        "headline_claims_permitted": False,
        "dataset_scope": [
            "MIMIC-IV Clinical Database Demo 2.2",
            "MIMIC-IV Clinical Database Demo on FHIR 2.1.0",
            "MIMIC-IV-ED Demo 2.2",
        ],
        "source_derived_cohort": {
            "evaluation_subjects": cohort["subject_count"],
            "development_subjects": cohort["development_subject_count"],
            "subject_disjoint": True,
            "independent_curator": cohort["independent_curator"],
            "tasks": cohort["task_count"],
            "events": cohort["event_count"],
            "domains": cohort["domain_coverage"],
            "ground_truth_kind": cohort["ground_truth_kind"],
        },
        "domain_evaluation": {
            "eligible_tasks": domain["eligible_tasks"],
            "excluded_temporal_ties": domain["excluded_temporal_ties"],
            "results": domain["domain_results"],
        },
        "q3_structural": {
            "clinical_demo_cases": clinical["mimic_demo"]["cases"],
            "ed_demo_cases": ed["mimic_demo"]["cases"],
            "final_score_released": False,
        },
        "assurance": {"tests": test_count, "failures_or_errors": failures},
        "archive_preparation": {
            "wall_clock": elapsed.group(1).strip() if elapsed else None,
            "peak_rss_kbytes": int(rss.group(1)) if rss else None,
        },
        "not_run": {
            "independent_adjudication": "skipped by user; no independent clinical oracle",
            "human_review": "no clinicians/reviewers supplied",
            "downstream_two_model_families": "no configured provider keys or model endpoints",
            "real_boundary_adversarial": (
                "transport observations only; operator/adjudicator labels not supplied"
                if gov_transport
                else "no deployed API/cache/retrieval environment"
            ),
            "postgresql_fullstack": (
                "completed on isolated VPS API container; HTTP transport not measured"
                if fullstack
                else "Docker/PostgreSQL unavailable in execution environment"
            ),
        },
        "source_revision": revision,
        "git_worktree_dirty": dirty,
        "limitations": [
            "Demo datasets only; not full MIMIC-IV.",
            "No qualified independent annotations or adjudication.",
            "Source-derived targets test timestamp/state mechanics, not clinical correctness.",
            "BTSA is mechanism-mapped and relation classification is not a faithful source implementation.",
            "Structural Q3 oracle remains developer-authored and cannot release a final score.",
        ],
    }
    if fullstack:
        status["postgresql_fullstack"] = {
            "status": fullstack["status"],
            "architecture_path": fullstack["architecture_path"],
            "api_boundary": fullstack["api_boundary"],
            "http_transport_measured": fullstack["http_transport_measured"],
            "hardware": fullstack["hardware"],
            "environment": fullstack["environment"],
            "history_depth": fullstack["history_depth"],
            "repetitions": fullstack["repetitions"],
            "metrics_artifact": str(fullstack_metrics_path.relative_to(run_dir)),
        }
    if gov_transport:
        status["governance_transport_observations"] = {
            "status": gov_transport["status"],
            "observations": len(gov_transport.get("observations", [])),
            "operator_label_required": True,
            "results_not_adjudicated": True,
            "artifact": str(gov_transport_path.relative_to(run_dir)),
        }
    (run_dir / "run-status.json").write_text(
        json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    environment = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "processor": platform.processor(),
        "source_revision": revision,
        "git_worktree_dirty": dirty,
    }
    (run_dir / "environment.json").write_text(
        json.dumps(environment, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# MIMIC Demo evidence-program run — no annotation",
        "",
        "Release class: sealed_nonheadline_not_claim_eligible.",
        "",
        "This run uses Demo datasets only and has no independent clinical annotations.",
        "It cannot support clinical safety, universal privacy, full-MIMIC generalisation, or superiority claims.",
        "",
        f"- Source-derived split: {cohort['development_subject_count']} development / {cohort['subject_count']} evaluation subjects; disjoint.",
        f"- Tasks: {cohort['task_count']} total; {domain['eligible_tasks']} eligible after excluding {domain['excluded_temporal_ties']} timestamp ties.",
        f"- Domains: {', '.join(sorted(cohort['domain_coverage']))}.",
        f"- Assurance: {test_count - failures}/{test_count} tests passed.",
        f"- FHIR preparation: {elapsed.group(1).strip() if elapsed else 'unknown'} wall-clock; {rss.group(1) if rss else 'unknown'} KB peak RSS.",
        "",
        "## Domain-stratified source-derived results",
        "",
        "| Domain | System | Correct | Total | Rate |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in domain["domain_results"]:
        lines.append(
            f"| {row['domain']} | {row['system']} | {row['correct']} | {row['total']} | {row['rate']:.4f} |"
        )
    lines += [
        "",
        "BTSA diagnosis results preserve unresolved concurrent branches because source records lack explicit supersede intent; this negative result is retained.",
        "",
        "## NOT RUN",
        "",
        "- Independent annotation/adjudication (explicitly skipped by user).",
        "- Human-review burden.",
        "- Two-model-family downstream utility.",
        "- Deployed API/cache/retrieval adversarial run.",
        "- PostgreSQL→GST→GLHS→THSS→API HTTP transport (the isolated in-process API service-layer benchmark is recorded separately).",
        "",
        f"Source revision: {revision}; dirty worktree: {str(dirty).lower()}.",
    ]
    if gov_transport:
        lines[lines.index("## NOT RUN") : lines.index("## NOT RUN")] = [
            "## VPS boundary transport observations",
            "",
            "Ten frozen governance attack requests were sent through the isolated API container. The harness stores status/latency/body hashes only; every observation remains `operator_label_required`, so no attack success or safety rate is claimed.",
            "",
            "See `governance-vps-transport/transport.json`.",
            "",
        ]
    if fullstack:
        lines[lines.index("## NOT RUN") : lines.index("## NOT RUN")] = [
            "## PostgreSQL full-stack service-layer benchmark",
            "",
            "The benchmark ran on the isolated VPS database `clara_evidence_20260809` inside the API container. It measured the API-owned gateway path with one worker, 50-event history, and 30 repetitions per operation. HTTP transport latency was intentionally not measured because no arbitrary public GST write endpoint exists.",
            "",
            "See `fullstack-postgresql-vps/fullstack_metrics.csv` and `fullstack-postgresql-vps/fullstack_manifest.json`.",
            "",
        ]
    (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    generate(args.run_dir)
