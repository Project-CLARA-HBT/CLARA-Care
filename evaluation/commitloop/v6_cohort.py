"""Generate the subject-disjoint v6 GLHS-Bench cohort before final freezing.

The template families, seeds and subject tokens are independent of v5.  Split
membership is allocated before any runner is invoked: development and
validation are available for iteration, while ``sealed_test`` is withheld for
one final candidate execution.
"""

from __future__ import annotations

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

SCHEMA_VERSION = "commitloop-v6-cohort.v1"
COHORT_NAME = "glhs_bench_subject_disjoint_heldout_cohort.v6"
MASTER_SEED = 2026081301
VALID_CUTOFF = datetime(2027, 6, 1, tzinfo=UTC)
KNOWN_CUTOFF = datetime(2027, 6, 1, tzinfo=UTC)
SPLIT_COUNTS = {"development": 12, "validation": 12, "sealed_test": 48}
STRATA = (
    "backdated_final_visible",
    "post_cutoff_observation",
    "cancellation_after_completion",
    "supersession_after_completion",
    "late_known_cancellation_hidden",
    "contradictory_final_pair",
    "long_backdated_irrelevant_history",
    "knowledge_boundary_exact",
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
    known_at: str,
    relation: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "resourceType": "Observation",
        "id": resource_id,
        "status": status,
        "subject": {"reference": f"Patient/{subject_id}"},
        "effectiveDateTime": valid_at,
        "meta": {"lastUpdated": known_at},
        "code": {"coding": [{"system": "http://loinc.org", "code": code}]},
    }
    if relation is not None:
        result["relation"] = relation
    return result


def _events(stratum: str) -> tuple[str, list[dict[str, str]]]:
    visible = "2027-05-30T00:00:00Z"
    hidden = "2027-06-03T00:00:00Z"
    if stratum == "backdated_final_visible":
        return "2027-05-20T00:00:00Z", [
            {"status": "final", "valid": "2027-05-12T00:00:00Z", "known": visible}
        ]
    if stratum == "post_cutoff_observation":
        return "2027-05-20T00:00:00Z", [
            {"status": "final", "valid": "2027-06-02T00:00:00Z", "known": visible}
        ]
    if stratum == "cancellation_after_completion":
        return "2027-05-20T00:00:00Z", [
            {"status": "final", "valid": "2027-05-10T00:00:00Z", "known": visible},
            {"status": "revoked", "valid": "2027-05-12T00:00:00Z", "known": visible},
        ]
    if stratum == "supersession_after_completion":
        return "2027-05-20T00:00:00Z", [
            {"status": "final", "valid": "2027-05-10T00:00:00Z", "known": visible},
            {"status": "replaced", "valid": "2027-05-13T00:00:00Z", "known": visible},
        ]
    if stratum == "late_known_cancellation_hidden":
        return "2027-05-20T00:00:00Z", [
            {"status": "final", "valid": "2027-05-10T00:00:00Z", "known": visible},
            {"status": "revoked", "valid": "2027-05-11T00:00:00Z", "known": hidden},
        ]
    if stratum == "contradictory_final_pair":
        return "2027-05-20T00:00:00Z", [
            {"status": "final", "valid": "2027-05-10T00:00:00Z", "known": visible},
            {
                "status": "preliminary",
                "valid": "2027-05-11T00:00:00Z",
                "known": visible,
                "relation": "contradicts",
            },
        ]
    if stratum == "long_backdated_irrelevant_history":
        return "2027-05-20T00:00:00Z", [
            {"status": "final", "valid": "2027-04-01T00:00:00Z", "known": visible}
        ]
    if stratum == "knowledge_boundary_exact":
        return "2027-05-20T00:00:00Z", [
            {
                "status": "final",
                "valid": "2027-05-15T00:00:00Z",
                "known": "2027-06-01T00:00:00Z",
            }
        ]
    raise ValueError("unknown_v6_stratum")


def _bundle(
    *, stratum: str, split: str, index: int, seed: int, schema_version: str
) -> dict[str, Any]:
    rng = random.Random(seed)
    opaque = _digest(
        {
            "schema": schema_version,
            "stratum": stratum,
            "split": split,
            "index": index,
            "seed": seed,
        }
    )
    subject_id, code = f"v6-{opaque[:20]}", f"v6-{opaque[20:36]}"
    due, specs = _events(stratum)
    resources: list[dict[str, Any]] = [
        {"resourceType": "Patient", "id": subject_id},
        {
            "resourceType": "ServiceRequest",
            "id": f"request-{opaque[:16]}",
            "status": "active",
            "subject": {"reference": f"Patient/{subject_id}"},
            "authoredOn": "2027-05-01T00:00:00Z",
            "meta": {"lastUpdated": "2027-05-02T00:00:00Z"},
            "code": {"coding": [{"system": "http://loinc.org", "code": code}]},
            "occurrencePeriod": {"end": due},
        },
    ]
    for position, spec in enumerate(specs):
        resources.append(
            _observation(
                subject_id=subject_id,
                resource_id=f"target-{opaque[:12]}-{position}",
                code=code,
                status=spec["status"],
                valid_at=spec["valid"],
                known_at=spec["known"],
                relation=spec.get("relation"),
            )
        )
    noise_count = 20 if stratum == "long_backdated_irrelevant_history" else 8
    for position in range(noise_count):
        resources.append(
            _observation(
                subject_id=subject_id,
                resource_id=f"noise-{opaque[:12]}-{position}",
                code=f"noise-{opaque[36:44]}-{position}",
                status=rng.choice(("amended", "corrected", "registered")),
                valid_at=f"2027-05-{2 + rng.randrange(28):02d}T12:00:00Z",
                known_at="2027-05-30T00:00:00Z",
            )
        )
    patient, *rest = resources
    rng.shuffle(rest)
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": patient}, *({"resource": item} for item in rest)],
    }


def build_cohort(
    *,
    master_seed: int = MASTER_SEED,
    cohort_name: str = COHORT_NAME,
    schema_version: str = SCHEMA_VERSION,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    tokens, bundles, outcomes = set(), set(), Counter()
    for stratum_index, stratum in enumerate(STRATA):
        for split_index, (split, count) in enumerate(SPLIT_COUNTS.items()):
            for index in range(count):
                seed = master_seed + stratum_index * 100_000 + split_index * 10_000 + index
                bundle = _bundle(
                    stratum=stratum,
                    split=split,
                    index=index,
                    seed=seed,
                    schema_version=schema_version,
                )
                token, events = ingest_bundle(bundle, fhir_version="R4", ingested_at=KNOWN_CUTOFF)
                cases = mine_candidates(token, events)
                if len(cases) != 1 or cases[0].status != "ELIGIBLE":
                    raise ValueError("v6_cohort_requires_one_eligible_case_per_subject")
                gold = compile_construction_gold(
                    cases[0],
                    events,
                    valid_cutoff=VALID_CUTOFF,
                    known_cutoff=KNOWN_CUTOFF,
                )
                if gold.get("status") != "SCORABLE":
                    raise ValueError("v6_cohort_gold_not_scorable")
                bundle_hash = _digest(bundle)
                if token in tokens or bundle_hash in bundles:
                    raise ValueError("v6_cohort_duplicate_subject_or_bundle")
                tokens.add(token)
                bundles.add(bundle_hash)
                outcomes[
                    f"{split}:{gold['lifecycle_state']}:{gold['evidence_state']}:{gold['timeliness_state']}"
                ] += 1
                rows.append(
                    {
                        "schema_version": schema_version,
                        "split": split,
                        "stratum": stratum,
                        "seed": seed,
                        "fhir_version": "R4",
                        "subject_token": token,
                        "bundle_sha256": bundle_hash,
                        "bundle": bundle,
                    }
                )
    rows.sort(key=lambda item: (str(item["split"]), str(item["stratum"]), int(item["seed"])))
    manifest = {
        "schema_version": schema_version,
        "status": "GENERATED_NOT_FROZEN",
        "cohort_name": cohort_name,
        "synthetic_software_evaluation_only": True,
        "clinical_adjudication": "NOT_RUN",
        "master_seed": master_seed,
        "seed_reuse_prohibited": True,
        "subject_count": len(rows),
        "split_counts": {
            split: sum(1 for row in rows if row["split"] == split) for split in SPLIT_COUNTS
        },
        "strata": {name: sum(SPLIT_COUNTS.values()) for name in STRATA},
        "template_families": list(STRATA),
        "valid_cutoff": VALID_CUTOFF.isoformat(),
        "known_cutoff": KNOWN_CUTOFF.isoformat(),
        "subject_token_count": len(tokens),
        "bundle_hash_count": len(bundles),
        "outcome_distribution": dict(sorted(outcomes.items())),
        "cohort_payload_sha256": _digest(rows),
        "prior_cohort_overlap_check": "PENDING_FREEZE_REGISTRY",
    }
    return rows, manifest


def write_cohort(
    output_dir: Path,
    *,
    master_seed: int = MASTER_SEED,
    cohort_name: str = COHORT_NAME,
    schema_version: str = SCHEMA_VERSION,
) -> tuple[Path, Path]:
    rows, manifest = build_cohort(
        master_seed=master_seed,
        cohort_name=cohort_name,
        schema_version=schema_version,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    cohort_path, manifest_path = (
        output_dir / "cohort.jsonl",
        output_dir / "cohort_manifest.json",
    )
    cohort_path.write_text("".join(_canonical(row) + "\n" for row in rows), encoding="utf-8")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return cohort_path, manifest_path


def bundles_for_split(
    rows: list[dict[str, Any]], *, split: str
) -> tuple[list[tuple[dict[str, Any], str]], dict[str, str]]:
    """Return exactly one preassigned subject partition for an allowed run."""

    if split not in SPLIT_COUNTS:
        raise ValueError("v6_split_invalid")
    selected = [row for row in rows if row["split"] == split]
    if len(selected) != len(STRATA) * SPLIT_COUNTS[split]:
        raise ValueError("v6_split_inventory_invalid")
    return (
        [(dict(row["bundle"]), str(row["fhir_version"])) for row in selected],
        {str(row["subject_token"]): split for row in selected},
    )
