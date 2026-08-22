from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

from clara_api.glhs.canonical_json import (
    _cached_frozen_digest,
    canonical_bytes,
    consistency_fingerprint,
    fast_canonical_digest,
    fast_merkle_digest,
    merkle_tree_digest,
    zero_copy_merkle_tree_digest,
)


def test_canonical_json_is_key_order_and_unicode_stable() -> None:
    left = {"z": [1, "thuốc"], "a": {"time": datetime(2026, 1, 1, tzinfo=UTC)}}
    right = {"a": {"time": datetime(2026, 1, 1, tzinfo=UTC)}, "z": [1, "thuốc"]}

    assert canonical_bytes(left) == canonical_bytes(right)
    assert consistency_fingerprint(left) == consistency_fingerprint(right)
    assert fast_canonical_digest(left) == consistency_fingerprint(left)
    assert b"thu\xe1\xbb\x91c" in canonical_bytes(left)


def test_canonical_json_normalizes_negative_zero_and_requires_safe_values() -> None:
    assert canonical_bytes({"value": -0.0}) == b'{"value":0}'
    with pytest.raises(ValueError, match="non_finite"):
        canonical_bytes({"value": float("nan")})
    with pytest.raises(ValueError, match="timezone_required"):
        canonical_bytes({"time": datetime(2026, 1, 1)})
    with pytest.raises(ValueError, match="unsupported_type"):
        canonical_bytes({"value": object()})


def test_fast_canonical_digest_lru_caching_and_zero_copy() -> None:
    payload = {
        "manifest_id": "snap-999",
        "actor_user_id": 42,
        "valid_at": datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC),
        "items": [1, 2, {"code": "rx-001"}],
    }

    # Initial computation
    digest_1 = fast_canonical_digest(payload)
    assert digest_1 == consistency_fingerprint(payload)
    assert digest_1 == hashlib.sha256(canonical_bytes(payload)).hexdigest()

    hits_before = _cached_frozen_digest.cache_info().hits
    # Subsequent calls hit LRU cache
    digest_2 = fast_canonical_digest(payload)
    assert digest_2 == digest_1
    assert _cached_frozen_digest.cache_info().hits > hits_before

    # Zero-copy memoryview / bytes handling
    raw_bytes = canonical_bytes(payload)
    mv = memoryview(raw_bytes)
    assert fast_canonical_digest(raw_bytes) == hashlib.sha256(raw_bytes).hexdigest()
    assert fast_canonical_digest(mv) == hashlib.sha256(raw_bytes).hexdigest()


def test_zero_copy_merkle_tree_hashing() -> None:
    # Test on byte chunks and memoryview
    data = b"CLARA-Health-Record-Merkle-Tree-Test-Payload-Zero-Copy" * 200
    mv = memoryview(data)

    root_digest_bytes = zero_copy_merkle_tree_digest(data, chunk_size=64)
    root_digest_mv = zero_copy_merkle_tree_digest(mv, chunk_size=64)
    assert root_digest_bytes == root_digest_mv
    assert len(root_digest_bytes) == 64  # Hex-encoded SHA-256

    # Test alias and structured fast_merkle_digest
    leaves = [
        {"assertion": "rx-1", "dosage": "5mg"},
        {"assertion": "rx-2", "dosage": "10mg"},
        {"assertion": "rx-3", "dosage": "20mg"},
    ]
    merkle_root = fast_merkle_digest(leaves)
    assert isinstance(merkle_root, str) and len(merkle_root) == 64
    assert merkle_tree_digest(leaves) == merkle_root

    # Empty payload handling
    assert zero_copy_merkle_tree_digest(b"") == hashlib.sha256(b"\x00").hexdigest()
    assert zero_copy_merkle_tree_digest([]) == hashlib.sha256(b"\x00").hexdigest()

