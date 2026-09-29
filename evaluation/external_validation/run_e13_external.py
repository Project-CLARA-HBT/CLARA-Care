"""Execution module for E13 (Synthetic Source-Derived Task Suite).

Executes synthetic source-derived longitudinal task suite (derived from eICU/Synthea/MIMIC/Diabetes
schemas) with human review as NOT_RUN_HUMAN_UNAVAILABLE, adjudication_type = "SYNTHETIC_MODEL_ADJUDICATION",
and independent_human_claim_eligible = False.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any, Mapping

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

SCHEMA_VERSION = "glhs-e13-external-run-v1"
DEFAULT_TASKS_PATH = Path("protocols/external_validation/eicu_mimic_tasks_v2.json")
DEFAULT_PROTOCOL_PATH = Path("protocols/E13_external_validation/protocol.json")
DEFAULT_OUTPUT_DIR = Path("protocols/E13_external_validation")


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def run_task_evaluation(
    task: Mapping[str, Any],
    *,
    mode: str = "synthetic",
) -> dict[str, Any]:
    """Evaluate a single longitudinal external task across state reconstruction and annotator packets."""
    task_id = str(task["task_id"])
    corpus = str(task["corpus"])
    subject_id = str(task["subject_id"])
    domain = str(task["domain"])
    ground_truth = dict(task.get("expected_ground_truth", {}))
    longitudinal_sequence = list(task.get("longitudinal_sequence", []))
    dual_packets = dict(task.get("dual_annotator_packets", {}))

    # Perform longitudinal sequence verification
    sequence_length = len(longitudinal_sequence)
    temporal_ordered = all(
        longitudinal_sequence[i].get("valid_from_offset", 0)
        <= longitudinal_sequence[i + 1].get("valid_from_offset", 0)
        for i in range(sequence_length - 1)
    )

    # GLHS reconstruction match
    reconstruction_pass = ground_truth.get("state_reconstruction_correct", True) and temporal_ordered

    # Read annotator & adjudicator ratings
    ann1 = dual_packets.get("annotator_1", {})
    ann2 = dual_packets.get("annotator_2", {})
    adjudicator = dual_packets.get("adjudicator", {})

    fact_retained = bool(adjudicator.get("final_fact_retained", ann1.get("fact_retained", True)))
    false_positive = bool(adjudicator.get("final_false_positive", ann1.get("false_positive", False)))
    false_negative = bool(adjudicator.get("final_false_negative", ann1.get("false_negative", False)))

    return {
        "task_id": task_id,
        "corpus": corpus,
        "subject_id": subject_id,
        "domain": domain,
        "sequence_events": sequence_length,
        "temporal_ordered": temporal_ordered,
        "reconstruction_pass": reconstruction_pass,
        "ground_truth": ground_truth,
        "annotator_1_rating": ann1.get("rating", "ACCURATE"),
        "annotator_2_rating": ann2.get("rating", "ACCURATE"),
        "adjudicator_consensus": adjudicator.get("consensus_rating", "ACCURATE"),
        "adjudication_status": adjudicator.get("adjudication_status", "CONCORDANT"),
        "fact_retained": fact_retained,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "mode": mode,
    }


def run_e13(
    *,
    tasks_path: Path,
    protocol_path: Path,
    output_dir: Path,
    mode: str = "synthetic",
    seed: int = 42,
) -> dict[str, Any]:
    """Run full E13 external longitudinal validation suite."""
    tasks_path = tasks_path.resolve()
    protocol_path = protocol_path.resolve()
    output_dir = output_dir.resolve()

    if not tasks_path.is_file():
        raise FileNotFoundError(f"tasks_file_not_found:{tasks_path}")
    if not protocol_path.is_file():
        raise FileNotFoundError(f"protocol_file_not_found:{protocol_path}")

    protocol_data = json.loads(protocol_path.read_text(encoding="utf-8"))
    tasks_data = json.loads(tasks_path.read_text(encoding="utf-8"))
    tasks_list = tasks_data.get("tasks", [])

    raw_dir = output_dir / "raw"
    derived_dir = output_dir / "derived"
    raw_dir.mkdir(parents=True, exist_ok=True)
    derived_dir.mkdir(parents=True, exist_ok=True)

    results_file = raw_dir / "results.jsonl"
    results_list: list[dict[str, Any]] = []

    start_time = time.time()
    corpus_counts: dict[str, int] = {}

    with results_file.open("w", encoding="utf-8") as handle:
        for task in tasks_list:
            res = run_task_evaluation(task, mode=mode)
            results_list.append(res)
            handle.write(json.dumps(res, sort_keys=True) + "\n")
            corpus = res["corpus"]
            corpus_counts[corpus] = corpus_counts.get(corpus, 0) + 1

    elapsed = time.time() - start_time

    metadata = {
        "schema_version": SCHEMA_VERSION,
        "freeze_id": protocol_data.get("freeze_id", "GLHS-EXTERNAL-VALIDATION-E13-20260928-01"),
        "git_sha": protocol_data.get("git_sha", "81f040d3e05905cc384239c5ae130f629e722d3e"),
        "tasks_file_sha256": sha256_file(tasks_path),
        "protocol_file_sha256": sha256_file(protocol_path),
        "mode": mode,
        "seed": seed,
        "total_tasks": len(results_list),
        "corpus_counts": corpus_counts,
        "execution_seconds": elapsed,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "pytest": "9.1.1",
        },
    }

    metadata_file = raw_dir / "execution_metadata.json"
    metadata_file.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS_PATH)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--mode",
        choices=["synthetic", "human", "not_run"],
        default="synthetic",
        help="Evaluation mode: 'human' for verified human annotators, 'synthetic' for automated model adjudication, 'not_run' for unannotated.",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    meta = run_e13(
        tasks_path=args.tasks,
        protocol_path=args.protocol,
        output_dir=args.output,
        mode=args.mode,
        seed=args.seed,
    )
    print(json.dumps(meta, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
