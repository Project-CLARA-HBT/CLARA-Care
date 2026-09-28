"""Minimal Read-Set Token definition, canonicalization, and HMAC signing.

Provides the experimental token construction for E02 alternative baseline
comparator studies (MIN_READSET_TOKEN and HMAC_READSET_TOKEN).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from clara_api.glhs.canonical_json import (
    CANONICALIZATION_PROFILE,
    canonical_json_bytes,
    canonicalize_json,
    fast_canonical_digest,
)

MIN_TOKEN_SCHEMA = "minimal-readset-token.v1"
HMAC_TOKEN_SCHEMA = "hmac-readset-token.v1"
MINIMAL_TOKEN_SCHEMA = MIN_TOKEN_SCHEMA

DEFAULT_HMAC_KEY_ID = "glhs-e02-test-key-1"
DEFAULT_HMAC_SECRET = b"glhs-e02-comparator-study-experiment-hmac-secret-20260928"


def compute_evidence_commitment(evidence_ids: Sequence[str] | set[str]) -> str:
    """Compute deterministic SHA-256 commitment over canonical sorted evidence IDs."""
    sorted_ids = sorted(set(evidence_ids))
    payload = json.dumps(sorted_ids, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StateDependency:
    """Single domain/semantic key state version dependency."""

    key: str
    observed_version: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "observed_version": self.observed_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StateDependency:
        return cls(
            key=str(data["key"]),
            observed_version=int(data["observed_version"]),
        )


@dataclass(frozen=True)
class MinReadsetToken:
    """Compact unsigned read-set token containing only fields necessary to test minimal binding."""

    schema: str
    profile_id: str
    actor_id: str
    actor_role: str
    purpose: str
    task: str
    snapshot_id: str
    snapshot_digest: str
    evidence_commitment: str
    state_dependencies: tuple[StateDependency, ...]
    policy_version: str
    consent_version: str
    expires_at: str
    disclosed_evidence_ids: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        doc: dict[str, Any] = {
            "schema": self.schema,
            "profile_id": self.profile_id,
            "actor_id": self.actor_id,
            "actor_role": self.actor_role,
            "purpose": self.purpose,
            "task": self.task,
            "snapshot_id": self.snapshot_id,
            "snapshot_digest": self.snapshot_digest,
            "evidence_commitment": self.evidence_commitment,
            "state_dependencies": [dep.to_dict() for dep in self.state_dependencies],
            "policy_version": self.policy_version,
            "consent_version": self.consent_version,
            "expires_at": self.expires_at,
        }
        if self.disclosed_evidence_ids:
            doc["disclosed_evidence_ids"] = list(self.disclosed_evidence_ids)
        return doc

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MinReadsetToken:
        deps = tuple(
            dep if isinstance(dep, StateDependency) else StateDependency.from_dict(dep)
            for dep in data.get("state_dependencies", [])
        )
        ev_ids = tuple(sorted(data.get("disclosed_evidence_ids", [])))
        return cls(
            schema=data.get("schema", MIN_TOKEN_SCHEMA),
            profile_id=str(data["profile_id"]),
            actor_id=str(data["actor_id"]),
            actor_role=str(data["actor_role"]),
            purpose=str(data["purpose"]),
            task=str(data["task"]),
            snapshot_id=str(data["snapshot_id"]),
            snapshot_digest=str(data["snapshot_digest"]),
            evidence_commitment=str(data["evidence_commitment"]),
            state_dependencies=deps,
            policy_version=str(data.get("policy_version", "commitloop.v1")),
            consent_version=str(data.get("consent_version", "consent.v1")),
            expires_at=str(data["expires_at"]),
            disclosed_evidence_ids=ev_ids,
        )

    def to_canonical_json(self) -> str:
        """Serialize token to canonical JSON string."""
        return canonicalize_json(self.to_dict(), profile=CANONICALIZATION_PROFILE)

    def to_canonical_bytes(self) -> bytes:
        """Serialize token to canonical bytes per GLHS canonical JSON profile."""
        return canonical_json_bytes(self.to_dict(), profile=CANONICALIZATION_PROFILE)

    @classmethod
    def from_json(cls, json_str: str) -> MinReadsetToken:
        data = json.loads(json_str)
        return cls.from_dict(data)

    def byte_size(self) -> int:
        """Return byte count of canonically serialized token."""
        return len(self.to_canonical_bytes())

    def compute_token_digest(self) -> str:
        """SHA-256 digest of canonically serialized token."""
        return fast_canonical_digest(self.to_dict(), profile=CANONICALIZATION_PROFILE)

    def canonical_digest(self) -> str:
        return self.compute_token_digest()


@dataclass(frozen=True)
class HmacReadsetToken(MinReadsetToken):
    """Authenticated read-set token containing HMAC-SHA256 signature."""

    signature: str = ""
    signature_algorithm: str = "HMAC-SHA256"
    key_id: str = DEFAULT_HMAC_KEY_ID

    def to_dict(self) -> dict[str, Any]:
        doc = super().to_dict()
        doc["signature"] = self.signature
        doc["signature_algorithm"] = self.signature_algorithm
        doc["key_id"] = self.key_id
        return doc

    def to_unsigned_dict(self) -> dict[str, Any]:
        doc = super().to_dict()
        doc["schema"] = MIN_TOKEN_SCHEMA
        return doc

    def to_unsigned_canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_unsigned_dict(), profile=CANONICALIZATION_PROFILE)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HmacReadsetToken:
        deps = tuple(
            dep if isinstance(dep, StateDependency) else StateDependency.from_dict(dep)
            for dep in data.get("state_dependencies", [])
        )
        ev_ids = tuple(sorted(data.get("disclosed_evidence_ids", [])))
        return cls(
            schema=data.get("schema", HMAC_TOKEN_SCHEMA),
            profile_id=str(data["profile_id"]),
            actor_id=str(data["actor_id"]),
            actor_role=str(data["actor_role"]),
            purpose=str(data["purpose"]),
            task=str(data["task"]),
            snapshot_id=str(data["snapshot_id"]),
            snapshot_digest=str(data["snapshot_digest"]),
            evidence_commitment=str(data["evidence_commitment"]),
            state_dependencies=deps,
            policy_version=str(data.get("policy_version", "commitloop.v1")),
            consent_version=str(data.get("consent_version", "consent.v1")),
            expires_at=str(data["expires_at"]),
            disclosed_evidence_ids=ev_ids,
            signature=str(data.get("signature", "")),
            signature_algorithm=str(data.get("signature_algorithm", "HMAC-SHA256")),
            key_id=str(data.get("key_id", DEFAULT_HMAC_KEY_ID)),
        )

    def verify_hmac(self, key: bytes = DEFAULT_HMAC_SECRET) -> bool:
        """Verify HMAC-SHA256 signature against key."""
        if not self.signature:
            return False
        computed = hmac.new(key, self.to_unsigned_canonical_bytes(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(self.signature, computed)


# Alias for backward compatibility
MinimalReadsetToken = MinReadsetToken


def generate_min_readset_token(
    *,
    profile_id: str | int,
    actor_id: str | int,
    actor_role: str,
    purpose: str,
    task: str,
    snapshot_id: str,
    snapshot_digest: str,
    disclosed_evidence_ids: Sequence[str] | set[str] | None = None,
    evidence_ids: Sequence[str] | set[str] | None = None,
    state_dependencies: Sequence[StateDependency | dict[str, Any]] | None = None,
    policy_version: str = "commitloop.v1",
    consent_version: str = "medical_disclaimer:v1",
    expires_at: str | datetime | None = None,
) -> MinReadsetToken:
    """Factory creating an unsigned MinReadsetToken."""
    ev_ids = tuple(sorted(set(disclosed_evidence_ids or evidence_ids or ())))
    commitment = compute_evidence_commitment(ev_ids)

    if state_dependencies is None:
        deps = (StateDependency(key="observations:default", observed_version=1),)
    else:
        deps = tuple(
            dep if isinstance(dep, StateDependency) else StateDependency.from_dict(dep)
            for dep in state_dependencies
        )

    if expires_at is None:
        exp_str = (datetime.now(UTC) + timedelta(days=365)).isoformat()
    elif isinstance(expires_at, datetime):
        exp_str = expires_at.astimezone(UTC).isoformat()
    else:
        exp_str = str(expires_at)

    return MinReadsetToken(
        schema=MIN_TOKEN_SCHEMA,
        profile_id=str(profile_id),
        actor_id=str(actor_id),
        actor_role=actor_role,
        purpose=purpose,
        task=task,
        snapshot_id=snapshot_id,
        snapshot_digest=snapshot_digest,
        evidence_commitment=commitment,
        state_dependencies=deps,
        policy_version=policy_version,
        consent_version=consent_version,
        expires_at=exp_str,
        disclosed_evidence_ids=ev_ids,
    )


create_minimal_token = generate_min_readset_token


def generate_hmac_readset_token(
    *,
    profile_id: str | int,
    actor_id: str | int,
    actor_role: str,
    purpose: str,
    task: str,
    snapshot_id: str,
    snapshot_digest: str,
    hmac_key: bytes = DEFAULT_HMAC_SECRET,
    key_id: str = DEFAULT_HMAC_KEY_ID,
    disclosed_evidence_ids: Sequence[str] | set[str] | None = None,
    evidence_ids: Sequence[str] | set[str] | None = None,
    state_dependencies: Sequence[StateDependency | dict[str, Any]] | None = None,
    policy_version: str = "commitloop.v1",
    consent_version: str = "medical_disclaimer:v1",
    expires_at: str | datetime | None = None,
) -> HmacReadsetToken:
    """Factory creating a signed HmacReadsetToken."""
    base_tok = generate_min_readset_token(
        profile_id=profile_id,
        actor_id=actor_id,
        actor_role=actor_role,
        purpose=purpose,
        task=task,
        snapshot_id=snapshot_id,
        snapshot_digest=snapshot_digest,
        disclosed_evidence_ids=disclosed_evidence_ids,
        evidence_ids=evidence_ids,
        state_dependencies=state_dependencies,
        policy_version=policy_version,
        consent_version=consent_version,
        expires_at=expires_at,
    )
    sig = hmac.new(hmac_key, base_tok.to_canonical_bytes(), hashlib.sha256).hexdigest()

    return HmacReadsetToken(
        schema=HMAC_TOKEN_SCHEMA,
        profile_id=base_tok.profile_id,
        actor_id=base_tok.actor_id,
        actor_role=base_tok.actor_role,
        purpose=base_tok.purpose,
        task=base_tok.task,
        snapshot_id=base_tok.snapshot_id,
        snapshot_digest=base_tok.snapshot_digest,
        evidence_commitment=base_tok.evidence_commitment,
        state_dependencies=base_tok.state_dependencies,
        policy_version=base_tok.policy_version,
        consent_version=base_tok.consent_version,
        expires_at=base_tok.expires_at,
        disclosed_evidence_ids=base_tok.disclosed_evidence_ids,
        signature=sig,
        signature_algorithm="HMAC-SHA256",
        key_id=key_id,
    )


def sign_token(
    token: MinReadsetToken,
    secret_key: bytes = DEFAULT_HMAC_SECRET,
    key_id: str = DEFAULT_HMAC_KEY_ID,
) -> HmacReadsetToken:
    """Sign an existing MinReadsetToken to produce an HmacReadsetToken."""
    sig = hmac.new(secret_key, token.to_canonical_bytes(), hashlib.sha256).hexdigest()
    return HmacReadsetToken(
        schema=HMAC_TOKEN_SCHEMA,
        profile_id=token.profile_id,
        actor_id=token.actor_id,
        actor_role=token.actor_role,
        purpose=token.purpose,
        task=token.task,
        snapshot_id=token.snapshot_id,
        snapshot_digest=token.snapshot_digest,
        evidence_commitment=token.evidence_commitment,
        state_dependencies=token.state_dependencies,
        policy_version=token.policy_version,
        consent_version=token.consent_version,
        expires_at=token.expires_at,
        disclosed_evidence_ids=token.disclosed_evidence_ids,
        signature=sig,
        signature_algorithm="HMAC-SHA256",
        key_id=key_id,
    )


def verify_token_signature(
    token: MinReadsetToken | HmacReadsetToken,
    secret_key: bytes = DEFAULT_HMAC_SECRET,
) -> bool:
    """Verify HMAC signature."""
    if not isinstance(token, HmacReadsetToken):
        return False
    return token.verify_hmac(secret_key)
