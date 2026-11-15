"""DSN venue synthetic dataset generator (task DSN-dataset, phase P02).

Purpose
-------
Build the deterministic crash-window / recovery scenario dataset for the DSN
2027 study "Recoverable Safety Journals for Crash-Consistent AI-Mediated
Health-State Mutations". All dataset semantics (determinism, split disjointness
by independent unit, family balance, PHI refusal) are delegated to the audited
shared kernel ``evaluation.venue2027._shared.dataset_kernel``; this module only
adds the DSN-specific scenario payload.

Payload (DSN-specific, deterministic, PHI-free)
-----------------------------------------------
- ``crash_point``: crash cut point of the window (one of ``none``,
  ``pre_commit``, ``post_commit_pre_response``, ``pre_outbox_delivery``);
  mirrors CASE_MATRIX DSN-CASE-02..07 crash/replay windows.
- ``ops_count``: number of governed operations in the window (1..4).
- ``fsync_mode``: durability posture (``group``, ``per_op``, ``async``);
  drives the RQ3 durable-write cost analysis.

Allowed input
-------------
``seed`` (non-negative int), ``split`` (None or one of train/dev/test), ``n``
(positive int). Split ratios follow the kernel defaults (60/20/20).

Failure semantics
-----------------
Any invalid input raises ``DatasetError`` with a stable reason code (delegated
to the kernel); it never silently produces a leaky or unbalanced dataset, and
it never fabricates a result when the kernel refuses the request.

Version
-------
``DSN_DATASET_GENERATOR_VERSION = "1.0.0"``
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from evaluation.venue2027._shared import dataset_kernel as dk

DSN_DATASET_GENERATOR_VERSION = "1.0.0"

VENUE = "dsn"

CRASH_POINTS: tuple[str, ...] = (
    "none",
    "pre_commit",
    "post_commit_pre_response",
    "pre_outbox_delivery",
)
FSYNC_MODES: tuple[str, ...] = ("group", "per_op", "async")

_RECOVERABLE_OUTCOME: dict[str, str] = {
    "clean_recovery": "COMMITTED",
    "torn_write": "INDETERMINATE",
    "duplicate_retry": "COMMITTED",
    "fsync_failure": "REJECTED",
}


@dataclasses.dataclass(frozen=True)
class DSNPayloadPolicy:
    """Deterministic mapping from (family, unit index) to DSN scenario knobs."""

    crash_points: tuple[str, ...] = CRASH_POINTS
    fsync_modes: tuple[str, ...] = FSYNC_MODES

    def crash_point(self, family: str, idx: int) -> str:
        if family == "clean_recovery":
            return self.crash_points[0]
        if family == "torn_write":
            return self.crash_points[1]
        if family == "duplicate_retry":
            return self.crash_points[2]
        return self.crash_points[3]

    def fsync_mode(self, family: str, idx: int) -> str:
        if family == "fsync_failure":
            return self.fsync_modes[2]
        return self.fsync_modes[idx % 2]

    def ops_count(self, family: str, idx: int) -> int:
        if family == "duplicate_retry":
            return 2 + (idx % 2)
        return 1 + (idx % 2)

    def expected_outcome(self, family: str) -> str:
        return _RECOVERABLE_OUTCOME[family]


def _payload(
    policy: DSNPayloadPolicy, family: str, seed: int, idx: int
) -> dict[str, Any]:
    """Kernel-compatible payload hook: DSN scenario knobs, PHI-free by construction."""

    payload = dk._payload(VENUE, family, seed, idx)
    payload.update(
        {
            "crash_point": policy.crash_point(family, idx),
            "ops_count": policy.ops_count(family, idx),
            "fsync_mode": policy.fsync_mode(family, idx),
            "expected_oracle_decision": policy.expected_outcome(family),
            "generator_version": DSN_DATASET_GENERATOR_VERSION,
        }
    )
    return payload


def generate(seed: int, split: str | None, n: int) -> dk.Dataset:
    """Generate the DSN dataset via the shared kernel plus DSN payload knobs.

    ``split=None`` returns the full buffered dataset; a named split returns only
    that split's records (the content hash stays split-independent because the
    kernel hashes the full buffered assignment before filtering).
    """

    dataset = dk.generate(VENUE, seed=seed, n=n, split=split)
    policy = DSNPayloadPolicy()
    records = tuple(
        dataclasses.replace(
            record,
            payload=_payload(policy, record.family, seed, int(record.unit_id.rsplit("-", 1)[-1])),
        )
        for record in dataset.records
    )
    return dataclasses.replace(dataset, records=records)


def write_dataset(outdir: str | Path, seed: int, n: int) -> dict[str, Any]:
    """Write the full dataset (all splits) plus inventory manifest to ``outdir``.

    Emits ``dataset.jsonl`` (records), ``inventory.json`` (split/family
    cardinalities and content hash) and ``manifest.json`` (run manifest with
    generator/kernel versions). Returns the manifest dict. Deterministic: the
    same ``(outdir content, seed, n)`` pair always yields byte-identical files.
    """

    dataset = generate(seed=seed, split=None, n=n)
    # Split-filtered views are wrappers over the buffered dataset; leakage
    # detection is run on explicit per-split Datasets built through the kernel.
    per_split = {s: dk.generate(VENUE, seed=seed, n=n, split=s) for s in dk.SPLITS}
    dk.assert_no_leakage(per_split)
    dk.assert_valid_frequencies(dataset)

    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)

    jsonl_text = dataset.to_jsonl()
    inventory_text = json.dumps(dataset.inventory, indent=2, sort_keys=True) + "\n"
    manifest: dict[str, Any] = {
        "venue": VENUE,
        "seed": seed,
        "n": n,
        "generator_version": DSN_DATASET_GENERATOR_VERSION,
        "kernel_version": dk.DATASET_KERNEL_VERSION,
        "content_sha256": dataset.content_sha256,
        "records_sha256": hashlib.sha256(jsonl_text.encode()).hexdigest(),
        "inventory_sha256": hashlib.sha256(inventory_text.encode()).hexdigest(),
        "files": ["dataset.jsonl", "inventory.json"],
        "synthetic_only": True,
    }
    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"

    (out / "dataset.jsonl").write_text(jsonl_text, encoding="utf-8")
    (out / "inventory.json").write_text(inventory_text, encoding="utf-8")
    (out / "manifest.json").write_text(manifest_text, encoding="utf-8")
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the DSN synthetic dataset")
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--seed", type=int, default=2027)
    parser.add_argument("--n", type=int, default=48)
    args = parser.parse_args(argv)
    manifest = write_dataset(args.outdir, seed=args.seed, n=args.n)
    print(json.dumps({"content_sha256": manifest["content_sha256"], "n": manifest["n"]}))
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
