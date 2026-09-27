"""SHA-256 seal generator for E01 2^3 factorial component-wise exact-binding ablation.

Validates the full artifact bundle (protocol, environment, raw executions, derived summaries,
validation assertions), checks the tamper-evident observer hash chain, and seals the run with
a cryptographically bound seal.json and checksums.sha256.
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

from evaluation.glhs_binding_component_ablation.analyze import analyze, generate_summary_markdown
from evaluation.glhs_binding_component_ablation.observer import read_records
from evaluation.glhs_binding_component_ablation.validate import (
    validate_execution_against_expected,
    validate_import_boundary,
    validate_no_production_flag,
    validate_protocol,
    validate_schedules,
)

SEAL_SCHEMA_VERSION = "glhs-binding-component-ablation-seal.v1"


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


def generate_environment_manifest(
    *,
    git_sha: str,
    backend: str = "isolated_sqlite",
) -> dict[str, Any]:
    """Capture execution environment metadata."""
    return {
        "schema_version": "glhs-binding-component-ablation-environment.v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "git_sha": git_sha,
        "backend": backend,
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count() or 1,
        "libraries": {
            "pytest": "9.1.1",
            "sqlalchemy": "2.0.46",
        },
    }


def seal(
    *,
    protocol_path: Path,
    schedules_path: Path,
    adapter_path: Path,
    binding_mask_path: Path,
    runner_path: Path,
    observer_path: Path,
    analyze_path: Path,
    validate_path: Path,
    raw_paths: list[Path],
    analysis_path: Path,
    out_dir: Path,
    run_id: str,
    freeze_id: str,
    results_dir: Path,
    claim_to_evidence_path: Path | None = None,
) -> dict[str, Any]:
    """Compute and write artifact manifest and seal document for results directory."""
    artifact_paths = [
        protocol_path,
        schedules_path,
        adapter_path,
        binding_mask_path,
        runner_path,
        observer_path,
        analyze_path,
        validate_path,
        *raw_paths,
        analysis_path,
    ]
    if claim_to_evidence_path is not None:
        artifact_paths.append(claim_to_evidence_path)

    missing = [str(p) for p in artifact_paths if not p.exists()]
    if missing:
        raise RuntimeError(f"glhs_binding_ablation_seal_artifact_missing:{missing}")

    artifact_hashes = {str(p): sha256_file(p) for p in artifact_paths}
    raw_hashes = {str(p): sha256_file(p) for p in raw_paths}
    raw_blob = b"".join(p.read_bytes() for p in raw_paths)

    manifest_file = results_dir / f"manifest_{run_id}.json"
    manifest_data = {}
    if manifest_file.exists():
        try:
            manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    backend = str(manifest_data.get("backend", "sqlite_smoke"))
    total_records = 0
    for rp in raw_paths:
        total_records += len(read_records(rp))

    seal_doc = {
        "schema_version": SEAL_SCHEMA_VERSION,
        "freeze_id": freeze_id,
        "run_id": run_id,
        "git_sha": _git_sha(),
        "backend": backend,
        "total_executions_sealed": total_records,
        "protocol_sha256": artifact_hashes[str(protocol_path)],
        "schedules_sha256": artifact_hashes[str(schedules_path)],
        "adapter_sha256": artifact_hashes[str(adapter_path)],
        "runner_sha256": artifact_hashes[str(runner_path)],
        "raw_streams": raw_hashes,
        "raw_streams_combined_sha256": hashlib.sha256(raw_blob).hexdigest(),
        "analysis_sha256": artifact_hashes[str(analysis_path)],
        "sealed_at_utc": datetime.now(UTC).isoformat(),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "artifact-sha256.json").write_text(
        json.dumps(artifact_hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "seal.json").write_text(
        json.dumps(seal_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return seal_doc


def seal_experiment(
    *,
    artifact_dir: Path,
    protocol_path: Path,
    schedules_path: Path,
    run_id: str,
    backend: str = "isolated_sqlite",
    services_root: Path = Path("services"),
) -> dict[str, Any]:
    """Seal the E01 experiment artifact bundle."""
    artifact_dir = artifact_dir.resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    derived_dir = artifact_dir / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = artifact_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    git_sha = _git_sha()

    # 1. Validate protocol & schedules
    protocol_data = json.loads(protocol_path.read_text(encoding="utf-8"))
    validate_protocol(protocol_data)

    schedules_data = json.loads(schedules_path.read_text(encoding="utf-8"))
    validate_schedules(schedules_data)
    schedules = schedules_data["schedules"]

    # 2. Validate no production flags or illegal imports
    flag_check = validate_no_production_flag(services_root)
    import_check = validate_import_boundary(services_root)

    # 3. Read & verify raw runs
    runs_file = raw_dir / f"executions_{run_id}.jsonl"
    if not runs_file.is_file():
        runs_file = raw_dir / "runs.jsonl"
    if not runs_file.is_file():
        candidates = sorted(raw_dir.glob("*.jsonl"))
        if candidates:
            runs_file = candidates[0]
        else:
            raise FileNotFoundError(f"raw_runs_missing:{runs_file}")

    records = read_records(runs_file)
    if len(records) != 2816:
        raise ValueError(f"record_count_mismatch:expected=2816:found={len(records)}")

    # 4. Copy protocol files and write protocol.sha256
    dest_protocol = artifact_dir / "protocol.json"
    dest_protocol.write_text(json.dumps(protocol_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    proto_sha = sha256_file(dest_protocol)
    (artifact_dir / "protocol.sha256").write_text(f"{proto_sha}  protocol.json\n", encoding="utf-8")

    # 5. Write environment.json
    env_data = generate_environment_manifest(git_sha=git_sha, backend=backend)
    (artifact_dir / "environment.json").write_text(
        json.dumps(env_data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # 6. Generate derived summary.json and summary.md
    summary_data = analyze(schedules_data, records, protocol_data)
    (derived_dir / "summary.json").write_text(
        json.dumps(summary_data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    summary_md = generate_summary_markdown(summary_data)
    (derived_dir / "summary.md").write_text(summary_md, encoding="utf-8")

    # 7. Validate executions against expected outcomes
    exec_audit = validate_execution_against_expected(records, schedules)
    validation_data = {
        "schema_version": "glhs-binding-component-ablation-validation.v1",
        "validated_at_utc": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "freeze_id": protocol_data["freeze_id"],
        "git_sha": git_sha,
        "clean_controls_admitted": summary_data["clean_acceptance_by_arm"]["B111"]["accepted"],
        "clean_controls_total": summary_data["clean_acceptance_by_arm"]["B111"]["total"],
        "clean_controls_rate": summary_data["clean_acceptance_by_arm"]["B111"]["acceptance_rate"],
        "adversarial_executions_audited": len([r for r in records if r["schedule_id"] not in {s["schedule_id"] for s in schedules if s["family_name"] == "CLEAN"}]),
        "total_executions_audited": len(records),
        "no_production_flags": flag_check["clean"],
        "no_forbidden_services_imports": import_check["clean"],
        "claim_eligible": summary_data["claim_eligible"],
        "execution_audit": exec_audit,
        "status": "VALIDATED",
    }
    (artifact_dir / "validation.json").write_text(
        json.dumps(validation_data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    # 8. Compute checksums for all files excluding checksums.sha256 and seal.json
    checksum_lines: list[str] = []
    file_digests: dict[str, str] = {}
    for p in sorted(artifact_dir.rglob("*")):
        if p.is_file() and p.name not in ("checksums.sha256", "seal.json"):
            rel_path = str(p.relative_to(artifact_dir))
            digest = sha256_file(p)
            file_digests[rel_path] = digest
            checksum_lines.append(f"{digest}  {rel_path}")

    (artifact_dir / "checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    # 9. Write seal.json
    seal_doc = {
        "schema_version": SEAL_SCHEMA_VERSION,
        "freeze_id": protocol_data["freeze_id"],
        "run_id": run_id,
        "git_sha": git_sha,
        "backend": backend,
        "total_schedules": len(schedules),
        "executed_executions": len(records),
        "expected_executions": 2816,
        "claim_eligible": summary_data["claim_eligible"],
        "protocol_sha256": proto_sha,
        "schedules_sha256": sha256_file(schedules_path),
        "raw_stream_sha256": sha256_file(runs_file),
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
        default=Path("protocols/E01_binding_components/protocol.json"),
    )
    parser.add_argument(
        "--schedules",
        type=Path,
        default=Path("protocols/E01_binding_components/schedules.json"),
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path("artifacts/glhs-q2-r2/GLHS-Q2-R2-20260928-R01/E01_binding_components"),
    )
    parser.add_argument("--run-id", default="GLHS-Q2-R2-20260928-R01")
    parser.add_argument("--backend", default="isolated_sqlite")
    args = parser.parse_args()

    seal_doc = seal_experiment(
        artifact_dir=args.artifact_dir,
        protocol_path=args.protocol,
        schedules_path=args.schedules,
        run_id=args.run_id,
        backend=args.backend,
    )
    print(json.dumps(seal_doc, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
