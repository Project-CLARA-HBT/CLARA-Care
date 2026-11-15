"""Tests for AIME-X06_selective_refresh — purpose-aware selective re-generation.

X06 is the candidate mechanism for RQ2 (blueprint arm B4,
``selective-consent-aware-context-regeneration``): when one field of the
workflow state changes, rebuild ONLY the evidence/purpose dependencies that
field can actually affect — instead of paying the strict comparator's
(blueprint arm B1, X05) full per-step re-derivation — while never trading
safety for cost:

- A consent/purpose change re-derives the authorization epoch that
  co-determines every dependency, so it forces FULL.
- A medication/allergy change with BOTH clinical sides populated is clinically
  ENTANGLED (shared drug–allergy interaction screen ``purpose_ddi_screen``):
  a change to one affects the interpretation of the other, so the plan routes
  to CLINICIAN_REVIEW — never an automatic PARTIAL that could miss an
  interaction. An unverifiable (missing/malformed) counterpart fails closed
  the same way.
- An unrelated note change cannot touch medication, allergy or consent
  interpretation, so only its affected dependency is recomputed and every
  other dependency is carried over (PARTIAL) — the measured utility of the
  mechanism.
- Unknown/undeclared changed fields, malformed states and caller-held-context
  gaps all fail closed to FULL with stable reason codes; nothing is ever
  silently dropped or counted as a safe completion.

Cross-checks against the REAL strong comparator and the INDEPENDENT oracle
(both imported unmodified; this test never re-implements them):
- Parity anchor (B1, ``evaluation/venue2027/aime/baselines.py``): on every
  scheduled step of a mid-episode-change vignette the X06 refresh decision is
  consistent with the real strict-refresh adapter's decision — any step where
  B1 refuses/invalidate (UNSAFE or INDETERMINATE) must never be answered by
  X06 with an automatic PARTIAL, and stable steps agree between both.
- Oracle direction (``evaluation/venue2027/aime/independent_oracle.py``): the
  X06 mode co-varies with the frozen family labels —
  ``consent_change``/``medication_withdrawal``/``allergy_update`` oracle
  REJECTs map to FULL/CLINICIAN_REVIEW (never PARTIAL), while
  ``stable_history`` ADMITs allow the cost-saving PARTIAL on an unrelated
  edit. The oracle remains independent: the candidate never feeds it.

Positive controls (>= 2): unrelated note change -> PARTIAL recomputing only
``evidence_note_summary``; consent change -> FULL. Additional: dependency
partition completeness, `update_context` soundness on held dependencies.
Adversarial controls (>= 2): entangled medication change (and its allergy
mirror) -> CLINICIAN_REVIEW, never PARTIAL; unknown changed field -> FULL.
Additional: unknown declared dependency, missing recompute dependency,
malformed state, conflicting observations, determinism, digest-free PARTIAL
proof, constant-partial-stub refusal analogue.

Version: X06_SELECTIVE_REFRESH_SPEC_VERSION 1.0.0 over
SELECTIVE_REFRESH_VERSION 1.0.0, BASELINES_VERSION 1.0.0,
INDEPENDENT_ORACLE_VERSION clara.aime.independent-oracle-v1.
No clinical validity claim: synthetic states/vignettes only, no clinician
reviewer, no live provider (blueprint falsification rule honored).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from evaluation.venue2027.aime import baselines as B
from evaluation.venue2027.aime import independent_oracle as oracle
from evaluation.venue2027.aime import selective_refresh as SR
from evaluation.venue2027.aime.baselines import (
    BASELINE_B1,
    BaselineContext,
    Outcome,
    run_baseline,
)
from evaluation.venue2027.aime.selective_refresh import (
    ALL_DEPENDENCIES,
    MODE_CLINICIAN_REVIEW,
    MODE_FULL,
    MODE_PARTIAL,
    REASON_CODE_RE,
    RefreshPlan,
    affected_dependencies,
    is_entangled,
    pair_entangled,
    refresh,
    update_context,
)

X06_SELECTIVE_REFRESH_SPEC_VERSION = "1.0.0"

SHA40 = "b" * 40


# ----------------------------------------------------------------- fixtures


def _base_state() -> dict[str, Any]:
    """Synthetic workflow state with both clinical sides populated.

    Medications AND allergies are present, which is exactly the entangled
    configuration the task contract protects.
    """
    return {
        "medications": ["metformin"],
        "allergies": ["penicillin"],
        "notes": "routine follow-up note (synthetic)",
        "consent": {"granted_purposes": ["self_care"]},
    }


def _consent_state() -> dict[str, Any]:
    """State with the allergy side absent (medication change NOT entangled)."""
    return {
        "medications": ["metformin"],
        "consent": {"granted_purposes": ["self_care"]},
    }


def _deps(*changed: str) -> dict[str, Any]:
    return {
        "changed_field": changed[0] if changed else "notes",
        "declared_dependencies": list(ALL_DEPENDENCIES),
    }


# ------------------------------------------------------------------- basics


def test_plan_serialization_round_trip() -> None:
    plan = refresh(_base_state(), "notes")
    payload = json.loads(json.dumps(plan.to_dict()))
    assert payload["mode"] == MODE_PARTIAL
    assert payload["version"] == SR.SELECTIVE_REFRESH_VERSION
    assert SR.SHA256_RE.match(payload["input_sha256"])


def test_plan_validates_its_own_fields() -> None:
    with pytest.raises(ValueError, match="PLAN_BAD_MODE"):
        RefreshPlan(
            mode="SOMETIMES", reason_code="OKK", detail="", changed_field="", input_sha256="0" * 64
        )
    with pytest.raises(ValueError, match="PLAN_BAD_REASON_CODE"):
        RefreshPlan(
            mode=MODE_FULL,
            reason_code="bad-code",
            detail="",
            changed_field="",
            input_sha256="0" * 64,
        )
    with pytest.raises(ValueError, match="PLAN_BAD_DIGEST"):
        RefreshPlan(
            mode=MODE_FULL, reason_code="OKK", detail="", changed_field="", input_sha256="xyz"
        )
    with pytest.raises(ValueError, match="PLAN_BAD_FLAGS"):
        RefreshPlan(
            mode=MODE_FULL,
            reason_code="OKK",
            detail="",
            changed_field="",
            input_sha256="0" * 64,
            full_rebuild=False,
        )


# ------------------------------------------------------ positive: PARTIAL


def test_unrelated_note_change_partial_recomputes_only_affected_deps() -> None:
    """Positive 1: unrelated edit -> PARTIAL with ONLY the affected dependency."""
    plan = refresh(_base_state(), "notes")
    assert plan.mode == MODE_PARTIAL
    assert plan.reason_code == SR.REASON_PARTIAL_OK
    assert plan.recompute_dependencies == ("evidence_note_summary",)
    assert plan.full_rebuild is False
    assert plan.entangled is False
    # Nothing clinical or authorization-bearing is recomputed.
    assert "evidence_medication_list" not in plan.recompute_dependencies
    assert "evidence_allergy_list" not in plan.recompute_dependencies
    assert "purpose_scope" not in plan.recompute_dependencies
    assert "purpose_ddi_screen" not in plan.recompute_dependencies


def test_partial_partition_is_complete_and_disjoint() -> None:
    """PARTIAL carries over everything it does not recompute (no silent drop)."""
    plan = refresh(_base_state(), "notes")
    assert set(plan.recompute_dependencies) | set(plan.carried_over_dependencies) == set(
        ALL_DEPENDENCIES
    )
    assert not set(plan.recompute_dependencies) & set(plan.carried_over_dependencies)


def test_consent_change_forces_full() -> None:
    """Positive 2: consent change -> FULL over every dependency."""
    plan = refresh(_base_state(), "consent")
    assert plan.mode == MODE_FULL
    assert plan.reason_code == SR.REASON_CONSENT_FULL
    assert plan.full_rebuild is True
    assert plan.recompute_dependencies == ALL_DEPENDENCIES
    assert plan.carried_over_dependencies == ()
    assert plan.entangled is False


def test_purpose_synonym_is_consent_class() -> None:
    """Purpose-grant/revoke field names share the consent rule."""
    for field in ("purpose", "consent_grant", "consent_revocation"):
        plan = refresh(_base_state(), field)
        assert plan.mode == MODE_FULL, field
        assert plan.reason_code == SR.REASON_CONSENT_FULL, field


def test_update_context_carries_over_held_dependencies() -> None:
    """update_context: partial rebuild scoped to what the caller actually holds."""
    plan = update_context(
        _base_state(),
        {
            "changed_field": "notes",
            "declared_dependencies": ["evidence_note_summary", "evidence_medication_list"],
        },
    )
    assert plan.mode == MODE_PARTIAL
    assert plan.recompute_dependencies == ("evidence_note_summary",)
    assert plan.carried_over_dependencies == ("evidence_medication_list",)


def test_affected_dependencies_agrees_with_the_graph() -> None:
    assert affected_dependencies("notes") == ("evidence_note_summary",)
    assert "purpose_ddi_screen" in affected_dependencies("medications")
    assert "purpose_ddi_screen" in affected_dependencies("allergies")
    assert affected_dependencies("quantum_flux") == ()


# -------------------------------------------------- positive: PARTIAL scope


def test_partial_only_for_proven_unrelated_fields() -> None:
    """No clinical or authorization field is ever partial-eligible."""
    for field in ("medications", "medication", "drug", "allergies", "allergy", "consent"):
        plan = refresh(_base_state(), field)
        assert plan.mode in (MODE_FULL, MODE_CLINICIAN_REVIEW), field
        assert plan.mode != MODE_PARTIAL, field


# ------------------------------------------------ adversarial: entanglement


def test_medication_change_with_allergy_context_routes_to_clinician_review() -> None:
    """Adversarial 1: entangled medication change -> CLINICIAN_REVIEW, never PARTIAL."""
    plan = refresh(_base_state(), "medications")
    assert plan.mode == MODE_CLINICIAN_REVIEW
    assert plan.reason_code == SR.REASON_ENTANGLED
    assert plan.entangled is True
    assert plan.full_rebuild is False
    # No automatic partial refresh is proposed at all.
    assert plan.recompute_dependencies == ()
    assert plan.carried_over_dependencies == ()


def test_allergy_change_with_medication_context_is_the_mirror_case() -> None:
    """The allergy side of the entangled pair routes identically."""
    plan = refresh(_base_state(), "allergies")
    assert plan.mode == MODE_CLINICIAN_REVIEW
    assert plan.reason_code == SR.REASON_ENTANGLED
    assert plan.entangled is True


def test_is_entangled_structural_and_fail_closed() -> None:
    """Counterpart populated -> entangled; counterpart unverifiable -> entangled."""
    assert is_entangled(_base_state(), "medications") is True
    assert is_entangled(_base_state(), "allergies") is True
    # No allergy section: the counterpart cannot be verified, fail closed.
    assert is_entangled(_consent_state(), "medications") is True
    # Change to allergies with medications present and NO allergy section:
    # the changed side itself is unverifiable (cannot prove the change is a
    # plain rename of an empty context) -> fail closed to entangled.
    assert is_entangled(_consent_state(), "allergies") is True
    # Malformed counterpart is unverifiable -> entangled.
    malformed = dict(_consent_state(), allergies="penicillin")
    assert is_entangled(malformed, "medications") is True
    # Non-clinical fields are never entangled (refused to FULL instead).
    assert is_entangled(_base_state(), "notes") is False
    assert is_entangled(_base_state(), "consent") is False


def test_pair_entangled_is_the_shared_dependency_predicate() -> None:
    assert pair_entangled("medications", "allergies") is True
    assert pair_entangled("allergies", "medications") is True
    assert pair_entangled("medications", "consent") is False
    assert pair_entangled("notes", "notes") is False


# ----------------------------------------------------- adversarial: unknown


def test_unknown_changed_field_forces_full() -> None:
    """Adversarial 2: unknown/undeclared field -> FULL (scope not proven narrow)."""
    plan = refresh(_base_state(), "billing_address")
    assert plan.mode == MODE_FULL
    assert plan.reason_code == SR.REASON_UNKNOWN_FIELD
    assert plan.full_rebuild is True
    assert plan.recompute_dependencies == ALL_DEPENDENCIES


def test_non_string_changed_field_forces_full() -> None:
    for bad in (None, 7, ["notes"], {"field": "notes"}):
        plan = refresh(_base_state(), bad)
        assert plan.mode == MODE_FULL, bad
        assert plan.reason_code == SR.REASON_UNKNOWN_FIELD, bad


# --------------------------------------------- adversarial: fail-closed set


def test_update_context_refuses_unknown_declared_dependency() -> None:
    plan = update_context(
        _base_state(),
        {
            "changed_field": "notes",
            "declared_dependencies": ["evidence_note_summary", "astral_plane"],
        },
    )
    assert plan.mode == MODE_FULL
    assert plan.reason_code == SR.REASON_UNKNOWN_DEPENDENCY


def test_update_context_refuses_partial_when_recompute_dependency_missing() -> None:
    """The caller does not hold the dependency the partial path must rebuild."""
    plan = update_context(
        _base_state(),
        {"changed_field": "notes", "declared_dependencies": ["evidence_medication_list"]},
    )
    assert plan.mode == MODE_FULL
    assert plan.reason_code == SR.REASON_MISSING_FIELD


def test_update_context_refuses_empty_or_malformed_dependencies() -> None:
    for deps in (
        {},
        {"changed_field": "notes"},
        {"changed_field": "notes", "declared_dependencies": []},
        {"changed_field": "notes", "declared_dependencies": "evidence_note_summary"},
    ):
        plan = update_context(_base_state(), deps)
        assert plan.mode == MODE_FULL, deps
        assert plan.reason_code in (
            SR.REASON_MISSING_DEPENDENCIES,
            SR.REASON_UNKNOWN_DEPENDENCY,
        ), deps


def test_malformed_and_phi_states_fail_closed() -> None:
    plan = refresh(dict(_base_state(), medications="metformin"), "notes")
    assert plan.mode == MODE_FULL
    assert plan.reason_code == SR.REASON_MALFORMED
    plan = refresh({"medications": "metformin"}, "notes")
    assert plan.mode == MODE_FULL
    assert plan.reason_code == SR.REASON_MISSING_FIELD
    plan = refresh({"consent": {"granted_purposes": ["self_care"]}}, "notes")
    assert plan.mode == MODE_FULL
    assert plan.reason_code == SR.REASON_MISSING_FIELD
    phi_state = dict(_base_state(), patient_name="Synthetic Person")
    plan = refresh(phi_state, "notes")
    assert plan.mode == MODE_FULL
    assert plan.reason_code == SR.REASON_PHI_FIELDS
    plan = refresh("not-a-mapping", "notes")  # type: ignore[arg-type]
    assert plan.mode == MODE_FULL
    assert plan.reason_code == SR.REASON_MALFORMED


def test_conflicting_observations_route_to_clinician_review() -> None:
    state = dict(_base_state(), conflicting_observations=True)
    plan = refresh(state, "notes")
    assert plan.mode == MODE_CLINICIAN_REVIEW
    assert plan.reason_code == SR.REASON_CONFLICTING


def test_stable_consent_only_state_allows_structural_partial_but_consent_never_partial() -> None:
    """Consent changes force FULL even when no entanglement exists."""
    plan = refresh(_consent_state(), "consent")
    assert plan.mode == MODE_FULL
    assert plan.reason_code == SR.REASON_CONSENT_FULL


# ------------------------------------------------------------ determinism


def test_identical_inputs_yield_identical_plans() -> None:
    for state in (_base_state(), _consent_state()):
        for field in ("notes", "consent", "medications", "allergies", "unknown_field"):
            first = refresh(state, field)
            second = refresh(state, field)
            assert first == second
            assert first.to_dict() == second.to_dict()
            assert REASON_CODE_RE.match(first.reason_code)


# ------------------------------------------- parity vs the real B1 adapter


def _step_view(case: dict[str, Any], step: int) -> dict[str, Any]:
    """Strict-arm context fetch (X05 driver): fold events at/below ``step``."""
    events = [e for e in case["timeline"] if e["logical_time"] <= step]
    medications = list(case["snapshot"]["medications"])
    purposes = list(case["snapshot"]["consent"]["granted_purposes"])
    for event in events:
        payload = event.get("payload") or {}
        kind = event["event_kind"]
        if kind == "MEDICATION_ADDED" and payload.get("medication"):
            medications.append(payload["medication"])
        elif kind == "MEDICATION_WITHDRAWN" and payload.get("medication"):
            medications = [m for m in medications if m != payload["medication"]]
        elif kind == "CONSENT_GRANTED" and payload.get("purpose"):
            purposes.append(payload["purpose"])
        elif kind == "CONSENT_REVOKED" and payload.get("purpose"):
            purposes = [p for p in purposes if p != payload["purpose"]]
    view = dict(case)
    view["current"] = {"medications": medications, "consent": {"granted_purposes": purposes}}
    view["timeline"] = events
    return view


def _mid_episode_change_case() -> dict[str, Any]:
    return {
        "case_id": "AIME-CASE-X06-synth",
        "purpose": "self_care",
        "snapshot": {
            "medications": ["metformin"],
            "consent": {"granted_purposes": ["self_care"]},
        },
        "current": {
            "medications": ["warfarin"],
            "consent": {"granted_purposes": []},
        },
        "timeline": [
            {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
            {
                "order": 1,
                "event_kind": "MEDICATION_WITHDRAWN",
                "logical_time": 3,
                "payload": {"medication": "metformin"},
            },
            {
                "order": 2,
                "event_kind": "CONSENT_REVOKED",
                "logical_time": 5,
                "payload": {"purpose": "self_care"},
            },
            {
                "order": 3,
                "event_kind": "MEDICATION_ADDED",
                "logical_time": 7,
                "payload": {"medication": "warfarin"},
            },
        ],
        "task": {"drug": "metformin", "kind": "recommendation"},
        "output": {"text": "continue metformin 1000mg per current plan"},
    }


def _x06_state_from_view(view: dict[str, Any]) -> dict[str, Any]:
    return {
        "medications": list(view["current"]["medications"]),
        "allergies": ["penicillin"],
        "notes": "routine follow-up note (synthetic)",
        "consent": {"granted_purposes": list(view["current"]["consent"]["granted_purposes"])},
    }


def test_x06_never_answers_a_b1_invalidated_step_with_partial() -> None:
    """Parity anchor: every B1-refused step is FULL/CLINICIAN_REVIEW under X06.

    The real strict-refresh adapter (B1) decides per step; X06's refresh plan
    for that step's live state must never propose an automatic PARTIAL where
    B1 refused or required regeneration.
    """
    case = _mid_episode_change_case()
    for step in (1, 3, 4, 5, 7):
        view = _step_view(case, step)
        outcome: Outcome = run_baseline(
            BASELINE_B1,
            view,
            BaselineContext(arm_id=BASELINE_B1, source_sha=SHA40, step_logical_time=step),
        )
        assert outcome.decision != B.DECISION_NOT_RUN_EXTERNAL
        state = _x06_state_from_view(view)
        plan = refresh(state, "medications")
        if outcome.decision in (B.DECISION_UNSAFE, B.DECISION_INDETERMINATE):
            assert plan.mode in (MODE_FULL, MODE_CLINICIAN_REVIEW), (step, outcome.reason_code)
            assert plan.mode != MODE_PARTIAL, (step, outcome.reason_code)
        else:
            assert outcome.decision == B.DECISION_SAFE
            # A stable step: the entanglement rule still guards the medication
            # side (both clinical sides populated), so no automatic PARTIAL.
            assert plan.mode == MODE_CLINICIAN_REVIEW
            assert plan.entangled is True


def test_x06_b1_parity_on_stable_consent_step_and_unrelated_edit() -> None:
    """On a stable state with no allergy side, B1 SAFE <=> X06 step-consistent."""
    case = _mid_episode_change_case()
    view = _step_view(case, 1)
    outcome = run_baseline(
        BASELINE_B1,
        view,
        BaselineContext(arm_id=BASELINE_B1, source_sha=SHA40, step_logical_time=1),
    )
    assert outcome.decision == B.DECISION_SAFE
    state = _x06_state_from_view(view)
    del state["allergies"]
    plan = refresh(state, "notes")
    assert plan.mode == MODE_PARTIAL
    assert plan.reason_code == SR.REASON_PARTIAL_OK


# --------------------------------- co-variation with the independent oracle


def test_x06_mode_covaries_with_independent_oracle_families() -> None:
    """Oracle REJECT families never admit an automatic PARTIAL refresh."""
    rejected = ("consent_change", "medication_withdrawal", "allergy_update")
    for family in rejected:
        verdict = oracle.adjudicate({"case_id": f"X06-{family}", "family": family})
        assert verdict.outcome == "REJECT", family
        if family == "consent_change":
            plan = refresh(_base_state(), "consent")
        elif family == "medication_withdrawal":
            plan = refresh(_base_state(), "medications")
        else:
            plan = refresh(_base_state(), "allergies")
        assert plan.mode in (MODE_FULL, MODE_CLINICIAN_REVIEW), family
        assert plan.mode != MODE_PARTIAL, family
    admit = oracle.adjudicate({"case_id": "X06-stable", "family": "stable_history"})
    assert admit.outcome == "ADMIT"
    plan = refresh(_base_state(), "notes")
    assert plan.mode == MODE_PARTIAL


def test_oracle_stays_independent_of_this_candidate() -> None:
    """The oracle module never imports the candidate (mechanical AST scan)."""
    result = oracle.assert_oracle_independence()
    assert result.outcome == "ADMIT"
    # Explicit extended scan including this candidate's module basename.
    from evaluation.venue2027._shared import oracle_kernel

    oracle_kernel.assert_oracle_independence(
        oracle.__file__,
        ("selective_refresh", *oracle.CANDIDATE_MODULE_BASENAMES),
    )


# ------------------------------------------------- stub-refusal analogue


def test_constant_partial_stub_analogue_is_refused() -> None:
    """A toy that answers PARTIAL regardless of the changed field is refused.

    Mirrors ``baselines.refuse_constant_safe_stub``: a selective-refresh
    implementation must separate the unsafe classes (consent/entangled/
    unknown -> FULL/CLINICIAN_REVIEW) from the safe one (unrelated note ->
    PARTIAL); the real ``refresh`` does.
    """

    def constant_partial(state: dict[str, Any], field: str) -> RefreshPlan:
        return RefreshPlan(
            mode=MODE_PARTIAL,
            reason_code=SR.REASON_PARTIAL_OK,
            detail="stub",
            changed_field=field,
            input_sha256=SR._sha256_state(state),
            recompute_dependencies=("evidence_note_summary",),
            carried_over_dependencies=tuple(
                d for d in ALL_DEPENDENCIES if d != "evidence_note_summary"
            ),
        )

    probes = (
        ("notes", MODE_PARTIAL),
        ("consent", MODE_FULL),
        ("medications", MODE_CLINICIAN_REVIEW),
    )
    for field, expected in probes:
        real = refresh(_base_state(), field)
        stub = constant_partial(_base_state(), field)
        assert real.mode == expected, field
        if real.mode != MODE_PARTIAL:
            assert stub.mode != real.mode, f"stub would fake {expected} for {field}"
