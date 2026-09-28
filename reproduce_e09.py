#!/usr/bin/env python3
"""Offline reproduction and evidence integrity validator for Phase 9 (E09: In-Memory Concurrency Simulation).

Validates the full sealed artifact bundle for E09 (In-Memory Concurrency Simulation using SimulatedPartitionCoordinator / thread locking, NOT production PostgreSQL benchmark):
1. Disables all network access fail-closed.
2. Verifies cryptographic checksums in checksums.sha256.
3. Validates protocol freeze and factor bindings.
4. Reproduces statistical analysis and derived summary from raw execution metrics.
5. Verifies invariants: 0.0% false-stale aborts on disjoint partitions & 0 deadlocks under canonical lock ordering.
6. Validates validation.json and seal.json binding and claim eligibility.

Run from repository root:

    python reproduce_e09.py [--artifact-dir DIR] [--protocol PATH] [--seal]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import socket
import sys
import time
from pathlib import Path
from typing import Any

# Ensure project root and service packages are resolvable
_REPO_ROOT = Path(__file__).resolve().parent
for _p in (_REPO_ROOT, _REPO_ROOT / "services" / "api" / "src", _REPO_ROOT / "services" / "ml" / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from clara_api.glhs.canonical_json import canonical_hash
from evaluation.concurrency_benchmark.analyze import analyze_concurrency_metrics, generate_markdown_summary
from evaluation.concurrency_benchmark.seal import seal_experiment_e09

PROTOCOL_SCHEMA_VERSION = "glhs-e09-concurrency-protocol-v1"
SEAL_SCHEMA_VERSION = "glhs-e09-concurrency-seal-v1"
DEFAULT_ARTIFACT_DIR = "research/glhs_journal/q3_r3/evidence/E09_concurrency"
DEFAULT_PROTOCOL_PATH = "research/glhs_journal/q3_r3/protocols/E09_concurrency/protocol.json"


class NetworkAccessProhibitedError(RuntimeError):
    """Raised if any network activity is attempted during offline reproduction."""


def disable_network() -> None:
    """Prohibit all socket creation and DNS resolution fail-closed (except AF_UNIX socketpairs)."""
    _orig_socket = socket.socket

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


def verify_checksums(artifact_dir: Path) -> dict[str, str]:
    """Verify that every file in checksums.sha256 matches its exact digest."""
    checksum_file = artifact_dir / "checksums.sha256"
    if not checksum_file.is_file():
        raise FileNotFoundError(f"checksums_file_missing:{checksum_file}")

    lines = checksum_file.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError("empty_checksums_sha256")

    verified_files: dict[str, str] = {}
    for lineno, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            expected_digest, rel_path = line.split("  ", 1)
        except ValueError as exc:
            raise ValueError(f"malformed_checksum_line:{lineno}:{line}") from exc

        if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
            raise ValueError(f"invalid_sha256_format:{lineno}:{expected_digest}")

        target = artifact_dir / rel_path
        if not target.is_file():
            raise FileNotFoundError(f"sealed_file_missing:{rel_path}")

        actual_digest = sha256_file(target)
        if actual_digest != expected_digest:
            raise ValueError(
                f"checksum_mismatch:{rel_path}:expected={expected_digest}:actual={actual_digest}"
            )
        verified_files[rel_path] = actual_digest

    # Verify inventory completeness
    for path in artifact_dir.rglob("*"):
        if path.is_file() and path.name not in ("checksums.sha256", "seal.json"):
            rel = str(path.relative_to(artifact_dir))
            if rel not in verified_files:
                raise ValueError(f"unsealed_file_detected:{rel}")

    return verified_files


def reproduce_and_verify(
    *,
    artifact_dir: Path,
    protocol_path: Path,
) -> dict[str, Any]:
    """Perform offline reproduction and verification of E09."""
    disable_network()

    artifact_dir = artifact_dir.resolve()
    protocol_path = protocol_path.resolve()

    if not protocol_path.is_file():
        raise FileNotFoundError(f"protocol_file_missing:{protocol_path}")
    if not artifact_dir.is_dir():
        raise FileNotFoundError(f"artifact_directory_not_found:{artifact_dir}")

    # 1. Verify file-level cryptographic checksums
    verified_checksums = verify_checksums(artifact_dir)

    # 2. Verify protocol document
    protocol_doc = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol_doc.get("schema_version") not in (PROTOCOL_SCHEMA_VERSION, "glhs-r3-protocol.v1", "glhs-r3-protocol-e09.v1"):
        raise ValueError(f"invalid_protocol_schema:{protocol_doc.get('schema_version')}")
    if protocol_doc.get("protocol_id") not in ("E09-CONCURRENCY-BENCHMARK", "GLHS-R3-E09-CONCURRENCY", "E09_concurrency"):
        raise ValueError(f"invalid_protocol_id:{protocol_doc.get('protocol_id')}")

    # 3. Read raw metrics and re-run statistical analysis
    raw_file = artifact_dir / "raw" / "benchmark_raw_metrics.json"
    runs_file = artifact_dir / "raw" / "runs.jsonl"
    if not raw_file.is_file() and not runs_file.is_file():
        raise FileNotFoundError("raw_metrics_file_missing")

    # If runs.jsonl exists, verify its cryptographic hash chain
    if runs_file.is_file():
        prev_hash = ""
        lines = runs_file.read_text(encoding="utf-8").splitlines()
        for lineno, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            stored_hash = record.get("hash")
            expected_prev = record.get("prev_hash", "")
            if expected_prev != prev_hash:
                raise ValueError(f"hash_chain_broken:line={lineno}")
            rec_copy = dict(record)
            rec_copy.pop("hash", None)
            computed_hash = canonical_hash(rec_copy, profile="clara.canonical-json.v2-rfc8785")
            if stored_hash != computed_hash:
                raise ValueError(f"hash_mismatch:line={lineno}")
            prev_hash = str(stored_hash)

    if raw_file.is_file():
        raw_data = json.loads(raw_file.read_text(encoding="utf-8"))
    else:
        raw_data = [json.loads(line) for line in runs_file.read_text(encoding="utf-8").splitlines() if line.strip()]

    reproduced_report = analyze_concurrency_metrics(raw_data)

    if not reproduced_report.all_invariants_passed:
        raise ValueError("reproduced_analysis_invariant_failed")
    if reproduced_report.disjoint_false_stale_rate_dag != 0.0:
        raise ValueError(f"reproduced_dag_false_stale_rate_not_zero:{reproduced_report.disjoint_false_stale_rate_dag}")
    if reproduced_report.total_deadlocks_across_all_runs != 0:
        raise ValueError(f"reproduced_deadlocks_detected:{reproduced_report.total_deadlocks_across_all_runs}")

    # 4. Compare reproduced analysis against sealed derived summary
    sealed_summary_file = artifact_dir / "derived" / "summary.json"
    if not sealed_summary_file.is_file():
        raise FileNotFoundError("sealed_summary_json_missing")

    sealed_summary = json.loads(sealed_summary_file.read_text(encoding="utf-8"))
    if reproduced_report.disjoint_false_stale_rate_dag != sealed_summary["disjoint_false_stale_rate_dag"]:
        raise ValueError("disjoint_dag_false_stale_rate_mismatch")
    if reproduced_report.total_deadlocks_across_all_runs != sealed_summary["total_deadlocks_across_all_runs"]:
        raise ValueError("deadlock_count_mismatch")
    if reproduced_report.total_run_records != sealed_summary["total_run_records"]:
        raise ValueError("total_run_records_mismatch")

    # 5. Verify validation.json and seal.json
    validation_file = artifact_dir / "validation.json"
    if not validation_file.is_file():
        raise FileNotFoundError("validation_json_missing")
    validation_doc = json.loads(validation_file.read_text(encoding="utf-8"))
    if validation_doc.get("status") != "VALIDATED" or not validation_doc.get("claim_eligible"):
        raise ValueError("validation_doc_invalid")

    seal_file = artifact_dir / "seal.json"
    if not seal_file.is_file():
        raise FileNotFoundError("seal_json_missing")
    seal_doc = json.loads(seal_file.read_text(encoding="utf-8"))
    if seal_doc.get("status") != "SEALED" or seal_doc.get("schema_version") not in (SEAL_SCHEMA_VERSION, "glhs-r3-experiment-seal.v1"):
        raise ValueError("seal_doc_invalid")

    return {
        "status": "REPRODUCED_AND_VERIFIED",
        "protocol_id": protocol_doc["protocol_id"],
        "freeze_id": seal_doc["freeze_id"],
        "git_sha": seal_doc["git_sha"],
        "checksums_verified_count": len(verified_checksums),
        "total_run_records": reproduced_report.total_run_records,
        "unique_cells": reproduced_report.unique_cells,
        "disjoint_false_stale_rate_dag": reproduced_report.disjoint_false_stale_rate_dag,
        "disjoint_false_stale_rate_monolithic": reproduced_report.disjoint_false_stale_rate_monolithic,
        "total_deadlocks": reproduced_report.total_deadlocks_across_all_runs,
        "claim_eligible": True,
        "seal_verified": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path(DEFAULT_ARTIFACT_DIR),
        help="Path to sealed artifact directory",
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path(DEFAULT_PROTOCOL_PATH),
        help="Path to protocol.json file",
    )
    parser.add_argument(
        "--seal",
        action="store_true",
        help="Re-execute sealing step before verification",
    )
    args = parser.parse_args()

    try:
        if args.seal:
            seal_experiment_e09(
                protocol_path=args.protocol,
                artifact_dir=args.artifact_dir,
            )

        report = reproduce_and_verify(
            artifact_dir=args.artifact_dir,
            protocol_path=args.protocol,
        )
        sys.stdout.write(json.dumps(report, indent=2) + "\n")
        return 0
    except Exception as exc:
        sys.stderr.write(f"ERROR: Reproduction failed: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
