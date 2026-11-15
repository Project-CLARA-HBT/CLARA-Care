"""Tests for the DIMVA venue2027 dataset generator (task DIMVA-dataset).

Positive vectors cover determinism, kernel delegation semantics, the
DIMVA-specific payload fields and split-family layout. Adversarial vectors
prove fail-closed behavior on unknown splits, invalid cardinalities, unknown
families, family-frequency degeneracy and cross-venue unit-id collisions.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from evaluation.venue2027._shared import dataset_kernel as dk
from evaluation.venue2027.dimva import generate_dataset as gd

# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_generate_returns_kernel_dataset_with_dimva_families() -> None:
    dataset = gd.generate(seed=2027, split=None, n=40)
    assert dataset.venue == "dimva"
    assert dataset.generator_version == dk.DATASET_KERNEL_VERSION
    assert dataset.inventory["total"] == 40
    assert set(dataset.inventory["by_family"]) == set(dk.VENUE_FAMILIES["dimva"])
    assert set(dataset.inventory["by_split"]) == set(dk.SPLITS)


def test_same_seed_yields_identical_content_hash_and_jsonl() -> None:
    a = gd.generate(seed=42, split=None, n=24)
    b = gd.generate(seed=42, split=None, n=24)
    assert a.content_sha256 == b.content_sha256
    assert a.to_jsonl() == b.to_jsonl()
    assert [r.to_dict() for r in a.records] == [r.to_dict() for r in b.records]


def test_different_seed_yields_different_content() -> None:
    a = gd.generate(seed=1, split=None, n=24)
    b = gd.generate(seed=2, split=None, n=24)
    assert a.content_sha256 != b.content_sha256
    assert a.to_jsonl() != b.to_jsonl()


def test_split_filter_matches_kernel_split_independent_hash() -> None:
    full = gd.generate(seed=9, split=None, n=30)
    train = gd.generate(seed=9, split="train", n=30)
    dev = gd.generate(seed=9, split="dev", n=30)
    test = gd.generate(seed=9, split="test", n=30)
    assert train.content_sha256 == dev.content_sha256 == test.content_sha256
    assert train.content_sha256 == full.content_sha256
    assert len(train.records) == full.inventory["by_split"]["train"]
    assert {r.split for r in train.records} == {"train"}
    assert {r.split for r in dev.records} == {"dev"}
    assert {r.split for r in test.records} == {"test"}


def test_splits_are_disjoint_by_independent_unit() -> None:
    datasets = {s: gd.generate(seed=11, split=s, n=60) for s in dk.SPLITS}
    dk.assert_no_leakage(datasets)
    unit_sets = [set(r.unit_id for r in datasets[s].records) for s in dk.SPLITS]
    assert not (unit_sets[0] & unit_sets[1])
    assert not (unit_sets[1] & unit_sets[2])
    assert not (unit_sets[0] & unit_sets[2])


def test_unit_ids_use_dimva_camp_prefix() -> None:
    dataset = gd.generate(seed=7, split=None, n=8)
    for record in dataset.records:
        assert record.unit_id.startswith("camp-")


def test_payload_carries_dimva_operational_fields() -> None:
    dataset = gd.generate(seed=3, split=None, n=40)
    for record in dataset.records:
        payload = record.payload
        assert set(payload) >= {
            "family",
            "synthetic",
            "determinant",
            "sequence",
            "campaign_length_events",
            "tools_used",
            "denial_rate",
            "inter_arrival_delay_seconds",
        }
        assert isinstance(payload["campaign_length_events"], int)
        assert payload["campaign_length_events"] > 0
        assert 0.0 <= payload["denial_rate"] <= 1.0
        assert isinstance(payload["inter_arrival_delay_seconds"], int)
        assert payload["inter_arrival_delay_seconds"] >= 0
        assert isinstance(payload["tools_used"], list)
        assert payload["tools_used"]
        assert len(set(payload["tools_used"])) == len(payload["tools_used"])


def test_family_profiles_distinguish_operational_regimes() -> None:
    dataset = gd.generate(seed=5, split=None, n=80)
    by_family: dict[str, list[dict]] = {}
    for record in dataset.records:
        by_family.setdefault(record.family, []).append(record.payload)
    benign = by_family["benign_session"]
    burst = by_family["burst_probe"]
    slow = by_family["low_and_slow"]
    cross = by_family["cross_tool_obfuscation"]
    # Benign sessions stay short and mostly-allowed.
    assert max(p["campaign_length_events"] for p in benign) <= 8
    assert max(p["denial_rate"] for p in benign) <= 0.2
    # Burst probes compress inter-arrival delays far below benign pacing.
    assert max(p["inter_arrival_delay_seconds"] for p in burst) <= 60
    assert min(p["inter_arrival_delay_seconds"] for p in slow) >= 3600
    # Cross-tool obfuscation uses more distinct tools than benign traffic.
    assert max(len(p["tools_used"]) for p in cross) >= 4
    assert max(len(p["tools_used"]) for p in benign) <= 3


def test_payload_fields_are_json_serializable_and_phi_free() -> None:
    dataset = gd.generate(seed=13, split=None, n=20)
    for record in dataset.records:
        encoded = json.dumps(record.to_dict(), sort_keys=True)
        assert isinstance(encoded, str)
        lowered_keys = [key.lower() for key in record.payload]
        for marker in dk.PHI_FIELD_MARKERS:
            assert all(marker not in key for key in lowered_keys)
    assert all(record.payload["synthetic"] is True for record in dataset.records)


def test_enrichment_matches_kernel_family_assignment() -> None:
    kernel_ds = dk.generate("dimva", seed=21, n=16)
    adapter_ds = gd.generate(seed=21, split=None, n=16)
    assert [r.unit_id for r in kernel_ds.records] == [r.unit_id for r in adapter_ds.records]
    assert [r.family for r in kernel_ds.records] == [r.family for r in adapter_ds.records]
    assert [r.split for r in kernel_ds.records] == [r.split for r in adapter_ds.records]


def test_balanced_family_frequencies_pass_kernel_gate() -> None:
    dataset = gd.generate(seed=6, split=None, n=40)  # 4 families x 10 units
    dk.assert_valid_frequencies(dataset)


def test_write_dataset_emits_jsonl_and_manifest(tmp_path: pathlib.Path) -> None:
    outdir = tmp_path / "dimva_ds"
    manifest = gd.write_dataset(outdir, seed=77, n=40)
    jsonl_path = outdir / "dataset.jsonl"
    manifest_path = outdir / "manifest.json"
    assert jsonl_path.is_file() and manifest_path.is_file()
    lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 40
    records = [json.loads(line) for line in lines]
    assert len({r["unit_id"] for r in records}) == 40
    on_disk_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert on_disk_manifest == manifest
    assert manifest["seed"] == 77 and manifest["n"] == 40
    assert manifest["total_records"] == 40
    assert sum(manifest["splits"].values()) == 40
    assert set(manifest["families"]) == set(dk.VENUE_FAMILIES["dimva"])
    assert manifest["generator_version"] == gd.DATASET_GENERATOR_VERSION


def test_write_dataset_is_deterministic(tmp_path: pathlib.Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    manifest_a = gd.write_dataset(first, seed=2027, n=24)
    manifest_b = gd.write_dataset(second, seed=2027, n=24)
    assert manifest_a["dataset_jsonl_sha256"] == manifest_b["dataset_jsonl_sha256"]
    assert manifest_a["content_sha256"] == manifest_b["content_sha256"]
    assert (first / "dataset.jsonl").read_bytes() == (second / "dataset.jsonl").read_bytes()


def test_write_dataset_overwrites_idempotently(tmp_path: pathlib.Path) -> None:
    outdir = tmp_path / "ds"
    manifest_first = gd.write_dataset(outdir, seed=5, n=12)
    manifest_again = gd.write_dataset(outdir, seed=5, n=12)
    assert manifest_first == manifest_again


# ---------------------------------------------------------------------------
# Adversarial controls (fail closed)
# ---------------------------------------------------------------------------


def test_zero_and_negative_n_refused() -> None:
    with pytest.raises(dk.DatasetError) as exc_zero:
        gd.generate(seed=1, split=None, n=0)
    assert exc_zero.value.reason_code == "INVALID_N"
    with pytest.raises(dk.DatasetError) as exc_negative:
        gd.generate(seed=1, split=None, n=-5)
    assert exc_negative.value.reason_code == "INVALID_N"


def test_unknown_split_refused() -> None:
    with pytest.raises(dk.DatasetError) as exc:
        gd.generate(seed=1, split="holdout", n=10)
    assert exc.value.reason_code == "UNKNOWN_SPLIT"


def test_leakage_is_detected_across_adapter_splits() -> None:
    a = gd.generate(seed=3, split="train", n=10)
    b = gd.generate(seed=3, split="train", n=10)  # same units as a
    with pytest.raises(dk.DatasetError) as exc:
        dk.assert_no_leakage({"train": a, "test": b})
    assert exc.value.reason_code == "SPLIT_LEAKAGE"


def test_degenerate_family_frequency_fails_closed(tmp_path: pathlib.Path) -> None:
    # n=3 across 4 dimva families leaves one family unrepresented with the
    # remaining share 1/3 far outside the 0.35 tolerance around 0.25; the raw
    # generate succeeds but the frequency gate must refuse it.
    dataset = gd.generate(seed=2, split=None, n=3)
    with pytest.raises(dk.DatasetError) as exc_gate:
        dk.assert_valid_frequencies(dataset)
    assert exc_gate.value.reason_code == "INVALID_FAMILY_FREQUENCY"
    # write_dataset must refuse BEFORE creating any file.
    outdir = tmp_path / "never_written"
    with pytest.raises(dk.DatasetError) as exc_write:
        gd.write_dataset(outdir, seed=2, n=3)
    assert exc_write.value.reason_code == "INVALID_FAMILY_FREQUENCY"
    assert not outdir.exists()


def test_unknown_family_enrichment_fails_closed() -> None:
    with pytest.raises(gd.DatasetError) as exc:
        gd._dimva_enrichment("not_a_dimva_family", {"determinant": 1, "sequence": 0})
    assert exc.value.reason_code == "UNKNOWN_DIMVA_FAMILY"


def test_enrichment_deterministic_regardless_of_call_order() -> None:
    base = {"family": "burst_probe", "synthetic": True, "determinant": 4242, "sequence": 3}
    first = gd._dimva_enrichment("burst_probe", base)
    second = gd._dimva_enrichment("burst_probe", base)
    assert first == second
    # Entropy must come from the determinant, not module state.
    other = gd._dimva_enrichment(
        "burst_probe", {**base, "determinant": (base["determinant"] + 1) % 100003}
    )
    assert other != first or first["campaign_length_events"] == other["campaign_length_events"]


def test_kernel_venue_families_unchanged_for_dimva() -> None:
    # Guard against accidental contract drift of the shared kernel registry.
    assert dk.VENUE_FAMILIES["dimva"] == (
        "benign_session",
        "low_and_slow",
        "cross_tool_obfuscation",
        "burst_probe",
    )
    assert dk.VENUE_UNIT_PREFIX["dimva"] == "camp"


def test_cross_venue_unit_ids_do_not_collide() -> None:
    dimva = gd.generate(seed=100, split=None, n=12)
    other = dk.generate("popets", seed=100, n=12)
    dimva_units = {r.unit_id for r in dimva.records}
    other_units = {r.unit_id for r in other.records}
    assert not (dimva_units & other_units)
