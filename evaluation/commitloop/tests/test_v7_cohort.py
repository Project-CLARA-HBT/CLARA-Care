from collections import Counter
from pathlib import Path

import pytest

from evaluation.commitloop.candidate_mining import mine_candidates
from evaluation.commitloop.fhir_ingest import ingest_bundle
from evaluation.commitloop.oracle import compile_construction_gold
from evaluation.commitloop.v6_cohort import MASTER_SEED as V6_MASTER_SEED
from evaluation.commitloop.v7_cohort import (
    KNOWN_CUTOFF,
    MASTER_SEED,
    SPLIT_COUNTS,
    STRATA,
    VALID_CUTOFF,
    build_cohort,
    bundles_for_split,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
KNOWN_REGISTRY_PATHS = (
    _REPO_ROOT / "evaluation/commitloop/prior_cohort_exclusion_registry.json",
    _REPO_ROOT / "artifacts/prior_cohort_exclusion_registry.json",
)


def test_v7_cohort_has_768_subjects_with_exact_split_counts() -> None:
    rows, manifest = build_cohort()
    assert len(rows) == 768
    assert manifest["subject_count"] == 768
    assert manifest["split_counts"] == {
        "development": 192,
        "validation": 192,
        "sealed_test": 384,
    }
    assert manifest["split_counts"] == {
        split: len(STRATA) * count for split, count in SPLIT_COUNTS.items()
    }


def test_v7_subject_tokens_and_bundle_hashes_are_unique() -> None:
    rows, _ = build_cohort()
    assert len({row["subject_token"] for row in rows}) == len(rows)
    assert len({row["bundle_sha256"] for row in rows}) == len(rows)


def test_v7_every_subject_has_exactly_one_eligible_scorable_case() -> None:
    rows, _ = build_cohort()
    for row in rows:
        token, events = ingest_bundle(
            row["bundle"], fhir_version=row["fhir_version"], ingested_at=KNOWN_CUTOFF
        )
        assert token == row["subject_token"]
        cases = mine_candidates(token, events)
        assert len(cases) == 1
        assert cases[0].status == "ELIGIBLE"
        gold = compile_construction_gold(
            cases[0], events, valid_cutoff=VALID_CUTOFF, known_cutoff=KNOWN_CUTOFF
        )
        assert gold["status"] == "SCORABLE"


def test_v7_strata_are_balanced_96_subjects_each() -> None:
    rows, _ = build_cohort()
    counts = Counter(row["stratum"] for row in rows)
    assert dict(counts) == {stratum: 96 for stratum in STRATA}
    for stratum in STRATA:
        assert {row["split"] for row in rows if row["stratum"] == stratum} == set(
            SPLIT_COUNTS
        )


def test_v7_split_selection_is_exact_and_does_not_reassign_subjects() -> None:
    rows, _ = build_cohort()
    bundles, assignments = bundles_for_split(rows, split="development")
    assert len(bundles) == len(STRATA) * SPLIT_COUNTS["development"]
    assert set(assignments.values()) == {"development"}
    bundles, assignments = bundles_for_split(rows, split="sealed_test")
    assert len(bundles) == len(STRATA) * SPLIT_COUNTS["sealed_test"]
    assert set(assignments.values()) == {"sealed_test"}


def test_v7_master_seed_distinct_from_v6_and_source_disjoint() -> None:
    assert MASTER_SEED != V6_MASTER_SEED
    v7_rows, _ = build_cohort()
    v6_rows, _ = _build_v6_cohort()
    assert not {row["subject_token"] for row in v7_rows} & {
        row["subject_token"] for row in v6_rows
    }
    assert not {row["bundle_sha256"] for row in v7_rows} & {
        row["bundle_sha256"] for row in v6_rows
    }


def test_v7_no_overlap_with_prior_cohort_registry_when_present() -> None:
    existing = [path for path in KNOWN_REGISTRY_PATHS if path.is_file()]
    if not existing:
        pytest.skip("no prior_cohort_exclusion_registry.json exists; freeze requires one")
    registry = __import__("json").loads(existing[0].read_text(encoding="utf-8"))
    rows, _ = build_cohort()
    overlap = set(registry["subject_tokens"]) & {row["subject_token"] for row in rows}
    assert not overlap


def _build_v6_cohort():
    from evaluation.commitloop.v6_cohort import build_cohort as v6_build

    return v6_build()
