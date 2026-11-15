"""Tests for the PST purpose-bound minimal audit receipt contract.

Task: PST-X01_receipt_contract (P02, ReceiptMin RQ1). Purpose: prove the
receipt grammar ``research/venue2027/pst/protocols/receipt.schema.json``
accepts the governed minimal receipt and rejects fail-closed every smuggling
vector the ReceiptMin threat model cares about: a missing
``omitted_field_digest`` (forensic reconstruction becomes impossible, so the
receipt is not admissible evidence), a raw PHI field (patient detail must
never be representable in a receipt), a malformed digest (digest comparison
is the only reconstruction proof, so it must be exact 64-lowercase-hex), and
an unknown extra field (``additionalProperties: false`` closes the hidden-ID
side channel: cross-epoch replay and hidden identifiers are rejected on
top of this grammar by the disclosure protocol and forensic oracle).

Allowed input: the on-disk receipt schema and the stdlib-only shared JSON
Schema validator ``research/venue2027/_shared/tools/schema_validator.py``;
no network, no DB, no clock, no randomness, no candidate implementation
import (tests are the oracle's disclosure gate, independent by construction).

Failure semantics: every rejection asserts a non-empty tuple of stable
reason codes returned by ``schema_validator.validate_instance``; a vacuous
pass (empty errors on a malformed receipt) fails the test. The schema is
also required to itself validate under the shared validator (an unusable
schema must raise, never silently accept).

Version: 1.0.0 (additive-only within 1.x).
"""

from __future__ import annotations

import copy
import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[4]
TOOLS = REPO / "research" / "venue2027" / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import schema_validator as sv  # noqa: E402

SCHEMA_PATH = REPO / "research" / "venue2027" / "pst" / "protocols" / "receipt.schema.json"

_REQUIRED_FIELDS = (
    "version",
    "receipt_id",
    "tenant",
    "principal",
    "purpose",
    "operation",
    "omitted_field_digest",
    "policy_epoch",
    "issued_at",
    "signature",
)

_PATTERNS = {
    "receipt_id": "^rcpt_[0-9a-f]{16,64}$",
    "tenant": "^tnt_[0-9a-f]{8,32}$",
    "principal": "^prn_[0-9a-f]{8,32}$",
    "omitted_field_digest": "^[0-9a-f]{64}$",
    "policy_epoch": "^epoch-[0-9]{1,8}$",
    "signature": "^[0-9a-f]{64}$",
}


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _digest(seed: str) -> str:
    """Deterministic 64-hex digest for fixtures (SHA-256 of a canonical line).

    The digest is over the canonical JSON of the declared omitted-fields
    object for the operation's audit query class; the value itself is never
    stored in (or derivable from) the receipt.
    """
    import hashlib

    canonical = json.dumps(
        {"declared_fields": ["subject_ref", "decision"], "seed": seed},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _signature(body: dict) -> str:
    """Deterministic 64-hex fixture signature over the receipt body.

    Mirrors the contract: HMAC-SHA256 over the canonical JSON of every field
    except ``signature``. Key material is externalized (fixture key only);
    tampering with any body field changes this value, which is what the
    DETECT_TAMPER case relies on downstream.
    """
    import hashlib
    import hmac

    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hmac.new(b"fixture-verification-key", canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def _receipt(
    *,
    receipt_id: str = "rcpt_0011223344556677",
    tenant: str = "tnt_0a1b2c3d",
    principal: str = "prn_9f8e7d6c",
    purpose: str = "forensic_review",
    operation: str = "record_read",
    seed: str = "pst-x01-positive-a",
    policy_epoch: str = "epoch-7",
    issued_at: str = "2026-11-15T09:30:00Z",
) -> dict:
    """One schema-valid minimal receipt; body carries no clinical payload."""
    body = {
        "version": "1",
        "receipt_id": receipt_id,
        "tenant": tenant,
        "principal": principal,
        "purpose": purpose,
        "operation": operation,
        "omitted_field_digest": _digest(seed),
        "policy_epoch": policy_epoch,
        "issued_at": issued_at,
    }
    body["signature"] = _signature(body)
    return body


def test_schema_is_well_formed_and_fail_closed() -> None:
    schema = _schema()
    # The shared validator must accept the schema itself (raises on
    # unsupported keywords, i.e. an unusable schema can never silently pass).
    sv.validate_instance(_receipt(), schema, schema_path=SCHEMA_PATH)
    assert schema["additionalProperties"] is False
    assert schema["type"] == "object"
    assert schema["properties"]["version"]["const"] == "1"
    assert set(schema["required"]) == set(_REQUIRED_FIELDS)
    assert set(schema["properties"]) == set(_REQUIRED_FIELDS)
    for field, pattern in _PATTERNS.items():
        assert schema["properties"][field]["pattern"] == pattern, field


# ---------------------------------------------------------------------------
# Positive vectors: governed receipts are accepted, reproducibly.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {
            "receipt_id": "rcpt_aaaa0000bbbb1111cccc2222dddd3333",
            "tenant": "tnt_9988ccbb",
            "principal": "prn_1122334455",
            "purpose": "self_care",
            "operation": "record_write",
            "seed": "pst-x01-positive-b",
            "policy_epoch": "epoch-1",
            "issued_at": "2026-11-14T23:59:59Z",
        },
        {
            "receipt_id": "rcpt_" + "0123456789abcdef" * 4,
            "tenant": "tnt_" + "abcd" * 8,
            "principal": "prn_" + "ef01" * 8,
            "purpose": "security_audit",
            "operation": "receipt_verify",
            "seed": "pst-x01-positive-c",
            "policy_epoch": "epoch-99999999",
            "issued_at": "2027-01-01T00:00:00Z",
        },
    ],
    ids=["positive-a-forensic-read", "positive-b-selfcare-write", "positive-c-audit-verify"],
)
def test_valid_receipt_accepted(overrides: dict) -> None:
    receipt = _receipt(**overrides)
    reason_codes = sv.validate_instance(receipt, _schema(), schema_path=SCHEMA_PATH)
    assert reason_codes == (), f"valid receipt rejected: {reason_codes}"
    # Reproducible: same fixture twice yields byte-identical receipt.
    assert receipt == _receipt(**overrides)
    # No clinical payload: every value is a bounded token, digest or epoch.
    for field, value in receipt.items():
        if field == "version":
            continue
        assert isinstance(value, str) and len(value) <= 128, field


def test_valid_receipt_fields_exactly_the_contract_set() -> None:
    receipt = _receipt()
    assert set(receipt) == set(_REQUIRED_FIELDS)
    assert sv.validate_instance(receipt, _schema(), schema_path=SCHEMA_PATH) == ()


# ---------------------------------------------------------------------------
# Adversarial vectors: each must be rejected with a stable reason code.
# ---------------------------------------------------------------------------


def test_missing_omitted_field_digest_rejected() -> None:
    receipt = _receipt()
    del receipt["omitted_field_digest"]
    codes = sv.validate_instance(receipt, _schema(), schema_path=SCHEMA_PATH)
    assert codes and "REQUIRED_MISSING" in codes, codes


def test_raw_phi_field_rejected() -> None:
    receipt = _receipt()
    receipt["patient_name"] = "Nguyen Van A"
    receipt["diagnosis"] = "type 2 diabetes"
    codes = sv.validate_instance(receipt, _schema(), schema_path=SCHEMA_PATH)
    assert codes and "ADDITIONAL_PROPERTY" in codes, codes


def test_bad_digest_pattern_rejected() -> None:
    schema = _schema()
    for bad in (
        "DEADBEEF" * 8,  # uppercase
        "z" * 64,  # non-hex
        "a" * 63,  # too short
        "b" * 65,  # too long
        "",  # empty
    ):
        receipt = _receipt(seed="pst-x01-digest-vector")
        receipt["omitted_field_digest"] = bad
        codes = sv.validate_instance(receipt, schema, schema_path=SCHEMA_PATH)
        assert codes and "PATTERN_MISMATCH" in codes, (bad, codes)


def test_unknown_field_rejected() -> None:
    receipt = _receipt()
    receipt["hidden_internal_id"] = "mrn-77-0042"
    codes = sv.validate_instance(receipt, _schema(), schema_path=SCHEMA_PATH)
    assert codes and "ADDITIONAL_PROPERTY" in codes, codes


def test_wrong_version_rejected_not_best_effort_parsed() -> None:
    receipt = _receipt()
    receipt["version"] = "2"
    codes = sv.validate_instance(receipt, _schema(), schema_path=SCHEMA_PATH)
    assert codes and "CONST_MISMATCH" in codes, codes


def test_cross_epoch_style_malformed_policy_epoch_rejected() -> None:
    # The token grammar refuses epochs that are not registry-live shaped;
    # cross-epoch admissibility is then refused by the disclosure protocol.
    schema = _schema()
    for bad in ("epoch-abc", "2024-epoch-1", "epoch-", "epoch-1 "):
        receipt = _receipt()
        receipt["policy_epoch"] = bad
        codes = sv.validate_instance(receipt, schema, schema_path=SCHEMA_PATH)
        assert codes and "PATTERN_MISMATCH" in codes, (bad, codes)


@pytest.mark.parametrize(
    "field",
    ["version", "receipt_id", "tenant", "principal", "purpose", "operation", "policy_epoch", "issued_at", "signature"],
)
def test_missing_required_field_rejected(field: str) -> None:
    receipt = _receipt()
    del receipt[field]
    codes = sv.validate_instance(receipt, _schema(), schema_path=SCHEMA_PATH)
    assert codes and "REQUIRED_MISSING" in codes, codes


def test_unknown_purpose_and_operation_rejected() -> None:
    # A purpose field that encodes a patient attribute cannot be represented.
    schema = _schema()
    receipt = _receipt()
    receipt["purpose"] = "pregnancy_followup"
    codes = sv.validate_instance(receipt, schema, schema_path=SCHEMA_PATH)
    assert codes and "ENUM_MISMATCH" in codes, codes
    receipt = _receipt()
    receipt["operation"] = "prescribe_dose"
    codes = sv.validate_instance(receipt, schema, schema_path=SCHEMA_PATH)
    assert codes and "ENUM_MISMATCH" in codes, codes


def test_signature_tamper_changes_digest_of_body() -> None:
    # Structural tamper evidence: the signature is bound to the canonical
    # body, so any mutated field invalidates verification (DETECT_TAMPER
    # semantics belong to the verifier, the grammar only guarantees the
    # signature field is a comparison-capable 64-hex token).
    receipt = _receipt(seed="pst-x01-tamper")
    original_sig = receipt["signature"]
    tampered = copy.deepcopy(receipt)
    tampered["policy_epoch"] = "epoch-8"
    assert _signature({k: v for k, v in tampered.items() if k != "signature"}) != original_sig
    assert tampered["signature"] == original_sig  # attacker cannot update it without the key


def test_receipts_are_independent_and_idempotent_artifacts() -> None:
    # Distinct logical operations yield distinct receipts and distinct
    # omitted-field digests for the same underlying query class.
    a = _receipt(seed="op-a")
    b = _receipt(receipt_id="rcpt_0011223344556688", seed="op-b")
    assert a["signature"] != b["signature"]
    assert a["omitted_field_digest"] != b["omitted_field_digest"]
    assert sv.validate_instance(a, _schema(), schema_path=SCHEMA_PATH) == ()
    assert sv.validate_instance(b, _schema(), schema_path=SCHEMA_PATH) == ()
