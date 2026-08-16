"""Fail-closed validation for CareGuard-VN external source manifests."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from evaluation.evidence_program.freeze import FreezeError

REQUIRED_ROLES = frozenset({
    "identity_frame", "terminology", "positive_ddi_reference", "regulatory_confirmation",
})
REQUIRED_FIELDS = frozenset({
    "schema_version", "status", "source_name", "independence_role", "source_url",
    "retrieved_at_utc", "version_or_release", "access_terms", "license",
    "redistribution_policy", "payload_sha256", "row_count", "record_hash_algorithm",
    "record_hash_inventory", "raw_retention_location",
})
_REDISTRIBUTION_POLICIES = frozenset({"raw_prohibited", "derived_only", "permitted"})
_RECORD_HASH_ALGORITHM = "sha256(canonical_record_json)"


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FreezeError("careguard_source_manifest_unreadable") from exc
    if not isinstance(value, dict):
        raise FreezeError("careguard_source_manifest_not_object")
    return value


def validate_source_manifest(path: Path) -> dict[str, Any]:
    """Validate one final acquired source; reject probes and unknown labels."""

    value = _load(path)
    if REQUIRED_FIELDS - value.keys():
        raise FreezeError("careguard_source_manifest_fields_missing")
    if value["schema_version"] != "careguard-vn.source-manifest.v1":
        raise FreezeError("careguard_source_manifest_schema_invalid")
    if value["status"] != "FROZEN_ACQUIRED":
        raise FreezeError("careguard_source_manifest_not_frozen_acquired")
    if value["independence_role"] not in REQUIRED_ROLES:
        raise FreezeError("careguard_source_manifest_role_invalid")
    if not isinstance(value["source_name"], str) or not value["source_name"].strip():
        raise FreezeError("careguard_source_manifest_name_invalid")
    if not isinstance(value["source_url"], str) or not value["source_url"].startswith("https://"):
        raise FreezeError("careguard_source_manifest_url_invalid")
    if not isinstance(value["retrieved_at_utc"], str):
        raise FreezeError("careguard_source_manifest_retrieved_at_invalid")
    try:
        retrieved_at = datetime.fromisoformat(value["retrieved_at_utc"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise FreezeError("careguard_source_manifest_retrieved_at_invalid") from exc
    if retrieved_at.tzinfo is None:
        raise FreezeError("careguard_source_manifest_retrieved_at_invalid")
    if not isinstance(value["version_or_release"], str) or not value["version_or_release"].strip():
        raise FreezeError("careguard_source_manifest_version_missing")
    if value["license"] in {"", "PENDING_REVIEW", None} or value["access_terms"] in {"", "PENDING_REVIEW", None}:
        raise FreezeError("careguard_source_manifest_terms_unresolved")
    if value["redistribution_policy"] not in _REDISTRIBUTION_POLICIES:
        raise FreezeError("careguard_source_manifest_redistribution_policy_invalid")
    if value["raw_retention_location"] in {"", "outside_git", None}:
        raise FreezeError("careguard_source_manifest_retention_unresolved")
    if not _is_sha256(value["payload_sha256"]):
        raise FreezeError("careguard_source_manifest_payload_hash_invalid")
    if not isinstance(value["row_count"], int) or value["row_count"] <= 0:
        raise FreezeError("careguard_source_manifest_row_count_invalid")
    if value["record_hash_algorithm"] != _RECORD_HASH_ALGORITHM:
        raise FreezeError("careguard_source_manifest_record_hash_algorithm_invalid")
    inventory = value["record_hash_inventory"]
    if not isinstance(inventory, list) or not inventory:
        raise FreezeError("careguard_source_manifest_inventory_missing")
    record_ids: set[str] = set()
    for item in inventory:
        if not isinstance(item, dict) or not item.get("source_record_id"):
            raise FreezeError("careguard_source_manifest_inventory_invalid")
        if not isinstance(item["source_record_id"], str) or item["source_record_id"] in record_ids:
            raise FreezeError("careguard_source_manifest_inventory_invalid")
        record_ids.add(item["source_record_id"])
        if not _is_sha256(item.get("source_record_hash")):
            raise FreezeError("careguard_source_manifest_inventory_hash_invalid")
    if len(inventory) != value["row_count"]:
        raise FreezeError("careguard_source_manifest_inventory_count_mismatch")
    return value


def validate_source_set(paths: list[Path]) -> list[dict[str, Any]]:
    """Require exactly one independently acquired source for every study role."""

    manifests = [validate_source_manifest(path) for path in paths]
    roles = [str(item["independence_role"]) for item in manifests]
    if set(roles) != REQUIRED_ROLES or len(roles) != len(set(roles)):
        raise FreezeError("careguard_source_set_roles_incomplete_or_duplicate")
    # A four-role benchmark cannot relabel the same source archive as several
    # ostensibly independent references.  Declared source identities, URLs,
    # and retained payloads must all be distinct; aliases in any one field are
    # not enough to establish independence.
    source_names = [str(item["source_name"]) for item in manifests]
    source_urls = [str(item["source_url"]) for item in manifests]
    payload_hashes = [str(item["payload_sha256"]) for item in manifests]
    if (
        len(source_names) != len(set(source_names))
        or len(source_urls) != len(set(source_urls))
        or len(payload_hashes) != len(set(payload_hashes))
    ):
        raise FreezeError("careguard_source_set_sources_not_independent")
    return manifests
