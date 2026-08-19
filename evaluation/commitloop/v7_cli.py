"""Fail-closed CLI for a frozen GLHS-Bench v7 non-final partition."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from evaluation.commitloop.http_transport import UrllibJsonTransport
from evaluation.commitloop.provider import (
    CONFIRMATORY_MODELS,
    EvaluationClient,
    RunLimits,
)
from evaluation.commitloop.v7_runner import run_v7_development_partition


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=("development", "validation"), required=True)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    args = parser.parse_args()
    freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
    contract = freeze.get("execution_contract")
    if not isinstance(contract, dict):
        raise TypeError("v7_cli_freeze_contract_missing")
    cohort_path = args.freeze.parent / "cohort" / "cohort.jsonl"
    rows = [
        json.loads(line)
        for line in cohort_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    split_subjects = contract.get(f"{args.split}_subjects")
    request_count = contract.get("solver_request_counts", {}).get(args.split)
    if not isinstance(split_subjects, int) or not isinstance(request_count, int):
        raise TypeError("v7_cli_split_contract_missing")
    limits = RunLimits(
        max_subjects=split_subjects,
        max_cases=split_subjects,
        max_requests=request_count,
        max_concurrency=int(contract["max_concurrency"]),
        timeout_seconds=90,
        checkpoint_every=5,
        max_retries=int(contract["max_retries"]),
        retry_backoff_seconds=1.5,
    )
    base_url = os.environ.get("ROUTER_BASE_URL", "")
    api_key = os.environ.get("CLARA_ROUTER_API_KEY", "")
    if not base_url or not api_key:
        raise ValueError("v7_cli_router_configuration_missing")
    clients = {
        model: EvaluationClient(
            base_url=base_url,
            api_key=api_key,
            transport=UrllibJsonTransport(),
            limits=limits,
        )
        for model in CONFIRMATORY_MODELS
    }
    result = run_v7_development_partition(
        rows=rows,
        split=args.split,
        output_dir=args.output,
        clients=clients,
        freeze_path=args.freeze,
        provider_probe_path=args.probe,
        repository_root=args.repository_root,
        limits=limits,
    )
    print(json.dumps({"status": result["run_status"], "cells": result["completed_cell_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
