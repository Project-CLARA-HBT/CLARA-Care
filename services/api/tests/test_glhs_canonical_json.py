from __future__ import annotations

import hashlib
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from clara_api.glhs.canonical_json import (
    canonical_bytes,
    canonical_json_bytes,
    consistency_fingerprint,
    fast_canonical_digest,
    fast_merkle_digest,
    fingerprint_for_profile,
    legacy_consistency_fingerprint,
    merkle_tree_digest,
    zero_copy_merkle_tree_digest,
)


@dataclass
class SampleMedication:
    name: str
    dose_mg: Decimal
    active: bool
    at: datetime


def test_dict_vs_dict_sentinel_collision() -> None:
    """Ensure tuple-encoding artifacts cannot collide with lists or dicts."""
    dict_payload = {"a": 1}
    sentinel_list = ["__dict__", [["a", 1]]]
    assert consistency_fingerprint(dict_payload) != consistency_fingerprint(sentinel_list)

    sentinel_dict = {"__dict__": [["a", 1]]}
    assert consistency_fingerprint(sentinel_dict) != consistency_fingerprint(sentinel_list)
    assert consistency_fingerprint(dict_payload) != consistency_fingerprint(sentinel_dict)


def test_bool_vs_int_collision() -> None:
    """Ensure boolean literals are not conflated with integers 1/0."""
    assert consistency_fingerprint(True) != consistency_fingerprint(1)
    assert consistency_fingerprint(False) != consistency_fingerprint(0)
    assert consistency_fingerprint({"k": True}) != consistency_fingerprint({"k": 1})
    assert consistency_fingerprint({"k": False}) != consistency_fingerprint({"k": 0})
    assert consistency_fingerprint([True]) != consistency_fingerprint([1])


def test_none_vs_empty_string_collision() -> None:
    """Ensure None is strictly distinguished from empty string."""
    assert consistency_fingerprint(None) != consistency_fingerprint("")
    assert consistency_fingerprint({"k": None}) != consistency_fingerprint({"k": ""})
    assert consistency_fingerprint([None]) != consistency_fingerprint([""])


def test_float_vs_string_collision() -> None:
    """Ensure floats are strictly distinguished from their string representations."""
    assert consistency_fingerprint(1.0) != consistency_fingerprint("1.0")
    assert consistency_fingerprint({"k": 1.0}) != consistency_fingerprint({"k": "1.0"})
    assert consistency_fingerprint([42.5]) != consistency_fingerprint(["42.5"])


def test_canonical_json_is_key_order_and_unicode_stable() -> None:
    left = {"z": [1, "thuốc"], "a": {"time": datetime(2026, 1, 1, tzinfo=UTC)}}
    right = {"a": {"time": datetime(2026, 1, 1, tzinfo=UTC)}, "z": [1, "thuốc"]}

    assert canonical_json_bytes(left) == canonical_json_bytes(right)
    assert canonical_bytes(left) == canonical_bytes(right)
    assert consistency_fingerprint(left) == consistency_fingerprint(right)
    assert fast_canonical_digest(left) == consistency_fingerprint(left)
    assert b"thu\xe1\xbb\x91c" in canonical_json_bytes(left)


def test_supported_types_and_safety() -> None:
    # 1. Dataclasses
    med = SampleMedication(
        name="Paracetamol",
        dose_mg=Decimal("500"),
        active=True,
        at=datetime(2026, 8, 22, 10, 0, 0, tzinfo=UTC),
    )
    fp_med = consistency_fingerprint(med)
    assert isinstance(fp_med, str) and len(fp_med) == 64

    # 2. Timezone normalization: UTC vs offset +07:00
    tz_vn = timezone(timedelta(hours=7))
    t1 = datetime(2026, 8, 22, 10, 0, 0, tzinfo=UTC)
    t2 = datetime(2026, 8, 22, 17, 0, 0, tzinfo=tz_vn)
    assert consistency_fingerprint({"time": t1}) == consistency_fingerprint({"time": t2})

    # 3. Dates & UUIDs
    d = date(2026, 8, 22)
    u = uuid.UUID("12345678-1234-5678-1234-567812345678")
    assert consistency_fingerprint({"date": d, "uuid": u}) == consistency_fingerprint(
        {"uuid": u, "date": d}
    )

    # 4. Sets (sorted)
    s1 = {3, 1, 2}
    s2 = {1, 2, 3}
    assert consistency_fingerprint(s1) == consistency_fingerprint(s2)

    # 5. Fail-closed on unsafe / unsupported values
    with pytest.raises(ValueError, match="timezone_required"):
        canonical_json_bytes({"time": datetime(2026, 1, 1)})
    with pytest.raises(ValueError):
        canonical_json_bytes({"value": float("nan")})
    with pytest.raises(ValueError, match="unsupported_type"):
        canonical_json_bytes({"value": object()})


def test_fast_canonical_digest_and_zero_copy() -> None:
    payload = {
        "manifest_id": "snap-999",
        "actor_user_id": 42,
        "valid_at": datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC),
        "items": [1, 2, {"code": "rx-001"}],
    }

    digest_1 = fast_canonical_digest(payload)
    assert digest_1 == consistency_fingerprint(payload)
    assert digest_1 == hashlib.sha256(canonical_bytes(payload)).hexdigest()

    raw_bytes = canonical_bytes(payload)
    mv = memoryview(raw_bytes)
    assert fast_canonical_digest(raw_bytes) == hashlib.sha256(raw_bytes).hexdigest()
    assert fast_canonical_digest(mv) == hashlib.sha256(raw_bytes).hexdigest()


def test_zero_copy_merkle_tree_hashing() -> None:
    data = b"CLARA-Health-Record-Merkle-Tree-Test-Payload-Zero-Copy" * 200
    mv = memoryview(data)

    root_digest_bytes = zero_copy_merkle_tree_digest(data, chunk_size=64)
    root_digest_mv = zero_copy_merkle_tree_digest(mv, chunk_size=64)
    assert root_digest_bytes == root_digest_mv
    assert len(root_digest_bytes) == 64

    leaves = [
        {"assertion": "rx-1", "dosage": "5mg"},
        {"assertion": "rx-2", "dosage": "10mg"},
        {"assertion": "rx-3", "dosage": "20mg"},
    ]
    merkle_root = fast_merkle_digest(leaves)
    assert isinstance(merkle_root, str) and len(merkle_root) == 64
    assert merkle_tree_digest(leaves) == merkle_root

    assert zero_copy_merkle_tree_digest(b"") == hashlib.sha256(b"\x00").hexdigest()
    assert zero_copy_merkle_tree_digest([]) == hashlib.sha256(b"\x00").hexdigest()


def test_profile_dispatch() -> None:
    payload = {"k": "v"}
    fp_v1 = fingerprint_for_profile(payload, profile="clara.canonical-json.v1", algorithm="sha-256")
    assert fp_v1 == consistency_fingerprint(payload)

    fp_leg = fingerprint_for_profile(
        payload, profile="python-json-sort-default-str.v1", algorithm="sha-256"
    )
    assert fp_leg == legacy_consistency_fingerprint(payload)

    with pytest.raises(ValueError, match="unsupported_digest_algorithm"):
        fingerprint_for_profile(payload, profile="clara.canonical-json.v1", algorithm="md5")

    with pytest.raises(ValueError, match="unsupported_canonicalization_profile"):
        fingerprint_for_profile(payload, profile="unknown-v0", algorithm="sha-256")


def test_cross_process_determinism() -> None:
    """Verify fingerprints are strictly deterministic across different Python processes."""
    test_obj = {
        "user_id": 12345,
        "active": True,
        "name": "Bệnh nhân Nguyễn Văn A",
        "iso_date": "2026-08-22T10:30:00+07:00",
        "scores": [1.5, 2.0, 3.25],
        "nested": {"key_b": "val_b", "key_a": "val_a"},
    }
    local_fp = consistency_fingerprint(test_obj)

    code = (
        "import sys, json; "
        "from clara_api.glhs.canonical_json import consistency_fingerprint; "
        f"payload = {repr(test_obj)}; "
        "print(consistency_fingerprint(payload))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    external_fp = proc.stdout.strip()
    assert local_fp == external_fp


def test_nested_structures_zero_collisions() -> None:
    """Verify distinct nested structures have strictly distinct fingerprints."""
    structures = [
        {"k": None},
        {"k": ""},
        {"k": False},
        {"k": 0},
        {"k": 0.5},
        {"k": []},
        {"k": {}},
        {"k": [None]},
        {"k": [""]},
        {"k": [False]},
        {"k": [0]},
        {"k": {"a": 1, "b": 2}},
        {"k": [["a", 1], ["b", 2]]},
        {"k": {"a": [1, 2], "b": {"c": True}}},
        {"k": {"a": [1, 2], "b": {"c": 1}}},
        {"data": [1, [2, 3]]},
        {"data": [[1, 2], 3]},
    ]
    fingerprints = [consistency_fingerprint(s) for s in structures]
    assert len(fingerprints) == len(set(fingerprints)), "Found hash collision in distinct structures!"


def test_rfc8785_number_formatting() -> None:
    """Verify strict RFC 8785 (JCS) number serialization rules."""
    # Negative zero -0.0 and 0.0 -> "0"
    assert canonical_json_bytes(-0.0) == b"0"
    assert canonical_json_bytes(0.0) == b"0"
    assert canonical_json_bytes(0) == b"0"
    assert consistency_fingerprint(-0.0) == consistency_fingerprint(0)
    assert consistency_fingerprint(-0.0) == consistency_fingerprint(0.0)

    # Integers serialized as integers
    assert canonical_json_bytes(42) == b"42"
    assert canonical_json_bytes(-42) == b"-42"
    assert canonical_json_bytes(100000000000000000000) == b"100000000000000000000"

    # Floats with integral values serialize as integers (ECMAScript Number::toString)
    assert canonical_json_bytes(1.0) == b"1"
    assert canonical_json_bytes(-1.0) == b"-1"
    assert consistency_fingerprint(1.0) == consistency_fingerprint(1)
    assert consistency_fingerprint(-1.0) == consistency_fingerprint(-1)

    # Decimal representation for floating point numbers
    assert canonical_json_bytes(1.5) == b"1.5"
    assert canonical_json_bytes(-1.5) == b"-1.5"

    # Exponent boundary conditions (k <= n <= 21 vs n > 21, and -6 < n <= 0 vs n <= -6)
    assert canonical_json_bytes(1e20) == b"100000000000000000000"
    assert canonical_json_bytes(1e21) == b"1e21"
    assert canonical_json_bytes(1e-6) == b"0.000001"
    assert canonical_json_bytes(1e-7) == b"1e-7"
    assert canonical_json_bytes(1.23456789e20) == b"123456789000000000000"
    assert canonical_json_bytes(1.23456789e21) == b"1.23456789e21"
    assert canonical_json_bytes(1.23456789e-6) == b"0.00000123456789"
    assert canonical_json_bytes(1.23456789e-7) == b"1.23456789e-7"
    assert canonical_json_bytes(-1e-7) == b"-1e-7"
    assert canonical_json_bytes(-1e21) == b"-1e21"

    # Exponent notation must use lowercase 'e' and no '+' sign
    out_exp_pos = canonical_json_bytes(1e21)
    assert b"e" in out_exp_pos
    assert b"E" not in out_exp_pos
    assert b"+" not in out_exp_pos

    out_exp_neg = canonical_json_bytes(1e-7)
    assert b"e-" in out_exp_neg
    assert b"E" not in out_exp_neg

    # Nested structures with floats
    assert canonical_json_bytes({"exp": 1e-7}) == b'{"exp":1e-7}'
    assert canonical_json_bytes({"exp": 1e20}) == b'{"exp":100000000000000000000}'
    assert canonical_json_bytes({"zero": -0.0}) == b'{"zero":0}'


def test_rfc8785_utf16_key_sorting() -> None:
    """Verify UTF-16 code unit key sorting per RFC 8785 Section 3.2.3."""
    # Emojis (supplementary characters, surrogate pair [0xD83D, ...]) sort BEFORE \uFFFF (0xFFFF)
    keys_surrogate = {"\uffff": 1, "\U0001f600": 2}
    assert canonical_json_bytes(keys_surrogate) == '{"\U0001f600":2,"\uffff":1}'.encode()

    # Standard ASCII and numeric strings lexicographical sorting
    keys_ascii = {"b": 1, "a": 2, "10": 3, "2": 4}
    assert canonical_json_bytes(keys_ascii) == b'{"10":3,"2":4,"a":2,"b":1}'

    # Unicode keys sorting
    keys_unicode = {"z": 1, "\u00e9": 2, "\u00e8": 3, "\U0001f4a9": 4}
    assert canonical_json_bytes(keys_unicode) == '{"z":1,"\u00e8":3,"\u00e9":2,"\U0001f4a9":4}'.encode()


def test_rfc8785_strict_character_escaping() -> None:
    """Verify RFC 8785 string escaping rules."""
    # Control characters 0x00-0x1F and standard escapes
    raw = "hello\x00world\x1f\b\t\n\f\r\"\\"
    expected = b'"hello\\u0000world\\u001f\\b\\t\\n\\f\\r\\"\\\\"'
    assert canonical_json_bytes(raw) == expected

    # Characters >= 0x20 must NOT be escaped (e.g. forward slash, unicode, emojis)
    url = "https://clara.care/api/v1/patient?id=123&type=phr"
    assert canonical_json_bytes(url) == b'"https://clara.care/api/v1/patient?id=123&type=phr"'

    unicode_str = "Bệnh nhân uống 500mg Paracetamol 💊"
    assert canonical_json_bytes(unicode_str) == '"Bệnh nhân uống 500mg Paracetamol 💊"'.encode()


def test_injective_distinctness() -> None:
    """Verify injective distinction between different types and encodings."""
    # bool vs int vs str
    assert consistency_fingerprint(True) != consistency_fingerprint(1)
    assert consistency_fingerprint(True) != consistency_fingerprint("true")
    assert consistency_fingerprint(False) != consistency_fingerprint(0)
    assert consistency_fingerprint(False) != consistency_fingerprint("false")

    # None vs empty string vs string "null"
    assert consistency_fingerprint(None) != consistency_fingerprint("")
    assert consistency_fingerprint(None) != consistency_fingerprint("null")

    # float vs string
    assert consistency_fingerprint(1.0) != consistency_fingerprint("1.0")
    assert consistency_fingerprint(1.0) != consistency_fingerprint("1")
    assert consistency_fingerprint(1e-7) != consistency_fingerprint("1e-7")
    assert consistency_fingerprint(1e20) != consistency_fingerprint("1e20")

    # list vs dict vs sentinel
    assert consistency_fingerprint([["a", 1]]) != consistency_fingerprint({"a": 1})
    assert consistency_fingerprint(["__dict__", [["a", 1]]]) != consistency_fingerprint({"a": 1})
    assert consistency_fingerprint({"__dict__": [["a", 1]]}) != consistency_fingerprint({"a": 1})


# --- Property-based tests ---

json_primitives = st.none() | st.booleans() | st.integers(min_value=-10000, max_value=10000) | st.text() | st.floats(allow_nan=False, allow_infinity=False)

json_values = st.recursive(
    json_primitives,
    lambda children: st.lists(children, max_size=5) | st.dictionaries(st.text(max_size=10), children, max_size=5),
    max_leaves=25,
)


@given(json_values)
def test_property_determinism(val: object) -> None:
    """Fingerprint must be 100% deterministic on identical input."""
    fp1 = consistency_fingerprint(val)
    fp2 = consistency_fingerprint(val)
    assert fp1 == fp2
    assert len(fp1) == 64


@given(st.dictionaries(st.text(min_size=1, max_size=10), json_primitives, min_size=2, max_size=10))
def test_property_dict_key_order_invariance(d: dict[str, object]) -> None:
    """Dict keys in any order produce identical canonical bytes and fingerprint."""
    shuffled_items = list(d.items())
    import random
    random.seed(42)
    random.shuffle(shuffled_items)
    shuffled_dict = dict(shuffled_items)

    assert canonical_json_bytes(d) == canonical_json_bytes(shuffled_dict)
    assert consistency_fingerprint(d) == consistency_fingerprint(shuffled_dict)


@given(st.lists(json_values, min_size=2, max_size=10, unique_by=lambda x: canonical_json_bytes(x)))
def test_property_distinct_values_have_distinct_fingerprints(values: list[object]) -> None:
    """Distinct inputs produce distinct fingerprints with zero collisions."""
    fps = [consistency_fingerprint(v) for v in values]
    assert len(fps) == len(set(fps))
