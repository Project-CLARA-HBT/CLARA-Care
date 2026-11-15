"""Tests for the IFIP_SEC venue receipt schema (task IFIP_SEC-X01_receipt_schema).

Task contract signature: a JSON Schema (2020-12 subset) for the canonical
context-bound authorization receipt at
``research/venue2027/ifip_sec/protocols/receipt.schema.json`` validated with
the shared stdlib validator (``_shared/tools/schema_validator.py``).

Positive controls (>=3 valid receipts):
- A canonical non-delegated receipt (delegated_actor == principal).
- A delegated multi-hop receipt with distinct actor and non-default epochs.
- A minimal-but-legal receipt with second-precision timestamps and a
  boundary-valid expiry (issued_at < expiry, one second apart).

Adversarial controls (each individually rejected, fail closed):
- Missing signature (REQUIRED_MISSING).
- Expired-before-issued (expiry <= issued_at -> composed TEMPORAL_ORDER).
- Bad hash pattern on proposal_lineage_hash (uppercase / short / non-hex,
  PATTERN_MISMATCH).
- Unknown extra field (ADDITIONAL_PROPERTY), including an injected health
  value - the receipt must carry no clinical content.
- Missing nonce (REQUIRED_MISSING).

Composed validator semantics: schema-level validation uses the shared
validator untouched; the temporal rule (expiry strictly after issued_at) is
encoded as strict UTC timestamps and test-enforced here with stable reason
codes (TEMPORAL_ORDER, TIMESTAMP_UNPARSEABLE). An unparseable timestamp is
never counted as a safe pass or a silent schema pass - it is a distinct
fail-closed code.

Independence: this test imports only the schema JSON and the shared stdlib
validator; it never imports any candidate receipt verifier implementation.
"""

from __future__ import annotations

import copy
import datetime
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
TOOLS = REPO / "research" / "venue2027" / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import schema_validator as sv  # noqa: E402

SCHEMA_PATH = pathlib.Path(__file__).resolve().parents[1] / "protocols" / "receipt.schema.json"

ISSUED = "2026-11-14T09:30:00Z"
EXPIRY = "2026-11-14T10:30:00Z"

VALID_BASE = {
    "version": "1",
    "tenant": "tenant-clinic-01",
    "principal": "prn:end_user:u-4f21",
    "purpose": "medication_management",
    "delegated_actor": "prn:agent:clara-orchestrator",
    "operation": "medication.ddi_check",
    "proposal_lineage_hash": "ab" * 32,
    "policy_epoch": "policy-epoch-2026-11-01",
    "consent_epoch": "consent-v7",
    "nonce": "9q7Xw2rT5yU8zA1bC3dE",
    "issued_at": ISSUED,
    "expiry": EXPIRY,
    "signature": {"algorithm": "HMAC-SHA256", "value": "cd" * 32},
}


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate(receipt: dict) -> tuple[str, ...]:
    """Schema validation plus the composed temporal rule (fail closed).

    The stdlib 2020-12 subset cannot compare two instance fields, so
    'expiry strictly after issued_at' is enforced here with stable codes:
    TEMPORAL_ORDER for ordering violations, TIMESTAMP_UNPARSEABLE for any
    timestamp that fails the strict UTC parse. An indeterminate timestamp is
    a rejection, never a silent pass.
    """

    reason_codes = set(sv.validate_instance(receipt, _load_schema(), schema_path=SCHEMA_PATH))
    parsed: dict[str, datetime.datetime] = {}
    for field in ("issued_at", "expiry"):
        value = receipt.get(field)
        if not isinstance(value, str):
            continue
        try:
            parsed[field] = datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            try:
                parsed[field] = datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                reason_codes.add("TIMESTAMP_UNPARSEABLE")
    if {"issued_at", "expiry"} <= set(parsed) and parsed["expiry"] <= parsed["issued_at"]:
        reason_codes.add("TEMPORAL_ORDER")
    return tuple(sorted(reason_codes))


def _valid(**overrides: object) -> dict:
    receipt = copy.deepcopy(VALID_BASE)
    for key, value in overrides.items():
        if value is _DELETE:
            receipt.pop(key, None)
        else:
            receipt[key] = value
    return receipt


class _Delete:
    """Sentinel overriding a base field with 'absent'."""


_DELETE = _Delete()

# ---------------------------------------------------------------- positive --


def test_positive_canonical_non_delegated_receipt() -> None:
    receipt = _valid(delegated_actor=VALID_BASE["principal"])
    assert _validate(receipt) == ()


def test_positive_delegated_multihop_receipt() -> None:
    receipt = _valid(
        tenant="tenant-hospital-07",
        principal="prn:clinician:dr-nguyen",
        delegated_actor="prn:agent:scribe-relay-2",
        purpose="medication_review",
        operation="medication.propose_adjustment",
        policy_epoch="policy-epoch-2026-11-14",
        consent_epoch="consent-v9",
        issued_at="2026-11-14T23:59:59.123456Z",
        expiry="2026-11-15T00:29:59.999999Z",
    )
    assert _validate(receipt) == ()


def test_positive_boundary_expiry_one_second_after_issued() -> None:
    receipt = _valid(issued_at="2026-11-14T09:30:00Z", expiry="2026-11-14T09:30:01Z")
    assert _validate(receipt) == ()


def test_positive_all_required_fields_present() -> None:
    schema = _load_schema()
    receipt = _valid()
    assert sorted(schema["required"]) == sorted(receipt)
    assert sv.validate_instance(receipt, schema, schema_path=SCHEMA_PATH) == ()


# -------------------------------------------------------------- adversarial --


def test_adversarial_missing_signature_rejected() -> None:
    receipt = _valid(signature=_DELETE)
    codes = _validate(receipt)
    assert "REQUIRED_MISSING" in codes


def test_adversarial_signature_value_missing_rejected() -> None:
    receipt = _valid(signature={"algorithm": "HMAC-SHA256"})
    codes = _validate(receipt)
    assert "REQUIRED_MISSING" in codes


def test_adversarial_expiry_equal_issued_rejected() -> None:
    receipt = _valid(expiry=ISSUED)
    codes = _validate(receipt)
    assert "TEMPORAL_ORDER" in codes


def test_adversarial_expired_before_issued_rejected() -> None:
    receipt = _valid(expiry="2026-11-14T08:30:00Z")
    codes = _validate(receipt)
    assert "TEMPORAL_ORDER" in codes


def test_adversarial_bad_hash_pattern_rejected() -> None:
    for bad in ("AB" * 32, "ab" * 31, "z" * 64, "0x" + "ab" * 31):
        receipt = _valid(proposal_lineage_hash=bad)
        codes = _validate(receipt)
        assert "PATTERN_MISMATCH" in codes, bad


def test_adversarial_bad_signature_value_pattern_rejected() -> None:
    receipt = _valid(signature={"algorithm": "HMAC-SHA256", "value": "cd" * 31})
    codes = _validate(receipt)
    assert "PATTERN_MISMATCH" in codes


def test_adversarial_unknown_extra_field_rejected() -> None:
    receipt = _valid(tenant_region="eu-central")
    codes = _validate(receipt)
    assert "ADDITIONAL_PROPERTY" in codes


def test_adversarial_injected_health_value_rejected() -> None:
    receipt = _valid(diagnosis_summary="type 2 diabetes, on metformin")
    codes = _validate(receipt)
    assert "ADDITIONAL_PROPERTY" in codes


def test_adversarial_missing_nonce_rejected() -> None:
    receipt = _valid(nonce=_DELETE)
    codes = _validate(receipt)
    assert "REQUIRED_MISSING" in codes


def test_adversarial_unknown_version_rejected() -> None:
    receipt = _valid(version="2")
    codes = _validate(receipt)
    assert "CONST_MISMATCH" in codes


def test_adversarial_unknown_signature_algorithm_rejected() -> None:
    receipt = _valid(signature={"algorithm": "ED25519", "value": "cd" * 32})
    codes = _validate(receipt)
    assert "ENUM_MISMATCH" in codes


def test_adversarial_garbage_timestamp_rejected() -> None:
    receipt = _valid(issued_at="not-a-timestamp")
    codes = _validate(receipt)
    assert "TIMESTAMP_UNPARSEABLE" in codes


def test_adversarial_empty_and_wrong_type_fields_rejected() -> None:
    receipt = _valid(tenant="", nonce="short")
    codes = _validate(receipt)
    assert "PATTERN_MISMATCH" in codes
    receipt = _valid(proposal_lineage_hash=64)
    codes = _validate(receipt)
    assert "TYPE_MISMATCH" in codes


def test_schema_self_declares_2020_12_and_fails_closed() -> None:
    schema = _load_schema()
    assert schema["$schema"].endswith("draft/2020-12/schema")
    assert schema["additionalProperties"] is False
    for field in (
        "tenant",
        "principal",
        "purpose",
        "delegated_actor",
        "operation",
        "proposal_lineage_hash",
        "policy_epoch",
        "consent_epoch",
        "nonce",
        "issued_at",
        "expiry",
        "version",
        "signature",
    ):
        assert field in schema["properties"], field
        assert field in schema["required"], field
    # Every hash-bearing field pins a 64-hex pattern.
    for field in ("proposal_lineage_hash",):
        assert schema["properties"][field]["pattern"] == "^[0-9a-f]{64}$"
    assert schema["properties"]["signature"]["properties"]["value"]["pattern"] == "^[0-9a-f]{64}$"
    # The shared validator must accept the schema itself (no unknown keywords).
    assert sv.validate_instance(_valid(), schema, schema_path=SCHEMA_PATH) == ()
