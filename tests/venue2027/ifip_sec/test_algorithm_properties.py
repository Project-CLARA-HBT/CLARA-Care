"""Deterministic property / metamorphic / mutation suite for IFIP_SEC-unit (P05).

Purpose
-------
Property-oriented tests over the REAL IFIP_SEC components — imported directly,
never reimplemented, stubbed or toyed (execution contract rule 8):

- ``evaluation.venue2027.ifip_sec.candidate`` — the replay-closed B4 candidate
  (:func:`authorize`, :func:`issue_receipt`, :class:`AuthorizationLedger`,
  ablation hooks) behind the consume-once + delegation-lineage semantics.
- ``evaluation.venue2027.ifip_sec.baselines`` — arms B0/B1/B2/B3 and the
  in-process Zanzibar-style consistency arm (B2_INPROCESS_ZANZIBAR).
- ``evaluation.venue2027.ifip_sec.consistency_token_adapter`` — zookie
  snapshot semantics (``check_with_revision``).
- ``evaluation.venue2027.ifip_sec.nonce_store`` — the thread-safe
  :class:`NonceStore` consume-once transition.
- ``evaluation.venue2027.ifip_sec.replay_generator`` — deterministic attack
  families used as a seeded property source.

Test families (blueprint P05 "positive/negative/unknown boundaries,
skew/race scenarios, two-step metamorphic relations and mutation tests"):

1. **Positive / negative / UNKNOWN boundaries** — fresh ADMITs, every
   determined attack DENYs with its stable reason code, and unmodelled
   families fall through to INDETERMINATE (never silently safe).
2. **Replay / delegation race scenarios** — double consumption races under
   real threads (:class:`NonceStore` lock + candidate nonce store), delegate
   and grantor interleavings, replay-after-revocation across policy epochs.
3. **Two-step metamorphic relations** — appending a caveat / lineage hop /
   delegation link never WIDENS authority; consuming a nonce makes a second
   identical request fail; shrinking a delegation chain can never resurrect
   a consumed right.
4. **Mutation checks** — each mechanism removed via the REAL ablation hooks
   admits exactly the attack the full mechanism denies (mechanism-proving
   contrasts); every single-byte claim mutation on a valid receipt either
   breaks the HMAC or is caught by a binding before the nonce step; seeded
   :func:`generate_replays` mutations are always detected as changed
   requests (no-op mutation ban).

All randomness is seeded and folded through deterministic arithmetic (no
``random`` module without a fixed seed, no hidden clock, no network, no
database, no PII — synthetic identifiers only).

Failure semantics
-----------------
Any property violation fails loudly with the offending vector in the assert
message; a component whose behaviour drifts from its declared semantics
(e.g. a replay ADMITted, a tampered caveat verifying) blocks the experiment
per the task's negative-control contract.

Version
-------
``ALGORITHM_PROPERTY_TESTS_VERSION = "1.0.0"``
"""

from __future__ import annotations

import json
import pathlib
import sys
import threading

import pytest

ALGORITHM_PROPERTY_TESTS_VERSION = "1.0.0"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.venue2027._shared.harness import Outcome  # noqa: E402
from evaluation.venue2027._shared.oracle_kernel import OracleError  # noqa: E402
from evaluation.venue2027.ifip_sec import independent_oracle  # noqa: E402
from evaluation.venue2027.ifip_sec.baselines import (  # noqa: E402
    BASELINE_B0,
    BASELINE_B1,
    BASELINE_B2,
    BASELINE_B2_INPROCESS_ZANZIBAR,
    BASELINE_B3,
    CAVEAT_KEYS,
    BaselineContext,
    build_caveat_chain,
    claims_from_case,
    issue_token,
    parity_check,
    run_baseline,
    synthetic_case,
    token_bytes,
)
from evaluation.venue2027.ifip_sec.candidate import (  # noqa: E402
    AuthorizationLedger,
    AuthorizationRequest,
    CandidateContext,
    Receipt,
    ablation_no_lineage_binding,
    ablation_no_nonce,
    authorize,
    issue_receipt,
    run_candidate,
    verify_receipt_signature,
)
from evaluation.venue2027.ifip_sec.consistency_token_adapter import (  # noqa: E402
    RC_RELATION_ABSENT,
    RC_RELATION_PRESENT,
    RC_RELATION_REVOKED,
    RC_TOKEN_SIGNATURE_INVALID,
    RC_TOKEN_UNPARSEABLE,
    ZanzibarStore,
    check_with_revision,
    zookie_bytes,
)
from evaluation.venue2027.ifip_sec.nonce_store import (  # noqa: E402
    CONSUMED,
    EXPIRED,
    REPLAY_DETECTED,
    InMemoryNonceBackend,
    NonceStore,
)
from evaluation.venue2027.ifip_sec.replay_generator import (  # noqa: E402
    ATTACK_FAMILIES,
    EXPECTED_VERDICTS,
    MUTATED_FIELD,
    ReplayAttack,
    generate_replays,
    legitimate_control,
)

#: Injected HMAC key (synthetic test material, >= 16 bytes, not a secret).
KEY = b"ifip-sec-algorithm-properties-key-0123456789abcdef"
#: Frozen verification clock — no hidden time reads anywhere in this suite.
NOW = 1_700_000_000
#: Fixed far-future expiry shared by every live fixture.
EXPIRY = 4_102_444_800
#: Deterministic seeds for the property generators (all randomness seeded).
SEED_A = 20270101
SEED_B = 20270202
PROPERTY_ATTACK_COUNT = 16


# ---------------------------------------------------------------------------
# Fixture builders over the REAL candidate components.
# ---------------------------------------------------------------------------


def _ledger(**overrides: object) -> AuthorizationLedger:
    return AuthorizationLedger(
        KEY,
        now_epoch_seconds=NOW,
        live_epochs=overrides.get("live_epochs") or {},
    )


def _delegated_receipt(
    ledger: AuthorizationLedger,
    *,
    receipt_id: str = "receipt-prop-0001",
    nonce: str = "nonce-prop-0001",
    proposal_lineage: tuple[str, ...] = ("proposal-P1",),
    purpose: str = "self_care",
    consent_epoch: str = "consent-3",
    policy_epoch: str = "epoch-7",
) -> Receipt:
    """Issue + register root -> delegated receipt (deterministic synthetic ids)."""
    root = ledger.issue(
        receipt_id=f"{receipt_id}-root",
        actor_id="attending-physician",
        patient_id="synthetic-patient",
        tenant_id="synthetic-tenant",
        purpose=purpose,
        task_id="task-medication-review",
        consent_epoch=consent_epoch,
        policy_epoch=policy_epoch,
        dispatch_digest="sha256:" + "p" * 64,
        nonce="nonce-prop-root",
        expiry=EXPIRY,
        delegation_chain=("attending-physician",),
        proposal_lineage=proposal_lineage,
    )
    return ledger.delegate(
        root,
        receipt_id=receipt_id,
        delegatee_actor_id="resident-physician",
        nonce=nonce,
        proposal_lineage=proposal_lineage,
    )


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
    nonce: str = "nonce-prop-0001",
    lineage: tuple[str, ...] = ("proposal-P1",),
) -> tuple[Receipt, AuthorizationRequest, set[str], AuthorizationLedger]:
    ledger = _ledger()
    receipt = _delegated_receipt(ledger, nonce=nonce, proposal_lineage=lineage)
    return receipt, _matching_request(receipt), {nonce}, ledger


def _signed_case(**overrides: object) -> dict[str, object]:
    """Deterministic legitimate receipt for the B0/B1/B3 arms."""
    case = synthetic_case(expiry=EXPIRY, **overrides)  # type: ignore[arg-type]
    case["token"] = issue_token(claims_from_case(case), _baseline_ctx())
    return case


def _baseline_ctx(nonce_store: set[str] | None = None) -> BaselineContext:
    return BaselineContext(hmac_key=KEY, nonce_store=nonce_store, now_epoch_seconds=NOW)


def _caveat_case(**overrides: str) -> dict[str, object]:
    """Deterministic legitimate B2 fixture: full caveat set + honest signature."""
    case = synthetic_case(expiry=EXPIRY)
    case["purpose"] = overrides.get("purpose", "self_care")
    caveats: dict[str, str] = {
        "actor": str(case["actor_id"]),
        "purpose": str(case["purpose"]),
        "task": str(case["task_id"]),
        "expiry": str(EXPIRY),
        "nonce": str(case["nonce"]),
        "parent": str(case["parent_ref"]),
    }
    case["caveats"] = caveats
    case["caveat_signature"] = build_caveat_chain(caveats, _baseline_ctx())
    return case


# ---------------------------------------------------------------------------
# 1. Positive / negative / UNKNOWN boundaries.
# ---------------------------------------------------------------------------


class TestDecisionBoundaries:
    def test_positive_fresh_delegated_request_is_allowed_exactly_once(self) -> None:
        """Positive boundary: a fully-bound fresh request under a delegated
        receipt is ALLOWed with the nonce consumed (never an exception)."""
        receipt, request, store, ledger = _fresh_authorization()
        verdict = authorize(receipt, request, store, ledger)
        assert verdict.decision == "ALLOW"
        assert verdict.reason_code == "NONCE_CONSUMED_OK"
        assert verdict.nonce_consumed is True
        assert verdict.fail_closed is False
        assert receipt.nonce not in store

    def test_negative_every_determined_attack_family_denies_with_stable_code(
        self,
    ) -> None:
        """Negative boundary: each determined attack mutates exactly one
        binding and is DENYed with its stable reason code; the nonce store is
        untouched on every DENY (binding failures never consume)."""
        attacks = (
            ("purpose", "PURPOSE_MISMATCH"),
            ("tenant_id", "TENANT_MISMATCH"),
            ("actor_id", "ACTOR_MISMATCH"),
            ("patient_id", "PATIENT_MISMATCH"),
            ("task_id", "TASK_MISMATCH"),
            ("consent_epoch", "CONSENT_EPOCH_MISMATCH"),
            ("policy_epoch", "POLICY_EPOCH_MISMATCH"),
            ("dispatch_digest", "DISPATCH_MISMATCH"),
        )
        for field, expected_reason in attacks:
            receipt, _request, store, ledger = _fresh_authorization()
            base_kwargs = {
                "actor_id": _request.actor_id,
                "tenant_id": _request.tenant_id,
                "patient_id": _request.patient_id,
                "purpose": _request.purpose,
                "task_id": _request.task_id,
                "consent_epoch": _request.consent_epoch,
                "policy_epoch": _request.policy_epoch,
                "dispatch_digest": _request.dispatch_digest,
                "delegation_chain": _request.delegation_chain,
                "proposal_lineage": _request.proposal_lineage,
            }
            base_kwargs[field] = f"evil-{field}"
            hostile = AuthorizationRequest(**base_kwargs)
            verdict = authorize(receipt, hostile, store, ledger)
            assert verdict.decision == "DENY", (field, verdict.to_dict())
            assert verdict.reason_code == expected_reason, (field, verdict.to_dict())
            assert verdict.fail_closed is False, field
            assert receipt.nonce in store, f"{field}: a DENY must never consume the nonce"

    def test_unknown_unregistered_receipt_fails_closed(self) -> None:
        """UNKNOWN boundary: a validly-SIGNED but never-registered receipt is
        DENYed RECEIPT_UNKNOWN (fail closed on unknown state, never ADMIT)."""
        receipt, request, store, ledger = _fresh_authorization()
        unregistered = issue_receipt(
            hmac_key=KEY,
            receipt_id="receipt-prop-unregistered",
            actor_id=receipt.actor_id,
            patient_id=receipt.patient_id,
            tenant_id=receipt.tenant_id,
            purpose=receipt.purpose,
            task_id=receipt.task_id,
            consent_epoch=receipt.consent_epoch,
            policy_epoch=receipt.policy_epoch,
            dispatch_digest=receipt.dispatch_digest,
            nonce="nonce-prop-unregistered",
            expiry=EXPIRY,
        )
        assert verify_receipt_signature(unregistered, KEY) is True
        verdict = authorize(unregistered, _matching_request(unregistered), store, ledger)
        assert verdict.decision == "DENY"
        assert verdict.reason_code == "RECEIPT_UNKNOWN"
        assert receipt.nonce in store

    def test_unknown_oracle_family_is_indeterminate_never_safe(self) -> None:
        """UNKNOWN boundary at the oracle: an unmodelled family is
        INDETERMINATE — an unknown situation can never count as a safe
        rejection or a successful completion."""
        result = independent_oracle.adjudicate_case(
            {"case_id": "prop-unknown-1", "family": "family_nobody_modelled"}
        )
        assert result.outcome == "INDETERMINATE"
        assert result.reason_code == "UNMODELLED_FAMILY"
        with pytest.raises(OracleError) as excinfo:
            independent_oracle.adjudicate_case({"family": "fresh_accept"})
        assert excinfo.value.reason_code == "MISSING_CASE_ID"


# ---------------------------------------------------------------------------
# 2. Replay / delegation race scenarios.
# ---------------------------------------------------------------------------


class TestReplayAndRaceScenarios:
    def test_exact_replay_denied_second_identical_request_fails(self) -> None:
        """Consume-once invariant: the second identical presentation of the
        same receipt fails on the consumed nonce (NONCE_REPLAYED), with the
        first consumption the only ALLOW the pair ever yields."""
        receipt, request, store, ledger = _fresh_authorization()
        first = authorize(receipt, request, store, ledger)
        second = authorize(receipt, request, store, ledger)
        assert first.decision == "ALLOW"
        assert second.decision == "DENY"
        assert second.reason_code == "NONCE_REPLAYED"
        assert second.nonce_consumed is False

    def test_signature_valid_replay_after_policy_epoch_revocation_is_denied(self) -> None:
        """Interleaving: receipt issued under epoch-7, policy rotates to
        epoch-8 between issue and presentation — the replay (still
        signature-valid) is denied by the live-epoch check before the nonce."""
        receipt, request, store, ledger = _fresh_authorization()
        ledger.set_live_epoch("policy", "epoch-8")
        verdict = authorize(receipt, request, store, ledger)
        assert verdict.decision == "DENY"
        assert verdict.reason_code == "POLICY_EPOCH_STALE"
        assert receipt.nonce in store

    def test_interleaved_grantor_delegate_consumption_shares_one_nonce_pool(
        self,
    ) -> None:
        """Delegation race: grantor and delegatee consume from the same
        injected store; each nonce admits at most once and any second
        presentation is NONCE_REPLAYED (no pool separation leak)."""
        ledger = _ledger()
        root = ledger.issue(
            receipt_id="receipt-prop-race-root",
            actor_id="attending-physician",
            patient_id="synthetic-patient",
            tenant_id="synthetic-tenant",
            purpose="self_care",
            task_id="task-medication-review",
            consent_epoch="consent-3",
            policy_epoch="epoch-7",
            dispatch_digest="sha256:" + "r" * 64,
            nonce="nonce-prop-race-root",
            expiry=EXPIRY,
        )
        child = ledger.delegate(
            root,
            receipt_id="receipt-prop-race-child",
            delegatee_actor_id="resident-physician",
            nonce="nonce-prop-race-child",
        )
        shared_store = {"nonce-prop-race-root", "nonce-prop-race-child"}
        root_verdict = authorize(root, _matching_request(root), shared_store, ledger)
        child_verdict = authorize(child, _matching_request(child), shared_store, ledger)
        assert root_verdict.decision == "ALLOW"
        assert child_verdict.decision == "ALLOW"
        assert not shared_store
        assert authorize(root, _matching_request(root), shared_store, ledger).reason_code == (
            "NONCE_REPLAYED"
        )
        assert authorize(child, _matching_request(child), shared_store, ledger).reason_code == (
            "NONCE_REPLAYED"
        )

    def test_concurrent_double_consumption_admits_exactly_one_thread(self) -> None:
        """Race: N threads race the same nonce through the REAL thread-safe
        :class:`NonceStore`; exactly one observe CONSUMED, the rest observe
        REPLAY_DETECTED — the consume-once invariant holds under concurrency.
        """
        store = NonceStore(InMemoryNonceBackend(), sweep_interval=None)
        outcomes: list[str] = []
        lock = threading.Lock()
        barrier = threading.Barrier(8)

        def _race() -> None:
            barrier.wait()
            result = store.consume("nonce-prop-race-0001", EXPIRY, NOW)
            with lock:
                outcomes.append(result.outcome)

        threads = [threading.Thread(target=_race) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert outcomes.count(CONSUMED) == 1, sorted(outcomes)
        assert outcomes.count(REPLAY_DETECTED) == 7, sorted(outcomes)
        assert store.size() == 1

    def test_expired_nonce_never_reshares_even_after_sweep_window_closes(self) -> None:
        """Skew: an expired nonce window fails closed (EXPIRED) in every
        branch — never re-claimed, never re-usable as a fresh grant."""
        store = NonceStore(InMemoryNonceBackend(), sweep_interval=None)
        assert store.consume("nonce-prop-skew-0001", NOW - 10, NOW).outcome == EXPIRED
        assert store.is_claimed("nonce-prop-skew-0001") is False
        assert store.consume("nonce-prop-skew-0001", NOW - 5, NOW).outcome == EXPIRED
        assert store.size() == 0

    def test_consumed_nonce_replayed_after_expiry_is_still_not_admitted(self) -> None:
        """Skew: a nonce consumed inside its window and presented after the
        recorded expiry classifies as EXPIRED (fail closed) — replay is never
        converted into an admission by clock passage."""
        store = NonceStore(InMemoryNonceBackend(), sweep_interval=None)
        assert store.consume("nonce-prop-skew-0002", NOW + 100, NOW).outcome == CONSUMED
        assert store.consume("nonce-prop-skew-0002", NOW + 200, NOW + 1).outcome == (
            REPLAY_DETECTED
        )
        assert store.consume("nonce-prop-skew-0002", NOW + 300, NOW + 101).outcome == EXPIRED


# ---------------------------------------------------------------------------
# 3. Two-step metamorphic relations.
# ---------------------------------------------------------------------------


class TestMetamorphicRelations:
    def test_metamorphic_appending_a_caveat_never_widens_authority(self) -> None:
        """MR-1 (B2 macaroon chain): attenuating with an EXTRA caveat byte
        changes the signature; the honest signature over the ORIGINAL set can
        never verify the GROWN set — appending never widens authority."""
        base = _caveat_case()
        original: dict[str, str] = dict(base["caveats"])  # type: ignore[arg-type]
        signature = str(base["caveat_signature"])
        ctx = _baseline_ctx()
        outcome = run_baseline(
            BASELINE_B2,
            {"caveats": original, "caveat_signature": signature},
            ctx,
        )
        assert outcome.observed_outcome == "ADMIT"
        grown = {**original, "nonce": original["nonce"] + "-attenuated"}
        assert build_caveat_chain(grown, ctx) != signature
        narrowed = run_baseline(
            BASELINE_B2, {"caveats": grown, "caveat_signature": signature}, ctx
        )
        assert narrowed.observed_outcome == "REJECT"
        assert narrowed.detail == "CAVEAT_VERIFICATION_FAILED"

    def test_metamorphic_consuming_a_nonce_makes_second_identical_request_fail(
        self,
    ) -> None:
        """MR-2 (B3 arm + candidate): step 1 consumes the nonce (ADMIT);
        step 2 replays the byte-identical request and must FAIL — for both
        the B3 nonce-store arm and the full candidate pipeline."""
        case = _signed_case()
        store: set[str] = {str(case["nonce"])}
        first = run_baseline(BASELINE_B3, case, _baseline_ctx(store))
        second = run_baseline(BASELINE_B3, case, _baseline_ctx(store))
        assert first.observed_outcome == "ADMIT"
        assert first.detail == "NONCE_CONSUMED_ONCE"
        assert second.observed_outcome == "REJECT"
        assert second.detail == "NONCE_REPLAYED"
        receipt, request, cand_store, ledger = _fresh_authorization()
        assert authorize(receipt, request, cand_store, ledger).decision == "ALLOW"
        assert authorize(receipt, request, cand_store, ledger).reason_code == "NONCE_REPLAYED"

    def test_metamorphic_delegation_never_broadens_scope(self) -> None:
        """MR-3 (candidate delegation): a delegated child binds the SAME
        purpose/tenant/patient/task/epochs/dispatch as the parent and EXTENDS
        the chain — delegation can only attenuate, never widen authority."""
        ledger = _ledger()
        parent = _delegated_receipt(ledger, receipt_id="receipt-prop-mr3-parent")
        child = ledger.delegate(
            parent,
            receipt_id="receipt-prop-mr3-child",
            delegatee_actor_id="nurse-practitioner",
            nonce="nonce-prop-mr3-child",
        )
        assert child.purpose == parent.purpose
        assert child.tenant_id == parent.tenant_id
        assert child.patient_id == parent.patient_id
        assert child.task_id == parent.task_id
        assert child.consent_epoch == parent.consent_epoch
        assert child.policy_epoch == parent.policy_epoch
        assert child.dispatch_digest == parent.dispatch_digest
        assert child.expiry == parent.expiry
        assert child.delegation_chain == parent.delegation_chain + ("nurse-practitioner",)
        assert child.delegation_depth == parent.delegation_depth + 1
        assert child.parent_ref == parent.receipt_id
        # The extended chain is a DIFFERENT commitment: presenting the child's
        # chain under the parent receipt is a chain change, DENYed.
        store = {"nonce-prop-mr3-parent"}
        swapped = AuthorizationRequest(
            actor_id=parent.actor_id,
            tenant_id=parent.tenant_id,
            patient_id=parent.patient_id,
            purpose=parent.purpose,
            task_id=parent.task_id,
            consent_epoch=parent.consent_epoch,
            policy_epoch=parent.policy_epoch,
            dispatch_digest=parent.dispatch_digest,
            delegation_chain=child.delegation_chain,
            proposal_lineage=parent.proposal_lineage,
        )
        verdict = authorize(parent, swapped, store, ledger)
        assert verdict.decision == "DENY"
        assert verdict.reason_code == "DELEGATION_CHAIN_CHANGED"
        assert "nonce-prop-mr3-parent" in store

    def test_metamorphic_lineage_append_never_resurrects_a_denied_receipt(self) -> None:
        """MR-4 (lineage): appending a proposal hop creates a NEW lineage
        commitment; the old signed receipt presented with the grown lineage is
        DENYed LINEAGE_SPLICED — appending never widens what the old receipt
        can do, and shrinking back restores only the original state."""
        receipt, request, store, ledger = _fresh_authorization()
        grown_request = AuthorizationRequest(
            actor_id=request.actor_id,
            tenant_id=request.tenant_id,
            patient_id=request.patient_id,
            purpose=request.purpose,
            task_id=request.task_id,
            consent_epoch=request.consent_epoch,
            policy_epoch=request.policy_epoch,
            dispatch_digest=request.dispatch_digest,
            delegation_chain=request.delegation_chain,
            proposal_lineage=request.proposal_lineage + ("proposal-P2",),
        )
        verdict = authorize(receipt, grown_request, store, ledger)
        assert verdict.decision == "DENY"
        assert verdict.reason_code == "LINEAGE_SPLICED"
        assert receipt.nonce in store
        # The unchanged (original) request still admits: the relation is a
        # pure function of the presented lineage, not of history.
        assert authorize(receipt, request, store, ledger).decision == "ALLOW"

    def test_metamorphic_zookie_snapshot_monotonicity(self) -> None:
        """MR-5 (consistency adapter): for a fixed tuple history, checking at
        an EARLIER revision never grants MORE than at a later revision —
        snapshot reads are monotone in the revision (grant-then-revoke)."""
        store = ZanzibarStore(store_id="prop-store", hmac_key=KEY)
        store.write("doc:prop-1", "viewer", "synthetic-actor")  # rev 1
        revoke_rev = store.delete("doc:prop-1", "viewer", "synthetic-actor")  # rev 2
        assert revoke_rev == 2
        for revision in range(0, store.head_revision + 1):
            token = store.issue_token_at(revision)
            verdict = check_with_revision(
                "synthetic-actor", "doc:prop-1", token, store=store
            )
            assert verdict.revision_evaluated == revision
            if revision == 0:
                # Pre-grant snapshot: the tuple was committed after this read.
                assert verdict.reason_code == RC_RELATION_ABSENT, revision
            elif revision < revoke_rev:
                assert verdict.reason_code == RC_RELATION_PRESENT, revision
            else:
                assert verdict.reason_code == RC_RELATION_REVOKED, revision
        # Monotonicity: no revision below the revoke is more permissive than
        # the head, and no revision admits what a later revision denies.
        fresh = check_with_revision(
            "synthetic-actor", "doc:prop-1", store.issue_token(), store=store
        )
        assert fresh.reason_code == RC_RELATION_REVOKED

    def test_metamorphic_token_append_never_resurrects_a_failed_signature(self) -> None:
        """MR-6 (zookie integrity): appending/mutating bytes to a valid zookie
        never yields a DIFFERENT allowed verdict — the HMAC fails closed
        (TOKEN_SIGNATURE_INVALID), and the failure is identical whether the
        token was tampered before or after a successful check."""
        store = ZanzibarStore(store_id="prop-store", hmac_key=KEY)
        store.write("doc:prop-2", "viewer", "synthetic-actor")
        token = store.issue_token()
        first_check = check_with_revision("synthetic-actor", "doc:prop-2", token, store=store)
        assert first_check.reason_code == RC_RELATION_PRESENT
        # Flip one character INSIDE the base64 payload: still decodable JSON
        # with a different mac (or unparseable base64) — either way fail
        # closed, never a different allowed verdict.
        swap = "A" if token[len(token) // 2] != "A" else "B"
        tampered = token[: len(token) // 2] + swap + token[len(token) // 2 + 1 :]
        verdict = check_with_revision("synthetic-actor", "doc:prop-2", tampered, store=store)
        assert verdict.allowed is False
        assert verdict.reason_code in {RC_TOKEN_UNPARSEABLE, RC_TOKEN_SIGNATURE_INVALID}


# ---------------------------------------------------------------------------
# 4. Mutation checks (mechanism-proving ablations + byte-level tampering).
# ---------------------------------------------------------------------------


class TestMutationChecks:
    def test_mutation_ablation_without_nonce_admits_exact_replay(self) -> None:
        """Mutation check (mechanism identity): removing ONLY the consume-once
        nonce admits the very exact replay the full mechanism DENYs; every
        other binding stays enforced."""
        receipt, request, store, ledger = _fresh_authorization()
        ablated = ablation_no_nonce()
        first = ablated(receipt, request, store, ledger)
        second = ablated(receipt, request, store, ledger)
        assert first.decision == "ALLOW"
        assert second.decision == "ALLOW"  # the mutation (nonce removal) is the bug
        assert store == {receipt.nonce}  # ablated authorizer never consumes
        # The FULL mechanism on a fresh store denies the identical replay.
        receipt2, request2, store2, ledger2 = _fresh_authorization(
            nonce="nonce-prop-0002", lineage=("proposal-P1",)
        )
        assert authorize(receipt2, request2, store2, ledger2).decision == "ALLOW"
        replay = authorize(receipt2, request2, store2, ledger2)
        assert replay.decision == "DENY"
        assert replay.reason_code == "NONCE_REPLAYED"

    def test_mutation_ablation_without_lineage_binding_admits_splice(self) -> None:
        """Mutation check: removing ONLY the proposal-lineage binding admits
        the very splice the full mechanism DENYs; other bindings enforced."""
        receipt, request, store, ledger = _fresh_authorization()
        spliced = AuthorizationRequest(
            actor_id=request.actor_id,
            tenant_id=request.tenant_id,
            patient_id=request.patient_id,
            purpose=request.purpose,
            task_id=request.task_id,
            consent_epoch=request.consent_epoch,
            policy_epoch=request.policy_epoch,
            dispatch_digest=request.dispatch_digest,
            delegation_chain=request.delegation_chain,
            proposal_lineage=("proposal-EVIL",),
        )
        ablated = ablation_no_lineage_binding()
        mutated_verdict = ablated(receipt, spliced, store, ledger)
        assert mutated_verdict.decision == "ALLOW"  # the mutation is the bug
        assert mutated_verdict.reason_code == "LINEAGE_UNBOUND"
        full = authorize(receipt, spliced, store, ledger)
        assert full.decision == "DENY"
        assert full.reason_code == "LINEAGE_SPLICED"

    def test_mutation_single_byte_claim_tampering_breaks_hmac_fail_closed(self) -> None:
        """Mutation check (candidate receipt): any single-field mutation of a
        valid receipt's signed claims breaks the HMAC; the pipeline denies
        with RECEIPT_SIGNATURE_INVALID and never consumes the nonce."""
        receipt, request, store, ledger = _fresh_authorization()
        payload = receipt.to_dict()
        transport = json.loads(json.dumps(payload))
        for field in ("purpose", "tenant_id", "actor_id", "nonce", "consent_epoch"):
            mutated = dict(transport)
            mutated[field] = f"mutated-{field}"
            forged = Receipt.from_dict(mutated)
            assert verify_receipt_signature(forged, KEY) is False, field
            verdict = authorize(forged, request, store, ledger)
            assert verdict.decision == "DENY", field
            assert verdict.reason_code == "RECEIPT_SIGNATURE_INVALID", field
            assert receipt.nonce in store, field

    def test_mutation_transport_commitment_drift_is_caught_by_binding(self) -> None:
        """Mutation check: mutating the UNSIGNED transport copies while keeping
        the honest signature must be caught by the commitment re-derivation
        (DELEGATION_CHAIN_CHANGED / LINEAGE_SPLICED), not silently accepted."""
        receipt, request, store, ledger = _fresh_authorization()
        payload = receipt.to_dict()
        drifted_chain = dict(payload)
        drifted_chain["delegation_chain"] = ["attending-physician", "impostor"]
        forged_chain = Receipt.from_dict(drifted_chain)
        # The MAC covers only signed claims; a forger could keep it valid.
        assert forged_chain.mac == receipt.mac
        verdict = authorize(forged_chain, request, store, ledger)
        assert verdict.decision == "DENY"
        assert verdict.reason_code == "DELEGATION_CHAIN_CHANGED"
        drifted_lineage = dict(payload)
        drifted_lineage["proposal_lineage"] = ["proposal-P1", "proposal-EVIL"]
        forged_lineage = Receipt.from_dict(drifted_lineage)
        assert forged_lineage.mac == receipt.mac
        verdict = authorize(forged_lineage, request, store, ledger)
        assert verdict.decision == "DENY"
        assert verdict.reason_code == "LINEAGE_SPLICED"
        assert receipt.nonce in store

    def test_mutation_b2_caveat_byte_flip_is_never_accepted(self) -> None:
        """Mutation check (B2 macaroon chain): mutating ANY single caveat
        value while presenting the honest signature fails verification —
        byte binding over the whole CAVEAT_KEYS domain."""
        base = _caveat_case()
        original: dict[str, str] = dict(base["caveats"])  # type: ignore[arg-type]
        signature = str(base["caveat_signature"])
        for key in CAVEAT_KEYS:
            mutated = dict(original)
            mutated[key] = str(mutated[key]) + "-x"
            outcome = run_baseline(
                BASELINE_B2, {"caveats": mutated, "caveat_signature": signature}, _baseline_ctx()
            )
            assert outcome.observed_outcome == "REJECT", key
            assert outcome.detail == "CAVEAT_VERIFICATION_FAILED", key

    def test_mutation_seeded_replay_generator_produces_real_attacks(self) -> None:
        """Mutation check (generator contract, seeded): for a fixed seed the
        generator is deterministic, every produced attack differs from its
        original in EXACTLY the family's primary field, and every family is
        represented — the paired legitimate control stays fresh/legitimate."""
        attacks_first = generate_replays(SEED_A, n=PROPERTY_ATTACK_COUNT)
        attacks_second = generate_replays(SEED_A, n=PROPERTY_ATTACK_COUNT)
        assert attacks_first == attacks_second  # deterministic under the seed
        assert len(attacks_first) == PROPERTY_ATTACK_COUNT
        families = {attack.family for attack in attacks_first}
        assert families == set(ATTACK_FAMILIES)
        for attack in attacks_first:
            assert isinstance(attack, ReplayAttack)
            field = MUTATED_FIELD[attack.family]
            assert attack.mutated_field == field
            assert attack.original_request != attack.mutated_request
            assert attack.original_request[field] != attack.mutated_request[field]
            assert attack.expected_oracle_verdict == EXPECTED_VERDICTS[attack.family]
            control = legitimate_control(attack)
            assert control["nonce_state"] == "fresh"
            assert control["replay_flag"] is False
            assert control["purpose"] == control["granted_purpose"]

    def test_mutation_seeded_attacks_are_decision_separated_from_controls(
        self,
    ) -> None:
        """Mutation check (end-to-end, seeded): every generated attack request
        is DENYed by the candidate boundary adapter while its paired
        legitimate control is ADMITted — the mutation is the only difference.
        Two distinct seeds produce distinct attack streams (seed sensitivity).
        """
        for seed in (SEED_A, SEED_B):
            for attack in generate_replays(seed, n=PROPERTY_ATTACK_COUNT):
                ledger = _ledger()
                receipt = _delegated_receipt(
                    ledger,
                    receipt_id=f"receipt-prop-{seed}-{attack.attack_id[:24]}",
                    nonce=f"nonce-prop-{seed}-{attack.attack_id[:24]}",
                    purpose=str(attack.original_request["purpose"]),
                    consent_epoch=str(attack.original_request["consent_epoch"]),
                )
                request = _matching_request(receipt)
                store = {receipt.nonce}
                admitted = run_candidate(
                    {"receipt": receipt.to_dict(), "request": request.to_dict()},
                    CandidateContext(
                        hmac_key=KEY, nonce_store=store, ledger=ledger, now_epoch_seconds=NOW
                    ),
                )
                assert isinstance(admitted, Outcome)
                assert admitted.observed_outcome == "ADMIT", (seed, attack.attack_id)
                if attack.family in ("cross_purpose", "lineage_splice"):
                    # Request-context mutations: present the mutated binding.
                    mutated = AuthorizationRequest(
                        actor_id=request.actor_id,
                        tenant_id=request.tenant_id,
                        patient_id=request.patient_id,
                        purpose=str(attack.mutated_request["purpose"]),
                        task_id=request.task_id,
                        consent_epoch=str(attack.mutated_request["consent_epoch"]),
                        policy_epoch=request.policy_epoch,
                        dispatch_digest=request.dispatch_digest,
                        delegation_chain=request.delegation_chain,
                        proposal_lineage=request.proposal_lineage,
                    )
                    store2 = {receipt.nonce}
                    denied = run_candidate(
                        {"receipt": receipt.to_dict(), "request": mutated.to_dict()},
                        CandidateContext(
                            hmac_key=KEY,
                            nonce_store=store2,
                            ledger=ledger,
                            now_epoch_seconds=NOW,
                        ),
                    )
                    assert denied.observed_outcome == "REJECT", (seed, attack.attack_id)
                    assert denied.detail in {
                        "PURPOSE_MISMATCH",
                        "CONSENT_EPOCH_MISMATCH",
                        "CONSENT_EPOCH_REVOKED",
                    }, (seed, attack.attack_id, denied.detail)
                else:
                    # Nonce-state mutations (delegation_replay / nonce_replay
                    # set nonce_state=consumed[_by_delegate]): the faithful
                    # candidate realization is a second presentation of the
                    # unchanged request after the nonce was consumed — the
                    # consume-once closure must deny it (NONCE_REPLAYED).
                    store2 = {receipt.nonce}
                    first = run_candidate(
                        {"receipt": receipt.to_dict(), "request": request.to_dict()},
                        CandidateContext(
                            hmac_key=KEY,
                            nonce_store=store2,
                            ledger=ledger,
                            now_epoch_seconds=NOW,
                        ),
                    )
                    assert first.observed_outcome == "ADMIT", (seed, attack.attack_id)
                    denied = run_candidate(
                        {"receipt": receipt.to_dict(), "request": request.to_dict()},
                        CandidateContext(
                            hmac_key=KEY,
                            nonce_store=store2,
                            ledger=ledger,
                            now_epoch_seconds=NOW,
                        ),
                    )
                    assert denied.observed_outcome == "REJECT", (seed, attack.attack_id)
                    assert denied.detail == "NONCE_REPLAYED", (seed, attack.attack_id)


# ---------------------------------------------------------------------------
# 5. Determinism + cost-marker properties (RQ3 sanity, no timing claims).
# ---------------------------------------------------------------------------


class TestDeterminismAndCostProperties:
    def test_determinism_identical_inputs_identical_verdicts(self) -> None:
        """Purity property: identical (receipt, request, store, ledger) inputs
        yield identical verdict dicts — verdicts are a pure function of the
        injected state (digests stable, no hidden entropy)."""
        receipt, request, _store, ledger = _fresh_authorization()
        verdicts = [
            authorize(receipt, request, {"nonce-prop-0001"}, ledger).to_dict()
            for _ in range(5)
        ]
        assert all(v == verdicts[0] for v in verdicts)

    def test_token_size_metrics_are_positive_and_stable(self) -> None:
        """RQ3 marker property: token/zookie size metrics are positive ints
        and deterministic for fixed inputs (no timing claims made here)."""
        case = _signed_case()
        size = token_bytes(str(case["token"]))
        assert isinstance(size, int) and size > 0
        assert size == token_bytes(str(case["token"]))
        store = ZanzibarStore(store_id="prop-store", hmac_key=KEY)
        store.write("doc:prop-3", "viewer", "synthetic-actor")
        zookie = store.issue_token()
        zsize = zookie_bytes(zookie)
        assert isinstance(zsize, int) and zsize > 0
        assert zsize == zookie_bytes(store.issue_token())

    def test_zanzibar_verdict_counts_are_real_and_deterministic(self) -> None:
        """Verdict counters (tuples_examined / nodes_visited /
        db_round_trips) are real, positive on a hit, and deterministic for a
        fixed snapshot — never fabricated."""
        store = ZanzibarStore(store_id="prop-store", hmac_key=KEY)
        store.write("doc:prop-4", "viewer", "synthetic-actor")
        store.write("doc:prop-4", "parent", "folder:prop-4")
        token = store.issue_token()
        first = check_with_revision("synthetic-actor", "doc:prop-4", token, store=store)
        second = check_with_revision("synthetic-actor", "doc:prop-4", token, store=store)
        assert first.to_dict() == second.to_dict()
        assert first.allowed is True
        assert first.reason_code == RC_RELATION_PRESENT
        assert first.db_round_trips == first.nodes_visited > 0
        assert first.tuples_examined >= 1
        # Unknown principal: the walk still runs, no relation is present.
        absent = check_with_revision("nobody-prop", "doc:prop-4", token, store=store)
        assert absent.reason_code == RC_RELATION_ABSENT
        assert absent.allowed is False

    def test_baseline_parity_roundtrip_and_cross_arm_nonce_consistency(self) -> None:
        """Cross-arm property: the B2 parity round-trip admits the honest
        construction and rejects every tampered variant; B0 (no state) and
        B1 (stateless) ADMIT the replay their published semantics allow,
        while B3 (consume-once) rejects it — the measured RQ1 separation."""
        caveats = {
            "actor": "synthetic-actor",
            "purpose": "self_care",
            "task": "task-medication-review",
            "expiry": str(EXPIRY),
            "nonce": "nonce-prop-parity",
            "parent": "root",
        }
        parity = parity_check(
            caveats,
            _baseline_ctx(),
            tamper={"variants": [{**caveats, "purpose": "evil"}]},
        )
        assert parity.observed_outcome == "ADMIT"
        assert parity.detail == "PARITY_OK"
        case = _signed_case()
        assert run_baseline(BASELINE_B0, case, _baseline_ctx()).observed_outcome == "ADMIT"
        assert run_baseline(BASELINE_B0, case, _baseline_ctx()).observed_outcome == "ADMIT"
        assert run_baseline(BASELINE_B1, case, _baseline_ctx()).observed_outcome == "ADMIT"
        store: set[str] = {str(case["nonce"])}
        assert run_baseline(BASELINE_B3, case, _baseline_ctx(store)).observed_outcome == "ADMIT"
        assert run_baseline(BASELINE_B3, case, _baseline_ctx(store)).observed_outcome == "REJECT"

    def test_zanzibar_fresh_vs_stale_boundary_via_run_baseline(self) -> None:
        """Consistency boundary (RQ1 comparator): a FRESH zookie rejects the
        post-revocation replay (RELATION_REVOKED); a pre-revocation token
        faithfully ADMITs the replay inside the bounded-staleness window —
        asserted, never hidden."""
        store = ZanzibarStore(store_id="prop-boundary", hmac_key=KEY)
        store.write("doc:prop-5", "viewer", "synthetic-actor")
        stale_token = store.issue_token_at(1)
        store.delete("doc:prop-5", "viewer", "synthetic-actor")
        fresh_case = {
            "principal": "synthetic-actor",
            "resource": "doc:prop-5",
            "zookie": store.issue_token(),
            "zanzibar_store": store,
        }
        stale_case = {
            "principal": "synthetic-actor",
            "resource": "doc:prop-5",
            "zookie": stale_token,
            "zanzibar_store": store,
        }
        fresh = run_baseline(BASELINE_B2_INPROCESS_ZANZIBAR, fresh_case, _baseline_ctx())
        stale = run_baseline(BASELINE_B2_INPROCESS_ZANZIBAR, stale_case, _baseline_ctx())
        assert fresh.observed_outcome == "REJECT"
        assert fresh.detail == RC_RELATION_REVOKED
        assert stale.observed_outcome == "ADMIT"  # honest staleness gap (RQ1)
        assert stale.detail == RC_RELATION_PRESENT
