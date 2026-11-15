"""Tests for IFIP_SEC-candidate (replay-closed authorization).

Positive controls (must pass):
- A fresh, correctly-bound request under a freshly issued delegated receipt is
  ALLOWed with the nonce consumed exactly once (CASE-01 fresh acceptance).
- A cross-purpose replay of the same receipt is DENYed PURPOSE_MISMATCH.
- A delegation-length change (chain truncated/extended) is DENYed
  DELEGATION_CHAIN_CHANGED (commitment re-derivation + request binding).
- A lineage splice (receipt carried with a different proposal lineage) is
  DENYed LINEAGE_SPLICED.
- An exact replay (same receipt, same request, valid signature, unchanged
  bindings) is DENYed NONCE_REPLAYED because the nonce was consumed once.

THE CENTRAL ABLATION CONTRASTS (proving each mechanism):
- ablation_no_lineage_binding() ADMITs the very splice authorize() DENYs —
  the lineage binding (not the HMAC) is the mechanism stopping it.
- ablation_no_nonce() ADMITs the very exact replay authorize() DENYs —
  the consume-once nonce (not the HMAC) is the mechanism stopping it.
Each ablation removes exactly one mechanism and leaves every other binding
enforced (e.g. the ablated authorizers still reject cross-purpose replay).

Fail-closed controls:
- Tampered receipt -> RECEIPT_SIGNATURE_INVALID; unknown (unregistered but
  validly signed) receipt -> RECEIPT_UNKNOWN; expired -> RECEIPT_EXPIRED;
  broken ancestry -> DELEGATION_ANCESTRY_BROKEN; consent revoked between
  issue and presentation -> CONSENT_EPOCH_REVOKED; malformed payloads ->
  fail_closed DENY (never raising, never silently counted).
- The nonce is consumed ONLY on ALLOW: any DENY leaves the store intact.

Determinism:
- Identical inputs yield identical verdict dicts (including digest); the
  pipeline order is fixed and verdict digests are stable.
"""

from __future__ import annotations

import pytest

from evaluation.venue2027.ifip_sec import candidate as cand
from evaluation.venue2027.ifip_sec.candidate import (
    CANDIDATE_ID,
    CANDIDATE_VERSION,
    AuthorizationLedger,
    AuthorizationRequest,
    CandidateContext,
    CandidateError,
    Receipt,
    ablation_no_lineage_binding,
    ablation_no_nonce,
    authorize,
    describe_mechanism,
    issue_receipt,
    run_candidate,
)

HMAC_KEY = b"ifip-sec-candidate-unit-test-key-0123456789"
NOW = 1_700_000_000
EXPIRY = 4_102_444_800

BASE_NONCE_STORE = {"nonce-fresh-0001"}


# ---------------------------------------------------------------------------
# Fixture builders: delegated receipt + matching request, all bindings aligned
# ---------------------------------------------------------------------------


def _ledger(**overrides: object) -> AuthorizationLedger:
    return AuthorizationLedger(
        HMAC_KEY,
        now_epoch_seconds=overrides.get("now_epoch_seconds", NOW),
        live_epochs=overrides.get("live_epochs") or {},
    )


def _fresh_receipt(
    ledger: AuthorizationLedger,
    *,
    nonce: str = "nonce-fresh-0001",
    proposal_lineage: tuple[str, ...] = ("proposal-A1",),
) -> Receipt:
    """Issue + register a delegated receipt: root -> practitioner -> resident."""
    root = ledger.issue(
        receipt_id="receipt-root-0001",
        actor_id="attending-physician",
        patient_id="synthetic-patient",
        tenant_id="synthetic-tenant",
        purpose="self_care",
        task_id="task-medication-review",
        consent_epoch="consent-3",
        policy_epoch="epoch-7",
        dispatch_digest="sha256:" + "a" * 64,
        nonce="nonce-root-0000",
        expiry=EXPIRY,
        delegation_chain=("attending-physician",),
        proposal_lineage=proposal_lineage,
    )
    delegated = ledger.delegate(
        root,
        receipt_id="receipt-delegated-0001",
        delegatee_actor_id="resident-physician",
        nonce=nonce,
        proposal_lineage=proposal_lineage,
    )
    return delegated


def _matching_request(receipt: Receipt) -> AuthorizationRequest:
    return AuthorizationRequest(
        actor_id=receipt.actor_id,
        tenant_id=receipt.tenant_id,
        patient_id=receipt.patient_id,
        purpose=receipt.purpose,
        task_id=receipt.task_id,
        consent_epoch=receipt.consent_epoch,
        policy_epoch=receipt.policy_epoch,
        dispatch_digest=receipt.dispatch_digest,
        delegation_chain=receipt.delegation_chain,
        proposal_lineage=receipt.proposal_lineage,
    )


def _fresh_authorization(
    *,
    nonce: str = "nonce-fresh-0001",
    store: set[str] | None = None,
    ledger: AuthorizationLedger | None = None,
    proposal_lineage: tuple[str, ...] = ("proposal-A1",),
) -> tuple[Receipt, AuthorizationRequest, set[str], AuthorizationLedger]:
    ledger = ledger or _ledger()
    receipt = _fresh_receipt(ledger, nonce=nonce, proposal_lineage=proposal_lineage)
    return receipt, _matching_request(receipt), store or set(BASE_NONCE_STORE), ledger


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_fresh_request_allowed_and_nonce_consumed() -> None:
    receipt, request, store, ledger = _fresh_authorization()
    verdict = authorize(receipt, request, store, ledger)
    assert verdict.decision == "ALLOW"
    assert verdict.reason_code == "NONCE_CONSUMED_OK"
    assert verdict.fail_closed is False
    assert verdict.nonce_consumed is True
    assert store == set()  # consume-once: the only nonce is gone


def test_fresh_request_via_run_candidate_maps_to_admit_outcome() -> None:
    receipt, request, store, ledger = _fresh_authorization()
    ctx = CandidateContext(hmac_key=HMAC_KEY, nonce_store=store, ledger=ledger)
    outcome = run_candidate({"receipt": receipt.to_dict(), "request": request.to_dict()}, ctx)
    assert outcome.observed_outcome == "ADMIT"
    assert outcome.detail == "NONCE_CONSUMED_OK"
    assert outcome.counted_as_success is True


# ---------------------------------------------------------------------------
# Replay-closure positives: every changed binding makes the replay fail closed
# ---------------------------------------------------------------------------


def test_cross_purpose_replay_denied() -> None:
    receipt, request, store, ledger = _fresh_authorization()
    assert authorize(receipt, request, store, ledger).decision == "ALLOW"
    replayed = cand.AuthorizationRequest(
        actor_id=request.actor_id,
        tenant_id=request.tenant_id,
        patient_id=request.patient_id,
        purpose="research_secondary",  # different purpose, same receipt
        task_id=request.task_id,
        consent_epoch=request.consent_epoch,
        policy_epoch=request.policy_epoch,
        dispatch_digest=request.dispatch_digest,
        delegation_chain=request.delegation_chain,
        proposal_lineage=request.proposal_lineage,
    )
    verdict = authorize(receipt, replayed, store, ledger)
    assert verdict.decision == "DENY"
    assert verdict.reason_code == "PURPOSE_MISMATCH"
    assert verdict.fail_closed is False
    assert verdict.nonce_consumed is False


def test_delegation_length_change_denied() -> None:
    ledger = _ledger()
    receipt = _fresh_receipt(ledger, nonce="nonce-fresh-0001")
    # The replaying attacker truncates the carried delegation chain.
    truncated = cand.AuthorizationRequest(
        actor_id=receipt.actor_id,
        tenant_id=receipt.tenant_id,
        patient_id=receipt.patient_id,
        purpose=receipt.purpose,
        task_id=receipt.task_id,
        consent_epoch=receipt.consent_epoch,
        policy_epoch=receipt.policy_epoch,
        dispatch_digest=receipt.dispatch_digest,
        delegation_chain=receipt.delegation_chain[:-1],  # shorter chain
        proposal_lineage=receipt.proposal_lineage,
    )
    verdict = authorize(receipt, truncated, {"nonce-fresh-0001"}, ledger)
    assert verdict.decision == "DENY"
    assert verdict.reason_code == "DELEGATION_CHAIN_CHANGED"

    # An extended chain (a hop the issuer never delegated) is caught too.
    extended = cand.AuthorizationRequest(
        actor_id=receipt.actor_id,
        tenant_id=receipt.tenant_id,
        patient_id=receipt.patient_id,
        purpose=receipt.purpose,
        task_id=receipt.task_id,
        consent_epoch=receipt.consent_epoch,
        policy_epoch=receipt.policy_epoch,
        dispatch_digest=receipt.dispatch_digest,
        delegation_chain=receipt.delegation_chain + ("impostor-hop",),
        proposal_lineage=receipt.proposal_lineage,
    )
    verdict = authorize(receipt, extended, {"nonce-fresh-0001"}, ledger)
    assert verdict.decision == "DENY"
    assert verdict.reason_code == "DELEGATION_CHAIN_CHANGED"


def test_lineage_splice_denied() -> None:
    receipt, request, store, ledger = _fresh_authorization()
    spliced = cand.AuthorizationRequest(
        actor_id=request.actor_id,
        tenant_id=request.tenant_id,
        patient_id=request.patient_id,
        purpose=request.purpose,
        task_id=request.task_id,
        consent_epoch=request.consent_epoch,
        policy_epoch=request.policy_epoch,
        dispatch_digest=request.dispatch_digest,
        delegation_chain=request.delegation_chain,
        proposal_lineage=("proposal-B2", "proposal-C3"),  # attacker-spliced lineage
    )
    verdict = authorize(receipt, spliced, store, ledger)
    assert verdict.decision == "DENY"
    assert verdict.reason_code == "LINEAGE_SPLICED"
    assert verdict.nonce_consumed is False


def test_exact_replay_denied_nonce_replayed() -> None:
    receipt, request, store, ledger = _fresh_authorization()
    first = authorize(receipt, request, store, ledger)
    assert first.decision == "ALLOW"
    # Byte-for-byte identical second presentation: signature still verifies,
    # every binding matches — the consumed nonce is the only difference.
    second = authorize(receipt, request, store, ledger)
    assert second.decision == "DENY"
    assert second.reason_code == "NONCE_REPLAYED"
    assert second.nonce_consumed is False


# ---------------------------------------------------------------------------
# Central ablation contrasts — each mechanism is proven by its removal
# ---------------------------------------------------------------------------


def test_ablation_no_lineage_binding_admits_the_splice() -> None:
    receipt, request, store, ledger = _fresh_authorization()
    spliced = cand.AuthorizationRequest(
        actor_id=request.actor_id,
        tenant_id=request.tenant_id,
        patient_id=request.patient_id,
        purpose=request.purpose,
        task_id=request.task_id,
        consent_epoch=request.consent_epoch,
        policy_epoch=request.policy_epoch,
        dispatch_digest=request.dispatch_digest,
        delegation_chain=request.delegation_chain,
        proposal_lineage=("proposal-B2", "proposal-C3"),
    )
    candidate_verdict = authorize(receipt, spliced, set(store), ledger)
    assert candidate_verdict.decision == "DENY"
    assert candidate_verdict.reason_code == "LINEAGE_SPLICED"

    ablated = ablation_no_lineage_binding()
    ablated_verdict = ablated(receipt, spliced, set(store), ledger)
    assert ablated_verdict.decision == "ALLOW"
    assert ablated_verdict.reason_code == "LINEAGE_UNBOUND"
    assert ablated_verdict.nonce_consumed is True
    # The differential is caused by the lineage binding and nothing else.


def test_ablation_no_lineage_binding_still_enforces_other_bindings() -> None:
    """The ablation removes ONE mechanism, not the security envelope."""
    receipt, request, store, ledger = _fresh_authorization()
    ablated = ablation_no_lineage_binding()
    cross_purpose = cand.AuthorizationRequest(
        actor_id=request.actor_id,
        tenant_id=request.tenant_id,
        patient_id=request.patient_id,
        purpose="research_secondary",
        task_id=request.task_id,
        consent_epoch=request.consent_epoch,
        policy_epoch=request.policy_epoch,
        dispatch_digest=request.dispatch_digest,
        delegation_chain=request.delegation_chain,
        proposal_lineage=request.proposal_lineage,
    )
    verdict = ablated(receipt, cross_purpose, store, ledger)
    assert verdict.decision == "DENY"
    assert verdict.reason_code == "PURPOSE_MISMATCH"
    assert verdict.nonce_consumed is False


def test_ablation_no_nonce_admits_the_replay() -> None:
    receipt, request, store, ledger = _fresh_authorization()
    live_store = set(store)
    candidate_first = authorize(receipt, request, live_store, ledger)
    assert candidate_first.decision == "ALLOW"
    candidate_second = authorize(receipt, request, live_store, ledger)
    assert candidate_second.decision == "DENY"
    assert candidate_second.reason_code == "NONCE_REPLAYED"

    ablated = ablation_no_nonce()
    # A shared live store demonstrates the ablation never consults or
    # consumes the nonce: the second call sees the SAME untouched store.
    shared_store = set(store)
    first = ablated(receipt, request, shared_store, ledger)
    assert first.decision == "ALLOW"
    assert first.reason_code == "NONCE_UNPROTECTED"
    second = ablated(receipt, request, shared_store, ledger)  # exact replay
    assert second.decision == "ALLOW"
    assert second.reason_code == "NONCE_UNPROTECTED"
    assert shared_store == store  # the nonce was never consumed by the ablation
    # The differential is caused by the consume-once nonce and nothing else.


def test_ablation_no_nonce_still_rejects_cross_purpose_replay() -> None:
    receipt, request, store, ledger = _fresh_authorization()
    ablated = ablation_no_nonce()
    cross_purpose = cand.AuthorizationRequest(
        actor_id=request.actor_id,
        tenant_id=request.tenant_id,
        patient_id=request.patient_id,
        purpose="research_secondary",
        task_id=request.task_id,
        consent_epoch=request.consent_epoch,
        policy_epoch=request.policy_epoch,
        dispatch_digest=request.dispatch_digest,
        delegation_chain=request.delegation_chain,
        proposal_lineage=request.proposal_lineage,
    )
    verdict = ablated(receipt, cross_purpose, store, ledger)
    assert verdict.decision == "DENY"
    assert verdict.reason_code == "PURPOSE_MISMATCH"


# ---------------------------------------------------------------------------
# Fail-closed controls (receipt integrity, registration, epochs, shape)
# ---------------------------------------------------------------------------


def _deny_reason(
    receipt: Receipt, request: AuthorizationRequest, store: set[str], ledger: AuthorizationLedger
) -> str:
    verdict = authorize(receipt, request, store, ledger)
    assert verdict.decision == "DENY"
    return verdict.reason_code


def test_tampered_receipt_denied_signature_invalid() -> None:
    ledger = _ledger()
    receipt = _fresh_receipt(ledger, nonce="nonce-fresh-0001")
    tampered = Receipt(
        receipt_id=receipt.receipt_id,
        actor_id=receipt.actor_id,
        patient_id=receipt.patient_id,
        tenant_id=receipt.tenant_id,
        purpose="research_secondary",  # attacker edits the claim...
        task_id=receipt.task_id,
        consent_epoch=receipt.consent_epoch,
        policy_epoch=receipt.policy_epoch,
        dispatch_digest=receipt.dispatch_digest,
        nonce=receipt.nonce,
        expiry=receipt.expiry,
        parent_ref=receipt.parent_ref,
        delegation_chain=receipt.delegation_chain,
        proposal_lineage=receipt.proposal_lineage,
        delegation_chain_hash=receipt.delegation_chain_hash,
        delegation_depth=receipt.delegation_depth,
        proposal_lineage_hash=receipt.proposal_lineage_hash,
        mac=receipt.mac,  # ...but keeps the original MAC
    )
    reason = _deny_reason(tampered, _matching_request(tampered), {"nonce-fresh-0001"}, ledger)
    assert reason == "RECEIPT_SIGNATURE_INVALID"


def test_unregistered_receipt_denied_unknown() -> None:
    other_ledger = _ledger()  # no registrations at all
    receipt, request, store, _ = _fresh_authorization()
    reason = _deny_reason(receipt, request, store, other_ledger)
    assert reason == "RECEIPT_UNKNOWN"


def test_expired_receipt_denied() -> None:
    ledger = _ledger(now_epoch_seconds=EXPIRY + 1)
    receipt = _fresh_receipt(ledger, nonce="nonce-fresh-0001")
    reason = _deny_reason(receipt, _matching_request(receipt), {"nonce-fresh-0001"}, ledger)
    assert reason == "RECEIPT_EXPIRED"


def test_broken_ancestry_denied() -> None:
    ledger = _ledger()
    receipt = issue_receipt(
        hmac_key=HMAC_KEY,
        receipt_id="receipt-orphan-0001",
        actor_id="resident-physician",
        patient_id="synthetic-patient",
        tenant_id="synthetic-tenant",
        purpose="self_care",
        task_id="task-medication-review",
        consent_epoch="consent-3",
        policy_epoch="epoch-7",
        dispatch_digest="sha256:" + "a" * 64,
        nonce="nonce-orphan-0001",
        expiry=EXPIRY,
        parent_ref="receipt-never-registered",  # dangling parent
        delegation_chain=("attending-physician", "resident-physician"),
        proposal_lineage=("proposal-A1",),
    )
    ledger.register(receipt)  # registered, but its parent ref resolves to nothing
    reason = _deny_reason(receipt, _matching_request(receipt), {"nonce-orphan-0001"}, ledger)
    assert reason == "DELEGATION_ANCESTRY_BROKEN"


def test_ancestry_cycle_denied() -> None:
    ledger = _ledger()
    a = ledger.issue(
        receipt_id="receipt-cycle-a",
        actor_id="attending-physician",
        patient_id="synthetic-patient",
        tenant_id="synthetic-tenant",
        purpose="self_care",
        task_id="task-medication-review",
        consent_epoch="consent-3",
        policy_epoch="epoch-7",
        dispatch_digest="sha256:" + "a" * 64,
        nonce="nonce-cycle-a",
        expiry=EXPIRY,
        parent_ref="receipt-cycle-b",
        delegation_chain=("attending-physician",),
        proposal_lineage=("proposal-A1",),
    )
    b = ledger.issue(
        receipt_id="receipt-cycle-b",
        actor_id="resident-physician",
        patient_id="synthetic-patient",
        tenant_id="synthetic-tenant",
        purpose="self_care",
        task_id="task-medication-review",
        consent_epoch="consent-3",
        policy_epoch="epoch-7",
        dispatch_digest="sha256:" + "a" * 64,
        nonce="nonce-cycle-b",
        expiry=EXPIRY,
        parent_ref="receipt-cycle-a",
        delegation_chain=("attending-physician", "resident-physician"),
        proposal_lineage=("proposal-A1",),
    )
    reason = _deny_reason(b, _matching_request(b), {"nonce-cycle-b"}, ledger)
    assert reason == "DELEGATION_ANCESTRY_BROKEN"
    assert not ledger.verify_ancestry(a)


def test_consent_revocation_between_issue_and_presentation_denied() -> None:
    ledger = _ledger(live_epochs={"consent": "consent-3", "policy": "epoch-7"})
    receipt = _fresh_receipt(ledger, nonce="nonce-fresh-0001")
    ledger.set_live_epoch("consent", "consent-4")  # revoked and re-consented
    reason = _deny_reason(receipt, _matching_request(receipt), {"nonce-fresh-0001"}, ledger)
    assert reason == "CONSENT_EPOCH_REVOKED"


def test_malformed_inputs_fail_closed_without_raising() -> None:
    receipt, request, store, ledger = _fresh_authorization()
    for args in (
        (None, request, store, ledger),
        (receipt, None, store, ledger),
        (receipt, request, None, ledger),
        (receipt, request, store, None),
        (receipt, request, ["not-a-set"], ledger),
    ):
        verdict = authorize(*args)  # type: ignore[arg-type]
        assert verdict.decision == "DENY"
        assert verdict.fail_closed is True
    assert store == set(BASE_NONCE_STORE)  # nothing consumed on any DENY


def test_run_candidate_boundary_faults_become_reject_outcomes() -> None:
    ctx = CandidateContext(hmac_key=HMAC_KEY)
    assert run_candidate({"receipt": {}, "request": {}}, ctx).detail in {
        "RECEIPT_MALFORMED",
        "REQUEST_MALFORMED",
    }
    assert run_candidate("not-a-mapping", ctx).detail == "RECEIPT_MALFORMED"  # type: ignore[arg-type]
    assert run_candidate({"request": {}}, ctx).detail == "RECEIPT_MALFORMED"
    with pytest.raises(CandidateError):
        AuthorizationRequest.from_dict({"actor_id": "x"})  # missing fields


def test_run_candidate_unknown_context_type_rejected() -> None:
    receipt, request, store, ledger = _fresh_authorization()
    outcome = run_candidate(
        {"receipt": receipt.to_dict(), "request": request.to_dict()},
        "not-a-context",  # type: ignore[arg-type]
    )
    assert outcome.observed_outcome == "REJECT"
    assert outcome.detail == "LEDGER_BAD_TYPE"


# ---------------------------------------------------------------------------
# Determinism + design-record controls
# ---------------------------------------------------------------------------


def test_determinism_identical_inputs_identical_verdicts() -> None:
    for _ in range(3):
        receipt, request, store, ledger = _fresh_authorization()
        first = authorize(receipt, request, store, ledger)
        assert first.decision == "ALLOW"
        receipt2, request2, store2, ledger2 = _fresh_authorization()
        second = authorize(receipt2, request2, store2, ledger2)
        assert first.to_dict() == second.to_dict()
        assert first.verdict_digest == second.verdict_digest


def test_bindings_evaluated_order_is_fixed() -> None:
    receipt, request, store, ledger = _fresh_authorization()
    verdict = authorize(receipt, request, store, ledger)
    assert verdict.bindings_evaluated[0] == "shape"
    assert verdict.bindings_evaluated[-1] == "consume_once_nonce"
    assert "hmac_receipt_integrity" in verdict.bindings_evaluated
    assert "proposal_lineage_binding" in verdict.bindings_evaluated


def test_describe_mechanism_and_identity() -> None:
    record = describe_mechanism()
    assert record["candidate_id"] == CANDIDATE_ID == cand.CANDIDATE_ID
    assert record["candidate_version"] == CANDIDATE_VERSION
    assert record["blueprint_arm"] == "B4"
    hooks = record["ablation_hooks"]
    assert set(hooks) == {"ablation_no_lineage_binding", "ablation_no_nonce"}
    axes = record["mechanism_axes"]
    assert "proposal_lineage_binding" in axes and "consume_once_nonce" in axes
    assert "RECEIPT_SIGNATURE_INVALID" in record["determined_deny_reason_codes"]
    assert "NONCE_REPLAYED" in record["determined_deny_reason_codes"]
    assert "LINEAGE_SPLICED" in record["determined_deny_reason_codes"]
    import json

    json.dumps(record)  # machine-readable: JSON-serializable
    json.dumps(authorize(*_fresh_authorization()).to_dict())


def test_receipt_json_round_trip_preserves_commitments() -> None:
    receipt, request, store, ledger = _fresh_authorization()
    restored = Receipt.from_dict(receipt.to_dict())
    assert restored == receipt
    assert restored.signed_claims == receipt.signed_claims
    verdict = authorize(restored, request, store, ledger)
    assert verdict.decision == "ALLOW"
