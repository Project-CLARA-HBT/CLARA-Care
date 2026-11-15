"""CLARA-Care 2027 IFIP_SEC task IFIP_SEC-ablation — causal mechanism ablations.

Purpose
-------
P04 ablation registry for "Replay-Closed Authorization Across Purpose,
Delegation, and AI Proposal Lineage" (``research/venue2027/VENUES/ifip_sec/
RESEARCH_BLUEPRINT.md``; task contract ``research/venue2027/VENUES/ifip_sec/
TASKS/IFIP_SEC-ablation.md``). The P04 candidate
(:mod:`evaluation.venue2027.ifip_sec.candidate`) authorizes a consumption
request against an HMAC-bound typed-commitment receipt through a fixed
binding pipeline (shape -> HMAC -> expiry -> registration -> ancestry ->
commitment re-derivation -> request-context binding -> live governance
epochs -> presented chain/lineage -> consume-once nonce). This module runs
the candidate against ITSELF with EXACTLY ONE mechanism removed per variant,
over the SAME frozen attack/control families, so each mechanism's causal
contribution to replay closure is measurable (development-scale mechanism
causality on frozen synthetic cases — never confirmatory results; no
empirical claims, no performance numbers, no win rates).

Preregistered variants (``ABLATION_REGISTRY``; each is a real callable
reusing the candidate's own components and declaring the single ablated
mechanism via :class:`VariantSpec`):

- ``no_nonce_consume_once`` — candidate WITHOUT the consume-once nonce: the
  candidate's own preregistered hook :func:`candidate.ablation_no_nonce`
  (the nonce store is never consulted or consumed). The exact replay the
  candidate DENYs with ``NONCE_REPLAYED`` is ADMITTED.
- ``no_purpose_binding`` — candidate WITHOUT the purpose binding: the
  presented purpose is replaced by the receipt's claimed purpose before the
  unmodified candidate pipeline runs, so the purpose comparison can never
  fail (mechanically equivalent to removing the check; the input-mutation
  pattern used by the SACMAT no-expiry ablation). The purpose-switch
  presentation the candidate DENYs with ``PURPOSE_MISMATCH`` is ADMITTED.
- ``no_delegation_lineage_validation`` — candidate WITHOUT the
  delegation-lineage provenance binding: the candidate's own preregistered
  hook :func:`candidate.ablation_no_lineage_binding` (proposal-lineage
  commitment re-derivation and request-presented lineage comparison are
  skipped; the delegation-chain binding, ancestry walk, purpose, epochs and
  nonce stay enforced). The lineage splice the candidate DENYs with
  ``LINEAGE_SPLICED`` is ADMITTED.
- ``no_epoch_recheck`` — candidate WITHOUT the consent/policy epoch recheck:
  the request-presented epochs are replaced by the receipt's claimed epochs
  AND the live-governance recheck is suppressed via an epoch-blind ledger
  view (same ancestry registration, no live epochs), so the candidate's
  epoch axis (``CONSENT_EPOCH_MISMATCH`` / ``CONSENT_EPOCH_REVOKED`` /
  ``POLICY_EPOCH_MISMATCH`` / ``POLICY_EPOCH_STALE``) can never fire. The
  revoked-consent replay the candidate DENYs with ``CONSENT_EPOCH_REVOKED``
  is ADMITTED.
- ``common_safety_gate`` — the full binding pipeline REPLACED by the common
  safety gate every arm already shares: real HMAC verification
  (:func:`candidate.verify_receipt_signature`) plus the expiry check against
  the injected clock — context-free, binding-free, no replay closure. Catches
  only tampered/expired receipts; admits exact replays, purpose switches,
  lineage splices, revoked-consent replays and chain truncations.

The reference row (the unmodified full candidate) is deliberately NOT a
registered variant: a variant that removes nothing is not an ablation.
:func:`refuse_unregistered_variant` refuses unknown ids with
``UNKNOWN_ABLATION_VARIANT`` and nothing-removing identities (the full
candidate and the candidate id itself) with ``VARIANT_REMOVES_NOTHING`` —
fail closed, never silently run as a degraded or full arm. The mechanistic
inference matrix (:func:`mechanistic_inference_matrix`,
:func:`verify_mechanistic_inference_matrix`) pins every
variant x family verdict against its preregistered prediction.

Allowed input
-------------
:func:`run_ablation(name, case)` (task-manifest signature
``run_ablation(name, case) -> Outcome``): ``name`` is a registered variant
id from :data:`ABLATION_REGISTRY`; ``case`` is one JSON-serializable mapping
``{"case_id", "receipt", "request", ...}`` shaped like the candidate's
:func:`candidate.run_candidate` input, plus the injected execution state:
``ledger`` (a prebuilt :class:`candidate.AuthorizationLedger` with the
receipt already registered — the delegated-chain fixtures build it through
the candidate's own ``issue``/``delegate`` paths), or ``hmac_key`` (bytes or
str, >= 16 bytes) plus optional ``now_epoch_seconds``/``live_epochs``/
``register_receipts`` to build one; ``nonce_store`` (set or list of nonce
strings; when omitted a fresh store is primed with the receipt's nonce,
modeling the issue path — pass an explicit shared set to exercise replay).
The frozen attack/control family fixtures :func:`case_fixtures` build the
synthetic multi-principal interleavings (PHI-free; synthetic identifiers
only; no hidden clock, randomness, network or database).

Failure semantics
-----------------
Fail closed with stable uppercase reason codes; no unhandled exception is
ever miscounted as a safe rejection:
- unknown / nothing-removing variant -> ``Outcome(EXECUTION_ERROR)`` carrying
  ``UNKNOWN_ABLATION_VARIANT`` / ``VARIANT_REMOVES_NOTHING`` (the raising
  guard :func:`refuse_unregistered_variant` exposes the same codes).
- malformed case (non-mapping, missing/ill-typed case id, missing or
  unparseable receipt/request) -> ``EXECUTION_ERROR`` / ``INDETERMINATE``
  outcomes, never ``ADMIT`` or ``REJECT``.
- wiring faults (bad ledger/nonce-store/hmac-key/clock types) ->
  ``EXECUTION_ERROR`` carrying the stable reason code.
- Determined candidate verdicts map ALLOW -> ``ADMIT`` and DENY ->
  ``REJECT`` (both ``counted_as_success=True``), mirroring the candidate's
  own task-contract adapter :func:`candidate.run_candidate`; the verdict's
  ``fail_closed`` flag and reason code stay in the outcome detail.

Version
-------
``ABLATIONS_VERSION = "clara.ifip_sec.ablations-v1"`` (additive-only 1.x).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Callable, Mapping
from typing import Any, Final

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.ifip_sec import candidate as cand

ABLATIONS_VERSION: Final[str] = "clara.ifip_sec.ablations-v1"

ABLATION_TASK_ID: Final[str] = "IFIP_SEC-ablation"

#: Preregistered ablation variant ids (one mechanism removed each).
VARIANT_NO_NONCE: Final[str] = "no_nonce_consume_once"
VARIANT_NO_PURPOSE: Final[str] = "no_purpose_binding"
VARIANT_NO_LINEAGE: Final[str] = "no_delegation_lineage_validation"
VARIANT_NO_EPOCH_RECHECK: Final[str] = "no_epoch_recheck"
VARIANT_COMMON_SAFETY_GATE: Final[str] = "common_safety_gate"

#: Reference row: the unmodified candidate. Deliberately NOT registered as an
#: ablation — a variant that removes nothing is not an ablation.
REFERENCE_VARIANT_ID: Final[str] = "full_candidate"

#: Identities known to remove nothing (refused, not guessed).
NON_ABLATION_IDENTITIES: Final[frozenset[str]] = frozenset(
    {REFERENCE_VARIANT_ID, cand.CANDIDATE_ID}
)

#: Ablated mechanism axes (exactly one per variant, all distinct).
ABLATED_CONSUME_ONCE_NONCE: Final[str] = "consume_once_nonce"
ABLATED_PURPOSE_BINDING: Final[str] = "purpose_binding"
ABLATED_LINEAGE_VALIDATION: Final[str] = "delegation_lineage_validation"
ABLATED_EPOCH_RECHECK: Final[str] = "policy_consent_epoch_recheck"
ABLATED_BINDING_PIPELINE: Final[str] = "full_binding_pipeline"

#: Stable reason codes (fail closed).
RC_UNKNOWN_ABLATION_VARIANT: Final[str] = "UNKNOWN_ABLATION_VARIANT"
RC_VARIANT_REMOVES_NOTHING: Final[str] = "VARIANT_REMOVES_NOTHING"
RC_CASE_NOT_AN_OBJECT: Final[str] = "CASE_NOT_AN_OBJECT"
RC_CASE_ID_MISSING: Final[str] = "CASE_ID_MISSING"
RC_CASE_ID_NOT_STRING: Final[str] = "CASE_ID_NOT_STRING"
RC_RECEIPT_MISSING: Final[str] = "RECEIPT_MISSING"
RC_REQUEST_MISSING: Final[str] = "REQUEST_MISSING"
RC_CONTEXT_KEY_TOO_SHORT: Final[str] = "CONTEXT_KEY_TOO_SHORT"
RC_NONCE_STORE_BAD_TYPE: Final[str] = "NONCE_STORE_BAD_TYPE"
RC_LEDGER_BAD_TYPE: Final[str] = "LEDGER_BAD_TYPE"
RC_NOW_BAD_TYPE: Final[str] = "NOW_BAD_TYPE"
RC_GATE_SIGNATURE_VALID: Final[str] = "GATE_SIGNATURE_VALID_NOT_REPLAY_CLOSED"

VERDICT_ADMIT: Final[str] = "ADMIT"
VERDICT_REJECT: Final[str] = "REJECT"

#: Frozen attack/control family ids (the same suite every variant executes).
FAMILY_FRESH_CONSUMPTION: Final[str] = "fresh_consumption"
FAMILY_EXACT_REPLAY: Final[str] = "exact_replay"
FAMILY_PURPOSE_SWITCH: Final[str] = "purpose_switch"
FAMILY_LINEAGE_SPLICE: Final[str] = "lineage_splice"
FAMILY_CONSENT_REVOKED_REPLAY: Final[str] = "consent_revoked_replay"
FAMILY_TAMPERED_RECEIPT: Final[str] = "tampered_receipt"
FAMILY_CHAIN_TRUNCATION: Final[str] = "chain_truncation"
FAULT_FAMILY_IDS: Final[tuple[str, ...]] = (
    FAMILY_FRESH_CONSUMPTION,
    FAMILY_EXACT_REPLAY,
    FAMILY_PURPOSE_SWITCH,
    FAMILY_LINEAGE_SPLICE,
    FAMILY_CONSENT_REVOKED_REPLAY,
    FAMILY_TAMPERED_RECEIPT,
    FAMILY_CHAIN_TRUNCATION,
)

#: Default injected HMAC key for the frozen fixture surface (test-only bytes;
#: every real run injects its own key via the case mapping).
_DEFAULT_HMAC_KEY: Final[bytes] = b"ifip-sec-ablation-fixture-key-0123456789"

_FIXTURE_NOW: Final[int] = 1_700_000_000
_FIXTURE_EXPIRY: Final[int] = 4_102_444_800


class AblationError(ValueError):
    """Fail-closed ablation registry error with a stable reason code."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class VariantSpec:
    """One preregistered ablation variant.

    ``ablated_mechanism`` is the DECLARED single mechanism removed; a spec
    that declares no ablated mechanism (empty string) is refused at
    construction — a variant removing nothing is not an ablation.
    """

    variant_id: str
    title: str
    ablated_mechanism: str
    description: str
    expected_effect: str
    reuses: tuple[str, ...]
    applied_by: str

    def __post_init__(self) -> None:
        if not isinstance(self.ablated_mechanism, str) or not self.ablated_mechanism.strip():
            raise AblationError(
                RC_VARIANT_REMOVES_NOTHING,
                f"variant {self.variant_id!r} declares no ablated mechanism; "
                "a variant removing nothing is not an ablation",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "title": self.title,
            "ablated_mechanism": self.ablated_mechanism,
            "description": self.description,
            "expected_effect": self.expected_effect,
            "reuses": list(self.reuses),
            "applied_by": self.applied_by,
        }


ABLATION_REGISTRY: Final[Mapping[str, VariantSpec]] = {
    spec.variant_id: spec
    for spec in (
        VariantSpec(
            variant_id=VARIANT_NO_NONCE,
            title="Candidate without the consume-once nonce",
            ablated_mechanism=ABLATED_CONSUME_ONCE_NONCE,
            description=(
                "The candidate's own preregistered hook "
                "candidate.ablation_no_nonce: the consume-once store is never "
                "consulted or consumed; HMAC, expiry, registration, ancestry, "
                "chain/lineage commitments and every request binding stay "
                "enforced. An exact replay is ADMITTED where the full "
                "candidate DENYs with NONCE_REPLAYED"
            ),
            expected_effect="admits_exact_replay",
            reuses=(
                "candidate.ablation_no_nonce",
                "candidate._authorize_pipeline",
                "candidate.AuthorizationLedger",
            ),
            applied_by="candidate_ablation_hook",
        ),
        VariantSpec(
            variant_id=VARIANT_NO_PURPOSE,
            title="Candidate without the purpose binding",
            ablated_mechanism=ABLATED_PURPOSE_BINDING,
            description=(
                "The presented request purpose is replaced by the receipt's "
                "claimed purpose before the unmodified candidate pipeline "
                "runs (input-mutation ablation, the SACMAT no-expiry "
                "pattern), so the purpose comparison can never fail; every "
                "other mechanism — including the consume-once nonce — stays "
                "enforced. A purpose-switch presentation is ADMITTED where "
                "the full candidate DENYs with PURPOSE_MISMATCH"
            ),
            expected_effect="admits_purpose_switch",
            reuses=(
                "candidate.authorize",
                "candidate.AuthorizationRequest",
                "candidate.AuthorizationLedger",
            ),
            applied_by="harness_input_mutation",
        ),
        VariantSpec(
            variant_id=VARIANT_NO_LINEAGE,
            title="Candidate without the delegation-lineage validation",
            ablated_mechanism=ABLATED_LINEAGE_VALIDATION,
            description=(
                "The candidate's own preregistered hook "
                "candidate.ablation_no_lineage_binding: the proposal-lineage "
                "commitment re-derivation and the request-presented lineage "
                "comparison are skipped; the delegation-chain binding, "
                "ancestry walk, purpose, epochs and consume-once nonce stay "
                "enforced. A lineage splice is ADMITTED where the full "
                "candidate DENYs with LINEAGE_SPLICED"
            ),
            expected_effect="admits_lineage_splice",
            reuses=(
                "candidate.ablation_no_lineage_binding",
                "candidate._authorize_pipeline",
                "candidate.AuthorizationLedger",
            ),
            applied_by="candidate_ablation_hook",
        ),
        VariantSpec(
            variant_id=VARIANT_NO_EPOCH_RECHECK,
            title="Candidate without the policy/consent epoch recheck",
            ablated_mechanism=ABLATED_EPOCH_RECHECK,
            description=(
                "The request-presented consent/policy epochs are replaced by "
                "the receipt's claimed epochs AND the live-governance recheck "
                "is suppressed via an epoch-blind ledger view (same ancestry "
                "registration, no live epochs), so the candidate's epoch axis "
                "can never fire; HMAC, purpose, chain/lineage and the "
                "consume-once nonce stay enforced. A revoked-consent replay "
                "is ADMITTED where the full candidate DENYs with "
                "CONSENT_EPOCH_REVOKED"
            ),
            expected_effect="admits_revoked_consent_replay",
            reuses=(
                "candidate.authorize",
                "candidate.AuthorizationRequest",
                "candidate.AuthorizationLedger.verify_ancestry",
            ),
            applied_by="harness_input_mutation",
        ),
        VariantSpec(
            variant_id=VARIANT_COMMON_SAFETY_GATE,
            title="Candidate replaced by the common safety gate",
            ablated_mechanism=ABLATED_BINDING_PIPELINE,
            description=(
                "The full binding pipeline is REPLACED by the common safety "
                "gate every arm already shares: real HMAC verification "
                "(candidate.verify_receipt_signature) plus the expiry check "
                "against the injected clock — context-free, binding-free, no "
                "replay closure. Catches only tampered/expired receipts; "
                "admits replays, purpose switches, lineage splices, "
                "revoked-consent replays and chain truncations"
            ),
            expected_effect="admits_every_noncryptographic_attack",
            reuses=(
                "candidate.verify_receipt_signature",
                "candidate.Receipt",
                "candidate.AuthorizationLedger",
            ),
            applied_by="harness_modeled_gate",
        ),
    )
}


def refuse_unregistered_variant(name: str) -> VariantSpec:
    """Guard: return the registered spec for ``name`` or refuse fail-closed.

    Refuses (raises :class:`AblationError`):
    - any id not in :data:`ABLATION_REGISTRY` and not a known nothing-removing
      identity -> ``UNKNOWN_ABLATION_VARIANT`` (never guessed, never silently
      run as the full candidate);
    - known nothing-removing identities (the unmodified full candidate and the
      candidate id itself) -> ``VARIANT_REMOVES_NOTHING``: a variant that
      removes no mechanism is not an ablation.
    """
    spec = ABLATION_REGISTRY.get(name)
    if spec is not None:
        return spec
    if name in NON_ABLATION_IDENTITIES:
        raise AblationError(
            RC_VARIANT_REMOVES_NOTHING,
            f"{name!r} is the unmodified candidate and removes no mechanism; "
            "run candidate.authorize directly for the reference row",
        )
    raise AblationError(
        RC_UNKNOWN_ABLATION_VARIANT,
        f"variant {name!r} not in registry {sorted(ABLATION_REGISTRY)}",
    )


def variant_ids() -> tuple[str, ...]:
    """Registered ablation variant ids in canonical (registry) order."""
    return tuple(ABLATION_REGISTRY)


# ---------------------------------------------------------------------------
# Injected execution state + frozen attack/control family fixtures.
# ---------------------------------------------------------------------------


class _EpochBlindLedger(cand.AuthorizationLedger):
    """Ledger view with the live-governance epoch recheck suppressed.

    Shares the wrapped ledger's HMAC key, frozen clock and registered
    ancestry (registration and the cycle-safe ancestry walk behave
    identically) but reports NO live consent/policy epochs, so the
    candidate's live-governance recheck (step 8) can never fire. This is the
    exact mechanism removed by the ``no_epoch_recheck`` variant's online
    revocation check; the offline request-vs-receipt epoch comparison is
    separately neutralized by presenting the receipt's own epochs.
    """

    def live_epoch(self, kind: str) -> str | None:
        return None


def _epoch_blind(ledger: cand.AuthorizationLedger) -> _EpochBlindLedger:
    """Build the epoch-blind view, carrying over the ledger's registrations.

    The candidate's registry is name-private, so the view re-registers the
    same receipt ids its ancestry walk needs: the caller passes the receipts
    via ``register_view``; ``_run_no_epoch_recheck`` registers the presented
    receipt so ``is_registered``/``verify_ancestry`` behave identically to
    the wrapped ledger for the receipt under test (single-hop delegation to
    root is resolved through the re-registered chain entries).
    """
    view = _EpochBlindLedger(ledger.hmac_key, now_epoch_seconds=ledger.now_epoch_seconds)
    return view


def register_epoch_blind_view(
    ledger: cand.AuthorizationLedger, *receipts: cand.Receipt
) -> _EpochBlindLedger:
    """Epoch-blind view of ``ledger`` with the given receipts re-registered.

    The candidate's registry is name-private, so every receipt needed by the
    ancestry walk (the presented receipt AND its registered ancestors) must
    be re-registered into the view; callers obtain them from the case's
    ``registered_receipts`` payloads. A parent reference that does not
    resolve on the ORIGINAL ledger still does not resolve here (ancestry
    faults are never masked — the view only removes the live-epoch recheck).
    """
    view = _epoch_blind(ledger)
    seen: set[str] = set()
    for receipt in receipts:
        if receipt.receipt_id in seen:
            continue
        seen.add(receipt.receipt_id)
        view.register(receipt)
    return view


def _base_delegated_case(live_epochs: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Issue + register a delegated receipt through the candidate's own paths.

    Root receipt (attending-physician) -> delegated receipt (resident-
    physician) with an extended delegation chain and the carried proposal
    lineage; the case carries the FULL injected state (ledger with both
    receipts registered, fresh consume-once store, matching request). The
    optional ``live_epochs`` seeds the ledger's live-governance state (the
    online revocation recheck), staying ``None`` (offline) by default.
    """
    ledger = cand.AuthorizationLedger(
        _DEFAULT_HMAC_KEY, now_epoch_seconds=_FIXTURE_NOW, live_epochs=live_epochs
    )
    root = ledger.issue(
        receipt_id="receipt-root-0001",
        actor_id="attending-physician",
        patient_id="synthetic-patient",
        tenant_id="synthetic-tenant",
        purpose="self_care",
        task_id="task-medication-review",
        consent_epoch="consent-3",
        policy_epoch="epoch-7",
        dispatch_digest="sha256:" + "a" * 64,
        nonce="nonce-root-0000",
        expiry=_FIXTURE_EXPIRY,
        delegation_chain=("attending-physician",),
        proposal_lineage=("proposal-A1", "proposal-A2"),
    )
    delegated = ledger.delegate(
        root,
        receipt_id="receipt-delegated-0001",
        delegatee_actor_id="resident-physician",
        nonce="nonce-delegated-0001",
        proposal_lineage=("proposal-A1", "proposal-A2"),
    )
    request = {
        "actor_id": "resident-physician",
        "tenant_id": "synthetic-tenant",
        "patient_id": "synthetic-patient",
        "purpose": "self_care",
        "task_id": "task-medication-review",
        "consent_epoch": "consent-3",
        "policy_epoch": "epoch-7",
        "dispatch_digest": "sha256:" + "a" * 64,
        "delegation_chain": list(delegated.delegation_chain),
        "proposal_lineage": list(delegated.proposal_lineage),
    }
    return {
        "case_id": "IFIP_SEC-ABL-BASE",
        "receipt": delegated.to_dict(),
        "request": request,
        "ledger": ledger,
        "nonce_store": {delegated.nonce},
        "registered_receipts": [root.to_dict(), delegated.to_dict()],
    }


# ---------------------------------------------------------------------------
# Frozen attack/control family fixture builders.
# ---------------------------------------------------------------------------


def _hmac_key_bytes(hmac_key: Any) -> bytes:
    if isinstance(hmac_key, str):
        return hmac_key.encode("utf-8")
    if isinstance(hmac_key, bytes | bytearray):
        return bytes(hmac_key)
    raise AblationError(
        RC_CONTEXT_KEY_TOO_SHORT, f"hmac_key must be bytes/str, got {type(hmac_key)}"
    )


def _ledger_from_case(case: Mapping[str, Any]) -> cand.AuthorizationLedger:
    """Build or extract the injected authorization ledger (never hidden state)."""
    ledger = case.get("ledger")
    if ledger is not None:
        if not isinstance(ledger, cand.AuthorizationLedger):
            raise AblationError(
                RC_LEDGER_BAD_TYPE,
                f"case 'ledger' must be an AuthorizationLedger, got {type(ledger)}",
            )
        return ledger
    hmac_key = _hmac_key_bytes(case.get("hmac_key", _DEFAULT_HMAC_KEY))
    try:
        now = int(case.get("now_epoch_seconds", 0))
    except (TypeError, ValueError) as exc:
        raise AblationError(RC_NOW_BAD_TYPE, f"now_epoch_seconds unusable: {exc}") from exc
    live_epochs = case.get("live_epochs") or {}
    ledger = cand.AuthorizationLedger(hmac_key, now_epoch_seconds=now, live_epochs=live_epochs)
    if case.get("register_receipts", True):
        receipts = case.get("registered_receipts") or ()
        for payload in receipts:
            ledger.register(cand.Receipt.from_dict(payload))
    return ledger


def _nonce_store_from_case(case: Mapping[str, Any], receipt: cand.Receipt) -> set[str]:
    """Build the injected consume-once store (fresh-primed when omitted)."""
    store = case.get("nonce_store")
    if store is None:
        return {receipt.nonce}
    if isinstance(store, set):
        return store
    if isinstance(store, list) and all(isinstance(item, str) for item in store):
        return set(store)
    raise AblationError(
        RC_NONCE_STORE_BAD_TYPE, "nonce_store must be a set/list of nonce strings or None"
    )


def _fresh_consumption_case() -> dict[str, Any]:
    """Control: a correctly-bound first consumption (delegated receipt)."""
    return _base_delegated_case()


def _exact_replay_case() -> dict[str, Any]:
    """Attack: the SAME receipt presented twice against a shared nonce store."""
    case = _base_delegated_case()
    # First presentation (pre-executed): the nonce is already consumed, so the
    # case models the SECOND presentation of the exact same receipt.
    ledger = _ledger_from_case(case)
    receipt = cand.Receipt.from_dict(case["receipt"])
    ledger.register(receipt)
    case["ledger"] = ledger
    case["nonce_store"] = set()  # consumed by the first presentation
    return case


def _purpose_switch_case() -> dict[str, Any]:
    """Attack: a self_care receipt presented under a research purpose."""
    case = _base_delegated_case()
    request = dict(case["request"])
    request["purpose"] = "secondary_research"
    case["request"] = request
    return case


def _lineage_splice_case() -> dict[str, Any]:
    """Attack: the receipt carried with a spliced AI proposal lineage."""
    case = _base_delegated_case()
    request = dict(case["request"])
    request["proposal_lineage"] = ["proposal-ATTACKER-SPLICED"]
    case["request"] = request
    return case


def _consent_revoked_replay_case() -> dict[str, Any]:
    """Attack: consent revoked between issue and presentation (epoch bump)."""
    case = _base_delegated_case(live_epochs={"consent": "consent-4", "policy": "epoch-7"})
    # The replayed receipt still carries the stale consent-3 epoch; the
    # ledger's live governance has moved to consent-4, so the full candidate
    # must DENY with CONSENT_EPOCH_REVOKED at the live recheck.
    return case


def _tampered_receipt_case() -> dict[str, Any]:
    """Attack: a receipt whose patient claim was tampered after issuance."""
    case = _base_delegated_case()
    receipt = dict(case["receipt"])
    receipt["patient_id"] = "synthetic-patient-B"
    case["receipt"] = receipt
    return case


def _chain_truncation_case() -> dict[str, Any]:
    """Attack: the delegation chain truncated to drop the delegating root."""
    case = _base_delegated_case()
    request = dict(case["request"])
    request["delegation_chain"] = ["resident-physician"]
    case["request"] = request
    return case


_CASE_FIXTURE_BUILDERS: Final[Mapping[str, Callable[[], dict[str, Any]]]] = {
    FAMILY_FRESH_CONSUMPTION: _fresh_consumption_case,
    FAMILY_EXACT_REPLAY: _exact_replay_case,
    FAMILY_PURPOSE_SWITCH: _purpose_switch_case,
    FAMILY_LINEAGE_SPLICE: _lineage_splice_case,
    FAMILY_CONSENT_REVOKED_REPLAY: _consent_revoked_replay_case,
    FAMILY_TAMPERED_RECEIPT: _tampered_receipt_case,
    FAMILY_CHAIN_TRUNCATION: _chain_truncation_case,
}


def case_fixtures() -> Mapping[str, Callable[[], dict[str, Any]]]:
    """Frozen attack/control family fixture builders (fresh dict per call)."""
    return dict(_CASE_FIXTURE_BUILDERS)


# ---------------------------------------------------------------------------
# Preregistered mechanistic inference matrix (predictions BEFORE execution).
# ---------------------------------------------------------------------------

#: (variant_id, family_id) -> preregistered verdict. Derived from each
#: variant's declared mechanism semantics; pinned before any run. The
#: reference row (full candidate) is the detection ceiling the ablations are
#: compared against.
PREDICTED_VERDICTS: Final[Mapping[tuple[str, str], str]] = {
    # Reference ceiling: the full candidate admits ONLY the fresh control.
    (REFERENCE_VARIANT_ID, FAMILY_FRESH_CONSUMPTION): VERDICT_ADMIT,
    (REFERENCE_VARIANT_ID, FAMILY_EXACT_REPLAY): VERDICT_REJECT,
    (REFERENCE_VARIANT_ID, FAMILY_PURPOSE_SWITCH): VERDICT_REJECT,
    (REFERENCE_VARIANT_ID, FAMILY_LINEAGE_SPLICE): VERDICT_REJECT,
    (REFERENCE_VARIANT_ID, FAMILY_CONSENT_REVOKED_REPLAY): VERDICT_REJECT,
    (REFERENCE_VARIANT_ID, FAMILY_TAMPERED_RECEIPT): VERDICT_REJECT,
    (REFERENCE_VARIANT_ID, FAMILY_CHAIN_TRUNCATION): VERDICT_REJECT,
    # no_nonce_consume_once: exact replay slips through; nothing else changes.
    (VARIANT_NO_NONCE, FAMILY_FRESH_CONSUMPTION): VERDICT_ADMIT,
    (VARIANT_NO_NONCE, FAMILY_EXACT_REPLAY): VERDICT_ADMIT,
    (VARIANT_NO_NONCE, FAMILY_PURPOSE_SWITCH): VERDICT_REJECT,
    (VARIANT_NO_NONCE, FAMILY_LINEAGE_SPLICE): VERDICT_REJECT,
    (VARIANT_NO_NONCE, FAMILY_CONSENT_REVOKED_REPLAY): VERDICT_REJECT,
    (VARIANT_NO_NONCE, FAMILY_TAMPERED_RECEIPT): VERDICT_REJECT,
    (VARIANT_NO_NONCE, FAMILY_CHAIN_TRUNCATION): VERDICT_REJECT,
    # no_purpose_binding: purpose switch slips through; nothing else changes.
    (VARIANT_NO_PURPOSE, FAMILY_FRESH_CONSUMPTION): VERDICT_ADMIT,
    (VARIANT_NO_PURPOSE, FAMILY_EXACT_REPLAY): VERDICT_REJECT,
    (VARIANT_NO_PURPOSE, FAMILY_PURPOSE_SWITCH): VERDICT_ADMIT,
    (VARIANT_NO_PURPOSE, FAMILY_LINEAGE_SPLICE): VERDICT_REJECT,
    (VARIANT_NO_PURPOSE, FAMILY_CONSENT_REVOKED_REPLAY): VERDICT_REJECT,
    (VARIANT_NO_PURPOSE, FAMILY_TAMPERED_RECEIPT): VERDICT_REJECT,
    (VARIANT_NO_PURPOSE, FAMILY_CHAIN_TRUNCATION): VERDICT_REJECT,
    # no_delegation_lineage_validation: splice slips through; nonce still
    # enforced so the exact replay is still caught; the delegation-chain
    # binding (separate axis) still catches the chain truncation.
    (VARIANT_NO_LINEAGE, FAMILY_FRESH_CONSUMPTION): VERDICT_ADMIT,
    (VARIANT_NO_LINEAGE, FAMILY_EXACT_REPLAY): VERDICT_REJECT,
    (VARIANT_NO_LINEAGE, FAMILY_PURPOSE_SWITCH): VERDICT_REJECT,
    (VARIANT_NO_LINEAGE, FAMILY_LINEAGE_SPLICE): VERDICT_ADMIT,
    (VARIANT_NO_LINEAGE, FAMILY_CONSENT_REVOKED_REPLAY): VERDICT_REJECT,
    (VARIANT_NO_LINEAGE, FAMILY_TAMPERED_RECEIPT): VERDICT_REJECT,
    (VARIANT_NO_LINEAGE, FAMILY_CHAIN_TRUNCATION): VERDICT_REJECT,
    # no_epoch_recheck: revoked-consent replay slips through; nothing else.
    (VARIANT_NO_EPOCH_RECHECK, FAMILY_FRESH_CONSUMPTION): VERDICT_ADMIT,
    (VARIANT_NO_EPOCH_RECHECK, FAMILY_EXACT_REPLAY): VERDICT_REJECT,
    (VARIANT_NO_EPOCH_RECHECK, FAMILY_PURPOSE_SWITCH): VERDICT_REJECT,
    (VARIANT_NO_EPOCH_RECHECK, FAMILY_LINEAGE_SPLICE): VERDICT_REJECT,
    (VARIANT_NO_EPOCH_RECHECK, FAMILY_CONSENT_REVOKED_REPLAY): VERDICT_ADMIT,
    (VARIANT_NO_EPOCH_RECHECK, FAMILY_TAMPERED_RECEIPT): VERDICT_REJECT,
    (VARIANT_NO_EPOCH_RECHECK, FAMILY_CHAIN_TRUNCATION): VERDICT_REJECT,
    # common_safety_gate: signature+expiry only — every noncryptographic
    # attack passes; the fresh control passes; tampering is still caught.
    (VARIANT_COMMON_SAFETY_GATE, FAMILY_FRESH_CONSUMPTION): VERDICT_ADMIT,
    (VARIANT_COMMON_SAFETY_GATE, FAMILY_EXACT_REPLAY): VERDICT_ADMIT,
    (VARIANT_COMMON_SAFETY_GATE, FAMILY_PURPOSE_SWITCH): VERDICT_ADMIT,
    (VARIANT_COMMON_SAFETY_GATE, FAMILY_LINEAGE_SPLICE): VERDICT_ADMIT,
    (VARIANT_COMMON_SAFETY_GATE, FAMILY_CONSENT_REVOKED_REPLAY): VERDICT_ADMIT,
    (VARIANT_COMMON_SAFETY_GATE, FAMILY_TAMPERED_RECEIPT): VERDICT_REJECT,
    (VARIANT_COMMON_SAFETY_GATE, FAMILY_CHAIN_TRUNCATION): VERDICT_ADMIT,
}


# ---------------------------------------------------------------------------
# Variant runners (each reuses candidate components; one mechanism removed).
# ---------------------------------------------------------------------------


def _run_no_nonce(
    case: Mapping[str, Any],
    receipt: cand.Receipt,
    request: cand.AuthorizationRequest,
    nonce_store: set[str],
    ledger: cand.AuthorizationLedger,
) -> cand.Verdict:
    """Ablated mechanism: consume-once nonce (candidate hook ablation_no_nonce)."""
    return cand.ablation_no_nonce()(receipt, request, nonce_store, ledger)


def _run_no_purpose(
    case: Mapping[str, Any],
    receipt: cand.Receipt,
    request: cand.AuthorizationRequest,
    nonce_store: set[str],
    ledger: cand.AuthorizationLedger,
) -> cand.Verdict:
    """Ablated mechanism: purpose binding (presented purpose forced to match)."""
    bound_request = cand.AuthorizationRequest(
        actor_id=request.actor_id,
        tenant_id=request.tenant_id,
        patient_id=request.patient_id,
        purpose=receipt.purpose,
        task_id=request.task_id,
        consent_epoch=request.consent_epoch,
        policy_epoch=request.policy_epoch,
        dispatch_digest=request.dispatch_digest,
        delegation_chain=request.delegation_chain,
        proposal_lineage=request.proposal_lineage,
    )
    return cand.authorize(receipt, bound_request, nonce_store, ledger)


def _run_no_lineage(
    case: Mapping[str, Any],
    receipt: cand.Receipt,
    request: cand.AuthorizationRequest,
    nonce_store: set[str],
    ledger: cand.AuthorizationLedger,
) -> cand.Verdict:
    """Ablated mechanism: delegation-lineage validation (candidate hook)."""
    return cand.ablation_no_lineage_binding()(receipt, request, nonce_store, ledger)


def _run_no_epoch_recheck(
    case: Mapping[str, Any],
    receipt: cand.Receipt,
    request: cand.AuthorizationRequest,
    nonce_store: set[str],
    ledger: cand.AuthorizationLedger,
) -> cand.Verdict:
    """Ablated mechanism: policy/consent epoch recheck (epochs forced + live off)."""
    bound_request = cand.AuthorizationRequest(
        actor_id=request.actor_id,
        tenant_id=request.tenant_id,
        patient_id=request.patient_id,
        purpose=request.purpose,
        task_id=request.task_id,
        consent_epoch=receipt.consent_epoch,
        policy_epoch=receipt.policy_epoch,
        dispatch_digest=request.dispatch_digest,
        delegation_chain=request.delegation_chain,
        proposal_lineage=request.proposal_lineage,
    )
    ancestry = case.get("registered_receipts") or ()
    blind = register_epoch_blind_view(
        ledger, receipt, *(cand.Receipt.from_dict(payload) for payload in ancestry)
    )
    return cand.authorize(receipt, bound_request, nonce_store, blind)


def _run_common_safety_gate(
    case: Mapping[str, Any],
    receipt: cand.Receipt,
    request: cand.AuthorizationRequest,
    nonce_store: set[str],
    ledger: cand.AuthorizationLedger,
) -> cand.Verdict:
    """Ablated mechanism: the full binding pipeline (common safety gate instead).

    The gate is the HMAC verification plus expiry check every arm already
    shares, evaluated over the receipt alone: signature valid AND not expired
    -> ALLOW (context-free, binding-free, no replay closure; the nonce store
    is never consulted). Any other request binding is ignored.
    """
    evaluated: tuple[str, ...] = ("gate_hmac_receipt_integrity", "gate_expiry")
    if not cand.verify_receipt_signature(receipt, ledger.hmac_key):
        return _gate_verdict(
            cand.REASON_RECEIPT_SIGNATURE_INVALID, ledger, evaluated, allowed=False
        )
    if ledger.now_epoch_seconds > receipt.expiry:
        return _gate_verdict(cand.REASON_RECEIPT_EXPIRED, ledger, evaluated, allowed=False)
    return _gate_verdict(RC_GATE_SIGNATURE_VALID, ledger, evaluated, allowed=True)


def _gate_verdict(
    reason_code: str,
    ledger: cand.AuthorizationLedger,
    evaluated: tuple[str, ...],
    *,
    allowed: bool,
) -> cand.Verdict:
    receipt_id = "?"
    return cand.Verdict(
        decision=cand.DECISION_ALLOW if allowed else cand.DECISION_DENY,
        reason_code=reason_code,
        receipt_id=receipt_id,
        fail_closed=False,
        nonce_consumed=False,
        bindings_evaluated=evaluated,
        detail=(f"common_safety_gate|{reason_code}|now={ledger.now_epoch_seconds}"),
        verdict_digest=hashlib.sha256(
            json.dumps({"decision": allowed, "reason_code": reason_code}, sort_keys=True).encode(
                "utf-8"
            )
        ).hexdigest(),
    )


_VARIANT_RUNNERS: Final[
    Mapping[
        str,
        Callable[..., cand.Verdict],
    ]
] = {
    VARIANT_NO_NONCE: _run_no_nonce,
    VARIANT_NO_PURPOSE: _run_no_purpose,
    VARIANT_NO_LINEAGE: _run_no_lineage,
    VARIANT_NO_EPOCH_RECHECK: _run_no_epoch_recheck,
    VARIANT_COMMON_SAFETY_GATE: _run_common_safety_gate,
}


# ---------------------------------------------------------------------------
# Task-manifest signature adapter: run_ablation(name, case) -> Outcome.
# ---------------------------------------------------------------------------


def _outcome(observed_outcome: str, counted_as_success: bool, detail: str) -> Outcome:
    return Outcome(
        observed_outcome=observed_outcome,
        counted_as_success=counted_as_success,
        retriable=False,
        detail=detail,
    )


def _refusal_outcome(exc: AblationError) -> Outcome:
    return _outcome("EXECUTION_ERROR", False, f"{exc.reason_code}: {exc.detail}")


def _parse_case(
    case: Mapping[str, Any],
) -> tuple[cand.Receipt, cand.AuthorizationRequest, set[str], cand.AuthorizationLedger] | Outcome:
    """Validate and parse the case payload (fail closed, never raising)."""
    if "receipt" not in case:
        return _outcome("INDETERMINATE", False, f"{ABLATIONS_VERSION}|{RC_RECEIPT_MISSING}")
    if "request" not in case:
        return _outcome("INDETERMINATE", False, f"{ABLATIONS_VERSION}|{RC_REQUEST_MISSING}")
    try:
        ledger = _ledger_from_case(case)
        receipt = cand.Receipt.from_dict(case["receipt"])
        request = cand.AuthorizationRequest.from_dict(case["request"])
        nonce_store = _nonce_store_from_case(case, receipt)
    except AblationError as exc:
        return _outcome(
            "EXECUTION_ERROR", False, f"{ABLATIONS_VERSION}|{exc.reason_code}: {exc.detail}"
        )
    except cand.CandidateError as exc:
        return _outcome(
            "EXECUTION_ERROR", False, f"{ABLATIONS_VERSION}|{exc.reason_code}: {exc.detail}"
        )
    return receipt, request, nonce_store, ledger


def run_ablation(name: str, case: Mapping[str, Any]) -> Outcome:
    """Task-manifest signature: run ONE ablation variant on ONE case.

    - Determined outcomes: candidate ALLOW -> ``ADMIT`` and DENY ->
      ``REJECT`` (both ``counted_as_success=True``); the ``detail`` JSON
      carries the variant id, the declared ablated mechanism, the reason
      code and the fail-closed flag.
    - Fail closed: unknown variant or nothing-removing identity ->
      ``EXECUTION_ERROR`` with ``UNKNOWN_ABLATION_VARIANT`` /
      ``VARIANT_REMOVES_NOTHING``; malformed case -> ``INDETERMINATE`` /
      ``EXECUTION_ERROR`` (never ``ADMIT``/``REJECT``, never counted);
      wiring errors surface as ``EXECUTION_ERROR`` carrying stable reason
      codes.
    """
    try:
        spec = refuse_unregistered_variant(name)
    except AblationError as exc:
        return _refusal_outcome(exc)
    if not isinstance(case, Mapping):
        return _outcome(
            "EXECUTION_ERROR",
            False,
            f"{RC_CASE_NOT_AN_OBJECT}: case must be a mapping, got {type(case).__name__}",
        )
    case_id = case.get("case_id")
    if case_id is None:
        return _outcome("INDETERMINATE", False, f"{ABLATIONS_VERSION}|{RC_CASE_ID_MISSING}")
    if not isinstance(case_id, str) or not case_id:
        return _outcome("INDETERMINATE", False, f"{ABLATIONS_VERSION}|{RC_CASE_ID_NOT_STRING}")
    parsed = _parse_case(case)
    if isinstance(parsed, Outcome):
        return parsed
    receipt, request, nonce_store, ledger = parsed
    verdict = _VARIANT_RUNNERS[name](case, receipt, request, nonce_store, ledger)
    observed = VERDICT_ADMIT if verdict.decision == cand.DECISION_ALLOW else VERDICT_REJECT
    detail = json.dumps(
        {
            "ablations_version": ABLATIONS_VERSION,
            "variant_id": name,
            "ablated_mechanism": spec.ablated_mechanism,
            "case_id": case_id,
            "decision": verdict.decision,
            "reason_code": verdict.reason_code,
            "fail_closed": verdict.fail_closed,
            "nonce_consumed": verdict.nonce_consumed,
            "bindings_evaluated": list(verdict.bindings_evaluated),
        },
        sort_keys=True,
    )
    return _outcome(observed, True, detail)


# ---------------------------------------------------------------------------
# Mechanistic inference matrix: preregistered predictions + verification run.
# ---------------------------------------------------------------------------


def _run_reference(case: Mapping[str, Any]) -> Outcome:
    """The unmodified candidate (reference row; not an ablation)."""
    if not isinstance(case, Mapping):
        return _outcome("EXECUTION_ERROR", False, f"{RC_CASE_NOT_AN_OBJECT}")
    parsed = _parse_case(case)
    if isinstance(parsed, Outcome):
        return parsed
    receipt, request, nonce_store, ledger = parsed
    verdict = cand.authorize(receipt, request, nonce_store, ledger)
    observed = VERDICT_ADMIT if verdict.decision == cand.DECISION_ALLOW else VERDICT_REJECT
    return _outcome(observed, True, verdict.reason_code)


def _observed_verdict(outcome: Outcome) -> str:
    return outcome.observed_outcome


def _degradation_summary(predicted: Mapping[tuple[str, str], str]) -> dict[str, Any]:
    """Families where an ablation's verdict degrades vs the reference row."""
    summary: dict[str, Any] = {}
    for variant_id in ABLATION_REGISTRY:
        missed = sorted(
            family
            for family in FAULT_FAMILY_IDS
            if predicted[(variant_id, family)] == VERDICT_ADMIT
            and predicted[(REFERENCE_VARIANT_ID, family)] == VERDICT_REJECT
        )
        false_flagged = sorted(
            family
            for family in FAULT_FAMILY_IDS
            if predicted[(variant_id, family)] == VERDICT_REJECT
            and predicted[(REFERENCE_VARIANT_ID, family)] == VERDICT_ADMIT
        )
        summary[variant_id] = {
            "missed_families": missed,
            "false_flagged_families": false_flagged,
            "measurably_degraded": bool(missed or false_flagged),
        }
    return summary


def mechanistic_inference_matrix() -> dict[str, Any]:
    """Preregistered DESIGN RECORD: variant x family predicted verdicts.

    Predictions are frozen constants (:data:`PREDICTED_VERDICTS`) derived from
    each variant's declared mechanism semantics BEFORE any execution
    (prespecified, per the task contract). No results live here.
    """
    return {
        "ablations_version": ABLATIONS_VERSION,
        "reference_variant": REFERENCE_VARIANT_ID,
        "fault_families": list(FAULT_FAMILY_IDS),
        "variants": {vid: spec.to_dict() for vid, spec in ABLATION_REGISTRY.items()},
        "predicted_verdicts": {
            variant_id: {
                family: PREDICTED_VERDICTS[(variant_id, family)] for family in FAULT_FAMILY_IDS
            }
            for variant_id in (REFERENCE_VARIANT_ID, *ABLATION_REGISTRY)
        },
        "degradation_axes": _degradation_summary(PREDICTED_VERDICTS),
        "scale": "DEVELOPMENT (mechanism causality; NOT confirmatory)",
    }


def verify_mechanistic_inference_matrix() -> dict[str, Any]:
    """Run EVERY variant over EVERY frozen attack family and compare.

    Each cell executes the variant on the family fixture (fresh dict per
    call), maps the candidate verdict to REJECT/ADMIT and compares against
    the preregistered prediction. Any mismatch means the mechanistic story is
    falsified and must be resolved before the ablation registry may be used —
    never repaired post hoc to match an observed run.
    """
    fixtures = case_fixtures()
    runners: dict[str, Callable[[Mapping[str, Any]], Outcome]] = {
        REFERENCE_VARIANT_ID: _run_reference,
        **{vid: (lambda case, _vid=vid: run_ablation(_vid, case)) for vid in ABLATION_REGISTRY},
    }
    cells: list[dict[str, Any]] = []
    all_match = True
    observed_verdicts: dict[tuple[str, str], str] = {}
    for variant_id, runner in runners.items():
        for family in FAULT_FAMILY_IDS:
            outcome = runner(fixtures[family]())
            observed = _observed_verdict(outcome)
            predicted = PREDICTED_VERDICTS[(variant_id, family)]
            match = observed == predicted
            all_match = all_match and match
            observed_verdicts[(variant_id, family)] = observed
            cells.append(
                {
                    "variant_id": variant_id,
                    "family_id": family,
                    "predicted": predicted,
                    "observed": observed,
                    "match": match,
                    "detail": outcome.detail,
                }
            )
    observed_degradation = _degradation_summary(observed_verdicts)
    return {
        "ablations_version": ABLATIONS_VERSION,
        "all_cells_match": all_match,
        "cell_count": len(cells),
        "cells": cells,
        "observed_verdicts": {
            variant_id: {
                family: observed_verdicts[(variant_id, family)] for family in FAULT_FAMILY_IDS
            }
            for variant_id in runners
        },
        "observed_degradation": observed_degradation,
        "predicted_degradation": _degradation_summary(PREDICTED_VERDICTS),
        "scale": "DEVELOPMENT (mechanism causality; NOT confirmatory)",
    }


def describe_ablations() -> dict[str, Any]:
    """Machine-readable ablation design record (no empirical results here)."""
    return {
        "ablations_version": ABLATIONS_VERSION,
        "task_id": ABLATION_TASK_ID,
        "phase": "P04 (development-scale mechanism ablation)",
        "candidate_id": cand.CANDIDATE_ID,
        "reference_variant": REFERENCE_VARIANT_ID,
        "registry": {vid: spec.to_dict() for vid, spec in ABLATION_REGISTRY.items()},
        "fault_families": list(FAULT_FAMILY_IDS),
        "manifest_signature": "run_ablation(name: str, case: Mapping) -> Outcome",
        "refusal_codes": [RC_UNKNOWN_ABLATION_VARIANT, RC_VARIANT_REMOVES_NOTHING],
    }


__all__ = [
    "ABLATION_REGISTRY",
    "ABLATION_TASK_ID",
    "ABLATIONS_VERSION",
    "AblationError",
    "FAULT_FAMILY_IDS",
    "PREDICTED_VERDICTS",
    "RC_UNKNOWN_ABLATION_VARIANT",
    "RC_VARIANT_REMOVES_NOTHING",
    "REFERENCE_VARIANT_ID",
    "VARIANT_COMMON_SAFETY_GATE",
    "VARIANT_NO_EPOCH_RECHECK",
    "VARIANT_NO_LINEAGE",
    "VARIANT_NO_NONCE",
    "VARIANT_NO_PURPOSE",
    "VariantSpec",
    "case_fixtures",
    "describe_ablations",
    "mechanistic_inference_matrix",
    "refuse_unregistered_variant",
    "run_ablation",
    "variant_ids",
    "verify_mechanistic_inference_matrix",
]
