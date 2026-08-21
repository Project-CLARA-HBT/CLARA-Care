"""Seal one non-headline GovRed development boundary-probe artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


_DEVELOPMENT_PROBE_CONTRACTS = {
    "boundary_path_probe.json": (
        "govred-boundary-development-probe-v1",
        "development_boundary_probe_not_headline",
    ),
    "http_admission_probe.json": (
        "govred-isolated-http-admission-development-v1",
        "development_probe_not_headline",
    ),
    "development_case_matrix.json": (
        "govred-development-case-matrix-v1",
        "development_matrix_not_headline",
    ),
    "cache_audit_probe.json": (
        "govred-cache-audit-development-probe-v1",
        "development_cache_audit_probe_not_headline",
    ),
}


def seal(
    *, run_dir: Path, expected_probe_sha256: str, probe_filename: str = "boundary_path_probe.json"
) -> Path:
    expected_contract = _DEVELOPMENT_PROBE_CONTRACTS.get(probe_filename)
    if expected_contract is None:
        raise ValueError("govred_development_probe_filename_invalid")
    probe = run_dir / probe_filename
    if not probe.is_file():
        raise ValueError("govred_development_probe_missing")
    try:
        value = json.loads(probe.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("govred_development_probe_invalid_json") from exc
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != expected_contract[0]
        or value.get("status") != expected_contract[1]
    ):
        raise ValueError("govred_development_probe_contract_invalid")
    if _sha256(probe) != expected_probe_sha256:
        raise ValueError("govred_development_probe_transfer_hash_mismatch")
    files = {
        str(path.relative_to(run_dir)): _sha256(path)
        for path in sorted(run_dir.rglob("*"))
        if path.is_file() and path.name != "artifact-sha256.json"
    }
    target = run_dir / "artifact-sha256.json"
    target.write_text(
        json.dumps(
            {
                "schema_version": "govred-development-artifact-seal-v1",
                "status": "sealed_development_not_claim_eligible",
                "headline_claims_permitted": False,
                "probe_filename": probe_filename,
                "expected_probe_sha256": expected_probe_sha256,
                "files": files,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return target


def verify_seal(*, run_dir: Path) -> dict[str, object]:
    """Fail closed when a sealed non-headline artifact no longer matches bytes."""

    path = run_dir / "artifact-sha256.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("govred_development_seal_invalid") from exc
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != "govred-development-artifact-seal-v1"
        or value.get("status") != "sealed_development_not_claim_eligible"
        or value.get("headline_claims_permitted") is not False
    ):
        raise ValueError("govred_development_seal_contract_invalid")
    files = value.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("govred_development_seal_files_invalid")
    expected_probe_sha256 = value.get("expected_probe_sha256")
    if not isinstance(expected_probe_sha256, str):
        raise TypeError("govred_development_seal_expected_hash_invalid")
    probe_filename = value.get("probe_filename", "boundary_path_probe.json")
    if not isinstance(probe_filename, str) or probe_filename not in _DEVELOPMENT_PROBE_CONTRACTS:
        raise ValueError("govred_development_seal_probe_filename_invalid")
    actual_files = {
        str(candidate.relative_to(run_dir)): _sha256(candidate)
        for candidate in sorted(run_dir.rglob("*"))
        if candidate.is_file() and candidate.name != "artifact-sha256.json"
    }
    if files != actual_files or files.get(probe_filename) != expected_probe_sha256:
        raise ValueError("govred_development_seal_hash_mismatch")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--expected-probe-sha256")
    parser.add_argument("--probe-filename", default="boundary_path_probe.json")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify_seal(run_dir=args.run_dir), sort_keys=True))
    else:
        if not args.expected_probe_sha256:
            parser.error("govred_expected_probe_sha256_required")
        print(
            seal(
                run_dir=args.run_dir,
                expected_probe_sha256=args.expected_probe_sha256,
                probe_filename=args.probe_filename,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
