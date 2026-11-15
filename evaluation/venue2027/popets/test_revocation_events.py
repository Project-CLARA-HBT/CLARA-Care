"""Tests for POPETS-X02_revocation_events (post-revocation security semantics).

Positive controls (must pass):
- Pre-revocation dispatch under active consent with a consented purpose and
  verifiable lineage is ALLOW.
- At and after the revocation instant (``time >= t_r``) future disclosure of the
  revoked scope is DENY with DENY_POST_REVOCATION.
- Stored-data deletion is flagged SEPARATELY (``stored_data == "deleted"``) and is
  orthogonal to the disclosure verdict: an ALLOW on an unaffected purpose at the
  same instant is not marked deleted.
- A purpose-wide revocation ("*") covers every purpose of the principal.
- A replayed payload bound to a superseded consent epoch is DENY_EPOCH_STALE.
- The explicit RevocationSemantics states every promise and every non-promise,
  including that already-delivered bytes are OUT_OF_SCOPE_PAST and model
  memorization is NOT_GUARANTEED.
- JSON round-trip of every typed object; determinism (no hidden clock/randomness).

Adversarial controls (must be refused / honest, never fabricated):
- Already-delivered bytes are NOT claimed deleted: the verdict never asserts
  retroactive erasure; ``already_delivered_effect == OUT_OF_SCOPE_PAST`` and the
  semantics refuse ``retroactive_erasure_of_delivered_bytes``.
- Model memorization is INDETERMINATE-with-respect-to-guarantee, i.e. reported as
  ``memorization_guarantee == "NOT_GUARANTEED"`` — never converted into a DENY that
  would masquerade as an erasure guarantee.
- An unknown purpose string is refused INDETERMINATE (PURPOSE_UNKNOWN), not
  silently treated as unconsented-DENY and never as ALLOW.
- A clock before the grant instant is refused INDETERMINATE (TIME_BEFORE_GRANT).
- Missing/unlabelled lineage node fails closed INDETERMINATE
  (LINEAGE_INDETERMINATE, POPETS-CASE-07) — never a silent safe rejection.
- Malformed item / principal / time raise ValueError with stable reason codes.
- INDETERMINATE is first-class: it is never coerced to DENY or ALLOW by the module.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from evaluation.venue2027.popets.revocation_model import (
    ALLOWED_VERDICTS,
    OUT_OF_SCOPE_PAST,
    REASON_CODE_UNKNOWN_PURPOSE,
    REVOCATION_MODEL_VERSION,
    ConsentLedgerView,
    DispatchItem,
    RevocationDecision,
    RevocationSemantics,
    allowed,
    decide,
    effective_revocation_time,
    revocation_semantics,
    stored_data_effect,
)

GRANTED_AT = 10
REVOKED_AT = 100

LEDGER = ConsentLedgerView(
    grants={
        "subj-1": {
            "granted_at": GRANTED_AT,
            "purposes": ["clinical", "analytics"],
            "consent_epoch": 3,
            "lineage_labels": {
                "vitals_2026_01": "vitals",
                "med_list_2026_02": "medications",
                "summary_cache_1": "vitals",
                "retry_payload_1": "vitals",
                "admin_note_2026_01": "administrative",
            },
        },
    },
    revocations=(),
)

LEDGER_REVOKED = ConsentLedgerView(
    grants=dict(LEDGER.grants),
    revocations=({"principal": "subj-1", "purpose": "analytics", "revoked_at": REVOKED_AT},),
)

LEDGER_REVOKED_SUBJECT_WIDE = ConsentLedgerView(
    grants=dict(LEDGER.grants),
    revocations=({"principal": "subj-1", "purpose": "*", "revoked_at": REVOKED_AT},),
)


def _item(
    item_id: str = "d1",
    lineage: tuple[str, ...] = ("vitals_2026_01",),
    epoch: int | None = 3,
    already_delivered: bool = False,
    stored_copy: bool = True,
) -> DispatchItem:
    return DispatchItem(
        item_id=item_id,
        lineage=frozenset(lineage),
        item_epoch=epoch,
        already_delivered=already_delivered,
        stored_copy=stored_copy,
    )


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_pre_revocation_authorized_dispatch_is_allowed() -> None:
    decision = decide(_item(), "subj-1", "clinical", GRANTED_AT + 5, LEDGER)
    assert decision.decision == "ALLOW"
    assert decision.reason_code == "ALLOWED_ACTIVE_CONSENT"
    assert allowed(_item(), "subj-1", "clinical", GRANTED_AT + 5, LEDGER) == "ALLOW"
    # Consent active: no deletion obligation, no delivered-bytes caveat.
    assert decision.stored_data == "not_applicable"
    assert decision.already_delivered_effect is None
    assert decision.memorization_guarantee is None


@pytest.mark.parametrize("offset", [0, 1, 50])
def test_at_and_after_revocation_future_disclosure_denied(offset: int) -> None:
    time = REVOKED_AT + offset
    decision = decide(_item(), "subj-1", "analytics", time, LEDGER_REVOKED)
    assert decision.decision == "DENY"
    assert decision.reason_code == "DENY_POST_REVOCATION"
    assert decision.stored_data == "deleted"


def test_revocation_boundary_is_inclusive_at_exact_t_r() -> None:
    assert allowed(_item(), "subj-1", "analytics", REVOKED_AT, LEDGER_REVOKED) == "DENY"
    assert allowed(_item(), "subj-1", "analytics", REVOKED_AT - 1, LEDGER_REVOKED) == "ALLOW"


def test_transitive_lineage_after_revocation_denied() -> None:
    item = _item(
        item_id="d3-post-revocation-transitive",
        lineage=("summary_cache_1", "retry_payload_1", "vitals_2026_01"),
    )
    decision = decide(item, "subj-1", "analytics", REVOKED_AT + 10, LEDGER_REVOKED)
    assert decision.decision == "DENY"
    assert decision.reason_code == "DENY_POST_REVOCATION"


def test_stored_data_deletion_flagged_separately_from_verdict() -> None:
    # Same instant, same revocation: the revoked purpose is denied AND its stored
    # copy is deleted; the unaffected purpose is allowed AND its stored copy is
    # untouched. The verdict never conflates the two surfaces.
    denied = decide(_item(), "subj-1", "analytics", REVOKED_AT + 1, LEDGER_REVOKED)
    unaffected = decide(_item(), "subj-1", "clinical", REVOKED_AT + 1, LEDGER_REVOKED)
    assert (denied.decision, denied.stored_data) == ("DENY", "deleted")
    assert (unaffected.decision, unaffected.stored_data) == ("ALLOW", "not_applicable")
    # The orthogonal classifier agrees with the flag.
    assert stored_data_effect(LEDGER_REVOKED, "subj-1", "analytics", REVOKED_AT + 1) == "deleted"
    assert stored_data_effect(LEDGER_REVOKED, "subj-1", "clinical", REVOKED_AT + 1) == (
        "not_applicable"
    )
    # Before the revocation instant the platform cannot promise downstream retention.
    assert stored_data_effect(LEDGER_REVOKED, "subj-1", "analytics", REVOKED_AT - 1) == (
        "retained_unknown"
    )


def test_purpose_wildcard_revocation_covers_all_purposes() -> None:
    assert effective_revocation_time(LEDGER_REVOKED_SUBJECT_WIDE, "subj-1", "clinical") == (
        REVOKED_AT
    )
    assert allowed(_item(), "subj-1", "clinical", REVOKED_AT + 1, LEDGER_REVOKED_SUBJECT_WIDE) == (
        "DENY"
    )


def test_replayed_payload_with_stale_epoch_denied() -> None:
    item = _item(item_id="replay", epoch=1)
    decision = decide(item, "subj-1", "clinical", GRANTED_AT + 5, LEDGER)
    assert decision.decision == "DENY"
    assert decision.reason_code == "DENY_EPOCH_STALE"


def test_purpose_not_consented_is_determined_deny() -> None:
    # "billing" is a known purpose vocabulary token (some ledger row references it)
    # but subj-1 never consented to it -> determined purpose-scope DENY.
    ledger_with_billing = ConsentLedgerView(
        grants=dict(LEDGER.grants),
        revocations=({"principal": "other-subj", "purpose": "billing", "revoked_at": 1},),
    )
    decision = decide(_item(), "subj-1", "billing", GRANTED_AT + 5, ledger_with_billing)
    assert decision.decision == "DENY"
    assert decision.reason_code == "PURPOSE_NOT_CONSENTED"


def test_no_grant_at_all_is_determined_deny() -> None:
    decision = decide(_item(), "subj-unknown", "clinical", GRANTED_AT + 5, LEDGER)
    assert decision.decision == "DENY"
    assert decision.reason_code == "GRANT_UNKNOWN"


def test_explicit_semantics_states_promises_and_non_promises() -> None:
    semantics: RevocationSemantics = revocation_semantics()
    assert semantics.version == "1.0.0"
    # Promised: future disclosure prevention, purpose boundary, replay prevention,
    # stored-data deletion, fail-closed indeterminate.
    assert semantics.future_disclosure_prevented is True
    assert semantics.purpose_boundary_enforced is True
    assert semantics.retry_replay_prevented is True
    assert semantics.deletion_of_stored_data_promised is True
    assert semantics.indeterminate_fail_closed is True
    assert len(semantics.guarantees) >= 4
    # Explicit non-promises: no retroactive erasure, no memorization erasure.
    assert semantics.retroactive_erasure_of_delivered_bytes is False
    assert semantics.model_memorization_erasure is False
    assert semantics.model_memorization_guarantee == "NOT_GUARANTEED"
    assert any("OUT_OF_SCOPE_PAST" in n for n in semantics.non_guarantees)
    assert any("memorization" in n.lower() for n in semantics.non_guarantees)
    blob = json.dumps(semantics.to_dict())
    assert "retroactive" in blob and "NOT_GUARANTEED" in blob


def test_json_round_trip_of_typed_objects() -> None:
    item = _item(item_id="d1", lineage=("vitals_2026_01", "summary_cache_1"))
    assert DispatchItem.from_mapping(json.loads(json.dumps(item.to_dict()))) == item
    ledger = ConsentLedgerView.from_mapping(json.loads(json.dumps(LEDGER_REVOKED.to_dict())))
    assert ledger == LEDGER_REVOKED
    decision = decide(item, "subj-1", "clinical", GRANTED_AT + 5, ledger)
    payload = json.loads(json.dumps(decision.to_dict()))
    field_names = {f.name for f in dataclasses.fields(RevocationDecision)}
    assert set(payload) - field_names == {"model_version"}
    revived = RevocationDecision(**{k: v for k, v in payload.items() if k in field_names})
    assert revived == decision
    assert payload["model_version"] == REVOCATION_MODEL_VERSION
    assert revived.decision in ALLOWED_VERDICTS
    assert decision.semantics_version == revocation_semantics().version
    assert REVOCATION_MODEL_VERSION == "1.0.0"


def test_deterministic_no_hidden_clock_or_randomness() -> None:
    a = decide(_item(), "subj-1", "clinical", GRANTED_AT + 5, LEDGER)
    b = decide(_item(), "subj-1", "clinical", GRANTED_AT + 5, LEDGER)
    assert a == b
    a_r = decide(_item(), "subj-1", "analytics", REVOKED_AT + 3, LEDGER_REVOKED)
    b_r = decide(_item(), "subj-1", "analytics", REVOKED_AT + 3, LEDGER_REVOKED)
    assert a_r == b_r


def test_item_from_mapping_and_verdict_contract_signature() -> None:
    raw = {"item_id": "d1", "lineage": ["vitals_2026_01"], "item_epoch": 3}
    assert allowed(raw, "subj-1", "clinical", GRANTED_AT + 5, LEDGER) == "ALLOW"
    # Mapping-shaped ledger is accepted too (JSON-serializable inputs).
    assert allowed(raw, "subj-1", "clinical", GRANTED_AT + 5, LEDGER.to_dict()) == "ALLOW"


# ---------------------------------------------------------------------------
# Adversarial controls
# ---------------------------------------------------------------------------


def test_already_delivered_bytes_not_claimed_deleted() -> None:
    # Bytes that left the process boundary before the revocation are OUT_OF_SCOPE_PAST.
    # The platform-side stored copy may be deleted, but the decision NEVER claims
    # the delivered copy was erased: no reason code asserts retroactive erasure and
    # the effect label is the explicit out-of-scope marker.
    item = _item(item_id="d2-delivered", already_delivered=True, stored_copy=True)
    decision = decide(item, "subj-1", "analytics", REVOKED_AT + 10, LEDGER_REVOKED)
    assert decision.decision == "DENY"
    assert decision.already_delivered_effect == OUT_OF_SCOPE_PAST
    assert decision.reason_code != "RETROACTIVE_ERASURE"
    assert "erasure" not in decision.reason_code.lower()
    # Platform copy deletion is still reported — as a SEPARATE field, never as a
    # claim about the delivered bytes.
    assert decision.stored_data == "deleted"
    # Even pre-revocation queries of delivered bytes carry the out-of-scope marker.
    pre = decide(item, "subj-1", "analytics", GRANTED_AT + 5, LEDGER)
    assert pre.decision == "ALLOW"
    assert pre.already_delivered_effect == OUT_OF_SCOPE_PAST
    assert pre.stored_data == "not_applicable"


def test_already_delivered_without_stored_copy_reports_no_deletion() -> None:
    item = _item(item_id="d6", already_delivered=True, stored_copy=False)
    decision = decide(item, "subj-1", "analytics", REVOKED_AT + 10, LEDGER_REVOKED)
    assert decision.decision == "DENY"
    assert decision.already_delivered_effect == OUT_OF_SCOPE_PAST
    # Nothing stored platform-side, so no deletion is claimed at all.
    assert decision.stored_data == "not_applicable"


def test_model_memorization_is_not_guaranteed_never_deny_as_erasure() -> None:
    # A delivered item's model-learned content is reported as NOT_GUARANTEED; the
    # module must not emit a DENY whose meaning is "the model has been made to
    # forget" — memorization is surfaced as an orthogonal, non-actionable limit.
    item = _item(item_id="d7", already_delivered=True)
    decision = decide(item, "subj-1", "analytics", REVOKED_AT + 10, LEDGER_REVOKED)
    assert decision.memorization_guarantee == "NOT_GUARANTEED"
    semantics = revocation_semantics()
    assert semantics.model_memorization_erasure is False
    assert semantics.model_memorization_guarantee == "NOT_GUARANTEED"
    # The DENY here is a *future disclosure* denial (POST_REVOCATION), not an
    # unlearning claim: its reason code names the disclosure gate, not erasure.
    assert decision.reason_code == "DENY_POST_REVOCATION"
    # And even for a still-authorized pre-revocation delivered item the guarantee
    # stays NOT_GUARANTEED — allowance never implies memorization control either.
    pre = decide(item, "subj-1", "analytics", GRANTED_AT + 5, LEDGER)
    assert pre.decision == "ALLOW"
    assert pre.memorization_guarantee == "NOT_GUARANTEED"


def test_unknown_purpose_refused_indeterminate() -> None:
    decision = decide(_item(), "subj-1", " totally-unknown-purpose ", GRANTED_AT + 5, LEDGER)
    assert decision.decision == "INDETERMINATE"
    assert decision.reason_code == REASON_CODE_UNKNOWN_PURPOSE
    assert allowed(_item(), "subj-1", "totally-unknown-purpose", GRANTED_AT + 5, LEDGER) == (
        "INDETERMINATE"
    )
    # Blank purpose is an outright refusal with the same stable code.
    with pytest.raises(ValueError, match=REASON_CODE_UNKNOWN_PURPOSE):
        allowed(_item(), "subj-1", "", GRANTED_AT + 5, LEDGER)


def test_clock_before_grant_refused_indeterminate() -> None:
    decision = decide(_item(), "subj-1", "clinical", GRANTED_AT - 1, LEDGER)
    assert decision.decision == "INDETERMINATE"
    assert decision.reason_code == "TIME_BEFORE_GRANT"
    # Far before the grant: still refused, never DENY- or ALLOW-guessed.
    assert allowed(_item(), "subj-1", "clinical", 0, LEDGER) == "INDETERMINATE"


def test_missing_lineage_edge_fails_closed_indeterminate() -> None:
    # POPETS-CASE-07: a lineage node with no verifiable label is an unknown-ancestry
    # probe; fail closed INDETERMINATE, never a silent safe rejection.
    unlabelled = _item(item_id="d8", lineage=("ghost_artifact",))
    decision = decide(unlabelled, "subj-1", "clinical", GRANTED_AT + 5, LEDGER)
    assert decision.decision == "INDETERMINATE"
    assert decision.reason_code == "LINEAGE_INDETERMINATE"
    # An explicitly None label (present node, unverifiable origin) behaves the same.
    ledger_none_label = ConsentLedgerView(
        grants={
            "subj-1": {
                "granted_at": GRANTED_AT,
                "purposes": ["clinical"],
                "consent_epoch": 3,
                "lineage_labels": {"vitals_2026_01": None},
            }
        },
        revocations=(),
    )
    decision2 = decide(_item(), "subj-1", "clinical", GRANTED_AT + 5, ledger_none_label)
    assert decision2.decision == "INDETERMINATE"
    assert decision2.reason_code == "LINEAGE_INDETERMINATE"


def test_malformed_inputs_raise_stable_reason_codes() -> None:
    with pytest.raises(ValueError, match="ITEM_MALFORMED"):
        allowed(None, "subj-1", "clinical", GRANTED_AT + 5, LEDGER)
    with pytest.raises(ValueError, match="ITEM_MALFORMED"):
        allowed({"lineage": ["vitals_2026_01"]}, "subj-1", "clinical", GRANTED_AT + 5, LEDGER)
    with pytest.raises(ValueError, match="ITEM_MALFORMED"):
        allowed(
            {"item_id": "d1", "lineage": "vitals_2026_01"},
            "subj-1",
            "clinical",
            GRANTED_AT + 5,
            LEDGER,
        )  # noqa: E501
    with pytest.raises(ValueError, match="ITEM_MALFORMED"):
        allowed({"item_id": "d1", "item_epoch": "3"}, "subj-1", "clinical", GRANTED_AT + 5, LEDGER)
    with pytest.raises(ValueError, match="PRINCIPAL_MALFORMED"):
        allowed(_item(), "", "clinical", GRANTED_AT + 5, LEDGER)
    with pytest.raises(ValueError, match="PRINCIPAL_MALFORMED"):
        allowed(_item(), 42, "clinical", GRANTED_AT + 5, LEDGER)
    with pytest.raises(ValueError, match="TIME_MALFORMED"):
        allowed(_item(), "subj-1", "clinical", -1, LEDGER)
    with pytest.raises(ValueError, match="TIME_MALFORMED"):
        allowed(_item(), "subj-1", "clinical", "soon", LEDGER)
    with pytest.raises(ValueError, match="TIME_MALFORMED"):
        allowed(_item(), "subj-1", "clinical", True, LEDGER)


def test_indeterminate_is_first_class_never_coerced() -> None:
    # The module returns INDETERMINATE as its own verdict; nothing in the return
    # path maps it onto DENY/ALLOW, and ALLOWED_VERDICTS exposes exactly the tri
    # vocabulary for downstream callers.
    verdicts = {
        allowed(_item(), "subj-1", "clinical", GRANTED_AT + 5, LEDGER),
        allowed(_item(), "subj-1", "clinical", GRANTED_AT - 1, LEDGER),
        allowed(_item(), "subj-1", "unknown-purpose-x", GRANTED_AT + 5, LEDGER),
        allowed(_item(), "subj-1", "analytics", REVOKED_AT + 1, LEDGER_REVOKED),
    }
    assert verdicts == {"ALLOW", "INDETERMINATE", "DENY"}
    assert set(ALLOWED_VERDICTS) == {"ALLOW", "DENY", "INDETERMINATE"}


def test_future_effective_revocation_not_applied_before_effect() -> None:
    # A revocation recorded in the ledger applies at its revoked_at instant; a query
    # strictly before it is still authorized (backdated grant / future-effective
    # revocation remain distinguishable through the ledger, not the wall clock).
    assert allowed(_item(), "subj-1", "analytics", REVOKED_AT - 1, LEDGER_REVOKED) == "ALLOW"
    assert allowed(_item(), "subj-1", "analytics", REVOKED_AT, LEDGER_REVOKED) == "DENY"


def test_backdated_grant_is_refused_by_ledger_timeline() -> None:
    # A grant whose granted_at sits AFTER the revocation instant: any query in the
    # overlap resolves against the ledger's own ordering — a query before the
    # (backdated) grant instant is refused INDETERMINATE rather than guessed, and a
    # query after the backdated grant still cannot resurrect the revoked scope:
    # the covering revocation keeps the scope denied (a later grant would be a new
    # consent epoch, out of scope for this task).
    ledger_backdated = ConsentLedgerView(
        grants={
            "subj-1": {
                "granted_at": REVOKED_AT + 20,
                "purposes": ["analytics"],
                "consent_epoch": 1,
                "lineage_labels": {"vitals_2026_01": "vitals"},
            }
        },
        revocations=({"principal": "subj-1", "purpose": "analytics", "revoked_at": REVOKED_AT},),
    )
    assert effective_revocation_time(ledger_backdated, "subj-1", "analytics") == REVOKED_AT
    assert allowed(_item(), "subj-1", "analytics", REVOKED_AT + 25, ledger_backdated) == "DENY"
    assert allowed(_item(), "subj-1", "analytics", REVOKED_AT + 5, ledger_backdated) == (
        "INDETERMINATE"
    )
    # The stored copy is deleted from REVOKED_AT onward regardless of grant timing.
    assert stored_data_effect(ledger_backdated, "subj-1", "analytics", REVOKED_AT + 25) == (
        "deleted"
    )


def test_emergency_override_cannot_resurrect_revoked_scope() -> None:
    # An "emergency override" has no representation in the ledger vocabulary: an
    # unknown purpose string stays refused, and a post-revocation dispatch stays
    # DENY even if a caller smuggles override-ish naming into the purpose field.
    assert allowed(_item(), "subj-1", "emergency_override", REVOKED_AT + 1, LEDGER_REVOKED) == (
        "INDETERMINATE"
    )
    assert allowed(_item(), "subj-1", "analytics", REVOKED_AT + 1, LEDGER_REVOKED) == "DENY"
