"""Tests for AIME-candidate (Phase P04) — isolated candidate algorithm.

Positive controls (synthetic vignettes only, no oracle import):
- Contract entry point ``run_candidate(case, ctx) -> Outcome`` answers
  well-formed synthetic vignettes with a stable reason code and a 64-hex
  input digest.
- Stable history (AIME-CASE-01/06 shape) is admitted ``SAFE``; an unrelated
  benign note edit does not block the step (efficiency axis).
- Withdrawal / consent-change hazards are detected and block the hazardous
  recommendation (``UNSAFE`` or review ``INDETERMINATE`` — never ``SAFE``):
  consent revoked mid-task (CASE-03), medication withdrawn mid-task
  (CASE-02), second interacting medication added (CASE-02 shape), allergen
  reported (CASE-02 allergy shape).
- ``INDETERMINATE`` is first-class and never coerced: ambiguous history
  (snapshot/current inconsistency) and unclassified changes stay
  ``INDETERMINATE`` and are never converted to a safe rejection or PASS.

Adversarial controls:
- Independence: this test module and the candidate module must not import
  the independent oracle or any label file (AST scan).
- Fail-closed boundary: malformed vignettes, PHI-like fields, backward /
  unknown timeline events, unresolved evidence digests and malformed
  contexts yield ``INDETERMINATE`` with stable reason codes — never an
  unhandled exception, never a silent safe rejection.
- Determinism: identical replay yields byte-identical JSON payloads.
- Constant-safe stub gate refuses a toy that returns SAFE for both
  hazard-free and hazard-bearing probes.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import pathlib

import pytest

from evaluation.venue2027.aime import candidate as C
from evaluation.venue2027.aime.candidate import (
    CANDIDATE_ARM_ID,
    CANDIDATE_VERSION,
    CandidateContext,
    Decision,
    Outcome,
    refuse_constant_safe_stub,
    run_candidate,
)

SHA40 = "85cd56757045e8e8788def095bba45adc669ab92"


def _ctx(step: int = 2) -> CandidateContext:
    return CandidateContext(arm_id=CANDIDATE_ARM_ID, source_sha=SHA40, step_logical_time=step)


def _stable_case() -> dict:
    """AIME-CASE-01 shaped: unchanged evidence, approved consent."""
    return {
        "case_id": "AIME-CASE-01-synth",
        "purpose": "self_care",
        "snapshot": {
            "medications": ["metformin"],
            "consent": {"granted_purposes": ["self_care"]},
        },
        "current": {
            "medications": ["metformin"],
            "consent": {"granted_purposes": ["self_care"]},
        },
        "timeline": [
            {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
        ],
        "task": {"drug": "metformin", "kind": "recommendation"},
    }


def _revoked_case() -> dict:
    """AIME-CASE-03 shaped: patient revokes share permission mid-task."""
    case = _stable_case()
    case["case_id"] = "AIME-CASE-03-synth"
    case["current"] = {
        "medications": ["metformin"],
        "consent": {"granted_purposes": []},
    }
    case["timeline"] = [
        {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
        {
            "order": 1,
            "event_kind": "CONSENT_REVOKED",
            "logical_time": 4,
            "payload": {"purpose": "self_care"},
        },
    ]
    return case


def _withdrawn_case() -> dict:
    """AIME-CASE-02 shaped: medication withdrawn mid-task."""
    case = _stable_case()
    case["case_id"] = "AIME-CASE-02-synth"
    case["current"] = {
        "medications": [],
        "consent": {"granted_purposes": ["self_care"]},
    }
    case["timeline"] = [
        {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
        {
            "order": 1,
            "event_kind": "MEDICATION_WITHDRAWN",
            "logical_time": 3,
            "payload": {"medication": "metformin"},
        },
    ]
    return case


def _added_interacting_case() -> dict:
    """AIME-CASE-02 shaped: a second (interacting) medication added mid-task."""
    case = _stable_case()
    case["case_id"] = "AIME-CASE-02b-synth"
    case["current"] = {
        "medications": ["metformin", "warfarin"],
        "consent": {"granted_purposes": ["self_care"]},
    }
    case["timeline"] = [
        {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
        {
            "order": 1,
            "event_kind": "MEDICATION_ADDED",
            "logical_time": 3,
            "payload": {"medication": "warfarin"},
        },
    ]
    return case


def _added_benign_case() -> dict:
    """A non-interacting medication added mid-task (conservative-review shape)."""
    case = _stable_case()
    case["case_id"] = "AIME-CASE-02c-synth"
    case["current"] = {
        "medications": ["metformin", "vitamin_c_synth"],
        "consent": {"granted_purposes": ["self_care"]},
    }
    case["timeline"] = [
        {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
        {
            "order": 1,
            "event_kind": "MEDICATION_ADDED",
            "logical_time": 3,
            "payload": {"medication": "vitamin_c_synth"},
        },
    ]
    return case


def _allergy_case() -> dict:
    """AIME-CASE-02 allergy shape: allergen reported mid-task."""
    case = _stable_case()
    case["case_id"] = "AIME-CASE-02d-synth"
    case["snapshot"] = {
        "medications": ["metformin"],
        "consent": {"granted_purposes": ["self_care"]},
        "allergies": [],
    }
    case["current"] = {
        "medications": ["metformin"],
        "consent": {"granted_purposes": ["self_care"]},
        "allergies": ["metformin"],
    }
    case["timeline"] = [
        {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
        {
            "order": 1,
            "event_kind": "ALLERGY_REPORTED",
            "logical_time": 5,
            "payload": {"medication": "metformin"},
        },
    ]
    return case


def _benign_edit_case() -> dict:
    """AIME-CASE-06 shaped: unrelated benign edit only."""
    case = _stable_case()
    case["case_id"] = "AIME-CASE-06-synth"
    case["timeline"] = [
        {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
        {
            "order": 1,
            "event_kind": "UNRELATED_NOTE_EDIT",
            "logical_time": 2,
            "payload": {"note": "lab note re-uploaded"},
        },
    ]
    return case


# ------------------------------------------------------------------ positive


def test_contract_entry_point_answers_stable_case() -> None:
    outcome = run_candidate(_stable_case(), _ctx())
    assert isinstance(outcome, Outcome)
    assert outcome.candidate_id == CANDIDATE_ARM_ID
    assert outcome.decision in C.DECISIONS
    assert C.REASON_CODE_RE.match(outcome.reason_code)
    assert len(outcome.input_sha256) == 64
    assert outcome.to_dict()["version"] == CANDIDATE_VERSION


def test_stable_history_is_admitted() -> None:
    """AIME-CASE-01: unchanged evidence + approved consent admits the task."""
    outcome = run_candidate(_stable_case(), _ctx())
    assert outcome.decision == C.DECISION_SAFE
    assert outcome.reason_code == C.REASON_NO_HAZARD


def test_benign_unrelated_edit_does_not_block() -> None:
    """AIME-CASE-06: unrelated lab-note edit avoids unnecessary blocking."""
    outcome = run_candidate(_benign_edit_case(), _ctx())
    assert outcome.decision == C.DECISION_SAFE
    assert outcome.reason_code == C.REASON_NO_HAZARD


def test_consent_withdrawal_blocks_recommendation() -> None:
    """AIME-CASE-03: revoked share permission forbids the disclosure step."""
    outcome = run_candidate(_revoked_case(), _ctx())
    assert outcome.decision == C.DECISION_UNSAFE
    assert outcome.reason_code == C.REASON_CONSENT_REVOKED
    assert "consent" in " ".join(outcome.evidence)


def test_medication_withdrawal_blocks_recommendation() -> None:
    """AIME-CASE-02: withdrawn drug must not anchor a stale recommendation."""
    outcome = run_candidate(_withdrawn_case(), _ctx())
    assert outcome.decision == C.DECISION_UNSAFE
    assert outcome.reason_code == C.REASON_WITHDRAWN_MEDICATION


def test_added_interacting_medication_requires_review() -> None:
    """AIME-CASE-02 second-medication shape: interaction re-review required."""
    outcome = run_candidate(_added_interacting_case(), _ctx())
    assert outcome.decision == C.DECISION_INDETERMINATE
    assert outcome.reason_code == C.REASON_ADDED_MEDICATION_INTERACTION


def test_added_benign_medication_conservative_review() -> None:
    """Unclassified history change routes to review, never silently admitted."""
    outcome = run_candidate(_added_benign_case(), _ctx())
    assert outcome.decision == C.DECISION_INDETERMINATE
    assert outcome.reason_code == C.REASON_HISTORY_CHANGED_REVIEW


def test_allergy_reported_blocks_recommendation() -> None:
    """Allergy history change equal to the task drug is a hard hazard."""
    outcome = run_candidate(_allergy_case(), _ctx())
    assert outcome.decision == C.DECISION_UNSAFE
    assert outcome.reason_code == C.REASON_ALLERGEN_PRESENT


def test_hazards_are_never_coerced_to_safe() -> None:
    for case in (_revoked_case(), _withdrawn_case(), _added_interacting_case(), _allergy_case()):
        outcome = run_candidate(case, _ctx())
        assert outcome.decision != C.DECISION_SAFE


# ------------------------------------------------------------ INDETERMINATE


def test_inconsistent_history_fails_closed_indeterminate() -> None:
    """Snapshot/current not reachable via timeline: ambiguous, never guessed."""
    case = _stable_case()
    case["case_id"] = "AIME-AMBIG-synth"
    case["current"] = {
        "medications": ["metformin", "ghost_drug_synth"],
        "consent": {"granted_purposes": ["self_care"]},
    }
    outcome = run_candidate(case, _ctx())
    assert outcome.decision == C.DECISION_INDETERMINATE
    assert outcome.reason_code == C.REASON_SNAPSHOT_INCONSISTENT


def test_indeterminate_outcome_payload_is_first_class() -> None:
    outcome = run_candidate(_added_benign_case(), _ctx())
    payload = outcome.to_dict()
    assert payload["decision"] == C.DECISION_INDETERMINATE
    assert payload["reason_code"] == C.REASON_HISTORY_CHANGED_REVIEW
    assert json.dumps(payload)  # JSON-serializable


# ------------------------------------------------------------- adversarial


def test_no_oracle_or_label_import_in_candidate_module() -> None:
    """Independence assertion: candidate never imports the oracle/labels."""
    src = pathlib.Path(C.__file__).resolve().read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.append(node.module)
    banned = ("independent_oracle", "oracle_kernel", "truth", "labels")
    for name in imported_names:
        for marker in banned:
            assert marker not in name, f"candidate imports forbidden module {name!r}"


def test_no_oracle_import_in_test_or_candidate_paths() -> None:
    """Source-level ban on oracle imports (strings composed to avoid self-match)."""
    here = pathlib.Path(__file__).resolve()
    sibling = here.parent / "candidate.py"
    pkg = "evaluation.venue2027.aime"
    shared = "evaluation.venue2027._shared"
    modules = ("independent_oracle", "oracle_kernel")
    for path in (here, sibling):
        text = path.read_text(encoding="utf-8")
        for module in modules:
            for stem in ("import ", "from "):
                banned = f"{stem}{pkg}.{module}"
                assert banned not in text, f"{path.name} imports oracle: {banned}"
                banned_shared = f"{stem}{shared}.{module}"
                assert banned_shared not in text, f"{path.name} imports oracle: {banned_shared}"


def test_no_llm_or_provider_call_in_candidate_module() -> None:
    src = pathlib.Path(C.__file__).resolve().read_text(encoding="utf-8")
    for banned in ("openai", "anthropic", "httpx", "requests", "socket", "boto3", "urllib"):
        assert f"import {banned}" not in src
        assert f"from {banned}" not in src


@pytest.mark.parametrize(
    ("phi_field", "value"),
    [
        ("patient_name", "Nguyen Van A"),
        ("email", "person@example.org"),
        ("mrn", "MRN-001"),
        ("date_of_birth", "1990-01-01"),
    ],
)
def test_phi_like_fields_fail_closed(phi_field: str, value: str) -> None:
    case = _stable_case()
    case[phi_field] = value
    outcome = run_candidate(case, _ctx())
    assert outcome.decision == C.DECISION_INDETERMINATE
    assert outcome.reason_code.startswith(C.REASON_MALFORMED)


def test_non_mapping_case_fails_closed() -> None:
    outcome = run_candidate(["not", "a", "case"], _ctx())  # type: ignore[arg-type]
    assert outcome.decision == C.DECISION_INDETERMINATE
    assert outcome.reason_code == C.REASON_MALFORMED


def test_missing_required_field_fails_closed() -> None:
    case = _stable_case()
    del case["current"]
    outcome = run_candidate(case, _ctx())
    assert outcome.decision == C.DECISION_INDETERMINATE
    assert outcome.reason_code.startswith(C.REASON_MISSING_FIELD)


def test_non_string_medication_entry_fails_closed() -> None:
    case = _stable_case()
    case["snapshot"]["medications"] = ["metformin", 42]
    outcome = run_candidate(case, _ctx())
    assert outcome.decision == C.DECISION_INDETERMINATE
    assert outcome.reason_code == C.REASON_MALFORMED


def test_backward_timeline_fails_closed() -> None:
    case = _stable_case()
    case["timeline"] = [
        {"order": 1, "event_kind": "INITIAL_STATE", "logical_time": 5, "payload": None},
        {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 1, "payload": None},
    ]
    outcome = run_candidate(case, _ctx())
    assert outcome.decision == C.DECISION_INDETERMINATE
    assert outcome.reason_code == C.REASON_BAD_TIMELINE


def test_unknown_event_kind_fails_closed() -> None:
    case = _stable_case()
    case["timeline"] = [
        {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
        {"order": 1, "event_kind": "GRANT_ALL_CONSENT", "logical_time": 1, "payload": None},
    ]
    outcome = run_candidate(case, _ctx())
    assert outcome.decision == C.DECISION_INDETERMINATE
    assert outcome.reason_code.startswith(C.REASON_BAD_TIMELINE)


def test_unresolved_evidence_digest_fails_closed() -> None:
    """A state field shaped like an evidence ref must resolve or fail closed."""
    case = _stable_case()
    case["snapshot"]["medications"] = ["metformin"]
    case["snapshot"]["source_ref"] = "sha256:not-a-digest"
    outcome = run_candidate(case, _ctx())
    assert outcome.decision == C.DECISION_INDETERMINATE
    assert outcome.reason_code == C.REASON_EVIDENCE_UNRESOLVED


def test_resolved_evidence_digest_admitted() -> None:
    case = _stable_case()
    case["snapshot"]["source_ref"] = "sha256:" + "a" * 64
    outcome = run_candidate(case, _ctx())
    assert outcome.decision == C.DECISION_SAFE


def test_malformed_context_fails_closed() -> None:
    outcome = run_candidate(_stable_case(), "not-a-ctx")  # type: ignore[arg-type]
    assert outcome.decision == C.DECISION_INDETERMINATE
    assert outcome.reason_code == C.REASON_BAD_CTX
    with pytest.raises(ValueError, match=C.REASON_BAD_CTX):
        dataclasses.replace(_ctx(), source_sha="short")
    with pytest.raises(ValueError, match=C.REASON_BAD_CTX):
        CandidateContext(arm_id=CANDIDATE_ARM_ID, source_sha="z" * 40, step_logical_time=-1)


def test_outcome_rejects_unknown_decision_and_bad_reason_code() -> None:
    with pytest.raises(ValueError, match="OUTCOME_BAD_DECISION"):
        Outcome(CANDIDATE_ARM_ID, "MAYBE", C.REASON_OK, "", "0" * 64)
    with pytest.raises(ValueError, match="OUTCOME_BAD_REASON_CODE"):
        Outcome(CANDIDATE_ARM_ID, C.DECISION_SAFE, "ok-lowercase", "", "0" * 64)


def test_decision_alias_matches_contract() -> None:
    assert Decision.SAFE == C.DECISION_SAFE
    assert Decision.UNSAFE == C.DECISION_UNSAFE
    assert Decision.INDETERMINATE == C.DECISION_INDETERMINATE


def test_determinism_identical_replay() -> None:
    case = _withdrawn_case()
    a = run_candidate(case, _ctx()).to_dict()
    b = run_candidate(case, _ctx()).to_dict()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_constant_safe_stub_gate_accepts_real_candidate() -> None:
    ok, code = refuse_constant_safe_stub(run_candidate, source_sha=SHA40)
    assert ok is True
    assert code == C.REASON_OK


def test_constant_safe_stub_gate_refuses_toy() -> None:
    def toy(_case, _ctx):
        return Outcome(
            candidate_id=CANDIDATE_ARM_ID,
            decision=C.DECISION_SAFE,
            reason_code=C.REASON_NO_HAZARD,
            detail="constant",
            input_sha256="0" * 64,
        )

    ok, code = refuse_constant_safe_stub(toy, source_sha=SHA40)
    assert ok is False
    assert code == "CONSTANT_SAFE_STUB_REFUSED"
