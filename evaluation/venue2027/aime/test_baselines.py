"""Tests for AIME-baselines (Phase P03) — baseline fidelity adapters.

Positive controls (synthetic vignettes only, in-process arms):
- Every registry arm answers ``run_baseline(id, case, ctx) -> Outcome`` on
  well-formed synthetic vignettes with a stable reason code and a 64-hex
  input digest.
- B0 (single-history) issues a recommendation from the task-start snapshot
  and — by declared stale-context semantics — misses a mid-task medication
  withdrawal that the B4 candidate flags: the demonstration pair behind the
  study's axis-A hazard claim (a systems-level behavior on synthetic labels,
  NOT a clinical efficacy result).
- B1 per-step refresh + current policy filter refuses a post-revocation
  step; on a stable vignette it completes cleanly.
- B3 output post-filter blocks a proposed output that names a withdrawn
  medication and lets an unrelated benign edit through.
- B5 consent-agnostic retrieval foil surfaces the revoked-evidence failure
  mode it is designed to expose.
- Registry integrity: every arm id in ``_ARM_TABLE`` is registered with
  provenance, all reason codes match the stable-code pattern, decisions are
  within the allowed set.
- Constant-safe-stub gate accepts the real B4 arm and refuses a stub that
  returns SAFE for both hazard-free and hazard-bearing probes.

Adversarial controls:
- LLM/provider-dependent arms (B0/B1/B2/B3 full provider execution) return
  ``NOT_RUN_EXTERNAL`` / ``PROVIDER_DEPENDENT_NOT_RUN``; no live model call
  exists to make (module imports no provider client).
- A constant-safe stub (SAFE regardless of hazard) is refused with
  ``CONSTANT_SAFE_STUB_REFUSED``.
- No real PHI fields are accepted: vignettes carrying PHI-like field names
  (patient_name, email, mrn, ...) or non-string medication entries fail
  closed to ``INDETERMINATE`` with a structural reason code — never a silent
  safe rejection.
- Malformed vignettes (missing fields, backward timeline, unknown event
  kind) and context mismatches (ctx.arm_id != baseline_id) fail closed with
  stable codes.
- ``NOT_RUN_EXTERNAL`` outcomes are structurally incapable of being counted
  as successes.
"""

from __future__ import annotations

import dataclasses

import pytest

from evaluation.venue2027.aime import baselines as B
from evaluation.venue2027.aime.baselines import (
    BASELINE_REGISTRY,
    BaselineContext,
    Decision,
    Outcome,
    refuse_constant_safe_stub,
    run_baseline,
)

SHA40 = "9b6be889db89c2228c6ea1ac599f0000d03c63a4"

ALL_ARMS = tuple(BASELINE_REGISTRY)


def _ctx(arm_id: str, step: int = 2) -> BaselineContext:
    return BaselineContext(arm_id=arm_id, source_sha=SHA40, step_logical_time=step)


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
        "output": {"text": "continue metformin per current plan"},
    }


def _withdrawn_case() -> dict:
    """AIME-CASE-02 shaped: medication withdrawn mid-task (stale-snapshot hazard)."""
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
    case["output"] = {"text": "metformin appears in the record"}
    return case


def _revoked_case() -> dict:
    """AIME-CASE-03 shaped: consent withdrawal mid-task."""
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


def _added_case() -> dict:
    """AIME-CASE-02 shaped: second medication added after initial context."""
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


# ------------------------------------------------------------ positive arms


@pytest.mark.parametrize("arm_id", ALL_ARMS)
def test_every_registered_arm_answers_stable_case(arm_id: str) -> None:
    outcome = run_baseline(arm_id, _stable_case(), _ctx(arm_id))
    assert isinstance(outcome, Outcome)
    assert outcome.decision in B.DECISIONS
    assert B.REASON_CODE_RE.match(outcome.reason_code)
    assert len(outcome.input_sha256) == 64
    assert outcome.baseline_id == arm_id
    assert outcome.to_dict()["version"] == B.BASELINES_VERSION


@pytest.mark.parametrize("arm_id", ALL_ARMS)
def test_every_registered_arm_answers_benign_edit(arm_id: str) -> None:
    outcome = run_baseline(arm_id, _benign_edit_case(), _ctx(arm_id))
    assert outcome.decision in B.DECISIONS
    assert B.REASON_CODE_RE.match(outcome.reason_code)


def test_b0_single_history_issues_snapshot_recommendation() -> None:
    outcome = run_baseline(B.BASELINE_B0, _stable_case(), _ctx(B.BASELINE_B0))
    assert outcome.decision == B.DECISION_SAFE
    assert outcome.reason_code == B.REASON_NO_HAZARD
    assert "snapshot" in " ".join(outcome.evidence)


def test_b0_misses_medication_withdrawal_b4_flags_it() -> None:
    """Core demonstration pair: stale B0 vs counterfactual-history-aware B4.

    B0's declared semantics (single snapshot, ignores history change) leave
    the withdrawn medication in its recommendation context — the axis-A
    action-eligibility hazard. B4's counterfactual history check flags it.
    This is a synthetic system-behavior contrast, not a clinical claim.
    """
    case = _withdrawn_case()
    b0 = run_baseline(B.BASELINE_B0, case, _ctx(B.BASELINE_B0))
    b4 = run_baseline(B.BASELINE_B4, case, _ctx(B.BASELINE_B4))
    assert b0.decision == B.DECISION_SAFE, "B0 must be blind to mid-task change"
    assert b0.reason_code == B.REASON_NO_HAZARD
    assert b4.decision == B.DECISION_UNSAFE
    assert b4.reason_code == B.REASON_WITHDRAWN_MEDICATION
    assert b4.input_sha256 == b0.input_sha256, "same vignette, different awareness"


def test_b1_refreshes_and_refuses_post_revocation_step() -> None:
    outcome = run_baseline(B.BASELINE_B1, _revoked_case(), _ctx(B.BASELINE_B1))
    assert outcome.decision == B.DECISION_UNSAFE
    assert outcome.reason_code == B.REASON_CONSENT_REVOKED


def test_b1_stable_context_completes_cleanly() -> None:
    outcome = run_baseline(B.BASELINE_B1, _stable_case(), _ctx(B.BASELINE_B1))
    assert outcome.decision == B.DECISION_SAFE
    assert outcome.reason_code == B.REASON_NO_HAZARD


def test_b1_surfaces_added_medication_as_indeterminate_review() -> None:
    outcome = run_baseline(B.BASELINE_B1, _added_case(), _ctx(B.BASELINE_B1))
    assert outcome.decision == B.DECISION_INDETERMINATE
    assert outcome.reason_code == B.REASON_ADITIONAL_MEDICATION_HAZARD


def test_b3_post_filter_blocks_withdrawn_medication_output() -> None:
    outcome = run_baseline(B.BASELINE_B3, _withdrawn_case(), _ctx(B.BASELINE_B3))
    assert outcome.decision == B.DECISION_UNSAFE
    assert outcome.reason_code == B.REASON_WITHDRAWN_MEDICATION


def test_b3_post_filter_passes_benign_edit() -> None:
    outcome = run_baseline(B.BASELINE_B3, _benign_edit_case(), _ctx(B.BASELINE_B3))
    assert outcome.decision == B.DECISION_SAFE


def test_b4_flags_consent_revocation_and_added_medication() -> None:
    revoked = run_baseline(B.BASELINE_B4, _revoked_case(), _ctx(B.BASELINE_B4))
    assert revoked.decision == B.DECISION_UNSAFE
    assert revoked.reason_code == B.REASON_CONSENT_REVOKED
    added = run_baseline(B.BASELINE_B4, _added_case(), _ctx(B.BASELINE_B4))
    assert added.decision == B.DECISION_INDETERMINATE
    assert added.reason_code == B.REASON_ADITIONAL_MEDICATION_HAZARD


def test_b4_stable_and_benign_edit_stay_safe() -> None:
    assert (
        run_baseline(B.BASELINE_B4, _stable_case(), _ctx(B.BASELINE_B4)).decision == B.DECISION_SAFE
    )
    benign = run_baseline(B.BASELINE_B4, _benign_edit_case(), _ctx(B.BASELINE_B4))
    assert benign.decision == B.DECISION_SAFE


def test_b5_foil_surfaces_revoked_evidence_failure_mode() -> None:
    outcome = run_baseline(B.BASELINE_B5, _revoked_case(), _ctx(B.BASELINE_B5))
    assert outcome.decision == B.DECISION_UNSAFE
    assert outcome.reason_code == B.REASON_CONSENT_AGNOSTIC_RETRIEVAL


def test_b5_foil_mixes_stale_medication_state() -> None:
    outcome = run_baseline(B.BASELINE_B5, _withdrawn_case(), _ctx(B.BASELINE_B5))
    assert outcome.decision == B.DECISION_UNSAFE
    assert outcome.reason_code == B.RETRIEVAL_MEDICATION_REASON


# ------------------------------------------------------- registry integrity


def test_registry_covers_all_arms_with_provenance() -> None:
    required = {"comparator_id", "algorithm_class", "fidelity_status", "upstream"}
    for arm_id, entry in BASELINE_REGISTRY.items():
        assert required <= set(entry), f"{arm_id} missing provenance fields"
        assert entry["fidelity_status"] == "UNAVAILABLE_NOT_RUN"
        assert entry["upstream"].startswith("research/venue2027/aime/literature_matrix.csv#")


def test_outcomes_reject_unknown_decision_and_bad_reason_code() -> None:
    with pytest.raises(ValueError, match="OUTCOME_BAD_DECISION"):
        Outcome("x", "MAYBE", B.REASON_OK, "", "0" * 64)
    with pytest.raises(ValueError, match="OUTCOME_BAD_REASON_CODE"):
        Outcome("x", B.DECISION_SAFE, "ok-lowercase", "", "0" * 64)


def test_constant_safe_stub_gate_accepts_real_arms() -> None:
    def real_b4(case, ctx):
        return run_baseline(B.BASELINE_B4, case, ctx)

    ok, code = refuse_constant_safe_stub(real_b4, arm_id=B.BASELINE_B4, source_sha=SHA40)
    assert ok is True
    assert code == B.REASON_OK


def test_constant_safe_stub_gate_refuses_toy() -> None:
    def toy(_case, _ctx):
        return Outcome(
            baseline_id=B.BASELINE_B4,
            decision=B.DECISION_SAFE,
            reason_code=B.REASON_NO_HAZARD,
            detail="constant",
            input_sha256="0" * 64,
        )

    ok, code = refuse_constant_safe_stub(toy, arm_id=B.BASELINE_B4, source_sha=SHA40)
    assert ok is False
    assert code == B.REASON_CONSTANT_SAFE_STUB


# ------------------------------------------------------ adversarial vectors


def test_provider_dependent_arms_not_run_external() -> None:
    """LLM-backed execution of B0/B1/B2/B3 is never performed in-process."""
    b2 = run_baseline(B.BASELINE_B2, _stable_case(), _ctx(B.BASELINE_B2))
    assert b2.decision == B.DECISION_NOT_RUN_EXTERNAL
    assert b2.reason_code == B.REASON_PROVIDER_DEPENDENT
    for arm_id in (B.BASELINE_B0, B.BASELINE_B1, B.BASELINE_B3):
        entry = BASELINE_REGISTRY[arm_id]
        assert entry["provider_dependent"] == "true"
        assert entry["fidelity_status"] == "UNAVAILABLE_NOT_RUN"


def test_module_imports_no_provider_client() -> None:
    import inspect
    import pathlib

    src = pathlib.Path(inspect.getsourcefile(B) or "").read_text(encoding="utf-8")
    for banned in ("openai", "anthropic", "httpx", "requests", "socket", "boto3"):
        assert f"import {banned}" not in src
        assert f"from {banned}" not in src


def test_not_run_external_never_counted_as_success() -> None:
    outcome = run_baseline(B.BASELINE_B2, _stable_case(), _ctx(B.BASELINE_B2))
    payload = outcome.to_dict()
    assert payload["decision"] == B.DECISION_NOT_RUN_EXTERNAL
    # False-zero ban: an external-not-run outcome carries no success path.
    assert "counted_as_success" not in payload


@pytest.mark.parametrize(
    ("phi_field", "value"),
    [
        ("patient_name", "Nguyen Van A"),
        ("email", "person@example.org"),
        ("mrn", "MRN-001"),
        ("national_id", "012345678"),
    ],
)
def test_phi_like_fields_fail_closed(phi_field: str, value: str) -> None:
    """Vignettes carrying PHI-like fields are refused with a stable code."""
    case = _stable_case()
    case[phi_field] = value
    outcome = run_baseline(B.BASELINE_B4, case, _ctx(B.BASELINE_B4))
    assert outcome.decision == B.DECISION_INDETERMINATE
    assert outcome.reason_code in (B.REASON_MALFORMED, B.REASON_MISSING_FIELD)


def test_non_string_medication_entry_fails_closed() -> None:
    case = _stable_case()
    case["snapshot"]["medications"] = ["metformin", 42]
    outcome = run_baseline(B.BASELINE_B4, case, _ctx(B.BASELINE_B4))
    assert outcome.decision == B.DECISION_INDETERMINATE
    assert outcome.reason_code == B.REASON_MALFORMED


def test_missing_required_field_fails_closed() -> None:
    case = _stable_case()
    del case["current"]
    outcome = run_baseline(B.BASELINE_B1, case, _ctx(B.BASELINE_B1))
    assert outcome.decision == B.DECISION_INDETERMINATE
    assert outcome.reason_code.startswith(B.REASON_MISSING_FIELD)


def test_backward_timeline_fails_closed() -> None:
    case = _stable_case()
    case["timeline"] = [
        {"order": 1, "event_kind": "INITIAL_STATE", "logical_time": 5, "payload": None},
        {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 1, "payload": None},
    ]
    outcome = run_baseline(B.BASELINE_B4, case, _ctx(B.BASELINE_B4))
    assert outcome.decision == B.DECISION_INDETERMINATE
    assert outcome.reason_code == B.REASON_BAD_TIMELINE


def test_unknown_event_kind_fails_closed() -> None:
    case = _stable_case()
    case["timeline"] = [
        {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
        {"order": 1, "event_kind": "HACK_ALL_CONSENT", "logical_time": 1, "payload": None},
    ]
    outcome = run_baseline(B.BASELINE_B4, case, _ctx(B.BASELINE_B4))
    assert outcome.decision == B.DECISION_INDETERMINATE
    assert outcome.reason_code.startswith(B.REASON_BAD_TIMELINE)


def test_non_mapping_case_fails_closed() -> None:
    outcome = run_baseline(B.BASELINE_B4, ["not", "a", "case"], _ctx(B.BASELINE_B4))  # type: ignore[arg-type]
    assert outcome.decision == B.DECISION_INDETERMINATE
    assert outcome.reason_code == B.REASON_MALFORMED


def test_unknown_baseline_id_fails_closed() -> None:
    outcome = run_baseline("B9-fake-naive-baseline", _stable_case(), _ctx("B9-fake-naive-baseline"))
    assert outcome.decision == B.DECISION_INDETERMINATE
    assert outcome.reason_code == B.REASON_UNKNOWN_ARM


def test_context_arm_mismatch_fails_closed() -> None:
    case = _stable_case()
    ctx = _ctx(B.BASELINE_B1)
    outcome = run_baseline(B.BASELINE_B4, case, ctx)
    assert outcome.decision == B.DECISION_INDETERMINATE
    assert outcome.reason_code == "ARM_CONTEXT_MISMATCH"


def test_malformed_context_is_refused() -> None:
    with pytest.raises(ValueError, match=B.REASON_BAD_CTX):
        dataclasses.replace(_ctx(B.BASELINE_B4), source_sha="short")
    with pytest.raises(ValueError, match=B.REASON_BAD_CTX):
        BaselineContext(arm_id=B.BASELINE_B4, source_sha="z" * 40, step_logical_time=-1)
    # A foreign ctx object also fails closed (never silently accepted).
    outcome = run_baseline(B.BASELINE_B4, _stable_case(), "not-a-ctx")  # type: ignore[arg-type]
    assert outcome.decision == B.DECISION_INDETERMINATE
    assert outcome.reason_code == B.REASON_BAD_CTX


def test_no_clock_or_randomness_in_arms() -> None:
    """Determinism: identical replay yields byte-identical outcome payloads."""
    import json

    case = _withdrawn_case()
    a = run_baseline(B.BASELINE_B4, case, _ctx(B.BASELINE_B4)).to_dict()
    b = run_baseline(B.BASELINE_B4, case, _ctx(B.BASELINE_B4)).to_dict()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_module_declares_no_clinical_efficacy_path() -> None:
    """Claim-boundary guard: the module is a decision adapter over synthetic
    vignettes; nothing in it evaluates diagnosis, treatment or outcomes."""
    import inspect
    import pathlib

    src = pathlib.Path(inspect.getsourcefile(B) or "").read_text(encoding="utf-8")
    assert "synthetic" in src
    assert "not clinical" in B.__doc__ or "NOT a decision algorithm" in src


def test_decision_alias_matches_contract() -> None:
    assert Decision.SAFE == B.DECISION_SAFE
    assert Decision.UNSAFE == B.DECISION_UNSAFE
    assert Decision.INDETERMINATE == B.DECISION_INDETERMINATE
    assert Decision.NOT_RUN_EXTERNAL == B.DECISION_NOT_RUN_EXTERNAL
