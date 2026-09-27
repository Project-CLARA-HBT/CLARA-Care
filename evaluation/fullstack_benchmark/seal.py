"""SHA-256 seal generator for E10 Full-Stack Performance Characterization.

Validates the full artifact bundle (protocol, raw execution metrics, derived summaries, raw latencies),
verifies sample size sufficiency (N >= 100 per operation class), and seals the run with seal.json and checksums.sha256.
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

from evaluation.fullstack_benchmark.analyze import analyze

SEAL_SCHEMA_VERSION = "fullstack-seal.v1"


def sha256_file(path: Path) -> str:
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
    return {
        "schema_version": "fullstack-environment.v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "git_sha": git_sha,
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count() or 1,
    }


def seal_experiment(
    *,
    artifact_dir: Path,
    protocol_path: Path,
    metrics_path: Path,
    manifest_path: Path,
    raw_latencies_path: Path | None = None,
    run_id: str,
) -> dict[str, Any]:
    artifact_dir = artifact_dir.resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)

    derived_dir = artifact_dir / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)

    raw_dir = artifact_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    git_sha = _git_sha()

    # 1. Read protocol
    protocol_data = json.loads(protocol_path.read_text(encoding="utf-8"))

    # 2. Copy protocol & raw files
    dest_protocol = artifact_dir / "protocol.json"
    dest_protocol.write_text(json.dumps(protocol_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    dest_metrics = raw_dir / "fullstack_metrics.csv"
    dest_metrics.write_bytes(metrics_path.read_bytes())

    dest_manifest = raw_dir / "fullstack_manifest.json"
    dest_manifest.write_bytes(manifest_path.read_bytes())

    dest_raw_latencies: Path | None = None
    if raw_latencies_path is not None and raw_latencies_path.is_file():
        dest_raw_latencies = raw_dir / "raw_latencies.json"
        dest_raw_latencies.write_bytes(raw_latencies_path.read_bytes())

    # 3. Environment manifest
    env_data = generate_environment_manifest(git_sha=git_sha)
    (artifact_dir / "environment.json").write_text(
        json.dumps(env_data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # 4. Perform analysis & write summary artifacts
    summary_data = analyze(dest_metrics, dest_manifest, derived_dir)

    if not summary_data["claim_eligible"]:
        raise ValueError(
            f"experiment_not_claim_eligible: repetitions={summary_data['repetitions']} "
            f"(N >= 100 required for tail statistics)"
        )

    # 5. Validation document
    validation_doc = {
        "schema_version": "fullstack-validation.v1",
        "validated_at_utc": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "freeze_id": protocol_data.get("freeze_id", "GLHS-FULLSTACK-E10-20260928-01"),
        "git_sha": git_sha,
        "repetitions": summary_data["repetitions"],
        "claim_eligible": summary_data["claim_eligible"],
        "sample_size_sufficient": summary_data["sample_size_sufficient"],
        "missing_operations_count": summary_data["missing_operations_count"],
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
        "freeze_id": protocol_data.get("freeze_id", "GLHS-FULLSTACK-E10-20260928-01"),
        "run_id": run_id,
        "git_sha": git_sha,
        "repetitions": summary_data["repetitions"],
        "claim_eligible": summary_data["claim_eligible"],
        "sample_size_sufficient": summary_data["sample_size_sufficient"],
        "protocol_sha256": sha256_file(dest_protocol),
        "raw_metrics_sha256": sha256_file(dest_metrics),
        "raw_manifest_sha256": sha256_file(dest_manifest),
        "summary_sha256": sha256_file(derived_dir / "summary.json"),
        "validation_sha256": sha256_file(artifact_dir / "validation.json"),
        "artifact_inventory": file_digests,
        "sealed_at_utc": datetime.now(UTC).isoformat(),
        "status": "SEALED",
    }
    if dest_raw_latencies is not None:
        seal_doc["raw_latencies_sha256"] = sha256_file(dest_raw_latencies)

    (artifact_dir / "seal.json").write_text(
        json.dumps(seal_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return seal_doc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("protocols/E10_fullstack/protocol.json"),
    )
    parser.add_argument(
        "--metrics",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--raw-latencies",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/glhs-q2-r2/GLHS-Q2-R2-20260928-R01/E10_fullstack"),
    )
    parser.add_argument("--run-id", default="GLHS-Q2-R2-20260928-R01")
    args = parser.parse_args()

    seal_doc = seal_experiment(
        artifact_dir=args.artifact_dir,
        protocol_path=args.protocol,
        metrics_path=args.metrics,
        manifest_path=args.manifest,
        raw_latencies_path=args.raw_latencies,
        run_id=args.run_id,
    )
    print(json.dumps(seal_doc, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
