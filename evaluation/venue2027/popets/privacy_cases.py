"""CLARA-Care 2027 POPETS task POPETS-X07_privacy_cases — frozen privacy test cases.

Purpose
-------
The **ex-ante frozen** privacy test-case set for the PoPETs 2027 study
*Revocation-Complete Future Disclosure for Cached Longitudinal AI Contexts*
(``research/venue2027/VENUES/popets/RESEARCH_BLUEPRINT.md``, scenario matrix
``research/venue2027/VENUES/popets/CASE_MATRIX.md``, task contract
``research/venue2027/VENUES/popets/TASKS/POPETS-X07_privacy_cases.md``).

The set is frozen BEFORE any candidate arm (B0-B4, C0) executes: it is the
confirmatory denominator for RQ1 (post-revocation leakage through transitive
caches and retries) plus the guarantee-boundary cases that keep the threat
model honest. Five scenario classes are represented:

1. ``fresh_dispatch``            — authorized fresh dispatch under active consent
   (POPETS-CASE-01/04 shape) → expected ``ALLOW``.
2. ``post_revocation_dispatch``  — cached context dispatched at/after ``t_r``
   (POPETS-CASE-02/08 shape) → expected ``DENY``.
3. ``cross_purpose``             — cache built for purpose A served for
   purpose B (POPETS-CASE-05 shape) → expected ``DENY``.
4. ``transitive_gap``            — derived cache with unknown ancestry /
   missing lineage edge (POPETS-CASE-03/07 shape) → expected
   ``INDETERMINATE`` on the disclosure gate, never coerced to a safe verdict.
5. ``already_delivered``         — bytes left the process boundary strictly
   before ``t_r`` (POPETS-CASE-06 shape) → the future-dispatch verdict is
   reported ``ALLOW``/``DENY`` exactly as the ledger dictates, but the
   *expected semantic outcome* for the study is ``OUT_OF_SCOPE``: no
   retroactive-erasure claim is admissible. Memorization of already-delivered
   bytes is ``NOT_GUARANTEED`` (``memorization_uncertainty`` class).

Each case carries a :class:`PrivacyCase` with a typed ``scenario`` (the
controlled synthetic input: ledger view, dispatch item, principal, purpose,
query time), the ``expected_semantic_outcome`` drawn from
:class:`ExpectedSemanticOutcome`, and a ``revocation_model_reference`` naming
the exact clause of :mod:`evaluation.venue2027.popets.revocation_model` that
adjudicates it (``allowed``/``decide`` verdicts plus the orthogonal
``RevocationDecision`` effect fields). Expected outcomes are *semantic
outcomes of the study*, not a fourth verdict value: ``OUT_OF_SCOPE`` and
``NOT_GUARANTEED`` cases still produce an ordinary
``ALLOW``/``DENY``/``INDETERMINATE`` verdict from the model; the expected
outcome constrains the honest interpretation (threat precision), never the
verdict itself.

Allowed input
-------------
None at import time: the set is a module-level constant tuple of frozen
dataclasses. Helper functions accept only the case objects shipped here.
No real PHI, no live provider, no clock, no randomness; all principals,
purposes and artifacts are synthetic structural placeholders.

Failure semantics (stable uppercase reason codes on :class:`PrivacyCaseError`)
------------------------------------------------------------------------------
- ``CASE_SET_DRIFT`` — a candidate case set does not hash to the committed
  freeze constant ``FROZEN_CASE_SET_SHA256`` (post-hoc addition, removal,
  rewording or reordering of a case is drift and is refused).
- ``CASE_MALFORMED`` — a case fails internal-consistency validation (unknown
  outcome class, non-positive timeline, empty ids, missing semantic
  reference).
- ``CASE_UNKNOWN`` — lookup by id for an id outside the frozen set.

Version
-------
``PRIVACY_CASES_VERSION = "1.0.0"``. Output is JSON-serializable via
:meth:`PrivacyCase.to_dict`.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Final, Literal

from evaluation.venue2027.popets.revocation_model import (
    ConsentLedgerView,
    DispatchItem,
)

__all__ = [
    "FROZEN_CASE_SET_SHA256",
    "EXPECTED_SEMANTIC_OUTCOMES",
    "PRIVACY_CASES_VERSION",
    "SCENARIO_CLASSES",
    "CaseScenario",
    "PrivacyCase",
    "PrivacyCaseError",
    "assert_frozen_cases",
    "case_by_id",
    "cases_sha256",
    "expected_semantic_outcomes",
    "serialize_case_set",
    "PRIVACY_CASES",
    "PRIVACY_CASE_IDS",
]

PRIVACY_CASES_VERSION: Final[str] = "1.0.0"

#: Scenario classes of the frozen set (CASE_MATRIX-aligned study vocabulary).
ScenarioClass = Literal[
    "fresh_dispatch",
    "post_revocation_dispatch",
    "cross_purpose",
    "transitive_gap",
    "already_delivered",
]

SCENARIO_CLASSES: Final[tuple[str, ...]] = (
    "fresh_dispatch",
    "post_revocation_dispatch",
    "cross_purpose",
    "transitive_gap",
    "already_delivered",
)

#: Expected *semantic* outcomes of the study (not verdict values; see module
#: docstring). ``ALLOW``/``DENY``/``INDETERMINATE`` mirror the model's verdict
#: vocabulary; ``OUT_OF_SCOPE`` (threat precision, POPETS-CASE-06) and
#: ``NOT_GUARANTEED`` (memorization uncertainty) are honest guarantee-boundary
#: outcomes that must never be coerced into a verdict.
ExpectedSemanticOutcome = Literal[
    "ALLOW",
    "DENY",
    "INDETERMINATE",
    "OUT_OF_SCOPE",
    "NOT_GUARANTEED",
]

EXPECTED_SEMANTIC_OUTCOMES: Final[tuple[str, ...]] = (
    "ALLOW",
    "DENY",
    "INDETERMINATE",
    "OUT_OF_SCOPE",
    "NOT_GUARANTEED",
)

OUT_OF_SCOPE: Final[str] = "OUT_OF_SCOPE"
NOT_GUARANTEED: Final[str] = "NOT_GUARANTEED"

REASON_CASE_SET_DRIFT: Final[str] = "CASE_SET_DRIFT"
REASON_CASE_MALFORMED: Final[str] = "CASE_MALFORMED"
REASON_CASE_UNKNOWN: Final[str] = "CASE_UNKNOWN"


class PrivacyCaseError(ValueError):
    """Fail-closed error carrying a stable uppercase ``reason_code``."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


# ---------------------------------------------------------------------------
# Typed case objects (JSON-serializable)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class CaseScenario:
    """Controlled synthetic input of one privacy case.

    ``ledger`` is the injected consent-ledger projection (grants keyed by
    synthetic principal; revocations with logical instants); ``item`` is the
    outbound dispatch whose disclosure is gated; ``principal`` / ``purpose`` /
    ``time`` are the query triple. Everything is a synthetic structural
    placeholder: artifact ids encode *labels*, never content.
    """

    ledger: Mapping[str, Any]
    item: Mapping[str, Any]
    principal: str
    purpose: str
    time: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "ledger": {
                "grants": {k: dict(v) for k, v in self.ledger["grants"].items()},
                "revocations": [dict(r) for r in self.ledger["revocations"]],
            },
            "item": dict(self.item),
            "principal": self.principal,
            "purpose": self.purpose,
            "time": self.time,
        }


@dataclasses.dataclass(frozen=True)
class PrivacyCase:
    """One frozen ex-ante privacy test case."""

    case_id: str
    scenario_class: ScenarioClass
    scenario: CaseScenario
    expected_semantic_outcome: ExpectedSemanticOutcome
    revocation_model_reference: str
    case_matrix_ref: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "scenario_class": self.scenario_class,
            "scenario": self.scenario.to_dict(),
            "expected_semantic_outcome": self.expected_semantic_outcome,
            "revocation_model_reference": self.revocation_model_reference,
            "case_matrix_ref": self.case_matrix_ref,
            "description": self.description,
            "cases_version": PRIVACY_CASES_VERSION,
        }


# ---------------------------------------------------------------------------
# Synthetic shared fixtures (structural placeholders only, PHI-free)
# ---------------------------------------------------------------------------

GRANTED_AT: Final[int] = 10
REVOKED_AT: Final[int] = 100

#: Lineage-label table for the synthetic principal (grant-scoped label table,
#: revocation_model.py LINEAGE_INDETERMINATE semantics: a node absent here or
#: mapped to None is unknown ancestry).
_LABELS: Final[dict[str, str | None]] = {
    "record_vitals_1": "vitals",
    "record_meds_1": "medications",
    "summary_cache_1": "vitals",
    "summary_cache_2": "vitals",
    "embedding_pointer_1": "vitals",
    "retry_payload_1": "vitals",
    "fallback_transport_1": "vitals",
    "orphan_derived_cache": None,
}

_GRANT: Final[dict[str, Any]] = {
    "granted_at": GRANTED_AT,
    "purposes": ["self_care", "care_summary"],
    "consent_epoch": 3,
    "lineage_labels": dict(_LABELS),
}

#: Second synthetic principal whose consented purpose vocabulary makes
#: ``medication_review`` a KNOWN purpose in the ledger, so the cross-purpose
#: case is a determined DENY (PURPOSE_NOT_CONSENTED), not an unknown-purpose
#: refusal (PURPOSE_UNKNOWN).
_GRANT_OTHER: Final[dict[str, Any]] = {
    "granted_at": GRANTED_AT,
    "purposes": ["medication_review"],
    "consent_epoch": 2,
    "lineage_labels": {},
}

_LEDGER_ACTIVE: Final[dict[str, Any]] = {
    "grants": {"subj-1": dict(_GRANT)},
    "revocations": [],
}

_LEDGER_REVOKED: Final[dict[str, Any]] = {
    "grants": {"subj-1": dict(_GRANT)},
    "revocations": [{"principal": "subj-1", "purpose": "care_summary", "revoked_at": REVOKED_AT}],
}


def _ledger_active() -> dict[str, Any]:
    return {
        "grants": {
            "subj-1": {**_GRANT, "lineage_labels": dict(_LABELS)},
            "subj-2": dict(_GRANT_OTHER),
        },
        "revocations": [],
    }


def _ledger_revoked() -> dict[str, Any]:
    return {
        "grants": {
            "subj-1": {**_GRANT, "lineage_labels": dict(_LABELS)},
            "subj-2": dict(_GRANT_OTHER),
        },
        "revocations": [
            {"principal": "subj-1", "purpose": "care_summary", "revoked_at": REVOKED_AT}
        ],
    }


# ---------------------------------------------------------------------------
# The ex-ante frozen set (N=8). Do not edit below this line without a new
# freeze version; the tests recompute FROZEN_CASE_SET_SHA256.
# ---------------------------------------------------------------------------

PRIVACY_CASES: Final[tuple[PrivacyCase, ...]] = (
    # ---- class 1: fresh dispatch (authorized utility, POPETS-CASE-01/04) ----
    PrivacyCase(
        case_id="PC-FRESH-01",
        scenario_class="fresh_dispatch",
        scenario=CaseScenario(
            ledger=_ledger_active(),
            item={
                "item_id": "dispatch-fresh-01",
                "lineage": ["record_vitals_1"],
                "item_epoch": 3,
                "already_delivered": False,
                "stored_copy": True,
            },
            principal="subj-1",
            purpose="care_summary",
            time=GRANTED_AT + 5,
        ),
        expected_semantic_outcome="ALLOW",
        revocation_model_reference=(
            "revocation_model.decide: ALLOW/ALLOWED_ACTIVE_CONSENT under active "
            "consent, consented purpose, verifiable lineage and live epoch"
        ),
        case_matrix_ref="POPETS-CASE-01",
        description=(
            "Authorized fresh dispatch: valid consent, consented purpose, live "
            "consent epoch, fully labelled lineage, no revocation."
        ),
    ),
    PrivacyCase(
        case_id="PC-FRESH-02",
        scenario_class="fresh_dispatch",
        scenario=CaseScenario(
            ledger=_ledger_active(),
            item={
                "item_id": "dispatch-fresh-02",
                "lineage": ["record_vitals_1", "summary_cache_1"],
                "item_epoch": 3,
                "already_delivered": False,
                "stored_copy": True,
            },
            principal="subj-1",
            purpose="care_summary",
            time=GRANTED_AT + 7,
        ),
        expected_semantic_outcome="ALLOW",
        revocation_model_reference=(
            "revocation_model.decide: ALLOW with a derived cache node in lineage; "
            "scope-local recompute preserves utility without false invalidation"
        ),
        case_matrix_ref="POPETS-CASE-04",
        description=(
            "Independent unrelated record edit: no policy or dependency edge "
            "changed; labelled derived node must NOT trigger false invalidation."
        ),
    ),
    # ---- class 2: post-revocation dispatch (retry leakage, CASE-02/08) ----
    PrivacyCase(
        case_id="PC-REVOKE-01",
        scenario_class="post_revocation_dispatch",
        scenario=CaseScenario(
            ledger=_ledger_revoked(),
            item={
                "item_id": "dispatch-retry-01",
                "lineage": ["record_vitals_1", "retry_payload_1"],
                "item_epoch": 3,
                "already_delivered": False,
                "stored_copy": True,
            },
            principal="subj-1",
            purpose="care_summary",
            time=REVOKED_AT,
        ),
        expected_semantic_outcome="DENY",
        revocation_model_reference=(
            "revocation_model.decide: DENY/DENY_POST_REVOCATION for every "
            "dispatch with time >= t_r in the revoked (principal, purpose) "
            "scope, boundary inclusive"
        ),
        case_matrix_ref="POPETS-CASE-02",
        description=(
            "Revocation before retry: old context cached, consent revoked, "
            "retry dispatch issued exactly at t_r."
        ),
    ),
    PrivacyCase(
        case_id="PC-REVOKE-02",
        scenario_class="post_revocation_dispatch",
        scenario=CaseScenario(
            ledger=_ledger_revoked(),
            item={
                "item_id": "dispatch-retry-02",
                "lineage": ["record_vitals_1", "fallback_transport_1"],
                "item_epoch": 3,
                "already_delivered": False,
                "stored_copy": True,
            },
            principal="subj-1",
            purpose="care_summary",
            time=REVOKED_AT + 5,
        ),
        expected_semantic_outcome="DENY",
        revocation_model_reference=(
            "revocation_model.decide: DENY/DENY_POST_REVOCATION on the fallback "
            "transport path; every post-t_r transport is gated identically"
        ),
        case_matrix_ref="POPETS-CASE-08",
        description=(
            "Out-of-causal-order retry on fallback transport with the old "
            "consent epoch after t_r: epoch must be revalidated per dispatch."
        ),
    ),
    # ---- class 3: cross-purpose cache reuse (purpose binding, CASE-05) ----
    PrivacyCase(
        case_id="PC-XPURP-01",
        scenario_class="cross_purpose",
        scenario=CaseScenario(
            ledger=_ledger_active(),
            item={
                "item_id": "dispatch-xpurpose-01",
                "lineage": ["record_meds_1", "summary_cache_1"],
                "item_epoch": 3,
                "already_delivered": False,
                "stored_copy": True,
            },
            principal="subj-1",
            purpose="medication_review",
            time=GRANTED_AT + 6,
        ),
        expected_semantic_outcome="DENY",
        revocation_model_reference=(
            "revocation_model._purpose_refusal: known-but-unconsented purpose is "
            "a determined DENY/PURPOSE_NOT_CONSENTED regardless of revocation "
            "state (purpose boundary G2)"
        ),
        case_matrix_ref="POPETS-CASE-05",
        description=(
            "Cross-purpose cache reuse: context built for care_summary is "
            "requested under medication_review, a purpose the grant does not "
            "consent (known in the ledger vocabulary, unconsented for subj-1)."
        ),
    ),
    # ---- class 4: transitive gap (lineage completeness, CASE-03/07) ----
    PrivacyCase(
        case_id="PC-TGAP-01",
        scenario_class="transitive_gap",
        scenario=CaseScenario(
            # Derived-summary-chain shape: the second-order node
            # ``summary_cache_2`` was written by a delayed cache write and
            # carries NO origin label in this scenario's grant table, so the
            # transitive closure cannot be adjudicated (fail closed).
            ledger={
                "grants": {
                    "subj-1": {
                        **_GRANT,
                        "lineage_labels": {
                            "record_vitals_1": "vitals",
                            "summary_cache_2": None,
                            "embedding_pointer_1": "vitals",
                        },
                    },
                    "subj-2": dict(_GRANT_OTHER),
                },
                "revocations": [
                    {"principal": "subj-1", "purpose": "care_summary", "revoked_at": REVOKED_AT}
                ],
            },
            item={
                "item_id": "dispatch-tgap-01",
                "lineage": ["record_vitals_1", "summary_cache_2", "embedding_pointer_1"],
                "item_epoch": 3,
                "already_delivered": False,
                "stored_copy": True,
            },
            principal="subj-1",
            purpose="care_summary",
            time=REVOKED_AT + 1,
        ),
        expected_semantic_outcome="INDETERMINATE",
        revocation_model_reference=(
            "revocation_model.decide: INDETERMINATE/LINEAGE_INDETERMINATE on a "
            "derived node with unverifiable ancestry inside the transitive "
            "closure; the closure question stays first-class, never coerced "
            "into a safe rejection or a completion"
        ),
        case_matrix_ref="POPETS-CASE-03",
        description=(
            "Derived summary chain field -> summary -> second summary dispatched "
            "after t_r: a second-order derived node lacks a verifiable origin "
            "label, so the closure cannot be adjudicated and fails closed."
        ),
    ),
    PrivacyCase(
        case_id="PC-TGAP-02",
        scenario_class="transitive_gap",
        scenario=CaseScenario(
            ledger=_ledger_active(),
            item={
                "item_id": "dispatch-tgap-02",
                "lineage": ["record_vitals_1", "orphan_derived_cache"],
                "item_epoch": 3,
                "already_delivered": False,
                "stored_copy": True,
            },
            principal="subj-1",
            purpose="care_summary",
            time=GRANTED_AT + 8,
        ),
        expected_semantic_outcome="INDETERMINATE",
        revocation_model_reference=(
            "revocation_model.decide: INDETERMINATE/LINEAGE_INDETERMINATE fail "
            "closed on a node without a verifiable origin label; never a "
            "silent safe rejection"
        ),
        case_matrix_ref="POPETS-CASE-07",
        description=(
            "Missing lineage edge: derived cache with unknown ancestry must "
            "fail closed and force fresh authorized reconstruction."
        ),
    ),
    # ---- class 5: already-delivered bytes + memorization (threat
    # precision, CASE-06) ----
    PrivacyCase(
        case_id="PC-DELIV-01",
        scenario_class="already_delivered",
        scenario=CaseScenario(
            ledger=_ledger_revoked(),
            item={
                "item_id": "dispatch-deliv-01",
                "lineage": ["record_vitals_1"],
                "item_epoch": 3,
                "already_delivered": True,
                "stored_copy": True,
            },
            principal="subj-1",
            purpose="care_summary",
            time=REVOKED_AT + 2,
        ),
        expected_semantic_outcome=OUT_OF_SCOPE,
        revocation_model_reference=(
            "revocation_model.decide: future verdict DENY/DENY_POST_REVOCATION "
            "for the post-t_r dispatch, while already_delivered_effect="
            "OUT_OF_SCOPE_PAST records that the pre-t_r delivered copy cannot "
            "be retracted; NO retroactive-erasure claim is admissible"
        ),
        case_matrix_ref="POPETS-CASE-06",
        description=(
            "Already-delivered copy: the provider received the bytes strictly "
            "before t_r; only preventable future disclosures are measurable."
        ),
    ),
    PrivacyCase(
        case_id="PC-DELIV-02",
        scenario_class="already_delivered",
        scenario=CaseScenario(
            ledger=_ledger_active(),
            item={
                "item_id": "dispatch-deliv-02",
                "lineage": ["record_vitals_1"],
                "item_epoch": 3,
                "already_delivered": True,
                "stored_copy": True,
            },
            principal="subj-1",
            purpose="care_summary",
            time=GRANTED_AT + 5,
        ),
        expected_semantic_outcome=NOT_GUARANTEED,
        revocation_model_reference=(
            "revocation_model.decide: verdict ALLOW/ALLOWED_ACTIVE_CONSENT for "
            "the authorized dispatch while memorization_guarantee="
            "NOT_GUARANTEED is surfaced as an honest, non-actionable "
            "limitation; it is never a DENY-as-erasure claim"
        ),
        case_matrix_ref="POPETS-CASE-06",
        description=(
            "Memorization uncertainty: anything a provider's model learned "
            "from already-delivered bytes is NOT guaranteed removable by any "
            "platform-side control."
        ),
    ),
)

#: Stable case ids, in frozen order.
PRIVACY_CASE_IDS: Final[tuple[str, ...]] = tuple(c.case_id for c in PRIVACY_CASES)

_CASE_BY_ID: Final[Mapping[str, PrivacyCase]] = {c.case_id: c for c in PRIVACY_CASES}


# ---------------------------------------------------------------------------
# Freeze discipline (mirrors pst.forensic_queries / _shared.analysis_policy)
# ---------------------------------------------------------------------------


def serialize_case_set(cases: Sequence[PrivacyCase] = PRIVACY_CASES) -> str:
    """Canonical JSON serialization of a case list (freeze hash input)."""

    return json.dumps([c.to_dict() for c in cases], sort_keys=True, separators=(",", ":"))


def cases_sha256(cases: Sequence[PrivacyCase] = PRIVACY_CASES) -> str:
    """Canonical SHA256 of a case list; the freeze constant is its digest."""

    return hashlib.sha256(serialize_case_set(cases).encode("utf-8")).hexdigest()


def frozen_case_set_sha256() -> str:
    """SHA256 of the shipped frozen set (must equal the freeze constant)."""

    return cases_sha256(PRIVACY_CASES)


#: ---------------------------------------------------------------------------
#: FREEZE LOCK. Computed once from the N=8 set above and committed; the test
#: suite recomputes it and refuses any drift (CASE_SET_DRIFT). Editing any
#: case, adding or removing one, or reordering the tuple changes this digest
#: and is a protocol violation visible in review.
#: ---------------------------------------------------------------------------
FROZEN_CASE_SET_SHA256: Final[str] = (
    "d48dfcb37af0d998b801101c34ec9a0f8710505e2cecf8a56b574168e3399d9b"
)


def assert_frozen_cases(cases: Sequence[PrivacyCase]) -> None:
    """Refuse a drifted case set (stable reason code ``CASE_SET_DRIFT``).

    The denominator actually used downstream must hash to the committed
    freeze constant. Any post-hoc addition, removal, rewording or reordering
    is refused, mirroring ``assert_frozen_analysis`` in the shared analysis
    policy and ``assert_frozen_query_set`` in the PST venue.
    """

    actual = cases_sha256(cases)
    if actual != FROZEN_CASE_SET_SHA256:
        raise PrivacyCaseError(
            REASON_CASE_SET_DRIFT,
            f"case set hash {actual} != frozen {FROZEN_CASE_SET_SHA256}",
        )


def case_by_id(case_id: str) -> PrivacyCase:
    """Lookup by frozen case id; unknown ids fail closed (``CASE_UNKNOWN``)."""

    case = _CASE_BY_ID.get(case_id)
    if case is None:
        raise PrivacyCaseError(REASON_CASE_UNKNOWN, f"no frozen case {case_id!r}")
    return case


def expected_semantic_outcomes() -> tuple[str, ...]:
    """The frozen expected-outcome column, in frozen case order."""

    return tuple(c.expected_semantic_outcome for c in PRIVACY_CASES)


# ---------------------------------------------------------------------------
# Internal consistency validation (fail closed at import)
# ---------------------------------------------------------------------------


def _assert_internal_consistency(cases: Sequence[PrivacyCase] = PRIVACY_CASES) -> None:
    seen: set[str] = set()
    for case in cases:
        if not case.case_id or case.case_id in seen:
            raise PrivacyCaseError(
                REASON_CASE_MALFORMED,
                f"duplicate or empty case_id {case.case_id!r}",
            )
        seen.add(case.case_id)
        if case.scenario_class not in SCENARIO_CLASSES:
            raise PrivacyCaseError(
                REASON_CASE_MALFORMED,
                f"{case.case_id}: unknown scenario_class {case.scenario_class!r}",
            )
        if case.expected_semantic_outcome not in EXPECTED_SEMANTIC_OUTCOMES:
            raise PrivacyCaseError(
                REASON_CASE_MALFORMED,
                f"{case.case_id}: unknown expected_semantic_outcome "
                f"{case.expected_semantic_outcome!r}",
            )
        if not case.revocation_model_reference.strip():
            raise PrivacyCaseError(
                REASON_CASE_MALFORMED,
                f"{case.case_id}: revocation_model_reference must be non-empty",
            )
        if not case.case_matrix_ref.startswith("POPETS-CASE-"):
            raise PrivacyCaseError(
                REASON_CASE_MALFORMED,
                f"{case.case_id}: bad case_matrix_ref {case.case_matrix_ref!r}",
            )
        scenario = case.scenario
        if not scenario.principal or not scenario.purpose:
            raise PrivacyCaseError(
                REASON_CASE_MALFORMED,
                f"{case.case_id}: principal/purpose must be non-empty",
            )
        if isinstance(scenario.time, bool) or not isinstance(scenario.time, int):
            raise PrivacyCaseError(
                REASON_CASE_MALFORMED,
                f"{case.case_id}: time must be an integer",
            )
        # The typed scenario must round-trip through the model's input
        # contracts; a scenario that cannot be parsed is malformed by
        # construction (fail closed at import, never at adjudication time).
        try:
            DispatchItem.from_mapping(scenario.item)
            ConsentLedgerView.from_mapping(scenario.ledger)
        except ValueError as exc:
            raise PrivacyCaseError(
                REASON_CASE_MALFORMED,
                f"{case.case_id}: scenario does not parse as model input: {exc}",
            ) from exc


_assert_internal_consistency()
