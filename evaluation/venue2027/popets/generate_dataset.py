"""POPETS-dataset — synthetic dataset and split builder (Phase P02, venue ``popets``).

Purpose
-------
Deterministic synthetic dataset generator for the PoPETs 2027 study
"Revocation-Complete Future Disclosure for Cached Longitudinal AI Contexts"
(``research/venue2027/VENUES/popets/RESEARCH_BLUEPRINT.md``; scenario matrix
``research/venue2027/VENUES/popets/CASE_MATRIX.md``; task contract
``research/venue2027/VENUES/popets/TASKS/POPETS-dataset.md``). All record
construction, family assignment, split-by-independent-unit assignment, content
hashing, leakage detection and family-frequency validation are delegated to the
audited shared kernel :mod:`evaluation.venue2027._shared.dataset_kernel` — this
module never re-implements those invariants. On top of the kernel payload it
attaches the POPETS-specific *revocation-and-dispatch payload* (revocation
instant, dispatch time, purpose, cache mode, subject history length) that
drives RQ1-RQ3 (post-revocation dispatch leakage through transitive caches,
purpose-bound closure parity, and lineage-density costs), derived
deterministically from ``(seed, family, unit index)`` with pure integer
arithmetic — no clock, no RNG object, no hash randomization, no live provider,
no real PHI.

The four POPETS revocation/cache families come from the kernel registry
``VENUE_FAMILIES["popets"]`` and match the preregistered case-matrix shapes:
``fresh`` (POPETS-CASE-01/04 authorized-dispatch shape), ``revoked_then_dispatch``
(POPETS-CASE-02/08 revocation before retry dispatch), ``cross_purpose``
(POPETS-CASE-05 cross-purpose cache reuse) and ``transitive_gap``
(POPETS-CASE-03/07 derived summary chain with a missing lineage edge).

Allowed input
-------------
- ``seed``: int (feeds deterministic arithmetic only).
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
``UNKNOWN_POPETS_FAMILY`` if a revocation/dispatch payload is requested for a
family outside the POPETS registry. Leaky splits and degenerate family
frequencies are never produced silently: :func:`write_dataset` runs the kernel
validators on every emitted dataset before persisting anything.

Version
-------
``GENERATE_DATASET_VERSION = "clara.popets.generate-dataset-v1"``. Output is
JSON-serializable: :meth:`dataset_kernel.Dataset.to_jsonl` plus the inventory
mapping returned by :func:`write_dataset`.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any

from evaluation.venue2027._shared import dataset_kernel as dk

GENERATE_DATASET_VERSION = "clara.popets.generate-dataset-v1"
REVOCATION_PAYLOAD_VERSION = "clara.popets.revocation-payload-v1"

VENUE = "popets"

#: POPETS scenario families (kernel registry, CASE_MATRIX mapping).
POPETS_FAMILIES: tuple[str, ...] = dk.VENUE_FAMILIES["popets"]

#: Synthetic consent purposes (CASE_MATRIX ``purpose`` vocabulary).
PURPOSES: tuple[str, ...] = ("self_care", "care_summary", "medication_review")

#: Cache modes of the synthetic derived context store (RQ3 cache-hit costs).
CACHE_MODES: tuple[str, ...] = ("none", "prompt_only", "summary_pointer", "retry_payload")

#: Synthetic derivation paths of the lineage graph (blueprint method
#: architecture: prompt segment, cached summary, embedding pointer, retry
#: payload, fallback transport).
LINEAGE_PATHS: tuple[str, ...] = (
    "prompt_segment",
    "cached_summary",
    "embedding_pointer",
    "retry_payload",
    "fallback_transport",
)

#: Subject history lengths (blueprint study population: 3-6 longitudinal
#: contexts per synthetic subject).
HISTORY_MIN = 3
HISTORY_MAX = 6

DEFAULT_N = 120

#: Revocation and dispatch instants (logical seconds). The revocation instant
#: is always strictly before the dispatch time so every record encodes a
#: post-revocation dispatch decision, the blueprint's observation target.
REVOCATION_AT = 100
DISPATCH_AT_MIN = 101
DISPATCH_AT_MAX = 400


def _assert_no_phi(payload: dict[str, Any]) -> None:
    """Fail closed on any payload field name resembling PHI/PII."""

    for key in payload:
        lowered = key.lower()
        if any(marker in lowered for marker in dk.PHI_FIELD_MARKERS):
            raise dk.DatasetError("PHI_FIELD_PRESENT", f"field {key!r} looks like PHI/PII")


def revocation_payload(seed: int, family: str, idx: int) -> dict[str, Any]:
    """POPETS per-family revocation/dispatch payload, pure function of inputs.

    Deterministic integer arithmetic only — no RNG objects, no clock, no dict
    iteration order dependence — so the same inputs always yield the same
    payload across runs and Python versions. Encodes the family as the
    ground-truth signal for downstream oracle/baseline code while staying
    PHI-free (structural purpose/cache/lineage placeholders only).
    """

    if family not in POPETS_FAMILIES:
        raise dk.DatasetError(
            "UNKNOWN_POPETS_FAMILY", f"{family!r} is not a POPETS family in {POPETS_FAMILIES}"
        )
    determinant = (seed * 7919 + idx * 104729) % 100003
    purpose = PURPOSES[(determinant // 3) % len(PURPOSES)]
    # Cross-purpose reuse must be an actual confusion: the cache was built for
    # one purpose and served for a different one, so the requested purpose is
    # forced off the cached purpose (POPETS-CASE-05).
    shift = 1 + (determinant // 11) % (len(PURPOSES) - 1)
    requested_purpose = (
        PURPOSES[(PURPOSES.index(purpose) + shift) % len(PURPOSES)]
        if family == "cross_purpose"
        else PURPOSES[(determinant // 11) % len(PURPOSES)]
    )
    history_length = HISTORY_MIN + (determinant // 13) % (HISTORY_MAX - HISTORY_MIN + 1)
    dispatch_at = DISPATCH_AT_MIN + (determinant // 17) % (DISPATCH_AT_MAX - DISPATCH_AT_MIN + 1)
    is_fresh = family == "fresh"
    # ``fresh`` records are served directly from source (no cache); every
    # revocation/cache family draws a non-trivial cache mode. Cache mode
    # "none" is reserved for fresh dispatches, so the dataset still sweeps
    # all four modes across families.
    cache_mode = (
        "none" if is_fresh else CACHE_MODES[1 + (determinant // 23) % (len(CACHE_MODES) - 1)]
    )
    payload: dict[str, Any] = {
        "revocation_payload_version": REVOCATION_PAYLOAD_VERSION,
        "scenario_family": family,
        "revocation_at": REVOCATION_AT,
        "dispatch_at": dispatch_at,
        "dispatch_after_revocation": dispatch_at > REVOCATION_AT,
        "purpose": purpose,
        "requested_purpose": requested_purpose,
        "cache_mode": cache_mode,
        "lineage_paths": []
        if is_fresh
        else [LINEAGE_PATHS[(determinant // 29) % len(LINEAGE_PATHS)]],
        "lineage_gap": family == "transitive_gap",
        "subject_history_length": history_length,
        "synthetic_only": True,
    }
    _assert_no_phi(payload)
    return payload


def _augment(dataset: dk.Dataset, seed: int) -> dk.Dataset:
    """Attach the POPETS revocation/dispatch payload to every kernel record."""

    records = tuple(
        dataclasses.replace(
            record,
            payload={
                **record.payload,
                **revocation_payload(seed, record.family, int(record.payload["sequence"])),
            },
        )
        for record in dataset.records
    )
    inventory = {
        **dataset.inventory,
        "revocation_payload_version": REVOCATION_PAYLOAD_VERSION,
        "generate_dataset_version": GENERATE_DATASET_VERSION,
    }
    return dataclasses.replace(dataset, records=records, inventory=inventory)


def generate(seed: int, split: str | None = None, n: int = DEFAULT_N) -> dk.Dataset:
    """Generate the deterministic POPETS dataset via the shared kernel.

    ``split=None`` returns the full buffered dataset (inventory covers all
    ``n`` records regardless of the filter, so the kernel content hash stays
    split-independent). ``split`` in ``train``/``dev``/``test`` filters the
    records to that split.
    """

    base = dk.generate(VENUE, seed=seed, n=n, split=split)
    return _augment(base, seed)


def validate_dataset(dataset: dk.Dataset) -> None:
    """Fail closed on degenerate family frequencies or split leakage."""

    n = int(dataset.inventory["total"])
    dk.assert_valid_frequencies(dataset)
    dk.assert_no_leakage({s: generate(seed=dataset.seed, split=s, n=n) for s in dk.SPLITS})


def write_dataset(outdir: str | Path, seed: int, n: int = DEFAULT_N) -> dict[str, Any]:
    """Build, validate, and persist one dataset artifact directory.

    Writes ``dataset.jsonl`` and ``inventory.json`` under ``outdir`` only after
    the fail-closed kernel validators pass. Returns a JSON-serializable
    manifest (paths, record counts, SHA256 of the JSONL file and the kernel
    content hash). Raises ``DatasetError`` on any kernel refusal; I/O errors
    propagate untouched.
    """

    dataset = generate(seed=seed, split=None, n=n)
    validate_dataset(dataset)
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    jsonl_text = dataset.to_jsonl()
    jsonl_sha256 = hashlib.sha256(jsonl_text.encode("utf-8")).hexdigest()
    manifest: dict[str, Any] = {
        "schema_version": "clara.venue2027.popets.dataset.v1",
        "venue": VENUE,
        "seed": seed,
        "n": n,
        "records": len(dataset.records),
        "generator_version": GENERATE_DATASET_VERSION,
        "dataset_kernel_version": dk.DATASET_KERNEL_VERSION,
        "revocation_payload_version": REVOCATION_PAYLOAD_VERSION,
        "unit_prefix": dk.VENUE_UNIT_PREFIX[VENUE],
        "splits": list(dk.SPLITS),
        "families": list(POPETS_FAMILIES),
        "purposes": list(PURPOSES),
        "cache_modes": list(CACHE_MODES),
        "lineage_paths": list(LINEAGE_PATHS),
        "revocation_at": REVOCATION_AT,
        "dispatch_at_range": [DISPATCH_AT_MIN, DISPATCH_AT_MAX],
        "subject_history_length_range": [HISTORY_MIN, HISTORY_MAX],
        "inventory": dataset.inventory,
        "content_sha256": dataset.content_sha256,
        "jsonl_sha256": jsonl_sha256,
        "synthetic_only": True,
        "phi_fields": [],
    }
    (out / "dataset.jsonl").write_text(jsonl_text, encoding="utf-8")
    (out / "inventory.json").write_text(
        json.dumps(dataset.inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="POPETS 2027 synthetic dataset builder")
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--seed", type=int, default=2027)
    parser.add_argument("--n", type=int, default=DEFAULT_N)
    args = parser.parse_args(argv)
    manifest = write_dataset(args.outdir, seed=args.seed, n=args.n)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CACHE_MODES",
    "DEFAULT_N",
    "GENERATE_DATASET_VERSION",
    "LINEAGE_PATHS",
    "POPETS_FAMILIES",
    "PURPOSES",
    "REVOCATION_PAYLOAD_VERSION",
    "VENUE",
    "generate",
    "revocation_payload",
    "validate_dataset",
    "write_dataset",
]
