"""Network-disabled reproduction of all derived Phase-B v5 result artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

from evaluation.commitloop.run_local import seal_artifacts
from evaluation.commitloop.score import score_adversarial_variants, score_outputs
from evaluation.commitloop.statistics import (
    paired_primary_statistics,
    per_case_rows_with_subject,
)

DERIVED_FILES = (
    "metrics.json",
    "per_case_metrics.csv",
    "error_ledger.csv",
    "statistical_results.json",
)


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(stream.getvalue(), encoding="utf-8")


def verify_seal(root: Path) -> None:
    lines = (root / "checksums.sha256").read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError("empty_artifact_seal")
    sealed: set[str] = set()
    for line in lines:
        try:
            digest, relative = line.split("  ", 1)
        except ValueError as exc:
            raise ValueError("malformed_artifact_checksum") from exc
        path = Path(relative)
        if (
            not re.fullmatch(r"[0-9a-f]{64}", digest)
            or path.is_absolute()
            or ".." in path.parts
            or relative in sealed
        ):
            raise ValueError("malformed_artifact_checksum")
        target = root / path
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError("artifact_checksum_mismatch")
        sealed.add(relative)
    actual = {
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file() and path.name != "checksums.sha256"
    }
    if sealed != actual:
        raise ValueError("artifact_seal_inventory_mismatch")


def _per_case_rows(
    *,
    gold_by_case: dict[str, dict[str, Any]],
    subject_by_case: dict[str, str],
    outputs: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    models: list[str],
    conditions: list[str],
) -> list[dict[str, object]]:
    outputs_by_key = {
        (
            str(item["case_id"]),
            str(item["requested_model_id"]),
            str(item["condition"]),
        ): item
        for item in outputs
    }
    errors_by_key = {
        (
            str(item["case_id"]),
            str(item["requested_model_id"]),
            str(item["condition"]),
        ): item
        for item in errors
    }
    rows: list[dict[str, object]] = []
    for case_id in sorted(subject_by_case):
        expected = gold_by_case[case_id]
        for model in models:
            for condition in conditions:
                output = outputs_by_key.get((case_id, model, condition))
                error = errors_by_key.get((case_id, model, condition))
                prediction = (
                    output["prediction"]
                    if output is not None and isinstance(output.get("prediction"), dict)
                    else {}
                )
                rows.append(
                    {
                        "case_id": case_id,
                        "subject_token": subject_by_case[case_id],
                        "model": model,
                        "condition": condition,
                        "output_present": int(output is not None),
                        "failure": str(error.get("error", "")) if error else "",
                        "lifecycle_correct": int(
                            prediction.get("lifecycle_state")
                            == expected.get("lifecycle_state")
                        ),
                        "evidence_correct": int(
                            prediction.get("evidence_state")
                            == expected.get("evidence_state")
                        ),
                        "timeliness_correct": int(
                            prediction.get("timeliness_state")
                            == expected.get("timeliness_state")
                        ),
                        "escalation_correct": int(
                            prediction.get("escalation_state")
                            == expected.get("escalation_state")
                        ),
                        "all_axes_exact": int(
                            all(
                                prediction.get(axis) == expected.get(axis)
                                for axis in (
                                    "lifecycle_state",
                                    "evidence_state",
                                    "timeliness_state",
                                )
                            )
                        ),
                    }
                )
    return rows


def reproduce(source: Path, output: Path) -> dict[str, Any]:
    source = source.resolve()
    output = output.resolve()
    if output == source or source in output.parents or output in source.parents:
        raise ValueError("reproduction_output_must_be_separate")
    verify_seal(source)
    output.mkdir(parents=True, exist_ok=False)

    manifest = _read_json(source / "run_manifest.json")
    outputs = _read_json(source / "solver_outputs.json")
    errors = _read_json(source / "error_ledger.json")
    gold = _read_jsonl(source / "construction_gold.jsonl")
    commitments = _read_jsonl(source / "commitments.jsonl")
    perturbations = _read_jsonl(source / "perturbation_manifest.jsonl")
    if not isinstance(outputs, list) or not isinstance(errors, list):
        raise TypeError("invalid_solver_ledger")
    models = [str(value) for value in manifest["models"]]
    conditions = [str(value) for value in manifest["conditions"]]
    primary_model = str(manifest.get("primary_model") or "")
    if len(models) != 1 or primary_model != models[0]:
        raise ValueError("v5_primary_model_manifest_invalid")
    gold_by_case = {str(item["case_id"]): item for item in gold}
    subject_by_case = {
        str(item["case_id"]): str(item["subject_token"]) for item in commitments
    }
    if set(gold_by_case) != set(subject_by_case):
        raise ValueError("gold_commitment_case_inventory_mismatch")

    metrics = score_outputs(
        gold_by_case,
        outputs,
        errors=errors,
        models=models,
        conditions=conditions,
    )
    metrics["generation"] = {
        "mode": "deterministic_construction_only",
        "expected_case_count": len(subject_by_case),
        "model_review_request_count": 0,
        "clinical_adjudication": "NOT_RUN",
    }
    metrics["adversarial_variants"] = score_adversarial_variants(
        gold_by_case,
        outputs,
        perturbations,
        models=models,
        conditions=conditions,
    )
    metrics["context_volume_bytes"] = {
        condition: sum(
            len(_json(item).encode())
            for item in _read_jsonl(
                source / "solver_packets" / f"{condition}.jsonl"
            )
        )
        for condition in conditions
    }
    _write_json(output / "metrics.json", metrics)

    per_case = _per_case_rows(
        gold_by_case=gold_by_case,
        subject_by_case=subject_by_case,
        outputs=outputs,
        errors=errors,
        models=models,
        conditions=conditions,
    )
    _write_csv(
        output / "per_case_metrics.csv",
        per_case,
        [
            "case_id",
            "subject_token",
            "model",
            "condition",
            "output_present",
            "failure",
            "lifecycle_correct",
            "evidence_correct",
            "timeliness_correct",
            "escalation_correct",
            "all_axes_exact",
        ],
    )
    _write_csv(
        output / "error_ledger.csv",
        errors,
        [
            "key",
            "case_id",
            "condition",
            "requested_model_id",
            "reported_model_id",
            "error",
            "attempts",
            "usage",
        ],
    )
    subject_rows = per_case_rows_with_subject(
        outputs=outputs,
        gold_by_case=gold_by_case,
        subject_by_case=subject_by_case,
        models=models,
        conditions=conditions,
    )
    statistics = {
        **paired_primary_statistics(
            subject_rows,
            primary_model=primary_model,
            reference_condition="glhs_hybrid_thss_strict",
            comparator_condition="full_authorized_history",
        ),
        "status": "DESCRIPTIVE_SYNTHETIC_ONLY",
        "clinical_adjudication": "NOT_RUN",
        "reason": (
            "router_backed_synthetic_not_clinical_evidence"
            if manifest.get("execution_mode") == "phase_b_router"
            else "fake_transport_validation_not_clinical_evidence"
        ),
    }
    _write_json(output / "statistical_results.json", statistics)

    comparisons = {}
    for name in DERIVED_FILES:
        reproduced = output / name
        original = source / name
        comparisons[name] = {
            "source_sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
            "reproduced_sha256": hashlib.sha256(reproduced.read_bytes()).hexdigest(),
            "identical": reproduced.read_bytes() == original.read_bytes(),
        }
    if not all(item["identical"] for item in comparisons.values()):
        raise ValueError("derived_artifact_reproduction_mismatch")
    report = {
        "schema_version": "commitloop-v5-reproduction.v1",
        "status": "PASS",
        "network_access": "DISABLED_IN_PROCESS",
        "provider_calls": 0,
        "source_checksum_sha256": hashlib.sha256(
            (source / "checksums.sha256").read_bytes()
        ).hexdigest(),
        "derived_files": comparisons,
    }
    _write_json(output / "reproduction_report.json", report)
    seal_artifacts(output)
    return report


@contextmanager
def _network_disabled() -> Iterator[None]:
    def denied(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("network_disabled_for_reproduction")

    with (
        patch.object(socket, "socket", denied),
        patch.object(socket, "create_connection", denied),
    ):
        yield


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with _network_disabled():
        report = reproduce(args.source, args.output)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
