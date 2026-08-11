"""Shared registry and local-source validation primitives."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = "clara-dataset-registry.v1"
REQUIRED_FIELDS = frozenset(
    {
        "id",
        "display_name",
        "provider",
        "canonical_source",
        "mirror_source",
        "download_method",
        "license",
        "access_class",
        "evidence_class",
        "synthetic",
        "schema",
        "version",
        "release_date",
        "acquired_at",
        "raw_path",
        "normalized_path",
        "expected_files",
        "checksum_manifest",
        "subject_identifier",
        "encounter_identifier",
        "valid_time_fields",
        "knowledge_time_fields",
        "provenance_fields",
        "clinical_domains",
        "known_limitations",
    }
)
ALLOWED_ACCESS_CLASSES = frozenset(
    {"open", "open_public_use_agreement", "credentialed", "not_available"}
)


class DatasetRegistryError(RuntimeError):
    """Raised when registry or local-source evidence is invalid."""


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_registry_path() -> Path:
    return repository_root() / "datasets" / "registry.yaml"


def repository_relative_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repository_root().resolve()))
    except ValueError as exc:
        raise DatasetRegistryError("source_path_outside_repository") from exc


def _safe_repository_path(root: Path, value: object, *, field: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise DatasetRegistryError(f"invalid_{field}")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise DatasetRegistryError(f"unsafe_{field}")
    resolved = (root / relative).resolve()
    if root != resolved and root not in resolved.parents:
        raise DatasetRegistryError(f"unsafe_{field}")
    return resolved


def load_registry(path: Path | None = None) -> dict[str, Any]:
    registry_path = (path or default_registry_path()).resolve()
    try:
        payload = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise DatasetRegistryError("registry_unreadable") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise DatasetRegistryError("registry_schema_invalid")
    datasets = payload.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        raise DatasetRegistryError("registry_datasets_missing")
    seen: set[str] = set()
    root = repository_root()
    for item in datasets:
        if not isinstance(item, dict) or REQUIRED_FIELDS - set(item):
            raise DatasetRegistryError("registry_dataset_fields_missing")
        dataset_id = item.get("id")
        if not isinstance(dataset_id, str) or not dataset_id.replace("_", "").isalnum():
            raise DatasetRegistryError("registry_dataset_id_invalid")
        if dataset_id in seen:
            raise DatasetRegistryError("registry_dataset_id_duplicate")
        seen.add(dataset_id)
        if item.get("access_class") not in ALLOWED_ACCESS_CLASSES:
            raise DatasetRegistryError("registry_access_class_invalid")
        if not isinstance(item.get("synthetic"), bool):
            raise DatasetRegistryError("registry_synthetic_flag_invalid")
        if not isinstance(item.get("clinical_domains"), list):
            raise DatasetRegistryError("registry_domains_invalid")
        _safe_repository_path(root, item["raw_path"], field="raw_path")
        _safe_repository_path(root, item["normalized_path"], field="normalized_path")
        _safe_repository_path(root, item["checksum_manifest"], field="checksum_manifest")
        candidates = item.get("local_candidates", [])
        if not isinstance(candidates, list):
            raise DatasetRegistryError("registry_local_candidates_invalid")
        for candidate in candidates:
            _safe_repository_path(root, candidate, field="local_candidate")
    return payload


def get_dataset(registry: Mapping[str, Any], dataset_id: str) -> dict[str, Any]:
    for item in registry["datasets"]:
        if item["id"] == dataset_id:
            return dict(item)
    raise DatasetRegistryError("dataset_not_registered")


def candidate_paths(dataset: Mapping[str, Any]) -> tuple[Path, ...]:
    root = repository_root()
    values = [dataset["raw_path"], *dataset.get("local_candidates", [])]
    resolved: list[Path] = []
    for value in values:
        path = _safe_repository_path(root, value, field="local_candidate")
        if path not in resolved:
            resolved.append(path)
    return tuple(resolved)


def resolve_local_source(dataset: Mapping[str, Any]) -> Path:
    for path in candidate_paths(dataset):
        if path.is_file() or (path.is_dir() and next(iter_source_files(path), None)):
            return path
    if dataset.get("access_class") == "credentialed":
        raise DatasetRegistryError("ACCESS_REQUIRED")
    raise DatasetRegistryError("NOT_AVAILABLE")


def iter_source_files(source: Path) -> Iterator[Path]:
    if source.is_file():
        yield source
        return
    for path in sorted(source.rglob("*")):
        if path.is_file() and not path.is_symlink() and not path.name.endswith(".part"):
            yield path


def sha256_file(path: Path, *, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def source_inventory(source: Path) -> list[dict[str, object]]:
    base = source if source.is_dir() else source.parent
    inventory = []
    for path in iter_source_files(source):
        inventory.append(
            {
                "path": path.name if source.is_file() else str(path.relative_to(base)),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    if not inventory:
        raise DatasetRegistryError("source_inventory_empty")
    return inventory
