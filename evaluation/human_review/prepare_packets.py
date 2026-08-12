"""Create method-blinded human-review packets from a sealed GLHS-Bench run.

This tool prepares review material only. It does not create human labels, infer
clinical correctness, or establish reviewer independence. Reviewers receive the
same neutral source context for every candidate derived from a source case;
model and experimental-condition identities remain coordinator-only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import secrets
from pathlib import Path
from typing import Any

from evaluation.commitloop.v5_reproduce import verify_seal

PACKET_SCHEMA = "glhs-bench.human-review-packet.v2"
RUBRIC_VERSION = "glhs-bench-human-rubric.v2"
REFERENCE_CONTEXT_PREFERENCE = ("full_authorized_history", "long_context_chronological")
IMPORT_COLUMNS = (
    "packet_id",
    "reviewer_id",
    "lifecycle_state",
    "evidence_state",
    "timeliness_state",
    "escalation_state",
    "unsupported_assertion",
    "critical_omission",
    "prohibited_disclosure",
    "notes",
    "reviewed_at",
)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _opaque(seed: str, *parts: str, length: int = 24) -> str:
    return hashlib.sha256(":".join((seed, *parts)).encode()).hexdigest()[:length]


def _require_complete_source_run(manifest: dict[str, Any]) -> None:
    if manifest.get("run_status") != "COMPLETE":
        raise ValueError("review_source_run_not_complete")
    try:
        expected = int(manifest["expected_cell_count"])
        completed = int(manifest["completed_cell_count"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("review_source_run_counts_invalid") from exc
    if expected <= 0 or completed != expected:
        raise ValueError("review_source_run_cells_incomplete")


def _select_reference_condition(conditions: list[str]) -> str:
    for condition in REFERENCE_CONTEXT_PREFERENCE:
        if condition in conditions:
            return condition
    raise ValueError("review_reference_context_missing")


def _neutral_context(packet: dict[str, Any]) -> dict[str, Any]:
    context = packet.get("context")
    if not isinstance(context, dict) or not isinstance(context.get("events"), list):
        raise ValueError("review_reference_context_invalid")
    # Do not expose the method-specific representation/condition label.
    return {"events": context["events"]}


def _task(reference_packet: dict[str, Any], commitment: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "task",
        "anchor_evidence_id",
        "anchor_valid_time",
        "domain",
        "action",
        "target",
        "due_time",
        "grace_end",
        "valid_cutoff",
        "known_cutoff",
    )
    task = {field: reference_packet.get(field) for field in fields}
    task["fulfillment_predicate"] = commitment.get("fulfillment_predicate")
    if not isinstance(task.get("task"), str) or not task["task"]:
        raise ValueError("review_task_invalid")
    return task


def prepare_packets(
    *,
    run_dir: Path,
    output_dir: Path,
    split: str,
    randomization_seed: str | None = None,
) -> dict[str, object]:
    """Write randomized, method-blinded packets and a prefilled import sheet."""

    if split not in {"development", "validation", "sealed_test"}:
        raise ValueError("review_packet_split_invalid")
    verify_seal(run_dir)
    partitions = _json(run_dir / "partition_manifest.json")
    commitments = _jsonl(run_dir / "commitments.jsonl")
    manifest = _json(run_dir / "run_manifest.json")
    source_manifest = _json(run_dir / "source_manifest.json")
    _require_complete_source_run(manifest)
    if source_manifest.get("raw_patient_resources_persisted") is not False:
        raise ValueError("review_source_data_boundary_unverified")

    raw_models = manifest.get("models")
    raw_conditions = manifest.get("conditions")
    if (
        not isinstance(raw_models, list)
        or not raw_models
        or any(not isinstance(value, str) or not value for value in raw_models)
        or len(raw_models) != len(set(raw_models))
    ):
        raise ValueError("review_models_invalid")
    if (
        not isinstance(raw_conditions, list)
        or not raw_conditions
        or any(not isinstance(value, str) or not value for value in raw_conditions)
        or len(raw_conditions) != len(set(raw_conditions))
    ):
        raise ValueError("review_conditions_invalid")
    models = list(raw_models)
    conditions = list(raw_conditions)
    reference_condition = _select_reference_condition(conditions)

    selected = {str(subject) for subject, assigned in partitions.items() if assigned == split}
    rows = [item for item in commitments if str(item.get("subject_token")) in selected]
    if not rows:
        raise ValueError("review_packet_split_empty")
    commitments_by_case: dict[str, dict[str, Any]] = {}
    for item in rows:
        case_id = item.get("case_id")
        if not isinstance(case_id, str) or not case_id or case_id in commitments_by_case:
            raise ValueError("review_case_ids_invalid")
        commitments_by_case[case_id] = item

    packets_by_condition: dict[str, dict[str, dict[str, Any]]] = {}
    for condition in conditions:
        records = _jsonl(run_dir / "solver_packets" / f"{condition}.jsonl")
        indexed = {str(item["case_id"]): item for item in records}
        if len(indexed) != len(records):
            raise ValueError("review_solver_packet_duplicate_case")
        packets_by_condition[condition] = indexed

    output_records = _json(run_dir / "solver_outputs.json")
    if not isinstance(output_records, list):
        raise ValueError("review_solver_outputs_invalid")
    outputs: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in output_records:
        if not isinstance(item, dict):
            raise ValueError("review_solver_outputs_invalid")
        case_id = item.get("case_id")
        model_id = item.get("requested_model_id")
        condition = item.get("condition")
        if not all(isinstance(value, str) and value for value in (case_id, model_id, condition)):
            raise ValueError("review_solver_outputs_invalid")
        key = (case_id, model_id, condition)
        if key in outputs:
            raise ValueError("review_solver_output_duplicate_cell")
        outputs[key] = item

    seed = (randomization_seed or secrets.token_hex(32)).strip()
    if not seed:
        raise ValueError("review_randomization_seed_invalid")

    review_packets: list[dict[str, object]] = []
    mapping: dict[str, dict[str, object]] = {}
    for case_id in sorted(commitments_by_case):
        reference = packets_by_condition[reference_condition].get(case_id)
        if reference is None:
            raise ValueError("review_reference_case_missing")
        task = _task(reference, commitments_by_case[case_id])
        source_context = _neutral_context(reference)
        for model in models:
            for condition in conditions:
                source_packet = packets_by_condition[condition].get(case_id)
                if source_packet is None:
                    raise ValueError("review_packet_context_missing")
                output = outputs.get((case_id, model, condition))
                if output is None or not isinstance(output.get("prediction"), dict):
                    # Missing provider cells must be handled as run failures, not
                    # silently omitted from a human-reviewed comparison.
                    raise ValueError("review_packet_model_output_missing")
                packet_id = _opaque(seed, "packet", case_id, model, condition)
                if packet_id in mapping:
                    raise ValueError("review_packet_id_collision")
                review_packets.append(
                    {
                        "packet_schema": PACKET_SCHEMA,
                        "packet_id": packet_id,
                        "task": task,
                        "source_context": source_context,
                        "candidate_prediction": output["prediction"],
                        "rubric_version": RUBRIC_VERSION,
                    }
                )
                mapping[packet_id] = {
                    "source_case_id": case_id,
                    "requested_model_id": model,
                    "reported_model_id": output.get("reported_model_id"),
                    "condition": condition,
                    "source_solver_packet_sha256": source_packet.get("packet_sha256"),
                    "source_response_sha256": output.get("response_sha256"),
                }

    # Randomize across the complete candidate pool. Do not group all methods for
    # one source case together or preserve model/condition ordering.
    review_packets.sort(key=lambda item: _opaque(seed, "order", str(item["packet_id"]), length=64))

    output_dir.mkdir(parents=True, exist_ok=False)
    packets_path = output_dir / "blinded_packets.jsonl"
    packets_path.write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in review_packets),
        encoding="utf-8",
    )
    template_path = output_dir / "reviewer_import_template.csv"
    with template_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=IMPORT_COLUMNS)
        writer.writeheader()
        for packet in review_packets:
            row = {column: "" for column in IMPORT_COLUMNS}
            row["packet_id"] = str(packet["packet_id"])
            writer.writerow(row)

    rubric_source = Path(__file__).with_name("GLHS_BENCH_RUBRIC.md")
    rubric_path = output_dir / "GLHS_BENCH_RUBRIC.md"
    rubric_path.write_bytes(rubric_source.read_bytes())

    coordinator_dir = output_dir / "coordinator_only"
    coordinator_dir.mkdir()
    mapping_path = coordinator_dir / "coordinator_mapping.json"
    mapping_path.write_text(
        json.dumps(
            {
                "schema_version": "glhs-bench.human-review-mapping.v2",
                "warning": "COORDINATOR ONLY; sharing this file breaks reviewer blinding",
                "randomization_seed": seed,
                "randomization_seed_sha256": hashlib.sha256(seed.encode()).hexdigest(),
                "reference_context_condition": reference_condition,
                "packet_mapping": mapping,
                "packet_count": len(review_packets),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    review_manifest = {
        "schema_version": "glhs-bench.human-review-manifest.v2",
        "status": "READY_FOR_EXTERNAL_ADJUDICATION",
        "human_attestation": False,
        "clinical_adjudication": "NOT_RUN",
        "adjudication_scope": "structural_state_review_not_clinical_validity",
        "reviewer_ids": [],
        "qualifications": "external qualified reviewers required",
        "blinding": (
            "model and experimental-condition labels absent from reviewer packets; "
            "all candidates for a source case use the same neutral source context; "
            "packet order randomized"
        ),
        "blinding_limit": (
            "repeated source material may permit partial case recognition; no claim of perfect concealment"
        ),
        "split": split,
        "source_run_status": manifest["run_status"],
        "source_run_checksum_sha256": _digest(run_dir / "checksums.sha256"),
        "source_run_manifest_sha256": _digest(run_dir / "run_manifest.json"),
        "source_data_manifest_sha256": _digest(run_dir / "source_manifest.json"),
        "packet_sha256": _digest(packets_path),
        "import_template_sha256": _digest(template_path),
        "rubric_sha256": _digest(rubric_path),
        "coordinator_mapping_sha256": _digest(mapping_path),
        "randomization_seed_sha256": hashlib.sha256(seed.encode()).hexdigest(),
        "packet_schema": PACKET_SCHEMA,
        "rubric_version": RUBRIC_VERSION,
        "import_columns": list(IMPORT_COLUMNS),
        "packet_count": len(review_packets),
    }
    (output_dir / "review_manifest.json").write_text(
        json.dumps(review_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {"status": review_manifest["status"], "packet_count": len(review_packets), "split": split}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=("development", "validation", "sealed_test"), default="validation")
    parser.add_argument(
        "--randomization-seed-file",
        type=Path,
        help="Optional coordinator-only text file containing a fixed secret seed.",
    )
    args = parser.parse_args()
    seed = (
        args.randomization_seed_file.read_text(encoding="utf-8").strip()
        if args.randomization_seed_file is not None
        else None
    )
    print(
        json.dumps(
            prepare_packets(
                run_dir=args.run_dir,
                output_dir=args.output,
                split=args.split,
                randomization_seed=seed,
            ),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
