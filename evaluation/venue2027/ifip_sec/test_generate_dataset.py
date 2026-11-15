"""Tests for IFIP_SEC-dataset — synthetic dataset and split builder.

Positive controls:
- generate(seed, split, n) delegates to the shared kernel: same seed yields
  byte-identical JSONL and content hash; different seed/n differ.
- The IFIP-specific payload (purpose, delegation depth, consent epoch,
  replay flag, nonce state) is present, deterministic, and consistent with
  the ground-truth family (fresh_accept is same-purpose and not replayed;
  cross_purpose_replay presents a purpose other than the granted one and
  carries a consumed nonce; delegation_replay is consumed-by-delegate with
  depth >= 1; lineage_splice has a consent epoch differing from its parent).
- The full buffer's content hash is split-independent (kernel property
  preserved through the extension layer).
- write_dataset writes records.jsonl / inventory.json / manifest.json,
  records pass counts, and determinism holds across two directories.
- validate_dataset accepts a balanced dataset and refuses degenerate ones.

Adversarial controls (fail closed with stable reason codes):
- unknown split, unknown family smuggling, non-positive n, and unknown venue
  via the kernel are refused;
- a payload-layer PHI-like field is refused (PHI_FIELD_PRESENT);
- write_dataset must not write anything when validation fails (crash-clean
  output directory);
- dataset_kernel's own leakage and frequency detectors still fire on the
  IFIP venue families;
- every generated payload is free of PHI-marked field names and
  ``synthetic_only`` stays asserted in the manifest.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from evaluation.venue2027._shared import dataset_kernel as dk
from evaluation.venue2027.ifip_sec import generate_dataset as gd

FAMILIES = dk.VENUE_FAMILIES["ifip_sec"]


def test_same_seed_byte_identical() -> None:
    a = gd.generate(seed=2027, split="all", n=40)
    b = gd.generate(seed=2027, split="all", n=40)
    assert a.content_sha256 == b.content_sha256
    assert a.to_jsonl() == b.to_jsonl()


def test_different_seed_differs() -> None:
    a = gd.generate(seed=1, n=40)
    b = gd.generate(seed=2, n=40)
    assert a.content_sha256 != b.content_sha256


def test_hash_is_split_independent() -> None:
    full = gd.generate(seed=11, split="all", n=48)
    assert full.content_sha256 == dk.generate("ifip_sec", seed=11, n=48).content_sha256
    for split in dk.SPLITS:
        assert gd.generate(seed=11, split=split, n=48).content_sha256 == full.content_sha256


def test_split_counts_cover_inventory() -> None:
    ds = gd.generate(seed=5, split="all", n=48)
    assert ds.inventory["total"] == 48
    assert sum(ds.inventory["by_split"].values()) == 48
    parts = [len(gd.generate(seed=5, split=s, n=48).records) for s in dk.SPLITS]
    assert parts == [ds.inventory["by_split"][s] for s in dk.SPLITS]


def test_unit_ids_use_venue_prefix_and_unique() -> None:
    ds = gd.generate(seed=7, split="all", n=32)
    ids = [r.unit_id for r in ds.records]
    assert len(set(ids)) == len(ids)
    assert all(i.startswith("req-") for i in ids)


def test_ifip_payload_fields_present_and_deterministic() -> None:
    ds = gd.generate(seed=9, split="all", n=40)
    expected = {"purpose", "granted_purpose", "delegation_depth", "consent_epoch",
                "parent_consent_epoch", "replay_flag", "nonce_state"}
    for record in ds.records:
        assert expected <= set(record.payload)
        again = gd.generate(seed=9, split="all", n=40)
        by_id = {r.unit_id: r.payload for r in again.records}
        assert record.payload == by_id[record.unit_id]


def test_payload_encodes_family_ground_truth() -> None:
    ds = gd.generate(seed=3, split="all", n=200)
    for record in ds.records:
        p = record.payload
        family = record.family
        if family == "fresh_accept":
            assert p["purpose"] == p["granted_purpose"]
            assert p["replay_flag"] is False
            assert p["nonce_state"] == "fresh"
        elif family == "cross_purpose_replay":
            assert p["purpose"] != p["granted_purpose"]
            assert p["replay_flag"] is True
            assert p["nonce_state"] == "consumed"
        elif family == "delegation_replay":
            assert p["delegation_depth"] >= 1
            assert p["nonce_state"] == "consumed_by_delegate"
            assert p["replay_flag"] is True
        elif family == "lineage_splice":
            assert p["consent_epoch"] != p["parent_consent_epoch"]
        else:  # pragma: no cover - defensive
            pytest.fail(f"unexpected family {family}")


def test_all_families_represented_and_balanced() -> None:
    ds = gd.generate(seed=21, split="all", n=120)
    dk.assert_valid_frequencies(ds)
    assert set(ds.inventory["by_family"]) == set(FAMILIES)
    assert all(c > 0 for c in ds.inventory["by_family"].values())


def test_validate_dataset_passes_on_healthy_dataset() -> None:
    gd.validate_dataset(gd.generate(seed=13, split="all", n=120))


def test_write_dataset_writes_and_is_deterministic(tmp_path: pathlib.Path) -> None:
    out_a, out_b = tmp_path / "a", tmp_path / "b"
    manifest_a = gd.write_dataset(out_a, seed=42, n=120)
    manifest_b = gd.write_dataset(out_b, seed=42, n=120)
    assert manifest_a == manifest_b
    assert json.loads((out_a / "manifest.json").read_text()) == manifest_a
    assert (out_a / "records.jsonl").read_bytes() == (out_b / "records.jsonl").read_bytes()
    lines = (out_a / "records.jsonl").read_text().splitlines()
    assert len(lines) == manifest_a["records"] == 120
    inventory = json.loads((out_a / "inventory.json").read_text())
    assert inventory == manifest_a["inventory"]
    assert manifest_a["synthetic_only"] is True
    assert manifest_a["phi_fields"] == []
    for line in lines:
        payload = json.loads(line)["payload"]
        assert payload["synthetic"] is True


def test_adversarial_unknown_split_refused() -> None:
    with pytest.raises(dk.DatasetError) as exc:
        gd.generate(seed=1, split="holdout", n=10)
    assert exc.value.reason_code == "UNKNOWN_SPLIT"


def test_adversarial_non_positive_n_refused() -> None:
    with pytest.raises(dk.DatasetError) as exc:
        gd.generate(seed=1, split="all", n=0)
    assert exc.value.reason_code == "INVALID_N"


def test_adversarial_unknown_family_refused() -> None:
    with pytest.raises(dk.DatasetError) as exc:
        gd._ifip_extension("stale_readset", seed=1, idx=0)
    assert exc.value.reason_code == "UNKNOWN_FAMILY"


def test_adversarial_phi_like_payload_field_refused() -> None:
    with pytest.raises(dk.DatasetError) as exc:
        gd._assert_no_phi({"patient_email": "x"})
    assert exc.value.reason_code == "PHI_FIELD_PRESENT"


def test_adversarial_kernel_frequency_detector_fires_for_ifip() -> None:
    # 2 units across 4 ifip families: present families share 0.5, far outside
    # the 0.35 tolerance around 0.25 -> fail closed.
    ds = gd.generate(seed=4, split="all", n=2)
    with pytest.raises(dk.DatasetError) as exc:
        dk.assert_valid_frequencies(ds)
    assert exc.value.reason_code == "INVALID_FAMILY_FREQUENCY"


def test_adversarial_kernel_leakage_detector_fires() -> None:
    a = gd.generate(seed=6, split="train", n=10)
    b = gd.generate(seed=6, split="train", n=10)
    with pytest.raises(dk.DatasetError) as exc:
        dk.assert_no_leakage({"train": a, "test": b})
    assert exc.value.reason_code == "SPLIT_LEAKAGE"


def test_adversarial_no_split_leakage_between_named_splits() -> None:
    datasets = {s: gd.generate(seed=8, split=s, n=60) for s in dk.SPLITS}
    dk.assert_no_leakage(datasets)
    ids = [set(r.unit_id for r in datasets[s].records) for s in dk.SPLITS]
    assert not (ids[0] & ids[1]) and not (ids[1] & ids[2]) and not (ids[0] & ids[2])


def test_adversarial_no_phi_fields_in_any_record() -> None:
    ds = gd.generate(seed=17, split="all", n=120)
    for record in ds.records:
        gd._assert_no_phi(record.payload)
        for key in record.payload:
            assert not any(m in key.lower() for m in dk.PHI_FIELD_MARKERS)


def test_adversarial_write_dataset_fails_clean_before_writing(tmp_path: pathlib.Path) -> None:
    outdir = tmp_path / "never_written"
    with pytest.raises(dk.DatasetError):
        gd.write_dataset(outdir, seed=4, n=2)  # degenerate frequencies -> fail closed
    assert not outdir.exists()


def test_kernel_venue_still_validated_venue_is_ifip_sec() -> None:
    ds = gd.generate(seed=2, n=12)
    assert ds.venue == "ifip_sec"
    assert ds.generator_version == dk.DATASET_KERNEL_VERSION
