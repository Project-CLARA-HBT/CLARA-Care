"""CLARA-Care 2027 AIME task AIME-ablation — causal mechanism ablation variants.

Purpose
-------
P04 ablation registry for "Counterfactual Clinical Workflow Safety under Changing
Consent and Medication Histories" (``research/venue2027/VENUES/aime/
RESEARCH_BLUEPRINT.md``; task contract ``research/venue2027/VENUES/aime/
TASKS/AIME-ablation.md``). The P04 candidate
(:mod:`evaluation.venue2027.aime.candidate`) performs counterfactual history
contrast (task-start snapshot vs current state vs timeline events) to detect
changed consent epochs, medication withdrawals, new allergies, and added
interactions before any completion is counted. This module runs the candidate
against ITSELF with EXACTLY ONE mechanism removed per variant, over the SAME
frozen synthetic case families, so each mechanism's causal contribution to
safety is measurable (development-scale mechanism causality on frozen synthetic
cases — never confirmatory results; no clinical efficacy claims).

Preregistered variants (``ABLATION_REGISTRY``; each is a real callable reusing
the candidate with exactly ONE mechanism removed, declaring it via
:class:`VariantSpec`):

- ``without_history_contrast`` — candidate WITHOUT counterfactual history
  contrast: evaluates the recommendation against the task-start snapshot alone
  without contrasting against subsequent history changes or timeline events
  (mid-task medication withdrawals and deltas are not contrasted against the
  baseline snapshot). Reuses candidate components; misses a medication
  withdrawal hazard that the full candidate catches with
  ``WITHDRAWN_MEDICATION_IN_OUTPUT``.
- ``without_consent_recheck`` — candidate WITHOUT consent epoch recheck:
  Axis A consent recheck is suppressed (current consent is treated as
  unconditionally granted for the requested purpose and timeline consent
  revocations are neutralized), while medication history contrast and allergy
  checks stay enforced. The mid-task consent revocation the candidate rejects
  with ``CONSENT_REVOKED_MID_TASK`` is admitted.
- ``without_medication_allergy_gate`` — candidate WITHOUT the medication/allergy
  entanglement gate: Axis B allergy checks and added medication hazard checks
  are suppressed, while Axis A consent epoch validation remains strictly
  enforced. The newly reported allergy the candidate rejects with
  ``ALLERGEN_PRESENT_IN_TASK`` is admitted.
- ``common_safety_gate`` — candidate REPLACED by the static common safety gate
  shared across simple baselines: context-free, temporal-blind check of
  snapshot initial consent and snapshot initial allergies only. Misses all
  mid-task timeline hazards (withdrawal, revocation, and allergy).
- ``full_refresh`` — candidate REPLACED by the strict full per-step refresh
  comparator (blueprint arm B1). Re-reads the record at the step's logical time
  and applies current policy epoch; requires full context regeneration
  (``INDETERMINATE``) upon any medication withdrawal or addition, paying full
  regeneration cost rather than selectively isolating the hazard.

The reference row (the unmodified full candidate) is deliberately NOT a
registered variant: a variant that removes nothing is not an ablation.
:func:`refuse_unregistered_variant` refuses unknown ids with
``UNKNOWN_ABLATION_VARIANT`` and nothing-removing identities (the full candidate
and candidate id) with ``VARIANT_REMOVES_NOTHING`` — fail closed, never
silently run as a degraded or full arm. The mechanistic inference matrix
(:func:`mechanistic_inference_matrix`, :func:`verify_mechanistic_inference_matrix`)
pins every variant x family verdict against its preregistered prediction.

Allowed input
-------------
:func:`run_ablation(name, case)` (task-manifest signature
``run_ablation(name, case) -> Outcome``): ``name`` is a registered variant id
from :data:`ABLATION_REGISTRY`; ``case`` is one JSON-serializable mapping
``{"case_id", "purpose", "snapshot", "current", "timeline", "task", ...}``
shaped like the candidate's :func:`candidate.run_candidate` input.
All identities and timestamps are synthetic (no real PHI; no live provider,
no LLM call, no clock, no randomness, no network, no database).

Failure semantics
-----------------
Fail closed with stable uppercase reason codes; no unhandled exception escapes:
- unknown / nothing-removing variant -> ``Outcome(EXECUTION_ERROR)`` carrying
  ``UNKNOWN_ABLATION_VARIANT`` / ``VARIANT_REMOVES_NOTHING`` (the raising
  guard :func:`refuse_unregistered_variant` exposes the same codes).
- malformed case (non-mapping, missing/ill-typed case id, missing required
  fields, non-monotone timeline) -> ``EXECUTION_ERROR`` / ``INDETERMINATE``
  outcomes, never ``ADMIT`` or ``REJECT``.
- Determined candidate verdicts map SAFE -> ``ADMIT`` (counted_as_success=True),
  UNSAFE -> ``REJECT`` (counted_as_success=True), and INDETERMINATE ->
  ``INDETERMINATE`` (counted_as_success=False).

Version
-------
``ABLATIONS_VERSION = "clara.aime.ablations-v1"`` (additive-only within 1.x).
"""

from __future__ import annotations

import copy
import dataclasses
import json
from collections.abc import Callable, Mapping
from typing import Any, Final

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.aime import candidate as cand

ABLATIONS_VERSION: Final[str] = "clara.aime.ablations-v1"
ABLATION_TASK_ID: Final[str] = "AIME-ablation"

#: Preregistered ablation variant ids (one mechanism removed each).
VARIANT_WITHOUT_HISTORY_CONTRAST: Final[str] = "without_history_contrast"
VARIANT_WITHOUT_CONSENT_RECHECK: Final[str] = "without_consent_recheck"
VARIANT_WITHOUT_MEDICATION_ALLERGY_GATE: Final[str] = "without_medication_allergy_gate"
VARIANT_COMMON_SAFETY_GATE: Final[str] = "common_safety_gate"
VARIANT_FULL_REFRESH: Final[str] = "full_refresh"

#: Reference row: the unmodified candidate. Deliberately NOT registered as an
#: ablation — a variant that removes nothing is not an ablation.
REFERENCE_VARIANT_ID: Final[str] = "full_candidate"

#: Identities known to remove nothing (refused, not guessed).
NON_ABLATION_IDENTITIES: Final[frozenset[str]] = frozenset(
    {REFERENCE_VARIANT_ID, cand.CANDIDATE_ARM_ID, "candidate"}
)

#: Ablated mechanism axes (exactly one per variant, all distinct).
ABLATED_HISTORY_CONTRAST: Final[str] = "counterfactual_history_contrast"
ABLATED_CONSENT_RECHECK: Final[str] = "consent_epoch_recheck"
ABLATED_MEDICATION_ALLERGY_GATE: Final[str] = "medication_allergy_entanglement_gate"
ABLATED_COMMON_SAFETY_GATE: Final[str] = "counterfactual_reasoning_and_temporal_history"
ABLATED_FULL_REFRESH: Final[str] = "selective_history_regeneration"

#: Stable reason codes (fail closed).
RC_UNKNOWN_ABLATION_VARIANT: Final[str] = "UNKNOWN_ABLATION_VARIANT"
RC_VARIANT_REMOVES_NOTHING: Final[str] = "VARIANT_REMOVES_NOTHING"
RC_CASE_NOT_AN_OBJECT: Final[str] = "CASE_NOT_AN_OBJECT"
RC_CASE_ID_MISSING: Final[str] = "CASE_ID_MISSING"
RC_CASE_ID_NOT_STRING: Final[str] = "CASE_ID_NOT_STRING"
RC_MALFORMED_CASE: Final[str] = "VIGNETTE_MALFORMED"

VERDICT_ADMIT: Final[str] = "ADMIT"
VERDICT_REJECT: Final[str] = "REJECT"
VERDICT_INDETERMINATE: Final[str] = "INDETERMINATE"

#: Frozen synthetic fault/control family ids.
FAMILY_STABLE: Final[str] = "stable_history"
FAMILY_WITHDRAWN: Final[str] = "medication_withdrawal"
FAMILY_REVOKED: Final[str] = "consent_revoked"
FAMILY_ALLERGY: Final[str] = "allergy_reported"

FAULT_FAMILY_IDS: Final[tuple[str, ...]] = (
    FAMILY_STABLE,
    FAMILY_WITHDRAWN,
    FAMILY_REVOKED,
    FAMILY_ALLERGY,
)

#: Default synthetic context SHA40.
_DEFAULT_SOURCE_SHA: Final[str] = "28ff55110f980f42002524cef126290e91258cd6"


class AblationError(ValueError):
    """Fail-closed ablation registry error with a stable reason code."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class VariantSpec:
    """One preregistered ablation variant.

    ``ablated_mechanism`` is the DECLARED single mechanism removed; a spec
    that declares no ablated mechanism (empty string) is refused at
    construction — a variant removing nothing is not an ablation.
    """

    variant_id: str
    title: str
    ablated_mechanism: str
    description: str
    expected_effect: str
    reuses: tuple[str, ...]
    applied_by: str

    def __post_init__(self) -> None:
        if not isinstance(self.ablated_mechanism, str) or not self.ablated_mechanism.strip():
            raise AblationError(
                RC_VARIANT_REMOVES_NOTHING,
                f"variant {self.variant_id!r} declares no ablated mechanism; "
                "a variant removing nothing is not an ablation",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "title": self.title,
            "ablated_mechanism": self.ablated_mechanism,
            "description": self.description,
            "expected_effect": self.expected_effect,
            "reuses": list(self.reuses),
            "applied_by": self.applied_by,
        }


ABLATION_REGISTRY: Final[Mapping[str, VariantSpec]] = {
    spec.variant_id: spec
    for spec in (
        VariantSpec(
            variant_id=VARIANT_WITHOUT_HISTORY_CONTRAST,
            title="Candidate without counterfactual history contrast",
            ablated_mechanism=ABLATED_HISTORY_CONTRAST,
            description=(
                "Evaluates the recommendation against the task-start snapshot "
                "without contrasting against subsequent history changes or timeline events. "
                "Mid-task medication withdrawals and deltas are not compared against "
                "the baseline snapshot, so stale snapshot recommendations are issued blindly."
            ),
            expected_effect="misses_mid_task_withdrawal_and_history_changes",
            reuses=(
                "candidate.decide",
                "candidate.parse_case",
                "candidate.CandidateContext",
                "candidate.Outcome",
            ),
            applied_by="harness_input_mutation",
        ),
        VariantSpec(
            variant_id=VARIANT_WITHOUT_CONSENT_RECHECK,
            title="Candidate without consent epoch recheck",
            ablated_mechanism=ABLATED_CONSENT_RECHECK,
            description=(
                "Disables the Axis A consent epoch recheck. Current consent is treated "
                "as unconditionally granted for the requested purpose and timeline "
                "consent revocations are suppressed, while history contrast, medication "
                "checks, and allergy checks remain enforced."
            ),
            expected_effect="admits_revoked_consent_disclosure",
            reuses=(
                "candidate.decide",
                "candidate.parse_case",
                "candidate.CandidateContext",
                "candidate.Outcome",
            ),
            applied_by="harness_input_mutation",
        ),
        VariantSpec(
            variant_id=VARIANT_WITHOUT_MEDICATION_ALLERGY_GATE,
            title="Candidate without medication/allergy entanglement gate",
            ablated_mechanism=ABLATED_MEDICATION_ALLERGY_GATE,
            description=(
                "Disables the Axis B medication and allergy entanglement gate. "
                "Allergy reports and medication additions/withdrawals are ignored and "
                "bypass safety checks, while Axis A consent epoch validation remains strictly enforced."
            ),
            expected_effect="admits_allergen_and_medication_hazards",
            reuses=(
                "candidate.decide",
                "candidate.parse_case",
                "candidate.CandidateContext",
                "candidate.Outcome",
            ),
            applied_by="harness_input_mutation",
        ),
        VariantSpec(
            variant_id=VARIANT_COMMON_SAFETY_GATE,
            title="Candidate replaced by common safety gate",
            ablated_mechanism=ABLATED_COMMON_SAFETY_GATE,
            description=(
                "Replaces the candidate's temporal and counterfactual pipeline with the "
                "static, context-free safety gate shared across simple baselines. Checks "
                "only snapshot initial consent and snapshot initial allergies; blind to "
                "all mid-task timeline events and state transitions."
            ),
            expected_effect="misses_all_temporal_and_counterfactual_hazards",
            reuses=(
                "candidate._granted_purposes",
                "candidate._allergies",
                "candidate.Outcome",
            ),
            applied_by="harness_modeled_gate",
        ),
        VariantSpec(
            variant_id=VARIANT_FULL_REFRESH,
            title="Strict full per-step refresh comparator",
            ablated_mechanism=ABLATED_FULL_REFRESH,
            description=(
                "Replaces selective history regeneration with strict full per-step "
                "context refresh (blueprint arm B1). Re-reads the record at the step's "
                "logical time and applies current policy epoch. When any medication is "
                "withdrawn or added, it forces full regeneration (INDETERMINATE), paying "
                "full regeneration cost rather than selectively isolating the hazard."
            ),
            expected_effect="forces_full_regeneration_on_any_history_change",
            reuses=(
                "candidate._granted_purposes",
                "candidate._allergies",
                "candidate.Outcome",
            ),
            applied_by="baseline_comparator_adapter",
        ),
    )
}

#: Known aliases mapping to canonical variant IDs.
ALIAS_MAP: Final[dict[str, str]] = {
    "no_history_contrast": VARIANT_WITHOUT_HISTORY_CONTRAST,
    "no_consent_recheck": VARIANT_WITHOUT_CONSENT_RECHECK,
    "no_medication_allergy_gate": VARIANT_WITHOUT_MEDICATION_ALLERGY_GATE,
    "no_medication_allergy_entanglement": VARIANT_WITHOUT_MEDICATION_ALLERGY_GATE,
    "full_per_step_refresh": VARIANT_FULL_REFRESH,
}


def refuse_unregistered_variant(name: str) -> VariantSpec:
    """Guard: return the registered spec for ``name`` or refuse fail-closed.

    Refuses (raises :class:`AblationError`):
    - any id not in :data:`ABLATION_REGISTRY` -> ``UNKNOWN_ABLATION_VARIANT``;
    - known nothing-removing identities (full candidate and candidate id) ->
      ``VARIANT_REMOVES_NOTHING``: a variant that removes no mechanism is not
      an ablation.
    """
    canonical = ALIAS_MAP.get(name, name)
    spec = ABLATION_REGISTRY.get(canonical)
    if spec is not None:
        return spec
    if name in NON_ABLATION_IDENTITIES:
        raise AblationError(
            RC_VARIANT_REMOVES_NOTHING,
            f"{name!r} is the unmodified candidate and removes no mechanism; "
            "run candidate.run_candidate directly for the reference row",
        )
    raise AblationError(
        RC_UNKNOWN_ABLATION_VARIANT,
        f"variant {name!r} not in registry {sorted(ABLATION_REGISTRY)}",
    )


def variant_ids() -> tuple[str, ...]:
    """Registered ablation variant ids in canonical (registry) order."""
    return tuple(ABLATION_REGISTRY)


# ---------------------------------------------------------------------------
# Frozen attack/control family fixtures.
# ---------------------------------------------------------------------------


def _fixture_stable() -> dict[str, Any]:
    """Routine stable context: unchanged evidence, approved consent (CASE-01/06)."""
    return {
        "case_id": "AIME-ABLATION-STABLE",
        "purpose": "self_care",
        "snapshot": {
            "medications": ["metformin"],
            "consent": {"granted_purposes": ["self_care"]},
            "allergies": [],
        },
        "current": {
            "medications": ["metformin"],
            "consent": {"granted_purposes": ["self_care"]},
            "allergies": [],
        },
        "timeline": [
            {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
        ],
        "task": {"drug": "metformin", "kind": "recommendation"},
    }


def _fixture_withdrawn() -> dict[str, Any]:
    """Medication withdrawal: task drug withdrawn mid-task (CASE-02)."""
    return {
        "case_id": "AIME-ABLATION-WITHDRAWN",
        "purpose": "self_care",
        "snapshot": {
            "medications": ["metformin"],
            "consent": {"granted_purposes": ["self_care"]},
            "allergies": [],
        },
        "current": {
            "medications": [],
            "consent": {"granted_purposes": ["self_care"]},
            "allergies": [],
        },
        "timeline": [
            {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
            {
                "order": 1,
                "event_kind": "MEDICATION_WITHDRAWN",
                "logical_time": 2,
                "payload": {"medication": "metformin"},
            },
        ],
        "task": {"drug": "metformin", "kind": "recommendation"},
    }


def _fixture_revoked() -> dict[str, Any]:
    """Consent revocation: patient revokes share permission mid-task (CASE-03)."""
    return {
        "case_id": "AIME-ABLATION-REVOKED",
        "purpose": "self_care",
        "snapshot": {
            "medications": ["metformin"],
            "consent": {"granted_purposes": ["self_care"]},
            "allergies": [],
        },
        "current": {
            "medications": ["metformin"],
            "consent": {"granted_purposes": []},
            "allergies": [],
        },
        "timeline": [
            {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
            {
                "order": 1,
                "event_kind": "CONSENT_REVOKED",
                "logical_time": 2,
                "payload": {"purpose": "self_care"},
            },
        ],
        "task": {"drug": "metformin", "kind": "recommendation"},
    }


def _fixture_allergy() -> dict[str, Any]:
    """Allergy reported: task drug reported as allergen mid-task (CASE-02 shape)."""
    return {
        "case_id": "AIME-ABLATION-ALLERGY",
        "purpose": "self_care",
        "snapshot": {
            "medications": ["metformin"],
            "consent": {"granted_purposes": ["self_care"]},
            "allergies": [],
        },
        "current": {
            "medications": ["metformin"],
            "consent": {"granted_purposes": ["self_care"]},
            "allergies": ["metformin"],
        },
        "timeline": [
            {"order": 0, "event_kind": "INITIAL_STATE", "logical_time": 0, "payload": None},
            {
                "order": 1,
                "event_kind": "ALLERGY_REPORTED",
                "logical_time": 2,
                "payload": {"medication": "metformin"},
            },
        ],
        "task": {"drug": "metformin", "kind": "recommendation"},
    }


def case_fixtures() -> dict[str, Callable[[], dict[str, Any]]]:
    """Frozen synthetic case fixtures for all registered families."""
    return {
        FAMILY_STABLE: _fixture_stable,
        FAMILY_WITHDRAWN: _fixture_withdrawn,
        FAMILY_REVOKED: _fixture_revoked,
        FAMILY_ALLERGY: _fixture_allergy,
    }


# ---------------------------------------------------------------------------
# Individual variant runners (pure callables reusing candidate components).
# ---------------------------------------------------------------------------


def _run_without_history_contrast(
    case: dict[str, Any], ctx: cand.CandidateContext, digest: str
) -> cand.Outcome:
    """Candidate without counterfactual history contrast.

    Evaluates the recommendation against the task-start snapshot alone;
    mid-task medication deltas and timeline withdrawal/addition events are
    neutralized before candidate execution. Axis A consent recheck and allergy
    checks remain enforced.
    """
    mutated = copy.deepcopy(case)
    mutated["current"]["medications"] = list(mutated["snapshot"]["medications"])
    mutated["timeline"] = [
        e
        for e in mutated["timeline"]
        if e.get("event_kind") not in ("MEDICATION_WITHDRAWN", "MEDICATION_ADDED")
    ]
    for idx, event in enumerate(mutated["timeline"]):
        event["order"] = idx
    return cand.decide(mutated, ctx, digest)


def _run_without_consent_recheck(
    case: dict[str, Any], ctx: cand.CandidateContext, digest: str
) -> cand.Outcome:
    """Candidate without consent epoch recheck.

    Axis A consent recheck is neutralized: current consent is granted for the
    requested purpose, and timeline consent revocations are suppressed. History
    contrast, medication checks, and allergy checks stay enforced.
    """
    mutated = copy.deepcopy(case)
    current_consent = dict(mutated["current"].get("consent", {}))
    granted = list(current_consent.get("granted_purposes", []))
    if ctx.purpose not in granted:
        granted.append(ctx.purpose)
    current_consent["granted_purposes"] = granted
    mutated["current"]["consent"] = current_consent
    mutated["timeline"] = [
        e for e in mutated["timeline"] if e.get("event_kind") != "CONSENT_REVOKED"
    ]
    for idx, event in enumerate(mutated["timeline"]):
        event["order"] = idx
    return cand.decide(mutated, ctx, digest)


def _run_without_medication_allergy_gate(
    case: dict[str, Any], ctx: cand.CandidateContext, digest: str
) -> cand.Outcome:
    """Candidate without medication/allergy entanglement gate.

    Axis B allergy check is neutralized: current allergies are cleared and
    timeline allergy report events are suppressed. Axis A consent recheck and
    withdrawn medication checks remain enforced.
    """
    mutated = copy.deepcopy(case)
    mutated["current"]["allergies"] = []
    mutated["snapshot"]["allergies"] = []
    mutated["timeline"] = [
        e for e in mutated["timeline"] if e.get("event_kind") != "ALLERGY_REPORTED"
    ]
    for idx, event in enumerate(mutated["timeline"]):
        event["order"] = idx
    return cand.decide(mutated, ctx, digest)


def _run_common_safety_gate(
    case: dict[str, Any], ctx: cand.CandidateContext, digest: str
) -> cand.Outcome:
    """Candidate replaced by static common safety gate.

    Context-free, temporal-blind check: inspects only whether initial snapshot
    consent includes the purpose, and whether the task drug is listed in initial
    snapshot allergies. Ignores all mid-task timeline events and changes.
    """
    snapshot = case["snapshot"]
    task_drug = case["task"]["drug"]
    purpose = ctx.purpose or case["purpose"]

    if purpose not in cand._granted_purposes(snapshot):
        return cand.Outcome(
            candidate_id=VARIANT_COMMON_SAFETY_GATE,
            decision=cand.DECISION_UNSAFE,
            reason_code=cand.REASON_CONSENT_REVOKED,
            detail="common safety gate: purpose not granted in initial snapshot",
            input_sha256=digest,
            evidence=("snapshot.consent",),
        )
    if task_drug in cand._allergies(snapshot):
        return cand.Outcome(
            candidate_id=VARIANT_COMMON_SAFETY_GATE,
            decision=cand.DECISION_UNSAFE,
            reason_code=cand.REASON_ALLERGEN_PRESENT,
            detail=f"common safety gate: task drug {task_drug!r} in initial snapshot allergies",
            input_sha256=digest,
            evidence=("snapshot.allergies",),
        )
    return cand.Outcome(
        candidate_id=VARIANT_COMMON_SAFETY_GATE,
        decision=cand.DECISION_SAFE,
        reason_code=cand.REASON_NO_HAZARD,
        detail="common safety gate: initial snapshot has granted consent and no initial allergen",
        input_sha256=digest,
        evidence=("snapshot",),
    )


def _run_full_refresh(
    case: dict[str, Any], ctx: cand.CandidateContext, digest: str
) -> cand.Outcome:
    """Candidate replaced by strict full per-step refresh comparator (arm B1).

    Re-reads the current record at the step's logical time and applies the
    current policy epoch. Requires full regeneration (INDETERMINATE) on any
    detected medication change.
    """
    current = case["current"]
    purpose = ctx.purpose or case["purpose"]
    task_drug = case["task"]["drug"]

    if purpose not in cand._granted_purposes(current):
        return cand.Outcome(
            candidate_id=VARIANT_FULL_REFRESH,
            decision=cand.DECISION_UNSAFE,
            reason_code=cand.REASON_CONSENT_REVOKED,
            detail="full refresh: current-epoch policy filter refuses: purpose not granted",
            input_sha256=digest,
            evidence=("current.consent",),
        )
    if task_drug in cand._allergies(current):
        return cand.Outcome(
            candidate_id=VARIANT_FULL_REFRESH,
            decision=cand.DECISION_UNSAFE,
            reason_code=cand.REASON_ALLERGEN_PRESENT,
            detail=f"full refresh: task drug {task_drug!r} is allergen in refreshed record",
            input_sha256=digest,
            evidence=("current.allergies",),
        )
    before = set(case["snapshot"]["medications"])
    after = set(current["medications"])
    withdrawn = tuple(sorted(before - after))
    added = tuple(sorted(after - before))
    if withdrawn:
        return cand.Outcome(
            candidate_id=VARIANT_FULL_REFRESH,
            decision=cand.DECISION_INDETERMINATE,
            reason_code=cand.REASON_WITHDRAWN_MEDICATION,
            detail="full refresh: context excludes withdrawn medication; regeneration required",
            input_sha256=digest,
            evidence=("current.medications",),
        )
    if added:
        return cand.Outcome(
            candidate_id=VARIANT_FULL_REFRESH,
            decision=cand.DECISION_INDETERMINATE,
            reason_code=cand.REASON_ADDED_MEDICATION_INTERACTION,
            detail="full refresh: context shows added medication; interaction re-review required",
            input_sha256=digest,
            evidence=("current.medications",),
        )
    return cand.Outcome(
        candidate_id=VARIANT_FULL_REFRESH,
        decision=cand.DECISION_SAFE,
        reason_code=cand.REASON_NO_HAZARD,
        detail="full refresh: refreshed context is consistent with current policy epoch",
        input_sha256=digest,
        evidence=("current.medications", "current.consent"),
    )


_VARIANT_RUNNERS: Final[
    dict[str, Callable[[dict[str, Any], cand.CandidateContext, str], cand.Outcome]]
] = {
    VARIANT_WITHOUT_HISTORY_CONTRAST: _run_without_history_contrast,
    VARIANT_WITHOUT_CONSENT_RECHECK: _run_without_consent_recheck,
    VARIANT_WITHOUT_MEDICATION_ALLERGY_GATE: _run_without_medication_allergy_gate,
    VARIANT_COMMON_SAFETY_GATE: _run_common_safety_gate,
    VARIANT_FULL_REFRESH: _run_full_refresh,
}


# ---------------------------------------------------------------------------
# Target contract: run_ablation(name, case) -> Outcome
# ---------------------------------------------------------------------------


def _outcome(
    observed_outcome: str,
    counted_as_success: bool,
    detail: str,
) -> Outcome:
    return Outcome(
        observed_outcome=observed_outcome,
        counted_as_success=counted_as_success,
        detail=detail,
    )


def _refusal_outcome(exc: AblationError) -> Outcome:
    return _outcome(
        "EXECUTION_ERROR",
        False,
        f"{ABLATIONS_VERSION}|{exc.reason_code}: {exc.detail}",
    )


def run_ablation(name: str, case: Any) -> Outcome:
    """Task-manifest signature: run ONE ablation variant on ONE synthetic case.

    - Determined outcomes: SAFE -> ``ADMIT`` (counted_as_success=True),
      UNSAFE -> ``REJECT`` (counted_as_success=True), and INDETERMINATE ->
      ``INDETERMINATE`` (counted_as_success=False).
    - Fail closed: unknown variant or nothing-removing identity ->
      ``EXECUTION_ERROR`` with ``UNKNOWN_ABLATION_VARIANT`` /
      ``VARIANT_REMOVES_NOTHING``; malformed case -> ``EXECUTION_ERROR`` /
      ``INDETERMINATE`` (never ``ADMIT``/``REJECT``, never counted as success).
    """
    try:
        spec = refuse_unregistered_variant(name)
    except AblationError as exc:
        return _refusal_outcome(exc)

    if not isinstance(case, Mapping):
        return _outcome(
            "EXECUTION_ERROR",
            False,
            f"{RC_CASE_NOT_AN_OBJECT}: case must be a mapping, got {type(case).__name__}",
        )

    case_id = case.get("case_id")
    if case_id is None:
        return _outcome("INDETERMINATE", False, f"{ABLATIONS_VERSION}|{RC_CASE_ID_MISSING}")
    if not isinstance(case_id, str) or not case_id:
        return _outcome("INDETERMINATE", False, f"{ABLATIONS_VERSION}|{RC_CASE_ID_NOT_STRING}")

    normalized, reason, digest = cand.parse_case(case)
    if normalized is None:
        code, _, extra = reason.partition(":")
        return _outcome("INDETERMINATE", False, f"vignette refused: {extra or code}")

    ctx = cand.CandidateContext(
        arm_id=f"ablation::{spec.variant_id}",
        source_sha=_DEFAULT_SOURCE_SHA,
        step_logical_time=int(case.get("step_logical_time", 1)),
        purpose=str(case.get("purpose", "self_care")),
    )

    canonical_name = spec.variant_id
    runner = _VARIANT_RUNNERS[canonical_name]
    candidate_outcome = runner(normalized, ctx, digest)

    if candidate_outcome.decision == cand.DECISION_SAFE:
        observed_verdict = VERDICT_ADMIT
        counted = True
    elif candidate_outcome.decision == cand.DECISION_UNSAFE:
        observed_verdict = VERDICT_REJECT
        counted = True
    else:
        observed_verdict = VERDICT_INDETERMINATE
        counted = False

    detail = json.dumps(
        {
            "ablations_version": ABLATIONS_VERSION,
            "variant_id": canonical_name,
            "ablated_mechanism": spec.ablated_mechanism,
            "case_id": case_id,
            "decision": candidate_outcome.decision,
            "reason_code": candidate_outcome.reason_code,
            "detail": candidate_outcome.detail,
            "evidence": list(candidate_outcome.evidence),
            "input_sha256": digest,
        },
        sort_keys=True,
    )
    return _outcome(observed_verdict, counted, detail)


# ---------------------------------------------------------------------------
# Mechanistic inference matrix: preregistered predictions + verification.
# ---------------------------------------------------------------------------


def _run_reference(case: Mapping[str, Any]) -> Outcome:
    """The unmodified full candidate (reference row; not an ablation)."""
    if not isinstance(case, Mapping):
        return _outcome("EXECUTION_ERROR", False, f"{RC_CASE_NOT_AN_OBJECT}")
    normalized, reason, digest = cand.parse_case(case)
    if normalized is None:
        return _outcome("INDETERMINATE", False, f"vignette refused: {reason}", digest)
    ctx = cand.CandidateContext(
        arm_id=cand.CANDIDATE_ARM_ID,
        source_sha=_DEFAULT_SOURCE_SHA,
        step_logical_time=int(case.get("step_logical_time", 1)),
        purpose=str(case.get("purpose", "self_care")),
    )
    outcome = cand.decide(normalized, ctx, digest)
    if outcome.decision == cand.DECISION_SAFE:
        observed = VERDICT_ADMIT
        counted = True
    elif outcome.decision == cand.DECISION_UNSAFE:
        observed = VERDICT_REJECT
        counted = True
    else:
        observed = VERDICT_INDETERMINATE
        counted = False
    return _outcome(observed, counted, outcome.reason_code)


#: Preregistered mechanistic inference matrix predictions.
PREDICTED_VERDICTS: Final[dict[tuple[str, str], str]] = {
    # Full candidate (reference row): admits stable, rejects all hazards
    (REFERENCE_VARIANT_ID, FAMILY_STABLE): VERDICT_ADMIT,
    (REFERENCE_VARIANT_ID, FAMILY_WITHDRAWN): VERDICT_REJECT,
    (REFERENCE_VARIANT_ID, FAMILY_REVOKED): VERDICT_REJECT,
    (REFERENCE_VARIANT_ID, FAMILY_ALLERGY): VERDICT_REJECT,
    # without_history_contrast: misses medication withdrawal!
    (VARIANT_WITHOUT_HISTORY_CONTRAST, FAMILY_STABLE): VERDICT_ADMIT,
    (VARIANT_WITHOUT_HISTORY_CONTRAST, FAMILY_WITHDRAWN): VERDICT_ADMIT,
    (VARIANT_WITHOUT_HISTORY_CONTRAST, FAMILY_REVOKED): VERDICT_REJECT,
    (VARIANT_WITHOUT_HISTORY_CONTRAST, FAMILY_ALLERGY): VERDICT_REJECT,
    # without_consent_recheck: misses consent revocation!
    (VARIANT_WITHOUT_CONSENT_RECHECK, FAMILY_STABLE): VERDICT_ADMIT,
    (VARIANT_WITHOUT_CONSENT_RECHECK, FAMILY_WITHDRAWN): VERDICT_REJECT,
    (VARIANT_WITHOUT_CONSENT_RECHECK, FAMILY_REVOKED): VERDICT_ADMIT,
    (VARIANT_WITHOUT_CONSENT_RECHECK, FAMILY_ALLERGY): VERDICT_REJECT,
    # without_medication_allergy_gate: misses allergy hazard!
    (VARIANT_WITHOUT_MEDICATION_ALLERGY_GATE, FAMILY_STABLE): VERDICT_ADMIT,
    (VARIANT_WITHOUT_MEDICATION_ALLERGY_GATE, FAMILY_WITHDRAWN): VERDICT_REJECT,
    (VARIANT_WITHOUT_MEDICATION_ALLERGY_GATE, FAMILY_REVOKED): VERDICT_REJECT,
    (VARIANT_WITHOUT_MEDICATION_ALLERGY_GATE, FAMILY_ALLERGY): VERDICT_ADMIT,
    # common_safety_gate: misses all mid-task hazards!
    (VARIANT_COMMON_SAFETY_GATE, FAMILY_STABLE): VERDICT_ADMIT,
    (VARIANT_COMMON_SAFETY_GATE, FAMILY_WITHDRAWN): VERDICT_ADMIT,
    (VARIANT_COMMON_SAFETY_GATE, FAMILY_REVOKED): VERDICT_ADMIT,
    (VARIANT_COMMON_SAFETY_GATE, FAMILY_ALLERGY): VERDICT_ADMIT,
    # full_refresh: forces regeneration (INDETERMINATE) on withdrawal
    (VARIANT_FULL_REFRESH, FAMILY_STABLE): VERDICT_ADMIT,
    (VARIANT_FULL_REFRESH, FAMILY_WITHDRAWN): VERDICT_INDETERMINATE,
    (VARIANT_FULL_REFRESH, FAMILY_REVOKED): VERDICT_REJECT,
    (VARIANT_FULL_REFRESH, FAMILY_ALLERGY): VERDICT_REJECT,
}


def _degradation_summary(predicted: Mapping[tuple[str, str], str]) -> dict[str, Any]:
    """Summary of families where each ablation's verdict degrades vs reference."""
    summary: dict[str, Any] = {}
    for variant_id in ABLATION_REGISTRY:
        missed = sorted(
            family
            for family in FAULT_FAMILY_IDS
            if predicted[(variant_id, family)] == VERDICT_ADMIT
            and predicted[(REFERENCE_VARIANT_ID, family)] == VERDICT_REJECT
        )
        indeterminate_refusals = sorted(
            family
            for family in FAULT_FAMILY_IDS
            if predicted[(variant_id, family)] == VERDICT_INDETERMINATE
            and predicted[(REFERENCE_VARIANT_ID, family)] != VERDICT_INDETERMINATE
        )
        summary[variant_id] = {
            "missed_hazard_families": missed,
            "indeterminate_refusals": indeterminate_refusals,
            "measurably_degraded": bool(missed or indeterminate_refusals),
        }
    return summary


def mechanistic_inference_matrix() -> dict[str, Any]:
    """Preregistered DESIGN RECORD: variant x family predicted verdicts.

    Predictions are frozen constants (:data:`PREDICTED_VERDICTS`) derived from
    each variant's declared mechanism semantics BEFORE any execution.
    """
    return {
        "ablations_version": ABLATIONS_VERSION,
        "reference_variant": REFERENCE_VARIANT_ID,
        "fault_families": list(FAULT_FAMILY_IDS),
        "variants": {vid: spec.to_dict() for vid, spec in ABLATION_REGISTRY.items()},
        "predicted_verdicts": {
            variant_id: {
                family: PREDICTED_VERDICTS[(variant_id, family)] for family in FAULT_FAMILY_IDS
            }
            for variant_id in (REFERENCE_VARIANT_ID, *ABLATION_REGISTRY)
        },
        "degradation_axes": _degradation_summary(PREDICTED_VERDICTS),
        "scale": "DEVELOPMENT (mechanism causality; NOT confirmatory)",
    }


def verify_mechanistic_inference_matrix() -> dict[str, Any]:
    """Run EVERY variant over EVERY frozen family fixture and verify against predictions.

    Each cell executes the variant on the family fixture, maps the verdict
    and asserts that it matches the preregistered prediction.
    """
    fixtures = case_fixtures()
    runners: dict[str, Callable[[Mapping[str, Any]], Outcome]] = {
        REFERENCE_VARIANT_ID: _run_reference,
        **{vid: (lambda case, _vid=vid: run_ablation(_vid, case)) for vid in ABLATION_REGISTRY},
    }
    cells: list[dict[str, Any]] = []
    all_match = True
    observed_verdicts: dict[str, dict[str, str]] = {}
    observed_pairs: dict[tuple[str, str], str] = {}

    for variant_id, runner in runners.items():
        observed_verdicts[variant_id] = {}
        for family in FAULT_FAMILY_IDS:
            fixture_case = fixtures[family]()
            outcome = runner(fixture_case)
            observed = outcome.observed_outcome
            predicted = PREDICTED_VERDICTS[(variant_id, family)]
            match = observed == predicted
            all_match = all_match and match
            observed_verdicts[variant_id][family] = observed
            observed_pairs[(variant_id, family)] = observed
            cells.append(
                {
                    "variant_id": variant_id,
                    "family_id": family,
                    "predicted": predicted,
                    "observed": observed,
                    "match": match,
                    "detail": outcome.detail,
                }
            )

    return {
        "ablations_version": ABLATIONS_VERSION,
        "all_cells_match": all_match,
        "cell_count": len(cells),
        "observed_verdicts": observed_verdicts,
        "degradation_summary": _degradation_summary(observed_pairs),
        "cells": cells,
    }
