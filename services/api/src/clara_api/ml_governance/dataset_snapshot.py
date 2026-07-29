"""Offline snapshot validation and leakage-resistant split auditing."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections import defaultdict
from datetime import datetime
from typing import Any


class DatasetSnapshotError(ValueError):
    pass


_REQUIRED = {
    "subject_ref",
    "household_ref",
    "site_ref",
    "source_ref",
    "device_ref",
    "window_start",
    "window_end",
    "purpose",
    "consent_active",
    "features",
}
_FORBIDDEN = {
    "name",
    "email",
    "phone",
    "address",
    "free_text",
    "document_text",
    "raw_query",
}


def _parse_time(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise DatasetSnapshotError("snapshot_time_must_be_aware")
    return parsed


def validate_snapshot_record(record: Any, *, purpose: str) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise DatasetSnapshotError("snapshot_record_must_be_object")
    missing = sorted(_REQUIRED - set(record))
    if missing:
        raise DatasetSnapshotError(f"snapshot_missing:{missing[0]}")
    forbidden = sorted(_FORBIDDEN & set(record))
    if forbidden:
        raise DatasetSnapshotError(f"snapshot_forbidden:{forbidden[0]}")
    if record["purpose"] != purpose or record["consent_active"] is not True:
        raise DatasetSnapshotError("snapshot_purpose_or_consent_denied")
    for key in (
        "subject_ref",
        "household_ref",
        "site_ref",
        "source_ref",
        "device_ref",
    ):
        value = str(record[key])
        if not value or len(value) > 96 or "@" in value:
            raise DatasetSnapshotError(f"snapshot_reference_invalid:{key}")
    start = _parse_time(record["window_start"])
    end = _parse_time(record["window_end"])
    if end <= start:
        raise DatasetSnapshotError("snapshot_window_invalid")
    if not isinstance(record["features"], dict):
        raise DatasetSnapshotError("snapshot_features_invalid")
    encoded = json.dumps(record["features"], ensure_ascii=False)
    if len(encoded) > 50_000:
        raise DatasetSnapshotError("snapshot_features_too_large")
    return dict(record)


def assign_group_split(
    record: dict[str, Any],
    *,
    secret_salt: bytes,
) -> str:
    if len(secret_salt) < 16:
        raise DatasetSnapshotError("split_salt_too_short")
    # Household is the widest identity unit: every person in one household must
    # remain in the same split. Subject isolation follows automatically.
    group = str(record["household_ref"]).encode()
    bucket = int.from_bytes(hmac.digest(secret_salt, group, "sha256")[:8], "big") % 100
    if bucket < 70:
        return "train"
    if bucket < 85:
        return "validation"
    return "test"


def _assign_connected_splits(records: list[dict[str, Any]], *, secret_salt: bytes) -> list[str]:
    if len(secret_salt) < 16:
        raise DatasetSnapshotError("split_salt_too_short")
    parents = list(range(len(records)))

    def root(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = root(left), root(right)
        if left_root != right_root:
            parents[right_root] = left_root

    seen: dict[tuple[str, str], int] = {}
    dimensions = (
        "subject_ref",
        "household_ref",
        "site_ref",
        "source_ref",
        "device_ref",
    )
    for index, record in enumerate(records):
        for key in dimensions:
            identity = (key, str(record[key]))
            prior = seen.setdefault(identity, index)
            union(index, prior)
    component_tokens: dict[int, list[str]] = defaultdict(list)
    for index, record in enumerate(records):
        component_tokens[root(index)].extend(f"{key}:{record[key]}" for key in dimensions)
    component_split: dict[int, str] = {}
    for component, tokens in component_tokens.items():
        token = "|".join(sorted(set(tokens))).encode()
        bucket = int.from_bytes(hmac.digest(secret_salt, token, "sha256")[:8], "big") % 100
        component_split[component] = (
            "train" if bucket < 70 else "validation" if bucket < 85 else "test"
        )
    return [component_split[root(index)] for index in range(len(records))]


def audit_split_leakage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Reject identity/source/device/site overlap and cross-split time overlap."""

    by_dimension: dict[str, dict[str, set[str]]] = {
        key: defaultdict(set)
        for key in (
            "subject_ref",
            "household_ref",
            "site_ref",
            "source_ref",
            "device_ref",
        )
    }
    windows: dict[str, list[tuple[datetime, datetime, str]]] = defaultdict(list)
    for row in rows:
        split = str(row.get("split"))
        if split not in {"train", "validation", "test"}:
            raise DatasetSnapshotError("snapshot_split_invalid")
        for key, values in by_dimension.items():
            values[str(row[key])].add(split)
        windows[str(row["subject_ref"])].append(
            (_parse_time(row["window_start"]), _parse_time(row["window_end"]), split)
        )
    for key, values in by_dimension.items():
        if any(len(splits) > 1 for splits in values.values()):
            raise DatasetSnapshotError(f"split_leakage:{key}")
    for subject_windows in windows.values():
        ordered = sorted(subject_windows)
        for index, (start, end, split) in enumerate(ordered):
            for other_start, other_end, other_split in ordered[index + 1 :]:
                if other_start >= end:
                    break
                if split != other_split and start < other_end:
                    raise DatasetSnapshotError("split_leakage:overlapping_window")
    counts = {
        split: sum(row["split"] == split for row in rows)
        for split in ("train", "validation", "test")
    }
    return {"status": "passed", "row_count": len(rows), "split_counts": counts}


def build_snapshot_manifest(
    records: list[dict[str, Any]],
    *,
    dataset_id: str,
    version: str,
    purpose: str,
    secret_salt: bytes,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for record in records:
        validated = validate_snapshot_record(record, purpose=purpose)
        prepared.append(validated)
    splits = _assign_connected_splits(prepared, secret_salt=secret_salt)
    prepared = [{**record, "split": split} for record, split in zip(prepared, splits, strict=True)]
    audit = audit_split_leakage(prepared)
    content_digest = hashlib.sha256(
        b"\n".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
            for row in sorted(
                prepared,
                key=lambda item: (
                    item["subject_ref"],
                    item["window_start"],
                    item["source_ref"],
                ),
            )
        )
    ).hexdigest()
    return prepared, {
        "dataset_id": dataset_id,
        "version": version,
        "purpose": purpose,
        "sha256": content_digest,
        "row_count": len(prepared),
        "split_audit": audit,
        "contains_direct_identifiers": False,
        "source": "audited_pseudonymized_export_not_oltp",
    }
