"""CLARA-Care 2027 IFIP_SEC task IFIP_SEC-candidate — replay-closed authorization.

Purpose
-------
CANDIDATE design (phase P04, priority; blueprint arm B4 of
``research/venue2027/VENUES/ifip_sec/RESEARCH_BLUEPRINT.md``) for
"Replay-Closed Authorization Across Purpose, Delegation, and AI Proposal
Lineage". This module is a DESIGN OBJECT: it defines the authorization
algorithm, its typed inputs/outputs, its fail-closed reason codes, its
ablation hooks and its machine-readable mechanism description. It contains
NO empirical results, NO performance numbers and NO win rates (the P04 gate
forbids main-test claims); the PostgreSQL-linearizable nonce store and
lineage digest belong to tasks IFIP_SEC-X03 / IFIP_SEC-X02.

Mechanism under study: REPLAY-CLOSED AUTHORIZATION
--------------------------------------------------
Every authorization is a *typed commitment* receipt (real HMAC-SHA256 over
``hmac``/``hashlib``) binding the full consumption context — actor, patient,
tenant, purpose, task, consent epoch, policy epoch, dispatch digest,
delegation-chain hash + depth, proposal-lineage hash, nonce and parent
reference — plus a consume-once nonce in an injected store and a delegation
ancestry walk over an injected ledger. ``authorize`` re-derives every binding
at presentation time and fails closed on ANY divergence, so a replayed
receipt whose purpose, delegation chain, proposal lineage or epochs changed
is DENYed even though its signature still verifies (signature equality alone
is insufficient — that is exactly the B1/B2 gap the blueprint measures).

Algorithmic definition (canonical authorize pipeline, first-failure-wins)
-------------------------------------------------------------------------
``authorize(receipt, request, nonce_store, ledger) -> Verdict`` executes, in
order:

1. **Shape validation** (fail closed): receipt/request/ledger/nonce_store
   types and fields (``RECEIPT_MALFORMED`` / ``REQUEST_MALFORMED`` /
   ``LEDGER_MISSING`` / ``LEDGER_BAD_TYPE`` / ``NONCE_STORE_MISSING`` /
   ``NONCE_STORE_BAD_TYPE``); a receipt without a nonce fails closed
   (``NONCE_MISSING``).
2. **HMAC receipt verification**: recompute HMAC-SHA256 over the canonical
   signed claims and constant-time compare (``RECEIPT_SIGNATURE_INVALID``).
3. **Expiry** against the ledger's injected clock (``RECEIPT_EXPIRED``).
4. **Ledger registration**: the receipt id must have been issued through the
   ledger (``RECEIPT_UNKNOWN`` — fail closed on unknown state).
5. **Delegation ancestry**: the parent-reference chain must resolve to the
   root within the ledger, cycle-safe and bounded (``DELEGATION_ANCESTRY_BROKEN``).
6. **Commitment re-derivation** (byte binding of the unsigned transport):
   the delegation-chain hash + depth recomputed from the carried chain must
   equal the signed commitments (``DELEGATION_CHAIN_CHANGED``); likewise the
   proposal-lineage hash (``LINEAGE_SPLICED``).
7. **Request context binding** (pointwise against the SIGNED claims, so any
   replayed receipt consumed in a changed context fails closed):
   purpose, tenant, actor, patient, task, consent epoch, policy epoch and
   dispatch digest (``PURPOSE_MISMATCH`` / ``TENANT_MISMATCH`` /
   ``ACTOR_MISMATCH`` / ``PATIENT_MISMATCH`` / ``TASK_MISMATCH`` /
   ``CONSENT_EPOCH_MISMATCH`` / ``POLICY_EPOCH_MISMATCH`` /
   ``DISPATCH_MISMATCH``).
8. **Live governance epochs** (optional ledger-provided online check):
   ``CONSENT_EPOCH_REVOKED`` / ``POLICY_EPOCH_STALE`` (CASE-04 revocation).
9. **Request-presented chain/lineage binding**: the consuming request must
   present exactly the delegated chain and the committed lineage
   (``DELEGATION_CHAIN_CHANGED`` / ``LINEAGE_SPLICED``).
10. **Consume-once nonce** (LAST, so binding failures never consume): the
    nonce must still be in the injected store and is removed in the same
    logical step (``NONCE_REPLAYED`` otherwise); ALLOW carries
    ``NONCE_CONSUMED_OK``.

Allowed input
-------------
- :class:`Receipt` — the HMAC-bound typed commitment (issue via
  :func:`issue_receipt` or :meth:`AuthorizationLedger.issue`; JSON round-trip
  via ``to_dict``/``from_dict``).
- :class:`AuthorizationRequest` — the consumption context presented at
  verification time (purpose, tenant, actor, patient, task, epochs, dispatch
  digest, presented delegation chain and proposal lineage).
- ``nonce_store`` — injected mutable consume-once set (in-process stand-in;
  the PostgreSQL-serializable registry is task IFIP_SEC-X03).
- ``ledger`` — injected :class:`AuthorizationLedger` carrying the HMAC key,
  the frozen clock, the registered ancestry and optional live governance
  epochs. No network, no database, no hidden clock or randomness: identical
  inputs always yield an identical :class:`Verdict`.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes. ``authorize`` is total: it
NEVER raises for case/verification faults; structural faults return
``DENY`` with ``fail_closed=True`` (never silently treated as determined
rejections — the verdict carries the distinction). Wiring errors (a ledger
constructed with a too-short HMAC key, malformed ``from_dict`` payloads)
raise :class:`CandidateError` at construction/boundary time, and
:func:`run_candidate` converts every boundary fault into a first-class
``REJECT`` :class:`~evaluation.venue2027._shared.harness.Outcome` carrying
the stable reason code (never an uncounted crash).

Ablation hooks (real mechanism axes, P04)
-----------------------------------------
- :func:`ablation_no_lineage_binding` — returns an authorizer with the
  proposal-lineage binding removed: a spliced lineage is ADMITTED, proving
  the lineage binding (not the signature) is the mechanism that stops it.
- :func:`ablation_no_nonce` — returns an authorizer with the consume-once
  nonce removed: an exact replay is ADMITTED, proving the nonce is the
  mechanism that stops it. Each ablation removes exactly one mechanism;
  every other binding stays enforced.

Independence boundary (never violated by this module)
-----------------------------------------------------
This module does NOT import the independent oracle
(``evaluation.venue2027.ifip_sec.independent_oracle``), any baseline adapter
or any label file; ground truth for the venue's cases is adjudicated outside
this module. ``run_candidate`` is the task-contract adapter
``run_candidate(case, ctx) -> Outcome`` mapping ALLOW->ADMIT and DENY->REJECT.

Version
-------
``CANDIDATE_ID = "clara.ifip_sec.candidate.replay-closed-lineage-authorization"``,
``CANDIDATE_VERSION = "1.0.0"``. :func:`describe_mechanism` returns the
machine-readable design record. All output types are JSON-serializable via
``to_dict``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import hmac
import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Final

from evaluation.venue2027._shared.harness import Outcome

CANDIDATE_ID: Final[str] = "clara.ifip_sec.candidate.replay-closed-lineage-authorization"
CANDIDATE_VERSION: Final[str] = "1.0.0"

DECISION_ALLOW: Final[str] = "ALLOW"
DECISION_DENY: Final[str] = "DENY"

#: HMAC key must carry at least this many bytes of entropy (wiring guard).
_HMAC_KEY_MIN_BYTES: Final[int] = 16

#: Ancestry walk is bounded and cycle-safe; anything deeper is broken.
MAX_ANCESTRY_HOPS: Final[int] = 64

ROOT_REF: Final[str] = "root"

# ---------------------------------------------------------------------------
# Stable reason codes (uppercase, machine-checkable).
# ---------------------------------------------------------------------------

REASON_NONCE_CONSUMED_OK: Final[str] = "NONCE_CONSUMED_OK"
REASON_NONCE_UNPROTECTED: Final[str] = "NONCE_UNPROTECTED"
REASON_LINEAGE_UNBOUND: Final[str] = "LINEAGE_UNBOUND"

REASON_RECEIPT_MALFORMED: Final[str] = "RECEIPT_MALFORMED"
REASON_REQUEST_MALFORMED: Final[str] = "REQUEST_MALFORMED"
REASON_LEDGER_MISSING: Final[str] = "LEDGER_MISSING"
REASON_LEDGER_BAD_TYPE: Final[str] = "LEDGER_BAD_TYPE"
REASON_NONCE_STORE_MISSING: Final[str] = "NONCE_STORE_MISSING"
REASON_NONCE_STORE_BAD_TYPE: Final[str] = "NONCE_STORE_BAD_TYPE"
REASON_NONCE_MISSING: Final[str] = "NONCE_MISSING"
REASON_RECEIPT_SIGNATURE_INVALID: Final[str] = "RECEIPT_SIGNATURE_INVALID"
REASON_RECEIPT_EXPIRED: Final[str] = "RECEIPT_EXPIRED"
REASON_RECEIPT_UNKNOWN: Final[str] = "RECEIPT_UNKNOWN"
REASON_DELEGATION_ANCESTRY_BROKEN: Final[str] = "DELEGATION_ANCESTRY_BROKEN"
REASON_DELEGATION_CHAIN_CHANGED: Final[str] = "DELEGATION_CHAIN_CHANGED"
REASON_LINEAGE_SPLICED: Final[str] = "LINEAGE_SPLICED"
REASON_PURPOSE_MISMATCH: Final[str] = "PURPOSE_MISMATCH"
REASON_TENANT_MISMATCH: Final[str] = "TENANT_MISMATCH"
REASON_ACTOR_MISMATCH: Final[str] = "ACTOR_MISMATCH"
REASON_PATIENT_MISMATCH: Final[str] = "PATIENT_MISMATCH"
REASON_TASK_MISMATCH: Final[str] = "TASK_MISMATCH"
REASON_CONSENT_EPOCH_MISMATCH: Final[str] = "CONSENT_EPOCH_MISMATCH"
REASON_POLICY_EPOCH_MISMATCH: Final[str] = "POLICY_EPOCH_MISMATCH"
REASON_DISPATCH_MISMATCH: Final[str] = "DISPATCH_MISMATCH"
REASON_CONSENT_EPOCH_REVOKED: Final[str] = "CONSENT_EPOCH_REVOKED"
REASON_POLICY_EPOCH_STALE: Final[str] = "POLICY_EPOCH_STALE"
REASON_NONCE_REPLAYED: Final[str] = "NONCE_REPLAYED"

#: Structural faults (fail_closed=True) — never silently treated as
#: determined rejections; the Verdict carries the distinction.
FAIL_CLOSED_REASON_CODES: Final[tuple[str, ...]] = (
    REASON_RECEIPT_MALFORMED,
    REASON_REQUEST_MALFORMED,
    REASON_LEDGER_MISSING,
    REASON_LEDGER_BAD_TYPE,
    REASON_NONCE_STORE_MISSING,
    REASON_NONCE_STORE_BAD_TYPE,
    REASON_NONCE_MISSING,
)

#: Determined DENY outcomes (the security results under measurement).
DETERMINED_DENY_REASON_CODES: Final[tuple[str, ...]] = (
    REASON_RECEIPT_SIGNATURE_INVALID,
    REASON_RECEIPT_EXPIRED,
    REASON_RECEIPT_UNKNOWN,
    REASON_DELEGATION_ANCESTRY_BROKEN,
    REASON_DELEGATION_CHAIN_CHANGED,
    REASON_LINEAGE_SPLICED,
    REASON_PURPOSE_MISMATCH,
    REASON_TENANT_MISMATCH,
    REASON_ACTOR_MISMATCH,
    REASON_PATIENT_MISMATCH,
    REASON_TASK_MISMATCH,
    REASON_CONSENT_EPOCH_MISMATCH,
    REASON_POLICY_EPOCH_MISMATCH,
    REASON_DISPATCH_MISMATCH,
    REASON_CONSENT_EPOCH_REVOKED,
    REASON_POLICY_EPOCH_STALE,
    REASON_NONCE_REPLAYED,
)

_SIGNED_CLAIM_KEYS: Final[tuple[str, ...]] = (
    "receipt_id",
    "actor_id",
    "patient_id",
    "tenant_id",
    "purpose",
    "task_id",
    "consent_epoch",
    "policy_epoch",
    "dispatch_digest",
    "nonce",
    "expiry",
    "parent_ref",
    "delegation_chain_hash",
    "delegation_depth",
    "proposal_lineage_hash",
)


class CandidateError(ValueError):
    """Boundary/wiring error carrying a stable reason code (not a Verdict)."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


# ---------------------------------------------------------------------------
# Canonical serialization + commitment hashes (real hashlib usage).
# ---------------------------------------------------------------------------


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_delegation_chain(chain: Sequence[str]) -> str:
    """Delegation-chain commitment: sha256 over the canonical JSON link list."""
    return _sha256_hex(_canonical_json(list(chain)))


def hash_proposal_lineage(lineage: Sequence[str]) -> str:
    """Proposal-lineage commitment: sha256 over the canonical JSON lineage list."""
    return _sha256_hex(_canonical_json(list(lineage)))


def _receipt_mac(hmac_key: bytes, claims: Mapping[str, Any]) -> str:
    """Real HMAC-SHA256 over the canonical signed-claim JSON."""
    canonical = _canonical_json(dict(claims)).encode("utf-8")
    return hmac.new(hmac_key, canonical, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Receipt — the typed commitment.
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Receipt:
    """HMAC-bound authorization receipt (typed commitment).

    Signed claims cover the full consumption context including the
    delegation-chain hash + depth and the proposal-lineage hash. The
    ``delegation_chain`` / ``proposal_lineage`` lists are UNSIGNED transport
    copies whose recomputed hashes must equal the signed commitments at
    verification time — so a spliced lineage or a truncated delegation chain
    is caught by the BINDING (a stable lineage/delegation reason code), not
    by signature equality, which is precisely the B1/B2 gap under study.
    """

    receipt_id: str
    actor_id: str
    patient_id: str
    tenant_id: str
    purpose: str
    task_id: str
    consent_epoch: str
    policy_epoch: str
    dispatch_digest: str
    nonce: str
    expiry: int
    parent_ref: str = ROOT_REF
    delegation_chain: tuple[str, ...] = ()
    proposal_lineage: tuple[str, ...] = ()
    delegation_chain_hash: str = ""
    delegation_depth: int = -1
    proposal_lineage_hash: str = ""
    mac: str = ""

    def __post_init__(self) -> None:
        for field_name in (
            "receipt_id",
            "actor_id",
            "patient_id",
            "tenant_id",
            "purpose",
            "task_id",
            "consent_epoch",
            "policy_epoch",
            "dispatch_digest",
            "nonce",
            "parent_ref",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                raise CandidateError(
                    REASON_RECEIPT_MALFORMED,
                    f"receipt field {field_name!r} must be a non-empty str",
                )
        if isinstance(self.expiry, bool) or not isinstance(self.expiry, int):
            raise CandidateError(REASON_RECEIPT_MALFORMED, "receipt expiry must be an int")
        if not isinstance(self.delegation_chain, tuple) or not all(
            isinstance(link, str) and link for link in self.delegation_chain
        ):
            raise CandidateError(
                REASON_RECEIPT_MALFORMED, "delegation_chain must be a tuple of non-empty strs"
            )
        if not isinstance(self.proposal_lineage, tuple) or not all(
            isinstance(step, str) and step for step in self.proposal_lineage
        ):
            raise CandidateError(
                REASON_RECEIPT_MALFORMED, "proposal_lineage must be a tuple of non-empty strs"
            )
        if not self.delegation_chain:
            object.__setattr__(self, "delegation_chain", (self.actor_id,))
        if not self.delegation_chain_hash:
            object.__setattr__(
                self, "delegation_chain_hash", hash_delegation_chain(self.delegation_chain)
            )
        if self.delegation_depth < 0:
            object.__setattr__(self, "delegation_depth", len(self.delegation_chain))
        if not self.proposal_lineage_hash:
            object.__setattr__(
                self, "proposal_lineage_hash", hash_proposal_lineage(self.proposal_lineage)
            )

    @property
    def signed_claims(self) -> dict[str, Any]:
        """The exact claim mapping covered by the HMAC."""
        return {key: getattr(self, key) for key in _SIGNED_CLAIM_KEYS}

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "actor_id": self.actor_id,
            "patient_id": self.patient_id,
            "tenant_id": self.tenant_id,
            "purpose": self.purpose,
            "task_id": self.task_id,
            "consent_epoch": self.consent_epoch,
            "policy_epoch": self.policy_epoch,
            "dispatch_digest": self.dispatch_digest,
            "nonce": self.nonce,
            "expiry": self.expiry,
            "parent_ref": self.parent_ref,
            "delegation_chain": list(self.delegation_chain),
            "proposal_lineage": list(self.proposal_lineage),
            "delegation_chain_hash": self.delegation_chain_hash,
            "delegation_depth": self.delegation_depth,
            "proposal_lineage_hash": self.proposal_lineage_hash,
            "mac": self.mac,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Receipt:
        """Reconstruct verbatim (commitments are NOT re-derived here)."""
        if not isinstance(payload, Mapping):
            raise CandidateError(REASON_RECEIPT_MALFORMED, "receipt payload must be a mapping")
        missing = [key for key in (*_SIGNED_CLAIM_KEYS, "mac") if key not in payload]
        if missing:
            raise CandidateError(REASON_RECEIPT_MALFORMED, f"receipt payload missing {missing}")
        try:
            return cls(
                receipt_id=payload["receipt_id"],
                actor_id=payload["actor_id"],
                patient_id=payload["patient_id"],
                tenant_id=payload["tenant_id"],
                purpose=payload["purpose"],
                task_id=payload["task_id"],
                consent_epoch=payload["consent_epoch"],
                policy_epoch=payload["policy_epoch"],
                dispatch_digest=payload["dispatch_digest"],
                nonce=payload["nonce"],
                expiry=payload["expiry"],
                parent_ref=payload["parent_ref"],
                delegation_chain=tuple(payload["delegation_chain"]),
                proposal_lineage=tuple(payload["proposal_lineage"]),
                delegation_chain_hash=payload["delegation_chain_hash"],
                delegation_depth=payload["delegation_depth"],
                proposal_lineage_hash=payload["proposal_lineage_hash"],
                mac=payload["mac"],
            )
        except CandidateError:
            raise
        except (TypeError, ValueError) as exc:
            raise CandidateError(
                REASON_RECEIPT_MALFORMED, f"receipt payload unusable: {exc}"
            ) from exc


def issue_receipt(
    *,
    hmac_key: bytes,
    receipt_id: str,
    actor_id: str,
    patient_id: str,
    tenant_id: str,
    purpose: str,
    task_id: str,
    consent_epoch: str,
    policy_epoch: str,
    dispatch_digest: str,
    nonce: str,
    expiry: int,
    parent_ref: str = ROOT_REF,
    delegation_chain: Sequence[str] = (),
    proposal_lineage: Sequence[str] = (),
) -> Receipt:
    """Issue an HMAC-signed receipt (pure helper; registration is separate)."""
    receipt = Receipt(
        receipt_id=receipt_id,
        actor_id=actor_id,
        patient_id=patient_id,
        tenant_id=tenant_id,
        purpose=purpose,
        task_id=task_id,
        consent_epoch=consent_epoch,
        policy_epoch=policy_epoch,
        dispatch_digest=dispatch_digest,
        nonce=nonce,
        expiry=expiry,
        parent_ref=parent_ref,
        delegation_chain=tuple(delegation_chain),
        proposal_lineage=tuple(proposal_lineage),
    )
    mac = _receipt_mac(hmac_key, receipt.signed_claims)
    return dataclasses.replace(receipt, mac=mac)


def verify_receipt_signature(receipt: Receipt, hmac_key: bytes) -> bool:
    """Recompute the HMAC over the signed claims and constant-time compare."""
    if not isinstance(receipt.mac, str) or not receipt.mac:
        return False
    expected = _receipt_mac(hmac_key, receipt.signed_claims)
    return hmac.compare_digest(expected, receipt.mac)


# ---------------------------------------------------------------------------
# AuthorizationRequest — the consumption context presented at verify time.
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class AuthorizationRequest:
    """The consuming context checked pointwise against the signed claims."""

    actor_id: str
    tenant_id: str
    patient_id: str
    purpose: str
    task_id: str
    consent_epoch: str
    policy_epoch: str
    dispatch_digest: str
    delegation_chain: tuple[str, ...] = ()
    proposal_lineage: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "actor_id",
            "tenant_id",
            "patient_id",
            "purpose",
            "task_id",
            "consent_epoch",
            "policy_epoch",
            "dispatch_digest",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                raise CandidateError(
                    REASON_REQUEST_MALFORMED,
                    f"request field {field_name!r} must be a non-empty str",
                )
        if not isinstance(self.delegation_chain, tuple) or not all(
            isinstance(link, str) and link for link in self.delegation_chain
        ):
            raise CandidateError(
                REASON_REQUEST_MALFORMED, "delegation_chain must be a tuple of non-empty strs"
            )
        if not isinstance(self.proposal_lineage, tuple) or not all(
            isinstance(step, str) and step for step in self.proposal_lineage
        ):
            raise CandidateError(
                REASON_REQUEST_MALFORMED, "proposal_lineage must be a tuple of non-empty strs"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "tenant_id": self.tenant_id,
            "patient_id": self.patient_id,
            "purpose": self.purpose,
            "task_id": self.task_id,
            "consent_epoch": self.consent_epoch,
            "policy_epoch": self.policy_epoch,
            "dispatch_digest": self.dispatch_digest,
            "delegation_chain": list(self.delegation_chain),
            "proposal_lineage": list(self.proposal_lineage),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> AuthorizationRequest:
        if not isinstance(payload, Mapping):
            raise CandidateError(REASON_REQUEST_MALFORMED, "request payload must be a mapping")
        required = (
            "actor_id",
            "tenant_id",
            "patient_id",
            "purpose",
            "task_id",
            "consent_epoch",
            "policy_epoch",
            "dispatch_digest",
        )
        missing = [key for key in required if key not in payload]
        if missing:
            raise CandidateError(REASON_REQUEST_MALFORMED, f"request payload missing {missing}")
        return cls(
            actor_id=payload["actor_id"],
            tenant_id=payload["tenant_id"],
            patient_id=payload["patient_id"],
            purpose=payload["purpose"],
            task_id=payload["task_id"],
            consent_epoch=payload["consent_epoch"],
            policy_epoch=payload["policy_epoch"],
            dispatch_digest=payload["dispatch_digest"],
            delegation_chain=tuple(payload.get("delegation_chain") or ()),
            proposal_lineage=tuple(payload.get("proposal_lineage") or ()),
        )


# ---------------------------------------------------------------------------
# AuthorizationLedger — injected registry: key, clock, ancestry, live epochs.
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class _LedgerEntry:
    """Registered receipt facts used for ancestry resolution."""

    parent_ref: str
    delegation_chain_hash: str
    delegation_depth: int
    proposal_lineage_hash: str


class AuthorizationLedger:
    """In-process authorization registry (passive register; injected, never hidden).

    Carries the HMAC verification key, the frozen verification clock, the
    registered receipt ancestry (parent references, cycle-safe and bounded)
    and optional live governance epochs for the online revocation check. All
    replay decisions belong to :func:`authorize`, never to the ledger. The
    PostgreSQL-serializable registry and duplicate-consumption race are the
    scope of task IFIP_SEC-X03, deliberately out of scope here.
    """

    def __init__(
        self,
        hmac_key: bytes,
        *,
        now_epoch_seconds: int = 0,
        live_epochs: Mapping[str, str] | None = None,
    ) -> None:
        if not isinstance(hmac_key, bytes | bytearray) or len(hmac_key) < _HMAC_KEY_MIN_BYTES:
            raise CandidateError(
                "CONTEXT_KEY_TOO_SHORT",
                f"hmac_key must be >= {_HMAC_KEY_MIN_BYTES} bytes",
            )
        self.hmac_key = bytes(hmac_key)
        self.now_epoch_seconds = int(now_epoch_seconds)
        self._entries: dict[str, _LedgerEntry] = {}
        self._live_epochs: dict[str, str] = dict(live_epochs or {})

    def register(self, receipt: Receipt) -> None:
        if not isinstance(receipt, Receipt):
            raise CandidateError(REASON_RECEIPT_MALFORMED, "register expects a Receipt")
        self._entries[receipt.receipt_id] = _LedgerEntry(
            parent_ref=receipt.parent_ref,
            delegation_chain_hash=receipt.delegation_chain_hash,
            delegation_depth=receipt.delegation_depth,
            proposal_lineage_hash=receipt.proposal_lineage_hash,
        )

    def is_registered(self, receipt_id: str) -> bool:
        return receipt_id in self._entries

    def entry_of(self, receipt_id: str) -> _LedgerEntry | None:
        return self._entries.get(receipt_id)

    def live_epoch(self, kind: str) -> str | None:
        value = self._live_epochs.get(kind)
        return None if value is None else str(value)

    def set_live_epoch(self, kind: str, epoch: str) -> None:
        self._live_epochs[kind] = str(epoch)

    def verify_ancestry(self, receipt: Receipt) -> bool:
        """Walk parent references to the root; cycle-safe and bounded."""
        visited: set[str] = set()
        ref: str = receipt.parent_ref
        for _ in range(MAX_ANCESTRY_HOPS):
            if ref == ROOT_REF:
                return True
            if ref in visited:
                return False
            visited.add(ref)
            entry = self._entries.get(ref)
            if entry is None:
                return False
            ref = entry.parent_ref
        return False

    def issue(
        self,
        *,
        receipt_id: str,
        actor_id: str,
        patient_id: str,
        tenant_id: str,
        purpose: str,
        task_id: str,
        consent_epoch: str,
        policy_epoch: str,
        dispatch_digest: str,
        nonce: str,
        expiry: int,
        parent_ref: str = ROOT_REF,
        delegation_chain: Sequence[str] = (),
        proposal_lineage: Sequence[str] = (),
    ) -> Receipt:
        """Issue an HMAC-signed receipt AND register it (issue path)."""
        receipt = issue_receipt(
            hmac_key=self.hmac_key,
            receipt_id=receipt_id,
            actor_id=actor_id,
            patient_id=patient_id,
            tenant_id=tenant_id,
            purpose=purpose,
            task_id=task_id,
            consent_epoch=consent_epoch,
            policy_epoch=policy_epoch,
            dispatch_digest=dispatch_digest,
            nonce=nonce,
            expiry=expiry,
            parent_ref=parent_ref,
            delegation_chain=delegation_chain,
            proposal_lineage=proposal_lineage,
        )
        self.register(receipt)
        return receipt

    def delegate(
        self,
        parent: Receipt,
        *,
        receipt_id: str,
        delegatee_actor_id: str,
        nonce: str,
        expiry: int | None = None,
        proposal_lineage: Sequence[str] | None = None,
    ) -> Receipt:
        """Delegate ``parent`` to ``delegatee_actor_id`` (purpose-preserving).

        The child binds the SAME purpose, tenant, patient, task, epochs and
        dispatch digest as the parent (delegation never broadens scope), the
        extended delegation chain, ``parent.receipt_id`` as its parent
        reference and a FRESH consume-once nonce. Registered on issue.
        """
        if not isinstance(parent, Receipt):
            raise CandidateError(REASON_RECEIPT_MALFORMED, "delegate expects a parent Receipt")
        child = issue_receipt(
            hmac_key=self.hmac_key,
            receipt_id=receipt_id,
            actor_id=delegatee_actor_id,
            patient_id=parent.patient_id,
            tenant_id=parent.tenant_id,
            purpose=parent.purpose,
            task_id=parent.task_id,
            consent_epoch=parent.consent_epoch,
            policy_epoch=parent.policy_epoch,
            dispatch_digest=parent.dispatch_digest,
            nonce=nonce,
            expiry=parent.expiry if expiry is None else int(expiry),
            parent_ref=parent.receipt_id,
            delegation_chain=tuple(parent.delegation_chain) + (delegatee_actor_id,),
            proposal_lineage=(
                tuple(parent.proposal_lineage)
                if proposal_lineage is None
                else tuple(proposal_lineage)
            ),
        )
        self.register(child)
        return child


# ---------------------------------------------------------------------------
# Verdict + authorize pipeline.
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Verdict:
    """Authorization decision (JSON-serializable via ``to_dict``)."""

    decision: str
    reason_code: str
    receipt_id: str
    fail_closed: bool
    nonce_consumed: bool
    bindings_evaluated: tuple[str, ...]
    detail: str
    verdict_digest: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason_code": self.reason_code,
            "receipt_id": self.receipt_id,
            "fail_closed": self.fail_closed,
            "nonce_consumed": self.nonce_consumed,
            "bindings_evaluated": list(self.bindings_evaluated),
            "detail": self.detail,
            "verdict_digest": self.verdict_digest,
        }


AuthorizeFn = Callable[
    [Receipt, AuthorizationRequest, "set[str] | None", AuthorizationLedger], Verdict
]


def _finish(
    *,
    decision: str,
    reason_code: str,
    receipt_id: str,
    fail_closed: bool,
    nonce_consumed: bool,
    bindings_evaluated: Sequence[str],
) -> Verdict:
    detail_payload = {
        "candidate_id": CANDIDATE_ID,
        "candidate_version": CANDIDATE_VERSION,
        "decision": decision,
        "reason_code": reason_code,
        "receipt_id": receipt_id,
        "fail_closed": fail_closed,
        "nonce_consumed": nonce_consumed,
        "bindings_evaluated": list(bindings_evaluated),
    }
    digest_payload = {
        "decision": decision,
        "reason_code": reason_code,
        "receipt_id": receipt_id,
        "fail_closed": fail_closed,
        "nonce_consumed": nonce_consumed,
    }
    return Verdict(
        decision=decision,
        reason_code=reason_code,
        receipt_id=receipt_id,
        fail_closed=fail_closed,
        nonce_consumed=nonce_consumed,
        bindings_evaluated=tuple(bindings_evaluated),
        detail=_canonical_json(detail_payload),
        verdict_digest=_sha256_hex(_canonical_json(digest_payload)),
    )


def _authorize_pipeline(
    receipt: Receipt | None,
    request: AuthorizationRequest | None,
    nonce_store: set[str] | None,
    ledger: AuthorizationLedger | None,
    *,
    skip_lineage: bool,
    skip_nonce: bool,
) -> Verdict:
    evaluated: list[str] = []
    receipt_id = receipt.receipt_id if isinstance(receipt, Receipt) else "?"

    def deny(reason_code: str, *, fail_closed: bool = False) -> Verdict:
        return _finish(
            decision=DECISION_DENY,
            reason_code=reason_code,
            receipt_id=receipt_id,
            fail_closed=fail_closed,
            nonce_consumed=False,
            bindings_evaluated=evaluated,
        )

    # 1. Shape validation (fail closed, never raising).
    evaluated.append("shape")
    if not isinstance(receipt, Receipt):
        return deny(REASON_RECEIPT_MALFORMED, fail_closed=True)
    if not isinstance(request, AuthorizationRequest):
        return deny(REASON_REQUEST_MALFORMED, fail_closed=True)
    if ledger is None:
        return deny(REASON_LEDGER_MISSING, fail_closed=True)
    if not isinstance(ledger, AuthorizationLedger):
        return deny(REASON_LEDGER_BAD_TYPE, fail_closed=True)
    if nonce_store is None:
        return deny(REASON_NONCE_STORE_MISSING, fail_closed=True)
    if not isinstance(nonce_store, set):
        return deny(REASON_NONCE_STORE_BAD_TYPE, fail_closed=True)
    evaluated.append("nonce_form")
    if not isinstance(receipt.nonce, str) or not receipt.nonce:
        return deny(REASON_NONCE_MISSING, fail_closed=True)

    # 2. Real HMAC receipt verification (hmac + hashlib, constant-time).
    evaluated.append("hmac_receipt_integrity")
    if not verify_receipt_signature(receipt, ledger.hmac_key):
        return deny(REASON_RECEIPT_SIGNATURE_INVALID)

    # 3. Expiry against the injected clock.
    evaluated.append("expiry")
    if ledger.now_epoch_seconds > receipt.expiry:
        return deny(REASON_RECEIPT_EXPIRED)

    # 4. Ledger registration (fail closed on unknown state).
    evaluated.append("ledger_registration")
    if not ledger.is_registered(receipt.receipt_id):
        return deny(REASON_RECEIPT_UNKNOWN)

    # 5. Delegation ancestry (bounded, cycle-safe).
    evaluated.append("delegation_ancestry")
    if not ledger.verify_ancestry(receipt):
        return deny(REASON_DELEGATION_ANCESTRY_BROKEN)

    # 6. Commitment re-derivation over the unsigned transport copies.
    evaluated.append("delegation_chain_binding")
    if (
        hash_delegation_chain(receipt.delegation_chain) != receipt.delegation_chain_hash
        or len(receipt.delegation_chain) != receipt.delegation_depth
    ):
        return deny(REASON_DELEGATION_CHAIN_CHANGED)
    if not skip_lineage:
        evaluated.append("proposal_lineage_binding")
        if hash_proposal_lineage(receipt.proposal_lineage) != receipt.proposal_lineage_hash:
            return deny(REASON_LINEAGE_SPLICED)

    # 7. Request context binding against the SIGNED claims.
    for binding, expected, presented, reason_code in (
        ("purpose_binding", receipt.purpose, request.purpose, REASON_PURPOSE_MISMATCH),
        ("tenant_binding", receipt.tenant_id, request.tenant_id, REASON_TENANT_MISMATCH),
        ("actor_binding", receipt.actor_id, request.actor_id, REASON_ACTOR_MISMATCH),
        ("patient_binding", receipt.patient_id, request.patient_id, REASON_PATIENT_MISMATCH),
        ("task_binding", receipt.task_id, request.task_id, REASON_TASK_MISMATCH),
        (
            "consent_epoch_binding",
            receipt.consent_epoch,
            request.consent_epoch,
            REASON_CONSENT_EPOCH_MISMATCH,
        ),
        (
            "policy_epoch_binding",
            receipt.policy_epoch,
            request.policy_epoch,
            REASON_POLICY_EPOCH_MISMATCH,
        ),
        (
            "dispatch_binding",
            receipt.dispatch_digest,
            request.dispatch_digest,
            REASON_DISPATCH_MISMATCH,
        ),
    ):
        evaluated.append(binding)
        if expected != presented:
            return deny(reason_code)

    # 8. Optional live governance epochs (online revocation, CASE-04).
    live_consent = ledger.live_epoch("consent")
    if live_consent is not None:
        evaluated.append("live_consent_epoch")
        if receipt.consent_epoch != live_consent:
            return deny(REASON_CONSENT_EPOCH_REVOKED)
    live_policy = ledger.live_epoch("policy")
    if live_policy is not None:
        evaluated.append("live_policy_epoch")
        if receipt.policy_epoch != live_policy:
            return deny(REASON_POLICY_EPOCH_STALE)

    # 9. Request-presented chain/lineage must equal the receipt's bound state.
    evaluated.append("request_delegation_binding")
    if list(request.delegation_chain) != list(receipt.delegation_chain):
        return deny(REASON_DELEGATION_CHAIN_CHANGED)
    if not skip_lineage:
        evaluated.append("request_lineage_binding")
        if list(request.proposal_lineage) != list(receipt.proposal_lineage):
            return deny(REASON_LINEAGE_SPLICED)

    # 10. Consume-once nonce (LAST: binding failures never consume).
    if skip_nonce:
        return _finish(
            decision=DECISION_ALLOW,
            reason_code=REASON_NONCE_UNPROTECTED,
            receipt_id=receipt_id,
            fail_closed=False,
            nonce_consumed=False,
            bindings_evaluated=evaluated,
        )
    evaluated.append("consume_once_nonce")
    if receipt.nonce not in nonce_store:
        return deny(REASON_NONCE_REPLAYED)
    nonce_store.discard(receipt.nonce)
    allow_reason = REASON_LINEAGE_UNBOUND if skip_lineage else REASON_NONCE_CONSUMED_OK
    return _finish(
        decision=DECISION_ALLOW,
        reason_code=allow_reason,
        receipt_id=receipt_id,
        fail_closed=False,
        nonce_consumed=True,
        bindings_evaluated=evaluated,
    )


def authorize(
    receipt: Receipt | None,
    request: AuthorizationRequest | None,
    nonce_store: set[str] | None,
    ledger: AuthorizationLedger | None,
) -> Verdict:
    """Replay-closed authorization of ``request`` under ``receipt``.

    Total function: returns ALLOW/DENY with a stable reason code, never
    raises for case faults. See the module docstring for the canonical
    pipeline order; the nonce is consumed only after every binding passes.
    """
    return _authorize_pipeline(
        receipt, request, nonce_store, ledger, skip_lineage=False, skip_nonce=False
    )


# ---------------------------------------------------------------------------
# Ablation hooks — each removes exactly ONE mechanism.
# ---------------------------------------------------------------------------


def ablation_no_lineage_binding() -> AuthorizeFn:
    """Authorizer without the proposal-lineage binding (permits spliced lineage).

    The lineage commitment re-derivation and the request lineage comparison
    are skipped; every other mechanism (HMAC, epochs, purpose, delegation
    chain, consume-once nonce) stays enforced. On the canonical splice attack
    this authorizer ADMITs what :func:`authorize` DENYs with
    ``LINEAGE_SPLICED`` — proving the lineage binding is the mechanism.
    """

    def _authorizer(
        receipt: Receipt | None,
        request: AuthorizationRequest | None,
        nonce_store: set[str] | None,
        ledger: AuthorizationLedger | None,
    ) -> Verdict:
        return _authorize_pipeline(
            receipt, request, nonce_store, ledger, skip_lineage=True, skip_nonce=False
        )

    return _authorizer


def ablation_no_nonce() -> AuthorizeFn:
    """Authorizer without the consume-once nonce (permits exact replay).

    The nonce store is never consulted or consumed; every other mechanism
    stays enforced. On the canonical exact-replay attack this authorizer
    ADMITs what :func:`authorize` DENYs with ``NONCE_REPLAYED`` — proving the
    consume-once nonce is the mechanism.
    """

    def _authorizer(
        receipt: Receipt | None,
        request: AuthorizationRequest | None,
        nonce_store: set[str] | None,
        ledger: AuthorizationLedger | None,
    ) -> Verdict:
        return _authorize_pipeline(
            receipt, request, nonce_store, ledger, skip_lineage=False, skip_nonce=True
        )

    return _authorizer


# ---------------------------------------------------------------------------
# Mechanism description (machine-readable design record, no results).
# ---------------------------------------------------------------------------


def describe_mechanism() -> dict[str, Any]:
    """Machine-readable mechanism description (design record, no results)."""
    return {
        "candidate_id": CANDIDATE_ID,
        "candidate_version": CANDIDATE_VERSION,
        "name": "Replay-closed authorization across purpose, delegation and AI proposal lineage",
        "blueprint_arm": "B4",
        "blueprint": "research/venue2027/VENUES/ifip_sec/RESEARCH_BLUEPRINT.md",
        "phase": "P04 (candidate design; no empirical results)",
        "algorithmic_definition": [
            "shape-validate receipt/request/ledger/nonce_store (fail closed)",
            "verify HMAC-SHA256 over the canonical signed claims (hmac+hashlib, constant-time)",
            "check expiry against the injected clock",
            "require ledger registration of the receipt id (fail closed on unknown state)",
            "walk delegation ancestry to root (cycle-safe, bounded)",
            "re-derive delegation-chain hash+depth and proposal-lineage hash from transport",
            "bind request context pointwise against the signed claims (purpose, tenant, actor, patient, task, consent/policy epoch, dispatch digest)",
            "optional live governance epoch check (consent revocation / policy staleness)",
            "bind the request-presented delegation chain and proposal lineage",
            "atomically consume the once-only nonce (last step; binding failures never consume)",
        ],
        "mechanism_axes": {
            "hmac_receipt_integrity": "real HMAC-SHA256 typed-commitment receipt (hmac+hashlib)",
            "purpose_binding": "receipt purpose must equal the consuming request purpose",
            "delegation_chain_binding": "chain hash + depth commitments and ledger ancestry walk",
            "proposal_lineage_binding": "AI proposal lineage hash bound into the signed claims",
            "epoch_binding": "consent/policy epochs bound in the receipt and checked against request and live governance state",
            "dispatch_byte_binding": "dispatch digest binds the intended transport/adapter",
            "consume_once_nonce": "injected consume-once store; replay fails closed",
        },
        "replay_closure_property": (
            "any change in purpose, delegation chain, proposal lineage or epochs makes a "
            "replayed (still signature-valid) receipt fail closed before the nonce step; an "
            "unchanged replay fails closed on the consumed nonce"
        ),
        "ablation_hooks": {
            "ablation_no_lineage_binding": (
                "removes the proposal-lineage binding -> spliced lineage is ADMITTED "
                "(proves the lineage binding)"
            ),
            "ablation_no_nonce": (
                "removes the consume-once nonce -> exact replay is ADMITTED (proves the nonce)"
            ),
        },
        "fail_closed_reason_codes": list(FAIL_CLOSED_REASON_CODES),
        "determined_deny_reason_codes": list(DETERMINED_DENY_REASON_CODES),
        "allow_reason_codes": [
            REASON_NONCE_CONSUMED_OK,
            REASON_NONCE_UNPROTECTED,
            REASON_LINEAGE_UNBOUND,
        ],
        "out_of_scope": [
            "PostgreSQL-serializable nonce registry and duplicate-consumption race (IFIP_SEC-X03)",
            "lineage digest storage layout (IFIP_SEC-X02)",
            "token-size and latency measurement (RQ3 campaigns)",
        ],
    }


# ---------------------------------------------------------------------------
# Task-contract adapter: run_candidate(case, ctx) -> Outcome.
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class CandidateContext:
    """Injected execution context for :func:`run_candidate`.

    ``hmac_key`` — verification key (>= 16 bytes); ``nonce_store`` — mutable
    consume-once set; ``ledger`` — authorization registry (created from
    ``hmac_key``/``now_epoch_seconds`` when omitted); ``now_epoch_seconds`` —
    frozen clock. No hidden state.
    """

    hmac_key: bytes
    nonce_store: set[str] = dataclasses.field(default_factory=set)
    ledger: AuthorizationLedger | None = None
    now_epoch_seconds: int = 0

    def __post_init__(self) -> None:
        if self.ledger is None:
            self.ledger = AuthorizationLedger(
                self.hmac_key, now_epoch_seconds=self.now_epoch_seconds
            )


def run_candidate(case: Mapping[str, Any], ctx: CandidateContext) -> Outcome:
    """Task-contract adapter ``run_candidate(case, ctx) -> Outcome``.

    ``case`` carries ``receipt`` and ``request`` dicts; ``ctx`` is a
    :class:`CandidateContext`. ALLOW maps to ``ADMIT`` and DENY to
    ``REJECT`` (counted, first-class outcomes with the stable reason code in
    ``detail``); boundary faults (malformed payloads/context) become
    ``REJECT`` outcomes carrying their reason codes — never uncounted
    exceptions.
    """
    if not isinstance(case, Mapping):
        return Outcome(
            observed_outcome="REJECT",
            counted_as_success=True,
            retriable=False,
            detail=REASON_RECEIPT_MALFORMED,
        )
    if not isinstance(ctx, CandidateContext):
        return Outcome(
            observed_outcome="REJECT",
            counted_as_success=True,
            retriable=False,
            detail=REASON_LEDGER_BAD_TYPE,
        )
    if "receipt" not in case or "request" not in case:
        return Outcome(
            observed_outcome="REJECT",
            counted_as_success=True,
            retriable=False,
            detail=REASON_RECEIPT_MALFORMED,
        )
    try:
        receipt = Receipt.from_dict(case["receipt"])
        request = AuthorizationRequest.from_dict(case["request"])
    except CandidateError as exc:
        return Outcome(
            observed_outcome="REJECT",
            counted_as_success=True,
            retriable=False,
            detail=exc.reason_code,
        )
    verdict = authorize(receipt, request, ctx.nonce_store, ctx.ledger)
    return Outcome(
        observed_outcome="ADMIT" if verdict.decision == DECISION_ALLOW else "REJECT",
        counted_as_success=True,
        retriable=False,
        detail=verdict.reason_code,
    )


__all__ = [
    "AuthorizationLedger",
    "AuthorizationRequest",
    "AuthorizeFn",
    "CANDIDATE_ID",
    "CANDIDATE_VERSION",
    "CandidateContext",
    "CandidateError",
    "DETERMINED_DENY_REASON_CODES",
    "DECISION_ALLOW",
    "DECISION_DENY",
    "FAIL_CLOSED_REASON_CODES",
    "MAX_ANCESTRY_HOPS",
    "REASON_NONCE_CONSUMED_OK",
    "REASON_NONCE_UNPROTECTED",
    "REASON_LINEAGE_UNBOUND",
    "Receipt",
    "ROOT_REF",
    "Verdict",
    "ablation_no_lineage_binding",
    "ablation_no_nonce",
    "authorize",
    "describe_mechanism",
    "hash_delegation_chain",
    "hash_proposal_lineage",
    "issue_receipt",
    "run_candidate",
    "verify_receipt_signature",
]
