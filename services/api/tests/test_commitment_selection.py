"""P5 tests: task-bounded relevance selection for Clinical Commitments.

Pure unit tests (no DB): same-domain unrelated commitments never block a
declared target task, dependency closures resolve deterministically, cycles
terminate, and identical inputs produce identical selection output.
"""

from __future__ import annotations

from clara_api.glhs.canonical_json import consistency_fingerprint
from clara_api.glhs.commitment_selection import select_relevant_commitments

OBSERVATIONS = frozenset({"observations"})
TARGET_SYSTEM = "http://loinc.org"
TARGET_CODE = "example"


def _commitment(
    commitment_id: str,
    *,
    semantic_key: str,
    domain: str = "observations",
    evidence_state: str = "CLEAR",
    target: dict[str, str] | None = None,
    dependencies: tuple[str, ...] = (),
    evidence_ids: tuple[str, ...] = ("e-target",),
) -> dict[str, object]:
    return {
        "commitment_id": commitment_id,
        "version_id": f"v-{commitment_id}",
        "domain": domain,
        "semantic_key": semantic_key,
        "lifecycle_state": "OPEN",
        "evidence_state": evidence_state,
        "timeliness_state": "BEFORE_DUE",
        "action": "repeat_measurement",
        "target": target or {"system": TARGET_SYSTEM, "code": TARGET_CODE},
        "evidence_ids": list(evidence_ids),
        "dependencies": list(dependencies),
        "authority_class": "patient_report",
        "anchor_valid_time": "2026-08-01T00:00:00+00:00",
        "anchor_known_time": "2026-08-01T00:00:00+00:00",
        "fulfillment_predicate": None,
    }


def test_same_domain_unrelated_conflicted_does_not_block() -> None:
    target = _commitment("c-target", semantic_key="observation:example")
    unrelated = _commitment(
        "c-unrelated",
        semantic_key="observation:unrelated",
        evidence_state="CONFLICTED",
        evidence_ids=("e-unrelated",),
    )
    result = select_relevant_commitments(
        (target, unrelated),
        task="repeat_measurement",
        purpose="self_care",
        allowed_domains=OBSERVATIONS,
        target_semantic_key="observation:example",
    )
    assert [item["commitment_id"] for item in result["relevant"]] == ["c-target"]
    assert [item["commitment_id"] for item in result["blocking"]] == []
    assert result["blocked"] is False
    assert result["visible_conflicts_irrelevant"] == ("c-unrelated",)
    assert ("c-unrelated", "task_irrelevant") in {
        (item["commitment_id"], item["reason"]) for item in result["irrelevant_exclusions"]
    }
    assert "c-unrelated" not in result["dependency_ids"]


def test_target_matches_by_semantic_key_or_system_code() -> None:
    by_key = _commitment("c-a", semantic_key="observation:a")
    by_target = _commitment(
        "c-b",
        semantic_key="observation:b",
        target={"system": "http://snomed.info/sct", "code": "b-code"},
    )
    unrelated = _commitment(
        "c-c",
        semantic_key="observation:c",
        target={"system": "http://snomed.info/sct", "code": "c-code"},
    )
    by_key_result = select_relevant_commitments(
        (by_key, by_target, unrelated),
        task="repeat_measurement",
        purpose="self_care",
        allowed_domains=OBSERVATIONS,
        target_semantic_key="observation:a",
    )
    assert [item["commitment_id"] for item in by_key_result["relevant"]] == ["c-a"]
    by_target_result = select_relevant_commitments(
        (by_key, by_target, unrelated),
        task="repeat_measurement",
        purpose="self_care",
        allowed_domains=OBSERVATIONS,
        target={"system": "http://snomed.info/sct", "code": "b-code"},
    )
    assert [item["commitment_id"] for item in by_target_result["relevant"]] == ["c-b"]


def test_dependency_closure_resolves_and_blocks() -> None:
    target = _commitment(
        "c-target",
        semantic_key="observation:target",
        dependencies=("observation:dep-a",),
    )
    dep_a = _commitment(
        "c-dep-a",
        semantic_key="observation:dep-a",
        evidence_state="CONFLICTED",
        dependencies=("observation:dep-b",),
        evidence_ids=("e-dep-a",),
    )
    dep_b = _commitment(
        "c-dep-b",
        semantic_key="observation:dep-b",
        evidence_state="INSUFFICIENT_EVIDENCE",
        dependencies=(),
        evidence_ids=("e-dep-b",),
    )
    unrelated = _commitment(
        "c-unrelated",
        semantic_key="observation:unrelated",
        evidence_state="CONFLICTED",
        evidence_ids=("e-unrelated",),
    )
    result = select_relevant_commitments(
        (target, dep_a, dep_b, unrelated),
        task="repeat_measurement",
        purpose="self_care",
        allowed_domains=OBSERVATIONS,
        target_semantic_key="observation:target",
        dependencies=("observation:dep-a",),
    )
    assert [item["commitment_id"] for item in result["relevant"]] == [
        "c-dep-a",
        "c-dep-b",
        "c-target",
    ]
    assert [item["commitment_id"] for item in result["blocking"]] == ["c-dep-a", "c-dep-b"]
    assert result["blocked"] is True
    assert result["dependency_ids"] == ("observation:dep-a", "observation:dep-b")
    assert result["missing_dependencies"] == ()
    assert result["dependency_cycles"] == ()
    assert result["visible_conflicts_irrelevant"] == ("c-unrelated",)


def test_cross_domain_dependency_resolves_but_does_not_enter_snapshot() -> None:
    target = _commitment(
        "c-target",
        semantic_key="observation:target",
        dependencies=("condition:dep",),
    )
    cross_domain = _commitment(
        "c-dep",
        semantic_key="condition:dep",
        domain="conditions",
        evidence_state="INSUFFICIENT_EVIDENCE",
        evidence_ids=("e-dep",),
    )
    result = select_relevant_commitments(
        (target, cross_domain),
        task="repeat_measurement",
        purpose="self_care",
        allowed_domains=OBSERVATIONS,
        target_semantic_key="observation:target",
    )
    assert result["dependency_ids"] == ("condition:dep",)
    assert [item["commitment_id"] for item in result["relevant"]] == ["c-target"]
    assert [item["commitment_id"] for item in result["blocking"]] == []


def test_dependency_cycle_terminates_and_excludes_cycle_members() -> None:
    target = _commitment(
        "c-target",
        semantic_key="observation:target",
        dependencies=("observation:dep-a",),
    )
    dep_a = _commitment(
        "c-dep-a",
        semantic_key="observation:dep-a",
        dependencies=("observation:dep-b",),
    )
    dep_b = _commitment(
        "c-dep-b",
        semantic_key="observation:dep-b",
        dependencies=("observation:dep-a",),
    )
    result = select_relevant_commitments(
        (target, dep_a, dep_b),
        task="repeat_measurement",
        purpose="self_care",
        allowed_domains=OBSERVATIONS,
        target_semantic_key="observation:target",
        dependencies=("observation:dep-a",),
    )
    assert result["dependency_cycles"] == (
        ("observation:dep-a", "observation:dep-b", "observation:dep-a"),
    )
    assert result["dependency_ids"] == ()
    assert "observation:dep-a" not in result["dependency_ids"]
    assert [item["commitment_id"] for item in result["relevant"]] == ["c-target"]
    assert result["missing_dependencies"] == ()


def test_missing_dependency_recorded_without_hanging() -> None:
    target = _commitment(
        "c-target",
        semantic_key="observation:target",
        dependencies=("observation:missing-dep",),
    )
    result = select_relevant_commitments(
        (target,),
        task="repeat_measurement",
        purpose="self_care",
        allowed_domains=OBSERVATIONS,
        target_semantic_key="observation:target",
        dependencies=("observation:missing-dep",),
    )
    assert result["missing_dependencies"] == ("observation:missing-dep",)
    assert result["dependency_ids"] == ()
    assert result["dependency_cycles"] == ()


def test_legacy_domain_scoped_mode_without_target_keeps_all_same_domain() -> None:
    conflicted = _commitment(
        "c-conflicted",
        semantic_key="observation:conflicted",
        evidence_state="CONFLICTED",
        evidence_ids=("e-conflicted",),
    )
    clear = _commitment("c-clear", semantic_key="observation:clear")
    other_domain = _commitment(
        "c-allergy",
        semantic_key="allergy:x",
        domain="allergies",
        evidence_state="CONFLICTED",
    )
    result = select_relevant_commitments(
        (conflicted, clear, other_domain),
        task="repeat_measurement",
        purpose="self_care",
        allowed_domains=OBSERVATIONS,
    )
    assert [item["commitment_id"] for item in result["relevant"]] == ["c-clear", "c-conflicted"]
    assert [item["commitment_id"] for item in result["blocking"]] == ["c-conflicted"]
    assert result["blocked"] is True
    assert result["visible_conflicts_irrelevant"] == ()
    assert result["irrelevant_exclusions"] == ()


def test_selection_is_deterministic() -> None:
    target = _commitment(
        "c-target",
        semantic_key="observation:target",
        dependencies=("observation:dep",),
    )
    dep = _commitment(
        "c-dep",
        semantic_key="observation:dep",
        evidence_state="CONFLICTED",
        evidence_ids=("e-dep",),
    )
    unrelated = _commitment(
        "c-unrelated",
        semantic_key="observation:unrelated",
        evidence_state="CONFLICTED",
    )
    arguments = {
        "task": "repeat_measurement",
        "purpose": "self_care",
        "allowed_domains": OBSERVATIONS,
        "target_semantic_key": "observation:target",
        "dependencies": ("observation:dep",),
    }
    first = select_relevant_commitments((target, dep, unrelated), **arguments)
    second = select_relevant_commitments((target, dep, unrelated), **arguments)
    assert first == second
    assert consistency_fingerprint(first) == consistency_fingerprint(second)
