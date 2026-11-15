"""AIME-dataset — synthetic dataset and split builder (Phase P02, venue ``aime``).

Purpose
-------
Deterministic synthetic dataset generator for the AIME 2027 study
"Counterfactual Clinical Workflow Safety under Changing Consent and Medication
Histories" (``research/venue2027/VENUES/aime/RESEARCH_BLUEPRINT.md``; scenario
matrix ``research/venue2027/VENUES/aime/CASE_MATRIX.md``; task contract
``research/venue2027/VENUES/aime/TASKS/AIME-dataset.md``). All record
construction, family assignment, split-by-independent-unit assignment, content
hashing, leakage detection and family-frequency validation are delegated to the
audited shared kernel :mod:`evaluation.venue2027._shared.dataset_kernel` — this
module never re-implements those invariants. On top of the kernel payload it
attaches the AIME-specific *longitudinal workflow payload* (medication state,
allergy state, consent revision, synthetic update family) that drives
RQ1-RQ3 counterfactual pairs, derived deterministically from
``(seed, family, unit index)`` with pure integer arithmetic — no clock, no RNG
object, no hash randomization, no live provider, no real PHI.

The five AIME update families come from the kernel registry
``VENUE_FAMILIES["aime"]`` and match the preregistered counterfactual pair
design (baseline ``stable_history`` plus mid-task context updates):
``stable_history`` (AIME-CASE-01/06 shape), ``consent_change``
(AIME-CASE-03), ``medication_withdrawal`` (AIME-CASE-02 analogue),
``allergy_update`` and ``reconciliation`` (AIME-CASE-04/05).

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
``UNKNOWN_AIME_FAMILY`` if a workflow payload is requested for a family outside
the AIME registry. Leaky splits and degenerate family frequencies are never
produced silently: :func:`write_dataset` runs the kernel validators on every
emitted dataset before persisting anything.

Version
-------
``GENERATE_DATASET_VERSION = "clara.aime.generate-dataset-v1"``. Output is
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

GENERATE_DATASET_VERSION = "clara.aime.generate-dataset-v1"
WORKFLOW_PAYLOAD_VERSION = "clara.aime.workflow-payload-v1"

VENUE = "aime"

#: AIME scenario families (kernel registry, CASE_MATRIX mapping).
AIME_FAMILIES: tuple[str, ...] = dk.VENUE_FAMILIES["aime"]

#: Synthetic medication vocabulary (structural placeholders, never real drugs).
MEDICATIONS: tuple[str, ...] = ("synthetic-med-alpha", "synthetic-med-beta", "synthetic-med-gamma")

#: Synthetic consent purposes (CASE_MATRIX ``purpose`` vocabulary).
PURPOSES: tuple[str, ...] = ("self_care", "care_summary", "medication_review")

#: Synthetic sources for the reconciliation family's conflicting observations.
OBSERVATION_SOURCES: tuple[str, ...] = ("synthetic-note-a", "synthetic-note-b")

#: Event kinds per update family (CASE_MATRIX timeline vocabulary).
_FAMILY_EVENT: dict[str, str] = {
    "stable_history": "UNRELATED_NOTE_EDIT",
    "consent_change": "CONSENT_REVOKED",
    "medication_withdrawal": "MEDICATION_WITHDRAWN",
    "allergy_update": "ALLERGY_REPORTED",
    "reconciliation": "CONFLICTING_OBSERVATION",
}

#: Update families that change the task-relevant context mid-task.
_HAZARD_FAMILIES: frozenset[str] = frozenset(
    {"consent_change", "medication_withdrawal", "allergy_update", "reconciliation"}
)

DEFAULT_N = 120


def _assert_no_phi(payload: dict[str, Any]) -> None:
    """Fail closed on any payload field name resembling PHI/PII."""

    for key in payload:
        lowered = key.lower()
        if any(marker in lowered for marker in dk.PHI_FIELD_MARKERS):
            raise dk.DatasetError("PHI_FIELD_PRESENT", f"field {key!r} looks like PHI/PII")


def workflow_payload(seed: int, family: str, idx: int) -> dict[str, Any]:
    """AIME per-family longitudinal workflow payload, pure function of inputs.

    Deterministic integer arithmetic only — no RNG objects, no clock, no dict
    iteration order dependence — so the same inputs always yield the same
    payload across runs and Python versions. Encodes the family as the
    ground-truth signal for downstream oracle/baseline code while staying
    PHI-free (structural medication/allergy/consent placeholders only).
    """

    if family not in _FAMILY_EVENT:
        raise dk.DatasetError(
            "UNKNOWN_AIME_FAMILY", f"{family!r} is not an AIME family in {AIME_FAMILIES}"
        )
    determinant = (seed * 7919 + idx * 104729) % 100003
    medication = MEDICATIONS[determinant % len(MEDICATIONS)]
    purpose = PURPOSES[(determinant // 3) % len(PURPOSES)]
    is_hazard = family in _HAZARD_FAMILIES
    payload: dict[str, Any] = {
        "workflow_payload_version": WORKFLOW_PAYLOAD_VERSION,
        "update_family": family,
        "event_kind": _FAMILY_EVENT[family],
        "active_medications": (
            [] if (is_hazard and family == "medication_withdrawal") else [medication]
        ),
        "withdrawn_medication": medication if family == "medication_withdrawal" else None,
        "allergies": [medication] if family == "allergy_update" else [],
        "consent_revision": ((determinant // 7) % 3) + 1 if family == "consent_change" else 0,
        "granted_purposes": [] if family == "consent_change" else [purpose],
        "revoked_purpose": purpose if family == "consent_change" else None,
        "conflicting_sources": list(OBSERVATION_SOURCES) if family == "reconciliation" else [],
        "logical_time": 1 if is_hazard else 0,
        "synthetic_only": True,
    }
    _assert_no_phi(payload)
    return payload


def _augment(dataset: dk.Dataset, seed: int) -> dk.Dataset:
    """Attach the AIME workflow payload to every kernel record."""

    records = tuple(
        dataclasses.replace(
            record,
            payload={
                **record.payload,
                **workflow_payload(seed, record.family, int(record.payload["sequence"])),
            },
        )
        for record in dataset.records
    )
    inventory = {
        **dataset.inventory,
        "workflow_payload_version": WORKFLOW_PAYLOAD_VERSION,
        "generate_dataset_version": GENERATE_DATASET_VERSION,
    }
    return dataclasses.replace(dataset, records=records, inventory=inventory)


def generate(seed: int, split: str | None = None, n: int = DEFAULT_N) -> dk.Dataset:
    """Generate the deterministic AIME dataset via the shared kernel.

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
        "schema_version": "clara.venue2027.aime.dataset.v1",
        "venue": VENUE,
        "seed": seed,
        "n": n,
        "records": len(dataset.records),
        "generator_version": GENERATE_DATASET_VERSION,
        "dataset_kernel_version": dk.DATASET_KERNEL_VERSION,
        "workflow_payload_version": WORKFLOW_PAYLOAD_VERSION,
        "unit_prefix": dk.VENUE_UNIT_PREFIX[VENUE],
        "splits": list(dk.SPLITS),
        "families": list(AIME_FAMILIES),
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
    parser = argparse.ArgumentParser(description="AIME 2027 synthetic dataset builder")
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
    "AIME_FAMILIES",
    "DEFAULT_N",
    "GENERATE_DATASET_VERSION",
    "MEDICATIONS",
    "OBSERVATION_SOURCES",
    "PURPOSES",
    "VENUE",
    "WORKFLOW_PAYLOAD_VERSION",
    "generate",
    "validate_dataset",
    "workflow_payload",
    "write_dataset",
]
