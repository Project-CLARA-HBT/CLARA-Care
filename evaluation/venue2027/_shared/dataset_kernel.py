"""CLARA-Care 2027 shared deterministic dataset generator kernel.

Purpose
-------
Provide one audited, deterministic dataset builder that every venue's
``generate_dataset.py`` delegates to. It guarantees the properties the program
manifest requires:

- same ``(venue, seed, split, n)`` always yields byte-identical content (stable
  content hash),
- splits are disjoint by *independent unit* (no split leakage),
- a cardinality/family inventory is emitted alongside the data,
- a detector that fails closed on split leakage or invalid family frequencies,
- synthetic provenance only (no PHI fields may appear).

Allowed input
-------------
A ``DatasetSpec`` describing the venue, families, split ratios and seed.

Failure semantics
-----------------
Raises ``DatasetError`` with a stable reason code for unknown venue, leakage,
invalid frequencies, or PHI-named fields. Never silently produces a leaky split.

Version
-------
``DATASET_KERNEL_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import random
from collections.abc import Iterable
from typing import Any

DATASET_KERNEL_VERSION = "1.0.0"

SPLITS: tuple[str, ...] = ("train", "dev", "test")
PHI_FIELD_MARKERS: tuple[str, ...] = (
    "name",
    "email",
    "phone",
    "address",
    "national_id",
    "passport",
    "mrn",
    "insurance_id",
    "dob",
    "date_of_birth",
)

# Per-venue unit id prefix so independently generated datasets can never collide.
VENUE_UNIT_PREFIX: dict[str, str] = {
    "compsac": "sched",
    "popets": "rev",
    "aime": "vig",
    "ifip_sec": "req",
    "sacmat": "dlg",
    "acns": "evd",
    "dsn": "rcv",
    "dimva": "camp",
    "pst": "aud",
}

VENUE_FAMILIES: dict[str, tuple[str, ...]] = {
    "compsac": ("clean", "omitted_dependency", "epoch_race", "stale_readset"),
    "popets": ("fresh", "revoked_then_dispatch", "cross_purpose", "transitive_gap"),
    "aime": ("stable_history", "consent_change", "medication_withdrawal", "allergy_update", "reconciliation"),
    "ifip_sec": ("fresh_accept", "cross_purpose_replay", "delegation_replay", "lineage_splice"),
    "sacmat": ("conformant", "expiry_divergence", "policy_skew", "obligation_mismatch"),
    "acns": ("bound_evidence", "attestation_downgrade", "unbound_claim", "replayed_receipt"),
    "dsn": ("clean_recovery", "torn_write", "duplicate_retry", "fsync_failure"),
    "dimva": ("benign_session", "low_and_slow", "cross_tool_obfuscation", "burst_probe"),
    "pst": ("full_evidence", "minimized_omission", "receipt_anchored", "linkability_leak"),
}


class DatasetError(ValueError):
    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class DatasetSpec:
    venue: str
    seed: int
    n: int
    train_ratio: float = 0.6
    dev_ratio: float = 0.2
    test_ratio: float = 0.2

    def validate(self) -> None:
        if self.venue not in VENUE_FAMILIES:
            raise DatasetError("UNKNOWN_VENUE", f"no families defined for {self.venue!r}")
        if self.n <= 0:
            raise DatasetError("INVALID_N", "n must be positive")
        total = self.train_ratio + self.dev_ratio + self.test_ratio
        if abs(total - 1.0) > 1e-9:
            raise DatasetError("INVALID_SPLIT_RATIOS", f"ratios sum to {total}, expected 1.0")
        if min(self.train_ratio, self.dev_ratio, self.test_ratio) < 0:
            raise DatasetError("INVALID_SPLIT_RATIOS", "ratios must be non-negative")


@dataclasses.dataclass(frozen=True)
class DatasetRecord:
    unit_id: str
    family: str
    split: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "family": self.family,
            "split": self.split,
            "payload": self.payload,
        }


@dataclasses.dataclass(frozen=True)
class Dataset:
    venue: str
    seed: int
    generator_version: str
    records: tuple[DatasetRecord, ...]
    inventory: dict[str, Any]
    content_sha256: str

    def to_jsonl(self) -> str:
        return "\n".join(json.dumps(r.to_dict(), sort_keys=True) for r in self.records) + "\n"

    def split(self, name: str) -> tuple[DatasetRecord, ...]:
        return tuple(r for r in self.records if r.split == name)


def _check_no_phi(payload: dict[str, Any]) -> None:
    for key in payload:
        lowered = key.lower()
        if any(marker in lowered for marker in PHI_FIELD_MARKERS):
            raise DatasetError("PHI_FIELD_PRESENT", f"field {key!r} looks like PHI/PII")


def _family_assignment(venue: str, n: int) -> list[str]:
    families = VENUE_FAMILIES[venue]
    # Balanced round-robin so family frequencies are valid by construction.
    return [families[i % len(families)] for i in range(n)]


def _split_assignment(n: int, spec: DatasetSpec) -> list[str]:
    n_train = int(round(n * spec.train_ratio))
    n_dev = int(round(n * spec.dev_ratio))
    # Remainder to test guarantees full coverage of n.
    n_test = n - n_train - n_dev
    return ["train"] * n_train + ["dev"] * n_dev + ["test"] * n_test


def generate(venue: str, seed: int, n: int, *, split: str | None = None) -> Dataset:
    """Generate a deterministic synthetic dataset for ``venue``.

    ``split`` filters the returned records to one split (buffered dataset is
    still built from the full spec so the hash is split-independent).
    """

    spec = DatasetSpec(venue=venue, seed=seed, n=n)
    spec.validate()

    families = _family_assignment(venue, n)
    split_labels = _split_assignment(n, spec)
    rng = random.Random(seed)

    # Deterministic unit ordering independent of Python dict/set iteration.
    order = list(range(n))
    rng.shuffle(order)

    records: list[DatasetRecord] = []
    prefix = VENUE_UNIT_PREFIX[venue]
    for idx in order:
        family = families[idx]
        label = split_labels[idx]
        payload = _payload(venue, family, seed, idx)
        _check_no_phi(payload)
        records.append(
            DatasetRecord(
                unit_id=f"{prefix}-{seed}-{idx:05d}",
                family=family,
                split=label,
                payload=payload,
            )
        )
    records.sort(key=lambda r: r.unit_id)

    inventory = _inventory(records, venue, seed)
    digest = hashlib.sha256(
        json.dumps(
            {
                "venue": venue,
                "seed": seed,
                "version": DATASET_KERNEL_VERSION,
                "records": [r.unit_id + ":" + r.family + ":" + r.split for r in records],
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()

    if split is not None:
        if split not in SPLITS:
            raise DatasetError("UNKNOWN_SPLIT", f"{split!r} is not one of {SPLITS}")
        records = [r for r in records if r.split == split]

    return Dataset(
        venue=venue,
        seed=seed,
        generator_version=DATASET_KERNEL_VERSION,
        records=tuple(records),
        inventory=inventory,
        content_sha256=digest,
    )


def _payload(venue: str, family: str, seed: int, idx: int) -> dict[str, Any]:
    """Small, deterministic, PHI-free payload used by every venue.

    The payload encodes the family as the ground-truth signal so downstream
    oracle/baseline code can be exercised, but it carries no real data.
    """

    return {
        "family": family,
        "synthetic": True,
        "determinant": (seed * 7919 + idx * 104729) % 100003,
        "sequence": idx,
    }


def _inventory(records: Iterable[DatasetRecord], venue: str, seed: int) -> dict[str, Any]:
    by_split: dict[str, int] = {s: 0 for s in SPLITS}
    by_family: dict[str, int] = {f: 0 for f in VENUE_FAMILIES[venue]}
    for record in records:
        by_split[record.split] += 1
        by_family[record.family] += 1
    return {
        "venue": venue,
        "seed": seed,
        "total": sum(by_split.values()),
        "by_split": by_split,
        "by_family": by_family,
        "generator_version": DATASET_KERNEL_VERSION,
    }


def detect_split_leakage(datasets: dict[str, Dataset]) -> tuple[str, ...]:
    """Return reason codes for any leaky split combination (empty == clean)."""

    reasons: list[str] = []
    seen: dict[str, str] = {}
    for name, dataset in datasets.items():
        for record in dataset.records:
            key = f"{record.unit_id}"
            if key in seen and seen[key] != name:
                reasons.append("SPLIT_LEAKAGE")
            seen[key] = name
    return tuple(sorted(set(reasons)))


def assert_no_leakage(datasets: dict[str, Dataset]) -> None:
    reasons = detect_split_leakage(datasets)
    if reasons:
        raise DatasetError(reasons[0], "same independent unit appears in multiple splits")


def assert_valid_frequencies(dataset: Dataset, *, tolerance: float = 0.35) -> None:
    """Refuse degenerate family distributions (a family missing or dominant)."""

    family_counts = dataset.inventory["by_family"]
    total = sum(family_counts.values())
    if total == 0:
        raise DatasetError("EMPTY_DATASET", "no records")
    for family, count in family_counts.items():
        if count == 0:
            raise DatasetError(
                "INVALID_FAMILY_FREQUENCY",
                f"family {family!r} has zero records; every family must be represented",
            )
        share = count / total
        expected = 1.0 / len(family_counts)
        if abs(share - expected) > tolerance:
            raise DatasetError(
                "INVALID_FAMILY_FREQUENCY",
                f"{family} share {share:.3f} deviates from {expected:.3f} beyond {tolerance}",
            )
