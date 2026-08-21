"""Evaluate source-timestamp state selection across three MIMIC Demo FHIR domains.

This is operational/source-derived evidence, not clinician-adjudicated truth.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from evaluation.comparator_studies.bitemporal_state_arbitration import (
    ArbitrationEvent,
    arbitrate,
)

SYSTEMS = ("latest_knowledge_lww", "valid_time_resolver", "btsa_mechanism_mapped")


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _btsa(events: list[dict[str, str]], index_time: str) -> tuple[str | None, bool]:
    ordered = sorted(events, key=lambda item: (item["knowledge_time"], item["event_id"]))
    inputs: list[ArbitrationEvent] = []
    active_id: str | None = None
    active_value: str | None = None
    active_valid: str | None = None
    for event in ordered:
        relation = "SUPPORT"
        target = active_id
        if active_id is None:
            target = None
        elif event["value_fingerprint"] == active_value:
            relation = "SUPPORT"
        elif event["valid_time"] > str(active_valid):
            relation = "SUPERSEDE"
        else:
            relation = "BRANCH-CONFLICT"
        inputs.append(
            ArbitrationEvent(
                event_id=event["event_id"],
                slot="source_slot",
                value=event["value_fingerprint"],
                valid_from=_dt(event["valid_time"]),
                valid_to=None,
                known_at=_dt(event["knowledge_time"]),
                authority=1,
                relation=relation,
                target_id=target,
            )
        )
        if relation in {"SUPERSEDE", "REFINE"} or active_id is None:
            active_id = event["event_id"]
            active_value = event["value_fingerprint"]
            active_valid = event["valid_time"]
    result = arbitrate(
        inputs,
        valid_at=_dt(index_time),
        known_at=max(item.known_at for item in inputs),
    )
    selected = result.active_ids[0] if len(result.active_ids) == 1 else None
    return selected, bool(result.conflict_ids)


def run(records: Path, output_dir: Path) -> dict[str, object]:
    outputs: list[dict[str, object]] = []
    counts: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    excluded_ties = 0
    subject_tokens: set[str] = set()
    with records.open(encoding="utf-8") as stream:
        for line in stream:
            task = json.loads(line)
            events = task["structured_events"]
            latest_valid = max(event["valid_time"] for event in events)
            latest_candidates = [event for event in events if event["valid_time"] == latest_valid]
            if len(latest_candidates) != 1:
                excluded_ties += 1
                continue
            target = latest_candidates[0]["event_id"]
            lww = max(events, key=lambda item: (item["knowledge_time"], item["event_id"]))[
                "event_id"
            ]
            resolver = target
            btsa, conflict = _btsa(events, task["index_time"])
            selections = {
                "latest_knowledge_lww": lww,
                "valid_time_resolver": resolver,
                "btsa_mechanism_mapped": btsa,
            }
            subject_tokens.add(task["subject_token"])
            for system, selected in selections.items():
                correct = selected == target
                counts[(task["domain"], system)][1] += 1
                counts[(task["domain"], system)][0] += int(correct)
                outputs.append(
                    {
                        "task_id": task["task_id"],
                        "subject_token": task["subject_token"],
                        "domain": task["domain"],
                        "system": system,
                        "selected_event_id": selected or "",
                        "source_target_event_id": target,
                        "state_correct": correct,
                        "conflict_preserved": conflict if system == "btsa_mechanism_mapped" else "",
                        "ground_truth_kind": task["ground_truth_kind"],
                    }
                )
    domain_rows = [
        {
            "domain": domain,
            "system": system,
            "correct": value[0],
            "total": value[1],
            "rate": value[0] / value[1] if value[1] else None,
        }
        for (domain, system), value in sorted(counts.items())
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "system_outputs.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(outputs[0]))
        writer.writeheader()
        writer.writerows(outputs)
    with (output_dir / "domain_results.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(domain_rows[0]))
        writer.writeheader()
        writer.writerows(domain_rows)
    summary = {
        "schema_version": "mimic-demo-source-derived-domain-eval-v1",
        "status": "completed_not_clinician_adjudicated",
        "subjects": len(subject_tokens),
        "eligible_tasks": len(outputs) // len(SYSTEMS),
        "excluded_temporal_ties": excluded_ties,
        "systems": list(SYSTEMS),
        "domains": sorted({row["domain"] for row in domain_rows}),
        "domain_results": domain_rows,
        "limitations": [
            "MIMIC-IV Demo on FHIR, not full MIMIC-IV.",
            "Targets are derived from observable FHIR timestamps, not clinician adjudication.",
            "BTSA relation classification is an explicitly documented mechanism mapping.",
            "No GLHS clinical correctness or clinical safety claim is permitted.",
        ],
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "report.md").write_text(
        "# MIMIC Demo source-derived domain evaluation\n\n"
        "This run is not clinician-adjudicated and is not clinical validation.\n\n"
        + "\n".join(
            f"- {row['domain']} / {row['system']}: {row['correct']}/{row['total']}"
            for row in domain_rows
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "mimic-demo-source-derived-domain-evidence-v1",
        "summary_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
        "artifacts": ["summary.json", "system_outputs.csv", "domain_results.csv", "report.md"],
    }
    (output_dir / "evidence-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.records, args.output)
