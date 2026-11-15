"""SACMAT-X01_policy_trace_dsl — temporal policy-trace DSL.

Purpose
-------
Machine-checkable *policy-history input language and temporal conformance
oracle* for "PolicyTrace: Temporal Conformance Testing of Delegated Consent
across Heterogeneous Policy Engines"
(``research/venue2027/VENUES/sacmat/RESEARCH_BLUEPRINT.md``, RQ1; task
contract ``research/venue2027/VENUES/sacmat/TASKS/SACMAT-X01_policy_trace_dsl.md``).
A delegated-consent trace is a strictly ordered sequence of :class:`Event`
records (grant / revoke / delegate / access) over ``(principal, tenant,
resource, purpose)``; :class:`PolicyTrace` validation refuses histories
without an explicit logical time (ambiguous no-time policies) and
:func:`evaluate_trace` detects the trace-level errors static rule/decision
coverage misses: revoke-before-grant, delegation cycles and revoked-actor
transitivity.

Allowed input
-------------
- :class:`Event` records constructed directly or via :meth:`Event.from_dict`;
  every event carries an explicit integer ``logical_time`` (total order,
  bool excluded), a ``policy_state`` epoch token, a non-empty ``kind``
  (``GRANT``/``REVOKE``/``DELEGATE``/``ACCESS``), ``principal``, ``tenant``,
  ``resource`` and ``purpose`` strings.
- :class:`PolicyTrace` built via :func:`parse_policy_trace` (JSON mapping,
  version-pinned) with events in strictly ascending logical-time order.
  Out-of-order or duplicate timestamps are refused, never silently
  reordered.

Failure semantics (stable reason codes on ``PolicyTraceError``)
----------------------------------------------------------------
- ``MISSING_LOGICAL_TIME`` — an event whose explicit logical time is absent
  or ``None``. Ambiguous no-time policies are refused outright: temporal
  precedence is undecidable without a total order.
- ``UNORDERED_TIMESTAMPS`` — events supplied out of ascending order.
- ``DUPLICATE_TIMESTAMP`` — two events sharing one logical time.
- ``MALFORMED_EVENT`` — non-string identifiers, empty strings, non-int
  logical time, unknown event kind, non-object event entries, bad trace_id.
- ``SCHEMA_VERSION_MISMATCH`` — trace version differs from the DSL version.
- ``EMPTY_TRACE`` — a trace with zero events has no history to adjudicate.

Evaluation semantics (:func:`evaluate_trace` -> :class:`TraceVerdict`)
----------------------------------------------------------------------
Events are replayed in logical-time order. Active grants are tracked per
``(tenant, resource, purpose)`` scope; ``DELEGATE`` extends an active grant
to a delegate principal (storing the delegator edge for cycle detection);
``REVOKE`` removes the actor's authority in that scope. Findings, each
carrying the witness event index:
- ``REVOKE_BEFORE_GRANT`` — a revoke (or delegation source) for a principal
  holding no active grant in the relevant scope.
- ``DELEGATION_CYCLE`` — a delegate edge closes a cycle in the delegation
  graph (A delegates to B, B delegates to A).
- ``REVOKED_ACTOR_TRANSITIVITY`` — an actor already revoked still holds
  delegated authority and exercises it; the stale authority is stripped
  fail-closed and the access denied.
The final ``outcome`` is the last access's decision — ``PERMIT`` under
intact authority, ``DENY`` otherwise; ``INDETERMINATE`` marks an access
referencing authority never established in scope (never silently mapped to
a permit, blueprint SACMAT-CASE-04). Findings are sorted deterministically;
no wall clock, randomness or I/O anywhere.

All outputs (:meth:`TraceVerdict.to_dict`, :meth:`Event.to_dict`,
:meth:`PolicyTrace.to_dict`) are JSON-serializable.

Version
-------
``POLICY_TRACE_DSL_VERSION = "clara.sacmat.policy-trace-dsl-v1"``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping
from typing import Any, Final

POLICY_TRACE_DSL_VERSION: Final[str] = "clara.sacmat.policy-trace-dsl-v1"

REASON_MISSING_LOGICAL_TIME: Final[str] = "MISSING_LOGICAL_TIME"
REASON_UNORDERED_TIMESTAMPS: Final[str] = "UNORDERED_TIMESTAMPS"
REASON_DUPLICATE_TIMESTAMP: Final[str] = "DUPLICATE_TIMESTAMP"
REASON_MALFORMED_EVENT: Final[str] = "MALFORMED_EVENT"
REASON_SCHEMA_VERSION_MISMATCH: Final[str] = "SCHEMA_VERSION_MISMATCH"
REASON_EMPTY_TRACE: Final[str] = "EMPTY_TRACE"

FINDING_REVOKE_BEFORE_GRANT: Final[str] = "REVOKE_BEFORE_GRANT"
FINDING_DELEGATION_CYCLE: Final[str] = "DELEGATION_CYCLE"
FINDING_REVOKED_ACTOR_TRANSITIVITY: Final[str] = "REVOKED_ACTOR_TRANSITIVITY"
FINDING_UNESTABLISHED_AUTHORITY: Final[str] = "UNESTABLISHED_AUTHORITY"

OUTCOME_PERMIT: Final[str] = "PERMIT"
OUTCOME_DENY: Final[str] = "DENY"
OUTCOME_INDETERMINATE: Final[str] = "INDETERMINATE"

EVENT_KIND_GRANT: Final[str] = "GRANT"
EVENT_KIND_REVOKE: Final[str] = "REVOKE"
EVENT_KIND_DELEGATE: Final[str] = "DELEGATE"
EVENT_KIND_ACCESS: Final[str] = "ACCESS"
_EVENT_KINDS: Final[frozenset[str]] = frozenset(
    {EVENT_KIND_GRANT, EVENT_KIND_REVOKE, EVENT_KIND_DELEGATE, EVENT_KIND_ACCESS}
)

_EVENT_STRING_FIELDS: Final[tuple[str, ...]] = (
    "principal",
    "tenant",
    "resource",
    "purpose",
    "policy_state",
)

ScopeKey = tuple[str, str, str]


class PolicyTraceError(Exception):
    """Fail-closed trace rejection carrying a stable reason code."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(f"{reason_code}: {detail}" if detail else reason_code)
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class Event:
    """One temporal policy event; ``logical_time`` is mandatory and total."""

    principal: str
    tenant: str
    resource: str
    purpose: str
    policy_state: str
    logical_time: int
    kind: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def __post_init__(self) -> None:
        if self.logical_time is None:
            raise PolicyTraceError(
                REASON_MISSING_LOGICAL_TIME,
                "event has no explicit logical_time (ambiguous no-time policy is refused)",
            )

    @classmethod
    def field_names(cls) -> tuple[str, ...]:
        return (
            "principal",
            "tenant",
            "resource",
            "purpose",
            "policy_state",
            "logical_time",
            "kind",
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Event:
        missing = [key for key in cls.field_names() if key not in payload]
        if "logical_time" not in payload or payload.get("logical_time") is None:
            raise PolicyTraceError(
                REASON_MISSING_LOGICAL_TIME,
                "event has no explicit logical_time (ambiguous no-time policy is refused)",
            )
        if missing:
            raise PolicyTraceError(
                REASON_MALFORMED_EVENT, f"event missing fields: {sorted(missing)}"
            )
        values = {key: payload[key] for key in cls.field_names()}
        try:
            return cls(**values)
        except TypeError as exc:
            raise PolicyTraceError(REASON_MALFORMED_EVENT, f"event malformed: {exc}") from exc


def _validate_event_fields(event: Event, index: int) -> None:
    for field in _EVENT_STRING_FIELDS:
        value = getattr(event, field)
        if not isinstance(value, str) or not value:
            raise PolicyTraceError(
                REASON_MALFORMED_EVENT,
                f"event[{index}].{field} must be a non-empty string, got {value!r}",
            )
    if isinstance(event.logical_time, bool) or not isinstance(event.logical_time, int):
        raise PolicyTraceError(
            REASON_MISSING_LOGICAL_TIME if event.logical_time is None else REASON_MALFORMED_EVENT,
            f"event[{index}].logical_time must be an int, got {event.logical_time!r}",
        )
    if event.kind not in _EVENT_KINDS:
        raise PolicyTraceError(
            REASON_MALFORMED_EVENT,
            f"event[{index}].kind unknown: {event.kind!r} (allowed: {sorted(_EVENT_KINDS)})",
        )


@dataclasses.dataclass(frozen=True)
class PolicyTrace:
    """A validated, strictly ordered policy history."""

    trace_id: str
    events: tuple[Event, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": POLICY_TRACE_DSL_VERSION,
            "trace_id": self.trace_id,
            "events": [event.to_dict() for event in self.events],
        }

    @property
    def trace_sha256(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(canonical).hexdigest()


def parse_policy_trace(payload: Mapping[str, Any]) -> PolicyTrace:
    """Parse a JSON mapping into a validated :class:`PolicyTrace`.

    Required keys: ``version``, ``trace_id``, ``events`` (non-empty list of
    event objects, each carrying an explicit ``logical_time``). Events must
    arrive in strictly ascending logical-time order; out-of-order or
    duplicate timestamps are refused, not silently reordered.
    """
    version = payload.get("version")
    if version != POLICY_TRACE_DSL_VERSION:
        raise PolicyTraceError(
            REASON_SCHEMA_VERSION_MISMATCH,
            f"trace {version!r} != DSL {POLICY_TRACE_DSL_VERSION!r}",
        )
    trace_id = payload.get("trace_id")
    if not isinstance(trace_id, str) or not trace_id:
        raise PolicyTraceError(REASON_MALFORMED_EVENT, "trace_id must be a non-empty string")
    raw_events = payload.get("events")
    if not isinstance(raw_events, list | tuple) or not raw_events:
        raise PolicyTraceError(REASON_EMPTY_TRACE, "events must be a non-empty list")
    events: list[Event] = []
    for index, raw in enumerate(raw_events):
        if not isinstance(raw, Mapping):
            raise PolicyTraceError(REASON_MALFORMED_EVENT, f"event[{index}] is not an object")
        try:
            event = Event.from_dict(raw)
        except PolicyTraceError as exc:
            raise PolicyTraceError(
                exc.reason_code, f"event[{index}]: {exc.detail}" if exc.detail else exc.reason_code
            ) from exc
        _validate_event_fields(event, index)
        events.append(event)
    for index in range(1, len(events)):
        previous = events[index - 1].logical_time
        current = events[index].logical_time
        if current == previous:
            raise PolicyTraceError(
                REASON_DUPLICATE_TIMESTAMP,
                f"events[{index - 1}] and events[{index}] share logical_time {current}",
            )
        if current < previous:
            raise PolicyTraceError(
                REASON_UNORDERED_TIMESTAMPS,
                f"events[{index}].logical_time {current} < events[{index - 1}] {previous}",
            )
    return PolicyTrace(trace_id=trace_id, events=tuple(events))


@dataclasses.dataclass(frozen=True)
class Finding:
    """One trace-level policy error with its witness event index."""

    kind: str
    witness_event_index: int
    actor: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "witness_event_index": self.witness_event_index,
            "actor": self.actor,
            "detail": self.detail,
        }


@dataclasses.dataclass(frozen=True)
class TraceVerdict:
    """JSON-serializable evaluation outcome (fail-closed record)."""

    trace_id: str
    outcome: str
    findings: tuple[Finding, ...]
    dsl_version: str = POLICY_TRACE_DSL_VERSION
    trace_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "outcome": self.outcome,
            "findings": sorted(
                (finding.to_dict() for finding in self.findings),
                key=lambda finding: (finding["witness_event_index"], finding["kind"]),
            ),
            "dsl_version": self.dsl_version,
            "trace_sha256": self.trace_sha256,
        }


def _delegation_reaches(start: str, target: str, edges: Mapping[str, frozenset[str]]) -> bool:
    """True if ``target`` is reachable from ``start`` over delegation edges."""
    stack, seen = [start], set()
    while stack:
        node = stack.pop()
        if node == target:
            return True
        if node in seen:
            continue
        seen.add(node)
        stack.extend(sorted(edges.get(node, frozenset()), reverse=True))
    return False


def _revoked_in_chain(
    principal: str,
    revoked_actors: set[str],
    delegation_edges: Mapping[str, frozenset[str]],
) -> bool:
    """True if ``principal`` or any delegator backing its authority is revoked.

    Authority flows delegator -> delegate, so this walks the *inverted*
    delegation graph upstream from ``principal``: any revoked actor in the
    chain backing the principal's authority is the transitivity witness.
    """
    if principal in revoked_actors:
        return True
    upstream: dict[str, set[str]] = {}
    for delegator, delegates in delegation_edges.items():
        for delegate in delegates:
            upstream.setdefault(delegate, set()).add(delegator)
    stack, seen = [principal], set()
    while stack:
        node = stack.pop()
        for delegator in upstream.get(node, ()):  # noqa: B007
            if delegator in revoked_actors:
                return True
            if delegator not in seen:
                seen.add(delegator)
                stack.append(delegator)
    return False


def evaluate_trace(trace: PolicyTrace) -> TraceVerdict:
    """Replay ``trace`` in logical-time order and adjudicate trace-level errors.

    Active grants are tracked per ``(tenant, resource, purpose)`` scope.
    ``DELEGATE`` extends the delegator's active authority to the delegate and
    records the edge for cycle detection. ``REVOKE`` strips the actor's own
    authority in that scope; revoking authority never established is
    ``REVOKE_BEFORE_GRANT``. Revocation is *not* silently cascaded: if a
    revoked actor's delegatee still holds or exercises delegated authority,
    that is the ``REVOKED_ACTOR_TRANSITIVITY`` witness — the stale authority
    is then stripped fail-closed and the access denied (the trace-level error
    a correct engine must not produce). A delegate edge that closes a cycle
    is ``DELEGATION_CYCLE``. An access referencing authority never
    established yields ``INDETERMINATE`` with an ``UNESTABLISHED_AUTHORITY``
    finding; it is never coerced to a permit.
    """
    findings: list[Finding] = []
    # principal -> {scope -> frozenset(authority actors backing the grant)}
    active_grants: dict[str, dict[ScopeKey, frozenset[str]]] = {}
    # delegate -> frozenset(delegators)
    delegation_edges: dict[str, frozenset[str]] = {}
    revoked_actors: set[str] = set()
    # principals whose authority was established at some point (grant or delegate)
    established_actors: set[str] = set()

    def _record(kind: str, index: int, actor: str, detail: str) -> None:
        findings.append(Finding(kind, index, actor, detail))

    last_access_outcome = OUTCOME_DENY
    saw_access = False
    for index, event in enumerate(trace.events):
        scope: ScopeKey = (event.tenant, event.resource, event.purpose)
        scopes = active_grants.setdefault(event.principal, {})
        if event.kind == EVENT_KIND_GRANT:
            established_actors.add(event.principal)
            scopes[scope] = scopes.get(scope, frozenset()) | {event.principal}
        elif event.kind == EVENT_KIND_REVOKE:
            if scope not in active_grants.get(event.principal, {}):
                _record(
                    FINDING_REVOKE_BEFORE_GRANT,
                    index,
                    event.principal,
                    f"revoke at t={event.logical_time} for principal with no active grant "
                    f"in scope {scope}",
                )
            else:
                remaining = {
                    held_scope: authorities
                    for held_scope, authorities in scopes.items()
                    if held_scope != scope
                }
                active_grants[event.principal] = remaining
            revoked_actors.add(event.principal)
        elif event.kind == EVENT_KIND_DELEGATE:
            if scope not in active_grants.get(event.principal, {}):
                _record(
                    FINDING_REVOKE_BEFORE_GRANT,
                    index,
                    event.principal,
                    f"delegate at t={event.logical_time} from principal without active grant "
                    f"in scope {scope}",
                )
            delegation_edges[event.principal] = delegation_edges.get(
                event.principal, frozenset()
            ) | {event.policy_state}
            if _delegation_reaches(event.policy_state, event.principal, delegation_edges):
                _record(
                    FINDING_DELEGATION_CYCLE,
                    index,
                    event.principal,
                    f"delegate at t={event.logical_time} closes a cycle: "
                    f"{event.principal} -> {event.policy_state} -> ... -> {event.principal}",
                )
            delegate_scopes = active_grants.setdefault(event.policy_state, {})
            inherited = scopes.get(scope, frozenset()) | {event.principal}
            delegate_scopes[scope] = delegate_scopes.get(scope, frozenset()) | inherited
            established_actors.add(event.policy_state)
        elif event.kind == EVENT_KIND_ACCESS:
            saw_access = True
            holds_authority = scope in active_grants.get(event.principal, {})
            if holds_authority:
                last_access_outcome = OUTCOME_PERMIT
            else:
                known_principal = (
                    event.principal in established_actors
                    or event.principal in delegation_edges
                    or any(event.principal in targets for targets in delegation_edges.values())
                )
                if known_principal:
                    last_access_outcome = OUTCOME_DENY
                else:
                    last_access_outcome = OUTCOME_INDETERMINATE
                    _record(
                        FINDING_UNESTABLISHED_AUTHORITY,
                        index,
                        event.principal,
                        f"access at t={event.logical_time} references authority never "
                        f"established in scope {scope}",
                    )
            if holds_authority and _revoked_in_chain(
                event.principal, revoked_actors, delegation_edges
            ):
                _record(
                    FINDING_REVOKED_ACTOR_TRANSITIVITY,
                    index,
                    event.principal,
                    f"access at t={event.logical_time}: principal was revoked yet still "
                    f"holds delegated authority in scope {scope}",
                )
                active_grants[event.principal].pop(scope, None)
                last_access_outcome = OUTCOME_DENY
    if not saw_access:
        last_access_outcome = OUTCOME_DENY
    ordered = tuple(sorted(findings, key=lambda f: (f.witness_event_index, f.kind, f.actor)))
    return TraceVerdict(
        trace_id=trace.trace_id,
        outcome=last_access_outcome,
        findings=ordered,
        trace_sha256=trace.trace_sha256,
    )


def evaluate_trace_json(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Parse and evaluate a JSON trace payload in one call; JSON-serializable."""
    trace = parse_policy_trace(payload)
    return evaluate_trace(trace).to_dict()
