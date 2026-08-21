"""Fail-closed metadata validation for an externally curated EHR cohort."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from evaluation.evidence_program.freeze import FreezeError, load_frozen_json

REQUIRED = frozenset(
    {
        "status",
        "dataset",
        "dataset_version",
        "lawful_access_attestation",
        "partition",
        "subject_count",
        "test_subject_tokens_sha256",
        "development_subject_tokens_sha256",
        "inclusion_exclusion",
        "event_count",
        "domain_coverage",
        "missingness",
        "curator_attestation",
        "selection_frozen_at",
        "source_checksum",
        "synthetic_governance_separate",
        "independent_curator",
    }
)


def _token_hash(path: Path) -> str:
    tokens = {
        line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    }
    return hashlib.sha256("\n".join(sorted(tokens)).encode()).hexdigest()


def validate(
    manifest_path: Path,
    development_path: Path | None = None,
    test_path: Path | None = None,
) -> None:
    manifest = load_frozen_json(manifest_path)
    missing = REQUIRED.difference(manifest)
    if missing:
        raise FreezeError("missing_cohort_fields:" + ",".join(sorted(missing)))
    if manifest["status"] != "frozen" or manifest["partition"] != "sealed_holdout":
        raise FreezeError("external_cohort_not_frozen_sealed_holdout")
    if not manifest["lawful_access_attestation"] or not manifest["curator_attestation"]:
        raise FreezeError("lawful_or_curator_attestation_missing")
    if manifest["independent_curator"] is not True:
        raise FreezeError("independent_curator_required_for_headline")
    if manifest["synthetic_governance_separate"] is not True:
        raise FreezeError("synthetic_governance_must_be_separate")
    if development_path is None or test_path is None:
        raise FreezeError("subject_token_files_required_for_disjointness_proof")
    if _token_hash(development_path) != manifest["development_subject_tokens_sha256"]:
        raise FreezeError("development_subject_hash_mismatch")
    if _token_hash(test_path) != manifest["test_subject_tokens_sha256"]:
        raise FreezeError("test_subject_hash_mismatch")
    development_tokens = {
        line.strip()
        for line in development_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    test_tokens = {
        line.strip() for line in test_path.read_text(encoding="utf-8").splitlines() if line.strip()
    }
    if not test_tokens or len(test_tokens) != manifest["subject_count"]:
        raise FreezeError("test_subject_count_mismatch")
    if development_tokens.intersection(test_tokens):
        raise FreezeError("subject_sets_not_disjoint")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--development-subjects", type=Path, required=True)
    parser.add_argument("--test-subjects", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate(args.manifest, args.development_subjects, args.test_subjects)
    except FreezeError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
