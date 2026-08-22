"""Versioned canonical JSON used for GLHS consistency fingerprints.

Strict RFC 8785 byte-level canonical serialization with deterministic
type dispatch for dataclasses, dates, datetimes, UUIDs, sets, and Decimals.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import uuid
from collections.abc import Mapping, Sequence
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

# Character replacement map for RFC 8785 Section 3.2.2.2 string escaping
_CHAR_REPLACEMENTS = {
    ord('"'): '\\"',
    ord('\\'): '\\\\',
    ord('\b'): '\\b',
    ord('\t'): '\\t',
    ord('\n'): '\\n',
    ord('\f'): '\\f',
    ord('\r'): '\\r',
}
for _i in range(0x20):
    if _i not in _CHAR_REPLACEMENTS:
        _CHAR_REPLACEMENTS[_i] = f"\\u{_i:04x}"


def _serialize_str(s: str) -> str:
    """Serialize string per RFC 8785 strict character escaping rules."""
    return '"' + s.translate(_CHAR_REPLACEMENTS) + '"'


def _utf16_sort_key(s: str) -> bytes:
    """UTF-16 code unit sort key per RFC 8785 Section 3.2.3."""
    if not isinstance(s, str):
        raise TypeError(f"canonical_json_dict_key_must_be_str:{type(s).__name__}")
    return s.encode("utf-16-be")


def _float_to_jcs(val: float) -> str:
    """Format float per RFC 8785 / ECMAScript Number::toString rules."""
    if math.isnan(val) or math.isinf(val):
        raise ValueError("canonical_json_non_finite_number")
    if val == 0.0:
        return "0"
    sign = "-" if math.copysign(1.0, val) < 0 else ""
    val = abs(val)

    s = repr(val)
    if "e" in s:
        mantissa, exp_str = s.split("e")
        exp = int(exp_str)
        if "." in mantissa:
            int_p, frac_p = mantissa.split(".")
            m = (int_p + frac_p).rstrip("0")
            n = len(int_p) + exp
        else:
            m = mantissa.rstrip("0")
            n = len(mantissa) + exp
    else:
        if "." in s:
            int_p, frac_p = s.split(".")
            combined = int_p + frac_p
            stripped = combined.lstrip("0")
            if not stripped:
                return "0"
            first_nz = len(combined) - len(stripped)
            m = stripped.rstrip("0")
            n = len(int_p) - first_nz
        else:
            stripped = s.lstrip("0")
            if not stripped:
                return "0"
            first_nz = len(s) - len(stripped)
            m = stripped.rstrip("0")
            n = len(s) - first_nz

    k = len(m)
    # Section 3.2.2.3 Number Serialization
    if n <= -6 or n > 21:
        e = n - 1
        e_str = str(e)
        if k == 1:
            return f"{sign}{m}e{e_str}"
        return f"{sign}{m[0]}.{m[1:]}e{e_str}"
    if k <= n <= 21:
        return f"{sign}{m}" + "0" * (n - k)
    if 0 < n <= 21:
        return f"{sign}{m[:n]}.{m[n:]}"
    if -6 < n <= 0:
        return f"{sign}0." + "0" * (-n) + m
    raise RuntimeError("Unhandled float serialization state")


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


def _serialize(obj: object) -> str:
    """Recursive RFC 8785 canonical serializer with injective type dispatch."""
    if obj is None:
        return "null"
    if isinstance(obj, bool):
        return "true" if obj else "false"
    if isinstance(obj, int):
        return str(obj)
    if isinstance(obj, float):
        return _float_to_jcs(obj)
    if isinstance(obj, str):
        return _serialize_str(obj)
    if isinstance(obj, (list, tuple)):
        return "[" + ",".join(_serialize(item) for item in obj) + "]"
    if isinstance(obj, (dict, Mapping)):
        sorted_keys = sorted(obj.keys(), key=_utf16_sort_key)
        return "{" + ",".join(f"{_serialize_str(k)}:{_serialize(obj[k])}" for k in sorted_keys) + "}"
    return _serialize(_json_default(obj))


def canonical_json_bytes(payload: object) -> bytes:
    """Strict byte-level canonical JSON serialization per RFC 8785."""
    return _serialize(payload).encode("utf-8")


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
