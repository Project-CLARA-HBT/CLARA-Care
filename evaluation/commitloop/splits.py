"""Stable subject-disjoint split assignment before case variants."""

from __future__ import annotations

import hashlib


def assign_subject_split(subject_token: str, *, seed: str) -> str:
    bucket = int(hashlib.sha256(f"{seed}:{subject_token}".encode()).hexdigest()[:8], 16) % 100
    if bucket < 70:
        return "development"
    if bucket < 85:
        return "validation"
    return "sealed_test"


def split_subjects(subject_tokens: set[str], *, seed: str) -> dict[str, str]:
    return {token: assign_subject_split(token, seed=seed) for token in sorted(subject_tokens)}
