"""Fail-closed validation for a contract-clause ablation artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from evaluation.contract_clause_ablation.engine import VARIANTS
from evaluation.contract_clause_ablation.run import cases


def validate_frozen_contract(root: Path | None = None) -> dict[str, object]:
    contract_root = root or Path(__file__).resolve().parent
    manifest_path = contract_root / "experiment_manifest.json"
    if not manifest_path.is_file():
        raise ValueError("ablation_frozen_manifest_missing")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("ablation_frozen_manifest_not_object")
    expected_cases = [case.case_id for case in cases()]
    if (
        payload.get("schema_version") != "contract-clause-ablation.v1"
        or payload.get("status") != "FROZEN_STRUCTURAL_CONTRACT"
        or payload.get("developer_authored") is not True
        or payload.get("external_calls") != 0
        or payload.get("clinical_adjudication") != "NOT_RUN"
        or payload.get("case_count") != len(expected_cases)
        or payload.get("case_ids") != expected_cases
        or payload.get("variant_count") != len(VARIANTS)
        or payload.get("variants") != list(VARIANTS)
    ):
        raise ValueError("ablation_frozen_manifest_contract_invalid")
    hashes = payload.get("files_sha256")
    required_files = {"engine.py", "run.py"}
    if not isinstance(hashes, dict) or set(hashes) != required_files:
        raise ValueError("ablation_frozen_manifest_file_set_invalid")
    for filename in sorted(required_files):
        candidate = contract_root / filename
        if not candidate.is_file():
            raise ValueError(f"ablation_contract_file_missing:{filename}")
        expected = hashes.get(filename)
        observed = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if not isinstance(expected, str) or expected != observed:
            raise ValueError(f"ablation_contract_digest_mismatch:{filename}")
    return payload


def validate(output: Path) -> dict[str, object]:
    result_path = output / "results.json"
    checksum_path = output / "checksums.sha256"
    if not result_path.is_file() or not checksum_path.is_file():
        raise ValueError("ablation_artifact_incomplete")
    checksum_parts = checksum_path.read_text(encoding="utf-8").strip().split()
    if (
        len(checksum_parts) != 2
        or checksum_parts[1] != "results.json"
        or checksum_parts[0] != hashlib.sha256(result_path.read_bytes()).hexdigest()
    ):
        raise ValueError("ablation_checksum_mismatch")
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    if (
        payload.get("schema_version") != "contract-clause-ablation.v1"
        or payload.get("status") != "DETERMINISTIC_STRUCTURAL_CONFORMANCE"
        or payload.get("external_calls") != 0
        or payload.get("clinical_adjudication") != "NOT_RUN"
        or payload.get("variants") != list(VARIANTS)
        or payload.get("case_count") != len(cases())
    ):
        raise ValueError("ablation_manifest_contract_invalid")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise TypeError("ablation_rows_missing")
    expected_grid = {(case.case_id, variant) for case in cases() for variant in VARIANTS}
    observed_grid = {
        (str(row.get("case_id")), str(row.get("variant")))
        for row in rows
        if isinstance(row, dict)
    }
    if observed_grid != expected_grid or len(rows) != len(expected_grid):
        raise ValueError("ablation_grid_incomplete")
    expected_aggregate = {
        variant: {
            "case_count": len(cases()),
            "accepted": sum(
                int(bool(row["accepted"]))
                for row in rows
                if row["variant"] == variant
            ),
            "rejected": sum(
                int(not bool(row["accepted"]))
                for row in rows
                if row["variant"] == variant
            ),
            "exact_seen_context_reconstructable": sum(
                int(bool(row["exact_seen_context_reconstructable"]))
                for row in rows
                if row["variant"] == variant
            ),
        }
        for variant in VARIANTS
    }
    if payload.get("aggregate") != expected_aggregate:
        raise ValueError("ablation_aggregate_mismatch")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    frozen = validate_frozen_contract()
    result = validate(args.output) if args.output is not None else None
    print(
        json.dumps(
            {
                "frozen_status": frozen["status"],
                "result_status": result["status"] if result is not None else "NOT_RUN",
                "external_calls": 0,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
