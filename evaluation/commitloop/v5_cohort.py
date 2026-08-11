"""Generate the independent deterministic Phase-B v5 synthetic cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evaluation.commitloop.candidate_mining import mine_candidates
from evaluation.commitloop.fhir_ingest import ingest_bundle
from evaluation.commitloop.oracle import compile_construction_gold

SCHEMA_VERSION = "commitloop-v5-cohort.v1"
COHORT_NAME = "confirmatory_controlled_r4_factorial_cohort.v5"
MASTER_SEED = 2026081201
SUBJECTS_PER_STRATUM = 48
VALID_CUTOFF = datetime(2027, 4, 1, tzinfo=UTC)
KNOWN_CUTOFF = datetime(2027, 4, 1, tzinfo=UTC)
STRATA = (
    "due_edge_final_interleaved",
    "grace_edge_partial_interleaved",
    "knowledge_cutoff_final_hidden",
    "same_time_cancellation_precedence",
    "same_time_supersession_precedence",
    "conflict_after_valid_completion",
    "undated_multistatus_completion",
    "deep_relevant_history_old_decisive",
)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _observation(
    *,
    subject_id: str,
    resource_id: str,
    code: str,
    status: str,
    valid_at: str,
    known_at: str = "2027-03-31T00:00:00Z",
    relation: str | None = None,
) -> dict[str, Any]:
    resource: dict[str, Any] = {
        "resourceType": "Observation",
        "id": resource_id,
        "status": status,
        "subject": {"reference": f"Patient/{subject_id}"},
        "effectiveDateTime": valid_at,
        "meta": {"lastUpdated": known_at},
        "code": {"coding": [{"system": "http://loinc.org", "code": code}]},
    }
    if relation is not None:
        resource["relation"] = relation
    return resource


def _relevant_specs(stratum: str) -> tuple[str | None, list[dict[str, str]]]:
    if stratum == "due_edge_final_interleaved":
        return "2027-03-20T00:00:00Z", [
            {"status": "final", "valid_at": "2027-03-20T00:00:00Z"}
        ]
    if stratum == "grace_edge_partial_interleaved":
        return "2027-03-10T00:00:00Z", [
            {"status": "preliminary", "valid_at": "2027-03-17T00:00:00Z"}
        ]
    if stratum == "knowledge_cutoff_final_hidden":
        return "2027-03-15T00:00:00Z", [
            {"status": "preliminary", "valid_at": "2027-03-18T00:00:00Z"},
            {
                "status": "final",
                "valid_at": "2027-03-10T00:00:00Z",
                "known_at": "2027-04-03T00:00:00Z",
            },
        ]
    if stratum == "same_time_cancellation_precedence":
        return "2027-03-20T00:00:00Z", [
            {"status": "final", "valid_at": "2027-03-11T00:00:00Z"},
            {"status": "revoked", "valid_at": "2027-03-11T00:00:00Z"},
        ]
    if stratum == "same_time_supersession_precedence":
        return "2027-03-20T00:00:00Z", [
            {"status": "final", "valid_at": "2027-03-25T00:00:00Z"},
            {"status": "replaced", "valid_at": "2027-03-25T00:00:00Z"},
        ]
    if stratum == "conflict_after_valid_completion":
        return "2027-03-20T00:00:00Z", [
            {"status": "final", "valid_at": "2027-03-10T00:00:00Z"},
            {
                "status": "preliminary",
                "valid_at": "2027-03-12T00:00:00Z",
                "relation": "contradicts",
            },
        ]
    if stratum == "undated_multistatus_completion":
        return None, [
            {"status": "registered", "valid_at": "2027-03-08T00:00:00Z"},
            {"status": "final", "valid_at": "2027-03-14T00:00:00Z"},
            {"status": "amended", "valid_at": "2027-03-16T00:00:00Z"},
        ]
    if stratum == "deep_relevant_history_old_decisive":
        return "2027-03-20T00:00:00Z", [
            {"status": "final", "valid_at": "2027-03-05T00:00:00Z"},
            *[
                {
                    "status": "amended",
                    "valid_at": f"2027-03-{day:02d}T00:00:00Z",
                }
                for day in range(6, 15)
            ],
        ]
    raise ValueError("unknown_v5_stratum")


def _bundle(*, stratum: str, index: int, seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    opaque = hashlib.sha256(f"{SCHEMA_VERSION}:{stratum}:{index}:{seed}".encode()).hexdigest()
    subject_id = f"v5-{opaque[:20]}"
    target_code = f"v5-{opaque[20:36]}"
    due_time, relevant_specs = _relevant_specs(stratum)
    request: dict[str, Any] = {
        "resourceType": "ServiceRequest",
        "id": f"request-{opaque[:16]}",
        "status": "active",
        "subject": {"reference": f"Patient/{subject_id}"},
        "authoredOn": "2027-03-01T00:00:00Z",
        "meta": {"lastUpdated": "2027-03-02T00:00:00Z"},
        "code": {
            "coding": [{"system": "http://loinc.org", "code": target_code}]
        },
    }
    if due_time is not None:
        request["occurrencePeriod"] = {"end": due_time}
    resources: list[dict[str, Any]] = [
        {"resourceType": "Patient", "id": subject_id},
        request,
    ]
    for event_index, spec in enumerate(relevant_specs):
        resources.append(
            _observation(
                subject_id=subject_id,
                resource_id=f"target-{opaque[:12]}-{event_index:02d}",
                code=target_code,
                status=spec["status"],
                valid_at=spec["valid_at"],
                known_at=spec.get("known_at", "2027-03-31T00:00:00Z"),
                relation=spec.get("relation"),
            )
        )
    noise_statuses = ("amended", "corrected", "registered", "unknown")
    for noise_index in range(6 + index % 5):
        day = 2 + rng.randrange(0, 28)
        resources.append(
            _observation(
                subject_id=subject_id,
                resource_id=f"noise-{opaque[:12]}-{noise_index:02d}",
                code=f"noise-{opaque[36:44]}-{noise_index:02d}",
                status=rng.choice(noise_statuses),
                valid_at=f"2027-03-{day:02d}T12:00:00Z",
            )
        )
    patient, anchor, *events = resources
    rng.shuffle(events)
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"resource": patient},
            *({"resource": resource} for resource in [*events, anchor]),
        ],
    }


def build_cohort() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    subject_tokens: set[str] = set()
    bundle_hashes: set[str] = set()
    outcomes: Counter[str] = Counter()
    for stratum_index, stratum in enumerate(STRATA):
        for index in range(SUBJECTS_PER_STRATUM):
            seed = MASTER_SEED + stratum_index * 10000 + index
            bundle = _bundle(stratum=stratum, index=index, seed=seed)
            token, events = ingest_bundle(
                bundle, fhir_version="R4", ingested_at=KNOWN_CUTOFF
            )
            cases = mine_candidates(token, events)
            if len(cases) != 1 or cases[0].status != "ELIGIBLE":
                raise ValueError("v5_cohort_requires_one_eligible_case_per_subject")
            gold = compile_construction_gold(
                cases[0],
                events,
                valid_cutoff=VALID_CUTOFF,
                known_cutoff=KNOWN_CUTOFF,
            )
            if gold.get("status") != "SCORABLE":
                raise ValueError("v5_cohort_gold_not_scorable")
            bundle_hash = _digest(bundle)
            if token in subject_tokens or bundle_hash in bundle_hashes:
                raise ValueError("v5_cohort_duplicate_subject_or_bundle")
            subject_tokens.add(token)
            bundle_hashes.add(bundle_hash)
            outcomes[
                ":".join(
                    str(gold[field])
                    for field in (
                        "lifecycle_state",
                        "evidence_state",
                        "timeliness_state",
                    )
                )
            ] += 1
            rows.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "stratum": stratum,
                    "seed": seed,
                    "fhir_version": "R4",
                    "subject_token": token,
                    "bundle_sha256": bundle_hash,
                    "bundle": bundle,
                }
            )
    rows.sort(key=lambda item: (str(item["stratum"]), int(item["seed"])))
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "GENERATED_NOT_FROZEN",
        "cohort_name": COHORT_NAME,
        "synthetic_software_evaluation_only": True,
        "clinical_adjudication": "NOT_RUN",
        "master_seed": MASTER_SEED,
        "seed_reuse_prohibited": True,
        "subject_count": len(rows),
        "cases_per_subject": 1,
        "strata": {name: SUBJECTS_PER_STRATUM for name in STRATA},
        "template_families": list(STRATA),
        "valid_cutoff": VALID_CUTOFF.isoformat(),
        "known_cutoff": KNOWN_CUTOFF.isoformat(),
        "subject_token_count": len(subject_tokens),
        "bundle_hash_count": len(bundle_hashes),
        "outcome_distribution": dict(sorted(outcomes.items())),
        "cohort_payload_sha256": _digest(rows),
        "prior_cohort_overlap_check": "PENDING_FREEZE_REGISTRY",
    }
    return rows, manifest


def write_cohort(output_dir: Path) -> tuple[Path, Path]:
    rows, manifest = build_cohort()
    output_dir.mkdir(parents=True, exist_ok=True)
    cohort_path = output_dir / "cohort.jsonl"
    manifest_path = output_dir / "cohort_manifest.json"
    cohort_path.write_text(
        "".join(_canonical(item) + "\n" for item in rows), encoding="utf-8"
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return cohort_path, manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    cohort_path, manifest_path = write_cohort(args.output_dir)
    print(cohort_path)
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
