"""Run the complete v5 grid through the deterministic no-network transport."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.commitloop.fixtures import DeterministicFakeTransport
from evaluation.commitloop.provider import REVIEWER_MODEL, EvaluationClient, RunLimits
from evaluation.commitloop.run_local import run_local_e2e
from evaluation.commitloop.solver_packets import CONDITIONS
from evaluation.commitloop.v5_cohort import (
    COHORT_NAME,
    KNOWN_CUTOFF,
    VALID_CUTOFF,
    write_cohort,
)
from evaluation.commitloop.v5_validate import validate_v5_run


def run_offline_v5_dry_run(*, output_dir: Path, cohort_dir: Path) -> dict[str, object]:
    """Create a sealed v5-shaped run without a provider or network request."""

    cohort_path, cohort_manifest_path = write_cohort(cohort_dir)
    rows = [json.loads(line) for line in cohort_path.read_text(encoding="utf-8").splitlines()]
    limits = RunLimits(
        max_subjects=len(rows),
        max_cases=len(rows),
        max_requests=len(rows) * len(CONDITIONS),
        max_concurrency=8,
        max_retries=0,
        checkpoint_every=64,
    )
    transport = DeterministicFakeTransport()
    client = EvaluationClient(
        base_url="https://offline.invalid/v1",
        api_key="offline-fixture-token",
        transport=transport,
        limits=limits,
    )
    run_local_e2e(
        bundles=[(row["bundle"], row["fhir_version"]) for row in rows],
        output_dir=output_dir,
        clients={REVIEWER_MODEL: client},
        valid_cutoff=VALID_CUTOFF,
        known_cutoff=KNOWN_CUTOFF,
        limits=limits,
        conditions=CONDITIONS,
        primary_model=REVIEWER_MODEL,
        source_cohort=COHORT_NAME,
    )
    validation = validate_v5_run(
        output_dir,
        cohort_path=cohort_path,
        cohort_manifest_path=cohort_manifest_path,
        expected_subject_count=len(rows),
    )
    return {
        "schema_version": "commitloop-v5-offline-dry-run.v1",
        "status": "VALID",
        "provider_calls": 0,
        "injected_transport_calls": transport.call_count,
        "validation": validation,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cohort-output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_offline_v5_dry_run(output_dir=args.output, cohort_dir=args.cohort_output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
