"""Matched valid/invalid control-case builders per GovRed family.

Each family's contract (``family_contracts.FamilyContract``) names its matched
valid control class(es) — one of the seven prespecified ``*_valid`` builders —
and its invalid (adversarial) control.  This module turns those names into
concrete, sanitized :class:`ControlCase` objects so an evaluation can pair every
adversarial schedule with a no-drift control of the same boundary shape.

A valid control pins a single governance dimension (consent, policy, actor,
state, digest, expiry, subject) to its intact value; the invalid control applies
the family's scheduled drift on that dimension.  Both cases carry the family's
required boundary stages, so the pair is measured over the same boundary.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from evaluation.governance_adversarial.family_contracts import (
    VALID_CONTROL_NAMES,
    family_contract,
)

ControlKind = Literal["valid", "invalid"]

_DIMENSION_BY_VALID: dict[str, str] = {
    "consent_unchanged_valid": "consent",
    "policy_unchanged_valid": "policy",
    "actor_stable_valid": "actor",
    "same_state_valid": "state",
    "digest_intact_valid": "digest",
    "unexpired_valid": "expiry",
    "same_subject_valid": "subject",
}

_DIMENSION_BY_INVALID: dict[str, str] = {
    "cross_subject_retrieval": "subject",
    "subject_cross_replay": "subject",
    "consent_revoke": "consent",
    "actor_switch_replay": "actor",
    "state_advance": "state",
    "concurrent_governance_writer": "state",
    "policy_version_change": "policy",
    "snapshot_digest_invalid": "digest",
    "purpose_mismatch": "purpose",
    "gst_bypass_prompt": "prompt",
    "patient_evidence_prompt_injection": "prompt",
    "unrelated_disclosure_request": "subject",
    "audit_reconstruction_failure": "audit",
}

#: invalid-control name → mutation actually sent to the synthetic commit probe
#: (mirrors ``isolated_boundary_adapter._MUTATIONS``; ``None`` means the
#: schedule is exercised on the disclosure/retrieval path, not a commit mutation).
_MUTATION_BY_INVALID: dict[str, str | None] = {
    "cross_subject_retrieval": None,
    "subject_cross_replay": "subject_cross_replay",
    "consent_revoke": "consent_revoke",
    "actor_switch_replay": "actor_switch_replay",
    "state_advance": "state_advance",
    "concurrent_governance_writer": "concurrent_governance_writer",
    "policy_version_change": "policy_version_change",
    "snapshot_digest_invalid": "snapshot_digest_invalid",
    "purpose_mismatch": None,
    "gst_bypass_prompt": None,
    "patient_evidence_prompt_injection": None,
    "unrelated_disclosure_request": None,
    "audit_reconstruction_failure": "none",
}


@dataclass(frozen=True)
class ControlCase:
    """One sanitized, matched control case for a family.

    ``dimension`` is the governance dimension the control pins or drifts.
    ``mutation`` is the synthetic commit-probe mutation (``None`` when the
    schedule runs on the disclosure/retrieval path).
    """

    family: str
    kind: ControlKind
    control: str
    dimension: str
    mutation: str | None
    governance_delta: str
    expected_outcome: str
    required_stages: frozenset[str]


def _valid_case(family: str, control: str) -> ControlCase:
    contract = family_contract(family)
    if control not in _DIMENSION_BY_VALID:
        raise ValueError(f"govred_valid_control_unknown:{control}")
    return ControlCase(
        family=family,
        kind="valid",
        control=control,
        dimension=_DIMENSION_BY_VALID[control],
        mutation=None,
        governance_delta="none",
        expected_outcome="governance_intact",
        required_stages=contract.required_stages(),
    )


def consent_unchanged_valid(family: str) -> ControlCase:
    return _valid_case(family, "consent_unchanged_valid")


def policy_unchanged_valid(family: str) -> ControlCase:
    return _valid_case(family, "policy_unchanged_valid")


def actor_stable_valid(family: str) -> ControlCase:
    return _valid_case(family, "actor_stable_valid")


def same_state_valid(family: str) -> ControlCase:
    return _valid_case(family, "same_state_valid")


def digest_intact_valid(family: str) -> ControlCase:
    return _valid_case(family, "digest_intact_valid")


def unexpired_valid(family: str) -> ControlCase:
    return _valid_case(family, "unexpired_valid")


def same_subject_valid(family: str) -> ControlCase:
    return _valid_case(family, "same_subject_valid")


_VALID_BUILDERS: dict[str, Callable[[str], ControlCase]] = {
    "consent_unchanged_valid": consent_unchanged_valid,
    "policy_unchanged_valid": policy_unchanged_valid,
    "actor_stable_valid": actor_stable_valid,
    "same_state_valid": same_state_valid,
    "digest_intact_valid": digest_intact_valid,
    "unexpired_valid": unexpired_valid,
    "same_subject_valid": same_subject_valid,
}


def _invalid_case(family: str) -> ControlCase:
    contract = family_contract(family)
    invalid_control = contract.invalid_control
    if invalid_control not in _DIMENSION_BY_INVALID:
        raise ValueError(f"govred_invalid_control_unknown:{invalid_control}")
    return ControlCase(
        family=family,
        kind="invalid",
        control=invalid_control,
        dimension=_DIMENSION_BY_INVALID[invalid_control],
        mutation=_MUTATION_BY_INVALID.get(invalid_control),
        governance_delta="drift",
        expected_outcome="prohibited_outcome_expected",
        required_stages=contract.required_stages(),
    )


def valid_control(family: str, *, primary: bool = True) -> ControlCase:
    """Return a family's matched valid control (primary by default).

    ``digest_expiry_tamper_replay`` declares two valid controls
    (``digest_intact_valid`` and ``unexpired_valid``); use ``primary=False`` to
    select the secondary one.
    """

    contract = family_contract(family)
    name = contract.valid_controls[0] if primary else contract.valid_controls[-1]
    return _VALID_BUILDERS[name](family)


def invalid_control(family: str) -> ControlCase:
    """Return a family's adversarial (invalid) control case."""

    return _invalid_case(family)


def control_pair(family: str) -> tuple[ControlCase, ControlCase]:
    """Return ``(valid, invalid)`` matched controls for one family."""

    return valid_control(family), invalid_control(family)


def validate_control_names() -> None:
    """Fail closed if any valid builder name is not in the prespecified set."""

    if set(_VALID_BUILDERS) != set(VALID_CONTROL_NAMES):
        raise ValueError("govred_valid_control_set_mismatch")
