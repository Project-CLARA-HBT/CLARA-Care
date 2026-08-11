from __future__ import annotations

from datetime import UTC, datetime

import pytest

from clara_api.glhs.canonical_json import canonical_bytes, consistency_fingerprint


def test_canonical_json_is_key_order_and_unicode_stable() -> None:
    left = {"z": [1, "thuốc"], "a": {"time": datetime(2026, 1, 1, tzinfo=UTC)}}
    right = {"a": {"time": datetime(2026, 1, 1, tzinfo=UTC)}, "z": [1, "thuốc"]}

    assert canonical_bytes(left) == canonical_bytes(right)
    assert consistency_fingerprint(left) == consistency_fingerprint(right)
    assert b"thu\xe1\xbb\x91c" in canonical_bytes(left)


def test_canonical_json_normalizes_negative_zero_and_requires_safe_values() -> None:
    assert canonical_bytes({"value": -0.0}) == b'{"value":0}'
    with pytest.raises(ValueError, match="non_finite"):
        canonical_bytes({"value": float("nan")})
    with pytest.raises(ValueError, match="timezone_required"):
        canonical_bytes({"time": datetime(2026, 1, 1)})
    with pytest.raises(ValueError, match="unsupported_type"):
        canonical_bytes({"value": object()})
