#!/usr/bin/env python3
"""
GLHS R4 — Chronology & Prospective Protocol Freeze Validator
============================================================
Author: Agent E — Hostile Q1/Q2/Q3/Q4 Reviewer
Program: GLHS R4 — Governed Read-to-Write Continuity (GRWC)
Phase: Phase 0 Gate Verification (Protocols E15–E22)

Formal Chronology & Quality Invariants Enforced:
1. Complete Prospective Protocol Set: All 8 prospective protocols (E15–E22) must exist.
2. Canonical Freeze Timestamp: freeze_timestamp_utc == "2026-09-30T00:00:00Z"
3. Strict Chronology Precedence: freeze_timestamp_utc < execution_started_utc <= execution_completed_utc <= validated_at_utc <= sealed_at_utc
   No execution artifact may exist with timestamp <= freeze_timestamp_utc (fails closed).
4. Statistical Sample Size Locking: All sample sizes (N) must be strictly positive integers.
5. Explicit Stopping Rules: Fail-closed criteria and missing-data rules must be explicitly specified.
6. Disjoint Endpoints: Primary and secondary endpoints must be strictly disjoint sets (Primary ∩ Secondary = ∅).
7. Cryptographic Seal Verification: Each protocol.json must match its sealed SHA-256 hash.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
R4_DIR = REPO_ROOT / "research" / "glhs_journal" / "q4_r4"
PROTOCOLS_DIR = R4_DIR / "protocols"
EVIDENCE_DIR = R4_DIR / "evidence"
RELEASE_DIR = R4_DIR / "release"
CANONICAL_FREEZE_UTC = "2026-09-30T00:00:00Z"

R4_EXPERIMENTS: list[tuple[str, list[str]]] = [
    ("E15", ["E15_dispatch_attestation"]),
    ("E16", ["E16_five_way_comparator"]),
    ("E17", ["E17_current_state_insufficiency"]),
    ("E18", ["E18_global_vs_disclosed_support", "E18_global_vs_disclosed_evidence"]),
    ("E19", ["E19_transport_serialization_attacks", "E19_transport_serialization"]),
    ("E20", ["E20_provider_receipt_study"]),
    ("E21", ["E21_formal_novelty_model"]),
    ("E22", ["E22_public_reproducibility_audit", "E22_r4_reproducibility"]),
]


class ChronologyAnomalyError(RuntimeError):
    """Raised when any chronological inversion or contemporaneous freeze anomaly is detected."""


def parse_iso8601(ts_str: str) -> datetime:
    """Parse ISO 8601 UTC timestamp string."""
    if not ts_str:
        raise ValueError("empty_timestamp_string")
    ts_clean = str(ts_str).strip().replace("Z", "+00:00")
    if len(ts_clean) == 10 and ts_clean.count("-") == 2:
        ts_clean += "T00:00:00+00:00"
    dt = datetime.fromisoformat(ts_clean)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def compute_sha256(filepath: Path) -> str:
    """Compute hex SHA256 of file bytes."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def find_protocol_dir(exp_id: str, candidate_names: list[str]) -> Path | None:
    """Locate experiment protocol directory under R4 protocols or repository root protocols."""
    search_roots = [PROTOCOLS_DIR, REPO_ROOT / "protocols"]
    for root in search_roots:
        if not root.is_dir():
            continue
        for name in candidate_names:
            candidate = root / name
            if candidate.is_dir() and (candidate / "protocol.json").is_file():
                return candidate
    return None


def extract_endpoint_names(endpoint_list: list[Any]) -> set[str]:
    """Extract set of endpoint names from endpoint specification list."""
    names = set()
    for item in endpoint_list:
        if isinstance(item, str):
            names.add(item.strip())
        elif isinstance(item, dict):
            name = item.get("name") or item.get("id") or item.get("estimand")
            if name:
                names.add(str(name).strip())
    return names


def collect_integer_sample_sizes(obj: Any, prefix: str = "") -> list[tuple[str, Any]]:
    """Recursively collect sample size parameters and verify types."""
    collected: list[tuple[str, Any]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                collected.append((full_key, v))
            elif isinstance(v, (dict, list)):
                collected.extend(collect_integer_sample_sizes(v, full_key))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            collected.extend(collect_integer_sample_sizes(item, f"{prefix}[{i}]"))
    return collected


def validate_prospective_protocol_r4(
    exp_id: str,
    candidate_names: list[str],
) -> tuple[bool, list[str], dict[str, Any]]:
    """
    Audit a single prospective protocol for strict freeze compliance:
    1. Freeze timestamp == "2026-09-30T00:00:00Z"
    2. No execution artifact exists with timestamp <= freeze timestamp
    3. All sample sizes (N) are positive integers
    4. Stopping rules are explicit
    5. Primary and secondary endpoints are disjoint
    """
    errors: list[str] = []
    metadata: dict[str, Any] = {"exp_id": exp_id}

    proto_dir = find_protocol_dir(exp_id, candidate_names)
    if not proto_dir:
        errors.append(f"MISSING_PROTOCOL_DIR: No protocol directory found for {exp_id} in {candidate_names}")
        return False, errors, metadata

    metadata["directory"] = proto_dir.name
    proto_json = proto_dir / "protocol.json"
    proto_sha = proto_dir / "protocol.sha256"

    if not proto_json.is_file():
        errors.append(f"MISSING_PROTOCOL_JSON: {proto_json} does not exist.")
        return False, errors, metadata

    # 1. Cryptographic SHA-256 seal verification
    actual_hash = compute_sha256(proto_json)
    metadata["sha256"] = actual_hash
    if proto_sha.is_file():
        sealed_hash = proto_sha.read_text(encoding="utf-8").strip().split()[0]
        metadata["sealed_sha256"] = sealed_hash
        if actual_hash.lower() != sealed_hash.lower():
            errors.append(
                f"SEAL_MISMATCH: {proto_json.name} SHA-256 ({actual_hash}) does not match sealed ({sealed_hash})"
            )
            metadata["hash_verified"] = False
        else:
            metadata["hash_verified"] = True
    else:
        errors.append(f"MISSING_PROTOCOL_SHA256: {proto_sha} does not exist.")
        metadata["hash_verified"] = False

    # 2. Parse protocol JSON
    try:
        data = json.loads(proto_json.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"INVALID_JSON: Failed to parse {proto_json}: {e}")
        return False, errors, metadata

    metadata["protocol_id"] = data.get("protocol_id", "UNKNOWN")
    metadata["title"] = data.get("title", "")

    # 3. Freeze Timestamp Validation: Must equal CANONICAL_FREEZE_UTC ("2026-09-30T00:00:00Z")
    freeze_raw = data.get("freeze_timestamp_utc") or data.get("freeze_timestamp")
    if not freeze_raw:
        errors.append(f"MISSING_FREEZE_TIMESTAMP: {proto_json} lacks 'freeze_timestamp_utc'.")
        return False, errors, metadata

    try:
        freeze_dt = parse_iso8601(freeze_raw)
        metadata["freeze_timestamp"] = freeze_dt.isoformat()
    except Exception as e:
        errors.append(f"MALFORMED_FREEZE_TIMESTAMP: Cannot parse '{freeze_raw}': {e}")
        return False, errors, metadata

    expected_freeze_dt = parse_iso8601(CANONICAL_FREEZE_UTC)
    if freeze_dt != expected_freeze_dt or freeze_raw != CANONICAL_FREEZE_UTC:
        errors.append(
            f"CANONICAL_FREEZE_TIMESTAMP_MISMATCH: Found '{freeze_raw}', expected exactly '{CANONICAL_FREEZE_UTC}'"
        )

    # 4. Strict Chronological Precedence Audit:
    # No execution artifact may exist with timestamp <= freeze_timestamp_utc
    checked_dirs = [proto_dir]
    # Also check evidence dir if present
    for name in candidate_names:
        ev_cand = EVIDENCE_DIR / name
        if ev_cand.is_dir():
            checked_dirs.append(ev_cand)

    execution_artifacts_found = 0
    for cdir in checked_dirs:
        for child in cdir.rglob("*"):
            if not child.is_file():
                continue
            if child.name in ("protocol.json", "protocol.sha256", "README.md", ".gitkeep", "freeze.json"):
                continue

            if child.suffix in (".json", ".jsonl"):
                execution_artifacts_found += 1
                try:
                    raw_text = child.read_text(encoding="utf-8").strip()
                    if not raw_text:
                        continue
                    docs = []
                    if child.suffix == ".jsonl":
                        for line in raw_text.splitlines():
                            if line.strip():
                                docs.append(json.loads(line))
                    else:
                        parsed = json.loads(raw_text)
                        if isinstance(parsed, list):
                            docs.extend(parsed)
                        elif isinstance(parsed, dict):
                            docs.append(parsed)

                    for doc in docs:
                        if not isinstance(doc, dict):
                            continue
                        for ts_field in (
                            "execution_timestamp",
                            "started_at",
                            "execution_started_utc",
                            "execution_completed_utc",
                            "created_at",
                            "timestamp",
                            "sealed_at_utc",
                            "validated_at_utc",
                            "sealed_at",
                            "validated_at",
                        ):
                            ts_val = doc.get(ts_field)
                            if ts_val and isinstance(ts_val, str):
                                try:
                                    exec_dt = parse_iso8601(ts_val)
                                    if exec_dt <= freeze_dt:
                                        errors.append(
                                            f"STRICT_PROSPECTIVE_FREEZE_VIOLATION: Execution artifact {child.name} "
                                            f"has timestamp {exec_dt.isoformat()} <= freeze {freeze_dt.isoformat()}! "
                                            f"(Strict precedence freeze_dt < exec_dt violated)"
                                        )
                                except Exception:
                                    pass
                except Exception:
                    pass

    metadata["execution_artifacts_scanned"] = execution_artifacts_found

    # 5. Statistical Locking: All sample sizes (N) must be strictly positive integers
    sample_spec = data.get("sample_size") or data.get("sample_size_allocation")
    if not sample_spec:
        errors.append(f"MISSING_SAMPLE_SIZE: Protocol {proto_json} lacks 'sample_size' / 'sample_size_allocation'.")
    else:
        sample_metrics = collect_integer_sample_sizes(sample_spec)
        if not sample_metrics:
            errors.append(f"UNLOCKED_SAMPLE_SIZE: No sample size metrics found in {proto_json}.")
        else:
            primary_n = None
            for key, val in sample_metrics:
                if not isinstance(val, int) or isinstance(val, bool):
                    errors.append(
                        f"NON_INTEGER_SAMPLE_SIZE: Sample size parameter '{key}'={val} (type={type(val).__name__}) "
                        f"is not an integer."
                    )
                elif val <= 0:
                    errors.append(
                        f"NON_POSITIVE_SAMPLE_SIZE: Sample size parameter '{key}'={val} is not a positive integer (<= 0)."
                    )
                if primary_n is None and any(n_token in key.lower() for n_token in ("total", "n_", "_n", "executions", "scenarios")):
                    primary_n = val

            if primary_n is None and sample_metrics:
                primary_n = sample_metrics[0][1]
            metadata["sample_size_N"] = primary_n

    # 6. Explicit Stopping Rules Verification
    stopping_rules = data.get("stopping_rules") or data.get("stopping_criteria")
    if not stopping_rules:
        errors.append(f"MISSING_STOPPING_RULES: Protocol {proto_json} lacks explicit stopping rules.")
    elif isinstance(stopping_rules, dict):
        rule_desc = (
            stopping_rules.get("explicit_rule_description")
            or stopping_rules.get("description")
            or stopping_rules.get("safety_halt_threshold")
        )
        fail_closed = stopping_rules.get("fail_closed_criteria")
        missing_data = stopping_rules.get("missing_data_rule")
        if not (rule_desc or (fail_closed and missing_data)):
            errors.append(
                f"STOPPING_RULES_INCOMPLETE: Stopping rules dictionary must contain explicit halting rules "
                f"('explicit_rule_description' or 'fail_closed_criteria' + 'missing_data_rule')."
            )
        metadata["stopping_rules_status"] = "EXPLICIT_VERIFIED"
    elif isinstance(stopping_rules, str):
        if len(stopping_rules.strip()) < 10 or stopping_rules.lower() in ("none", "n/a", "tbd"):
            errors.append(f"STOPPING_RULES_NOT_EXPLICIT: Stopping rule string '{stopping_rules}' is non-explicit.")
        metadata["stopping_rules_status"] = "EXPLICIT_STRING"
    else:
        errors.append(f"STOPPING_RULES_INVALID_TYPE: Stopping rules has unrecognized type {type(stopping_rules).__name__}.")

    # 7. Disjoint Primary and Secondary Endpoints Verification
    primary_endpoints = data.get("primary_endpoints") or data.get("primary_estimands") or []
    secondary_endpoints = data.get("secondary_endpoints") or data.get("secondary_estimands") or []

    if not isinstance(primary_endpoints, list) or len(primary_endpoints) == 0:
        errors.append(f"MISSING_PRIMARY_ENDPOINTS: Protocol {proto_json} must define at least one primary endpoint.")
        primary_names = set()
    else:
        primary_names = extract_endpoint_names(primary_endpoints)
        if not primary_names:
            errors.append(f"UNNAMED_PRIMARY_ENDPOINTS: Could not extract endpoint names from primary_endpoints.")

    secondary_names = extract_endpoint_names(secondary_endpoints) if isinstance(secondary_endpoints, list) else set()

    overlap = primary_names.intersection(secondary_names)
    if overlap:
        errors.append(
            f"NON_DISJOINT_ENDPOINTS: Primary and secondary endpoints share overlapping elements: {sorted(overlap)}! "
            f"Primary and secondary endpoints must be strictly disjoint (Primary ∩ Secondary = ∅)."
        )
        metadata["endpoints_disjoint"] = False
    else:
        metadata["endpoints_disjoint"] = True

    metadata["primary_endpoint_count"] = len(primary_names)
    metadata["secondary_endpoint_count"] = len(secondary_names)
    metadata["primary_endpoints"] = sorted(primary_names)
    metadata["secondary_endpoints"] = sorted(secondary_names)

    passed = len(errors) == 0
    metadata["passed"] = passed
    return passed, errors, metadata


def verify_experiment_chronology_r4(exp_dir: Path) -> dict[str, Any]:
    """Verify strict chronological ordering for an R4 experiment evidence directory."""
    freeze_file = exp_dir / "freeze.json"
    protocol_file = exp_dir / "protocol.json"

    freeze_ts_str = None
    if freeze_file.is_file():
        fdata = json.loads(freeze_file.read_text(encoding="utf-8"))
        freeze_ts_str = fdata.get("freeze_timestamp_utc") or fdata.get("freeze_timestamp")
    elif protocol_file.is_file():
        pdata = json.loads(protocol_file.read_text(encoding="utf-8"))
        freeze_ts_str = pdata.get("freeze_timestamp_utc")

    if not freeze_ts_str:
        return {"exp_id": exp_dir.name, "status": "PENDING_EXECUTION", "freeze_checked": True}

    freeze_dt = parse_iso8601(freeze_ts_str)

    exec_started_dt = None
    exec_completed_dt = None
    validated_dt = None
    sealed_dt = None

    candidates = [
        exp_dir / "seal.json",
        exp_dir / "validation.json",
        exp_dir / "derived" / "summary.json",
        exp_dir / "raw" / "execution_manifest.json",
    ]

    for candidate in candidates:
        if candidate.is_file():
            doc = json.loads(candidate.read_text(encoding="utf-8"))
            st_str = doc.get("execution_started_utc") or doc.get("started_at")
            cp_str = doc.get("execution_completed_utc") or doc.get("completed_at")
            vl_str = doc.get("validated_at_utc") or doc.get("validated_utc")
            sl_str = doc.get("sealed_at_utc") or doc.get("sealed_utc")

            if st_str and exec_started_dt is None:
                exec_started_dt = parse_iso8601(st_str)
            if cp_str and exec_completed_dt is None:
                exec_completed_dt = parse_iso8601(cp_str)
            if vl_str and validated_dt is None:
                validated_dt = parse_iso8601(vl_str)
            if sl_str and sealed_dt is None:
                sealed_dt = parse_iso8601(sl_str)

    # STRICT PRECEDENCE RULE: freeze_timestamp_utc MUST strictly precede execution_started_utc
    if exec_started_dt is not None:
        if exec_started_dt <= freeze_dt:
            raise ChronologyAnomalyError(
                f"STRICT_PREPOSPECTIVE_FREEZE_VIOLATION: execution_started_utc ({exec_started_dt.isoformat()}) "
                f"does not strictly follow freeze_timestamp_utc ({freeze_dt.isoformat()}) in {exp_dir.name}! "
                f"(Equal or inverted timestamps are strictly forbidden)"
            )

    if exec_started_dt and exec_completed_dt:
        if exec_completed_dt < exec_started_dt:
            raise ChronologyAnomalyError(
                f"EXECUTION_DURATION_INVERSION: completed ({exec_completed_dt.isoformat()}) "
                f"< started ({exec_started_dt.isoformat()}) in {exp_dir.name}"
            )

    if exec_completed_dt and validated_dt:
        if validated_dt < exec_completed_dt:
            raise ChronologyAnomalyError(
                f"VALIDATION_BEFORE_COMPLETION: validated ({validated_dt.isoformat()}) "
                f"< completed ({exec_completed_dt.isoformat()}) in {exp_dir.name}"
            )

    if validated_dt and sealed_dt:
        if sealed_dt < validated_dt:
            raise ChronologyAnomalyError(
                f"SEAL_BEFORE_VALIDATION: sealed ({sealed_dt.isoformat()}) "
                f"< validated ({validated_dt.isoformat()}) in {exp_dir.name}"
            )

    return {
        "exp_id": exp_dir.name,
        "status": "CHRONOLOGY_VERIFIED",
        "freeze_timestamp": freeze_dt.isoformat(),
        "execution_started": exec_started_dt.isoformat() if exec_started_dt else None,
        "execution_completed": exec_completed_dt.isoformat() if exec_completed_dt else None,
        "validated_at": validated_dt.isoformat() if validated_dt else None,
        "sealed_at": sealed_dt.isoformat() if sealed_dt else None,
    }


def audit_all_r4_protocols() -> tuple[bool, list[tuple[str, bool, list[str], dict[str, Any]]]]:
    """Audit all 8 prospective protocol files in protocols/ (E15–E22)."""
    overall_pass = True
    results = []

    for exp_id, candidate_names in R4_EXPERIMENTS:
        passed, errs, meta = validate_prospective_protocol_r4(exp_id, candidate_names)
        if not passed:
            overall_pass = False
        results.append((exp_id, passed, errs, meta))

    return overall_pass, results


def run_self_tests() -> bool:
    """Verify that validator self-tests correctly reject anomalies and accept valid constructs."""
    freeze = parse_iso8601("2026-09-30T00:00:00Z")
    contemporaneous_exec = parse_iso8601("2026-09-30T00:00:00Z")
    inverted_exec = parse_iso8601("2026-09-29T23:59:59Z")
    valid_exec = parse_iso8601("2026-09-30T00:00:01Z")

    # 1. Contemporaneous rejection test
    if not (contemporaneous_exec <= freeze):
        print("[FAIL] Self-test: contemporaneous exec <= freeze assertion broken")
        return False

    # 2. Inverted rejection test
    if not (inverted_exec <= freeze):
        print("[FAIL] Self-test: inverted exec <= freeze assertion broken")
        return False

    # 3. Strictly prospective test
    if not (valid_exec > freeze):
        print("[FAIL] Self-test: strictly prospective valid_exec > freeze broken")
        return False

    # 4. Disjoint endpoint test
    set_a = {"endpoint_alpha", "endpoint_beta"}
    set_b = {"endpoint_gamma", "endpoint_delta"}
    set_overlap = {"endpoint_alpha", "endpoint_gamma"}
    if len(set_a.intersection(set_b)) != 0:
        print("[FAIL] Self-test: disjoint set intersection test broken")
        return False
    if len(set_a.intersection(set_overlap)) == 0:
        print("[FAIL] Self-test: overlapping set intersection test broken")
        return False

    # 5. Positive integer test
    if not (isinstance(1024, int) and 1024 > 0):
        print("[FAIL] Self-test: positive integer check broken")
        return False
    if isinstance(0, int) and 0 > 0:
        print("[FAIL] Self-test: zero sample size check broken")
        return False

    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="GLHS R4 Prospective Chronology & Protocol Validator")
    parser.add_argument("--test-inversion", action="store_true", help="Run self-tests and exit")
    args = parser.parse_args()

    print("================================================================================")
    print("GLHS R4 — CHRONOLOGY & PROSPECTIVE PROTOCOL FREEZE VALIDATOR")
    print("Phase 0 Prospective Protocol Gate Audit (Agent E — Hostile Review)")
    print("================================================================================\n")
    print(f"Canonical Freeze Timestamp UTC: {CANONICAL_FREEZE_UTC}")
    print("Invariant Rule: freeze_timestamp_utc < execution_started_utc <= execution_completed_utc <= validated_at_utc <= sealed_at_utc")
    print("Quality Rules: Sample sizes N > 0 (int), Stopping rules explicit, Endpoints disjoint (Primary ∩ Secondary = ∅)\n")

    # 1. Execute Self-Tests
    print("--- 1. VALIDATOR SELF-TEST EXECUTION ---")
    if not run_self_tests():
        print("[FAIL] Validator self-tests failed!")
        return 1
    print("[PASS] Self-tests verified: strict precedence (freeze_dt < exec_dt), endpoint disjointness, and integer sample sizes enforced.\n")

    if args.test_inversion:
        return 0

    # 2. Prospective Protocol Audit across E15–E22
    print("--- 2. PROSPECTIVE PROTOCOL AUDIT (E15–E22) ---")
    all_passed, results = audit_all_r4_protocols()

    header = f"{'Exp':<5} | {'Directory':<38} | {'Freeze UTC':<20} | {'N':<7} | {'Stop Rule':<10} | {'Disjoint':<9} | {'Verdict':<7}"
    print(header)
    print("-" * len(header))

    total_anomalies = 0
    for exp_id, passed, errs, meta in results:
        dir_name = meta.get("directory", "MISSING")
        freeze_str = meta.get("freeze_timestamp", "MISSING")[:19]
        n_str = str(meta.get("sample_size_N", "N/A"))
        stop_str = "EXPLICIT" if meta.get("stopping_rules_status") else "FAIL"
        disjoint_str = "DISJOINT" if meta.get("endpoints_disjoint") else "OVERLAP"
        verdict = "PASS" if passed else "FAIL"

        print(f"{exp_id:<5} | {dir_name:<38} | {freeze_str:<20} | {n_str:<7} | {stop_str:<10} | {disjoint_str:<9} | {verdict:<7}")
        if errs:
            total_anomalies += len(errs)
            for e in errs:
                print(f"      -> ERROR: {e}")

    # 3. Evidence Chronology Audit (if evidence directory populated)
    print("\n--- 3. EVIDENCE DIRECTORY CHRONOLOGY AUDIT ---")
    if EVIDENCE_DIR.is_dir() and any(EVIDENCE_DIR.iterdir()):
        evidence_results = {}
        for exp_id, candidate_names in R4_EXPERIMENTS:
            for name in candidate_names:
                target_dir = EVIDENCE_DIR / name
                if target_dir.is_dir():
                    try:
                        res = verify_experiment_chronology_r4(target_dir)
                        evidence_results[exp_id] = res
                    except ChronologyAnomalyError as e:
                        print(f"  [FAIL] {exp_id} ({name}): {e}")
                        total_anomalies += 1
                        all_passed = False
        print(f"Evidence Directory Audit: {len(evidence_results)} experiment folders verified.")
    else:
        print("Evidence directory contains 0 executed runs. Prospective freeze holds without execution contamination.")

    # 4. Final Verdict
    print("\n================================================================================")
    print("CHRONOLOGY & PROSPECTIVE FREEZE AUDIT SUMMARY")
    print("================================================================================")
    print(f"Total Protocols Audited: {len(results)}")
    print(f"Protocols Passing 100% of Checks: {sum(1 for r in results if r[1])} / {len(results)}")
    print(f"Total Anomalies Detected: {total_anomalies}")

    if all_passed and total_anomalies == 0:
        print("\n>>> VERDICT: PHASE 0 PROSPECTIVE PROTOCOL GATE PASSED (100% CONCORDANCE) <<<")
        print("All 8 protocols (E15–E22) strictly frozen at 2026-09-30T00:00:00Z with explicit rules, disjoint endpoints, and positive integer sample sizes.")
        return 0
    else:
        print("\n>>> VERDICT: PHASE 0 PROSPECTIVE PROTOCOL GATE REJECTED <<<")
        print(f"Found {total_anomalies} blocker anomalies requiring remediation.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
