#!/usr/bin/env python3
"""Build the R3 claim audit and a tracked-source-only release package."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PACKAGE = OUT / "package"
GENERATED_DATE = "2026-08-19"
CANONICAL_GUARANTEE = (
    "On the evaluated snapshot-bound path, a proposal derived from THSS retains "
    "the exact disclosure binding through GST admission; universal "
    "provenance-sensitive retention across every internal review/adaptation path "
    "has not yet been established."
)

# This list is deliberately explicit. It excludes publication_registry.yaml,
# sealed directories, evaluation files, and untracked user manuscripts.
SOURCE_FILES = (
    "research/claim_ledger.csv",
    "research/FINAL_PRE_CAREGUARD_STATUS.md",
    "research/FINAL_TOP_TIER_EVIDENCE_STATUS.md",
    "research/PROGRAM_READINESS.md",
    "research/R3_BASELINE_AUDIT.json",
    "research/R3_WORKSTREAM_A_REPORT.md",
    "research/glhs_journal/CANONICAL_TOCTOU_EVIDENCE.md",
    "research/glhs_journal/CURRENT_EVIDENCE_STATUS.json",
    "research/glhs_journal/MANUSCRIPT_RESULTS.md",
    "research/glhs_journal/REVISION_READINESS.md",
    "research/glhs_journal/revision_claim_ledger.csv",
    "research/govred_rivf/MANUSCRIPT_RESULTS.md",
    "research/govred_rivf/PUBLICATION_ROUTING.md",
    "research/govred_rivf/READINESS.md",
    "research/govred_rivf/claim_to_evidence.csv",
    "research/assurance_soict/MANUSCRIPT_RESULTS.md",
    "research/assurance_soict/READINESS.md",
    "research/assurance_soict/claim_to_evidence.csv",
    "research/careguard_vn/MANUSCRIPT_RESULTS.md",
    "research/careguard_vn/READINESS.md",
    "research/careguard_vn/claim_to_evidence.csv",
)

LEDGERS = (
    "research/claim_ledger.csv",
    "research/glhs_journal/revision_claim_ledger.csv",
    "research/govred_rivf/claim_to_evidence.csv",
    "research/assurance_soict/claim_to_evidence.csv",
    "research/careguard_vn/claim_to_evidence.csv",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_files() -> set[str]:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return {line for line in result.stdout.splitlines() if line}


def git_head() -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def load_json(relative: str) -> tuple[Path, dict[str, Any]]:
    path = ROOT / relative
    return path, json.loads(path.read_text(encoding="utf-8"))


def resolve_anchor(value: str) -> tuple[str | None, str]:
    """Return one deterministic anchor, preferring the first listed path."""
    for raw in value.split(";"):
        candidate = raw.strip()
        if not candidate or candidate.upper() == "NOT_RUN":
            continue
        pattern = candidate
        if "{" in pattern and "}" in pattern:
            prefix, suffix = pattern.split("{", 1)
            _choices, tail = suffix.split("}", 1)
            pattern = f"{prefix}*{tail}"
        if any(char in pattern for char in "*?["):
            matches = sorted(
                (item for item in ROOT.glob(pattern) if item.is_file()),
                key=lambda item: item.as_posix(),
            )
            if matches:
                return matches[0].relative_to(ROOT).as_posix(), "first_glob_match"
            continue
        path = ROOT / candidate
        if path.is_file():
            return candidate, "listed_path"
    return None, "missing"


def audit_claim_ledgers() -> dict[str, Any]:
    claims: list[dict[str, Any]] = []
    for ledger in LEDGERS:
        with (ROOT / ledger).open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                evidence = row.get("evidence_artifact", "")
                anchor, resolution = resolve_anchor(evidence)
                status = row.get("status", "").strip()
                item: dict[str, Any] = {
                    "ledger": ledger,
                    "claim_id": row.get("claim_id", ""),
                    "claim": row.get("claim") or row.get("claim_text") or "",
                    "ledger_status": status,
                    "canonical_anchor": anchor,
                    "anchor_resolution": resolution,
                    "one_canonical_anchor": anchor is not None,
                }
                if anchor is not None:
                    anchor_path = ROOT / anchor
                    item["anchor_sha256"] = sha256(anchor_path)
                    item["audit_status"] = "verified_anchor"
                elif status.upper() == "NOT_RUN":
                    item["audit_status"] = "declared_not_run"
                else:
                    item["audit_status"] = "missing_anchor"
                claims.append(item)

    by_status: dict[str, int] = {}
    for claim in claims:
        by_status[claim["audit_status"]] = by_status.get(claim["audit_status"], 0) + 1
    return {
        "rule": "Each claim has one deterministic canonical anchor; the anchor must exist and be hashed. NOT_RUN claims remain explicit gates.",
        "claim_count": len(claims),
        "counts": by_status,
        "declared_not_run_claim_ids": [
            claim["claim_id"] for claim in claims if claim["audit_status"] == "declared_not_run"
        ],
        "missing_anchor_claim_ids": [
            claim["claim_id"] for claim in claims if claim["audit_status"] == "missing_anchor"
        ],
        "claims": claims,
        "pass": not any(claim["audit_status"] == "missing_anchor" for claim in claims),
    }


def balance_check() -> dict[str, Any]:
    positive_path, positive = load_json("artifacts/commitloop/confirmatory-cohort-v2/result_audit.json")
    null_path, null = load_json(
        "artifacts/commitloop/confirmatory-cohort-v3/offline_dry_run/statistical_results.json"
    )
    cohort_path, cohort = load_json(
        "artifacts/commitloop/confirmatory-cohort-v3/cohort/cohort_manifest.json"
    )
    positive_subjects = positive["execution"]["subjects"]
    null_subjects = null["subject_count"]
    return {
        "rule": "Keep the 64-subject positive and 384-subject/null records separate; the null-like record is never sealed by this package.",
        "positive": {
            "path": positive_path.relative_to(ROOT).as_posix(),
            "sha256": sha256(positive_path),
            "subjects": positive_subjects,
            "status": positive["status"],
            "claim_class": "sealed_historical_positive",
        },
        "null_like": {
            "path": null_path.relative_to(ROOT).as_posix(),
            "sha256": sha256(null_path),
            "cohort_manifest": cohort_path.relative_to(ROOT).as_posix(),
            "cohort_manifest_sha256": sha256(cohort_path),
            "subjects": null_subjects,
            "ties": null["ties"],
            "effect": null["effect_mean_reference_minus_comparator"],
            "p_value": null["exact_two_sided_sign_p_value"],
            "status": null["status"],
            "cohort_status": cohort["status"],
            "claim_class": "descriptive_synthetic_unfrozen",
        },
        "balanced_subject_counts": positive_subjects == 64 and null_subjects == 384,
        "null_is_not_sealed": (
            null["status"] == "DESCRIPTIVE_SYNTHETIC_ONLY"
            and cohort["status"] == "GENERATED_NOT_FROZEN"
        ),
    }


def venue_overlap_check() -> dict[str, Any]:
    registry = (ROOT / "research/publication_registry.yaml").read_text(encoding="utf-8")
    required = (
        "govred-final-003",
        "2026-08-17-rivf-final-003",
        "govmut-w8-45mutant",
        "govmut-soict-2026-final-v2",
        "same-frozen-evidence; second-venue-requires-material-extension",
    )
    return {
        "registry_path": "research/publication_registry.yaml",
        "owner": "agent A; read-only for this workstream",
        "pairs": {
            "GovRed_02_08": "same-frozen-evidence; second-venue-requires-material-extension",
            "GovMut_03_11": "same-frozen-evidence; second-venue-requires-material-extension",
        },
        "required_tokens_present": {token: token in registry for token in required},
        "pass": all(token in registry for token in required),
    }


def preflight() -> dict[str, Any]:
    tracked = git_files()
    missing_sources = [path for path in SOURCE_FILES if path not in tracked]
    tracked_pdfs = sorted(
        path for path in tracked if path.lower().endswith(".pdf") and not path.startswith("research/release_r3/")
    )
    tools = {
        name: shutil.which(name) is not None
        for name in ("latexmk", "pdflatex", "xelatex", "pandoc")
    }
    return {
        "source_files_all_tracked": not missing_sources,
        "missing_tracked_sources": missing_sources,
        "tracked_pdf_sources": tracked_pdfs,
        "pdf_source_count": len(tracked_pdfs),
        "pdf_preflight": "PASS" if tracked_pdfs else "MISSING_TRACKED_PDF_SOURCES",
        "build_tools": tools,
        "build_tool_preflight": "PASS" if any(tools.values()) else "MISSING_PDF_BUILD_TOOLS",
    }


def package_sources(tracked: set[str]) -> list[str]:
    if PACKAGE.exists():
        for path in sorted(PACKAGE.rglob("*"), reverse=True):
            if path.is_file() or path.is_symlink():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
    PACKAGE.mkdir(parents=True, exist_ok=True)
    pdfs = [
        path for path in tracked if path.lower().endswith(".pdf") and not path.startswith("research/release_r3/")
    ]
    files = list(SOURCE_FILES) + sorted(pdfs)
    for relative in files:
        source = ROOT / relative
        if relative not in tracked or not source.is_file():
            continue
        destination = PACKAGE / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return sorted(
        path.relative_to(OUT).as_posix()
        for path in PACKAGE.rglob("*")
        if path.is_file()
    )


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def generate_checksums(paths: list[Path]) -> None:
    lines = [f"{sha256(path)}  {path.relative_to(OUT).as_posix()}" for path in sorted(paths)]
    (OUT / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    tracked = git_files()
    package_files = package_sources(tracked)
    claim_audit = audit_claim_ledgers()
    balance = balance_check()
    overlap = venue_overlap_check()
    package_preflight = preflight()

    build_info = {
        "schema_version": "clara-r3-build-info.v1",
        "generated_date": GENERATED_DATE,
        "source_commit": git_head(),
        "spec": "MASTER_SPEC_REVIEWER_R3_2026-08-19.md#2.11",
        "sealed_artifacts_modified": False,
        "publication_registry_modified": False,
        "package_policy": "tracked source and tracked PDF paths only",
        "package_files": package_files,
        "preflight": package_preflight,
    }
    write_json(OUT / "BUILD_INFO.json", build_info)

    evidence_manifest = {
        "schema_version": "clara-r3-evidence-manifest.v1",
        "generated_date": GENERATED_DATE,
        "source_commit": git_head(),
        "r3_requirements": {
            "manual_gates": [
                "Canonical GLHS guarantee was checked only in the tracked GLHS manuscript; untracked user manuscripts for papers 01/04/05/07/09/10 were intentionally excluded.",
                "GovMut second-venue manuscripts are untracked user documents and were not edited; M3 superset and non-budget-normalized wording must be checked there manually.",
                "No tracked PDF source exists; PDF source/package preflight is incomplete.",
                "No latexmk, pdflatex, xelatex, or pandoc executable was detected; PDF build preflight is incomplete.",
                "GLHS v2 has two frozen classification mismatches and remains not claim-eligible until reconciliation and resealing.",
                "GovRed follow-up holdout/repetition/auditability and dual-model QA gates remain open; 180 protocol-excluded cases are not counted.",
                "CareGuard CG-01 authorized DAV identity frame and CG-05 human mapping review remain manual gates; status stays RESULT-INCOMPLETE.",
            ],
            "canonical_glhs_guarantee": {
                "text": CANONICAL_GUARANTEE,
                "tracked_manuscript_checks": {
                    "research/glhs_journal/MANUSCRIPT_RESULTS.md": CANONICAL_GUARANTEE
                    in (ROOT / "research/glhs_journal/MANUSCRIPT_RESULTS.md").read_text(encoding="utf-8")
                },
                "untracked_user_manuscripts_checked": False,
            },
            "claim_to_evidence_audit": claim_audit,
            "context_utility_balance": balance,
            "venue_overlap": overlap,
            "careguard_status": {
                "required_status": "RESULT-INCOMPLETE",
                "manuscript_has_status": "RESULT-INCOMPLETE" in (ROOT / "research/careguard_vn/MANUSCRIPT_RESULTS.md").read_text(encoding="utf-8"),
                "manual_gates": ["CG-01 authorized DAV identity frame", "CG-05 human mapping review"],
                "performance_claim_permitted": False,
            },
        },
        "tracked_source_package": package_files,
        "sealed_or_owner_files_read_only": [
            "research/publication_registry.yaml",
            "research/assurance_soict/seal/**",
            "research/glhs_journal/protocol_v2/**",
            "artifacts/**",
        ],
    }
    write_json(OUT / "EVIDENCE_MANIFEST.json", evidence_manifest)

    checksum_paths = [
        OUT / "BUILD_INFO.json",
        OUT / "EVIDENCE_MANIFEST.json",
        OUT / "README.md",
        OUT / "synchronize_r3.py",
    ] + [OUT / relative for relative in package_files]
    generate_checksums(checksum_paths)
    return 0 if (
        package_preflight["source_files_all_tracked"]
        and package_preflight["pdf_preflight"] == "PASS"
        and package_preflight["build_tool_preflight"] == "PASS"
        and claim_audit["pass"]
        and balance["balanced_subject_counts"]
        and balance["null_is_not_sealed"]
        and overlap["pass"]
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
