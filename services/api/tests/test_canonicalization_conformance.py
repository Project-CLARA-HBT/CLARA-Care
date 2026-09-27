"""Phase 7 (E07): Comprehensive Unit Tests for Canonicalization Conformance.

Verifies strict RFC 8785 byte equality, cross-runtime determinism, and Red Team edge cases.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from clara_api.glhs.canonical_json import (
    MAX_SAFE_INTEGER,
    MIN_SAFE_INTEGER,
    PROFILE_V1_CUSTOM,
    PROFILE_V1_LEGACY_PYTHON,
    PROFILE_V2_RFC8785,
    canonical_bytes,
    canonical_hash,
    canonical_json_bytes,
    canonicalize_json,
    consistency_fingerprint,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_VECTORS_PATH = _REPO_ROOT / "testdata" / "glhs" / "canonicalization" / "v2" / "vectors.json"
_EXPECTED_PATH = _REPO_ROOT / "testdata" / "glhs" / "canonicalization" / "v2" / "expected.json"


def _resolve_input(inp: Any) -> Any:
    if isinstance(inp, dict) and "$type" in inp:
        tag = inp["$type"]
        if tag == "lone_surrogate":
            return chr(int(inp["value"], 16))
        if tag == "non_finite_float":
            val = inp["value"]
            if val == "NaN":
                return float("nan")
            return float("-inf") if val.startswith("-") else float("inf")
        if tag == "unsafe_decimal":
            return Decimal(inp["value"])
        if tag == "integer_overflow":
            return int(inp["value"])
    return inp


def test_testdata_vector_corpus_conformance() -> None:
    """Verify all 35 test vectors in testdata/glhs/canonicalization/v2/ match expected output."""
    assert _VECTORS_PATH.is_file(), f"missing_vectors_file:{_VECTORS_PATH}"
    assert _EXPECTED_PATH.is_file(), f"missing_expected_file:{_EXPECTED_PATH}"

    vectors = json.loads(_VECTORS_PATH.read_text(encoding="utf-8"))
    expected = json.loads(_EXPECTED_PATH.read_text(encoding="utf-8"))
    exp_map = {e["id"]: e for e in expected}

    assert len(vectors) >= 30, f"insufficient_vectors:{len(vectors)}"

    for vec in vectors:
        vid = vec["id"]
        exp = exp_map[vid]
        py_inp = _resolve_input(vec["input"])

        if exp["status"] == "VALID":
            c_str = canonicalize_json(py_inp, profile=PROFILE_V2_RFC8785)
            assert c_str == exp["expected_canonical_json"], f"Vector {vid} string mismatch"
            c_hash = canonical_hash(py_inp, profile=PROFILE_V2_RFC8785)
            assert c_hash == exp["expected_sha256"], f"Vector {vid} hash mismatch"
        else:
            with pytest.raises((ValueError, TypeError)) as exc_info:
                canonicalize_json(py_inp, profile=PROFILE_V2_RFC8785)
            assert exp["expected_error"] in str(exc_info.value), f"Vector {vid} error mismatch"


def test_node_cross_runtime_parity() -> None:
    """Run Node.js cross-runtime validator script and assert 100% byte equality."""
    if not shutil.which("node"):
        pytest.skip("Node.js not installed")

    node_script = _REPO_ROOT / "evaluation" / "canonicalization" / "verify_node_rfc8785.js"
    assert node_script.is_file(), f"missing_node_script:{node_script}"

    cmd = [
        "node",
        str(node_script),
        f"--vectors={_VECTORS_PATH}",
        f"--expected={_EXPECTED_PATH}",
        "--json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"Node verification failed:\n{proc.stderr or proc.stdout}"

    report = json.loads(proc.stdout)
    assert report["passed"] == report["total_vectors"]
    assert report["byte_equality_rate"] == 1.0
    assert report["cross_runtime_determinism"] is True


# --- Red Team Edge Case Audit Tests ---

def test_red_team_utf16_vs_utf8_vs_python_str_sorting() -> None:
    """Audit Red Team Case 1: UTF-16 code unit ordering vs UTF-8 byte order vs Python str order.

    Astral character U+1F600 (😀) has UTF-16 representation [0xD83D, 0xDE00].
    PUA character U+E000 has UTF-16 representation [0xE000].
    Unicode 0xFFFF has UTF-16 representation [0xFFFF].

    Order comparisons:
    - Python string ord(): ord('\U0001f600') = 128512 > ord('\ue000') = 57344. (Puts \ue000 FIRST)
    - UTF-8 bytes: '\U0001f600' -> b'\xf0\x9f\x98\x80' (starts with 0xF0) > '\ue000' -> b'\xe0\x80\x80' (starts with 0xE0). (Puts \ue000 FIRST)
    - RFC 8785 UTF-16 code units: 0xD83D < 0xE000. (Puts \U0001f600 FIRST!)

    Our implementation must strictly put U+1F600 BEFORE U+E000 and U+FFFF!
    """
    dict_pua = {"\ue000": 1, "\U0001f600": 2}
    c_pua = canonicalize_json(dict_pua)
    assert c_pua == '{"\U0001f600":2,"\ue000":1}'

    dict_ffff = {"\uffff": 1, "\U0001f600": 2}
    c_ffff = canonicalize_json(dict_ffff)
    assert c_ffff == '{"\U0001f600":2,"\uffff":1}'


def test_red_team_negative_zero_handling() -> None:
    """Audit Red Team Case 2: Negative floating point zero (-0.0) handling.

    -0.0 must be normalized to '0' per RFC 8785 Section 3.2.2.3.
    Must produce identical fingerprints for -0.0, 0.0, and integer 0.
    """
    assert canonical_json_bytes(-0.0) == b"0"
    assert canonical_json_bytes(0.0) == b"0"
    assert canonical_json_bytes(0) == b"0"

    fp_neg_zero = consistency_fingerprint(-0.0)
    fp_pos_zero = consistency_fingerprint(0.0)
    fp_int_zero = consistency_fingerprint(0)

    assert fp_neg_zero == fp_pos_zero == fp_int_zero
    assert canonicalize_json({"zero": -0.0}) == '{"zero":0}'


def test_red_team_lone_surrogate_rejection() -> None:
    """Audit Red Team Case 3: Lone surrogate rejection in Python.

    Unpaired surrogate code points (0xD800 - 0xDFFF) must be rejected with ValueError.
    """
    with pytest.raises(ValueError, match="lone_surrogate"):
        canonicalize_json("\ud800")

    with pytest.raises(ValueError, match="lone_surrogate"):
        canonicalize_json("\udfff")

    with pytest.raises(ValueError, match="lone_surrogate"):
        canonicalize_json({"key": "bad_\ud800_str"})


def test_red_team_ijson_integer_range_rejection() -> None:
    """Audit Red Team Case 4: I-JSON safe integer range enforcement under v2 profile."""
    # Boundary values pass
    assert canonicalize_json(MIN_SAFE_INTEGER) == str(MIN_SAFE_INTEGER)
    assert canonicalize_json(MAX_SAFE_INTEGER) == str(MAX_SAFE_INTEGER)

    # Overflow values fail under v2
    with pytest.raises(ValueError, match="canonical_json_integer_out_of_ijson_range"):
        canonicalize_json(MAX_SAFE_INTEGER + 1, profile=PROFILE_V2_RFC8785)

    with pytest.raises(ValueError, match="canonical_json_integer_out_of_ijson_range"):
        canonicalize_json(MIN_SAFE_INTEGER - 1, profile=PROFILE_V2_RFC8785)

    # Overflow values pass under legacy profiles
    assert canonicalize_json(MAX_SAFE_INTEGER + 1, profile=PROFILE_V1_CUSTOM) == str(MAX_SAFE_INTEGER + 1)
    assert canonicalize_json(MAX_SAFE_INTEGER + 1, profile=PROFILE_V1_LEGACY_PYTHON) == str(MAX_SAFE_INTEGER + 1)


def test_red_team_unsafe_decimal_rejection() -> None:
    """Audit Red Team Case 5: Lossy Decimal precision rejection under v2 profile."""
    # High precision Decimal that cannot be losslessly represented as IEEE-754 float
    lossy_decimal = Decimal("1.234567890123456789")
    with pytest.raises(ValueError, match="canonical_json_unsafe_decimal_precision"):
        canonicalize_json(lossy_decimal, profile=PROFILE_V2_RFC8785)

    # Out of range Decimal
    large_decimal = Decimal("9007199254740992")
    with pytest.raises(ValueError, match="canonical_json_unsafe_decimal_precision"):
        canonicalize_json(large_decimal, profile=PROFILE_V2_RFC8785)
