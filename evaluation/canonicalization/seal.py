"""SHA-256 seal generator for E07 Canonicalization Conformance benchmark.

Validates vector corpus conformance, cross-runtime determinism with Node.js,
verifies 100% byte equality, and seals artifacts with seal.json and checksums.sha256.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Ensure services/api/src is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_API_SRC = _REPO_ROOT / "services" / "api" / "src"
if str(_API_SRC) not in sys.path:
    sys.path.insert(0, str(_API_SRC))

from evaluation.canonicalization.analyze import analyze_conformance_results
from evaluation.canonicalization.runner import run_conformance_benchmark, sanitize_for_json

SEAL_SCHEMA_VERSION = "canonicalization-seal.v1"


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_sha() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return res.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def generate_environment_manifest(*, git_sha: str) -> dict[str, Any]:
    """Capture execution environment metadata."""
    node_ver = "unknown"
    try:
        res = subprocess.run(["node", "--version"], capture_output=True, text=True, check=False)
        node_ver = res.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass

    return {
        "schema_version": "canonicalization-environment.v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "git_sha": git_sha,
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "node_version": node_ver,
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count() or 1,
    }


def seal_experiment(
    *,
    artifact_dir: Path,
    protocol_path: Path,
    vectors_path: Path,
    expected_path: Path,
    node_script_path: Path,
    run_id: str,
) -> dict[str, Any]:
    """Seal the E07 experiment artifact bundle."""
    artifact_dir = artifact_dir.resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)

    derived_dir = artifact_dir / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)

    raw_dir = artifact_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    git_sha = _git_sha()

    # 1. Read protocol
    protocol_data = json.loads(protocol_path.read_text(encoding="utf-8"))

    # 2. Run benchmark and generate raw execution results
    benchmark_summary = run_conformance_benchmark(
        vectors_path=vectors_path,
        expected_path=expected_path,
        node_script_path=node_script_path,
    )

    # Copy protocol & raw input files
    dest_protocol = artifact_dir / "protocol.json"
    dest_protocol.write_text(json.dumps(protocol_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    dest_vectors = raw_dir / "vectors.json"
    dest_vectors.write_bytes(vectors_path.read_bytes())

    dest_expected = raw_dir / "expected.json"
    dest_expected.write_bytes(expected_path.read_bytes())

    dest_results = raw_dir / "results.jsonl"
    with dest_results.open("w", encoding="utf-8") as handle:
        for res in benchmark_summary["python_results"]:
            handle.write(json.dumps(sanitize_for_json(res), ensure_ascii=False) + "\n")

    # 3. Environment manifest
    env_data = generate_environment_manifest(git_sha=git_sha)
    (artifact_dir / "environment.json").write_text(
        json.dumps(env_data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # 4. Perform analysis & write summary artifacts
    summary_data = analyze_conformance_results(dest_results, dest_protocol, derived_dir)

    if not summary_data["claim_eligible"]:
        raise ValueError(
            f"experiment_not_claim_eligible: byte_equality_rate={summary_data['byte_equality_rate']}, "
            f"python_failed={summary_data['python_v2_failed']}"
        )

    # 5. Validation document
    validation_doc = {
        "schema_version": "canonicalization-validation.v1",
        "validated_at_utc": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "freeze_id": protocol_data.get("freeze_id", "GLHS-CANONICALIZATION-E07-20260928-01"),
        "git_sha": git_sha,
        "total_vectors": summary_data["total_vectors"],
        "python_v2_passed": summary_data["python_v2_passed"],
        "python_v2_failed": summary_data["python_v2_failed"],
        "byte_equality_rate": summary_data["byte_equality_rate"],
        "cross_runtime_determinism": summary_data["cross_runtime_determinism"],
        "claim_eligible": summary_data["claim_eligible"],
        "status": "VALIDATED",
    }
    (artifact_dir / "validation.json").write_text(
        json.dumps(validation_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # 6. Compute checksums
    checksum_lines: list[str] = []
    file_digests: dict[str, str] = {}
    for p in sorted(artifact_dir.rglob("*")):
        if p.is_file() and p.name not in ("checksums.sha256", "seal.json"):
            rel_path = str(p.relative_to(artifact_dir))
            digest = sha256_file(p)
            file_digests[rel_path] = digest
            checksum_lines.append(f"{digest}  {rel_path}")

    (artifact_dir / "checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    # 7. Write seal document
    seal_doc = {
        "schema_version": SEAL_SCHEMA_VERSION,
        "freeze_id": protocol_data.get("freeze_id", "GLHS-CANONICALIZATION-E07-20260928-01"),
        "run_id": run_id,
        "git_sha": git_sha,
        "total_vectors": summary_data["total_vectors"],
        "python_v2_passed": summary_data["python_v2_passed"],
        "python_v2_failed": summary_data["python_v2_failed"],
        "byte_equality_rate": summary_data["byte_equality_rate"],
        "cross_runtime_determinism": summary_data["cross_runtime_determinism"],
        "claim_eligible": summary_data["claim_eligible"],
        "protocol_sha256": sha256_file(dest_protocol),
        "raw_vectors_sha256": sha256_file(dest_vectors),
        "raw_expected_sha256": sha256_file(dest_expected),
        "raw_results_sha256": sha256_file(dest_results),
        "summary_sha256": sha256_file(derived_dir / "summary.json"),
        "validation_sha256": sha256_file(artifact_dir / "validation.json"),
        "artifact_inventory": file_digests,
        "sealed_at_utc": datetime.now(UTC).isoformat(),
        "status": "SEALED",
    }

    (artifact_dir / "seal.json").write_text(
        json.dumps(seal_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return seal_doc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=_REPO_ROOT / "protocols" / "E07_canonicalization" / "protocol.json",
    )
    parser.add_argument(
        "--vectors",
        type=Path,
        default=_REPO_ROOT / "testdata" / "glhs" / "canonicalization" / "v2" / "vectors.json",
    )
    parser.add_argument(
        "--expected",
        type=Path,
        default=_REPO_ROOT / "testdata" / "glhs" / "canonicalization" / "v2" / "expected.json",
    )
    parser.add_argument(
        "--node-script",
        type=Path,
        default=_REPO_ROOT / "evaluation" / "canonicalization" / "verify_node_rfc8785.js",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=_REPO_ROOT / "artifacts" / "glhs-q2-r2" / "GLHS-Q2-R2-20260928-R01" / "E07_canonicalization",
    )
    parser.add_argument("--run-id", default="GLHS-Q2-R2-20260928-R01")
    args = parser.parse_args()

    seal_doc = seal_experiment(
        artifact_dir=args.artifact_dir,
        protocol_path=args.protocol,
        vectors_path=args.vectors,
        expected_path=args.expected,
        node_script_path=args.node_script,
        run_id=args.run_id,
    )
    print(json.dumps(seal_doc, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
