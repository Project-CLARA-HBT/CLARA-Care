"""Stable offline CommitLoop Phase-A commands."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from evaluation.commitloop.fixtures import DeterministicFakeTransport, synthetic_bundle
from evaluation.commitloop.provider import (
    GENERATOR_MODEL,
    REVIEWER_MODEL,
    EvaluationClient,
    RunLimits,
)
from evaluation.commitloop.run_local import run_local_e2e
from evaluation.commitloop.validate import validate_run


def _local_fixture(output: Path, max_requests: int) -> dict[str, object]:
    limits = RunLimits(
        max_subjects=2,
        max_cases=20,
        max_requests=max_requests,
        checkpoint_every=3,
    )
    transport = DeterministicFakeTransport()
    clients = {
        model: EvaluationClient(
            base_url="https://offline.invalid/v1",
            api_key="offline-fixture-token",
            transport=transport,
            limits=limits,
        )
        for model in (GENERATOR_MODEL, REVIEWER_MODEL)
    }
    cutoff = datetime(2026, 2, 1, tzinfo=UTC)
    manifest = run_local_e2e(
        bundles=[
            (synthetic_bundle("synthetic-a", "a"), "R4"),
            (synthetic_bundle("synthetic-b", "b"), "R4"),
        ],
        output_dir=output,
        clients=clients,
        construction_clients=(clients[GENERATOR_MODEL], clients[REVIEWER_MODEL]),
        valid_cutoff=cutoff,
        known_cutoff=cutoff,
        limits=limits,
    )
    validate_run(output)
    return {**manifest, "transport_call_count": transport.call_count}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    local = subparsers.add_parser("local-fixture")
    local.add_argument("--output", type=Path, required=True)
    local.add_argument("--max-requests", type=int, default=500)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "local-fixture":
        if not 1 <= args.max_requests <= 10000:
            parser.error("max-requests must be between 1 and 10000")
        result = _local_fixture(args.output, args.max_requests)
    else:
        validate_run(args.run_dir)
        result = {"status": "VALID", "run_dir": str(args.run_dir)}
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
