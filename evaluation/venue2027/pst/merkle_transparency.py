"""PST-X05_transparency_ref — Merkle transparency reference baseline.

Purpose
-------
Reference implementation of the Certificate Transparency (RFC 9162 / RFC 6962)
append-only Merkle tree integrity baseline for the PST 2027 study
"ReceiptMin: Measuring Forensic Reconstructability under Purpose-Bound Audit Minimization"
(``research/venue2027/VENUES/pst/RESEARCH_BLUEPRINT.md`` Arm B3; task contract
``research/venue2027/VENUES/pst/TASKS/PST-X05_transparency_ref.md``, phase P03).

Security and Confidentiality Disclaimer
---------------------------------------
CRITICAL: Transparency != Confidentiality.
An immutable, append-only Merkle tree guarantees PUBLIC TAMPER-EVIDENCE and
NON-REPUDIATION through inclusion and consistency proofs against a witnessed root.
It does NOT provide confidentiality, secrecy, redaction, or access control.
Never equate a public immutable hash tree with encrypted secrecy or audit
minimization. Retention decay and privacy require cryptographic key management
and purpose-bound minimization (ReceiptMin), not public tree append alone.

Algorithm & Formal Specification
--------------------------------
Aligned with RFC 9162 (Certificate Transparency v2) Section 2.1 and RFC 6962 Section 2.1:
- Hash algorithm: SHA-256.
- Leaf node hash: SHA-256(0x00 || entry).
- Interior node hash: SHA-256(0x01 || left || right).
- Empty tree hash: SHA-256("") = e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.
- Subtree split: for tree size n > 1, k = 1 << ((n - 1).bit_length() - 1),
  the largest power of 2 strictly less than n.
- Inclusion proof (audit path): PATH(m, D_n) per RFC 9162 Section 2.1.3.1.
- Consistency proof: PROOF(m, D_n) = SUBPROOF(m, D_n, True) per RFC 9162 Section 2.1.4.1.
- Inclusion verification: iteratively verifies candidate leaf against tree head
  per RFC 9162 Section 2.1.3.2.
- Consistency verification: iteratively verifies prefix consistency between two
  tree heads per RFC 9162 Section 2.1.4.2.

Allowed Input
-------------
Entries as bytes or str (or JSON-serializable dict/list converted to canonical bytes).
Zero-indexed integer positions. 64-character lowercase or uppercase hex digest strings.
No network, no database, no hidden clock, no random state.

Failure Semantics
-----------------
Refusals raise :class:`MerkleTransparencyError` with a stable uppercase reason code
(``INVALID_INDEX``, ``INVALID_TREE_SIZE``, ``INVALID_CONSISTENCY_RANGE``,
``MALFORMED_ENTRY``, ``MALFORMED_PROOF``, ``MALFORMED_ROOT``).
Verification functions return ``False`` on invalid inputs, tampered data, forged
proofs, or tree divergence, failing closed without unhandled exceptions.

Version
-------
``MERKLE_TRANSPARENCY_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Sequence
from typing import Any, Final, Literal

MERKLE_TRANSPARENCY_VERSION: Final[str] = "1.0.0"

TRANSPARENCY_DISCLAIMER: Final[str] = (
    "An immutable public Merkle tree provides append-only tamper-evidence and "
    "non-repudiation; it does NOT provide confidentiality or encryption of logged "
    "data. Transparency is for public tamper-evidence, NOT confidentiality."
)

EMPTY_TREE_HASH: Final[str] = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

ReasonCode = Literal[
    "INVALID_INDEX",
    "INVALID_TREE_SIZE",
    "INVALID_CONSISTENCY_RANGE",
    "MALFORMED_ENTRY",
    "MALFORMED_PROOF",
    "MALFORMED_ROOT",
]


class MerkleTransparencyError(ValueError):
    """Domain error for Merkle transparency operations with stable reason code."""

    def __init__(self, reason_code: ReasonCode, message: str = "") -> None:
        self.reason_code: ReasonCode = reason_code
        super().__init__(message or reason_code)


@dataclasses.dataclass(frozen=True)
class MerkleInclusionProof:
    """Typed JSON-serializable Merkle inclusion proof."""

    leaf_index: int
    tree_size: int
    leaf_hash: str
    root_hash: str
    audit_path: list[str]
    disclaimer: str = TRANSPARENCY_DISCLAIMER

    def to_dict(self) -> dict[str, Any]:
        return {
            "leaf_index": self.leaf_index,
            "tree_size": self.tree_size,
            "leaf_hash": self.leaf_hash,
            "root_hash": self.root_hash,
            "audit_path": list(self.audit_path),
            "disclaimer": self.disclaimer,
        }


@dataclasses.dataclass(frozen=True)
class MerkleConsistencyProof:
    """Typed JSON-serializable Merkle consistency proof."""

    first_size: int
    second_size: int
    first_root: str
    second_root: str
    consistency_path: list[str]
    disclaimer: str = TRANSPARENCY_DISCLAIMER

    def to_dict(self) -> dict[str, Any]:
        return {
            "first_size": self.first_size,
            "second_size": self.second_size,
            "first_root": self.first_root,
            "second_root": self.second_root,
            "consistency_path": list(self.consistency_path),
            "disclaimer": self.disclaimer,
        }


def _normalize_entry(entry: bytes | str | dict[str, Any] | Sequence[Any]) -> bytes:
    """Normalize input entry to bytes."""
    if isinstance(entry, bytes):
        return entry
    if isinstance(entry, str):
        return entry.encode("utf-8")
    if isinstance(entry, dict | list | tuple):
        return json.dumps(entry, sort_keys=True, separators=(",", ":")).encode("utf-8")
    raise MerkleTransparencyError(
        "MALFORMED_ENTRY",
        f"Entry must be bytes, str, or JSON-serializable structure, got {type(entry).__name__}",
    )


def leaf_hash(entry: bytes | str) -> str:
    """Compute leaf hash per RFC 9162 Section 2.1.1: HASH(0x00 || entry)."""
    raw = _normalize_entry(entry)
    return hashlib.sha256(b"\x00" + raw).hexdigest()


def interior_hash(left: str | bytes, right: str | bytes) -> str:
    """Compute interior node hash per RFC 9162 Section 2.1.1: HASH(0x01 || left || right)."""
    left_bytes = bytes.fromhex(left) if isinstance(left, str) else left
    right_bytes = bytes.fromhex(right) if isinstance(right, str) else right
    if len(left_bytes) != 32 or len(right_bytes) != 32:
        raise MerkleTransparencyError(
            "MALFORMED_ROOT", "Interior node child hashes must be 32 bytes"
        )
    return hashlib.sha256(b"\x01" + left_bytes + right_bytes).hexdigest()


def empty_tree_hash() -> str:
    """Return empty tree root hash per RFC 9162: HASH("")."""
    return EMPTY_TREE_HASH


def _leaf_digest(raw: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + raw).digest()


def _node_digest(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


def _mth(leaves: Sequence[bytes]) -> bytes:
    """Compute Merkle Tree Hash over list of leaf digests."""
    n = len(leaves)
    if n == 0:
        return hashlib.sha256(b"").digest()
    if n == 1:
        return leaves[0]
    k = 1 << ((n - 1).bit_length() - 1)
    return _node_digest(_mth(leaves[:k]), _mth(leaves[k:]))


def _path(m: int, leaves: Sequence[bytes]) -> list[bytes]:
    """Compute Merkle audit path PATH(m, D_n) per RFC 9162 Section 2.1.3.1."""
    n = len(leaves)
    if n == 1 and m == 0:
        return []
    k = 1 << ((n - 1).bit_length() - 1)
    if m < k:
        return _path(m, leaves[:k]) + [_mth(leaves[k:])]
    else:
        return _path(m - k, leaves[k:]) + [_mth(leaves[:k])]


def _subproof(m: int, leaves: Sequence[bytes], b: bool) -> list[bytes]:
    """Compute SUBPROOF(m, D_n, b) per RFC 9162 Section 2.1.4.1."""
    n = len(leaves)
    if m == n:
        if b:
            return []
        else:
            return [_mth(leaves)]
    k = 1 << ((n - 1).bit_length() - 1)
    if m <= k:
        return _subproof(m, leaves[:k], b) + [_mth(leaves[k:])]
    else:
        return _subproof(m - k, leaves[k:], False) + [_mth(leaves[:k])]


def _consistency_proof(m: int, leaves: Sequence[bytes]) -> list[bytes]:
    """Compute Merkle consistency proof PROOF(m, D_n) per RFC 9162 Section 2.1.4.1."""
    n = len(leaves)
    if m == n:
        return []
    return _subproof(m, leaves, True)


class MerkleTransparencyTree:
    """Append-only Merkle tree adhering to RFC 9162 and RFC 6962."""

    def __init__(self, entries: Sequence[bytes | str] | None = None) -> None:
        self._entries: list[bytes] = []
        self._leaf_hashes: list[bytes] = []
        if entries:
            for e in entries:
                self.append(e)

    def append(self, entry: bytes | str) -> int:
        """Append an entry to the Merkle tree and return its 0-based leaf index."""
        raw = _normalize_entry(entry)
        leaf = _leaf_digest(raw)
        idx = len(self._entries)
        self._entries.append(raw)
        self._leaf_hashes.append(leaf)
        return idx

    def root_hash(self, size: int | None = None) -> str:
        """Compute the Merkle Tree Hash for the tree prefix of length size."""
        target_size = len(self._leaf_hashes) if size is None else size
        if target_size < 0 or target_size > len(self._leaf_hashes):
            raise MerkleTransparencyError(
                "INVALID_TREE_SIZE",
                f"Size {target_size} out of range [0, {len(self._leaf_hashes)}]",
            )
        return _mth(self._leaf_hashes[:target_size]).hex()

    def inclusion_proof(self, index: int, size: int | None = None) -> list[str]:
        """Compute inclusion proof (audit path) for leaf at index in tree of size."""
        target_size = len(self._leaf_hashes) if size is None else size
        if target_size <= 0 or target_size > len(self._leaf_hashes):
            raise MerkleTransparencyError(
                "INVALID_TREE_SIZE",
                f"Size {target_size} invalid for inclusion proof (current={len(self._leaf_hashes)})",
            )
        if index < 0 or index >= target_size:
            raise MerkleTransparencyError(
                "INVALID_INDEX",
                f"Index {index} out of range [0, {target_size})",
            )
        proof = _path(index, self._leaf_hashes[:target_size])
        return [p.hex() for p in proof]

    def consistency_proof(self, m: int, n: int | None = None) -> list[str]:
        """Compute consistency proof between tree sizes m and n."""
        target_n = len(self._leaf_hashes) if n is None else n
        if m < 0 or m > target_n or target_n > len(self._leaf_hashes):
            raise MerkleTransparencyError(
                "INVALID_CONSISTENCY_RANGE",
                f"Consistency range m={m}, n={target_n} invalid for tree size {len(self._leaf_hashes)}",
            )
        if m == 0 or m == target_n:
            return []
        proof = _consistency_proof(m, self._leaf_hashes[:target_n])
        return [p.hex() for p in proof]

    def append_and_prove(self, entry: bytes | str) -> MerkleInclusionProof:
        """Append an entry and return the inclusion proof against the resulting tree head."""
        idx = self.append(entry)
        tree_sz = len(self._entries)
        rt = self.root_hash(tree_sz)
        path = self.inclusion_proof(idx, tree_sz)
        lf = self._leaf_hashes[idx].hex()
        return MerkleInclusionProof(
            leaf_index=idx,
            tree_size=tree_sz,
            leaf_hash=lf,
            root_hash=rt,
            audit_path=path,
        )

    @property
    def size(self) -> int:
        """Current number of entries in the tree."""
        return len(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serializable summary of the tree."""
        return {
            "version": MERKLE_TRANSPARENCY_VERSION,
            "tree_size": self.size,
            "root_hash": self.root_hash(),
            "disclaimer": TRANSPARENCY_DISCLAIMER,
        }


# Type alias
MerkleTree = MerkleTransparencyTree

# Module default tree instance
_DEFAULT_TREE: MerkleTransparencyTree = MerkleTransparencyTree()


def reset_default_tree() -> None:
    """Reset the module-level default tree."""
    global _DEFAULT_TREE
    _DEFAULT_TREE = MerkleTransparencyTree()


def append(
    entry: bytes | str,
    tree: MerkleTransparencyTree | None = None,
) -> int:
    """Append entry to tree (default module tree if None). Returns 0-based leaf index."""
    target_tree = _DEFAULT_TREE if tree is None else tree
    return target_tree.append(entry)


def root_hash(
    size: int | None = None,
    tree: MerkleTransparencyTree | None = None,
) -> str:
    """Return root hash for tree (default module tree if None)."""
    target_tree = _DEFAULT_TREE if tree is None else tree
    return target_tree.root_hash(size)


def inclusion_proof(
    index: int,
    size: int | None = None,
    tree: MerkleTransparencyTree | None = None,
) -> list[str]:
    """Generate inclusion proof for leaf at index in tree of size."""
    target_tree = _DEFAULT_TREE if tree is None else tree
    return target_tree.inclusion_proof(index, size)


def consistency_proof(
    m: int,
    n: int | None = None,
    tree: MerkleTransparencyTree | None = None,
) -> list[str]:
    """Generate consistency proof between sizes m and n."""
    target_tree = _DEFAULT_TREE if tree is None else tree
    return target_tree.consistency_proof(m, n)


def verify_inclusion(
    entry: bytes | str,
    index: int,
    size: int,
    proof: Sequence[str],
    root: str,
) -> bool:
    """Verify inclusion of entry at 0-based index in tree of size against root.

    Aligned with RFC 9162 Section 2.1.3.2. Fails closed (returns False) on any
    tampering, malformed value, forged node, or out-of-bounds parameter.
    """
    if not isinstance(index, int) or not isinstance(size, int):
        return False
    if index < 0 or size <= 0 or index >= size:
        return False

    try:
        root_bytes = bytes.fromhex(root)
        proof_bytes = [bytes.fromhex(p) for p in proof]
    except (ValueError, TypeError):
        return False

    if len(root_bytes) != 32:
        return False
    if any(len(p) != 32 for p in proof_bytes):
        return False

    try:
        raw_entry = _normalize_entry(entry)
    except MerkleTransparencyError:
        return False

    leaf = _leaf_digest(raw_entry)

    fn = index
    sn = size - 1
    r = leaf

    for p in proof_bytes:
        if sn == 0:
            return False
        if (fn & 1) == 1 or fn == sn:
            r = hashlib.sha256(b"\x01" + p + r).digest()
            while (fn & 1) == 0 and fn != 0:
                fn >>= 1
                sn >>= 1
        else:
            r = hashlib.sha256(b"\x01" + r + p).digest()
        fn >>= 1
        sn >>= 1

    return sn == 0 and r == root_bytes


def verify_consistency(
    m: int,
    n: int,
    root_m: str,
    root_n: str,
    proof: Sequence[str],
) -> bool:
    """Verify consistency between tree size m (root_m) and size n (root_n).

    Aligned with RFC 9162 Section 2.1.4.2. Fails closed (returns False) on any
    tampering, divergence, malformed hex, forged node, or invalid size range.
    """
    if not isinstance(m, int) or not isinstance(n, int):
        return False
    if m < 0 or n < 0 or m > n:
        return False

    try:
        root_m_bytes = bytes.fromhex(root_m)
        root_n_bytes = bytes.fromhex(root_n)
        proof_bytes = [bytes.fromhex(p) for p in proof]
    except (ValueError, TypeError):
        return False

    if len(root_m_bytes) != 32 or len(root_n_bytes) != 32:
        return False
    if any(len(p) != 32 for p in proof_bytes):
        return False

    # RFC 9162 Section 2.1.4: m == n case
    if m == n:
        return root_m_bytes == root_n_bytes and len(proof_bytes) == 0

    if m == 0:
        return root_m.lower() == EMPTY_TREE_HASH and len(proof_bytes) == 0

    if not proof_bytes:
        return False

    consistency_path = list(proof_bytes)
    if (m & (m - 1)) == 0:
        consistency_path.insert(0, root_m_bytes)

    fn = m - 1
    sn = n - 1

    while (fn & 1) == 1:
        fn >>= 1
        sn >>= 1

    fr = consistency_path[0]
    sr = consistency_path[0]

    for c in consistency_path[1:]:
        if sn == 0:
            return False
        if (fn & 1) == 1 or fn == sn:
            fr = hashlib.sha256(b"\x01" + c + fr).digest()
            sr = hashlib.sha256(b"\x01" + c + sr).digest()
            while (fn & 1) == 0 and fn != 0:
                fn >>= 1
                sn >>= 1
        else:
            sr = hashlib.sha256(b"\x01" + sr + c).digest()
        fn >>= 1
        sn >>= 1

    return fr == root_m_bytes and sr == root_n_bytes and sn == 0
