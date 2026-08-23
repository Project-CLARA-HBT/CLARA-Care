from __future__ import annotations

import hashlib
import json
import shutil
import struct
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from clara_api.glhs.canonical_json import (
    CANONICALIZATION_PROFILE,
    CANONICALIZATION_PROFILE_V1,
    CANONICALIZATION_PROFILE_V1_CUSTOM,
    CANONICALIZATION_PROFILE_V1_LEGACY_PYTHON,
    CANONICALIZATION_PROFILE_V2,
    LEGACY_CANONICALIZATION_PROFILE,
    PROFILE_V1_CUSTOM,
    PROFILE_V1_LEGACY_PYTHON,
    PROFILE_V2_RFC8785,
    SUPPORTED_PROFILES,
    canonical_bytes,
    canonical_hash,
    canonical_json_bytes,
    canonicalize_json,
    consistency_fingerprint,
    fast_canonical_digest,
    fast_merkle_digest,
    fingerprint_for_profile,
    legacy_consistency_fingerprint,
    merkle_tree_digest,
    resolve_profile,
    zero_copy_merkle_tree_digest,
)

_SURROGATE_CAT: tuple[Literal["Cs"]] = ("Cs",)


@dataclass
class SampleMedication:
    name: str
    dose_mg: Decimal
    active: bool
    at: datetime


# RFC 8785 Table 1: ECMAScript-Compatible JSON Number Serialization Samples (Appendix B)
RFC_8785_APPENDIX_B_VECTORS = [
    ("0000000000000000", "0"),
    ("8000000000000000", "0"),
    ("0000000000000001", "5e-324"),
    ("8000000000000001", "-5e-324"),
    ("7fefffffffffffff", "1.7976931348623157e+308"),
    ("ffefffffffffffff", "-1.7976931348623157e+308"),
    ("4340000000000000", "9007199254740992"),
    ("c340000000000000", "-9007199254740992"),
    ("4430000000000000", "295147905179352830000"),
    ("44b52d02c7e14af5", "9.999999999999997e+22"),
    ("44b52d02c7e14af6", "1e+23"),
    ("44b52d02c7e14af7", "1.0000000000000001e+23"),
    ("444b1ae4d6e2ef4e", "999999999999999700000"),
    ("444b1ae4d6e2ef4f", "999999999999999900000"),
    ("444b1ae4d6e2ef50", "1e+21"),
    ("3eb0c6f7a0b5ed8c", "9.999999999999997e-7"),
    ("3eb0c6f7a0b5ed8d", "0.000001"),
    ("41b3de4355555553", "333333333.3333332"),
    ("41b3de4355555554", "333333333.33333325"),
    ("41b3de4355555555", "333333333.3333333"),
    ("41b3de4355555556", "333333333.3333334"),
    ("41b3de4355555557", "333333333.33333343"),
    ("becbf647612f3696", "-0.0000033333333333333333"),
    ("43143ff3c1cb0959", "1424953923781206.2"),
]


def test_rfc8785_appendix_b_all_vectors() -> None:
    """Verify all 24 IEEE-754 test vectors from RFC 8785 Appendix B."""
    for hex_str, expected in RFC_8785_APPENDIX_B_VECTORS:
        val = struct.unpack("!d", bytes.fromhex(hex_str))[0]
        serialized = canonicalize_json(val, profile=PROFILE_V2_RFC8785)
        assert serialized == expected, f"Failed for {hex_str} (val={val}): expected {expected}, got {serialized}"
        # Byte representation matches UTF-8 of expected
        assert canonical_json_bytes(val, profile=PROFILE_V2_RFC8785) == expected.encode("utf-8")


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
    with pytest.raises(ValueError, match="non_finite_number"):
        canonical_json_bytes({"value": float("nan")})
    with pytest.raises(ValueError, match="non_finite_number"):
        canonical_json_bytes({"value": float("inf")})
    with pytest.raises(ValueError, match="non_finite_number"):
        canonical_json_bytes({"value": float("-inf")})
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


def test_profile_resolution_and_dispatch() -> None:
    """Verify profile resolution for all 3 profiles and legacy aliases."""
    assert resolve_profile(PROFILE_V2_RFC8785) == PROFILE_V2_RFC8785
    assert resolve_profile("clara.canonical-json.v2-rfc8785") == PROFILE_V2_RFC8785
    assert resolve_profile(PROFILE_V1_CUSTOM) == PROFILE_V1_CUSTOM
    assert resolve_profile("clara.canonical-json.v1-custom") == PROFILE_V1_CUSTOM
    assert resolve_profile("clara.canonical-json.v1") == PROFILE_V1_CUSTOM
    assert resolve_profile(PROFILE_V1_LEGACY_PYTHON) == PROFILE_V1_LEGACY_PYTHON
    assert resolve_profile("clara.canonical-json.v1-legacy-python") == PROFILE_V1_LEGACY_PYTHON
    assert resolve_profile("python-json-sort-default-str.v1") == PROFILE_V1_LEGACY_PYTHON

    assert CANONICALIZATION_PROFILE == PROFILE_V2_RFC8785
    assert CANONICALIZATION_PROFILE_V2 == PROFILE_V2_RFC8785
    assert CANONICALIZATION_PROFILE_V1_CUSTOM == PROFILE_V1_CUSTOM
    assert CANONICALIZATION_PROFILE_V1_LEGACY_PYTHON == PROFILE_V1_LEGACY_PYTHON
    assert CANONICALIZATION_PROFILE_V1 == PROFILE_V1_CUSTOM
    assert LEGACY_CANONICALIZATION_PROFILE == PROFILE_V1_LEGACY_PYTHON
    assert SUPPORTED_PROFILES == frozenset([PROFILE_V2_RFC8785, PROFILE_V1_CUSTOM, PROFILE_V1_LEGACY_PYTHON])

    with pytest.raises(ValueError, match="unsupported_canonicalization_profile"):
        resolve_profile("unknown-profile-v9")


def test_profile_dispatch() -> None:
    payload = {"k": "v", "num": 1e21}
    fp_v2 = fingerprint_for_profile(payload, profile="clara.canonical-json.v2-rfc8785", algorithm="sha-256")
    assert fp_v2 == consistency_fingerprint(payload, profile=PROFILE_V2_RFC8785)
    assert fp_v2 == canonical_hash(payload, profile=PROFILE_V2_RFC8785)

    fp_v1_custom = fingerprint_for_profile(payload, profile="clara.canonical-json.v1-custom", algorithm="sha-256")
    assert fp_v1_custom == consistency_fingerprint(payload, profile=PROFILE_V1_CUSTOM)

    fp_v1_alias = fingerprint_for_profile(payload, profile="clara.canonical-json.v1", algorithm="sha-256")
    assert fp_v1_alias == fp_v1_custom

    fp_leg = fingerprint_for_profile(
        payload, profile="clara.canonical-json.v1-legacy-python", algorithm="sha-256"
    )
    assert fp_leg == legacy_consistency_fingerprint(payload)

    fp_leg_alias = fingerprint_for_profile(
        payload, profile="python-json-sort-default-str.v1", algorithm="sha-256"
    )
    assert fp_leg_alias == legacy_consistency_fingerprint(payload)

    # v2 vs v1-custom difference on 1e21 (1e+21 vs 1e21)
    assert fp_v2 != fp_v1_custom
    assert canonicalize_json(payload, profile=PROFILE_V2_RFC8785) == '{"k":"v","num":1e+21}'
    assert canonicalize_json(payload, profile=PROFILE_V1_CUSTOM) == '{"k":"v","num":1e21}'

    with pytest.raises(ValueError, match="unsupported_digest_algorithm"):
        fingerprint_for_profile(payload, profile=PROFILE_V2_RFC8785, algorithm="md5")

    with pytest.raises(ValueError, match="unsupported_digest_algorithm"):
        canonical_hash(payload, algorithm="sha-1")

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
    assert canonical_json_bytes(1e21) == b"1e+21"
    assert canonical_json_bytes(1e30) == b"1e+30"
    assert canonical_json_bytes(1e-6) == b"0.000001"
    assert canonical_json_bytes(1e-7) == b"1e-7"
    assert canonical_json_bytes(1.23456789e20) == b"123456789000000000000"
    assert canonical_json_bytes(1.23456789e21) == b"1.23456789e+21"
    assert canonical_json_bytes(1.23456789e-6) == b"0.00000123456789"
    assert canonical_json_bytes(1.23456789e-7) == b"1.23456789e-7"
    assert canonical_json_bytes(-1e-7) == b"-1e-7"
    assert canonical_json_bytes(-1e21) == b"-1e+21"

    # Positive exponent notation must use lowercase 'e' and '+' sign in v2
    out_exp_pos = canonical_json_bytes(1e21)
    assert b"e+21" in out_exp_pos
    assert b"E" not in out_exp_pos

    out_exp_neg = canonical_json_bytes(1e-7)
    assert b"e-7" in out_exp_neg
    assert b"E" not in out_exp_neg

    # Nested structures with floats
    assert canonical_json_bytes({"exp": 1e-7}) == b'{"exp":1e-7}'
    assert canonical_json_bytes({"exp": 1e20}) == b'{"exp":100000000000000000000}'
    assert canonical_json_bytes({"exp": 1e21}) == b'{"exp":1e+21}'
    assert canonical_json_bytes({"zero": -0.0}) == b'{"zero":0}'

    # Min/max finite IEEE-754 values
    assert canonical_json_bytes(5e-324) == b"5e-324"
    assert canonical_json_bytes(1.7976931348623157e308) == b"1.7976931348623157e+308"


def test_rfc8785_utf16_key_sorting() -> None:
    """Verify UTF-16 code unit key sorting per RFC 8785 Section 3.2.3."""
    # RFC 8785 Section 3.2.3 Official Test Vector
    rfc_vector = {
        "\u20ac": "Euro Sign",
        "\r": "Carriage Return",
        "\ufb33": "Hebrew Letter Dalet With Dagesh",
        "1": "One",
        "\U0001f600": "Emoji: Grinning Face",
        "\u0080": "Control",
        "\u00f6": "Latin Small Letter O With Diaeresis",
    }
    expected_rfc = (
        '{"\\r":"Carriage Return","1":"One","\x80":"Control",'
        '"\xf6":"Latin Small Letter O With Diaeresis","\u20ac":"Euro Sign",'
        '"\U0001f600":"Emoji: Grinning Face","\ufb33":"Hebrew Letter Dalet With Dagesh"}'
    )
    assert canonicalize_json(rfc_vector) == expected_rfc

    # Emojis (supplementary characters, surrogate pair [0xD83D, ...]) sort BEFORE \uFFFF (0xFFFF)
    keys_surrogate = {"\uffff": 1, "\U0001f600": 2}
    assert canonical_json_bytes(keys_surrogate) == '{"\U0001f600":2,"\uffff":1}'.encode()

    # Standard ASCII and numeric strings lexicographical sorting
    keys_ascii = {"b": 1, "a": 2, "10": 3, "2": 4}
    assert canonical_json_bytes(keys_ascii) == b'{"10":3,"2":4,"a":2,"b":1}'

    # Prefix order
    keys_prefix = {"ab": 4, "a": 2, "": 1, "aa": 3}
    assert canonical_json_bytes(keys_prefix) == b'{"":1,"a":2,"aa":3,"ab":4}'

    # Unicode keys sorting
    keys_unicode = {"z": 1, "\u00e9": 2, "\u00e8": 3, "\U0001f4a9": 4}
    assert canonical_json_bytes(keys_unicode) == '{"z":1,"\u00e8":3,"\u00e9":2,"\U0001f4a9":4}'.encode()

    # Dict keys must be strings
    with pytest.raises(TypeError, match="dict_key_must_be_str"):
        canonicalize_json({1: "num_key"})  # type: ignore[dict-item]


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


def test_rfc8785_surrogate_rejection() -> None:
    """Verify strict rejection of lone Unicode surrogates (0xD800 - 0xDFFF)."""
    # Lone high surrogate
    with pytest.raises(ValueError, match="lone_surrogate"):
        canonicalize_json("\ud800")
    with pytest.raises(ValueError, match="lone_surrogate"):
        canonicalize_json("\ud83d")

    # Lone low surrogate
    with pytest.raises(ValueError, match="lone_surrogate"):
        canonicalize_json("\udfff")
    with pytest.raises(ValueError, match="lone_surrogate"):
        canonicalize_json("\ude00")

    # Surrogates in dictionary values
    with pytest.raises(ValueError, match="lone_surrogate"):
        canonicalize_json({"key": "bad_\ud800_val"})

    # Surrogates in dictionary keys
    with pytest.raises(ValueError, match="lone_surrogate"):
        canonicalize_json({"\ud800": "val"})

    # Surrogates in list elements
    with pytest.raises(ValueError, match="lone_surrogate"):
        canonicalize_json(["safe", "\udbff"])


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
    assert consistency_fingerprint(1e20) != consistency_fingerprint("100000000000000000000")

    # list vs dict vs sentinel
    assert consistency_fingerprint([["a", 1]]) != consistency_fingerprint({"a": 1})
    assert consistency_fingerprint(["__dict__", [["a", 1]]]) != consistency_fingerprint({"a": 1})
    assert consistency_fingerprint({"__dict__": [["a", 1]]}) != consistency_fingerprint({"a": 1})


def test_node_differential_parity() -> None:
    """Differential test against Node.js ECMAScript JSON engine if node is available."""
    if not shutil.which("node"):
        pytest.skip("Node.js not installed")

    complex_sample = {
        "numbers": [333333333.33333329, 1e30, 4.5, 0.002, 1e-27, 0.0, -0.0, 1.0, -1.0],
        "string": "€$\x0f\nA'B\"\\\\\"/",
        "literals": [None, True, False],
        "nested": {
            "z": 1,
            "a": 2,
            "10": 3,
            "2": 4,
            "emoji": "💊",
        },
    }

    # RFC 8785 Section 3.2.4 sample bytes check
    section_3_2_2_sample = {
        "numbers": [333333333.33333329, 1e30, 4.5, 0.002, 1e-27],
        "string": "\u20ac$\u000f\u000aA'\u0042\u0022\u005c\\\"/",
        "literals": [None, True, False],
    }
    # Section 3.2.4 hex output in RFC 8785:
    expected_hex = (
        "7b226c69746572616c73223a5b6e756c6c2c7472"
        "75652c66616c73655d2c226e756d62657273223a"
        "5b3333333333333333332e333333333333332c31"
        "652b33302c342e352c302e3030322c31652d3237"
        "5d2c22737472696e67223a22e282ac245c753030"
        "30665c6e4127425c225c5c5c5c5c222f227d"
    )
    assert canonical_json_bytes(section_3_2_2_sample).hex() == expected_hex

    # Run Node.js reference canonicalizer script
    node_script = """
    function canonicalize(object) {
        let buffer = '';
        function serialize(object) {
            if (object === null || typeof object !== 'object' || object.toJSON != null) {
                buffer += JSON.stringify(object);
            } else if (Array.isArray(object)) {
                buffer += '[';
                let next = false;
                object.forEach((element) => {
                    if (next) buffer += ',';
                    next = true;
                    serialize(element);
                });
                buffer += ']';
            } else {
                buffer += '{';
                let next = false;
                const sortedKeys = Object.keys(object).sort((a, b) => {
                    return a < b ? -1 : a > b ? 1 : 0;
                });
                sortedKeys.forEach((property) => {
                    if (next) buffer += ',';
                    next = true;
                    buffer += JSON.stringify(property);
                    buffer += ':';
                    serialize(object[property]);
                });
                buffer += '}';
            }
        }
        serialize(object);
        return buffer;
    }
    let data = '';
    process.stdin.on('data', chunk => data += chunk);
    process.stdin.on('end', () => {
        const input = JSON.parse(data);
        process.stdout.write(canonicalize(input));
    });
    """
    proc = subprocess.run(
        ["node", "-e", node_script],
        input=json.dumps(complex_sample, ensure_ascii=False),
        capture_output=True,
        text=True,
        check=True,
    )
    node_canonical = proc.stdout
    py_canonical = canonicalize_json(complex_sample)
    assert py_canonical == node_canonical


# --- Property-based tests ---

json_primitives = (
    st.none()
    | st.booleans()
    | st.integers(min_value=-10000, max_value=10000)
    | st.text(
        alphabet=st.characters(
            blacklist_categories=_SURROGATE_CAT,  # exclude lone surrogates
        ),
        max_size=20,
    )
    | st.floats(allow_nan=False, allow_infinity=False)
)

json_values = st.recursive(
    json_primitives,
    lambda children: st.lists(children, max_size=4)
    | st.dictionaries(
        st.text(
            alphabet=st.characters(blacklist_categories=_SURROGATE_CAT),
            min_size=1,
            max_size=8,
        ),
        children,
        max_size=4,
    ),
    max_leaves=20,
)


@given(json_values)
def test_property_determinism(val: object) -> None:
    """Fingerprint must be 100% deterministic on identical input."""
    fp1 = consistency_fingerprint(val)
    fp2 = consistency_fingerprint(val)
    assert fp1 == fp2
    assert len(fp1) == 64


@given(
    st.dictionaries(
        st.text(
            alphabet=st.characters(blacklist_categories=_SURROGATE_CAT),
            min_size=1,
            max_size=8,
        ),
        json_primitives,
        min_size=2,
        max_size=8,
    )
)
def test_property_dict_key_order_invariance(d: dict[str, object]) -> None:
    """Dict keys in any order produce identical canonical bytes and fingerprint."""
    shuffled_items = list(d.items())
    import random
    random.seed(42)
    random.shuffle(shuffled_items)
    shuffled_dict = dict(shuffled_items)

    assert canonical_json_bytes(d) == canonical_json_bytes(shuffled_dict)
    assert consistency_fingerprint(d) == consistency_fingerprint(shuffled_dict)


@given(
    st.lists(
        json_values,
        min_size=2,
        max_size=8,
        unique_by=lambda x: canonical_json_bytes(x),
    )
)
def test_property_distinct_values_have_distinct_fingerprints(values: list[object]) -> None:
    """Distinct inputs produce distinct fingerprints with zero collisions."""
    fps = [consistency_fingerprint(v) for v in values]
    assert len(fps) == len(set(fps))


# Restrict primitives to non-float or safe floats for round-trip JSON parsing idempotence
# (JSON numbers like -0.0 re-parse as 0.0 in standard JSON parsers)
json_idempotent_primitives = (
    st.none()
    | st.booleans()
    | st.integers(min_value=-9007199254740991, max_value=9007199254740991)
    | st.text(
        alphabet=st.characters(blacklist_categories=_SURROGATE_CAT),
        max_size=20,
    )
)

json_idempotent_values = st.recursive(
    json_idempotent_primitives,
    lambda children: st.lists(children, max_size=4)
    | st.dictionaries(
        st.text(
            alphabet=st.characters(blacklist_categories=_SURROGATE_CAT),
            min_size=1,
            max_size=8,
        ),
        children,
        max_size=4,
    ),
    max_leaves=20,
)


@given(json_idempotent_values)
def test_property_canonical_parse_idempotence(val: object) -> None:
    """Verify canonicalize(parse(canonicalize(x))) == canonicalize(x) for supported values."""
    c1 = canonicalize_json(val)
    parsed = json.loads(c1)
    c2 = canonicalize_json(parsed)
    assert c1 == c2


def test_exact_decimal_policy() -> None:
    """Verify exact Decimal serialization policy."""
    # Integral Decimal -> int
    assert canonical_json_bytes(Decimal("500")) == b"500"
    assert canonical_json_bytes(Decimal("-42")) == b"-42"
    assert canonical_json_bytes(Decimal("0")) == b"0"
    assert canonical_json_bytes(Decimal("1e21")) == b"1000000000000000000000"

    # Fractional Decimal -> float
    assert canonical_json_bytes(Decimal("1.5")) == b"1.5"
    assert canonical_json_bytes(Decimal("1.234567890123456789")) == canonical_json_bytes(float(Decimal("1.234567890123456789")))

    # Non-finite Decimal -> rejection
    with pytest.raises(ValueError, match="non_finite_number"):
        canonical_json_bytes(Decimal("NaN"))
    with pytest.raises(ValueError, match="non_finite_number"):
        canonical_json_bytes(Decimal("Infinity"))
    with pytest.raises(ValueError, match="non_finite_number"):
        canonical_json_bytes(Decimal("-Infinity"))

