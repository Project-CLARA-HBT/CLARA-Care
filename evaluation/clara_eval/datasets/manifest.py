"""Schema and validation for privacy-safe CLARA-Eval VN dataset manifests.

This module is intentionally stdlib-only so that PR smoke checks can validate
evaluation provenance without model credentials, a database, or an evaluator.
It never derives quality metrics from fixture contents.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from ..tracks import REQUIRED_TRACK_IDS


class ManifestValidationError(ValueError):
    """Raised when a dataset or suite manifest cannot be trusted."""


MeasurementState = Literal["not_measured", "measured", "blocked"]
ALLOWED_PROVENANCE = frozenset(
    {
        "synthetic_safety_fixture",
        "public_dataset",
        "restricted_clinically_reviewed",
        "credentialed_dataset",
    }
)


@dataclass(frozen=True)
class Measurement:
    """An honest metric declaration; a manifest is not a benchmark result."""

    metric_id: str
    state: MeasurementState
    reason: str | None
    command: str | None

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> Measurement:
        state = str(raw.get("state", ""))
        if state not in {"not_measured", "measured", "blocked"}:
            raise ManifestValidationError("measurement_state_invalid")
        metric_id = str(raw.get("metric_id", "")).strip()
        if not metric_id:
            raise ManifestValidationError("measurement_id_missing")
        reason = raw.get("reason")
        command = raw.get("command")
        if state != "measured" and (not isinstance(reason, str) or not reason.strip()):
            raise ManifestValidationError("measurement_reason_required")
        if state != "measured" and (not isinstance(command, str) or not command.strip()):
            raise ManifestValidationError("measurement_command_required")
        return cls(
            metric_id=metric_id,
            state=state,  # type: ignore[arg-type]
            reason=reason.strip() if isinstance(reason, str) else None,
            command=command.strip() if isinstance(command, str) else None,
        )


@dataclass(frozen=True)
class DatasetEntry:
    dataset_id: str
    track_id: str
    split: Literal["smoke", "nightly", "release_locked", "judge_demo"]
    path: str
    sha256: str
    record_count: int
    provenance: str
    license_or_access: str
    contains_phi: bool
    contains_secrets: bool
    clinically_representative: bool
    measurements: tuple[Measurement, ...]

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> DatasetEntry:
        try:
            split = str(raw["split"])
            boolean_fields = (
                "contains_phi",
                "contains_secrets",
                "clinically_representative",
            )
            if any(not isinstance(raw[name], bool) for name in boolean_fields):
                raise ManifestValidationError("dataset_boolean_invalid")
            entry = cls(
                dataset_id=str(raw["dataset_id"]).strip(),
                track_id=str(raw["track_id"]).strip(),
                split=split,  # type: ignore[arg-type]
                path=str(raw["path"]).strip(),
                sha256=str(raw["sha256"]).strip().lower(),
                record_count=int(raw["record_count"]),
                provenance=str(raw["provenance"]).strip(),
                license_or_access=str(raw["license_or_access"]).strip(),
                contains_phi=raw["contains_phi"],
                contains_secrets=raw["contains_secrets"],
                clinically_representative=raw["clinically_representative"],
                measurements=tuple(
                    Measurement.from_mapping(item) for item in raw.get("measurements", [])
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ManifestValidationError("dataset_entry_invalid") from exc
        entry.validate_shape()
        return entry

    def validate_shape(self) -> None:
        if not self.dataset_id or self.track_id not in REQUIRED_TRACK_IDS:
            raise ManifestValidationError("dataset_track_invalid")
        if self.split not in {"smoke", "nightly", "release_locked", "judge_demo"}:
            raise ManifestValidationError("dataset_split_invalid")
        if not self.path or Path(self.path).is_absolute() or ".." in Path(self.path).parts:
            raise ManifestValidationError("dataset_path_invalid")
        if len(self.sha256) != 64 or any(char not in "0123456789abcdef" for char in self.sha256):
            raise ManifestValidationError("dataset_sha256_invalid")
        if self.record_count < 1:
            raise ManifestValidationError("dataset_record_count_invalid")
        if self.provenance not in ALLOWED_PROVENANCE:
            raise ManifestValidationError("dataset_provenance_invalid")
        if not self.license_or_access:
            raise ManifestValidationError("dataset_license_missing")
        if self.contains_phi or self.contains_secrets:
            raise ManifestValidationError("dataset_sensitive_content_forbidden")
        if self.provenance == "synthetic_safety_fixture" and self.clinically_representative:
            raise ManifestValidationError("synthetic_fixture_cannot_be_clinically_representative")
        if not self.measurements:
            raise ManifestValidationError("dataset_measurements_missing")
        metric_ids = [measurement.metric_id for measurement in self.measurements]
        if len(metric_ids) != len(set(metric_ids)):
            raise ManifestValidationError("measurement_ids_not_unique")


@dataclass(frozen=True)
class DatasetManifest:
    schema_version: str
    suite_id: str
    suite_version: str
    data_policy: dict[str, bool]
    datasets: tuple[DatasetEntry, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "suite_id": self.suite_id,
            "suite_version": self.suite_version,
            "data_policy": self.data_policy,
            "datasets": [asdict(entry) for entry in self.datasets],
        }


def canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def jsonl_record_count(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ManifestValidationError(
                    f"dataset_jsonl_invalid:{path.name}:{line_number}"
                ) from exc
            if not isinstance(value, dict):
                raise ManifestValidationError(
                    f"dataset_record_not_object:{path.name}:{line_number}"
                )
            count += 1
    return count


def _validate_data_policy(raw: Any) -> dict[str, bool]:
    if not isinstance(raw, dict):
        raise ManifestValidationError("data_policy_missing")
    required = {"contains_phi", "contains_secrets", "synthetic_fixtures_only"}
    if set(raw) != required or any(not isinstance(raw[key], bool) for key in required):
        raise ManifestValidationError("data_policy_invalid")
    if raw["contains_phi"] or raw["contains_secrets"]:
        raise ManifestValidationError("manifest_sensitive_content_forbidden")
    return {key: bool(raw[key]) for key in required}


def load_dataset_manifest(path: Path, *, repository_root: Path | None = None) -> DatasetManifest:
    """Load a manifest and verify all referenced JSONL assets by checksum/count."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestValidationError("dataset_manifest_unreadable") from exc
    if not isinstance(raw, dict):
        raise ManifestValidationError("dataset_manifest_not_object")
    schema_version = raw.get("schema_version")
    suite_id = raw.get("suite_id")
    suite_version = raw.get("suite_version")
    if schema_version != "clara-eval-vn.dataset-manifest.v1":
        raise ManifestValidationError("dataset_manifest_schema_unsupported")
    if not isinstance(suite_id, str) or not suite_id.strip() or not isinstance(suite_version, str):
        raise ManifestValidationError("dataset_manifest_identity_invalid")
    datasets_raw = raw.get("datasets")
    if not isinstance(datasets_raw, list):
        raise ManifestValidationError("dataset_manifest_datasets_invalid")
    entries = tuple(
        DatasetEntry.from_mapping(item) for item in datasets_raw if isinstance(item, dict)
    )
    if len(entries) != len(datasets_raw):
        raise ManifestValidationError("dataset_manifest_dataset_not_object")
    if {entry.track_id for entry in entries} != REQUIRED_TRACK_IDS:
        raise ManifestValidationError("dataset_manifest_required_tracks_missing")
    if len({entry.dataset_id for entry in entries}) != len(entries):
        raise ManifestValidationError("dataset_manifest_dataset_ids_not_unique")

    root = repository_root or path.parent.parent.parent.parent
    for entry in entries:
        asset_path = root / entry.path
        if not asset_path.is_file():
            raise ManifestValidationError(f"dataset_asset_missing:{entry.dataset_id}")
        if file_sha256(asset_path) != entry.sha256:
            raise ManifestValidationError(f"dataset_checksum_mismatch:{entry.dataset_id}")
        if jsonl_record_count(asset_path) != entry.record_count:
            raise ManifestValidationError(f"dataset_record_count_mismatch:{entry.dataset_id}")
    return DatasetManifest(
        schema_version=schema_version,
        suite_id=suite_id.strip(),
        suite_version=suite_version,
        data_policy=_validate_data_policy(raw.get("data_policy")),
        datasets=entries,
    )


def validate_dataset_manifest(
    path: Path, *, repository_root: Path | None = None
) -> DatasetManifest:
    """Explicit validator alias for CI and report tooling."""

    return load_dataset_manifest(path, repository_root=repository_root)
