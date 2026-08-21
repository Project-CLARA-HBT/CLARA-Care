from __future__ import annotations

import json

from evaluation.commitloop.v5_cohort import (
    STRATA,
    SUBJECTS_PER_STRATUM,
    build_cohort,
    write_cohort,
)


def test_v5_cohort_is_deterministic_balanced_unique_and_scorable(tmp_path) -> None:
    first_rows, first_manifest = build_cohort()
    second_rows, second_manifest = build_cohort()
    assert first_rows == second_rows
    assert first_manifest == second_manifest
    assert len(first_rows) == len(STRATA) * SUBJECTS_PER_STRATUM == 384
    assert len({row["subject_token"] for row in first_rows}) == 384
    assert len({row["bundle_sha256"] for row in first_rows}) == 384
    assert first_manifest["strata"] == {stratum: SUBJECTS_PER_STRATUM for stratum in STRATA}
    assert first_manifest["prior_cohort_overlap_check"] == "PENDING_FREEZE_REGISTRY"

    cohort_path, manifest_path = write_cohort(tmp_path)
    assert len(cohort_path.read_text(encoding="utf-8").splitlines()) == 384
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == first_manifest
