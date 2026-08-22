"""Versioned canonical JSON used for GLHS consistency fingerprints.

This profile is intentionally an internal deterministic encoding, not a sender
authentication mechanism and not a claim of RFC 8785 conformance.  It accepts
only JSON-compatible values plus timezone-aware ``datetime`` values, which are
normalized to UTC.  Unsupported objects and non-finite numbers fail closed.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from datetime import UTC, datetime
from functools import lru_cache
from typing import TypeAlias

JsonScalar: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]

DIGEST_ALGORITHM = "sha-256"
CANONICALIZATION_PROFILE = "clara.canonical-json.v1"
LEGACY_CANONICALIZATION_PROFILE = "python-json-sort-default-str.v1"


def _normalize(value: object) -> JsonValue:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical_json_non_finite_number")
        return 0 if value == 0 else value
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("canonical_json_timezone_required")
        return value.astimezone(UTC).isoformat(timespec="microseconds")
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("canonical_json_string_keys_required")
        return {key: _normalize(item) for key, item in value.items()}
    raise ValueError(f"canonical_json_unsupported_type:{type(value).__name__}")


def _freeze(value: object) -> object:
    """Convert an arbitrary JSON-compatible payload to an immutable hashable tuple."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical_json_non_finite_number")
        return 0 if value == 0 else value
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("canonical_json_timezone_required")
        return value.astimezone(UTC).isoformat(timespec="microseconds")
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("canonical_json_string_keys_required")
        return ("__dict__", tuple(sorted((k, _freeze(v)) for k, v in value.items())))
    raise ValueError(f"canonical_json_unsupported_type:{type(value).__name__}")


def _frozen_to_normalized(frozen: object) -> JsonValue:
    """Reconstruct normalized structure from frozen representation."""
    if isinstance(frozen, tuple):
        if len(frozen) == 2 and frozen[0] == "__dict__":
            return {k: _frozen_to_normalized(v) for k, v in frozen[1]}
        return [_frozen_to_normalized(item) for item in frozen]
    return frozen  # type: ignore[return-value]


def _frozen_to_canonical_bytes(frozen: object) -> bytes:
    """Serialize frozen structure to canonical JSON UTF-8 bytes."""
    obj = _frozen_to_normalized(frozen)
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


@lru_cache(maxsize=16384)
def _cached_frozen_digest(frozen: object) -> str:
    """Compute and cache SHA-256 digest on immutable state payloads."""
    return hashlib.sha256(_frozen_to_canonical_bytes(frozen)).hexdigest()


def canonical_bytes(value: object) -> bytes:
    """Encode according to ``clara.canonical-json.v1``.

    Objects use lexicographically sorted string keys, arrays preserve order,
    UTF-8 is emitted directly, whitespace is omitted, negative zero is encoded
    as zero, and aware datetimes are rendered in UTC with six fractional digits.
    """

    normalized = _normalize(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def fast_canonical_digest(value: object) -> str:
    """Zero-copy byte-level SHA-256 digest with LRU caching on immutable state payloads.

    Provides O(1) cached lookups on repeated state payload fingerprints and avoids
    unnecessary re-serialization.
    """
    if isinstance(value, (bytes, bytearray, memoryview)):
        return hashlib.sha256(memoryview(value)).hexdigest()
    frozen = _freeze(value)
    return _cached_frozen_digest(frozen)


def consistency_fingerprint(value: object) -> str:
    """Return an unkeyed integrity fingerprint inside the trusted-store model."""
    return fast_canonical_digest(value)


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
                b = canonical_bytes(item)
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


@lru_cache(maxsize=16384)
def _cached_frozen_merkle_digest(frozen_seq: tuple[object, ...]) -> str:
    raw_leaves = [_frozen_to_canonical_bytes(f) for f in frozen_seq]
    return zero_copy_merkle_tree_digest(raw_leaves)


def fast_merkle_digest(
    leaves: bytes | bytearray | memoryview | Sequence[object],
) -> str:
    """Compute Merkle tree root digest with LRU caching for structured sequences."""
    if isinstance(leaves, (bytes, bytearray, memoryview)):
        return zero_copy_merkle_tree_digest(leaves)
    frozen_items = tuple(_freeze(item) for item in leaves)
    return _cached_frozen_merkle_digest(frozen_items)


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
    if algorithm != DIGEST_ALGORITHM:
        raise ValueError("unsupported_digest_algorithm")
    if profile == CANONICALIZATION_PROFILE:
        return consistency_fingerprint(value)
    if profile == LEGACY_CANONICALIZATION_PROFILE:
        return legacy_consistency_fingerprint(value)
    raise ValueError("unsupported_canonicalization_profile")
