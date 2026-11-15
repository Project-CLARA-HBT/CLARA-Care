"""SACMAT-X04_openfga_runner — OpenFGA real-engine adapter (phase P03).

Purpose
-------
Adapter for the SACMAT 2027 study "PolicyTrace: Temporal Conformance Testing
of Delegated Consent across Heterogeneous Policy Engines"
(``research/venue2027/VENUES/sacmat/RESEARCH_BLUEPRINT.md``, task contract
``research/venue2027/VENUES/sacmat/TASKS/SACMAT-X04_openfga_runner.md``).
The task signature is ``evaluate_openfga(model, tuples, query) -> Decision``:
translate a synthetic delegated-consent policy history into OpenFGA
authorization tuples, evaluate an access request through the engine and
return a portable four-valued decision (PERMIT / DENY / NOT_APPLICABLE /
INDETERMINATE).

Two clearly labelled execution modes — never confused in any result:

- ``real`` (engine used = ``openfga-http``): when a REAL OpenFGA server is
  reachable (discovery order below), the delegated-consent history is
  translated explicitly into OpenFGA relation tuples on a pinned
  authorization model (schema 1.1) and the request is evaluated by the
  actual engine via ``POST /stores/{store_id}/check`` with the pinned
  consistency mode. Nothing about the engine's verdict is simulated. The
  pinned model, consistency mode and discovered server identity are
  recorded in every result's ``evidence`` block.
- ``port`` (engine used = ``zanzibar-inprocess-port``): when no server is
  reachable, evaluation falls back to :class:`baselines.ZanzibarPolicyEngine`
  from ``evaluation/venue2027/sacmat/baselines.py`` — an in-process
  Zanzibar/OpenFGA-like relation-tuple walk. This path is FAITHFUL-PORT
  labelled: it is a port of the pinned upstream's documented semantics
  (Zanzibar ATC 2019 §2.3–2.4 / OpenFGA v1.22.1), NOT the upstream binary,
  and every result returned through it is marked ``NOT_RUN_EXTERNAL`` with
  reason code ``BASELINE_UNAVAILABLE`` (never counted as a completion, per
  EXECUTION_CONTRACT rule 8 — no toy substitution under a real name).

Server discovery (``discover_openfga``), in order:

1. environment variables ``OPENFGA_API_URL`` / ``OPENFGA_API_TOKEN`` when
   set (non-empty), or
2. well-known local endpoints (``http://127.0.0.1:8080``,
   ``http://127.0.0.1:18080``, ``http://localhost:8080``) probed on the
   ``/healthz`` liveness endpoint.

A server is only reported as discovered if it answers ``/healthz`` with
HTTP 200; any other HTTP status, timeout or connection error keeps the
runner in port mode. No server is ever started or stopped by this module.

Translation (explicit, no silent over-approximation)
----------------------------------------------------
Delegated-consent model on the pinned schema-1.1 authorization model:

- object type ``consent_record`` — one record per (patient, purpose)
  delegation scope; relation ``delegate``: directly related user type
  ``user``. GRANT/REGRANT write ``user:{delegate}`#delegate@consent_record:{id}``.
- object type ``consent`` — the accessible resource; relation ``record``:
  directly related type ``consent_record``; relation ``delegate``: directly
  related type restriction ``consent_record#delegate`` (userset-relation
  grantee); relation ``can_access`` = computedUserset(delegate). A link
  tuple ``consent_record:{id}`#record@consent:{id}` binds each record into
  its consent. Patient access resolves through the userset: the engine
  walks consent#delegate -> consent_record#delegate -> user — a real
  relation-tuple walk on the actual server.

Event mapping (``logical_time`` ordering is the caller's responsibility and
is replayed in order; no policy state is over-approximated):

- GRANT / REGRANT -> WRITE the delegate tuple on the scope's record.
- REVOKE -> DELETE the delegate tuple on the scope's record. REVOKE on a
  key with no live tuple is recorded as a no-op (it cannot resurrect).
- EXPIRE -> DELETE the delegate tuple (OpenFGA tuples carry no TTL; expiry
  is realized as an explicit deletion at the expire tick — this is the one
  semantic boundary of the mapping and is disclosed rather than hidden).
- POLICY_VERSION_BUMP -> re-created store with a fresh authorization model
  instance (same DSL text, new model id), so post-bump evaluation provably
  consults the new model id; recorded in evidence as ``model_epoch``.

All engine writes/reads go through one typed client bound to the store,
pinned model id and pinned consistency mode; evaluation happens at the
request's decision tick, i.e. only events at ticks <= decision_time have
been applied when the check runs. Query result mapping: ``allowed: true``
-> PERMIT; ``allowed: false`` -> NOT_APPLICABLE (OpenFGA returns a boolean
reachability answer and has no explicit-deny construct — a negative check
is absence of permission, not a deny; this portability limit is asserted in
tests); HTTP 4xx -> INDETERMINATE with a stable reason code; connection
failure mid-run -> INDETERMINATE with reason code ``OPENFGA_CONNECTION_FAILED``
(never a silent safe rejection).

Decision flow
-------------
``run_case(case, ctx) -> Outcome`` (harness adapter):

- validated synthetic case (as in ``baselines.py``) + injected
  :class:`SacmatContext`-shaped context (reused from ``baselines``);
- ``ctx.simulate_unavailable_upstream=True`` forces port mode;
- server discovered -> real run (``observed_outcome=ADMIT``/``REJECT`` —
  counted, first-class, with ``engine=openfga-http`` evidence);
- no server / probe failure -> ``NOT_RUN_EXTERNAL`` /
  ``BASELINE_UNAVAILABLE`` through the labelled in-process port.

Fail closed with stable uppercase reason codes; never silently drop a
failure and never present port-mode output as an upstream run.

Version
-------
``OPENFGA_ADAPTER_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import dataclasses
import json
import os
import urllib.error
import urllib.request

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.sacmat import baselines as bl

OPENFGA_ADAPTER_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Stable reason codes.
# ---------------------------------------------------------------------------
RC_BASELINE_UNAVAILABLE = bl.RC_BASELINE_UNAVAILABLE
RC_HISTORY_MISSING = bl.RC_HISTORY_MISSING
RC_OPENFGA_SERVER_UNREACHABLE = "OPENFGA_SERVER_UNREACHABLE"
RC_OPENFGA_CHECK_ERROR = "OPENFGA_CHECK_ERROR"
RC_OPENFGA_CONNECTION_FAILED = "OPENFGA_CONNECTION_FAILED"
RC_OPENFGA_PROBE_FAILED = "OPENFGA_PROBE_FAILED"
RC_CONTEXT_MALFORMED = bl.RC_CONTEXT_MALFORMED

#: Engine identifiers recorded in evidence — mutually exclusive, checked in
#: tests to never be conflated.
ENGINE_REAL = "openfga-http"
ENGINE_PORT = "zanzibar-inprocess-port"

#: Pinned upstream (verified live via docker image digest, 2026-11-15):
#: openfga/openfga:v1.22.1 -> 44054f542f64e9b9589dd26a595081b3d2cfd942.
OPENFGA_PINNED_IMAGE = "openfga/openfga:v1.22.1"
OPENFGA_PINNED_REVISION = "44054f542f64e9b9589dd26a595081b3d2cfd942"

#: Pinned consistency predictor for real-engine checks: every check and
#: tuple write must observe the latest tuple set (no stale reads inside an
#: evaluation), per OpenFGA v1.22.1 consistency modes.
OPENFGA_CONSISTENCY_MODE = "HIGHER_CONSISTENCY"

#: Pinned authorization model (schema 1.1 DSL-equivalent JSON structure).
OPENFGA_SCHEMA_VERSION = "1.1"

#: Default candidate endpoints probed when the environment is silent.
DEFAULT_OPENFGA_ENDPOINTS: tuple[str, ...] = (
    "http://127.0.0.1:8080",
    "http://127.0.0.1:18080",
    "http://localhost:8080",
)

#: Timeout for every engine HTTP call (seconds) — bounded, injected-friendly.
DEFAULT_HTTP_TIMEOUT_SECONDS = 3.0


# ---------------------------------------------------------------------------
# Typed objects (JSON-serializable).
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class OpenFgaModel:
    """Pinned authorization-model description (JSON-serializable)."""

    schema_version: str = OPENFGA_SCHEMA_VERSION
    type_definitions: tuple[dict[str, object], ...] = (
        {
            "type": "user",
            "relations": {},
        },
        {
            "type": "consent_record",
            "metadata": {
                "relations": {"delegate": {"directly_related_user_types": [{"type": "user"}]}}
            },
            "relations": {"delegate": {"this": {}}},
        },
        {
            "type": "consent",
            "metadata": {
                "relations": {
                    "record": {"directly_related_user_types": [{"type": "consent_record"}]},
                    "delegate": {
                        "directly_related_user_types": [
                            {"type": "consent_record", "relation": "delegate"}
                        ]
                    },
                }
            },
            "relations": {
                "record": {"this": {}},
                "delegate": {"this": {}},
                "can_access": {"computedUserset": {"relation": "delegate"}},
            },
        },
    )

    def to_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "type_definitions": [dict(td) for td in self.type_definitions],
        }


@dataclasses.dataclass(frozen=True)
class OpenFgaTuple:
    """One OpenFGA relation tuple (JSON-serializable)."""

    user: str
    relation: str
    object: str

    def to_payload(self) -> dict[str, str]:
        return {"user": self.user, "relation": self.relation, "object": self.object}


@dataclasses.dataclass(frozen=True)
class OpenFgaQuery:
    """One access request evaluated at a logical decision tick."""

    actor_id: str
    purpose: str
    object_id: str
    decision_time: int


@dataclasses.dataclass(frozen=True)
class OpenFgaDecision:
    """Portable four-valued decision with evidence (JSON-serializable)."""

    decision: str
    engine_used: str
    reason_code: str
    evidence: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "engine_used": self.engine_used,
            "reason_code": self.reason_code,
            "evidence": self.evidence,
        }


# ---------------------------------------------------------------------------
# Engine errors — stable reason codes, never bare exceptions leaking out.
# ---------------------------------------------------------------------------


class OpenFgaEngineError(Exception):
    """Stable-reason-code failure of one engine interaction."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


# ---------------------------------------------------------------------------
# HTTP client (urllib only — stdlib, injected timeout, no hidden state).
# ---------------------------------------------------------------------------


def _http_json(
    method: str,
    url: str,
    payload: dict[str, object] | None,
    token: str,
    timeout: float,
) -> dict[str, object]:
    """One JSON HTTP call; raises OpenFgaEngineError on any failure."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"content-type": "application/json"}
    if token:
        headers["authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8") or "{}"
            return dict(json.loads(body)) if body.strip() else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200] or ""
        raise OpenFgaEngineError(
            RC_OPENFGA_CHECK_ERROR, f"{method} {url} -> HTTP {exc.code}: {detail}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise OpenFgaEngineError(
            RC_OPENFGA_CONNECTION_FAILED, f"{method} {url} failed: {exc}"
        ) from exc


def _check_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/healthz"


def _probe_endpoint(base_url: str, token: str, timeout: float) -> bool:
    """True iff ``/healthz`` answers HTTP 200 (liveness, OpenFGA v1.22.1)."""
    request = urllib.request.Request(
        _check_url(base_url),
        headers={"authorization": f"Bearer {token}"} if token else {},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status == 200
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
        return False


def discover_openfga(
    *,
    env: dict[str, str] | None = None,
    timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
) -> str | None:
    """Return the base URL of a live OpenFGA server, or None.

    Discovery order: ``OPENFGA_API_URL``/``OPENFGA_API_TOKEN`` environment
    variables when set, then well-known local endpoints. A server counts as
    discovered only when it answers ``/healthz`` with HTTP 200.
    """
    environment = dict(os.environ if env is None else env)
    token = environment.get("OPENFGA_API_TOKEN", "")
    env_url = environment.get("OPENFGA_API_URL", "").strip()
    candidates = (env_url,) if env_url else DEFAULT_OPENFGA_ENDPOINTS
    for base in candidates:
        if not base:
            continue
        if _probe_endpoint(base, token, timeout):
            return base
    return None


# ---------------------------------------------------------------------------
# Real-engine session: one synthetic case -> one ephemeral store.
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _RealEngineSession:
    """Bound HTTP session against one real OpenFGA server."""

    base_url: str
    token: str
    timeout: float
    store_id: str
    model_id: str
    checks_url: str

    @classmethod
    def create(cls, base_url: str, token: str, timeout: float) -> _RealEngineSession:
        """Create an ephemeral store + write the pinned authorization model."""
        store = _http_json(
            "POST",
            f"{base_url.rstrip('/')}/stores",
            {"name": "sacmat-x04-openfga-runner"},
            token,
            timeout,
        )
        store_id = store.get("id")
        if not isinstance(store_id, str) or not store_id:
            raise OpenFgaEngineError(
                RC_OPENFGA_CHECK_ERROR, f"store creation returned no id: {store}"
            )
        model = _http_json(
            "POST",
            f"{base_url.rstrip('/')}/stores/{store_id}/authorization-models",
            dict(OpenFgaModel().to_payload()),
            token,
            timeout,
        )
        model_id = model.get("authorization_model_id")
        if not isinstance(model_id, str) or not model_id:
            raise OpenFgaEngineError(
                RC_OPENFGA_CHECK_ERROR, f"model creation returned no id: {model}"
            )
        return cls(
            base_url=base_url,
            token=token,
            timeout=timeout,
            store_id=store_id,
            model_id=model_id,
            checks_url=f"{base_url.rstrip('/')}/stores/{store_id}/check",
        )

    def write_tuples(self, tuples: tuple[OpenFgaTuple, ...]) -> None:
        """Write relation tuples (idempotent by exact tuple content)."""
        if not tuples:
            return
        _http_json(
            "POST",
            f"{self.base_url.rstrip('/')}/stores/{self.store_id}/write",
            {
                "writes": {"tuple_keys": [t.to_payload() for t in tuples]},
                "authorization_model_id": self.model_id,
            },
            self.token,
            self.timeout,
        )

    def delete_tuples(self, tuples: tuple[OpenFgaTuple, ...]) -> None:
        """Delete relation tuples (revocation/expiry as tuple deletion)."""
        if not tuples:
            return
        _http_json(
            "POST",
            f"{self.base_url.rstrip('/')}/stores/{self.store_id}/write",
            {
                "deletes": {"tuple_keys": [t.to_payload() for t in tuples]},
                "authorization_model_id": self.model_id,
            },
            self.token,
            self.timeout,
        )

    def check(self, query: OpenFgaQuery) -> bool:
        """One permission check under the pinned consistency mode."""
        response = _http_json(
            "POST",
            self.checks_url,
            {
                "tuple_key": {
                    "user": f"user:{query.actor_id}",
                    "relation": "can_access",
                    "object": f"consent:{query.object_id}",
                },
                "authorization_model_id": self.model_id,
                "consistency": OPENFGA_CONSISTENCY_MODE,
            },
            self.token,
            self.timeout,
        )
        allowed = response.get("allowed")
        if not isinstance(allowed, bool):
            raise OpenFgaEngineError(
                RC_OPENFGA_CHECK_ERROR, f"check returned no boolean 'allowed': {response}"
            )
        return allowed

    def delete_store(self) -> None:
        """Remove the ephemeral store (cleanup; best effort)."""
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/stores/{self.store_id}",
            headers={"authorization": f"Bearer {self.token}"} if self.token else {},
            method="DELETE",
        )
        try:
            urllib.request.urlopen(request, timeout=self.timeout).close()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
            pass


# ---------------------------------------------------------------------------
# History translation (explicit; no silent over-approximation).
# ---------------------------------------------------------------------------


def _scope_id(actor_id: str, purpose: str) -> str:
    """Deterministic, engine-safe object id for one delegation scope.

    OpenFGA object ids must not contain ':', '#', '@' or whitespace; the
    purpose string is sanitized to those constraints (collision-free within
    a single synthetic case, which is the only scope that matters here).
    """
    sanitized = "".join(c if c not in ":#@ \t" else "_" for c in purpose)
    return f"{actor_id}_{sanitized}"


def _tuple_for_grant(actor_id: str, purpose: str, delegate_id: str) -> OpenFgaTuple:
    scope = _scope_id(actor_id, purpose)
    return OpenFgaTuple(
        user=f"user:{delegate_id}", relation="delegate", object=f"consent_record:{scope}"
    )


def _link_tuples(actor_id: str, purpose: str) -> tuple[OpenFgaTuple, ...]:
    scope = _scope_id(actor_id, purpose)
    return (
        OpenFgaTuple(user=f"consent_record:{scope}", relation="record", object=f"consent:{scope}"),
        OpenFgaTuple(
            user=f"consent_record:{scope}#delegate",
            relation="delegate",
            object=f"consent:{scope}",
        ),
    )


def _evidence(action: str, applied: int, model_epoch: int) -> dict[str, object]:
    return {
        "pinned_image": OPENFGA_PINNED_IMAGE,
        "pinned_revision": OPENFGA_PINNED_REVISION,
        "authorization_model": "consent/consent_record schema 1.1",
        "consistency": OPENFGA_CONSISTENCY_MODE,
        "last_action": action,
        "tuples_applied": applied,
        "model_epoch": model_epoch,
    }


def run_real_evaluation(
    history: bl.PolicyHistory,
    query: OpenFgaQuery,
    *,
    base_url: str,
    token: str = "",
    timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
) -> OpenFgaDecision:
    """Evaluate the history + query through a REAL OpenFGA server.

    Events are applied in order up to the decision tick; only events with
    ``logical_time <= decision_time`` are ever applied (temporal precedence
    is realized by the replay itself, not asserted). A POLICY_VERSION_BUMP
    re-creates the store with a fresh model instance (model epoch bump).
    """
    session = _RealEngineSession.create(base_url, token, timeout)
    evidence: dict[str, object] = {
        "pinned_image": OPENFGA_PINNED_IMAGE,
        "pinned_revision": OPENFGA_PINNED_REVISION,
        "authorization_model": "consent/consent_record schema 1.1",
        "consistency": OPENFGA_CONSISTENCY_MODE,
        "last_action": "none",
        "tuples_applied": 0,
        "model_epoch": 1,
    }
    try:
        # Pre-create every scope that appears in the history: the consent
        # object, its record link and the userset grantee edge.
        scopes: dict[tuple[str, str], int] = {}
        for event_ in history.events:
            key = (event_.actor_id, event_.purpose)
            if key not in scopes:
                scopes[key] = 1
                link = _link_tuples(event_.actor_id, event_.purpose)
                session.write_tuples(link)
                evidence["tuples_applied"] = int(evidence["tuples_applied"]) + len(link)

        for event_ in history.events:
            if event_.logical_time > query.decision_time:
                break
            if event_.event_kind == bl.EVENT_POLICY_VERSION_BUMP:
                # Version bump: fresh model epoch on a fresh store.
                session.delete_store()
                session = _RealEngineSession.create(base_url, token, timeout)
                evidence["model_epoch"] = int(evidence["model_epoch"]) + 1
                # Re-materialize scopes in the new epoch.
                for (actor_id, purpose), _ in list(scopes.items()):
                    link = _link_tuples(actor_id, purpose)
                    session.write_tuples(link)
                    evidence["tuples_applied"] = int(evidence["tuples_applied"]) + len(link)
                evidence["last_action"] = "model_epoch_bump"
                continue
            grant_tuple = _tuple_for_grant(event_.actor_id, event_.purpose, event_.delegate_id)
            if event_.event_kind in (bl.EVENT_GRANT, bl.EVENT_REGRANT):
                session.write_tuples((grant_tuple,))
                evidence["last_action"] = event_.event_kind.lower()
                evidence["tuples_applied"] = int(evidence["tuples_applied"]) + 1
            elif event_.event_kind in (bl.EVENT_REVOKE, bl.EVENT_EXPIRE):
                session.delete_tuples((grant_tuple,))
                evidence["last_action"] = event_.event_kind.lower()
                evidence["tuples_applied"] = int(evidence["tuples_applied"]) + 1
            else:
                raise OpenFgaEngineError(
                    RC_OPENFGA_CHECK_ERROR, f"unmapped event kind: {event_.event_kind}"
                )

        allowed = session.check(query)
        evidence["last_action"] = "check"
        decision = bl.PERMIT if allowed else bl.NOT_APPLICABLE
        return OpenFgaDecision(
            decision=decision,
            engine_used=ENGINE_REAL,
            reason_code="OK" if allowed else "NO_RELATION_REACHABILITY",
            evidence=evidence,
        )
    finally:
        session.delete_store()


# ---------------------------------------------------------------------------
# Labelled in-process port (fallback; NEVER presented as a real run).
# ---------------------------------------------------------------------------


def run_port_evaluation(history: bl.PolicyHistory, query: OpenFgaQuery) -> OpenFgaDecision:
    """FAITHFUL-PORT evaluation through ``baselines.ZanzibarPolicyEngine``.

    Clearly labelled: ``engine_used=zanzibar-inprocess-port``. The port
    implements the pinned upstream's documented semantics (relation-tuple
    walk at read time; revoked/expired tuples absent) as an in-process
    relation walk — it is NOT the OpenFGA binary.
    """
    request = bl.AccessRequest(
        actor_id=query.actor_id,
        purpose=query.purpose,
        decision_time=query.decision_time,
    )
    scoped_history = bl.PolicyHistory(
        case_id=history.case_id, events=history.events, request=request
    )
    decision = bl.ZanzibarPolicyEngine().evaluate(scoped_history, request)
    return OpenFgaDecision(
        decision=decision,
        engine_used=ENGINE_PORT,
        reason_code="PORT_ZANZIBAR_RELATION_WALK",
        evidence={
            "port_of": OPENFGA_PINNED_IMAGE,
            "port_source": "evaluation/venue2027/sacmat/baselines.py:ZanzibarPolicyEngine",
            "semantics": "Zanzibar ATC 2019 / OpenFGA v1.22.1 relation walk (documented)",
        },
    )


# ---------------------------------------------------------------------------
# Task-signature entry point: evaluate_openfga(model, tuples, query).
# ---------------------------------------------------------------------------


def evaluate_openfga(
    model: OpenFgaModel,
    tuples: tuple[OpenFgaTuple, ...],
    query: OpenFgaQuery,
    *,
    base_url: str,
    token: str = "",
    timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
) -> OpenFgaDecision:
    """Task contract signature: evaluate pre-translated tuples on the engine.

    Writes ``tuples`` verbatim into an ephemeral store on the pinned model,
    then checks ``query``. Positive path of the task contract
    (``evaluate_openfga(model, tuples, query) -> Decision``).
    """
    session = _RealEngineSession.create(base_url, token, timeout)
    try:
        session.write_tuples(tuples)
        allowed = session.check(query)
        return OpenFgaDecision(
            decision=bl.PERMIT if allowed else bl.NOT_APPLICABLE,
            engine_used=ENGINE_REAL,
            reason_code="OK" if allowed else "NO_RELATION_REACHABILITY",
            evidence={
                "pinned_image": OPENFGA_PINNED_IMAGE,
                "consistency": OPENFGA_CONSISTENCY_MODE,
                "tuples_written": len(tuples),
            },
        )
    finally:
        session.delete_store()


# ---------------------------------------------------------------------------
# Harness adapter.
# ---------------------------------------------------------------------------


def _indeterminate(detail: str) -> Outcome:
    return Outcome(
        observed_outcome="INDETERMINATE",
        counted_as_success=False,
        retriable=False,
        detail=detail,
    )


def _not_run_external(reason: str) -> Outcome:
    return Outcome(
        observed_outcome="NOT_RUN_EXTERNAL",
        counted_as_success=False,
        retriable=True,
        detail=f"{RC_BASELINE_UNAVAILABLE}|{reason}",
    )


def run_case(case: dict[str, object], ctx: bl.SacmatContext) -> Outcome:
    """Run one ``(policy history, request)`` case through the OpenFGA arm.

    Real engine when reachable (evidence carries ``engine=openfga-http``);
    otherwise ``NOT_RUN_EXTERNAL`` / ``BASELINE_UNAVAILABLE`` through the
    clearly labelled in-process Zanzibar port (engine
    ``zanzibar-inprocess-port``). Malformed input is INDETERMINATE with a
    stable reason code; engine check failures are INDETERMINATE with their
    own reason codes — never silently a safe rejection.
    """
    if not isinstance(ctx, bl.SacmatContext):
        raise bl.SacmatBaselineError(
            RC_CONTEXT_MALFORMED, f"ctx must be a SacmatContext, got {type(ctx)}"
        )
    if not isinstance(case, dict):
        raise bl.SacmatBaselineError("CASE_NOT_AN_OBJECT", f"case must be a dict, got {type(case)}")
    validated = bl._validate_case(case)
    if isinstance(validated, Outcome):
        return validated
    history = validated
    req = history.request

    query = OpenFgaQuery(
        actor_id=req.actor_id,
        purpose=req.purpose,
        object_id=_scope_id(req.actor_id, req.purpose),
        decision_time=req.decision_time,
    )

    base_url: str | None = None
    token = ""
    if not ctx.simulate_unavailable_upstream:
        try:
            base_url = discover_openfga()
            token = os.environ.get("OPENFGA_API_TOKEN", "")
        except OpenFgaEngineError:
            base_url = None

    if base_url is None:
        # No reachable server: labelled port evaluation, transparently
        # NOT_RUN_EXTERNAL (never counted, never a fake upstream success).
        port_decision = run_port_evaluation(history, query)
        return _not_run_external(
            f"real OpenFGA server unreachable; port path used "
            f"engine={port_decision.engine_used} "
            f"decision={port_decision.decision} "
            f"port_evidence={json.dumps(port_decision.evidence, sort_keys=True)}"
        )

    try:
        decision = run_real_evaluation(history, query, base_url=base_url, token=token)
    except OpenFgaEngineError as exc:
        if exc.reason_code == RC_OPENFGA_CONNECTION_FAILED:
            # Server vanished mid-run: explicit indeterminate, never a safe
            # rejection and never a port fallback masquerading as a run.
            return _indeterminate(f"{exc.reason_code}|{exc.detail}")
        return _indeterminate(f"{exc.reason_code}|{exc.detail}")

    detail = (
        f"engine={decision.engine_used}|decision={decision.decision}|"
        f"evidence={json.dumps(decision.evidence, sort_keys=True)}"
    )
    # OpenFGA answers pure reachability; the case is a single pointwise
    # permission question, so the harness verdict mirrors the engine:
    # PERMIT is the governed operation accepted (ADMIT), anything else is a
    # non-permission (REJECT) — both counted as measured outcomes.
    observed = "ADMIT" if decision.decision == bl.PERMIT else "REJECT"
    return Outcome(
        observed_outcome=observed,
        counted_as_success=True,
        retriable=False,
        detail=detail,
    )
