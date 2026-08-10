"""Minimal deterministic adversarial edits with complete edit manifests."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

from evaluation.commitloop.schema import TimelineEvent


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def apply_minimal_edit(
    event: dict[str, Any],
    *,
    field: str,
    new_value: object,
    reason: str,
    seed: int,
    valid_at: datetime,
    known_at: datetime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if field not in event:
        raise ValueError("edit_field_not_source_present")
    edited = deepcopy(event)
    old_value = edited[field]
    edited[field] = new_value
    manifest = {
        "source_id": str(event.get("evidence_id", "")),
        "field": field,
        "old_value": old_value,
        "new_value": new_value,
        "reason": reason,
        "seed": seed,
        "valid_at": valid_at.isoformat(),
        "known_at": known_at.isoformat(),
        "before_sha256": _digest(event),
        "after_sha256": _digest(edited),
        "model_prompt_version": None,
    }
    return edited, manifest


def materialize_perturbation(
    event: dict[str, Any], *, manifest: dict[str, Any]
) -> dict[str, Any]:
    """Replay one recorded adversarial edit and verify its exact source hashes.

    The manifest is the authority for a deliberately minimal edit.  This is
    intentionally data-only: it cannot execute model output, expressions, or
    arbitrary patch operations.
    """

    source_id = manifest.get("source_id")
    if not isinstance(source_id, str) or event.get("evidence_id") != source_id:
        raise ValueError("perturbation_source_mismatch")
    if _digest(event) != manifest.get("before_sha256"):
        raise ValueError("perturbation_before_hash_mismatch")
    field = manifest.get("field")
    operation = manifest.get("operation")
    if not isinstance(field, str) or operation not in {"replace", "remove", "duplicate"}:
        raise ValueError("perturbation_operation_invalid")
    edited = deepcopy(event)
    if operation == "replace":
        if field not in edited and manifest.get("old_value") is not None:
            raise ValueError("perturbation_field_missing")
        edited[field] = manifest.get("new_value")
    elif operation == "remove":
        if field not in edited:
            raise ValueError("perturbation_field_missing")
        edited.pop(field)
    else:
        edited["evidence_id"] = f"{source_id}:duplicate"
    if _digest(edited) != manifest.get("after_sha256"):
        raise ValueError("perturbation_after_hash_mismatch")
    return edited


def materialize_timeline_perturbation(
    event: TimelineEvent, *, manifest: dict[str, Any]
) -> TimelineEvent:
    """Replay an audited edit as a typed timeline event for deterministic tests."""

    source_view = {
        "evidence_id": event.evidence_id,
        "status": event.status,
        "valid_at": event.valid_at,
        "known_at": event.known_at,
    }
    edited = materialize_perturbation(source_view, manifest=manifest)

    def timestamp(field: str) -> datetime | None:
        value = edited[field]
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
        raise ValueError("perturbation_timestamp_invalid")

    known_at = timestamp("known_at")
    if known_at is None:
        raise ValueError("perturbation_known_time_missing")
    source = deepcopy(event.source)
    if manifest["variant_kind"] == "conflict":
        source["relation"] = edited.get("relation")
    return replace(
        event,
        evidence_id=str(edited["evidence_id"]),
        status=edited.get("status"),
        valid_at=timestamp("valid_at"),
        known_at=known_at,
        source=source,
    )


def generate_adversarial_perturbations(
    event: dict[str, Any], *, cutoff: datetime, seed: int
) -> tuple[dict[str, Any], ...]:
    """Return auditable one-operation variants without adding clinical facts."""

    evidence_id = str(event.get("evidence_id", ""))
    valid_at = event.get("valid_at")
    known_at = event.get("known_at")
    if not evidence_id or not isinstance(valid_at, datetime) or not isinstance(known_at, datetime):
        raise ValueError("perturbation_requires_bitemporal_source_event")
    valid_at = valid_at.replace(tzinfo=UTC) if valid_at.tzinfo is None else valid_at.astimezone(UTC)
    known_at = known_at.replace(tzinfo=UTC) if known_at.tzinfo is None else known_at.astimezone(UTC)

    def manifest(
        *,
        kind: str,
        field: str,
        old_value: object,
        new_value: object,
        operation: str = "replace",
    ) -> dict[str, Any]:
        before = deepcopy(event)
        after = deepcopy(event)
        if operation == "remove":
            after.pop(field, None)
        elif operation == "duplicate":
            after["evidence_id"] = f"{evidence_id}:duplicate"
        else:
            after[field] = new_value
        return {
            "variant_kind": kind,
            "source_id": evidence_id,
            "generated_id": f"{evidence_id}:{kind}",
            "operation": operation,
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
            "reason": f"minimal_{kind}_perturbation",
            "seed": seed,
            "valid_at": valid_at.isoformat(),
            "known_at": known_at.isoformat(),
            "before_sha256": _digest(before),
            "after_sha256": _digest(after),
            "model_prompt_version": None,
        }

    status = event.get("status")
    status_replacement = "revoked" if status != "revoked" else "on-hold"
    after_cutoff = (cutoff + timedelta(seconds=1)).isoformat()
    return (
        manifest(kind="cancellation", field="status", old_value=status, new_value=status_replacement),
        manifest(kind="supersession", field="status", old_value=status, new_value="replaced"),
        manifest(kind="conflict", field="relation", old_value=None, new_value="contradicts"),
        manifest(
            kind="partial_completion", field="status", old_value=status, new_value="preliminary"
        ),
        manifest(
            kind="late_ingestion",
            field="known_at",
            old_value=known_at.isoformat(),
            new_value=after_cutoff,
        ),
        manifest(
            kind="duplicate",
            field="evidence_id",
            old_value=evidence_id,
            new_value=evidence_id,
            operation="duplicate",
        ),
        manifest(
            kind="missing_prerequisite",
            field="status",
            old_value=status,
            new_value=None,
            operation="remove",
        ),
        manifest(kind="fuzzy_time", field="valid_at", old_value=valid_at.isoformat(), new_value=None),
        manifest(
            kind="post_cutoff_evidence",
            field="valid_at",
            old_value=valid_at.isoformat(),
            new_value=after_cutoff,
        ),
    )
