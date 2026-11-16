"""Unit and adversarial test suite for PST-X04_encrypted_ref (ReceiptMin B2).

Tested mechanisms:
- evaluation/venue2027/pst/encrypted_full_log.py: Authenticated encryption reference
  for audit logs under AES-GCM and ChaCha20-Poly1305.

Positive controls:
- Encrypt + decrypt round-trip with correct key and authorized role (AES-GCM & ChaCha20).
- Nonce uniqueness verified (random generator and counter-based generator).
- Periodic key rotation support (KeyRing, key retirement, re-encryption).
- Decryption allowed within valid retention window.
- Store full log contract fidelity (store_full_log -> EncryptedRecord).
- JSON serialization / deserialization roundtrip.
- Scientific comparison of legitimate audit query vs insider auxiliary leakage.

Adversarial controls:
- Tampered ciphertext fails auth tag verification (AUTH_TAG_FAILED).
- Tampered auth tag fails authentication (AUTH_TAG_FAILED).
- Tampered additional authenticated data (AAD) fails verification (AUTH_TAG_FAILED).
- Wrong key fails decryption (AUTH_TAG_FAILED).
- Unauthorized role denied decryption (UNAUTHORIZED_ROLE).
- Reused nonce detected and refused (NONCE_REUSED).
- Expired record decryption refused (RETENTION_EXPIRED).
- Destroyed key re-derivation/decryption refused (KEY_DESTROYED).
- Invalid key length refused (KEY_INVALID).
- Unsupported cipher algorithm refused (ALGORITHM_UNSUPPORTED).
"""

from __future__ import annotations

import json
import os

import pytest

from evaluation.venue2027.pst.encrypted_full_log import (
    ALG_AES_GCM,
    ALG_CHACHA20_POLY1305,
    RC_ALGORITHM_UNSUPPORTED,
    RC_AUTH_TAG_FAILED,
    RC_KEY_DESTROYED,
    RC_KEY_INVALID,
    RC_NONCE_REUSED,
    RC_RETENTION_EXPIRED,
    RC_UNAUTHORIZED_ROLE,
    EncryptedLogError,
    EncryptedRecord,
    KeyRing,
    NonceTracker,
    compare_audit_vs_leakage,
    decrypt_audit_record,
    encrypt_audit_record,
    generate_nonce,
    reencrypt_record,
    store_full_log,
)

# --- Synthetic Fixtures -----------------------------------------------------


def _sample_audit_record() -> dict[str, object]:
    """Return a representative synthetic clinical audit record."""
    return {
        "event_id": "evt_syn_9901",
        "operation_id": "op_med_dispense_101",
        "tenant_id": "tnt_hospital_alpha",
        "principal_id": "prn_dr_smith",
        "subject_id": "subj_synthetic_patient_42",
        "purpose": "clinical_care",
        "operation": "prescribe_medication",
        "policy_epoch": "epoch-2026-q4",
        "payload": {
            "medication": "amoxicillin",
            "dosage": "500mg",
            "frequency": "tid",
            "diagnosis": "acute_pharyngitis",
        },
        "created_at": "2026-11-16T10:00:00Z",
    }


# --- Positive Controls ------------------------------------------------------


def test_positive_encrypt_decrypt_roundtrip_aes_gcm() -> None:
    """Assert correct encryption and decryption round-trip under AES-GCM."""
    record = _sample_audit_record()
    key = os.urandom(32)  # 256-bit AES key
    tracker = NonceTracker()

    encrypted = encrypt_audit_record(
        record,
        key,
        acl=("auditor", "compliance_officer"),
        algorithm=ALG_AES_GCM,
        nonce_tracker=tracker,
    )

    assert isinstance(encrypted, EncryptedRecord)
    assert encrypted.algorithm == ALG_AES_GCM
    assert len(encrypted.nonce) == 24  # 12 bytes hex
    assert len(encrypted.auth_tag) == 32  # 16 bytes hex

    decrypted = decrypt_audit_record(
        encrypted,
        key,
        accessor_role="auditor",
    )

    assert decrypted == record
    assert decrypted["operation_id"] == "op_med_dispense_101"
    assert decrypted["payload"]["medication"] == "amoxicillin"


def test_positive_encrypt_decrypt_roundtrip_chacha20() -> None:
    """Assert correct encryption and decryption round-trip under ChaCha20-Poly1305."""
    record = _sample_audit_record()
    key = os.urandom(32)  # 256-bit ChaCha20 key
    tracker = NonceTracker()

    encrypted = encrypt_audit_record(
        record,
        key,
        acl=("security_admin",),
        algorithm=ALG_CHACHA20_POLY1305,
        nonce_tracker=tracker,
    )

    assert encrypted.algorithm == ALG_CHACHA20_POLY1305

    decrypted = decrypt_audit_record(
        encrypted,
        key,
        accessor_role="security_admin",
    )

    assert decrypted == record


def test_positive_nonce_uniqueness_and_modes() -> None:
    """Assert unique nonces across generation calls and deterministic counter mode."""
    # Random mode: generate 100 nonces and assert no collision
    nonces = {generate_nonce(ALG_AES_GCM, mode="random") for _ in range(100)}
    assert len(nonces) == 100
    assert all(len(n) == 12 for n in nonces)

    # Counter mode: sequential nonces are unique and strictly monotonic
    ctr1 = generate_nonce(ALG_AES_GCM, mode="counter", counter=1)
    ctr2 = generate_nonce(ALG_AES_GCM, mode="counter", counter=2)
    ctr3 = generate_nonce(ALG_AES_GCM, mode="counter", counter=3)

    assert len(ctr1) == 12
    assert ctr1 != ctr2 != ctr3
    assert ctr1 < ctr2 < ctr3


def test_positive_decryption_within_retention_window() -> None:
    """Assert decryption succeeds before retention deadline."""
    record = _sample_audit_record()
    key = os.urandom(32)
    tracker = NonceTracker()

    # 2 hours retention window
    encrypted = encrypt_audit_record(
        record,
        key,
        created_at="2026-11-16T10:00:00Z",
        retention_seconds=7200.0,
        nonce_tracker=tracker,
    )

    assert encrypted.expires_at == "2026-11-16T12:00:00Z"

    # Decrypt 30 minutes before expiration
    decrypted = decrypt_audit_record(
        encrypted,
        key,
        accessor_role="auditor",
        now="2026-11-16T11:30:00Z",
    )
    assert decrypted["event_id"] == "evt_syn_9901"


def test_positive_key_rotation_and_reencryption() -> None:
    """Assert key rotation and historical record re-encryption without disclosure."""
    record = _sample_audit_record()
    key1 = os.urandom(32)
    key2 = os.urandom(32)
    tracker = NonceTracker()

    ring = KeyRing()
    ring.add_key("key-2026-q3", key1, active=True)

    # Encrypt under epoch 1 key
    enc_v1 = encrypt_audit_record(
        record,
        ring.get_key("key-2026-q3"),
        key_id="key-2026-q3",
        acl=("auditor",),
        nonce_tracker=tracker,
    )
    assert enc_v1.key_id == "key-2026-q3"

    # Rotate to epoch 2 key
    ring.rotate_key("key-2026-q4", key2)
    assert ring.active_key_id == "key-2026-q4"

    # Re-encrypt record under epoch 2 key
    enc_v2 = reencrypt_record(
        enc_v1,
        old_key=ring.get_key("key-2026-q3"),
        new_key=ring.get_key("key-2026-q4"),
        new_key_id="key-2026-q4",
        accessor_role="auditor",
        nonce_tracker=tracker,
    )

    assert enc_v2.key_id == "key-2026-q4"
    assert enc_v2.nonce != enc_v1.nonce  # Fresh nonce
    assert enc_v2.ciphertext != enc_v1.ciphertext

    # Decrypting v2 with key2 succeeds
    dec_v2 = decrypt_audit_record(enc_v2, ring.get_key("key-2026-q4"), accessor_role="auditor")
    assert dec_v2 == record


def test_positive_store_full_log_contract() -> None:
    """Assert store_full_log target contract operates as expected."""
    event = _sample_audit_record()
    key = os.urandom(32)

    enc = store_full_log(event, key)
    assert isinstance(enc, EncryptedRecord)
    assert enc.record_id == "op_med_dispense_101"

    dec = decrypt_audit_record(enc, key, accessor_role="auditor")
    assert dec == event


def test_positive_json_serializability() -> None:
    """Assert EncryptedRecord serializes to JSON and round-trips via from_dict."""
    record = _sample_audit_record()
    key = os.urandom(32)

    enc = encrypt_audit_record(record, key, key_id="key-test")
    data_dict = enc.to_dict()

    # Must be valid JSON string
    json_str = json.dumps(data_dict)
    loaded_dict = json.loads(json_str)

    restored = EncryptedRecord.from_dict(loaded_dict)
    assert restored == enc

    decrypted = decrypt_audit_record(restored, key, accessor_role="auditor")
    assert decrypted == record


def test_positive_compare_audit_vs_leakage() -> None:
    """Assert scientific comparison function computes legitimate vs insider leakage metrics."""
    events = [_sample_audit_record()]
    key = os.urandom(32)

    res = compare_audit_vs_leakage(
        events,
        key,
        authorized_role="auditor",
        unauthorized_role="observer",
        retention_seconds=86400.0,
    )

    # Legitimate auditor gets full reconstruction within retention
    assert res.legitimate_reconstructability == 1.0
    assert res.legitimate_query_answered is True

    # Insider without key gets 0.0 payload exposure
    assert res.insider_without_key_payload_exposure == 0.0

    # Insider with compromised key gets 1.0 (exposing full sensitive payload and linkability)
    assert res.insider_with_key_payload_exposure == 1.0
    assert res.insider_with_key_linkability == 1.0

    # Post-retention query is refused
    assert res.post_retention_reconstructability == 0.0
    assert res.post_retention_leakage == 0.0

    assert res.summary["all_or_nothing_drawback_demonstrated"] is True


# --- Adversarial Controls ---------------------------------------------------


def test_adversarial_tampered_ciphertext_fails_auth_tag() -> None:
    """Assert tampered ciphertext fails authentication tag check (AUTH_TAG_FAILED)."""
    record = _sample_audit_record()
    key = os.urandom(32)

    enc = encrypt_audit_record(record, key)

    # Tamper with 1 hex nibble of the ciphertext
    ct_bytes = bytearray.fromhex(enc.ciphertext)
    ct_bytes[0] ^= 0xFF
    tampered_ct = ct_bytes.hex()

    tampered_record = EncryptedRecord(
        record_id=enc.record_id,
        ciphertext=tampered_ct,
        nonce=enc.nonce,
        auth_tag=enc.auth_tag,
        algorithm=enc.algorithm,
        key_id=enc.key_id,
        acl=enc.acl,
        created_at=enc.created_at,
        expires_at=enc.expires_at,
        aad=enc.aad,
        metadata=enc.metadata,
    )

    with pytest.raises(EncryptedLogError) as excinfo:
        decrypt_audit_record(tampered_record, key, accessor_role="auditor")

    assert excinfo.value.reason_code == RC_AUTH_TAG_FAILED


def test_adversarial_tampered_auth_tag_fails() -> None:
    """Assert tampered authentication tag fails verification (AUTH_TAG_FAILED)."""
    record = _sample_audit_record()
    key = os.urandom(32)

    enc = encrypt_audit_record(record, key)

    # Tamper with auth tag
    tag_bytes = bytearray.fromhex(enc.auth_tag)
    tag_bytes[-1] ^= 0x01
    tampered_tag = tag_bytes.hex()

    tampered_record = EncryptedRecord(
        record_id=enc.record_id,
        ciphertext=enc.ciphertext,
        nonce=enc.nonce,
        auth_tag=tampered_tag,
        algorithm=enc.algorithm,
        key_id=enc.key_id,
        acl=enc.acl,
        created_at=enc.created_at,
        expires_at=enc.expires_at,
        aad=enc.aad,
        metadata=enc.metadata,
    )

    with pytest.raises(EncryptedLogError) as excinfo:
        decrypt_audit_record(tampered_record, key, accessor_role="auditor")

    assert excinfo.value.reason_code == RC_AUTH_TAG_FAILED


def test_adversarial_tampered_aad_fails() -> None:
    """Assert tampered associated authenticated data fails decryption (AUTH_TAG_FAILED)."""
    record = _sample_audit_record()
    key = os.urandom(32)

    enc = encrypt_audit_record(record, key, aad="tenant_123:audit")

    # Attempt decrypt with different AAD
    with pytest.raises(EncryptedLogError) as excinfo:
        decrypt_audit_record(enc, key, accessor_role="auditor", aad="tenant_999:audit")

    assert excinfo.value.reason_code == RC_AUTH_TAG_FAILED


def test_adversarial_wrong_key_fails_auth_tag() -> None:
    """Assert decrypting with wrong key fails authentication tag check (AUTH_TAG_FAILED)."""
    record = _sample_audit_record()
    correct_key = os.urandom(32)
    wrong_key = os.urandom(32)

    enc = encrypt_audit_record(record, correct_key)

    with pytest.raises(EncryptedLogError) as excinfo:
        decrypt_audit_record(enc, wrong_key, accessor_role="auditor")

    assert excinfo.value.reason_code == RC_AUTH_TAG_FAILED


def test_adversarial_unauthorized_role_denied_decryption() -> None:
    """Assert accessor role not in ACL is denied decryption (UNAUTHORIZED_ROLE)."""
    record = _sample_audit_record()
    key = os.urandom(32)

    enc = encrypt_audit_record(
        record,
        key,
        acl=("auditor", "security_admin"),
    )

    # Reader with unauthorized role
    with pytest.raises(EncryptedLogError) as excinfo:
        decrypt_audit_record(enc, key, accessor_role="guest_researcher")

    assert excinfo.value.reason_code == RC_UNAUTHORIZED_ROLE


def test_adversarial_reused_nonce_detected() -> None:
    """Assert reusing the same nonce under the same key is detected and refused (NONCE_REUSED)."""
    record = _sample_audit_record()
    key = os.urandom(32)
    fixed_nonce = b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c"
    tracker = NonceTracker()

    # First use succeeds
    enc1 = encrypt_audit_record(
        record,
        key,
        nonce=fixed_nonce,
        nonce_tracker=tracker,
    )
    assert enc1.nonce == fixed_nonce.hex()

    # Second use with same key and same nonce MUST fail
    with pytest.raises(EncryptedLogError) as excinfo:
        encrypt_audit_record(
            record,
            key,
            nonce=fixed_nonce,
            nonce_tracker=tracker,
        )

    assert excinfo.value.reason_code == RC_NONCE_REUSED


def test_adversarial_expired_record_decryption_refused() -> None:
    """Assert decryption past retention deadline is refused (RETENTION_EXPIRED)."""
    record = _sample_audit_record()
    key = os.urandom(32)
    tracker = NonceTracker()

    # 1 hour retention
    enc = encrypt_audit_record(
        record,
        key,
        created_at="2026-11-16T10:00:00Z",
        retention_seconds=3600.0,
        nonce_tracker=tracker,
    )

    # Query exactly at expiration deadline
    with pytest.raises(EncryptedLogError) as excinfo1:
        decrypt_audit_record(
            enc,
            key,
            accessor_role="auditor",
            now="2026-11-16T11:00:00Z",
        )
    assert excinfo1.value.reason_code == RC_RETENTION_EXPIRED

    # Query well past expiration deadline
    with pytest.raises(EncryptedLogError) as excinfo2:
        decrypt_audit_record(
            enc,
            key,
            accessor_role="auditor",
            now="2026-11-17T00:00:00Z",
        )
    assert excinfo2.value.reason_code == RC_RETENTION_EXPIRED


def test_adversarial_destroyed_key_refused() -> None:
    """Assert crypto-shredded key in KeyRing cannot be used (KEY_DESTROYED)."""
    ring = KeyRing()
    ring.add_key("key-ephemeral", os.urandom(32))

    # Key is valid
    assert len(ring.get_key("key-ephemeral")) == 32

    # Destroy key
    ring.destroy_key("key-ephemeral")

    with pytest.raises(EncryptedLogError) as excinfo:
        ring.get_key("key-ephemeral")

    assert excinfo.value.reason_code == RC_KEY_DESTROYED


def test_adversarial_invalid_key_length() -> None:
    """Assert invalid key lengths are refused (KEY_INVALID)."""
    record = _sample_audit_record()

    # 10 bytes is invalid for AES (must be 16, 24, or 32)
    with pytest.raises(EncryptedLogError) as excinfo:
        encrypt_audit_record(record, b"short_key!", algorithm=ALG_AES_GCM)

    assert excinfo.value.reason_code == RC_KEY_INVALID


def test_adversarial_unsupported_algorithm() -> None:
    """Assert requesting unsupported cipher algorithm is refused (ALGORITHM_UNSUPPORTED)."""
    record = _sample_audit_record()
    key = os.urandom(32)

    with pytest.raises(EncryptedLogError) as excinfo:
        encrypt_audit_record(record, key, algorithm="DES-EDE3-CBC")

    assert excinfo.value.reason_code == RC_ALGORITHM_UNSUPPORTED
