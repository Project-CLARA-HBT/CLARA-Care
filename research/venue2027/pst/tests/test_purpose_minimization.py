"""Tests for the PST purpose-bound receipt minimizer (PST-X03_minimization).

Positive vectors prove the governed path: the per-purpose field-level
allowlist keeps only registered fields (everything else is dropped with an
observable ``NOT_IN_ALLOWLIST`` reason), the HMAC pseudonym is stable for the
same key yet unlinkable without it (key rotation changes every pseudonym,
raw ``subject_ref`` never appears), and the retention window drops expired
decaying content with ``RETENTION_EXPIRED`` while commitment and
consent/policy-epoch proofs persist past the deadline (the ReceiptMin design
point). Adversarial vectors prove fail-closed refusals: an unsalted
patient-identifier hash is refused with ``UNSALTED_HASH_REFUSED`` (bare
MD5/SHA-1/SHA-256 hex and prefixed forms, never laundered into a
pseudonym), an unknown purpose is refused with ``UNKNOWN_PURPOSE``, and an
escape attempt without an injected log sink is refused with
``ESCAPE_LOG_REQUIRED`` while an unauthorized escape (unknown grant, wrong
authority, uncovered purpose, expired window, missing justification) is
refused with ``ESCAPE_NOT_AUTHORIZED`` and — when a sink exists — always
logged. All fixtures are synthetic and PHI-free.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import pathlib
import sys
from datetime import UTC, datetime, timedelta

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from evaluation.venue2027._shared.dataset_kernel import PHI_FIELD_MARKERS
from evaluation.venue2027.pst import purpose_minimizer as pm

_KEY_A = b"pst-eval-key-alpha"
_KEY_B = b"pst-eval-key-beta"

_COMMIT_TIME = "2026-11-01T12:00:00Z"

_NOW_FRESH = "2026-11-10T12:00:00Z"  # 9 days after commit: nothing decayed
_NOW_EVIDENCE_DEAD = "2026-12-05T12:00:00Z"  # 34 days: evidence_digest decayed
_NOW_ALL_DEAD = "2027-02-15T12:00:00Z"  # 106 days: witness_id decayed too

_GRANT = pm.AUTHORIZED_ESCAPE_GRANTS["ESC-GRANT-PST-FORENSIC-01"]
_GRANT_ID = _GRANT.grant_id
_AUTHORITY = _GRANT.authority_id


def _record(**overrides: str) -> dict[str, str]:
    base = {
        "operation_id": "op-0001",
        "subject_ref": "subject-77",
        "created_at": _COMMIT_TIME,
        "commitment_digest": "a" * 64,
        "purpose_tag": "purpose-3",
        "consent_epoch": "consent-e7",
        "policy_epoch": "epoch-12",
        "witness_id": "witness-91",
        "retention_mode": "selective",
        "evidence_digest": "b" * 64,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Positive: allowlist keeps only allowed fields, drops are observable
# ---------------------------------------------------------------------------


def test_allowlist_keeps_only_registered_fields() -> None:
    out = pm.minimize(_record(), "self_care", _NOW_FRESH, pseudonym_key=_KEY_A)
    assert set(out.receipt) <= pm.PURPOSE_ALLOWLISTS["self_care"]
    assert "witness_id" not in out.receipt
    assert "evidence_digest" not in out.receipt
    assert out.dropped_fields["witness_id"] == pm.DROP_NOT_IN_ALLOWLIST
    assert out.dropped_fields["evidence_digest"] == pm.DROP_NOT_IN_ALLOWLIST


def test_allowlist_per_purpose_grants_different_content() -> None:
    out = pm.minimize(_record(), "clinical_care", _NOW_FRESH, pseudonym_key=_KEY_A)
    assert out.receipt["witness_id"] == "witness-91"
    assert out.receipt["evidence_digest"] == "b" * 64
    research = pm.minimize(_record(), "research_analytics", _NOW_FRESH, pseudonym_key=_KEY_A)
    assert "witness_id" not in research.receipt
    assert "evidence_digest" not in research.receipt


def test_purpose_tag_is_redacted_to_declared_purpose() -> None:
    """The purpose surface itself is redacted (PST-CASE-06): the receipt's
    purpose is the declared enum value, and the raw free-form purpose_tag
    never widens authorization."""

    out = pm.minimize(_record(), "self_care", _NOW_FRESH, pseudonym_key=_KEY_A)
    assert out.purpose == "self_care"
    assert out.receipt.get("purpose_tag") == "purpose-3"


def test_minimized_record_is_json_serializable() -> None:
    out = pm.minimize(_record(), "forensic_review", _NOW_FRESH, pseudonym_key=_KEY_A)
    payload = json.loads(json.dumps(out.to_dict()))
    assert payload["schema_version"] == pm.MINIMIZED_RECEIPT_SCHEMA_VERSION
    assert payload["minimizer_version"] == pm.PURPOSE_MINIMIZER_VERSION
    assert payload["purpose"] == "forensic_review"


def test_receipt_carries_no_phi_marker_fields() -> None:
    out = pm.minimize(_record(), "clinical_care", _NOW_FRESH, pseudonym_key=_KEY_A)
    for field in out.receipt:
        assert not any(marker in field.lower() for marker in PHI_FIELD_MARKERS)


# ---------------------------------------------------------------------------
# Positive: keyed pseudonyms — stable per key, unlinkable without it
# ---------------------------------------------------------------------------


def test_pseudonym_is_stable_for_same_key() -> None:
    first = pm.minimize(_record(), "self_care", _NOW_FRESH, pseudonym_key=_KEY_A)
    second = pm.minimize(
        _record(operation_id="op-0002"), "self_care", _NOW_FRESH, pseudonym_key=_KEY_A
    )
    assert first.pseudonym == second.pseudonym
    expected = "psn_" + hmac.new(_KEY_A, b"subject-77", hashlib.sha256).hexdigest()[:32]
    assert first.pseudonym == expected


def test_pseudonym_changes_under_key_rotation() -> None:
    """Unlinkability without the key: rotating the HMAC key yields a fresh
    pseudonym space, so cross-key joins leak nothing."""

    under_a = pm.minimize(_record(), "self_care", _NOW_FRESH, pseudonym_key=_KEY_A)
    under_b = pm.minimize(_record(), "self_care", _NOW_FRESH, pseudonym_key=_KEY_B)
    assert under_a.pseudonym != under_b.pseudonym


def test_raw_subject_ref_never_reaches_receipt() -> None:
    out = pm.minimize(_record(), "clinical_care", _NOW_FRESH, pseudonym_key=_KEY_A)
    blob = json.dumps(out.to_dict())
    assert "subject-77" not in blob
    assert out.pseudonym.startswith("psn_")


def test_pseudonym_unverifiable_without_key() -> None:
    out = pm.minimize(_record(), "self_care", _NOW_FRESH, pseudonym_key=_KEY_A)
    assert "subject-77" not in hashlib.sha256(b"subject-77").hexdigest()
    assert "subject-77" not in out.pseudonym


# ---------------------------------------------------------------------------
# Positive: retention windows drop expired fields, proofs persist
# ---------------------------------------------------------------------------


def test_fresh_record_keeps_all_allowed_fields() -> None:
    out = pm.minimize(_record(), "clinical_care", _NOW_FRESH, pseudonym_key=_KEY_A)
    assert out.dropped_fields == {}
    assert out.missing_mandatory_fields == ()


def test_evidence_digest_drops_after_retention_window() -> None:
    out = pm.minimize(_record(), "clinical_care", _NOW_EVIDENCE_DEAD, pseudonym_key=_KEY_A)
    assert "evidence_digest" not in out.receipt
    assert out.dropped_fields["evidence_digest"] == pm.DROP_RETENTION_EXPIRED
    assert out.receipt["witness_id"] == "witness-91"


def test_witness_id_drops_after_its_longer_window() -> None:
    out = pm.minimize(_record(), "clinical_care", _NOW_ALL_DEAD, pseudonym_key=_KEY_A)
    assert "witness_id" not in out.receipt
    assert "evidence_digest" not in out.receipt
    assert out.dropped_fields["witness_id"] == pm.DROP_RETENTION_EXPIRED


def test_commitment_and_epoch_proofs_persist_past_deadlines() -> None:
    """The ReceiptMin design point: content decays, proofs persist."""

    out = pm.minimize(_record(), "clinical_care", _NOW_ALL_DEAD, pseudonym_key=_KEY_A)
    assert out.receipt["commitment_digest"] == "a" * 64
    assert out.receipt["consent_epoch"] == "consent-e7"
    assert out.receipt["policy_epoch"] == "epoch-12"
    assert set(pm.PERSISTENT_PROOF_FIELDS) <= set(out.receipt)


def test_retention_boundary_is_exact() -> None:
    """``now == created_at + window`` is expired (window is half-open)."""

    deadline = datetime(2026, 11, 1, 12, 0, 0, tzinfo=UTC) + timedelta(days=90)
    out = pm.minimize(
        _record(), "clinical_care", deadline.strftime("%Y-%m-%dT%H:%M:%SZ"), pseudonym_key=_KEY_A
    )
    assert out.dropped_fields["witness_id"] == pm.DROP_RETENTION_EXPIRED
    before = pm.minimize(
        _record(),
        "clinical_care",
        (deadline - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        pseudonym_key=_KEY_A,
    )
    assert before.receipt["witness_id"] == "witness-91"


# ---------------------------------------------------------------------------
# Positive: controlled escape for authorized audits
# ---------------------------------------------------------------------------


def test_authorized_escape_restores_decayed_field_and_logs() -> None:
    log: list[dict] = []
    escape = pm.EscapeRequest(
        grant_id=_GRANT_ID, authority_id=_AUTHORITY, justification="case PST-CASE-01 investigation"
    )
    out = pm.minimize(
        _record(),
        "forensic_review",
        _NOW_ALL_DEAD,
        pseudonym_key=_KEY_A,
        escape=escape,
        escape_log=log,
    )
    assert len(log) == 1
    assert log[0]["decision"] == pm.ESCAPE_DECISION_GRANTED
    assert log[0]["grant_id"] == _GRANT_ID
    assert "escape_ref" in log[0]
    assert out.escape is not None and out.escape["decision"] == pm.ESCAPE_DECISION_GRANTED
    assert "witness_id" in out.receipt
    assert out.dropped_fields.get("witness_id") != pm.DROP_NOT_IN_ALLOWLIST


def test_escape_log_entry_carries_no_field_values() -> None:
    """The escape log is a decision record, not a content channel."""

    log: list[dict] = []
    escape = pm.EscapeRequest(
        grant_id=_GRANT_ID, authority_id=_AUTHORITY, justification="authorized audit"
    )
    pm.minimize(
        _record(),
        "forensic_review",
        _NOW_FRESH,
        pseudonym_key=_KEY_A,
        escape=escape,
        escape_log=log,
    )
    blob = json.dumps(log)
    assert "witness-91" not in blob
    assert "b" * 64 not in blob


# ---------------------------------------------------------------------------
# Adversarial: unsalted patient hash refused
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_ref",
    [
        "d41d8cd98f00b204e9800998ecf8427e",  # bare MD5 hex
        hashlib.sha1(b"patient-1").hexdigest(),  # bare SHA-1 hex
        hashlib.sha256(b"patient-1").hexdigest(),  # bare SHA-256 hex
        "sha256:" + hashlib.sha256(b"patient-1").hexdigest(),  # prefixed form
        "md5_" + "0" * 32,
        "sha1:" + "1" * 40,
    ],
)
def test_unsalted_patient_hash_refused(bad_ref: str) -> None:
    with pytest.raises(pm.MinimizationError) as excinfo:
        pm.minimize(_record(subject_ref=bad_ref), "self_care", _NOW_FRESH, pseudonym_key=_KEY_A)
    assert excinfo.value.reason_code == pm.REASON_UNSALTED_HASH_REFUSED


def test_unsalted_hash_refused_even_with_key_injected() -> None:
    """A key in hand does not launder an unsalted patient hash."""

    with pytest.raises(pm.MinimizationError) as excinfo:
        pm.pseudonymize(hashlib.sha256(b"patient-2").hexdigest(), _KEY_A)
    assert excinfo.value.reason_code == pm.REASON_UNSALTED_HASH_REFUSED


def test_refusal_is_typed_not_bare_exception() -> None:
    with pytest.raises(pm.MinimizationError) as excinfo:
        pm.minimize(_record(subject_ref="2" * 64), "self_care", _NOW_FRESH, pseudonym_key=_KEY_A)
    assert isinstance(excinfo.value, ValueError)
    assert excinfo.value.reason_code == pm.REASON_UNSALTED_HASH_REFUSED


# ---------------------------------------------------------------------------
# Adversarial: unknown purpose refused
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_purpose", ["data_enrichment", "marketing", "", "SELF_CARE"])
def test_unknown_purpose_refused(bad_purpose: str) -> None:
    with pytest.raises(pm.MinimizationError) as excinfo:
        pm.minimize(_record(), bad_purpose, _NOW_FRESH, pseudonym_key=_KEY_A)
    assert excinfo.value.reason_code == pm.REASON_UNKNOWN_PURPOSE


def test_overbroad_purpose_cannot_widen_allowlist() -> None:
    """A purpose outside the enum gains nothing, even by naming a real one
    inside a longer string."""

    with pytest.raises(pm.MinimizationError) as excinfo:
        pm.minimize(_record(), "forensic_review_all", _NOW_FRESH, pseudonym_key=_KEY_A)
    assert excinfo.value.reason_code == pm.REASON_UNKNOWN_PURPOSE


# ---------------------------------------------------------------------------
# Adversarial: escape without authorization refused (and logged when possible)
# ---------------------------------------------------------------------------


def test_escape_without_log_sink_refused() -> None:
    escape = pm.EscapeRequest(
        grant_id=_GRANT_ID, authority_id=_AUTHORITY, justification="authorized audit"
    )
    with pytest.raises(pm.MinimizationError) as excinfo:
        pm.minimize(_record(), "forensic_review", _NOW_FRESH, pseudonym_key=_KEY_A, escape=escape)
    assert excinfo.value.reason_code == pm.REASON_ESCAPE_LOG_REQUIRED


def test_escape_with_unknown_grant_refused_and_logged() -> None:
    log: list[dict] = []
    escape = pm.EscapeRequest(
        grant_id="ESC-GRANT-FORGED-99", authority_id=_AUTHORITY, justification="forged grant"
    )
    with pytest.raises(pm.MinimizationError) as excinfo:
        pm.minimize(
            _record(),
            "forensic_review",
            _NOW_FRESH,
            pseudonym_key=_KEY_A,
            escape=escape,
            escape_log=log,
        )
    assert excinfo.value.reason_code == pm.REASON_ESCAPE_NOT_AUTHORIZED
    assert len(log) == 1
    assert log[0]["decision"] == pm.ESCAPE_DECISION_REFUSED


def test_escape_with_wrong_authority_refused() -> None:
    log: list[dict] = []
    escape = pm.EscapeRequest(
        grant_id=_GRANT_ID, authority_id="impostor-adjudicator", justification="not mine"
    )
    with pytest.raises(pm.MinimizationError) as excinfo:
        pm.minimize(
            _record(),
            "forensic_review",
            _NOW_FRESH,
            pseudonym_key=_KEY_A,
            escape=escape,
            escape_log=log,
        )
    assert excinfo.value.reason_code == pm.REASON_ESCAPE_NOT_AUTHORIZED
    assert log[0]["decision"] == pm.ESCAPE_DECISION_REFUSED


def test_escape_for_uncovered_purpose_refused() -> None:
    log: list[dict] = []
    escape = pm.EscapeRequest(
        grant_id=_GRANT_ID, authority_id=_AUTHORITY, justification="purpose laundering"
    )
    with pytest.raises(pm.MinimizationError) as excinfo:
        pm.minimize(
            _record(),
            "self_care",
            _NOW_FRESH,
            pseudonym_key=_KEY_A,
            escape=escape,
            escape_log=log,
        )
    assert excinfo.value.reason_code == pm.REASON_ESCAPE_NOT_AUTHORIZED
    assert log[0]["purpose"] == "self_care"


def test_expired_escape_grant_refused() -> None:
    log: list[dict] = []
    escape = pm.EscapeRequest(
        grant_id=_GRANT_ID, authority_id=_AUTHORITY, justification="after expiry"
    )
    with pytest.raises(pm.MinimizationError) as excinfo:
        pm.minimize(
            _record(),
            "forensic_review",
            "2031-06-01T00:00:00Z",
            pseudonym_key=_KEY_A,
            escape=escape,
            escape_log=log,
        )
    assert excinfo.value.reason_code == pm.REASON_ESCAPE_NOT_AUTHORIZED


@pytest.mark.parametrize("justification", ["", "   "])
def test_escape_without_justification_refused(justification: str) -> None:
    log: list[dict] = []
    escape = pm.EscapeRequest(
        grant_id=_GRANT_ID, authority_id=_AUTHORITY, justification=justification
    )
    with pytest.raises(pm.MinimizationError) as excinfo:
        pm.minimize(
            _record(),
            "forensic_review",
            _NOW_FRESH,
            pseudonym_key=_KEY_A,
            escape=escape,
            escape_log=log,
        )
    assert excinfo.value.reason_code == pm.REASON_MALFORMED_ESCAPE
    assert log[0]["decision"] == pm.ESCAPE_DECISION_REFUSED


def test_refused_escape_grants_no_fields() -> None:
    """A refused escape must not silently widen the receipt; the refusal is
    an exception, so no MinimizedRecord escapes the call at all."""

    escape = pm.EscapeRequest(grant_id=_GRANT_ID, authority_id="impostor", justification="sneak")
    with pytest.raises(pm.MinimizationError):
        pm.minimize(
            _record(),
            "forensic_review",
            _NOW_FRESH,
            pseudonym_key=_KEY_A,
            escape=escape,
            escape_log=[],
        )


# ---------------------------------------------------------------------------
# Adversarial: malformed records and hidden-ID smuggling
# ---------------------------------------------------------------------------


def test_hidden_extra_field_refused() -> None:
    """``additionalProperties: false`` analogue: no hidden-ID side channel."""

    smuggled = _record(track_id="cross-epoch-join-token")
    with pytest.raises(pm.MinimizationError) as excinfo:
        pm.minimize(smuggled, "self_care", _NOW_FRESH, pseudonym_key=_KEY_A)
    assert excinfo.value.reason_code == pm.REASON_UNRECOGNIZED_FIELD


@pytest.mark.parametrize("phi_name", ["patient_name", "mrn", "email", "date_of_birth"])
def test_phi_marker_field_refused(phi_name: str) -> None:
    with pytest.raises(pm.MinimizationError) as excinfo:
        pm.minimize(_record(**{phi_name: "x"}), "self_care", _NOW_FRESH, pseudonym_key=_KEY_A)
    assert excinfo.value.reason_code == pm.REASON_PHI_FIELD_PRESENT


def test_missing_identity_field_refused() -> None:
    with pytest.raises(pm.MinimizationError) as excinfo:
        pm.minimize(
            {k: v for k, v in _record().items() if k != "operation_id"},
            "self_care",
            _NOW_FRESH,
            pseudonym_key=_KEY_A,
        )
    assert excinfo.value.reason_code == pm.REASON_MALFORMED_RECORD


def test_non_string_value_refused() -> None:
    with pytest.raises(pm.MinimizationError) as excinfo:
        pm.minimize(_record(retention_mode=3), "self_care", _NOW_FRESH, pseudonym_key=_KEY_A)
    assert excinfo.value.reason_code == pm.REASON_MALFORMED_RECORD


def test_malformed_timestamp_refused() -> None:
    with pytest.raises(pm.MinimizationError) as excinfo:
        pm.minimize(_record(created_at="01/11/2026"), "self_care", _NOW_FRESH, pseudonym_key=_KEY_A)
    assert excinfo.value.reason_code == pm.REASON_MALFORMED_RECORD
    with pytest.raises(pm.MinimizationError) as excinfo:
        pm.minimize(_record(), "self_care", "2026-11-10T12:00:00+07:00", pseudonym_key=_KEY_A)
    assert excinfo.value.reason_code == pm.REASON_MALFORMED_RECORD


def test_empty_pseudonym_key_refused() -> None:
    with pytest.raises(pm.MinimizationError) as excinfo:
        pm.minimize(_record(), "self_care", _NOW_FRESH, pseudonym_key=b"")
    assert excinfo.value.reason_code == pm.REASON_PSEUDONYM_KEY_REQUIRED


# ---------------------------------------------------------------------------
# Determinism / purity
# ---------------------------------------------------------------------------


def test_minimize_is_deterministic_and_pure() -> None:
    record = _record()
    snapshot = copy.deepcopy(record)
    first = pm.minimize(record, "clinical_care", _NOW_FRESH, pseudonym_key=_KEY_A)
    second = pm.minimize(record, "clinical_care", _NOW_FRESH, pseudonym_key=_KEY_A)
    assert record == snapshot, "minimize must not mutate its input"
    assert first.to_dict() == second.to_dict()


def test_missing_mandatory_proof_reported_not_repaired() -> None:
    """Committer under-commitment (PST-CASE-05) is reported as incompleteness,
    never silently repaired nor coerced into a complete receipt."""

    stripped = _record()
    del stripped["consent_epoch"]
    out = pm.minimize(stripped, "self_care", _NOW_FRESH, pseudonym_key=_KEY_A)
    assert "consent_epoch" in out.missing_mandatory_fields
    assert out.missing_mandatory_fields == ("consent_epoch",)
