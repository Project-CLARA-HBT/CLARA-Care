"""Write one deterministic, network-free contract clause matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evaluation.contract_clause_ablation.engine import VARIANTS, ContractCase, evaluate


def cases() -> tuple[ContractCase, ...]:
    valid = ContractCase(case_id="valid_write")
    return (
        valid,
        replace(valid, case_id="wrong_profile", profile_matches=False),
        replace(valid, case_id="stale_base", base_version_matches=False),
        replace(
            valid,
            case_id="unauthorized_at_disclosure",
            authorized_at_disclosure=False,
        ),
        replace(valid, case_id="missing_provenance", provenance_present=False),
        replace(valid, case_id="wrong_snapshot_id", snapshot_id_matches=False),
        replace(valid, case_id="wrong_actor", actor_matches=False),
        replace(valid, case_id="wrong_actor_role", actor_role_matches=False),
        replace(valid, case_id="wrong_purpose", purpose_matches=False),
        replace(valid, case_id="wrong_task", task_matches=False),
        replace(valid, case_id="digest_mismatch", digest_matches=False),
        replace(
            valid,
            case_id="undisclosed_evidence",
            evidence_within_snapshot=False,
        ),
        replace(valid, case_id="expired_snapshot", snapshot_unexpired=False),
        replace(valid, case_id="revoked_before_write", authorized_at_write=False),
        replace(valid, case_id="policy_change", policy_matches=False),
        replace(valid, case_id="consent_change", consent_matches=False),
    )


def run(output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=False)
    rows = [
        {
            "case_id": case.case_id,
            "variant": variant,
            **asdict(evaluate(variant, case)),
        }
        for case in cases()
        for variant in VARIANTS
    ]
    aggregate = {
        variant: {
            "case_count": len(cases()),
            "accepted": sum(int(row["accepted"]) for row in rows if row["variant"] == variant),
            "rejected": sum(int(not row["accepted"]) for row in rows if row["variant"] == variant),
            "exact_seen_context_reconstructable": sum(
                int(row["exact_seen_context_reconstructable"])
                for row in rows
                if row["variant"] == variant
            ),
        }
        for variant in VARIANTS
    }
    payload: dict[str, object] = {
        "schema_version": "contract-clause-ablation.v1",
        "status": "DETERMINISTIC_STRUCTURAL_CONFORMANCE",
        "developer_authored_cases": True,
        "external_calls": 0,
        "clinical_adjudication": "NOT_RUN",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "variants": list(VARIANTS),
        "case_count": len(cases()),
        "aggregate": aggregate,
        "rows": rows,
    }
    result = output / "results.json"
    result.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    digest = hashlib.sha256(result.read_bytes()).hexdigest()
    (output / "checksums.sha256").write_text(f"{digest}  results.json\n", encoding="utf-8")
    return payload


def freeze(root: Path | None = None) -> dict[str, object]:
    contract_root = root or Path(__file__).resolve().parent
    manifest_path = contract_root / "experiment_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files_sha256 = {}
    for filename in sorted(manifest.get("files_sha256", {}).keys() or ["engine.py", "run.py"]):
        target = contract_root / filename
        files_sha256[filename] = hashlib.sha256(target.read_bytes()).hexdigest()
    manifest["files_sha256"] = files_sha256
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--freeze", action="store_true", help="Freeze contract manifest checksums")
    args = parser.parse_args()
    if args.freeze:
        frozen = freeze()
        print(json.dumps({"status": frozen["status"], "files_sha256": frozen["files_sha256"]}, sort_keys=True))
        return 0
    if args.output is None:
        parser.error("--output is required when not using --freeze")
    result = run(args.output)
    print(json.dumps({"status": result["status"], "external_calls": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
