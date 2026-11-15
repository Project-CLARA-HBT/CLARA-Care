"""SACMAT-candidate — temporal conformance testing across heterogeneous policy engines.

Purpose
-------
P04 candidate mechanism for "PolicyTrace: Temporal Conformance Testing of
Delegated Consent across Heterogeneous Policy Engines"
(``research/venue2027/VENUES/sacmat/RESEARCH_BLUEPRINT.md``, RQ1-RQ3; task
contract ``research/venue2027/VENUES/sacmat/TASKS/SACMAT-candidate.md``).
:func:`conformance_test` replays ONE delegated-consent trace through MULTIPLE
heterogeneous policy-engine models tick by tick over LOGICAL time and reports
the first DIVERGENCE between any two engine models at the same tick, carrying
the exact logical timestamp and the two disagreeing engines with their
decisions. The mechanism detects divergence that a static policy diff or a
single-engine test structurally cannot see: an engine model whose decision
differs from a peer only at the tick where a delegation expires (and whose
terminal state has been "healed" by a later event) is invisible to every
terminal-state comparison.

Heterogeneous engine models (in-process, deterministic, no external binaries):
each model implements a pinned upstream's documented semantics over the same
replayed event stream, differing in the exact dimension the study measures
(portability surface):

- ``cedar``   — Cedar-like permit/forbid set with forbid precedence (Cedar
  v4.14.1 semantics): delegation expiry is NOT encoded in the policy and must
  be re-checked by the caller, so the model permits any delegation recorded
  before the tick regardless of expiry.
- ``openfga`` — Zanzibar/OpenFGA-like relation-tuple walk evaluated at read
  time (Zanzibar ATC 2019 §2.3-2.4 / OpenFGA v1.22.1): expired or revoked
  tuples are absent from the walk; the check API is two-valued, so a failed
  walk DENIES rather than reporting not-applicable.
- ``opa``     — OPA-like fail-closed temporal evaluation (explicit-deny
  precedence, per the reference semantics): a delegation lapsed at the
  decision tick is an explicit temporal DENY, never a silent fall-through.

Two ablations remove one mechanism component each so tests can prove the
mechanism is load-bearing:

- :func:`ablation_single_engine` — runs the SAME temporal replay with ONE
  engine model only. With no second engine there is no pairwise comparison,
  so cross-engine divergence is structurally unobservable.
- :func:`ablation_no_time` — collapses the trace to its TERMINAL policy state
  and evaluates every engine ONCE at the terminal tick, discarding the access
  request's decision time and all intermediate ticks. A divergence that the
  terminal state has healed is invisible to it.

Allowed input
-------------
``trace``: a mapping with ``events`` (and optional ``trace_id``) or any object
exposing ``.events`` (PolicyTrace-shaped). Event records (mappings or
duck-typed objects) carry ``kind`` (``GRANT``/``REVOKE``/``DELEGATE``/
``ACCESS``), ``principal``, ``tenant``, ``resource``, ``purpose``,
``logical_time`` (mandatory int; strictly ascending; bool excluded), optional
``policy_state`` (delegating source, mandatory for ``DELEGATE``) and optional
``expiry`` (logical tick at which a ``GRANT``/``DELEGATE`` lapses; a decision
at ``tick >= expiry`` sees the delegation as expired). ``engines``: a sequence
of engine-model ids (default :data:`ENGINE_MODELS`).

Failure semantics
-----------------
Fail closed with stable reason codes. Data-level faults (missing logical
time, malformed events, empty trace, unordered/duplicate timestamps,
unsupported constructs) yield a first-class :class:`ConformanceResult` with
status ``INDETERMINATE`` — never a silent safe verdict. Wiring errors (trace
input of the wrong type, unknown engine id, non-sequence engines, non-mapping
case) raise :class:`TemporalConformanceError` with a stable reason code.
:func:`run_candidate` maps ``DIVERGENCE`` -> ``REJECT`` and
``NO_DIVERGENCE`` -> ``ADMIT`` (both ``counted_as_success=True``) and
``INDETERMINATE`` -> ``INDETERMINATE`` (never counted); when the injected
context declares the pinned upstream binaries unavailable it returns
``NOT_RUN_EXTERNAL`` / ``BASELINE_UNAVAILABLE`` (never counted, retriable).
No wall clock, randomness, network or I/O anywhere; identical inputs give
byte-identical results.

Version
-------
``CANDIDATE_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import dataclasses
import itertools
from collections.abc import Mapping, Sequence
from typing import Any, Final

from evaluation.venue2027._shared.harness import Outcome

CANDIDATE_ID: Final[str] = "sacmat-candidate-temporal-conformance"
CANDIDATE_VERSION: Final[str] = "1.0.0"

#: Result statuses (first-class, mutually exclusive).
STATUS_NO_DIVERGENCE: Final[str] = "NO_DIVERGENCE"
STATUS_DIVERGENCE: Final[str] = "DIVERGENCE"
STATUS_INDETERMINATE: Final[str] = "INDETERMINATE"

#: Stable reason codes.
RC_NO_DIVERGENCE: Final[str] = "NO_DIVERGENCE"
RC_TEMPORAL_CONFORMANCE_DIVERGENCE: Final[str] = "TEMPORAL_CONFORMANCE_DIVERGENCE"
RC_ABLATION_SINGLE_ENGINE: Final[str] = "ABLATION_SINGLE_ENGINE_NO_COMPARISON"
RC_ABLATION_NO_TIME: Final[str] = "ABLATION_NO_TIME_TERMINAL_VIEW_ONLY"
RC_INSUFFICIENT_ENGINES: Final[str] = "INSUFFICIENT_ENGINES"
RC_UNKNOWN_ENGINE: Final[str] = "UNKNOWN_ENGINE"
RC_ENGINES_NOT_A_SEQUENCE: Final[str] = "ENGINES_NOT_A_SEQUENCE"
RC_TRACE_INPUT_UNRECOGNIZED: Final[str] = "TRACE_INPUT_UNRECOGNIZED"
RC_TRACE_MISSING: Final[str] = "TRACE_MISSING"
RC_CASE_ID_MISSING: Final[str] = "CASE_ID_MISSING"
RC_CASE_ID_NOT_STRING: Final[str] = "CASE_ID_NOT_STRING"
RC_CASE_NOT_AN_OBJECT: Final[str] = "CASE_NOT_AN_OBJECT"
RC_BASELINE_UNAVAILABLE: Final[str] = "BASELINE_UNAVAILABLE"
RC_MISSING_LOGICAL_TIME: Final[str] = "MISSING_LOGICAL_TIME"
RC_UNORDERED_TIMESTAMPS: Final[str] = "UNORDERED_TIMESTAMPS"
RC_DUPLICATE_TIMESTAMP: Final[str] = "DUPLICATE_TIMESTAMP"
RC_MALFORMED_EVENT: Final[str] = "MALFORMED_EVENT"
RC_EMPTY_TRACE: Final[str] = "EMPTY_TRACE"
RC_UNSUPPORTED_CONSTRUCT: Final[str] = "UNSUPPORTED_CONSTRUCT"

#: Portable four-valued decision vocabulary (blueprint "Method architecture").
DECISION_PERMIT: Final[str] = "PERMIT"
DECISION_DENY: Final[str] = "DENY"
DECISION_NOT_APPLICABLE: Final[str] = "NOT_APPLICABLE"
DECISION_INDETERMINATE: Final[str] = "INDETERMINATE"

#: Trace event kinds (delegated-consent history).
EVENT_GRANT: Final[str] = "GRANT"
EVENT_REVOKE: Final[str] = "REVOKE"
EVENT_DELEGATE: Final[str] = "DELEGATE"
EVENT_ACCESS: Final[str] = "ACCESS"
SUPPORTED_EVENT_KINDS: Final[frozenset[str]] = frozenset(
    {EVENT_GRANT, EVENT_REVOKE, EVENT_DELEGATE, EVENT_ACCESS}
)

#: Heterogeneous engine-model ids, in fixed comparison order.
ENGINE_CEDAR: Final[str] = "cedar"
ENGINE_OPENFGA: Final[str] = "openfga"
ENGINE_OPA: Final[str] = "opa"
ENGINE_MODELS: Final[tuple[str, ...]] = (ENGINE_CEDAR, ENGINE_OPENFGA, ENGINE_OPA)

ABLATION_SINGLE_ENGINE: Final[str] = "single_engine"
ABLATION_NO_TIME: Final[str] = "no_time"

StateKey = tuple[str, str, str, str]
ScopeKey = tuple[str, str, str]


class TemporalConformanceError(ValueError):
    """Wiring/configuration error carrying a stable reason code (not a result)."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


# ---------------------------------------------------------------------------
# Typed result (JSON-serializable).
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ConformanceResult:
    """First-class result of one conformance run (or ablation run).

    ``divergence_time`` is the exact logical timestamp of the first tick where
    two engine models disagree; ``engine_a``/``engine_b`` name the disagreeing
    engines in fixed comparison order with their decisions.
    """

    candidate_id: str
    candidate_version: str
    status: str
    reason_code: str
    trace_id: str = ""
    engines: tuple[str, ...] = ()
    divergence_time: int | None = None
    engine_a: str | None = None
    engine_b: str | None = None
    decision_a: str | None = None
    decision_b: str | None = None
    timeline: tuple[dict[str, Any], ...] = ()
    ablation: str | None = None
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "candidate_version": self.candidate_version,
            "status": self.status,
            "reason_code": self.reason_code,
            "trace_id": self.trace_id,
            "engines": list(self.engines),
            "divergence_time": self.divergence_time,
            "engine_a": self.engine_a,
            "engine_b": self.engine_b,
            "decision_a": self.decision_a,
            "decision_b": self.decision_b,
            "timeline": [dict(entry) for entry in self.timeline],
            "ablation": self.ablation,
            "detail": self.detail,
        }


# ---------------------------------------------------------------------------
# Trace normalization / validation — fail closed to INDETERMINATE.
# ---------------------------------------------------------------------------


def _field(record: Any, name: str, default: Any = None) -> Any:
    """Read ``name`` from a mapping entry or an object attribute."""
    if isinstance(record, Mapping):
        return record.get(name, default)
    return getattr(record, name, default)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _string_field(record: Any, name: str, index: int, *, required: bool) -> str:
    value = _field(record, name, None)
    if value is None:
        if required:
            return ""
        return ""
    if not isinstance(value, str):
        return ""
    return value


def _normalize_trace(trace: Any) -> tuple[str, list[dict[str, Any]], str]:
    """Validate and normalize one trace.

    Returns ``(trace_id, normalized_events, "")`` on success and
    ``("", [], "<REASON_CODE>:<detail>")`` on data-level failure.
    """
    if isinstance(trace, Mapping):
        raw_events = trace.get("events")
        raw_trace_id = trace.get("trace_id", "")
    else:
        raw_events = getattr(trace, "events", None)
        raw_trace_id = getattr(trace, "trace_id", "")
    if raw_events is None or isinstance(raw_events, str | bytes):
        raise TemporalConformanceError(
            RC_TRACE_INPUT_UNRECOGNIZED,
            "trace must be a mapping with 'events' or an object exposing .events",
        )
    if not isinstance(raw_events, Sequence):
        raise TemporalConformanceError(
            RC_TRACE_INPUT_UNRECOGNIZED, "trace events must be a sequence"
        )
    trace_id = raw_trace_id if isinstance(raw_trace_id, str) else ""
    if not raw_events:
        return "", [], RC_EMPTY_TRACE

    normalized: list[dict[str, Any]] = []
    previous_time: int | None = None
    for index, raw in enumerate(raw_events):
        kind = _field(raw, "kind")
        if not isinstance(kind, str) or not kind:
            return "", [], f"{RC_MALFORMED_EVENT}:event[{index}].kind"
        if kind not in SUPPORTED_EVENT_KINDS:
            return "", [], f"{RC_UNSUPPORTED_CONSTRUCT}:{kind}"
        principal = _field(raw, "principal")
        if not isinstance(principal, str) or not principal:
            return "", [], f"{RC_MALFORMED_EVENT}:event[{index}].principal"
        logical_time = _field(raw, "logical_time")
        if logical_time is None:
            return "", [], f"{RC_MISSING_LOGICAL_TIME}:event[{index}]"
        if not _is_int(logical_time) or logical_time < 0:
            return "", [], f"{RC_MALFORMED_EVENT}:event[{index}].logical_time"
        tenant = _string_field(raw, "tenant", index, required=False)
        resource = _string_field(raw, "resource", index, required=False)
        purpose = _string_field(raw, "purpose", index, required=False)
        policy_state = _field(raw, "policy_state")
        if kind == EVENT_DELEGATE and (not isinstance(policy_state, str) or not policy_state):
            return "", [], f"{RC_MALFORMED_EVENT}:event[{index}].policy_state"
        if policy_state is not None and not isinstance(policy_state, str):
            return "", [], f"{RC_MALFORMED_EVENT}:event[{index}].policy_state"
        expiry = _field(raw, "expiry", None)
        if expiry is not None and (not _is_int(expiry) or expiry < 0):
            return "", [], f"{RC_MALFORMED_EVENT}:event[{index}].expiry"
        if previous_time is not None:
            if logical_time == previous_time:
                return "", [], f"{RC_DUPLICATE_TIMESTAMP}:{logical_time}"
            if logical_time < previous_time:
                return "", [], f"{RC_UNORDERED_TIMESTAMPS}:{logical_time}<{previous_time}"
        previous_time = logical_time
        normalized.append(
            {
                "kind": kind,
                "principal": principal,
                "tenant": tenant,
                "resource": resource,
                "purpose": purpose,
                "policy_state": policy_state if isinstance(policy_state, str) else "",
                "logical_time": logical_time,
                "expiry": expiry,
            }
        )
    return trace_id, normalized, ""


# ---------------------------------------------------------------------------
# Heterogeneous engine models over the replayed state.
#
# Shared replayed state: ``latest`` maps (principal, tenant, resource, purpose)
# -> the latest state-changing event (GRANT/REVOKE/DELEGATE) applied so far.
# A delegation is in force at tick T iff ``expiry is None or T < expiry``.
# ---------------------------------------------------------------------------


def _in_force(entry: Mapping[str, Any], tick: int) -> bool:
    expiry = entry["expiry"]
    return expiry is None or tick < expiry


def _decide_cedar(
    latest: Mapping[StateKey, dict[str, Any]], principal: str, scope: ScopeKey, tick: int
) -> str:
    """Cedar-like permit/forbid set with forbid precedence (Cedar v4.14.1).

    Delegation expiry is NOT encoded in the policy (caller must re-check), so
    a recorded grant/delegation permits regardless of expiry; an explicit
    REVOKE compiles a forbid that wins. Empty purpose is a validation error
    (INDETERMINATE), never a silent permit.
    """
    if not scope[2]:
        return DECISION_INDETERMINATE
    entry = latest.get((principal, *scope))
    if entry is None:
        return DECISION_NOT_APPLICABLE
    if entry["kind"] == EVENT_REVOKE:
        return DECISION_DENY
    if entry["kind"] == EVENT_DELEGATE:
        source_entry = latest.get((entry["policy_state"], *scope))
        if source_entry is None or source_entry["kind"] == EVENT_REVOKE:
            return DECISION_NOT_APPLICABLE
        return DECISION_PERMIT
    return DECISION_PERMIT


def _decide_openfga(
    latest: Mapping[StateKey, dict[str, Any]], principal: str, scope: ScopeKey, tick: int
) -> str:
    """Zanzibar/OpenFGA-like relation-tuple walk at read time (ATC 2019).

    Permission is tuple reachability at read time; revoked or expired tuples
    are absent, breaking the walk. The OpenFGA check API is two-valued, so a
    failed walk DENIES rather than reporting not-applicable.
    """
    seen: set[str] = set()
    node = principal
    while node not in seen:
        seen.add(node)
        entry = latest.get((node, *scope))
        if entry is None:
            break
        if entry["kind"] == EVENT_REVOKE or not _in_force(entry, tick):
            break
        if entry["kind"] == EVENT_GRANT:
            return DECISION_PERMIT
        node = entry["policy_state"]
    return DECISION_DENY


def _decide_opa(
    latest: Mapping[StateKey, dict[str, Any]], principal: str, scope: ScopeKey, tick: int
) -> str:
    """OPA-like fail-closed temporal evaluation (explicit-deny precedence).

    A delegation lapsed at the decision tick is an explicit temporal DENY
    (never a silent fall-through); an unresolvable delegation chain denies;
    unknown principals are NOT_APPLICABLE.
    """
    entry = latest.get((principal, *scope))
    if entry is None:
        return DECISION_NOT_APPLICABLE
    if entry["kind"] == EVENT_REVOKE or not _in_force(entry, tick):
        return DECISION_DENY
    if entry["kind"] == EVENT_GRANT:
        return DECISION_PERMIT
    seen = {principal}
    node = entry["policy_state"]
    while node not in seen:
        seen.add(node)
        source_entry = latest.get((node, *scope))
        if source_entry is None:
            return DECISION_DENY
        if source_entry["kind"] == EVENT_REVOKE or not _in_force(source_entry, tick):
            return DECISION_DENY
        if source_entry["kind"] == EVENT_GRANT:
            return DECISION_PERMIT
        node = source_entry["policy_state"]
    return DECISION_DENY


ENGINE_DECIDERS: Mapping[str, Any] = {
    ENGINE_CEDAR: _decide_cedar,
    ENGINE_OPENFGA: _decide_openfga,
    ENGINE_OPA: _decide_opa,
}


# ---------------------------------------------------------------------------
# Core mechanism: temporal replay + pairwise conformance comparison.
# ---------------------------------------------------------------------------


def _result(
    status: str,
    reason_code: str,
    *,
    engines: tuple[str, ...],
    trace_id: str = "",
    timeline: tuple[dict[str, Any], ...] = (),
    ablation: str | None = None,
    divergence_time: int | None = None,
    engine_a: str | None = None,
    engine_b: str | None = None,
    decision_a: str | None = None,
    decision_b: str | None = None,
    detail: str = "",
) -> ConformanceResult:
    return ConformanceResult(
        candidate_id=CANDIDATE_ID,
        candidate_version=CANDIDATE_VERSION,
        status=status,
        reason_code=reason_code,
        trace_id=trace_id,
        engines=engines,
        divergence_time=divergence_time,
        engine_a=engine_a,
        engine_b=engine_b,
        decision_a=decision_a,
        decision_b=decision_b,
        timeline=timeline,
        ablation=ablation,
        detail=detail,
    )


def _indeterminate(
    reason_code: str, *, engines: tuple[str, ...], ablation: str | None
) -> ConformanceResult:
    return _result(
        STATUS_INDETERMINATE,
        reason_code,
        engines=engines,
        ablation=ablation,
        detail=f"fail_closed|{reason_code}",
    )


def _validated_engines(engines: Sequence[str]) -> tuple[str, ...]:
    if isinstance(engines, str | bytes) or not isinstance(engines, Sequence):
        raise TemporalConformanceError(
            RC_ENGINES_NOT_A_SEQUENCE, f"engines must be a sequence, got {type(engines).__name__}"
        )
    ordered: list[str] = []
    for engine in engines:
        if not isinstance(engine, str) or engine not in ENGINE_MODELS:
            raise TemporalConformanceError(
                RC_UNKNOWN_ENGINE, f"engine {engine!r} not in {ENGINE_MODELS}"
            )
        if engine not in ordered:
            ordered.append(engine)
    return tuple(ordered)


def _replay(
    events: Sequence[Mapping[str, Any]], engines: tuple[str, ...], trace_id: str
) -> ConformanceResult:
    """Replay events in logical-time order, comparing engines at each ACCESS tick."""
    latest: dict[StateKey, dict[str, Any]] = {}
    timeline: list[dict[str, Any]] = []
    for entry in events:
        tick = entry["logical_time"]
        kind = entry["kind"]
        if kind == EVENT_ACCESS:
            scope: ScopeKey = (entry["tenant"], entry["resource"], entry["purpose"])
            decisions = {
                engine: ENGINE_DECIDERS[engine](latest, entry["principal"], scope, tick)
                for engine in engines
            }
            timeline.append(
                {
                    "logical_time": tick,
                    "principal": entry["principal"],
                    "purpose": entry["purpose"],
                    "decisions": decisions,
                }
            )
            for engine_a, engine_b in itertools.combinations(engines, 2):
                if decisions[engine_a] != decisions[engine_b]:
                    return _result(
                        STATUS_DIVERGENCE,
                        RC_TEMPORAL_CONFORMANCE_DIVERGENCE,
                        engines=engines,
                        trace_id=trace_id,
                        timeline=tuple(timeline),
                        divergence_time=tick,
                        engine_a=engine_a,
                        engine_b=engine_b,
                        decision_a=decisions[engine_a],
                        decision_b=decisions[engine_b],
                        detail=(
                            f"{engine_a}={decisions[engine_a]} vs {engine_b}="
                            f"{decisions[engine_b]} at logical_time={tick}"
                        ),
                    )
        else:
            latest[(entry["principal"], entry["tenant"], entry["resource"], entry["purpose"])] = (
                dict(entry)
            )
    return _result(
        STATUS_NO_DIVERGENCE,
        RC_NO_DIVERGENCE,
        engines=engines,
        trace_id=trace_id,
        timeline=tuple(timeline),
        detail="engines_agree_at_every_evaluated_tick",
    )


def _terminal_view(
    events: Sequence[Mapping[str, Any]], engines: tuple[str, ...], trace_id: str
) -> ConformanceResult:
    """Ablation: evaluate every engine ONCE on the terminal state (no replay).

    Applies every event once (input order), then evaluates the FIRST access
    request at the TERMINAL tick only — the access's decision time and all
    intermediate ticks are discarded, so temporal divergence the terminal
    state has healed is invisible.
    """
    latest: dict[StateKey, dict[str, Any]] = {}
    first_access: Mapping[str, Any] | None = None
    for entry in events:
        if entry["kind"] == EVENT_ACCESS:
            if first_access is None:
                first_access = entry
        else:
            latest[(entry["principal"], entry["tenant"], entry["resource"], entry["purpose"])] = (
                dict(entry)
            )
    if first_access is None:
        return _result(
            STATUS_NO_DIVERGENCE,
            RC_NO_DIVERGENCE,
            engines=engines,
            trace_id=trace_id,
            ablation=ABLATION_NO_TIME,
            detail="no_access_event_terminal_view_only",
        )
    terminal_tick = events[-1]["logical_time"]
    scope = (first_access["tenant"], first_access["resource"], first_access["purpose"])
    decisions = {
        engine: ENGINE_DECIDERS[engine](latest, first_access["principal"], scope, terminal_tick)
        for engine in engines
    }
    timeline = (
        {
            "logical_time": terminal_tick,
            "principal": first_access["principal"],
            "purpose": first_access["purpose"],
            "decisions": decisions,
        },
    )
    for engine_a, engine_b in itertools.combinations(engines, 2):
        if decisions[engine_a] != decisions[engine_b]:
            return _result(
                STATUS_DIVERGENCE,
                RC_TEMPORAL_CONFORMANCE_DIVERGENCE,
                engines=engines,
                trace_id=trace_id,
                timeline=timeline,
                ablation=ABLATION_NO_TIME,
                divergence_time=terminal_tick,
                engine_a=engine_a,
                engine_b=engine_b,
                decision_a=decisions[engine_a],
                decision_b=decisions[engine_b],
                detail=(
                    f"terminal_view|{engine_a}={decisions[engine_a]} vs {engine_b}="
                    f"{decisions[engine_b]} at logical_time={terminal_tick}"
                ),
            )
    return _result(
        STATUS_NO_DIVERGENCE,
        RC_ABLATION_NO_TIME,
        engines=engines,
        trace_id=trace_id,
        timeline=timeline,
        ablation=ABLATION_NO_TIME,
        detail="terminal_view_only|engines_agree_at_terminal_tick",
    )


# ---------------------------------------------------------------------------
# Public API.
# ---------------------------------------------------------------------------


def conformance_test(trace: Any, engines: Sequence[str] | None = None) -> ConformanceResult:
    """Run one delegated-consent trace through heterogeneous engine models.

    Replays the trace over logical time, applying state events tick by tick
    and evaluating every engine model at each ACCESS tick; reports the first
    cross-engine divergence with its exact logical timestamp and the two
    disagreeing engines. Fewer than two (distinct) engines cannot express a
    conformance property and yield INDETERMINATE / ``INSUFFICIENT_ENGINES``.
    """
    engine_tuple = _validated_engines(ENGINE_MODELS if engines is None else engines)
    if len(engine_tuple) < 2:
        return _indeterminate(RC_INSUFFICIENT_ENGINES, engines=engine_tuple, ablation=None)
    trace_id, events, error = _normalize_trace(trace)
    if error:
        return _indeterminate(error, engines=engine_tuple, ablation=None)
    return _replay(events, engine_tuple, trace_id)


def ablation_single_engine(trace: Any, engine: str = ENGINE_CEDAR) -> ConformanceResult:
    """Ablation: the same temporal replay with ONE engine model only.

    With no second engine there is no pairwise comparison, so cross-engine
    divergence is structurally unobservable — the run reports NO_DIVERGENCE
    even on traces :func:`conformance_test` flags. This is the component
    proof that cross-engine comparison is load-bearing.
    """
    engine_tuple = _validated_engines((engine,))
    trace_id, events, error = _normalize_trace(trace)
    if error:
        return _indeterminate(error, engines=engine_tuple, ablation=ABLATION_SINGLE_ENGINE)
    replayed = _replay(events, engine_tuple, trace_id)
    if replayed.status != STATUS_NO_DIVERGENCE:
        raise TemporalConformanceError(
            "ABLATION_INVARIANT_BROKEN", "single-engine replay cannot produce divergence"
        )
    return _result(
        STATUS_NO_DIVERGENCE,
        RC_ABLATION_SINGLE_ENGINE,
        engines=engine_tuple,
        trace_id=trace_id,
        timeline=replayed.timeline,
        ablation=ABLATION_SINGLE_ENGINE,
        detail="single_engine_no_pairwise_comparison",
    )


def ablation_no_time(trace: Any, engines: Sequence[str] | None = None) -> ConformanceResult:
    """Ablation: all engines, but the terminal state only — no logical replay.

    Discards the access request's decision time and every intermediate tick,
    so a divergence that exists only at its exact tick (e.g. a delegation
    expiring between grant and a later healing revoke) is missed. This is the
    component proof that logical-time replay is load-bearing.
    """
    engine_tuple = _validated_engines(ENGINE_MODELS if engines is None else engines)
    trace_id, events, error = _normalize_trace(trace)
    if error:
        return _indeterminate(error, engines=engine_tuple, ablation=ABLATION_NO_TIME)
    return _terminal_view(events, engine_tuple, trace_id)


def describe_mechanism() -> dict[str, Any]:
    """JSON-serializable description of the candidate mechanism and ablations."""
    return {
        "candidate_id": CANDIDATE_ID,
        "candidate_version": CANDIDATE_VERSION,
        "mechanism": (
            "Temporal conformance testing: replay one delegated-consent trace "
            "through multiple heterogeneous policy-engine models over logical "
            "time, comparing their decisions pairwise at every ACCESS tick; "
            "report the first divergence with the exact logical timestamp and "
            "the two disagreeing engines."
        ),
        "components": [
            "logical-time replay of the ordered policy history",
            "heterogeneous engine models with mismatched portability surfaces",
            "pairwise four-valued decision comparison at every evaluated tick",
            "minimal first-divergence witness (timestamp + engine pair + decisions)",
        ],
        "decision_vocabulary": [
            DECISION_PERMIT,
            DECISION_DENY,
            DECISION_NOT_APPLICABLE,
            DECISION_INDETERMINATE,
        ],
        "engine_models": {
            ENGINE_CEDAR: (
                "Cedar v4.14.1 semantics: permit/forbid set, forbid precedence; "
                "delegation expiry is caller-encoded and NOT honored"
            ),
            ENGINE_OPENFGA: (
                "Zanzibar ATC 2019 / OpenFGA v1.22.1 semantics: relation-tuple "
                "walk at read time; expired/revoked tuples absent; two-valued check"
            ),
            ENGINE_OPA: (
                "OPA-like fail-closed temporal evaluation: lapsed delegation is an "
                "explicit DENY; unresolvable chains deny"
            ),
        },
        "ablations": {
            ABLATION_SINGLE_ENGINE: (
                "same replay with one engine model only: no pairwise comparison, "
                "so cross-engine divergence is unobservable"
            ),
            ABLATION_NO_TIME: (
                "all engines evaluated once on the terminal state: the access's "
                "decision time and intermediate ticks are discarded, so "
                "expiry-tick divergence the terminal state healed is missed"
            ),
        },
        "witness": "first tick where two engine models disagree",
    }


# ---------------------------------------------------------------------------
# Harness adapter: run_candidate(case, ctx) -> Outcome (task contract).
# ---------------------------------------------------------------------------


def _case_outcome(observed_outcome: str, counted_as_success: bool, detail: str) -> Outcome:
    return Outcome(
        observed_outcome=observed_outcome,
        counted_as_success=counted_as_success,
        retriable=False,
        detail=detail,
    )


def run_candidate(case: Mapping[str, Any], ctx: Any = None) -> Outcome:
    """Execute the candidate on one ``{"case_id", "trace"}`` case.

    Maps the conformance verdict onto a first-class harness :class:`Outcome`:
    DIVERGENCE -> REJECT and NO_DIVERGENCE -> ADMIT (both
    ``counted_as_success=True``); malformed cases yield INDETERMINATE (never
    counted, never a silent safe rejection). When the injected context
    declares the pinned upstream binaries unavailable
    (``simulate_unavailable_upstream``) the arm returns ``NOT_RUN_EXTERNAL`` /
    ``BASELINE_UNAVAILABLE`` (never counted, retriable) — no toy substitution.
    """
    if not isinstance(case, Mapping):
        raise TemporalConformanceError(
            RC_CASE_NOT_AN_OBJECT, f"case must be a mapping, got {type(case).__name__}"
        )
    if getattr(ctx, "simulate_unavailable_upstream", False):
        return Outcome(
            observed_outcome="NOT_RUN_EXTERNAL",
            counted_as_success=False,
            retriable=True,
            detail=f"{RC_BASELINE_UNAVAILABLE}|conformance replay requires the pinned binaries",
        )
    case_id = case.get("case_id")
    if case_id is None:
        return _case_outcome("INDETERMINATE", False, f"{CANDIDATE_ID}|{RC_CASE_ID_MISSING}")
    if not isinstance(case_id, str) or not case_id:
        return _case_outcome("INDETERMINATE", False, f"{CANDIDATE_ID}|{RC_CASE_ID_NOT_STRING}")
    if "trace" not in case and "events" not in case:
        return _case_outcome("INDETERMINATE", False, f"{CANDIDATE_ID}|{RC_TRACE_MISSING}")
    trace_payload = case["trace"] if "trace" in case else case
    result = conformance_test(trace_payload)
    if result.status == STATUS_DIVERGENCE:
        return _case_outcome(
            "REJECT",
            True,
            (
                f"{CANDIDATE_ID}@{CANDIDATE_VERSION}|{result.reason_code}"
                f"|t={result.divergence_time}|{result.engine_a}:{result.decision_a}"
                f"!={result.engine_b}:{result.decision_b}"
            ),
        )
    if result.status == STATUS_NO_DIVERGENCE:
        return _case_outcome(
            "ADMIT",
            True,
            f"{CANDIDATE_ID}@{CANDIDATE_VERSION}|{result.reason_code}|{result.detail}",
        )
    return _case_outcome(
        "INDETERMINATE",
        False,
        f"{CANDIDATE_ID}@{CANDIDATE_VERSION}|{result.reason_code}|{result.detail}",
    )
