"""Closed contracts for the optional, non-release Council shadow path.

This module is intentionally free of settings, HTTP clients, and provider code.
It defines the *only* specialist identities, output shapes, source classes, and
adjudication transition that a future registry-bound Council shadow runner may
use.  The deterministic Council remains the release path.

Most importantly, :func:`merge_verified_shadow_adjudication` is monotonic:
it retains the deterministic baseline triage unless independently-verified
shadow evidence calls for a higher urgency.  It can also request human review;
it can never lower triage, clear a review requirement, confirm a case fact, or
make a release decision.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, field_validator

COUNCIL_SHADOW_CONTRACT_VERSION = "council-specialist-shadow.v5"
COUNCIL_SHADOW_PROMPT_FAMILY_VERSION = "council-specialist-profiles.vi.v1"

CouncilShadowSpecialty = Literal[
    "cardiology",
    "neurology",
    "nephrology",
    "pharmacology",
    "endocrinology",
]
CouncilShadowTriage = Literal[
    "routine_follow_up",
    "same_day_review",
    "emergency_escalation",
]
CouncilShadowSafeAction = Literal[
    "collect_more_information",
    "clinician_review",
    "same_day_in_person_review",
    "emergency_evaluation",
]
CouncilShadowSourceClass = Literal["case_packet_fact"]
CouncilShadowTool = Literal["case_packet"]
CouncilShadowVerifierStatus = Literal["verified", "rejected"]

_TRIAGE_RANK: dict[CouncilShadowTriage, int] = {
    "routine_follow_up": 1,
    "same_day_review": 2,
    "emergency_escalation": 3,
}
_STABLE_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._:-]{0,127}$")


@dataclass(frozen=True)
class CouncilShadowSpecialistProfile:
    """Code-owned policy for a single independent shadow specialist.

    A caller cannot nominate a new specialty, prompt version, tool, or source
    class through request data.  ``case_packet`` is the sole tool and only
    immutable case-fact IDs may substantiate a finding.  Retrieval availability
    remains outside this contract because opaque retrieval IDs are not clinical
    support.
    """

    specialty: CouncilShadowSpecialty
    prompt_version: str
    allowed_source_classes: tuple[CouncilShadowSourceClass, ...]
    allowed_tools: tuple[CouncilShadowTool, ...]
    required_structured_fields: tuple[str, ...]


_REQUIRED_STRUCTURED_FIELDS = (
    "contract_version",
    "specialty",
    "prompt_version",
    "source_class",
    "tool",
    "supported_findings",
    "missing_information",
    "uncertainties",
    "suggested_questions",
    "abstain",
    "abstention_reason",
    "triage_suggestion",
    "safe_next_action_class",
)


def _profile(specialty: CouncilShadowSpecialty) -> CouncilShadowSpecialistProfile:
    return CouncilShadowSpecialistProfile(
        specialty=specialty,
        prompt_version=f"{COUNCIL_SHADOW_PROMPT_FAMILY_VERSION}.{specialty}",
        allowed_source_classes=("case_packet_fact",),
        allowed_tools=("case_packet",),
        required_structured_fields=_REQUIRED_STRUCTURED_FIELDS,
    )


# The allowlist is deliberately code-owned, frozen, and shared by all future
# call sites.  There is no caller-controlled prompt/template selection.
COUNCIL_SHADOW_SPECIALIST_PROFILES: Mapping[
    CouncilShadowSpecialty, CouncilShadowSpecialistProfile
] = {
    "cardiology": _profile("cardiology"),
    "neurology": _profile("neurology"),
    "nephrology": _profile("nephrology"),
    "pharmacology": _profile("pharmacology"),
    "endocrinology": _profile("endocrinology"),
}


def resolve_council_shadow_specialist_profile(
    specialty: object,
) -> CouncilShadowSpecialistProfile | None:
    """Return a code-owned profile, never a profile supplied by the caller."""

    if not isinstance(specialty, str):
        return None
    canonical = specialty.strip().lower()
    return COUNCIL_SHADOW_SPECIALIST_PROFILES.get(canonical)  # type: ignore[arg-type]


def resolve_council_shadow_specialist_profiles(
    requested: Iterable[object],
) -> tuple[CouncilShadowSpecialistProfile, ...]:
    """De-duplicate requested names and discard every non-allowlisted value."""

    output: list[CouncilShadowSpecialistProfile] = []
    seen: set[str] = set()
    for value in requested:
        profile = resolve_council_shadow_specialist_profile(value)
        if profile is None or profile.specialty in seen:
            continue
        seen.add(profile.specialty)
        output.append(profile)
    return tuple(output)


class CouncilShadowFinding(BaseModel):
    """One specialist claim, linked only to immutable case-packet fact IDs."""

    model_config = ConfigDict(extra="forbid", strict=True)

    statement: StrictStr = Field(min_length=1, max_length=600)
    evidence_case_fact_ids: list[StrictStr] = Field(min_length=1, max_length=12)

    @field_validator("evidence_case_fact_ids")
    @classmethod
    def _case_fact_ids_are_stable(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value) or any(
            not _STABLE_ID_RE.fullmatch(item) for item in value
        ):
            raise ValueError("invalid or duplicate case fact ID")
        return value


class CouncilShadowSpecialistOpinion(BaseModel):
    """Closed model-output contract for one profile-bound specialist.

    This is a parse boundary only.  A valid parse is *not* clinical truth; an
    independent deterministic verifier must return ``verified`` before the
    opinion can participate in the merge helper below.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    contract_version: Literal[COUNCIL_SHADOW_CONTRACT_VERSION]
    specialty: CouncilShadowSpecialty
    prompt_version: StrictStr = Field(min_length=1, max_length=160)
    source_class: CouncilShadowSourceClass
    tool: CouncilShadowTool
    supported_findings: list[CouncilShadowFinding] = Field(default_factory=list, max_length=10)
    missing_information: list[StrictStr] = Field(default_factory=list, max_length=10)
    uncertainties: list[StrictStr] = Field(default_factory=list, max_length=8)
    suggested_questions: list[StrictStr] = Field(default_factory=list, max_length=8)
    abstain: StrictBool
    abstention_reason: StrictStr = Field(max_length=600)
    triage_suggestion: CouncilShadowTriage
    safe_next_action_class: CouncilShadowSafeAction

    @field_validator("missing_information", "uncertainties", "suggested_questions")
    @classmethod
    def _bounded_text_is_nonempty(cls, value: list[str]) -> list[str]:
        if any(not item.strip() or len(item) > 600 for item in value):
            raise ValueError("blank or overlong structured text")
        return value


class CouncilShadowVerifierResult(BaseModel):
    """Closed result of a deterministic, non-self verifier."""

    model_config = ConfigDict(extra="forbid", strict=True)

    contract_version: Literal[COUNCIL_SHADOW_CONTRACT_VERSION]
    specialty: CouncilShadowSpecialty
    prompt_version: StrictStr = Field(min_length=1, max_length=160)
    status: CouncilShadowVerifierStatus
    accepted_finding_count: int = Field(ge=0, le=10)
    rejected_finding_count: int = Field(ge=0, le=10)
    rejection_codes: list[StrictStr] = Field(default_factory=list, max_length=12)
    self_verification_performed: Literal[False] = False
    verifier_method: Literal["deterministic_case_fact_and_profile_validation"]


class CouncilShadowAdjudication(BaseModel):
    """Closed, non-release result of a monotonic deterministic merge."""

    model_config = ConfigDict(extra="forbid", strict=True)

    contract_version: Literal[COUNCIL_SHADOW_CONTRACT_VERSION]
    stage: Literal["deterministic_shadow_adjudication"]
    release_effect: Literal["none_shadow_only"]
    baseline_triage: CouncilShadowTriage
    effective_triage: CouncilShadowTriage
    shadow_urgency_raised: StrictBool
    baseline_requires_human_review: StrictBool
    requires_human_review: StrictBool
    verified_specialties: list[CouncilShadowSpecialty] = Field(default_factory=list, max_length=5)
    reason_codes: list[StrictStr] = Field(default_factory=list, max_length=12)
    self_verification_performed: Literal[False] = False
    adjudicator_scope: Literal["monotonic_safety_floor_and_human_review_only"]


@dataclass(frozen=True)
class VerifiedCouncilShadowOpinion:
    """Opaque pair emitted only by the deterministic local verifier helper."""

    opinion: CouncilShadowSpecialistOpinion
    verifier: CouncilShadowVerifierResult


def _validate_profile_bound_opinion(
    opinion: CouncilShadowSpecialistOpinion,
    *,
    valid_case_fact_ids: set[str],
) -> CouncilShadowVerifierResult:
    """Verify profile binding and case-fact evidence without clinical inference."""

    profile = resolve_council_shadow_specialist_profile(opinion.specialty)
    rejection_codes: list[str] = []
    accepted = 0
    rejected = 0
    if profile is None:
        rejection_codes.append("specialty_not_allowlisted")
    else:
        if opinion.prompt_version != profile.prompt_version:
            rejection_codes.append("prompt_version_not_profile_bound")
        if opinion.source_class not in profile.allowed_source_classes:
            rejection_codes.append("source_class_not_allowed")
        if opinion.tool not in profile.allowed_tools:
            rejection_codes.append("tool_not_allowed")

    for finding in opinion.supported_findings:
        if all(
            case_fact_id in valid_case_fact_ids for case_fact_id in finding.evidence_case_fact_ids
        ):
            accepted += 1
        else:
            rejected += 1
    if rejected:
        rejection_codes.append("finding_references_unknown_case_fact")
    if not opinion.abstain and accepted == 0:
        rejection_codes.append("non_abstaining_opinion_has_no_supported_finding")
    if opinion.abstain and not opinion.abstention_reason.strip():
        rejection_codes.append("abstention_reason_required")
    if not opinion.abstain and opinion.abstention_reason.strip():
        rejection_codes.append("abstention_reason_present_without_abstention")

    status: CouncilShadowVerifierStatus = "verified" if not rejection_codes else "rejected"
    return CouncilShadowVerifierResult(
        contract_version=COUNCIL_SHADOW_CONTRACT_VERSION,
        specialty=opinion.specialty,
        prompt_version=opinion.prompt_version,
        status=status,
        accepted_finding_count=accepted,
        rejected_finding_count=rejected,
        rejection_codes=rejection_codes,
        verifier_method="deterministic_case_fact_and_profile_validation",
    )


def verify_council_shadow_specialist_opinion(
    opinion: CouncilShadowSpecialistOpinion,
    *,
    valid_case_fact_ids: Iterable[str],
) -> VerifiedCouncilShadowOpinion | None:
    """Return an independently verified opinion or ``None``.

    This function does not decide whether the clinical assertion is correct.
    It verifies only code-owned profile policy and the source IDs that existed
    before the model invocation.  A rejected output is intentionally discarded
    rather than partially repaired or made release-eligible.
    """

    verifier = _validate_profile_bound_opinion(
        opinion,
        valid_case_fact_ids={item for item in valid_case_fact_ids if isinstance(item, str)},
    )
    if verifier.status != "verified":
        return None
    return VerifiedCouncilShadowOpinion(opinion=opinion, verifier=verifier)


def merge_verified_shadow_adjudication(
    *,
    baseline_triage: CouncilShadowTriage,
    baseline_requires_human_review: bool,
    verified_opinions: Sequence[VerifiedCouncilShadowOpinion],
) -> CouncilShadowAdjudication:
    """Merge independently verified shadow opinions without lowering safety.

    The output has no release authority.  The only state it can add is a
    higher triage safety floor and/or a human-review request.  Invalid/mismatched
    pairs are ignored defensively, so an external caller cannot turn a raw LLM
    output into an adjudication input merely by constructing a lookalike value.
    """

    effective_triage = baseline_triage
    reason_codes: list[str] = []
    verified_specialties: list[CouncilShadowSpecialty] = []
    seen: set[str] = set()
    has_uncertainty_or_abstention = False
    observed_triages: set[CouncilShadowTriage] = set()

    for item in verified_opinions:
        opinion = item.opinion
        verifier = item.verifier
        profile = resolve_council_shadow_specialist_profile(opinion.specialty)
        if (
            profile is None
            or verifier.status != "verified"
            or verifier.specialty != opinion.specialty
            or verifier.prompt_version != profile.prompt_version
            or opinion.prompt_version != profile.prompt_version
            or opinion.contract_version != COUNCIL_SHADOW_CONTRACT_VERSION
        ):
            continue
        if opinion.specialty not in seen:
            seen.add(opinion.specialty)
            verified_specialties.append(opinion.specialty)
        observed_triages.add(opinion.triage_suggestion)
        if _TRIAGE_RANK[opinion.triage_suggestion] > _TRIAGE_RANK[effective_triage]:
            effective_triage = opinion.triage_suggestion
        has_uncertainty_or_abstention = has_uncertainty_or_abstention or bool(
            opinion.abstain or opinion.uncertainties or opinion.missing_information
        )

    if _TRIAGE_RANK[effective_triage] > _TRIAGE_RANK[baseline_triage]:
        reason_codes.append("shadow_urgency_vote_above_baseline")
    if len(observed_triages) > 1:
        reason_codes.append("verified_shadow_triage_disagreement")
    if has_uncertainty_or_abstention:
        reason_codes.append("verified_shadow_uncertainty_or_abstention")
    if verified_specialties:
        reason_codes.append("verified_shadow_output_requires_human_review")

    # ``or`` ensures the shadow merge cannot clear an existing review hold.
    requires_human_review = baseline_requires_human_review or bool(verified_specialties)
    return CouncilShadowAdjudication(
        contract_version=COUNCIL_SHADOW_CONTRACT_VERSION,
        stage="deterministic_shadow_adjudication",
        release_effect="none_shadow_only",
        baseline_triage=baseline_triage,
        effective_triage=effective_triage,
        shadow_urgency_raised=_TRIAGE_RANK[effective_triage] > _TRIAGE_RANK[baseline_triage],
        baseline_requires_human_review=baseline_requires_human_review,
        requires_human_review=requires_human_review,
        verified_specialties=verified_specialties,
        reason_codes=reason_codes,
        adjudicator_scope="monotonic_safety_floor_and_human_review_only",
    )


def _case_packet_fact_ids(case_packet: Mapping[str, Any]) -> set[str] | None:
    """Read only pre-existing, stable fact IDs from an immutable case packet."""

    facts = case_packet.get("facts")
    if not isinstance(facts, list) or not facts:
        return None
    identifiers: set[str] = set()
    for item in facts:
        if not isinstance(item, Mapping):
            return None
        fact_id = item.get("id")
        if not isinstance(fact_id, str) or not _STABLE_ID_RE.fullmatch(fact_id):
            return None
        if fact_id in identifiers:
            return None
        identifiers.add(fact_id)
    return identifiers


def run_specialist_shadow_workflow(
    case_packet: dict[str, Any],
    assessments: list[dict[str, Any]],
    *,
    client: Any,
) -> dict[str, Any]:
    """Validate completed specialist outputs and create a non-release projection.

    Interface for the registry-bound runner:

    * ``case_packet`` must be an immutable packet with ``facts`` (stable IDs),
      ``deterministic_baseline_triage`` and
      ``deterministic_baseline_requires_human_review`` supplied by the
      deterministic Council path.
    * ``assessments`` contains one raw JSON object per already-completed
      specialist call.  It must not contain provider responses, prompts, chain
      of thought, retrieval text, or case facts not in ``case_packet``.
    * ``client`` is accepted for the runner's uniform interface but deliberately
      unused here.  This final verifier/adjudicator is deterministic so a model
      cannot become the sole verifier of its own risk-sensitive output.

    Exceptions and malformed data become safe, content-free failure records.
    The function does not invoke ``client``, mutate case data, perform a model
    call, or create a release decision.
    """

    # Keep the signature compatible with model-runner call sites while making
    # the non-self-verification boundary explicit and mechanically reviewable.
    _ = client
    unavailable = {
        "status": "unavailable",
        "mode": "shadow",
        "release_effect": "none_shadow_only",
        "assessments": [],
        "failures": [{"stage": "workflow", "code": "invalid_case_packet"}],
        "client_used": False,
    }
    if not isinstance(case_packet, dict) or not isinstance(assessments, list):
        return unavailable
    fact_ids = _case_packet_fact_ids(case_packet)
    baseline_triage = case_packet.get("deterministic_baseline_triage")
    baseline_review = case_packet.get("deterministic_baseline_requires_human_review")
    if (
        fact_ids is None
        or baseline_triage not in _TRIAGE_RANK
        or not isinstance(baseline_review, bool)
    ):
        return unavailable

    verified: list[VerifiedCouncilShadowOpinion] = []
    accepted_assessments: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for raw in assessments:
        if not isinstance(raw, dict):
            failures.append({"stage": "specialist_output", "code": "invalid_schema"})
            continue
        try:
            opinion = CouncilShadowSpecialistOpinion.model_validate(raw)
        except Exception:  # noqa: BLE001 - never expose parser/provider details
            failures.append({"stage": "specialist_output", "code": "invalid_schema"})
            continue
        checked = verify_council_shadow_specialist_opinion(opinion, valid_case_fact_ids=fact_ids)
        if checked is None:
            failures.append({"stage": "deterministic_verifier", "code": "rejected_contract"})
            continue
        verified.append(checked)
        # Only the closed contract is retained: never raw provider metadata or
        # prompt content.  The parent can attach this shadow-only projection to
        # its existing audit envelope.
        accepted_assessments.append(checked.opinion.model_dump())

    adjudication = merge_verified_shadow_adjudication(
        baseline_triage=baseline_triage,
        baseline_requires_human_review=baseline_review,
        verified_opinions=verified,
    )
    status = "complete" if verified and not failures else "partial" if verified else "unavailable"
    return {
        "status": status,
        "mode": "shadow",
        "release_effect": "none_shadow_only",
        "client_used": False,
        "assessments": accepted_assessments,
        "failures": failures,
        "adjudication": adjudication.model_dump(),
    }


__all__ = [
    "COUNCIL_SHADOW_CONTRACT_VERSION",
    "COUNCIL_SHADOW_PROMPT_FAMILY_VERSION",
    "COUNCIL_SHADOW_SPECIALIST_PROFILES",
    "CouncilShadowAdjudication",
    "CouncilShadowFinding",
    "CouncilShadowSpecialistOpinion",
    "CouncilShadowSpecialistProfile",
    "CouncilShadowVerifierResult",
    "VerifiedCouncilShadowOpinion",
    "merge_verified_shadow_adjudication",
    "resolve_council_shadow_specialist_profile",
    "resolve_council_shadow_specialist_profiles",
    "run_specialist_shadow_workflow",
    "verify_council_shadow_specialist_opinion",
]
