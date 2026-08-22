"""Versioned canonical JSON used for GLHS consistency fingerprints.

Strict RFC 8785 byte-level canonical serialization with deterministic
type dispatch for dataclasses, dates, datetimes, UUIDs, sets, and Decimals.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import TypeAlias

JsonScalar: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]

DIGEST_ALGORITHM = "sha-256"
CANONICALIZATION_PROFILE = "clara.canonical-json.v1"
LEGACY_CANONICALIZATION_PROFILE = "python-json-sort-default-str.v1"


def _json_default(obj: object) -> object:
    """Deterministic canonical serializer for non-primitive Python types."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    if isinstance(obj, datetime):
        if obj.tzinfo is None or obj.utcoffset() is None:
            raise ValueError("canonical_json_timezone_required")
        return obj.astimezone(UTC).isoformat(timespec="microseconds")
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, (set, frozenset)):
        try:
            return sorted(obj)
        except TypeError:
            return sorted(obj, key=lambda x: canonical_json_bytes(x))
    if isinstance(obj, Decimal):
        if not obj.is_finite():
            raise ValueError("canonical_json_non_finite_number")
        if obj == obj.to_integral_value():
            return int(obj)
        return float(obj)
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, Path):
        return str(obj)
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        return obj.model_dump(mode="json")
    if hasattr(obj, "dict") and callable(obj.dict):
        return obj.dict()
    raise ValueError(f"canonical_json_unsupported_type:{type(obj).__name__}")


def canonical_json_bytes(payload: object) -> bytes:
    """Strict byte-level canonical JSON serialization per RFC 8785."""
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
        default=_json_default,
    ).encode("utf-8")


canonical_bytes = canonical_json_bytes


def consistency_fingerprint(payload: object) -> str:
    """Return SHA-256 consistency fingerprint for payload."""
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def fast_canonical_digest(value: object) -> str:
    """Return SHA-256 consistency fingerprint (zero-copy for bytes/memoryview)."""
    if isinstance(value, (bytes, bytearray, memoryview)):
        return hashlib.sha256(memoryview(value)).hexdigest()
    return consistency_fingerprint(value)


def zero_copy_merkle_tree_digest(
    data: bytes | bytearray | memoryview | Sequence[bytes | memoryview | str | object],
    *,
    chunk_size: int = 4096,
) -> str:
    """Compute a zero-copy byte-level SHA-256 Merkle tree root digest.

    Uses domain separation:
    - Leaf node: SHA-256(0x00 || chunk_bytes)
    - Internal node: SHA-256(0x01 || left_digest || right_digest)
    """
    if isinstance(data, (bytes, bytearray, memoryview)):
        mv = memoryview(data)
        if len(mv) == 0:
            return hashlib.sha256(b"\x00").hexdigest()
        leaf_hashes: list[bytes] = []
        for i in range(0, len(mv), chunk_size):
            chunk = mv[i : i + chunk_size]
            h = hashlib.sha256(b"\x00")
            h.update(chunk)
            leaf_hashes.append(h.digest())
    else:
        seq = list(data)
        if not seq:
            return hashlib.sha256(b"\x00").hexdigest()
        leaf_hashes = []
        for item in seq:
            if isinstance(item, (bytes, bytearray, memoryview)):
                b = bytes(item)
            elif isinstance(item, str):
                b = item.encode("utf-8")
            else:
                b = canonical_json_bytes(item)
            h = hashlib.sha256(b"\x00")
            h.update(b)
            leaf_hashes.append(h.digest())

    current_layer = leaf_hashes
    while len(current_layer) > 1:
        next_layer: list[bytes] = []
        for i in range(0, len(current_layer), 2):
            left = current_layer[i]
            right = current_layer[i + 1] if (i + 1 < len(current_layer)) else left
            h = hashlib.sha256(b"\x01")
            h.update(left)
            h.update(right)
            next_layer.append(h.digest())
        current_layer = next_layer

    return current_layer[0].hex()


merkle_tree_digest = zero_copy_merkle_tree_digest


def fast_merkle_digest(
    leaves: bytes | bytearray | memoryview | Sequence[object],
) -> str:
    """Compute Merkle tree root digest."""
    return zero_copy_merkle_tree_digest(leaves)


def legacy_consistency_fingerprint(value: object) -> str:
    """Reproduce the pre-versioned digest for historical snapshot validation."""
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fingerprint_for_profile(value: object, *, profile: str, algorithm: str) -> str:
    """Validate profile and return digest accordingly."""
    if algorithm != DIGEST_ALGORITHM:
        raise ValueError("unsupported_digest_algorithm")
    if profile == CANONICALIZATION_PROFILE:
        return consistency_fingerprint(value)
    if profile == LEGACY_CANONICALIZATION_PROFILE:
        return legacy_consistency_fingerprint(value)
    raise ValueError("unsupported_canonicalization_profile")
