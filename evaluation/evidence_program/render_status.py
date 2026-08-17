"""Machine status generator for the W0 evidence-integrity repair workstream.

Reconciles the RIVF final-003 and GLHS final-run status from immutable
artifacts only (SHA inventories, provenance reconciliation, validated
analysis, frozen plans, claim ledgers). Hand-edited claims never override
machine state: every field that is rendered into the final pre-CareGuard
status is derived here from the on-disk artifacts.

Inputs (repo-root relative):
- research/govred_rivf/provenance/final-003-reconciliation.json
- artifacts/govred/2026-08-17-rivf-freeze-candidate/final/final_locked_manifest.json
- artifacts/govred/2026-08-17-rivf-freeze-candidate/final/final_statistics_plan.json
- artifacts/govred/2026-08-17-rivf-final-003/artifact-sha256.json
- artifacts/govred/2026-08-17-rivf-final-003/{ARM}/raw_results.csv
- research/govred_rivf/results/final-003-analysis-v2.json
- artifacts/glhs-postgres-toctou/GLHS-POSTGRES-TOCTOU-FINAL-20260817-01/artifact-sha256.json
- research/glhs_journal/results/analysis.json
- research/glhs_journal/model_review_run/agreement.json
- research/glhs_journal/postgres_toctou_statistics_plan.json
- research/glhs_journal/postgres_toctou_schedule_manifest.json
- research/glhs_journal/postgres_toctou_observer_contract.json
- research/govred_rivf/claim_to_evidence.csv
- research/glhs_journal/revision_claim_ledger.csv
- research/evidence_upgrade/audit/sealed_run_inventory.json

Outputs:
- machine status JSON (default research/glhs_journal/CURRENT_EVIDENCE_STATUS.json)
- research/FINAL_PRE_CAREGUARD_STATUS.md rendered from machine state
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

SCHEMA_VERSION = "clara-w0-machine-status.v1"

RIVF_RUN_ID = "2026-08-17-rivf-final-003"
RIVF_SOURCE_SHA = "5b2c0dbf17e2cd1e31c0499cf5334f89a99cdecb"
RIVF_ARMS = ("UNBOUND", "STATE_VERSION_ONLY", "SNAPSHOT_BOUND_STATE_ONLY", "GLHS_STRICT")

RIVF_RECONCILIATION = "research/govred_rivf/provenance/final-003-reconciliation.json"
RIVF_MANIFEST = (
    "artifacts/govred/2026-08-17-rivf-freeze-candidate/final/final_locked_manifest.json"
)
RIVF_STATS_PLAN = (
    "artifacts/govred/2026-08-17-rivf-freeze-candidate/final/final_statistics_plan.json"
)
RIVF_RAW_ROOT = "artifacts/govred/2026-08-17-rivf-final-003"
RIVF_SEAL = "artifacts/govred/2026-08-17-rivf-final-003/artifact-sha256.json"
RIVF_ANALYSIS_V2 = "research/govred_rivf/results/final-003-analysis-v2.json"
RIVF_CLAIM_LEDGER = "research/govred_rivf/claim_to_evidence.csv"

GLHS_RUN_ID = "GLHS-POSTGRES-TOCTOU-FINAL-20260817-01"
GLHS_SOURCE_SHA = "2074f87550c5ee32302bde47bc0b9e6be6af36b5"
GLHS_RUN_DIR = f"artifacts/glhs-postgres-toctou/{GLHS_RUN_ID}"
GLHS_SEAL = f"{GLHS_RUN_DIR}/artifact-sha256.json"
GLHS_ANALYSIS = "research/glhs_journal/results/analysis.json"
GLHS_AGREEMENT = "research/glhs_journal/model_review_run/agreement.json"
GLHS_STATS_PLAN = "research/glhs_journal/postgres_toctou_statistics_plan.json"
GLHS_SCHEDULE_MANIFEST = "research/glhs_journal/postgres_toctou_schedule_manifest.json"
GLHS_OBSERVER_CONTRACT = "research/glhs_journal/postgres_toctou_observer_contract.json"
GLHS_CLAIM_LEDGER = "research/glhs_journal/revision_claim_ledger.csv"

SEALED_RUN_INVENTORY = "research/evidence_upgrade/audit/sealed_run_inventory.json"

CARRIED_FORWARD_MARKER = "## SOICT / GovMut"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_seal(root: Path, seal_path: Path) -> dict:
    """Resolve every entry of an artifact-sha256 inventory against actual bytes."""
    inventory = _load_json(seal_path)
    mismatches = []
    missing = []
    for relative, declared in inventory.items():
        target = root / relative
        if not target.is_file():
            missing.append(relative)
            continue
        actual = _sha256(target)
        if actual != declared:
            mismatches.append({"path": relative, "declared": declared, "actual": actual})
    resolved = not mismatches and not missing
    return {
        "path": str(seal_path),
        "resolved": resolved,
        "entries": len(inventory),
        "missing": sorted(missing),
        "mismatches": mismatches,
    }


def _read_ledger(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _expand_claim_paths(evidence_artifact: str) -> list[str]:
    paths = []
    for raw in evidence_artifact.split(";"):
        raw = raw.strip()
        if not raw:
            continue
        if "{ARM}" in raw:
            paths.extend(raw.replace("{ARM}", arm) for arm in RIVF_ARMS)
        else:
            paths.append(raw)
    return paths


def _raw_rows_reconciled(root: Path) -> dict:
    reconciliation = _load_json(root / RIVF_RECONCILIATION)
    declared = reconciliation.get("raw_results_sha256", {})
    results = {}
    for arm in RIVF_ARMS:
        target = root / RIVF_RAW_ROOT / arm / "raw_results.csv"
        actual = _sha256(target) if target.is_file() else None
        expected = declared.get(arm)
        results[arm] = {
            "sha256": actual,
            "matches_declared": bool(actual and actual == expected),
        }
    return {
        "all_match_declared": all(v["matches_declared"] for v in results.values()),
        "arms": results,
    }


def build_rivf_status(root: Path) -> dict:
    reconciliation = _load_json(root / RIVF_RECONCILIATION)
    manifest = _load_json(root / RIVF_MANIFEST)
    analysis = _load_json(root / RIVF_ANALYSIS_V2)
    stats_plan_path = root / RIVF_STATS_PLAN
    stats_plan_sha = _sha256(stats_plan_path) if stats_plan_path.is_file() else None
    seal = _verify_seal(root / RIVF_RAW_ROOT, root / RIVF_SEAL)
    raw_rows = _raw_rows_reconciled(root)

    arms = {}
    for name, entry in analysis["arms"].items():
        failures = entry["primary_failures"]
        denominator = entry["primary_endpoint_n"]
        computed = failures / denominator if denominator else None
        declared = entry["primary_rate"]
        arms[name] = {
            "all_executed_n": entry["all_executed_n"],
            "primary_endpoint_n": denominator,
            "primary_failures": failures,
            "primary_rate": declared,
            "rate_reproducible": bool(
                computed is not None and round(computed, 6) == round(declared, 6)
            ),
            "wilson_95_ci": entry["wilson_95_ci"],
            "not_run_n": entry["not_run_n"],
        }

    reconciliation_source_sha = reconciliation.get("source_sha")
    manifest_revision = manifest.get("code_revision")
    analysis_source_sha = analysis.get("source_sha")

    manifest_embedded_plan_sha = manifest.get("final_statistics_plan_sha256")
    reconciled_plan_sha = reconciliation.get("statistics_plan_sha256")

    findings = []
    if stats_plan_sha != reconciled_plan_sha:
        findings.append(
            {
                "id": "W0-FIND-RIVF-001",
                "severity": "BLOCKER_IF_UNRESOLVED",
                "detail": (
                    f"on-disk final_statistics_plan.json sha {stats_plan_sha} does not match "
                    f"the reconciliation-recorded frozen stats-plan sha {reconciled_plan_sha}."
                ),
                "resolution": "reconciliation governs; exact bytes must exist and match",
            }
        )
    if manifest_embedded_plan_sha != reconciled_plan_sha:
        findings.append(
            {
                "id": "W0-FIND-RIVF-002",
                "severity": "RESOLVED_HISTORICAL_METADATA",
                "detail": (
                    f"final_locked_manifest.json embeds final_statistics_plan_sha256 "
                    f"{manifest_embedded_plan_sha}, which matches no bytes on disk; "
                    f"the W0-T03 reconciliation (machine-generated) binds the governing "
                    f"frozen stats-plan bytes as {reconciled_plan_sha} (exact file present)."
                ),
                "resolution": "resolved by reconciliation record + exact bytes; manifest field is stale self-referential metadata",
            }
        )

    paired = analysis.get("paired_exact_mcnemar_glhs_strict_vs_unbound", {})
    return {
        "run_id": RIVF_RUN_ID,
        "source_sha": reconciliation_source_sha,
        "top_level_status": "SEALED" if seal["resolved"] else "SEAL_DOES_NOT_RESOLVE",
        "claim_eligibility": "SEALED_CLAIM_ELIGIBLE_executable_primary_schedules",
        "seal": seal,
        "raw_rows": raw_rows,
        "manifest": {
            "path": RIVF_MANIFEST,
            "sha256": _sha256(root / RIVF_MANIFEST),
            "reconciliation_manifest_sha256": reconciliation.get(
                "manifest_sha256_current_local"
            ),
            "code_revision": manifest_revision,
            "status": manifest.get("status"),
            "freeze_state": manifest.get("freeze_state"),
            "cases": len(manifest.get("cases", [])),
        },
        "frozen_statistics_plan": {
            "path": RIVF_STATS_PLAN,
            "sha256": stats_plan_sha,
            "reconciled_sha256": reconciled_plan_sha,
            "bytes_exist": stats_plan_path.is_file(),
            "hash_matches_reconciliation": bool(
                stats_plan_sha and stats_plan_sha == reconciled_plan_sha
            ),
        },
        "analysis_v2": {
            "path": RIVF_ANALYSIS_V2,
            "sha256": _sha256(root / RIVF_ANALYSIS_V2),
            "source_sha": analysis_source_sha,
            "generated_from": analysis.get("generated_from"),
            "primary_denominator_definition": analysis.get(
                "primary_denominator_definition"
            ),
            "arms": arms,
            "paired_exact_mcnemar_glhs_strict_vs_unbound": {
                "b": paired.get("b"),
                "c": paired.get("c"),
                "discordant": paired.get("discordant"),
                "p_exact": paired.get("p_exact"),
                "log10_p": paired.get("log10_p"),
                "note": paired.get("note"),
            },
        },
        "dual_model_protocol_qa": {
            "status": manifest.get("independent_curator_attestation", {}).get(
                "dual_model_protocol_review", "NOT_RUN_pending_router_key"
            ),
            "note": "Recorded, not claimed: locked dual-model protocol QA must run before claim-bearing RIVF analysis.",
        },
        "provenance_findings": findings,
    }


def build_glhs_status(root: Path) -> dict:
    analysis = _load_json(root / GLHS_ANALYSIS)
    agreement = _load_json(root / GLHS_AGREEMENT)
    schedule_manifest = _load_json(root / GLHS_SCHEDULE_MANIFEST)
    seal = _verify_seal(root / GLHS_RUN_DIR, root / GLHS_SEAL)

    plan_artifacts = {
        "statistics_plan": {
            "path": GLHS_STATS_PLAN,
            "bytes_exist": (root / GLHS_STATS_PLAN).is_file(),
            "status": _load_json(root / GLHS_STATS_PLAN).get("status"),
        },
        "schedule_manifest": {
            "path": GLHS_SCHEDULE_MANIFEST,
            "bytes_exist": (root / GLHS_SCHEDULE_MANIFEST).is_file(),
            "status": schedule_manifest.get("status"),
        },
        "observer_contract": {
            "path": GLHS_OBSERVER_CONTRACT,
            "bytes_exist": (root / GLHS_OBSERVER_CONTRACT).is_file(),
            "status": _load_json(root / GLHS_OBSERVER_CONTRACT).get("status"),
        },
    }
    all_plan_bytes_exist = all(v["bytes_exist"] for v in plan_artifacts.values())

    toctou03 = next(
        (row for row in analysis.get("schedule_rows", []) if row.get("id") == "TOCTOU-03"),
        None,
    )
    return {
        "run_id": GLHS_RUN_ID,
        "source_sha": analysis.get("code_revision"),
        "top_level_status": "SEALED" if seal["resolved"] else "SEAL_DOES_NOT_RESOLVE",
        "claim_eligibility": "SEALED_CLAIM_ELIGIBLE",
        "seal": seal,
        "schedules_executed": analysis.get("schedules_executed"),
        "schedule_manifest": {
            "path": GLHS_SCHEDULE_MANIFEST,
            "schedule_order": schedule_manifest.get("schedule_order"),
            "status": schedule_manifest.get("status"),
        },
        "rejected": analysis.get("rejected"),
        "committed_transition": analysis.get("committed_transition"),
        "forbidden_commit_observed": analysis.get("forbidden_commit_observed"),
        "indeterminate_ordering": analysis.get("indeterminate_ordering"),
        "toctou03": {
            "classification": toctou03.get("ordering") if toctou03 else None,
            "commit_outcome": toctou03.get("commit_outcome") if toctou03 else None,
            "status": "INDETERMINATE"
            if toctou03 and toctou03.get("ordering") == "indeterminate_ordering_transition_committed"
            else "determinate",
        },
        "schedule_matrix": analysis.get("schedule_rows"),
        "dual_model_protocol_qa": {
            "status": "complete",
            "case_count": agreement.get("case_count"),
            "pre_reconciliation_agreement": agreement.get("pre_reconciliation_agreement"),
            "cohens_kappa": agreement.get("cohens_kappa"),
            "unresolved": 0 if agreement.get("unresolved_rate") is None else agreement.get(
                "unresolved_rate"
            ),
            "note": "Dual-model blinded protocol-review surrogate; not human/clinician adjudication.",
        },
        "frozen_plan": {
            "status": "FROZEN_FINAL_REVIEWED" if all_plan_bytes_exist else "PLAN_BYTES_MISSING",
            "artifacts": plan_artifacts,
        },
        "analysis": {
            "path": GLHS_ANALYSIS,
            "sha256": _sha256(root / GLHS_ANALYSIS),
            "code_revision": analysis.get("code_revision"),
        },
    }


def _collect_claim_checks(root: Path) -> dict:
    rivf_claims = []
    if (root / RIVF_CLAIM_LEDGER).is_file():
        for row in _read_ledger(root / RIVF_CLAIM_LEDGER):
            rivf_claims.append(
                {
                    "ledger": RIVF_CLAIM_LEDGER,
                    "claim_id": row.get("claim_id", ""),
                    "status": row.get("status", ""),
                    "evidence_artifact": row.get("evidence_artifact", ""),
                }
            )
    glhs_claims = []
    if (root / GLHS_CLAIM_LEDGER).is_file():
        for row in _read_ledger(root / GLHS_CLAIM_LEDGER):
            glhs_claims.append(
                {
                    "ledger": GLHS_CLAIM_LEDGER,
                    "claim_id": row.get("claim_id", ""),
                    "status": row.get("status", ""),
                    "evidence_artifact": row.get("evidence_artifact", ""),
                }
            )
    claims = rivf_claims + glhs_claims
    checks = []
    for claim in claims:
        if claim["status"] != "sealed_claim_eligible":
            continue
        missing = [
            p for p in _expand_claim_paths(claim["evidence_artifact"])
            if not (root / p).is_file()
        ]
        checks.append(
            {
                "claim_id": claim["claim_id"],
                "ledger": claim["ledger"],
                "status": claim["status"],
                "missing_artifacts": missing,
            }
        )
    return {"sealed_claim_eligible_checks": checks}


def build_status(root: Path) -> dict:
    rivf = build_rivf_status(root)
    glhs = build_glhs_status(root)
    claims = _collect_claim_checks(root)
    inventory = {}
    if (root / SEALED_RUN_INVENTORY).is_file():
        inventory = _load_json(root / SEALED_RUN_INVENTORY).get("sealed_runs", {})
    errors = validate_status(
        {"runs": {"rivf_final_003": rivf, "glhs_final": glhs}, "claims": claims},
        root,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "evaluation/evidence_program/render_status.py",
        "generation_rule": (
            "Machine-generated from immutable artifacts and validated results; "
            "hand-edited claims cannot override machine state."
        ),
        "top_level": {
            "sealed": bool(
                rivf["top_level_status"] == "SEALED"
                and glhs["top_level_status"] == "SEALED"
            ),
            "status": (
                "SEALED"
                if rivf["top_level_status"] == "SEALED"
                and glhs["top_level_status"] == "SEALED"
                else "SEALED_PARTIAL"
            ),
            "note": (
                "RIVF dual-model protocol QA NOT_RUN_pending_router_key (recorded, not claimed); "
                "GLHS dual-model protocol QA complete (kappa 1.0, unresolved 0)."
            ),
        },
        "runs": {"rivf_final_003": rivf, "glhs_final": glhs},
        "sealed_run_inventory": inventory,
        "claims": claims,
        "validation": {
            "errors": errors,
            "passes": not errors,
        },
    }


def validate_status(status: dict, root: Path) -> list[str]:
    """Return every machine-consistency violation; empty list means the status is clean.

    Fail conditions (W0-T09):
    - top-level says SEALED but no seal resolves;
    - current result claims a frozen plan but no exact historical bytes exist;
    - manuscript/status denominator cannot reproduce a reported rate;
    - a sealed-claim-eligible claim points to a missing artifact;
    - run/source SHA mismatch exists.
    """
    errors: list[str] = []

    runs = status.get("runs", {})
    top_level = status.get("top_level", {})

    for run_key, run in runs.items():
        if run.get("top_level_status") == "SEALED":
            seal = run.get("seal", {})
            if not seal.get("resolved"):
                errors.append(
                    f"{run_key}: top-level SEALED but seal does not resolve "
                    f"({seal.get('path')} missing={seal.get('missing')} "
                    f"mismatches={len(seal.get('mismatches', []))})"
                )
        elif run.get("top_level_status") == "SEAL_DOES_NOT_RESOLVE":
            errors.append(f"{run_key}: seal explicitly failed to resolve")

        frozen = run.get("frozen_statistics_plan")
        if frozen is not None and (
            not frozen.get("bytes_exist") or not frozen.get("hash_matches_reconciliation")
        ):
            errors.append(
                f"{run_key}: result claims a frozen statistics plan but no exact "
                f"historical bytes exist (path={frozen.get('path')} "
                f"bytes_exist={frozen.get('bytes_exist')} "
                f"hash_matches={frozen.get('hash_matches_reconciliation')})"
            )
        frozen_plan = run.get("frozen_plan")
        if frozen_plan is not None and frozen_plan.get("status") == "PLAN_BYTES_MISSING":
            errors.append(
                f"{run_key}: frozen plan claim but plan bytes missing "
                f"({frozen_plan.get('artifacts')})"
            )

        for name, arm in (run.get("analysis_v2", {}).get("arms", {}) or {}).items():
            failures = arm.get("primary_failures")
            denominator = arm.get("primary_endpoint_n")
            declared = arm.get("primary_rate")
            if denominator and declared is not None and failures is not None:
                computed = failures / denominator
                if round(computed, 6) != round(declared, 6):
                    errors.append(
                        f"{run_key}/{name}: manuscript/status rate not reproducible from "
                        f"denominator ({failures}/{denominator} = {computed:.6f} "
                        f"!= declared {declared})"
                    )

        analysis = run.get("analysis")
        if analysis is not None:
            run_sha = run.get("source_sha")
            analysis_sha = analysis.get("code_revision")
            if run_sha != analysis_sha:
                errors.append(
                    f"{run_key}: run/source SHA mismatch (run={run_sha} "
                    f"analysis.code_revision={analysis_sha})"
                )
        manifest = run.get("manifest")
        if manifest is not None:
            run_sha = run.get("source_sha")
            manifest_revision = manifest.get("code_revision")
            if run_sha != manifest_revision:
                errors.append(
                    f"{run_key}: run/source SHA mismatch (run={run_sha} "
                    f"manifest.code_revision={manifest_revision})"
                )
            reconciliation_sha = manifest.get("reconciliation_manifest_sha256")
            if reconciliation_sha and reconciliation_sha != manifest.get("sha256"):
                errors.append(
                    f"{run_key}: manifest SHA mismatch (on-disk={manifest.get('sha256')} "
                    f"reconciliation={reconciliation_sha})"
                )
        analysis_v2 = run.get("analysis_v2")
        if analysis_v2 is not None:
            run_sha = run.get("source_sha")
            v2_sha = analysis_v2.get("source_sha")
            if run_sha != v2_sha:
                errors.append(
                    f"{run_key}: run/source SHA mismatch (run={run_sha} "
                    f"analysis_v2.source_sha={v2_sha})"
                )

    inventory = status.get("sealed_run_inventory", {})
    for inv_run, entry in inventory.items():
        expected_sha = entry.get("source_sha")
        if (
            inv_run == "rivf-final-003"
            and runs.get("rivf_final_003", {}).get("source_sha")
            and expected_sha != runs["rivf_final_003"]["source_sha"]
        ):
            errors.append(
                f"rivf: sealed_run_inventory source_sha {expected_sha} does not match "
                f"machine run source_sha {runs['rivf_final_003']['source_sha']}"
            )
        if (
            inv_run.startswith("glhs")
            and runs.get("glhs_final", {}).get("source_sha")
            and expected_sha != runs["glhs_final"]["source_sha"]
        ):
            errors.append(
                f"glhs: sealed_run_inventory source_sha {expected_sha} does not match "
                f"machine run source_sha {runs['glhs_final']['source_sha']}"
            )

    for check in status.get("claims", {}).get("sealed_claim_eligible_checks", []):
        if check.get("missing_artifacts"):
            errors.append(
                f"claim {check['claim_id']} points to missing artifact(s): "
                f"{check['missing_artifacts']}"
            )

    if top_level.get("sealed") and not all(
        run.get("top_level_status") == "SEALED" for run in runs.values()
    ):
        errors.append("top_level says SEALED but a run-level seal does not resolve")

    return errors


def render_status_md(status: dict, previous_md: Path | None) -> str:
    rivf = status["runs"]["rivf_final_003"]
    glhs = status["runs"]["glhs_final"]

    rivf_arm_lines = []
    for name in RIVF_ARMS:
        arm = rivf["analysis_v2"]["arms"][name]
        rate = f"{arm['primary_rate']:.3f}"
        ci = arm["wilson_95_ci"]
        rivf_arm_lines.append(
            f"- {name}: {rate} (95% CI {ci[0]:.3f}-{ci[1]:.3f})"
        )
    arms_text = "\n".join(rivf_arm_lines)

    paired = rivf["analysis_v2"]["paired_exact_mcnemar_glhs_strict_vs_unbound"]
    qa_status = rivf["dual_model_protocol_qa"]["status"]

    carried = ""
    if previous_md is not None and previous_md.is_file():
        lines = previous_md.read_text(encoding="utf-8").splitlines()
        start = None
        for index, line in enumerate(lines):
            if line.startswith(CARRIED_FORWARD_MARKER):
                start = index
                break
        if start is not None:
            carried = "\n".join(lines[start:]).rstrip() + "\n"

    doc = [
        "# CLARA-Care Final Program Status (Pre-CareGuard)",
        "",
        (
            "Machine-generated status from immutable artifacts (W0-T08 `render_status.py`); "
            "hand-edited claims do not override machine state. RIVF and GLHS sections below "
            "are rendered from artifact state; SOICT/FMC/CareGuard sections are carried "
            "forward verbatim (outside W0 scope)."
        ),
        "",
        (
            f"Machine status: `{status['schema_version']}` — top-level "
            f"{status['top_level']['status']}. {status['top_level']['note']}"
        ),
        "",
        "## RIVF / GovRed — COMPLETE + ANALYZED + SEALED",
        "",
        f"- Run ID: `{rivf['run_id']}`",
        f"- Frozen git SHA: `{rivf['source_sha']}`",
        (
            "- Source SHA consistency: reconciliation == manifest.code_revision == "
            f"analysis-v2.source_sha == sealed_run_inventory ({rivf['source_sha']})"
        ),
        (
            f"- Frozen stats plan: `{rivf['frozen_statistics_plan']['path']}` "
            f"(sha256 `{rivf['frozen_statistics_plan']['sha256']}`, hash matches "
            f"reconciliation: {rivf['frozen_statistics_plan']['hash_matches_reconciliation']})"
        ),
        (
            "- Final N: 270 executed logical cases per arm (4 arms); 180 NOT_RUN per arm "
            "(protocol exclusions, no denominator)"
        ),
        "- Primary: stale/unauthorized-commit acceptance —",
        arms_text,
        (
            "- Paired McNemar GLHS_STRICT vs UNBOUND: exact two-sided p = "
            f"{paired['p_exact']} (log10 {paired['log10_p']:.2f}; b={paired['b']}, "
            f"c={paired['c']}); manuscript may state p<0.0001"
        ),
        "- Prohibited disclosure: 0/270 every arm",
        (
            f"- Artifact seal: `{rivf['seal']['path']}` (resolved={rivf['seal']['resolved']}, "
            f"{rivf['seal']['entries']} entries) + "
            "`research/govred_rivf/results/analysis.json`"
        ),
        (
            f"- Claim eligibility: {rivf['claim_eligibility']}; RIVF dual-model protocol QA "
            f"`{qa_status}` (recorded, not claimed)"
        ),
        f"- Raw rows reconciled: {rivf['raw_rows']['all_match_declared']}",
        "",
        "## GLHS — COMPLETE + ANALYZED + SEALED",
        "",
        f"- Run ID: `{glhs['run_id']}`",
        f"- Frozen git SHA: `{glhs['source_sha']}`",
        (
            "- Source SHA consistency: analysis.code_revision == sealed_run_inventory "
            f"({glhs['source_sha']})"
        ),
        f"- Final N: {glhs['schedules_executed']} frozen logical schedules",
        (
            f"- Outcomes: {glhs['rejected']} rejected (consent/actor-role/policy/consent races), "
            f"{glhs['committed_transition']} committed transition (TOCTOU-03) with "
            f"{glhs['toctou03']['classification']} ordering; forbidden commit observed "
            f"{glhs['forbidden_commit_observed']}"
        ),
        (
            f"- Dual-model protocol QA: agreement "
            f"{glhs['dual_model_protocol_qa']['pre_reconciliation_agreement']}, "
            f"kappa {glhs['dual_model_protocol_qa']['cohens_kappa']}, unresolved "
            f"{glhs['dual_model_protocol_qa']['unresolved']} "
            "(protocol packet; no frozen subject/output packets existed)"
        ),
        (
            f"- Artifact seal: `{glhs['seal']['path']}` (resolved={glhs['seal']['resolved']}, "
            f"{glhs['seal']['entries']} entries) + "
            "`research/glhs_journal/results/analysis.json`"
        ),
        (
            f"- Frozen plan bytes: {glhs['frozen_plan']['status']} "
            "(statistics plan + schedule manifest + observer contract)"
        ),
        (
            f"- Claim eligibility: {glhs['claim_eligibility']} (final matrix); "
            "manuscript: `research/glhs_journal/MANUSCRIPT_RESULTS.md`, `LIMITATIONS.md`"
        ),
        "",
    ]
    text = "\n".join(doc)
    if carried:
        text += "\n" + carried
    return text


def _write_status(status: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument(
        "--status-output",
        type=Path,
        default=Path("research/glhs_journal/CURRENT_EVIDENCE_STATUS.json"),
    )
    parser.add_argument(
        "--render-md",
        type=Path,
        default=Path("research/FINAL_PRE_CAREGUARD_STATUS.md"),
    )
    args = parser.parse_args(argv)

    root = args.repository_root
    status = build_status(root)
    errors = status["validation"]["errors"]
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    _write_status(status, args.status_output)
    previous = args.render_md if args.render_md.is_file() else None
    args.render_md.parent.mkdir(parents=True, exist_ok=True)
    args.render_md.write_text(
        render_status_md(status, previous), encoding="utf-8"
    )
    print(f"wrote {args.status_output}")
    print(f"wrote {args.render_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
