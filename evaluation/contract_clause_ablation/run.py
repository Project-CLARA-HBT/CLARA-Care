"""Write one deterministic, network-free contract clause matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

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
            "accepted": sum(
                int(row["accepted"])
                for row in rows
                if row["variant"] == variant
            ),
            "rejected": sum(
                int(not row["accepted"])
                for row in rows
                if row["variant"] == variant
            ),
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps({"status": result["status"], "external_calls": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
