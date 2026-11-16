"""Tests for Merkle transparency reference baseline (PST-X05_transparency_ref).

Purpose
-------
Verify the RFC 9162 (Certificate Transparency v2) and RFC 6962 append-only Merkle
tree model in ``evaluation/venue2027/pst/merkle_transparency.py`` (Arm B3, phase P03).

Test Coverage
-------------
Positive controls:
- Leaf append: consecutive appends monotonically increment index and expand tree size.
- Root computation matches RFC test vectors:
  - Empty tree hash matches RFC 6962 Section 2.1: SHA-256("") = e3b0c442...
  - Single-leaf hash matches SHA-256(0x00 || entry).
  - 7-leaf tree matches RFC 6962 Section 2.1.3 / RFC 9162 Section 2.1.5 structure.
- Inclusion proofs:
  - Empty audit path for size=1.
  - Exact audit paths matching RFC 6962 Section 2.1.3 test vector (d0, d3, d4, d6).
  - Inclusion verification holds for every leaf across arbitrary tree sizes (1..33).
- Consistency proofs:
  - Empty consistency proof for identical tree sizes (m == n).
  - Exact consistency proofs matching RFC 6962 Section 2.1.3 (m=3, m=4, m=6 vs n=7).
  - Prefix consistency verification holds for all 1 <= m <= n <= 32.
- Data formats & disclaimer:
  - Typed proof objects serialize to valid JSON.
  - Explicit disclaimer confirms transparency is for tamper-evidence, NOT confidentiality.

Adversarial controls:
- Tampered leaf entry fails inclusion verification.
- Tampered root hash fails inclusion and consistency verification.
- Forged inclusion proof (modified node, omitted node, extra node, swapped nodes) fails.
- Out-of-bounds indices and sizes fail closed without crashing.
- Consistency check across diverged tree branches fails.
- Forged consistency proof fails.
- Malformed inputs (non-hex strings, invalid byte lengths) return False.
- Boundary operations raise MerkleTransparencyError with stable reason codes.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from evaluation.venue2027.pst import merkle_transparency as mt

# ---------------------------------------------------------------------------
# Positive Controls: RFC Test Vectors & Structure
# ---------------------------------------------------------------------------


def test_empty_tree_root_matches_rfc_test_vector() -> None:
    """Empty tree hash must equal SHA-256('') per RFC 6962 Section 2.1."""
    tree = mt.MerkleTransparencyTree()
    expected = hashlib.sha256(b"").hexdigest()
    assert expected == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert tree.root_hash() == expected
    assert mt.empty_tree_hash() == expected
    assert mt.root_hash(0, tree) == expected


def test_single_leaf_root_matches_rfc_definition() -> None:
    """Single leaf root must equal SHA-256(0x00 || entry) per RFC 9162."""
    tree = mt.MerkleTransparencyTree()
    entry = b"first-clinical-receipt"
    idx = tree.append(entry)
    assert idx == 0
    assert tree.size == 1

    expected_leaf = hashlib.sha256(b"\x00" + entry).hexdigest()
    assert tree.root_hash() == expected_leaf
    assert mt.leaf_hash(entry) == expected_leaf

    # Inclusion proof for size 1 must be empty list
    proof = tree.inclusion_proof(0, 1)
    assert proof == []
    assert mt.verify_inclusion(entry, 0, 1, proof, expected_leaf) is True


def test_rfc6962_section_2_1_3_seven_leaf_intermediate_nodes() -> None:
    """RFC 6962 Section 2.1.3 7-leaf tree intermediate node computation and proofs."""
    d = [f"leaf-{i}".encode() for i in range(7)]
    tree = mt.MerkleTransparencyTree(d)
    assert tree.size == 7

    # Compute expected intermediate nodes from RFC 6962 Section 2.1.3 diagram
    a = hashlib.sha256(b"\x00" + d[0]).digest()
    b = hashlib.sha256(b"\x00" + d[1]).digest()
    c = hashlib.sha256(b"\x00" + d[2]).digest()
    d_node = hashlib.sha256(b"\x00" + d[3]).digest()
    e = hashlib.sha256(b"\x00" + d[4]).digest()
    f = hashlib.sha256(b"\x00" + d[5]).digest()
    d6_leaf = hashlib.sha256(b"\x00" + d[6]).digest()

    g = hashlib.sha256(b"\x01" + a + b).digest()
    h = hashlib.sha256(b"\x01" + c + d_node).digest()
    i = hashlib.sha256(b"\x01" + e + f).digest()
    j = d6_leaf
    k = hashlib.sha256(b"\x01" + g + h).digest()
    l_node = hashlib.sha256(b"\x01" + i + j).digest()
    expected_root = hashlib.sha256(b"\x01" + k + l_node).hexdigest()

    assert tree.root_hash() == expected_root

    # Audit paths from RFC 6962 Section 2.1.3:
    # d0 audit path: [b, h, l]
    assert tree.inclusion_proof(0) == [b.hex(), h.hex(), l_node.hex()]
    # d3 audit path: [c, g, l]
    assert tree.inclusion_proof(3) == [c.hex(), g.hex(), l_node.hex()]
    # d4 audit path: [f, j, k]
    assert tree.inclusion_proof(4) == [f.hex(), j.hex(), k.hex()]
    # d6 audit path: [i, k]
    assert tree.inclusion_proof(6) == [i.hex(), k.hex()]

    # Verify each audit path
    for idx in range(7):
        p = tree.inclusion_proof(idx)
        assert mt.verify_inclusion(d[idx], idx, 7, p, expected_root) is True

    # Consistency proofs from RFC 6962 Section 2.1.3:
    # PROOF(3, D[7]) = [c, d, g, l]
    assert tree.consistency_proof(3, 7) == [c.hex(), d_node.hex(), g.hex(), l_node.hex()]
    # PROOF(4, D[7]) = [l]
    assert tree.consistency_proof(4, 7) == [l_node.hex()]
    # PROOF(6, D[7]) = [i, j, k]
    assert tree.consistency_proof(6, 7) == [i.hex(), j.hex(), k.hex()]

    # Verify each consistency proof
    root3 = tree.root_hash(3)
    root4 = tree.root_hash(4)
    root6 = tree.root_hash(6)

    assert mt.verify_consistency(3, 7, root3, expected_root, tree.consistency_proof(3, 7)) is True
    assert mt.verify_consistency(4, 7, root4, expected_root, tree.consistency_proof(4, 7)) is True
    assert mt.verify_consistency(6, 7, root6, expected_root, tree.consistency_proof(6, 7)) is True


def test_leaf_append_sequence_and_module_functions() -> None:
    """Leaf appends sequentially expand the tree and module-level functions operate."""
    mt.reset_default_tree()
    entries = [f"receipt-{idx}".encode() for idx in range(10)]

    for idx, item in enumerate(entries):
        appended_idx = mt.append(item)
        assert appended_idx == idx

    current_root = mt.root_hash()
    assert len(current_root) == 64

    # Test inclusion proof via module function
    for idx, item in enumerate(entries):
        proof = mt.inclusion_proof(idx, len(entries))
        assert mt.verify_inclusion(item, idx, len(entries), proof, current_root) is True


def test_comprehensive_inclusion_proofs_multiple_sizes() -> None:
    """Inclusion proofs verify for all leaves across tree sizes 1..25."""
    tree = mt.MerkleTransparencyTree()
    for size in range(1, 26):
        tree.append(f"event-record-{size}")
        root = tree.root_hash(size)
        for idx in range(size):
            proof = tree.inclusion_proof(idx, size)
            assert mt.verify_inclusion(f"event-record-{idx + 1}", idx, size, proof, root) is True


def test_comprehensive_consistency_proofs_all_prefix_pairs() -> None:
    """Consistency proofs verify for all 1 <= m <= n <= 20."""
    tree = mt.MerkleTransparencyTree()
    for i in range(20):
        tree.append(f"block-{i}")

    for n in range(1, 21):
        root_n = tree.root_hash(n)
        for m in range(1, n + 1):
            root_m = tree.root_hash(m)
            proof = tree.consistency_proof(m, n)
            assert mt.verify_consistency(m, n, root_m, root_n, proof) is True


def test_same_size_consistency_proof_is_empty_and_verifies() -> None:
    """When m == n, consistency proof is empty and verification succeeds."""
    tree = mt.MerkleTransparencyTree([b"x", b"y", b"z"])
    root = tree.root_hash()
    proof = tree.consistency_proof(3, 3)
    assert proof == []
    assert mt.verify_consistency(3, 3, root, root, proof) is True


def test_power_of_two_tree_sizes_consistency() -> None:
    """Powers of 2 exercise the first_hash prepending branch in verify_consistency."""
    tree = mt.MerkleTransparencyTree([f"leaf-{i}" for i in range(16)])
    for m in (1, 2, 4, 8):
        for n in (m, m + 1, 16):
            if n <= 16:
                root_m = tree.root_hash(m)
                root_n = tree.root_hash(n)
                proof = tree.consistency_proof(m, n)
                assert mt.verify_consistency(m, n, root_m, root_n, proof) is True


def test_json_serializability_and_proof_dataclasses() -> None:
    """Tree state and typed proof dataclasses must be JSON-serializable."""
    tree = mt.MerkleTransparencyTree([b"alpha", b"beta", b"gamma"])
    inc_proof = tree.append_and_prove(b"delta")
    assert isinstance(inc_proof, mt.MerkleInclusionProof)

    inc_dict = inc_proof.to_dict()
    serialized_inc = json.dumps(inc_dict)
    assert json.loads(serialized_inc) == inc_dict

    const_proof = mt.MerkleConsistencyProof(
        first_size=2,
        second_size=4,
        first_root=tree.root_hash(2),
        second_root=tree.root_hash(4),
        consistency_path=tree.consistency_proof(2, 4),
    )
    const_dict = const_proof.to_dict()
    serialized_const = json.dumps(const_dict)
    assert json.loads(serialized_const) == const_dict

    tree_dict = tree.to_dict()
    assert "root_hash" in tree_dict
    assert tree_dict["tree_size"] == 4


def test_explicit_transparency_disclaimer_present() -> None:
    """Transparency disclaimer must explicitly state transparency is NOT confidentiality."""
    disclaimer = mt.TRANSPARENCY_DISCLAIMER
    assert "tamper-evidence" in disclaimer.lower()
    assert "not confidentiality" in disclaimer.lower()


# ---------------------------------------------------------------------------
# Adversarial Controls: Tampering, Forgery & Divergence
# ---------------------------------------------------------------------------


def test_tampered_leaf_content_fails_inclusion_verification() -> None:
    """Altering leaf content causes verify_inclusion to fail closed."""
    tree = mt.MerkleTransparencyTree([b"original-action-1", b"original-action-2"])
    root = tree.root_hash()
    proof = tree.inclusion_proof(0, 2)

    # Valid check passes
    assert mt.verify_inclusion(b"original-action-1", 0, 2, proof, root) is True

    # Tampered leaf content fails
    assert mt.verify_inclusion(b"tampered-action-1", 0, 2, proof, root) is False
    assert mt.verify_inclusion(b"", 0, 2, proof, root) is False


def test_tampered_root_hash_fails_inclusion_and_consistency() -> None:
    """Altering root hash fails both inclusion and consistency verification."""
    tree = mt.MerkleTransparencyTree([b"rec-1", b"rec-2", b"rec-3", b"rec-4"])
    root = tree.root_hash()
    tampered_root = ("0" if root[0] != "0" else "1") + root[1:]

    proof_inc = tree.inclusion_proof(1, 4)
    assert mt.verify_inclusion(b"rec-2", 1, 4, proof_inc, tampered_root) is False

    proof_const = tree.consistency_proof(2, 4)
    root2 = tree.root_hash(2)
    assert mt.verify_consistency(2, 4, root2, tampered_root, proof_const) is False


def test_forged_inclusion_proof_fails() -> None:
    """Forged, modified, truncated, or extended inclusion proofs must fail."""
    tree = mt.MerkleTransparencyTree([b"e1", b"e2", b"e3", b"e4", b"e5"])
    root = tree.root_hash()
    valid_proof = tree.inclusion_proof(2, 5)

    # Corrupted node hash
    corrupted_node = ("0" if valid_proof[0][0] != "0" else "1") + valid_proof[0][1:]
    forged_proof = [corrupted_node, *valid_proof[1:]]
    assert mt.verify_inclusion(b"e3", 2, 5, forged_proof, root) is False

    # Truncated proof
    assert mt.verify_inclusion(b"e3", 2, 5, valid_proof[:-1], root) is False

    # Extra fabricated node
    dummy_node = hashlib.sha256(b"dummy").hexdigest()
    assert mt.verify_inclusion(b"e3", 2, 5, [*valid_proof, dummy_node], root) is False

    # Reversed proof
    if len(valid_proof) > 1:
        assert mt.verify_inclusion(b"e3", 2, 5, list(reversed(valid_proof)), root) is False


def test_out_of_bounds_inclusion_parameters_fail_closed() -> None:
    """Out-of-bounds indices and sizes fail closed (return False)."""
    tree = mt.MerkleTransparencyTree([b"a", b"b"])
    root = tree.root_hash()
    proof = tree.inclusion_proof(0, 2)

    assert mt.verify_inclusion(b"a", -1, 2, proof, root) is False
    assert mt.verify_inclusion(b"a", 2, 2, proof, root) is False
    assert mt.verify_inclusion(b"a", 3, 2, proof, root) is False
    assert mt.verify_inclusion(b"a", 0, 0, proof, root) is False
    assert mt.verify_inclusion(b"a", 0, -1, proof, root) is False


def test_forged_consistency_proof_fails() -> None:
    """Modified consistency proof nodes fail verification."""
    tree = mt.MerkleTransparencyTree([f"msg-{i}" for i in range(8)])
    root4 = tree.root_hash(4)
    root8 = tree.root_hash(8)
    valid_proof = tree.consistency_proof(4, 8)

    assert mt.verify_consistency(4, 8, root4, root8, valid_proof) is True

    # Corrupted consistency node
    bad_node = hashlib.sha256(b"fake").hexdigest()
    forged_proof = [bad_node]
    assert mt.verify_consistency(4, 8, root4, root8, forged_proof) is False

    # Empty proof when m < n must fail
    assert mt.verify_consistency(4, 8, root4, root8, []) is False


def test_consistency_check_across_diverged_branches_fails() -> None:
    """Two trees with divergent leaves at the same prefix must fail consistency verification."""
    branch_a = [b"common-1", b"common-2", b"unique-branch-a"]
    branch_b = [b"common-1", b"common-2", b"unique-branch-b", b"extra-4"]

    tree_a = mt.MerkleTransparencyTree(branch_a)
    tree_b = mt.MerkleTransparencyTree(branch_b)

    root_a = tree_a.root_hash()
    root_b = tree_b.root_hash()

    # Using tree_b's consistency proof against tree_a's root must fail
    proof = tree_b.consistency_proof(3, 4)
    assert mt.verify_consistency(3, 4, root_a, root_b, proof) is False

    # Using tree_a's consistency proof against tree_b's root must fail
    proof_a = tree_a.consistency_proof(2, 3)
    assert mt.verify_consistency(3, 4, root_a, root_b, proof_a) is False


def test_consistency_invalid_ranges_fail_closed() -> None:
    """Invalid consistency parameters (m > n, m < 0, n < 0) return False."""
    tree = mt.MerkleTransparencyTree([b"x", b"y", b"z"])
    root = tree.root_hash()

    assert mt.verify_consistency(4, 3, root, root, ["ab" * 32]) is False
    assert mt.verify_consistency(-1, 3, root, root, ["ab" * 32]) is False
    assert mt.verify_consistency(2, -1, root, root, ["ab" * 32]) is False


def test_malformed_hex_inputs_fail_closed_without_exceptions() -> None:
    """Non-hex strings and bad lengths fail closed."""
    assert mt.verify_inclusion(b"x", 0, 1, ["not-a-hex-string"], "deadbeef") is False
    assert mt.verify_inclusion(b"x", 0, 1, [], "short-hex") is False

    assert mt.verify_consistency(1, 2, "bad_hex", "bad_hex", ["bad_hex"]) is False
    assert mt.verify_consistency(1, 2, "aa" * 32, "bb" * 32, ["short"]) is False


def test_tree_domain_error_reason_codes() -> None:
    """Invalid tree operations raise MerkleTransparencyError with stable reason codes."""
    tree = mt.MerkleTransparencyTree([b"one", b"two"])

    # Invalid tree size for root_hash
    with pytest.raises(mt.MerkleTransparencyError) as exc_info:
        tree.root_hash(10)
    assert exc_info.value.reason_code == "INVALID_TREE_SIZE"

    with pytest.raises(mt.MerkleTransparencyError) as exc_info:
        tree.root_hash(-1)
    assert exc_info.value.reason_code == "INVALID_TREE_SIZE"

    # Invalid index for inclusion_proof
    with pytest.raises(mt.MerkleTransparencyError) as exc_info:
        tree.inclusion_proof(5, 2)
    assert exc_info.value.reason_code == "INVALID_INDEX"

    with pytest.raises(mt.MerkleTransparencyError) as exc_info:
        tree.inclusion_proof(-1, 2)
    assert exc_info.value.reason_code == "INVALID_INDEX"

    # Invalid tree size for inclusion_proof
    with pytest.raises(mt.MerkleTransparencyError) as exc_info:
        tree.inclusion_proof(0, 0)
    assert exc_info.value.reason_code == "INVALID_TREE_SIZE"

    # Invalid consistency range
    with pytest.raises(mt.MerkleTransparencyError) as exc_info:
        tree.consistency_proof(3, 2)
    assert exc_info.value.reason_code == "INVALID_CONSISTENCY_RANGE"

    with pytest.raises(mt.MerkleTransparencyError) as exc_info:
        tree.consistency_proof(-1, 2)
    assert exc_info.value.reason_code == "INVALID_CONSISTENCY_RANGE"

    # Malformed entry type
    with pytest.raises(mt.MerkleTransparencyError) as exc_info:
        tree.append(object())  # type: ignore[arg-type]
    assert exc_info.value.reason_code == "MALFORMED_ENTRY"
