from evaluation.commitloop.run_local import expected_solver_case_count
from evaluation.commitloop.v6_cohort import (
    KNOWN_CUTOFF,
    SPLIT_COUNTS,
    STRATA,
    VALID_CUTOFF,
    build_cohort,
    bundles_for_split,
)


def test_v6_cohort_is_subject_disjoint_and_has_heldout_templates() -> None:
    rows, manifest = build_cohort()
    assert len(rows) == len(STRATA) * sum(SPLIT_COUNTS.values())
    assert manifest["split_counts"] == {
        split: len(STRATA) * count for split, count in SPLIT_COUNTS.items()
    }
    assert len({row["subject_token"] for row in rows}) == len(rows)
    assert len({row["bundle_sha256"] for row in rows}) == len(rows)
    for stratum in STRATA:
        assert {row["split"] for row in rows if row["stratum"] == stratum} == set(
            SPLIT_COUNTS
        )


def test_v6_split_selection_is_exact_and_does_not_reassign_subjects() -> None:
    rows, _ = build_cohort()
    bundles, assignments = bundles_for_split(rows, split="development")
    assert len(bundles) == len(STRATA) * SPLIT_COUNTS["development"]
    assert set(assignments.values()) == {"development"}


def test_v6_development_inventory_includes_every_adversarial_variant() -> None:
    rows, _ = build_cohort()
    bundles, _assignments = bundles_for_split(rows, split="development")
    count = expected_solver_case_count(
        bundles=bundles,
        valid_cutoff=VALID_CUTOFF,
        known_cutoff=KNOWN_CUTOFF,
        max_subjects=len(bundles),
        max_base_cases=len(bundles),
    )
    assert count == 528
    assert count > len(bundles)


def test_new_cohort_spec_has_no_subject_or_bundle_overlap() -> None:
    original, _ = build_cohort()
    replacement, _ = build_cohort(
        master_seed=2026081401,
        cohort_name="glhs_bench_replacement_cohort.v7",
        schema_version="commitloop-v7-cohort.v1",
    )
    assert not {row["subject_token"] for row in original} & {
        row["subject_token"] for row in replacement
    }
    assert not {row["bundle_sha256"] for row in original} & {
        row["bundle_sha256"] for row in replacement
    }
