"""Fail-closed validation for the frozen standards-composed comparator."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REQUIRED_FILES = (
    "engine.py",
    "METHOD_CARD.md",
    "SOURCE_MAPPING.md",
    "DEVIATIONS.md",
    "capabilities.json",
)


def validate_manifest(root: Path | None = None) -> dict[str, object]:
    comparator_root = root or Path(__file__).resolve().parent
    manifest_path = comparator_root / "comparator_manifest.json"
    if not manifest_path.is_file():
        raise ValueError("comparator_manifest_missing")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("comparator_manifest_not_object")
    if (
        payload.get("schema_version") != "standards-composed-manifest.v1"
        or payload.get("artifact_status") != "FROZEN_MECHANISM_CONTRACT"
        or payload.get("direct_product_fidelity_claim_allowed") is not False
    ):
        raise ValueError("comparator_manifest_contract_invalid")
    hashes = payload.get("files_sha256")
    if not isinstance(hashes, dict) or set(hashes) != set(REQUIRED_FILES):
        raise ValueError("comparator_manifest_file_set_invalid")
    for filename in REQUIRED_FILES:
        candidate = comparator_root / filename
        if not candidate.is_file():
            raise ValueError(f"comparator_file_missing:{filename}")
        expected = hashes.get(filename)
        observed = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if not isinstance(expected, str) or expected != observed:
            raise ValueError(f"comparator_file_digest_mismatch:{filename}")
    return payload


if __name__ == "__main__":
    validate_manifest()
