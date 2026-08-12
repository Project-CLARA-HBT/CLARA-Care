"""Create blinded, no-PHI human-review packets from a sealed synthetic run.

This tool does not label cases, infer human judgments, or establish clinical
validity.  It only prepares an import-compatible packet for qualified external
reviewers.  The arm mapping is kept in a separate sealed file for the study
coordinator; reviewer packets use deterministic opaque arm aliases.
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

PACKET_SCHEMA = "glhs-bench.human-review-packet.v1"
IMPORT_COLUMNS = (
    "case_id",
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


def prepare_packets(*, run_dir: Path, output_dir: Path, split: str) -> dict[str, object]:
    """Write randomized arm packets and an empty human import template."""

    if split not in {"development", "validation", "sealed_test"}:
        raise ValueError("review_packet_split_invalid")
    verify_seal(run_dir)
    partitions = _json(run_dir / "partition_manifest.json")
    commitments = _jsonl(run_dir / "commitments.jsonl")
    manifest = _json(run_dir / "run_manifest.json")
    selected = {
        str(subject) for subject, assigned in partitions.items() if assigned == split
    }
    rows = [item for item in commitments if str(item.get("subject_token")) in selected]
    if not rows:
        raise ValueError("review_packet_split_empty")
    arms = [(str(model), str(condition)) for model in manifest["models"] for condition in manifest["conditions"]]
    nonce = secrets.token_hex(32)
    shuffled = sorted(
        arms,
        key=lambda arm: hashlib.sha256(f"{nonce}:{arm[0]}:{arm[1]}".encode()).hexdigest(),
    )
    aliases = {arm: f"ARM-{index:02d}" for index, arm in enumerate(shuffled, start=1)}
    packets_by_condition = {
        condition: {str(item["case_id"]): item for item in _jsonl(run_dir / "solver_packets" / f"{condition}.jsonl")}
        for _model, condition in arms
    }
    outputs = {
        (str(item["case_id"]), str(item["requested_model_id"]), str(item["condition"])): item
        for item in _json(run_dir / "solver_outputs.json")
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    packets: list[dict[str, object]] = []
    for item in sorted(rows, key=lambda row: str(row["case_id"])):
        case_id = str(item["case_id"])
        opaque_case = hashlib.sha256(f"{nonce}:case:{case_id}".encode()).hexdigest()[:24]
        for model, condition in shuffled:
            packet = packets_by_condition[condition].get(case_id)
            if packet is None:
                raise ValueError("review_packet_context_missing")
            output = outputs.get((case_id, model, condition))
            packets.append(
                {
                    "packet_schema": PACKET_SCHEMA,
                    "case_id": opaque_case,
                    "arm": aliases[(model, condition)],
                    "task": packet["task"],
                    "context": packet["context"],
                    "model_prediction": output.get("prediction") if output else None,
                    "model_output_available": output is not None,
                    "rubric_version": "glhs-bench-human-rubric.v1",
                }
            )
    packets_path = output_dir / "blinded_packets.jsonl"
    packets_path.write_text("".join(json.dumps(item, sort_keys=True) + "\n" for item in packets), encoding="utf-8")
    with (output_dir / "reviewer_import_template.csv").open("w", encoding="utf-8", newline="") as stream:
        csv.DictWriter(stream, fieldnames=IMPORT_COLUMNS).writeheader()
    coordinator_mapping = {
        "schema_version": "glhs-bench.human-review-mapping.v1",
        "warning": "study-coordinator-only; do not share with blinded reviewers",
        "nonce_sha256": hashlib.sha256(nonce.encode()).hexdigest(),
        "arm_mapping": {alias: {"model": arm[0], "condition": arm[1]} for arm, alias in aliases.items()},
        "packet_count": len(packets),
    }
    mapping_path = output_dir / "coordinator_mapping.json"
    mapping_path.write_text(json.dumps(coordinator_mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    review_manifest = {
        "schema_version": "glhs-bench.human-review-manifest.v1",
        "status": "READY_FOR_EXTERNAL_ADJUDICATION",
        "human_attestation": False,
        "clinical_adjudication": "NOT_RUN",
        "reviewer_ids": [],
        "qualifications": "external qualified reviewers required",
        "blinding": "system-blinded; coordinator mapping stored separately",
        "split": split,
        "source_run_checksum_sha256": _digest(run_dir / "checksums.sha256"),
        "packet_sha256": _digest(packets_path),
        "rubric_version": "glhs-bench-human-rubric.v1",
        "import_columns": list(IMPORT_COLUMNS),
    }
    (output_dir / "review_manifest.json").write_text(json.dumps(review_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"status": review_manifest["status"], "packet_count": len(packets), "split": split}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=("development", "validation", "sealed_test"), default="validation")
    args = parser.parse_args()
    print(json.dumps(prepare_packets(run_dir=args.run_dir, output_dir=args.output, split=args.split), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
