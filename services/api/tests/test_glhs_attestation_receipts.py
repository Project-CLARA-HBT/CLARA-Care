"""Unit tests for GLHS Provider Receipts Abstraction Layer (attestation_receipts.py)."""

import base64
import hmac
import json
from datetime import UTC, datetime

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from clara_api.glhs.attestation_receipts import (
    APPLICATION_ENVELOPE_ONLY,
    PROVIDER_ATTESTATION_SCHEMA,
    PROVIDER_EXECUTION_ATTESTED,
    PROVIDER_RECEIPT_VERIFIED,
    TRANSPORT_DISPATCH,
    TRANSPORT_DISPATCH_ATTESTED,
    ProviderReceipt,
    attestation_level_for_binding,
    evaluate_provider_attestation,
    parse_provider_receipt,
    verify_provider_receipt,
)


def _generate_ed25519_keypair():
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    return priv, pub


def test_provider_receipt_dataclass_and_serialization():
    now = datetime(2026, 9, 30, 12, 0, 0, tzinfo=UTC)
    receipt = ProviderReceipt(
        provider="deepseek",
        request_digest="abc123request",
        response_digest="def456response",
        model_id="deepseek-chat",
        timestamp=now,
        key_id="deepseek-key-1",
    )
    assert receipt.schema == PROVIDER_ATTESTATION_SCHEMA
    assert receipt.provider == "deepseek"
    assert receipt.request_digest == "abc123request"
    assert receipt.response_digest == "def456response"

    d = receipt.to_dict()
    assert d["provider"] == "deepseek"
    assert d["timestamp"] == now.isoformat()

    canon_json = receipt.to_canonical_json()
    assert isinstance(canon_json, str)
    assert "abc123request" in canon_json

    canon_bytes = receipt.to_canonical_bytes()
    assert isinstance(canon_bytes, bytes)

    signing_bytes = receipt.signing_bytes()
    assert isinstance(signing_bytes, bytes)
    assert b"signature" not in signing_bytes


def test_parse_provider_receipt_direct_dict():
    raw = {
        "schema": "clara.provider-attestation.v1",
        "provider": "deepseek",
        "request_digest": "req_digest_111",
        "model_id": "deepseek-reasoner",
        "key_id": "k1",
        "signature": "sig123",
    }
    parsed = parse_provider_receipt(raw)
    assert parsed is not None
    assert parsed.provider == "deepseek"
    assert parsed.request_digest == "req_digest_111"
    assert parsed.model_id == "deepseek-reasoner"
    assert parsed.signature == "sig123"


def test_parse_provider_receipt_from_headers_case_insensitive():
    inner_receipt = {
        "provider": "deepseek",
        "request_digest": "req_header_222",
        "model_id": "deepseek-chat",
    }

    # Header as json string
    headers1 = {"X-Provider-Receipt": json.dumps(inner_receipt)}
    p1 = parse_provider_receipt(headers1)
    assert p1 is not None
    assert p1.request_digest == "req_header_222"

    # Header with lowercase key and base64 encoded json
    b64_str = base64.b64encode(json.dumps(inner_receipt).encode()).decode()
    headers2 = {"x-provider-receipt": b64_str}
    p2 = parse_provider_receipt(headers2)
    assert p2 is not None
    assert p2.request_digest == "req_header_222"

    # Alternative header name
    headers3 = {"x-clara-provider-receipt": json.dumps(inner_receipt)}
    p3 = parse_provider_receipt(headers3)
    assert p3 is not None
    assert p3.request_digest == "req_header_222"


def test_parse_provider_receipt_from_body_wrapper():
    inner = {
        "provider": "anthropic",
        "request_digest": "req_body_333",
        "signature": "sig_body",
    }
    body = {"provider_receipt": inner, "other_field": 42}
    p = parse_provider_receipt(body)
    assert p is not None
    assert p.provider == "anthropic"
    assert p.request_digest == "req_body_333"

    body_alt = {"receipt": json.dumps(inner)}
    p_alt = parse_provider_receipt(body_alt)
    assert p_alt is not None
    assert p_alt.provider == "anthropic"


def test_parse_provider_receipt_passthrough_and_empty():
    assert parse_provider_receipt(None) is None
    assert parse_provider_receipt("") is None
    assert parse_provider_receipt({}) is None
    assert parse_provider_receipt("invalid json") is None
    assert parse_provider_receipt({"random_key": "val"}) is None

    # Passthrough
    r = ProviderReceipt(provider="p", request_digest="r")
    assert parse_provider_receipt(r) is r


def test_verify_provider_receipt_ed25519():
    priv, pub = _generate_ed25519_keypair()
    receipt_no_sig = ProviderReceipt(
        provider="deepseek",
        request_digest="req_digest_valid",
        response_digest="resp_digest_valid",
        model_id="deepseek-v3",
        key_id="ds-key-1",
    )
    sig_bytes = priv.sign(receipt_no_sig.signing_bytes())
    sig_b64 = base64.b64encode(sig_bytes).decode()

    receipt = ProviderReceipt(
        provider=receipt_no_sig.provider,
        request_digest=receipt_no_sig.request_digest,
        response_digest=receipt_no_sig.response_digest,
        model_id=receipt_no_sig.model_id,
        key_id=receipt_no_sig.key_id,
        signature=sig_b64,
    )

    # Valid verification with public key object
    keys = {"ds-key-1": pub}
    assert verify_provider_receipt(
        receipt,
        expected_request_digest="req_digest_valid",
        expected_response_digest="resp_digest_valid",
        public_keys=keys,
    ) is True

    # Valid verification with normalized "sha256:" prefix
    assert verify_provider_receipt(
        receipt,
        expected_request_digest="sha256:req_digest_valid",
        public_keys=keys,
    ) is True

    # Tampered request digest
    assert verify_provider_receipt(
        receipt,
        expected_request_digest="wrong_request_digest",
        public_keys=keys,
    ) is False

    # Tampered response digest
    assert verify_provider_receipt(
        receipt,
        expected_request_digest="req_digest_valid",
        expected_response_digest="wrong_response_digest",
        public_keys=keys,
    ) is False

    # Wrong public key
    _, other_pub = _generate_ed25519_keypair()
    assert verify_provider_receipt(
        receipt,
        expected_request_digest="req_digest_valid",
        public_keys={"ds-key-1": other_pub},
    ) is False

    # Missing public key for key_id
    assert verify_provider_receipt(
        receipt,
        expected_request_digest="req_digest_valid",
        public_keys={"other-key": pub},
    ) is False


def test_verify_provider_receipt_pem_and_hmac():
    priv, pub = _generate_ed25519_keypair()
    pub_pem = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    receipt_no_sig = ProviderReceipt(
        provider="custom_provider",
        request_digest="req_pem",
        key_id="pem_key",
    )
    sig_b64 = base64.b64encode(priv.sign(receipt_no_sig.signing_bytes())).decode()
    receipt = ProviderReceipt(
        provider="custom_provider",
        request_digest="req_pem",
        key_id="pem_key",
        signature=sig_b64,
    )

    assert verify_provider_receipt(
        receipt,
        expected_request_digest="req_pem",
        public_keys={"pem_key": pub_pem.decode()},
    ) is True

    # HMAC key verification
    receipt_hmac_no_sig = ProviderReceipt(
        provider="custom_provider",
        request_digest="req_pem",
        key_id="hmac_key",
    )
    hmac_secret = b"my_super_secret_key_123"
    hmac_sig = hmac.new(hmac_secret, receipt_hmac_no_sig.signing_bytes(), "sha256").digest()
    receipt_hmac = ProviderReceipt(
        provider="custom_provider",
        request_digest="req_pem",
        key_id="hmac_key",
        signature=base64.b64encode(hmac_sig).decode(),
    )
    assert verify_provider_receipt(
        receipt_hmac,
        expected_request_digest="req_pem",
        public_keys={"hmac_key": hmac_secret},
    ) is True


def test_unsupported_provider_clean_reporting():
    # Unsupported provider without signature or keys returns False without errors
    unsupported_receipt = ProviderReceipt(
        provider="unsupported_llm",
        request_digest="req_123",
    )
    assert verify_provider_receipt(unsupported_receipt, expected_request_digest="req_123") is False
    assert verify_provider_receipt(None) is False


def test_attestation_level_for_binding_hierarchy():
    # L0: Application envelope only (no transport payload or status completed)
    binding_l0 = {"status": "PENDING"}
    assert attestation_level_for_binding(binding_l0) == APPLICATION_ENVELOPE_ONLY
    assert attestation_level_for_binding(None) == APPLICATION_ENVELOPE_ONLY

    # L1: Transport dispatch attested (request envelope or transport payload digest present)
    binding_l1 = {
        "request_envelope_digest": "h_trans_abc",
        "provider": "deepseek",
        "status": "COMPLETED",
    }
    assert attestation_level_for_binding(binding_l1) == TRANSPORT_DISPATCH_ATTESTED
    assert TRANSPORT_DISPATCH == TRANSPORT_DISPATCH_ATTESTED

    # L2: Provider receipt verified
    binding_l2 = {
        "request_envelope_digest": "h_trans_abc",
        "provider": "deepseek",
        "status": "COMPLETED",
        "provider_receipt_verified": True,
    }
    assert attestation_level_for_binding(binding_l2) == PROVIDER_RECEIPT_VERIFIED

    # L3: Provider execution attested (TEE / ZKML proof)
    binding_l3 = {
        "request_envelope_digest": "h_trans_abc",
        "provider": "deepseek",
        "status": "COMPLETED",
        "provider_receipt_verified": True,
        "execution_proof": "tee_quote_sgx_v1_xyz",
    }
    assert attestation_level_for_binding(binding_l3) == PROVIDER_EXECUTION_ATTESTED


def test_evaluate_provider_attestation_end_to_end():
    priv, pub = _generate_ed25519_keypair()
    req_digest = "digest_req_999"

    # Unsupported provider call (no receipt header)
    binding_standard = {
        "provider": "deepseek",
        "status": "COMPLETED",
        "request_envelope_digest": req_digest,
    }
    verified, level, parsed_receipt = evaluate_provider_attestation(
        binding=binding_standard,
        raw_headers_or_body=None,
    )
    assert verified is False
    assert parsed_receipt is None
    assert level == TRANSPORT_DISPATCH

    # Supported provider call with valid receipt header
    receipt_data = ProviderReceipt(
        provider="governed_provider",
        request_digest=req_digest,
        key_id="gov-key",
    )
    sig_b64 = base64.b64encode(priv.sign(receipt_data.signing_bytes())).decode()

    headers = {
        "X-Provider-Receipt": json.dumps({
            "provider": "governed_provider",
            "request_digest": req_digest,
            "key_id": "gov-key",
            "signature": sig_b64,
        })
    }

    verified, level, parsed_receipt = evaluate_provider_attestation(
        binding=binding_standard,
        raw_headers_or_body=headers,
        public_keys={"gov-key": pub},
    )
    assert verified is True
    assert parsed_receipt is not None
    assert parsed_receipt.provider == "governed_provider"
    assert level == PROVIDER_RECEIPT_VERIFIED
