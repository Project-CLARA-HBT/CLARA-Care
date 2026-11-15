"""IFIP_SEC baseline fidelity adapters (task IFIP_SEC-baselines, phase P03).

Purpose
-------
In-process reference implementations of the blueprint's strong-baseline arms
for "Replay-Closed Authorization Across Purpose, Delegation, and AI Proposal
Lineage" (IFIP_SEC 2027). Each adapter realises the *declared semantics* of
its arm from ``research/venue2027/_shared/baselines/registry.yaml`` and the
study blueprint (``research/venue2027/VENUES/ifip_sec/RESEARCH_BLUEPRINT.md``):

- ``B0`` bearer-signed-receipt — HMAC-signed bearer receipt; checks only that
  the presented bearer token's signature verifies and it has not expired.
  No caveat binding, no consume-once state: a replayed token is ACCEPTED,
  which is the scientifically correct weakness this weak control exists to
  quantify (RQ1 lower bound).
- ``B1`` stateless purpose binding — checks the receipt's purpose/tenant/
  actor/epoch claims pointwise against the request, but has NO replay
  closure: the nonce is checked for form, never consumed against a shared
  store, so the same valid receipt replays successfully until expiry
  (stateless per-presentation caveat satisfaction, Macaroon-style).
- ``B2`` capability/macaron-style caveat check — real HMAC caveat-chain
  verification over ``hmac``/``hashlib``: caveats (actor, purpose, task,
  expiry, nonce, parent) are bound into the token signature exactly as the
  NDSS 2014 Macaroons construction attenuates a root capability; each
  caveat is checked for satisfaction at presentation. Tampering with any
  caveat byte breaks the chain. Satisfaction is still pointwise, so —
  faithfully to the published semantics — replay within expiry is admitted.
- ``B3`` nonce-store replay rejection — real consume-once set: the first
  presentation atomically consumes the nonce and ADMITs; any later
  presentation of the same nonce is REJECTED with ``NONCE_REPLAYED``.
  Application-side replay registry in the spirit of the registered
  ``cedar-opa-policy-decision-nonce-registry`` arm (in-process, injected
  store; the PostgreSQL-backed variant belongs to task IFIP_SEC-X03).
- ``B2_INPROCESS_ZANZIBAR`` (task IFIP_SEC-X06, additive in 1.1.0) — real
  in-process Zanzibar-style consistency-aware authorization reference
  (``consistency_token_adapter.py``): relation-tuple changelog with
  zookie-style consistency tokens and a relation-walk evaluator behind the
  task contract ``check_with_revision(principal, resource, token) ->
  Verdict``. A FRESH token sees a just-granted relation and rejects a
  pre-revocation replay (``RELATION_REVOKED``); a token captured before the
  revocation evaluates the earlier snapshot and faithfully admits the replay
  inside the bounded-staleness window (the published Zanzibar boundary this
  arm measures). This row does NOT replace the pinned external OpenFGA
  v1.22.1 arm ``B2_OPENFGA``, which stays NOT_RUN_EXTERNAL (rule 8).

Pinned external upstreams (OpenFGA v1.22.1 server, Cedar v4.14.1, OPA
v1.22.4 binaries) are NOT bundled in this in-process module; their adapter
arms are therefore recorded as ``NOT_RUN_EXTERNAL`` with reason code
``BASELINE_UNAVAILABLE`` per execution contract rule 8 (never replaced by a
toy under the same name). ``BASELINE_REGISTRY`` maps every baseline id to
its runnability and provenance; ``parity_check`` round-trips the B2 macaroon
caveat construction (attenuate -> serialize -> verify -> re-serialize) and
refuses any tampered variant.

Allowed input
-------------
JSON-serializable ``case`` mappings shaped like the blueprint scenario
records (``actor_id``, ``tenant_id``, ``purpose``, ``task_id``,
``policy_epoch``, ``consent_epoch``, ``nonce``, ``dispatch_digest``,
``parent_ref``, ``expiry``, plus the arm-specific ``token``/``caveats``)
and an injected :class:`BaselineContext` (HMAC key, nonce store, frozen
clock). No network, no database, no live provider access; the nonce store
and clock are always injected, never hidden.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes; errors are first-class
:class:`Outcome` values (``NOT_RUN_EXTERNAL`` / ``REJECT``), never unhandled
exceptions that could be miscounted as safe rejections. An unknown baseline
id raises :class:`BaselineError` (a wiring error, not an arm outcome).

Version
-------
``BASELINES_VERSION = "1.1.0"`` (1.0.0 = baseline fidelity adapters; 1.1.0
additively wires the IFIP_SEC-X06 in-process Zanzibar-style consistency
adapter — no pre-existing arm, registry row or reason code changed).
"""

from __future__ import annotations

import dataclasses
import hashlib
import hmac
import json
import time
from collections.abc import Mapping, Sequence
from typing import Any

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.ifip_sec.consistency_token_adapter import (
    ConsistencyError,
    ConsistencyVerdict,
    ZanzibarStore,
    bind_consistency_checker,
    check_with_revision,
)

BASELINES_VERSION = "1.1.0"

#: Blueprint arm ids and the registry baseline names they serve.
BASELINE_B0 = "B0"
BASELINE_B1 = "B1"
BASELINE_B2 = "B2"
BASELINE_B3 = "B3"

#: IFIP_SEC-X06 additive arm: in-process Zanzibar-style consistency reference.
BASELINE_B2_INPROCESS_ZANZIBAR = "B2_INPROCESS_ZANZIBAR"

#: Registry name -> blueprint arm (from _shared/baselines/registry.yaml).
REGISTRY_BASELINE_NAMES: Mapping[str, str] = {
    "bearer-signed-receipt": BASELINE_B0,
    "macaroon-hmac-caveats": BASELINE_B1,
    "zanzibar-openfga": BASELINE_B2,
    "cedar-opa-policy-decision-nonce-registry": BASELINE_B3,
}

#: Stable reason codes (uppercase, machine-checkable).
RC_OK = "OK"
RC_BASELINE_UNAVAILABLE = "BASELINE_UNAVAILABLE"
RC_TOKEN_MISSING = "TOKEN_MISSING"
RC_TOKEN_SIGNATURE_INVALID = "TOKEN_SIGNATURE_INVALID"
RC_TOKEN_EXPIRED = "TOKEN_EXPIRED"
RC_PURPOSE_MISMATCH = "PURPOSE_MISMATCH"
RC_TENANT_MISMATCH = "TENANT_MISMATCH"
RC_ACTOR_MISMATCH = "ACTOR_MISMATCH"
RC_EPOCH_MISMATCH = "EPOCH_MISMATCH"
RC_CAVEAT_VERIFICATION_FAILED = "CAVEAT_VERIFICATION_FAILED"
RC_NONCE_MISSING = "NONCE_MISSING"
RC_NONCE_REPLAYED = "NONCE_REPLAYED"
RC_CONTEXT_KEY_TOO_SHORT = "CONTEXT_KEY_TOO_SHORT"
RC_PARITY_OK = "PARITY_OK"
RC_PARITY_TAMPER_DETECTED = "PARITY_TAMPER_DETECTED"
RC_PARITY_SELFTEST_FAILED = "PARITY_SELFTEST_FAILED"

#: Caveat keys bound into the B2 HMAC chain (blueprint arm B1 caveat set).
CAVEAT_KEYS: tuple[str, ...] = (
    "actor",
    "purpose",
    "task",
    "expiry",
    "nonce",
    "parent",
)

#: Baselines whose pinned external upstream is not available in-process.
#: OpenFGA v1.22.1 / Cedar v4.14.1 / OPA v1.22.4 run as external pinned
#: binaries (registry ORIGINAL_UPSTREAM rows); this module never substitutes
#: a toy under their names (execution contract rule 8).
EXTERNAL_PINNED_BASELINES: frozenset[str] = frozenset({"B2_OPENFGA", "B3_CEDAR"})

_HMAC_KEY_MIN_BYTES = 16


class BaselineError(ValueError):
    """Wiring/configuration error carrying a stable reason code (not an arm outcome)."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclasses.dataclass
class BaselineContext:
    """Injected execution context for one baseline invocation.

    ``hmac_key`` — symmetric verification key (>= 16 bytes); injected by the
    caller, never derived from hidden state.
    ``nonce_store`` — mutable consume-once set for B3; a fresh set must be
    supplied per independent unit so retries stay deterministic.
    ``now_epoch_seconds`` — frozen verification clock (no hidden time reads).
    ``upstream_available`` — pinned external binaries visible for B2/B3
    external arms; ``False`` (the test default) yields NOT_RUN_EXTERNAL.
    """

    hmac_key: bytes
    nonce_store: set[str] | None = None
    now_epoch_seconds: int = 0
    upstream_available: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.hmac_key, bytes | bytearray) or len(self.hmac_key) < (
            _HMAC_KEY_MIN_BYTES
        ):
            raise BaselineError(
                "CONTEXT_KEY_TOO_SHORT",
                f"hmac_key must be >= {_HMAC_KEY_MIN_BYTES} bytes",
            )
        if isinstance(self.nonce_store, list):
            self.nonce_store = set(self.nonce_store)
        if self.nonce_store is not None and not isinstance(self.nonce_store, set):
            raise BaselineError("CONTEXT_STORE_BAD_TYPE", "nonce_store must be a set or None")
        if isinstance(self.now_epoch_seconds, bool) or not isinstance(self.now_epoch_seconds, int):
            raise BaselineError("CONTEXT_CLOCK_BAD_TYPE", "now_epoch_seconds must be an integer")


def _require_mapping(case: Mapping[str, Any], field: str) -> Any:
    if field not in case:
        raise BaselineError("CASE_FIELD_MISSING", f"case is missing required field {field!r}")
    return case[field]


def _receipt_digest(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sign(key: bytes, payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hmac.new(key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def issue_token(
    claims: Mapping[str, Any],
    ctx: BaselineContext,
    *,
    caveats: Mapping[str, str] | None = None,
) -> str:
    """Issue a deterministic token: ``base64url(json{claims, caveats, mac})``.

    ``claims`` is HMAC-protected; ``caveats`` (B2) are appended to the signed
    payload exactly as Macaroons bind caveats into the signature chain.
    """
    payload: dict[str, Any] = {"claims": dict(claims)}
    if caveats is not None:
        payload["caveats"] = dict(caveats)
    payload["mac"] = _sign(ctx.hmac_key, payload)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    import base64

    return base64.urlsafe_b64encode(raw).decode("ascii")


def _parse_token(token: str) -> dict[str, Any]:
    import base64

    try:
        padded = token + "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BaselineError("TOKEN_UNPARSEABLE", f"token is not decodable: {exc}") from exc
    if not isinstance(payload, dict) or "mac" not in payload:
        raise BaselineError("TOKEN_MALFORMED", "token payload lacks mac")
    return payload


def _verify_signature(payload: Mapping[str, Any], ctx: BaselineContext) -> bool:
    mac = payload.get("mac")
    expected = _sign(ctx.hmac_key, {k: v for k, v in payload.items() if k != "mac"})
    return isinstance(mac, str) and hmac.compare_digest(mac, expected)


def _outcome_reject(reason_code: str) -> Outcome:
    return Outcome(
        observed_outcome="REJECT",
        counted_as_success=True,
        retriable=False,
        detail=reason_code,
    )


def _outcome_admit(reason_code: str) -> Outcome:
    return Outcome(
        observed_outcome="ADMIT",
        counted_as_success=True,
        retriable=False,
        detail=reason_code,
    )


# ---------------------------------------------------------------------------
# B0 — bearer signed receipt (weak control): signature + expiry only.
# ---------------------------------------------------------------------------


def _run_b0(case: Mapping[str, Any], ctx: BaselineContext) -> Outcome:
    token = case.get("token")
    if not isinstance(token, str) or not token:
        return _outcome_reject(RC_TOKEN_MISSING)
    payload = _parse_token(token)
    if not _verify_signature(payload, ctx):
        return _outcome_reject(RC_TOKEN_SIGNATURE_INVALID)
    expiry = payload.get("claims", {}).get("expiry")
    if isinstance(expiry, int) and ctx.now_epoch_seconds > expiry:
        return _outcome_reject(RC_TOKEN_EXPIRED)
    # Deliberate weakness (the measured RQ1 lower bound): no caveat binding,
    # no purpose/tenant check, no nonce consumption — replay is ACCEPTED.
    return _outcome_admit("BEARER_SIGNATURE_VALID")


# ---------------------------------------------------------------------------
# B1 — stateless purpose binding: pointwise claim checks, no replay closure.
# ---------------------------------------------------------------------------


def _run_b1(case: Mapping[str, Any], ctx: BaselineContext) -> Outcome:
    token = case.get("token")
    if not isinstance(token, str) or not token:
        return _outcome_reject(RC_TOKEN_MISSING)
    payload = _parse_token(token)
    if not _verify_signature(payload, ctx):
        return _outcome_reject(RC_TOKEN_SIGNATURE_INVALID)
    claims = payload.get("claims", {})
    expiry = claims.get("expiry")
    if isinstance(expiry, int) and ctx.now_epoch_seconds > expiry:
        return _outcome_reject(RC_TOKEN_EXPIRED)
    for claim, reason in (
        ("purpose", RC_PURPOSE_MISMATCH),
        ("tenant_id", RC_TENANT_MISMATCH),
        ("actor_id", RC_ACTOR_MISMATCH),
    ):
        expected = case.get(claim)
        if expected is not None and claims.get(claim) != expected:
            return _outcome_reject(reason)
    for claim, reason in (
        ("policy_epoch", RC_EPOCH_MISMATCH),
        ("consent_epoch", RC_EPOCH_MISMATCH),
    ):
        expected = case.get(claim)
        if expected is not None and claims.get(claim) != expected:
            return _outcome_reject(reason)
    nonce = claims.get("nonce")
    if not isinstance(nonce, str) or not nonce:
        # The nonce caveat is checked for FORM ONLY — never consumed against
        # a shared store, so the same receipt replays within expiry. This is
        # the faithful stateless semantics being measured (RQ1 gap).
        return _outcome_reject(RC_NONCE_MISSING)
    return _outcome_admit("PURPOSE_BOUND_STATELESS")


# ---------------------------------------------------------------------------
# B2 — capability/macaron-style HMAC caveat chain (real crypto, pointwise).
# ---------------------------------------------------------------------------


def build_caveat_chain(
    caveats: Mapping[str, str],
    ctx: BaselineContext,
    *,
    root_identifier: str = "ifip-sec-b2",
) -> str:
    """Macaroon-style attenuation: fold each caveat into the running HMAC.

    sig_0 = HMAC(key, root_identifier); sig_i = HMAC(sig_{i-1}, f"{k}={v}")
    over the canonical :data:`CAVEAT_KEYS` order. Returns the final signature
    hex — the "signed caveats" a verifier re-derives at presentation.
    """
    missing = [key for key in CAVEAT_KEYS if key not in caveats]
    if missing:
        raise BaselineError(
            "CAVEATS_INCOMPLETE", f"caveat chain requires all {CAVEAT_KEYS}, missing {missing}"
        )
    signature = hmac.new(ctx.hmac_key, root_identifier.encode(), hashlib.sha256).digest()
    for key in CAVEAT_KEYS:
        message = f"{key}={caveats[key]}".encode()
        signature = hmac.new(signature, message, hashlib.sha256).digest()
    return signature.hex()


def verify_caveat_chain(
    caveats: Mapping[str, str],
    presented_signature: str,
    ctx: BaselineContext,
    *,
    root_identifier: str = "ifip-sec-b2",
) -> bool:
    """Re-derive the attenuation chain and constant-time compare the tag."""
    try:
        expected = build_caveat_chain(caveats, ctx, root_identifier=root_identifier)
    except BaselineError:
        return False
    return hmac.compare_digest(expected, presented_signature)


def _run_b2(case: Mapping[str, Any], ctx: BaselineContext) -> Outcome:
    caveats = case.get("caveats")
    presented = case.get("caveat_signature")
    if not isinstance(caveats, Mapping) or not caveats:
        return _outcome_reject(RC_CAVEAT_VERIFICATION_FAILED)
    if not isinstance(presented, str) or not presented:
        return _outcome_reject(RC_CAVEAT_VERIFICATION_FAILED)
    if not verify_caveat_chain(caveats, presented, ctx):
        return _outcome_reject(RC_CAVEAT_VERIFICATION_FAILED)
    # Pointwise caveat satisfaction at presentation (published Macaroons
    # semantics): binding checks against the request context.
    now = ctx.now_epoch_seconds
    expiry = caveats.get("expiry")
    try:
        expiry_int = int(expiry)
    except (TypeError, ValueError):
        return _outcome_reject(RC_CAVEAT_VERIFICATION_FAILED)
    if now > expiry_int:
        return _outcome_reject(RC_TOKEN_EXPIRED)
    for caveat, reason in (
        ("purpose", RC_PURPOSE_MISMATCH),
        ("actor", RC_ACTOR_MISMATCH),
    ):
        expected = case.get(caveat if caveat != "actor" else "actor_id")
        if expected is not None and caveats.get(caveat) != expected:
            return _outcome_reject(reason)
    # Faithful gap under measurement: the nonce caveat is satisfied by FORM,
    # never consumed from a shared store, so replay within expiry ADMITs.
    nonce = caveats.get("nonce")
    if not isinstance(nonce, str) or not nonce:
        return _outcome_reject(RC_NONCE_MISSING)
    return _outcome_admit("CAVEAT_CHAIN_VALID")


# ---------------------------------------------------------------------------
# B3 — nonce-store replay rejection: real consume-once set.
# ---------------------------------------------------------------------------


def _run_b3(case: Mapping[str, Any], ctx: BaselineContext) -> Outcome:
    if ctx.nonce_store is None:
        raise BaselineError(
            "CONTEXT_STORE_MISSING", "B3 requires an injected consume-once nonce store"
        )
    token = case.get("token")
    if not isinstance(token, str) or not token:
        return _outcome_reject(RC_TOKEN_MISSING)
    payload = _parse_token(token)
    if not _verify_signature(payload, ctx):
        return _outcome_reject(RC_TOKEN_SIGNATURE_INVALID)
    claims = payload.get("claims", {})
    expiry = claims.get("expiry")
    if isinstance(expiry, int) and ctx.now_epoch_seconds > expiry:
        return _outcome_reject(RC_TOKEN_EXPIRED)
    nonce = claims.get("nonce")
    if not isinstance(nonce, str) or not nonce:
        return _outcome_reject(RC_NONCE_MISSING)
    # Real consume-once semantics: membership test and removal happen as one
    # logical consume step (single-threaded in-process store; the
    # PostgreSQL-serializable variant is task IFIP_SEC-X03).
    if nonce not in ctx.nonce_store:
        return _outcome_reject(RC_NONCE_REPLAYED)
    ctx.nonce_store.discard(nonce)
    return _outcome_admit("NONCE_CONSUMED_ONCE")


# ---------------------------------------------------------------------------
# Registry + dispatch
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class BaselineSpec:
    """Registry row: provenance + runnability for one baseline arm."""

    baseline_id: str
    registry_name: str
    title: str
    algorithm_class: str
    runnable_in_process: bool
    upstream_url: str
    upstream_revision: str
    notes: str


BASELINE_REGISTRY: Mapping[str, BaselineSpec] = {
    spec.baseline_id: spec
    for spec in (
        BaselineSpec(
            baseline_id=BASELINE_B0,
            registry_name="bearer-signed-receipt",
            title="Bearer signed receipt (weak control)",
            algorithm_class="HMAC-signed bearer receipt without caveat binding or consume-once",
            runnable_in_process=True,
            upstream_url="https://github.com/Project-CLARA-HBT/CLARA-Care",
            upstream_revision="UNAVAILABLE",
            notes="Arm B0 weak control; in-project; replay admission is the measured signal.",
        ),
        BaselineSpec(
            baseline_id=BASELINE_B1,
            registry_name="macaroon-hmac-caveats",
            title="Stateless purpose binding (pointwise caveats, no replay closure)",
            algorithm_class="pointwise claim binding; nonce checked for form, never consumed",
            runnable_in_process=True,
            upstream_url=(
                "https://www.ndss-symposium.org/ndss2014/ndss-2014-programme/"
                "macaroons-cookies-contextual-caveats-decentralized-authorization-cloud/"
            ),
            upstream_revision="faea0d28bc33a27d625a09bdece4f1e39a8d6b23b2d1e607f58cf99d43e39aa5",
            notes=(
                "Arm B1 strong token baseline (stateless per-presentation semantics); "
                "FAITHFUL_PORT per registry; nonce-form-only gap is the RQ1 measurement."
            ),
        ),
        BaselineSpec(
            baseline_id=BASELINE_B2,
            registry_name="zanzibar-openfga",
            title="Capability/macaron-style HMAC caveat chain (real crypto)",
            algorithm_class="HMAC caveat-chain attenuation over hmac+hashlib",
            runnable_in_process=True,
            upstream_url=(
                "https://www.ndss-symposium.org/ndss2014/ndss-2014-programme/"
                "macaroons-cookies-contextual-caveats-decentralized-authorization-cloud/"
            ),
            upstream_revision="faea0d28bc33a27d625a09bdece4f1e39a8d6b23b2d1e607f58cf99d43e39aa5",
            notes=(
                "Real HMAC caveat-chain verification in-process; the OpenFGA "
                "consistency-token arm itself (pinned v1.22.1 server) runs via "
                "IFIP_SEC-X06 and is NOT_RUN_EXTERNAL here (rule 8)."
            ),
        ),
        BaselineSpec(
            baseline_id=BASELINE_B3,
            registry_name="cedar-opa-policy-decision-nonce-registry",
            title="Nonce-store replay rejection (consume-once set)",
            algorithm_class="policy decision + application-side consume-once replay registry",
            runnable_in_process=True,
            upstream_url="https://github.com/cedar-policy/cedar",
            upstream_revision="47d82a8293354f235d3f8d092c71071706401741",
            notes=(
                "In-process consume-once nonce store (PREFILLED injected set); the "
                "PostgreSQL-serializable registry and Cedar v4.14.1 PDP run via "
                "IFIP_SEC-X03 and are NOT_RUN_EXTERNAL here (rule 8)."
            ),
        ),
        BaselineSpec(
            baseline_id="B2_OPENFGA",
            registry_name="zanzibar-openfga",
            title="Zanzibar/OpenFGA consistency token (external pinned binary)",
            algorithm_class="Zanzibar-inspired ReBAC with consistency tokens",
            runnable_in_process=False,
            upstream_url="https://github.com/openfga/openfga",
            upstream_revision="44054f542f64e9b9589dd26a595081b3d2cfd942",
            notes="Pinned OpenFGA v1.22.1 server not bundled; honest NOT_RUN_EXTERNAL.",
        ),
        BaselineSpec(
            baseline_id=BASELINE_B2_INPROCESS_ZANZIBAR,
            registry_name="zanzibar-openfga",
            title=(
                "In-process Zanzibar-style consistency-aware authorization reference "
                "(task IFIP_SEC-X06)"
            ),
            algorithm_class=(
                "relation-tuple changelog + zookie consistency tokens + relation-walk "
                "evaluator behind check_with_revision(principal, resource, token) -> Verdict"
            ),
            runnable_in_process=True,
            upstream_url="https://www.usenix.org/conference/atc19/presentation/pang",
            upstream_revision=(
                "paper design reference (USENIX ATC 2019, Sec. 2.3-2.4); executable "
                "upstream path remains the pinned OpenFGA v1.22.1 server (B2_OPENFGA row)"
            ),
            notes=(
                "Additive 1.1.0 arm over consistency_token_adapter.py: implements the "
                "PUBLISHED Zanzibar snapshot/consistency semantics in-process (fresh "
                "token sees the just-granted relation; pre-revocation replay rejected "
                "only with a fresh token). Does NOT replace the pinned external OpenFGA "
                "arm B2_OPENFGA, which stays NOT_RUN_EXTERNAL (execution contract rule 8)."
            ),
        ),
        BaselineSpec(
            baseline_id="B3_CEDAR",
            registry_name="cedar-opa-policy-decision-nonce-registry",
            title="Cedar PDP + PostgreSQL nonce registry (external pinned binary)",
            algorithm_class="policy-as-code ABAC + serializable replay-nonce registry",
            runnable_in_process=False,
            upstream_url="https://github.com/cedar-policy/cedar",
            upstream_revision="47d82a8293354f235d3f8d092c71071706401741",
            notes="Pinned Cedar v4.14.1 / OPA v1.22.4 not bundled; honest NOT_RUN_EXTERNAL.",
        ),
    )
}

#: IFIP_SEC-X06 arm: the in-process Zanzibar-style reference is dispatched by
#: ``run_baseline`` through the dedicated adapter contract (``ZanzibarStore`` +
#: ``check_with_revision``), not the case/ctx ``_RUNNERS`` table above.
_ARM_VIA_ADAPTER = frozenset({BASELINE_B2_INPROCESS_ZANZIBAR})

_RUNNERS: Mapping[str, Any] = {
    BASELINE_B0: _run_b0,
    BASELINE_B1: _run_b1,
    BASELINE_B2: _run_b2,
    BASELINE_B3: _run_b3,
}


def run_zanzibar_case(case: Mapping[str, Any], ctx: BaselineContext) -> Outcome:
    """Execute the IFIP_SEC-X06 in-process Zanzibar arm on one synthetic case.

    The case must carry an injected ``zanzibar_store`` (:class:`ZanzibarStore`
    sharing ``ctx.hmac_key``), a ``zookie`` token, and the request identity
    (``actor_id``/``principal``, ``resource``, optional ``relation``). This is
    a thin adapter from the baselines case/ctx convention onto the X06 target
    contract ``check_with_revision(principal, resource, token) -> Verdict``;
    the verdict becomes a first-class Outcome (REJECT for every token fault,
    never an exception miscounted as a safe rejection).
    """
    store = case.get("zanzibar_store")
    if not isinstance(store, ZanzibarStore):
        raise BaselineError(
            "CONTEXT_STORE_MISSING",
            "case must carry an injected ZanzibarStore under 'zanzibar_store'",
        )
    principal = case.get("principal", case.get("actor_id"))
    resource = case.get("resource")
    if not isinstance(principal, str) or not isinstance(resource, str):
        raise BaselineError(
            "CASE_FIELD_MISSING", "case must carry string 'principal'/'actor_id' and 'resource'"
        )
    token = case.get("zookie")
    if not isinstance(token, str):
        return _outcome_reject(RC_TOKEN_MISSING)
    relation = case.get("relation", "viewer")
    if not isinstance(relation, str):
        raise BaselineError("CASE_FIELD_MISSING", "case 'relation' must be a string")
    verdict = check_with_revision(principal, resource, token, store=store, relation=relation)
    return Outcome(
        observed_outcome="ADMIT" if verdict.allowed else "REJECT",
        counted_as_success=True,
        retriable=False,
        detail=verdict.reason_code,
    )


def run_baseline(baseline_id: str, case: Mapping[str, Any], ctx: BaselineContext) -> Outcome:
    """Execute one baseline arm on one synthetic case; never raises for arm faults.

    Returns an :class:`Outcome` whose ``observed_outcome`` is one of
    ``ADMIT | REJECT | NOT_RUN_EXTERNAL``. Unknown baseline ids are wiring
    errors (:class:`BaselineError`); external-pinned arms whose upstream is
    unavailable return ``NOT_RUN_EXTERNAL`` with ``BASELINE_UNAVAILABLE``.
    ``ctx.upstream_available=True`` unlocks the external arms for a pinned
    run harness (still unsupported in this in-process module).
    """
    if not isinstance(case, Mapping):
        raise BaselineError("CASE_NOT_AN_OBJECT", f"case must be a mapping, got {type(case)}")
    spec = BASELINE_REGISTRY.get(baseline_id)
    if spec is None:
        known = sorted(BASELINE_REGISTRY)
        raise BaselineError(
            "BASELINE_UNKNOWN_ID", f"baseline_id {baseline_id!r} not in registry {known}"
        )
    if not spec.runnable_in_process or baseline_id in EXTERNAL_PINNED_BASELINES:
        if not ctx.upstream_available:
            return Outcome(
                observed_outcome="NOT_RUN_EXTERNAL",
                counted_as_success=False,
                retriable=True,
                detail=RC_BASELINE_UNAVAILABLE,
            )
        raise BaselineError(
            "BASELINE_EXTERNAL_UNIMPLEMENTED",
            f"{baseline_id} external pinned run requires its adapter task (X05/X03)",
        )
    if baseline_id in _ARM_VIA_ADAPTER:
        return run_zanzibar_case(case, ctx)
    try:
        return _RUNNERS[baseline_id](case, ctx)
    except BaselineError as exc:
        if exc.reason_code.startswith(("TOKEN_", "CASE_")):
            # Arm-fault evidence: a malformed/unverifiable token is a REJECT
            # outcome carrying its stable reason code — never an unhandled
            # exception that could be miscounted as a safe rejection.
            return _outcome_reject(exc.reason_code)
        raise  # wiring/context errors are configuration faults, not outcomes


# ---------------------------------------------------------------------------
# Parity check — round-trip verification of the B2 caveat construction.
# ---------------------------------------------------------------------------


def parity_check(
    caveats: Mapping[str, str],
    ctx: BaselineContext,
    *,
    tamper: Mapping[str, str] | None = None,
    root_identifier: str = "ifip-sec-b2",
) -> Outcome:
    """Round-trip the macaroon caveat construction and verify fidelity.

    Build the attenuation signature from ``caveats``, verify the chain
    round-trip, then — when ``tamper`` is supplied — prove a tampered caveat
    set fails verification (byte binding). Returns ADMIT (``PARITY_OK``) only
    if the honest round-trip verifies AND every supplied tamper vector is
    rejected; REJECT (``PARITY_TAMPER_DETECTED`` / ``PARITY_SELFTEST_FAILED``)
    otherwise.
    """
    if set(caveats) != set(CAVEAT_KEYS):
        raise BaselineError(
            "PARITY_BAD_CAVEATS", f"parity vectors must cover exactly {CAVEAT_KEYS}"
        )
    signature = build_caveat_chain(caveats, ctx, root_identifier=root_identifier)
    if not verify_caveat_chain(caveats, signature, ctx, root_identifier=root_identifier):
        return _outcome_reject(RC_PARITY_SELFTEST_FAILED)
    if tamper:
        for tampered in tamper.get("variants", []):
            if not isinstance(tampered, Mapping):
                return _outcome_reject(RC_PARITY_SELFTEST_FAILED)
            # Byte binding: a mutated caveat set presented with the HONEST
            # signature must fail verification; acceptance = broken parity.
            if verify_caveat_chain(tampered, signature, ctx, root_identifier=root_identifier):
                return _outcome_reject(RC_PARITY_TAMPER_DETECTED)
    return _outcome_admit(RC_PARITY_OK)


def token_bytes(token: str) -> int:
    """RQ3 token-size metric: serialized capability length in bytes."""
    return len(token.encode("utf-8"))


def default_clock(now_epoch_seconds: int | None = None) -> int:
    """Explicit clock for callers that need wall time; tests inject fixed values."""
    return int(time.time()) if now_epoch_seconds is None else now_epoch_seconds


__all__ = [
    "BASELINE_B0",
    "BASELINE_B1",
    "BASELINE_B2",
    "BASELINE_B2_INPROCESS_ZANZIBAR",
    "BASELINE_B3",
    "BASELINE_REGISTRY",
    "BASELINES_VERSION",
    "CAVEAT_KEYS",
    "EXTERNAL_PINNED_BASELINES",
    "REGISTRY_BASELINE_NAMES",
    "BaselineContext",
    "BaselineError",
    "BaselineSpec",
    "ConsistencyError",
    "ConsistencyVerdict",
    "ZanzibarStore",
    "bind_consistency_checker",
    "build_caveat_chain",
    "check_with_revision",
    "claims_from_case",
    "default_clock",
    "issue_token",
    "parity_check",
    "run_baseline",
    "run_zanzibar_case",
    "synthetic_case",
    "token_bytes",
    "verify_caveat_chain",
]


def synthetic_case(**overrides: Any) -> dict[str, Any]:
    """Deterministic synthetic case fixture (no randomness, no PII)."""
    base: dict[str, Any] = {
        "case_id": "IFIP_SEC-CASE-01",
        "case_family": "legitimate_same_purpose",
        "actor_id": "synthetic-actor",
        "tenant_id": "synthetic-tenant",
        "purpose": "self_care",
        "task_id": "task-medication-review",
        "policy_epoch": "epoch-7",
        "consent_epoch": "consent-3",
        "nonce": "nonce-0001",
        "dispatch_digest": "sha256:" + "0" * 64,
        "parent_ref": "root",
        "expiry": 4102444800,
    }
    base.update(overrides)
    return base


def claims_from_case(case: Mapping[str, Any]) -> dict[str, Any]:
    """Project a case onto the receipt claim set (typed commitment subset)."""
    keys: Sequence[str] = (
        "actor_id",
        "tenant_id",
        "purpose",
        "task_id",
        "policy_epoch",
        "consent_epoch",
        "nonce",
        "expiry",
    )
    return {key: case[key] for key in keys if key in case}
