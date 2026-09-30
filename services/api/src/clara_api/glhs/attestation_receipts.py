"""GLHS Provider Receipts Abstraction Layer and Attestation Hierarchy.

Provides typed structures and cryptographic verification for provider receipts,
mapping inference context bindings to attestation levels L0-L3 per GLHS R4 formal semantics:
- L0: APPLICATION_ENVELOPE_ONLY
- L1: TRANSPORT_DISPATCH_ATTESTED (short alias: TRANSPORT_DISPATCH)
- L2: PROVIDER_RECEIPT_VERIFIED
- L3: PROVIDER_EXECUTION_ATTESTED
"""

from __future__ import annotations

import base64
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PublicKey,
)

from clara_api.glhs.canonical_json import (
    canonical_json_bytes,
    canonicalize_json,
)


class AttestationLevel(str, Enum):
    """GLHS R4 attestation hierarchy levels L0-L3."""

    APPLICATION_ENVELOPE_ONLY = "APPLICATION_ENVELOPE_ONLY"
    TRANSPORT_DISPATCH_ATTESTED = "TRANSPORT_DISPATCH_ATTESTED"
    PROVIDER_RECEIPT_VERIFIED = "PROVIDER_RECEIPT_VERIFIED"
    PROVIDER_EXECUTION_ATTESTED = "PROVIDER_EXECUTION_ATTESTED"


class _AttestationLevelStr(str):
    """String subclass that treats 'TRANSPORT_DISPATCH' and 'TRANSPORT_DISPATCH_ATTESTED' as equivalent."""

    def __eq__(self, other: object) -> bool:
        if str.__eq__(self, str(other)):
            return True
        val = str(self)
        oth = str(other)
        return val in ("TRANSPORT_DISPATCH_ATTESTED", "TRANSPORT_DISPATCH") and oth in (
            "TRANSPORT_DISPATCH_ATTESTED",
            "TRANSPORT_DISPATCH",
        )

    def __hash__(self) -> int:
        return hash(str(self))


# Exported string constants
APPLICATION_ENVELOPE_ONLY = AttestationLevel.APPLICATION_ENVELOPE_ONLY.value
TRANSPORT_DISPATCH_ATTESTED = _AttestationLevelStr(AttestationLevel.TRANSPORT_DISPATCH_ATTESTED.value)
TRANSPORT_DISPATCH = _AttestationLevelStr("TRANSPORT_DISPATCH")
PROVIDER_RECEIPT_VERIFIED = AttestationLevel.PROVIDER_RECEIPT_VERIFIED.value
PROVIDER_EXECUTION_ATTESTED = AttestationLevel.PROVIDER_EXECUTION_ATTESTED.value

PROVIDER_ATTESTATION_SCHEMA = "clara.provider-attestation.v1"


@dataclass(frozen=True)
class ProviderReceipt:
    """Typed representation of a cryptographic provider attestation receipt."""

    provider: str
    request_digest: str
    schema: str = PROVIDER_ATTESTATION_SCHEMA
    provider_request_id: str | None = None
    response_digest: str | None = None
    model_id: str | None = None
    timestamp: str | datetime | None = None
    key_id: str | None = None
    signature: str | None = None
    execution_proof: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert ProviderReceipt to a primitive dictionary."""
        res: dict[str, Any] = {
            "schema": self.schema,
            "provider": self.provider,
            "request_digest": self.request_digest,
        }
        if self.provider_request_id is not None:
            res["provider_request_id"] = self.provider_request_id
        if self.response_digest is not None:
            res["response_digest"] = self.response_digest
        if self.model_id is not None:
            res["model_id"] = self.model_id
        if self.timestamp is not None:
            if isinstance(self.timestamp, datetime):
                res["timestamp"] = self.timestamp.isoformat()
            else:
                res["timestamp"] = str(self.timestamp)
        if self.key_id is not None:
            res["key_id"] = self.key_id
        if self.signature is not None:
            res["signature"] = self.signature
        if self.execution_proof is not None:
            res["execution_proof"] = self.execution_proof
        if self.metadata:
            res["metadata"] = self.metadata
        return res

    def signing_payload(self) -> dict[str, Any]:
        """Return canonical payload dictionary covered by receipt signature."""
        payload: dict[str, Any] = {
            "schema": self.schema,
            "provider": self.provider,
            "request_digest": self.request_digest,
        }
        if self.provider_request_id is not None:
            payload["provider_request_id"] = self.provider_request_id
        if self.response_digest is not None:
            payload["response_digest"] = self.response_digest
        if self.model_id is not None:
            payload["model_id"] = self.model_id
        if self.timestamp is not None:
            if isinstance(self.timestamp, datetime):
                payload["timestamp"] = self.timestamp.isoformat()
            else:
                payload["timestamp"] = str(self.timestamp)
        if self.key_id is not None:
            payload["key_id"] = self.key_id
        if self.execution_proof is not None:
            payload["execution_proof"] = self.execution_proof
        return payload

    def signing_bytes(self) -> bytes:
        """Return byte representation covered by signature."""
        return canonical_json_bytes(self.signing_payload())

    def to_canonical_json(self) -> str:
        """Serialize complete receipt to canonical JSON."""
        return canonicalize_json(self.to_dict())

    def to_canonical_bytes(self) -> bytes:
        """Serialize complete receipt to canonical bytes."""
        return canonical_json_bytes(self.to_dict())


def _normalize_digest(digest: str | None) -> str | None:
    if digest is None:
        return None
    d = str(digest).strip()
    if d.startswith("sha256:"):
        return d[7:]
    return d


def _dict_to_provider_receipt(d: dict[str, Any]) -> ProviderReceipt | None:
    schema = str(d.get("schema", PROVIDER_ATTESTATION_SCHEMA))
    provider = d.get("provider")
    request_digest = (
        d.get("request_digest")
        or d.get("request_hash")
        or d.get("transport_payload_digest")
        or d.get("request_envelope_digest")
    )

    if not provider or not request_digest:
        return None

    provider_req_id = d.get("provider_request_id") or d.get("request_id")
    response_digest = d.get("response_digest") or d.get("response_hash")
    model_id = d.get("model_id") or d.get("reported_model_id")
    timestamp = d.get("timestamp") or d.get("created_at")
    key_id = d.get("key_id")
    signature = d.get("signature")
    execution_proof = d.get("execution_proof") or d.get("pi_exec")
    metadata = d.get("metadata") if isinstance(d.get("metadata"), dict) else {}

    return ProviderReceipt(
        schema=schema,
        provider=str(provider),
        request_digest=str(request_digest),
        provider_request_id=str(provider_req_id) if provider_req_id is not None else None,
        response_digest=str(response_digest) if response_digest is not None else None,
        model_id=str(model_id) if model_id is not None else None,
        timestamp=timestamp,
        key_id=str(key_id) if key_id is not None else None,
        signature=str(signature) if signature is not None else None,
        execution_proof=str(execution_proof) if execution_proof is not None else None,
        metadata=dict(metadata),
    )


def parse_provider_receipt(raw_headers_or_body: Any) -> ProviderReceipt | None:
    """Extract and parse ProviderReceipt if present in headers, body, or JSON string/bytes.

    Returns None cleanly if raw_headers_or_body is empty, unparseable, or lacks
    required receipt fields. Unsupported providers cleanly yield None.
    """
    if raw_headers_or_body is None:
        return None

    if isinstance(raw_headers_or_body, ProviderReceipt):
        return raw_headers_or_body

    data = raw_headers_or_body

    if isinstance(data, (str, bytes)):
        if isinstance(data, bytes):
            try:
                data = data.decode("utf-8")
            except UnicodeDecodeError:
                return None
        data_str = data.strip()
        if not data_str:
            return None
        if not data_str.startswith("{"):
            try:
                decoded = base64.b64decode(data_str).decode("utf-8")
                if decoded.startswith("{"):
                    data_str = decoded
            except Exception:
                pass
        try:
            data = json.loads(data_str)
        except Exception:
            return None

    if not isinstance(data, Mapping):
        return None

    # 1. Check HTTP header format (case-insensitive keys)
    header_keys = (
        "x-provider-receipt",
        "provider-receipt",
        "x-clara-provider-receipt",
        "x-attestation-receipt",
        "attestation-receipt",
    )
    for k, v in data.items():
        if isinstance(k, str) and k.lower() in header_keys:
            parsed = parse_provider_receipt(v)
            if parsed is not None:
                return parsed

    # 2. Check wrapper keys inside JSON request/response body
    wrapper_keys = (
        "provider_receipt",
        "attestation_receipt",
        "receipt",
        "provider_attestation",
    )
    for key in wrapper_keys:
        if key in data and data[key] is not None:
            sub_val = data[key]
            if isinstance(sub_val, dict):
                parsed = _dict_to_provider_receipt(sub_val)
                if parsed is not None:
                    return parsed
            parsed = parse_provider_receipt(sub_val)
            if parsed is not None:
                return parsed

    # 3. Check if dictionary itself is a receipt
    return _dict_to_provider_receipt(dict(data))


def verify_provider_receipt(
    receipt: ProviderReceipt | None,
    expected_request_digest: str | None = None,
    expected_response_digest: str | None = None,
    public_keys: dict[str, Any] | None = None,
    allowed_clock_skew_seconds: float = 300.0,
) -> bool:
    """Verify cryptographic provider receipt against expected digests and public keys.

    Returns False for None, missing signatures, mismatching request/response digests,
    unsupported/missing provider keys, or invalid cryptographic signatures.
    """
    if receipt is None:
        return False

    if expected_request_digest is not None:
        norm_actual = _normalize_digest(receipt.request_digest)
        norm_expected = _normalize_digest(expected_request_digest)
        if norm_actual != norm_expected:
            return False

    if expected_response_digest is not None:
        if receipt.response_digest is None:
            return False
        norm_resp_actual = _normalize_digest(receipt.response_digest)
        norm_resp_expected = _normalize_digest(expected_response_digest)
        if norm_resp_actual != norm_resp_expected:
            return False

    if receipt.signature is None:
        return False

    if public_keys is None:
        return False

    key_id = receipt.key_id or "default"
    key_obj = public_keys.get(key_id) or public_keys.get(receipt.provider) or public_keys.get("default")
    if key_obj is None:
        return False

    sig_bytes: bytes
    try:
        sig_bytes = base64.b64decode(receipt.signature)
    except Exception:
        return False

    payload_bytes = receipt.signing_bytes()

    # Signature verification for Ed25519 key / HMAC key / PEM key
    try:
        if isinstance(key_obj, Ed25519PublicKey):
            key_obj.verify(sig_bytes, payload_bytes)
            return True

        if isinstance(key_obj, (str, bytes)):
            kb = key_obj.encode() if isinstance(key_obj, str) else key_obj

            # PEM format Ed25519 public key
            if b"-----BEGIN PUBLIC KEY-----" in kb:
                pub_key = serialization.load_pem_public_key(kb)
                if isinstance(pub_key, Ed25519PublicKey):
                    pub_key.verify(sig_bytes, payload_bytes)
                    return True
                return False

            # Raw 32-byte or base64-encoded Ed25519 key
            if len(kb) == 32:
                pub_key = Ed25519PublicKey.from_public_bytes(kb)
                pub_key.verify(sig_bytes, payload_bytes)
                return True

            try:
                raw_b64 = base64.b64decode(kb)
                if len(raw_b64) == 32:
                    pub_key = Ed25519PublicKey.from_public_bytes(raw_b64)
                    pub_key.verify(sig_bytes, payload_bytes)
                    return True
            except Exception:
                pass

            # Fallback to HMAC-SHA256 comparison
            expected_hmac = hmac.new(kb, payload_bytes, "sha256").digest()
            if hmac.compare_digest(sig_bytes, expected_hmac):
                return True

    except (InvalidSignature, ValueError, TypeError):
        return False

    return False


def attestation_level_for_binding(binding: Any) -> str:
    """Map binding (GlhsInferenceContextBinding or dictionary) to GLHS attestation level L0-L3.

    Returns:
    - APPLICATION_ENVELOPE_ONLY (L0)
    - TRANSPORT_DISPATCH_ATTESTED (L1)
    - PROVIDER_RECEIPT_VERIFIED (L2)
    - PROVIDER_EXECUTION_ATTESTED (L3)

    Unsupported providers cleanly yield TRANSPORT_DISPATCH_ATTESTED (L1) when transport
    dispatch is recorded, without fabricating receipts.
    """
    if binding is None:
        return AttestationLevel.APPLICATION_ENVELOPE_ONLY.value

    def _get(attr: str) -> Any:
        if isinstance(binding, Mapping):
            return binding.get(attr)
        return getattr(binding, attr, None)

    explicit_level = _get("attestation_level")
    if explicit_level:
        el_str = str(explicit_level).upper()
        if el_str in ("L3", AttestationLevel.PROVIDER_EXECUTION_ATTESTED.value):
            return AttestationLevel.PROVIDER_EXECUTION_ATTESTED.value
        if el_str in ("L2", AttestationLevel.PROVIDER_RECEIPT_VERIFIED.value):
            return AttestationLevel.PROVIDER_RECEIPT_VERIFIED.value
        if el_str in ("L1", "TRANSPORT_DISPATCH", AttestationLevel.TRANSPORT_DISPATCH_ATTESTED.value):
            return AttestationLevel.TRANSPORT_DISPATCH_ATTESTED.value
        if el_str in ("L0", "SERVER_PRE_DISPATCH", AttestationLevel.APPLICATION_ENVELOPE_ONLY.value):
            return AttestationLevel.APPLICATION_ENVELOPE_ONLY.value

    # L3: Hardware TEE / ZKML execution proof present
    has_exec_proof = bool(_get("execution_proof") or _get("execution_attestation") or _get("pi_exec"))
    if has_exec_proof:
        return AttestationLevel.PROVIDER_EXECUTION_ATTESTED.value

    # L2: Provider receipt verified
    receipt_verified = bool(_get("provider_receipt_verified") or _get("receipt_verified"))
    if receipt_verified:
        return AttestationLevel.PROVIDER_RECEIPT_VERIFIED.value

    receipt = _get("provider_receipt") or _get("receipt")
    if isinstance(receipt, ProviderReceipt) and receipt.signature and receipt_verified:
        return AttestationLevel.PROVIDER_RECEIPT_VERIFIED.value

    # L1: Egress transport payload digest recorded or consumed THSS completed
    has_req_env = bool(_get("request_envelope_digest") or _get("transport_payload_digest"))
    has_consumed = bool(_get("consumed_thss"))
    provider = _get("provider")
    status = _get("status")

    if has_req_env or has_consumed or (provider and status == "COMPLETED"):
        return AttestationLevel.TRANSPORT_DISPATCH_ATTESTED.value

    # L0: In-memory application envelope only
    return AttestationLevel.APPLICATION_ENVELOPE_ONLY.value


def evaluate_provider_attestation(
    binding: Any,
    raw_headers_or_body: Any = None,
    expected_request_digest: str | None = None,
    expected_response_digest: str | None = None,
    public_keys: dict[str, Any] | None = None,
) -> tuple[bool, str, ProviderReceipt | None]:
    """Evaluate provider receipt attestation status, level, and parsed receipt for a binding.

    For unsupported providers without receipts or verification, cleanly yields:
    (False, AttestationLevel.TRANSPORT_DISPATCH_ATTESTED.value, None)
    """
    receipt = parse_provider_receipt(raw_headers_or_body)
    verified = False
    if receipt is not None:
        req_digest = expected_request_digest
        if req_digest is None and binding is not None:
            if isinstance(binding, Mapping):
                req_digest = binding.get("transport_payload_digest") or binding.get("request_envelope_digest")
            else:
                req_digest = getattr(binding, "transport_payload_digest", None) or getattr(binding, "request_envelope_digest", None)

        resp_digest = expected_response_digest
        if resp_digest is None and binding is not None:
            if isinstance(binding, Mapping):
                resp_digest = binding.get("response_digest")
            else:
                resp_digest = getattr(binding, "response_digest", None)

        verified = verify_provider_receipt(
            receipt,
            expected_request_digest=req_digest,
            expected_response_digest=resp_digest,
            public_keys=public_keys,
        )

    if verified and receipt is not None:
        level = (
            AttestationLevel.PROVIDER_EXECUTION_ATTESTED.value
            if receipt.execution_proof
            else AttestationLevel.PROVIDER_RECEIPT_VERIFIED.value
        )
    else:
        level = attestation_level_for_binding(binding)

    return verified, level, receipt
