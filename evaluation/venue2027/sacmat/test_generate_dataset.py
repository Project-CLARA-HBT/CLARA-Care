"""Tests for SACMAT-dataset — synthetic delegated-consent dataset builder.

Positive controls:
- ``generate(seed, split, n)`` delegates to the audited shared kernel: same
  ``(seed, split, n)`` is byte-identical (determinism), different seeds
  differ, unit ids use the kernel ``dlg-`` prefix, families are exactly the
  kernel SACMAT families, and split filtering yields disjoint units with no
  leakage (kernel ``assert_no_leakage``) plus valid family frequencies
  (kernel ``assert_valid_frequencies``).
- SACMAT payload enrichment is deterministic and family-conditioned:
  ``conformant`` carries zero policy-version skew and a non-lapsed expiry
  offset, ``expiry_divergence`` always carries a strictly negative expiry
  offset, ``policy_skew`` always carries a strictly positive skew; every
  record keeps the kernel ground-truth fields and no PHI-named fields.
- ``write_dataset`` persists byte-identical files across runs; a split slice
  of the persisted dataset matches a direct ``generate`` of that split.
- Manifest integrity: recorded digests match the on-disk bytes;
  ``verify_dataset_dir`` re-derives the dataset and accepts.

Adversarial controls:
- Invalid ``n`` and unknown ``split`` fail closed via kernel reason codes.
- Tampered ``dataset.jsonl`` or ``manifest.json`` (swapped bytes between two
  seeds) is rejected by ``verify_dataset_dir`` with
  ``MANIFEST_HASH_MISMATCH`` — never silently accepted.
- Enrichment never leaks across families: skew/expiry invariants hold for
  every record of a large dataset, and the conformant family never contains
  a lapsed or skewed unit.

Failure semantics: every adversarial case raises ``DatasetError`` with a
stable reason code; none is swallowed or miscounted as a safe rejection.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evaluation.venue2027._shared import dataset_kernel as dk
from evaluation.venue2027.sacmat import generate_dataset as gd


def test_deterministic_same_inputs_identical() -> None:
    a = gd.generate(2027, None, 60)
    b = gd.generate(2027, None, 60)
    assert a.content_sha256 == b.content_sha256
    assert a.to_jsonl() == b.to_jsonl()


def test_different_seeds_differ() -> None:
    assert gd.generate(1, None, 40).content_sha256 != gd.generate(2, None, 40).content_sha256


def test_delegates_to_kernel_families_and_prefix() -> None:
    ds = gd.generate(2027, None, 40)
    assert ds.venue == "sacmat"
    assert ds.generator_version == dk.DATASET_KERNEL_VERSION
    assert set(r.family for r in ds.records) == set(dk.VENUE_FAMILIES["sacmat"])
    for record in ds.records:
        assert record.unit_id.startswith(dk.VENUE_UNIT_PREFIX["sacmat"] + "-")


def test_split_slices_are_disjoint_and_hash_stable() -> None:
    full = gd.generate(2027, None, 60)
    slices = {s: gd.generate(2027, s, 60) for s in dk.SPLITS}
    dk.assert_no_leakage(slices)
    units = [set(r.unit_id for r in slices[s].records) for s in dk.SPLITS]
    assert not (units[0] & units[1])
    assert not (units[1] & units[2])
    for s in dk.SPLITS:
        assert slices[s].content_sha256 == full.content_sha256
        assert {r.unit_id for r in slices[s].records} == {
            r.unit_id for r in full.split(s)
        }


def test_family_frequencies_valid() -> None:
    dk.assert_valid_frequencies(gd.generate(2027, None, 80))


def test_payload_enrichment_is_family_conditioned() -> None:
    ds = gd.generate(2027, None, 200)
    seen: set[str] = set()
    for record in ds.records:
        seen.add(record.family)
        payload = record.payload
        # Kernel ground-truth fields survive enrichment.
        assert payload["family"] == record.family
        assert payload["synthetic"] is True
        assert payload["determinant"] == (
            2027 * 7919 + record.payload["sequence"] * 104729
        ) % 100003
        assert 0 <= payload["delegation_depth"] <= gd.DELEGATION_DEPTH_MAX
        assert 0 <= payload["policy_version_skew"] <= gd.POLICY_VERSION_SKEW_MAX
        if record.family == "conformant":
            assert payload["policy_version_skew"] == 0
            assert payload["expiry_offset_ticks"] >= 0
        elif record.family == "expiry_divergence":
            assert payload["expiry_offset_ticks"] < 0
        elif record.family == "policy_skew":
            assert payload["policy_version_skew"] > 0
    assert seen == set(dk.VENUE_FAMILIES["sacmat"])


def test_enrichment_independent_of_requested_split() -> None:
    full = gd.generate(2027, None, 40)
    by_unit = {r.unit_id: r.payload for r in full.records}
    for s in dk.SPLITS:
        for record in gd.generate(2027, s, 40).records:
            assert record.payload == by_unit[record.unit_id]


def test_no_phi_fields() -> None:
    for record in gd.generate(2027, None, 50).records:
        for key in record.payload:
            assert not any(marker in key.lower() for marker in dk.PHI_FIELD_MARKERS)


def test_write_dataset_deterministic_and_verifiable(tmp_path: Path) -> None:
    out_a, out_b = tmp_path / "a", tmp_path / "b"
    manifest_a = gd.write_dataset(out_a, seed=2027, n=120)
    manifest_b = gd.write_dataset(out_b, seed=2027, n=120)
    assert (out_a / gd.DATASET_FILENAME).read_bytes() == (out_b / gd.DATASET_FILENAME).read_bytes()
    assert manifest_a == manifest_b
    assert manifest_a["venue"] == "sacmat"
    assert manifest_a["inventory"]["total"] == 120
    lines = (out_a / gd.DATASET_FILENAME).read_text(encoding="utf-8").splitlines()
    assert len(lines) == 120
    records = [json.loads(line) for line in lines]
    assert [r["unit_id"] for r in records] == sorted(r["unit_id"] for r in records)
    digest = hashlib.sha256((out_a / gd.DATASET_FILENAME).read_bytes()).hexdigest()
    assert manifest_a["dataset_jsonl_sha256"] == digest
    assert gd.verify_dataset_dir(out_a)["dataset_jsonl_sha256"] == digest


def test_write_dataset_split_slice_matches_direct_generate(tmp_path: Path) -> None:
    out = tmp_path / "ds"
    gd.write_dataset(out, seed=2027, n=60)
    records = {
        json.loads(line)["unit_id"]: json.loads(line)
        for line in (out / gd.DATASET_FILENAME).read_text(encoding="utf-8").splitlines()
    }
    for s in dk.SPLITS:
        for record in gd.generate(2027, s, 60).records:
            assert records[record.unit_id] == record.to_dict()


def test_invalid_n_fails_closed() -> None:
    with pytest.raises(dk.DatasetError) as exc:
        gd.generate(2027, None, 0)
    assert exc.value.reason_code == "INVALID_N"


def test_unknown_split_fails_closed() -> None:
    with pytest.raises(dk.DatasetError) as exc:
        gd.generate(2027, "holdout", 10)
    assert exc.value.reason_code == "UNKNOWN_SPLIT"


def test_tampered_dataset_bytes_rejected(tmp_path: Path) -> None:
    out = tmp_path / "tampered"
    gd.write_dataset(out, seed=2027, n=40)
    other = gd.write_dataset(tmp_path / "other", seed=9, n=40)
    # Swap in a foreign dataset.jsonl (same schema, different seed).
    (out / gd.DATASET_FILENAME).write_bytes((tmp_path / "other" / gd.DATASET_FILENAME).read_bytes())
    with pytest.raises(dk.DatasetError) as exc:
        gd.verify_dataset_dir(out)
    assert exc.value.reason_code == "MANIFEST_HASH_MISMATCH"
    assert other["seed"] == 9  # sanity: the foreign manifest really is seed 9


def test_tampered_manifest_digest_rejected(tmp_path: Path) -> None:
    out = tmp_path / "tampered_manifest"
    gd.write_dataset(out, seed=2027, n=40)
    manifest = json.loads((out / gd.MANIFEST_FILENAME).read_text(encoding="utf-8"))
    manifest["dataset_jsonl_sha256"] = "0" * 64
    (out / gd.MANIFEST_FILENAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with pytest.raises(dk.DatasetError) as exc:
        gd.verify_dataset_dir(out)
    assert exc.value.reason_code == "MANIFEST_HASH_MISMATCH"


def test_main_cli_writes_dataset(tmp_path: Path) -> None:
    out = tmp_path / "cli"
    assert gd.main(["--outdir", str(out), "--seed", "2027", "--n", "24"]) == 0
    assert (out / gd.DATASET_FILENAME).is_file()
    assert gd.verify_dataset_dir(out)["n"] == 24
