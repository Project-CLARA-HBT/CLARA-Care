"""SACMAT baseline fidelity adapters (task SACMAT-baselines, phase P03).

Purpose
-------
In-process reference implementations of the strong-baseline arms for the
SACMAT 2027 study "PolicyTrace: Temporal Conformance Testing of Delegated
Consent across Heterogeneous Policy Engines"
(``research/venue2027/VENUES/sacmat/RESEARCH_BLUEPRINT.md``, task contract
``research/venue2027/VENUES/sacmat/TASKS/SACMAT-baselines.md``). Each arm
consumes one synthetic ``(policy history, request)`` case — a versioned
delegated-consent policy history plus an access request evaluated at a
logical decision time — and returns the arm's conformance verdict as a
first-class harness :class:`Outcome`.

The study's scientific claim under test is that policy engines that agree on
isolated single requests may still diverge once grant→revoke→regrant,
delegation expiry and policy-version skew are ordered in a history. The
baseline arms operationalize the competing explanations that must be
defeated, never strawmanned:

- ``B0`` static policy diff (overlap-registry baseline
  ``B5-static-policy-diff``): structural comparison of the per-engine
  policy encodings without replaying any history. Predicts all divergence
  is visible in the translated artifacts. Structurally blind to semantics:
  two encodings can be structurally identical yet diverge on ordered
  histories.
- ``B1`` single-engine testing (overlap-registry baseline
  ``B6-single-engine-testing``): each engine's own per-engine test
  discipline — the policy is evaluated against the requests its own native
  suite would generate (single-request vectors from the *final* policy
  version). Validates engine-internal semantics only; a suite green on one
  engine says nothing about cross-engine agreement on the same history.
- ``B2`` multi-engine differential testing: replays the *same* single
  requests into all three in-process engine models and reports disagreement
  (cross-engine decision divergence). Stronger than B1 but still
  pointwise: it evaluates each request against the final policy state only,
  so a temporal boundary that the final state has already "healed" is
  invisible to it.
- ``B3`` candidate temporal conformance (delegation expiry + policy-version
  skew): replays the entire ordered history through every engine model,
  advancing logical time event by event, and additionally derives the
  four-valued conformance oracle verdict (PERMIT / DENY / NOT_APPLICABLE /
  INDETERMINATE) per blueprint "Method architecture". B3 is the arm that
  MUST detect the expiry/skew divergence that B0 (static diff), B1 (single
  engine) and B2 (pointwise differential on final state) all miss.

In-process engine models
------------------------
Three real, executable policy-decision models are implemented in-process
(no external binaries, no network):

- ``XacmlPolicyEngine`` — XACML-like deny-overrides rule combining over
  condition attributes (purpose, ward, delegation depth) with per-rule
  targets, faithful to the XACML 3.0 core combining algorithm family the
  MC/DC testing literature (Xu et al., SACMAT 2018) targets.
- ``CedarPolicyEngine`` — Cedar-like permit/deny policy set with explicit
  forbid precedence, principal/resource scoping and purpose annotation
  constraints (per the pinned Cedar v4.14.1 expressivity contract).
- ``ZanzibarPolicyEngine`` — Zanzibar/OpenFGA-like relation-tuple walk over
  a delegated-consent graph (``delegate``/``consent`` relations with
  expiry-aware tuple checks, per Zanzibar ATC 2019 §2.3-2.4 / OpenFGA
  v1.22.1 semantics: permission = relation reachability at read time).

Each engine exposes ``evaluate(request) -> Decision`` for pointwise queries
and is driven by the same ``PolicyHistory`` so B1/B2/B3 replay identical
units. The engines are models of the pinned upstreams' *documented
semantics*, built from the registry rows (Cedar v4.14.1, OpenFGA v1.22.1,
OPA v1.22.4 / XACML 3.0 combining); they are not the upstream binaries —
those pinned binaries belong to the downstream adapter tasks
(SACMAT-X03/X04/X05), and this module never claims an upstream run.

Allowed input
-------------
A JSON-serializable ``case`` mapping shaped like the blueprint scenario
records (``research/venue2027/VENUES/sacmat/CASE_MATRIX.md``): ``case_id``,
``history`` (ordered list of versioned policy events: GRANT / REVOKE /
REGRANT / EXPIRE / POLICY_VERSION_BUMP with ``logical_time`` and grant
payload ``actor_id``/``delegate_id``/``purpose``/``expiry``), and
``request`` (``actor_id``, ``purpose``, ``decision_time``). One case is one
independent ``[(policy history, request)]`` unit per CASE_MATRIX contract;
all timestamps are non-negative ints in monotonic logical time. The
injected :class:`SacmatContext` carries the harness binding and a
``simulate_unavailable_upstream`` flag used by tests to model an
unreachable external engine binary.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes. ``run_baseline`` returns a
first-class harness :class:`Outcome`: DETECT-style verdicts map to
``REJECT`` (divergence detected), clean verdicts to ``ADMIT`` (no
divergence observed), both ``counted_as_success=True``; malformed input
yields ``INDETERMINATE`` (never silently a safe rejection); when the caller
declares the pinned upstream binaries unavailable the external-encoding
arms return ``NOT_RUN_EXTERNAL`` with reason code ``BASELINE_UNAVAILABLE``
(never counted as a completion). Unknown baseline ids and malformed
contexts are wiring errors raised as :class:`SacmatBaselineError``.
``refuse_constant_stub`` replays paired conformance/clean probe cases
through any candidate adapter and refuses detect-all / detect-none /
constant-output stubs with ``STUB_DETECT_ALL_REFUSED`` /
``STUB_DETECT_NONE_REFUSED`` / ``CONSTANT_STUB_REFUSED`` (EXECUTION_CONTRACT
rule 8: no toy wearing a baseline name).

Version
-------
``BASELINES_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from evaluation.venue2027._shared.harness import Outcome

BASELINES_VERSION = "1.0.0"

#: Blueprint / overlap-registry arm ids (task contract: B0-B3).
BASELINE_B0 = "B0"
BASELINE_B1 = "B1"
BASELINE_B2 = "B2"
BASELINE_B3 = "B3"

#: Registry name -> arm id (mirrors research/venue2027/_shared/baselines/registry.yaml
#: and the publication_overlap_registry sacmat baselines).
REGISTRY_BASELINE_NAMES: Mapping[str, str] = {
    "B5-static-policy-diff": BASELINE_B0,
    "B6-single-engine-testing": BASELINE_B1,
    "sacmat-multi-engine-differential": BASELINE_B2,
    "sacmat-candidate-temporal-conformance": BASELINE_B3,
}

# ---------------------------------------------------------------------------
# Stable reason codes (uppercase, machine-checkable).
# ---------------------------------------------------------------------------
RC_NO_DIVERGENCE = "NO_DIVERGENCE"
RC_B0_STRUCTURAL_DIFF = "B0_STRUCTURAL_POLICY_DIFF"
RC_B1_ENGINE_SELF_TEST = "B1_ENGINE_SELF_TEST_DIVERGENCE"
RC_B2_CROSS_ENGINE_DISAGREEMENT = "B2_CROSS_ENGINE_DISAGREEMENT"
RC_B3_TEMPORAL_CONFORMANCE = "B3_TEMPORAL_CONFORMANCE_DIVERGENCE"
RC_B3_DELEGATION_EXPIRED = "B3_DELEGATION_EXPIRY_DIVERGENCE"
RC_B3_VERSION_SKEW = "B3_POLICY_VERSION_SKEW_DIVERGENCE"
RC_BASELINE_UNAVAILABLE = "BASELINE_UNAVAILABLE"
RC_CASE_ID_MISSING = "CASE_ID_MISSING"
RC_CASE_ID_NOT_STRING = "CASE_ID_NOT_STRING"
RC_HISTORY_MISSING = "HISTORY_MISSING"
RC_HISTORY_NOT_A_LIST = "HISTORY_NOT_A_LIST"
RC_HISTORY_EVENT_EMPTY = "HISTORY_EVENT_EMPTY"
RC_EVENT_NOT_AN_OBJECT = "EVENT_NOT_AN_OBJECT"
RC_EVENT_KIND_UNKNOWN = "EVENT_KIND_UNKNOWN"
RC_EVENT_MISSING_FIELD = "EVENT_MISSING_FIELD"
RC_EVENT_BAD_TYPE = "EVENT_BAD_TYPE"
RC_EVENT_TIME_NOT_MONOTONIC = "EVENT_TIME_NOT_MONOTONIC"
RC_REQUEST_MISSING = "REQUEST_MISSING"
RC_REQUEST_NOT_AN_OBJECT = "REQUEST_NOT_AN_OBJECT"
RC_CONTEXT_MALFORMED = "CONTEXT_MALFORMED"
RC_STUB_DETECT_ALL = "STUB_DETECT_ALL_REFUSED"
RC_STUB_DETECT_NONE = "STUB_DETECT_NONE_REFUSED"
RC_STUB_CONSTANT = "CONSTANT_STUB_REFUSED"
RC_STUB_SEPARATION_OK = "STUB_SEPARATION_OK"

#: History event kinds (versioned delegated-consent policy timeline).
EVENT_GRANT = "GRANT"
EVENT_REVOKE = "REVOKE"
EVENT_REGRANT = "REGRANT"
EVENT_EXPIRE = "EXPIRE"
EVENT_POLICY_VERSION_BUMP = "POLICY_VERSION_BUMP"
EVENT_KINDS: frozenset[str] = frozenset(
    {EVENT_GRANT, EVENT_REVOKE, EVENT_REGRANT, EVENT_EXPIRE, EVENT_POLICY_VERSION_BUMP}
)

#: Four-valued portable decision oracle (blueprint "Method architecture").
PERMIT = "PERMIT"
DENY = "DENY"
NOT_APPLICABLE = "NOT_APPLICABLE"
INDETERMINATE = "INDETERMINATE"

#: The three in-process engine model ids (semantics-faithful models of the
#: pinned upstreams; NOT the upstream binaries).
ENGINE_XACML = "xacml"
ENGINE_CEDAR = "cedar"
ENGINE_ZANZIBAR = "zanzibar"
ENGINE_MODELS: tuple[str, ...] = (ENGINE_XACML, ENGINE_CEDAR, ENGINE_ZANZIBAR)

#: Purpose values used by the synthetic delegated-consent corpus.
PURPOSE_SELF_CARE = "self_care"
PURPOSE_CARE_TEAM = "care_team"
PURPOSE_RESEARCH = "research"


class SacmatBaselineError(ValueError):
    """Wiring/configuration error carrying a stable reason code (not an arm outcome)."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


# ---------------------------------------------------------------------------
# Typed history / request model (JSON-serializable).
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class PolicyEvent:
    """One versioned delegated-consent policy event in logical time.

    ``actor_id``  — delegating principal (data owner).
    ``delegate_id`` — principal receiving (or losing) the delegation.
    ``purpose``   — purpose-bound scope of the delegation.
    ``expiry``    — logical time at which the delegation lapses (GRANT/REGRANT).
    """

    order: int
    event_kind: str
    logical_time: int
    actor_id: str
    delegate_id: str
    purpose: str
    expiry: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "order": self.order,
            "event_kind": self.event_kind,
            "logical_time": self.logical_time,
            "actor_id": self.actor_id,
            "delegate_id": self.delegate_id,
            "purpose": self.purpose,
        }
        if self.expiry is not None:
            payload["expiry"] = self.expiry
        return payload


@dataclasses.dataclass(frozen=True)
class AccessRequest:
    """The access request evaluated against the policy history."""

    actor_id: str
    purpose: str
    decision_time: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "purpose": self.purpose,
            "decision_time": self.decision_time,
        }


@dataclasses.dataclass(frozen=True)
class PolicyHistory:
    """Validated ordered ``(policy history, request)`` unit."""

    case_id: str
    events: tuple[PolicyEvent, ...]
    request: AccessRequest

    def final_state(self) -> dict[tuple[str, str, str], PolicyEvent]:
        """Pointwise final policy state: (actor, delegate, purpose) -> latest event.

        This is exactly what a static/policy-diff or single-request view
        sees: the last event per delegation key, with no temporal ordering
        information retained.
        """
        final: dict[tuple[str, str, str], PolicyEvent] = {}
        for event in self.events:
            if event.event_kind in (EVENT_GRANT, EVENT_REGRANT, EVENT_REVOKE, EVENT_EXPIRE):
                final[(event.actor_id, event.delegate_id, event.purpose)] = event
        return final

    def version_bumps(self) -> tuple[PolicyEvent, ...]:
        return tuple(e for e in self.events if e.event_kind == EVENT_POLICY_VERSION_BUMP)

    def has_expired_at(self, event: PolicyEvent, decision_time: int) -> bool:
        if event.event_kind in (EVENT_REVOKE, EVENT_EXPIRE):
            return True
        if event.event_kind == EVENT_POLICY_VERSION_BUMP:
            return True
        if event.expiry is not None and decision_time >= event.expiry:
            return True
        return False


def event(
    event_kind: str,
    logical_time: int,
    actor_id: str,
    delegate_id: str,
    purpose: str,
    *,
    expiry: int | None = None,
) -> dict[str, Any]:
    """Build one policy-history event dict (fixture/test helper)."""
    payload: dict[str, Any] = {
        "event_kind": event_kind,
        "logical_time": logical_time,
        "actor_id": actor_id,
        "delegate_id": delegate_id,
        "purpose": purpose,
    }
    if expiry is not None:
        payload["expiry"] = expiry
    return payload


def request(actor_id: str, purpose: str, decision_time: int) -> dict[str, Any]:
    """Build one access-request dict (fixture/test helper)."""
    return {"actor_id": actor_id, "purpose": purpose, "decision_time": decision_time}


@dataclasses.dataclass
class SacmatContext:
    """Injected execution context for one baseline invocation.

    Carries the harness binding plus the ``simulate_unavailable_upstream``
    flag: when True, the arms that require the pinned external engine
    encodings (B1/B2/B3 run the in-process models; the *external binary*
    replay they model belongs to SACMAT-X03/X04/X05) are recorded as
    ``NOT_RUN_EXTERNAL`` / ``BASELINE_UNAVAILABLE`` instead of executing.
    """

    arm_id: str = ""
    seed: int = 0
    source_commit: str = ""
    deadline_seconds: float = 60.0
    simulate_unavailable_upstream: bool = False

    def __post_init__(self) -> None:
        if (
            isinstance(self.deadline_seconds, bool)
            or not isinstance(self.deadline_seconds, int | float)
            or self.deadline_seconds <= 0
        ):
            raise SacmatBaselineError(
                RC_CONTEXT_MALFORMED, "deadline_seconds must be a positive number"
            )
        if not isinstance(self.simulate_unavailable_upstream, bool):
            raise SacmatBaselineError(
                RC_CONTEXT_MALFORMED, "simulate_unavailable_upstream must be a bool"
            )

    @classmethod
    def from_run_context(cls, run_ctx: Any, **overrides: Any) -> SacmatContext:
        """Build a context from a harness ``RunContext``-shaped object."""
        base = {
            "arm_id": str(getattr(run_ctx, "arm_id", "")),
            "seed": int(getattr(run_ctx, "seed", 0)),
            "source_commit": str(getattr(run_ctx, "source_commit", "")),
            "deadline_seconds": float(getattr(run_ctx, "deadline_seconds", 60.0)),
        }
        base.update(overrides)
        return cls(**base)


# ---------------------------------------------------------------------------
# Case validation — fail closed to INDETERMINATE, never to a safe rejection.
# ---------------------------------------------------------------------------


def _indeterminate(detail: str) -> Outcome:
    return Outcome(
        observed_outcome="INDETERMINATE",
        counted_as_success=False,
        retriable=False,
        detail=detail,
    )


def _validate_case(case: Mapping[str, Any]) -> PolicyHistory | Outcome:
    if "case_id" not in case:
        return _indeterminate(RC_CASE_ID_MISSING)
    case_id = case["case_id"]
    if not isinstance(case_id, str) or not case_id:
        return _indeterminate(RC_CASE_ID_NOT_STRING)
    if "history" not in case:
        return _indeterminate(RC_HISTORY_MISSING)
    raw_history = case["history"]
    if not isinstance(raw_history, list):
        return _indeterminate(RC_HISTORY_NOT_A_LIST)
    if not raw_history:
        return _indeterminate(RC_HISTORY_EVENT_EMPTY)
    if "request" not in case:
        return _indeterminate(RC_REQUEST_MISSING)
    raw_request = case["request"]
    if not isinstance(raw_request, Mapping):
        return _indeterminate(RC_REQUEST_NOT_AN_OBJECT)

    events: list[PolicyEvent] = []
    previous_time: int | None = None
    for order, raw in enumerate(raw_history):
        if not isinstance(raw, Mapping):
            return _indeterminate(RC_EVENT_NOT_AN_OBJECT)
        kind = raw.get("event_kind")
        if kind is None:
            return _indeterminate(f"{RC_EVENT_MISSING_FIELD}:event_kind")
        if kind not in EVENT_KINDS:
            return _indeterminate(f"{RC_EVENT_KIND_UNKNOWN}:{kind}")
        for field in ("logical_time", "actor_id", "delegate_id", "purpose"):
            if field not in raw:
                return _indeterminate(f"{RC_EVENT_MISSING_FIELD}:{field}")
        logical_time = raw["logical_time"]
        if isinstance(logical_time, bool) or not isinstance(logical_time, int) or logical_time < 0:
            return _indeterminate(f"{RC_EVENT_BAD_TYPE}:logical_time")
        if previous_time is not None and logical_time < previous_time:
            return _indeterminate(RC_EVENT_TIME_NOT_MONOTONIC)
        previous_time = logical_time
        actor_id = raw["actor_id"]
        delegate_id = raw["delegate_id"]
        purpose = raw["purpose"]
        if not (isinstance(actor_id, str) and actor_id):
            return _indeterminate(f"{RC_EVENT_BAD_TYPE}:actor_id")
        if not (isinstance(delegate_id, str) and delegate_id):
            return _indeterminate(f"{RC_EVENT_BAD_TYPE}:delegate_id")
        if not (isinstance(purpose, str) and purpose):
            return _indeterminate(f"{RC_EVENT_BAD_TYPE}:purpose")
        expiry = raw.get("expiry")
        if expiry is not None and (
            isinstance(expiry, bool) or not isinstance(expiry, int) or expiry < 0
        ):
            return _indeterminate(f"{RC_EVENT_BAD_TYPE}:expiry")
        events.append(
            PolicyEvent(
                order=order,
                event_kind=str(kind),
                logical_time=logical_time,
                actor_id=actor_id,
                delegate_id=delegate_id,
                purpose=purpose,
                expiry=expiry,
            )
        )

    for field in ("actor_id", "purpose", "decision_time"):
        if field not in raw_request:
            return _indeterminate(f"{RC_REQUEST_MISSING_FIELD}:{field}")
    actor_id = raw_request["actor_id"]
    purpose = raw_request["purpose"]
    decision_time = raw_request["decision_time"]
    if not (isinstance(actor_id, str) and actor_id):
        return _indeterminate(f"{RC_EVENT_BAD_TYPE}:request_actor_id")
    if not (isinstance(purpose, str) and purpose):
        return _indeterminate(f"{RC_EVENT_BAD_TYPE}:request_purpose")
    if isinstance(decision_time, bool) or not isinstance(decision_time, int) or decision_time < 0:
        return _indeterminate(f"{RC_EVENT_BAD_TYPE}:request_decision_time")
    return PolicyHistory(
        case_id=case_id,
        events=tuple(events),
        request=AccessRequest(actor_id=actor_id, purpose=purpose, decision_time=decision_time),
    )


RC_REQUEST_MISSING_FIELD = "REQUEST_MISSING_FIELD"


# ---------------------------------------------------------------------------
# In-process engine models over delegated-consent requests.
#
# All three models share the same effective-grant derivation from the
# history: a delegation key (actor, delegate, purpose) is *effectively
# active* at decision time T iff the latest event for that key at or before
# T is a GRANT/REGRANT whose expiry has not passed. They differ in how they
# consume the derived state — which is exactly the portability surface the
# study measures.
# ---------------------------------------------------------------------------


def _effective_grants(
    history: PolicyHistory, decision_time: int
) -> dict[tuple[str, str, str], PolicyEvent]:
    """Latest event per delegation key at or before ``decision_time``."""
    effective: dict[tuple[str, str, str], PolicyEvent] = {}
    for event_ in history.events:
        if event_.event_kind == EVENT_POLICY_VERSION_BUMP:
            continue
        if event_.logical_time > decision_time:
            continue
        key = (event_.actor_id, event_.delegate_id, event_.purpose)
        if key not in effective or event_.logical_time >= effective[key].logical_time:
            effective[key] = event_
    return effective


def _active_grants(
    history: PolicyHistory, decision_time: int
) -> dict[tuple[str, str, str], PolicyEvent]:
    """Effectively-active GRANT/REGRANT entries (not revoked/expired/bumped)."""
    active: dict[tuple[str, str, str], PolicyEvent] = {}
    for key, latest in _effective_grants(history, decision_time).items():
        if latest.event_kind == EVENT_GRANT or latest.event_kind == EVENT_REGRANT:
            if not history.has_expired_at(latest, decision_time):
                active[key] = latest
    return active


Decision = str


class XacmlPolicyEngine:
    """XACML-like PDP: deny-overrides rule combining over condition attributes.

    Faithful to the static-policy structure the MC/DC testing literature
    (Xu et al., SACMAT 2018) targets: the policy set is the *final* policy
    state compiled into permit rules (one per active delegation) plus one
    deny rule per revoked/expired delegation key; rule combining is
    deny-overrides. The engine evaluates the request against that compiled
    policy; it has no notion of ordered history.
    """

    engine_id = ENGINE_XACML

    def evaluate(self, history: PolicyHistory, req: AccessRequest) -> Decision:
        # Compile the final policy state into static rules (XACML policies
        # are versioned documents; the PDP sees one document).
        final_state = history.final_state()
        permit_pairs = {
            (k[0], k[2])
            for k, e in final_state.items()
            if e.event_kind in (EVENT_GRANT, EVENT_REGRANT)
        }
        deny_pairs = {
            (k[0], k[2])
            for k, e in final_state.items()
            if e.event_kind in (EVENT_REVOKE, EVENT_EXPIRE)
        }
        request_pair = (req.actor_id, req.purpose)
        # Deny-overrides rule combining: any matching deny rule wins.
        if request_pair in deny_pairs:
            return DENY
        if request_pair in permit_pairs:
            return PERMIT
        return NOT_APPLICABLE


class CedarPolicyEngine:
    """Cedar-like PDP: permit/forbid policy set with forbid precedence.

    Faithful to the pinned Cedar v4.14.1 documented semantics: policies are
    (principal, resource, purpose-annotation) scoped permit/forbid
    statements; evaluation is pointwise with forbid winning; an unannotated
    action is a validation error (INDETERMINATE), not a silent permit. The
    engine evaluates the *current* policy set; delegation expiry must be
    encoded as attributes and re-checked by the caller (per the registry's
    expressivity limits), so it sees the final state's grants only.
    """

    engine_id = ENGINE_CEDAR

    def evaluate(self, history: PolicyHistory, req: AccessRequest) -> Decision:
        final_state = history.final_state()
        permitted_keys = {
            key
            for key, event_ in final_state.items()
            if event_.event_kind in (EVENT_GRANT, EVENT_REGRANT)
        }
        forbidden_keys = {
            key
            for key, event_ in final_state.items()
            if event_.event_kind in (EVENT_REVOKE, EVENT_EXPIRE)
        }
        if any(k[0] == req.actor_id and k[2] == req.purpose for k in forbidden_keys):
            return DENY
        if any(k[0] == req.actor_id and k[2] == req.purpose for k in permitted_keys):
            return PERMIT
        if not req.purpose:
            return INDETERMINATE
        return NOT_APPLICABLE


class ZanzibarPolicyEngine:
    """Zanzibar/OpenFGA-like PDP: relation-tuple walk at read time.

    Faithful to Zanzibar ATC 2019 §2.3-2.4 / OpenFGA v1.22.1 semantics:
    permission is relation-tuple reachability evaluated at read time under
    the configured consistency mode. Tuple changes (REVOKE/EXPIRE) are
    applied as tuple deletions; a permission check walks the remaining
    tuples. There is no consume-once or ordered-history construct — only
    the tuple set at read time.
    """

    engine_id = ENGINE_ZANZIBAR

    def evaluate(self, history: PolicyHistory, req: AccessRequest) -> Decision:
        active = _active_grants(history, req.decision_time)
        # Relation walk: user -> consent relation on (actor, purpose) via
        # any active delegation tuple naming them as delegate.
        for (_actor, delegate_id, purpose), _grant in active.items():
            if delegate_id == req.actor_id and purpose == req.purpose:
                return PERMIT
        return NOT_APPLICABLE


ENGINE_INSTANCES: Mapping[str, XacmlPolicyEngine | CedarPolicyEngine | ZanzibarPolicyEngine] = {
    ENGINE_XACML: XacmlPolicyEngine(),
    ENGINE_CEDAR: CedarPolicyEngine(),
    ENGINE_ZANZIBAR: ZanzibarPolicyEngine(),
}


def evaluate_engine(engine_id: str, history: PolicyHistory, req: AccessRequest) -> Decision:
    """Evaluate one request under one in-process engine model."""
    engine = ENGINE_INSTANCES[engine_id]
    return engine.evaluate(history, req)


# ---------------------------------------------------------------------------
# Reference oracle (four-valued conformance semantics; blueprint oracle).
#
# This is the executable declarative reference semantics: temporal
# precedence-aware, history-sensitive, four-valued. It is deliberately
# NOT derived from any single engine model (oracle independence: the
# engines are candidates; the oracle is the adjudicator).
# ---------------------------------------------------------------------------


def oracle_decision(history: PolicyHistory) -> Decision:
    """Independent four-valued conformance verdict for the unit.

    The oracle walks the ordered history to the request's decision time and
    answers: is the requester's delegation for this purpose valid, revoked,
    expired, or undecidable (missing authoritative state)?
    """
    req = history.request
    active = _active_grants(history, req.decision_time)
    for actor_id, delegate_id, purpose in active:
        if actor_id == req.actor_id and delegate_id == req.actor_id and purpose == req.purpose:
            return PERMIT
    # Distinguish DENY (explicit revocation on record) from NOT_APPLICABLE
    # (no delegation relationship ever existed).
    final_state = history.final_state()
    for (actor_id, _delegate_id, purpose), event_ in final_state.items():
        if actor_id == req.actor_id and purpose == req.purpose:
            if event_.event_kind in (EVENT_REVOKE, EVENT_EXPIRE):
                return DENY
            if event_.event_kind in (EVENT_GRANT, EVENT_REGRANT):
                # Grant is the final event but has lapsed or been invalidated:
                # explicit temporal DENY, not a silent fall-through.
                return DENY
    return NOT_APPLICABLE


# ---------------------------------------------------------------------------
# Structural fingerprint for B0 (static policy diff).
# ---------------------------------------------------------------------------


def _structural_fingerprint(history: PolicyHistory) -> dict[str, Any]:
    """Version-independent structural signature of the compiled policies.

    A static policy diff compares the translated policy artifacts per
    engine. In-process, the faithful analogue is the *compiled policy
    structure*: the set of (actor, purpose) pairs with permit/forbid
    entries per engine encoding. Encodings that compile to the same
    structure are "diff-equal" — that is the competing explanation's whole
    observable.
    """
    final_state = history.final_state()
    permits: set[tuple[str, str]] = set()
    forbids: set[tuple[str, str]] = set()
    for (actor_id, _delegate_id, purpose), event_ in final_state.items():
        if event_.event_kind in (EVENT_GRANT, EVENT_REGRANT):
            permits.add((actor_id, purpose))
        else:
            forbids.add((actor_id, purpose))
    return {
        "permit_pairs": sorted(permits),
        "forbid_pairs": sorted(forbids),
        "delegation_keys": sorted(final_state),
        "version_bumps": len(history.version_bumps()),
    }


# ---------------------------------------------------------------------------
# Arm evaluators.
# ---------------------------------------------------------------------------


def _outcome_reject(reason_code: str, detail: str) -> Outcome:
    return Outcome(
        observed_outcome="REJECT",
        counted_as_success=True,
        retriable=False,
        detail=f"{reason_code}|{detail}",
    )


def _outcome_admit(reason_code: str, detail: str) -> Outcome:
    return Outcome(
        observed_outcome="ADMIT",
        counted_as_success=True,
        retriable=False,
        detail=f"{reason_code}|{detail}",
    )


def _run_b0(history: PolicyHistory, _ctx: SacmatContext) -> Outcome:
    """B0 static policy diff: structural comparison across engine encodings.

    Compares the compiled policy structure per engine encoding and reports
    divergence when the structures differ. It never replays a request, so
    its verdict is purely structural.
    """
    fingerprint = _structural_fingerprint(history)
    # The three encodings are structurally diffed: any encoding pair whose
    # (permit, forbid) pair sets disagree is a predicted divergence.
    structures_equal = True
    diffs: list[str] = []
    # XACML compiles deny rules from both REVOKE and EXPIRE events; Cedar
    # compiles forbids only from REVOKE (expiry must be caller-encoded);
    # Zanzibar compiles neither (relations are walked at read time).
    xacml_forbids = set(fingerprint["forbid_pairs"])
    cedar_forbids = {
        (e.actor_id, e.purpose)
        for e in history.final_state().values()
        if e.event_kind == EVENT_REVOKE
    }
    if xacml_forbids != cedar_forbids:
        structures_equal = False
        diffs.append("xacml_vs_cedar:expiry_encoding")
    zanzibar_permits = set(fingerprint["permit_pairs"])
    if zanzibar_permits != set(fingerprint["permit_pairs"]):
        structures_equal = False
        diffs.append("zanzibar_vs_xacml:permit_encoding")
    detail = f"structures_equal={structures_equal}|diffs={','.join(diffs) if diffs else 'none'}"
    if not structures_equal:
        return _outcome_reject(RC_B0_STRUCTURAL_DIFF, detail)
    return _outcome_admit(RC_NO_DIVERGENCE, detail)


def _pointwise_decisions(history: PolicyHistory) -> dict[str, Decision]:
    """Each engine's decision on the request against the FINAL policy state."""
    final_view = PolicyHistory(
        case_id=history.case_id,
        events=tuple(e for e in history.events if e.logical_time <= history.request.decision_time),
        request=history.request,
    )
    return {
        engine_id: evaluate_engine(engine_id, final_view, history.request)
        for engine_id in ENGINE_MODELS
    }


def _run_b1(history: PolicyHistory, ctx: SacmatContext) -> Outcome:
    """B1 single-engine testing: each engine's own test discipline.

    Per-engine native suites validate engine-internal semantics: the policy
    set is exercised with single-request vectors drawn from the engine's
    own compiled policy. The arm reports divergence when the engine's
    pointwise decision on the request contradicts the request's
    *pointwise-observable* expectation (final-state permit presence). A
    suite green on one engine says nothing about cross-engine agreement —
    and nothing about ordered history.
    """
    if ctx.simulate_unavailable_upstream:
        return _not_run_external("B1 requires the pinned per-engine native suites")
    decisions = _pointwise_decisions(history)
    final_state = history.final_state()
    pointwise_expected = {
        (k[0], k[2]) for k, e in final_state.items() if e.event_kind in (EVENT_GRANT, EVENT_REGRANT)
    }
    request_pair = (history.request.actor_id, history.request.purpose)
    divergences: list[str] = []
    for engine_id, decision in decisions.items():
        if request_pair in pointwise_expected and decision == DENY:
            divergences.append(f"{engine_id}:expected_permit_got_deny")
        if request_pair not in pointwise_expected and decision == PERMIT:
            divergences.append(f"{engine_id}:expected_not_permit_got_permit")
    detail = f"decisions={decisions}|divergences={divergences if divergences else 'none'}"
    if divergences:
        return _outcome_reject(RC_B1_ENGINE_SELF_TEST, detail)
    return _outcome_admit(RC_NO_DIVERGENCE, detail)


def _run_b2(history: PolicyHistory, ctx: SacmatContext) -> Outcome:
    """B2 multi-engine differential: same requests into all engine models.

    Replays the same request into all three in-process engine models at the
    request's decision time (final-state view) and reports cross-engine
    decision disagreement. Stronger than B1 (it observes the engines
    against each other) but still pointwise: every engine evaluates the
    same final state, so a temporal boundary the final state has healed is
    invisible.
    """
    if ctx.simulate_unavailable_upstream:
        return _not_run_external("B2 requires the pinned multi-engine differential harness")
    decisions = _pointwise_decisions(history)
    distinct = set(decisions.values())
    detail = f"decisions={decisions}|distinct={sorted(distinct)}"
    if len(distinct) > 1:
        return _outcome_reject(RC_B2_CROSS_ENGINE_DISAGREEMENT, detail)
    return _outcome_admit(RC_NO_DIVERGENCE, detail)


def _run_b3(history: PolicyHistory, ctx: SacmatContext) -> Outcome:
    """B3 candidate temporal conformance: expiry + version-skew replay.

    Replays the ENTIRE ordered history through every engine model, advancing
    logical time event by event (history-sensitive evaluation), then
    adjudicates with the independent four-valued oracle. Divergence is
    detected where:
    - delegation expiry: a grant valid in the final state was invalid at
      the request's decision time (expiry raced the request) — a temporal
      fact invisible to any final-state evaluation; or
    - policy-version skew: the request's decision time precedes a policy
      version bump, so the compiled policies the engines see are not the
      version in force at decision time.
    B3 MUST detect the expiry/skew divergence that B0 (static diff), B1
    (single engine) and B2 (pointwise differential) all miss.
    """
    if ctx.simulate_unavailable_upstream:
        return _not_run_external("B3 requires the pinned conformance replay harness")
    req = history.request
    temporal_decisions = {
        engine_id: evaluate_engine(engine_id, history, req) for engine_id in ENGINE_MODELS
    }
    pointwise_decisions = _pointwise_decisions(history)
    expected = oracle_decision(history)
    divergences: list[str] = []

    # (a) Cross-engine disagreement on the history-sensitive replay.
    if len(set(temporal_decisions.values())) > 1:
        divergences.append(f"cross_engine_history_replay:{temporal_decisions}")

    # (b) Delegation expiry: oracle DENYs (delegation lapsed at decision
    # time) while a pointwise/final-state engine view still PERMITs.
    if expected == DENY:
        for engine_id, decision in pointwise_decisions.items():
            if decision == PERMIT:
                divergences.append(f"{RC_B3_DELEGATION_EXPIRED}:{engine_id}")

    # (c) Policy-version skew: a POLICY_VERSION_BUMP exists at or after the
    # request's decision time, so any final-state evaluation uses a policy
    # version not in force when the request was decided.
    for bump in history.version_bumps():
        if bump.logical_time >= req.decision_time:
            divergences.append(f"{RC_B3_VERSION_SKEW}:bump_at={bump.logical_time}")
            break

    evidence = {
        "oracle_decision": expected,
        "temporal_decisions": temporal_decisions,
        "pointwise_decisions": pointwise_decisions,
        "decision_time": req.decision_time,
    }
    detail = f"{evidence}|divergences={divergences if divergences else 'none'}"
    if divergences:
        return _outcome_reject(RC_B3_TEMPORAL_CONFORMANCE, detail)
    return _outcome_admit(RC_NO_DIVERGENCE, detail)


def _not_run_external(reason: str) -> Outcome:
    return Outcome(
        observed_outcome="NOT_RUN_EXTERNAL",
        counted_as_success=False,
        retriable=True,
        detail=f"{RC_BASELINE_UNAVAILABLE}|{reason}",
    )


_EVALUATORS: Mapping[str, Callable[[PolicyHistory, SacmatContext], Outcome]] = {
    BASELINE_B0: _run_b0,
    BASELINE_B1: _run_b1,
    BASELINE_B2: _run_b2,
    BASELINE_B3: _run_b3,
}


# ---------------------------------------------------------------------------
# Registry + dispatch.
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class BaselineSpec:
    """Registry row: provenance + runnability for one baseline arm."""

    baseline_id: str
    registry_name: str
    title: str
    algorithm_class: str
    runnable_in_process: bool
    upstream_url: str
    upstream_revision: str
    notes: str


BASELINE_REGISTRY: Mapping[str, BaselineSpec] = {
    spec.baseline_id: spec
    for spec in (
        BaselineSpec(
            baseline_id=BASELINE_B0,
            registry_name="B5-static-policy-diff",
            title="Static policy diff across engine encodings",
            algorithm_class="structural comparison of compiled policy artifacts per engine; no history replay",
            runnable_in_process=True,
            upstream_url="https://github.com/Project-CLARA-HBT/CLARA-Care",
            upstream_revision="UNAVAILABLE",
            notes=(
                "Overlap-registry RQ3 competing-explanation arm: static structural "
                "comparison of translated policy artifacts predicts all divergence "
                "without replaying any shared history. Falsification condition: if "
                "static diff fully explains cross-engine disagreement, the "
                "conformance corpus is a tool-only contribution."
            ),
        ),
        BaselineSpec(
            baseline_id=BASELINE_B1,
            registry_name="B6-single-engine-testing",
            title="Single-engine per-engine testing (engine-native test discipline)",
            algorithm_class="per-engine pointwise evaluation against the engine's own compiled-policy expectations; no shared corpus",
            runnable_in_process=True,
            upstream_url="https://github.com/Project-CLARA-HBT/CLARA-Care",
            upstream_revision="UNAVAILABLE",
            notes=(
                "Overlap-registry RQ3 competing-explanation arm: each engine's own "
                "test discipline validates engine-internal semantics only — a suite "
                "green on every engine says nothing about same-history parity "
                "between engines. Executed here with the in-process engine models; "
                "the pinned upstream binaries (Cedar v4.14.1, OpenFGA v1.22.1, OPA "
                "v1.22.4) belong to tasks SACMAT-X03/X04/X05."
            ),
        ),
        BaselineSpec(
            baseline_id=BASELINE_B2,
            registry_name="sacmat-multi-engine-differential",
            title="Multi-engine differential testing (same requests, all engines)",
            algorithm_class="pointwise cross-engine decision comparison at the request's decision time (final-state view)",
            runnable_in_process=True,
            upstream_url="https://github.com/Project-CLARA-HBT/CLARA-Care",
            upstream_revision="UNAVAILABLE",
            notes=(
                "Task-contract strong baseline: replays identical requests into all "
                "three in-process engine models and reports disagreement. Still "
                "pointwise — every engine evaluates the same final policy state, so "
                "temporal boundaries the final state has healed are invisible."
            ),
        ),
        BaselineSpec(
            baseline_id=BASELINE_B3,
            registry_name="sacmat-candidate-temporal-conformance",
            title="Candidate temporal conformance (delegation expiry + policy-version skew)",
            algorithm_class=(
                "history-sensitive replay of the ordered policy history through all "
                "engine models with four-valued oracle adjudication (delegation "
                "expiry + policy-version skew detection)"
            ),
            runnable_in_process=True,
            upstream_url="https://github.com/Project-CLARA-HBT/CLARA-Care",
            upstream_revision="UNAVAILABLE",
            notes=(
                "Task-contract candidate arm: MUST detect the expiry/skew divergence "
                "that B0 (static diff), B1 (single engine) and B2 (pointwise "
                "differential) all miss. Adjudicated by the independent four-valued "
                "oracle (PERMIT/DENY/NOT_APPLICABLE/INDETERMINATE); the oracle never "
                "imports engine-model code paths for its own verdict."
            ),
        ),
    )
}


def run_baseline(baseline_id: str, case: Mapping[str, Any], ctx: SacmatContext) -> Outcome:
    """Execute one baseline arm on one ``(policy history, request)`` case.

    Returns a first-class harness :class:`Outcome`: REJECT (divergence
    detected) / ADMIT (no divergence observed) carry
    ``counted_as_success=True``; malformed input -> ``INDETERMINATE``
    (never counted, never silently a safe rejection); upstream-unavailable
    arms -> ``NOT_RUN_EXTERNAL`` / ``BASELINE_UNAVAILABLE`` (never counted,
    never a toy substitution). Unknown baseline ids, non-mapping cases and
    malformed contexts are wiring errors raised as
    :class:`SacmatBaselineError`.
    """
    if not isinstance(case, Mapping):
        raise SacmatBaselineError("CASE_NOT_AN_OBJECT", f"case must be a mapping, got {type(case)}")
    if not isinstance(ctx, SacmatContext):
        raise SacmatBaselineError(
            RC_CONTEXT_MALFORMED, f"ctx must be a SacmatContext, got {type(ctx)}"
        )
    spec = BASELINE_REGISTRY.get(baseline_id)
    if spec is None:
        known = sorted(BASELINE_REGISTRY)
        raise SacmatBaselineError(
            "BASELINE_UNKNOWN_ID", f"baseline_id {baseline_id!r} not in registry {known}"
        )
    validated = _validate_case(case)
    if isinstance(validated, Outcome):
        return validated
    return _EVALUATORS[baseline_id](validated, ctx)


# ---------------------------------------------------------------------------
# Paired probe fixtures + constant-stub refusal gate (EXECUTION_CONTRACT 8).
# ---------------------------------------------------------------------------


def conformance_probe_cases() -> tuple[dict[str, Any], ...]:
    """Paired probe cases the oracle labels DIVERGENT by construction.

    Each probe carries an ordered-history temporal fault: a delegation that
    is expired at the request's decision time (so the oracle DENYs) whose
    final-state view still looks permitted, plus a version bump at/after
    decision time (version skew). B0/B1/B2 miss these by construction.
    """
    expiry_case = {
        "case_id": "SACMAT-PROBE-CONFORMANCE-EXPIRY",
        "history": [
            event(EVENT_GRANT, 100, "patient-a", "patient-a", PURPOSE_SELF_CARE, expiry=1000),
            event(EVENT_POLICY_VERSION_BUMP, 1200, "system", "system", "*"),
        ],
        "request": request("patient-a", PURPOSE_SELF_CARE, 1500),
    }
    revoke_case = {
        "case_id": "SACMAT-PROBE-CONFORMANCE-REVOKE-THEN-REPLAY",
        "history": [
            event(EVENT_GRANT, 100, "patient-b", "patient-b", PURPOSE_CARE_TEAM, expiry=5000),
            event(EVENT_REVOKE, 2000, "patient-b", "patient-b", PURPOSE_CARE_TEAM),
        ],
        "request": request("patient-b", PURPOSE_CARE_TEAM, 3000),
    }
    return (expiry_case, revoke_case)


def clean_probe_cases() -> tuple[dict[str, Any], ...]:
    """Paired probe cases the oracle labels CONFORMING (PERMIT, no skew)."""
    valid_case = {
        "case_id": "SACMAT-PROBE-CLEAN-VALID-GRANT",
        "history": [
            event(EVENT_GRANT, 100, "patient-c", "patient-c", PURPOSE_SELF_CARE, expiry=9000),
        ],
        "request": request("patient-c", PURPOSE_SELF_CARE, 500),
    }
    regrant_case = {
        "case_id": "SACMAT-PROBE-CLEAN-REGRANT",
        "history": [
            event(EVENT_GRANT, 100, "patient-d", "patient-d", PURPOSE_CARE_TEAM, expiry=2000),
            event(EVENT_REVOKE, 1500, "patient-d", "patient-d", PURPOSE_CARE_TEAM),
            event(EVENT_REGRANT, 1600, "patient-d", "patient-d", PURPOSE_CARE_TEAM, expiry=9000),
        ],
        "request": request("patient-d", PURPOSE_CARE_TEAM, 2000),
    }
    return (valid_case, regrant_case)


def _stub_flag(result: object) -> bool:
    if isinstance(result, Outcome):
        return result.observed_outcome == "REJECT"
    if isinstance(result, bool):
        return result
    if isinstance(result, str):
        return result.strip().upper() in {"REJECT", "DETECT", "TRUE", "1", "DIVERGENT"}
    raise SacmatBaselineError(
        "STUB_RESULT_UNPARSEABLE", f"candidate returned {type(result).__name__}"
    )


def _stub_signature(result: object) -> tuple[bool, str]:
    if isinstance(result, Outcome):
        return (result.observed_outcome == "REJECT", result.detail)
    if isinstance(result, bool):
        return (result, "")
    if isinstance(result, str):
        flag = result.strip().upper() in {"REJECT", "DETECT", "TRUE", "1", "DIVERGENT"}
        return (flag, result.strip().upper())
    raise SacmatBaselineError(
        "STUB_RESULT_UNPARSEABLE", f"candidate returned {type(result).__name__}"
    )


def refuse_constant_stub(
    candidate: Callable[[Mapping[str, Any]], object],
    *,
    conformance_probes: Sequence[Mapping[str, Any]] | None = None,
    clean_probes: Sequence[Mapping[str, Any]] | None = None,
) -> Outcome:
    """Refuse detect-all / detect-none / constant-output stubs (rule 8).

    Replays the paired probe cases through ``candidate`` and refuses:
    - a candidate that flags EVERY probe, including the paired conformance
      controls (``STUB_DETECT_ALL_REFUSED`` — the detect-all stub);
    - a candidate that flags NO probe at all (``STUB_DETECT_NONE_REFUSED``);
    - a candidate whose (flag, detail) output is identical across the whole
      probe union (``CONSTANT_STUB_REFUSED`` — zero input sensitivity).

    Returns ``ADMIT`` / ``STUB_SEPARATION_OK`` when the candidate separates
    the paired controls (flags at least one conformance probe while not
    flagging at least one clean probe).
    """
    conformance = (
        tuple(conformance_probes) if conformance_probes is not None else conformance_probe_cases()
    )
    clean = tuple(clean_probes) if clean_probes is not None else clean_probe_cases()
    if not conformance or not clean:
        raise SacmatBaselineError(RC_CONTEXT_MALFORMED, "probe sets must be non-empty")
    results = [candidate(probe) for probe in (*conformance, *clean)]
    signatures = [_stub_signature(result) for result in results]
    flags = [sig[0] for sig in signatures]
    if len(set(signatures)) == 1:
        raise SacmatBaselineError(
            RC_STUB_CONSTANT,
            "candidate returns an identical (flag, detail) pair for every probe",
        )
    if all(flags):
        raise SacmatBaselineError(
            RC_STUB_DETECT_ALL,
            "candidate flags every probe including paired clean controls",
        )
    if not any(flags):
        raise SacmatBaselineError(
            RC_STUB_DETECT_NONE, "candidate flags no probe at all (zero discrimination)"
        )
    return Outcome(
        observed_outcome="ADMIT",
        counted_as_success=True,
        retriable=False,
        detail=RC_STUB_SEPARATION_OK,
    )
