"""Tests for the W6 actual context builders (AUD-050 regression)."""

from __future__ import annotations

import hashlib
from itertools import combinations

import pytest

from evaluation.clinical_utility.context_builders import (
    CONDITIONS,
    build_context,
    content_sha256,
    hash_context,
    token_estimate,
)

DISCLOSURE_BLOCK = (
    "Current consent (c3) authorizes evidence set {e0, e1} for purpose "
    "treatment-summary only. Policy p2 governs role clinician. No other "
    "disclosure is authorized."
)

TASK: dict[str, object] = {
    "task_id": "case-001",
    "scenario": (
        "A synthetic governed record with two events; the later event carries a "
        "new version. Return the current state and whether the proposed commit "
        "is authorized."
    ),
    "state_version": "v7",
    "consent_version": "c3",
    "policy_version": "p2",
    "governed_disclosure_block": DISCLOSURE_BLOCK,
    "source_ids": ("evidence:e0", "evidence:e1"),
}


@pytest.mark.parametrize("condition", CONDITIONS)
def test_build_context_returns_valid_metadata(condition: str) -> None:
    built = build_context(TASK, condition)
    assert built.condition == condition
    assert built.task_id == TASK["task_id"]
    assert built.text
    assert isinstance(built.source_ids, tuple)
    assert built.token_estimate == token_estimate(built.text)
    assert built.sha256 == content_sha256(built.text)
    assert built.content_bytes == built.text.encode("utf-8")
    assert built.sha256 == hashlib.sha256(built.content_bytes).hexdigest()


def test_all_conditions_produce_distinct_content_bytes() -> None:
    rendered = {condition: build_context(TASK, condition) for condition in CONDITIONS}
    for left, right in combinations(CONDITIONS, 2):
        assert rendered[left].content_bytes != rendered[right].content_bytes, (
            f"conditions {left!r} and {right!r} produced identical context bytes; "
            "conditions must differ by actual content, not a label (AUD-050)"
        )
        assert rendered[left].sha256 != rendered[right].sha256


@pytest.mark.parametrize("condition", CONDITIONS)
def test_sha256_is_stable_and_deterministic(condition: str) -> None:
    first = build_context(TASK, condition)
    second = build_context(TASK, condition)
    assert first.sha256 == second.sha256 == hash_context(TASK, condition)
    assert first.content_bytes == second.content_bytes
    assert first.token_estimate == second.token_estimate


def test_unbound_has_no_governance_context() -> None:
    built = build_context(TASK, "unbound")
    assert built.source_ids == ()
    assert "Scenario:" in built.text
    governance_markers = (
        "GOVERNED_DISCLOSURE",
        "COVERSIONED_BINDING",
        "STATE_VERSION",
        "v7",
        "c3",
        "p2",
    )
    for marker in governance_markers:
        assert (
            marker not in built.text
        ), f"unbound context must not contain governance content {marker!r}"


def test_state_only_contains_state_version_but_no_consent_or_policy() -> None:
    built = build_context(TASK, "state_only")
    assert "STATE_VERSION" in built.text
    assert "v7" in built.text
    assert "GOVERNED_DISCLOSURE" not in built.text
    assert "COVERSIONED_BINDING" not in built.text
    assert "c3" not in built.text
    assert "p2" not in built.text
    assert built.source_ids == ("state_version:v7",)


def test_thss_bound_is_co_versioned_without_disclosure_narrative() -> None:
    built = build_context(TASK, "thss_bound")
    assert "COVERSIONED_BINDING" in built.text
    assert "consent=c3" in built.text
    assert "policy=p2" in built.text
    assert "state=v7" in built.text
    assert "GOVERNED_DISCLOSURE" not in built.text
    assert DISCLOSURE_BLOCK not in built.text
    assert built.source_ids == (
        "consent_version:c3",
        "policy_version:p2",
        "state_version:v7",
    )


def test_thss_strict_includes_full_governed_disclosure_block() -> None:
    built = build_context(TASK, "thss_strict")
    assert "GOVERNED_DISCLOSURE" in built.text
    assert DISCLOSURE_BLOCK in built.text
    assert "consent=c3" in built.text
    assert "policy=p2" in built.text
    assert "state=v7" in built.text
    assert built.source_ids == (
        "evidence:e0",
        "evidence:e1",
        "consent_version:c3",
        "policy_version:p2",
        "state_version:v7",
    )


def test_content_differs_by_actual_content_not_label() -> None:
    strict = build_context(TASK, "thss_strict")
    state_only = build_context(TASK, "state_only")
    assert strict.text != state_only.text
    strict_without_disclosure = strict.text.replace(
        f"[GOVERNED_DISCLOSURE] full governed disclosure block:\n{DISCLOSURE_BLOCK}\n", ""
    )
    assert strict_without_disclosure != state_only.text


def test_unknown_condition_rejected() -> None:
    with pytest.raises(ValueError, match="unknown context condition"):
        build_context(TASK, "not_a_condition")


def test_missing_required_field_rejected() -> None:
    incomplete = dict(TASK)
    del incomplete["scenario"]
    with pytest.raises(ValueError, match="scenario"):
        build_context(incomplete, "unbound")
