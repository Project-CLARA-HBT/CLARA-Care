"""Tests for the PST venue2027 frozen forensic query set (PST-X02_forensic_queries).

Positive vectors cover the freeze discipline (stable ids, deterministic
canonical hash equal to the committed freeze constant) and the fail-closed
``answerable`` classification over full, minimized (PST-CASE-05 over-redaction
shape), hash-only, no-log (PST-CASE-09), missing-key-custody (PST-CASE-07/12)
and missing-epoch-attestation audit views. Adversarial vectors prove that
``assert_frozen_query_set`` refuses a drifted denominator (addition, removal,
rewording, reordering of any query) with the stable ``QUERY_SET_DRIFT`` reason
code, that unknown query ids and malformed views are refused with stable
reason codes, and that INDETERMINATE outcomes are never coerced to
ANSWERABLE. All fixtures are synthetic and PHI-free.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from evaluation.venue2027._shared.dataset_kernel import PHI_FIELD_MARKERS
from evaluation.venue2027.pst import forensic_queries as fq

_QUERY_ID_PATTERN = re.compile(r"^FQ-(AUTH|PROV|ELIG)-\d{2}$")


def _full_view(event_id: str = "evt-0001") -> fq.AuditView:
    """Complete retention view: every receipt field survives, proofs active."""

    return fq.AuditView(
        event_id=event_id,
        retained_fields={
            "commitment_digest": "sha256:aa",
            "purpose_tag": "self_care",
            "consent_epoch": "consent-e7",
            "policy_epoch": "policy-2026-r4",
            "witness_id": "witness-91",
            "retention_mode": "full",
        },
        retention_mode="full",
        epoch_active={"consent_epoch": "consent-e7", "policy_epoch": "policy-2026-r4"},
        key_custody_attested=True,
    )


def _minimized_view(event_id: str = "evt-0001") -> fq.AuditView:
    """Over-redacted receipt (PST-CASE-05): witness_id + retention_mode dropped."""

    return dataclasses.replace(
        _full_view(event_id),
        retained_fields={
            "commitment_digest": "sha256:aa",
            "purpose_tag": "self_care",
            "consent_epoch": "consent-e7",
            "policy_epoch": "policy-2026-r4",
        },
        retention_mode="selective",
    )


def _hash_only_view(event_id: str = "evt-0001") -> fq.AuditView:
    """Hash-only comparator (B1): digests alone survive."""

    return fq.AuditView(
        event_id=event_id,
        retained_fields={"commitment_digest": "sha256:aa"},
        retention_mode="hash_only",
        epoch_active={},
        key_custody_attested=False,
    )


def _no_log_view(event_id: str = "evt-0001") -> fq.AuditView:
    """No-log comparator (PST-CASE-09): nothing retained."""

    return fq.AuditView(event_id=event_id, retained_fields={}, retention_mode="full")


def _no_key_custody_view(event_id: str = "evt-0001") -> fq.AuditView:
    """Missing key-deletion attestation (PST-CASE-07/12 shape).

    All receipt fields are retained so the only load-bearing missing proof is
    key custody: full retention + attested custody would make the content
    recoverable, so without the attestation neither success nor loss is
    provable (INDETERMINATE, never coerced).
    """

    return dataclasses.replace(_full_view(event_id), key_custody_attested=False)


def _missing_policy_epoch_view(event_id: str = "evt-0001") -> fq.AuditView:
    """Receipt present but policy-epoch attestation absent from the view."""

    return dataclasses.replace(
        _full_view(event_id),
        epoch_active={"consent_epoch": "consent-e7"},
    )


# ---------------------------------------------------------------------------
# Positive controls — freeze discipline
# ---------------------------------------------------------------------------


def test_set_is_nonempty_and_ids_are_stable() -> None:
    assert len(fq.FORENSIC_QUERIES) >= 8
    assert len(fq.QUERY_IDS) == len(set(fq.QUERY_IDS))
    for query in fq.FORENSIC_QUERIES:
        assert _QUERY_ID_PATTERN.match(query.query_id), query.query_id
        assert query.statement.strip()
        assert query.oracle_pointer.startswith(
            "research/venue2027/pst/protocols/forensic_query_catalog.yaml#"
        )


def test_query_ids_unique_and_lookup_consistent() -> None:
    assert len(fq.QUERY_BY_ID) == len(fq.FORENSIC_QUERIES)
    for query in fq.FORENSIC_QUERIES:
        assert fq.QUERY_BY_ID[query.query_id] is query
    assert fq.QUERY_IDS == tuple(fq.QUERY_BY_ID)


def test_query_classes_and_witness_fields_are_registered() -> None:
    covered_classes = {q.query_class for q in fq.FORENSIC_QUERIES}
    assert covered_classes == set(fq.QUERY_CLASSES)
    for query in fq.FORENSIC_QUERIES:
        assert query.query_class in fq.QUERY_CLASSES
        assert query.witnesses_needed
        assert all(f in fq.RECEIPT_FIELDS for f in query.witnesses_needed)
        assert query.oracle_answer in ("ANSWERABLE", "NOT_ANSWERABLE", "INDETERMINATE")


def test_set_hash_is_deterministic() -> None:
    first = fq.queries_sha256()
    second = fq.queries_sha256(fq.FORENSIC_QUERIES)
    third = fq.queries_sha256(tuple(reversed(fq.FORENSIC_QUERIES)))
    assert first == second == fq.frozen_query_set_sha256()
    assert first == fq.FROZEN_QUERY_SET_SHA256
    assert len(first) == 64
    # Canonical form is order-sensitive: reordering is detectable drift.
    assert first != third
    # Serialization itself is deterministic (byte-identical across calls).
    assert fq.serialize_query_set() == fq.serialize_query_set()


def test_frozen_set_passes_its_own_freeze_gate() -> None:
    fq.assert_frozen_query_set(fq.FORENSIC_QUERIES)
    fq.assert_frozen_query_set(list(fq.FORENSIC_QUERIES))


def test_module_constant_matches_recomputed_hash() -> None:
    recomputed = fq.queries_sha256(
        tuple(fq.ForensicQuery(**q.to_dict()) for q in fq.FORENSIC_QUERIES)
    )
    assert recomputed == fq.FROZEN_QUERY_SET_SHA256


def test_queries_are_json_serializable_and_phi_free() -> None:
    for query in fq.FORENSIC_QUERIES:
        encoded = json.dumps(query.to_dict(), sort_keys=True)
        assert isinstance(encoded, str)
        blob = encoded.lower()
        for marker in PHI_FIELD_MARKERS:
            assert marker not in blob, (query.query_id, marker)
    for field in fq.RECEIPT_FIELDS:
        assert not any(marker in field for marker in PHI_FIELD_MARKERS)


def test_answerable_on_full_view_matches_class_expectations() -> None:
    view = _full_view()
    for query in fq.FORENSIC_QUERIES:
        assert fq.answerable(query, view) == "ANSWERABLE", query.query_id
        assert fq.answerable_by_id(query.query_id, view) == "ANSWERABLE"


def test_answerable_classifies_full_vs_minimized_audit() -> None:
    full = _full_view()
    minimized = _minimized_view()
    for query in fq.FORENSIC_QUERIES:
        if set(query.witnesses_needed) <= set(minimized.retained_fields):
            assert fq.answerable(query, minimized) == "ANSWERABLE", query.query_id
        else:
            # Over-redaction (PST-CASE-05) is a reconstruction loss, not a pass.
            assert fq.answerable(query, minimized) == "NOT_ANSWERABLE", query.query_id
        assert fq.answerable(query, full) == "ANSWERABLE"


def test_minimized_view_drops_exactly_the_tail_witnesses() -> None:
    # The PST-CASE-05 adversarial shape: the committer withholds the tail of
    # the mandatory field set, so tail-dependent queries become a measured
    # utility loss while commitment + epoch proofs persist.
    dropped = set(fq.RECEIPT_FIELDS[-2:])
    view = _minimized_view()
    affected = [q.query_id for q in fq.FORENSIC_QUERIES if set(q.witnesses_needed) & dropped]
    assert affected, "freeze breach: no query exercises the over-redaction surface"
    for query in fq.FORENSIC_QUERIES:
        if query.query_id in affected:
            assert fq.answerable(query, view) == "NOT_ANSWERABLE", query.query_id


def test_hash_only_and_no_log_views_are_reconstruction_losses() -> None:
    hash_only = _hash_only_view()
    no_log = _no_log_view()
    commitments = [
        q.query_id for q in fq.FORENSIC_QUERIES if "commitment_digest" in q.witnesses_needed
    ]
    for query in fq.FORENSIC_QUERIES:
        got_hash = fq.answerable(query, hash_only)
        got_none = fq.answerable(query, no_log)
        assert got_none == "NOT_ANSWERABLE", query.query_id
        if query.witnesses_needed == ("commitment_digest",):
            # A digest survives hash-only retention and needs no content key.
            assert got_hash == "ANSWERABLE", query.query_id
        else:
            assert got_hash == "NOT_ANSWERABLE", query.query_id
    assert commitments


def test_missing_key_custody_yields_ineterminate_not_success() -> None:
    view = _no_key_custody_view()
    verdicts = {q.query_id: fq.answerable(q, view) for q in fq.FORENSIC_QUERIES}
    # PST-CASE-07/12: provenance queries needing the committed CONTENT (any
    # witness beyond the bare commitment digest) must be INDETERMINATE —
    # neither reconstruction success nor loss is provable. A bare-digest
    # existence query (FQ-PROV-01) stays ANSWERABLE: proving that a
    # commitment exists needs no content key.
    content_queries = [
        q.query_id
        for q in fq.FORENSIC_QUERIES
        if q.query_class == "provenance"
        and "commitment_digest" in q.witnesses_needed
        and any(f != "commitment_digest" for f in q.witnesses_needed)
    ]
    assert content_queries
    for query_id in content_queries:
        assert verdicts[query_id] == "INDETERMINATE", query_id
    # Existence-of-commitment is decidable from the digest alone (ReceiptMin:
    # commitment proofs survive minimization; content recovery may not).
    assert verdicts["FQ-PROV-01"] == "ANSWERABLE"
    assert "INDETERMINATE" in verdicts.values()


def test_missing_epoch_attestation_yields_ineterminate_not_answerable() -> None:
    view = _missing_policy_epoch_view()
    verdicts = {q.query_id: fq.answerable(q, view) for q in fq.FORENSIC_QUERIES}
    for query in fq.FORENSIC_QUERIES:
        if query.query_class in ("authorization", "commit_eligibility"):
            assert verdicts[query.query_id] == "INDETERMINATE", query.query_id
        else:
            assert verdicts[query.query_id] == "ANSWERABLE", query.query_id


def test_answerability_is_pure_and_order_independent() -> None:
    view = _full_view()
    baseline = [fq.answerable(q, view) for q in fq.FORENSIC_QUERIES]
    shuffled = list(fq.FORENSIC_QUERIES)
    shuffled.reverse()
    assert [fq.answerable(q, view) for q in shuffled] == baseline[::-1]
    # No hidden state: a second pass is identical.
    assert [fq.answerable(q, view) for q in fq.FORENSIC_QUERIES] == baseline


# ---------------------------------------------------------------------------
# Adversarial controls — drift refusal and fail-closed semantics
# ---------------------------------------------------------------------------


def _drifted_with_extra_query() -> tuple[fq.ForensicQuery, ...]:
    extra = fq.ForensicQuery(
        query_id="FQ-AUTH-05",
        query_class="authorization",
        statement="Who accessed record X at time T? (post-hoc addition)",
        witnesses_needed=("purpose_tag",),
        oracle_answer="ANSWERABLE",
        oracle_pointer=("research/venue2027/pst/protocols/forensic_query_catalog.yaml#FQ-AUTH-05"),
    )
    return tuple(fq.FORENSIC_QUERIES) + (extra,)


def test_assert_frozen_query_set_refuses_added_query() -> None:
    drifted = _drifted_with_extra_query()
    assert fq.queries_sha256(drifted) != fq.FROZEN_QUERY_SET_SHA256
    with pytest.raises(fq.ForensicQueryError) as exc:
        fq.assert_frozen_query_set(drifted)
    assert exc.value.reason_code == "QUERY_SET_DRIFT"


def test_assert_frozen_query_set_refuses_removed_query() -> None:
    drifted = tuple(q for q in fq.FORENSIC_QUERIES if q.query_id != "FQ-PROV-04")
    with pytest.raises(fq.ForensicQueryError) as exc:
        fq.assert_frozen_query_set(drifted)
    assert exc.value.reason_code == "QUERY_SET_DRIFT"


def test_assert_frozen_query_set_refuses_reworded_query() -> None:
    substituted = fq.ForensicQuery(
        query_id="FQ-AUTH-01",
        query_class="authorization",
        statement="Which principal authorized the action committed under event E? (reworded)",
        witnesses_needed=("purpose_tag", "witness_id"),
        oracle_answer="ANSWERABLE",
        oracle_pointer=("research/venue2027/pst/protocols/forensic_query_catalog.yaml#FQ-AUTH-01"),
    )
    drifted = tuple(substituted if q.query_id == "FQ-AUTH-01" else q for q in fq.FORENSIC_QUERIES)
    with pytest.raises(fq.ForensicQueryError) as exc:
        fq.assert_frozen_query_set(drifted)
    assert exc.value.reason_code == "QUERY_SET_DRIFT"


def test_assert_frozen_query_set_refuses_reordered_set() -> None:
    drifted = tuple(reversed(fq.FORENSIC_QUERIES))
    with pytest.raises(fq.ForensicQueryError) as exc:
        fq.assert_frozen_query_set(drifted)
    assert exc.value.reason_code == "QUERY_SET_DRIFT"


def test_assert_frozen_query_set_refuses_witness_set_change() -> None:
    loosened = dataclasses.replace(
        fq.QUERY_BY_ID["FQ-ELIG-04"], witnesses_needed=("commitment_digest",)
    )
    drifted = tuple(loosened if q.query_id == "FQ-ELIG-04" else q for q in fq.FORENSIC_QUERIES)
    with pytest.raises(fq.ForensicQueryError) as exc:
        fq.assert_frozen_query_set(drifted)
    assert exc.value.reason_code == "QUERY_SET_DRIFT"


def test_assert_frozen_query_set_error_is_machine_checkable() -> None:
    with pytest.raises(fq.ForensicQueryError) as exc:
        fq.assert_frozen_query_set(_drifted_with_extra_query())
    assert exc.value.reason_code == "QUERY_SET_DRIFT"
    assert fq.FROZEN_QUERY_SET_SHA256 in str(exc.value)


def test_unknown_query_id_fails_closed() -> None:
    with pytest.raises(fq.ForensicQueryError) as exc:
        fq.answerable_by_id("FQ-HACK-99", _full_view())
    assert exc.value.reason_code == "UNKNOWN_QUERY_ID"
    with pytest.raises(fq.ForensicQueryError) as exc_empty:
        fq.answerable_by_id("", _full_view())
    assert exc_empty.value.reason_code == "UNKNOWN_QUERY_ID"


def test_malformed_audit_views_fail_closed() -> None:
    for kwargs in (
        {"event_id": "", "retained_fields": {}},
        {"event_id": "   ", "retained_fields": {}},
        {"event_id": "evt-1", "retained_fields": {}, "retention_mode": "encrypted_all"},
    ):
        with pytest.raises(fq.ForensicQueryError) as exc:
            fq.AuditView(**kwargs)
        assert exc.value.reason_code == "MALFORMED_AUDIT_VIEW"


def test_malformed_queries_are_refused_at_set_level() -> None:
    duplicate = tuple(fq.FORENSIC_QUERIES) + (fq.FORENSIC_QUERIES[0],)
    with pytest.raises(fq.ForensicQueryError) as exc_dup:
        fq._assert_internal_consistency(duplicate)
    assert exc_dup.value.reason_code == "MALFORMED_QUERY"
    bad_class = dataclasses.replace(fq.FORENSIC_QUERIES[0], query_class="marketing")
    with pytest.raises(fq.ForensicQueryError) as exc_class:
        fq._assert_internal_consistency((bad_class,))
    assert exc_class.value.reason_code == "MALFORMED_QUERY"
    phi_witness = dataclasses.replace(fq.FORENSIC_QUERIES[0], witnesses_needed=("patient_email",))
    with pytest.raises(fq.ForensicQueryError) as exc_phi:
        fq._assert_internal_consistency((phi_witness,))
    assert exc_phi.value.reason_code == "MALFORMED_QUERY"


def test_ineterminate_is_never_coerced_to_answerable() -> None:
    # Guard the CASE MATRIX rule: INDETERMINATE is retained and counted.
    indeterminate_views = (_no_key_custody_view(), _missing_policy_epoch_view())
    for view in indeterminate_views:
        verdicts = [fq.answerable(q, view) for q in fq.FORENSIC_QUERIES]
        assert "INDETERMINATE" in verdicts
        for verdict in verdicts:
            assert verdict in ("ANSWERABLE", "NOT_ANSWERABLE", "INDETERMINATE")


def test_full_view_answerability_is_the_utility_upper_bound() -> None:
    # B0 discipline: nothing may be LESS answerable on the full view than on
    # any minimized projection of the same event.
    full = _full_view()
    degraded = (_minimized_view(), _hash_only_view(), _no_log_view())
    for query in fq.FORENSIC_QUERIES:
        base = fq.answerable(query, full)
        rank = {"ANSWERABLE": 2, "INDETERMINATE": 1, "NOT_ANSWERABLE": 0}
        for view in degraded:
            assert rank[fq.answerable(query, view)] <= rank[base], query.query_id
