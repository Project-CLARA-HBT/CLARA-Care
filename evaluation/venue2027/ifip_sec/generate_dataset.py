"""IFIP_SEC venue2027 synthetic dataset and split builder (task IFIP_SEC-dataset).

Purpose
-------
Deterministic, PHI-free synthetic dataset generator for the IFIP SEC 2027
study "Replay-Closed Authorization Across Purpose, Delegation, and AI
Proposal Lineage" (phase P02, task ``IFIP_SEC-dataset``). All record
construction is delegated to the audited shared kernel
:mod:`evaluation.venue2027._shared.dataset_kernel` — the same
``(venue, seed, n)`` always yields byte-identical content and a stable
content hash; splits are disjoint by independent unit. This module only
layers the IFIP-specific authorization payload onto each kernel record:

- ``purpose`` / ``granted_purpose`` — presented vs. granted consent-purpose
  scope (cross-purpose replay signal: they differ for ``cross_purpose_replay``),
- ``delegation_depth`` — length of the delegated receipt chain (>= 1 for the
  delegation families),
- ``consent_epoch`` / ``parent_consent_epoch`` — claimed vs. parent consent
  epoch (lineage-splice signal: they differ for ``lineage_splice``),
- ``replay_flag`` — whether the record represents a replayed presentation,
- ``nonce_state`` — consume-once state of the receipt nonce
  (``fresh`` | ``consumed`` | ``consumed_by_delegate``).

The payload encodes the family as the ground-truth signal so downstream
independent-oracle and baseline code can be exercised; it carries no real
data and is never used for algorithm tuning.

Allowed input
-------------
``seed`` (int), ``split`` (``"all"`` or one of the kernel splits
``train``/``dev``/``test``), ``n`` (positive int) for :func:`generate`;
an output directory for :func:`write_dataset`. No network, no database,
no hidden clock or randomness beyond the seed; no production secret or
patient-data access.

Failure semantics
-----------------
Fail closed with stable ``reason_code`` via
:class:`dataset_kernel.DatasetError`: ``UNKNOWN_VENUE`` / ``INVALID_N`` /
``INVALID_SPLIT_RATIOS`` (kernel spec validation), ``UNKNOWN_SPLIT``
(kernel split filter), ``UNKNOWN_FAMILY`` (defensive: an unregistered
family cannot be smuggled through the payload layer), ``PHI_FIELD_PRESENT``
(extended payload field resembles PHI/PII), ``SPLIT_LEAKAGE`` /
``INVALID_FAMILY_FREQUENCY`` (fail-closed validators applied by
:func:`validate_dataset` and :func:`write_dataset` before anything is
written to disk). Never silently produces a leaky split or a degenerate
family distribution.

Version
-------
``IFIP_DATASET_GENERATOR_VERSION = "1.0.0"``
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from evaluation.venue2027._shared import dataset_kernel as dk

VENUE = "ifip_sec"
IFIP_DATASET_GENERATOR_VERSION = "1.0.0"
DATASET_SCHEMA_VERSION = "clara.venue2027.ifip_sec.dataset.v1"

_PURPOSES: tuple[str, ...] = ("self_care", "clinical_review", "billing_audit", "research_export")
_NONCE_STATES: tuple[str, ...] = ("fresh", "consumed", "consumed_by_delegate")
_PAYLOAD_FIELDS: tuple[str, ...] = (
    "purpose",
    "granted_purpose",
    "delegation_depth",
    "consent_epoch",
    "parent_consent_epoch",
    "replay_flag",
    "nonce_state",
)


def _determinant(seed: int, idx: int) -> int:
    """Same arithmetic anchor as the kernel payload, so both layers agree."""

    return (seed * 7919 + idx * 104729) % 100003


def _ifip_extension(family: str, seed: int, idx: int) -> dict[str, Any]:
    """Deterministic IFIP authorization payload for one independent unit.

    The family drives the ground-truth signal encoding; every value is a pure
    function of ``(family, seed, idx)`` with no clock or hidden randomness.
    """

    det = _determinant(seed, idx)
    granted = _PURPOSES[det % len(_PURPOSES)]
    epoch = det % 4
    if family == "fresh_accept":
        presented, replay, nonce_state = granted, False, "fresh"
        depth, parent_epoch = det % 3, epoch
    elif family == "cross_purpose_replay":
        presented, replay, nonce_state = _PURPOSES[(det + 1) % len(_PURPOSES)], True, "consumed"
        depth, parent_epoch = det % 2, epoch
    elif family == "delegation_replay":
        presented, replay = granted, True
        nonce_state = "consumed_by_delegate"
        depth, parent_epoch = 1 + det % 3, epoch
    elif family == "lineage_splice":
        presented, replay, nonce_state = granted, False, "fresh"
        depth = 1 + det % 2
        parent_epoch = (epoch + 1) % 4
    else:
        raise dk.DatasetError("UNKNOWN_FAMILY", f"family {family!r} is not registered for {VENUE}")
    return {
        "purpose": presented,
        "granted_purpose": granted,
        "delegation_depth": depth,
        "consent_epoch": f"consent-{epoch}",
        "parent_consent_epoch": f"consent-{parent_epoch}",
        "replay_flag": replay,
        "nonce_state": nonce_state,
    }


def _assert_no_phi(payload: Mapping[str, Any]) -> None:
    for key in payload:
        lowered = key.lower()
        if any(marker in lowered for marker in dk.PHI_FIELD_MARKERS):
            raise dk.DatasetError("PHI_FIELD_PRESENT", f"field {key!r} looks like PHI/PII")


def _extend(dataset: dk.Dataset) -> dk.Dataset:
    """Return a copy of ``dataset`` whose records carry the IFIP payload."""

    records: list[dk.DatasetRecord] = []
    for record in dataset.records:
        idx = int(record.unit_id.rsplit("-", 1)[-1])
        payload = {**record.payload, **_ifip_extension(record.family, dataset.seed, idx)}
        _assert_no_phi(payload)
        records.append(
            dk.DatasetRecord(
                unit_id=record.unit_id,
                family=record.family,
                split=record.split,
                payload=payload,
            )
        )
    return dataclasses.replace(dataset, records=tuple(records))


def generate(seed: int, split: str = "all", n: int = 48) -> dk.Dataset:
    """Generate the deterministic IFIP_SEC dataset.

    ``split="all"`` returns every record; any other value must be one of
    ``train``/``dev``/``test`` and filters the buffered dataset (the kernel
    builds from the full spec, so the content hash is split-independent).
    Raises :class:`dataset_kernel.DatasetError` with a stable reason code on
    invalid input; never returns a partially built dataset.
    """

    if split == "all":
        return _extend(dk.generate(VENUE, seed=seed, n=n))
    return _extend(dk.generate(VENUE, seed=seed, n=n, split=split))


def validate_dataset(dataset: dk.Dataset) -> None:
    """Fail closed on degenerate family frequencies or split leakage."""

    n = int(dataset.inventory["total"])
    dk.assert_valid_frequencies(dataset)
    dk.assert_no_leakage({s: generate(seed=dataset.seed, split=s, n=n) for s in dk.SPLITS})


def write_dataset(outdir: str | Path, seed: int, n: int) -> dict[str, Any]:
    """Build, validate, and persist one dataset artifact directory.

    Writes ``records.jsonl``, ``inventory.json`` and ``manifest.json`` under
    ``outdir`` only after the fail-closed validators pass; returns the
    manifest (path-free, so identical inputs yield byte-identical manifests).
    """

    dataset = generate(seed=seed, split="all", n=n)
    validate_dataset(dataset)
    payload_jsonl = dataset.to_jsonl()
    manifest: dict[str, Any] = {
        "schema_version": DATASET_SCHEMA_VERSION,
        "venue": VENUE,
        "seed": seed,
        "n": n,
        "records": len(dataset.records),
        "generator_version": IFIP_DATASET_GENERATOR_VERSION,
        "dataset_kernel_version": dk.DATASET_KERNEL_VERSION,
        "unit_prefix": dk.VENUE_UNIT_PREFIX[VENUE],
        "splits": list(dk.SPLITS),
        "families": list(dk.VENUE_FAMILIES[VENUE]),
        "inventory": dataset.inventory,
        "content_sha256": dataset.content_sha256,
        "records_sha256": hashlib.sha256(payload_jsonl.encode("utf-8")).hexdigest(),
        "synthetic_only": True,
        "phi_fields": [],
    }
    out_path = Path(outdir)
    out_path.mkdir(parents=True, exist_ok=True)
    (out_path / "records.jsonl").write_text(payload_jsonl, encoding="utf-8")
    (out_path / "inventory.json").write_text(
        json.dumps(dataset.inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_path / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IFIP_SEC 2027 synthetic dataset builder")
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--seed", type=int, default=2027)
    parser.add_argument("--n", type=int, default=120)
    args = parser.parse_args(argv)
    manifest = write_dataset(args.outdir, seed=args.seed, n=args.n)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
