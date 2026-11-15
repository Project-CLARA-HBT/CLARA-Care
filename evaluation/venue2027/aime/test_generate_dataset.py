"""Tests for AIME-dataset — deterministic dataset and split builder.

Positive controls: same seed yields identical content hash and byte-identical
JSONL; split filtering works and never changes the buffered inventory; the
inventory totals equal ``n``; family frequencies are balanced (no leakage, no
degenerate distribution) under the kernel validators; every record carries the
AIME longitudinal workflow payload (medication state, allergy state, consent
revision, update family) deterministically. Adversarial controls: split
leakage is detected by the kernel, degenerate frequencies are refused, unknown
splits/families fail closed with stable reason codes, and no PHI-like field
name ever appears in payloads or written artifacts. The test module imports
only the generator under test and the kernel it delegates to (no candidate
runtime, no DB, no model, no clock/randomness).
"""

from __future__ import annotations

import json

import pytest

from evaluation.venue2027._shared import dataset_kernel as dk
from evaluation.venue2027.aime.generate_dataset import (
    AIME_FAMILIES,
    DEFAULT_N,
    GENERATE_DATASET_VERSION,
    WORKFLOW_PAYLOAD_VERSION,
    generate,
    validate_dataset,
    workflow_payload,
    write_dataset,
)

# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_same_seed_identical_content_hash_and_bytes(tmp_path):
    """Same (seed, n) => identical content hash and byte-identical JSONL."""

    a = generate(seed=42, n=50)
    b = generate(seed=42, n=50)
    assert a.content_sha256 == b.content_sha256
    assert a.to_jsonl() == b.to_jsonl()
    assert a.inventory["by_family"] == b.inventory["by_family"]
    assert a.inventory["by_split"] == b.inventory["by_split"]

    dirs = [tmp_path / "run_a", tmp_path / "run_b"]
    manifests = [write_dataset(d, seed=42, n=50) for d in dirs]
    assert manifests[0]["jsonl_sha256"] == manifests[1]["jsonl_sha256"]
    assert (dirs[0] / "dataset.jsonl").read_bytes() == (dirs[1] / "dataset.jsonl").read_bytes()

    # A different seed must produce a different dataset.
    assert generate(seed=43, n=50).content_sha256 != a.content_sha256


def test_split_filter_returns_only_requested_split():
    """Split filtering returns exactly the records of that split."""

    full = generate(seed=7, n=60)
    assert {r.split for r in full.records} == {"train", "dev", "test"}
    for name in ("train", "dev", "test"):
        subset = generate(seed=7, n=60, split=name)
        assert all(r.split == name for r in subset.records)
        assert len(subset.records) == full.inventory["by_split"][name]
        assert subset.records == full.split(name)
        # Buffered inventory (and hash) is split-independent.
        assert subset.content_sha256 == full.content_sha256
        assert subset.inventory["total"] == 60


def test_inventory_totals_equal_n(tmp_path):
    """Inventory cardinality equals n; written artifacts agree with inventory."""

    n = 80
    ds = generate(seed=99, n=n)
    assert len(ds.records) == n
    assert ds.inventory["total"] == n
    assert sum(ds.inventory["by_split"].values()) == n
    assert sum(ds.inventory["by_family"].values()) == n
    assert ds.inventory["venue"] == "aime"
    assert ds.inventory["generator_version"] == dk.DATASET_KERNEL_VERSION
    assert ds.inventory["generate_dataset_version"] == GENERATE_DATASET_VERSION

    manifest = write_dataset(tmp_path, seed=99, n=n)
    written = [json.loads(line) for line in (tmp_path / "dataset.jsonl").read_text().splitlines()]
    assert manifest["records"] == n
    assert len(written) == n
    inventory = json.loads((tmp_path / "inventory.json").read_text())
    assert inventory["total"] == n
    assert inventory["by_family"] == ds.inventory["by_family"]
    assert inventory["by_split"] == ds.inventory["by_split"]


def test_no_split_leakage_across_splits():
    """The three split views are disjoint by independent unit (kernel check)."""

    datasets = {name: generate(seed=5, n=64, split=name) for name in ("train", "dev", "test")}
    dk.assert_no_leakage(datasets)


def test_balanced_family_frequencies():
    """Every AIME family is represented within the kernel balance tolerance."""

    ds = generate(seed=11, n=120)
    dk.assert_valid_frequencies(ds)
    counts = ds.inventory["by_family"]
    assert set(counts) == set(AIME_FAMILIES)
    for count in counts.values():
        assert count > 0
        assert abs(count / sum(counts.values()) - 1.0 / len(counts)) <= 0.35


def test_unit_ids_use_kernel_aime_prefix():
    """Unit ids are kernel-managed, prefixed per venue, and unique."""

    ds = generate(seed=19, n=30)
    unit_ids = [r.unit_id for r in ds.records]
    assert len(set(unit_ids)) == len(unit_ids)
    assert all(uid.startswith(f"{dk.VENUE_UNIT_PREFIX['aime']}-") for uid in unit_ids)


def test_workflow_payload_present_deterministic_and_family_shaped():
    """Every record carries the AIME workflow payload, deterministically."""

    ds = generate(seed=21, n=50)
    consent_revisions: set[int] = set()
    for record in ds.records:
        payload = record.payload
        for key in (
            "workflow_payload_version",
            "update_family",
            "event_kind",
            "active_medications",
            "allergies",
            "consent_revision",
            "granted_purposes",
            "synthetic_only",
        ):
            assert key in payload
        assert payload["workflow_payload_version"] == WORKFLOW_PAYLOAD_VERSION
        assert payload["update_family"] == record.family
        assert payload["synthetic_only"] is True

        if record.family == "stable_history":
            assert payload["active_medications"]
            assert payload["allergies"] == []
            assert payload["consent_revision"] == 0
            assert payload["granted_purposes"]
        elif record.family == "consent_change":
            assert payload["granted_purposes"] == []
            assert payload["revoked_purpose"] is not None
            assert payload["consent_revision"] > 0
            consent_revisions.add(payload["consent_revision"])
        elif record.family == "medication_withdrawal":
            assert payload["active_medications"] == []
            assert payload["withdrawn_medication"] is not None
        elif record.family == "allergy_update":
            assert payload["allergies"]
            assert payload["allergies"][0] in payload["active_medications"]
        else:  # reconciliation
            assert len(payload["conflicting_sources"]) == 2

    # Consent revisions actually sweep the revision space across the dataset.
    assert consent_revisions == {1, 2, 3}

    # Determinism: payload is a pure function of (seed, family, idx).
    first = ds.records[0]
    again = workflow_payload(seed=21, family=first.family, idx=first.payload["sequence"])
    for key, value in again.items():
        assert first.payload[key] == value


def test_validate_dataset_accepts_kernel_output():
    """The bundled fail-closed validator passes a healthy generated dataset."""

    validate_dataset(generate(seed=23, n=60))


# ---------------------------------------------------------------------------
# Adversarial controls
# ---------------------------------------------------------------------------


def test_leakage_detected_when_unit_reappears_in_another_split():
    """Same unit_id injected into two splits must be flagged by the kernel."""

    train = generate(seed=3, n=24, split="train")
    cloned = generate(seed=3, n=24, split="dev")
    # Force a genuine leakage scenario: one train unit_id appears in dev.
    leaked_record = train.records[0]
    leaked = dk.DatasetRecord(
        unit_id=leaked_record.unit_id,
        family=leaked_record.family,
        split="dev",
        payload=dict(leaked_record.payload),
    )
    datasets = {
        "train": train,
        "dev": dk.Dataset(
            venue=cloned.venue,
            seed=cloned.seed,
            generator_version=cloned.generator_version,
            records=tuple([leaked, *cloned.records]),
            inventory=cloned.inventory,
            content_sha256=cloned.content_sha256,
        ),
    }
    reasons = dk.detect_split_leakage(datasets)
    assert "SPLIT_LEAKAGE" in reasons
    with pytest.raises(dk.DatasetError) as excinfo:
        dk.assert_no_leakage(datasets)
    assert excinfo.value.reason_code == "SPLIT_LEAKAGE"


def test_degenerate_family_frequencies_refused():
    """A family with zero records (or a dominant one) is refused."""

    ds = generate(seed=13, n=50)
    # Zero-record family: remove one family entirely (records AND inventory),
    # simulating a builder that silently lost a class.
    victim = AIME_FAMILIES[-1]
    survivors = [r for r in ds.records if r.family != victim]
    gutted_inventory = {
        **ds.inventory,
        "by_family": {f: 0 if f == victim else c for f, c in ds.inventory["by_family"].items()},
        "total": len(survivors),
    }
    gutted = dk.Dataset(
        venue=ds.venue,
        seed=ds.seed,
        generator_version=ds.generator_version,
        records=tuple(survivors),
        inventory=gutted_inventory,
        content_sha256=ds.content_sha256,
    )
    with pytest.raises(dk.DatasetError) as excinfo:
        dk.assert_valid_frequencies(gutted)
    assert excinfo.value.reason_code == "INVALID_FAMILY_FREQUENCY"
    assert "zero records" in excinfo.value.detail

    # Dominant family: one family absorbs almost every record.
    dominant_inventory = {
        **ds.inventory,
        "by_family": {
            f: (1 if i == 0 else 30 if i == 1 else 0) for i, f in enumerate(AIME_FAMILIES)
        },
        "total": 31,
    }
    dominant = dk.Dataset(
        venue=ds.venue,
        seed=ds.seed,
        generator_version=ds.generator_version,
        records=tuple(ds.records),
        inventory=dominant_inventory,
        content_sha256=ds.content_sha256,
    )
    with pytest.raises(dk.DatasetError) as excinfo:
        dk.assert_valid_frequencies(dominant)
    assert excinfo.value.reason_code == "INVALID_FAMILY_FREQUENCY"


def test_unknown_split_refused():
    """Unknown split name fails closed with UNKNOWN_SPLIT."""

    with pytest.raises(dk.DatasetError) as excinfo:
        generate(seed=1, split="holdout", n=12)
    assert excinfo.value.reason_code == "UNKNOWN_SPLIT"


def test_unknown_family_workflow_payload_refused():
    """Workflow payload for an unregistered family fails closed."""

    with pytest.raises(dk.DatasetError) as excinfo:
        workflow_payload(seed=1, family="phantom_family", idx=0)
    assert excinfo.value.reason_code == "UNKNOWN_AIME_FAMILY"


def test_invalid_n_refused():
    """Non-positive n is refused by the kernel before any record is built."""

    for bad in (0, -5):
        with pytest.raises(dk.DatasetError) as excinfo:
            generate(seed=1, n=bad)
        assert excinfo.value.reason_code == "INVALID_N"


def test_no_phi_fields_in_any_record(tmp_path):
    """No PHI/PII-named field ever appears in payloads or written artifacts."""

    ds = generate(seed=17, n=40)
    for record in ds.records:
        for key in record.payload:
            assert not any(marker in key.lower() for marker in dk.PHI_FIELD_MARKERS)
        # Payload values stay structural placeholders: no free-text identities.
        blob = json.dumps(record.payload, sort_keys=True).lower()
        for marker in ("patient_name", "doctor", "@", "national"):
            assert marker not in blob
    write_dataset(tmp_path, seed=17, n=40)
    text = (tmp_path / "dataset.jsonl").read_text()
    for marker in dk.PHI_FIELD_MARKERS:
        assert marker not in text.lower()
    assert DEFAULT_N > 0  # default cardinality sanity
