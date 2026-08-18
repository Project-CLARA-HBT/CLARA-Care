"""P8 tests: minimal evidence selection for Clinical Commitment THSS.

Pure unit tests (no DB): caller evidence only enters when it earns a supported
role; predicate-supporting evidence is retained; the opening flow admits the
declared anchor; identical inputs produce identical digests.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from clara_api.glhs.canonical_json import consistency_fingerprint
from clara_api.glhs.commitment_evidence import (
    ANCHOR_ROLE,
    CONFLICT_ROLE,
    DEPENDENCY_ROLE,
    EXCLUDED_EVIDENCE_REASON,
    PREDICATE_SUPPORTING_ROLE,
    TARGET_SUPPORTING_ROLE,
    select_minimal_evidence,
)

TARGET_SYSTEM = "http://loinc.org"
TARGET_CODE = "example"
OBSERVATIONS = frozenset({"observations"})


def _commitment(
    commitment_id: str,
    *,
    semantic_key: str,
    evidence_state: str = "CLEAR",
    target: dict[str, str] | None = None,
    evidence_ids: tuple[str, ...] = ("e-target",),
    fulfillment_predicate: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "commitment_id": commitment_id,
        "version_id": f"v-{commitment_id}",
        "domain": "observations",
        "semantic_key": semantic_key,
        "lifecycle_state": "OPEN",
        "evidence_state": evidence_state,
        "timeliness_state": "BEFORE_DUE",
        "action": "repeat_measurement",
        "target": target or {"system": TARGET_SYSTEM, "code": TARGET_CODE},
        "evidence_ids": list(evidence_ids),
        "authority_class": "patient_report",
        "anchor_valid_time": "2026-08-01T00:00:00+00:00",
        "anchor_known_time": "2026-08-01T00:00:00+00:00",
        "fulfillment_predicate": fulfillment_predicate,
    }


def _evidence(public_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        public_id=public_id,
        artifact_type="fhir_resource",
        artifact_public_id=f"Observation/{public_id}",
        evidence_kind="source_event",
        valid_from=datetime(2026, 7, 1, tzinfo=UTC),
        recorded_at=datetime(2026, 7, 1, tzinfo=UTC),
    )


def test_caller_evidence_excluded_unless_justified() -> None:
    target = _commitment("c-target", semantic_key="observation:example")
    result = select_minimal_evidence(
        relevant=(target,),
        target_semantic_key="observation:example",
        target={"system": TARGET_SYSTEM, "code": TARGET_CODE},
        anchor_commitment=target,
        blocking=(),
        disclosed_evidence=(_evidence("e-caller"),),
    )
    assert result["evidence_ids"] == ["e-target"]
    assert result["roles"] == {"e-target": ANCHOR_ROLE}
    assert result["excluded_caller_evidence"] == (
        {"evidence_id": "e-caller", "reason": EXCLUDED_EVIDENCE_REASON},
    )


def test_predicate_supporting_evidence_retained() -> None:
    predicate = {
        "op": "event",
        "equals": {"resource_type": "fhir_resource", "status": "source_event"},
    }
    target = _commitment(
        "c-target",
        semantic_key="observation:example",
        fulfillment_predicate=predicate,
    )
    result = select_minimal_evidence(
        relevant=(target,),
        target_semantic_key="observation:example",
        target={"system": TARGET_SYSTEM, "code": TARGET_CODE},
        anchor_commitment=target,
        blocking=(),
        disclosed_evidence=(_evidence("e-matched"),),
    )
    assert "e-matched" in result["evidence_ids"]
    assert result["roles"]["e-matched"] == PREDICATE_SUPPORTING_ROLE
    assert result["excluded_caller_evidence"] == ()


def test_commitment_named_evidence_matches_lifecycle_predicate() -> None:
    predicate = {
        "op": "event",
        "equals": {"system": TARGET_SYSTEM, "code": TARGET_CODE},
    }
    target = _commitment(
        "c-target",
        semantic_key="observation:example",
        evidence_ids=("e-pred",),
        fulfillment_predicate=predicate,
    )
    result = select_minimal_evidence(
        relevant=(target,),
        target_semantic_key="observation:example",
        target={"system": TARGET_SYSTEM, "code": TARGET_CODE},
        anchor_commitment=target,
        blocking=(),
    )
    assert result["evidence_ids"] == ["e-pred"]
    assert result["roles"]["e-pred"] == ANCHOR_ROLE
    assert result["predicate_matched_ids"] == ["e-pred"]


def test_opening_flow_disclosed_evidence_is_declared_anchor() -> None:
    result = select_minimal_evidence(
        relevant=(),
        target_semantic_key="observation:example",
        target={"system": TARGET_SYSTEM, "code": TARGET_CODE},
        anchor_commitment=None,
        blocking=(),
        disclosed_evidence=(_evidence("e-anchor"),),
    )
    assert result["evidence_ids"] == ["e-anchor"]
    assert result["roles"] == {"e-anchor": ANCHOR_ROLE}
    assert result["excluded_caller_evidence"] == ()


def test_blocking_conflict_evidence_gets_conflict_role() -> None:
    target = _commitment(
        "c-target",
        semantic_key="observation:example",
        evidence_state="CONFLICTED",
        evidence_ids=("e-conflict",),
    )
    result = select_minimal_evidence(
        relevant=(target,),
        target_semantic_key="observation:example",
        target={"system": TARGET_SYSTEM, "code": TARGET_CODE},
        anchor_commitment=target,
        blocking=(target,),
    )
    assert result["evidence_ids"] == ["e-conflict"]
    assert result["roles"] == {"e-conflict": CONFLICT_ROLE}


def test_dependency_closure_evidence_gets_dependency_role() -> None:
    target = _commitment("c-target", semantic_key="observation:example")
    dep = _commitment(
        "c-dep",
        semantic_key="observation:dep",
        evidence_ids=("e-dep",),
    )
    result = select_minimal_evidence(
        relevant=(target, dep),
        target_semantic_key="observation:example",
        target={"system": TARGET_SYSTEM, "code": TARGET_CODE},
        anchor_commitment=target,
        dependency_ids=frozenset({"observation:dep"}),
        blocking=(),
    )
    assert result["evidence_ids"] == ["e-dep", "e-target"]
    assert result["roles"] == {"e-dep": DEPENDENCY_ROLE, "e-target": ANCHOR_ROLE}


def test_target_supporting_evidence_role() -> None:
    target = _commitment("c-target", semantic_key="observation:example")
    duplicate = _commitment(
        "c-duplicate",
        semantic_key="observation:duplicate",
        evidence_ids=("e-dup",),
    )
    result = select_minimal_evidence(
        relevant=(target, duplicate),
        target_semantic_key="observation:example",
        target={"system": TARGET_SYSTEM, "code": TARGET_CODE},
        anchor_commitment=target,
        blocking=(),
    )
    assert result["roles"] == {"e-dup": TARGET_SUPPORTING_ROLE, "e-target": ANCHOR_ROLE}


def test_conflict_role_wins_over_anchor_priority() -> None:
    target = _commitment(
        "c-target",
        semantic_key="observation:example",
        evidence_state="CONFLICTED",
        evidence_ids=("e-both",),
    )
    result = select_minimal_evidence(
        relevant=(target,),
        target_semantic_key="observation:example",
        target={"system": TARGET_SYSTEM, "code": TARGET_CODE},
        anchor_commitment=target,
        blocking=(target,),
    )
    assert result["roles"] == {"e-both": CONFLICT_ROLE}


def test_legacy_domain_scoped_mode_discloses_relevant_set() -> None:
    target = _commitment("c-target", semantic_key="observation:example")
    result = select_minimal_evidence(
        relevant=(target,),
        target_semantic_key=None,
        target=None,
        anchor_commitment=None,
        blocking=(),
        disclosed_evidence=(_evidence("e-caller"),),
    )
    assert result["evidence_ids"] == ["e-caller", "e-target"]
    assert result["roles"] == {"e-caller": ANCHOR_ROLE, "e-target": ANCHOR_ROLE}
    assert result["excluded_caller_evidence"] == ()


def test_minimal_selection_is_deterministic() -> None:
    target = _commitment("c-target", semantic_key="observation:example")
    arguments = {
        "relevant": (target,),
        "target_semantic_key": "observation:example",
        "target": {"system": TARGET_SYSTEM, "code": TARGET_CODE},
        "anchor_commitment": target,
        "blocking": (),
        "disclosed_evidence": (_evidence("e-caller"),),
    }
    first = select_minimal_evidence(**arguments)
    second = select_minimal_evidence(**arguments)
    assert first == second
    assert consistency_fingerprint(first) == consistency_fingerprint(second)
