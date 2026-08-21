from __future__ import annotations

import argparse
import re
from pathlib import Path

from evaluation.evidence_program.freeze import FreezeError, load_frozen_json

_PSEUDONYMOUS_CODE = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")


def validate(path: Path) -> None:
    value = load_frozen_json(path)
    required = {
        "status",
        "annotation_guide_sha256",
        "annotator_ids",
        "adjudicator_id",
        "oracle_sha256",
        "blinding",
        "reviewer_qualifications",
    }
    if required - value.keys():
        raise FreezeError("missing_annotation_manifest_fields")
    annotators = value["annotator_ids"]
    adjudicator = value["adjudicator_id"]
    if (
        value["status"] != "frozen"
        or not isinstance(annotators, list)
        or len(annotators) != 2
        or not all(
            isinstance(item, str) and _PSEUDONYMOUS_CODE.fullmatch(item) for item in annotators
        )
        or len(set(annotators)) != 2
        or not isinstance(adjudicator, str)
        or not _PSEUDONYMOUS_CODE.fullmatch(adjudicator)
    ):
        raise FreezeError("independent_annotation_not_ready")
    if adjudicator in set(annotators):
        raise FreezeError("adjudicator_must_be_distinct")
    qualifications = value["reviewer_qualifications"]
    required_reviewers = set(annotators) | {adjudicator}
    if not isinstance(qualifications, dict) or set(qualifications) != required_reviewers:
        raise FreezeError("reviewer_qualifications_incomplete")
    for reviewer_id in required_reviewers:
        metadata = qualifications[reviewer_id]
        if not isinstance(metadata, dict):
            raise FreezeError("reviewer_qualification_invalid")
        role_code = metadata.get("role_code")
        if not isinstance(role_code, str) or not role_code.strip():
            raise FreezeError("reviewer_qualification_role_code_required")
        if metadata.get("eligibility_attested") is not True:
            raise FreezeError("reviewer_eligibility_attestation_required")
        if metadata.get("independence_attested") is not True:
            raise FreezeError("reviewer_independence_attestation_required")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate(args.manifest)
    except FreezeError as exc:
        parser.error(str(exc))
