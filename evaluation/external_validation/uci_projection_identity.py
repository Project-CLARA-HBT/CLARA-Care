"""Replay the UCI 296 paired medication projection study and emit aggregate counts."""

import csv
import io
import json
import zipfile
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path

from clara_api.glhs.inference_envelope import compute_projection_digest

from datasets.adapters.diabetes_130_tabular import DATA_MEMBER, MEDICATION_FIELDS
from scripts.data._registry import get_dataset, load_registry, resolve_local_source, sha256_file
from scripts.data.verify_manifest import verify_frozen_manifest

DATASET = "diabetes_130_us_hospitals"
PROTOCOL = Path(__file__).with_name("protocols") / "uci296-projection-identity-v1.md"
PRESENCE = {"No": False, "Steady": True, "Down": True, "Up": True, "?": None, "": None}


def paired_counts(rows: Iterable[Mapping[str, str]]) -> dict[str, int]:
    encounters = set()
    per_person: Counter[str] = Counter()
    first: dict[str, dict[str, str]] = {}
    exact = coarse_only = different = disagreements = 0
    for row in rows:
        subject, encounter = row["patient_nbr"], row["encounter_id"]
        if subject in ("?", "", None) or encounter in ("?", "", None):
            raise ValueError("encounter_key_missing")
        if encounter in encounters:
            raise ValueError("duplicate_encounter")
        encounters.add(encounter)
        projection = {key: row[key] for key in MEDICATION_FIELDS}
        if any(value not in PRESENCE for value in projection.values()):
            raise ValueError("unknown_medication_status")
        per_person[subject] += 1
        if per_person[subject] == 1:
            first[subject] = projection
        elif per_person[subject] == 2:
            previous = first.pop(subject)
            same = previous == projection
            digest_equal = compute_projection_digest(previous) == compute_projection_digest(
                projection
            )
            disagreements += int(same != digest_equal)
            if same:
                exact += 1
            elif all(PRESENCE[previous[k]] == PRESENCE[projection[k]] for k in MEDICATION_FIELDS):
                coarse_only += 1
            else:
                different += 1
    pairs = exact + coarse_only + different
    return {
        "encounters": len(encounters),
        "subjects": len(per_person),
        "singletons": len(first),
        "paired_subjects": pairs,
        "encounters_after_second": len(encounters) - len(first) - 2 * pairs,
        "equal_full_projection": exact,
        "equal_only_on_presence": coarse_only,
        "different_on_presence": different,
        "digest_vs_direct_equality_disagreements": disagreements,
    }


def replay() -> dict:
    dataset = get_dataset(load_registry(), DATASET)
    manifest = Path(dataset["checksum_manifest"])
    verified = verify_frozen_manifest(DATASET, manifest_path=manifest)
    files = json.loads(manifest.read_text())["verification"]["files"]
    if len(files) != 1:
        raise ValueError("expected_one_source_archive")
    archive = resolve_local_source(dataset) / files[0]["path"]
    with zipfile.ZipFile(archive) as source, source.open(DATA_MEMBER) as stream:
        reader = csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig", newline=""))
        columns = reader.fieldnames or []
        if len(set(columns)) != len(columns) or set(
            ("patient_nbr", "encounter_id", *MEDICATION_FIELDS)
        ) - set(columns):
            raise ValueError("source_schema_invalid")
        counts = paired_counts(reader)
    return {
        "schema": "uci296-projection-identity.v1",
        "dataset_doi": "10.24432/C5230J",
        "source_sha256": files[0]["sha256"],
        "source_manifest_sha256": verified["manifest_file_sha256"],
        "protocol_sha256": sha256_file(PROTOCOL),
        "runner_sha256": sha256_file(Path(__file__)),
        "counts": counts,
        "independent_unit": "subject",
        "scope": "descriptive_source_projection_identity",
    }


if __name__ == "__main__":
    print(json.dumps(replay(), indent=2, sort_keys=True))
