"""COMPSAC-dataset — synthetic dataset and split builder.

Purpose
-------
Deterministic synthetic dataset generator for "Dependency-Complete Optimistic
Admission for Concurrent Clinical AI Writes"
(research/venue2027/VENUES/compsac/RESEARCH_BLUEPRINT.md, RQ1-RQ3; fixture
matrix in research/venue2027/VENUES/compsac/CASE_MATRIX.md). All record
construction, split assignment, leakage detection and family-frequency
validation are delegated to the audited shared kernel
:mod:`evaluation.venue2027._shared.dataset_kernel` — this module never
re-implements those invariants. On top of the kernel payload it attaches the
COMPSAC-specific *per-family schedule payload* (dependency density, contention
level, zipf skew, graph fanout) that drives RQ3 contention/fanout experiments,
derived deterministically from ``(seed, family, unit index)`` with pure
integer arithmetic (no clock, no RNG object, no hash randomization).

Allowed input
-------------
- ``seed``: non-negative int (any int is accepted; it only feeds arithmetic).
- ``split``: ``None`` (full buffered dataset) or one of the kernel splits
  ``train`` / ``dev`` / ``test``; anything else is refused by the kernel with
  ``UNKNOWN_SPLIT``.
- ``n``: positive record count; non-positive is refused with ``INVALID_N``.
- :func:`write_dataset` writes the JSONL corpus and inventory JSON under a
  caller-supplied output directory.

Failure semantics (stable reason codes on ``dataset_kernel.DatasetError``)
--------------------------------------------------------------------------
Delegated fail-closed codes: ``UNKNOWN_VENUE``, ``INVALID_N``,
``UNKNOWN_SPLIT``, ``SPLIT_LEAKAGE`` (via :func:`assert_no_leakage`),
``INVALID_FAMILY_FREQUENCY`` / ``EMPTY_DATASET`` (via
:func:`assert_valid_frequencies`), ``PHI_FIELD_PRESENT``. Local code adds
``UNKNOWN_FAMILY`` if a schedule payload is requested for a family outside
the COMPSAC registry. Leaky splits and degenerate family frequencies are
never produced silently: the intended usage is
``assert_no_leakage`` + ``assert_valid_frequencies`` on every emitted dataset.

Version
-------
``GENERATE_DATASET_VERSION = "clara.compsac.generate-dataset-v1"``.
Output is JSON-serializable: :meth:`dataset_kernel.Dataset.to_jsonl` plus the
inventory mapping returned by :func:`write_dataset`.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any

from evaluation.venue2027._shared import dataset_kernel as dk

GENERATE_DATASET_VERSION = "clara.compsac.generate-dataset-v1"
SCHEDULE_PAYLOAD_VERSION = "clara.compsac.schedule-payload-v1"

#: COMPSAC scenario families (kernel registry, CASE_MATRIX mapping).
COMPSAC_FAMILIES: tuple[str, ...] = dk.VENUE_FAMILIES["compsac"]

#: Worker tiers from the blueprint planned population (1, 2, 4, 8, 16).
WORKER_TIERS: tuple[int, ...] = (1, 2, 4, 8, 16)

#: Base dependency density per family; RQ3 sweeps density around these bases.
_FAMILY_DENSITY_BASE: dict[str, float] = {
    "clean": 0.12,
    "omitted_dependency": 0.58,
    "epoch_race": 0.34,
    "stale_readset": 0.47,
}

#: Contention tier bias per family (index shift into WORKER_TIERS).
_FAMILY_CONTENTION_BIAS: dict[str, int] = {
    "clean": 0,
    "omitted_dependency": 2,
    "epoch_race": 3,
    "stale_readset": 1,
}

DEFAULT_N = 120


def schedule_payload(seed: int, family: str, idx: int) -> dict[str, Any]:
    """COMPSAC per-family schedule payload, pure function of (seed, family, idx).

    Deterministic integer arithmetic only — no RNG objects, no clock, no dict
    iteration order dependence — so the same inputs always yield the same
    payload across runs and Python versions.
    """

    if family not in _FAMILY_DENSITY_BASE:
        raise dk.DatasetError(
            "UNKNOWN_FAMILY", f"{family!r} is not a COMPSAC family in {COMPSAC_FAMILIES}"
        )
    bias = _FAMILY_CONTENTION_BIAS[family]
    jitter = ((seed * 7919 + idx * 104729 + bias * 3571) % 199) / 1000.0
    dependency_density = min(1.0, round(_FAMILY_DENSITY_BASE[family] + jitter, 3))
    contention_level = WORKER_TIERS[(seed + idx + bias) % len(WORKER_TIERS)]
    zipf_skew = round(0.5 + ((seed * 31 + idx * 97 + bias * 13) % 101) / 100.0, 3)
    graph_fanout = max(1, min(8, 1 + int(round(dependency_density * 7))))
    return {
        "schedule_version": SCHEDULE_PAYLOAD_VERSION,
        "dependency_density": dependency_density,
        "contention_level": contention_level,
        "zipf_skew": zipf_skew,
        "graph_fanout": graph_fanout,
    }


def _augment(dataset: dk.Dataset, seed: int) -> dk.Dataset:
    """Attach the COMPSAC schedule payload to every kernel record."""

    records = tuple(
        dataclasses.replace(
            record,
            payload={
                **record.payload,
                **schedule_payload(seed, record.family, int(record.payload["sequence"])),
            },
        )
        for record in dataset.records
    )
    inventory = {
        **dataset.inventory,
        "schedule_payload_version": SCHEDULE_PAYLOAD_VERSION,
        "generate_dataset_version": GENERATE_DATASET_VERSION,
    }
    return dataclasses.replace(dataset, records=records, inventory=inventory)


def generate(seed: int, split: str | None = None, n: int = DEFAULT_N) -> dk.Dataset:
    """Generate the deterministic COMPSAC dataset via the shared kernel.

    ``split=None`` returns the full buffered dataset (inventory covers all
    ``n`` records regardless of the filter, so the kernel content hash stays
    split-independent). ``split`` in ``train``/``dev``/``test`` filters the
    records to that split.
    """

    base = dk.generate("compsac", seed=seed, n=n, split=split)
    return _augment(base, seed)


def write_dataset(outdir: str | Path, seed: int, n: int = DEFAULT_N) -> dict[str, Any]:
    """Write ``dataset.jsonl`` + ``inventory.json`` under ``outdir``.

    Returns a JSON-serializable manifest (paths, record counts, SHA256 of the
    JSONL file and the kernel content hash). Raises ``DatasetError`` on any
    kernel refusal; I/O errors propagate untouched.
    """

    dataset = generate(seed, split=None, n=n)
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    jsonl_path = out / "dataset.jsonl"
    inventory_path = out / "inventory.json"
    jsonl_text = dataset.to_jsonl()
    jsonl_path.write_text(jsonl_text, encoding="utf-8")
    jsonl_sha256 = hashlib.sha256(jsonl_text.encode("utf-8")).hexdigest()
    inventory = {
        **dataset.inventory,
        "generator_version": GENERATE_DATASET_VERSION,
        "content_sha256": dataset.content_sha256,
        "jsonl_sha256": jsonl_sha256,
        "records": len(dataset.records),
    }
    inventory_path.write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "jsonl_path": str(jsonl_path),
        "inventory_path": str(inventory_path),
        "records": len(dataset.records),
        "content_sha256": dataset.content_sha256,
        "jsonl_sha256": jsonl_sha256,
    }


__all__ = [
    "COMPSAC_FAMILIES",
    "DEFAULT_N",
    "GENERATE_DATASET_VERSION",
    "SCHEDULE_PAYLOAD_VERSION",
    "WORKER_TIERS",
    "generate",
    "schedule_payload",
    "write_dataset",
]
