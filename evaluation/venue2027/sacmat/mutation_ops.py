"""SACMAT-X07_mutation_ops — PolicyTrace mutation operator library.

Purpose
-------
Well-defined *policy/trace mutation operators* for "PolicyTrace: Temporal
Conformance Testing of Delegated Consent across Heterogeneous Policy
Engines" (``research/venue2027/VENUES/sacmat/RESEARCH_BLUEPRINT.md``, RQ2;
task contract
``research/venue2027/VENUES/sacmat/TASKS/SACMAT-X07_mutation_ops.md``).
Each operator injects EXACTLY ONE executable trace-level defect into a
validated :class:`~evaluation.venue2027.sacmat.policy_trace_dsl.PolicyTrace`
— the mutant families the RQ2 mutation-score denominators are built from
(revocation, delegation-expiry and policy-epoch / temporal-precedence
defects). Operators are pure functions over immutable
:class:`PolicyTrace` values: no clock, no randomness, no I/O, so identical
(inputs, operator_id) pairs yield byte-identical mutants.

Mutant families (one operator each, stable ``operator_id``):
- ``MUT_REMOVE_REVOKE`` — delete a REVOKE event (revocation omission):
  authority that should have been stripped survives to the replay.
- ``MUT_SWAP_GRANT_REVOKE`` — swap a directly adjacent GRANT/REVOKE pair
  (inverted temporal precedence): the revoke is moved ahead of the grant
  it was paired with, producing the REVOKE_BEFORE_GRANT trace-level
  error class. Because the DSL demands strictly ascending logical times,
  the swap exchanges the pair's sequence positions together with their
  logical times, so the event multiset is preserved while the precedence
  order is inverted.
- ``MUT_EXTEND_DELEGATION_EXPIRY`` — move the DELEGATE event carrying an
  expiry in its ``policy_state`` epoch token (``...@t<expiry>``) to the
  last logical time of the trace (stale delegation / expired-authority
  replay); refusal codes cover absent expiry, a non-integer expiry or a
  non-advancing rewrite.
- ``MUT_CHANGE_POLICY_VERSION`` — rewrite the ``policy_state`` epoch token
  of one non-terminal event to a different version string (stale-policy
  defect); the operator refuses no-op rewrites and events whose token
  already carries a stale-version marker (marker stacking).
- ``MUT_DROP_OBLIGATION`` — downgrade one ACCESS event to a redundant
  GRANT of the same scope (audit-obligation drop): the adjudicable
  request disappears from the history, so if it was the only access the
  last-access outcome degenerates to DENY-by-default.

Allowed input
-------------
- A :class:`PolicyTrace` produced by
  :func:`~evaluation.venue2027.sacmat.policy_trace_dsl.parse_policy_trace`
  (strictly ascending logical times, explicit ``logical_time`` on every
  event, version-pinned). Mutants are returned as the same frozen
  dataclass; :meth:`PolicyTrace.to_dict` stays JSON-serializable.
- A mutant :class:`Mutant` record: ``operator_id``, ``mutated_trace``,
  ``detail``. :meth:`Mutant.to_dict` is JSON-serializable.

Failure semantics (stable reason codes on ``MutationOpError``)
--------------------------------------------------------------
- ``UNKNOWN_OPERATOR`` — an operator id absent from
  :data:`MUTATION_REGISTRY` (typo'd or unregistered operator), or
  :func:`apply_operator` called with an unregistered callable.
- ``EVENT_NOT_FOUND`` — the operator's target event (by index) is out of
  range for the trace.
- ``WRONG_EVENT_KIND`` — the target event exists but is not of the kind
  the operator mutates (e.g. revoke removal pointed at an ACCESS).
- ``NO_ADJACENT_GRANT_REVOKE_PAIR`` — the swap operator found no directly
  adjacent GRANT/REVOKE pair to invert.
- ``NO_EXPIRY_TOKEN`` — the delegation-expiry operator's DELEGATE event
  carries no ``@t<expiry>`` epoch suffix.
- ``MALFORMED_EXPIRY`` — the expiry suffix is not a base-10 integer.
- ``NO_EXPIRY_ADVANCE`` — the rewritten expiry would not move the
  delegation past the trace's last logical time (no-op mutant refused).
- ``STALE_VERSION_MARKER_PRESENT`` — the policy-version operator's target
  event already carries the ``-v2@`` stale-version marker (marker
  stacking refused; this is also the operator's no-op guard, since a
  token that would be left unchanged by the rewrite necessarily already
  carries the marker).
- ``EMPTY_TRACE`` — a trace with zero events cannot be mutated.
- ``TRACE_UNCHANGED`` — defensive post-condition: a registered operator
  produced a byte-identical trace (never emitted as a mutant).

Structural well-formedness is re-established on every mutant via
:data:`POLICY_TRACE_DSL_VERSION`-pinned revalidation with
:func:`parse_policy_trace`; a mutant that cannot round-trip through the
independent DSL parser is refused with its underlying reason code
(structurally invalid mutants are never returned), and mutants are
forbidden from changing ``trace_id`` or reordering events silently.

Version
-------
``MUTATION_OPS_VERSION = "clara.sacmat.mutation-ops-v1"``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Final

from evaluation.venue2027.sacmat.policy_trace_dsl import (
    EVENT_KIND_ACCESS,
    EVENT_KIND_DELEGATE,
    EVENT_KIND_GRANT,
    EVENT_KIND_REVOKE,
    PolicyTrace,
    PolicyTraceError,
    parse_policy_trace,
)

MUTATION_OPS_VERSION: Final[str] = "clara.sacmat.mutation-ops-v1"

MUT_REMOVE_REVOKE: Final[str] = "MUT_REMOVE_REVOKE"
MUT_SWAP_GRANT_REVOKE: Final[str] = "MUT_SWAP_GRANT_REVOKE"
MUT_EXTEND_DELEGATION_EXPIRY: Final[str] = "MUT_EXTEND_DELEGATION_EXPIRY"
MUT_CHANGE_POLICY_VERSION: Final[str] = "MUT_CHANGE_POLICY_VERSION"
MUT_DROP_OBLIGATION: Final[str] = "MUT_DROP_OBLIGATION"

REASON_UNKNOWN_OPERATOR: Final[str] = "UNKNOWN_OPERATOR"
REASON_EVENT_NOT_FOUND: Final[str] = "EVENT_NOT_FOUND"
REASON_WRONG_EVENT_KIND: Final[str] = "WRONG_EVENT_KIND"
REASON_NO_ADJACENT_GRANT_REVOKE_PAIR: Final[str] = "NO_ADJACENT_GRANT_REVOKE_PAIR"
REASON_NO_EXPIRY_TOKEN: Final[str] = "NO_EXPIRY_TOKEN"
REASON_MALFORMED_EXPIRY: Final[str] = "MALFORMED_EXPIRY"
REASON_NO_EXPIRY_ADVANCE: Final[str] = "NO_EXPIRY_ADVANCE"
REASON_STALE_VERSION_MARKER_PRESENT: Final[str] = "STALE_VERSION_MARKER_PRESENT"
REASON_EMPTY_TRACE: Final[str] = "EMPTY_TRACE"
REASON_TRACE_UNCHANGED: Final[str] = "TRACE_UNCHANGED"

EXPIRY_SUFFIX: Final[str] = "@t"
STALE_VERSION_MARKER: Final[str] = "-v2@"


class MutationOpError(Exception):
    """Fail-closed mutation refusal carrying a stable reason code."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(f"{reason_code}: {detail}" if detail else reason_code)
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class Mutant:
    """One executable mutant: operator id + mutated trace + provenance."""

    operator_id: str
    mutated_trace: PolicyTrace
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator_id": self.operator_id,
            "detail": self.detail,
            "mutated_trace": self.mutated_trace.to_dict(),
            "mutation_ops_version": MUTATION_OPS_VERSION,
        }


def _validate_target(trace: PolicyTrace, index: int, kind: str, operator_id: str) -> None:
    """Fail closed unless ``trace.events[index]`` exists and has ``kind``."""
    if not trace.events:
        raise MutationOpError(
            REASON_EMPTY_TRACE, f"{operator_id}: trace {trace.trace_id!r} has no events"
        )
    if not 0 <= index < len(trace.events):
        raise MutationOpError(
            REASON_EVENT_NOT_FOUND,
            f"{operator_id}: event index {index} out of range for "
            f"{len(trace.events)} event(s) in trace {trace.trace_id!r}",
        )
    event = trace.events[index]
    if event.kind != kind:
        raise MutationOpError(
            REASON_WRONG_EVENT_KIND,
            f"{operator_id}: event[{index}] is {event.kind}, expected {kind} "
            f"in trace {trace.trace_id!r}",
        )


def _revalidated(trace: PolicyTrace, operator_id: str) -> PolicyTrace:
    """Round-trip ``trace`` through the independent DSL parser.

    A mutant is only returned if the DSL (version-pinned) accepts it as a
    well-formed, strictly ordered history. Any DSL refusal — malformed
    fields, unordered/duplicate timestamps, schema mismatch, empty trace —
    propagates as a fail-closed refusal instead of a broken mutant.
    """
    try:
        return parse_policy_trace(trace.to_dict())
    except PolicyTraceError as exc:
        raise MutationOpError(
            exc.reason_code,
            f"{operator_id}: mutated trace rejected by DSL validation: {exc.detail}",
        ) from exc


def _assert_mutated(original: PolicyTrace, mutant: PolicyTrace, operator_id: str) -> None:
    if mutant.trace_sha256 == original.trace_sha256:
        raise MutationOpError(
            REASON_TRACE_UNCHANGED,
            f"{operator_id}: mutant is byte-identical to the original trace "
            f"{original.trace_id!r}",
        )


def mutate_remove_revoke(trace: PolicyTrace, event_index: int) -> PolicyTrace:
    """MUT_REMOVE_REVOKE — revocation omission.

    Deletes the REVOKE event at ``event_index`` so the authority it should
    have stripped survives to the replay (revoked-actor replay /
    transitivity defect). The remaining events keep their original logical
    times, so strict ordering is preserved by construction.
    """
    _validate_target(trace, event_index, EVENT_KIND_REVOKE, MUT_REMOVE_REVOKE)
    remaining = [event for i, event in enumerate(trace.events) if i != event_index]
    mutated = PolicyTrace(trace_id=trace.trace_id, events=tuple(remaining))
    mutated = _revalidated(mutated, MUT_REMOVE_REVOKE)
    _assert_mutated(trace, mutated, MUT_REMOVE_REVOKE)
    return mutated


def mutate_swap_grant_revoke(trace: PolicyTrace, event_index: int) -> PolicyTrace:
    """MUT_SWAP_GRANT_REVOKE — inverted temporal precedence.

    Inverts a directly adjacent GRANT (at ``event_index``) / REVOKE (at
    ``event_index + 1``) pair: the REVOKE is moved one slot *earlier* in
    sequence and its logical time set just below the grant's, so the
    revoke precedes the grant it was paired with (REVOKE_BEFORE_GRANT
    class) while the sequence stays strictly ascending — the DSL refuses
    reordered histories, so the inversion must respect the total order.
    Only *directly adjacent* pairs are invertible: a non-adjacent swap
    would shift intervening events' relative order semantics.
    """
    _validate_target(trace, event_index, EVENT_KIND_GRANT, MUT_SWAP_GRANT_REVOKE)
    if event_index + 1 >= len(trace.events):
        raise MutationOpError(
            REASON_NO_ADJACENT_GRANT_REVOKE_PAIR,
            f"{MUT_SWAP_GRANT_REVOKE}: GRANT at index {event_index} has no "
            f"successor in trace {trace.trace_id!r}",
        )
    revoke_event = trace.events[event_index + 1]
    if revoke_event.kind != EVENT_KIND_REVOKE:
        raise MutationOpError(
            REASON_NO_ADJACENT_GRANT_REVOKE_PAIR,
            f"{MUT_SWAP_GRANT_REVOKE}: event[{event_index + 1}] is "
            f"{revoke_event.kind}, expected a directly adjacent REVOKE pair "
            f"in trace {trace.trace_id!r}",
        )
    grant_event = trace.events[event_index]
    grant_time = grant_event.logical_time
    events = list(trace.events)
    events[event_index] = dataclasses.replace(revoke_event, logical_time=max(0, grant_time - 1))
    events[event_index + 1] = dataclasses.replace(grant_event, logical_time=grant_time)
    mutated = PolicyTrace(trace_id=trace.trace_id, events=tuple(events))
    mutated = _revalidated(mutated, MUT_SWAP_GRANT_REVOKE)
    _assert_mutated(trace, mutated, MUT_SWAP_GRANT_REVOKE)
    return mutated


def _split_expiry(policy_state: str) -> tuple[str, int]:
    """Split a ``base@t<expiry>`` epoch token; refuse absent/bad expiry."""
    marker = policy_state.rfind(EXPIRY_SUFFIX)
    if marker <= 0 or marker + len(EXPIRY_SUFFIX) >= len(policy_state):
        raise MutationOpError(
            REASON_NO_EXPIRY_TOKEN,
            f"{MUT_EXTEND_DELEGATION_EXPIRY}: policy_state {policy_state!r} "
            f"carries no {EXPIRY_SUFFIX}<expiry> suffix",
        )
    base = policy_state[:marker]
    raw = policy_state[marker + len(EXPIRY_SUFFIX) :]
    try:
        return base, int(raw, 10)
    except ValueError as exc:
        raise MutationOpError(
            REASON_MALFORMED_EXPIRY,
            f"{MUT_EXTEND_DELEGATION_EXPIRY}: expiry suffix {raw!r} is not a " f"base-10 integer",
        ) from exc


def mutate_extend_delegation_expiry(trace: PolicyTrace, event_index: int) -> PolicyTrace:
    """MUT_EXTEND_DELEGATION_EXPIRY — stale-delegation defect.

    Rewrites the DELEGATE event's ``policy_state`` epoch token
    (``base@t<expiry>``) so the delegation's expiry moves to the trace's
    last logical time: the delegation is still "valid" at replay time even
    though it should have lapsed (expired-authority replay). Refuses
    delegates without an expiry token, non-integer expiries and rewrites
    that would not actually advance the expiry past the previous value
    (no-op mutants).
    """
    _validate_target(trace, event_index, EVENT_KIND_DELEGATE, MUT_EXTEND_DELEGATION_EXPIRY)
    delegate_event = trace.events[event_index]
    base, current_expiry = _split_expiry(delegate_event.policy_state)
    last_time = max(event.logical_time for event in trace.events)
    if last_time <= current_expiry:
        raise MutationOpError(
            REASON_NO_EXPIRY_ADVANCE,
            f"{MUT_EXTEND_DELEGATION_EXPIRY}: last logical_time {last_time} "
            f"does not exceed current expiry {current_expiry}; the rewrite "
            f"would not extend the delegation",
        )
    new_state = f"{base}{EXPIRY_SUFFIX}{last_time}"
    mutated_event = dataclasses.replace(delegate_event, policy_state=new_state)
    events = list(trace.events)
    events[event_index] = mutated_event
    mutated = PolicyTrace(trace_id=trace.trace_id, events=tuple(events))
    mutated = _revalidated(mutated, MUT_EXTEND_DELEGATION_EXPIRY)
    _assert_mutated(trace, mutated, MUT_EXTEND_DELEGATION_EXPIRY)
    return mutated


def mutate_change_policy_version(trace: PolicyTrace, event_index: int) -> PolicyTrace:
    """MUT_CHANGE_POLICY_VERSION — stale-policy epoch defect.

    Rewrites one non-terminal event's ``policy_state`` epoch token to
    ``<base>-v2@t<epoch-of-next-event>``: the event now references a policy
    version/epoch that differs from the one its successor was issued
    under, the stale-policy defect static decision coverage cannot see.
    The terminal (last) event is not a valid target — its epoch token is
    the reference point, and mutating it would leave nothing to diverge
    from. Refuses events whose token already carries the ``-v2@``
    stale-version marker: marker stacking would fabricate a fresh defect
    out of an already mutated token, and a token the rewrite would leave
    unchanged necessarily already carries the marker, so this refusal is
    also the operator's no-op guard.
    """
    if not trace.events:
        raise MutationOpError(
            REASON_EMPTY_TRACE,
            f"{MUT_CHANGE_POLICY_VERSION}: trace {trace.trace_id!r} has no events",
        )
    if not 0 <= event_index < len(trace.events) - 1:
        raise MutationOpError(
            REASON_EVENT_NOT_FOUND,
            f"{MUT_CHANGE_POLICY_VERSION}: event index {event_index} is not a "
            f"non-terminal index of a {len(trace.events)}-event trace "
            f"{trace.trace_id!r}",
        )
    event = trace.events[event_index]
    if STALE_VERSION_MARKER in event.policy_state:
        raise MutationOpError(
            REASON_STALE_VERSION_MARKER_PRESENT,
            f"{MUT_CHANGE_POLICY_VERSION}: event[{event_index}].policy_state "
            f"{event.policy_state!r} already carries the stale-version marker "
            f"{STALE_VERSION_MARKER!r} in trace {trace.trace_id!r}",
        )
    successor = trace.events[event_index + 1]
    new_state = f"{event.policy_state}{STALE_VERSION_MARKER}t{successor.logical_time}"
    mutated_event = dataclasses.replace(event, policy_state=new_state)
    events = list(trace.events)
    events[event_index] = mutated_event
    mutated = PolicyTrace(trace_id=trace.trace_id, events=tuple(events))
    mutated = _revalidated(mutated, MUT_CHANGE_POLICY_VERSION)
    _assert_mutated(trace, mutated, MUT_CHANGE_POLICY_VERSION)
    return mutated


def mutate_drop_obligation(trace: PolicyTrace, event_index: int) -> PolicyTrace:
    """MUT_DROP_OBLIGATION — audit-obligation drop.

    Downgrades the ACCESS event at ``event_index`` to a redundant GRANT of
    the same ``(tenant, resource, purpose)`` scope by the access
    principal (a re-grant of authority the principal already holds — a
    no-op for any correct engine). The adjudicable request therefore
    disappears from the history: if it was the only access, the replay
    has none left and the last-access outcome degenerates to
    DENY-by-default — the dropped-obligation observable. The kind rewrite
    keeps every other field, so ordering is preserved by construction.
    """
    _validate_target(trace, event_index, EVENT_KIND_ACCESS, MUT_DROP_OBLIGATION)
    access_event = trace.events[event_index]
    downgraded = dataclasses.replace(access_event, kind=EVENT_KIND_GRANT)
    events = list(trace.events)
    events[event_index] = downgraded
    mutated = PolicyTrace(trace_id=trace.trace_id, events=tuple(events))
    mutated = _revalidated(mutated, MUT_DROP_OBLIGATION)
    _assert_mutated(trace, mutated, MUT_DROP_OBLIGATION)
    return mutated


OperatorFn = Callable[[PolicyTrace, int], PolicyTrace]

MUTATION_REGISTRY: Final[Mapping[str, OperatorFn]] = {
    MUT_REMOVE_REVOKE: mutate_remove_revoke,
    MUT_SWAP_GRANT_REVOKE: mutate_swap_grant_revoke,
    MUT_EXTEND_DELEGATION_EXPIRY: mutate_extend_delegation_expiry,
    MUT_CHANGE_POLICY_VERSION: mutate_change_policy_version,
    MUT_DROP_OBLIGATION: mutate_drop_obligation,
}


def apply_operator(trace: PolicyTrace, operator_id: str, event_index: int) -> Mutant:
    """Apply one registered operator; return the mutant record.

    Refuses unknown operator ids with ``UNKNOWN_OPERATOR`` — an unregistered
    operator is never silently mapped onto a default. Also refuses
    callables that were registered behind a different name than their
    documented id (registry/implementation drift).
    """
    operator_fn = MUTATION_REGISTRY.get(operator_id)
    if operator_fn is None:
        raise MutationOpError(
            REASON_UNKNOWN_OPERATOR,
            f"operator id {operator_id!r} is not registered (known: "
            f"{sorted(MUTATION_REGISTRY)})",
        )
    mutated_trace = operator_fn(trace, event_index)
    return Mutant(operator_id=operator_id, mutated_trace=mutated_trace, detail=operator_id)


def apply_all(trace: PolicyTrace, *, event_indices: Sequence[int] | None = None) -> list[Mutant]:
    """Apply every registered operator at every applicable target index.

    For each operator, candidate indices are ``event_indices`` if given,
    otherwise every event index. Targets the operator structurally refuses
    (wrong kind, out of range, no adjacent pair, no expiry token, no-op
    rewrite) are skipped silently *as non-applicable targets* — refusing
    the whole sweep because one operator cannot apply to one event would
    starve the mutation score denominator; refusals for unknown operators
    or DSL-rejected mutants still propagate fail-closed. The result is
    ordered by (operator_id, target index) — deterministic, duplicate-free
    by hash, and every mutant provably differs from the original.
    """
    indices = list(event_indices) if event_indices is not None else list(range(len(trace.events)))
    mutants: list[Mutant] = []
    seen_hashes: set[str] = set()
    for operator_id in sorted(MUTATION_REGISTRY):
        operator_fn = MUTATION_REGISTRY[operator_id]
        for index in indices:
            try:
                mutant = Mutant(
                    operator_id=operator_id,
                    mutated_trace=operator_fn(trace, index),
                    detail=f"target=event[{index}]",
                )
            except MutationOpError as exc:
                if exc.reason_code == REASON_UNKNOWN_OPERATOR:
                    raise
                continue
            if mutant.mutated_trace.trace_sha256 in seen_hashes:
                continue
            seen_hashes.add(mutant.mutated_trace.trace_sha256)
            mutants.append(mutant)
    return mutants
