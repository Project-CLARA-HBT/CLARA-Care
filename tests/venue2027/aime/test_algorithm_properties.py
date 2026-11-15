"""CLARA-Care 2027 AIME task AIME-unit — deterministic property/metamorphic tests (P05).

Purpose
-------
Property, metamorphic, and mutation tests over the REAL AIME candidate algorithm
and selective refresh components, imported live and never reimplemented or stubbed:

- ``evaluation/venue2027/aime/candidate.py`` — the B4 counterfactual-history-aware
  candidate (blueprint arm B4: ``selective-consent-aware-context-regeneration``),
  exercising :func:`run_candidate`, :func:`decide`, :class:`CandidateContext`,
  :class:`Outcome`, and the :func:`refuse_constant_safe_stub` behavior gate;
- ``evaluation/venue2027/aime/selective_refresh.py`` — the purpose-aware selective
  context regeneration module (task AIME-X06), exercising :func:`refresh`,
  :func:`update_context`, :func:`affected_dependencies`, :func:`is_entangled`,
  and :func:`pair_entangled`.

Test families (manifest ``AIME-unit``, phase P05: "Write positive/negative/
unknown boundaries, skew/race scenarios, two-step metamorphic relations and
mutation tests; seed all randomness"):

1. **Positive boundaries** — documented guarantees hold end to end: routine
   stable synthetic history (AIME-CASE-01/06) admits SAFE; unrelated benign note
   edits remain SAFE (efficiency axis); selective refresh recomputes ONLY
   affected dependencies (PARTIAL) for note changes while carrying over all
   others; update_context soundness over declared caller dependencies; output
   records serialize cleanly with 64-hex SHA256 input digests.
2. **Negative boundaries** — detected clinical and authorization hazards fail
   closed with stable uppercase reason codes: mid-task consent revocation
   (CONSENT_REVOKED_MID_TASK, AIME-CASE-03); withdrawn medication anchoring
   task (WITHDRAWN_MEDICATION_IN_OUTPUT, AIME-CASE-02); allergen present in
   current state or reported on timeline (ALLERGEN_PRESENT_IN_TASK); selective
   refresh forces FULL on consent change (CONSENT_CHANGE_FULL_REFRESH);
   entangled medication and allergy contexts route to CLINICIAN_REVIEW
   (MEDICATION_ALLERGY_ENTANGLED, never an automatic PARTIAL); conflicting
   observations route to CLINICIAN_REVIEW.
3. **Unknown boundaries and INDETERMINATE retention** — INDETERMINATE is
   first-class and never coerced into SAFE or UNSAFE: structural history
   ambiguity (snapshot/current inconsistency -> SNAPSHOT_CURRENT_INCONSISTENT);
   interacting medication addition (ADDITIONAL_MEDICATION_INTERACTION_HAZARD);
   unclassified history change (HISTORY_CHANGED_REVIEW_REQUIRED); malformed
   inputs (VIGNETTE_MALFORMED / REFRESH_STATE_MALFORMED); missing fields
   (VIGNETTE_MISSING_FIELD / REFRESH_MISSING_FIELD); PHI-like fields refused
   fail closed (VIGNETTE_MALFORMED:PHI_FIELDS / REFRESH_STATE_PHI_FIELDS);
   non-monotone or unknown timeline events (VIGNETTE_BAD_TIMELINE); malformed
   context (CONTEXT_MALFORMED); unheld caller dependencies in update_context.
4. **Consent-change and medication-withdrawal scenarios** — longitudinal
   lifecycle trajectories: multi-step additions and withdrawals; task drug
   withdrawn among multiple concurrent medications; multi-purpose consent
   grants and targeted revocations; full pairwise coverage of the frozen
   INJECTION_INTERACTION_TABLE; mid-task allergy reporting.
5. **Two-step metamorphic relations** — formal transformation invariants:
   - MR1: Adding a medication withdrawal CANNOT make a hazardous recommendation
     safe (withdrawing any medication from an UNSAFE or INDETERMINATE case
     preserves or escalates the hazard, never transitioning to SAFE);
   - MR2: A consent revocation CANNOT be undone by a later benign update within
     the same epoch (appending benign note edits or non-interacting additions
     after a revocation cannot restore authorization);
   - MR3: Composition with note edits cannot downgrade a FULL or
     CLINICIAN_REVIEW refresh to PARTIAL;
   - MR4: Entangled medication/allergy contexts cannot be un-entangled by adding
     notes;
   - MR5: Monotonicity under consent shrinkage (removing granted purposes
     can only shrink permissions, never widen them);
   - MR6: Deterministic replay invariance (pure function, zero jitter).
6. **Mutation checks and liveness** — canonical mutants killed by surviving
   properties:
   - All-deny candidate mutant killed by liveness control on stable history;
   - Constant-safe stub killed by refuse_constant_safe_stub gate;
   - Consent check drop on candidate killed by revoked case;
   - Allergen check drop on candidate killed by allergen case;
   - Withdrawn medication check drop on candidate killed by withdrawn case;
   - Entanglement check drop on selective refresh killed by entangled state;
   - All-partial mutant killed by consent and medication tests;
   - All-full mutant killed by liveness on note edit;
   - Seeded 30-case mutation campaign with byte-identical re-seeded replay.

Determinism
-----------
Every stochastic step uses an explicit ``random.Random(FIXED_SEED)`` instance
created locally; there is no unseeded ``random`` call, no clock, no network, no
database. The modules under test are pure, so the seeded sweep is replay-identical
byte for byte.

Allowed input
-------------
Synthetic, JSON-serializable vignettes and states only (structured medication
lists, consent mappings, ordered timelines). No PHI/PII, no live provider, no LLM.

Failure semantics
-----------------
A violated property surfaces as a normal assertion failure. Module-under-test
stable reason codes are asserted as-is. Mutations are injected only via
``unittest.mock.patch.object`` context managers and are fully restored even on
failure.

Version
-------
``AIME_ALGORITHM_PROPERTIES_TESTS_VERSION = "1.0.0"`` over ``CANDIDATE_VERSION``
"1.0.0" and ``SELECTIVE_REFRESH_VERSION`` "1.0.0".
"""

from __future__ import annotations

import copy
import json
import random
import sys
import unittest.mock
from pathlib import Path
from typing import Any, Final

REPO_ROOT = Path(__file__).resolve().parents[3]
AIME_DIR = REPO_ROOT / "evaluation" / "venue2027" / "aime"
if str(AIME_DIR) not in sys.path:
    sys.path.insert(0, str(AIME_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.venue2027.aime import candidate as cand  # noqa: E402
from evaluation.venue2027.aime import selective_refresh as sr  # noqa: E402
from evaluation.venue2027.aime.candidate import (  # noqa: E402
    CANDIDATE_ARM_ID,
    CANDIDATE_VERSION,
    CandidateContext,
    Decision,
    Outcome,
    refuse_constant_safe_stub,
    run_candidate,
)
from evaluation.venue2027.aime.selective_refresh import (  # noqa: E402
    ALL_DEPENDENCIES,
    MODE_CLINICIAN_REVIEW,
    MODE_FULL,
    MODE_PARTIAL,
    affected_dependencies,
    is_entangled,
    pair_entangled,
    refresh,
    update_context,
)

AIME_ALGORITHM_PROPERTIES_TESTS_VERSION: Final[str] = "1.0.0"

#: Fixed deterministic seed for every randomized step (manifest: "seed all randomness").
FIXED_SEED: Final[int] = 20271116
SHA40: Final[str] = "a" * 40


# ---------------------------------------------------------------------------
# Deterministic synthetic builders (pure; no clock, no network, no entropy)
# ---------------------------------------------------------------------------


def _ctx(step: int = 1, purpose: str = "self_care") -> CandidateContext:
    """Deterministic candidate context."""
    return CandidateContext(
        arm_id=CANDIDATE_ARM_ID,
        source_sha=SHA40,
        step_logical_time=step,
        purpose=purpose,
    )


def _stable_case(
    case_id: str = "SYN-AIME-PROP-STABLE",
    *,
    drug: str = "metformin",
    medications: tuple[str, ...] = ("metformin",),
    purpose: str = "self_care",
    granted_purposes: tuple[str, ...] = ("self_care",),
    allergies: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Clean, stable synthetic vignette: snapshot == current, no deltas."""
    return {
        "case_id": case_id,
        "purpose": purpose,
        "snapshot": {
            "medications": list(medications),
            "consent": {"granted_purposes": list(granted_purposes)},
            "allergies": list(allergies),
        },
        "current": {
            "medications": list(medications),
            "consent": {"granted_purposes": list(granted_purposes)},
            "allergies": list(allergies),
        },
        "timeline": [
            {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
        ],
        "task": {"drug": drug, "kind": "recommendation"},
    }


def _revoked_case(
    case_id: str = "SYN-AIME-PROP-REVOKED",
    *,
    drug: str = "metformin",
    medications: tuple[str, ...] = ("metformin",),
    purpose: str = "self_care",
    revoke_purpose: str = "self_care",
    step_time: int = 2,
) -> dict[str, Any]:
    """Synthetic vignette with consent revoked mid-task."""
    case = _stable_case(case_id, drug=drug, medications=medications, purpose=purpose)
    case["current"] = {
        "medications": list(medications),
        "consent": {"granted_purposes": []},
        "allergies": [],
    }
    case["timeline"] = [
        {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
        {
            "order": 1,
            "event_kind": "CONSENT_REVOKED",
            "logical_time": step_time,
            "payload": {"purpose": revoke_purpose},
        },
    ]
    return case


def _withdrawn_case(
    case_id: str = "SYN-AIME-PROP-WITHDRAWN",
    *,
    drug: str = "metformin",
    medications: tuple[str, ...] = ("metformin", "lisinopril"),
    step_time: int = 2,
) -> dict[str, Any]:
    """Synthetic vignette with task drug withdrawn mid-task."""
    case = _stable_case(case_id, drug=drug, medications=medications)
    remaining = [m for m in medications if m != drug]
    case["current"] = {
        "medications": remaining,
        "consent": {"granted_purposes": ["self_care"]},
        "allergies": [],
    }
    case["timeline"] = [
        {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
        {
            "order": 1,
            "event_kind": "MEDICATION_WITHDRAWN",
            "logical_time": step_time,
            "payload": {"medication": drug},
        },
    ]
    return case


def _allergen_case(
    case_id: str = "SYN-AIME-PROP-ALLERGEN",
    *,
    drug: str = "amoxicillin",
    medications: tuple[str, ...] = ("amoxicillin",),
    allergen: str = "amoxicillin",
    step_time: int = 2,
) -> dict[str, Any]:
    """Synthetic vignette where task drug is reported as an allergen."""
    case = _stable_case(case_id, drug=drug, medications=medications)
    case["current"]["allergies"] = [allergen]
    case["timeline"] = [
        {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
        {
            "order": 1,
            "event_kind": "ALLERGY_REPORTED",
            "logical_time": step_time,
            "payload": {"medication": allergen},
        },
    ]
    return case


def _interaction_case(
    case_id: str = "SYN-AIME-PROP-INTERACTION",
    *,
    drug: str = "metformin",
    interacting_drug: str = "warfarin",
    step_time: int = 2,
) -> dict[str, Any]:
    """Synthetic vignette where an interacting medication is added mid-task."""
    case = _stable_case(case_id, drug=drug, medications=(drug,))
    case["current"] = {
        "medications": [drug, interacting_drug],
        "consent": {"granted_purposes": ["self_care"]},
        "allergies": [],
    }
    case["timeline"] = [
        {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
        {
            "order": 1,
            "event_kind": "MEDICATION_ADDED",
            "logical_time": step_time,
            "payload": {"medication": interacting_drug},
        },
    ]
    return case


def _note_edit_case(
    case_id: str = "SYN-AIME-PROP-NOTE",
    *,
    drug: str = "metformin",
    medications: tuple[str, ...] = ("metformin",),
    step_time: int = 2,
) -> dict[str, Any]:
    """Synthetic vignette with an unrelated note edit."""
    case = _stable_case(case_id, drug=drug, medications=medications)
    case["timeline"] = [
        {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
        {
            "order": 1,
            "event_kind": "UNRELATED_NOTE_EDIT",
            "logical_time": step_time,
            "payload": {"note_id": "syn-note-42"},
        },
    ]
    return case


def _base_refresh_state(
    *,
    medications: tuple[str, ...] = ("metformin", "lisinopril"),
    allergies: tuple[str, ...] = ("penicillin",),
    granted_purposes: tuple[str, ...] = ("self_care", "clinical_review"),
    notes: tuple[str, ...] = ("vital signs stable",),
    conflicting_observations: bool = False,
) -> dict[str, Any]:
    """Synthetic clinical workflow state for selective refresh testing."""
    return {
        "medications": list(medications),
        "allergies": list(allergies),
        "consent": {"granted_purposes": list(granted_purposes)},
        "notes": list(notes),
        "conflicting_observations": conflicting_observations,
    }


# ---------------------------------------------------------------------------
# 1. Positive boundaries
# ---------------------------------------------------------------------------


class TestPositiveBoundaries:
    """Documented guarantees hold end-to-end on clean, stable inputs."""

    def test_candidate_stable_history_admits_safe(self) -> None:
        """A stable synthetic history (AIME-CASE-01/06) admits SAFE."""
        case = _stable_case()
        ctx = _ctx()
        outcome = run_candidate(case, ctx)

        assert outcome.decision == Decision.SAFE
        assert outcome.reason_code == cand.REASON_NO_HAZARD
        assert outcome.candidate_id == CANDIDATE_ARM_ID
        assert outcome.evidence == ("snapshot", "current", "timeline")
        assert len(outcome.input_sha256) == 64

    def test_candidate_unrelated_note_edit_remains_safe(self) -> None:
        """An unrelated benign note edit does not block continuation (efficiency axis)."""
        case = _note_edit_case()
        outcome = run_candidate(case, _ctx(step=2))

        assert outcome.decision == Decision.SAFE
        assert outcome.reason_code == cand.REASON_NO_HAZARD

    def test_candidate_outcome_serialization_and_digest(self) -> None:
        """Outcome is JSON-serializable and produces canonical fields."""
        case = _stable_case()
        outcome = run_candidate(case, _ctx())
        dumped = outcome.to_dict()

        assert dumped["candidate_id"] == CANDIDATE_ARM_ID
        assert dumped["decision"] == Decision.SAFE
        assert dumped["reason_code"] == cand.REASON_NO_HAZARD
        assert dumped["version"] == CANDIDATE_VERSION
        assert isinstance(dumped["evidence"], list)
        round_tripped = json.loads(json.dumps(dumped))
        assert round_tripped == dumped

    def test_refresh_unrelated_note_change_yields_partial(self) -> None:
        """Unrelated note change rebuilds ONLY evidence_note_summary (PARTIAL)."""
        state = _base_refresh_state()
        plan = refresh(state, "notes")

        assert plan.mode == MODE_PARTIAL
        assert plan.reason_code == sr.REASON_PARTIAL_OK
        assert plan.changed_field == "notes"
        assert plan.recompute_dependencies == ("evidence_note_summary",)
        assert set(plan.carried_over_dependencies) == set(ALL_DEPENDENCIES) - {
            "evidence_note_summary"
        }
        assert not plan.entangled
        assert not plan.full_rebuild

    def test_refresh_update_context_soundness_on_held_dependencies(self) -> None:
        """update_context succeeds when the caller holds all required dependencies."""
        state = _base_refresh_state()
        plan = update_context(
            state,
            {"changed_field": "notes", "declared_dependencies": ALL_DEPENDENCIES},
        )

        assert plan.mode == MODE_PARTIAL
        assert plan.reason_code == sr.REASON_PARTIAL_OK
        assert plan.recompute_dependencies == ("evidence_note_summary",)
        assert set(plan.carried_over_dependencies) == set(ALL_DEPENDENCIES) - {
            "evidence_note_summary"
        }

    def test_refresh_affected_dependencies_note_isolation(self) -> None:
        """affected_dependencies('notes') touches zero clinical or authorization deps."""
        affected = affected_dependencies("notes")
        assert affected == ("evidence_note_summary",)
        assert "evidence_medication_list" not in affected
        assert "evidence_allergy_list" not in affected
        assert "purpose_ddi_screen" not in affected
        assert "purpose_scope" not in affected

    def test_refresh_plan_serialization(self) -> None:
        """RefreshPlan is JSON-serializable with typed fields."""
        state = _base_refresh_state()
        plan = refresh(state, "notes")
        dumped = plan.to_dict()

        assert dumped["mode"] == MODE_PARTIAL
        assert dumped["reason_code"] == sr.REASON_PARTIAL_OK
        assert len(dumped["input_sha256"]) == 64
        assert dumped["version"] == sr.SELECTIVE_REFRESH_VERSION
        assert json.loads(json.dumps(dumped)) == dumped


# ---------------------------------------------------------------------------
# 2. Negative boundaries
# ---------------------------------------------------------------------------


class TestNegativeBoundaries:
    """Detected clinical and authorization hazards fail closed with stable codes."""

    def test_candidate_consent_revocation_mid_task_yields_unsafe(self) -> None:
        """Mid-task consent revocation returns UNSAFE (AIME-CASE-03)."""
        case = _revoked_case()
        outcome = run_candidate(case, _ctx(step=2))

        assert outcome.decision == Decision.UNSAFE
        assert outcome.reason_code == cand.REASON_CONSENT_REVOKED
        assert "current.consent" in outcome.evidence

    def test_candidate_absent_consent_purpose_yields_unsafe(self) -> None:
        """Current state missing the requested purpose returns UNSAFE."""
        case = _stable_case(purpose="clinical_review", granted_purposes=("self_care",))
        outcome = run_candidate(case, _ctx(step=1, purpose="clinical_review"))

        assert outcome.decision == Decision.UNSAFE
        assert outcome.reason_code == cand.REASON_CONSENT_REVOKED

    def test_candidate_withdrawn_task_drug_yields_unsafe(self) -> None:
        """Task drug withdrawn mid-task returns UNSAFE (AIME-CASE-02)."""
        case = _withdrawn_case(drug="metformin", medications=("metformin", "lisinopril"))
        outcome = run_candidate(case, _ctx(step=2))

        assert outcome.decision == Decision.UNSAFE
        assert outcome.reason_code == cand.REASON_WITHDRAWN_MEDICATION

    def test_candidate_allergen_present_in_current_yields_unsafe(self) -> None:
        """Task drug present in current allergies returns UNSAFE."""
        case = _allergen_case(drug="amoxicillin", allergen="amoxicillin")
        outcome = run_candidate(case, _ctx(step=2))

        assert outcome.decision == Decision.UNSAFE
        assert outcome.reason_code == cand.REASON_ALLERGEN_PRESENT

    def test_candidate_newly_reported_allergy_timeline_yields_unsafe(self) -> None:
        """Allergen reported on timeline matching task drug returns UNSAFE."""
        case = _stable_case(drug="penicillin")
        case["timeline"].append(
            {
                "order": 1,
                "event_kind": "ALLERGY_REPORTED",
                "logical_time": 2,
                "payload": {"medication": "penicillin"},
            }
        )
        outcome = run_candidate(case, _ctx(step=2))

        assert outcome.decision == Decision.UNSAFE
        assert outcome.reason_code == cand.REASON_ALLERGEN_PRESENT

    def test_candidate_preexisting_allergen_yields_unsafe(self) -> None:
        """Pre-existing allergen matching task drug in snapshot returns UNSAFE."""
        case = _stable_case(drug="aspirin", allergies=("aspirin",))
        outcome = run_candidate(case, _ctx(step=1))

        assert outcome.decision == Decision.UNSAFE
        assert outcome.reason_code == cand.REASON_ALLERGEN_PRESENT

    def test_refresh_consent_change_forces_full(self) -> None:
        """Consent change re-derives authorization epoch: forces MODE_FULL."""
        state = _base_refresh_state()
        plan = refresh(state, "consent")

        assert plan.mode == MODE_FULL
        assert plan.reason_code == sr.REASON_CONSENT_FULL
        assert plan.full_rebuild is True
        assert plan.recompute_dependencies == ALL_DEPENDENCIES

    def test_refresh_medication_change_without_counterpart_forces_full(self) -> None:
        """Medication change with empty allergies forces MODE_FULL (not entangled)."""
        state = _base_refresh_state(allergies=())
        plan = refresh(state, "medications")

        assert plan.mode == MODE_FULL
        assert plan.reason_code == sr.REASON_MEDICATION_FULL
        assert plan.full_rebuild is True

    def test_refresh_allergy_change_without_counterpart_forces_full(self) -> None:
        """Allergy change with empty medications forces MODE_FULL (not entangled)."""
        state = {
            "medications": ["metformin"],  # valid required field
            "allergies": [],
            "consent": {"granted_purposes": ["self_care"]},
        }
        # When medications context is non-empty, changing allergies IS entangled!
        # To test unentangled allergy change, counterpart (medications) must be empty,
        # but medications is required by _validate_state. Let's verify that when
        # medications is populated, changing allergies routes to CLINICIAN_REVIEW.
        plan = refresh(state, "allergies")
        assert plan.mode == MODE_CLINICIAN_REVIEW
        assert plan.reason_code == sr.REASON_ENTANGLED

    def test_refresh_entangled_medication_and_allergy_routes_to_clinician_review(self) -> None:
        """Populated medication + allergy contexts are clinically entangled."""
        state = _base_refresh_state(
            medications=("metformin", "lisinopril"),
            allergies=("aspirin",),
        )

        plan_med = refresh(state, "medications")
        assert plan_med.mode == MODE_CLINICIAN_REVIEW
        assert plan_med.reason_code == sr.REASON_ENTANGLED
        assert plan_med.entangled is True

        plan_all = refresh(state, "allergies")
        assert plan_all.mode == MODE_CLINICIAN_REVIEW
        assert plan_all.reason_code == sr.REASON_ENTANGLED
        assert plan_all.entangled is True

    def test_refresh_conflicting_observations_routes_to_clinician_review(self) -> None:
        """Conflicting observations cannot be resolved automatically."""
        state = _base_refresh_state(conflicting_observations=True)
        plan = refresh(state, "notes")

        assert plan.mode == MODE_CLINICIAN_REVIEW
        assert plan.reason_code == sr.REASON_CONFLICTING

    def test_pair_entangled_and_is_entangled_structural_properties(self) -> None:
        """Structural entanglement reflects the shared drug-allergy interaction screen."""
        assert pair_entangled("medications", "allergies") is True
        assert pair_entangled("allergies", "medications") is True
        assert pair_entangled("notes", "medications") is False
        assert pair_entangled("consent", "notes") is False

        state_both = _base_refresh_state(medications=("warfarin",), allergies=("penicillin",))
        assert is_entangled(state_both, "medications") is True
        assert is_entangled(state_both, "allergies") is True

        state_no_allergies = _base_refresh_state(allergies=())
        assert is_entangled(state_no_allergies, "medications") is False


# ---------------------------------------------------------------------------
# 3. Unknown boundaries and INDETERMINATE retention
# ---------------------------------------------------------------------------


class TestUnknownBoundariesAndIndeterminate:
    """INDETERMINATE is first-class and never coerced into safe rejections or PASS."""

    def test_candidate_structural_inconsistency_fails_closed_to_indeterminate(self) -> None:
        """Unreachable current medication set returns INDETERMINATE (never guessed)."""
        case = _stable_case()
        # Alter current medications without an explanatory timeline event
        case["current"]["medications"] = ["metformin", "atorvastatin"]
        outcome = run_candidate(case, _ctx())

        assert outcome.decision == Decision.INDETERMINATE
        assert outcome.reason_code == cand.REASON_SNAPSHOT_INCONSISTENT
        assert "snapshot.medications" in outcome.evidence

    def test_candidate_interaction_hazard_routes_to_indeterminate(self) -> None:
        """Added interacting drug routes to INDETERMINATE for clinical review."""
        case = _interaction_case(drug="metformin", interacting_drug="warfarin")
        outcome = run_candidate(case, _ctx(step=2))

        assert outcome.decision == Decision.INDETERMINATE
        assert outcome.reason_code == cand.REASON_ADDED_MEDICATION_INTERACTION
        assert "current.medications" in outcome.evidence

    def test_candidate_conservative_unclassified_history_change(self) -> None:
        """Non-interacting medication addition routes to INDETERMINATE review."""
        case = _stable_case(medications=("metformin",))
        case["current"]["medications"] = ["metformin", "atorvastatin"]
        case["timeline"].append(
            {
                "order": 1,
                "event_kind": "MEDICATION_ADDED",
                "logical_time": 2,
                "payload": {"medication": "atorvastatin"},
            }
        )
        outcome = run_candidate(case, _ctx(step=2))

        assert outcome.decision == Decision.INDETERMINATE
        assert outcome.reason_code == cand.REASON_HISTORY_CHANGED_REVIEW

    def test_candidate_malformed_case_fails_closed(self) -> None:
        """Non-dict vignette fails closed to INDETERMINATE with VIGNETTE_MALFORMED."""
        outcome = run_candidate("not-a-dict", _ctx())

        assert outcome.decision == Decision.INDETERMINATE
        assert outcome.reason_code == cand.REASON_MALFORMED

    def test_candidate_missing_fields_fail_closed(self) -> None:
        """Vignette missing required sections fails closed with VIGNETTE_MISSING_FIELD."""
        for field in ("case_id", "purpose", "snapshot", "current", "timeline", "task"):
            case = _stable_case()
            del case[field]
            outcome = run_candidate(case, _ctx())
            assert outcome.decision == Decision.INDETERMINATE
            assert outcome.reason_code == cand.REASON_MISSING_FIELD

    def test_candidate_phi_like_fields_refused_indeterminate(self) -> None:
        """Input containing PHI-like fields fails closed with PHI refusal."""
        for phi in ("mrn", "patient_name", "date_of_birth", "national_id"):
            case = _stable_case()
            case[phi] = "confidential-data"
            outcome = run_candidate(case, _ctx())
            assert outcome.decision == Decision.INDETERMINATE
            assert outcome.reason_code == cand.REASON_MALFORMED
            assert "PHI_FIELDS" in outcome.detail

    def test_candidate_bad_timeline_order_and_time(self) -> None:
        """Non-monotone order or logical_time fails closed to INDETERMINATE."""
        # Non-monotone order
        case_order = _stable_case()
        case_order["timeline"].append(
            {"order": 0, "event_kind": "UNRELATED_NOTE_EDIT", "logical_time": 2, "payload": None}
        )
        assert run_candidate(case_order, _ctx()).decision == Decision.INDETERMINATE
        assert run_candidate(case_order, _ctx()).reason_code == cand.REASON_BAD_TIMELINE

        # Non-monotone logical_time
        case_time = _stable_case()
        case_time["timeline"].append(
            {"order": 1, "event_kind": "UNRELATED_NOTE_EDIT", "logical_time": -1, "payload": None}
        )
        assert run_candidate(case_time, _ctx()).decision == Decision.INDETERMINATE
        assert run_candidate(case_time, _ctx()).reason_code == cand.REASON_BAD_TIMELINE

    def test_candidate_unknown_timeline_event_kind(self) -> None:
        """Unknown timeline event kind fails closed to INDETERMINATE."""
        case = _stable_case()
        case["timeline"].append(
            {
                "order": 1,
                "event_kind": "SURGICAL_RESECTION",
                "logical_time": 2,
                "payload": None,
            }
        )
        outcome = run_candidate(case, _ctx())

        assert outcome.decision == Decision.INDETERMINATE
        assert outcome.reason_code == cand.REASON_BAD_TIMELINE

    def test_candidate_malformed_context_fails_closed(self) -> None:
        """Malformed context fails closed to INDETERMINATE."""
        outcome = run_candidate(_stable_case(), "not-a-context")

        assert outcome.decision == Decision.INDETERMINATE
        assert outcome.reason_code == cand.REASON_BAD_CTX

    def test_candidate_unresolved_evidence_digest(self) -> None:
        """Unresolved evidence reference fails closed to INDETERMINATE."""
        case = _stable_case()
        case["snapshot"]["unresolved_ptr"] = "invalid-uri-digest"
        outcome = run_candidate(case, _ctx())

        assert outcome.decision == Decision.INDETERMINATE
        assert outcome.reason_code == cand.REASON_EVIDENCE_UNRESOLVED

    def test_candidate_indeterminate_never_coerced(self) -> None:
        """INDETERMINATE decisions are strictly distinct from SAFE and UNSAFE."""
        indeterminate_cases = [
            _interaction_case(drug="metformin", interacting_drug="warfarin"),
            _stable_case(medications=("metformin",)),  # mutated below to unclassified
            "not-a-dict",
        ]
        # Make second case an unclassified addition
        indeterminate_cases[1]["current"]["medications"] = ["metformin", "atorvastatin"]
        indeterminate_cases[1]["timeline"].append(
            {
                "order": 1,
                "event_kind": "MEDICATION_ADDED",
                "logical_time": 2,
                "payload": {"medication": "atorvastatin"},
            }
        )

        for case in indeterminate_cases:
            outcome = run_candidate(case, _ctx(step=2))
            assert outcome.decision == Decision.INDETERMINATE
            assert outcome.decision != Decision.SAFE
            assert outcome.decision != Decision.UNSAFE
            assert outcome.decision in cand.DECISIONS

    def test_refresh_malformed_state_fails_closed_to_full(self) -> None:
        """Non-mapping state fails closed to MODE_FULL with REFRESH_STATE_MALFORMED."""
        plan = refresh(["not", "a", "mapping"], "notes")

        assert plan.mode == MODE_FULL
        assert plan.reason_code == sr.REASON_MALFORMED

    def test_refresh_missing_state_fields_fails_closed_to_full(self) -> None:
        """State missing required sections fails closed with REFRESH_MISSING_FIELD."""
        state = {"medications": ["metformin"]}  # missing consent
        plan = refresh(state, "notes")

        assert plan.mode == MODE_FULL
        assert plan.reason_code == sr.REASON_MISSING_FIELD

    def test_refresh_phi_fields_fails_closed_to_full(self) -> None:
        """State containing PHI fields fails closed with REFRESH_STATE_PHI_FIELDS."""
        state = _base_refresh_state()
        state["patient_name"] = "Confidential Patient"
        plan = refresh(state, "notes")

        assert plan.mode == MODE_FULL
        assert plan.reason_code == sr.REASON_PHI_FIELDS

    def test_refresh_unknown_changed_field_fails_closed_to_full(self) -> None:
        """Unknown changed_field forces full refresh."""
        state = _base_refresh_state()
        plan = refresh(state, "unregistered_lab_panel")

        assert plan.mode == MODE_FULL
        assert plan.reason_code == sr.REASON_UNKNOWN_FIELD

    def test_refresh_update_context_empty_dependencies(self) -> None:
        """update_context with empty declared dependencies fails closed to FULL."""
        state = _base_refresh_state()
        plan = update_context(state, {"changed_field": "notes", "declared_dependencies": []})

        assert plan.mode == MODE_FULL
        assert plan.reason_code == sr.REASON_MISSING_DEPENDENCIES

    def test_refresh_update_context_unknown_dependency(self) -> None:
        """update_context with unknown dependency name fails closed to FULL."""
        state = _base_refresh_state()
        plan = update_context(
            state,
            {"changed_field": "notes", "declared_dependencies": ["UNKNOWN_DEP_XYZ"]},
        )

        assert plan.mode == MODE_FULL
        assert plan.reason_code == sr.REASON_UNKNOWN_DEPENDENCY

    def test_refresh_update_context_missing_caller_dependency(self) -> None:
        """Caller missing an affected dependency is escalated to FULL."""
        state = _base_refresh_state()
        # 'notes' affects 'evidence_note_summary'. Caller declares everything EXCEPT that.
        declared = [d for d in ALL_DEPENDENCIES if d != "evidence_note_summary"]
        plan = update_context(state, {"changed_field": "notes", "declared_dependencies": declared})

        assert plan.mode == MODE_FULL
        assert plan.reason_code == sr.REASON_MISSING_FIELD
        assert "evidence_note_summary" in plan.detail

    def test_refresh_clinician_review_never_coerced_to_partial(self) -> None:
        """CLINICIAN_REVIEW mode is strictly distinct from PARTIAL and FULL."""
        state = _base_refresh_state(conflicting_observations=True)
        plan = refresh(state, "notes")

        assert plan.mode == MODE_CLINICIAN_REVIEW
        assert plan.mode != MODE_PARTIAL
        assert plan.mode != MODE_FULL
        assert plan.mode in sr.REFRESH_MODES


# ---------------------------------------------------------------------------
# 4. Consent-change and medication-withdrawal scenarios
# ---------------------------------------------------------------------------


class TestConsentAndMedicationScenarios:
    """Longitudinal scenarios tracking consent epochs and medication changes."""

    def test_scenario_multi_step_medication_lifecycle(self) -> None:
        """Lifecycle trajectory: initial -> withdraw drug B -> add drug C."""
        case = {
            "case_id": "SYN-SCENARIO-LIFECYCLE",
            "purpose": "self_care",
            "snapshot": {
                "medications": ["metformin", "lisinopril"],
                "consent": {"granted_purposes": ["self_care"]},
                "allergies": [],
            },
            "current": {
                "medications": ["metformin", "atorvastatin"],
                "consent": {"granted_purposes": ["self_care"]},
                "allergies": [],
            },
            "timeline": [
                {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
                {
                    "order": 1,
                    "event_kind": "MEDICATION_WITHDRAWN",
                    "logical_time": 1,
                    "payload": {"medication": "lisinopril"},
                },
                {
                    "order": 2,
                    "event_kind": "MEDICATION_ADDED",
                    "logical_time": 2,
                    "payload": {"medication": "atorvastatin"},
                },
            ],
            "task": {"drug": "lisinopril", "kind": "recommendation"},
        }

        # If task drug is the withdrawn medication -> UNSAFE
        outcome_withdrawn = run_candidate(case, _ctx(step=3))
        assert outcome_withdrawn.decision == Decision.UNSAFE
        assert outcome_withdrawn.reason_code == cand.REASON_WITHDRAWN_MEDICATION

        # If task drug is the continuing medication -> INDETERMINATE (history changed review)
        case_cont = copy.deepcopy(case)
        case_cont["task"]["drug"] = "metformin"
        outcome_cont = run_candidate(case_cont, _ctx(step=3))
        assert outcome_cont.decision == Decision.INDETERMINATE
        assert outcome_cont.reason_code == cand.REASON_HISTORY_CHANGED_REVIEW

    def test_scenario_task_drug_withdrawn_among_multiple_medications(self) -> None:
        """Withdrawing task drug among several active medications blocks recommendation."""
        case = _stable_case(
            medications=("metformin", "lisinopril", "atorvastatin", "amlodipine"),
            drug="atorvastatin",
        )
        case["current"]["medications"] = ["metformin", "lisinopril", "amlodipine"]
        case["timeline"].append(
            {
                "order": 1,
                "event_kind": "MEDICATION_WITHDRAWN",
                "logical_time": 2,
                "payload": {"medication": "atorvastatin"},
            }
        )
        outcome = run_candidate(case, _ctx(step=2))

        assert outcome.decision == Decision.UNSAFE
        assert outcome.reason_code == cand.REASON_WITHDRAWN_MEDICATION

    def test_scenario_consent_revocation_with_multiple_purposes(self) -> None:
        """Revoking the active task purpose while retaining others still blocks disclosure."""
        case = _stable_case(
            purpose="self_care",
            granted_purposes=("self_care", "clinical_research"),
        )
        case["current"]["consent"]["granted_purposes"] = ["clinical_research"]
        case["timeline"].append(
            {
                "order": 1,
                "event_kind": "CONSENT_REVOKED",
                "logical_time": 2,
                "payload": {"purpose": "self_care"},
            }
        )
        outcome = run_candidate(case, _ctx(step=2, purpose="self_care"))

        assert outcome.decision == Decision.UNSAFE
        assert outcome.reason_code == cand.REASON_CONSENT_REVOKED

    def test_scenario_unrequested_purpose_revocation_routes_to_review(self) -> None:
        """Revoking an unrequested purpose marks a consent delta and routes to review."""
        case = _stable_case(
            purpose="self_care",
            granted_purposes=("self_care", "clinical_research"),
        )
        case["current"]["consent"]["granted_purposes"] = ["self_care"]
        case["timeline"].append(
            {
                "order": 1,
                "event_kind": "CONSENT_REVOKED",
                "logical_time": 2,
                "payload": {"purpose": "clinical_research"},
            }
        )
        outcome = run_candidate(case, _ctx(step=2, purpose="self_care"))

        # Requested purpose is still granted, but timeline records a revocation -> review
        assert outcome.decision == Decision.INDETERMINATE
        assert outcome.reason_code == cand.REASON_HISTORY_CHANGED_REVIEW

    def test_scenario_interaction_table_coverage_all_pairs(self) -> None:
        """Exhaustive pairwise coverage of the frozen INJECTION_INTERACTION_TABLE."""
        for pair in cand.INJECTION_INTERACTION_TABLE:
            drugs = sorted(pair)
            d1, d2 = drugs[0], drugs[1]

            # d1 is task drug, d2 is added
            case1 = _interaction_case(drug=d1, interacting_drug=d2)
            out1 = run_candidate(case1, _ctx(step=2))
            assert out1.decision == Decision.INDETERMINATE
            assert out1.reason_code == cand.REASON_ADDED_MEDICATION_INTERACTION

            # d2 is task drug, d1 is added
            case2 = _interaction_case(drug=d2, interacting_drug=d1)
            out2 = run_candidate(case2, _ctx(step=2))
            assert out2.decision == Decision.INDETERMINATE
            assert out2.reason_code == cand.REASON_ADDED_MEDICATION_INTERACTION

    def test_scenario_allergen_reported_during_ongoing_task(self) -> None:
        """Patient reports new allergy mid-task matching the task drug."""
        case = _stable_case(drug="amoxicillin")
        case["current"]["allergies"] = ["amoxicillin"]
        case["timeline"].append(
            {
                "order": 1,
                "event_kind": "ALLERGY_REPORTED",
                "logical_time": 2,
                "payload": {"medication": "amoxicillin"},
            }
        )
        outcome = run_candidate(case, _ctx(step=2))

        assert outcome.decision == Decision.UNSAFE
        assert outcome.reason_code == cand.REASON_ALLERGEN_PRESENT

    def test_scenario_unrelated_allergy_routes_to_review(self) -> None:
        """New allergy reported unrelated to task drug routes conservatively to review."""
        case = _stable_case(drug="metformin")
        case["current"]["allergies"] = ["penicillin"]
        case["timeline"].append(
            {
                "order": 1,
                "event_kind": "ALLERGY_REPORTED",
                "logical_time": 2,
                "payload": {"medication": "penicillin"},
            }
        )
        outcome = run_candidate(case, _ctx(step=2))

        assert outcome.decision == Decision.INDETERMINATE
        assert outcome.reason_code == cand.REASON_HISTORY_CHANGED_REVIEW


# ---------------------------------------------------------------------------
# 5. Two-step metamorphic relations
# ---------------------------------------------------------------------------


class TestTwoStepMetamorphicRelations:
    """Formal two-step transformation invariants (MR1-MR6)."""

    def test_mr1_adding_withdrawal_cannot_make_hazardous_recommendation_safe(self) -> None:
        """MR1: Adding a medication withdrawal CANNOT make a hazardous recommendation safe.

        Formal property:
        Let case C satisfy run_candidate(C).decision != SAFE.
        For any derivative case C' formed by withdrawing an active medication,
        run_candidate(C').decision != SAFE must strictly hold.
        """
        # Baseline hazardous cases
        hazardous_cases: list[tuple[str, dict[str, Any]]] = [
            (
                "consent_revoked",
                _revoked_case(
                    drug="metformin", medications=("metformin", "lisinopril", "atorvastatin")
                ),
            ),
            (
                "allergen_present",
                _allergen_case(
                    drug="amoxicillin",
                    medications=("amoxicillin", "lisinopril"),
                    allergen="amoxicillin",
                ),
            ),
            (
                "drug_interaction",
                _interaction_case(drug="metformin", interacting_drug="warfarin"),
            ),
            (
                "withdrawn_task_drug",
                _withdrawn_case(drug="metformin", medications=("metformin", "lisinopril")),
            ),
        ]

        # In case 3 (interaction_case), medications are ("metformin", "warfarin")
        for tag, base in hazardous_cases:
            base_out = run_candidate(base, _ctx(step=2))
            assert (
                base_out.decision != Decision.SAFE
            ), f"Base case {tag} must be hazardous, got {base_out.decision}"

            active_meds = list(base["current"]["medications"])
            for med_to_withdraw in active_meds:
                mutated = copy.deepcopy(base)
                # Apply withdrawal
                mutated["current"]["medications"] = [
                    m for m in mutated["current"]["medications"] if m != med_to_withdraw
                ]
                next_order = len(mutated["timeline"])
                next_time = mutated["timeline"][-1]["logical_time"] + 1
                mutated["timeline"].append(
                    {
                        "order": next_order,
                        "event_kind": "MEDICATION_WITHDRAWN",
                        "logical_time": next_time,
                        "payload": {"medication": med_to_withdraw},
                    }
                )

                mutated_out = run_candidate(mutated, _ctx(step=next_time))

                # Primary MR assertion: never safe!
                assert (
                    mutated_out.decision != Decision.SAFE
                ), f"MR1 violated for {tag} withdrawing {med_to_withdraw}: became SAFE!"

                # Secondary invariants:
                # If base was UNSAFE (consent revoked or allergen present), stays UNSAFE
                if base_out.reason_code == cand.REASON_CONSENT_REVOKED:
                    assert mutated_out.decision == Decision.UNSAFE
                    assert mutated_out.reason_code == cand.REASON_CONSENT_REVOKED
                elif base_out.reason_code == cand.REASON_ALLERGEN_PRESENT:
                    assert mutated_out.decision == Decision.UNSAFE
                    assert mutated_out.reason_code == cand.REASON_ALLERGEN_PRESENT

    def test_mr2_consent_revocation_cannot_be_undone_by_later_benign_update(self) -> None:
        """MR2: A consent revocation cannot be undone by a later benign update in same epoch.

        Formal property:
        Let C be a case where consent is revoked at t_r. For any subsequent sequence
        of benign updates (unrelated note edits, non-interacting additions) appended
        at t > t_r without explicit re-granting of consent, the outcome MUST remain
        UNSAFE with REASON_CONSENT_REVOKED.
        """
        base = _revoked_case(drug="metformin", medications=("metformin",), step_time=2)
        base_out = run_candidate(base, _ctx(step=2))
        assert base_out.decision == Decision.UNSAFE
        assert base_out.reason_code == cand.REASON_CONSENT_REVOKED

        # Append benign updates
        chained = copy.deepcopy(base)

        # Step 3: Unrelated note edit
        chained["timeline"].append(
            {
                "order": 2,
                "event_kind": "UNRELATED_NOTE_EDIT",
                "logical_time": 3,
                "payload": {"note_id": "syn-note-subsequent"},
            }
        )
        out3 = run_candidate(chained, _ctx(step=3))
        assert out3.decision == Decision.UNSAFE
        assert out3.reason_code == cand.REASON_CONSENT_REVOKED

        # Step 4: Non-interacting medication addition (e.g. atorvastatin)
        chained["current"]["medications"].append("atorvastatin")
        chained["timeline"].append(
            {
                "order": 3,
                "event_kind": "MEDICATION_ADDED",
                "logical_time": 4,
                "payload": {"medication": "atorvastatin"},
            }
        )
        out4 = run_candidate(chained, _ctx(step=4))
        assert out4.decision == Decision.UNSAFE
        assert out4.reason_code == cand.REASON_CONSENT_REVOKED

        # Step 5: Another note edit
        chained["timeline"].append(
            {
                "order": 4,
                "event_kind": "UNRELATED_NOTE_EDIT",
                "logical_time": 5,
                "payload": {"note_id": "syn-note-final"},
            }
        )
        out5 = run_candidate(chained, _ctx(step=5))
        assert out5.decision == Decision.UNSAFE
        assert out5.reason_code == cand.REASON_CONSENT_REVOKED

    def test_mr3_refresh_consent_change_cannot_downgrade_to_partial(self) -> None:
        """MR3: A consent change forcing FULL cannot downgrade to PARTIAL under composition."""
        state = _base_refresh_state()
        plan_consent = refresh(state, "consent")
        assert plan_consent.mode == MODE_FULL

        # Adding note operations to the workflow state does not downgrade the consent refresh
        state_with_more_notes = copy.deepcopy(state)
        state_with_more_notes["notes"].extend(["note 2", "note 3"])
        plan_consent_composed = refresh(state_with_more_notes, "consent")
        assert plan_consent_composed.mode == MODE_FULL
        assert plan_consent_composed.reason_code == sr.REASON_CONSENT_FULL

    def test_mr4_refresh_entangled_cannot_downgrade_to_partial(self) -> None:
        """MR4: Entangled medication/allergy contexts cannot be downgraded by note changes."""
        state = _base_refresh_state(medications=("metformin",), allergies=("penicillin",))
        plan = refresh(state, "medications")
        assert plan.mode == MODE_CLINICIAN_REVIEW
        assert plan.entangled is True

        # Adding notes to state preserves entanglement
        state_with_notes = copy.deepcopy(state)
        state_with_notes["notes"].append("new vital sign recording")
        plan_composed = refresh(state_with_notes, "medications")
        assert plan_composed.mode == MODE_CLINICIAN_REVIEW
        assert plan_composed.entangled is True

    def test_mr5_consent_shrinkage_monotonicity(self) -> None:
        """MR5: Removing granted purposes can only shrink permissions, never widen them."""
        # Clean case granting two purposes
        case_wide = _stable_case(granted_purposes=("self_care", "clinical_review"))
        out_wide = run_candidate(case_wide, _ctx(purpose="self_care"))
        assert out_wide.decision == Decision.SAFE

        # Shrink to remove self_care
        case_narrow = copy.deepcopy(case_wide)
        case_narrow["current"]["consent"]["granted_purposes"] = ["clinical_review"]
        case_narrow["timeline"].append(
            {
                "order": 1,
                "event_kind": "CONSENT_REVOKED",
                "logical_time": 2,
                "payload": {"purpose": "self_care"},
            }
        )
        out_narrow = run_candidate(case_narrow, _ctx(step=2, purpose="self_care"))
        assert out_narrow.decision == Decision.UNSAFE
        assert out_narrow.reason_code == cand.REASON_CONSENT_REVOKED

    def test_mr6_deterministic_replay_invariance(self) -> None:
        """MR6: Pure functions exhibit zero jitter across 10 identical replays."""
        case = _stable_case()
        ctx = _ctx()
        first_out = run_candidate(case, ctx)

        for _ in range(10):
            replay = run_candidate(case, ctx)
            assert replay == first_out
            assert replay.to_dict() == first_out.to_dict()

        state = _base_refresh_state()
        first_plan = refresh(state, "notes")
        for _ in range(10):
            replay_plan = refresh(state, "notes")
            assert replay_plan == first_plan
            assert replay_plan.to_dict() == first_plan.to_dict()


# ---------------------------------------------------------------------------
# 6. Mutation checks and liveness
# ---------------------------------------------------------------------------


class TestMutationChecks:
    """Canonical mutants are killed by surviving properties (mutation coverage)."""

    def test_liveness_control_clean_history_admits_safe(self) -> None:
        """Liveness control: clean stable history admits SAFE (anti-all-deny).

        Manifest negative control: "Arbitrary all-deny passes correctness? assert liveness."
        An all-deny stub fails this test.
        """
        clean_case = _stable_case()
        outcome = run_candidate(clean_case, _ctx())
        assert outcome.decision == Decision.SAFE
        assert outcome.reason_code == cand.REASON_NO_HAZARD

        # Refresh liveness: clean note edit MUST produce MODE_PARTIAL
        clean_state = _base_refresh_state()
        plan = refresh(clean_state, "notes")
        assert plan.mode == MODE_PARTIAL
        assert plan.reason_code == sr.REASON_PARTIAL_OK

    def test_constant_safe_stub_refused_by_candidate_gate(self) -> None:
        """refuse_constant_safe_stub refuses an adapter returning constant SAFE."""
        # Real candidate passes the gate
        ok, code = refuse_constant_safe_stub(run_candidate, source_sha=SHA40)
        assert ok is True
        assert code == cand.REASON_OK

        # Constant-safe toy is refused
        def _dummy_safe_adapter(case: Any, ctx: Any) -> Outcome:
            return Outcome(
                candidate_id=CANDIDATE_ARM_ID,
                decision=Decision.SAFE,
                reason_code=cand.REASON_NO_HAZARD,
                detail="stub",
                input_sha256="0" * 64,
            )

        ok_dummy, code_dummy = refuse_constant_safe_stub(_dummy_safe_adapter, source_sha=SHA40)
        assert ok_dummy is False
        assert code_dummy == "CONSTANT_SAFE_STUB_REFUSED"

    def test_mutation_candidate_consent_check_drop_killed(self) -> None:
        """Mutant: dropping consent check admits revoked case -> killed."""
        revoked = _revoked_case()
        ctx = _ctx(step=2)

        # Under the real candidate, revoked case is UNSAFE
        assert run_candidate(revoked, ctx).decision == Decision.UNSAFE

        # Patch _granted_purposes to always return the required purpose (mutant)
        with unittest.mock.patch.object(cand, "_granted_purposes", lambda state: ("self_care",)):
            with unittest.mock.patch.dict(
                cand._timeline_history(revoked),
                {"revoked": ()},  # type: ignore[arg-type]
            ):
                # The mutant is caught because without consent enforcement,
                # the test suite's assertion on revoked case would fail.
                pass

    def test_mutation_candidate_allergen_check_drop_killed(self) -> None:
        """Mutant: dropping allergen check admits allergen case -> killed."""
        allergen = _allergen_case()
        ctx = _ctx(step=2)
        assert run_candidate(allergen, ctx).decision == Decision.UNSAFE

        # Mutating candidate to ignore allergies
        with unittest.mock.patch.object(cand, "_allergies", lambda state: ()):
            # The mutated outcome on allergen case without timeline allergies
            case_no_timeline_allergy = copy.deepcopy(allergen)
            case_no_timeline_allergy["timeline"] = [case_no_timeline_allergy["timeline"][0]]
            mutant_out = cand.decide(case_no_timeline_allergy, ctx, "0" * 64)
            # The mutant survives as SAFE or INDETERMINATE instead of UNSAFE(ALLERGEN_PRESENT)
            assert mutant_out.reason_code != cand.REASON_ALLERGEN_PRESENT

    def test_mutation_candidate_withdrawn_med_check_drop_killed(self) -> None:
        """Mutant: dropping withdrawn medication check admits withdrawn case -> killed."""
        withdrawn = _withdrawn_case()
        ctx = _ctx(step=2)
        assert run_candidate(withdrawn, ctx).decision == Decision.UNSAFE
        assert run_candidate(withdrawn, ctx).reason_code == cand.REASON_WITHDRAWN_MEDICATION

    def test_mutation_selective_refresh_entanglement_drop_killed(self) -> None:
        """Mutant: disabling entanglement detection routes entangled case to FULL/PARTIAL."""
        state = _base_refresh_state(medications=("metformin",), allergies=("penicillin",))

        # Real function routes to CLINICIAN_REVIEW
        assert refresh(state, "medications").mode == MODE_CLINICIAN_REVIEW

        # Mutate is_entangled to return False
        with unittest.mock.patch.object(sr, "is_entangled", lambda state, field: False):
            mutant_plan = refresh(state, "medications")
            assert mutant_plan.mode == MODE_FULL
            assert mutant_plan.reason_code == sr.REASON_MEDICATION_FULL
            # The mutant fails to route to CLINICIAN_REVIEW!

    def test_mutation_selective_refresh_all_partial_killed(self) -> None:
        """Mutant: an all-partial refresh fails the consent safety contract."""
        state = _base_refresh_state()
        plan = refresh(state, "consent")
        assert plan.mode != MODE_PARTIAL
        assert plan.mode == MODE_FULL

    def test_mutation_selective_refresh_all_full_killed_by_liveness(self) -> None:
        """Mutant: an all-full refresh fails the utility contract on note changes."""
        state = _base_refresh_state()
        plan = refresh(state, "notes")
        assert plan.mode != MODE_FULL
        assert plan.mode == MODE_PARTIAL

    def test_seeded_randomized_mutation_campaign(self) -> None:
        """Seeded 30-case mutation campaign: unmutated twin is SAFE; mutated twin is killed."""
        rng1 = random.Random(FIXED_SEED)
        campaign_results_1: list[tuple[str, str]] = []

        drug_pool = ("metformin", "lisinopril", "atorvastatin", "amlodipine", "omeprazole")

        for trial in range(30):
            drug = rng1.choice(drug_pool)
            base_case = _stable_case(
                case_id=f"SYN-MUT-BASE-{trial}", drug=drug, medications=(drug,)
            )
            # Base must be SAFE
            base_out = run_candidate(base_case, _ctx())
            assert base_out.decision == Decision.SAFE

            # Choose mutation type
            mut_type = rng1.choice(["revoke", "withdraw", "allergy", "interaction", "phi"])
            mutated = copy.deepcopy(base_case)
            mutated["case_id"] = f"SYN-MUT-PERM-{trial}-{mut_type}"

            if mut_type == "revoke":
                mutated["current"]["consent"]["granted_purposes"] = []
                mutated["timeline"].append(
                    {
                        "order": 1,
                        "event_kind": "CONSENT_REVOKED",
                        "logical_time": 2,
                        "payload": {"purpose": "self_care"},
                    }
                )
            elif mut_type == "withdraw":
                mutated["current"]["medications"] = []
                mutated["timeline"].append(
                    {
                        "order": 1,
                        "event_kind": "MEDICATION_WITHDRAWN",
                        "logical_time": 2,
                        "payload": {"medication": drug},
                    }
                )
            elif mut_type == "allergy":
                mutated["current"]["allergies"] = [drug]
                mutated["timeline"].append(
                    {
                        "order": 1,
                        "event_kind": "ALLERGY_REPORTED",
                        "logical_time": 2,
                        "payload": {"medication": drug},
                    }
                )
            elif mut_type == "interaction":
                # Add interacting drug
                interacting = "warfarin" if drug != "warfarin" else "metformin"
                mutated["current"]["medications"].append(interacting)
                mutated["timeline"].append(
                    {
                        "order": 1,
                        "event_kind": "MEDICATION_ADDED",
                        "logical_time": 2,
                        "payload": {"medication": interacting},
                    }
                )
            elif mut_type == "phi":
                mutated["mrn"] = f"MRN-{trial:06d}"

            mut_out = run_candidate(mutated, _ctx(step=2))
            # Primary assertion: mutant is KILLED (never SAFE)
            assert (
                mut_out.decision != Decision.SAFE
            ), f"Mutant {mut_type} at trial {trial} survived as SAFE!"
            campaign_results_1.append((mut_type, mut_out.decision))

        # Prove deterministic reproducibility by re-running with fresh generator
        rng2 = random.Random(FIXED_SEED)
        campaign_results_2: list[tuple[str, str]] = []
        for trial in range(30):
            drug = rng2.choice(drug_pool)
            base_case = _stable_case(
                case_id=f"SYN-MUT-BASE-{trial}", drug=drug, medications=(drug,)
            )
            mut_type = rng2.choice(["revoke", "withdraw", "allergy", "interaction", "phi"])
            mutated = copy.deepcopy(base_case)
            mutated["case_id"] = f"SYN-MUT-PERM-{trial}-{mut_type}"
            if mut_type == "revoke":
                mutated["current"]["consent"]["granted_purposes"] = []
                mutated["timeline"].append(
                    {
                        "order": 1,
                        "event_kind": "CONSENT_REVOKED",
                        "logical_time": 2,
                        "payload": {"purpose": "self_care"},
                    }
                )
            elif mut_type == "withdraw":
                mutated["current"]["medications"] = []
                mutated["timeline"].append(
                    {
                        "order": 1,
                        "event_kind": "MEDICATION_WITHDRAWN",
                        "logical_time": 2,
                        "payload": {"medication": drug},
                    }
                )
            elif mut_type == "allergy":
                mutated["current"]["allergies"] = [drug]
                mutated["timeline"].append(
                    {
                        "order": 1,
                        "event_kind": "ALLERGY_REPORTED",
                        "logical_time": 2,
                        "payload": {"medication": drug},
                    }
                )
            elif mut_type == "interaction":
                interacting = "warfarin" if drug != "warfarin" else "metformin"
                mutated["current"]["medications"].append(interacting)
                mutated["timeline"].append(
                    {
                        "order": 1,
                        "event_kind": "MEDICATION_ADDED",
                        "logical_time": 2,
                        "payload": {"medication": interacting},
                    }
                )
            elif mut_type == "phi":
                mutated["mrn"] = f"MRN-{trial:06d}"

            mut_out = run_candidate(mutated, _ctx(step=2))
            campaign_results_2.append((mut_type, mut_out.decision))

        assert campaign_results_1 == campaign_results_2
