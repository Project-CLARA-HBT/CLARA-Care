"""Deterministic property, metamorphic, and adversarial tests for DSN-unit (P05).

Purpose
-------
Property and metamorphic tests over the REAL DSN candidate, state machine, and
comparators — imported directly and never stubbed or reimplemented:

- ``evaluation.venue2027.dsn.candidate`` — the arm-B3 recoverable safety journal
  (:func:`execute_operation`, :func:`recoverable_outcome`, :func:`verify_journal`,
  :func:`corrupt_journal`, :func:`run_candidate`, :class:`SafetyJournal`,
  :class:`DurableStores`, :func:`ablation_no_journal_execute`);
- ``evaluation.venue2027.dsn.state_machine`` — the 3-way durable state machine
  (:func:`evaluate_durability`, :func:`reconcile`, :func:`recover`,
  :class:`DurableState`, :class:`EventHistory`, :class:`DurabilityVerdict`);
- ``evaluation.venue2027.dsn.baselines`` — the baseline fidelity suite arms
  and constant-stub refusal gates (:func:`run_baseline`, :func:`refuse_constant_stub`);
- ``evaluation.venue2027.dsn.independent_oracle`` — the independent declarative
  reference oracle (:func:`adjudicate`, :func:`verify_independence`).

Test families
-------------
1. **Positive boundaries** — documented guarantees hold end to end: nominal clean
   execution (DSN-CASE-01), outbox delayed / pending delivery (DSN-CASE-07),
   pre-revocation commit surviving later epoch bump, reconciler helper,
   candidate harness adapter, and mechanism description invariants.
2. **Negative boundaries** — crash before commit (DSN-CASE-02), consent revoked
   before commit (DSN-CASE-05), outbox failure, non-accept receipt, and structural
   refusals (malformed intent, unknown crash window, bad delivery schedule,
   corrupt durable state).
3. **Unknown boundaries** — fail-closed adjudication: torn clinical row, tampered
   decision receipt (DSN-CASE-06), timestamp anomalies, cross-channel operation
   mismatch, orphan receipt / outbox, candidate journal corruption modes
   (payload flip, forged digest, dropped interior entry, unknown kind),
   contradictions in journal (abort+commit, duplicate commit, effect without commit,
   divergent effect digests), event history anomalies, and oracle unknown family.
4. **Crash-window and duplicate-delivery scenarios** — systematic sweep of all
   four crash cut points (pre_commit, post_commit_pre_response, pre_outbox_delivery,
   mid_effect) with recovery resumption; broker replay (DSN-CASE-04) with duplicate
   deliveries deduped by write-ahead effect records; contrast with journal-less
   ablation.
5. **Two-step metamorphic relations**:
   - MR1: Replaying an acked operation is idempotent (zero additional row writes,
     zero additional effect applications, identical COMMITTED verdict).
   - MR2: Adding a recovery step after a crash cannot lose a committed effect
     (committed or write-ahead journaled effects survive and materialize exactly once).
   - MR3: Truncation (legal prefix / crash window) vs interior tampering distinction
     (dropping the last entry is a valid prefix that resumes; dropping an interior
     entry breaks the chain and fails closed).
   - MR4: Delivery schedule expansion monotonicity (expanding delivery schedule
     causes zero additional row writes and zero additional effect applications).
6. **Mutation checks** — canonical mutants killed: skip journal verification,
   skip consent check at commit, skip write-ahead effect journaling, ignore
   duplicate effect divergence, refuse constant / all-deny stubs, and verify
   oracle source independence.
7. **Seeded safety invariant sweep & replay determinism** — deterministic sweep
   over randomized parameter tuples with fixed seed; zero forbidden commits;
   byte-level replay identical transcripts.

Version
-------
``DSN_ALGORITHM_PROPERTIES_TESTS_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import random
import unittest.mock
from typing import Any, Final

import pytest

from evaluation.venue2027._shared import oracle_kernel
from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.dsn import baselines as bl
from evaluation.venue2027.dsn import candidate as cand
from evaluation.venue2027.dsn import independent_oracle as oracle
from evaluation.venue2027.dsn import state_machine as sm

DSN_ALGORITHM_PROPERTIES_TESTS_VERSION: Final[str] = "1.0.0"

#: Fixed seed for every randomized step of this suite (manifest: "seed all randomness").
FIXED_SEED: Final[int] = 20271116

OP_DEFAULT: Final[str] = "op:dsn-prop-0001"
PAYLOAD_DEFAULT: Final[str] = "a" * 64
EPOCH_DEFAULT: Final[int] = 3
LOGICAL_TIME_DEFAULT: Final[int] = 10


# ---------------------------------------------------------------------------
# Test fixture builders (pure, deterministic, synthetic identifiers)
# ---------------------------------------------------------------------------


def _candidate_intent(
    op_id: str = OP_DEFAULT,
    epoch: int = EPOCH_DEFAULT,
    payload_digest: str | None = None,
    logical_time: int = LOGICAL_TIME_DEFAULT,
) -> cand.WriteIntent:
    return cand.WriteIntent(
        operation_id=op_id,
        tenant_id="tenant:clinical-alpha",
        principal_id="user:clinician-1",
        purpose="medication_update",
        authorized_consent_epoch=epoch,
        payload_digest_sha256=payload_digest or cand._synthetic_digest(op_id),
        issued_logical_time=logical_time,
    )


def _state_machine_intent(
    op_id: str = OP_DEFAULT,
    epoch: int = EPOCH_DEFAULT,
    payload_digest: str | None = None,
    logical_time: int = LOGICAL_TIME_DEFAULT,
) -> sm.WriteIntent:
    return sm.WriteIntent(
        operation_id=op_id,
        tenant_id="tenant:clinical-alpha",
        principal_id="user:clinician-1",
        purpose="medication_update",
        authorized_consent_epoch=epoch,
        payload_digest_sha256=payload_digest or sm._synthetic_digest(op_id),
        issued_logical_time=logical_time,
    )


def _committed_durable_state(
    op_id: str = OP_DEFAULT,
    epoch: int = EPOCH_DEFAULT,
    deliveries_count: int = 1,
    current_epoch: int = EPOCH_DEFAULT,
    reconciler_time: int = 100,
    divergent_delivery: bool = False,
) -> sm.DurableState:
    digest = sm._synthetic_digest(op_id)
    deliveries: list[sm.DeliveryReceipt] = []
    for att in range(1, deliveries_count + 1):
        eff_digest = sm._synthetic_digest(
            f"{op_id}:divergent" if (divergent_delivery and att > 1) else f"{op_id}:effect"
        )
        deliveries.append(
            sm.DeliveryReceipt(
                operation_id=op_id,
                attempt=att,
                effect_applied=True,
                delivered_logical_time=30 + att,
                effect_receipt_digest=eff_digest,
            )
        )
    return sm.DurableState(
        clinical_row=sm.ClinicalRowState(
            status=sm.ChannelStatus.PRESENT,
            operation_id=op_id,
            row_version=1,
            wal_commit_logical_time=20,
            consent_epoch_at_commit=epoch,
            row_digest_sha256=digest,
        ),
        decision_receipt=sm.DecisionReceipt(
            status=sm.ChannelStatus.PRESENT,
            operation_id=op_id,
            row_version=1,
            consent_epoch=epoch,
            decision=sm.RECEIPT_DECISION_ACCEPT,
            receipt_logical_time=21,
            receipt_digest_sha256=sm._synthetic_digest(f"{op_id}:receipt"),
            stored_transition_digest=digest,
        ),
        outbox=sm.OutboxState(
            status=sm.ChannelStatus.PRESENT,
            operation_id=op_id,
            recorded_logical_time=20,
            deliveries=tuple(deliveries),
        ),
        current_consent_epoch=current_epoch,
        reconciler_logical_time=reconciler_time,
    )


def _blank_durable_state(
    epoch: int = EPOCH_DEFAULT, reconciler_time: int = 100
) -> sm.DurableState:
    return sm.DurableState(
        clinical_row=sm.ClinicalRowState(status=sm.ChannelStatus.ABSENT),
        decision_receipt=sm.DecisionReceipt(status=sm.ChannelStatus.ABSENT),
        outbox=sm.OutboxState(status=sm.ChannelStatus.ABSENT),
        current_consent_epoch=epoch,
        reconciler_logical_time=reconciler_time,
    )


# ---------------------------------------------------------------------------
# 1. Positive boundaries (nominal success and valid edge invariants)
# ---------------------------------------------------------------------------


class TestPositiveBoundaries:
    def test_nominal_execution_clean_commit(self) -> None:
        """DSN-CASE-01 nominal transition: candidate completes with 1 row write,
        1 effect apply, and verifiable hash chain."""
        intent = _candidate_intent()
        stores = cand.DurableStores()
        report = cand.execute_operation(
            intent,
            crash_point=cand.CRASH_NONE,
            delivery_schedule=(1,),
            stores=stores,
        )

        assert report.stopped_at == "completed"
        assert not report.resumed
        assert report.row_writes == 1
        assert report.effect_applications == 1
        assert report.deliveries_observed == 1
        assert report.deliveries_deduped == 0
        assert stores.row_version(intent.operation_id) == 1
        assert stores.effect_digest(intent.operation_id) is not None

        # Verify journal structural integrity
        defects = cand.verify_journal(report.journal, intent.operation_id)
        assert defects == ()

        # Recoverable outcome pure evaluation
        outcome = cand.recoverable_outcome(report.journal, intent)
        assert outcome.outcome == cand.VERDICT_COMMITTED
        assert outcome.reason_code == cand.RC_COMMITTED_EFFECT_APPLIED
        assert not outcome.retriable

    def test_pending_delivery_without_schedule(self) -> None:
        """DSN-CASE-07: Outbox delayed / delivery pending. The row is committed
        and outbox recorded, but delivery has not executed."""
        intent = _candidate_intent()
        stores = cand.DurableStores()
        report = cand.execute_operation(
            intent,
            crash_point=cand.CRASH_NONE,
            delivery_schedule=(),
            stores=stores,
        )

        assert report.stopped_at == "completed"
        assert report.row_writes == 1
        assert report.effect_applications == 0
        assert stores.row_version(intent.operation_id) == 1
        assert stores.effect_digest(intent.operation_id) is None

        outcome = cand.recoverable_outcome(report.journal, intent)
        assert outcome.outcome == cand.VERDICT_COMMITTED
        assert outcome.reason_code == cand.RC_COMMITTED_PENDING_DELIVERY

        # State machine equivalent
        sm_intent = _state_machine_intent()
        sm_state = _committed_durable_state(deliveries_count=0)
        verdict = sm.evaluate_durability(sm_intent, sm_state)
        assert verdict.outcome == sm.DurabilityOutcome.COMMITTED
        assert verdict.reason_code == sm.REASON_COMMITTED_PENDING_DELIVERY

    def test_pre_revocation_commit_survives_later_epoch(self) -> None:
        """Governance ordering: a commit authorized and finalized at epoch E
        survives a later revocation / bump to epoch E+1."""
        sm_intent = _state_machine_intent(epoch=3)
        sm_state = _committed_durable_state(epoch=3, current_epoch=4)
        verdict = sm.evaluate_durability(sm_intent, sm_state)
        assert verdict.outcome == sm.DurabilityOutcome.COMMITTED
        assert verdict.reason_code == sm.REASON_COMMITTED_PRE_REVOCATION

    def test_state_machine_reconciler_helper(self) -> None:
        """The reconciler helper reconstructs minimal intent envelope from
        state and confirms COMMITTED."""
        sm_state = _committed_durable_state()
        verdict = sm.reconcile(OP_DEFAULT, sm_state)
        assert verdict.outcome == sm.DurabilityOutcome.COMMITTED
        assert verdict.reason_code == sm.REASON_COMMITTED_EFFECT_APPLIED

    def test_candidate_harness_adapter_admit(self) -> None:
        """Candidate run_candidate harness adapter returns ADMIT with
        counted_as_success=True on clean case."""
        case = {
            "case_id": "DSN-CASE-01",
            "operation_id": OP_DEFAULT,
            "authorized_consent_epoch": 3,
            "delivery_schedule": [1],
        }
        outcome = cand.run_candidate(case)
        assert isinstance(outcome, Outcome)
        assert outcome.observed_outcome == "ADMIT"
        assert outcome.counted_as_success
        assert not outcome.retriable

    def test_mechanism_description_invariants(self) -> None:
        """Candidate describe_mechanism statement exposes expected invariants."""
        desc = cand.describe_mechanism()
        assert desc["candidate_id"] == cand.CANDIDATE_ID
        assert desc["version"] == cand.CANDIDATE_VERSION
        assert desc["enforcement"]["write_ahead_effect_record"]
        assert desc["enforcement"]["hash_chained_lineage"]
        assert desc["enforcement"]["fail_closed_adjudication"]

    def test_independent_oracle_positive_families(self) -> None:
        """Independent oracle maps positive families accurately."""
        clean_res = oracle.adjudicate({"case_id": "C1", "family": "clean_recovery"})
        assert clean_res.outcome == "ADMIT"
        dup_res = oracle.adjudicate({"case_id": "C2", "family": "duplicate_retry"})
        assert dup_res.outcome == "ADMIT"


# ---------------------------------------------------------------------------
# 2. Negative boundaries (adversarial, revocations, and refusals)
# ---------------------------------------------------------------------------


class TestNegativeBoundaries:
    def test_crash_pre_commit_rejected_retriable(self) -> None:
        """DSN-CASE-02: Crash before SQL COMMIT produces REJECTED with retriable=True.
        Nothing durable is mutated in stores."""
        intent = _candidate_intent()
        stores = cand.DurableStores()
        report = cand.execute_operation(
            intent,
            crash_point=cand.CRASH_PRE_COMMIT,
            delivery_schedule=(1,),
            stores=stores,
        )

        assert report.stopped_at == f"crash:{cand.CRASH_PRE_COMMIT}"
        assert report.row_writes == 0
        assert report.effect_applications == 0
        assert stores.row_version(intent.operation_id) is None
        assert stores.effect_digest(intent.operation_id) is None

        outcome = cand.recoverable_outcome(report.journal, intent)
        assert outcome.outcome == cand.VERDICT_REJECTED
        assert outcome.reason_code == cand.RC_NOT_COMMITTED_NO_DURABLE_EVIDENCE
        assert outcome.retriable

    def test_state_machine_nothing_durable_rejected(self) -> None:
        """State machine on blank state yields REJECTED / NOT_COMMITTED_NO_DURABLE_EVIDENCE."""
        intent = _state_machine_intent()
        state = _blank_durable_state()
        verdict = sm.evaluate_durability(intent, state)
        assert verdict.outcome == sm.DurabilityOutcome.REJECTED
        assert verdict.reason_code == sm.REASON_NOT_COMMITTED_NO_DURABLE_EVIDENCE

    def test_consent_revoked_before_commit_aborted_stable(self) -> None:
        """DSN-CASE-05: Revocation race. Consent revoked before commit appends
        durable ABORT; stores are untouched; replay stays stable rejected."""
        intent = _candidate_intent(epoch=2)
        stores = cand.DurableStores()
        report = cand.execute_operation(
            intent,
            consent_epoch_at_commit=3,  # epoch moved from 2 to 3
            delivery_schedule=(1,),
            stores=stores,
        )

        assert report.stopped_at == "aborted"
        assert report.row_writes == 0
        assert report.effect_applications == 0
        assert stores.row_version(intent.operation_id) is None

        outcome = cand.recoverable_outcome(report.journal, intent)
        assert outcome.outcome == cand.VERDICT_REJECTED
        assert outcome.reason_code == cand.RC_CONSENT_REVOKED_BEFORE_COMMIT
        assert not outcome.retriable

        # Resuming an aborted journal halts immediately at rejected_stable
        resumed = cand.execute_operation(
            intent,
            journal=report.journal,
            stores=stores,
        )
        assert resumed.stopped_at == "rejected_stable"
        assert resumed.row_writes == 0
        assert resumed.effect_applications == 0

    def test_state_machine_forbidden_write_post_revocation(self) -> None:
        """State machine rejects clinical row stamped with post-revocation epoch."""
        intent = _state_machine_intent(epoch=2)
        state = _committed_durable_state(epoch=3)  # commit stamped 3 > authorized 2
        verdict = sm.evaluate_durability(intent, state)
        assert verdict.outcome == sm.DurabilityOutcome.REJECTED
        assert verdict.reason_code == sm.REASON_FORBIDDEN_WRITE_POST_REVOCATION

    def test_state_machine_outbox_failure_rejected(self) -> None:
        """Durable outbox fsync failure record yields REJECTED."""
        intent = _state_machine_intent()
        state = dataclasses.replace(
            _committed_durable_state(),
            outbox=sm.OutboxState(
                status=sm.ChannelStatus.FAILED,
                operation_id=OP_DEFAULT,
                failure_reason="disk_quota_exceeded",
            ),
        )
        verdict = sm.evaluate_durability(intent, state)
        assert verdict.outcome == sm.DurabilityOutcome.REJECTED
        assert verdict.reason_code == sm.REASON_OUTBOX_FSYNC_FAILED

    def test_state_machine_non_accept_decision_rejected(self) -> None:
        """Ledger receipt with non-accept decision yields REJECTED."""
        intent = _state_machine_intent()
        state = dataclasses.replace(
            _committed_durable_state(),
            decision_receipt=sm.DecisionReceipt(
                status=sm.ChannelStatus.PRESENT,
                operation_id=OP_DEFAULT,
                row_version=1,
                consent_epoch=3,
                decision="DENY",
                receipt_logical_time=21,
                receipt_digest_sha256=sm._synthetic_digest("denied"),
            ),
        )
        verdict = sm.evaluate_durability(intent, state)
        assert verdict.outcome == sm.DurabilityOutcome.REJECTED

    @pytest.mark.parametrize(
        ("bad_intent", "expected_code"),
        [
            ({"operation_id": "", "tenant_id": "t", "principal_id": "p", "purpose": "self", "authorized_consent_epoch": 1, "payload_digest_sha256": "a" * 64, "issued_logical_time": 1}, cand.RC_MALFORMED_WRITE_INTENT),
            ({"operation_id": "op:1", "tenant_id": "t", "principal_id": "p", "purpose": "self", "authorized_consent_epoch": -1, "payload_digest_sha256": "a" * 64, "issued_logical_time": 1}, cand.RC_MALFORMED_WRITE_INTENT),
            ({"operation_id": "op:1", "tenant_id": "t", "principal_id": "p", "purpose": "self", "authorized_consent_epoch": 1, "payload_digest_sha256": "badsha", "issued_logical_time": 1}, cand.RC_MALFORMED_WRITE_INTENT),
        ],
    )
    def test_candidate_malformed_intent_refused(
        self, bad_intent: dict[str, Any], expected_code: str
    ) -> None:
        """Malformed write intents are refused before state mutation."""
        intent = cand.WriteIntent(**bad_intent)
        with pytest.raises(cand.CandidateError) as excinfo:
            cand.execute_operation(intent)
        assert excinfo.value.reason_code == expected_code

        # recoverable_outcome on malformed intent fails closed with INDETERMINATE
        outcome = cand.recoverable_outcome(cand.SafetyJournal(), intent)
        assert outcome.outcome == cand.VERDICT_INDETERMINATE

    def test_candidate_unknown_crash_point_refused(self) -> None:
        """Unknown crash window raises CandidateError(RC_CRASH_POINT_UNKNOWN)."""
        intent = _candidate_intent()
        with pytest.raises(cand.CandidateError) as excinfo:
            cand.execute_operation(intent, crash_point="corrupt_cut_point")
        assert excinfo.value.reason_code == cand.RC_CRASH_POINT_UNKNOWN

    def test_candidate_malformed_schedule_refused(self) -> None:
        """Delivery schedule containing non-positive ints is refused."""
        intent = _candidate_intent()
        with pytest.raises(cand.CandidateError) as excinfo:
            cand.execute_operation(intent, delivery_schedule=(0,))
        assert excinfo.value.reason_code == cand.RC_DELIVERY_SCHEDULE_MALFORMED

    def test_candidate_malformed_consent_epoch_refused(self) -> None:
        """Negative consent epoch at commit raises CandidateError."""
        intent = _candidate_intent()
        with pytest.raises(cand.CandidateError) as excinfo:
            cand.execute_operation(intent, consent_epoch_at_commit=-5)
        assert excinfo.value.reason_code == cand.RC_CONSENT_EPOCH_MALFORMED

    def test_state_machine_malformed_inputs_indeterminate(self) -> None:
        """State machine evaluates malformed intent or state to INDETERMINATE."""
        bad_intent = sm.WriteIntent(
            operation_id="",
            tenant_id="t",
            principal_id="p",
            purpose="self",
            authorized_consent_epoch=1,
            payload_digest_sha256="a" * 64,
            issued_logical_time=1,
        )
        verdict = sm.evaluate_durability(bad_intent, _blank_durable_state())
        assert verdict.outcome == sm.DurabilityOutcome.INDETERMINATE
        assert verdict.reason_code == sm.REASON_MALFORMED_WRITE_INTENT


# ---------------------------------------------------------------------------
# 3. Unknown boundaries (torn states, tampering, and INDETERMINATE retention)
# ---------------------------------------------------------------------------


class TestUnknownBoundaries:
    def test_torn_clinical_row_indeterminate(self) -> None:
        """Torn row write (CORRUPT status) fails closed to INDETERMINATE."""
        intent = _state_machine_intent()
        state = dataclasses.replace(
            _committed_durable_state(),
            clinical_row=sm.ClinicalRowState(
                status=sm.ChannelStatus.CORRUPT,
                operation_id=OP_DEFAULT,
            ),
        )
        verdict = sm.evaluate_durability(intent, state)
        assert verdict.outcome == sm.DurabilityOutcome.INDETERMINATE
        assert verdict.reason_code == sm.REASON_CLINICAL_ROW_CORRUPT

    def test_corrupt_decision_receipt_indeterminate(self) -> None:
        """Tampered ledger receipt (CORRUPT status) yields INDETERMINATE."""
        intent = _state_machine_intent()
        state = dataclasses.replace(
            _committed_durable_state(),
            decision_receipt=sm.DecisionReceipt(
                status=sm.ChannelStatus.CORRUPT,
                operation_id=OP_DEFAULT,
            ),
        )
        verdict = sm.evaluate_durability(intent, state)
        assert verdict.outcome == sm.DurabilityOutcome.INDETERMINATE
        assert verdict.reason_code == sm.REASON_DECISION_RECEIPT_CORRUPT

    def test_receipt_digest_mismatch_indeterminate(self) -> None:
        """DSN-CASE-06: Receipt transition digest mismatch (tamper witness)."""
        intent = _state_machine_intent()
        state = dataclasses.replace(
            _committed_durable_state(),
            decision_receipt=dataclasses.replace(
                _committed_durable_state().decision_receipt,
                stored_transition_digest=sm._synthetic_digest("forged_row"),
            ),
        )
        verdict = sm.evaluate_durability(intent, state)
        assert verdict.outcome == sm.DurabilityOutcome.INDETERMINATE
        assert verdict.reason_code == sm.REASON_RECEIPT_DIGEST_MISMATCH

    @pytest.mark.parametrize(
        ("mutator", "expected_reason"),
        [
            (
                lambda s: dataclasses.replace(s, reconciler_logical_time=15),
                sm.REASON_WAL_COMMIT_TIMESTAMP_ANOMALY,
            ),
            (
                lambda s: dataclasses.replace(
                    s,
                    decision_receipt=dataclasses.replace(
                        s.decision_receipt, receipt_logical_time=10  # < wal_commit_time 20
                    ),
                ),
                sm.REASON_RECEIPT_TIMESTAMP_ANOMALY,
            ),
            (
                lambda s: dataclasses.replace(
                    s,
                    outbox=dataclasses.replace(
                        s.outbox, recorded_logical_time=15  # < wal_commit_time 20
                    ),
                ),
                sm.REASON_OUTBOX_TIMESTAMP_ANOMALY,
            ),
            (
                lambda s: dataclasses.replace(
                    s,
                    outbox=dataclasses.replace(
                        s.outbox,
                        deliveries=(
                            sm.DeliveryReceipt(
                                operation_id=OP_DEFAULT,
                                attempt=1,
                                effect_applied=True,
                                delivered_logical_time=15,  # < recorded_time 20
                                effect_receipt_digest=sm._synthetic_digest(f"{OP_DEFAULT}:effect"),
                            ),
                        ),
                    ),
                ),
                sm.REASON_DELIVERY_TIMESTAMP_ANOMALY,
            ),
        ],
    )
    def test_timestamp_anomalies_indeterminate(
        self, mutator: Any, expected_reason: str
    ) -> None:
        """Inverted durable timestamps fail closed to INDETERMINATE."""
        intent = _state_machine_intent()
        state = mutator(_committed_durable_state())
        verdict = sm.evaluate_durability(intent, state)
        assert verdict.outcome == sm.DurabilityOutcome.INDETERMINATE
        assert verdict.reason_code == expected_reason

    def test_state_operation_mismatch_indeterminate(self) -> None:
        """Mismatched operation IDs across channels yield STATE_OPERATION_MISMATCH."""
        intent = _state_machine_intent()
        state = dataclasses.replace(
            _committed_durable_state(),
            decision_receipt=dataclasses.replace(
                _committed_durable_state().decision_receipt,
                operation_id="op:foreign-other",
            ),
        )
        verdict = sm.evaluate_durability(intent, state)
        assert verdict.outcome == sm.DurabilityOutcome.INDETERMINATE
        assert verdict.reason_code == sm.REASON_STATE_OPERATION_MISMATCH

    def test_orphan_receipt_and_outbox_indeterminate(self) -> None:
        """Orphan ledger receipt or orphan outbox without clinical row yields INDETERMINATE."""
        intent = _state_machine_intent()
        orphan_receipt_state = sm.DurableState(
            clinical_row=sm.ClinicalRowState(status=sm.ChannelStatus.ABSENT),
            decision_receipt=_committed_durable_state().decision_receipt,
            outbox=sm.OutboxState(status=sm.ChannelStatus.ABSENT),
            current_consent_epoch=3,
            reconciler_logical_time=100,
        )
        v1 = sm.evaluate_durability(intent, orphan_receipt_state)
        assert v1.outcome == sm.DurabilityOutcome.INDETERMINATE
        assert v1.reason_code == sm.REASON_ORPHAN_RECEIPT_NO_CLINICAL_ROW

        orphan_outbox_state = sm.DurableState(
            clinical_row=sm.ClinicalRowState(status=sm.ChannelStatus.ABSENT),
            decision_receipt=sm.DecisionReceipt(status=sm.ChannelStatus.ABSENT),
            outbox=_committed_durable_state().outbox,
            current_consent_epoch=3,
            reconciler_logical_time=100,
        )
        v2 = sm.evaluate_durability(intent, orphan_outbox_state)
        assert v2.outcome == sm.DurabilityOutcome.INDETERMINATE
        assert v2.reason_code == sm.REASON_OUTBOX_ORPHAN_NO_CLINICAL_ROW

    @pytest.mark.parametrize("mode", cand.CORRUPTION_MODES)
    def test_candidate_journal_corruption_modes_indeterminate(self, mode: str) -> None:
        """Every interior corruption mode in candidate journal fails verification
        and recoverable_outcome fails closed with JOURNAL_CORRUPT."""
        intent = _candidate_intent()
        clean = cand.execute_operation(intent, delivery_schedule=(1,))
        corrupt = cand.corrupt_journal(clean.journal, mode, 1)

        defects = cand.verify_journal(corrupt, intent.operation_id)
        assert len(defects) > 0

        outcome = cand.recoverable_outcome(corrupt, intent)
        assert outcome.outcome == cand.VERDICT_INDETERMINATE
        assert outcome.reason_code == cand.RC_JOURNAL_CORRUPT

        # Executor refuses execution on corrupted journal
        with pytest.raises(cand.CandidateError) as excinfo:
            cand.execute_operation(intent, journal=corrupt)
        assert excinfo.value.reason_code == cand.RC_JOURNAL_CORRUPT

    def test_candidate_journal_semantic_contradictions_indeterminate(self) -> None:
        """Semantic contradictions (abort+commit, duplicate commit, effect without commit)
        in candidate journal all evaluate to INDETERMINATE."""
        intent = _candidate_intent()
        op = intent.operation_id

        # 1. Effect without commit
        j_orphan = (
            cand.SafetyJournal()
            .append(cand.INTENT, op, {"payload_digest_sha256": intent.payload_digest_sha256, "authorized_consent_epoch": intent.authorized_consent_epoch}, 10)
            .append(cand.EFFECT_APPLIED, op, {"attempt": 1, "effect_receipt_digest": cand._effect_digest(op)}, 11)
        )
        assert cand.recoverable_outcome(j_orphan, intent).reason_code == cand.RC_EFFECT_WITHOUT_COMMIT

        # 2. Abort + commit contradiction
        j_contra = (
            cand.SafetyJournal()
            .append(cand.INTENT, op, {"payload_digest_sha256": intent.payload_digest_sha256, "authorized_consent_epoch": intent.authorized_consent_epoch}, 10)
            .append(cand.ABORT, op, {"reason": cand.RC_CONSENT_REVOKED_BEFORE_COMMIT}, 11)
            .append(cand.COMMIT, op, {"row_version": 1, "consent_epoch_at_commit": 3, "payload_digest_sha256": intent.payload_digest_sha256}, 12)
        )
        assert cand.recoverable_outcome(j_contra, intent).reason_code == cand.RC_ABORT_COMMIT_CONTRADICTION

        # 3. Duplicate commit record
        j_dup_commit = (
            cand.SafetyJournal()
            .append(cand.INTENT, op, {"payload_digest_sha256": intent.payload_digest_sha256, "authorized_consent_epoch": intent.authorized_consent_epoch}, 10)
            .append(cand.COMMIT, op, {"row_version": 1, "consent_epoch_at_commit": 3, "payload_digest_sha256": intent.payload_digest_sha256}, 11)
            .append(cand.COMMIT, op, {"row_version": 1, "consent_epoch_at_commit": 3, "payload_digest_sha256": intent.payload_digest_sha256}, 12)
        )
        assert cand.recoverable_outcome(j_dup_commit, intent).reason_code == cand.RC_DUPLICATE_COMMIT_RECORD

    def test_state_machine_event_history_fail_closed(self) -> None:
        """Malformed or incomplete event histories fold to INDETERMINATE."""
        # Empty history
        empty_hist = sm.EventHistory(events=(), reconciler_logical_time=100)
        assert sm.recover(empty_hist).outcome == sm.DurabilityOutcome.INDETERMINATE

        # Unknown history event kind
        bad_event = sm.HistoryEvent(kind="UNKNOWN_ACTION", logical_time=10, payload={})
        bad_hist = sm.EventHistory(events=(bad_event,), reconciler_logical_time=100)
        assert sm.recover(bad_hist).outcome == sm.DurabilityOutcome.INDETERMINATE

    def test_oracle_unknown_family_indeterminate(self) -> None:
        """Independent oracle returns INDETERMINATE for unmodelled case family."""
        res = oracle.adjudicate({"case_id": "U1", "family": "unregistered_family"})
        assert res.outcome == "INDETERMINATE"
        assert res.reason_code == "UNMODELLED_FAMILY"


# ---------------------------------------------------------------------------
# 4. Crash-window and duplicate-delivery scenarios (RQs & CASE_MATRIX)
# ---------------------------------------------------------------------------


class TestCrashWindowAndDuplicateDelivery:
    @pytest.mark.parametrize(
        "crash_point",
        [
            cand.CRASH_PRE_COMMIT,
            cand.CRASH_POST_COMMIT_PRE_RESPONSE,
            cand.CRASH_PRE_OUTBOX_DELIVERY,
            cand.CRASH_MID_EFFECT,
        ],
    )
    def test_all_crash_windows_and_recovery_convergence(self, crash_point: str) -> None:
        """For every crash cut point: the first episode halts at the cut point;
        resuming recovery on the surviving journal converges to COMMITTED
        with exactly 1 row write and 1 effect application."""
        intent = _candidate_intent()
        stores = cand.DurableStores()

        # Step 1: execute with crash
        rep1 = cand.execute_operation(
            intent,
            crash_point=crash_point,
            delivery_schedule=(1,),
            stores=stores,
        )
        assert rep1.stopped_at == f"crash:{crash_point}"

        if crash_point == cand.CRASH_PRE_COMMIT:
            assert stores.row_version(intent.operation_id) is None
            assert stores.effect_digest(intent.operation_id) is None
        elif crash_point in (cand.CRASH_POST_COMMIT_PRE_RESPONSE, cand.CRASH_PRE_OUTBOX_DELIVERY):
            assert stores.row_version(intent.operation_id) == 1
            assert stores.effect_digest(intent.operation_id) is None
        elif crash_point == cand.CRASH_MID_EFFECT:
            assert stores.row_version(intent.operation_id) == 1
            # Mid-effect crash interrupted before store apply
            assert stores.effect_digest(intent.operation_id) is None

        # Step 2: recovery re-entry using surviving journal
        rep2 = cand.execute_operation(
            intent,
            crash_point=cand.CRASH_NONE,
            delivery_schedule=(1, 2),
            journal=rep1.journal,
            stores=stores,
        )
        assert rep2.stopped_at == "completed"
        assert rep2.resumed

        # Invariants across joint episode
        assert stores.row_write_count == 1
        assert stores.effect_apply_count == 1
        assert stores.row_version(intent.operation_id) == 1
        assert stores.effect_digest(intent.operation_id) is not None

        outcome = cand.recoverable_outcome(rep2.journal, intent)
        assert outcome.outcome == cand.VERDICT_COMMITTED
        assert outcome.reason_code == cand.RC_COMMITTED_EFFECT_APPLIED

    def test_broker_replay_duplicate_deliveries_deduped(self) -> None:
        """DSN-CASE-04: Broker replay delivering same outbox message 5 times.
        Candidate executes effect once and dedups 4 times."""
        intent = _candidate_intent()
        stores = cand.DurableStores()
        schedule = (1, 1, 2, 2, 3)

        report = cand.execute_operation(
            intent,
            delivery_schedule=schedule,
            stores=stores,
        )
        assert report.deliveries_observed == 5
        assert report.deliveries_deduped == 4
        assert report.effect_applications == 1
        assert stores.effect_apply_count == 1

        outcome = cand.recoverable_outcome(report.journal, intent)
        assert outcome.outcome == cand.VERDICT_COMMITTED
        assert outcome.reason_code == cand.RC_COMMITTED_EFFECT_APPLIED

    def test_state_machine_duplicate_delivery_idempotent(self) -> None:
        """State machine recognizes idempotent duplicate delivery receipts."""
        intent = _state_machine_intent()
        state = _committed_durable_state(deliveries_count=3)
        verdict = sm.evaluate_durability(intent, state)
        assert verdict.outcome == sm.DurabilityOutcome.COMMITTED
        assert verdict.reason_code == sm.REASON_COMMITTED_DUPLICATE_DELIVERY_IDEMPOTENT

    def test_ablation_proves_journal_is_load_bearing_for_dedup(self) -> None:
        """Ablation arm B0 (journal removed) fails to deduplicate deliveries,
        applying one effect per delivery under broker replay."""
        intent = _candidate_intent()
        stores = cand.DurableStores()
        schedule = (1, 1, 2)

        ablation_report = cand.ablation_no_journal_execute(
            intent,
            delivery_schedule=schedule,
            stores=stores,
        )
        assert not ablation_report["recoverable_outcome_available"]
        assert ablation_report["effect_applications"] == 3
        assert stores.effect_apply_count == 3  # Triple duplicate effect!

    def test_mid_effect_crash_wal_style_replay_on_resume(self) -> None:
        """In mid_effect crash, the effect record was journaled write-ahead.
        Resume performs WAL-style replay of that journaled effect into stores."""
        intent = _candidate_intent()
        stores = cand.DurableStores()

        rep1 = cand.execute_operation(
            intent,
            crash_point=cand.CRASH_MID_EFFECT,
            delivery_schedule=(1,),
            stores=stores,
        )
        assert stores.effect_apply_count == 0

        # Resume episode
        rep2 = cand.execute_operation(
            intent,
            delivery_schedule=(1, 2),
            journal=rep1.journal,
            stores=stores,
        )
        assert stores.effect_apply_count == 1
        # Confirms EFFECT_REPLAY step was executed
        step_names = [s["step"] for s in rep2.steps]
        assert "EFFECT_REPLAY" in step_names


# ---------------------------------------------------------------------------
# 5. Two-step metamorphic relations
# ---------------------------------------------------------------------------


class TestTwoStepMetamorphicRelations:
    def test_mr1_replaying_acked_operation_is_idempotent(self) -> None:
        """MR1: Replaying an acknowledged operation is idempotent.
        Base run: complete an operation to COMMITTED.
        Step 2: execute again with same intent and returned journal/stores.
        Assertion: zero additional row writes, zero additional effect applications,
        identical COMMITTED verdict."""
        rng = random.Random(FIXED_SEED)
        for i in range(10):
            op_id = f"op:mr1-idem-{i}-{rng.randint(1000, 9999)}"
            intent = _candidate_intent(op_id=op_id)
            stores = cand.DurableStores()

            # Base execution
            base_rep = cand.execute_operation(
                intent,
                delivery_schedule=(1,),
                stores=stores,
            )
            assert base_rep.row_writes == 1
            assert base_rep.effect_applications == 1
            base_outcome = cand.recoverable_outcome(base_rep.journal, intent)
            assert base_outcome.outcome == cand.VERDICT_COMMITTED

            # Metamorphic step 2: replay with replay schedule
            replay_rep = cand.execute_operation(
                intent,
                delivery_schedule=(1, 2, 3),
                journal=base_rep.journal,
                stores=stores,
            )
            assert replay_rep.resumed
            assert replay_rep.row_writes == 0
            assert replay_rep.effect_applications == 0
            assert replay_rep.deliveries_deduped == 3
            assert stores.row_write_count == 1
            assert stores.effect_apply_count == 1

            replay_outcome = cand.recoverable_outcome(replay_rep.journal, intent)
            assert replay_outcome.outcome == base_outcome.outcome
            assert replay_outcome.reason_code == base_outcome.reason_code

    def test_mr2_recovery_step_cannot_lose_committed_effect(self) -> None:
        """MR2: Adding a recovery step after a crash cannot lose a committed effect.
        For any post-commit crash:
        Step 1: run episode to crash cut point.
        Step 2: run recovery resume.
        Assertion: outcome is COMMITTED, row is intact, effect is applied and never lost."""
        crash_points = [
            cand.CRASH_POST_COMMIT_PRE_RESPONSE,
            cand.CRASH_PRE_OUTBOX_DELIVERY,
            cand.CRASH_MID_EFFECT,
        ]
        for idx, cp in enumerate(crash_points):
            op_id = f"op:mr2-lossless-{idx}"
            intent = _candidate_intent(op_id=op_id)
            stores = cand.DurableStores()

            # Step 1: run with crash
            crashed_rep = cand.execute_operation(
                intent,
                crash_point=cp,
                delivery_schedule=(1,),
                stores=stores,
            )
            # Row was already committed
            assert stores.row_version(op_id) == 1

            # Step 2: recovery step
            recovered_rep = cand.execute_operation(
                intent,
                crash_point=cand.CRASH_NONE,
                delivery_schedule=(1, 2),
                journal=crashed_rep.journal,
                stores=stores,
            )
            assert recovered_rep.stopped_at == "completed"
            assert stores.row_version(op_id) == 1
            assert stores.effect_digest(op_id) is not None

            outcome = cand.recoverable_outcome(recovered_rep.journal, intent)
            assert outcome.outcome == cand.VERDICT_COMMITTED
            assert outcome.reason_code == cand.RC_COMMITTED_EFFECT_APPLIED

    def test_mr3_legal_prefix_truncation_vs_interior_tampering(self) -> None:
        """MR3: Dropping the last entry of a journal is a legal prefix (crash window),
        which verify_journal accepts and resume can complete; whereas dropping an
        interior entry is tampering, which verify_journal catches and fails closed."""
        intent = _candidate_intent()
        clean = cand.execute_operation(intent, delivery_schedule=(1,))
        full_journal = clean.journal
        assert len(full_journal) == 4

        # Truncation: drop LAST entry (legal prefix)
        prefix_journal = cand.SafetyJournal(full_journal.entries[:-1])
        assert cand.verify_journal(prefix_journal, intent.operation_id) == ()
        prefix_outcome = cand.recoverable_outcome(prefix_journal, intent)
        assert prefix_outcome.outcome == cand.VERDICT_COMMITTED
        assert prefix_outcome.reason_code == cand.RC_COMMITTED_PENDING_DELIVERY

        # Resume from prefix completes cleanly
        stores = cand.DurableStores(rows={intent.operation_id: 1})
        resumed = cand.execute_operation(
            intent,
            journal=prefix_journal,
            stores=stores,
            delivery_schedule=(1,),
        )
        assert resumed.stopped_at == "completed"
        assert cand.recoverable_outcome(resumed.journal, intent).reason_code == cand.RC_COMMITTED_EFFECT_APPLIED

        # Interior tampering: drop non-last entry (e.g. index 1)
        tampered_journal = cand.corrupt_journal(full_journal, "drop_interior_entry", 1)
        defects = cand.verify_journal(tampered_journal, intent.operation_id)
        assert len(defects) > 0
        assert cand.recoverable_outcome(tampered_journal, intent).outcome == cand.VERDICT_INDETERMINATE

    def test_mr4_delivery_schedule_expansion_monotonicity(self) -> None:
        """MR4: Expanding delivery schedule S -> S + [attempts] cannot increase
        actual mutation counts in durable stores beyond 1."""
        intent = _candidate_intent()
        stores = cand.DurableStores()

        # Run with schedule length 1
        cand.execute_operation(intent, delivery_schedule=(1,), stores=stores)
        assert stores.row_write_count == 1
        assert stores.effect_apply_count == 1

        # Expand delivery schedule with 10 duplicate attempts
        cand.execute_operation(
            intent,
            delivery_schedule=(1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
            stores=stores,
        )
        assert stores.row_write_count == 1
        assert stores.effect_apply_count == 1


# ---------------------------------------------------------------------------
# 6. Mutation checks (mutation adequacy for the pass gate)
# ---------------------------------------------------------------------------


class TestMutationChecks:
    def test_mutation_skip_journal_verification_killed(self) -> None:
        """Mutant: verify_journal bypassed in execute_operation.
        The real executor detects corrupt journals; bypassing verify_journal
        would execute on corrupt data, killed by the safety refusal."""
        intent = _candidate_intent()
        clean = cand.execute_operation(intent, delivery_schedule=(1,))
        corrupt = cand.corrupt_journal(clean.journal, "flip_payload", 1)

        # Real candidate refuses execution
        with pytest.raises(cand.CandidateError) as excinfo:
            cand.execute_operation(intent, journal=corrupt)
        assert excinfo.value.reason_code == cand.RC_JOURNAL_CORRUPT

        # Verify mutant would have accepted
        with unittest.mock.patch.object(cand, "verify_journal", return_value=()):
            report = cand.execute_operation(intent, journal=corrupt)
            assert report.resumed, "mutant survived journal corruption guard"

    def test_mutation_skip_consent_check_killed(self) -> None:
        """Mutant: consent epoch check at commit removed.
        In the real system, epoch_at_commit > authorized triggers ABORT.
        Removing this check commits forbidden writes."""
        intent = _candidate_intent(epoch=2)
        stores = cand.DurableStores()
        report = cand.execute_operation(
            intent,
            consent_epoch_at_commit=3,  # revoked
            stores=stores,
        )
        assert report.stopped_at == "aborted"
        assert stores.row_version(intent.operation_id) is None

        # Verify mutant committing regardless would violate safety
        def fake_append(k: str, p: Any) -> None:
            pass

        with unittest.mock.patch.object(cand, "_validated_epoch", return_value=2):
            mutant_rep = cand.execute_operation(intent, consent_epoch_at_commit=3)
            # Mutant would have committed instead of aborted
            assert mutant_rep.stopped_at != "aborted"

    def test_mutation_skip_write_ahead_journaling_killed(self) -> None:
        """Mutant: effect applied without write-ahead journal entry.
        Ablation demonstrates that without write-ahead journal entries, broker
        replay causes multiple effect applications, which full candidate kills."""
        intent = _candidate_intent()
        stores_cand = cand.DurableStores()
        rep_cand = cand.execute_operation(intent, delivery_schedule=(1, 1, 1), stores=stores_cand)
        assert rep_cand.effect_applications == 1

        stores_ablation = cand.DurableStores()
        rep_abl = cand.ablation_no_journal_execute(intent, delivery_schedule=(1, 1, 1), stores=stores_ablation)
        assert rep_abl["effect_applications"] == 3

    def test_mutation_duplicate_effect_divergence_killed(self) -> None:
        """Mutant: ignore duplicate delivery receipt divergence.
        State machine with divergent effect receipts MUST return INDETERMINATE."""
        intent = _state_machine_intent()
        state = _committed_durable_state(deliveries_count=2, divergent_delivery=True)
        verdict = sm.evaluate_durability(intent, state)
        assert verdict.outcome == sm.DurabilityOutcome.INDETERMINATE
        assert verdict.reason_code == sm.REASON_DUPLICATE_EFFECT_DIVERGENCE

    def test_mutation_constant_stub_refused(self) -> None:
        """Constant-output stubs that ignore crash cut points are refused by
        refuse_constant_stub (EXECUTION_CONTRACT rule 8)."""
        constant_stub = lambda case: Outcome("ADMIT", detail="ALWAYS_ADMIT")  # noqa: E731
        with pytest.raises(bl.BaselineError) as excinfo:
            bl.refuse_constant_stub(constant_stub)
        assert excinfo.value.reason_code == bl.RC_STUB_CONSTANT

        # Baseline arm B0 distinguishes clean and crash probe cases
        b0_adapter = lambda case: bl.run_baseline(bl.BASELINE_B0, case, bl.BaselineContext(store={}))  # noqa: E731
        res = bl.refuse_constant_stub(b0_adapter)
        assert res.observed_outcome == "ADMIT"
        assert res.detail == bl.RC_STUB_SEPARATION_OK

    def test_mutation_oracle_candidate_import_killed(self, tmp_path: pathlib.Path) -> None:
        """Independence guard kills any candidate import in oracle source."""
        oracle.verify_independence()

        poisoned_oracle = tmp_path / "poisoned_oracle.py"
        poisoned_oracle.write_text("import state_machine\n", encoding="utf-8")
        with pytest.raises(oracle_kernel.OracleError) as excinfo:
            oracle_kernel.assert_oracle_independence(
                str(poisoned_oracle), oracle.CANDIDATE_MODULES
            )
        assert excinfo.value.reason_code == "CANDIDATE_IMPORT"


# ---------------------------------------------------------------------------
# 7. Seeded safety invariant sweep & replay determinism
# ---------------------------------------------------------------------------


class TestSeededSafetyInvariantSweep:
    def test_safety_invariant_sweep_across_random_schedules(self) -> None:
        """SAFETY INVARIANT: across a family-balanced sweep with random schedules,
        no operation ever double-writes a row, no operation ever double-applies
        an effect, and no revoked write is ever committed."""
        rng = random.Random(FIXED_SEED)
        crash_points = list(cand.CRASH_POINTS)

        for trial in range(48):
            op_id = f"op:sweep-{trial}-{rng.randint(1000, 9999)}"
            auth_epoch = rng.randint(1, 5)
            # 20% probability of revocation race
            is_revoked = rng.random() < 0.2
            commit_epoch = auth_epoch + 1 if is_revoked else auth_epoch
            cp = rng.choice(crash_points)
            schedule_len = rng.randint(1, 4)
            schedule = tuple(rng.randint(1, 3) for _ in range(schedule_len))

            intent = _candidate_intent(op_id=op_id, epoch=auth_epoch)
            stores = cand.DurableStores()

            first_rep = cand.execute_operation(
                intent,
                crash_point=cp,
                delivery_schedule=schedule,
                consent_epoch_at_commit=commit_epoch,
                stores=stores,
            )

            if is_revoked:
                # If crash_point was pre_commit, episode halted at pre_commit before reaching commit check;
                # on recovery resume, the consent revocation is detected and it halts at aborted.
                if cp == cand.CRASH_PRE_COMMIT:
                    assert first_rep.stopped_at == f"crash:{cand.CRASH_PRE_COMMIT}"
                    rec_rep = cand.execute_operation(
                        intent,
                        crash_point=cand.CRASH_NONE,
                        delivery_schedule=(1, 2),
                        journal=first_rep.journal,
                        stores=stores,
                        consent_epoch_at_commit=commit_epoch,
                    )
                    assert rec_rep.stopped_at == "aborted"
                else:
                    assert first_rep.stopped_at == "aborted"
                assert stores.row_version(op_id) is None
                assert stores.effect_digest(op_id) is None
                continue

            if cp != cand.CRASH_NONE:
                # Recovery resume
                rec_rep = cand.execute_operation(
                    intent,
                    crash_point=cand.CRASH_NONE,
                    delivery_schedule=(1, 2),
                    journal=first_rep.journal,
                    stores=stores,
                    consent_epoch_at_commit=commit_epoch,
                )
                assert rec_rep.stopped_at == "completed"

            # Invariant: exactly-once durable mutations
            assert stores.row_write_count == 1
            assert stores.effect_apply_count == 1
            assert stores.row_version(op_id) == 1
            assert stores.effect_digest(op_id) is not None

    def test_sweep_is_replay_identical(self) -> None:
        """Determinism: two independent runs under identical seed produce
        byte-identical detail transcripts."""
        def run_sweep(seed: int) -> list[str]:
            rng = random.Random(seed)
            records = []
            for i in range(16):
                op_id = f"op:det-{i}-{rng.randint(100, 999)}"
                intent = _candidate_intent(op_id=op_id, epoch=rng.randint(1, 5))
                stores = cand.DurableStores()
                rep = cand.execute_operation(
                    intent,
                    crash_point=cand.CRASH_POST_COMMIT_PRE_RESPONSE,
                    delivery_schedule=(1, 2),
                    stores=stores,
                )
                outcome = cand.recoverable_outcome(rep.journal, intent)
                payload = {
                    "report": rep.to_dict(),
                    "outcome": outcome.to_dict(),
                    "stores": stores.to_dict(),
                }
                records.append(json.dumps(payload, sort_keys=True))
            return records

        run1 = run_sweep(FIXED_SEED)
        run2 = run_sweep(FIXED_SEED)
        assert run1 == run2
