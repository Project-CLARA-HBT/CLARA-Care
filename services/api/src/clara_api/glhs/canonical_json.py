"""Versioned canonical JSON used for GLHS consistency fingerprints.

Strict RFC 8785 byte-level canonical serialization with deterministic
type dispatch for dataclasses, dates, datetimes, UUIDs, sets, and Decimals.
Supports cryptographic profiles:
- 'clara.canonical-json.v1-legacy-python': historical Python json.dumps semantics
- 'clara.canonical-json.v1-custom': frozen custom JCS-like serializer (no '+' exponent)
- 'clara.canonical-json.v2-rfc8785': strict RFC 8785 canonical JSON (default for new writes)
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

MIN_SAFE_INTEGER: int = -9007199254740991  # -(2**53 - 1)
MAX_SAFE_INTEGER: int = 9007199254740991   # 2**53 - 1

DIGEST_ALGORITHM = "sha-256"

PROFILE_V1_LEGACY_PYTHON = "clara.canonical-json.v1-legacy-python"
PROFILE_V1_CUSTOM = "clara.canonical-json.v1-custom"
PROFILE_V2_RFC8785 = "clara.canonical-json.v2-rfc8785"

CANONICALIZATION_PROFILE = PROFILE_V2_RFC8785
CANONICALIZATION_PROFILE_V2 = PROFILE_V2_RFC8785
CANONICALIZATION_PROFILE_V1_CUSTOM = PROFILE_V1_CUSTOM
CANONICALIZATION_PROFILE_V1_LEGACY_PYTHON = PROFILE_V1_LEGACY_PYTHON

# Backward compatibility / legacy aliases
LEGACY_CANONICALIZATION_PROFILE = PROFILE_V1_LEGACY_PYTHON
CANONICALIZATION_PROFILE_V1 = PROFILE_V1_CUSTOM

_PROFILE_ALIASES: dict[str, str] = {
    PROFILE_V2_RFC8785: PROFILE_V2_RFC8785,
    "glhs.canonical.v2": PROFILE_V2_RFC8785,
    "glhs.v2": PROFILE_V2_RFC8785,
    PROFILE_V1_CUSTOM: PROFILE_V1_CUSTOM,
    "clara.canonical-json.v1": PROFILE_V1_CUSTOM,
    "glhs.canonical.v1": PROFILE_V1_CUSTOM,
    "glhs.v1": PROFILE_V1_CUSTOM,
    PROFILE_V1_LEGACY_PYTHON: PROFILE_V1_LEGACY_PYTHON,
    "python-json-sort-default-str.v1": PROFILE_V1_LEGACY_PYTHON,
}

SUPPORTED_PROFILES: frozenset[str] = frozenset([
    PROFILE_V2_RFC8785,
    PROFILE_V1_CUSTOM,
    PROFILE_V1_LEGACY_PYTHON,
])


def resolve_profile(profile: str) -> str:
    """Resolve profile name or alias to canonical profile identifier."""
    resolved = _PROFILE_ALIASES.get(profile)
    if resolved is None:
        raise ValueError(f"unsupported_canonicalization_profile:{profile}")
    return resolved


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
    """Serialize string per RFC 8785 strict character escaping rules.

    Rejects lone surrogates (0xD800 - 0xDFFF) per RFC 8785 and I-JSON (RFC 7493).
    """
    for ch in s:
        if 0xD800 <= ord(ch) <= 0xDFFF:
            raise ValueError(f"canonical_json_lone_surrogate: U+{ord(ch):04X}")
    return '"' + s.translate(_CHAR_REPLACEMENTS) + '"'


def _utf16_sort_key(s: str) -> bytes:
    """UTF-16 code unit sort key per RFC 8785 Section 3.2.3.

    Rejects lone surrogates and non-string keys.
    """
    if not isinstance(s, str):
        raise TypeError(f"canonical_json_dict_key_must_be_str:{type(s).__name__}")
    for ch in s:
        if 0xD800 <= ord(ch) <= 0xDFFF:
            raise ValueError(f"canonical_json_lone_surrogate: U+{ord(ch):04X}")
    return s.encode("utf-16-be")


def _float_to_jcs(val: float, *, positive_exp_sign: bool = True) -> str:
    """Format float per RFC 8785 / ECMAScript Number::toString rules.

    If positive_exp_sign is True (v2 RFC 8785), positive exponents include '+', e.g. 1e+21.
    If positive_exp_sign is False (v1 custom), positive exponents omit '+', e.g. 1e21.
    """
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
        exp_sign = "+" if (positive_exp_sign and e >= 0) else ""
        e_str = f"{exp_sign}{e}"
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


def _json_default(obj: object, *, profile: str = PROFILE_V2_RFC8785) -> object:
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
            return sorted(obj, key=lambda x: canonical_json_bytes(x, profile=profile))
    if isinstance(obj, Decimal):
        if not obj.is_finite():
            raise ValueError("canonical_json_non_finite_number")
        if profile == PROFILE_V2_RFC8785:
            if obj < Decimal(MIN_SAFE_INTEGER) or obj > Decimal(MAX_SAFE_INTEGER):
                raise ValueError("canonical_json_unsafe_decimal_precision")
            if obj == obj.to_integral_value():
                return int(obj)
            try:
                f = float(obj)
            except OverflowError:
                raise ValueError("canonical_json_unsafe_decimal_precision") from None
            jcs = _float_to_jcs(f, positive_exp_sign=True)
            if Decimal(jcs) != obj:
                raise ValueError("canonical_json_unsafe_decimal_precision")
            return f
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


def _serialize(obj: object, *, profile: str = PROFILE_V2_RFC8785) -> str:
    """Recursive canonical serializer with injective type dispatch."""
    if obj is None:
        return "null"
    if isinstance(obj, bool):
        return "true" if obj else "false"
    if isinstance(obj, int):
        if profile == PROFILE_V2_RFC8785:
            if obj < MIN_SAFE_INTEGER or obj > MAX_SAFE_INTEGER:
                raise ValueError("canonical_json_integer_out_of_ijson_range")
        return str(obj)
    if isinstance(obj, float):
        positive_exp = profile == PROFILE_V2_RFC8785
        return _float_to_jcs(obj, positive_exp_sign=positive_exp)
    if isinstance(obj, str):
        return _serialize_str(obj)
    if isinstance(obj, (list, tuple)):
        return "[" + ",".join(_serialize(item, profile=profile) for item in obj) + "]"
    if isinstance(obj, (dict, Mapping)):
        sorted_keys = sorted(obj.keys(), key=_utf16_sort_key)
        return (
            "{"
            + ",".join(
                f"{_serialize_str(k)}:{_serialize(obj[k], profile=profile)}"
                for k in sorted_keys
            )
            + "}"
        )
    return _serialize(_json_default(obj, profile=profile), profile=profile)


def canonicalize_json(payload: object, *, profile: str = CANONICALIZATION_PROFILE) -> str:
    """Serialize payload to canonical JSON string under specified profile."""
    resolved = resolve_profile(profile)
    if resolved == PROFILE_V1_LEGACY_PYTHON:
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    return _serialize(payload, profile=resolved)


def canonical_json_bytes(payload: object, *, profile: str = CANONICALIZATION_PROFILE) -> bytes:
    """Strict byte-level canonical JSON serialization per specified profile."""
    return canonicalize_json(payload, profile=profile).encode("utf-8")


canonical_bytes = canonical_json_bytes


def canonical_hash(
    payload: object,
    *,
    profile: str = CANONICALIZATION_PROFILE,
    algorithm: str = DIGEST_ALGORITHM,
) -> str:
    """Compute cryptographic digest of canonically serialized payload."""
    if algorithm != DIGEST_ALGORITHM:
        raise ValueError(f"unsupported_digest_algorithm:{algorithm}")
    return hashlib.sha256(canonical_json_bytes(payload, profile=profile)).hexdigest()


def consistency_fingerprint(
    payload: object,
    *,
    profile: str = CANONICALIZATION_PROFILE,
) -> str:
    """Return SHA-256 consistency fingerprint for payload."""
    return canonical_hash(payload, profile=profile, algorithm=DIGEST_ALGORITHM)


def fast_canonical_digest(
    value: object,
    *,
    profile: str = CANONICALIZATION_PROFILE,
) -> str:
    """Return SHA-256 consistency fingerprint (zero-copy for bytes/memoryview)."""
    if isinstance(value, (bytes, bytearray, memoryview)):
        return hashlib.sha256(memoryview(value)).hexdigest()
    return consistency_fingerprint(value, profile=profile)


def zero_copy_merkle_tree_digest(
    data: bytes | bytearray | memoryview | Sequence[bytes | memoryview | str | object],
    *,
    chunk_size: int = 4096,
    profile: str = CANONICALIZATION_PROFILE,
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
                b = canonical_json_bytes(item, profile=profile)
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
fast_merkle_digest = zero_copy_merkle_tree_digest


def legacy_consistency_fingerprint(value: object) -> str:
    """Reproduce the pre-versioned digest for historical snapshot validation."""
    return consistency_fingerprint(value, profile=PROFILE_V1_LEGACY_PYTHON)


def fingerprint_for_profile(
    value: object,
    *,
    profile: str,
    algorithm: str = DIGEST_ALGORITHM,
) -> str:
    """Validate profile and return digest accordingly."""
    if algorithm != DIGEST_ALGORITHM:
        raise ValueError("unsupported_digest_algorithm")
    resolved = resolve_profile(profile)
    return consistency_fingerprint(value, profile=resolved)

