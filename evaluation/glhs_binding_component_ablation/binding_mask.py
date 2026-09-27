"""Binding mask definitions for the 2^3 factorial component ablation (E01)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

B000 = "B000"
B100 = "B100"
B010 = "B010"
B001 = "B001"
B110 = "B110"
B101 = "B101"
B011 = "B011"
B111 = "B111"

NONE = B000
ID_ONLY = B100
DIGEST_ONLY = B010
EVIDENCE_ONLY = B001
ID_DIGEST = B110
ID_EVIDENCE = B101
DIGEST_EVIDENCE = B011
FULL_EXACT = B111

ARMS = (
    B000,
    B100,
    B010,
    B001,
    B110,
    B101,
    B011,
    B111,
)
ALL_ARMS = ARMS


@dataclass(frozen=True)
class BindingMask:
    """Exact-binding component mask across the three core dimensions."""

    name: str
    snapshot_identity: bool
    snapshot_digest: bool
    evidence_membership: bool

    ALL_ARMS: ClassVar[tuple[str, ...]] = ALL_ARMS

    @classmethod
    def from_arm_name(cls, arm: str) -> BindingMask:
        arm_upper = arm.upper()
        if arm_upper == B000:
            return cls(name=B000, snapshot_identity=False, snapshot_digest=False, evidence_membership=False)
        if arm_upper == B100:
            return cls(name=B100, snapshot_identity=True, snapshot_digest=False, evidence_membership=False)
        if arm_upper == B010:
            return cls(name=B010, snapshot_identity=False, snapshot_digest=True, evidence_membership=False)
        if arm_upper == B001:
            return cls(name=B001, snapshot_identity=False, snapshot_digest=False, evidence_membership=True)
        if arm_upper == B110:
            return cls(name=B110, snapshot_identity=True, snapshot_digest=True, evidence_membership=False)
        if arm_upper == B101:
            return cls(name=B101, snapshot_identity=True, snapshot_digest=False, evidence_membership=True)
        if arm_upper == B011:
            return cls(name=B011, snapshot_identity=False, snapshot_digest=True, evidence_membership=True)
        if arm_upper == B111:
            return cls(name=B111, snapshot_identity=True, snapshot_digest=True, evidence_membership=True)
        raise ValueError(f"unknown_ablation_arm:{arm}")

    @property
    def vector(self) -> tuple[int, int, int]:
        return (
            1 if self.snapshot_identity else 0,
            1 if self.snapshot_digest else 0,
            1 if self.evidence_membership else 0,
        )

    def as_tuple(self) -> tuple[bool, bool, bool]:
        return (
            self.snapshot_identity,
            self.snapshot_digest,
            self.evidence_membership,
        )

    def as_code(self) -> str:
        return self.name


def get_binding_mask(arm: str | BindingMask) -> BindingMask:
    if isinstance(arm, BindingMask):
        return arm
    return BindingMask.from_arm_name(str(arm))
