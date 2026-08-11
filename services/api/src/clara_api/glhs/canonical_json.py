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
from datetime import UTC, datetime
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


def consistency_fingerprint(value: object) -> str:
    """Return an unkeyed integrity fingerprint inside the trusted-store model."""

    return hashlib.sha256(canonical_bytes(value)).hexdigest()


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
