"""Shared frozen-manifest verification without access to clinical data."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REQUIRED_FREEZE_FIELDS = frozenset({
    "protocol_version", "freeze_id", "frozen_at", "code_revision", "cohort_manifest_sha256",
    "annotation_guide_sha256", "domain_policy_manifest_sha256", "comparator_version",
    "task_manifest_sha256", "model_manifest_sha256", "statistics_plan_sha256",
})


class FreezeError(ValueError):
    """Raised when a proposed headline evaluation is not frozen."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_frozen_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FreezeError("invalid_json_manifest") from exc
    if not isinstance(value, dict):
        raise FreezeError("manifest_must_be_object")
    return value


def verify_freeze(path: Path) -> dict[str, object]:
    manifest = load_frozen_json(path)
    missing = REQUIRED_FREEZE_FIELDS.difference(manifest)
    if missing:
        raise FreezeError("missing_freeze_fields:" + ",".join(sorted(missing)))
    if manifest.get("status") != "frozen":
        raise FreezeError("freeze_status_not_frozen")
    if manifest.get("independent_curator_attestation") is not True:
        raise FreezeError("independent_curator_attestation_missing")
    return manifest
