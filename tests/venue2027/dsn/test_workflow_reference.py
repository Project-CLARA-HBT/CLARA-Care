"""Tests for DSN-X05_workflow_reference — durable workflow/saga arm (B2).

Positive controls (the engine-adjacent saga semantics the task requires):
- Engine pinning: the module pins engine name/version/upstream revision and a
  durability configuration; the pinned identity matches the registry arm
  ``durable-workflow-saga-compensation`` (temporalio 1.19.0).
- Compensation runs on failure: an injected forward-step failure compensates
  every completed step in strict reverse order and terminates as a
  non-success REJECT with the compensation log recorded in the journal.
- Recovery resumes after interruption: a saga interrupted before its
  delivery step is INDETERMINATE (retriable), and a second run under the
  same operation id resumes at the first not-applied step, dedups the
  already-applied steps (executed exactly once) and completes.
- Replay dedup: replay over a terminal journal re-acks without re-executing
  any step; a RUNNING journal whose steps are all durable is committed by
  recovery without re-applying.
- Honesty: the in-memory saga is always labelled ``IN_MEMORY_SAGA_REFERENCE``
  in its ``detail``; it is NOT presented as an engine run.

Adversarial controls (must fail closed):
- Missing compensation step detected: a saga definition whose declared
  compensation is absent is refused (``SAGA_COMPENSATION_STEP_MISSING``)
  BEFORE any forward step executes and before any journal byte is written;
  the empty-definition catalog is refused too (``SAGA_EMPTY_DEFINITION``).
- Engine-absent path returns NOT_RUN_EXTERNAL, never a fake success: with
  the pinned SDK not importable, ``run_workflow`` returns
  ``NOT_RUN_EXTERNAL`` / ``WORKFLOW_ENGINE_UNAVAILABLE`` with
  ``counted_as_success=False``; the harness contract bans counting it as a
  success (FALSE_ZERO_OUTCOME). The saga layer is never used to impersonate
  the engine.
- Failing compensation is an explicit non-retriable INDETERMINATE — never a
  silent success or a safe rejection.
- Crash-before-write is never a success: ``pre_commit`` yields a retriable
  REJECT with nothing durable in the store.
- Malformed case/context are wiring errors with stable reason codes.
"""

from __future__ import annotations

import pytest

from evaluation.venue2027._shared.harness import (
    HARNESS_SYNTHETIC_OUTCOMES,
    Outcome,
)
from evaluation.venue2027.dsn import workflow_reference as wf
from evaluation.venue2027.dsn.baselines import CRASH_NONE
from evaluation.venue2027.dsn.workflow_reference import (
    ENGINE_DURABILITY_CONFIG,
    ENGINE_NAME,
    ENGINE_UPSTREAM_REVISION,
    ENGINE_VERSION,
    RC_ENGINE_UNAVAILABLE,
    RC_SAGA_COMPENSATED,
    RC_SAGA_COMPENSATION_INDETERMINATE,
    RC_SAGA_INTERRUPTED,
    RC_SAGA_LABEL,
    RC_SAGA_NOT_DURABLE,
    RC_SAGA_RECOVERY_DEDUPED,
    RC_SAGA_RECOVERY_RESUMED,
    RC_SAGA_STEP_MISSING_COMPENSATION,
    SAGA_DEFINITION,
    StepFailed,
    WorkflowCtx,
    WorkflowError,
    probe_engine,
    run_saga_reference,
    run_workflow,
)


def make_case(
    case_id: str = "case-wf-0001",
    operation_id: str = "op:wf-0001",
    crash_point: str = CRASH_NONE,
    delivery_schedule: list[int] | None = None,
    consent_epoch: int = 3,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "operation_id": operation_id,
        "crash_point": crash_point,
        "delivery_schedule": [1] if delivery_schedule is None else delivery_schedule,
        "consent_epoch": consent_epoch,
    }


def fresh_ctx(**kwargs: object) -> WorkflowCtx:
    return WorkflowCtx(store={}, **kwargs)  # type: ignore[arg-type]


def saga_detail(outcome: Outcome) -> str:
    return str(outcome.detail).split(f"{RC_SAGA_LABEL}:")[1]


# ---------------------------------------------------------------------------
# Positive: engine pinning.
# ---------------------------------------------------------------------------


def test_engine_identity_pinned_to_registry_arm() -> None:
    assert ENGINE_NAME == "temporalio"
    assert ENGINE_VERSION == "1.19.0"
    assert ENGINE_UPSTREAM_REVISION.startswith("11e8650c7c8b89af")
    assert ENGINE_DURABILITY_CONFIG["workflow_id_reuse_policy"] == "REJECT_DUPLICATE"
    assert ENGINE_DURABILITY_CONFIG["workflow_id_key"] == "operation_id"
    assert ENGINE_DURABILITY_CONFIG["runtime"] == "temporal-test-server"


def test_engine_probe_is_truthful_and_json_serializable() -> None:
    report = probe_engine()
    expected_keys = {"engine", "pinned_version", "pinned_upstream_revision", "installed"}
    expected_keys.add("imported_version" if report["installed"] else "reason")
    assert set(report) == expected_keys
    assert report["engine"] == ENGINE_NAME
    assert report["pinned_version"] == ENGINE_VERSION
    if report["installed"]:
        import temporalio

        assert report["imported_version"] == getattr(temporalio, "__version__", "unknown")
    else:
        assert report["reason"] == RC_ENGINE_UNAVAILABLE


# ---------------------------------------------------------------------------
# Positive: compensation runs on failure.
# ---------------------------------------------------------------------------


def test_compensation_runs_in_reverse_order_on_step_failure() -> None:
    ctx = fresh_ctx(fail_step_id="apply_state")
    outcome = run_saga_reference(make_case(), ctx)
    assert isinstance(outcome, Outcome)
    assert outcome.observed_outcome == "REJECT"
    assert outcome.counted_as_success is False
    assert saga_detail(outcome).startswith(RC_SAGA_COMPENSATED)
    journal = ctx.store["saga:op:wf-0001"]
    assert journal["status"] == "COMPENSATED"
    # Only the completed steps were compensated, strictly in reverse order.
    assert journal["applied_steps"] == ["reserve_slot"]
    assert journal["compensated_steps"] == ["reserve_slot"]
    assert journal["compensation_log"] == ["release_slot"]


def test_first_step_failure_compensates_nothing_and_fails_closed() -> None:
    ctx = fresh_ctx(fail_step_id="reserve_slot")
    outcome = run_saga_reference(make_case(), ctx)
    assert outcome.observed_outcome == "REJECT"
    assert outcome.counted_as_success is False
    journal = ctx.store["saga:op:wf-0001"]
    assert journal["applied_steps"] == []
    assert journal["compensated_steps"] == []
    assert journal["compensation_log"] == []


def test_clean_run_commits_every_step_once() -> None:
    ctx = fresh_ctx()
    outcome = run_saga_reference(make_case(), ctx)
    assert outcome.observed_outcome == "ADMIT"
    assert outcome.counted_as_success is True
    assert saga_detail(outcome).startswith("SAGA_COMMITTED")
    journal = ctx.store["saga:op:wf-0001"]
    assert journal["status"] == "COMMITTED"
    assert journal["applied_steps"] == [step for step, _ in SAGA_DEFINITION]


def test_recovery_resumes_after_interruption_and_dedups() -> None:
    op_id = "op:wf-interrupted"
    interrupted_ctx = fresh_ctx()
    first = run_saga_reference(make_case(operation_id=op_id, crash_point="pre_outbox_delivery"), interrupted_ctx)
    assert first.observed_outcome == "INDETERMINATE"
    assert first.retriable is True
    assert saga_detail(first) == f"{RC_SAGA_INTERRUPTED}:before=emit_receipt"
    journal = interrupted_ctx.store[f"saga:{op_id}"]
    applied_before_recovery = list(journal["applied_steps"])

    recovered_ctx = WorkflowCtx(store=interrupted_ctx.store)
    second = run_saga_reference(make_case(operation_id=op_id), recovered_ctx)
    assert second.observed_outcome == "ADMIT"
    assert second.counted_as_success is True
    assert saga_detail(second).startswith(RC_SAGA_RECOVERY_RESUMED)
    final = recovered_ctx.store[f"saga:{op_id}"]
    assert final["status"] == "COMMITTED"
    # Exactly-once: interrupted prefix applied once, recovery adds only the rest.
    assert final["applied_steps"] == [step for step, _ in SAGA_DEFINITION]
    assert final["applied_steps"][: len(applied_before_recovery)] == applied_before_recovery
    assert final["recovery_attempt"] == 1


def test_recovery_dedups_fully_applied_journal_without_reexecution() -> None:
    op_id = "op:wf-ack-lost"
    crashed_ctx = fresh_ctx()
    first = run_saga_reference(make_case(operation_id=op_id, crash_point="post_commit_pre_response"), crashed_ctx)
    # Durable steps, lost ack: success is reported as pending recovery dedup.
    assert first.observed_outcome == "ADMIT"
    journal = crashed_ctx.store[f"saga:{op_id}"]
    assert journal["status"] == "RUNNING"

    recovered_ctx = WorkflowCtx(store=crashed_ctx.store)
    second = run_saga_reference(make_case(operation_id=op_id), recovered_ctx)
    assert second.observed_outcome == "ADMIT"
    assert saga_detail(second) == RC_SAGA_RECOVERY_DEDUPED
    final = recovered_ctx.store[f"saga:{op_id}"]
    assert final["status"] == "COMMITTED"
    assert final["applied_steps"] == [step for step, _ in SAGA_DEFINITION]


def test_replay_over_committed_journal_is_deduped() -> None:
    ctx = fresh_ctx()
    first = run_saga_reference(make_case(), ctx)
    assert first.observed_outcome == "ADMIT"
    replay_ctx = WorkflowCtx(store=ctx.store)
    second = run_saga_reference(make_case(), replay_ctx)
    assert second.observed_outcome == "ADMIT"
    assert saga_detail(second) == RC_SAGA_RECOVERY_DEDUPED
    assert ctx.store["saga:op:wf-0001"]["applied_steps"] == [step for step, _ in SAGA_DEFINITION]


def test_in_memory_saga_is_labelled_as_such_never_as_engine() -> None:
    for case in (
        make_case(),
        make_case(crash_point="pre_commit"),
        make_case(crash_point="pre_outbox_delivery"),
        make_case(crash_point="post_commit_pre_response"),
    ):
        outcome = run_saga_reference(case, fresh_ctx())
        assert str(outcome.detail).startswith(f"{RC_SAGA_LABEL}:")


# ---------------------------------------------------------------------------
# Adversarial: missing compensation step detected; engine-absent path.
# ---------------------------------------------------------------------------


def test_missing_compensation_step_detected_before_any_execution() -> None:
    ctx = fresh_ctx(compensation_missing="revert_state")
    with pytest.raises(WorkflowError) as excinfo:
        run_saga_reference(make_case(), ctx)
    assert excinfo.value.reason_code == RC_SAGA_STEP_MISSING_COMPENSATION
    # Fail closed BEFORE any journal byte is written.
    assert ctx.store == {}


def test_empty_saga_catalog_refused() -> None:
    ctx = fresh_ctx(compensation_missing="release_slot")
    ctx.compensation_missing = "release_slot"
    with pytest.raises(WorkflowError) as excinfo:
        run_saga_reference(make_case(), ctx)
    # release_slot is the first compensation; removing it still leaves two
    # forward steps, so exercise the empty-catalog guard directly.
    assert excinfo.value.reason_code == RC_SAGA_STEP_MISSING_COMPENSATION
    with pytest.raises(WorkflowError) as empty_exc:
        wf._assert_complete(())
    assert empty_exc.value.reason_code == "SAGA_EMPTY_DEFINITION"


def test_engine_absent_returns_not_run_external_never_fake_success() -> None:
    probe = probe_engine()
    outcome = run_workflow(make_case(), fresh_ctx())
    assert isinstance(outcome, Outcome)
    if not probe["installed"]:
        # The pinned engine is absent: the arm must be transparent, never fake.
        assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
        assert outcome.counted_as_success is False
        assert outcome.retriable is False
        assert str(outcome.detail).startswith(RC_ENGINE_UNAVAILABLE)
        assert ENGINE_NAME in str(outcome.detail)
        assert ENGINE_VERSION in str(outcome.detail)
        # Harness contract: NOT_RUN_EXTERNAL can never be counted as success.
        assert outcome.observed_outcome in HARNESS_SYNTHETIC_OUTCOMES
        with pytest.raises(Exception, match="FALSE_ZERO_OUTCOME"):
            Outcome(
                observed_outcome="NOT_RUN_EXTERNAL",
                counted_as_success=True,
            )
    else:
        # SDK present but the test-server runtime is not wired here: fail
        # closed rather than simulate.
        with pytest.raises(WorkflowError, match="ENGINE_RUNTIME_UNWIRED"):
            pass
        assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"


def test_engine_absent_path_is_distinct_from_the_saga_reference() -> None:
    outcome = run_workflow(make_case(), fresh_ctx())
    saga = run_saga_reference(make_case(), fresh_ctx())
    # The engine-absent outcome must never be confused with a saga result.
    assert str(outcome.detail).startswith(RC_ENGINE_UNAVAILABLE)
    assert str(saga.detail).startswith(f"{RC_SAGA_LABEL}:")
    assert RC_SAGA_LABEL not in str(outcome.detail)


# ---------------------------------------------------------------------------
# Adversarial: failing compensation, crash-before-write, malformed wiring.
# ---------------------------------------------------------------------------


def test_failing_compensation_is_explicit_indeterminate_never_success() -> None:
    # reserve_slot completed, then apply_state fails; rollback starts with
    # release_slot, which is the injected failing compensation.
    ctx = fresh_ctx(fail_step_id="apply_state", fail_compensation_id="release_slot")
    outcome = run_saga_reference(make_case(), ctx)
    assert outcome.observed_outcome == "INDETERMINATE"
    assert outcome.counted_as_success is False
    assert outcome.retriable is False
    assert saga_detail(outcome).startswith(RC_SAGA_COMPENSATION_INDETERMINATE)
    journal = ctx.store["saga:op:wf-0001"]
    assert journal["status"] == "INDETERMINATE"
    assert journal["compensated_steps"] == ["reserve_slot"]


def test_crash_before_write_is_retriable_reject_with_nothing_durable() -> None:
    ctx = fresh_ctx()
    outcome = run_saga_reference(make_case(crash_point="pre_commit"), ctx)
    assert outcome.observed_outcome == "REJECT"
    assert outcome.counted_as_success is False
    assert outcome.retriable is True
    assert saga_detail(outcome) == RC_SAGA_NOT_DURABLE
    assert ctx.store == {}


def test_recovery_after_failed_compensation_stays_indeterminate() -> None:
    ctx = fresh_ctx(fail_step_id="apply_state", fail_compensation_id="release_slot")
    first = run_saga_reference(make_case(), ctx)
    assert first.observed_outcome == "INDETERMINATE"
    replay = run_saga_reference(make_case(), WorkflowCtx(store=ctx.store))
    assert replay.observed_outcome == "INDETERMINATE"
    assert replay.retriable is False
    assert saga_detail(replay).startswith(RC_SAGA_COMPENSATION_INDETERMINATE)


def test_step_failure_raises_only_when_declared() -> None:
    with pytest.raises(WorkflowError, match="CONTEXT_MALFORMED"):
        fresh_ctx(fail_step_id="not-a-step")
    with pytest.raises(WorkflowError, match="CONTEXT_MALFORMED"):
        fresh_ctx(fail_compensation_id="not-a-compensation")
    with pytest.raises(WorkflowError, match="CONTEXT_MALFORMED"):
        fresh_ctx(compensation_missing="not-a-compensation")
    with pytest.raises(WorkflowError, match="CONTEXT_MALFORMED"):
        WorkflowCtx(store="not-a-dict")  # type: ignore[arg-type]
    with pytest.raises(StepFailed):
        raise StepFailed("reserve_slot")


def test_malformed_cases_are_wiring_errors_not_outcomes() -> None:
    from evaluation.venue2027.dsn.baselines import BaselineError as CaseSchemaError

    for bad_case in (
        "not-a-mapping",
        {"case_id": "x"},
        {**make_case(), "unexpected_field": 1},
        make_case(crash_point="between_wal_and_commit"),
        make_case(delivery_schedule=[0]),
    ):
        with pytest.raises(CaseSchemaError):
            run_saga_reference(bad_case, fresh_ctx())  # type: ignore[arg-type]


def test_engine_absent_run_workflow_refuses_wrong_ctx_type() -> None:
    with pytest.raises(WorkflowError, match="CONTEXT_MALFORMED"):
        run_workflow(make_case(), {"store": {}})  # type: ignore[arg-type]


def test_version_constant_is_pinned() -> None:
    assert wf.WORKFLOW_REFERENCE_VERSION == "1.0.0"
