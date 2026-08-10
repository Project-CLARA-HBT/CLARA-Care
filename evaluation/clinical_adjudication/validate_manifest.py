from __future__ import annotations

import argparse
from pathlib import Path

from evaluation.evidence_program.freeze import FreezeError, load_frozen_json


def validate(path: Path) -> None:
    value = load_frozen_json(path)
    required = {"status", "annotation_guide_sha256", "annotator_ids", "adjudicator_id", "oracle_sha256", "blinding"}
    if required - value.keys():
        raise FreezeError("missing_annotation_manifest_fields")
    if value["status"] != "frozen" or len(set(value["annotator_ids"])) < 2 or not value["adjudicator_id"]:
        raise FreezeError("independent_annotation_not_ready")
    if value["adjudicator_id"] in set(value["annotator_ids"]):
        raise FreezeError("adjudicator_must_be_distinct")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate(args.manifest)
    except FreezeError as exc:
        parser.error(str(exc))
