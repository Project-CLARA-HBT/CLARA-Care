"""DIMVA venue2027 deterministic dataset generator (task DIMVA-dataset, phase P02).

Purpose
-------
Thin venue adapter over the shared deterministic dataset kernel
(``evaluation/venue2027/_shared/dataset_kernel.py``) for the DIMVA 2027
"GovernanceTrace" study (``research/venue2027/VENUES/dimva/RESEARCH_BLUEPRINT.md``).
It produces synthetic, PHI-free minimal agent-session records across the four
registered DIMVA scenario families (``benign_session``, ``low_and_slow``,
``cross_tool_obfuscation``, ``burst_probe``), each enriched with the
DIMVA-specific operational payload — campaign length, tools used, denial rate
and inter-arrival delay — derived deterministically from the kernel payload so
the same ``(seed, split, n)`` always yields byte-identical content. No raw
patient data, no rejection reason codes on the primary leak-safe surface, no
live provider, no hidden clock or randomness.

Allowed input
-------------
``generate(seed, split, n)`` with a positive ``n`` and ``split`` in
``{"train", "dev", "test", None}`` (``None`` returns every split; the kernel
inventory always describes the full unfiltered dataset, so the content hash is
split-independent by construction).
``write_dataset(outdir, seed, n)`` materializes ``dataset.jsonl`` plus a
``manifest.json`` (inventory, hashes, generator versions) into ``outdir`` and
refuses degenerate family frequencies before anything reaches disk.

Failure semantics
-----------------
Every error is a ``dataset_kernel.DatasetError`` carrying a stable reason code
(``UNKNOWN_VENUE``, ``INVALID_N``, ``INVALID_SPLIT_RATIOS``, ``UNKNOWN_SPLIT``,
``SPLIT_LEAKAGE``, ``INVALID_FAMILY_FREQUENCY``, ``UNKNOWN_DIMVA_FAMILY``,
``PHI_FIELD_PRESENT``). The adapter never silently produces a leaky split, a
degenerate family distribution or a PHI-named field.

Version
-------
``DATASET_GENERATOR_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib
from collections.abc import Mapping
from typing import Any

from evaluation.venue2027._shared import dataset_kernel as _kernel

DATASET_GENERATOR_VERSION = "1.0.0"

VENUE = "dimva"

DatasetError = _kernel.DatasetError

#: Synthetic tool codes rotated into per-campaign ``tools_used`` sets. Codes
#: carry no semantic content beyond distinguishing tools within a campaign.
_TOOL_CODES: tuple[str, ...] = tuple(f"T{i:02d}" for i in range(1, 13))


@dataclasses.dataclass(frozen=True)
class FamilyProfile:
    """Deterministic sampling ranges for one DIMVA scenario family.

    Each range is an inclusive ``[lo, hi]`` interval; the concrete value is
    derived from the kernel ``determinant`` entropy so the profile itself
    stays seed-independent and auditable.
    """

    campaign_length_events: tuple[int, int]
    tools_used_count: tuple[int, int]
    denial_rate: tuple[float, float]
    inter_arrival_delay_seconds: tuple[int, int]


#: Per-family operational ranges. Benign sessions stay short with few tools,
#: low denial rates and steady pacing; ``low_and_slow`` stretches the horizon
#: with wide inter-arrival gaps; ``cross_tool_obfuscation`` spreads denials
#: across many tools; ``burst_probe`` compresses the inter-arrival delay.
FAMILY_PROFILES: Mapping[str, FamilyProfile] = {
    "benign_session": FamilyProfile(
        campaign_length_events=(3, 8),
        tools_used_count=(1, 3),
        denial_rate=(0.0, 0.2),
        inter_arrival_delay_seconds=(30, 600),
    ),
    "low_and_slow": FamilyProfile(
        campaign_length_events=(20, 60),
        tools_used_count=(1, 3),
        denial_rate=(0.3, 0.6),
        inter_arrival_delay_seconds=(3600, 21600),
    ),
    "cross_tool_obfuscation": FamilyProfile(
        campaign_length_events=(15, 40),
        tools_used_count=(4, 8),
        denial_rate=(0.4, 0.7),
        inter_arrival_delay_seconds=(600, 3600),
    ),
    "burst_probe": FamilyProfile(
        campaign_length_events=(10, 30),
        tools_used_count=(2, 5),
        denial_rate=(0.6, 0.9),
        inter_arrival_delay_seconds=(1, 60),
    ),
}


def _dimva_enrichment(family: str, base_payload: Mapping[str, Any]) -> dict[str, Any]:
    """Derive the DIMVA-specific payload fields deterministically.

    All entropy comes from the kernel payload (``determinant`` x ``sequence``)
    via integer modular arithmetic — no ``random`` module, no clock, no
    environment reads — so the same kernel record always enriches to the same
    DIMVA record. Fails closed with ``UNKNOWN_DIMVA_FAMILY`` on an
    unregistered family and ``PHI_FIELD_PRESENT`` if a field name would ever
    carry a PHI/PII marker.
    """

    profile = FAMILY_PROFILES.get(family)
    if profile is None:
        raise DatasetError("UNKNOWN_DIMVA_FAMILY", f"family {family!r} has no DIMVA profile")
    determinant = int(base_payload["determinant"])
    length_lo, length_hi = profile.campaign_length_events
    tool_lo, tool_hi = profile.tools_used_count
    denial_lo, denial_hi = profile.denial_rate
    gap_lo, gap_hi = profile.inter_arrival_delay_seconds
    campaign_length = length_lo + determinant % (length_hi - length_lo + 1)
    tool_count = tool_lo + (determinant // 7) % (tool_hi - tool_lo + 1)
    rotation = (determinant // 13) % len(_TOOL_CODES)
    tools_used = [_TOOL_CODES[(rotation + i) % len(_TOOL_CODES)] for i in range(tool_count)]
    denial_frac = ((determinant // 11) % 1001) / 1000.0
    denial_rate = round(denial_lo + denial_frac * (denial_hi - denial_lo), 4)
    inter_arrival = gap_lo + (determinant // 17) % (gap_hi - gap_lo + 1)
    payload: dict[str, Any] = {
        "campaign_length_events": campaign_length,
        "tools_used": tools_used,
        "denial_rate": denial_rate,
        "inter_arrival_delay_seconds": inter_arrival,
    }
    for key in payload:
        lowered = key.lower()
        if any(marker in lowered for marker in _kernel.PHI_FIELD_MARKERS):
            raise DatasetError("PHI_FIELD_PRESENT", f"field {key!r} looks like PHI/PII")
    return payload


def generate(seed: int, split: str | None, n: int) -> _kernel.Dataset:
    """Generate the DIMVA dataset for ``(seed, split, n)`` via the shared kernel.

    Delegates family assignment, split partitioning, leakage discipline and the
    content hash to ``dataset_kernel.generate('dimva', ...)``; only the
    DIMVA-specific payload enrichment happens locally. The returned
    ``Dataset.content_sha256`` equals the un-enriched kernel hash for the same
    inputs (the digest covers unit identity, family and split, not payload
    bytes), keeping cross-venue comparability intact.
    """

    dataset = _kernel.generate(VENUE, seed, n, split=split)
    enriched = tuple(
        dataclasses.replace(
            record,
            payload={**record.payload, **_dimva_enrichment(record.family, record.payload)},
        )
        for record in dataset.records
    )
    return dataclasses.replace(dataset, records=enriched)


def write_dataset(outdir: str | pathlib.Path, seed: int, n: int) -> dict[str, Any]:
    """Write the full-split DIMVA dataset to ``outdir`` and return the manifest.

    Emits ``dataset.jsonl`` (one JSON object per record, sorted keys) and
    ``manifest.json`` (versions, content hash, byte hash of the JSONL, split
    and family inventory). Fails closed — before creating any file — via
    ``assert_valid_frequencies`` when the requested ``n`` would leave a
    registered family unrepresented.
    """

    dataset = generate(seed, None, n)
    _kernel.assert_valid_frequencies(dataset)
    directory = pathlib.Path(outdir)
    directory.mkdir(parents=True, exist_ok=True)
    jsonl_bytes = dataset.to_jsonl().encode("utf-8")
    jsonl_path = directory / "dataset.jsonl"
    jsonl_path.write_bytes(jsonl_bytes)
    manifest: dict[str, Any] = {
        "schema_version": "clara.venue2027.dimva_dataset.v1",
        "venue": VENUE,
        "seed": seed,
        "n": n,
        "generator_version": DATASET_GENERATOR_VERSION,
        "dataset_kernel_version": _kernel.DATASET_KERNEL_VERSION,
        "content_sha256": dataset.content_sha256,
        "dataset_jsonl_sha256": hashlib.sha256(jsonl_bytes).hexdigest(),
        "total_records": dataset.inventory["total"],
        "splits": dataset.inventory["by_split"],
        "families": dataset.inventory["by_family"],
        "unit_id_prefix": _kernel.VENUE_UNIT_PREFIX[VENUE],
    }
    manifest_path = directory / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
