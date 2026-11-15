"""SACMAT-X06_temporal_generator — bounded temporal trace corpus generator.

Purpose
-------
Deterministic corpus generator for "PolicyTrace: Temporal Conformance Testing
of Delegated Consent across Heterogeneous Policy Engines"
(``research/venue2027/VENUES/sacmat/RESEARCH_BLUEPRINT.md``, RQ1; task
contract ``research/venue2027/VENUES/sacmat/TASKS/SACMAT-X06_temporal_generator.md``).
:func:`generate_traces` emits a corpus of delegated-consent policy histories
in the audited DSL shape (:mod:`evaluation.venue2027.sacmat.policy_trace_dsl`,
task SACMAT-X01) that bounds the three study variables — trace ``depth``,
delegation ``hops`` and ``mutation_points`` — and implements the RQ1
mechanism: every generated temporal bug (a trace-level policy error that
static rule/decision coverage cannot see) is PAIRED with a static
request-matched control — the SAME authorization request replayed against the
un-mutated history — so any decision/outcome-only comparison sees "no
difference" and only the temporal witness discriminates. VALID traces are
always preserved in the corpus and verified to replay PERMIT with zero
findings.

Corpus layout (deterministic, pure integer arithmetic — no clock, no PRNG,
no I/O):

- exactly one ``valid`` trace: grant -> ``hops`` delegations -> terminal
  request by the deepest delegate (or the grantee when ``hops == 0``);
- for each of at most ``mutation_points`` distinct bug classes (chosen by a
  seed-rotated deterministic order, restricted to hop-eligible classes) one
  ``bug`` trace carrying EXACTLY ONE temporal mutation plus its ``control``
  twin: same request, same event budget, no temporal mutation.

Bug classes (each instantiating one mutation point):

- ``REVOKE_BEFORE_GRANT`` — an intruder revoke is inserted BEFORE the grant
  (temporal reordering); the terminal request still PERMITs, so only the
  trace-level ``REVOKE_BEFORE_GRANT`` finding discriminates bug from control.
- ``DELEGATION_CYCLE`` (requires ``hops >= 2``) — the last delegation is
  retargeted back to the first delegate, closing a cycle; the request still
  PERMITs under the cycle-tainted authority and only ``DELEGATION_CYCLE``
  discriminates. The pair's request targets the first delegate so the cycle
  is the sole witness.
- ``REVOKED_ACTOR_TRANSITIVITY`` (requires ``hops >= 1``) — the root is
  revoked after the delegation chain but before the replay of a request by a
  downstream delegatee (revocation-before-replay); the correct outcome is
  ``DENY`` with the ``REVOKED_ACTOR_TRANSITIVITY`` witness while the control
  PERMITs.
- ``TIME_TRAVEL_ACCESS`` — a copy of the request is replayed at logical time
  0, BEFORE any authority exists; the early replay yields
  ``UNESTABLISHED_AUTHORITY`` and only that witness discriminates.

Allowed input
-------------
``generate_traces(seed, depth, hops, mutation_points)`` with a non-negative
int ``seed``; ``depth`` the maximum number of events any emitted trace may
carry (``MIN_DEPTH..MAX_DEPTH``); ``hops`` the delegation-hop count of the
base chain (``MIN_HOPS..MAX_HOPS``, and ``hops + 3 <= depth`` so grant,
request and one mutation slot always fit inside the depth budget);
``mutation_points`` the maximum number of distinct temporal bug classes the
corpus instantiates (``MIN_MUTATION_POINTS..MAX_MUTATION_POINTS``; ``0``
yields a valid-only corpus). ``DELEGATE`` events follow the DSL convention:
``principal`` is the delegating source and ``policy_state`` the delegatee.

Failure semantics (stable reason codes on ``TemporalGeneratorError``)
---------------------------------------------------------------------
- ``INVALID_SEED`` / ``DEPTH_OUT_OF_RANGE`` / ``HOPS_OUT_OF_RANGE`` /
  ``MUTATION_POINTS_OUT_OF_RANGE`` — parameter outside its declared bound
  (bools and non-ints included).
- ``HOPS_EXCEED_DEPTH`` — the chain plus request plus one mutation slot does
  not fit inside the depth budget.
- ``DUPLICATE_TRACE_ID`` / ``DUPLICATE_TRACE_HASH`` — corpus uniqueness
  invariant violated (never silently deduplicated).
- ``UNPAIRED_BUG`` / ``UNPAIRED_CONTROL`` / ``REQUEST_MISMATCH`` /
  ``PAIRING_MISMATCH`` — :func:`assert_all_paired` pairing invariants.
- ``INVALID_TRACE_RECORD`` — a record is not a well-formed corpus record.
- ``VALID_TRACE_BROKEN`` — a generated valid/control trace does not replay
  PERMIT with zero findings (generator bug; fail closed).
- ``MUTATION_NOT_OBSERVABLE`` — a generated bug trace does not produce its
  target witness finding under the independent DSL replay (fail closed; a
  silently non-discriminating trace is never emitted).

Every emitted record embeds ``expected_outcome`` / ``expected_findings``
derived from a real :func:`policy_trace_dsl.evaluate_trace` replay;
:func:`verify_corpus` re-derives them and refuses any tampering. All outputs
are JSON-serializable; identical inputs give byte-identical corpora.

Version
-------
``GENERATOR_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final

from evaluation.venue2027.sacmat.policy_trace_dsl import (
    EVENT_KIND_ACCESS,
    EVENT_KIND_DELEGATE,
    EVENT_KIND_GRANT,
    EVENT_KIND_REVOKE,
    FINDING_DELEGATION_CYCLE,
    FINDING_REVOKE_BEFORE_GRANT,
    FINDING_REVOKED_ACTOR_TRANSITIVITY,
    FINDING_UNESTABLISHED_AUTHORITY,
    OUTCOME_PERMIT,
    POLICY_TRACE_DSL_VERSION,
    PolicyTraceError,
    evaluate_trace,
    parse_policy_trace,
)

GENERATOR_VERSION: Final[str] = "1.0.0"
CORPUS_SCHEMA_VERSION: Final[str] = "clara.venue2027.sacmat.temporal_corpus.v1"

ROLE_VALID: Final[str] = "valid"
ROLE_BUG: Final[str] = "bug"
ROLE_CONTROL: Final[str] = "control"
_ROLES: Final[frozenset[str]] = frozenset({ROLE_VALID, ROLE_BUG, ROLE_CONTROL})

BUG_CLASS_REVOKE_BEFORE_GRANT: Final[str] = "REVOKE_BEFORE_GRANT"
BUG_CLASS_DELEGATION_CYCLE: Final[str] = "DELEGATION_CYCLE"
BUG_CLASS_REVOKED_ACTOR_TRANSITIVITY: Final[str] = "REVOKED_ACTOR_TRANSITIVITY"
BUG_CLASS_TIME_TRAVEL_ACCESS: Final[str] = "TIME_TRAVEL_ACCESS"

#: Canonical bug-class order (also the deterministic rotation order).
BUG_CLASSES: Final[tuple[str, ...]] = (
    BUG_CLASS_REVOKE_BEFORE_GRANT,
    BUG_CLASS_DELEGATION_CYCLE,
    BUG_CLASS_REVOKED_ACTOR_TRANSITIVITY,
    BUG_CLASS_TIME_TRAVEL_ACCESS,
)

MIN_DEPTH: Final[int] = 3
MAX_DEPTH: Final[int] = 12
MIN_HOPS: Final[int] = 0
MAX_HOPS: Final[int] = 4
MIN_MUTATION_POINTS: Final[int] = 0
MAX_MUTATION_POINTS: Final[int] = len(BUG_CLASSES)

#: Events reserved by the depth budget beyond the ``hops`` delegations: the
#: grant, the terminal request and one mutation slot.
_MIN_EVENT_BUDGET: Final[int] = 3

TENANT: Final[str] = "synthetic-tenant"
RESOURCE: Final[str] = "medication_record"
PURPOSE: Final[str] = "self_care"

RC_INVALID_SEED: Final[str] = "INVALID_SEED"
RC_DEPTH_OUT_OF_RANGE: Final[str] = "DEPTH_OUT_OF_RANGE"
RC_HOPS_OUT_OF_RANGE: Final[str] = "HOPS_OUT_OF_RANGE"
RC_MUTATION_POINTS_OUT_OF_RANGE: Final[str] = "MUTATION_POINTS_OUT_OF_RANGE"
RC_HOPS_EXCEED_DEPTH: Final[str] = "HOPS_EXCEED_DEPTH"
RC_DUPLICATE_TRACE_ID: Final[str] = "DUPLICATE_TRACE_ID"
RC_DUPLICATE_TRACE_HASH: Final[str] = "DUPLICATE_TRACE_HASH"
RC_UNPAIRED_BUG: Final[str] = "UNPAIRED_BUG"
RC_UNPAIRED_CONTROL: Final[str] = "UNPAIRED_CONTROL"
RC_REQUEST_MISMATCH: Final[str] = "REQUEST_MISMATCH"
RC_PAIRING_MISMATCH: Final[str] = "PAIRING_MISMATCH"
RC_INVALID_TRACE_RECORD: Final[str] = "INVALID_TRACE_RECORD"
RC_VALID_TRACE_BROKEN: Final[str] = "VALID_TRACE_BROKEN"
RC_MUTATION_NOT_OBSERVABLE: Final[str] = "MUTATION_NOT_OBSERVABLE"

#: bug class -> (minimum delegation hops, required witness finding kind).
_BUG_CLASS_SPECS: Final[dict[str, tuple[int, str]]] = {
    BUG_CLASS_REVOKE_BEFORE_GRANT: (0, FINDING_REVOKE_BEFORE_GRANT),
    BUG_CLASS_DELEGATION_CYCLE: (2, FINDING_DELEGATION_CYCLE),
    BUG_CLASS_REVOKED_ACTOR_TRANSITIVITY: (1, FINDING_REVOKED_ACTOR_TRANSITIVITY),
    BUG_CLASS_TIME_TRAVEL_ACCESS: (0, FINDING_UNESTABLISHED_AUTHORITY),
}


class TemporalGeneratorError(Exception):
    """Fail-closed generator refusal carrying a stable reason code."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(f"{reason_code}: {detail}" if detail else reason_code)
        self.reason_code = reason_code
        self.detail = detail


def _int_param(value: Any, name: str, low: int, high: int, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TemporalGeneratorError(code, f"{name} must be an int, got {value!r}")
    if not low <= value <= high:
        raise TemporalGeneratorError(code, f"{name}={value} outside [{low}, {high}]")
    return value


def _validate_params(seed: Any, depth: Any, hops: Any, mutation_points: Any) -> None:
    _int_param(seed, "seed", 0, 2**63 - 1, RC_INVALID_SEED)
    _int_param(depth, "depth", MIN_DEPTH, MAX_DEPTH, RC_DEPTH_OUT_OF_RANGE)
    _int_param(hops, "hops", MIN_HOPS, MAX_HOPS, RC_HOPS_OUT_OF_RANGE)
    _int_param(
        mutation_points,
        "mutation_points",
        MIN_MUTATION_POINTS,
        MAX_MUTATION_POINTS,
        RC_MUTATION_POINTS_OUT_OF_RANGE,
    )
    if hops + _MIN_EVENT_BUDGET > depth:
        raise TemporalGeneratorError(
            RC_HOPS_EXCEED_DEPTH,
            f"hops={hops} + {_MIN_EVENT_BUDGET} (grant, request, mutation slot) "
            f"exceeds depth={depth}",
        )


def _event(
    kind: str, principal: str, logical_time: int, *, policy_state: str, token: int
) -> dict[str, Any]:
    return {
        "principal": principal,
        "tenant": TENANT,
        "resource": RESOURCE,
        "purpose": PURPOSE,
        "policy_state": policy_state,
        "logical_time": logical_time,
        "kind": kind,
    }


def _principal_token(seed: int) -> int:
    return seed % 97


def _root(token: int) -> str:
    return f"root-{token}"


def _delegate(token: int, index: int) -> str:
    return f"delegate-{token}-{index}"


def _intruder(token: int) -> str:
    return f"intruder-{token}"


def _epoch(seed: int) -> str:
    return f"consent-epoch-{(seed % 16) + 1}"


def _base_chain(seed: int, hops: int) -> list[dict[str, Any]]:
    """GRANT at t=1 plus ``hops`` DELEGATE events at t=2..hops+1 (DSL convention)."""
    token = _principal_token(seed)
    epoch = _epoch(seed)
    chain = [_event(EVENT_KIND_GRANT, _root(token), 1, policy_state=epoch, token=token)]
    for i in range(1, hops + 1):
        source = _root(token) if i == 1 else _delegate(token, i - 1)
        chain.append(
            _event(
                EVENT_KIND_DELEGATE,
                source,
                1 + i,
                policy_state=_delegate(token, i),
                token=token,
            )
        )
    return chain


def _deep_actor(seed: int, hops: int) -> str:
    token = _principal_token(seed)
    return _root(token) if hops == 0 else _delegate(token, hops)


def _request(actor: str, logical_time: int) -> dict[str, Any]:
    return {
        "principal": actor,
        "tenant": TENANT,
        "resource": RESOURCE,
        "purpose": PURPOSE,
        "logical_time": logical_time,
    }


def _access_event(request: Mapping[str, Any], token: int) -> dict[str, Any]:
    return _event(
        EVENT_KIND_ACCESS,
        str(request["principal"]),
        int(request["logical_time"]),
        policy_state=_epoch(0),
        token=token,
    )


def _clean_events(seed: int, hops: int, request: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The un-mutated history: base chain plus the paired request (control shape)."""
    token = _principal_token(seed)
    return _base_chain(seed, hops) + [_access_event(request, token)]


def _bug_events(
    bug_class: str, seed: int, hops: int, request: Mapping[str, Any]
) -> list[dict[str, Any]]:
    token = _principal_token(seed)
    epoch = _epoch(seed)
    if bug_class == BUG_CLASS_REVOKE_BEFORE_GRANT:
        events = [_event(EVENT_KIND_REVOKE, _intruder(token), 1, policy_state=epoch, token=token)]
        events += [_event(EVENT_KIND_GRANT, _root(token), 2, policy_state=epoch, token=token)]
        for i in range(1, hops + 1):
            source = _root(token) if i == 1 else _delegate(token, i - 1)
            events.append(
                _event(
                    EVENT_KIND_DELEGATE,
                    source,
                    2 + i,
                    policy_state=_delegate(token, i),
                    token=token,
                )
            )
        events.append(_access_event(request, token))
        return events
    if bug_class == BUG_CLASS_REVOKED_ACTOR_TRANSITIVITY:
        events = _base_chain(seed, hops)
        events.append(
            _event(EVENT_KIND_REVOKE, _root(token), hops + 2, policy_state=epoch, token=token)
        )
        events.append(_access_event(request, token))
        return events
    if bug_class == BUG_CLASS_DELEGATION_CYCLE:
        events = _base_chain(seed, hops - 1)
        events.append(
            _event(
                EVENT_KIND_DELEGATE,
                _delegate(token, hops - 1),
                hops + 1,
                policy_state=_delegate(token, 1),
                token=token,
            )
        )
        events.append(_access_event(request, token))
        return events
    if bug_class == BUG_CLASS_TIME_TRAVEL_ACCESS:
        early = dict(request)
        early["logical_time"] = 0
        return (
            [_access_event(early, token)]
            + _base_chain(seed, hops)
            + [_access_event(request, token)]
        )
    raise TemporalGeneratorError(RC_INVALID_TRACE_RECORD, f"unknown bug class {bug_class!r}")


def _class_request(bug_class: str, seed: int, hops: int, t_req: int) -> dict[str, Any]:
    if bug_class == BUG_CLASS_DELEGATION_CYCLE:
        return _request(_delegate(_principal_token(seed), 1), t_req)
    return _request(_deep_actor(seed, hops), t_req)


def _replay(
    trace_id: str, events: Sequence[Mapping[str, Any]]
) -> tuple[str, list[dict[str, Any]], str]:
    payload = {
        "version": POLICY_TRACE_DSL_VERSION,
        "trace_id": trace_id,
        "events": [dict(event) for event in events],
    }
    try:
        trace = parse_policy_trace(payload)
    except PolicyTraceError as exc:
        raise TemporalGeneratorError(
            RC_INVALID_TRACE_RECORD, f"{trace_id}: {exc.reason_code}: {exc.detail}"
        ) from exc
    verdict = evaluate_trace(trace)
    return verdict.outcome, [finding.to_dict() for finding in verdict.findings], trace.trace_sha256


def _record(
    trace_id: str,
    role: str,
    bug_class: str | None,
    paired_trace_id: str | None,
    request: Mapping[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    outcome, findings, sha = _replay(trace_id, events)
    if role in (ROLE_VALID, ROLE_CONTROL):
        if outcome != OUTCOME_PERMIT or findings:
            raise TemporalGeneratorError(
                RC_VALID_TRACE_BROKEN,
                f"{trace_id}: replayed {outcome} with findings {findings}",
            )
    else:
        required = _BUG_CLASS_SPECS[str(bug_class)][1]
        if not any(finding["kind"] == required for finding in findings):
            raise TemporalGeneratorError(
                RC_MUTATION_NOT_OBSERVABLE,
                f"{trace_id}: witness {required} absent from findings {findings}",
            )
    return {
        "version": GENERATOR_VERSION,
        "corpus_schema_version": CORPUS_SCHEMA_VERSION,
        "dsl_version": POLICY_TRACE_DSL_VERSION,
        "trace_id": trace_id,
        "role": role,
        "bug_class": bug_class,
        "paired_trace_id": paired_trace_id,
        "request": dict(request),
        "events": [dict(event) for event in events],
        "trace_sha256": sha,
        "expected_outcome": outcome,
        "expected_findings": findings,
    }


def generate_traces(
    seed: int,
    depth: int = 6,
    hops: int = 3,
    mutation_points: int = MAX_MUTATION_POINTS,
) -> list[dict[str, Any]]:
    """Return the deterministic bounded temporal trace corpus for the parameters.

    Bounds ``depth`` / ``hops`` / ``mutation_points`` (out-of-bound values are
    refused with stable reason codes), always preserves a VALID trace, and
    pairs every generated temporal bug with a static request-matched control.
    Deterministic: identical inputs give byte-identical corpora.
    """
    _validate_params(seed, depth, hops, mutation_points)
    assert isinstance(seed, int) and isinstance(depth, int) and isinstance(hops, int)
    assert isinstance(mutation_points, int)
    t_req = hops + 3

    prefix = f"sacmat-x06-s{seed}-d{depth}-h{hops}-m{mutation_points}"
    valid_request = _request(_deep_actor(seed, hops), t_req)
    valid_events = _clean_events(seed, hops, valid_request)
    if len(valid_events) > depth:
        raise TemporalGeneratorError(
            RC_HOPS_EXCEED_DEPTH, f"valid trace needs {len(valid_events)} events > depth={depth}"
        )
    corpus = [_record(f"{prefix}-valid-main", ROLE_VALID, None, None, valid_request, valid_events)]

    eligible = [
        bug_class for bug_class, (min_hops, _kind) in _BUG_CLASS_SPECS.items() if hops >= min_hops
    ]
    start = seed % len(eligible)
    selected = [
        eligible[(start + offset) % len(eligible)]
        for offset in range(min(mutation_points, len(eligible)))
    ]
    for bug_class in selected:
        request = _class_request(bug_class, seed, hops, t_req)
        control_events = _clean_events(seed, hops, request)
        bug_events = _bug_events(bug_class, seed, hops, request)
        if bug_events == control_events:
            raise TemporalGeneratorError(
                RC_MUTATION_NOT_OBSERVABLE, f"{bug_class}: mutation did not alter the history"
            )
        if len(bug_events) > depth or len(control_events) > depth:
            raise TemporalGeneratorError(
                RC_HOPS_EXCEED_DEPTH,
                f"{bug_class}: trace exceeds depth={depth}",
            )
        bug_id = f"{prefix}-bug-{bug_class.lower()}"
        control_id = f"{prefix}-control-{bug_class.lower()}"
        corpus.append(_record(bug_id, ROLE_BUG, bug_class, control_id, request, bug_events))
        corpus.append(_record(control_id, ROLE_CONTROL, bug_class, bug_id, request, control_events))

    assert_corpus_integrity(corpus)
    assert_all_paired(corpus)
    return corpus


def _require_record(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise TemporalGeneratorError(RC_INVALID_TRACE_RECORD, f"record {record!r} is not an object")
    trace_id = record.get("trace_id")
    role = record.get("role")
    if not isinstance(trace_id, str) or not trace_id:
        raise TemporalGeneratorError(RC_INVALID_TRACE_RECORD, "trace_id must be a non-empty string")
    if role not in _ROLES:
        raise TemporalGeneratorError(RC_INVALID_TRACE_RECORD, f"{trace_id}: unknown role {role!r}")
    if not isinstance(record.get("request"), dict) or not isinstance(record.get("events"), list):
        raise TemporalGeneratorError(
            RC_INVALID_TRACE_RECORD, f"{trace_id}: request/events must be object/list"
        )
    if not isinstance(record.get("trace_sha256"), str) or not record["trace_sha256"]:
        raise TemporalGeneratorError(
            RC_INVALID_TRACE_RECORD, f"{trace_id}: trace_sha256 must be a non-empty string"
        )
    if role in (ROLE_BUG, ROLE_CONTROL) and record.get("bug_class") not in BUG_CLASSES:
        raise TemporalGeneratorError(
            RC_INVALID_TRACE_RECORD, f"{trace_id}: {role} record without a known bug_class"
        )
    if role == ROLE_VALID and record.get("bug_class") is not None:
        raise TemporalGeneratorError(
            RC_INVALID_TRACE_RECORD, f"{trace_id}: {role} record must carry bug_class None"
        )
    return record


def assert_corpus_integrity(traces: Sequence[Mapping[str, Any]]) -> None:
    """Refuse duplicate trace ids or duplicate trace hashes; never silently dedupe."""
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    for record in traces:
        checked = _require_record(record)
        trace_id = checked["trace_id"]
        sha = checked["trace_sha256"]
        if trace_id in seen_ids:
            raise TemporalGeneratorError(RC_DUPLICATE_TRACE_ID, f"trace_id {trace_id!r} repeated")
        if sha in seen_hashes:
            raise TemporalGeneratorError(
                RC_DUPLICATE_TRACE_HASH, f"trace_sha256 of {trace_id!r} repeated"
            )
        seen_ids.add(trace_id)
        seen_hashes.add(sha)


def assert_all_paired(traces: Sequence[Mapping[str, Any]]) -> None:
    """Refuse any temporal bug without its static request-matched control.

    Every ``bug`` record must reference an existing ``control`` record carrying
    the SAME request; every ``control`` must reference an existing ``bug``.
    """
    by_id: dict[str, dict[str, Any]] = {}
    for record in traces:
        checked = _require_record(record)
        if checked["trace_id"] in by_id:
            raise TemporalGeneratorError(
                RC_DUPLICATE_TRACE_ID, f"trace_id {checked['trace_id']!r} repeated"
            )
        by_id[checked["trace_id"]] = checked
    for record in traces:
        checked = _require_record(record)
        trace_id = checked["trace_id"]
        role = checked["role"]
        partner_id = checked.get("paired_trace_id")
        if role == ROLE_VALID:
            if partner_id is not None:
                raise TemporalGeneratorError(
                    RC_PAIRING_MISMATCH, f"{trace_id}: valid trace must not reference a partner"
                )
            continue
        expected_role = ROLE_CONTROL if role == ROLE_BUG else ROLE_BUG
        partner = by_id.get(partner_id) if isinstance(partner_id, str) else None
        if partner is None or partner["role"] != expected_role:
            code = RC_UNPAIRED_CONTROL if role == ROLE_BUG else RC_UNPAIRED_BUG
            raise TemporalGeneratorError(
                code,
                f"{trace_id} ({role}) has no matched {expected_role}"
                f" (paired_trace_id={partner_id!r})",
            )
        if partner.get("request") != checked["request"]:
            raise TemporalGeneratorError(
                RC_REQUEST_MISMATCH,
                f"{trace_id}: paired request differs from its {expected_role}",
            )
        if partner.get("bug_class") != checked["bug_class"]:
            raise TemporalGeneratorError(
                RC_PAIRING_MISMATCH,
                f"{trace_id}: paired bug_class differs from its {expected_role}",
            )


def verify_corpus(traces: Sequence[Mapping[str, Any]]) -> None:
    """Re-derive every record's verdict with the independent DSL replay.

    Refuses tampered events, tampered expected outcomes/findings, broken
    pairing and duplicate ids/hashes; a tampered record is a first-class
    refusal, never silently repaired.
    """
    assert_corpus_integrity(traces)
    assert_all_paired(traces)
    for record in traces:
        checked = _require_record(record)
        trace_id = checked["trace_id"]
        outcome, findings, sha = _replay(trace_id, checked["events"])
        if outcome != checked.get("expected_outcome") or findings != checked.get(
            "expected_findings"
        ):
            raise TemporalGeneratorError(
                RC_INVALID_TRACE_RECORD,
                f"{trace_id}: embedded verdict does not match the independent replay",
            )
        if sha != checked["trace_sha256"]:
            raise TemporalGeneratorError(
                RC_INVALID_TRACE_RECORD, f"{trace_id}: embedded trace_sha256 does not match events"
            )
        role = checked["role"]
        if role in (ROLE_VALID, ROLE_CONTROL):
            if outcome != OUTCOME_PERMIT or findings:
                raise TemporalGeneratorError(
                    RC_VALID_TRACE_BROKEN, f"{trace_id}: {role} trace does not replay clean PERMIT"
                )
        else:
            required = _BUG_CLASS_SPECS[str(checked["bug_class"])][1]
            if not any(finding["kind"] == required for finding in findings):
                raise TemporalGeneratorError(
                    RC_MUTATION_NOT_OBSERVABLE,
                    f"{trace_id}: witness {required} absent from the replay",
                )


def coverage_summary(traces: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize which bug classes are covered and how their controls pair up."""
    counts = {bug_class: {"bug_traces": 0, "matched_controls": 0} for bug_class in BUG_CLASSES}
    valid = bugs = controls = 0
    max_events = 0
    for record in traces:
        checked = _require_record(record)
        role = checked["role"]
        max_events = max(max_events, len(checked["events"]))
        if role == ROLE_VALID:
            valid += 1
        elif role == ROLE_BUG:
            bugs += 1
            counts[str(checked["bug_class"])]["bug_traces"] += 1
        else:
            controls += 1
            counts[str(checked["bug_class"])]["matched_controls"] += 1
    return {
        "corpus_schema_version": CORPUS_SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "total_traces": len(traces),
        "valid_traces": valid,
        "bug_traces": bugs,
        "control_traces": controls,
        "bug_control_pairs": bugs,
        "unique_trace_ids": len({str(record["trace_id"]) for record in traces}),
        "unique_trace_sha256": len({str(record["trace_sha256"]) for record in traces}),
        "max_trace_events": max_events,
        "bug_classes_declared": len(BUG_CLASSES),
        "bug_classes": counts,
    }


def build_corpus_document(seed: int, depth: int, hops: int, mutation_points: int) -> dict[str, Any]:
    """Return the JSON-serializable corpus artifact document (params + coverage + traces)."""
    traces = generate_traces(seed, depth, hops, mutation_points)
    return {
        "corpus_schema_version": CORPUS_SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "dsl_version": POLICY_TRACE_DSL_VERSION,
        "params": {
            "seed": seed,
            "depth": depth,
            "hops": hops,
            "mutation_points": mutation_points,
        },
        "coverage": coverage_summary(traces),
        "traces": traces,
    }
