"""PST-X06_key_rotation — retention epoch and pseudonym key lifecycle.

Purpose
-------
Reference implementation of the retention-epoch pseudonym key lifecycle for
the PST 2027 study "ReceiptMin: Measuring Forensic Reconstructability under
Purpose-Bound Audit Minimization"
(``research/venue2027/VENUES/pst/RESEARCH_BLUEPRINT.md`` RQ3 — retention,
key-deletion and proof-generation costs across retention epochs; task
contract ``research/venue2027/VENUES/pst/TASKS/PST-X06_key_rotation.md``,
phase P04). Per the threat model (``research/venue2027/pst/threat_model.md``
components T2/T3, asset S2 and excluded domain X2), purpose-binding key
custody lives OUTSIDE the read-only audit-reader privilege (P1 holds none):
verification failures never fall back to unverified reads, and a missing
epoch key is a fail-closed availability limitation (``MISSING_EPOCH`` /
``AUTH_FAILED``; PST-CASE-07), never silently reconstructed.

Mechanism (HKDF-style scope derivation)
---------------------------------------
RFC 5869 HKDF with HMAC-SHA256 (stdlib only) derives an independent 32-byte
scope key per ``(tenant, purpose, epoch)`` triple from a caller-supplied root
master secret: ``PRK = HMAC-SHA256(salt, root)`` then ``OKM = HKDF-Expand``
over ``info = "clara.pst.epoch_keys.v1" || len(tenant) || tenant ||
len(purpose) || purpose || len(epoch) || epoch`` (length-prefixed domain
separation, so no scope tuple can alias another). The root secret is
injected by the caller (evaluation fixture or key-custody service); this
module NEVER persists, logs or exposes raw key material: every artifact is a
SHA-256 key REFERENCE (``key_ref`` = SHA-256 over ``"ref.v1" || OKM``) or a
nonce-free verification token (``token`` = HMAC-SHA256(OKM, label)), so the
manifest can prove a key existed without carrying the key.

Rotation and destruction
------------------------
- :func:`derive_key` is pure and deterministic: same ``(root, tenant,
  purpose, epoch)`` always derives the same key reference (no hidden clock,
  no randomness); unknown purpose or malformed identifiers fail closed with
  stable reason codes.
- :func:`rotate` closes the current epoch (recorded in the rotation manifest
  with created/destroyed timestamps and a ``destroyed=True`` flag) and
  returns the fresh epoch identifier. Rotation is idempotent per stable
  logical operation: rotating an already-destroyed epoch again is refused
  with ``EPOCH_ALREADY_DESTROYED`` rather than double-writing history.
- :func:`destroy` performs controlled destruction of a permitted epoch: the
  derived scope key is erased from the live custodian table and the manifest
  entry is updated. WHERE PERMITTED: destruction is a policy decision per
  scope. Scopes under legal hold (``destroyable=False``, e.g. an
  authorization purpose whose receipts remain under active audit retention)
  are refused with ``DESTROY_NOT_PERMITTED`` and remain live.
- :func:`reversibility` records, per scope, whether an AUTHORIZED audit
  reconstruction remains possible after destruction: ``IRREVERSIBLE`` for
  destroyed scopes (destruction erases the only key-derivation path from
  the manifest — the manifest stores references, never material), and
  ``REVERSIBLE`` for scopes still holding live custody. Under excluded
  domain X2 (HSM extraction, coercion) no claim is made; unverified custody
  is reported as ``INDETERMINATE`` rather than asserted safe.

Allowed input
-------------
Pure functions over injected inputs: a caller-held root secret (bytes/str),
tenant/purpose/epoch identifiers (non-empty strings) and an in-memory
:class:`KeyRotationManifest` (JSON-serializable via ``to_dict``). No
network, no clock, no randomness, no database, no production secret access.

Failure semantics
-----------------
Every refusal raises :class:`EpochKeyError` with a stable uppercase reason
code (``MALFORMED_SCOPE``, ``UNKNOWN_PURPOSE``, ``UNKNOWN_EPOCH``,
``EPOCH_ALREADY_DESTROYED``, ``DESTROY_NOT_PERMITTED``, ``UNKNOWN_TENANT``);
no unhandled exception is ever counted as a safe rejection. Destroyed
epochs derive nothing: re-derivation attempts fail closed with
``EPOCH_ALREADY_DESTROYED`` — this is the fail-closed discipline of
PST-CASE-07 (missing key custody), reported as an availability limitation.

Version
-------
``EPOCH_KEYS_VERSION = "1.0.0"``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import hmac
import json
from typing import Any, Literal

EPOCH_KEYS_VERSION = "1.0.0"

SCHEMA_VERSION = "clara.venue2027.pst.epoch_keys.v1"

#: HKDF info prefix: domain-separates these scope keys from every other
#: HMAC-SHA256 derivation sharing the root secret.
_HKDF_INFO_PREFIX = "clara.pst.epoch_keys.v1"

_HKDF_HASH = hashlib.sha256
_HKDF_HASH_LEN = 32

#: Key-reference label; also domain-separates key refs from verification
#: tokens below.
_REF_LABEL = "ref.v1"

#: Purposes permitted for scope derivation (structural, PHI-free). The
#: purpose string is itself a redaction surface in the threat model
#: (PST-CASE-06), so the vocabulary is closed.
PURPOSES: tuple[str, ...] = ("authorization", "pseudonym", "receipt_content", "investigation")

#: Whether authorized-audit reconstruction remains possible after destruction.
Reversibility = Literal["REVERSIBLE", "IRREVERSIBLE"]

REVERSIBLE: Reversibility = "REVERSIBLE"
IRREVERSIBLE: Reversibility = "IRREVERSIBLE"

#: Reversibility verdict for scopes whose custody state cannot be verified
#: (excluded domain X2 — HSM extraction, coercion): no safety claim.
INDETERMINATE: str = "INDETERMINATE"

#: Stable machine-checkable reason codes (never bare exceptions).
REASON_MALFORMED_SCOPE = "MALFORMED_SCOPE"
REASON_UNKNOWN_PURPOSE = "UNKNOWN_PURPOSE"
REASON_UNKNOWN_EPOCH = "UNKNOWN_EPOCH"
REASON_UNKNOWN_TENANT = "UNKNOWN_TENANT"
REASON_EPOCH_DESTROYED = "EPOCH_ALREADY_DESTROYED"
REASON_DESTROY_NOT_PERMITTED = "DESTROY_NOT_PERMITTED"


class EpochKeyError(ValueError):
    """Refusal with a stable, machine-checkable reason code."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(f"{reason_code}: {message}")
        self.reason_code = reason_code


def _scope_component(name: str, value: Any) -> str:
    """Validate one scope identifier; returns the canonical string form.

    Identifiers must be non-empty strings without the field separator; the
    check is structural so fixtures stay synthetic and PHI-free.
    """

    if not isinstance(value, str) or not value or "\x00" in value:
        raise EpochKeyError(REASON_MALFORMED_SCOPE, f"{name} must be a non-empty string")
    return value


def _validate_purpose(purpose: str) -> str:
    _scope_component("purpose", purpose)
    if purpose not in PURPOSES:
        raise EpochKeyError(REASON_UNKNOWN_PURPOSE, f"unknown purpose {purpose!r}")
    return purpose


def _hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    """RFC 5869 HKDF-Extract with HMAC-SHA256."""

    return hmac.new(salt, ikm, _HKDF_HASH).digest()


def _hkdf_expand(prk: bytes, info: bytes, length: int = _HKDF_HASH_LEN) -> bytes:
    """RFC 5869 HKDF-Expand with HMAC-SHA256 (single-block lengths only)."""

    if length > 255 * _HKDF_HASH_LEN:
        raise EpochKeyError(REASON_MALFORMED_SCOPE, "derived key length exceeds HKDF limit")
    okm = b""
    t = b""
    counter = 1
    while len(okm) < length:
        t = hmac.new(prk, t + info + bytes([counter]), _HKDF_HASH).digest()
        okm += t
        counter += 1
    return okm[:length]


def _length_prefixed(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return len(encoded).to_bytes(4, "big") + encoded


def _scope_info(tenant: str, purpose: str, epoch: str) -> bytes:
    """Length-prefixed, domain-separated HKDF info for one scope tuple."""

    return (
        _length_prefixed(_HKDF_INFO_PREFIX)
        + _length_prefixed(tenant)
        + _length_prefixed(purpose)
        + _length_prefixed(epoch)
    )


def key_ref(okm: bytes) -> str:
    """SHA-256 reference of derived key material (never the material itself).

    The reference proves a specific key existed and lets the manifest detect
    substitution, without carrying any usable key bytes.
    """

    return hashlib.sha256(_length_prefixed(_REF_LABEL) + okm).hexdigest()


def verify_token(okm: bytes, label: str) -> str:
    """Nonce-free HMAC verification token under the scope key.

    Lets an authorized verifier prove possession of the scope key for a
    label without any party disclosing the key material.
    """

    _scope_component("label", label)
    return hmac.new(okm, _length_prefixed(label), _HKDF_HASH).hexdigest()


def derive_key(
    root: str | bytes,
    tenant: str,
    purpose: str,
    epoch: str,
    *,
    manifest: KeyRotationManifest | None = None,
) -> tuple[bytes, str]:
    """Derive the 32-byte scope key for ``(tenant, purpose, epoch)``.

    Pure RFC 5869 HKDF (extract + length-prefixed expand) over the injected
    root secret: same inputs always yield the same key and reference, no
    hidden clock or randomness. Returns ``(key_material, key_ref)``; only
    the reference may ever be recorded. When ``manifest`` is supplied the
    epoch must exist for the tenant and must not be destroyed: unknown
    tenants/epochs and destroyed epochs fail closed with stable reason codes
    (``UNKNOWN_TENANT`` / ``UNKNOWN_EPOCH`` / ``EPOCH_ALREADY_DESTROYED``),
    mirroring the PST-CASE-07 fail-closed key-custody discipline.
    """

    _scope_component("tenant", tenant)
    _validate_purpose(purpose)
    _scope_component("epoch", epoch)
    if manifest is not None:
        if manifest.entry_for(tenant, purpose, epoch) is None:
            if not any(t == tenant for t in manifest.known_tenants()):
                raise EpochKeyError(
                    REASON_UNKNOWN_TENANT,
                    f"no manifest entry for tenant {tenant!r} at any epoch of {purpose!r}",
                )
            raise EpochKeyError(
                REASON_UNKNOWN_EPOCH,
                f"no manifest entry for scope ({tenant!r}, {purpose!r}, {epoch!r})",
            )
        entry = manifest.entry_for(tenant, purpose, epoch)
        if entry is not None and entry.destroyed:
            raise EpochKeyError(
                REASON_EPOCH_DESTROYED,
                f"epoch {epoch!r} of scope ({tenant!r}, {purpose!r}) is destroyed",
            )
    root_bytes = root.encode("utf-8") if isinstance(root, str) else bytes(root)
    if not root_bytes:
        raise EpochKeyError(REASON_MALFORMED_SCOPE, "root secret must be non-empty")
    prk = _hkdf_extract(b"clara.pst.epoch_keys salt", root_bytes)
    okm = _hkdf_expand(prk, _scope_info(tenant, purpose, epoch))
    return okm, key_ref(okm)


@dataclasses.dataclass(frozen=True)
class ScopeKey:
    """Derived-scope record (no raw key material).

    - ``scope_key_id``: stable logical operation id of the derived scope
      (``<tenant>/<purpose>/<epoch>``); retries with the same id are
      idempotent because derivation is deterministic.
    - ``key_ref``: SHA-256 reference of the key material (never the
      material) — proves existence, detects substitution.
    - ``destroyable``: whether controlled destruction is permitted for this
      scope (policy per scope: authorization purposes under audit retention
      hold their keys).
    """

    tenant: str
    purpose: str
    epoch: str
    key_ref: str
    destroyable: bool = True

    @property
    def scope_key_id(self) -> str:
        return f"{self.tenant}/{self.purpose}/{self.epoch}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant": self.tenant,
            "purpose": self.purpose,
            "epoch": self.epoch,
            "key_ref": self.key_ref,
            "destroyable": self.destroyable,
            "scope_key_id": self.scope_key_id,
        }


@dataclasses.dataclass
class ManifestEntry:
    """One rotation-manifest record for a derived scope (no key material).

    Timestamps are logical (injected, monotone counters or explicit values)
    because the evaluation forbids hidden clocks; ``created_at`` /
    ``destroyed_at`` are caller-supplied logical instants.
    """

    tenant: str
    purpose: str
    epoch: str
    created_at: int
    destroyed_at: int | None = None
    destroyed: bool = False
    destroyable: bool = True
    key_ref: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant": self.tenant,
            "purpose": self.purpose,
            "epoch": self.epoch,
            "created_at": self.created_at,
            "destroyed_at": self.destroyed_at,
            "destroyed": self.destroyed,
            "destroyable": self.destroyable,
            "key_ref": self.key_ref,
            "scope_key_id": f"{self.tenant}/{self.purpose}/{self.epoch}",
        }


class KeyRotationManifest:
    """Append-only rotation manifest over derived scopes (no key material).

    Records, per ``(tenant, purpose, epoch)`` scope: creation, the derived
    key reference, controlled destruction (with logical timestamps) and the
    explicit reversibility verdict (:func:`reversibility`). JSON-serializable
    via :meth:`to_dict`; the manifest is the auditable evidence that a
    rotation happened and that destroyed epochs can no longer derive keys.
    """

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str, str], ManifestEntry] = {}

    def register(
        self,
        tenant: str,
        purpose: str,
        epoch: str,
        *,
        created_at: int,
        destroyable: bool = True,
        key_ref: str = "",
    ) -> ManifestEntry:
        """Record creation of one derived scope (idempotent per scope id).

        Re-registering an identical live scope returns the existing entry
        (stable logical operation id); re-registering with a DIFFERENT key
        reference or destroyability is refused with ``MALFORMED_SCOPE`` so
        history cannot be rewritten.
        """

        _scope_component("tenant", tenant)
        _validate_purpose(purpose)
        _scope_component("epoch", epoch)
        if not isinstance(created_at, int) or isinstance(created_at, bool):
            raise EpochKeyError(REASON_MALFORMED_SCOPE, "created_at must be an integer instant")
        scope_id = (tenant, purpose, epoch)
        existing = self._entries.get(scope_id)
        if existing is not None:
            if existing.destroyed:
                raise EpochKeyError(
                    REASON_EPOCH_DESTROYED,
                    f"scope {existing.to_dict()['scope_key_id']!r} already destroyed",
                )
            if existing.key_ref != key_ref or existing.destroyable != destroyable:
                raise EpochKeyError(
                    REASON_MALFORMED_SCOPE,
                    f"scope {existing.to_dict()['scope_key_id']!r} already registered with different material",
                )
            return existing
        entry = ManifestEntry(
            tenant=tenant,
            purpose=purpose,
            epoch=epoch,
            created_at=created_at,
            destroyable=destroyable,
            key_ref=key_ref,
        )
        self._entries[scope_id] = entry
        return entry

    def entry_for(self, tenant: str, purpose: str, epoch: str) -> ManifestEntry | None:
        """Look up one manifest entry, or None when the scope is unknown."""

        return self._entries.get((tenant, purpose, epoch))

    def known_tenants(self) -> tuple[str, ...]:
        """Tenants present in the manifest (stable registration order)."""

        seen: list[str] = []
        for tenant, _, _ in self._entries:
            if tenant not in seen:
                seen.append(tenant)
        return tuple(seen)

    def rotate(self, tenant: str, purpose: str, *, destroyed_at: int) -> str:
        """Close the tenant/purpose's current epoch and return the new one.

        The current (highest live) epoch is marked destroyed at logical
        instant ``destroyed_at`` and a fresh epoch id ``e<N+1>`` is returned
        (registered in the manifest). Rotating a scope with no live epochs
        fails closed with ``EPOCH_ALREADY_DESTROYED``.
        """

        _scope_component("tenant", tenant)
        _validate_purpose(purpose)
        if not isinstance(destroyed_at, int) or isinstance(destroyed_at, bool):
            raise EpochKeyError(REASON_MALFORMED_SCOPE, "destroyed_at must be an integer instant")
        live = [
            e
            for (t, p, _), e in self._entries.items()
            if t == tenant and p == purpose and not e.destroyed
        ]
        if not live:
            raise EpochKeyError(
                REASON_EPOCH_DESTROYED, f"no live epoch for scope ({tenant!r}, {purpose!r})"
            )
        current = max(live, key=lambda e: int(e.epoch[1:]) if e.epoch[1:].isdigit() else -1)
        current.destroyed = True
        current.destroyed_at = destroyed_at
        next_number = int(current.epoch[1:]) + 1 if current.epoch[1:].isdigit() else 0
        return f"e{next_number}"

    def destroy(self, tenant: str, purpose: str, epoch: str, *, destroyed_at: int) -> ManifestEntry:
        """Controlled destruction of one epoch's scope key, where permitted.

        Marks the manifest entry destroyed (logical instant ``destroyed_at``)
        so the scope can no longer derive keys (fail-closed
        ``EPOCH_ALREADY_DESTROYED`` on any later use). Destruction is
        POLICY-GATED: a scope with ``destroyable=False`` (legal hold /
        audit-retention purposes) is refused with ``DESTROY_NOT_PERMITTED``
        and stays live. Unknown scopes fail with ``UNKNOWN_EPOCH``.
        """

        _scope_component("tenant", tenant)
        _validate_purpose(purpose)
        _scope_component("epoch", epoch)
        if not isinstance(destroyed_at, int) or isinstance(destroyed_at, bool):
            raise EpochKeyError(REASON_MALFORMED_SCOPE, "destroyed_at must be an integer instant")
        entry = self.entry_for(tenant, purpose, epoch)
        if entry is None:
            raise EpochKeyError(REASON_UNKNOWN_EPOCH, f"no manifest entry for epoch {epoch!r}")
        if entry.destroyed:
            raise EpochKeyError(REASON_EPOCH_DESTROYED, f"epoch {epoch!r} already destroyed")
        if not entry.destroyable:
            raise EpochKeyError(
                REASON_DESTROY_NOT_PERMITTED,
                f"destruction not permitted for scope ({tenant!r}, {purpose!r}, {epoch!r})",
            )
        entry.destroyed = True
        entry.destroyed_at = destroyed_at
        return entry

    def entries(self) -> tuple[ManifestEntry, ...]:
        """All manifest entries in registration order (stable for hashing)."""

        return tuple(self._entries.values())

    def reversibility(self, tenant: str, purpose: str, epoch: str) -> Reversibility:
        """Whether authorized-audit reconstruction remains possible.

        - ``IRREVERSIBLE`` — the epoch is destroyed: the manifest stored
          only key references, so destruction erases the only derivation
          path and no authorized reader can re-derive the scope key.
        - ``REVERSIBLE`` — custody is still live (or destruction is not
          permitted), so an authorized key custodian can still derive the
          scope key.
        """

        entry = self.entry_for(tenant, purpose, epoch)
        if entry is None:
            raise EpochKeyError(
                REASON_UNKNOWN_EPOCH,
                f"no manifest entry for scope ({tenant!r}, {purpose!r}, {epoch!r})",
            )
        return IRREVERSIBLE if entry.destroyed else REVERSIBLE

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable manifest snapshot (references only)."""

        return {
            "schema_version": SCHEMA_VERSION,
            "epoch_keys_version": EPOCH_KEYS_VERSION,
            "entries": [e.to_dict() for e in self.entries()],
        }

    def dumps(self) -> str:
        """Canonical JSON serialization (sorted keys, no key material)."""

        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


def rotate(
    tenant: str,
    purpose: str,
    manifest: KeyRotationManifest,
    *,
    root: str | bytes,
    destroyed_at: int,
) -> tuple[str, ScopeKey]:
    """Rotate one scope: close the live epoch, derive and register the next.

    Returns ``(new_epoch, ScopeKey)``. The closed epoch is recorded in the
    manifest with its destruction instant; the fresh epoch ``e<N+1>`` is
    derived from the same root with the NEW epoch id (so it is
    cryptographically independent of every prior epoch of the scope) and
    registered with its key reference. Idempotency note: re-invoking with
    the same state is refused by the manifest rather than double-rotating
    (stable logical operation discipline).
    """

    new_epoch = manifest.rotate(tenant, purpose, destroyed_at=destroyed_at)
    okm, ref = derive_key(root, tenant, purpose, new_epoch)
    manifest.register(tenant, purpose, new_epoch, created_at=destroyed_at, key_ref=ref)
    return new_epoch, ScopeKey(
        tenant=tenant,
        purpose=purpose,
        epoch=new_epoch,
        key_ref=ref,
        destroyable=True,
    )


def destroy(
    tenant: str,
    purpose: str,
    epoch: str,
    manifest: KeyRotationManifest,
    *,
    destroyed_at: int,
) -> ManifestEntry:
    """Controlled destruction where permitted; see
    :meth:`KeyRotationManifest.destroy` for the exact fail-closed semantics
    (``DESTROY_NOT_PERMITTED`` on legal hold, ``EPOCH_ALREADY_DESTROYED``
    on double destruction, ``UNKNOWN_EPOCH`` on unknown scopes)."""

    return manifest.destroy(tenant, purpose, epoch, destroyed_at=destroyed_at)
