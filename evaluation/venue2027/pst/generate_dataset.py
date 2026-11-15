"""PST venue2027 deterministic dataset generator (task PST-dataset, phase P02).

Purpose
-------
Thin venue adapter over the shared deterministic dataset kernel
(``evaluation/venue2027/_shared/dataset_kernel.py``) for the PST 2027
"ReceiptMin" study (``research/venue2027/VENUES/pst/RESEARCH_BLUEPRINT.md``,
task contract ``research/venue2027/VENUES/pst/TASKS/PST-dataset.md``). It
produces synthetic, PHI-free audit-receipt records across the four registered
PST scenario families (``full_evidence``, ``minimized_omission``,
``receipt_anchored``, ``linkability_leak``), each enriched with the
PST-specific purpose-bound-minimization payload — audit retention mode,
omitted field count, receipt presence and the ex-ante forensic query set id —
derived deterministically from the kernel payload so the same
``(venue, seed, split, n)`` always yields byte-identical content. No real
patient data, no clinical payload, no live provider, no hidden clock or
randomness beyond the seed.

Allowed input
-------------
``generate(seed, split, n)`` with a positive ``n`` and ``split`` in
``{"all", "train", "dev", "test"}`` (``"all"`` returns every split; the kernel
inventory always describes the full unfiltered dataset, so the content hash is
split-independent by construction). ``write_dataset(outdir, seed, n)``
materializes ``records.jsonl``, ``inventory.json`` and ``manifest.json`` into
``outdir`` and refuses degenerate family frequencies and split leakage before
anything reaches disk.

Failure semantics
-----------------
Every error is a ``dataset_kernel.DatasetError`` carrying a stable reason code
(``UNKNOWN_VENUE``, ``INVALID_N``, ``INVALID_SPLIT_RATIOS``, ``UNKNOWN_SPLIT``,
``SPLIT_LEAKAGE``, ``INVALID_FAMILY_FREQUENCY``, ``UNKNOWN_PST_FAMILY``,
``PHI_FIELD_PRESENT``). The adapter never silently produces a leaky split, a
degenerate family distribution or a PHI-named field.

Version
-------
``DATASET_GENERATOR_VERSION = "1.0.0"``
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from evaluation.venue2027._shared import dataset_kernel as _kernel

DATASET_GENERATOR_VERSION = "1.0.0"
VENUE = "pst"
DATASET_SCHEMA_VERSION = "clara.venue2027.pst.dataset.v1"

DatasetError = _kernel.DatasetError

#: Ex-ante frozen forensic query set identifiers (RQ1 method architecture:
#: "Define forensic query set ex ante"). The id pinned per record declares
#: which query class the retained evidence must answer; the set itself carries
#: no clinical content.
QUERY_SETS: tuple[str, ...] = ("QS-forensic-bounded", "QS-retention-decay", "QS-linkage-bound")

#: Retention modes of the audited store (RQ3 retention epochs). ``full`` keeps
#: every field until the deadline, ``selective`` decays declared content
#: fields while commitment and epoch proofs persist, ``hash_only`` retains
#: digests alone.
RETENTION_MODES: tuple[str, ...] = ("full", "selective", "hash_only")

#: Synthetic field vocabulary of the minimized receipt. Omitted counts always
#: refer to positions in this tuple; names are structural, never clinical.
RECEIPT_FIELDS: tuple[str, ...] = (
    "commitment_digest",
    "purpose_tag",
    "consent_epoch",
    "policy_epoch",
    "witness_id",
    "retention_mode",
)

#: How many mandatory receipt fields each family drops. The ground-truth
#: signal: ``full_evidence`` drops nothing (utility upper bound), the
#: minimization families drop the load-bearing tail, ``linkability_leak``
#: keeps every field but its purpose tag is the disclosure surface
#: (PST-CASE-06), so nothing is omitted yet the record stays leaky.
_FAMILY_OMITTED_FIELDS: Mapping[str, int] = {
    "full_evidence": 0,
    "minimized_omission": 1,
    "receipt_anchored": 2,
    "linkability_leak": 0,
}

_FAMILY_RECEIPT_PRESENT: Mapping[str, bool] = {
    "full_evidence": True,
    "minimized_omission": True,
    "receipt_anchored": True,
    "linkability_leak": True,
}


def _assert_no_phi(payload: Mapping[str, Any]) -> None:
    """Fail closed on any payload field name resembling PHI/PII."""

    for key in payload:
        lowered = key.lower()
        if any(marker in lowered for marker in _kernel.PHI_FIELD_MARKERS):
            raise DatasetError("PHI_FIELD_PRESENT", f"field {key!r} looks like PHI/PII")


def _pst_enrichment(family: str, base_payload: Mapping[str, Any]) -> dict[str, Any]:
    """Derive the PST-specific payload fields deterministically.

    All entropy comes from the kernel payload (``determinant`` x ``sequence``)
    via integer modular arithmetic — no ``random`` module, no clock, no
    environment reads — so the same kernel record always enriches to the same
    PST record. Fails closed with ``UNKNOWN_PST_FAMILY`` on an unregistered
    family and ``PHI_FIELD_PRESENT`` if a field name would ever carry a
    PHI/PII marker.
    """

    if family not in _FAMILY_OMITTED_FIELDS:
        raise DatasetError("UNKNOWN_PST_FAMILY", f"family {family!r} has no PST profile")
    determinant = int(base_payload["determinant"])
    sequence = int(base_payload["sequence"])
    omitted_count = _FAMILY_OMITTED_FIELDS[family]
    # Omit the *tail* of the mandatory field set: the committer drops the
    # fields that would later convict it (model/policy epoch analogues),
    # keeping plausible filler — exactly the PST-CASE-05 adversarial shape.
    omitted_fields = list(RECEIPT_FIELDS[len(RECEIPT_FIELDS) - omitted_count :])
    payload: dict[str, Any] = {
        "audit_retention_mode": RETENTION_MODES[determinant % len(RETENTION_MODES)],
        "retention_epoch": determinant % 4,
        "omitted_field_count": omitted_count,
        "omitted_fields": omitted_fields,
        "receipt_present": _FAMILY_RECEIPT_PRESENT[family],
        "query_set_id": QUERY_SETS[(determinant // 7 + sequence) % len(QUERY_SETS)],
        "purpose_tag": f"purpose-{determinant % 5}",
    }
    _assert_no_phi(payload)
    return payload


def generate(seed: int, split: str | None, n: int) -> _kernel.Dataset:
    """Generate the PST dataset for ``(seed, split, n)`` via the shared kernel.

    Delegates family assignment, split partitioning, leakage discipline and the
    content hash to ``dataset_kernel.generate('pst', ...)``; only the
    PST-specific payload enrichment happens locally. The returned
    ``Dataset.content_sha256`` equals the un-enriched kernel hash for the same
    inputs (the digest covers unit identity, family and split, not payload
    bytes), keeping cross-venue comparability intact.
    """

    dataset = _kernel.generate(VENUE, seed, n, split=split)
    enriched = tuple(
        dataclasses.replace(
            record,
            payload={**record.payload, **_pst_enrichment(record.family, record.payload)},
        )
        for record in dataset.records
    )
    return dataclasses.replace(dataset, records=enriched)


def validate_dataset(dataset: _kernel.Dataset) -> None:
    """Fail closed on degenerate family frequencies or split leakage."""

    n = int(dataset.inventory["total"])
    _kernel.assert_valid_frequencies(dataset)
    _kernel.assert_no_leakage(
        {s: generate(seed=dataset.seed, split=s, n=n) for s in _kernel.SPLITS}
    )


def write_dataset(outdir: str | Path, seed: int, n: int) -> dict[str, Any]:
    """Build, validate, and persist one dataset artifact directory.

    Writes ``records.jsonl``, ``inventory.json`` and ``manifest.json`` under
    ``outdir`` only after the fail-closed validators pass; returns the
    manifest (path-free, so identical inputs yield byte-identical manifests).
    """

    dataset = generate(seed=seed, split=None, n=n)
    validate_dataset(dataset)
    records_jsonl = dataset.to_jsonl()
    manifest: dict[str, Any] = {
        "schema_version": DATASET_SCHEMA_VERSION,
        "venue": VENUE,
        "seed": seed,
        "n": n,
        "records": len(dataset.records),
        "generator_version": DATASET_GENERATOR_VERSION,
        "dataset_kernel_version": _kernel.DATASET_KERNEL_VERSION,
        "unit_prefix": _kernel.VENUE_UNIT_PREFIX[VENUE],
        "splits": list(_kernel.SPLITS),
        "families": list(_kernel.VENUE_FAMILIES[VENUE]),
        "query_sets": list(QUERY_SETS),
        "retention_modes": list(RETENTION_MODES),
        "receipt_fields": list(RECEIPT_FIELDS),
        "inventory": dataset.inventory,
        "content_sha256": dataset.content_sha256,
        "records_sha256": hashlib.sha256(records_jsonl.encode("utf-8")).hexdigest(),
        "synthetic_only": True,
        "phi_fields": [],
    }
    out_path = Path(outdir)
    out_path.mkdir(parents=True, exist_ok=True)
    (out_path / "records.jsonl").write_text(records_jsonl, encoding="utf-8")
    (out_path / "inventory.json").write_text(
        json.dumps(dataset.inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_path / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PST 2027 synthetic dataset builder")
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--seed", type=int, default=2027)
    parser.add_argument("--n", type=int, default=120)
    args = parser.parse_args(argv)
    manifest = write_dataset(args.outdir, seed=args.seed, n=args.n)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
