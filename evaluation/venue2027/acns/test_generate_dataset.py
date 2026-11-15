"""Tests for ACNS-dataset — synthetic dataset and split builder.

Positive controls: delegation to the shared kernel yields deterministic,
split-independent content hashes; every kernel family is represented with the
correct ACNS payload binding (claimed attestation level, receipt binding,
pre-registered gap code, source type); write_dataset produces the
JSONL/CSV/inventory/manifest bundle and is reproducible.

Adversarial controls: unknown split fails closed; overwrite of an existing
manifest is refused; split leakage and degenerate family frequencies are
detected via the kernel's fail-closed detectors; every dataset record stays
PHI-free; tampering with any written file is caught by the manifest hashes.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from evaluation.venue2027._shared import dataset_kernel as dk
from evaluation.venue2027.acns import generate_dataset as gd

# Families under test: the four kernel ACNS families must all be present.
_ALL_FAMILIES = set(dk.VENUE_FAMILIES["acns"])


def test_same_seed_identical_content_hash() -> None:
    a = gd.generate(seed=2027, split="all", n=40)
    b = gd.generate(seed=2027, split="all", n=40)
    assert a.content_sha256 == b.content_sha256
    assert a.to_jsonl() == b.to_jsonl()


def test_different_seed_differs() -> None:
    a = gd.generate(seed=1, split="all", n=40)
    b = gd.generate(seed=2, split="all", n=40)
    assert a.content_sha256 != b.content_sha256


def test_split_filter_is_hash_independent() -> None:
    full = gd.generate(seed=7, split="all", n=30)
    parts = {s: gd.generate(seed=7, split=s, n=30) for s in dk.SPLITS}
    # The kernel hashes the full buffered spec, so the hash must not depend on
    # which split filter was requested.
    assert full.content_sha256 == gd.generate(seed=7, split="test", n=30).content_sha256
    unit_sets = [set(r.unit_id for r in parts[s].records) for s in dk.SPLITS]
    assert not (unit_sets[0] & unit_sets[1])
    assert not (unit_sets[1] & unit_sets[2])
    assert sum(len(p.records) for p in parts.values()) == len(full.records)


def test_all_families_represented_with_expected_payload() -> None:
    ds = gd.generate(seed=11, split="all", n=40)
    seen_families = {r.family for r in ds.records}
    assert seen_families == _ALL_FAMILIES
    for record in ds.records:
        payload = record.payload
        assert payload["dataset"] == gd.DATASET_LABEL
        assert payload["synthetic"] is True
        assert payload["claimed_attestation_level"] in gd.ACNS_LATTICE_LEVELS
        gap = payload["evidence_gap_code"]
        assert gap == "NONE" or gap in gd.ACNS_GAP_CODES
        assert payload["source_type"] in {
            "provider_receipt",
            "transport_ack",
            "attested_execution",
            "timestamp_only",
            "undisclosed",
        }
        if record.family == "bound_evidence":
            assert payload["receipt_binding_present"] is True
            assert payload["evidence_gap_code"] == "NONE"
            assert payload["claimed_attestation_level"] == "L1-ASSEMBLED"
        if record.family == "attestation_downgrade":
            assert payload["evidence_gap_code"] == "G2_RECEIPT_AS_EXECUTION"
        if record.family == "unbound_claim":
            assert payload["receipt_binding_present"] is False
            assert payload["evidence_gap_code"] == "G9_CLAIM_WITHOUT_DISCLOSED_EVIDENCE"
        if record.family == "replayed_receipt":
            assert payload["receipt_binding_present"] is False
            assert payload["evidence_gap_code"] == "G4_SIGNATURE_AS_CONTEXT"


def test_inventory_counts_and_hashes() -> None:
    ds = gd.generate(seed=13, split="all", n=40)
    assert ds.inventory["total"] == 40
    assert sum(ds.inventory["by_split"].values()) == 40
    assert ds.inventory["dataset_label"] == gd.DATASET_LABEL
    assert ds.inventory["generator_version"] == gd.ACNS_DATASET_VERSION
    assert len(ds.inventory["by_claimed_attestation_level"]) >= 2
    assert set(ds.inventory["by_source_type"]) <= {
        "provider_receipt",
        "transport_ack",
        "attested_execution",
        "timestamp_only",
        "undisclosed",
    }


def test_no_phi_in_payload_keys() -> None:
    ds = gd.generate(seed=3, split="all", n=24)
    for record in ds.records:
        for key in record.payload:
            lowered = key.lower()
            for marker in dk.PHI_FIELD_MARKERS:
                assert marker not in lowered


def test_payloads_match_fixture_register_semantics() -> None:
    """Every generated record must align with the pinned fixture register.

    The smoke fixtures pin the four family ground truths; the generator must
    produce the same gap codes so oracle and baselines agree on labels.
    """

    fixture_gaps = {
        "bound": "NONE",
        "downgraded": "G2_RECEIPT_AS_EXECUTION",
        "unbound": "G9_CLAIM_WITHOUT_DISCLOSED_EVIDENCE",
        "replayed": "G4_SIGNATURE_AS_CONTEXT",
    }
    family_to_variant = {
        "bound_evidence": "bound",
        "attestation_downgrade": "downgraded",
        "unbound_claim": "unbound",
        "replayed_receipt": "replayed",
    }
    expected = {family: fixture_gaps[variant] for family, variant in family_to_variant.items()}
    ds = gd.generate(seed=17, split="all", n=40)
    for record in ds.records:
        assert record.payload["evidence_gap_code"] == expected[record.family]


def test_unknown_split_fails_closed() -> None:
    with pytest.raises(dk.DatasetError) as exc:
        gd.generate(seed=1, split="holdout", n=10)
    assert exc.value.reason_code == "UNKNOWN_SPLIT"


def test_invalid_n_fails_closed() -> None:
    with pytest.raises(dk.DatasetError) as exc:
        gd.generate(seed=1, split="all", n=0)
    assert exc.value.reason_code == "INVALID_N"


def test_leakage_detected_between_same_unit_splits() -> None:
    a = gd.generate(seed=5, split="train", n=10)
    b = gd.generate(seed=5, split="train", n=10)
    with pytest.raises(dk.DatasetError) as exc:
        dk.assert_no_leakage({"train": a, "test": b})
    assert exc.value.reason_code == "SPLIT_LEAKAGE"


def test_degenerate_family_frequency_fails_closed() -> None:
    # n=2 across 4 families -> present families have share 0.5, outside the
    # kernel's 0.35 tolerance around 0.25: must refuse.
    ds = gd.generate(seed=8, split="all", n=2)
    with pytest.raises(dk.DatasetError) as exc:
        dk.assert_valid_frequencies(ds)
    assert exc.value.reason_code == "INVALID_FAMILY_FREQUENCY"


def test_valid_frequency_passes_for_balanced_dataset() -> None:
    ds = gd.generate(seed=9, split="all", n=40)
    dk.assert_valid_frequencies(ds)


def test_write_dataset_bundle_and_reproducibility(tmp_path: pathlib.Path) -> None:
    out_a = tmp_path / "run_a"
    out_b = tmp_path / "run_b"
    manifest_a = gd.write_dataset(out_a, seed=42, n=40)
    manifest_b = gd.write_dataset(out_b, seed=42, n=40)
    assert manifest_a["content_sha256"] == manifest_b["content_sha256"]
    assert manifest_a["files"] == manifest_b["files"]
    for name in ("records.jsonl", "records.csv", "inventory.json", "manifest.json"):
        assert (out_a / name).is_file()
        assert (out_b / name).read_bytes() == (out_a / name).read_bytes()
    lines = (out_a / "records.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 40
    first = json.loads(lines[0])
    assert first["unit_id"].startswith("evd-")
    assert first["payload"]["dataset"] == gd.DATASET_LABEL
    inventory = json.loads((out_a / "inventory.json").read_text(encoding="utf-8"))
    assert inventory["content_sha256"] == manifest_a["content_sha256"]
    assert inventory["total"] == 40


def test_write_dataset_refuses_overwrite(tmp_path: pathlib.Path) -> None:
    out = tmp_path / "run"
    gd.write_dataset(out, seed=42, n=20)
    with pytest.raises(dk.DatasetError) as exc:
        gd.write_dataset(out, seed=42, n=20)
    assert exc.value.reason_code == "OVERWRITE_REFUSED"
    manifest = gd.write_dataset(out, seed=42, n=20, overwrite=True)
    assert manifest["n"] == 20


def test_manifest_hashes_detect_tampering(tmp_path: pathlib.Path) -> None:
    out = tmp_path / "run"
    manifest = gd.write_dataset(out, seed=42, n=20)
    records_path = out / "records.jsonl"
    original = records_path.read_bytes()
    records_path.write_bytes(original + b'{"tampered": true}\n')
    import hashlib

    actual = hashlib.sha256(records_path.read_bytes()).hexdigest()
    assert actual != manifest["files"]["records.jsonl"]
    records_path.write_bytes(original)  # restore for any later inspection
