"""DSN-X05_workflow_reference — durable workflow / saga competitor (arm B2).

Purpose
-------
Reference adapter for the durable-workflow/saga strong-baseline arm (blueprint
row B2) of the DSN 2027 study "Recoverable Safety Journals for Crash-Consistent
AI-Mediated Health-State Mutations" (RQ3; task contract
``research/venue2027/VENUES/dsn/TASKS/DSN-X05_workflow_reference.md``). The
arm contract is ``run_workflow(case: Case, ctx: WorkflowCtx) -> Outcome``.

Two layers, honestly labeled:

1. **Pinned external engine (Temporal Python SDK)** — the registry pins
   ``temporalio 1.19.0`` (tag ``1.19.0`` -> commit
   ``11e8650c7c8b89af45fab328e400d2fd5a9af16c`` via git ls-remote 2026-11-15;
   PyPI License-Expression MIT verified 2026-11-15) with unit runs on the
   Temporal test-server harness only (never a live service) and durability
   configuration ``WorkflowIDReusePolicy=REJECT_DUPLICATE`` on a workflow id
   keyed by the stable logical ``operation_id`` (stable operation ids,
   at-least-once replay, saga compensation in reverse completion order).
   :func:`run_workflow` probes for the SDK: if it is not importable in the
   execution environment the engine path is NOT executed and the first-class
   harness outcome ``NOT_RUN_EXTERNAL`` / ``WORKFLOW_ENGINE_UNAVAILABLE`` is
   returned — never a simulated result presented as the real engine. If the
   SDK is importable but the test-server runtime is not wired in this
   worktree, the arm fails closed with ``ENGINE_RUNTIME_UNWIRED`` rather
   than pretend to run it.

2. **In-memory saga reference (labelled as such, never as the engine)** —
   :func:`run_saga_reference` executes a deterministic, dependency-free saga
   with forward steps and compensations over the injected ``ctx.store`` dict.
   Every result is ``detail``-labelled ``IN_MEMORY_SAGA_REFERENCE`` and must
   not be counted as an engine run; no comparative claim against the pinned
   engine may be derived from it. It exists to exercise the compensation and
   recovery semantics the task requires:

   - forward execution of the declared saga steps, each identified by a
     stable logical step id;
   - on forward-step failure, completed steps are compensated in strict
     reverse order (saga compensation); a failing compensation leaves the
     saga explicitly non-retriable ``INDETERMINATE``
     (``SAGA_COMPENSATION_INDETERMINATE``) — never a silent success;
   - recovery replay: a second run over a journaled saga resumes at the
     first not-yet-applied step and dedups already-applied steps by the
     immutable operation id (``SAGA_RECOVERY_RESUMED`` /
     ``SAGA_RECOVERY_DEDUPED``); replay over a terminal journal re-acks the
     recorded terminal outcome without re-executing any step;
   - a forward step whose compensation is missing from the saga definition
     is detected and fails closed (``SAGA_COMPENSATION_STEP_MISSING``)
     before any forward step executes or any journal byte is written;
   - a saga catalog with no forward steps is refused
     (``SAGA_EMPTY_DEFINITION``).

Allowed input
-------------
A JSON-serializable ``case`` mapping ``{"case_id": str, "operation_id": str,
"crash_point": str, "delivery_schedule": [ints], "consent_epoch": int}`` (the
exact schema :mod:`evaluation.venue2027.dsn.baselines` validates) and an
injected :class:`WorkflowCtx` carrying the arm's in-process ``store`` dict
plus deterministic failure knobs: ``fail_step_id`` (forward step that raises
:class:`StepFailed`), ``fail_compensation_id`` (compensation step that raises
:class:`StepFailed`) and ``compensation_missing`` (declared compensation
marked absent from the definition — the adversarial control that must be
detected, never skipped). ``crash_point`` uses the shared crash vocabulary
(``none`` / ``pre_commit`` / ``post_commit_pre_response`` /
``pre_outbox_delivery``). No hidden clock, no randomness, no network, no live
provider, no real PHI/PII; every timestamp is a caller-supplied logical
integer.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes. Every terminal state is a
first-class harness :class:`Outcome`: ``ADMIT`` / ``REJECT`` /
``INDETERMINATE`` / ``NOT_RUN_EXTERNAL``. Malformed cases, malformed contexts
and unknown engine states are wiring errors raised as :class:`WorkflowError`
(never silently counted as safe rejections). A crash point is never coerced
into a success: ``pre_commit`` is a retriable ``REJECT`` with nothing
durable; ``pre_outbox_delivery`` interrupts the delivery step and honestly
reports a retriable ``INDETERMINATE`` until recovery reconciles it; a
post-commit crash window keeps the durable journal so the replay dedups
instead of re-applying.

Version
-------
``WORKFLOW_REFERENCE_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any, Final

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.dsn.baselines import (
    CRASH_NONE,
    CRASH_POINTS,
    CRASH_POST_COMMIT_PRE_RESPONSE,
    CRASH_PRE_COMMIT,
    CRASH_PRE_OUTBOX_DELIVERY,
    _Case,
    _validate_case,
)
from evaluation.venue2027.dsn.baselines import (
    BaselineError as CaseSchemaError,
)

WORKFLOW_REFERENCE_VERSION: Final[str] = "1.0.0"

#: Pinned engine identity (research/venue2027/_shared/baselines/registry.yaml,
#: arm ``durable-workflow-saga-compensation``; verified 2026-11-15).
ENGINE_NAME: Final[str] = "temporalio"
ENGINE_VERSION: Final[str] = "1.19.0"
ENGINE_UPSTREAM_REVISION: Final[str] = "11e8650c7c8b89af45fab328e400d2fd5a9af16c"
#: Unit runs use the Temporal test-server harness only (never a live service).
ENGINE_DURABILITY_CONFIG: Final[Mapping[str, str]] = {
    "runtime": "temporal-test-server",
    "workflow_id_reuse_policy": "REJECT_DUPLICATE",
    "workflow_id_key": "operation_id",
    "retry_policy": "at-least-once replay, idempotent by operation id",
    "compensation": "saga rollback in reverse completion order",
}

ARM_ID: Final[str] = "B2-durable-workflow"

# ---------------------------------------------------------------------------
# Stable reason codes (uppercase, machine-checkable).
# ---------------------------------------------------------------------------
RC_ENGINE_UNAVAILABLE = "WORKFLOW_ENGINE_UNAVAILABLE"
RC_SAGA_LABEL = "IN_MEMORY_SAGA_REFERENCE"
RC_SAGA_COMMITTED = "SAGA_COMMITTED"
RC_SAGA_COMPENSATED = "SAGA_COMPENSATED_ON_STEP_FAILURE"
RC_SAGA_COMPENSATION_INDETERMINATE = "SAGA_COMPENSATION_INDETERMINATE"
RC_SAGA_INTERRUPTED = "SAGA_INTERRUPTED_PENDING_RECOVERY"
RC_SAGA_RECOVERY_RESUMED = "SAGA_RECOVERY_RESUMED"
RC_SAGA_RECOVERY_DEDUPED = "SAGA_RECOVERY_DEDUPED"
RC_SAGA_STEP_MISSING_COMPENSATION = "SAGA_COMPENSATION_STEP_MISSING"
RC_SAGA_EMPTY_DEFINITION = "SAGA_EMPTY_DEFINITION"
RC_SAGA_NOT_DURABLE = "SAGA_NOT_DURABLE_CRASH_BEFORE_WRITE"
RC_CONTEXT_MALFORMED = "CONTEXT_MALFORMED"

#: Saga catalog: forward steps declared with their compensation steps.
SAGA_DEFINITION: Final[tuple[tuple[str, str], ...]] = (
    ("reserve_slot", "release_slot"),
    ("apply_state", "revert_state"),
    ("emit_receipt", "retract_receipt"),
)

SAGA_STEP_IDS: Final[frozenset[str]] = frozenset(step for step, _ in SAGA_DEFINITION)
SAGA_COMPENSATION_IDS: Final[frozenset[str]] = frozenset(comp for _, comp in SAGA_DEFINITION)


class WorkflowError(ValueError):
    """Wiring/configuration error carrying a stable reason code (not an arm outcome)."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


class StepFailed(RuntimeError):
    """Deterministic forward/compensation step failure (injected, never random)."""


@dataclasses.dataclass
class WorkflowCtx:
    """Injected per-run context: the arm's store plus deterministic failure knobs.

    ``store`` is a plain dict acting as the in-process durable saga journal;
    this arm owns the ``saga:<operation_id>`` keys. ``fail_step_id`` names the
    forward step that raises :class:`StepFailed` (``None`` = no failure);
    ``fail_compensation_id`` names the compensation step that raises
    :class:`StepFailed` during rollback; ``compensation_missing`` marks one
    declared compensation as absent from the definition — the adversarial
    control that must be detected before any step executes.
    """

    store: dict[str, Any]
    fail_step_id: str | None = None
    fail_compensation_id: str | None = None
    compensation_missing: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.store, dict):
            raise WorkflowError(RC_CONTEXT_MALFORMED, "store must be a dict")
        if self.fail_step_id is not None and self.fail_step_id not in SAGA_STEP_IDS:
            raise WorkflowError(
                RC_CONTEXT_MALFORMED,
                f"fail_step_id {self.fail_step_id!r} is not a declared forward step",
            )
        if (
            self.fail_compensation_id is not None
            and self.fail_compensation_id not in SAGA_COMPENSATION_IDS
        ):
            raise WorkflowError(
                RC_CONTEXT_MALFORMED,
                f"fail_compensation_id {self.fail_compensation_id!r} is not a declared "
                "compensation step",
            )
        if self.compensation_missing is not None and self.compensation_missing not in (
            SAGA_COMPENSATION_IDS
        ):
            raise WorkflowError(
                RC_CONTEXT_MALFORMED,
                f"compensation_missing {self.compensation_missing!r} is not a declared "
                "compensation step",
            )


# ---------------------------------------------------------------------------
# Saga definition resolution (fail closed on a missing compensation).
# ---------------------------------------------------------------------------


def _definition(ctx: WorkflowCtx) -> tuple[tuple[str, str | None], ...]:
    """Resolve the effective definition; a missing compensation keeps its
    forward step so the completeness check below can refuse the saga."""
    if ctx.compensation_missing is None:
        return SAGA_DEFINITION
    return tuple(
        (step, None if comp == ctx.compensation_missing else comp)
        for step, comp in SAGA_DEFINITION
    )


def _assert_complete(definition: tuple[tuple[str, str | None], ...]) -> None:
    """Refuse an incomplete saga BEFORE any journal byte is written."""
    if not definition:
        raise WorkflowError(RC_SAGA_EMPTY_DEFINITION, "saga catalog has no forward steps")
    for step, compensation in definition:
        if compensation is None:
            raise WorkflowError(
                RC_SAGA_STEP_MISSING_COMPENSATION,
                f"forward step {step!r} has no compensation step in the saga definition",
            )


def _saga_key(operation_id: str) -> str:
    return f"saga:{operation_id}"


def _outcome(success: bool, retriable: bool, reason_code: str, detail_suffix: str = "") -> Outcome:
    detail = f"{RC_SAGA_LABEL}:{reason_code}"
    if detail_suffix:
        detail = f"{detail}:{detail_suffix}"
    return Outcome(
        observed_outcome="ADMIT" if success else "REJECT",
        counted_as_success=success,
        retriable=retriable,
        detail=detail,
    )


def _indeterminate(reason_code: str, detail_suffix: str, retriable: bool) -> Outcome:
    return Outcome(
        observed_outcome="INDETERMINATE",
        counted_as_success=False,
        retriable=retriable,
        detail=f"{RC_SAGA_LABEL}:{reason_code}:{detail_suffix}",
    )


# ---------------------------------------------------------------------------
# In-memory saga reference (labelled as such; NOT the pinned engine).
# ---------------------------------------------------------------------------


def run_saga_reference(case: Mapping[str, Any], ctx: WorkflowCtx) -> Outcome:
    """Deterministic in-memory saga with compensation and recovery replay.

    Recovery model (deterministic, mirroring the shared crash vocabulary):
    - ``pre_commit``: the journal write itself is lost — nothing durable
      anywhere, so the outcome is a retriable ``REJECT``
      (``SAGA_NOT_DURABLE_CRASH_BEFORE_WRITE``) and recovery re-runs the saga
      under the same operation id.
    - ``pre_outbox_delivery``: the delivery (final) step is interrupted
      before it executes; earlier steps are durable in the journal, but the
      saga is incomplete and the caller saw no ack. First run: retriable
      ``INDETERMINATE`` (``SAGA_INTERRUPTED_PENDING_RECOVERY``) — never a
      success. Recovery replay under the same operation id resumes at the
      first not-applied step and completes (``SAGA_RECOVERY_RESUMED``).
    - ``post_commit_pre_response``: every forward step is durable but the
      final commit ack was lost; the journal stays ``RUNNING`` so the
      recovery replay re-acks without re-applying
      (``SAGA_RECOVERY_DEDUPED``).
    - ``none``: clean forward execution; an injected step failure triggers
      compensation of completed steps in strict reverse order, terminating
      the saga as ``REJECT`` / ``SAGA_COMPENSATED_ON_STEP_FAILURE``. A
      failing compensation leaves an explicit non-retriable
      ``INDETERMINATE`` — never a silent partial success.
    """
    validated = _validate_case(case)
    definition = _definition(ctx)
    _assert_complete(definition)

    key = _saga_key(validated.operation_id)
    store = ctx.store
    journal = store.get(key)
    if journal is None:
        if validated.crash_point == CRASH_PRE_COMMIT:
            return _outcome(False, True, RC_SAGA_NOT_DURABLE)
        store[key] = {
            "status": "RUNNING",
            "operation_id": validated.operation_id,
            "case_id": validated.case_id,
            "consent_epoch": validated.consent_epoch,
            "applied_steps": [],
            "compensated_steps": [],
        }
        return _forward(store, key, definition, ctx, validated, start_index=0)

    # Recovery replay over an existing journal (durable evidence survives).
    status = journal.get("status")
    applied: list[str] = list(journal.get("applied_steps", []))
    if status == "COMMITTED":
        return _outcome(True, False, RC_SAGA_RECOVERY_DEDUPED)
    if status == "COMPENSATED":
        return _outcome(False, False, RC_SAGA_COMPENSATED, "replay")
    if status == "INDETERMINATE":
        return _indeterminate(RC_SAGA_COMPENSATION_INDETERMINATE, "replay", retriable=False)
    # RUNNING: resume at the first not-yet-applied step, dedup the applied ones.
    definition_steps = [step for step, _comp in definition]
    remaining = [step for step in definition_steps if step not in set(applied)]
    if not remaining:
        store[key] = {**journal, "status": "COMMITTED", "consent_epoch": validated.consent_epoch}
        return _outcome(True, False, RC_SAGA_RECOVERY_DEDUPED)
    store[key] = {
        **journal,
        "status": "RUNNING",
        "consent_epoch": validated.consent_epoch,
        "recovery_attempt": journal.get("recovery_attempt", 0) + 1,
    }
    start_index = definition_steps.index(remaining[0])
    return _forward(store, key, definition, ctx, validated, start_index=start_index, resumed=True)


def _forward(
    store: dict[str, Any],
    key: str,
    definition: tuple[tuple[str, str | None], ...],
    ctx: WorkflowCtx,
    validated: _Case,
    *,
    start_index: int,
    resumed: bool = False,
) -> Outcome:
    """Execute forward steps from ``start_index``; compensate on step failure.

    The delivery interruption (``pre_outbox_delivery``) fires before the
    final declared step — the delivery/receipt step of the saga — leaving the
    journal RUNNING and the run honestly INDETERMINATE (retriable).
    """
    applied: list[str] = list(store[key].get("applied_steps", []))
    delivery_step = definition[-1][0]
    try:
        for index in range(start_index, len(definition)):
            step, _compensation = definition[index]
            if validated.crash_point == CRASH_PRE_OUTBOX_DELIVERY and step == delivery_step:
                store[key]["applied_steps"] = list(applied)
                return _indeterminate(
                    RC_SAGA_INTERRUPTED, f"before={step}", retriable=True
                )
            if ctx.fail_step_id == step:
                raise StepFailed(step)
            applied.append(step)
            store[key]["applied_steps"] = list(applied)
    except StepFailed as failure:
        return _compensate(store, key, definition, ctx, applied, failure)
    if validated.crash_point == CRASH_POST_COMMIT_PRE_RESPONSE:
        # Every step durable, final ack lost: recovery replay dedups.
        return _outcome(True, False, RC_SAGA_COMMITTED, "ack_lost_pending_recovery_dedup")
    if resumed:
        store[key]["status"] = "COMMITTED"
        return _outcome(True, False, RC_SAGA_RECOVERY_RESUMED, f"steps={len(applied)}")
    store[key]["status"] = "COMMITTED"
    return _outcome(True, False, RC_SAGA_COMMITTED, f"steps={len(applied)}")


def _compensate(
    store: dict[str, Any],
    key: str,
    definition: tuple[tuple[str, str | None], ...],
    ctx: WorkflowCtx,
    applied: list[str],
    failure: StepFailed,
) -> Outcome:
    """Compensate completed steps in strict reverse order.

    Fails closed: a failing compensation leaves the saga explicitly
    non-retriable INDETERMINATE (never a silent success or a safe
    rejection); a clean compensation run terminates the saga as a
    compensated REJECT and records the compensation log.
    """
    store[key]["failed_step"] = failure.args[0] if failure.args else "unknown"
    compensation_for = dict(definition)
    compensated: list[str] = []
    for step in reversed(applied):
        compensation_id = compensation_for[step]
        if compensation_id is None:  # unreachable: _assert_complete ran first
            raise WorkflowError(
                RC_SAGA_STEP_MISSING_COMPENSATION,
                f"forward step {step!r} has no compensation step at rollback time",
            )
        if ctx.fail_compensation_id == compensation_id:
            store[key]["status"] = "INDETERMINATE"
            store[key]["compensated_steps"] = store[key].get("compensated_steps", []) + [step]
            return _indeterminate(
                RC_SAGA_COMPENSATION_INDETERMINATE, f"failed_comp={compensation_id}",
                retriable=False,
            )
        compensated.append(compensation_id)
        store[key]["compensated_steps"] = store[key].get("compensated_steps", []) + [step]
    store[key]["status"] = "COMPENSATED"
    store[key]["compensation_log"] = compensated
    return _outcome(False, False, RC_SAGA_COMPENSATED, f"compensated={len(compensated)}")


# ---------------------------------------------------------------------------
# Engine probe + arm dispatch.
# ---------------------------------------------------------------------------


def probe_engine() -> dict[str, Any]:
    """Probe for the pinned Temporal Python SDK. Never raises, never fakes.

    Returns a JSON-serializable report: ``installed=True`` only when the real
    ``temporalio`` package imports, together with its true imported version;
    otherwise ``installed=False`` and ``reason=WORKFLOW_ENGINE_UNAVAILABLE``.
    The probe result alone never asserts that a workflow ran.
    """
    try:
        import temporalio
    except ImportError:
        return {
            "engine": ENGINE_NAME,
            "pinned_version": ENGINE_VERSION,
            "pinned_upstream_revision": ENGINE_UPSTREAM_REVISION,
            "installed": False,
            "reason": RC_ENGINE_UNAVAILABLE,
        }
    return {
        "engine": ENGINE_NAME,
        "pinned_version": ENGINE_VERSION,
        "pinned_upstream_revision": ENGINE_UPSTREAM_REVISION,
        "installed": True,
        "imported_version": getattr(temporalio, "__version__", "unknown"),
    }


def run_workflow(case: Mapping[str, Any], ctx: WorkflowCtx) -> Outcome:
    """Arm B2 entry point: ``run_workflow(case, ctx) -> Outcome``.

    Pins the engine (name/version/durability configuration above) and probes
    for it: if the real ``temporalio`` SDK is not importable, returns
    ``NOT_RUN_EXTERNAL`` / ``WORKFLOW_ENGINE_UNAVAILABLE`` — the transparent
    status the blueprint permits, never a simulated result presented as the
    engine. The dependency-free in-memory saga reference is available
    separately via :func:`run_saga_reference` and is always labelled
    ``IN_MEMORY_SAGA_REFERENCE`` in its ``detail``; it must not be counted as
    an engine run and supports no comparative claim against the engine.
    """
    if not isinstance(ctx, WorkflowCtx):
        raise WorkflowError(
            RC_CONTEXT_MALFORMED, f"ctx must be a WorkflowCtx, got {type(ctx)}"
        )
    _validate_case(case)
    probe = probe_engine()
    if not probe["installed"]:
        return Outcome(
            observed_outcome="NOT_RUN_EXTERNAL",
            counted_as_success=False,
            retriable=False,
            detail=(
                f"{RC_ENGINE_UNAVAILABLE}:{ENGINE_NAME}@{ENGINE_VERSION} not importable; "
                "pinned engine arm not executed (in-memory saga reference available via "
                "run_saga_reference, labelled as such)"
            ),
        )
    raise WorkflowError(
        "ENGINE_RUNTIME_UNWIRED",
        f"{ENGINE_NAME}@{ENGINE_VERSION} is importable but the test-server runtime is "
        "not wired in this worktree; refusing to simulate",
    )


__all__ = [
    "ARM_ID",
    "CRASH_NONE",
    "CRASH_POINTS",
    "CRASH_POST_COMMIT_PRE_RESPONSE",
    "CRASH_PRE_COMMIT",
    "CRASH_PRE_OUTBOX_DELIVERY",
    "ENGINE_DURABILITY_CONFIG",
    "ENGINE_NAME",
    "ENGINE_UPSTREAM_REVISION",
    "ENGINE_VERSION",
    "RC_ENGINE_UNAVAILABLE",
    "RC_SAGA_COMPENSATED",
    "RC_SAGA_COMPENSATION_INDETERMINATE",
    "RC_SAGA_COMMITTED",
    "RC_SAGA_INTERRUPTED",
    "RC_SAGA_LABEL",
    "RC_SAGA_NOT_DURABLE",
    "RC_SAGA_RECOVERY_DEDUPED",
    "RC_SAGA_RECOVERY_RESUMED",
    "RC_SAGA_STEP_MISSING_COMPENSATION",
    "SAGA_COMPENSATION_IDS",
    "SAGA_DEFINITION",
    "SAGA_STEP_IDS",
    "WORKFLOW_REFERENCE_VERSION",
    "CaseSchemaError",
    "StepFailed",
    "WorkflowCtx",
    "WorkflowError",
    "probe_engine",
    "run_saga_reference",
    "run_workflow",
]
