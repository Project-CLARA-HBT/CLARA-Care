"""Gate result files to attacks executed through isolated application boundaries."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from evaluation.evidence_program.freeze import FreezeError, load_frozen_json

SCENARIOS = frozenset({
    "cross_subject_retrieval", "revoked_consent_cache_reuse", "role_escalation",
    "purpose_mismatch", "stale_thss_replay", "stale_write", "gst_bypass_prompt",
    "patient_evidence_prompt_injection", "malicious_unrelated_disclosure",
    "revoked_derived_cache_or_index",
})
COLUMNS = frozenset({
    "attack_id", "scenario", "target_environment", "execution_id",
    "unauthorized_disclosure", "successful_bypass", "stale_commit",
    "wrong_subject_exposure", "cache_index_revocation_failure",
    "policy_decision_correct", "audit_trace_complete",
})


def validate(results: Path, manifest: Path) -> None:
    metadata = load_frozen_json(manifest)
    required = {"status", "execution_mode", "endpoint_manifest_sha256", "environment_attestation"}
    if required - metadata.keys() or metadata.get("status") != "frozen":
        raise FreezeError("adversarial_manifest_not_frozen")
    if metadata.get("execution_mode") != "isolated_real_application_boundary":
        raise FreezeError("adversarial_boundary_execution_required")
    if not metadata.get("environment_attestation"):
        raise FreezeError("adversarial_environment_attestation_missing")
    with results.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or not COLUMNS.issubset(reader.fieldnames):
            raise FreezeError("adversarial_result_schema_incomplete")
        rows = list(reader)
    seen = {row["scenario"] for row in rows}
    if seen != SCENARIOS:
        raise FreezeError("adversarial_scenarios_incomplete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate(args.results, args.manifest)
    except FreezeError as exc:
        parser.error(str(exc))
