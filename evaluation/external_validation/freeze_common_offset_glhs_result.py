"""Freeze and verify a sanitized aggregate of a common-offset GLHS run."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evaluation.external_validation.validate_common_offset_glhs import validate

SCHEMA_VERSION = "clara-common-offset-glhs-result-freeze.v1"
STATUS = "FROZEN_VALID_SOURCE_DERIVED_EXECUTION"


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=_root(), check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _record_path(path: Path, *, allow_external: bool) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(_root().resolve()))
    except ValueError:
        if allow_external:
            return str(resolved)
        raise ValueError("common_offset_freeze_path_outside_repository") from None


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("common_offset_freeze_json_invalid")
    return value


def _domain_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            rows.append(
                {
                    "domain": row["domain"],
                    "system": row["system"],
                    "correct": int(row["correct"]),
                    "total": int(row["total"]),
                    "rate": float(row["rate"]),
                }
            )
    return rows


def _payload_hash(payload: dict[str, Any]) -> str:
    stored = payload.get("freeze_payload_sha256")
    unsigned = dict(payload)
    unsigned.pop("freeze_payload_sha256", None)
    expected = hashlib.sha256(_canonical(unsigned).encode()).hexdigest()
    if stored != expected:
        raise ValueError("common_offset_freeze_payload_hash_mismatch")
    return expected


def freeze(
    output_dir: Path,
    tasks_path: Path,
    cohort_manifest_path: Path,
    protocol_path: Path,
    destination: Path,
    *,
    enforce_repository_freeze: bool = True,
) -> dict[str, object]:
    if destination.exists():
        raise FileExistsError("common_offset_freeze_destination_exists")
    if enforce_repository_freeze and _git("status", "--porcelain", "--untracked-files=no"):
        raise ValueError("common_offset_freeze_tracked_worktree_dirty")
    validation = validate(output_dir, tasks_path, cohort_manifest_path, protocol_path)
    run_manifest = _json(output_dir / "run_manifest.json")
    protocol = _json(protocol_path)
    artifact_files = [
        {
            "path": path.name,
            "bytes": path.stat().st_size,
            "sha256": _sha(path),
        }
        for path in sorted(output_dir.iterdir())
        if path.is_file()
    ]
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "freeze_id": protocol["freeze_id"],
        "frozen_at_utc": datetime.now(UTC).isoformat(),
        "dataset_id": run_manifest["dataset_id"],
        "source_git_sha": _git("rev-parse", "HEAD"),
        "source_git_tree": _git("rev-parse", "HEAD^{tree}"),
        "implementation_git_sha": protocol["implementation_git_sha"],
        "freezer_sha256": _sha(Path(__file__)),
        "artifact_root_local_only": _record_path(
            output_dir, allow_external=not enforce_repository_freeze
        ),
        "tasks_path_local_only": _record_path(
            tasks_path, allow_external=not enforce_repository_freeze
        ),
        "cohort_manifest_path_local_only": _record_path(
            cohort_manifest_path, allow_external=not enforce_repository_freeze
        ),
        "protocol_path": _record_path(protocol_path, allow_external=not enforce_repository_freeze),
        "artifact_files": artifact_files,
        "protocol_payload_sha256": protocol["protocol_payload_sha256"],
        "run_manifest_payload_sha256": run_manifest["manifest_payload_sha256"],
        "validation": validation,
        "primary_result": run_manifest["primary_result"],
        "system_results": run_manifest["system_results"],
        "domain_results": _domain_rows(output_dir / "domain_results.csv"),
        "row_counts": run_manifest["row_counts"],
        "error_taxonomy": run_manifest["error_taxonomy"],
        "operational": run_manifest["operational"],
        "environment": run_manifest["environment"],
        "provider_calls": run_manifest["provider_calls"],
        "clinical_oracle": run_manifest["clinical_oracle"],
        "headline_eligible": run_manifest["headline_eligible"],
        "execution_boundary": run_manifest["execution_boundary"],
        "postgresql_or_http_measured": run_manifest["postgresql_or_http_measured"],
        "claim_limit": run_manifest["claim_limit"],
    }
    payload["freeze_payload_sha256"] = hashlib.sha256(_canonical(payload).encode()).hexdigest()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def verify_freeze(path: Path, *, verify_local_artifact: bool = True) -> dict[str, object]:
    payload = _json(path)
    _payload_hash(payload)
    if (
        payload.get("schema_version") != SCHEMA_VERSION
        or payload.get("status") != STATUS
        or payload.get("clinical_oracle") is not False
        or payload.get("headline_eligible") is not False
        or payload.get("provider_calls") != 0
        or payload.get("postgresql_or_http_measured") is not False
    ):
        raise ValueError("common_offset_freeze_contract_invalid")
    source_sha = str(payload.get("source_git_sha", ""))
    subprocess.run(
        ["git", "cat-file", "-e", f"{source_sha}^{{commit}}"],
        cwd=_root(),
        check=True,
        capture_output=True,
    )
    if verify_local_artifact:
        output_dir = _root() / str(payload["artifact_root_local_only"])
        tasks = _root() / str(payload["tasks_path_local_only"])
        cohort = _root() / str(payload["cohort_manifest_path_local_only"])
        protocol = _root() / str(payload["protocol_path"])
        validation = validate(output_dir, tasks, cohort, protocol)
        if validation != payload.get("validation"):
            raise ValueError("common_offset_freeze_validation_mismatch")
        observed = [
            {"path": item["path"], "bytes": item["bytes"], "sha256": item["sha256"]}
            for item in payload.get("artifact_files", [])
            if isinstance(item, dict)
        ]
        expected = [
            {"path": path.name, "bytes": path.stat().st_size, "sha256": _sha(path)}
            for path in sorted(output_dir.iterdir())
            if path.is_file()
        ]
        if observed != expected:
            raise ValueError("common_offset_freeze_artifact_inventory_mismatch")
    return {
        "schema_version": "clara-common-offset-glhs-result-freeze-validation.v1",
        "status": "VALID",
        "freeze_id": payload["freeze_id"],
        "freeze_payload_sha256": payload["freeze_payload_sha256"],
        "tasks": payload["validation"]["tasks"],
        "subjects": payload["validation"]["subjects"],
        "claim_limit": payload["claim_limit"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--tasks", type=Path)
    parser.add_argument("--cohort-manifest", type=Path)
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--metadata-only", action="store_true")
    args = parser.parse_args()
    try:
        if args.verify:
            result = verify_freeze(args.destination, verify_local_artifact=not args.metadata_only)
        else:
            if not all((args.output, args.tasks, args.cohort_manifest, args.protocol)):
                parser.error("freeze requires --output, --tasks, --cohort-manifest and --protocol")
            result = freeze(
                args.output,
                args.tasks,
                args.cohort_manifest,
                args.protocol,
                args.destination,
            )
    except (OSError, TypeError, ValueError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"status": "INVALID", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
