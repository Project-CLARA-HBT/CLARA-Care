"""Controls for subject denominators, projection equality and invalid source rows."""

import pytest

from evaluation.external_validation.uci_projection_identity import MEDICATION_FIELDS, paired_counts


def row(subject, encounter, status="Steady"):
    return {
        **dict.fromkeys(MEDICATION_FIELDS, "No"),
        "patient_nbr": subject,
        "encounter_id": encounter,
        "insulin": status,
    }


def test_disjoint_pair_categories_and_singleton():
    rows = [
        row("s", "1"),
        row("a", "2"),
        row("b", "3"),
        row("c", "4"),
        row("a", "5"),
        row("a", "6", "Up"),
        row("b", "7", "Down"),
        row("c", "8", "?"),
    ]
    assert paired_counts(rows) == {
        "encounters": 8,
        "subjects": 4,
        "paired_subjects": 3,
        "singletons": 1,
        "encounters_after_second": 1,
        "equal_full_projection": 1,
        "equal_only_on_presence": 1,
        "different_on_presence": 1,
        "digest_vs_direct_equality_disagreements": 0,
    }


@pytest.mark.parametrize("bad", [row("b", "1"), row("?", "2"), row("a", "2", "invalid")])
def test_bad_source_invalidates_run(bad):
    with pytest.raises(ValueError):
        paired_counts([row("a", "1"), bad])
