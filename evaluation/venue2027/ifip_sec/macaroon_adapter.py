"""CLARA-Care 2027 IFIP_SEC task IFIP_SEC-X05_macaroons_strong — genuine caveat-bound capability baseline.

Purpose
-------
In-process reference implementation of genuine caveat-bound capability credentials
(Macaroons: Cookies with Contextual Caveats for Decentralized Authorization in the
Cloud, NDSS 2014) serving blueprint arm B1/B2 for "Replay-Closed Authorization Across
Purpose, Delegation, and AI Proposal Lineage" (IFIP_SEC 2027).

It implements the task's contract:
- ``MacaroonAdapter`` class providing:
  - ``create_macaroon(root_key, identifier, location) -> Macaroon``
  - ``add_first_party_caveat(macaroon, caveat) -> Macaroon``
  - ``bind_proposal_lineage(macaroon, lineage_hash) -> Macaroon``
  - ``verify_macaroon(macaroon, root_key, check_context) -> MacaroonVerificationResult``
- Exact target contract from task specification:
  - ``authorize(token, caveats, tx) -> Verdict``
- Enforces tenant, purpose, epoch, proposal hash and online checking;
- Separates offline-only mode as an ablation;
- Implements full HMAC-SHA256 caveat verification chain.

Allowed input
-------------
Macaroon objects or serialized macaroon strings (canonical JSON or base64url),
cryptographic root key (>= 16 bytes), check context / transaction dictionaries
with claims (tenant, purpose, epoch, lineage_hash, etc.), and optional online
checkers or revocation stores.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes inside :class:`MacaroonVerificationResult`
(``OK``, ``CAVEAT_VERIFICATION_FAILED``, ``TOKEN_EXPIRED``, ``PURPOSE_MISMATCH``,
``TENANT_MISMATCH``, ``ACTOR_MISMATCH``, ``TASK_MISMATCH``, ``EPOCH_MISMATCH``,
``LINEAGE_HASH_MISMATCH``, ``ONLINE_CHECK_REQUIRED``, ``ONLINE_CHECK_FAILED``,
``REVOKED``, ``TOKEN_MALFORMED``, ``TOKEN_MISSING``, ``CONTEXT_KEY_TOO_SHORT``).
Never raises for verification or caveat faults.

Version
-------
``MACAROON_ADAPTER_VERSION = "1.0.0"``
"""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import hmac
import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Final

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.ifip_sec.baselines import (
    CAVEAT_KEYS,
    BaselineContext,
    build_caveat_chain,
)

MACAROON_ADAPTER_VERSION: Final[str] = "1.0.0"

#: Minimum HMAC key length in bytes.
_HMAC_KEY_MIN_BYTES: Final[int] = 16

#: Stable uppercase reason codes.
RC_OK: Final[str] = "OK"
RC_CAVEAT_VERIFICATION_FAILED: Final[str] = "CAVEAT_VERIFICATION_FAILED"
RC_TOKEN_EXPIRED: Final[str] = "TOKEN_EXPIRED"
RC_PURPOSE_MISMATCH: Final[str] = "PURPOSE_MISMATCH"
RC_TENANT_MISMATCH: Final[str] = "TENANT_MISMATCH"
RC_ACTOR_MISMATCH: Final[str] = "ACTOR_MISMATCH"
RC_TASK_MISMATCH: Final[str] = "TASK_MISMATCH"
RC_EPOCH_MISMATCH: Final[str] = "EPOCH_MISMATCH"
RC_LINEAGE_HASH_MISMATCH: Final[str] = "LINEAGE_HASH_MISMATCH"
RC_ONLINE_CHECK_REQUIRED: Final[str] = "ONLINE_CHECK_REQUIRED"
RC_ONLINE_CHECK_FAILED: Final[str] = "ONLINE_CHECK_FAILED"
RC_REVOKED: Final[str] = "REVOKED"
RC_TOKEN_MALFORMED: Final[str] = "TOKEN_MALFORMED"
RC_TOKEN_MISSING: Final[str] = "TOKEN_MISSING"
RC_CAVEAT_MALFORMED: Final[str] = "CAVEAT_MALFORMED"
RC_CONTEXT_KEY_TOO_SHORT: Final[str] = "CONTEXT_KEY_TOO_SHORT"


@dataclasses.dataclass(frozen=True)
class Macaroon:
    """Macaroon capability credential with HMAC-SHA256 caveat chain.

    Attributes:
        location: String indicating target service or domain.
        identifier: Public key identifier or macaroon ID.
        signature: Hex-encoded HMAC-SHA256 signature tag after all caveat attenuations.
        caveats: Tuple of contextual caveat predicates in order of application.
    """

    location: str
    identifier: str
    signature: str
    caveats: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "location": self.location,
            "identifier": self.identifier,
            "signature": self.signature,
            "caveats": list(self.caveats),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Macaroon:
        location = str(data.get("location", ""))
        identifier = str(data.get("identifier", ""))
        signature = str(data.get("signature", ""))
        if not identifier or not signature:
            raise ValueError("Macaroon data must contain non-empty identifier and signature")
        caveats_raw = data.get("caveats", ())
        if not isinstance(caveats_raw, Sequence):
            raise ValueError("caveats must be a sequence of strings")
        caveats = tuple(str(c) for c in caveats_raw)
        return cls(location=location, identifier=identifier, signature=signature, caveats=caveats)

    def serialize(self) -> str:
        """Serialize macaroon to a canonical URL-safe base64 string."""
        raw = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii")

    @classmethod
    def deserialize(cls, token: str) -> Macaroon:
        """Deserialize macaroon from base64url or JSON string."""
        if not isinstance(token, str) or not token.strip():
            raise ValueError("Token must be a non-empty string")
        stripped = token.strip()
        # Direct JSON decode attempt
        if stripped.startswith("{") and stripped.endswith("}"):
            payload = json.loads(stripped)
            return cls.from_dict(payload)
        padded = stripped + "=" * (-len(stripped) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
        return cls.from_dict(payload)

    @property
    def token_bytes(self) -> int:
        """Length of the serialized token in bytes (RQ3 marker)."""
        return len(self.serialize().encode("utf-8"))


@dataclasses.dataclass(frozen=True)
class MacaroonVerificationResult:
    """Outcome of macaroon verification and caveat evaluation.

    Attributes:
        valid: True if HMAC chain and all caveat predicates are satisfied.
        reason_code: Stable uppercase outcome or rejection reason code.
        caveats_verified: Count of caveats evaluated.
        online_checked: True if verification mode was online; False if offline.
        detail: Human-readable diagnostic details.
    """

    valid: bool
    reason_code: str
    caveats_verified: int = 0
    online_checked: bool = False
    detail: str = ""

    @property
    def allowed(self) -> bool:
        """Alias for valid to match authorization Verdict semantics."""
        return self.valid

    @property
    def is_valid(self) -> bool:
        """Convenience alias for valid."""
        return self.valid

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "reason_code": self.reason_code,
            "caveats_verified": self.caveats_verified,
            "online_checked": self.online_checked,
            "detail": self.detail,
        }

    def to_outcome(self) -> Outcome:
        """Convert into standard harness Outcome."""
        return Outcome(
            observed_outcome="ADMIT" if self.valid else "REJECT",
            counted_as_success=True,
            retriable=False,
            detail=self.reason_code,
        )


#: Task target contract alias: authorize(...) -> Verdict
Verdict = MacaroonVerificationResult


def parse_caveat(caveat: str) -> tuple[str, str, str]:
    """Parse a caveat predicate into (key, operator, value).

    Supported operators: <=, >=, ==, !=, <, >, =, :.
    Defaults to operator '=' if no delimiter is found.
    """
    for op in ("<=", ">=", "==", "!=", "<", ">", "=", ":"):
        if op in caveat:
            parts = caveat.split(op, 1)
            return parts[0].strip(), op, parts[1].strip()
    return caveat.strip(), "=", ""


class MacaroonAdapter:
    """Adapter wrapping Macaroon capability operations and caveat verification.

    Supports:
    - Creation and attenuation of Macaroons via HMAC-SHA256.
    - Proposal-lineage binding for AI proposal chains.
    - Verification against transaction contexts enforcing tenant, purpose,
      epoch, proposal lineage hash, and expiry.
    - Offline-only mode as an explicit ablation where online-required caveats
      are rejected and online checks are distinguished.
    """

    def __init__(self, mode: str = "online", offline_only: bool = False) -> None:
        if mode not in ("online", "offline"):
            raise ValueError(f"Invalid mode {mode!r}; expected 'online' or 'offline'")
        self.mode = "offline" if offline_only else mode
        self.offline_only = self.mode == "offline"

    @classmethod
    def create_macaroon(
        cls,
        root_key: bytes,
        identifier: str,
        location: str,
    ) -> Macaroon:
        """Create a new root macaroon with an initial HMAC-SHA256 signature.

        sig_0 = HMAC-SHA256(root_key, identifier)
        """
        if not isinstance(root_key, bytes | bytearray) or len(root_key) < _HMAC_KEY_MIN_BYTES:
            raise ValueError(f"root_key must be bytes of length >= {_HMAC_KEY_MIN_BYTES}")
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError("identifier must be a non-empty string")
        loc = str(location or "")
        sig = hmac.new(root_key, identifier.encode("utf-8"), hashlib.sha256).hexdigest()
        return Macaroon(location=loc, identifier=identifier, signature=sig, caveats=())

    @classmethod
    def add_first_party_caveat(
        cls,
        macaroon: Macaroon,
        caveat: str,
    ) -> Macaroon:
        """Attenuate macaroon by appending a first-party caveat to the HMAC chain.

        sig_i = HMAC-SHA256(sig_{i-1}, caveat)
        """
        if not isinstance(macaroon, Macaroon):
            raise ValueError("macaroon must be a Macaroon instance")
        if not isinstance(caveat, str) or not caveat.strip():
            raise ValueError("caveat must be a non-empty string")
        stripped = caveat.strip()
        prev_sig = bytes.fromhex(macaroon.signature)
        new_sig = hmac.new(prev_sig, stripped.encode("utf-8"), hashlib.sha256).hexdigest()
        return Macaroon(
            location=macaroon.location,
            identifier=macaroon.identifier,
            signature=new_sig,
            caveats=(*macaroon.caveats, stripped),
        )

    @classmethod
    def bind_proposal_lineage(
        cls,
        macaroon: Macaroon,
        lineage_hash: str,
    ) -> Macaroon:
        """Bind proposal lineage hash as a first-party caveat."""
        if not isinstance(lineage_hash, str) or not lineage_hash.strip():
            raise ValueError("lineage_hash must be a non-empty string")
        return cls.add_first_party_caveat(macaroon, f"lineage_hash = {lineage_hash.strip()}")

    @classmethod
    def from_baseline_caveats(
        cls,
        root_key: bytes,
        caveats: Mapping[str, str],
        *,
        identifier: str = "ifip-sec-b2",
        location: str = "clara.care",
    ) -> Macaroon:
        """Wrap baselines.py B2 caveat chain construction into a Macaroon object."""
        ctx = BaselineContext(hmac_key=root_key)
        signature = build_caveat_chain(caveats, ctx, root_identifier=identifier)
        ordered_caveats = tuple(f"{k}={caveats[k]}" for k in CAVEAT_KEYS if k in caveats)
        return Macaroon(
            location=location,
            identifier=identifier,
            signature=signature,
            caveats=ordered_caveats,
        )

    def verify_macaroon(
        self,
        macaroon: Macaroon | str | Mapping[str, Any],
        root_key: bytes,
        check_context: Mapping[str, Any] | None = None,
        *,
        offline_only: bool | None = None,
    ) -> MacaroonVerificationResult:
        """Verify the cryptographic caveat chain and context satisfaction."""
        effective_offline = self.offline_only if offline_only is None else offline_only
        return verify_macaroon(
            macaroon=macaroon,
            root_key=root_key,
            check_context=check_context,
            offline_only=effective_offline,
        )

    def authorize(
        self,
        token: str | Macaroon,
        caveats: Sequence[str] | Mapping[str, str] | None = None,
        tx: Mapping[str, Any] | None = None,
        *,
        root_key: bytes | None = None,
    ) -> MacaroonVerificationResult:
        """Execute authorization under the adapter's configured mode."""
        return authorize(
            token=token,
            caveats=caveats,
            tx=tx,
            root_key=root_key,
            offline_only=self.offline_only,
        )


def verify_macaroon(
    macaroon: Macaroon | str | Mapping[str, Any],
    root_key: bytes,
    check_context: Mapping[str, Any] | None = None,
    *,
    offline_only: bool = False,
) -> MacaroonVerificationResult:
    """Verify a Macaroon's HMAC-SHA256 signature chain and discharge all caveats.

    Parameters:
        macaroon: Macaroon instance, serialized string, or mapping.
        root_key: Symmetric secret key (>= 16 bytes).
        check_context: Verification context mapping (tenant, purpose, epoch,
            proposal lineage, clock, online checkers, etc.).
        offline_only: When True (ablation mode), online-required caveats are
            rejected with ONLINE_CHECK_REQUIRED and online checks are not performed.

    Returns:
        MacaroonVerificationResult containing valid flag, stable reason code,
        count of verified caveats, and online_checked status.
    """
    ctx = check_context if check_context is not None else {}

    # Extract root_key from context if not provided
    if (root_key is None or len(root_key) == 0) and (
        "root_key" in ctx or "hmac_key" in ctx
    ):
        raw_k = ctx.get("root_key") or ctx.get("hmac_key")
        if isinstance(raw_k, str):
            root_key = raw_k.encode("utf-8")
        elif isinstance(raw_k, bytes | bytearray):
            root_key = bytes(raw_k)

    # 1. Validate root key length
    if not isinstance(root_key, bytes | bytearray) or len(root_key) < _HMAC_KEY_MIN_BYTES:
        return MacaroonVerificationResult(
            valid=False,
            reason_code=RC_CONTEXT_KEY_TOO_SHORT,
            detail=f"root_key must be >= {_HMAC_KEY_MIN_BYTES} bytes",
        )

    # 2. Parse macaroon
    target_macaroon: Macaroon
    if isinstance(macaroon, Macaroon):
        target_macaroon = macaroon
    elif isinstance(macaroon, str):
        try:
            target_macaroon = Macaroon.deserialize(macaroon)
        except Exception as exc:
            return MacaroonVerificationResult(
                valid=False,
                reason_code=RC_TOKEN_MALFORMED,
                detail=f"Failed to parse macaroon token: {exc}",
            )
    elif isinstance(macaroon, Mapping):
        try:
            target_macaroon = Macaroon.from_dict(macaroon)
        except Exception as exc:
            return MacaroonVerificationResult(
                valid=False,
                reason_code=RC_TOKEN_MALFORMED,
                detail=f"Invalid macaroon dictionary: {exc}",
            )
    else:
        return MacaroonVerificationResult(
            valid=False,
            reason_code=RC_TOKEN_MALFORMED,
            detail="macaroon must be Macaroon, str, or Mapping",
        )

    # 3. Cryptographic caveat chain re-derivation (constant-time comparison)
    try:
        running_sig = hmac.new(
            root_key,
            target_macaroon.identifier.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        for cav in target_macaroon.caveats:
            running_sig = hmac.new(
                running_sig,
                cav.strip().encode("utf-8"),
                hashlib.sha256,
            ).digest()
        expected_sig = running_sig.hex()
        if not hmac.compare_digest(expected_sig, target_macaroon.signature):
            return MacaroonVerificationResult(
                valid=False,
                reason_code=RC_CAVEAT_VERIFICATION_FAILED,
                caveats_verified=0,
                detail="HMAC-SHA256 signature mismatch (tampered caveat or invalid key)",
            )
    except Exception as exc:
        return MacaroonVerificationResult(
            valid=False,
            reason_code=RC_CAVEAT_VERIFICATION_FAILED,
            caveats_verified=0,
            detail=f"Caveat chain calculation error: {exc}",
        )

    # 4. Determine offline-only ablation mode
    is_offline = offline_only or bool(ctx.get("offline_only", False))

    # 5. Pointwise caveat predicate satisfaction
    now_epoch: int = 0
    now_raw = ctx.get("now_epoch_seconds", ctx.get("now", 0))
    if isinstance(now_raw, int | float) and not isinstance(now_raw, bool):
        now_epoch = int(now_raw)

    caveats_evaluated = 0

    for caveat in target_macaroon.caveats:
        key, op, val = parse_caveat(caveat)
        k = key.lower()

        # Check online requirement
        is_online_required = (
            (k in ("check", "mode", "verification") and val.lower() == "online")
            or (
                k in ("online", "online_check", "online_required", "revocation_check")
                and val.lower() in ("true", "1", "yes", "online", "required")
            )
            or k.startswith("online_")
        )

        if is_online_required:
            if is_offline:
                return MacaroonVerificationResult(
                    valid=False,
                    reason_code=RC_ONLINE_CHECK_REQUIRED,
                    caveats_verified=caveats_evaluated,
                    online_checked=False,
                    detail=f"Offline mode rejects online-required caveat: {caveat!r}",
                )
            # Evaluate online check (e.g., online_checker callback or revocation store)
            revocation_store = (
                ctx.get("revocation_store")
                or ctx.get("revoked_identifiers")
                or ctx.get("revoked")
            )
            if revocation_store is not None and target_macaroon.identifier in revocation_store:
                return MacaroonVerificationResult(
                    valid=False,
                    reason_code=RC_REVOKED,
                    caveats_verified=caveats_evaluated,
                    online_checked=True,
                    detail=f"Identifier {target_macaroon.identifier} is revoked online",
                )
            checker = ctx.get("online_checker")
            if callable(checker):
                try:
                    checker_ok = checker(caveat, ctx)
                except Exception as exc:
                    return MacaroonVerificationResult(
                        valid=False,
                        reason_code=RC_ONLINE_CHECK_FAILED,
                        caveats_verified=caveats_evaluated,
                        online_checked=True,
                        detail=f"Online checker error: {exc}",
                    )
                if not checker_ok:
                    return MacaroonVerificationResult(
                        valid=False,
                        reason_code=RC_ONLINE_CHECK_FAILED,
                        caveats_verified=caveats_evaluated,
                        online_checked=True,
                        detail=f"Online checker rejected caveat: {caveat!r}",
                    )
            caveats_evaluated += 1
            continue

        # Check expiry / time caveat
        if k in ("expiry", "expires", "time", "exp"):
            try:
                expiry_val = int(val)
            except ValueError:
                return MacaroonVerificationResult(
                    valid=False,
                    reason_code=RC_CAVEAT_MALFORMED,
                    caveats_verified=caveats_evaluated,
                    detail=f"Malformed expiry value {val!r}",
                )
            if now_epoch > expiry_val:
                return MacaroonVerificationResult(
                    valid=False,
                    reason_code=RC_TOKEN_EXPIRED,
                    caveats_verified=caveats_evaluated,
                    online_checked=not is_offline,
                    detail=f"Token expired: now {now_epoch} > expiry {expiry_val}",
                )
            caveats_evaluated += 1
            continue

        # Check proposal lineage hash caveat
        if k in ("lineage_hash", "proposal_hash", "proposal_lineage", "lineage"):
            expected_lineage = (
                ctx.get("lineage_hash")
                or ctx.get("proposal_hash")
                or ctx.get("proposal_lineage")
            )
            if expected_lineage is not None and str(expected_lineage) != val:
                return MacaroonVerificationResult(
                    valid=False,
                    reason_code=RC_LINEAGE_HASH_MISMATCH,
                    caveats_verified=caveats_evaluated,
                    online_checked=not is_offline,
                    detail=f"Lineage hash mismatch: presented={val} != context={expected_lineage}",
                )
            caveats_evaluated += 1
            continue

        # Check purpose caveat
        if k == "purpose":
            expected_purpose = ctx.get("purpose")
            if expected_purpose is not None and str(expected_purpose) != val:
                return MacaroonVerificationResult(
                    valid=False,
                    reason_code=RC_PURPOSE_MISMATCH,
                    caveats_verified=caveats_evaluated,
                    online_checked=not is_offline,
                    detail=f"Purpose mismatch: presented={val} != context={expected_purpose}",
                )
            caveats_evaluated += 1
            continue

        # Check tenant caveat
        if k in ("tenant", "tenant_id"):
            expected_tenant = ctx.get("tenant") or ctx.get("tenant_id")
            if expected_tenant is not None and str(expected_tenant) != val:
                return MacaroonVerificationResult(
                    valid=False,
                    reason_code=RC_TENANT_MISMATCH,
                    caveats_verified=caveats_evaluated,
                    online_checked=not is_offline,
                    detail=f"Tenant mismatch: presented={val} != context={expected_tenant}",
                )
            caveats_evaluated += 1
            continue

        # Check epoch caveat (policy_epoch, consent_epoch, epoch)
        if k in ("epoch", "policy_epoch", "consent_epoch"):
            if k == "policy_epoch":
                expected_epoch = ctx.get("policy_epoch") or ctx.get("epoch")
            elif k == "consent_epoch":
                expected_epoch = ctx.get("consent_epoch") or ctx.get("epoch")
            else:
                expected_epoch = (
                    ctx.get("epoch")
                    or ctx.get("policy_epoch")
                    or ctx.get("consent_epoch")
                )
            if expected_epoch is not None and str(expected_epoch) != val:
                return MacaroonVerificationResult(
                    valid=False,
                    reason_code=RC_EPOCH_MISMATCH,
                    caveats_verified=caveats_evaluated,
                    online_checked=not is_offline,
                    detail=f"Epoch mismatch: presented={val} != context={expected_epoch}",
                )
            caveats_evaluated += 1
            continue

        # Check actor caveat
        if k in ("actor", "actor_id"):
            expected_actor = ctx.get("actor") or ctx.get("actor_id")
            if expected_actor is not None and str(expected_actor) != val:
                return MacaroonVerificationResult(
                    valid=False,
                    reason_code=RC_ACTOR_MISMATCH,
                    caveats_verified=caveats_evaluated,
                    online_checked=not is_offline,
                    detail=f"Actor mismatch: presented={val} != context={expected_actor}",
                )
            caveats_evaluated += 1
            continue

        # Check task caveat
        if k in ("task", "task_id"):
            expected_task = ctx.get("task") or ctx.get("task_id")
            if expected_task is not None and str(expected_task) != val:
                return MacaroonVerificationResult(
                    valid=False,
                    reason_code=RC_TASK_MISMATCH,
                    caveats_verified=caveats_evaluated,
                    online_checked=not is_offline,
                    detail=f"Task mismatch: presented={val} != context={expected_task}",
                )
            caveats_evaluated += 1
            continue

        # Generic matching for other keys present in context
        if k in ctx:
            expected_val = ctx[k]
            if op in ("=", "==") and str(expected_val) != val:
                return MacaroonVerificationResult(
                    valid=False,
                    reason_code=f"{k.upper()}_MISMATCH",
                    caveats_verified=caveats_evaluated,
                    online_checked=not is_offline,
                    detail=f"{key} mismatch: presented={val} != context={expected_val}",
                )

        caveats_evaluated += 1

    # Clean verification success
    return MacaroonVerificationResult(
        valid=True,
        reason_code=RC_OK,
        caveats_verified=caveats_evaluated,
        online_checked=not is_offline,
        detail="Macaroon and all caveat predicates verified cleanly",
    )


def authorize(
    token: str | Macaroon | None,
    caveats: Sequence[str] | Mapping[str, str] | None = None,
    tx: Mapping[str, Any] | None = None,
    *,
    root_key: bytes | None = None,
    offline_only: bool = False,
) -> MacaroonVerificationResult:
    """Exact target contract: authorize(token, caveats, tx) -> Verdict.

    Adjudicates authorization for a presented macaroon token, optionally
    attenuated by additional caveats, against transaction context tx.
    """
    if token is None or (isinstance(token, str) and not token.strip()):
        return MacaroonVerificationResult(
            valid=False,
            reason_code=RC_TOKEN_MISSING,
            detail="Token is required for authorization",
        )

    context = dict(tx or {})
    target_macaroon: Macaroon
    if isinstance(token, Macaroon):
        target_macaroon = token
    else:
        try:
            target_macaroon = Macaroon.deserialize(token)
        except Exception as exc:
            return MacaroonVerificationResult(
                valid=False,
                reason_code=RC_TOKEN_MALFORMED,
                detail=f"Unparseable token: {exc}",
            )

    # Apply additional caveats if supplied
    if caveats is not None:
        if isinstance(caveats, Mapping):
            for k, v in caveats.items():
                target_macaroon = MacaroonAdapter.add_first_party_caveat(
                    target_macaroon, f"{k} = {v}"
                )
        elif isinstance(caveats, Sequence):
            for cav in caveats:
                target_macaroon = MacaroonAdapter.add_first_party_caveat(
                    target_macaroon, str(cav)
                )

    # Resolve root key from argument or context
    key = root_key
    if key is None or len(key) == 0:
        raw_key = context.get("root_key") or context.get("hmac_key")
        if isinstance(raw_key, str):
            key = raw_key.encode("utf-8")
        elif isinstance(raw_key, bytes | bytearray):
            key = bytes(raw_key)

    if key is None:
        return MacaroonVerificationResult(
            valid=False,
            reason_code=RC_CONTEXT_KEY_TOO_SHORT,
            detail="Root key is missing in arguments and transaction context",
        )

    return verify_macaroon(
        macaroon=target_macaroon,
        root_key=key,
        check_context=context,
        offline_only=offline_only,
    )


create_macaroon: Callable[..., Macaroon] = MacaroonAdapter.create_macaroon
add_first_party_caveat: Callable[..., Macaroon] = MacaroonAdapter.add_first_party_caveat
bind_proposal_lineage: Callable[..., Macaroon] = MacaroonAdapter.bind_proposal_lineage

__all__ = [
    "MACAROON_ADAPTER_VERSION",
    "Macaroon",
    "MacaroonAdapter",
    "MacaroonVerificationResult",
    "RC_ACTOR_MISMATCH",
    "RC_CAVEAT_MALFORMED",
    "RC_CAVEAT_VERIFICATION_FAILED",
    "RC_CONTEXT_KEY_TOO_SHORT",
    "RC_EPOCH_MISMATCH",
    "RC_LINEAGE_HASH_MISMATCH",
    "RC_OK",
    "RC_ONLINE_CHECK_FAILED",
    "RC_ONLINE_CHECK_REQUIRED",
    "RC_PURPOSE_MISMATCH",
    "RC_REVOKED",
    "RC_TASK_MISMATCH",
    "RC_TENANT_MISMATCH",
    "RC_TOKEN_EXPIRED",
    "RC_TOKEN_MALFORMED",
    "RC_TOKEN_MISSING",
    "Verdict",
    "add_first_party_caveat",
    "authorize",
    "bind_proposal_lineage",
    "create_macaroon",
    "parse_caveat",
    "verify_macaroon",
]
