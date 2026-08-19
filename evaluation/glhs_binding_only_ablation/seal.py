"""SHA-256 sealing for the GLHS exact-binding ablation.

Seals exactly what was actually executed and analyzed: the frozen protocol,
the frozen schedules, the adapter and runner sources, every raw append-only
execution stream, and the analysis output.  The seal never fabricates a
backend: the manifest's ``backend`` value is read from the runner manifest of
the sealed run (``postgres`` only when a real isolated PostgreSQL execution
produced the raw stream).

Outputs (research/glhs_journal/binding_only_ablation/seal/):

- ``artifact-sha256.json``: path -> sha256 for every sealed artifact.
- ``seal.json``: freeze_id, run_id, git sha, run backend, protocol/schedules
  hashes, raw-stream hash (over the concatenated raw stream), analysis hash,
  seal time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evaluation.glhs_binding_only_ablation.observer import read_records

SEAL_SCHEMA_VERSION = "glhs-binding-ablation-seal.v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return result.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _run_manifest(results_dir: Path, run_id: str) -> dict[str, Any] | None:
    manifest_path = results_dir / f"manifest_{run_id}.json"
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def seal(
    *,
    protocol_path: Path,
    schedules_path: Path,
    adapter_path: Path,
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
    """Compute and write the artifact manifest and seal document."""
    artifact_paths = [
        protocol_path,
        schedules_path,
        adapter_path,
        runner_path,
        observer_path,
        analyze_path,
        validate_path,
        *raw_paths,
        analysis_path,
    ]
    if claim_to_evidence_path is not None:
        artifact_paths.append(claim_to_evidence_path)
    missing = [str(path) for path in artifact_paths if not path.exists()]
    if missing:
        raise RuntimeError(f"glhs_binding_ablation_seal_artifact_missing:{missing}")
    artifact_hashes = {
        str(path): sha256_file(path) for path in artifact_paths
    }
    raw_hashes = {
        str(path): sha256_file(path) for path in raw_paths
    }
    raw_blob = b"".join(path.read_bytes() for path in raw_paths)
    run_manifest = _run_manifest(results_dir, run_id)
    if run_manifest is None:
        raise RuntimeError(f"glhs_binding_ablation_seal_manifest_missing:{run_id}")
    backend = str(run_manifest.get("backend"))
    if backend not in {"sqlite_smoke", "isolated_postgresql_random_schema"}:
        raise RuntimeError(f"glhs_binding_ablation_seal_backend_invalid:{backend}")
    if run_manifest.get("executed_executions") != 640 or run_manifest.get("expected_executions") != 640:
        raise RuntimeError("glhs_binding_ablation_seal_execution_count_invalid")
    if len(raw_paths) != 1:
        raise RuntimeError("glhs_binding_ablation_seal_requires_one_raw_stream")
    records = read_records(raw_paths[0])
    if len(records) != 640 or any(str(record.get("run_id")) != run_id for record in records):
        raise RuntimeError("glhs_binding_ablation_seal_raw_stream_invalid")
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    if analysis.get("run_ids") != [run_id] or analysis.get("execution_count") != 640:
        raise RuntimeError("glhs_binding_ablation_seal_analysis_run_mismatch")
    if backend == "isolated_postgresql_random_schema" and (
        (run_manifest.get("backend_detail") or {}).get("backend") != "postgresql"
    ):
        raise RuntimeError("glhs_binding_ablation_seal_postgres_metadata_invalid")
    seal_document = {
        "schema_version": SEAL_SCHEMA_VERSION,
        "freeze_id": freeze_id,
        "run_id": run_id,
        "git_sha": _git_sha(),
        "backend": backend,
        "backend_detail": run_manifest.get("backend_detail"),
        "executed_executions": run_manifest.get("executed_executions"),
        "protocol_sha256": artifact_hashes[str(protocol_path)],
        "schedules_sha256": artifact_hashes[str(schedules_path)],
        "adapter_sha256": artifact_hashes[str(adapter_path)],
        "runner_sha256": artifact_hashes[str(runner_path)],
        "raw_streams": raw_hashes,
        "raw_streams_combined_sha256": hashlib.sha256(raw_blob).hexdigest(),
        "analysis_sha256": artifact_hashes[str(analysis_path)],
        "sealed_at_utc": datetime.now(UTC).isoformat(),
        "note": (
            "SQLite smoke run: real production code paths on SQLite; NOT the "
            "final frozen PostgreSQL run."
            if backend == "sqlite_smoke"
            else "Isolated PostgreSQL random schema execution."
        ),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "artifact-sha256.json").write_text(
        json.dumps(artifact_hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "seal.json").write_text(
        json.dumps(seal_document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return seal_document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=Path("evaluation/glhs_binding_only_ablation/protocol.json"))
    parser.add_argument("--schedules", type=Path, default=Path("evaluation/glhs_binding_only_ablation/schedules.json"))
    parser.add_argument("--adapter", type=Path, default=Path("evaluation/glhs_binding_only_ablation/adapter.py"))
    parser.add_argument("--runner", type=Path, default=Path("evaluation/glhs_binding_only_ablation/postgres_runner.py"))
    parser.add_argument("--observer", type=Path, default=Path("evaluation/glhs_binding_only_ablation/observer.py"))
    parser.add_argument("--analyze", type=Path, default=Path("evaluation/glhs_binding_only_ablation/analyze.py"))
    parser.add_argument("--validate", type=Path, default=Path("evaluation/glhs_binding_only_ablation/validate.py"))
    parser.add_argument(
        "--claims",
        type=Path,
        default=Path("research/glhs_journal/binding_only_ablation/claim_to_evidence.csv"),
    )
    parser.add_argument("--results-dir", type=Path, default=Path("research/glhs_journal/binding_only_ablation/results"))
    parser.add_argument("--seal-dir", type=Path, default=Path("research/glhs_journal/binding_only_ablation/seal"))
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    freeze_id = str(protocol["freeze_id"])
    raw_paths = sorted((args.results_dir / "raw").glob(f"executions_{args.run_id}.jsonl"))
    analysis_path = args.results_dir / "analysis.json"
    seal_document = seal(
        protocol_path=args.protocol,
        schedules_path=args.schedules,
        adapter_path=args.adapter,
        runner_path=args.runner,
        observer_path=args.observer,
        analyze_path=args.analyze,
        validate_path=args.validate,
        raw_paths=raw_paths,
        analysis_path=analysis_path,
        claim_to_evidence_path=args.claims,
        out_dir=args.seal_dir,
        run_id=args.run_id,
        freeze_id=freeze_id,
        results_dir=args.results_dir,
    )
    print(json.dumps(seal_document, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
