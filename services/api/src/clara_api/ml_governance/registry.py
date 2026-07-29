"""Validation and private-context compilation for governed inference."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

ALLOWED_OBJECT_KINDS = frozenset(
    {
        "dataset",
        "feature_schema",
        "training_run",
        "model_artifact",
        "evaluation",
        "deployment",
        "drift_snapshot",
        "feedback",
    }
)
RELEASE_TRANSITIONS = {
    "research": {"offline_passed", "retired", "recalled"},
    "offline_passed": {"redteam_passed", "retired", "recalled"},
    "redteam_passed": {"shadow", "retired", "recalled"},
    "shadow": {"pilot", "retired", "recalled"},
    "pilot": {"challenger", "retired", "recalled"},
    "challenger": {"champion", "retired", "recalled"},
    "champion": {"retired", "recalled"},
    "retired": set(),
    "recalled": set(),
}


class GovernanceError(ValueError):
    pass


def validate_catalog_entry(entry: Any) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise GovernanceError("catalog_entry_must_be_object")
    required = {
        "id",
        "kind",
        "provider",
        "implementation",
        "intended_use",
        "forbidden_uses",
        "owner",
        "risk_class",
        "release_state",
        "flag",
        "fallback",
        "data_origin",
    }
    missing = sorted(required - set(entry))
    if missing:
        raise GovernanceError(f"catalog_missing:{missing[0]}")
    for key in required:
        if entry[key] in ("", None, []):
            raise GovernanceError(f"catalog_empty:{key}")
    if entry["release_state"] not in RELEASE_TRANSITIONS:
        raise GovernanceError("catalog_release_state_invalid")
    return dict(entry)


def require_transition(current: str, target: str) -> None:
    if target not in RELEASE_TRANSITIONS.get(current, set()):
        raise GovernanceError(f"invalid_release_transition:{current}:{target}")


def compile_private_context(
    *,
    use_case: dict[str, Any],
    profile_id: int,
    purpose: str,
    actor_category: str,
    requested_data_classes: set[str],
    revision_refs: list[str],
    consent_version: str,
    grant_version: int | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Compile authorization decisions before any content is sent to ML."""

    current = (now or datetime.now(UTC)).astimezone(UTC)
    allowed_purposes = set(use_case.get("allowed_purposes") or [])
    allowed_classes = set(use_case.get("allowed_data_classes") or [])
    if use_case.get("release_state") not in {
        "shadow",
        "pilot",
        "challenger",
        "champion",
    }:
        raise GovernanceError("use_case_not_deployable")
    if purpose not in allowed_purposes:
        raise GovernanceError("purpose_not_allowed")
    if not requested_data_classes or not requested_data_classes <= allowed_classes:
        raise GovernanceError("data_class_not_allowed")
    if use_case.get("requires_consent", True) and not consent_version:
        raise GovernanceError("consent_required")
    refs = sorted(set(revision_refs))
    if not refs or len(refs) > 500 or any(len(ref) > 128 for ref in refs):
        raise GovernanceError("revision_lineage_invalid")
    digest_payload = {
        "profile_id": profile_id,
        "use_case_id": use_case["use_case_id"],
        "purpose": purpose,
        "data_classes": sorted(requested_data_classes),
        "revision_refs": refs,
        "consent_version": consent_version,
        "grant_version": grant_version,
    }
    digest = hashlib.sha256(
        json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        **digest_payload,
        "actor_category": actor_category,
        "context_digest": digest,
        "expires_at": current + timedelta(minutes=15),
    }


def safe_operational_manifest(values: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "latency_ms",
        "input_revision_count",
        "citation_count",
        "abstained",
        "ood",
        "fallback_used",
        "locale",
    }
    if set(values) - allowed:
        raise GovernanceError("operational_manifest_contains_unknown_fields")
    if any(isinstance(value, str) and len(value) > 32 for value in values.values()):
        raise GovernanceError("operational_manifest_string_too_long")
    return dict(values)
