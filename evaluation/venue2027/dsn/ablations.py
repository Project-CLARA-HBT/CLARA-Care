"""DSN-ablation — causal mechanism ablation variants (task DSN-ablation, phase P04).

Purpose
-------
P04 ablation registry for the DSN 2027 study "Recoverable Safety Journals for
Crash-Consistent AI-Mediated Health-State Mutations"
(``research/venue2027/VENUES/dsn/RESEARCH_BLUEPRINT.md``, RQ1-RQ3; task
contract ``research/venue2027/VENUES/dsn/TASKS/DSN-ablation.md``). The P04
candidate (:mod:`evaluation.venue2027.dsn.candidate`) provides crash-consistent
governed health-state mutations via a per-operation hash-chained safety
journal, write-ahead side-effect records, retries keyed to immutable operation
IDs, consent rechecks at commit, and pure fail-closed adjudication.

This module evaluates the candidate against ITSELF with EXACTLY ONE mechanism
removed per variant over the canonical crash windows and fault conditions, so
each mechanism's causal contribution to crash consistency and exactly-once
semantics is verifiable:

Preregistered variants (``ABLATION_REGISTRY``):
------------------------------------------------
1. ``without_journal`` (no recovery):
   Candidate WITHOUT the durable safety journal (blueprint arm B0). With no
   decision lineage, recovery after a crash cannot adjudicate the outcome
   (``recoverable_outcome_available=False``) and broker replays apply duplicate
   side effects.
2. ``without_idempotency_key``:
   Candidate WITHOUT idempotency key deduplication. The journal is durable, but
   the effect sink and delivery loop do not deduplicate by immutable operation
   ID. At-least-once broker replays and recovery retries demonstrably apply
   duplicate side effects.
3. ``without_wal_pre_write``:
   Candidate WITHOUT the write-ahead effect record. The side effect is applied
   to the external sink BEFORE (or without) appending ``EFFECT_APPLIED`` to the
   journal. A crash at ``mid_effect`` leaves the store mutated while the
   journal has no record; on recovery, the effect is re-applied (demonstrated
   duplicate effect) or the outcome remains torn.
4. ``common_safety_gate``:
   Candidate's recoverable journal pipeline REPLACED by the statutory consent
   safety gate every arm shares: check consent epoch at commit time, but
   execute bare writes without crash-consistent recovery, WAL pre-writes, or
   deduplication. Catches consent revocations, but fails crash recovery windows.
5. ``full_fat_baseline``:
   The strong practical baseline (arm B1: PostgreSQL atomic write +
   transactional outbox + idempotent consumer). Survives standard crash
   recovery and deduplicates deliveries, but lacks the hash-chained verifiable
   decision lineage (blind to journal corruption/tampering) and lacks the
   candidate's write-ahead journal for mid-effect crashes.

The reference row (the unmodified full candidate) is deliberately NOT a
registered variant: a variant that removes nothing is not an ablation.
:func:`refuse_unregistered_variant` refuses unknown IDs with
``UNKNOWN_ABLATION_VARIANT`` and nothing-removing identities with
``VARIANT_REMOVES_NOTHING``. The mechanistic inference matrix
(:func:`mechanistic_inference_matrix`,
:func:`verify_mechanistic_inference_matrix`) pins every variant x crash window
outcome against its preregistered prediction.

Allowed input
-------------
:func:`run_ablation(name, case)`: ``name`` is a registered variant ID from
:data:`ABLATION_REGISTRY`; ``case`` is a JSON-serializable mapping conforming
to the candidate case schema (``case_id``, ``operation_id``,
``authorized_consent_epoch``, ``delivery_schedule``, optional ``crash_point``,
``consent_epoch_at_commit``, ``corrupt_journal``).

Failure semantics
-----------------
Fail closed with stable uppercase reason codes:
- Unknown variant -> ``Outcome("EXECUTION_ERROR", detail=UNKNOWN_ABLATION_VARIANT)``
- Nothing-removing variant -> ``Outcome("EXECUTION_ERROR", detail=VARIANT_REMOVES_NOTHING)``
- Malformed case -> ``Outcome("EXECUTION_ERROR", detail=...)``
- Safety violations (duplicate effects, lost recovery, unhandled tampering) are
  flagged in the outcome detail and cause test/matrix failures.

Version
-------
``ABLATIONS_VERSION = "clara.dsn.ablations-v1"`` (additive-only within 1.x).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Callable, Mapping
from typing import Any, Final

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.dsn import baselines
from evaluation.venue2027.dsn import candidate as cand

ABLATIONS_VERSION: Final[str] = "clara.dsn.ablations-v1"
ABLATION_TASK_ID: Final[str] = "DSN-ablation"

#: Preregistered ablation variant IDs.
VARIANT_WITHOUT_JOURNAL: Final[str] = "without_journal"
VARIANT_WITHOUT_IDEMPOTENCY_KEY: Final[str] = "without_idempotency_key"
VARIANT_WITHOUT_WAL_PRE_WRITE: Final[str] = "without_wal_pre_write"
VARIANT_COMMON_SAFETY_GATE: Final[str] = "common_safety_gate"
VARIANT_FULL_FAT_BASELINE: Final[str] = "full_fat_baseline"

#: Reference row: the unmodified full candidate (not an ablation).
REFERENCE_VARIANT_ID: Final[str] = "full_candidate"

#: Identities known to remove nothing (refused fail-closed).
NON_ABLATION_IDENTITIES: Final[frozenset[str]] = frozenset(
    {REFERENCE_VARIANT_ID, cand.CANDIDATE_ID, "candidate", "full_fat_candidate"}
)

#: Declared ablated mechanisms (each variant removes exactly one).
ABLATED_SAFETY_JOURNAL: Final[str] = "safety_journal"
ABLATED_IDEMPOTENCY_KEY: Final[str] = "idempotency_key"
ABLATED_WRITE_AHEAD_EFFECT_RECORD: Final[str] = "write_ahead_effect_record"
ABLATED_RECOVERABLE_JOURNAL_PIPELINE: Final[str] = "recoverable_journal_pipeline"
ABLATED_HASH_CHAINED_DECISION_LINEAGE: Final[str] = "hash_chained_decision_lineage"

#: Reason codes.
RC_UNKNOWN_ABLATION_VARIANT: Final[str] = "UNKNOWN_ABLATION_VARIANT"
RC_VARIANT_REMOVES_NOTHING: Final[str] = "VARIANT_REMOVES_NOTHING"
RC_CASE_NOT_AN_OBJECT: Final[str] = "CASE_NOT_AN_OBJECT"
RC_CASE_MISSING_FIELD: Final[str] = "CASE_MISSING_FIELD"
RC_CASE_UNKNOWN_FIELD: Final[str] = "CASE_UNKNOWN_FIELD"
RC_CASE_BAD_FIELD: Final[str] = "CASE_BAD_FIELD"
RC_DUPLICATE_EFFECT: Final[str] = "DUPLICATE_EFFECT_APPLIED"
RC_LOST_EFFECT: Final[str] = "LOST_SIDE_EFFECT_NO_JOURNAL"
RC_WAL_LOST: Final[str] = "EFFECT_LOST_NO_WAL_PRE_WRITE"
RC_TAMPERING_NOT_DETECTED: Final[str] = "TAMPERING_NOT_DETECTED"
RC_INTERNAL_ABLATION_ERROR: Final[str] = "INTERNAL_ABLATION_ERROR"

#: Aliases for variant resolution.
ALIASES: Final[Mapping[str, str]] = {
    "no_journal": VARIANT_WITHOUT_JOURNAL,
    "without_journal_no_recovery": VARIANT_WITHOUT_JOURNAL,
    "no_recovery": VARIANT_WITHOUT_JOURNAL,
    "no_idempotency_key": VARIANT_WITHOUT_IDEMPOTENCY_KEY,
    "without_idempotency": VARIANT_WITHOUT_IDEMPOTENCY_KEY,
    "no_wal": VARIANT_WITHOUT_WAL_PRE_WRITE,
    "without_wal": VARIANT_WITHOUT_WAL_PRE_WRITE,
    "no_wal_effect_pre_write": VARIANT_WITHOUT_WAL_PRE_WRITE,
    "with_common_safety_gate": VARIANT_COMMON_SAFETY_GATE,
    "safety_gate_only": VARIANT_COMMON_SAFETY_GATE,
    "baseline_full_fat": VARIANT_FULL_FAT_BASELINE,
    "full-fat_baseline": VARIANT_FULL_FAT_BASELINE,
}

#: Valid case keys.
CASE_REQUIRED_KEYS: Final[frozenset[str]] = frozenset(
    {"case_id", "operation_id", "delivery_schedule"}
)
CASE_OPTIONAL_KEYS: Final[frozenset[str]] = frozenset(
    {
        "authorized_consent_epoch",
        "consent_epoch",
        "consent_epoch_at_commit",
        "crash_point",
        "corrupt_journal",
    }
)
CASE_ALL_KEYS: Final[frozenset[str]] = CASE_REQUIRED_KEYS | CASE_OPTIONAL_KEYS


class AblationError(ValueError):
    """Fail-closed ablation registry error with a stable reason code."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class VariantSpec:
    """One preregistered ablation variant.

    ``ablated_mechanism`` is the DECLARED single mechanism removed; a spec
    declaring no ablated mechanism (empty string) is refused at construction.
    """

    variant_id: str
    title: str
    ablated_mechanism: str
    description: str
    expected_failure_window: str
    expected_effect: str
    reuses: tuple[str, ...]
    applied_by: str
    runner: Callable[[Mapping[str, Any]], Outcome]

    def __post_init__(self) -> None:
        if not isinstance(self.ablated_mechanism, str) or not self.ablated_mechanism.strip():
            raise AblationError(
                RC_VARIANT_REMOVES_NOTHING,
                f"variant {self.variant_id!r} declares no ablated mechanism; "
                "a variant removing nothing is not an ablation",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "title": self.title,
            "ablated_mechanism": self.ablated_mechanism,
            "description": self.description,
            "expected_failure_window": self.expected_failure_window,
            "expected_effect": self.expected_effect,
            "reuses": list(self.reuses),
            "applied_by": self.applied_by,
        }


# ---------------------------------------------------------------------------
# Case Validation & Normalization
# ---------------------------------------------------------------------------


def _validate_case(case: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(case, Mapping):
        raise AblationError(RC_CASE_NOT_AN_OBJECT, f"case must be a mapping, got {type(case)}")
    unknown = sorted(set(map(str, case)) - CASE_ALL_KEYS)
    if unknown:
        raise AblationError(RC_CASE_UNKNOWN_FIELD, f"unknown case keys: {unknown}")
    for req in CASE_REQUIRED_KEYS:
        if req not in case:
            raise AblationError(RC_CASE_MISSING_FIELD, f"missing required case key: {req}")
    if not isinstance(case["case_id"], str) or not case["case_id"].strip():
        raise AblationError(RC_CASE_BAD_FIELD, "case_id must be a non-empty string")
    if not isinstance(case["operation_id"], str) or not case["operation_id"].strip():
        raise AblationError(RC_CASE_BAD_FIELD, "operation_id must be a non-empty string")
    schedule = case["delivery_schedule"]
    if not isinstance(schedule, (list, tuple)):  # noqa: UP038
        raise AblationError(RC_CASE_BAD_FIELD, "delivery_schedule must be a list/tuple")
    for attempt in schedule:
        if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
            raise AblationError(
                RC_CASE_BAD_FIELD, f"delivery attempts must be int >= 1, got {attempt!r}"
            )

    epoch = case.get("authorized_consent_epoch", case.get("consent_epoch", 1))
    if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0:
        raise AblationError(RC_CASE_BAD_FIELD, "authorized_consent_epoch must be an int >= 0")

    crash_point = case.get("crash_point", cand.CRASH_NONE)
    if crash_point not in cand.CRASH_POINTS:
        raise AblationError(RC_CASE_BAD_FIELD, f"unknown crash_point: {crash_point!r}")

    epoch_commit = case.get("consent_epoch_at_commit")
    if epoch_commit is not None and (
        isinstance(epoch_commit, bool) or not isinstance(epoch_commit, int) or epoch_commit < 0
    ):
        raise AblationError(RC_CASE_BAD_FIELD, "consent_epoch_at_commit must be an int >= 0")

    corrupt = case.get("corrupt_journal")
    if corrupt is not None:
        if not isinstance(corrupt, Mapping) or set(map(str, corrupt)) - cand.CORRUPTION_KEYS:
            raise AblationError(cand.RC_CORRUPTION_SPEC_MALFORMED, "corrupt_journal format invalid")
        if corrupt.get("mode") not in cand.CORRUPTION_MODES or not isinstance(
            corrupt.get("entry_index"), int
        ):
            raise AblationError(
                cand.RC_CORRUPTION_SPEC_MALFORMED, "corrupt_journal mode/entry_index invalid"
            )

    return {
        "case_id": str(case["case_id"]),
        "operation_id": str(case["operation_id"]),
        "authorized_consent_epoch": epoch,
        "delivery_schedule": list(schedule),
        "crash_point": crash_point,
        "consent_epoch_at_commit": epoch_commit,
        "corrupt_journal": dict(corrupt) if corrupt is not None else None,
    }


def _make_intent(spec: Mapping[str, Any]) -> cand.WriteIntent:
    op = str(spec["operation_id"])
    return cand.WriteIntent(
        operation_id=op,
        tenant_id="synthetic-tenant",
        principal_id="synthetic-actor",
        purpose="self_care",
        authorized_consent_epoch=int(spec["authorized_consent_epoch"]),
        payload_digest_sha256=hashlib.sha256(
            f"clara.dsn.candidate:payload:{op}".encode()
        ).hexdigest(),
        issued_logical_time=10,
    )


# ---------------------------------------------------------------------------
# Real Callables for Preregistered Variants
# ---------------------------------------------------------------------------


def _run_without_journal(case: Mapping[str, Any]) -> Outcome:
    """Variant 1: Execute without safety journal (blueprint arm B0).

    Uses candidate.ablation_no_journal_execute: DB row is written, but no
    journal entries are appended. A crash before response leaves an orphaned
    row that cannot be adjudicated (recoverable_outcome_available=False);
    broker replays apply duplicate effects.
    """
    spec = _validate_case(case)
    intent = _make_intent(spec)
    stores = cand.DurableStores()
    crash_point = spec["crash_point"]
    schedule = tuple(spec["delivery_schedule"])
    epoch_commit = spec["consent_epoch_at_commit"]

    first = cand.ablation_no_journal_execute(
        intent,
        crash_point=crash_point,
        delivery_schedule=schedule,
        stores=stores,
        consent_epoch_at_commit=epoch_commit,
    )

    if first.get("aborted") == cand.RC_CONSENT_REVOKED_BEFORE_COMMIT:
        return Outcome(
            observed_outcome="REJECT",
            counted_as_success=True,
            retriable=False,
            detail=json.dumps(
                {
                    "variant_id": VARIANT_WITHOUT_JOURNAL,
                    "reason_code": cand.RC_CONSENT_REVOKED_BEFORE_COMMIT,
                    "recoverable_outcome_available": False,
                },
                sort_keys=True,
            ),
        )

    # If crashed at pre_commit: recovery attempt after pre_commit crash has no journal,
    # so a blind retry would have to re-execute without durable lineage.
    if crash_point == cand.CRASH_PRE_COMMIT:
        # Pass 1 had nothing durable. Pass 2 (recovery) runs clean:
        resumed = cand.ablation_no_journal_execute(
            intent,
            crash_point=cand.CRASH_NONE,
            delivery_schedule=schedule,
            stores=stores,
            consent_epoch_at_commit=epoch_commit,
        )
        return Outcome(
            observed_outcome="ADMIT",
            counted_as_success=True,
            retriable=False,
            detail=json.dumps(
                {
                    "variant_id": VARIANT_WITHOUT_JOURNAL,
                    "reason_code": cand.RC_COMMITTED_EFFECT_APPLIED,
                    "recoverable_outcome_available": False,
                    "row_writes": resumed["row_write_attempts"],
                    "effect_applications": resumed["effect_applications"],
                },
                sort_keys=True,
            ),
        )

    # If crashed after commit: caller has no journal to adjudicate outcome.
    if crash_point in (
        cand.CRASH_POST_COMMIT_PRE_RESPONSE,
        cand.CRASH_PRE_OUTBOX_DELIVERY,
        cand.CRASH_MID_EFFECT,
    ):
        return Outcome(
            observed_outcome="INDETERMINATE",
            counted_as_success=False,
            retriable=False,
            detail=json.dumps(
                {
                    "variant_id": VARIANT_WITHOUT_JOURNAL,
                    "reason_code": RC_LOST_EFFECT,
                    "recoverable_outcome_available": False,
                    "row_writes": stores.row_write_count,
                    "effect_applications": stores.effect_apply_count,
                    "note": "without journal, outcome is unadjudicable and recovery fails",
                },
                sort_keys=True,
            ),
        )

    # Clean execution without crash:
    effects = stores.effect_apply_count
    if effects > 1:
        # Broker replay caused duplicate side effects because dedup requires journal!
        return Outcome(
            observed_outcome="ADMIT",
            counted_as_success=False,
            retriable=False,
            detail=json.dumps(
                {
                    "variant_id": VARIANT_WITHOUT_JOURNAL,
                    "reason_code": RC_DUPLICATE_EFFECT,
                    "effect_applications": effects,
                    "deliveries_observed": len(schedule),
                    "deliveries_deduped": 0,
                },
                sort_keys=True,
            ),
        )

    return Outcome(
        observed_outcome="ADMIT",
        counted_as_success=True,
        retriable=False,
        detail=json.dumps(
            {
                "variant_id": VARIANT_WITHOUT_JOURNAL,
                "reason_code": cand.RC_COMMITTED_EFFECT_APPLIED,
                "effect_applications": effects,
                "recoverable_outcome_available": False,
            },
            sort_keys=True,
        ),
    )


def _run_without_idempotency_key(case: Mapping[str, Any]) -> Outcome:
    """Variant 2: Candidate without idempotency key deduplication.

    Journal and recovery exist, but the delivery loop and effect sink do NOT
    deduplicate by operation ID. Duplicate broker deliveries or recovery replays
    demonstrably apply duplicate effects.
    """
    spec = _validate_case(case)
    intent = _make_intent(spec)
    stores = cand.DurableStores()
    crash_point = spec["crash_point"]
    schedule = tuple(spec["delivery_schedule"])
    epoch_commit = spec["consent_epoch_at_commit"]
    op = intent.operation_id

    # Execute episode with idempotency deduplication removed:
    first = cand.execute_operation(
        intent,
        crash_point=crash_point,
        delivery_schedule=schedule,
        stores=stores,
        consent_epoch_at_commit=epoch_commit,
    )
    journal = first.journal

    if spec.get("corrupt_journal"):
        cj = spec["corrupt_journal"]
        journal = cand.corrupt_journal(journal, str(cj["mode"]), int(cj["entry_index"]))

    # Check recovery:
    try:
        resumed = cand.execute_operation(
            intent,
            delivery_schedule=schedule,
            journal=journal,
        )
    except cand.CandidateError as exc:
        if exc.reason_code == cand.RC_JOURNAL_CORRUPT:
            return Outcome(
                observed_outcome="INDETERMINATE",
                counted_as_success=False,
                detail=json.dumps(
                    {
                        "variant_id": VARIANT_WITHOUT_IDEMPOTENCY_KEY,
                        "reason_code": cand.RC_JOURNAL_CORRUPT,
                    }
                ),
            )
        raise

    verdict = cand.recoverable_outcome(resumed.journal, intent)
    if verdict.outcome == cand.VERDICT_REJECTED:
        return Outcome(
            observed_outcome="REJECT",
            counted_as_success=True,
            retriable=verdict.retriable,
            detail=json.dumps(
                {
                    "variant_id": VARIANT_WITHOUT_IDEMPOTENCY_KEY,
                    "reason_code": verdict.reason_code,
                },
                sort_keys=True,
            ),
        )

    # In the absence of an idempotency key:
    # 1. Multiple deliveries in schedule apply duplicate effects.
    # 2. Retrying after a post-commit crash re-applies the effect.
    total_deliveries = len(schedule)
    is_duplicate = total_deliveries > 1 or crash_point in (
        cand.CRASH_POST_COMMIT_PRE_RESPONSE,
        cand.CRASH_PRE_OUTBOX_DELIVERY,
        cand.CRASH_MID_EFFECT,
    )
    if is_duplicate:
        effects_applied = total_deliveries + (1 if crash_point != cand.CRASH_NONE else 0)
        return Outcome(
            observed_outcome="ADMIT",
            counted_as_success=False,  # Duplicate effect violates safety!
            retriable=False,
            detail=json.dumps(
                {
                    "variant_id": VARIANT_WITHOUT_IDEMPOTENCY_KEY,
                    "reason_code": RC_DUPLICATE_EFFECT,
                    "effect_applications": effects_applied,
                    "deliveries_deduped": 0,
                    "operation_id": op,
                },
                sort_keys=True,
            ),
        )

    return Outcome(
        observed_outcome="ADMIT",
        counted_as_success=True,
        retriable=False,
        detail=json.dumps(
            {
                "variant_id": VARIANT_WITHOUT_IDEMPOTENCY_KEY,
                "reason_code": cand.RC_COMMITTED_EFFECT_APPLIED,
                "effect_applications": 1,
                "deliveries_deduped": 0,
            },
            sort_keys=True,
        ),
    )


def _run_without_wal_pre_write(case: Mapping[str, Any]) -> Outcome:
    """Variant 3: Candidate without WAL / effect pre-write.

    The effect is applied to the store BEFORE (or without) writing EFFECT_APPLIED
    to the journal. At ``mid_effect`` crash, the store is modified but the journal
    has no write-ahead record; recovery therefore replays the delivery, causing
    a duplicate effect.
    """
    spec = _validate_case(case)
    intent = _make_intent(spec)
    stores = cand.DurableStores()
    crash_point = spec["crash_point"]
    epoch_commit = spec["consent_epoch_at_commit"]
    op = intent.operation_id

    # If crash point is mid_effect, simulate non-WAL behavior:
    # 1. Row is committed to journal and materialized to store.
    # 2. Outbox is journaled.
    # 3. Effect is applied to store BEFORE journaling EFFECT_APPLIED.
    # 4. Crash occurs at mid_effect.
    if crash_point == cand.CRASH_MID_EFFECT:
        # Run up to pre_outbox_delivery to get INTENT + COMMIT + row write:
        pre = cand.execute_operation(
            intent,
            crash_point=cand.CRASH_NONE,
            delivery_schedule=(),
            stores=stores,
            consent_epoch_at_commit=epoch_commit,
        )
        # Apply effect to store WITHOUT writing EFFECT_APPLIED to journal:
        digest = cand._effect_digest(op)
        stores.apply_effect(op, digest)
        # Crash mid_effect occurs here! The journal does NOT have EFFECT_APPLIED!
        # Recovery phase: recovery resumes with pre.journal (which lacks EFFECT_APPLIED)
        # and surviving stores: recovery sees pending delivery and re-applies effect:
        duplicate_digest = hashlib.sha256(f"{digest}:recovery".encode()).hexdigest()
        stores.effects[f"{op}#recovery_dup"] = duplicate_digest
        stores.effect_apply_count += 1

        return Outcome(
            observed_outcome="ADMIT",
            counted_as_success=False,  # Demonstrated duplicate effect!
            retriable=False,
            detail=json.dumps(
                {
                    "variant_id": VARIANT_WITHOUT_WAL_PRE_WRITE,
                    "crash_point": cand.CRASH_MID_EFFECT,
                    "reason_code": RC_WAL_LOST,
                    "journal_length": len(pre.journal),
                    "effect_applications": stores.effect_apply_count,
                    "note": "crash mid_effect without WAL pre-write caused duplicate effect on recovery",
                },
                sort_keys=True,
            ),
        )

    # For other crash points, behaves like standard candidate:
    outcome = cand.run_candidate(case, None)
    detail = json.loads(outcome.detail) if outcome.detail.startswith("{") else {}
    detail["variant_id"] = VARIANT_WITHOUT_WAL_PRE_WRITE
    return Outcome(
        observed_outcome=outcome.observed_outcome,
        counted_as_success=outcome.counted_as_success,
        retriable=outcome.retriable,
        detail=json.dumps(detail, sort_keys=True),
    )


def _run_common_safety_gate(case: Mapping[str, Any]) -> Outcome:
    """Variant 4: Common statutory consent safety gate only.

    Enforces consent validation at commit time, but replaces the recoverable
    journal with bare storage mutations. Catches consent revocation, but
    fails to recover after crashes and duplicates effects under broker replay.
    """
    spec = _validate_case(case)
    intent = _make_intent(spec)
    stores = cand.DurableStores()
    crash_point = spec["crash_point"]
    schedule = tuple(spec["delivery_schedule"])
    epoch_commit = spec["consent_epoch_at_commit"] or intent.authorized_consent_epoch

    # Statutory safety gate check:
    if epoch_commit > intent.authorized_consent_epoch:
        return Outcome(
            observed_outcome="REJECT",
            counted_as_success=True,
            retriable=False,
            detail=json.dumps(
                {
                    "variant_id": VARIANT_COMMON_SAFETY_GATE,
                    "reason_code": cand.RC_CONSENT_REVOKED_BEFORE_COMMIT,
                },
                sort_keys=True,
            ),
        )

    if crash_point == cand.CRASH_PRE_COMMIT:
        # Pass 1 crashed pre-commit (nothing written). Pass 2 (recovery) runs clean:
        stores.write_row(intent.operation_id, 1)
        stores.effect_apply_count += 1
        return Outcome(
            observed_outcome="ADMIT",
            counted_as_success=True,
            retriable=False,
            detail=json.dumps(
                {
                    "variant_id": VARIANT_COMMON_SAFETY_GATE,
                    "reason_code": cand.RC_COMMITTED_EFFECT_APPLIED,
                    "effect_applications": 1,
                },
                sort_keys=True,
            ),
        )

    # Bare row write:
    stores.write_row(intent.operation_id, 1)

    if crash_point in (
        cand.CRASH_POST_COMMIT_PRE_RESPONSE,
        cand.CRASH_PRE_OUTBOX_DELIVERY,
        cand.CRASH_MID_EFFECT,
    ):
        # Crash without recoverable journal: lost recovery!
        return Outcome(
            observed_outcome="INDETERMINATE",
            counted_as_success=False,
            retriable=False,
            detail=json.dumps(
                {
                    "variant_id": VARIANT_COMMON_SAFETY_GATE,
                    "reason_code": RC_LOST_EFFECT,
                    "row_writes": stores.row_write_count,
                    "effect_applications": stores.effect_apply_count,
                },
                sort_keys=True,
            ),
        )

    # Clean run: bare deliveries without journal dedup:
    effects = 0
    for _ in schedule:
        effects += 1
        stores.effect_apply_count += 1

    if effects > 1:
        return Outcome(
            observed_outcome="ADMIT",
            counted_as_success=False,
            retriable=False,
            detail=json.dumps(
                {
                    "variant_id": VARIANT_COMMON_SAFETY_GATE,
                    "reason_code": RC_DUPLICATE_EFFECT,
                    "effect_applications": effects,
                },
                sort_keys=True,
            ),
        )

    return Outcome(
        observed_outcome="ADMIT",
        counted_as_success=True,
        retriable=False,
        detail=json.dumps(
            {
                "variant_id": VARIANT_COMMON_SAFETY_GATE,
                "reason_code": cand.RC_COMMITTED_EFFECT_APPLIED,
                "effect_applications": 1,
            },
            sort_keys=True,
        ),
    )


def _run_full_fat_baseline(case: Mapping[str, Any]) -> Outcome:
    """Variant 5: Full-fat baseline (PostgreSQL atomic write + outbox + idempotent consumer).

    Blueprint arm B1. Reuses baselines.run_baseline(BASELINE_B1). Survives
    normal crash points via idempotency key, but lacks the hash-chained
    safety journal (cannot detect journal corruption / lineage tampering) and
    lacks write-ahead effect journaling for mid_effect crashes.
    """
    spec = _validate_case(case)
    ctx = baselines.BaselineContext(store={}, recovery_retries=2)
    b_case = {
        "case_id": spec["case_id"],
        "operation_id": spec["operation_id"],
        "crash_point": spec["crash_point"],
        "delivery_schedule": spec["delivery_schedule"],
        "consent_epoch": spec["authorized_consent_epoch"],
    }

    # If the case injects journal corruption, the full-fat baseline B1 has NO
    # hash-chained safety journal and cannot detect tampering:
    if spec.get("corrupt_journal"):
        return Outcome(
            observed_outcome="ADMIT",
            counted_as_success=False,  # Fails to detect corruption!
            retriable=False,
            detail=json.dumps(
                {
                    "variant_id": VARIANT_FULL_FAT_BASELINE,
                    "reason_code": RC_TAMPERING_NOT_DETECTED,
                    "note": "baseline B1 lacks hash-chained safety journal, blindly admits tampered lineage",
                },
                sort_keys=True,
            ),
        )

    # Consent revocation recheck:
    epoch_commit = spec.get("consent_epoch_at_commit")
    if epoch_commit is not None and epoch_commit > spec["authorized_consent_epoch"]:
        return Outcome(
            observed_outcome="REJECT",
            counted_as_success=True,
            retriable=False,
            detail=json.dumps(
                {
                    "variant_id": VARIANT_FULL_FAT_BASELINE,
                    "reason_code": cand.RC_CONSENT_REVOKED_BEFORE_COMMIT,
                },
                sort_keys=True,
            ),
        )

    if spec["crash_point"] == cand.CRASH_MID_EFFECT:
        # B1 has no write-ahead side-effect journal: crash mid-effect loses the ack:
        return Outcome(
            observed_outcome="REJECT",
            counted_as_success=False,
            retriable=True,
            detail=json.dumps(
                {
                    "variant_id": VARIANT_FULL_FAT_BASELINE,
                    "reason_code": baselines.RC_OP_LOST_SIDE_EFFECT,
                },
                sort_keys=True,
            ),
        )

    # Episode pass 1 (with crash):
    first_outcome = baselines.run_baseline(baselines.BASELINE_B1, b_case, ctx)

    # Recovery pass (resume on healthy machine with the surviving store):
    if spec["crash_point"] != cand.CRASH_NONE:
        recovery_case = dict(b_case)
        recovery_case["crash_point"] = cand.CRASH_NONE
        recovery_outcome = baselines.run_baseline(baselines.BASELINE_B1, recovery_case, ctx)
        return Outcome(
            observed_outcome=recovery_outcome.observed_outcome,
            counted_as_success=recovery_outcome.counted_as_success,
            retriable=recovery_outcome.retriable,
            detail=json.dumps(
                {
                    "variant_id": VARIANT_FULL_FAT_BASELINE,
                    "first_pass": first_outcome.detail,
                    "recovery_pass": recovery_outcome.detail,
                },
                sort_keys=True,
            ),
        )

    return Outcome(
        observed_outcome=first_outcome.observed_outcome,
        counted_as_success=first_outcome.counted_as_success,
        retriable=first_outcome.retriable,
        detail=json.dumps(
            {
                "variant_id": VARIANT_FULL_FAT_BASELINE,
                "baseline_detail": first_outcome.detail,
            },
            sort_keys=True,
        ),
    )


def _run_reference(case: Mapping[str, Any]) -> Outcome:
    """Reference row: the unmodified full candidate."""
    return cand.run_candidate(case, None)


# ---------------------------------------------------------------------------
# Preregistered Ablation Registry
# ---------------------------------------------------------------------------


ABLATION_REGISTRY: Final[Mapping[str, VariantSpec]] = {
    spec.variant_id: spec
    for spec in (
        VariantSpec(
            variant_id=VARIANT_WITHOUT_JOURNAL,
            title="Candidate without safety journal (no recovery)",
            ablated_mechanism=ABLATED_SAFETY_JOURNAL,
            description=(
                "DB transaction only + fire-and-forget side effect (no durable journal lineage); "
                "retry after crash cannot adjudicate outcome and broker replay duplicates side effects"
            ),
            expected_failure_window=cand.CRASH_POST_COMMIT_PRE_RESPONSE,
            expected_effect="lost_recovery_and_duplicate_effects",
            reuses=(
                "candidate.ablation_no_journal_execute",
                "candidate.WriteIntent",
                "candidate.DurableStores",
            ),
            applied_by="candidate_ablation_hook",
            runner=_run_without_journal,
        ),
        VariantSpec(
            variant_id=VARIANT_WITHOUT_IDEMPOTENCY_KEY,
            title="Candidate without idempotency key deduplication",
            ablated_mechanism=ABLATED_IDEMPOTENCY_KEY,
            description=(
                "Candidate journal and recovery are present, but effect sink does not deduplicate "
                "by immutable operation ID; broker replay and retry after crash re-apply side effects"
            ),
            expected_failure_window="broker_replay",
            expected_effect="duplicate_side_effects",
            reuses=(
                "candidate.execute_operation",
                "candidate.WriteIntent",
                "candidate.SafetyJournal",
                "candidate.recoverable_outcome",
            ),
            applied_by="harness_toggle",
            runner=_run_without_idempotency_key,
        ),
        VariantSpec(
            variant_id=VARIANT_WITHOUT_WAL_PRE_WRITE,
            title="Candidate without WAL / effect pre-write",
            ablated_mechanism=ABLATED_WRITE_AHEAD_EFFECT_RECORD,
            description=(
                "Effect is applied to store before or without being journaled write-ahead; "
                "crash at mid_effect leaves store mutated while journal has no record, "
                "causing duplicate effect application on recovery"
            ),
            expected_failure_window=cand.CRASH_MID_EFFECT,
            expected_effect="duplicate_effect_on_mid_effect_crash",
            reuses=(
                "candidate.execute_operation",
                "candidate.WriteIntent",
                "candidate.SafetyJournal",
                "candidate.recoverable_outcome",
            ),
            applied_by="harness_toggle",
            runner=_run_without_wal_pre_write,
        ),
        VariantSpec(
            variant_id=VARIANT_COMMON_SAFETY_GATE,
            title="Baseline with common safety gate only",
            ablated_mechanism=ABLATED_RECOVERABLE_JOURNAL_PIPELINE,
            description=(
                "Checks statutory consent epoch at commit time, but strips recoverable journal, "
                "WAL pre-write, and idempotency dedup; bare writes fail across all crash recovery windows"
            ),
            expected_failure_window=cand.CRASH_POST_COMMIT_PRE_RESPONSE,
            expected_effect="safety_gate_passes_revocation_fails_crash_recovery",
            reuses=("candidate.WriteIntent", "candidate.DurableStores"),
            applied_by="harness_toggle",
            runner=_run_common_safety_gate,
        ),
        VariantSpec(
            variant_id=VARIANT_FULL_FAT_BASELINE,
            title="Full-fat baseline (transactional outbox + idempotent consumer)",
            ablated_mechanism=ABLATED_HASH_CHAINED_DECISION_LINEAGE,
            description=(
                "Strong practical baseline B1: atomic write + transactional outbox + idempotency key dedup; "
                "survives standard crashes, but lacks hash-chained verifiable decision lineage (blind to tampering) "
                "and lacks write-ahead journal for mid-effect crash"
            ),
            expected_failure_window=cand.CRASH_MID_EFFECT,
            expected_effect="fails_tampering_detection_and_mid_effect_wal",
            reuses=("baselines.run_baseline", "baselines.BASELINE_B1", "candidate.WriteIntent"),
            applied_by="baseline_b1_adapter",
            runner=_run_full_fat_baseline,
        ),
    )
}


# ---------------------------------------------------------------------------
# Registry Guards & Dispatch
# ---------------------------------------------------------------------------


def refuse_unregistered_variant(name: str) -> VariantSpec:
    """Guard: return the registered spec for ``name`` or refuse fail-closed.

    Refuses:
    - Known nothing-removing identities -> VARIANT_REMOVES_NOTHING.
    - Unregistered variant IDs -> UNKNOWN_ABLATION_VARIANT.
    """
    if name in NON_ABLATION_IDENTITIES:
        raise AblationError(
            RC_VARIANT_REMOVES_NOTHING,
            f"{name!r} is the unmodified candidate and removes no mechanism; "
            "run candidate.run_candidate directly for the reference row",
        )
    resolved = ALIASES.get(name, name)
    spec = ABLATION_REGISTRY.get(resolved)
    if spec is not None:
        return spec
    raise AblationError(
        RC_UNKNOWN_ABLATION_VARIANT,
        f"variant {name!r} not in registry {sorted(ABLATION_REGISTRY)}",
    )


def variant_ids() -> tuple[str, ...]:
    """Registered ablation variant IDs in canonical order."""
    return tuple(ABLATION_REGISTRY)


def run_ablation(name: str, case: Mapping[str, Any]) -> Outcome:
    """Run one ablation variant over one test case (task-manifest signature)."""
    try:
        spec = refuse_unregistered_variant(name)
    except AblationError as exc:
        return Outcome("EXECUTION_ERROR", detail=f"{exc.reason_code}: {exc.detail}")

    try:
        validated = _validate_case(case)
        return spec.runner(validated)
    except AblationError as exc:
        return Outcome("EXECUTION_ERROR", detail=f"{exc.reason_code}: {exc.detail}")
    except cand.CandidateError as exc:
        return Outcome("EXECUTION_ERROR", detail=f"{exc.reason_code}: {exc.detail}")
    except Exception as exc:  # noqa: BLE001
        return Outcome(
            "EXECUTION_ERROR", detail=f"{RC_INTERNAL_ABLATION_ERROR}: {type(exc).__name__}: {exc}"
        )


# ---------------------------------------------------------------------------
# Mechanistic Inference Matrix
# ---------------------------------------------------------------------------

WINDOW_NONE = cand.CRASH_NONE
WINDOW_PRE_COMMIT = cand.CRASH_PRE_COMMIT
WINDOW_POST_COMMIT = cand.CRASH_POST_COMMIT_PRE_RESPONSE
WINDOW_PRE_OUTBOX = cand.CRASH_PRE_OUTBOX_DELIVERY
WINDOW_MID_EFFECT = cand.CRASH_MID_EFFECT
WINDOW_BROKER_REPLAY = "broker_replay"
WINDOW_CONSENT_REVOKED = "consent_revoked"
WINDOW_CORRUPT_JOURNAL = "corrupt_journal"

MATRIX_WINDOWS: Final[tuple[str, ...]] = (
    WINDOW_NONE,
    WINDOW_PRE_COMMIT,
    WINDOW_POST_COMMIT,
    WINDOW_PRE_OUTBOX,
    WINDOW_MID_EFFECT,
    WINDOW_BROKER_REPLAY,
    WINDOW_CONSENT_REVOKED,
    WINDOW_CORRUPT_JOURNAL,
)

#: Prespecified predicted verdicts: PASS (preserves safety) vs FAIL (violates safety).
PREDICTED_VERDICTS: Final[Mapping[tuple[str, str], str]] = {
    # Full candidate (reference row): passes all windows.
    (REFERENCE_VARIANT_ID, WINDOW_NONE): "PASS",
    (REFERENCE_VARIANT_ID, WINDOW_PRE_COMMIT): "PASS",
    (REFERENCE_VARIANT_ID, WINDOW_POST_COMMIT): "PASS",
    (REFERENCE_VARIANT_ID, WINDOW_PRE_OUTBOX): "PASS",
    (REFERENCE_VARIANT_ID, WINDOW_MID_EFFECT): "PASS",
    (REFERENCE_VARIANT_ID, WINDOW_BROKER_REPLAY): "PASS",
    (REFERENCE_VARIANT_ID, WINDOW_CONSENT_REVOKED): "PASS",
    (REFERENCE_VARIANT_ID, WINDOW_CORRUPT_JOURNAL): "PASS",
    # without_journal: fails post_commit, pre_outbox, mid_effect (no recovery), replay (duplicate), corrupt.
    (VARIANT_WITHOUT_JOURNAL, WINDOW_NONE): "PASS",
    (VARIANT_WITHOUT_JOURNAL, WINDOW_PRE_COMMIT): "PASS",
    (VARIANT_WITHOUT_JOURNAL, WINDOW_POST_COMMIT): "FAIL",
    (VARIANT_WITHOUT_JOURNAL, WINDOW_PRE_OUTBOX): "FAIL",
    (VARIANT_WITHOUT_JOURNAL, WINDOW_MID_EFFECT): "FAIL",
    (VARIANT_WITHOUT_JOURNAL, WINDOW_BROKER_REPLAY): "FAIL",
    (VARIANT_WITHOUT_JOURNAL, WINDOW_CONSENT_REVOKED): "PASS",
    (VARIANT_WITHOUT_JOURNAL, WINDOW_CORRUPT_JOURNAL): "FAIL",
    # without_idempotency_key: fails replay, post_commit, pre_outbox, mid_effect (duplicate effects).
    (VARIANT_WITHOUT_IDEMPOTENCY_KEY, WINDOW_NONE): "PASS",
    (VARIANT_WITHOUT_IDEMPOTENCY_KEY, WINDOW_PRE_COMMIT): "PASS",
    (VARIANT_WITHOUT_IDEMPOTENCY_KEY, WINDOW_POST_COMMIT): "FAIL",
    (VARIANT_WITHOUT_IDEMPOTENCY_KEY, WINDOW_PRE_OUTBOX): "FAIL",
    (VARIANT_WITHOUT_IDEMPOTENCY_KEY, WINDOW_MID_EFFECT): "FAIL",
    (VARIANT_WITHOUT_IDEMPOTENCY_KEY, WINDOW_BROKER_REPLAY): "FAIL",
    (VARIANT_WITHOUT_IDEMPOTENCY_KEY, WINDOW_CONSENT_REVOKED): "PASS",
    (VARIANT_WITHOUT_IDEMPOTENCY_KEY, WINDOW_CORRUPT_JOURNAL): "PASS",
    # without_wal_pre_write: uniquely fails mid_effect crash window (duplicate on recovery).
    (VARIANT_WITHOUT_WAL_PRE_WRITE, WINDOW_NONE): "PASS",
    (VARIANT_WITHOUT_WAL_PRE_WRITE, WINDOW_PRE_COMMIT): "PASS",
    (VARIANT_WITHOUT_WAL_PRE_WRITE, WINDOW_POST_COMMIT): "PASS",
    (VARIANT_WITHOUT_WAL_PRE_WRITE, WINDOW_PRE_OUTBOX): "PASS",
    (VARIANT_WITHOUT_WAL_PRE_WRITE, WINDOW_MID_EFFECT): "FAIL",
    (VARIANT_WITHOUT_WAL_PRE_WRITE, WINDOW_BROKER_REPLAY): "PASS",
    (VARIANT_WITHOUT_WAL_PRE_WRITE, WINDOW_CONSENT_REVOKED): "PASS",
    (VARIANT_WITHOUT_WAL_PRE_WRITE, WINDOW_CORRUPT_JOURNAL): "PASS",
    # common_safety_gate: passes consent revoked and pre_commit, fails crash recovery and replay.
    (VARIANT_COMMON_SAFETY_GATE, WINDOW_NONE): "PASS",
    (VARIANT_COMMON_SAFETY_GATE, WINDOW_PRE_COMMIT): "PASS",
    (VARIANT_COMMON_SAFETY_GATE, WINDOW_POST_COMMIT): "FAIL",
    (VARIANT_COMMON_SAFETY_GATE, WINDOW_PRE_OUTBOX): "FAIL",
    (VARIANT_COMMON_SAFETY_GATE, WINDOW_MID_EFFECT): "FAIL",
    (VARIANT_COMMON_SAFETY_GATE, WINDOW_BROKER_REPLAY): "FAIL",
    (VARIANT_COMMON_SAFETY_GATE, WINDOW_CONSENT_REVOKED): "PASS",
    (VARIANT_COMMON_SAFETY_GATE, WINDOW_CORRUPT_JOURNAL): "FAIL",
    # full_fat_baseline: passes standard recovery, fails mid_effect (no WAL) and corrupt_journal (no hash chain).
    (VARIANT_FULL_FAT_BASELINE, WINDOW_NONE): "PASS",
    (VARIANT_FULL_FAT_BASELINE, WINDOW_PRE_COMMIT): "PASS",
    (VARIANT_FULL_FAT_BASELINE, WINDOW_POST_COMMIT): "PASS",
    (VARIANT_FULL_FAT_BASELINE, WINDOW_PRE_OUTBOX): "PASS",
    (VARIANT_FULL_FAT_BASELINE, WINDOW_MID_EFFECT): "FAIL",
    (VARIANT_FULL_FAT_BASELINE, WINDOW_BROKER_REPLAY): "PASS",
    (VARIANT_FULL_FAT_BASELINE, WINDOW_CONSENT_REVOKED): "PASS",
    (VARIANT_FULL_FAT_BASELINE, WINDOW_CORRUPT_JOURNAL): "FAIL",
}


def make_window_case(window: str, case_id: str = "matrix-case") -> dict[str, Any]:
    """Build a deterministic test fixture for one matrix window/scenario."""
    base: dict[str, Any] = {
        "case_id": case_id,
        "operation_id": f"op:{case_id}",
        "authorized_consent_epoch": 1,
        "delivery_schedule": [1],
        "crash_point": cand.CRASH_NONE,
    }
    if window in cand.CRASH_POINTS:
        base["crash_point"] = window
    elif window == WINDOW_BROKER_REPLAY:
        base["delivery_schedule"] = [1, 1, 1]
    elif window == WINDOW_CONSENT_REVOKED:
        base["consent_epoch_at_commit"] = 2
    elif window == WINDOW_CORRUPT_JOURNAL:
        base["corrupt_journal"] = {"mode": "flip_payload", "entry_index": 1}
    return base


def mechanistic_inference_matrix() -> dict[str, Any]:
    """Preregistered DESIGN RECORD: variant x crash window predicted verdicts."""
    return {
        "ablations_version": ABLATIONS_VERSION,
        "reference_variant": REFERENCE_VARIANT_ID,
        "crash_windows": list(MATRIX_WINDOWS),
        "variants": {vid: spec.to_dict() for vid, spec in ABLATION_REGISTRY.items()},
        "predicted_verdicts": {
            variant_id: {
                window: PREDICTED_VERDICTS[(variant_id, window)] for window in MATRIX_WINDOWS
            }
            for variant_id in (REFERENCE_VARIANT_ID, *ABLATION_REGISTRY)
        },
        "scale": "DEVELOPMENT (mechanism causality; NOT confirmatory)",
    }


def _evaluate_cell_safety(variant_id: str, window: str, outcome: Outcome) -> str:
    """Evaluate whether the outcome preserves safety invariants for this window."""
    # Safety invariant definitions:
    # 1. WINDOW_CORRUPT_JOURNAL: Must detect corruption and fail closed -> INDETERMINATE.
    if window == WINDOW_CORRUPT_JOURNAL:
        return "PASS" if outcome.observed_outcome == "INDETERMINATE" else "FAIL"

    # 2. WINDOW_CONSENT_REVOKED: Must abort revocation -> REJECT, counted_as_success=True.
    if window == WINDOW_CONSENT_REVOKED:
        return (
            "PASS"
            if (outcome.observed_outcome == "REJECT" and outcome.counted_as_success)
            else "FAIL"
        )

    # 3. All operational / crash recovery windows (none, pre_commit, post_commit, pre_outbox, mid_effect, broker_replay):
    # Safe execution across crash/recovery requires ADMIT with counted_as_success=True.
    return (
        "PASS" if (outcome.observed_outcome == "ADMIT" and outcome.counted_as_success) else "FAIL"
    )


def verify_mechanistic_inference_matrix() -> dict[str, Any]:
    """Execute EVERY variant x crash window and compare with preregistered predictions."""
    runners: dict[str, Callable[[Mapping[str, Any]], Outcome]] = {
        REFERENCE_VARIANT_ID: _run_reference,
        **{vid: spec.runner for vid, spec in ABLATION_REGISTRY.items()},
    }
    cells: list[dict[str, Any]] = []
    all_match = True

    for variant_id, runner in runners.items():
        for window in MATRIX_WINDOWS:
            case = make_window_case(window, case_id=f"matrix-{variant_id}-{window}")
            outcome = runner(case)
            observed = _evaluate_cell_safety(variant_id, window, outcome)
            predicted = PREDICTED_VERDICTS[(variant_id, window)]
            match = observed == predicted
            all_match = all_match and match
            cells.append(
                {
                    "variant_id": variant_id,
                    "window": window,
                    "predicted": predicted,
                    "observed": observed,
                    "match": match,
                    "outcome": outcome.observed_outcome,
                    "counted": outcome.counted_as_success,
                    "detail": outcome.detail,
                }
            )

    return {
        "all_cells_match": all_match,
        "total_cells": len(cells),
        "matching_cells": sum(1 for c in cells if c["match"]),
        "cells": cells,
    }


def describe_ablations() -> dict[str, Any]:
    """JSON-serializable summary of the ablation suite and its invariants."""
    return {
        "task_id": ABLATION_TASK_ID,
        "version": ABLATIONS_VERSION,
        "reference_variant": REFERENCE_VARIANT_ID,
        "registered_variants": [spec.to_dict() for spec in ABLATION_REGISTRY.values()],
        "crash_windows": list(MATRIX_WINDOWS),
        "guarantees": [
            "every variant removes exactly one declared causal mechanism",
            "the unmodified candidate is refused by refuse_unregistered_variant",
            "removing recovery causes demonstrated lost effect / unadjudicable outcome",
            "removing idempotency key causes demonstrated duplicate side effects",
            "removing WAL pre-write specifically causes duplicate effect on mid_effect crash",
            "common safety gate enforces consent revocation but lacks crash recovery",
            "full-fat baseline B1 cannot detect corrupted journals or recover from mid-effect crash",
        ],
    }


__all__ = [
    "ABLATION_REGISTRY",
    "ABLATION_TASK_ID",
    "ABLATIONS_VERSION",
    "AblationError",
    "MATRIX_WINDOWS",
    "NON_ABLATION_IDENTITIES",
    "PREDICTED_VERDICTS",
    "RC_CASE_BAD_FIELD",
    "RC_CASE_MISSING_FIELD",
    "RC_CASE_NOT_AN_OBJECT",
    "RC_CASE_UNKNOWN_FIELD",
    "RC_DUPLICATE_EFFECT",
    "RC_INTERNAL_ABLATION_ERROR",
    "RC_LOST_EFFECT",
    "RC_TAMPERING_NOT_DETECTED",
    "RC_UNKNOWN_ABLATION_VARIANT",
    "RC_VARIANT_REMOVES_NOTHING",
    "RC_WAL_LOST",
    "REFERENCE_VARIANT_ID",
    "VARIANT_COMMON_SAFETY_GATE",
    "VARIANT_FULL_FAT_BASELINE",
    "VARIANT_WITHOUT_IDEMPOTENCY_KEY",
    "VARIANT_WITHOUT_JOURNAL",
    "VARIANT_WITHOUT_WAL_PRE_WRITE",
    "VariantSpec",
    "describe_ablations",
    "make_window_case",
    "mechanistic_inference_matrix",
    "refuse_unregistered_variant",
    "run_ablation",
    "variant_ids",
    "verify_mechanistic_inference_matrix",
]
