"""Tests for the shared deterministic dataset kernel."""

from __future__ import annotations

import pytest

from evaluation.venue2027._shared import dataset_kernel as dk


def test_same_seed_is_identical() -> None:
    a = dk.generate("compsac", seed=2027, n=40)
    b = dk.generate("compsac", seed=2027, n=40)
    assert a.content_sha256 == b.content_sha256
    assert a.to_jsonl() == b.to_jsonl()


def test_different_seed_differs() -> None:
    a = dk.generate("compsac", seed=1, n=40)
    b = dk.generate("compsac", seed=2, n=40)
    assert a.content_sha256 != b.content_sha256


def test_inventory_covers_all_records() -> None:
    ds = dk.generate("dsn", seed=5, n=30)
    assert ds.inventory["total"] == 30
    assert sum(ds.inventory["by_split"].values()) == 30
    assert set(ds.inventory["by_split"]) == set(dk.SPLITS)


def test_splits_are_disjoint_by_unit() -> None:
    datasets = {s: dk.generate("dimva", seed=9, n=50, split=s) for s in dk.SPLITS}
    dk.assert_no_leakage(datasets)
    unit_sets = [set(r.unit_id for r in datasets[s].records) for s in dk.SPLITS]
    assert not (unit_sets[0] & unit_sets[1])
    assert not (unit_sets[1] & unit_sets[2])


def test_leakage_detected() -> None:
    a = dk.generate("pst", seed=3, n=10, split="train")
    b = dk.generate("pst", seed=3, n=10, split="train")  # same units as a
    with pytest.raises(dk.DatasetError) as exc:
        dk.assert_no_leakage({"train": a, "test": b})
    assert exc.value.reason_code == "SPLIT_LEAKAGE"


def test_invalid_frequency_detected() -> None:
    # 2 units across 5 aime families: each present family has share 0.5,
    # far outside the 0.35 tolerance around 0.2 -> must fail closed.
    ds = dk.generate("aime", seed=4, n=2)
    with pytest.raises(dk.DatasetError) as exc:
        dk.assert_valid_frequencies(ds)
    assert exc.value.reason_code == "INVALID_FAMILY_FREQUENCY"


def test_balanced_frequency_passes() -> None:
    ds = dk.generate("sacmat", seed=6, n=40)  # 4 families, 40 units -> 10 each
    dk.assert_valid_frequencies(ds)


def test_unknown_venue_refused() -> None:
    with pytest.raises(dk.DatasetError) as exc:
        dk.generate("nope", seed=1, n=5)
    assert exc.value.reason_code == "UNKNOWN_VENUE"


def test_invalid_ratios_refused() -> None:
    spec = dk.DatasetSpec(venue="compsac", seed=1, n=10, train_ratio=0.9, dev_ratio=0.9, test_ratio=0.9)
    with pytest.raises(dk.DatasetError) as exc:
        spec.validate()
    assert exc.value.reason_code == "INVALID_SPLIT_RATIOS"


def test_no_phi_fields() -> None:
    ds = dk.generate("acns", seed=8, n=16)
    for record in ds.records:
        for key in record.payload:
            assert "email" not in key.lower()
            assert "name" not in key.lower()


def test_unknown_split_refused() -> None:
    with pytest.raises(dk.DatasetError) as exc:
        dk.generate("compsac", seed=1, n=10, split="holdout")
    assert exc.value.reason_code == "UNKNOWN_SPLIT"
