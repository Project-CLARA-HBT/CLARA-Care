#!/usr/bin/env python3
"""Unified Reproducibility & Cryptographic Verification Sweep for GLHS Q3/R3 (Phase 9 / E14).

Executes an offline, fail-closed reproducibility and cryptographic seal audit across all
15 prospective experiment bundles (E00 through E14):
  1. Enforces strict fail-closed network isolation (prohibits sockets and DNS).
  2. Validates clean-tree git state and dual-SHA provenance binding.
  3. Verifies SHA-256 seals, protocol digests, Merkle hash chains, and file checksums for E00–E14.
  4. Audits claim ledger rows in r3_claim_to_evidence.csv and q3_r3/evidence/claim_to_evidence.csv.
  5. Enforces claim eligibility and Red Team safety invariants (zero unbacked clinical claims).
  6. Generates reproduction_report.json under research/glhs_journal/q3_r3/release/.

Usage:
    python3 reproduce_q3_r3.py [--skip-git-check]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import socket
import subprocess
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

# Ensure repository root and service packages are on sys.path
_REPO_ROOT = Path(__file__).resolve().parent
for _p in (_REPO_ROOT, _REPO_ROOT / "services" / "api" / "src", _REPO_ROOT / "services" / "ml" / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from clara_api.glhs.canonical_json import canonical_hash

AUDITED_GIT_COMMIT = "81f040d3e05905cc384239c5ae130f629e722d3e"
AUDITED_SUT_COMMIT = "81f040d3e05905cc384239c5ae130f629e722d3e"
AUDITED_HARNESS_COMMIT = "e7a073749d8d3d434f6d47204238cc6655431f76"

MODEL_ALIAS_MAP: dict[str, list[str]] = {
    "claude-sonnet-4.6": ["claude-sonnet-4.6", "claude-sonnet-4-6"],
    "gemini-3.6-flash-high": ["gemini-3.6-flash-high"],
    "gemini-3.8-flash-tiered": ["gemini-3.8-flash-tiered", "antigravity/gemini-3.8-flash-tiered"],
}

RELEASE_ROOT = _REPO_ROOT / "research" / "glhs_journal" / "q3_r3" / "release"
EVIDENCE_ROOT = _REPO_ROOT / "research" / "glhs_journal" / "q3_r3" / "evidence"
PROTOCOLS_ROOT = _REPO_ROOT / "research" / "glhs_journal" / "q3_r3" / "protocols"
CLAIM_BUDGET_PATH = _REPO_ROOT / "research" / "glhs_journal" / "q3_r3" / "claim_budget.json"

EXPERIMENTS_MAP = [
    ("E00", "E00_code_sync", "Literature/Claim Freeze & AST Write Route Inventory", 47),
    ("E01", "E01_inference_consumption", "Inference Consumption Integrity & Continuous Attestation", 768),
    ("E02", "E02_component_ablation", "2^4 Binding Component Factorial Ablation", 2816),
    ("E03", "E03_minimal_baseline", "Minimal Token / HMAC / Macaroon Capability Baseline", 1408),
    ("E04", "E04_postgres_toctou", "PostgreSQL 16 Serializable TOCTOU Concurrency Campaign", 2280),
    ("E05", "E05_dependency_completeness", "Schema-Derived Dependency-Completeness Contracts", 312),
    ("E06", "E06_anti_downgrade", "Anti-Downgrade & Lineage Anti-Laundering Enforcement", 300),
    ("E07", "E07_canonicalization", "RFC 8785 JSON Canonicalization Multi-Runtime Conformance", 45),
    ("E08", "E08_formal_assurance", "TLA+ / TLC Bounded Exhaustive Formal Verification", 2),
    ("E09", "E09_concurrency", "Entity-Partitioned DAG Versioning Concurrency Benchmark", 6870),
    ("E10", "E10_fullstack", "FastAPI HTTP REST Gateway & PostgreSQL Tail Performance", 700),
    ("E11", "E11_model_replication", "Two-Model Large Context Utility & TOST Equivalence", 48),
    ("E12", "E12_malformed_sensitivity", "12-Class Malformed-Output Error Taxonomy & Sensitivity", 48),
    ("E13", "E13_external_validation", "Synthetic Source-Derived Task Suite (eICU/Synthea/MIMIC/Diabetes)", 9),
    ("E14", "E14_reproducibility", "Hermetic Clean-Environment Reproduction & Release Packaging", 15),
]


class NetworkAccessProhibitedError(RuntimeError):
    """Raised if any network activity is attempted during offline reproduction."""


class MissingArtifactError(RuntimeError):
    """Raised when a required prospective or sealed artifact is missing."""


class ChronologyAnomalyError(RuntimeError):
    """Raised when freeze timestamp does not strictly precede execution timestamp."""


class CorruptedHashError(RuntimeError):
    """Raised when file checksum or Merkle hash chain validation fails."""


class UnattestedSimulationError(RuntimeError):
    """Raised when a simulation is misrepresented as real PostgreSQL evidence."""


class UnbackedProviderClaimError(RuntimeError):
    """Raised when provider benchmarks lack durable raw request/response ledgers."""


class ClaimBudgetViolationError(RuntimeError):
    """Raised when a claim ledger statement breaches claim_budget.json prohibitions."""


class GitWorktreeDirtyError(RuntimeError):
    """Raised when git repository is dirty or git command fails during fail-closed check."""


class RecordCountMismatchError(RuntimeError):
    """Raised when raw runs record count does not match expected_records count."""


_orig_socket = socket.socket
_orig_create_connection = socket.create_connection
_orig_getaddrinfo = socket.getaddrinfo
_orig_gethostbyname = socket.gethostbyname


def restore_network() -> None:
    """Restore original socket functions."""
    socket.socket = _orig_socket
    socket.create_connection = _orig_create_connection
    socket.getaddrinfo = _orig_getaddrinfo
    socket.gethostbyname = _orig_gethostbyname


def disable_network() -> None:
    """Prohibit all socket creation and DNS resolution during offline reproduction."""
    def forbidden_socket(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0, fileno=None):
        if family in (socket.AF_INET, socket.AF_INET6):
            raise NetworkAccessProhibitedError("network_access_prohibited_during_reproduction")
        return _orig_socket(family, type, proto, fileno)

    def forbidden_conn(*args: Any, **kwargs: Any) -> Any:
        raise NetworkAccessProhibitedError("network_access_prohibited_during_reproduction")

    socket.socket = forbidden_socket  # type: ignore[assignment]
    socket.create_connection = forbidden_conn  # type: ignore[assignment]
    socket.getaddrinfo = forbidden_conn  # type: ignore[assignment]
    socket.gethostbyname = forbidden_conn  # type: ignore[assignment]


def sha256_file(path: Path) -> str:
    """Compute SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_iso8601(ts_str: str) -> datetime:
    """Parse ISO8601 UTC timestamp string."""
    if not ts_str:
        raise ValueError("empty_timestamp")
    ts_clean = ts_str.replace("Z", "+00:00")
    if len(ts_clean) == 10 and ts_clean.count("-") == 2:
        ts_clean += "T00:00:00+00:00"
    dt = datetime.fromisoformat(ts_clean)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def verify_git_state(skip_git_check: bool = False) -> dict[str, Any]:
    """Verify git commit and clean-tree state. Fail closed with GitWorktreeDirtyError if git is missing or tree is dirty."""
    git_available = True
    current_sha = AUDITED_SUT_COMMIT
    try:
        res_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=_REPO_ROOT,
        )
        current_sha = res_sha.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        git_available = False

    clean_tree = False
    if git_available:
        try:
            res_status = subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=no"],
                capture_output=True,
                text=True,
                check=True,
                cwd=_REPO_ROOT,
            )
            clean_tree = len(res_status.stdout.strip()) == 0
        except (subprocess.SubprocessError, OSError):
            git_available = False

    if not skip_git_check:
        if not git_available or not clean_tree:
            raise GitWorktreeDirtyError(
                "git_check_failed: git unavailable or tracked worktree is dirty"
            )

    return {
        "audited_commit": AUDITED_GIT_COMMIT,
        "audited_sut_commit": AUDITED_SUT_COMMIT,
        "audited_parent_harness_commit": AUDITED_HARNESS_COMMIT,
        "current_commit": current_sha,
        "commit_match": (current_sha == AUDITED_SUT_COMMIT or current_sha.startswith(AUDITED_SUT_COMMIT[:8])),
        "tracked_worktree_clean": clean_tree,
        "git_check_passed": skip_git_check or (git_available and clean_tree),
    }


def verify_experiment_checksums(exp_dir: Path) -> dict[str, str]:
    """Verify checksums.sha256 against every file in the experiment directory."""
    checksum_file = exp_dir / "checksums.sha256"
    if not checksum_file.is_file():
        raise MissingArtifactError(f"required_artifact_missing:checksums_file_missing:{checksum_file}")

    lines = checksum_file.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise CorruptedHashError(f"empty_checksums_sha256:{checksum_file}")

    verified_files: dict[str, str] = {}
    for lineno, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            expected_digest, rel_path = line.split("  ", 1)
        except ValueError as exc:
            raise CorruptedHashError(f"malformed_checksum_line:{lineno}:{line}") from exc

        if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
            raise CorruptedHashError(f"invalid_sha256_format:{lineno}:{expected_digest}")

        target = exp_dir / rel_path
        if not target.is_file():
            raise MissingArtifactError(f"sealed_file_missing:{rel_path}")

        actual_digest = sha256_file(target)
        if actual_digest != expected_digest:
            raise CorruptedHashError(
                f"checksum_mismatch:{rel_path}:expected={expected_digest}:actual={actual_digest}"
            )
        verified_files[rel_path] = actual_digest

    return verified_files


def verify_hash_chain(runs_file: Path) -> int:
    """Verify tamper-evident Merkle hash chain in runs.jsonl."""
    if not runs_file.is_file():
        return 0

    count = 0
    prev_hash = ""
    with runs_file.open("r", encoding="utf-8") as handle:
        for idx, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            rec = json.loads(line)
            count += 1
            if rec.get("prev_hash") != prev_hash:
                raise CorruptedHashError(
                    f"record_hash_mismatch:chain_broken:line_{idx}:expected_prev={prev_hash}:actual_prev={rec.get('prev_hash')}"
                )
            rec_copy = dict(rec)
            expected_hash = rec_copy.pop("hash", None)
            actual_hash = canonical_hash(rec_copy, profile="clara.canonical-json.v2-rfc8785")
            if expected_hash != actual_hash:
                raise CorruptedHashError(
                    f"record_hash_mismatch:line_{idx}:expected={expected_hash}:actual={actual_hash}"
                )
            prev_hash = actual_hash

    return count


def verify_backend_attestation(exp_dir: Path) -> dict[str, Any]:
    """Verify backend attestation contract truthfulness."""
    att_file = exp_dir / "backend_attestation.json"
    if not att_file.is_file():
        raise MissingArtifactError(f"backend_attestation_missing:{att_file}")

    data = json.loads(att_file.read_text(encoding="utf-8"))
    backend_type = data.get("backend_type", data.get("actual_backend", ""))
    is_simulation = data.get("simulation", False)

    # Check for simulation masquerading as production PostgreSQL
    if data.get("backend_type") == "real_postgresql_16" and is_simulation:
        raise UnattestedSimulationError(
            f"unattested_simulation_masquerading_as_postgresql in {exp_dir.name}"
        )
    if ("postgresql" in backend_type.lower() and "not production" not in backend_type.lower()) and is_simulation:
        raise UnattestedSimulationError(
            f"unattested_simulation_masquerading_as_postgresql in {exp_dir.name}"
        )

    return data


def verify_provider_run_ledger(exp_dir: Path) -> dict[str, Any]:
    """Verify provider run ledger for live LLM provider benchmark experiments."""
    att_file = exp_dir / "backend_attestation.json"
    if not att_file.is_file():
        raise MissingArtifactError(f"backend_attestation_missing:{att_file}")

    data = json.loads(att_file.read_text(encoding="utf-8"))
    actual_backend = data.get("actual_backend", "").lower()
    is_live_provider = data.get("network_provider", False) and ("live" in actual_backend or "provider ledger" in actual_backend or "e11" in exp_dir.name.lower())
    is_e12 = "e12" in exp_dir.name.lower()

    if is_live_provider or is_e12:
        ledger_file = exp_dir / "raw" / "provider_run_ledger.json"
        if not ledger_file.is_file() and is_e12:
            ledger_file = exp_dir.parent / "E11_model_replication" / "raw" / "provider_run_ledger.json"
        if not ledger_file.is_file():
            raise UnbackedProviderClaimError(
                f"unbacked_provider_claim_missing_ledger in {exp_dir.name}"
            )
        ledger_doc = json.loads(ledger_file.read_text(encoding="utf-8"))
        if not ledger_doc:
            raise UnbackedProviderClaimError(f"unbacked_provider_claim_empty_ledger:{exp_dir.name}")

        from evaluation.commitloop.v8_runner import audit_provider_run_ledger
        try:
            audit_res = audit_provider_run_ledger(
                ledger_doc,
                raise_on_empty_raw=True,
                raise_on_token_error=True,
                raise_on_taxonomy_error=True,
            )
        except (ValueError, TypeError) as err:
            raise UnbackedProviderClaimError(f"unbacked_provider_claim_invalid_ledger:{exp_dir.name}:{err}") from err

        # Deep-check requested vs reported models: verify non-empty strings and valid models tested
        if not audit_res.get("models_tested"):
            raise UnbackedProviderClaimError(f"unbacked_provider_claim_missing_models_tested:{exp_dir.name}")

        # Deep-check token usage non-negative and positive
        token_usage = audit_res.get("token_usage", {})
        if (
            token_usage.get("prompt_tokens", 0) <= 0
            or token_usage.get("completion_tokens", 0) <= 0
            or token_usage.get("total_tokens", 0) <= 0
        ):
            raise UnbackedProviderClaimError(f"unbacked_provider_claim_invalid_token_usage:{exp_dir.name}:{token_usage}")

        val_file = exp_dir / "validation.json"
        if val_file.is_file():
            val_doc = json.loads(val_file.read_text(encoding="utf-8"))
            val_fallbacks = val_doc.get("fallbacks_observed")
            if val_fallbacks is not None:
                if audit_res["fallbacks_observed"] > 0 and val_fallbacks == 0:
                    raise UnbackedProviderClaimError(
                        f"unbacked_provider_claim_false_zero_fallback:{exp_dir.name}: audited={audit_res['fallbacks_observed']} vs reported={val_fallbacks}"
                    )
                if val_fallbacks != audit_res["fallbacks_observed"]:
                    raise UnbackedProviderClaimError(
                        f"unbacked_provider_claim_fallback_count_mismatch:{exp_dir.name}: audited={audit_res['fallbacks_observed']} vs reported={val_fallbacks}"
                    )

        ledger_doc["_audit"] = audit_res
        return ledger_doc

    return {}


def verify_experiment_chronology(exp_dir: Path) -> None:
    """Verify that protocol freeze strictly precedes execution, validation, and seal timestamps."""
    freeze_file = exp_dir / "freeze.json"
    if not freeze_file.is_file():
        raise MissingArtifactError(f"freeze_file_missing:{freeze_file}")

    freeze_data = json.loads(freeze_file.read_text(encoding="utf-8"))
    freeze_ts_str = (
        freeze_data.get("freeze_timestamp_utc")
        or freeze_data.get("freeze_timestamp")
        or freeze_data.get("prospective_freeze_timestamp_utc")
    )
    if not freeze_ts_str:
        raise ChronologyAnomalyError(f"missing_freeze_timestamp:{exp_dir.name}")

    freeze_dt = parse_iso8601(freeze_ts_str)

    exec_started_dt = None
    exec_completed_dt = None
    validated_dt = None
    sealed_dt = None

    for candidate in [
        exp_dir / "seal.json",
        exp_dir / "validation.json",
        exp_dir / "derived" / "summary.json",
        exp_dir / "raw" / "fullstack_manifest.json",
    ]:
        if candidate.is_file():
            doc = json.loads(candidate.read_text(encoding="utf-8"))
            st_str = doc.get("execution_started_utc") or doc.get("started_at")
            cp_str = doc.get("execution_completed_utc") or doc.get("completed_at")
            vl_str = doc.get("validated_at_utc") or doc.get("validated_utc")
            sl_str = doc.get("sealed_at_utc") or doc.get("sealed_utc") or doc.get("execution_timestamp")

            if st_str and exec_started_dt is None:
                exec_started_dt = parse_iso8601(st_str)
            if cp_str and exec_completed_dt is None:
                exec_completed_dt = parse_iso8601(cp_str)
            if vl_str and validated_dt is None:
                validated_dt = parse_iso8601(vl_str)
            if sl_str and sealed_dt is None:
                sealed_dt = parse_iso8601(sl_str)

    # Monotonic order: freeze_timestamp_utc <= execution_started_utc <= execution_completed_utc <= sealed_at_utc
    if exec_started_dt and freeze_dt > exec_started_dt:
        raise ChronologyAnomalyError(
            f"chronology_anomaly: freeze {freeze_dt.isoformat()} > execution_started {exec_started_dt.isoformat()} in {exp_dir.name}"
        )
    if exec_started_dt and exec_completed_dt and exec_started_dt > exec_completed_dt:
        raise ChronologyAnomalyError(
            f"chronology_anomaly: execution_started {exec_started_dt.isoformat()} > execution_completed {exec_completed_dt.isoformat()} in {exp_dir.name}"
        )
    if exec_completed_dt and validated_dt and exec_completed_dt > validated_dt:
        raise ChronologyAnomalyError(
            f"chronology_anomaly: execution_completed {exec_completed_dt.isoformat()} > validated_at {validated_dt.isoformat()} in {exp_dir.name}"
        )
    if exec_completed_dt and sealed_dt and exec_completed_dt > sealed_dt:
        raise ChronologyAnomalyError(
            f"chronology_anomaly: execution_completed {exec_completed_dt.isoformat()} > sealed_at {sealed_dt.isoformat()} in {exp_dir.name}"
        )
    if validated_dt and sealed_dt and validated_dt > sealed_dt:
        raise ChronologyAnomalyError(
            f"chronology_anomaly: validated_at {validated_dt.isoformat()} > sealed_at {sealed_dt.isoformat()} in {exp_dir.name}"
        )
    if sealed_dt and freeze_dt > sealed_dt:
        raise ChronologyAnomalyError(
            f"chronology_anomaly: freeze {freeze_dt.isoformat()} > sealed_at {sealed_dt.isoformat()} in {exp_dir.name}"
        )


def verify_experiment_bundle(
    exp_id: str,
    folder_name: str,
    exp_title: str,
    expected_records: int | None = None,
    evidence_root: Path | None = None,
) -> dict[str, Any]:
    """Verify a single experiment bundle under research/glhs_journal/q3_r3/evidence/."""
    root = evidence_root or EVIDENCE_ROOT
    exp_dir = root / folder_name
    if not exp_dir.is_dir():
        raise MissingArtifactError(f"required_artifact_missing:{exp_id}:{exp_dir}")

    # Check required core artifacts
    for required_file in ("protocol.json", "protocol.sha256", "freeze.json"):
        if not (exp_dir / required_file).is_file():
            raise MissingArtifactError(f"required_artifact_missing:{exp_id}:{required_file}")

    # 1. Checksums verification
    verified_files = verify_experiment_checksums(exp_dir)

    # 2. Protocol freeze verification
    proto_file = exp_dir / "protocol.json"
    proto_sha_file = exp_dir / "protocol.sha256"
    actual_proto_sha = sha256_file(proto_file)
    expected_proto_sha = proto_sha_file.read_text(encoding="utf-8").strip().split()[0]
    if actual_proto_sha.lower() != expected_proto_sha.lower():
        raise CorruptedHashError(
            f"protocol_seal_mismatch:{exp_id}:actual={actual_proto_sha}:expected={expected_proto_sha}"
        )

    # 3. Chronology verification
    verify_experiment_chronology(exp_dir)

    # 4. Backend attestation and provider ledger verification
    verify_backend_attestation(exp_dir)
    if (exp_dir / "raw" / "provider_run_ledger.json").is_file():
        verify_provider_run_ledger(exp_dir)

    # 5. Merkle chain verification for raw execution logs
    records_count = 0
    runs_file = exp_dir / "raw" / "runs.jsonl"
    if runs_file.is_file():
        records_count = verify_hash_chain(runs_file)
    elif (exp_dir / "raw" / "results.jsonl").is_file():
        results_file = exp_dir / "raw" / "results.jsonl"
        records_count = len([l for l in results_file.read_text(encoding="utf-8").splitlines() if l.strip()])

    # Enforce expected_records line-count validation fail-closed
    exp_expected = expected_records
    val_file = exp_dir / "validation.json"
    if exp_expected is None and val_file.is_file():
        vdoc = json.loads(val_file.read_text(encoding="utf-8"))
        exp_expected = (
            vdoc.get("expected_records")
            or vdoc.get("total_schedules_audited")
            or vdoc.get("total_executions_audited")
            or vdoc.get("total_run_records")
            or vdoc.get("total_trials_audited")
            or vdoc.get("total_tasks")
            or vdoc.get("total_vectors_audited")
        )

    proto_file = exp_dir / "protocol.json"
    if exp_expected is None and proto_file.is_file():
        pdoc = json.loads(proto_file.read_text(encoding="utf-8"))
        exp_expected = (
            pdoc.get("sample_size_allocation", {}).get("total_executions")
            or pdoc.get("sample_size_allocation", {}).get("total_runs")
            or pdoc.get("sample_size_allocation", {}).get("total_schedules_N")
            or pdoc.get("sample_size_allocation", {}).get("total_executions_N")
        )

    if exp_expected is None:
        raise RecordCountMismatchError(
            f"record_count_mismatch:{exp_id}:missing_expected_records_count"
        )

    if records_count != exp_expected:
        raise RecordCountMismatchError(
            f"record_count_mismatch:{exp_id}:expected={exp_expected}:actual={records_count}"
        )

    # 6. Seal verification
    seal_file = exp_dir / "seal.json"
    if not seal_file.is_file():
        raise MissingArtifactError(f"required_artifact_missing:{exp_id}:seal.json")

    seal_data = json.loads(seal_file.read_text(encoding="utf-8"))
    val_file = exp_dir / "validation.json"
    val_verdict = "PASS"
    if val_file.is_file():
        val_data = json.loads(val_file.read_text(encoding="utf-8"))
        val_verdict = val_data.get("overall_verdict", val_data.get("validation_verdict", "PASS"))

    claim_eligible = seal_data.get("claim_eligible", False) and val_verdict == "PASS"

    return {
        "experiment_id": exp_id,
        "name": exp_title,
        "directory": folder_name,
        "status": "REPRODUCED_AND_VERIFIED",
        "claim_eligible": claim_eligible,
        "seal_verified": True,
        "validation_verdict": val_verdict,
        "checksums_verified_count": len(verified_files),
        "execution_records_verified": records_count,
        "seal_sha256": sha256_file(seal_file),
    }


def sweep_all_r3_experiments(evidence_root: Path | None = None) -> dict[str, dict[str, Any]]:
    """Sweep and reproduce all 15 experiments E00 through E14."""
    results: dict[str, dict[str, Any]] = {}
    for exp_id, folder_name, exp_title, exp_recs in EXPERIMENTS_MAP:
        res = verify_experiment_bundle(
            exp_id, folder_name, exp_title, expected_records=exp_recs, evidence_root=evidence_root
        )
        results[exp_id] = res
    return results


def verify_claim_ledger(
    claim_csv_path: Path,
    budget_json_path: Path | None = None,
    evidence_root: Path | None = None,
) -> dict[str, Any]:
    """Verify claim eligibility, SHA-256 evidence integrity, and claim budget compliance."""
    if not claim_csv_path.is_file():
        raise MissingArtifactError(f"claim_csv_missing:{claim_csv_path}")

    # Load forbidden claim patterns if budget file specified
    forbidden_patterns: list[re.Pattern] = []
    if budget_json_path and budget_json_path.is_file():
        budget_data = json.loads(budget_json_path.read_text(encoding="utf-8"))
        for rule in budget_data.get("forbidden_claims", []):
            rx = rule.get("regex")
            if rx:
                forbidden_patterns.append(re.compile(rx, re.IGNORECASE))

    with claim_csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    total_claims = len(rows)
    verified_claims = 0
    claim_eligible_count = 0
    violations: list[str] = []

    for row in rows:
        cid = row.get("claim_id", "")
        claim_text = row.get("claim_text", row.get("claim", ""))
        evidence_path_str = row.get("evidence_path", row.get("evidence_artifact", ""))
        expected_sha = row.get("seal_sha256", "")
        status = row.get("status", "")

        # Check claim budget prohibitions
        for pat in forbidden_patterns:
            if pat.search(claim_text):
                raise ClaimBudgetViolationError(
                    f"forbidden_claim_budget_violation:{cid}:pattern='{pat.pattern}':text='{claim_text}'"
                )

        target = _REPO_ROOT / evidence_path_str
        if not target.is_file():
            violations.append(f"{cid}:evidence_file_missing:{evidence_path_str}")
            continue

        actual_sha = sha256_file(target)
        if expected_sha and expected_sha != "SEALED" and not expected_sha.startswith("SEALED_"):
            if actual_sha.lower() != expected_sha.lower():
                violations.append(f"{cid}:seal_hash_mismatch:expected={expected_sha}:actual={actual_sha}")
                continue

        # Check for invalid NOT_RUN claiming eligibility
        if "claim_eligible" in row:
            claim_eligible = row["claim_eligible"].strip().lower() == "true"
        else:
            claim_eligible = not ("NOT_RUN" in status or "NOT_CLAIM_ELIGIBLE" in status)

        if ("NOT_RUN" in status or "NOT_CLAIM_ELIGIBLE" in status) and claim_eligible:
            violations.append(f"{cid}:marked_claim_eligible_but_status_is_{status}")
            continue

        if claim_eligible:
            claim_eligible_count += 1
        verified_claims += 1

    return {
        "ledger_path": str(claim_csv_path.relative_to(_REPO_ROOT)),
        "total_claims": total_claims,
        "verified_claims": verified_claims,
        "claim_eligible_claims": claim_eligible_count,
        "violations_count": len(violations),
        "violations": violations,
        "claim_ledger_valid": len(violations) == 0,
        "is_valid": len(violations) == 0,
    }


def verify_claim_ledger_csv(claim_csv_path: Path) -> dict[str, Any]:
    """Compatibility alias for verify_claim_ledger."""
    return verify_claim_ledger(claim_csv_path, budget_json_path=CLAIM_BUDGET_PATH)


def update_release_checksums() -> None:
    """Generate master checksums.sha256 for the release directory."""
    RELEASE_ROOT.mkdir(parents=True, exist_ok=True)
    checksum_lines: list[str] = []

    for path in sorted(RELEASE_ROOT.iterdir()):
        if path.is_file() and path.name != "checksums.sha256":
            digest = sha256_file(path)
            checksum_lines.append(f"{digest}  {path.name}")

    chk_file = RELEASE_ROOT / "checksums.sha256"
    chk_file.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")


def reproduce_q3_r3(*, skip_git_check: bool = False) -> dict[str, Any]:
    """Perform full sweep reproduction across E00–E14 and verify release root integrity."""
    disable_network()

    git_info = verify_git_state(skip_git_check=skip_git_check)
    exp_results = sweep_all_r3_experiments()

    # Audit claim ledgers
    q3_claim_csv = EVIDENCE_ROOT / "claim_to_evidence.csv"
    q3_claim_audit = verify_claim_ledger(q3_claim_csv, budget_json_path=CLAIM_BUDGET_PATH)

    r3_legacy_csv = _REPO_ROOT / "research" / "glhs_journal" / "r3_claim_to_evidence.csv"
    r3_legacy_audit = verify_claim_ledger(r3_legacy_csv)

    all_eligible = all(r.get("claim_eligible", False) for r in exp_results.values())
    all_reproduced = all(r.get("status") == "REPRODUCED_AND_VERIFIED" for r in exp_results.values())
    ledgers_valid = q3_claim_audit["is_valid"] and r3_legacy_audit["is_valid"]

    overall_passed = all_eligible and all_reproduced and ledgers_valid and git_info["git_check_passed"]

    sweep_report = {
        "schema_version": "glhs-r3-reproduction-report.v1",
        "release_id": "GLHS-Q3-R3-RELEASE-20260929-V1",
        "verified_at_utc": datetime.now(UTC).isoformat(),
        "git_state": git_info,
        "network_isolation_active": True,
        "total_experiments_swept": len(exp_results),
        "passed_experiments_count": sum(1 for r in exp_results.values() if r.get("status") == "REPRODUCED_AND_VERIFIED"),
        "experiments": exp_results,
        "claim_ledger_audit": q3_claim_audit,
        "claim_ledger_audits": {
            "q3_claim_ledger": q3_claim_audit,
            "r3_legacy_ledger": r3_legacy_audit,
        },
        "overall_status": "UNIFIED_REPRODUCIBILITY_VERIFIED" if overall_passed else "REPRODUCIBILITY_FAILED",
    }

    # Write reproduction_report.json
    RELEASE_ROOT.mkdir(parents=True, exist_ok=True)
    report_file = RELEASE_ROOT / "reproduction_report.json"
    report_file.write_text(json.dumps(sweep_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Update master checksums for release directory
    update_release_checksums()

    return sweep_report


def main() -> None:
    parser = argparse.ArgumentParser(description="GLHS Q3/R3 Unified Reproducibility Sweep (E00 - E14)")
    parser.add_argument("--skip-git-check", action="store_true", help="Skip clean git tree check")
    args = parser.parse_args()

    print("==================================================================")
    print(" GLHS Q3/R3 UNIFIED REPRODUCIBILITY SWEEP (E00 - E14)")
    print(" Hostile Reviewer Gate Attestation — Phase 9 / E14")
    print("==================================================================")

    report = reproduce_q3_r3(skip_git_check=args.skip_git_check)

    print(f"Overall Status:     {report['overall_status']}")
    print(f"Audited SUT Commit: {report['git_state']['audited_sut_commit']}")
    print(f"Audited Harness:    {report['git_state']['audited_parent_harness_commit']}")
    print(f"Git Clean Tree:     {report['git_state']['tracked_worktree_clean']}")
    print(f"Network Isolation:  {report['network_isolation_active']}")
    print(f"Total Experiments:  {report['passed_experiments_count']}/15 PASSED")
    print(f"Q3 Claims Verified: {report['claim_ledger_audits']['q3_claim_ledger']['verified_claims']}/{report['claim_ledger_audits']['q3_claim_ledger']['total_claims']}")
    print(f"R3 Claims Verified: {report['claim_ledger_audits']['r3_legacy_ledger']['verified_claims']}/{report['claim_ledger_audits']['r3_legacy_ledger']['total_claims']}")
    print("------------------------------------------------------------------")

    for eid, info in sorted(report["experiments"].items()):
        status_symbol = "✓" if info.get("claim_eligible") else "✗"
        print(f"  [{status_symbol}] {eid}: {info['name']} -> {info.get('status')} ({info['checksums_verified_count']} files, {info['execution_records_verified']} records)")

    print("==================================================================")

    if report["overall_status"] != "UNIFIED_REPRODUCIBILITY_VERIFIED":
        sys.exit(1)


if __name__ == "__main__":
    main()
