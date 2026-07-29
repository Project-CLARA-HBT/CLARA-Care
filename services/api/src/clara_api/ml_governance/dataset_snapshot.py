"""Offline snapshot validation and leakage-resistant split auditing."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import shutil
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
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
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_IDENTITY_KEYS = (
    "subject_ref",
    "household_ref",
    "site_ref",
    "source_ref",
    "device_ref",
)


@dataclass(frozen=True)
class StoredDatasetSnapshot:
    path: Path
    manifest: dict[str, Any]
    audit: dict[str, Any]


def _parse_time(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise DatasetSnapshotError("snapshot_time_must_be_aware")
    return parsed


def _validate_feature_value(value: Any, path: str = "features") -> None:
    if value is None or isinstance(value, (bool, int, float)):
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _validate_feature_value(child, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in _FORBIDDEN or not normalized or len(normalized) > 96:
                raise DatasetSnapshotError(f"snapshot_feature_key_forbidden:{path}")
            _validate_feature_value(child, f"{path}.{normalized}")
        return
    # No strings or binary content enter a numeric training feature snapshot.
    raise DatasetSnapshotError(f"snapshot_feature_value_forbidden:{path}")


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
    for key in _IDENTITY_KEYS:
        value = str(record[key])
        if not value or len(value) > 96 or "@" in value:
            raise DatasetSnapshotError(f"snapshot_reference_invalid:{key}")
    start = _parse_time(record["window_start"])
    end = _parse_time(record["window_end"])
    if end <= start:
        raise DatasetSnapshotError("snapshot_window_invalid")
    if not isinstance(record["features"], dict):
        raise DatasetSnapshotError("snapshot_features_invalid")
    _validate_feature_value(record["features"])
    encoded = json.dumps(record["features"], ensure_ascii=False)
    if len(encoded) > 50_000:
        raise DatasetSnapshotError("snapshot_features_too_large")
    return dict(record)


def pseudonymize_snapshot_record(
    record: dict[str, Any],
    *,
    pseudonymization_key: bytes,
) -> dict[str, Any]:
    """Replace all linkable identities; the mapping key stays outside the bundle."""

    if len(pseudonymization_key) < 32:
        raise DatasetSnapshotError("pseudonymization_key_too_short")
    output = dict(record)
    for field in _IDENTITY_KEYS:
        raw = str(record.get(field) or "")
        if not raw:
            raise DatasetSnapshotError(f"snapshot_reference_invalid:{field}")
        digest = hmac.digest(
            pseudonymization_key,
            f"{field}:{raw}".encode(),
            "sha256",
        ).hex()
        output[field] = f"{field.removesuffix('_ref')}-{digest[:32]}"
    return output


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


def _safe_identifier(value: str, field: str) -> str:
    if not _SAFE_ID.fullmatch(value):
        raise DatasetSnapshotError(f"snapshot_identity_invalid:{field}")
    return value


def _assert_outside_oltp(root: Path, forbidden_roots: tuple[Path, ...]) -> None:
    resolved = root.resolve()
    for forbidden in forbidden_roots:
        boundary = forbidden.resolve()
        if resolved == boundary or resolved.is_relative_to(boundary):
            raise DatasetSnapshotError("snapshot_store_overlaps_oltp")


def write_snapshot_bundle(
    records: list[dict[str, Any]],
    *,
    root: Path,
    forbidden_oltp_roots: tuple[Path, ...],
    dataset_id: str,
    version: str,
    purpose: str,
    secret_salt: bytes,
    pseudonymization_key: bytes,
    audit: dict[str, Any],
) -> StoredDatasetSnapshot:
    """Publish a deterministic, immutable, audited snapshot outside OLTP."""

    safe_dataset_id = _safe_identifier(dataset_id, "dataset_id")
    safe_version = _safe_identifier(version, "version")
    _assert_outside_oltp(root, forbidden_oltp_roots)
    allowed_audit = {
        "job_id",
        "actor_ref",
        "approval_ref",
        "consent_policy_version",
        "source_export_ref",
        "exported_at",
    }
    if set(audit) != allowed_audit or any(
        not isinstance(value, str) or not value or len(value) > 160 for value in audit.values()
    ):
        raise DatasetSnapshotError("snapshot_audit_invalid")

    pseudonymized = [
        pseudonymize_snapshot_record(
            validate_snapshot_record(record, purpose=purpose),
            pseudonymization_key=pseudonymization_key,
        )
        for record in records
    ]
    rows, manifest = build_snapshot_manifest(
        pseudonymized,
        dataset_id=safe_dataset_id,
        version=safe_version,
        purpose=purpose,
        secret_salt=secret_salt,
    )
    ordered_rows = sorted(
        rows,
        key=lambda item: (
            item["subject_ref"],
            item["window_start"],
            item["source_ref"],
        ),
    )
    row_bytes = b"\n".join(
        json.dumps(item, sort_keys=True, separators=(",", ":")).encode() for item in ordered_rows
    )
    if hashlib.sha256(row_bytes).hexdigest() != manifest["sha256"]:
        raise DatasetSnapshotError("snapshot_checksum_internal_mismatch")
    audited = {
        **audit,
        "purpose": purpose,
        "row_count": len(rows),
        "split_status": manifest["split_audit"]["status"],
        "dataset_sha256": manifest["sha256"],
        "contains_direct_identifiers": False,
    }

    destination = root.resolve() / safe_dataset_id / safe_version
    if destination.exists():
        loaded = load_snapshot_bundle(
            root=root,
            dataset_id=safe_dataset_id,
            version=safe_version,
        )
        if loaded.manifest == manifest and loaded.audit == audited:
            return loaded
        raise DatasetSnapshotError("snapshot_version_already_exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".snapshot-", dir=destination.parent))
    try:
        (temporary / "rows.ndjson").write_bytes(row_bytes)
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        (temporary / "audit.json").write_text(
            json.dumps(audited, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        try:
            os.rename(temporary, destination)
        except OSError as error:
            if destination.exists():
                raise DatasetSnapshotError("snapshot_version_already_exists") from error
            raise
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return load_snapshot_bundle(
        root=root,
        dataset_id=safe_dataset_id,
        version=safe_version,
    )


def load_snapshot_bundle(
    *,
    root: Path,
    dataset_id: str,
    version: str,
) -> StoredDatasetSnapshot:
    """Verify immutable bundle identity, audit linkage, and content checksum."""

    safe_dataset_id = _safe_identifier(dataset_id, "dataset_id")
    safe_version = _safe_identifier(version, "version")
    path = root.resolve() / safe_dataset_id / safe_version
    try:
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        audit = json.loads((path / "audit.json").read_text(encoding="utf-8"))
        content = (path / "rows.ndjson").read_bytes()
    except (OSError, json.JSONDecodeError) as error:
        raise DatasetSnapshotError("snapshot_bundle_invalid") from error
    if not isinstance(manifest, dict) or not isinstance(audit, dict):
        raise DatasetSnapshotError("snapshot_bundle_invalid")
    if (
        manifest.get("dataset_id") != safe_dataset_id
        or str(manifest.get("version")) != safe_version
    ):
        raise DatasetSnapshotError("snapshot_bundle_identity_mismatch")
    digest = hashlib.sha256(content).hexdigest()
    if (
        digest != manifest.get("sha256")
        or digest != audit.get("dataset_sha256")
        or manifest.get("row_count") != audit.get("row_count")
        or audit.get("contains_direct_identifiers") is not False
    ):
        raise DatasetSnapshotError("snapshot_bundle_checksum_mismatch")
    return StoredDatasetSnapshot(path=path, manifest=manifest, audit=audit)
