"""SACMAT-X02_reference_semantics — language-independent reference semantics.

Purpose
-------
Reference decision procedure for "PolicyTrace: Temporal Conformance Testing of
Delegated Consent across Heterogeneous Policy Engines"
(``research/venue2027/VENUES/sacmat/RESEARCH_BLUEPRINT.md``, RQ3; task
contract ``research/venue2027/VENUES/sacmat/TASKS/SACMAT-X02_reference_semantics.md``).
:func:`reference_decide` answers ONE authorization request
(:class:`ReferenceQuery`) against ONE policy history (:class:`ReferenceTrace`)
from first principles — grant ordering, delegation transitivity, revocation
dominance and obligation satisfaction — producing a portable
:class:`ReferenceVerdict` (``ALLOW``/``DENY``/``INDETERMINATE`` plus a fourth
``UNKNOWN`` for constructs outside the supported subset). It is the
independent yardstick against which heterogeneous PDPs (Cedar, OpenFGA, OPA
adapters) are compared; it implements its OWN decision logic and imports NO
candidate policy engine or baseline arm. It may accept PolicyTrace-shaped
input (objects carrying ``.events`` — or plain dicts with an ``events`` list —
whose records expose ``kind``/``principal``/``tenant``/``resource``/
``purpose``/``policy_state``/``logical_time``) without depending on that
module.

Supported subset and semantics
------------------------------
Event convention: ``GRANT``/``REVOKE``/``ACCESS`` act on ``principal``;
``DELEGATE`` transfers authority FROM the delegating source (carried in
``policy_state``) TO ``principal`` (the delegate gaining authority). Histories
are replayed in logical-time order per ``(tenant, resource, purpose)`` scope:

- ``GRANT(p, scope)`` — (re-)establishes ``p``'s direct authority in
  ``scope`` at that logical time, clearing any prior revocation or delegation
  cycle taint for ``p`` in that scope (a fresh direct grant is a new
  authority basis).
- ``DELEGATE(source -> p, scope)`` — transitivity: ``p`` inherits the
  source's active authority in ``scope``; the edge is recorded both forward
  (for cycle detection) and inverted (for revocation-chain walks). A
  delegation whose source holds no active authority at that logical time is
  unresolvable (``UNKNOWN``). An edge that closes a cycle taints every
  principal on the cycle in that scope: delegated consent must be acyclic,
  so tainted authority is denied, never minted.
- ``REVOKE(p, scope)`` — revocation DOMINATES: ``p`` loses authority in
  ``scope`` and the revocation epoch is remembered so any principal whose
  inherited-authority chain (walked upstream over the inverted delegation
  graph) reaches a revoked actor at or before the decision time is denied —
  a downstream redelegation cannot resurrect revoked authority.
- ``ACCESS(q, scope)`` — the queried decision point.

Decision composition (fail-closed order): missing logical time or malformed
history -> ``INDETERMINATE`` (temporal precedence undecidable — never a
safe-looking denial); unknown/empty purpose, no authority in scope, grant not
yet in force at the decision time (expiry divergence), revoked chain,
delegation cycle, or an unsatisfied obligation -> ``DENY`` (explicit-deny
precedence); unsupported event kinds -> ``UNKNOWN`` (never a forced deny
masquerading as a semantic judgment); otherwise ``ALLOW``.

Allowed input
-------------
- :class:`ReferenceTrace` built from :class:`ReferenceEvent` records or a
  plain mapping (``{"trace_id": ..., "events": [...]}``); any duck-typed
  object exposing ``.events`` (PolicyTrace-shaped) is accepted.
- :class:`ReferenceQuery` or a mapping of the same shape;
  ``decision_time`` is mandatory; ``obligations`` maps obligation name ->
  strictly-boolean satisfaction.

Failure semantics (stable reason codes on :class:`ReferenceSemanticsError`)
---------------------------------------------------------------------------
- ``MISSING_LOGICAL_TIME`` — an event without an explicit integer logical
  time, or a query without a decision time; verdict ``INDETERMINATE``.
- ``MALFORMED_EVENT`` — non-string/empty identifiers in an event or the
  query; verdict ``INDETERMINATE``.
- ``UNSUPPORTED_CONSTRUCT`` — event kind outside the supported subset;
  verdict ``UNKNOWN``.
- ``UNRESOLVABLE_DELEGATION`` — delegation from a source without active
  authority at that logical time; verdict ``UNKNOWN``.
- ``UNKNOWN_PURPOSE`` — query purpose absent/empty (purpose binding is a
  mandatory obligation axis); verdict ``DENY``.
- ``EMPTY_TRACE`` — zero events, no authority to adjudicate; verdict ``DENY``.

All outputs (:meth:`ReferenceVerdict.to_dict`, :meth:`ReferenceEvent.to_dict`,
:meth:`ReferenceTrace.to_dict`, :meth:`ReferenceQuery.to_dict`) are
JSON-serializable; no wall clock, randomness or I/O anywhere.

Version
-------
``REFERENCE_SEMANTICS_VERSION = "clara.sacmat.reference-semantics-v1"``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Final

REFERENCE_SEMANTICS_VERSION: Final[str] = "clara.sacmat.reference-semantics-v1"

DECISION_ALLOW: Final[str] = "ALLOW"
DECISION_DENY: Final[str] = "DENY"
DECISION_INDETERMINATE: Final[str] = "INDETERMINATE"
DECISION_UNKNOWN: Final[str] = "UNKNOWN"

REASON_OK: Final[str] = "OK"
REASON_MISSING_LOGICAL_TIME: Final[str] = "MISSING_LOGICAL_TIME"
REASON_UNSUPPORTED_CONSTRUCT: Final[str] = "UNSUPPORTED_CONSTRUCT"
REASON_UNRESOLVABLE_DELEGATION: Final[str] = "UNRESOLVABLE_DELEGATION"
REASON_UNKNOWN_PURPOSE: Final[str] = "UNKNOWN_PURPOSE"
REASON_MALFORMED_EVENT: Final[str] = "MALFORMED_EVENT"
REASON_EMPTY_TRACE: Final[str] = "EMPTY_TRACE"

DETAIL_NO_AUTHORITY: Final[str] = "NO_AUTHORITY_IN_SCOPE"
DETAIL_OBLIGATION_FAULT: Final[str] = "OBLIGATION_FAULT"
DETAIL_REVOKED_CHAIN: Final[str] = "REVOKED_CHAIN"
DETAIL_DELEGATION_CYCLE: Final[str] = "DELEGATION_CYCLE"
DETAIL_UNSUPPORTED_KIND: Final[str] = "UNSUPPORTED_EVENT_KIND"
DETAIL_NO_DECISION_TIME: Final[str] = "NO_DECISION_TIME"
DETAIL_NO_EVENTS: Final[str] = "NO_EVENTS"
DETAIL_UNKNOWN_PURPOSE: Final[str] = "QUERY_PURPOSE_MISSING"

EVENT_KIND_GRANT: Final[str] = "GRANT"
EVENT_KIND_REVOKE: Final[str] = "REVOKE"
EVENT_KIND_DELEGATE: Final[str] = "DELEGATE"
EVENT_KIND_ACCESS: Final[str] = "ACCESS"
SUPPORTED_EVENT_KINDS: Final[frozenset[str]] = frozenset(
    {EVENT_KIND_GRANT, EVENT_KIND_REVOKE, EVENT_KIND_DELEGATE, EVENT_KIND_ACCESS}
)

_SCOPE_FIELDS: Final[tuple[str, ...]] = ("tenant", "resource", "purpose")

ScopeKey = tuple[str, str, str]


class ReferenceSemanticsError(Exception):
    """Stable-reason-code rejection of a malformed decision input."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(f"{reason_code}: {detail}" if detail else reason_code)
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class ReferenceEvent:
    """One history event; ``logical_time`` is mandatory and total.

    ``DELEGATE`` convention: ``policy_state`` carries the delegating source
    and ``principal`` is the delegate gaining authority.
    """

    principal: str
    tenant: str
    resource: str
    purpose: str
    policy_state: str
    logical_time: int
    kind: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

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
    def from_dict(cls, payload: Mapping[str, Any]) -> ReferenceEvent:
        missing = [key for key in cls.field_names() if key not in payload]
        if "logical_time" not in payload or payload.get("logical_time") is None:
            raise ReferenceSemanticsError(
                REASON_MISSING_LOGICAL_TIME,
                "event has no explicit logical_time (ambiguous no-time policy is refused)",
            )
        if missing:
            raise ReferenceSemanticsError(
                REASON_MALFORMED_EVENT, f"event missing fields: {sorted(missing)}"
            )
        values = {key: payload[key] for key in cls.field_names()}
        try:
            return cls(**values)
        except TypeError as exc:
            raise ReferenceSemanticsError(
                REASON_MALFORMED_EVENT, f"event malformed: {exc}"
            ) from exc


@dataclasses.dataclass(frozen=True)
class ReferenceTrace:
    """A policy history in strictly ascending logical-time order."""

    trace_id: str
    events: tuple[ReferenceEvent, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": REFERENCE_SEMANTICS_VERSION,
            "trace_id": self.trace_id,
            "events": [event.to_dict() for event in self.events],
        }

    @property
    def trace_sha256(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(canonical).hexdigest()

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ReferenceTrace:
        trace_id = payload.get("trace_id")
        if not isinstance(trace_id, str) or not trace_id:
            raise ReferenceSemanticsError(
                REASON_MALFORMED_EVENT, "trace_id must be a non-empty string"
            )
        raw_events = payload.get("events")
        if not isinstance(raw_events, Sequence) or isinstance(raw_events, str | bytes):
            raise ReferenceSemanticsError(REASON_MALFORMED_EVENT, "events must be a list")
        events = tuple(ReferenceEvent.from_dict(raw) for raw in raw_events)
        return cls(trace_id=trace_id, events=events)


@dataclasses.dataclass(frozen=True)
class ReferenceQuery:
    """One authorization request; ``decision_time`` is mandatory."""

    principal: str
    tenant: str
    resource: str
    purpose: str
    decision_time: int
    policy_state: str = ""
    obligations: Mapping[str, bool] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = dataclasses.asdict(self)
        payload["obligations"] = dict(self.obligations)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ReferenceQuery:
        try:
            return cls(
                principal=payload["principal"],
                tenant=payload["tenant"],
                resource=payload["resource"],
                purpose=payload.get("purpose", ""),
                decision_time=payload["decision_time"],
                policy_state=payload.get("policy_state", ""),
                obligations=dict(payload.get("obligations", {})),
            )
        except KeyError as exc:
            raise ReferenceSemanticsError(
                REASON_MALFORMED_EVENT, f"query missing field: {exc.args[0]}"
            ) from exc


@dataclasses.dataclass(frozen=True)
class ReferenceVerdict:
    """JSON-serializable four-valued decision with its stable reason."""

    decision: str
    reason_code: str
    detail: str = ""
    reference_version: str = REFERENCE_SEMANTICS_VERSION
    trace_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason_code": self.reason_code,
            "detail": self.detail,
            "reference_version": self.reference_version,
            "trace_sha256": self.trace_sha256,
        }


def _field(record: Any, name: str, default: Any = None) -> Any:
    """Read ``name`` from a mapping entry or an object attribute."""
    if isinstance(record, Mapping):
        return record.get(name, default)
    return getattr(record, name, default)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _events_of(trace: Any) -> tuple[Any, ...]:
    events = _field(trace, "events")
    if events is None:
        return ()
    if isinstance(events, str | bytes) or not isinstance(events, Sequence):
        raise ReferenceSemanticsError(REASON_MALFORMED_EVENT, "trace.events must be a sequence")
    return tuple(events)


def _validate_kind(record: Any, index: int) -> str:
    """Fail-closed shape check; returns the event kind."""
    kind = _field(record, "kind")
    principal = _field(record, "principal")
    logical_time = _field(record, "logical_time")
    if logical_time is None or not _is_int(logical_time):
        raise ReferenceSemanticsError(
            REASON_MISSING_LOGICAL_TIME,
            f"event[{index}] has no explicit integer logical_time "
            f"(ambiguous no-time policy is refused)",
        )
    for name, value in (("kind", kind), ("principal", principal)):
        if not isinstance(value, str) or not value:
            raise ReferenceSemanticsError(
                REASON_MALFORMED_EVENT,
                f"event[{index}].{name} must be a non-empty string, got {value!r}",
            )
    return kind


def _scope_of(record: Any) -> ScopeKey:
    return (
        str(_field(record, "tenant") or ""),
        str(_field(record, "resource") or ""),
        str(_field(record, "purpose") or ""),
    )


def _reaches(start: str, target: str, edges: Mapping[str, frozenset[str]]) -> bool:
    """Bounded reachability over ``edges`` (``seen`` set caps the walk)."""
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


def _cycle_path(start: str, target: str, edges: Mapping[str, frozenset[str]]) -> list[str]:
    """Shortest path ``start -> ... -> target`` over ``edges`` (``target`` last)."""
    frontier: list[tuple[str, list[str]]] = [(start, [start])]
    seen: set[str] = set()
    while frontier:
        node, path = frontier.pop(0)
        if node == target:
            return path
        if node in seen:
            continue
        seen.add(node)
        for nxt in sorted(edges.get(node, frozenset())):
            if nxt not in seen:
                frontier.append((nxt, [*path, nxt]))
    return [start]


def _chain_reaches_revoked(
    principal: str,
    delegated_from: Mapping[str, frozenset[str]],
    revoked_at: Mapping[str, int],
    decision_time: int,
) -> bool:
    """True if authority backing ``principal`` at ``decision_time`` is revoked.

    Authority flows delegator -> delegate, so the walk goes UPSTREAM over the
    inverted delegation graph (``delegated_from``: delegate -> delegators);
    any revoked actor in the chain backing the principal's authority is the
    transitivity witness. The ``seen`` set bounds the walk so a delegation
    cycle cannot hang it (cycles themselves are denied via cycle taint).
    """
    stack, seen = [principal], set()
    while stack:
        node = stack.pop()
        if node in revoked_at and revoked_at[node] <= decision_time:
            return True
        for delegator in delegated_from.get(node, frozenset()):
            if delegator not in seen:
                seen.add(delegator)
                stack.append(delegator)
    return False


def reference_decide(trace: Any, request: Any) -> ReferenceVerdict:
    """Decide ``request`` against policy history ``trace`` from first principles.

    Accepts a :class:`ReferenceTrace` (or any object/dict exposing ``events``
    of :class:`ReferenceEvent`-shaped records) and a :class:`ReferenceQuery`
    (or a dict of the same shape). Implements its own grant-ordering,
    delegation-transitivity, revocation-dominance and obligation-satisfaction
    logic; imports no candidate policy engine or baseline. Fail closed:
    missing logical time / malformed history -> INDETERMINATE, unknown
    purpose -> DENY, unsupported constructs -> UNKNOWN.
    """
    trace_sha = ""
    try:
        trace_sha = trace.trace_sha256  # type: ignore[attr-defined]
    except AttributeError:
        pass

    query = request if isinstance(request, ReferenceQuery) else ReferenceQuery.from_dict(request)
    try:
        raw_events = _events_of(trace)
    except ReferenceSemanticsError as exc:
        return ReferenceVerdict(
            DECISION_INDETERMINATE, exc.reason_code, exc.detail, trace_sha256=trace_sha
        )
    if not raw_events:
        return ReferenceVerdict(
            DECISION_DENY, REASON_EMPTY_TRACE, DETAIL_NO_EVENTS, trace_sha256=trace_sha
        )

    # ------------------------------------------------------------------
    # Pass 0 — shape validation. Missing logical time is INDETERMINATE
    # (temporal precedence undecidable) and malformed fields are
    # INDETERMINATE; unsupported constructs are UNKNOWN — each with a
    # stable reason, never coerced into a safe-looking verdict.
    # ------------------------------------------------------------------
    for index, record in enumerate(raw_events):
        try:
            kind = _validate_kind(record, index)
        except ReferenceSemanticsError as exc:
            return ReferenceVerdict(
                DECISION_INDETERMINATE, exc.reason_code, exc.detail, trace_sha256=trace_sha
            )
        if kind not in SUPPORTED_EVENT_KINDS:
            return ReferenceVerdict(
                DECISION_UNKNOWN,
                REASON_UNSUPPORTED_CONSTRUCT,
                f"{DETAIL_UNSUPPORTED_KIND}: {kind!r} at event[{index}]",
                trace_sha256=trace_sha,
            )

    if not _is_int(_field(query, "decision_time")):
        return ReferenceVerdict(
            DECISION_INDETERMINATE,
            REASON_MISSING_LOGICAL_TIME,
            DETAIL_NO_DECISION_TIME,
            trace_sha256=trace_sha,
        )
    decision_time: int = _field(query, "decision_time")

    # ------------------------------------------------------------------
    # Pass 1 — grant ordering + delegation transitivity + revocation
    # dominance + cycle taint, replayed in logical-time order.
    # ------------------------------------------------------------------
    # principal -> scope -> logical time authority was (re-)established
    authority: dict[str, dict[ScopeKey, int]] = {}
    # forward delegation edges: delegator -> {delegates} (cycle detection)
    forward_edges: dict[str, set[str]] = {}
    # inverted delegation edges: delegate -> {delegators} (revocation walks)
    delegated_from: dict[str, set[str]] = {}
    revoked_at: dict[str, int] = {}
    # (principal, scope) pairs whose authority is cycle-tainted
    cycle_taint: set[tuple[str, ScopeKey]] = set()

    for record in raw_events:
        kind = _field(record, "kind")
        principal = _field(record, "principal")
        scope = _scope_of(record)
        logical_time = _field(record, "logical_time")
        if kind == EVENT_KIND_GRANT:
            revoked_at.pop(principal, None)
            cycle_taint.discard((principal, scope))
            authority.setdefault(principal, {})[scope] = logical_time
        elif kind == EVENT_KIND_REVOKE:
            revoked_at[principal] = logical_time
            authority.pop(principal, None)
        elif kind == EVENT_KIND_DELEGATE:
            source = _field(record, "policy_state")
            if not isinstance(source, str) or not source:
                return ReferenceVerdict(
                    DECISION_INDETERMINATE,
                    REASON_MALFORMED_EVENT,
                    f"delegate at t={logical_time} has no delegator identity",
                    trace_sha256=trace_sha,
                )
            if scope not in authority.get(source, {}) or authority[source][scope] > logical_time:
                return ReferenceVerdict(
                    DECISION_UNKNOWN,
                    REASON_UNRESOLVABLE_DELEGATION,
                    f"delegate at t={logical_time} from {source!r} without active "
                    f"authority in scope {scope}",
                    trace_sha256=trace_sha,
                )
            forward_edges.setdefault(source, set()).add(principal)
            delegated_from.setdefault(principal, set()).add(source)
            if _reaches(
                principal,
                source,
                {node: frozenset(targets) for node, targets in forward_edges.items()},
            ):
                # The edge source -> principal closes a cycle: taint every
                # principal on the cycle in this scope (delegated consent
                # must be acyclic; tainted authority is never minted).
                for node in {
                    *_cycle_path(
                        principal,
                        source,
                        {node: frozenset(targets) for node, targets in forward_edges.items()},
                    ),
                    source,
                }:
                    cycle_taint.add((node, scope))
            revoked_at.pop(principal, None)
            authority.setdefault(principal, {})[scope] = logical_time
        # ACCESS records carry no state change in this replay.

    # ------------------------------------------------------------------
    # Pass 2 — query adjudication, fail-closed composition order.
    # ------------------------------------------------------------------
    # Purpose binding (obligation axis): a query without a concrete purpose
    # cannot be bound to the purpose-scoped authority and is denied outright.
    q_purpose = _field(query, "purpose")
    if not isinstance(q_purpose, str) or not q_purpose:
        return ReferenceVerdict(
            DECISION_DENY, REASON_UNKNOWN_PURPOSE, DETAIL_UNKNOWN_PURPOSE, trace_sha256=trace_sha
        )
    q_tenant = _field(query, "tenant")
    q_resource = _field(query, "resource")
    if (
        not isinstance(q_tenant, str)
        or not q_tenant
        or not isinstance(q_resource, str)
        or not q_resource
    ):
        return ReferenceVerdict(
            DECISION_INDETERMINATE,
            REASON_MALFORMED_EVENT,
            "query tenant/resource must be non-empty strings",
            trace_sha256=trace_sha,
        )
    q_principal = _field(query, "principal")
    if not isinstance(q_principal, str) or not q_principal:
        return ReferenceVerdict(
            DECISION_INDETERMINATE,
            REASON_MALFORMED_EVENT,
            "query principal must be a non-empty string",
            trace_sha256=trace_sha,
        )
    q_scope: ScopeKey = (q_tenant, q_resource, q_purpose)

    established_at = authority.get(q_principal, {}).get(q_scope)
    if established_at is None or established_at > decision_time:
        # No authority in scope, or grant not yet in force at the decision
        # time (expiry divergence): explicit deny, never an implicit permit.
        return ReferenceVerdict(
            DECISION_DENY, REASON_OK, DETAIL_NO_AUTHORITY, trace_sha256=trace_sha
        )

    # Revocation dominance: the query principal or any delegator backing its
    # authority is revoked at or before decision_time -> DENY. Re-grants are
    # honored (revoked_at cleared for the direct principal) but inherited
    # authority from a still-revoked upstream actor cannot be resurrected.
    if _chain_reaches_revoked(
        q_principal,
        {node: frozenset(srcs) for node, srcs in delegated_from.items()},
        revoked_at,
        decision_time,
    ):
        return ReferenceVerdict(
            DECISION_DENY, REASON_OK, DETAIL_REVOKED_CHAIN, trace_sha256=trace_sha
        )

    # Delegation cycles deny: tainted authority is never minted, and a fresh
    # direct GRANT (pass 1) is the only way a taint is cleared.
    if (q_principal, q_scope) in cycle_taint:
        return ReferenceVerdict(
            DECISION_DENY, REASON_OK, DETAIL_DELEGATION_CYCLE, trace_sha256=trace_sha
        )

    # Obligation satisfaction: every declared obligation must be strictly
    # satisfied — one fault denies (explicit-deny precedence over permits).
    obligations = _field(query, "obligations", {})
    if isinstance(obligations, Mapping) and any(
        value is not True for value in obligations.values()
    ):
        return ReferenceVerdict(
            DECISION_DENY, REASON_OK, DETAIL_OBLIGATION_FAULT, trace_sha256=trace_sha
        )

    return ReferenceVerdict(DECISION_ALLOW, REASON_OK, "", trace_sha256=trace_sha)


def reference_decide_json(
    trace_payload: Mapping[str, Any], query_payload: Mapping[str, Any]
) -> dict[str, Any]:
    """Parse JSON payloads, decide, and return a JSON-serializable verdict."""
    trace = ReferenceTrace.from_dict(trace_payload)
    query = ReferenceQuery.from_dict(query_payload)
    return reference_decide(trace, query).to_dict()
