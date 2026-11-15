"""CLARA-Care 2027 POPETS task POPETS-X02_revocation_events — post-revocation semantics.

Purpose
-------
Formalize the post-revocation security semantics for the paper *Revocation-Complete
Future Disclosure for Cached Longitudinal AI Contexts*
(``research/venue2027/VENUES/popets/RESEARCH_BLUEPRINT.md``,
``research/venue2027/popets/novelty_contract.md``,
``research/venue2027/popets/threat_model.md``).

The exact target contract is ``allowed(item, principal, purpose, time) -> TriDecision``
(``ALLOW | DENY | INDETERMINATE``) that PRECISELY distinguishes four orthogonal
questions that consent-revocation designs routinely conflate:

1. **Deletion of stored data** — platform-side invalidation of stored records and
   derived artifacts (lineage nodes) after ``t_r``. Reported as a separate
   :class:`StoredDataEffect` (``deleted | retained_unknown | not_applicable``), never
   folded into the disclosure verdict.
2. **Prevention of future disclosure** — every dispatch at or after ``t_r`` whose
   lineage intersects ``forbidden_label(g, p)`` is denied. This is the ONLY thing the
   verdict ``ALLOW``/``DENY`` speaks about (threat model §2 noninterference predicate
   ``forbidden_label(g, p) ∩ lineage(d) = ∅``).
3. **Downstream already-delivered bytes** — content dispatched to an external provider
   strictly before ``t_r`` cannot be retracted. A stored-data deletion of the platform
   copy is reported, but the disclosure verdict does NOT claim retroactive erasure:
   the effect carries ``OUT_OF_SCOPE_PAST`` (threat model §5.2, POPETS-CASE-06).
4. **Model memorization** — anything a provider's model learned from already-delivered
   bytes is *not guaranteed removable* by any platform-side control. Reported as
   ``memorization_guarantee = "NOT_GUARANTEED"`` (machine unlearning is a different
   threat: novelty contract C2). It never drives a ``DENY``-as-erasure-guarantee; it is
   surfaced as an honest, non-actionable limitation alongside the verdict.

Explicit ``RevocationSemantics`` (versioned) states exactly what is and is not
promised after ``t_r``; see :func:`revocation_semantics` and the ``semantics`` field
of :class:`RevocationDecision`.

Allowed input
-------------
- ``item``: a JSON-serializable :class:`DispatchItem`-style mapping (or instance) with
  at least ``item_id``; optional ``lineage`` (list of artifact ids), ``sent_at``
  (logical dispatch instant), ``already_delivered`` (bool: bytes left the process
  boundary before the query), ``stored_copy`` (bool: a stored platform-side artifact
  exists), ``consent_epoch`` (payload-bound epoch).
- ``principal``: non-empty string subject key (tenant-scoped principal; synthetic
  identifiers only).
- ``purpose``: non-empty declared purpose string.
- ``time``: non-negative integer logical time (the consent ledger's logical clock —
  threat model §2 R5; no hidden wall clock).
- Ledger state: a :class:`ConsentLedgerView` (or mapping of the same shape) providing
  grants, revocations and epochs. Injected; the module performs no I/O.

Failure semantics (fail closed, stable uppercase reason codes — never an unhandled
exception counted as a safe rejection):
- ``ITEM_MALFORMED`` / ``PRINCIPAL_MALFORMED`` / ``PURPOSE_UNKNOWN`` /
  ``TIME_MALFORMED`` — ill-typed or out-of-domain inputs.
- ``TIME_BEFORE_GRANT`` — the query time precedes the grant instant: the clock itself
  is untrustworthy for this request, so the decision is ``INDETERMINATE``
  (never guessed).
- ``PURPOSE_NOT_CONSENTED`` — the purpose is not among the grant's consented purposes:
  determined ``DENY`` (purpose scope, POPETS-CASE-05), distinct from an *unknown*
  purpose string which is refused outright.
- ``GRANT_UNKNOWN`` — no grant for the principal at all: determined ``DENY``.
- ``LINEAGE_INDETERMINATE`` — a lineage node lacks a verifiable origin/epoch label:
  ``INDETERMINATE`` and fail closed (POPETS-CASE-07); never a silent safe rejection.
- ``INDETERMINATE`` is a first-class verdict and is never coerced to ``DENY`` or
  ``ALLOW`` by this module (the caller decides the fail-closed action).

Guarantee boundary (threat model §10, novelty contract §5.4): this model governs
*future* dispatches after ``t_r`` only. Already-delivered bytes are ``OUT_OF_SCOPE_PAST``;
no claim of cryptographic retroactive erasure and no claim of guaranteed LLM
unlearning is made anywhere.

Version
-------
``REVOCATION_MODEL_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any, Literal

__all__ = [
    "ALLOWED_VERDICTS",
    "REVOCATION_MODEL_VERSION",
    "REASON_CODE_UNKNOWN_PURPOSE",
    "ConsentLedgerView",
    "DispatchItem",
    "MemorizationGuarantee",
    "RevocationDecision",
    "RevocationSemantics",
    "StoredDataEffect",
    "TriDecision",
    "allowed",
    "effective_revocation_time",
    "revocation_semantics",
    "stored_data_effect",
]

REVOCATION_MODEL_VERSION = "1.0.0"

TriDecision = Literal["ALLOW", "DENY", "INDETERMINATE"]

ALLOWED_VERDICTS: tuple[str, ...] = ("ALLOW", "DENY", "INDETERMINATE")

REASON_CODE_UNKNOWN_PURPOSE = "PURPOSE_UNKNOWN"

#: Reason codes are stable, uppercase, machine-readable identifiers.
REASON_ITEM_MALFORMED = "ITEM_MALFORMED"
REASON_PRINCIPAL_MALFORMED = "PRINCIPAL_MALFORMED"
REASON_TIME_MALFORMED = "TIME_MALFORMED"
REASON_GRANT_UNKNOWN = "GRANT_UNKNOWN"
REASON_PURPOSE_NOT_CONSENTED = "PURPOSE_NOT_CONSENTED"
REASON_TIME_BEFORE_GRANT = "TIME_BEFORE_GRANT"
REASON_LINEAGE_INDETERMINATE = "LINEAGE_INDETERMINATE"
REASON_EPOCH_STALE = "DENY_EPOCH_STALE"
REASON_POST_REVOCATION = "DENY_POST_REVOCATION"
REASON_AUTHORIZED = "ALLOWED_ACTIVE_CONSENT"

#: Stored-data effect vocabulary (deletion of stored platform-side data).
StoredDataEffect = Literal["deleted", "retained_unknown", "not_applicable"]

#: What the platform can promise about a provider-side model's memory of content
#: learned from already-delivered bytes. Always NOT_GUARANTEED in this scope.
MemorizationGuarantee = Literal["NOT_GUARANTEED"]

#: Effect recorded for content already delivered strictly before ``t_r``.
OUT_OF_SCOPE_PAST = "OUT_OF_SCOPE_PAST"

UNGUARANTEED_MEMORIZATION: MemorizationGuarantee = "NOT_GUARANTEED"


# ---------------------------------------------------------------------------
# Input contracts (JSON-serializable typed objects)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ConsentLedgerView:
    """Injected, append-only consent-ledger projection (no I/O, no clock).

    ``grants`` maps ``principal -> {"granted_at": int, "purposes": [str, ...],
    "consent_epoch": int}``. ``revocations`` is a list of
    ``{"principal", "purpose" ("*" wildcard allowed), "revoked_at"}`` entries. The
    ledger is authoritative for grant instants, purposes, epochs and ``t_r``
    (threat model §4); a missing entry must lead to a fail-closed verdict, never a
    default-allow.
    """

    grants: Mapping[str, Mapping[str, Any]]
    revocations: tuple[Mapping[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "grants": {k: dict(v) for k, v in self.grants.items()},
            "revocations": [dict(r) for r in self.revocations],
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> ConsentLedgerView:
        if raw is None:
            return cls(grants={}, revocations=())
        grants_raw = raw.get("grants", {})
        rev_raw = raw.get("revocations", [])
        if not isinstance(grants_raw, Mapping) or not isinstance(rev_raw, list | tuple):
            raise ValueError(
                f"{REASON_ITEM_MALFORMED}: ledger must be an object with grants/revocations"
            )
        return cls(
            grants={str(k): dict(v) for k, v in grants_raw.items()},
            revocations=tuple(dict(r) for r in rev_raw if isinstance(r, Mapping)),
        )


@dataclasses.dataclass(frozen=True)
class DispatchItem:
    """One outbound item whose disclosure is being gated.

    ``lineage`` is the artifact-id set consulted to assemble the item
    (threat model §1 derivation paths). ``item_epoch`` is the consent epoch the
    payload was assembled under. ``already_delivered`` marks bytes that left the
    process boundary strictly before this query (retry/fallback re-issue of a
    pre-``t_r`` payload); a stored platform-side copy may still exist
    (``stored_copy``) — the two questions are orthogonal by design.
    """

    item_id: str
    lineage: frozenset[str] = frozenset()
    item_epoch: int | None = None
    already_delivered: bool = False
    stored_copy: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "lineage": sorted(self.lineage),
            "item_epoch": self.item_epoch,
            "already_delivered": self.already_delivered,
            "stored_copy": self.stored_copy,
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | DispatchItem | None) -> DispatchItem:
        if raw is None:
            raise ValueError(f"{REASON_ITEM_MALFORMED}: item is required")
        if isinstance(raw, DispatchItem):
            return raw
        if not isinstance(raw, Mapping):
            raise ValueError(f"{REASON_ITEM_MALFORMED}: item must be an object")
        item_id = raw.get("item_id")
        if not isinstance(item_id, str) or not item_id:
            raise ValueError(f"{REASON_ITEM_MALFORMED}: item_id must be a non-empty string")
        lineage_raw = raw.get("lineage", [])
        if isinstance(lineage_raw, list | tuple | set | frozenset):
            lineage = frozenset(str(x) for x in lineage_raw)
        else:
            raise ValueError(f"{REASON_ITEM_MALFORMED}: lineage must be an array of artifact ids")
        epoch = raw.get("item_epoch")
        if epoch is not None and (isinstance(epoch, bool) or not isinstance(epoch, int)):
            raise ValueError(f"{REASON_ITEM_MALFORMED}: item_epoch must be an integer or null")
        return cls(
            item_id=item_id,
            lineage=lineage,
            item_epoch=epoch,
            already_delivered=bool(raw.get("already_delivered", False)),
            stored_copy=bool(raw.get("stored_copy", True)),
        )


# ---------------------------------------------------------------------------
# Output contracts
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class RevocationDecision:
    """Verdict + the orthogonal post-revocation effects; JSON-serializable."""

    decision: TriDecision
    reason_code: str
    item_id: str
    principal: str
    purpose: str
    time: int
    stored_data: StoredDataEffect
    already_delivered_effect: str | None
    memorization_guarantee: MemorizationGuarantee | None
    semantics_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason_code": self.reason_code,
            "item_id": self.item_id,
            "principal": self.principal,
            "purpose": self.purpose,
            "time": self.time,
            "stored_data": self.stored_data,
            "already_delivered_effect": self.already_delivered_effect,
            "memorization_guarantee": self.memorization_guarantee,
            "semantics_version": self.semantics_version,
            "model_version": REVOCATION_MODEL_VERSION,
        }


# ---------------------------------------------------------------------------
# The explicit post-revocation semantics contract
# ---------------------------------------------------------------------------

_SEMANTICS_SINGLETON: RevocationSemantics | None = None


@dataclasses.dataclass(frozen=True)
class RevocationSemantics:
    """Explicit statement of what revocation at ``t_r`` does and does not promise.

    This is the normative semantics surface of the task: every promise is a field,
    every non-promise is an explicit refusal, so downstream studies can cite exact
    clauses instead of prose.
    """

    version: str
    future_disclosure_prevented: bool
    deletion_of_stored_data_promised: bool
    deletion_scope: str
    retroactive_erasure_of_delivered_bytes: bool
    model_memorization_erasure: bool
    model_memorization_guarantee: MemorizationGuarantee
    retry_replay_prevented: bool
    purpose_boundary_enforced: bool
    indeterminate_fail_closed: bool
    guarantees: tuple[str, ...]
    non_guarantees: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "future_disclosure_prevented": self.future_disclosure_prevented,
            "deletion_of_stored_data_promised": self.deletion_of_stored_data_promised,
            "deletion_scope": self.deletion_scope,
            "retroactive_erasure_of_delivered_bytes": self.retroactive_erasure_of_delivered_bytes,
            "model_memorization_erasure": self.model_memorization_erasure,
            "model_memorization_guarantee": self.model_memorization_guarantee,
            "retry_replay_prevented": self.retry_replay_prevented,
            "purpose_boundary_enforced": self.purpose_boundary_enforced,
            "indeterminate_fail_closed": self.indeterminate_fail_closed,
            "guarantees": list(self.guarantees),
            "non_guarantees": list(self.non_guarantees),
            "model_version": REVOCATION_MODEL_VERSION,
        }


def revocation_semantics() -> RevocationSemantics:
    """The versioned, immutable semantics statement (singleton)."""
    global _SEMANTICS_SINGLETON
    if _SEMANTICS_SINGLETON is None:
        _SEMANTICS_SINGLETON = RevocationSemantics(
            version="1.0.0",
            future_disclosure_prevented=True,
            deletion_of_stored_data_promised=True,
            deletion_scope=(
                "Platform-side stored records and derived artifacts (lineage nodes) "
                "reachable from the revoked (principal, purpose) scope are deleted or "
                "invalidated; storage deletion is reported separately from the "
                "disclosure verdict and never conflated with it."
            ),
            retroactive_erasure_of_delivered_bytes=False,
            model_memorization_erasure=False,
            model_memorization_guarantee=UNGUARANTEED_MEMORIZATION,
            retry_replay_prevented=True,
            purpose_boundary_enforced=True,
            indeterminate_fail_closed=True,
            guarantees=(
                "G1 Future disclosure: every dispatch with query time >= t_r whose "
                "forbidden_label(g, p) intersects lineage(d) is DENY (threat model §2).",
                "G2 Purpose boundary: a purpose outside the grant's consented set is DENY "
                "(PURPOSE_NOT_CONSENTED) regardless of revocation state.",
                "G3 Replay prevention: re-issued payloads bound to a superseded consent "
                "epoch are DENY (DENY_EPOCH_STALE) on every transport.",
                "G4 Stored-data deletion: the platform-side copy of revoked scope is "
                "deleted/invalidated and reported via stored_data='deleted'.",
                "G5 Fail closed: unknown purpose strings, times before the grant and "
                "unlabelled lineage yield INDETERMINATE/refusal, never a guessed decision.",
            ),
            non_guarantees=(
                "N1 OUT_OF_SCOPE_PAST: bytes already delivered to any external provider "
                "strictly before t_r cannot be retracted (threat model §5.2); the "
                "platform-side stored copy deletion is reported but the verdict makes no "
                "claim about provider-held copies.",
                "N2 Model memorization: content a provider's model learned from "
                "already-delivered bytes is NOT guaranteed removable (machine unlearning "
                "is a different threat; novelty contract C2); memorization_guarantee is "
                "always NOT_GUARANTEED and never converted into a DENY-as-erasure claim.",
                "N3 No cryptographic retroactive erasure is claimed anywhere in this scope.",
                "N4 INDETERMINATE is a first-class outcome; it is never counted as a safe "
                "rejection nor as a completion by this module.",
            ),
        )
    return _SEMANTICS_SINGLETON


# ---------------------------------------------------------------------------
# Ledger helpers
# ---------------------------------------------------------------------------


def _grant_for(ledger: ConsentLedgerView, principal: str) -> Mapping[str, Any] | None:
    entry = ledger.grants.get(principal)
    if entry is None:
        return None
    granted_at = entry.get("granted_at")
    if isinstance(granted_at, bool) or not isinstance(granted_at, int) or granted_at < 0:
        return None
    return entry


def effective_revocation_time(
    ledger: ConsentLedgerView, principal: str, purpose: str
) -> int | None:
    """Earliest revocation instant covering (principal, purpose); None if none.

    A revocation with ``purpose == "*"`` covers every purpose of the principal
    (subject-wide withdrawal, X05 semantics); a purpose-specific revocation covers
    only that purpose. Malformed revocation rows are ignored by THIS helper only
    when they cannot match (they can never *create* a later t_r); a row that would
    match but lacks a usable instant leaves the covering set empty for that row —
    the caller's fail-closed behavior for unlabelled lineage still applies.
    """
    times: list[int] = []
    for rev in ledger.revocations:
        if str(rev.get("principal", "")) != principal:
            continue
        rev_purpose = str(rev.get("purpose", "*"))
        if rev_purpose not in (purpose, "*"):
            continue
        revoked_at = rev.get("revoked_at")
        if isinstance(revoked_at, bool) or not isinstance(revoked_at, int) or revoked_at < 0:
            continue
        times.append(revoked_at)
    return min(times) if times else None


# ---------------------------------------------------------------------------
# Stored-data effect (orthogonal surface: deletion of stored data)
# ---------------------------------------------------------------------------


def stored_data_effect(
    ledger: ConsentLedgerView, principal: str, purpose: str, time: int
) -> StoredDataEffect:
    """Classify the platform-side *stored data* consequence at ``time``.

    - ``"deleted"``: a covering revocation is in force at ``time`` (the stored copy
      and its derived lineage nodes are deleted/invalidated platform-side).
    - ``"not_applicable"``: no covering revocation (consent active) — deletion is not
      part of any current obligation.
    - ``"retained_unknown"``: the query time is before the covering revocation's
      effect or lineage provenance is unverifiable — the platform cannot promise what
      a downstream store retains; reported honestly, never folded into the verdict.
    """
    grant = _grant_for(ledger, principal)
    if grant is None:
        return "not_applicable"
    t_r = effective_revocation_time(ledger, principal, purpose)
    if t_r is None:
        return "not_applicable"
    if time >= t_r:
        return "deleted"
    return "retained_unknown"


# ---------------------------------------------------------------------------
# Core contract: allowed(item, principal, purpose, time) -> TriDecision
# ---------------------------------------------------------------------------


def allowed(
    item: Mapping[str, Any] | DispatchItem,
    principal: str,
    purpose: str,
    time: int,
    ledger: ConsentLedgerView | Mapping[str, Any] | None = None,
) -> TriDecision:
    """Return ``ALLOW``/``DENY``/``INDETERMINATE`` for one outbound item.

    Precise semantics (see module docstring and :func:`revocation_semantics`):

    1. ``DENY`` — determined denial of *future disclosure*: consent revoked at or
       before ``time`` for the covering purpose (``DENY_POST_REVOCATION``); purpose
       outside the consented set (``PURPOSE_NOT_CONSENTED``); payload bound to a
       superseded consent epoch (``DENY_EPOCH_STALE``); no grant at all
       (``GRANT_UNKNOWN``).
    2. ``ALLOW`` — active consent, purpose consented, verifiable lineage and epoch:
       the item may be disclosed *now*; nothing about the past is claimed.
    3. ``INDETERMINATE`` — fail closed: unknown purpose string
       (``PURPOSE_UNKNOWN``), query time before the grant instant
       (``TIME_BEFORE_GRANT`` — the clock is untrustworthy for this request),
       malformed item/principal/time (refusals surfaced as ValueError with stable
       reason codes), lineage nodes lacking verifiable labels
       (``LINEAGE_INDETERMINATE``). Never coerced to ``DENY``/``ALLOW`` here.

    Already-delivered bytes and model memorization do NOT change the verdict: they
    are orthogonal limits of what revocation can promise
    (:class:`RevocationDecision` carries them via ``already_delivered_effect`` /
    ``memorization_guarantee``; :func:`decide` is the full-decision variant).

    Raises ``ValueError`` with a stable reason code on malformed input (an explicit
    refusal, never an unhandled crash counted as a safe rejection).
    """
    return decide(item, principal, purpose, time, ledger).decision


def decide(
    item: Mapping[str, Any] | DispatchItem,
    principal: str,
    purpose: str,
    time: int,
    ledger: ConsentLedgerView | Mapping[str, Any] | None = None,
) -> RevocationDecision:
    """Full-decision variant of :func:`allowed` including orthogonal effects."""
    # --- input validation (fail closed on malformed domain, stable codes) ----
    if isinstance(principal, bool) or not isinstance(principal, str) or not principal:
        raise ValueError(f"{REASON_PRINCIPAL_MALFORMED}: principal must be a non-empty string")
    if isinstance(purpose, bool) or not isinstance(purpose, str) or not purpose:
        raise ValueError(f"{REASON_CODE_UNKNOWN_PURPOSE}: purpose must be a non-empty string")
    if isinstance(time, bool) or not isinstance(time, int) or time < 0:
        raise ValueError(f"{REASON_TIME_MALFORMED}: time must be a non-negative integer")

    parsed_item = DispatchItem.from_mapping(item)
    ledger_view = (
        ledger
        if isinstance(ledger, ConsentLedgerView)
        else ConsentLedgerView.from_mapping(ledger if isinstance(ledger, Mapping) else None)
    )

    grant = _grant_for(ledger_view, principal)
    if grant is None:
        decision, reason = _deny(REASON_GRANT_UNKNOWN, "no grant for principal")
        return _finish(decision, reason, parsed_item, principal, purpose, time, ledger_view)

    granted_at = int(grant["granted_at"])
    if time < granted_at:
        # Clock before grant: the ledger's own timeline says this query cannot be
        # evaluated; fail closed as INDETERMINATE, never guessed.
        return _finish(
            "INDETERMINATE",
            REASON_TIME_BEFORE_GRANT,
            parsed_item,
            principal,
            purpose,
            time,
            ledger_view,
        )

    purposes = grant.get("purposes", [])
    if not isinstance(purposes, list | tuple) or not all(isinstance(p, str) for p in purposes):
        purposes = []
    if purpose not in purposes:
        # Unknown purpose *string* is refused (INDETERMINATE, cannot even be placed
        # in the ledger's purpose vocabulary); a known-but-unconsented purpose is a
        # determined DENY (purpose scope, POPETS-CASE-05).
        decision, reason = _purpose_refusal(purpose, ledger_view, principal)
        return _finish(decision, reason, parsed_item, principal, purpose, time, ledger_view)

    t_r = effective_revocation_time(ledger_view, principal, purpose)
    post_revocation = t_r is not None and time >= t_r

    # --- epoch binding: replayed payloads from a superseded epoch are denied ---
    item_epoch = parsed_item.item_epoch
    live_epoch = grant.get("consent_epoch", 0)
    if (
        not post_revocation
        and isinstance(item_epoch, int)
        and isinstance(live_epoch, int)
        and item_epoch != live_epoch
    ):
        decision, reason = _deny(REASON_EPOCH_STALE, "payload bound to superseded consent epoch")
        return _finish(decision, reason, parsed_item, principal, purpose, time, ledger_view)

    # --- lineage gate: forbidden_label(g, p) ∩ lineage(d) = ∅ -----------------
    # Lineage nodes must be verifiable: a node is verifiable iff it is labelled
    # with its origin (present in the synthetic label table below) or it is an
    # explicitly epoch-tagged derived node. The label table is injected via the
    # grant entry ("lineage_labels": {artifact_id: label|None}); a MISSING label
    # is an unknown-ancestry probe (POPETS-CASE-07) -> INDETERMINATE.
    labels = grant.get("lineage_labels", {})
    if not isinstance(labels, Mapping):
        labels = {}
    for node in sorted(parsed_item.lineage):
        if node not in labels:
            return _finish(
                "INDETERMINATE",
                REASON_LINEAGE_INDETERMINATE,
                parsed_item,
                principal,
                purpose,
                time,
                ledger_view,
            )
        if labels[node] is None:
            return _finish(
                "INDETERMINATE",
                REASON_LINEAGE_INDETERMINATE,
                parsed_item,
                principal,
                purpose,
                time,
                ledger_view,
            )

    if post_revocation:
        # Future disclosure prevention: every post-t_r dispatch in the revoked
        # scope is denied (revocation-complete by consent-scope denial; the
        # candidate B4 closure refines *which* artifacts, the verdict for revoked
        # scope is DENY either way under the declared observation model).
        decision, reason = _deny(REASON_POST_REVOCATION, "dispatch at/after t_r")
        return _finish(decision, reason, parsed_item, principal, purpose, time, ledger_view)

    return _finish(
        "ALLOW",
        REASON_AUTHORIZED,
        parsed_item,
        principal,
        purpose,
        time,
        ledger_view,
    )


def _purpose_refusal(
    purpose: str, ledger_view: ConsentLedgerView, principal: str
) -> tuple[TriDecision, str]:
    """Unknown purpose string -> INDETERMINATE refusal; known-but-unconsented -> DENY."""
    known_purposes: set[str] = set()
    for entry in ledger_view.grants.values():
        vals = entry.get("purposes", [])
        if isinstance(vals, list | tuple):
            known_purposes.update(str(p) for p in vals)
    for rev in ledger_view.revocations:
        rp = rev.get("purpose")
        if isinstance(rp, str) and rp != "*":
            known_purposes.add(rp)
    if purpose not in known_purposes:
        return "INDETERMINATE", REASON_CODE_UNKNOWN_PURPOSE
    return "DENY", REASON_PURPOSE_NOT_CONSENTED


def _deny(reason: str, detail: str) -> tuple[TriDecision, str]:
    del detail
    return "DENY", reason


def _finish(
    decision: TriDecision,
    reason: str,
    item: DispatchItem,
    principal: str,
    purpose: str,
    time: int,
    ledger: ConsentLedgerView,
) -> RevocationDecision:
    """Attach the orthogonal post-revocation effects to any verdict."""
    effect = stored_data_effect(ledger, principal, purpose, time)
    if item.already_delivered:
        delivered_effect: str | None = OUT_OF_SCOPE_PAST
        memorization: MemorizationGuarantee | None = UNGUARANTEED_MEMORIZATION
    else:
        delivered_effect = None
        memorization = None
    if effect == "deleted" and item.stored_copy is False:
        effect = "not_applicable"
    return RevocationDecision(
        decision=decision,
        reason_code=reason,
        item_id=item.item_id,
        principal=principal,
        purpose=purpose,
        time=time,
        stored_data=effect,
        already_delivered_effect=delivered_effect,
        memorization_guarantee=memorization,
        semantics_version=revocation_semantics().version,
    )
