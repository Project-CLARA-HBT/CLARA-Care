"""SACMAT-dataset — synthetic delegated-consent dataset and split builder.

Purpose
-------
Build the synthetic SACMAT 2027 dataset for "PolicyTrace: Temporal
Conformance Testing of Delegated Consent across Heterogeneous Policy
Engines" (``research/venue2027/VENUES/sacmat/RESEARCH_BLUEPRINT.md``, task
contract ``research/venue2027/VENUES/sacmat/TASKS/SACMAT-dataset.md``).
This module is a thin, deterministic adapter over the audited shared kernel
``evaluation/venue2027/_shared/dataset_kernel.py`` — it MUST delegate, never
reimplement, split assignment, family balancing, leakage detection or PHI
screening.

On top of the kernel payload every record is enriched with the three
SACMAT-controlled variables that downstream oracle and baseline tasks
consume, each a pure deterministic function of ``(seed, family, idx)``:

- ``delegation_depth`` — redelegation depth 0..3 of the synthetic grant,
- ``policy_version_skew`` — policy-version offset 0..4 between the grant
  epoch and the decision-time policy version,
- ``expiry_offset_ticks`` — signed logical-tick offset of the decision time
  relative to the grant expiry (negative == lapsed).

The family tag remains the ground-truth signal (kernel contract); the three
variables are family-conditioned so every family has a learnable witness:
``conformant`` keeps zero skew and a non-lapsed offset, ``expiry_divergence``
always carries a strictly negative offset, ``policy_skew`` always carries a
strictly positive skew. ``obligation_mismatch`` keeps the raw draws.

Allowed input
-------------
``generate(seed, split, n)`` with ``seed`` a non-negative int, ``split`` one
of ``dataset_kernel.SPLITS`` (or ``None`` for the full buffered dataset) and
``n`` a positive record count. ``write_dataset(outdir, seed, n)`` persists
the full dataset plus a manifest; ``verify_dataset_dir(outdir)`` re-derives
everything and fails closed on any mismatch.

Failure semantics
-----------------
All failures raise ``dataset_kernel.DatasetError`` with a stable reason code
delegated from the kernel (``INVALID_N``, ``UNKNOWN_SPLIT``,
``INVALID_SPLIT_RATIOS``, ``PHI_FIELD_PRESENT``) or raised locally by
``verify_dataset_dir`` (``MANIFEST_HASH_MISMATCH``). No silent partial
writes: the manifest is written only after the JSONL bytes are final.

Version
-------
``GENERATOR_VERSION = "1.0.0"``
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from evaluation.venue2027._shared import dataset_kernel as dk

GENERATOR_VERSION = "1.0.0"
MANIFEST_SCHEMA_VERSION = "clara.venue2027.sacmat.dataset_manifest.v1"
DATASET_FILENAME = "dataset.jsonl"
MANIFEST_FILENAME = "manifest.json"

VENUE = "sacmat"
SACMAT_FAMILIES: tuple[str, ...] = dk.VENUE_FAMILIES[VENUE]

FAMILY_CONFORMANT = "conformant"
FAMILY_EXPIRY_DIVERGENCE = "expiry_divergence"
FAMILY_POLICY_SKEW = "policy_skew"
FAMILY_OBLIGATION_MISMATCH = "obligation_mismatch"

DELEGATION_DEPTH_MAX = 3
POLICY_VERSION_SKEW_MAX = 4
EXPIRY_OFFSET_TICK_RANGE = 200

FIELD_DELEGATION_DEPTH = "delegation_depth"
FIELD_POLICY_VERSION_SKEW = "policy_version_skew"
FIELD_EXPIRY_OFFSET_TICKS = "expiry_offset_ticks"


def _sacmat_payload(family: str, seed: int, idx: int) -> dict[str, int]:
    """Deterministic, PHI-free SACMAT variables for one independent unit.

    Uses the same determinant family as the kernel payload so a unit's
    variables are reproducible from ``(seed, family, idx)`` alone, independent
    of which split was requested. No clock, no randomness, no I/O.
    """

    determinant = (seed * 7919 + idx * 104729) % 100003
    delegation_depth = determinant % (DELEGATION_DEPTH_MAX + 1)
    policy_version_skew = (determinant // 7) % (POLICY_VERSION_SKEW_MAX + 1)
    expiry_offset = (determinant // 11) % (2 * EXPIRY_OFFSET_TICK_RANGE) - EXPIRY_OFFSET_TICK_RANGE
    if family == FAMILY_CONFORMANT:
        policy_version_skew = 0
        expiry_offset = abs(expiry_offset)
    elif family == FAMILY_EXPIRY_DIVERGENCE:
        expiry_offset = -abs(expiry_offset) - 1
    elif family == FAMILY_POLICY_SKEW:
        policy_version_skew = policy_version_skew % POLICY_VERSION_SKEW_MAX + 1
    return {
        FIELD_DELEGATION_DEPTH: delegation_depth,
        FIELD_POLICY_VERSION_SKEW: policy_version_skew,
        FIELD_EXPIRY_OFFSET_TICKS: expiry_offset,
    }


def generate(seed: int, split: str | None, n: int) -> dk.Dataset:
    """Return the deterministic SACMAT dataset for ``(seed, split, n)``.

    Delegates to ``dataset_kernel.generate('sacmat', ...)`` and enriches every
    record payload with the SACMAT-controlled variables. The kernel
    ``content_sha256`` is split-independent by construction; enrichment is a
    pure function of the unit, so a unit's payload is byte-identical whether
    drawn from the full dataset or a single split.
    """

    dataset = dk.generate(VENUE, seed=seed, n=n, split=split)
    enriched = tuple(
        dataclasses.replace(
            record,
            payload={
                **record.payload,
                **_sacmat_payload(record.family, seed, record.payload["sequence"]),
            },
        )
        for record in dataset.records
    )
    return dataclasses.replace(dataset, records=enriched)


def write_dataset(outdir: str | os.PathLike[str], seed: int, n: int) -> dict[str, Any]:
    """Persist the full SACMAT dataset and manifest under ``outdir``.

    Writes ``dataset.jsonl`` (one JSON object per independent unit,
    sort_keys, newline-terminated) and ``manifest.json`` carrying the split
    inventory, the kernel content hash and the SHA256 of the JSONL bytes.
    Deterministic: the same ``(outdir content, seed, n)`` yields byte-identical
    files. Returns the manifest dict.
    """

    dataset = generate(seed, None, n)
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    jsonl_bytes = dataset.to_jsonl().encode("utf-8")
    (out / DATASET_FILENAME).write_bytes(jsonl_bytes)
    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "venue": VENUE,
        "seed": seed,
        "n": n,
        "generator_version": GENERATOR_VERSION,
        "dataset_kernel_version": dk.DATASET_KERNEL_VERSION,
        "unit_id_prefix": dk.VENUE_UNIT_PREFIX[VENUE],
        "families": list(SACMAT_FAMILIES),
        "content_sha256": dataset.content_sha256,
        "dataset_jsonl_sha256": hashlib.sha256(jsonl_bytes).hexdigest(),
        "inventory": dataset.inventory,
    }
    (out / MANIFEST_FILENAME).write_bytes(
        (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    return manifest


def verify_dataset_dir(outdir: str | os.PathLike[str]) -> dict[str, Any]:
    """Re-derive the dataset and fail closed on any mismatch with ``outdir``.

    Regenerates from the manifest's ``(seed, n)``, compares the JSONL bytes
    byte-for-byte, and re-checks both recorded SHA256 digests. Raises
    ``DatasetError("MANIFEST_HASH_MISMATCH", ...)`` on any divergence;
    returns the manifest on success.
    """

    out = Path(outdir)
    manifest = json.loads((out / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    seed, n = int(manifest["seed"]), int(manifest["n"])
    regenerated = generate(seed, None, n).to_jsonl().encode("utf-8")
    on_disk = (out / DATASET_FILENAME).read_bytes()
    if regenerated != on_disk:
        raise dk.DatasetError(
            "MANIFEST_HASH_MISMATCH",
            f"{out / DATASET_FILENAME} does not match a regeneration for seed={seed} n={n}",
        )
    if hashlib.sha256(on_disk).hexdigest() != manifest["dataset_jsonl_sha256"]:
        raise dk.DatasetError(
            "MANIFEST_HASH_MISMATCH",
            f"dataset_jsonl_sha256 mismatch for {out / DATASET_FILENAME}",
        )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--seed", type=int, default=2027)
    parser.add_argument("--n", type=int, default=120)
    args = parser.parse_args(argv)
    try:
        manifest = write_dataset(args.outdir, args.seed, args.n)
        verify_dataset_dir(args.outdir)
    except dk.DatasetError as exc:
        print(f"generate_dataset failed: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "outdir": str(args.outdir),
                "seed": args.seed,
                "n": args.n,
                "content_sha256": manifest["content_sha256"],
                "dataset_jsonl_sha256": manifest["dataset_jsonl_sha256"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
