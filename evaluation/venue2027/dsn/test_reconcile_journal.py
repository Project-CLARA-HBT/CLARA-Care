"""Tests for DSN-X06_reconcile_journal — three-view reconciliation.

Positive controls (must yield the adjudicated verdict):
- CONSISTENT: clinical row + ledger receipt + outbox record with one applied
  effect all agree (identity, version, digest) -> CONSISTENT with no repair
  plan (DSN-CASE-01).
- CONSISTENT_PENDING_DELIVERY: all three views present, no effect applied yet
  -> CONSISTENT (storage commit separated from downstream delivery,
  DSN-CASE-07).
- REPAIRABLE (missing outbox row, committed ledger): row + ledger agree,
  outbox ABSENT -> REPAIRABLE with an explicit deterministic plan whose steps
  re-queue the outbox bound to the committed row (CASE_MATRIX outbox-recovery
  window).
- REPAIRABLE (missing ledger): committed row + outbox present, ledger ABSENT
  -> REPAIRABLE with the ledger stamped from the committed row; durable
  success is NOT asserted from the row alone.

Adversarial controls (must fail closed):
- Missing delivery receipt is never treated as success: pending delivery is
  CONSISTENT_PENDING_DELIVERY, and an absent effect receipt never produces a
  verdict that claims an applied effect.
- A ledger that disagrees with the clinical row (row_version or transition
  digest) -> IRRECONCILABLE, never repaired, never coerced to success.
- Orphan ledger / orphan outbox without a committed row -> IRRECONCILABLE
  (never a "safe rejection" that could license a duplicate effect).
- INDETERMINATE is never coerced to CONSISTENT: corrupt views, timestamp
  anomalies, the all-absent picture and malformed views stay INDETERMINATE
  with stable reason codes.
- Determinism: identical inputs yield identical verdicts (sha256-stable), the
  repair plan is deterministic across repeated runs, and applying it is
  idempotent — re-running reconcile after each simulated plan application
  yields the same remaining plan until convergence, then CONSISTENT.
- Fail-closed boundary: reconcile never raises on semantically invalid
  evidence; unexpected internal errors yield INDETERMINATE.
"""

from __future__ import annotations

import dataclasses
import json

from evaluation.venue2027.dsn import reconcile_journal as rj

OP_ID = "op:w8-dsn-x06-0001"
OTHER_OP_ID = "op:w8-dsn-x06-other"
ROW_DIGEST = "a" * 64
OTHER_ROW_DIGEST = "b" * 64
EFFECT_DIGEST = "c" * 64
WAL_AT = 20
LEDGER_AT = 21
OUTBOX_AT = 20
DELIVERED_AT = 30
RECONCILER_AT = 100
EPOCH = 3


def clinical(
    *,
    op: str | None = OP_ID,
    status: rj.ViewStatus = rj.ViewStatus.PRESENT,
    row_version: int = 1,
    digest: str | None = ROW_DIGEST,
) -> rj.ClinicalView:
    if status is rj.ViewStatus.ABSENT:
        return rj.ClinicalView(status=status)
    return rj.ClinicalView(
        status=status,
        operation_id=op,
        row_version=row_version,
        wal_commit_logical_time=WAL_AT,
        row_digest_sha256=digest,
    )


def ledger(
    *,
    op: str | None = OP_ID,
    status: rj.ViewStatus = rj.ViewStatus.PRESENT,
    row_version: int = 1,
    decision: str = rj.DECISION_ACCEPT,
    transition_digest: str | None = ROW_DIGEST,
) -> rj.LedgerView:
    if status is rj.ViewStatus.ABSENT:
        return rj.LedgerView(status=status)
    return rj.LedgerView(
        status=status,
        operation_id=op,
        row_version=row_version,
        decision=decision,
        receipt_logical_time=LEDGER_AT,
        stored_transition_digest=transition_digest,
    )


def outbox(
    *,
    op: str | None = OP_ID,
    status: rj.ViewStatus = rj.ViewStatus.PRESENT,
    deliveries: tuple[rj.DeliveryReceipt, ...] = (),
) -> rj.OutboxView:
    if status is rj.ViewStatus.ABSENT:
        return rj.OutboxView(status=status)
    return rj.OutboxView(
        status=status,
        operation_id=op,
        recorded_logical_time=OUTBOX_AT,
        deliveries=deliveries,
    )


def applied_delivery(op: str = OP_ID, attempt: int = 1) -> rj.DeliveryReceipt:
    return rj.DeliveryReceipt(
        operation_id=op,
        attempt=attempt,
        effect_applied=True,
        delivered_logical_time=DELIVERED_AT,
        effect_receipt_digest=EFFECT_DIGEST,
    )


def reconcile(clin: rj.ClinicalView, led: rj.LedgerView, out: rj.OutboxView) -> rj.ReconcileVerdict:
    return rj.reconcile(
        clin,
        led,
        out,
        current_consent_epoch=EPOCH,
        reconciler_logical_time=RECONCILER_AT,
    )


# --- Positive controls --------------------------------------------------------


def test_consistent_triple_with_applied_effect():
    verdict = reconcile(clinical(), ledger(), outbox(deliveries=(applied_delivery(),)))
    assert verdict.outcome is rj.ReconcileOutcome.CONSISTENT
    assert verdict.reason_code == rj.REASON_CONSISTENT_ALL_VIEWS_AGREE
    assert verdict.details["operation_id"] == OP_ID
    assert verdict.details["effects_applied"] == 1
    assert verdict.details["effect_receipt_digest"] == EFFECT_DIGEST
    assert verdict.repair_plan.steps == ()


def test_consistent_pending_delivery_has_no_claimed_effect():
    verdict = reconcile(clinical(), ledger(), outbox())
    assert verdict.outcome is rj.ReconcileOutcome.CONSISTENT
    assert verdict.reason_code == rj.REASON_CONSISTENT_PENDING_DELIVERY
    assert verdict.details["effects_applied"] == 0
    assert verdict.details["effect_receipt_digest"] is None
    assert verdict.repair_plan.steps == ()


def test_missing_outbox_row_with_committed_ledger_is_repairable_with_plan():
    verdict = reconcile(clinical(), ledger(), outbox(status=rj.ViewStatus.ABSENT))
    assert verdict.outcome is rj.ReconcileOutcome.REPAIRABLE
    assert verdict.reason_code == rj.REASON_REPAIRABLE_MISSING_OUTBOX
    steps = verdict.repair_plan.steps
    assert [s.action for s in steps] == [rj.ACTION_ENQUEUE_OUTBOX]
    assert steps[0].view == rj.VIEW_OUTBOX
    assert steps[0].operation_id == OP_ID
    assert "idempotent by operation ID" in steps[0].detail
    assert "row_version=1" in steps[0].detail


def test_missing_ledger_with_committed_row_is_repairable_not_committed():
    verdict = reconcile(
        clinical(), ledger(status=rj.ViewStatus.ABSENT), outbox(deliveries=(applied_delivery(),))
    )
    assert verdict.outcome is rj.ReconcileOutcome.REPAIRABLE
    assert verdict.reason_code == rj.REASON_REPAIRABLE_MISSING_LEDGER
    actions = [s.action for s in verdict.repair_plan.steps]
    # The outbox already records an applied effect, so the only missing
    # evidence is the ledger receipt — exactly one deterministic repair.
    assert actions == [rj.ACTION_MARK_LEDGER_COMMITTED]
    assert verdict.repair_plan.steps[0].order == 0
    # Durable success is never invented from the row + effect alone.
    assert verdict.details["operation_id"] == OP_ID


def test_missing_outbox_and_ledger_repairable_ordered_plan():
    verdict = reconcile(
        clinical(), ledger(status=rj.ViewStatus.ABSENT), outbox(status=rj.ViewStatus.ABSENT)
    )
    assert verdict.outcome is rj.ReconcileOutcome.REPAIRABLE
    assert verdict.reason_code == rj.REASON_REPAIRABLE_MISSING_OUTBOX_AND_LEDGER
    actions = [s.action for s in verdict.repair_plan.steps]
    assert actions == [rj.ACTION_MARK_LEDGER_COMMITTED, rj.ACTION_ENQUEUE_OUTBOX]
    orders = [s.order for s in verdict.repair_plan.steps]
    assert orders == sorted(orders)


def test_verdict_round_trip_is_lossless():
    verdict = reconcile(clinical(), ledger(), outbox(status=rj.ViewStatus.ABSENT))
    payload = json.loads(json.dumps(verdict.to_dict()))
    restored = rj.ReconcileVerdict.from_dict(payload)
    assert restored == verdict
    assert rj.verdict_sha256(restored) == rj.verdict_sha256(verdict)


# --- Adversarial: missing receipt is never success -----------------------------


def test_missing_delivery_receipt_never_counts_as_applied_effect():
    verdict = reconcile(clinical(), ledger(), outbox())
    assert verdict.details["effects_applied"] == 0
    assert verdict.outcome is not rj.ReconcileOutcome.INDETERMINATE
    assert verdict.details["effect_receipt_digest"] is None


def test_committed_row_alone_never_yields_consistent():
    # Missing ledger with the outbox also absent: repairable at best, never
    # CONSISTENT — a missing receipt is never durable success.
    verdict = reconcile(
        clinical(), ledger(status=rj.ViewStatus.ABSENT), outbox(status=rj.ViewStatus.ABSENT)
    )
    assert verdict.outcome is rj.ReconcileOutcome.REPAIRABLE
    actions = [s.action for s in verdict.repair_plan.steps]
    assert rj.ACTION_MARK_LEDGER_COMMITTED in actions
    assert verdict.outcome is not rj.ReconcileOutcome.CONSISTENT


def test_ledger_reject_decision_is_irreconcilable_not_success():
    verdict = reconcile(
        clinical(), ledger(decision="REJECT"), outbox(deliveries=(applied_delivery(),))
    )
    assert verdict.outcome is rj.ReconcileOutcome.IRRECONCILABLE
    assert verdict.reason_code == rj.REASON_IRRECONCILABLE_LEDGER_DISAGREES
    assert verdict.repair_plan.steps == ()


# --- Adversarial: ledger disagrees with clinical row ---------------------------


def test_ledger_row_version_disagreement_irreconcilable():
    verdict = reconcile(
        clinical(row_version=2), ledger(row_version=1), outbox(deliveries=(applied_delivery(),))
    )
    assert verdict.outcome is rj.ReconcileOutcome.IRRECONCILABLE
    assert verdict.reason_code == rj.REASON_IRRECONCILABLE_ROW_VERSION_MISMATCH
    assert verdict.details["clinical_row_version"] == 2
    assert verdict.details["ledger_row_version"] == 1
    assert verdict.repair_plan.steps == ()


def test_ledger_transition_digest_tamper_irreconcilable():
    verdict = reconcile(clinical(), ledger(transition_digest=OTHER_ROW_DIGEST), outbox())
    assert verdict.outcome is rj.ReconcileOutcome.IRRECONCILABLE
    assert verdict.reason_code == rj.REASON_IRRECONCILABLE_DIGEST_MISMATCH
    assert verdict.details["stored_transition_digest"] == OTHER_ROW_DIGEST
    assert verdict.details["row_digest_sha256"] == ROW_DIGEST
    assert verdict.repair_plan.steps == ()


def test_operation_mismatch_irreconcilable():
    verdict = reconcile(clinical(op=OTHER_OP_ID), ledger(), outbox())
    assert verdict.outcome is rj.ReconcileOutcome.IRRECONCILABLE
    assert verdict.reason_code == rj.REASON_IRRECONCILABLE_OPERATION_MISMATCH
    # Identity anchors on the clinical row; the dissenting views are named.
    assert verdict.details["operation_id"] == OTHER_OP_ID
    assert verdict.details["mismatches"][rj.VIEW_LEDGER] == OP_ID
    assert verdict.details["mismatches"][rj.VIEW_OUTBOX] == OP_ID


def test_effect_digest_divergence_irreconcilable():
    duplicate = rj.DeliveryReceipt(
        operation_id=OP_ID,
        attempt=2,
        effect_applied=True,
        delivered_logical_time=DELIVERED_AT + 1,
        effect_receipt_digest=OTHER_ROW_DIGEST,
    )
    verdict = reconcile(
        clinical(), ledger(), outbox(deliveries=(applied_delivery(), duplicate))
    )
    assert verdict.outcome is rj.ReconcileOutcome.IRRECONCILABLE
    assert verdict.reason_code == rj.REASON_IRRECONCILABLE_EFFECT_DIVERGENCE
    assert verdict.repair_plan.steps == ()


def test_orphan_ledger_without_row_irreconcilable():
    verdict = reconcile(
        clinical(status=rj.ViewStatus.ABSENT), ledger(), outbox(status=rj.ViewStatus.ABSENT)
    )
    assert verdict.outcome is rj.ReconcileOutcome.IRRECONCILABLE
    assert verdict.reason_code == rj.REASON_IRRECONCILABLE_ORPHAN_LEDGER
    assert verdict.repair_plan.steps == ()


def test_orphan_outbox_without_row_irreconcilable():
    verdict = reconcile(
        clinical(status=rj.ViewStatus.ABSENT), ledger(status=rj.ViewStatus.ABSENT), outbox()
    )
    assert verdict.outcome is rj.ReconcileOutcome.IRRECONCILABLE
    assert verdict.reason_code == rj.REASON_IRRECONCILABLE_ORPHAN_OUTBOX
    assert verdict.repair_plan.steps == ()


# --- Adversarial: INDETERMINATE is never coerced to CONSISTENT -----------------


def test_all_views_absent_is_indeterminate():
    verdict = reconcile(
        clinical(status=rj.ViewStatus.ABSENT),
        ledger(status=rj.ViewStatus.ABSENT),
        outbox(status=rj.ViewStatus.ABSENT),
    )
    assert verdict.outcome is rj.ReconcileOutcome.INDETERMINATE
    assert verdict.reason_code == rj.REASON_INDETERMINATE_NO_EVIDENCE
    assert verdict.repair_plan.steps == ()


def test_corrupt_views_are_indeterminate():
    for kwargs in (
        dict(clin=rj.ClinicalView(status=rj.ViewStatus.CORRUPT, operation_id=OP_ID)),
        dict(led=rj.LedgerView(status=rj.ViewStatus.CORRUPT, operation_id=OP_ID)),
        dict(out=rj.OutboxView(status=rj.ViewStatus.CORRUPT, operation_id=OP_ID)),
    ):
        verdict = reconcile(
            kwargs.get("clin", clinical()),
            kwargs.get("led", ledger()),
            kwargs.get("out", outbox()),
        )
        assert verdict.outcome is rj.ReconcileOutcome.INDETERMINATE
        assert verdict.reason_code.startswith("INDETERMINATE_")
        assert verdict.repair_plan.steps == ()


def test_timestamp_anomaly_is_indeterminate():
    future_ledger = dataclasses.replace(ledger(), receipt_logical_time=RECONCILER_AT + 1)
    verdict = reconcile(clinical(), future_ledger, outbox())
    assert verdict.outcome is rj.ReconcileOutcome.INDETERMINATE
    assert verdict.reason_code == rj.REASON_INDETERMINATE_TIMESTAMP_ANOMALY


def test_malformed_views_are_indeterminate_with_stable_codes():
    bad_row = rj.ClinicalView(
        status=rj.ViewStatus.PRESENT,
        operation_id=OP_ID,
        row_version=-1,
        wal_commit_logical_time=WAL_AT,
        row_digest_sha256=ROW_DIGEST,
    )
    verdict = reconcile(bad_row, ledger(), outbox())
    assert verdict.outcome is rj.ReconcileOutcome.INDETERMINATE
    assert verdict.reason_code == rj.REASON_MALFORMED_CLINICAL_VIEW
    assert verdict.details["invalid_fields"] == [f"{rj.VIEW_CLINICAL}.row_version"]

    bad_outbox = rj.OutboxView(
        status=rj.ViewStatus.PRESENT,
        operation_id=OP_ID,
        recorded_logical_time=OUTBOX_AT,
        deliveries=(
            rj.DeliveryReceipt(
                operation_id=OP_ID,
                attempt=1,
                effect_applied=True,
                delivered_logical_time=DELIVERED_AT,
                effect_receipt_digest="zz",
            ),
        ),
    )
    verdict = reconcile(clinical(), ledger(), bad_outbox)
    assert verdict.outcome is rj.ReconcileOutcome.INDETERMINATE
    assert verdict.reason_code == rj.REASON_MALFORMED_OUTBOX_VIEW
    assert f"{rj.VIEW_OUTBOX}.delivery.effect_receipt_digest" in verdict.details["invalid_fields"]


def test_malformed_governance_inputs_fail_closed():
    for bad_epoch, bad_time in ((-1, RECONCILER_AT), (EPOCH, -5)):
        verdict = rj.reconcile(
            clinical(),
            ledger(),
            outbox(),
            current_consent_epoch=bad_epoch,
            reconciler_logical_time=bad_time,
        )
        assert verdict.outcome is rj.ReconcileOutcome.INDETERMINATE
        assert verdict.reason_code in (
            rj.REASON_MALFORMED_CONSENT_EPOCH,
            rj.REASON_MALFORMED_RECONCILER_TIME,
        )


# --- Determinism and idempotent plan application -------------------------------


def test_reconcile_is_deterministic():
    views = (clinical(), ledger(), outbox(status=rj.ViewStatus.ABSENT))
    first = reconcile(*views)
    second = reconcile(*views)
    assert first == second
    assert rj.verdict_sha256(first) == rj.verdict_sha256(second)
    assert first.to_dict() == second.to_dict()


def test_repair_plan_is_deterministic_across_runs():
    plans = {
        tuple(rj.verdict_sha256(reconcile(clinical(), ledger(), outbox(status=rj.ViewStatus.ABSENT))).encode())
        for _ in range(5)
    }
    assert len(plans) == 1
    verdict = reconcile(clinical(), ledger(), outbox(status=rj.ViewStatus.ABSENT))
    # Same inputs (independent instances) -> structurally identical plan.
    again = reconcile(clinical(), ledger(), outbox(status=rj.ViewStatus.ABSENT))
    assert verdict.repair_plan == again.repair_plan
    assert [s.action for s in verdict.repair_plan.steps] == [rj.ACTION_ENQUEUE_OUTBOX]


def _apply_step(out: rj.OutboxView, step: rj.RepairStep) -> rj.OutboxView:
    """Simulate applying one plan step to the outbox view (idempotently)."""

    if step.action == rj.ACTION_ENQUEUE_OUTBOX:
        if out.status is rj.ViewStatus.PRESENT:
            return out
        return outbox(deliveries=out.deliveries)
    if step.action == rj.ACTION_RECORD_DELIVERY:
        applied = applied_delivery()
        if any(d.effect_applied for d in out.deliveries):
            return out
        return dataclasses.replace(out, deliveries=(applied,))
    return out


def test_repair_plan_applies_idempotently_to_consistency():
    clin, led = clinical(), ledger()
    out = outbox(status=rj.ViewStatus.ABSENT)
    seen_reasons: list[str] = []
    for _ in range(10):
        verdict = reconcile(clin, led, out)
        seen_reasons.append(verdict.reason_code)
        if verdict.outcome is rj.ReconcileOutcome.CONSISTENT:
            break
        assert verdict.outcome is rj.ReconcileOutcome.REPAIRABLE
        for step in verdict.repair_plan.steps:
            out = _apply_step(out, step)
    else:  # pragma: no cover - guards non-convergence
        raise AssertionError("repair did not converge within bound")
    assert seen_reasons[0] == rj.REASON_REPAIRABLE_MISSING_OUTBOX
    assert seen_reasons[-1] == rj.REASON_CONSISTENT_PENDING_DELIVERY
    # Re-applying the final step is a no-op: the view stays CONSISTENT.
    final = reconcile(clin, led, out)
    assert final.outcome is rj.ReconcileOutcome.CONSISTENT
    assert final.repair_plan.steps == ()


def test_repair_plan_idempotent_under_duplicate_application():
    clin, led = clinical(), ledger()
    out = outbox(status=rj.ViewStatus.ABSENT)
    verdict = reconcile(clin, led, out)
    enqueue = verdict.repair_plan.steps[0]
    once = _apply_step(out, enqueue)
    twice = _apply_step(once, enqueue)
    assert once == twice
    assert twice.status is rj.ViewStatus.PRESENT


def test_irreconcilable_never_carries_a_repair_plan():
    combos = (
        (clinical(row_version=2), ledger(row_version=1), outbox()),
        (clinical(), ledger(transition_digest=OTHER_ROW_DIGEST), outbox()),
        (clinical(status=rj.ViewStatus.ABSENT), ledger(), outbox(status=rj.ViewStatus.ABSENT)),
        (clinical(status=rj.ViewStatus.ABSENT), ledger(status=rj.ViewStatus.ABSENT), outbox()),
    )
    for clin, led, out in combos:
        verdict = reconcile(clin, led, out)
        assert verdict.outcome is rj.ReconcileOutcome.IRRECONCILABLE
        assert verdict.repair_plan.steps == ()


# --- Self-check entry point ----------------------------------------------------


def test_demo_and_cli_are_deterministic():
    demo_one = rj._demo()
    demo_two = rj._demo()
    assert demo_one == demo_two
    assert demo_one["results"]["consistent_triple"]["outcome"] == "CONSISTENT"
    assert demo_one["results"]["missing_outbox_row"]["outcome"] == "REPAIRABLE"
    assert demo_one["results"]["ledger_disagrees"]["outcome"] == "IRRECONCILABLE"
    assert rj.main(["--json"]) == 0
