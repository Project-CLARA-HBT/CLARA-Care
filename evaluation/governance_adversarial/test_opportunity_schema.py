from __future__ import annotations

import csv
from pathlib import Path

from evaluation.governance_adversarial.opportunity_schema import (
    COMMITTED_OPERATION_EXACT_RECONSTRUCTION,
    GOVERNANCE_MUTATION_TRACE_LINKAGE,
    REJECTED_OPERATION_DECISION_RECORD,
    build_opportunity_denominators,
)

_COLUMNS = [
    "case_id", "family", "arm", "run_status", "normalized_outcome",
    "audit_reconstruction_complete", "rejection_reason_code", "transaction_trace",
]


def _write_raw(tmp_path: Path, *, committed: int, rejected: int, audit_complete: int) -> None:
    for arm in ("UNBOUND", "STATE_VERSION_ONLY", "SNAPSHOT_BOUND_STATE_ONLY", "GLHS_STRICT"):
        arm_dir = tmp_path / arm
        arm_dir.mkdir(parents=True, exist_ok=True)
        rows = []
        for index in range(committed):
            rows.append({
                "case_id": f"{arm}-commit-{index}",
                "family": "role_mismatch",
                "arm": arm,
                "run_status": "EXECUTED",
                "normalized_outcome": "committed",
                "audit_reconstruction_complete": "true" if index < audit_complete else "false",
                "rejection_reason_code": "",
                "transaction_trace": "",
            })
        for index in range(rejected):
            rows.append({
                "case_id": f"{arm}-reject-{index}",
                "family": "authorization_consent_toctou",
                "arm": arm,
                "run_status": "EXECUTED",
                "normalized_outcome": "rejected",
                "audit_reconstruction_complete": "false",
                "rejection_reason_code": "",
                "transaction_trace": "",
            })
        with (arm_dir / "raw_results.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=_COLUMNS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)


def test_completeness_reported_only_within_eligible_set(tmp_path: Path) -> None:
    _write_raw(tmp_path, committed=10, rejected=5, audit_complete=4)
    payload = build_opportunity_denominators(tmp_path)

    summary = payload["summary"]
    committed_summary = summary[COMMITTED_OPERATION_EXACT_RECONSTRUCTION]
    # 40 committed rows across four arms, 16 with reconstruction complete.
    assert committed_summary["eligible_opportunity_n"] == 40
    assert committed_summary["complete_n"] == 16
    assert committed_summary["completeness_within_eligible_set"] == 0.4
    # The observer column exists (boolean emitted) even when values are false.
    assert committed_summary["observer_emitted_required_record"] is True

    rejected_summary = summary[REJECTED_OPERATION_DECISION_RECORD]
    assert rejected_summary["eligible_opportunity_n"] == 20
    assert rejected_summary["complete_n"] == 0
    assert rejected_summary["completeness_within_eligible_set"] == 0.0
    assert rejected_summary["observer_emitted_required_record"] is False

    trace_summary = summary[GOVERNANCE_MUTATION_TRACE_LINKAGE]
    # role_mismatch + authorization_consent_toctou are governance-mutation
    # families; every executed row is eligible.
    assert trace_summary["eligible_opportunity_n"] == 60
    assert trace_summary["complete_n"] == 0
    assert trace_summary["observer_emitted_required_record"] is False


def test_rejected_vs_committed_not_mixed(tmp_path: Path) -> None:
    _write_raw(tmp_path, committed=3, rejected=7, audit_complete=3)
    payload = build_opportunity_denominators(tmp_path)
    for row in payload["rows"]:
        if row["opportunity_kind"] == REJECTED_OPERATION_DECISION_RECORD:
            assert row["eligible_opportunity_n"] == 7
        if row["opportunity_kind"] == COMMITTED_OPERATION_EXACT_RECONSTRUCTION:
            assert row["eligible_opportunity_n"] == 3