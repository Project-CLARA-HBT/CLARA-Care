"""ACNS-dataset — synthetic dataset and split builder (venue acns, Phase P02).

Purpose
-------
Task ACNS-dataset for the ACNS 2027 SoK "Evidence Boundaries of Attestation in
Tool-Using AI Systems". Provides :func:`generate` — the manifest signature
``generate(seed:int, split:str, n:int) -> Dataset`` — plus :func:`write_dataset`
for producing the CSV/JSONL artifact bundle and split inventory required by the
pass gate. All record construction is delegated to the audited shared kernel
``evaluation.venue2027._shared.dataset_kernel`` (SH dataset kernel, v1.0.0);
this module only adds the ACNS-specific evidence-claim payload and the artifact
writer. Every family is deterministic, PHI-free and synthetic-only.

ACNS-specific payload (deterministic from ``(seed, idx, family)``)
-----------------------------------------------------------------
- ``claimed_attestation_level`` — claimed rung of the evidence-to-claim lattice
  (``L0-ASSUMED`` .. ``L4-COMMITTED``, threat model §1.2), consistent with the
  kernel family's ground-truth signal.
- ``receipt_binding_present`` — whether a provider receipt is actually bound to
  the claim (False exactly for the families whose boundary gap is a missing or
  transplanted binding).
- ``evidence_gap_code`` — a stable code from the pre-registered register
  G1–G9 (threat model §6) or ``NONE`` for the fully bound family.
- ``source_type`` — the synthetic provenance of the claimed evidence
  (``provider_receipt`` | ``transport_ack`` | ``attested_execution`` |
  ``timestamp_only`` | ``undisclosed``).

Allowed input
-------------
``seed`` non-negative int, ``split`` one of ``train|dev|test|all``, ``n``
positive int. Invalid input fails closed with a stable ``DatasetError``
reason code from the kernel (never a silent acceptance).

Failure semantics
-----------------
Propagates kernel ``DatasetError`` codes (``UNKNOWN_VENUE``, ``INVALID_N``,
``UNKNOWN_SPLIT``, ``PHI_FIELD_PRESENT``); :func:`write_dataset` additionally
raises ``DatasetError(OVERWRITE_REFUSED)`` if the target manifest exists unless
``overwrite=True`` is passed explicitly.

Version
-------
``ACNS_DATASET_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any

from evaluation.venue2027._shared.dataset_kernel import (
    DATASET_KERNEL_VERSION,
    SPLITS,
    VENUE_FAMILIES,
    Dataset,
    DatasetError,
    _check_no_phi,
)
from evaluation.venue2027._shared.dataset_kernel import (
    generate as _kernel_generate,
)

ACNS_DATASET_VERSION = "1.0.0"
ACNS_VENUE = "acns"
DATASET_LABEL = "synthetic-acns-2027"

#: Evidence-to-claim lattice (threat model §1.2); mirrors the SoK taxonomy.
ACNS_LATTICE_LEVELS: tuple[str, ...] = (
    "L0-ASSUMED",
    "L1-ASSEMBLED",
    "L2-ACKNOWLEDGED",
    "L3-EXECUTED",
    "L4-COMMITTED",
)

#: Pre-registered evidence-boundary gap register (threat model §6, G1–G9).
ACNS_GAP_CODES: frozenset[str] = frozenset(
    {
        "G1_TRANSPORT_ACK_AS_PROCESSING",
        "G2_RECEIPT_AS_EXECUTION",
        "G3_EXECUTION_AS_CONSUMPTION",
        "G4_SIGNATURE_AS_CONTEXT",
        "G5_MINT_TIME_AS_RELY_TIME",
        "G6_TIMESTAMP_AS_ORDERING",
        "G7_LEVEL_IMPLICIT_UPGRADE",
        "G8_AUTHORITY_SCOPE_CROSSING",
        "G9_CLAIM_WITHOUT_DISCLOSED_EVIDENCE",
    }
)

#: Per-family ground truth: (claimed lattice level, receipt bound?, gap code,
#: source type of the disclosed evidence). The kernel family names
# (VENUE_FAMILIES["acns"]) are: bound_evidence, attestation_downgrade,
# unbound_claim, replayed_receipt.
_ACNS_FAMILY_PAYLOAD: dict[str, dict[str, Any]] = {
    "bound_evidence": {
        "claimed_attestation_level": "L3-EXECUTED",
        "receipt_binding_present": True,
        "evidence_gap_code": "NONE",
        "source_type": "attested_execution",
    },
    "attestation_downgrade": {
        "claimed_attestation_level": "L3-EXECUTED",
        "receipt_binding_present": True,
        "evidence_gap_code": "G2_RECEIPT_AS_EXECUTION",
        "source_type": "provider_receipt",
    },
    "unbound_claim": {
        "claimed_attestation_level": "L2-ACKNOWLEDGED",
        "receipt_binding_present": False,
        "evidence_gap_code": "G9_CLAIM_WITHOUT_DISCLOSED_EVIDENCE",
        "source_type": "undisclosed",
    },
    "replayed_receipt": {
        "claimed_attestation_level": "L3-EXECUTED",
        "receipt_binding_present": False,
        "evidence_gap_code": "G4_SIGNATURE_AS_CONTEXT",
        "source_type": "transport_ack",
    },
}

#: Split filter token accepted by :func:`generate` in addition to SPLITS.
ALL_SPLITS_TOKEN = "all"


def _acns_payload(family: str, seed: int, idx: int) -> dict[str, Any]:
    """Return the deterministic ACNS evidence-claim payload for one unit.

    Pure arithmetic on ``(seed, idx)`` — no clock, no randomness, no I/O — so
    the same inputs always regenerate byte-identical payloads.
    """

    base = _ACNS_FAMILY_PAYLOAD[family]
    determinant = (seed * 7919 + idx * 104729) % 100003
    # Deterministic claim-dimension rotation; dispatch never claims L3+.
    dimensions = ("dispatch", "receipt", "execution", "consumption")
    dimension = dimensions[idx % len(dimensions)]
    if dimension == "dispatch" and base["claimed_attestation_level"] in {
        "L3-EXECUTED",
        "L4-COMMITTED",
    }:
        claimed = "L1-ASSEMBLED"
    else:
        claimed = str(base["claimed_attestation_level"])
    return {
        "dataset": DATASET_LABEL,
        "family": family,
        "synthetic": True,
        "determinant": determinant,
        "sequence": idx,
        "claim_dimension": dimension,
        "claimed_attestation_level": claimed,
        "receipt_binding_present": bool(base["receipt_binding_present"]),
        "evidence_gap_code": str(base["evidence_gap_code"]),
        "source_type": str(base["source_type"]),
        "receipt_digest": f"sha256:{determinant:016x}" + "0" * 48,
        "schedule_checked_at_rely_time": base["receipt_binding_present"],
    }


def generate(seed: int, split: str, n: int) -> Dataset:
    """Generate the ACNS synthetic dataset, delegating to the shared kernel.

    ``split`` selects one of ``train|dev|test`` (records filtered to that
    split) or ``all`` (the full buffered dataset). The kernel builds the full
    spec either way, so ``content_sha256`` is split-independent.
    """

    if split != ALL_SPLITS_TOKEN and split not in SPLITS:
        raise DatasetError(
            "UNKNOWN_SPLIT",
            f"{split!r} is not one of {SPLITS + (ALL_SPLITS_TOKEN,)}",
        )
    kernel_split = None if split == ALL_SPLITS_TOKEN else split
    # Always build the full buffered dataset (split-independent hash, matching
    # the kernel contract), then filter locally for split selection.
    dataset = _kernel_generate(ACNS_VENUE, seed=seed, n=n, split=None)
    # Re-wrap with the venue-specific payload; every payload is re-checked
    # against the kernel PHI-field rule so a future ACNS field cannot leak a
    # PHI-shaped key past the kernel's own base-payload validation.
    records = []
    for r in dataset.records:
        payload = _acns_payload(r.family, seed, int(r.unit_id.rsplit("-", 1)[1]))
        _check_no_phi(payload)
        records.append(dataclasses.replace(r, payload=payload))
    records_tuple = tuple(records)
    if kernel_split is not None:
        records_tuple = tuple(r for r in records_tuple if r.split == kernel_split)
    # Inventory and content hash are computed on the FULL buffered record set
    # so they are independent of the requested split filter (kernel contract).
    inventory = dict(dataset.inventory)
    inventory["dataset_label"] = DATASET_LABEL
    inventory["generator_version"] = ACNS_DATASET_VERSION
    inventory["dataset_kernel_version"] = DATASET_KERNEL_VERSION
    inventory["lattice_levels"] = list(ACNS_LATTICE_LEVELS)
    inventory["gap_codes"] = sorted(ACNS_GAP_CODES)
    inventory["by_claimed_attestation_level"] = _count_by(records, "claimed_attestation_level")
    inventory["by_evidence_gap_code"] = _count_by(records, "evidence_gap_code")
    inventory["by_source_type"] = _count_by(records, "source_type")
    content_sha256 = hashlib.sha256(
        json.dumps(
            {
                "venue": ACNS_VENUE,
                "seed": seed,
                "version": ACNS_DATASET_VERSION,
                "kernel_version": DATASET_KERNEL_VERSION,
                "records": [
                    r.unit_id + ":" + r.family + ":" + r.split for r in records
                ],
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return Dataset(
        venue=ACNS_VENUE,
        seed=seed,
        generator_version=ACNS_DATASET_VERSION,
        records=records_tuple,
        inventory=inventory,
        content_sha256=content_sha256,
    )


def _count_by(records: tuple[Any, ...], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        value = str(record.payload[key])
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def write_dataset(outdir: str | Path, seed: int, n: int, *, overwrite: bool = False) -> dict[str, Any]:
    """Write the dataset bundle for ``(seed, n)`` into ``outdir``.

    Produces: ``records.jsonl`` (sorted, stable field order), ``records.csv``
    (flat column projection), ``inventory.json`` (cardinality inventory and
    content hash) and ``manifest.json`` (version pinning for mechanical
    traceability). Refuses to overwrite an existing manifest unless
    ``overwrite=True``. Returns the written manifest dict.
    """

    out = Path(outdir)
    manifest_path = out / "manifest.json"
    if manifest_path.exists() and not overwrite:
        raise DatasetError(
            "OVERWRITE_REFUSED",
            f"{manifest_path} exists; pass overwrite=True to regenerate",
        )
    dataset = generate(seed, ALL_SPLITS_TOKEN, n)
    out.mkdir(parents=True, exist_ok=True)

    (out / "records.jsonl").write_text(dataset.to_jsonl(), encoding="utf-8")

    columns = (
        "unit_id",
        "family",
        "split",
        "claim_dimension",
        "claimed_attestation_level",
        "receipt_binding_present",
        "evidence_gap_code",
        "source_type",
        "determinant",
        "sequence",
    )
    csv_lines = [",".join(columns)]
    for record in dataset.records:
        values: list[str] = [record.unit_id, record.family, record.split]
        values += [str(record.payload[column]) for column in columns[3:]]
        csv_lines.append(",".join(values))
    (out / "records.csv").write_text("\n".join(csv_lines) + "\n", encoding="utf-8")

    (out / "inventory.json").write_text(
        json.dumps({"content_sha256": dataset.content_sha256, **dataset.inventory}, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest: dict[str, Any] = {
        "dataset_label": DATASET_LABEL,
        "venue": ACNS_VENUE,
        "seed": seed,
        "n": n,
        "generator_version": ACNS_DATASET_VERSION,
        "dataset_kernel_version": DATASET_KERNEL_VERSION,
        "content_sha256": dataset.content_sha256,
        "files": {
            name: _sha256_file(out / name) for name in ("records.jsonl", "records.csv", "inventory.json")
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "ACNS_DATASET_VERSION",
    "ACNS_GAP_CODES",
    "ACNS_LATTICE_LEVELS",
    "ACNS_VENUE",
    "DATASET_LABEL",
    "Dataset",
    "DatasetError",
    "VENUE_FAMILIES",
    "generate",
    "write_dataset",
]
