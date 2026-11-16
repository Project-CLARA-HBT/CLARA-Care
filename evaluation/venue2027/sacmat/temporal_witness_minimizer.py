"""SACMAT-X09_minimizer — Delta-debugging witness minimizer for temporal policy traces.

Purpose
-------
Delta-debugging over ordered policy-trace events without deleting required
granting context for "PolicyTrace: Temporal Conformance Testing of Delegated
Consent across Heterogeneous Policy Engines"
(``research/venue2027/VENUES/sacmat/RESEARCH_BLUEPRINT.md``, RQ1; task contract
``research/venue2027/VENUES/sacmat/TASKS/SACMAT-X09_minimizer.md``).

Reduces a fault-revealing temporal witness trace to a minimal reproducible
sub-trace using delta debugging (ddmin), guaranteeing:
1. Same semantic fault: The minimized trace exposes the exact same semantic
   fault (findings, error class, or decision divergence) on the target oracle.
2. Granting context preservation: Authority grants required to reach the fault
   state are never prematurely stripped.
3. Length reduction: len(minimized) <= len(original).
4. 1-minimality: Removing any single further event from the minimized trace
   eliminates the fault or alters its semantic signature.

Allowed input
-------------
- ``failing_trace``: A :class:`PolicyTrace` or mapping with ``version``,
  ``trace_id``, and ``events`` adhering to
  :data:`evaluation.venue2027.sacmat.policy_trace_dsl.POLICY_TRACE_DSL_VERSION`.
- ``oracle``: A callable (defaulting to :func:`evaluate_trace`) mapping a
  :class:`PolicyTrace` to a :class:`TraceVerdict`, dict, or boolean indicating
  fault presence.
- Optional ``target_fault`` / ``target_actor`` to target a specific finding
  class.

Failure semantics (stable reason codes on ``MinimizerError``)
-------------------------------------------------------------
- ``NO_FAULT_DETECTED`` — trace does not expose any fault on the oracle.
- ``NON_MONOTONIC_TIMESTAMPS`` — events are not strictly ascending in
  logical_time.
- ``EMPTY_TRACE`` — input trace has zero events.
- ``MALFORMED_TRACE`` — invalid trace structure or events.
- ``SCHEMA_VERSION_MISMATCH`` — trace version differs from DSL version.
- ``TARGET_FAULT_NOT_FOUND`` — specified target fault not observed on initial
  trace.

Version
-------
``TEMPORAL_WITNESS_MINIMIZER_VERSION = "clara.sacmat.temporal-witness-minimizer-v1"``
``MINIMIZER_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Final

from evaluation.venue2027.sacmat.policy_trace_dsl import (
    OUTCOME_DENY,
    OUTCOME_INDETERMINATE,
    OUTCOME_PERMIT,
    POLICY_TRACE_DSL_VERSION,
    REASON_DUPLICATE_TIMESTAMP,
    REASON_EMPTY_TRACE,
    REASON_MALFORMED_EVENT,
    REASON_MISSING_LOGICAL_TIME,
    REASON_SCHEMA_VERSION_MISMATCH,
    REASON_UNORDERED_TIMESTAMPS,
    Event,
    PolicyTrace,
    PolicyTraceError,
    TraceVerdict,
    evaluate_trace,
    parse_policy_trace,
)

TEMPORAL_WITNESS_MINIMIZER_VERSION: Final[str] = "clara.sacmat.temporal-witness-minimizer-v1"
MINIMIZER_VERSION: Final[str] = "1.0.0"

REASON_NO_FAULT_DETECTED: Final[str] = "NO_FAULT_DETECTED"
REASON_NON_MONOTONIC_TIMESTAMPS: Final[str] = "NON_MONOTONIC_TIMESTAMPS"
REASON_EMPTY_TRACE_CODE: Final[str] = REASON_EMPTY_TRACE
REASON_MALFORMED_TRACE: Final[str] = "MALFORMED_TRACE"
REASON_SCHEMA_VERSION_MISMATCH_CODE: Final[str] = REASON_SCHEMA_VERSION_MISMATCH
REASON_TARGET_FAULT_NOT_FOUND: Final[str] = "TARGET_FAULT_NOT_FOUND"


class MinimizerError(PolicyTraceError):
    """Fail-closed error raised during witness minimization with stable reason code."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(reason_code, detail)


@dataclasses.dataclass(frozen=True)
class MinimizedTrace:
    """Immutable, JSON-serializable record of a minimized witness trace."""

    trace: PolicyTrace
    original_trace: PolicyTrace
    fault: str
    original_event_count: int
    minimized_event_count: int
    reduction_ratio: float
    iterations: int
    oracle_evaluations: int
    is_1_minimal: bool
    removed_indices: tuple[int, ...]
    dsl_version: str = POLICY_TRACE_DSL_VERSION
    minimizer_version: str = TEMPORAL_WITNESS_MINIMIZER_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.minimizer_version,
            "dsl_version": self.dsl_version,
            "fault": self.fault,
            "original_event_count": self.original_event_count,
            "minimized_event_count": self.minimized_event_count,
            "reduction_ratio": self.reduction_ratio,
            "iterations": self.iterations,
            "oracle_evaluations": self.oracle_evaluations,
            "is_1_minimal": self.is_1_minimal,
            "removed_indices": list(self.removed_indices),
            "trace": self.trace.to_dict(),
            "original_trace_sha256": self.original_trace.trace_sha256,
            "minimized_trace_sha256": self.trace.trace_sha256,
        }

    @property
    def events(self) -> tuple[Event, ...]:
        return self.trace.events

    @property
    def trace_id(self) -> str:
        return self.trace.trace_id

    def __len__(self) -> int:
        return self.minimized_event_count


def _normalize_and_validate_trace(
    trace_input: PolicyTrace | Mapping[str, Any],
) -> PolicyTrace:
    """Normalize input into a validated PolicyTrace, failing closed on defects."""
    if isinstance(trace_input, Mapping):
        try:
            trace = parse_policy_trace(trace_input)
        except PolicyTraceError as exc:
            if exc.reason_code in (
                REASON_UNORDERED_TIMESTAMPS,
                REASON_DUPLICATE_TIMESTAMP,
            ):
                raise MinimizerError(REASON_NON_MONOTONIC_TIMESTAMPS, exc.detail) from exc
            if exc.reason_code == REASON_SCHEMA_VERSION_MISMATCH:
                raise MinimizerError(REASON_SCHEMA_VERSION_MISMATCH_CODE, exc.detail) from exc
            if exc.reason_code == REASON_EMPTY_TRACE:
                raise MinimizerError(REASON_EMPTY_TRACE_CODE, exc.detail) from exc
            if exc.reason_code in (
                REASON_MALFORMED_EVENT,
                REASON_MISSING_LOGICAL_TIME,
            ):
                raise MinimizerError(REASON_MALFORMED_TRACE, exc.detail) from exc
            raise MinimizerError(exc.reason_code, exc.detail) from exc
    elif isinstance(trace_input, PolicyTrace):
        trace = trace_input
    else:
        raise MinimizerError(
            REASON_MALFORMED_TRACE,
            f"failing_trace must be a PolicyTrace or mapping, got {type(trace_input).__name__}",
        )

    if not trace.events:
        raise MinimizerError(REASON_EMPTY_TRACE_CODE, "trace contains zero events")

    for idx in range(1, len(trace.events)):
        prev_t = trace.events[idx - 1].logical_time
        curr_t = trace.events[idx].logical_time
        if curr_t <= prev_t:
            raise MinimizerError(
                REASON_NON_MONOTONIC_TIMESTAMPS,
                f"event[{idx}].logical_time ({curr_t}) <= event[{idx - 1}].logical_time ({prev_t}); "
                "trace events must have strictly ascending logical_time",
            )
    return trace


def _extract_fault_signature(
    oracle_result: Any,
    target_fault: str | None = None,
    target_actor: str | None = None,
) -> tuple[str, str | None]:
    """Extract (fault_kind, actor) from initial oracle evaluation."""
    if isinstance(oracle_result, bool):
        if not oracle_result:
            raise MinimizerError(
                REASON_NO_FAULT_DETECTED,
                "oracle predicate returned False on initial trace (no fault detected)",
            )
        return (target_fault or "PREDICATE_TRUE", target_actor)

    if isinstance(oracle_result, TraceVerdict):
        if not oracle_result.findings and oracle_result.outcome == OUTCOME_PERMIT:
            raise MinimizerError(
                REASON_NO_FAULT_DETECTED,
                "trace outcome is PERMIT with zero findings (no fault detected)",
            )

        if target_fault is not None:
            matching = [
                f
                for f in oracle_result.findings
                if f.kind == target_fault and (target_actor is None or f.actor == target_actor)
            ]
            if not matching and oracle_result.outcome != target_fault:
                raise MinimizerError(
                    REASON_TARGET_FAULT_NOT_FOUND,
                    f"target fault {target_fault!r} (actor={target_actor!r}) not present in initial verdict",
                )
            actor = matching[0].actor if matching else target_actor
            return (target_fault, actor)

        if oracle_result.findings:
            primary = oracle_result.findings[0]
            return (primary.kind, target_actor or primary.actor)
        return (oracle_result.outcome, target_actor)

    if isinstance(oracle_result, Mapping):
        findings = oracle_result.get("findings", [])
        outcome = oracle_result.get("outcome", OUTCOME_DENY)
        if not findings and outcome == OUTCOME_PERMIT:
            raise MinimizerError(
                REASON_NO_FAULT_DETECTED,
                "trace outcome is PERMIT with zero findings (no fault detected)",
            )

        if target_fault is not None:
            matching_maps = [
                f
                for f in findings
                if isinstance(f, Mapping)
                and f.get("kind") == target_fault
                and (target_actor is None or f.get("actor") == target_actor)
            ]
            if not matching_maps and outcome != target_fault:
                raise MinimizerError(
                    REASON_TARGET_FAULT_NOT_FOUND,
                    f"target fault {target_fault!r} not in initial dict verdict",
                )
            actor = matching_maps[0].get("actor") if matching_maps else target_actor
            return (target_fault, actor)

        if findings and isinstance(findings[0], Mapping):
            return (
                findings[0].get("kind", "UNKNOWN_FINDING"),
                target_actor or findings[0].get("actor"),
            )
        return (str(outcome), target_actor)

    if isinstance(oracle_result, str):
        if oracle_result in (OUTCOME_PERMIT, "OK"):
            raise MinimizerError(
                REASON_NO_FAULT_DETECTED,
                f"oracle returned benign status {oracle_result!r}",
            )
        return (oracle_result, target_actor)

    raise MinimizerError(
        REASON_MALFORMED_TRACE,
        f"unsupported oracle result type: {type(oracle_result).__name__}",
    )


def _matches_fault(
    cand_result: Any,
    target_fault: str,
    target_actor: str | None,
    orig_result: Any,
) -> bool:
    """True if cand_result reproduces the same semantic fault without spurious corruption."""
    if isinstance(cand_result, bool):
        return cand_result

    if isinstance(cand_result, TraceVerdict):
        if target_fault in (OUTCOME_DENY, OUTCOME_INDETERMINATE):
            return cand_result.outcome == target_fault

        has_target = any(
            f.kind == target_fault and (target_actor is None or f.actor == target_actor)
            for f in cand_result.findings
        )
        if not has_target:
            return False

        # Preserving granting context: candidate must not introduce spurious finding kinds
        # that were not present in the original trace!
        if isinstance(orig_result, TraceVerdict):
            orig_kinds = {f.kind for f in orig_result.findings}
            cand_kinds = {f.kind for f in cand_result.findings}
            if not cand_kinds.issubset(orig_kinds):
                return False

        return True

    if isinstance(cand_result, Mapping):
        cand_findings = cand_result.get("findings", [])
        cand_outcome = cand_result.get("outcome")
        if target_fault in (OUTCOME_DENY, OUTCOME_INDETERMINATE):
            return cand_outcome == target_fault

        has_target = any(
            isinstance(f, Mapping)
            and f.get("kind") == target_fault
            and (target_actor is None or f.get("actor") == target_actor)
            for f in cand_findings
        )
        if not has_target:
            return False

        if isinstance(orig_result, Mapping):
            orig_kinds = {
                f.get("kind") for f in orig_result.get("findings", []) if isinstance(f, Mapping)
            }
            cand_kinds = {f.get("kind") for f in cand_findings if isinstance(f, Mapping)}
            if not cand_kinds.issubset(orig_kinds):
                return False

        return True

    if isinstance(cand_result, str):
        return cand_result == target_fault

    return False


def _split_indices(total_len: int, n: int) -> list[list[int]]:
    """Partition range(total_len) into n disjoint chunks."""
    if n <= 0 or total_len <= 0:
        return []
    chunk_size = total_len // n
    remainder = total_len % n
    chunks: list[list[int]] = []
    start = 0
    for i in range(min(n, total_len)):
        end = start + chunk_size + (1 if i < remainder else 0)
        if start < end:
            chunks.append(list(range(start, end)))
        start = end
    return chunks


def minimize_witness(
    failing_trace: PolicyTrace | Mapping[str, Any],
    oracle: Callable[[PolicyTrace], Any] = evaluate_trace,
    *,
    target_fault: str | None = None,
    target_actor: str | None = None,
) -> MinimizedTrace:
    """Delta-debugging over ordered policy-trace events to reduce fault witness.

    Guarantees:
    - Minimized trace still exposes the SAME semantic fault on the oracle.
    - Preserves required granting context without deleting necessary prerequisites.
    - Length is <= original length.
    - Result is 1-minimal: removing any further event eliminates the fault.
    """
    trace = _normalize_and_validate_trace(failing_trace)
    original_events = list(trace.events)
    original_count = len(original_events)
    trace_id = trace.trace_id

    # Initial evaluation: verify presence of fault and establish baseline
    try:
        orig_result = oracle(trace)
    except Exception as exc:
        raise MinimizerError(
            REASON_MALFORMED_TRACE, f"oracle failed on initial trace: {exc}"
        ) from exc

    eff_fault, eff_actor = _extract_fault_signature(orig_result, target_fault, target_actor)

    oracle_evals = 1
    active_indices = list(range(original_count))

    def test_candidate(indices: Sequence[int]) -> bool:
        nonlocal oracle_evals
        if not indices:
            return False
        cand_trace = PolicyTrace(
            trace_id=trace_id,
            events=tuple(original_events[i] for i in indices),
        )
        oracle_evals += 1
        try:
            cand_result = oracle(cand_trace)
            return _matches_fault(cand_result, eff_fault, eff_actor, orig_result)
        except Exception:
            return False

    n = 2
    iterations = 0

    while len(active_indices) >= 2:
        iterations += 1
        chunks = _split_indices(len(active_indices), n)
        reduced = False

        # Phase 1: Test each partition subset
        for chunk in chunks:
            subset = [active_indices[i] for i in chunk]
            if not subset or len(subset) == len(active_indices):
                continue
            if test_candidate(subset):
                active_indices = subset
                n = 2
                reduced = True
                break

        if reduced:
            continue

        # Phase 2: Test complement of each partition subset
        for chunk in chunks:
            chunk_set = set(chunk)
            complement = [
                active_indices[i] for i in range(len(active_indices)) if i not in chunk_set
            ]
            if not complement or len(complement) == len(active_indices):
                continue
            if test_candidate(complement):
                active_indices = complement
                n = max(n - 1, 2)
                reduced = True
                break

        if reduced:
            continue

        # Phase 3: Increase granularity
        if n < len(active_indices):
            n = min(2 * n, len(active_indices))
        else:
            break

    # Final 1-minimality assurance pass:
    # Test removing each event individually. If removing an event still reproduces
    # the fault, greedily prune it.
    idx = 0
    while idx < len(active_indices):
        if len(active_indices) <= 1:
            break
        candidate = active_indices[:idx] + active_indices[idx + 1 :]
        if test_candidate(candidate):
            active_indices = candidate
            idx = 0
        else:
            idx += 1

    minimized_events = tuple(original_events[i] for i in active_indices)
    minimized_trace = PolicyTrace(trace_id=trace_id, events=minimized_events)
    minimized_count = len(minimized_events)
    removed = tuple(i for i in range(original_count) if i not in set(active_indices))
    reduction_ratio = (
        round(1.0 - (minimized_count / original_count), 4) if original_count > 0 else 0.0
    )

    # Verify 1-minimality invariant: removing any single event must eliminate fault
    is_1_min = True
    if minimized_count > 1:
        for i in range(minimized_count):
            probe_subset = minimized_events[:i] + minimized_events[i + 1 :]
            probe_trace = PolicyTrace(trace_id=trace_id, events=probe_subset)
            try:
                probe_res = oracle(probe_trace)
                if _matches_fault(probe_res, eff_fault, eff_actor, orig_result):
                    is_1_min = False
                    break
            except Exception:
                pass

    return MinimizedTrace(
        trace=minimized_trace,
        original_trace=trace,
        fault=eff_fault,
        original_event_count=original_count,
        minimized_event_count=minimized_count,
        reduction_ratio=reduction_ratio,
        iterations=iterations,
        oracle_evaluations=oracle_evals,
        is_1_minimal=is_1_min,
        removed_indices=removed,
    )


def minimize(
    trace: PolicyTrace | Mapping[str, Any],
    predicate: Callable[[PolicyTrace], bool] | None = None,
    *,
    oracle: Callable[[PolicyTrace], Any] | None = None,
    target_fault: str | None = None,
    target_actor: str | None = None,
) -> PolicyTrace:
    """Convenience contract matching minimize(trace, predicate) -> PolicyTrace.

    If predicate is provided, it acts as the oracle function.
    Returns the minimized PolicyTrace object directly.
    """
    effective_oracle = predicate if predicate is not None else (oracle or evaluate_trace)
    result = minimize_witness(
        trace,
        effective_oracle,
        target_fault=target_fault,
        target_actor=target_actor,
    )
    return result.trace


def is_1_minimal(
    trace: PolicyTrace | Mapping[str, Any],
    oracle: Callable[[PolicyTrace], Any] = evaluate_trace,
    *,
    target_fault: str | None = None,
    target_actor: str | None = None,
) -> bool:
    """Return True if removing any single event from trace eliminates the fault."""
    norm_trace = _normalize_and_validate_trace(trace)
    events = list(norm_trace.events)
    if len(events) <= 1:
        return True

    try:
        orig_res = oracle(norm_trace)
        eff_fault, eff_actor = _extract_fault_signature(orig_res, target_fault, target_actor)
    except Exception:
        return False

    for i in range(len(events)):
        cand_events = events[:i] + events[i + 1 :]
        cand_trace = PolicyTrace(trace_id=norm_trace.trace_id, events=tuple(cand_events))
        try:
            cand_res = oracle(cand_trace)
            if _matches_fault(cand_res, eff_fault, eff_actor, orig_res):
                return False
        except Exception:
            pass
    return True
