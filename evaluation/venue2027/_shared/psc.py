"""CLARA-Care 2027 shared task SH-psc_interface — Policy-Scoped Commit interface.

Purpose
-------
Program-level typed "Policy-Scoped Commit" (PSC) advisory-witness interface,
reused by all nine venue2027 candidate arms. A machine-generated health-state
write is authorized only if its claimed scope, the live governance epochs and
the required dependency closure are all demonstrably valid. This module is the
shared *advisory* witness layer (``CONTEXT/PSC_METHOD_CARD.md`` sections C-D):
``Govern`` + ``Fresh`` checks against injected governance state, producing
``COMMIT | REJECT | INDETERMINATE`` decisions. It never writes state, never
imports a candidate implementation, and its ``COMMIT`` outcome is an advisory
candidate only — the atomic transaction must repeat every predicate
(``PSC_METHOD_CARD.md``: "A certificate computed outside the transaction is
only an advisory candidate") and is deliberately out of scope here, as is the
venue-specific historical dispatch-bytes witness (Shadow A).

Allowed input
-------------
A :class:`PscRequest` (or its JSON-serializable ``psc_request.v1`` dict form)
plus two injected, deterministic dependencies: a :class:`DependencyOracle`
resolving required dependency keys to observed ``(version, digest)`` pairs and
a :class:`GovernanceEpochSource` returning the live consent epoch and policy
version for a ``(tenant, principal)`` pair. No network, no database, no
hidden clock or randomness: identical inputs always yield an identical
:class:`PscDecision`.

Failure semantics
-----------------
Fail closed with stable uppercase reason codes; :func:`evaluate_psc` is total
(it returns a decision instead of raising for request-content problems):

- structural scope/request problems => ``REJECT`` (``SCOPE_*`` / ``REQUEST_*``);
- dispatch binding diverging from the claimed scope => ``REJECT``
  ``SCOPE_CONFUSION`` (same-tenant cross-purpose reuse, method-card table H);
- consent epoch drift / revocation => ``REJECT EPOCH_CONSENT_STALE``;
- claimed policy version older than live => ``REJECT EPOCH_POLICY_DOWNGRADE``;
- claimed policy version with no orderable relation to live => ``REJECT
  EPOCH_POLICY_DIVERGENT`` (fail closed on unknown policy relation);
- required dependency unknown to the oracle => ``INDETERMINATE
  DEPENDENCY_UNRESOLVED`` — a first-class outcome that is never counted as a
  safe rejection or a completion (``GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md``
  rule 4);
- required dependency resolved but changed since dispatch => ``REJECT
  DEPENDENCY_STALE``;
- oracle/epoch-source malfunction => ``INDETERMINATE`` (``*_ERROR`` /
  ``*_MALFORMED``), never a fabricated rejection;
- empty required closure => ``REJECT DEPENDENCY_CLOSURE_EMPTY`` (an arm cannot
  bypass the oracle by declaring nothing).

Only wiring errors (a non-callable injected dependency) raise, with stable
codes, because they are programmer errors rather than case outcomes. Foreign
exception text is never embedded in details (PII hygiene): only the exception
class name is recorded.

Version
-------
``PSC_INTERFACE_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

PSC_INTERFACE_VERSION = "1.0.0"

OUTCOME_COMMIT = "COMMIT"
OUTCOME_REJECT = "REJECT"
OUTCOME_INDETERMINATE = "INDETERMINATE"

#: First-class decision outcomes; ``INDETERMINATE`` is never collapsed into a
#: rejection and neither non-COMMIT outcome is ever counted as a completion.
PSC_OUTCOMES: frozenset[str] = frozenset({OUTCOME_COMMIT, OUTCOME_REJECT, OUTCOME_INDETERMINATE})

REASON_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
DEP_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+-]{0,127}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

ENFORCEMENT_ADVISORY = "ADVISORY_WITNESS"

STATUS_RESOLVED = "RESOLVED"
STATUS_UNRESOLVED = "UNRESOLVED"
DEPENDENCY_STATUSES: frozenset[str] = frozenset({STATUS_RESOLVED, STATUS_UNRESOLVED})

_SCOPE_FIELDS: tuple[str, ...] = (
    "tenant",
    "principal",
    "purpose",
    "consent_epoch",
    "policy_version",
)
_REQUEST_REQUIRED_FIELDS: tuple[str, ...] = (
    "request_id",
    "scope",
    "dispatch_scope",
    "operation_kind",
    "required_dependencies",
)
_DECISION_FIELDS: tuple[str, ...] = (
    "request_id",
    "outcome",
    "reason_code",
    "detail",
    "scope",
    "verified_dependency_keys",
    "enforcement",
    "contract_version",
    "request_sha256",
)

_FALLBACK_TENANT = "unknown"


def _fallback_scope() -> PolicyScope:
    """Structurally valid scope for decisions on malformed requests (fail closed)."""
    return PolicyScope(
        tenant=_FALLBACK_TENANT,
        principal=_FALLBACK_TENANT,
        purpose=_FALLBACK_TENANT,
        consent_epoch=_FALLBACK_TENANT,
        policy_version="0.0.0",
    )


class PscContractError(ValueError):
    """Fail-closed contract violation carrying a stable machine-checkable reason code."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


class PscScopeError(PscContractError):
    """The claimed or dispatch-bound policy scope is structurally invalid."""


class PscRequestError(PscContractError):
    """The PSC request record is structurally invalid."""


class PscDecisionError(PscContractError):
    """A PSC decision record is structurally invalid."""


class DependencyOracleError(PscContractError):
    """The injected dependency oracle misbehaved or is misconfigured."""


class GovernanceEpochError(PscContractError):
    """The injected governance epoch source failed or returned invalid epochs."""


def _require_identifier(value: Any, code: str, field: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER_RE.match(value):
        raise PscContractError(code, f"{field} must match {IDENTIFIER_RE.pattern!r}")
    return value


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _policy_relation(claimed: str, current: str) -> str:
    """Classify claimed-vs-live policy version: CURRENT | DOWNGRADE | DIVERGENT."""
    if claimed == current:
        return "CURRENT"
    claimed_tuple = tuple(int(part) for part in claimed.split("."))
    current_tuple = tuple(int(part) for part in current.split("."))
    if claimed_tuple < current_tuple:
        return "DOWNGRADE"
    return "DIVERGENT"


@dataclasses.dataclass(frozen=True)
class PolicyScope:
    """Typed governance scope of one PSC request (fail closed on construction).

    ``consent_epoch`` is the opaque consent-state token the proposal was
    computed under and ``policy_version`` the semantic version of the policy
    document it was evaluated against; both are re-checked against live
    governance by :func:`evaluate_psc`.
    """

    tenant: str
    principal: str
    purpose: str
    consent_epoch: str
    policy_version: str

    def __post_init__(self) -> None:
        for field in ("tenant", "principal", "purpose", "consent_epoch"):
            _require_identifier(getattr(self, field), "SCOPE_MALFORMED", f"scope.{field}")
        if not isinstance(self.policy_version, str) or not SEMVER_RE.match(self.policy_version):
            raise PscScopeError(
                "SCOPE_MALFORMED",
                f"scope.policy_version {self.policy_version!r} must match {SEMVER_RE.pattern!r}",
            )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PolicyScope:
        """Build a validated scope from a dict; fail closed on missing/unknown keys."""
        if not isinstance(data, Mapping):
            raise PscScopeError(
                "SCOPE_NOT_AN_OBJECT", f"expected an object, got {type(data).__name__}"
            )
        unknown = sorted(set(data) - set(_SCOPE_FIELDS))
        if unknown:
            raise PscScopeError("SCOPE_UNKNOWN_FIELD", f"unexpected scope keys: {unknown}")
        missing = [field for field in _SCOPE_FIELDS if field not in data]
        if missing:
            raise PscScopeError("SCOPE_MISSING_FIELD", f"missing scope fields: {missing}")
        return cls(
            tenant=data["tenant"],
            principal=data["principal"],
            purpose=data["purpose"],
            consent_epoch=data["consent_epoch"],
            policy_version=data["policy_version"],
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "tenant": self.tenant,
            "principal": self.principal,
            "purpose": self.purpose,
            "consent_epoch": self.consent_epoch,
            "policy_version": self.policy_version,
        }


@dataclasses.dataclass(frozen=True)
class DependencyRef:
    """One required dependency of the proposal's dispatch-time closure."""

    key: str
    version: str
    digest: str

    def __post_init__(self) -> None:
        _require_identifier(self.key, "DEPENDENCY_BAD_REF", "dependency.key")
        if not isinstance(self.version, str) or not DEP_VERSION_RE.match(self.version):
            raise PscContractError(
                "DEPENDENCY_BAD_REF",
                f"dependency.version {self.version!r} must match {DEP_VERSION_RE.pattern!r}",
            )
        if not isinstance(self.digest, str) or not SHA256_RE.match(self.digest):
            raise PscContractError(
                "DEPENDENCY_BAD_REF",
                f"dependency.digest {self.digest!r} must be 64 lowercase hex chars",
            )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DependencyRef:
        if not isinstance(data, Mapping):
            raise PscContractError(
                "DEPENDENCY_BAD_REF", f"expected an object, got {type(data).__name__}"
            )
        required = {"key", "version", "digest"}
        unknown = sorted(set(data) - required)
        if unknown:
            raise PscContractError("DEPENDENCY_BAD_REF", f"unexpected dependency keys: {unknown}")
        missing = sorted(required - set(data))
        if missing:
            raise PscContractError("DEPENDENCY_BAD_REF", f"missing dependency fields: {missing}")
        return cls(key=data["key"], version=data["version"], digest=data["digest"])

    def to_dict(self) -> dict[str, str]:
        return {"key": self.key, "version": self.version, "digest": self.digest}


@dataclasses.dataclass(frozen=True)
class PscRequest:
    """Typed advisory-witness request (``psc_request.v1``, JSON-serializable).

    ``scope`` is the scope claimed at commit time; ``dispatch_scope`` is the
    scope bound when the proposal was actually computed. The two must be
    exactly equal — any divergence is scope confusion and rejects.
    """

    request_id: str
    scope: PolicyScope
    dispatch_scope: PolicyScope
    operation_kind: str
    required_dependencies: tuple[DependencyRef, ...]

    def __post_init__(self) -> None:
        _require_identifier(self.request_id, "REQUEST_MALFORMED", "request_id")
        if not isinstance(self.scope, PolicyScope) or not isinstance(
            self.dispatch_scope, PolicyScope
        ):
            raise PscRequestError(
                "REQUEST_MALFORMED", "scope and dispatch_scope must be PolicyScope instances"
            )
        _require_identifier(self.operation_kind, "REQUEST_MALFORMED", "operation_kind")
        if isinstance(self.required_dependencies, list):
            object.__setattr__(self, "required_dependencies", tuple(self.required_dependencies))
        if not isinstance(self.required_dependencies, tuple):
            raise PscRequestError(
                "REQUEST_MALFORMED", "required_dependencies must be a sequence of DependencyRef"
            )
        if not self.required_dependencies:
            raise PscRequestError(
                "DEPENDENCY_CLOSURE_EMPTY",
                "required_dependencies is empty; an arm cannot bypass the dependency oracle",
            )
        for ref in self.required_dependencies:
            if not isinstance(ref, DependencyRef):
                raise PscRequestError(
                    "REQUEST_MALFORMED", "required_dependencies entries must be DependencyRef"
                )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PscRequest:
        """Build a validated request from a ``psc_request.v1`` dict; fail closed."""
        if not isinstance(data, Mapping):
            raise PscRequestError(
                "REQUEST_NOT_AN_OBJECT", f"expected an object, got {type(data).__name__}"
            )
        unknown = sorted(set(data) - set(_REQUEST_REQUIRED_FIELDS))
        if unknown:
            raise PscRequestError("REQUEST_UNKNOWN_FIELD", f"unexpected request keys: {unknown}")
        missing = [field for field in _REQUEST_REQUIRED_FIELDS if field not in data]
        if missing:
            raise PscRequestError("REQUEST_MISSING_FIELD", f"missing request fields: {missing}")
        raw_deps = data["required_dependencies"]
        if not isinstance(raw_deps, Sequence) or isinstance(raw_deps, str | bytes):
            raise PscRequestError("REQUEST_MALFORMED", "required_dependencies must be an array")
        claimed = data["scope"]
        bound = data["dispatch_scope"]
        return cls(
            request_id=data["request_id"],
            scope=claimed if isinstance(claimed, PolicyScope) else PolicyScope.from_dict(claimed),
            dispatch_scope=(
                bound if isinstance(bound, PolicyScope) else PolicyScope.from_dict(bound)
            ),
            operation_kind=data["operation_kind"],
            required_dependencies=tuple(
                item if isinstance(item, DependencyRef) else DependencyRef.from_dict(item)
                for item in raw_deps
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "scope": self.scope.to_dict(),
            "dispatch_scope": self.dispatch_scope.to_dict(),
            "operation_kind": self.operation_kind,
            "required_dependencies": [ref.to_dict() for ref in self.required_dependencies],
        }

    @property
    def canonical_sha256(self) -> str:
        """Stable content digest of the canonical request (audit/observability)."""
        return hashlib.sha256(_canonical_json(self.to_dict()).encode("utf-8")).hexdigest()


@dataclasses.dataclass(frozen=True)
class DependencyResolution:
    """Observed state of one dependency key, as resolved by the injected oracle."""

    key: str
    status: str
    version: str | None = None
    digest: str | None = None
    reason_code: str = "OK"

    def __post_init__(self) -> None:
        _require_identifier(self.key, "DEPENDENCY_BAD_RESOLUTION", "resolution.key")
        if self.status not in DEPENDENCY_STATUSES:
            raise DependencyOracleError(
                "DEPENDENCY_BAD_RESOLUTION",
                f"status {self.status!r} not in {sorted(DEPENDENCY_STATUSES)}",
            )
        if self.status == STATUS_RESOLVED:
            if not isinstance(self.version, str) or not DEP_VERSION_RE.match(self.version):
                raise DependencyOracleError(
                    "DEPENDENCY_BAD_RESOLUTION",
                    f"RESOLVED requires a version matching {DEP_VERSION_RE.pattern!r}",
                )
            if not isinstance(self.digest, str) or not SHA256_RE.match(self.digest):
                raise DependencyOracleError(
                    "DEPENDENCY_BAD_RESOLUTION", "RESOLVED requires a 64-hex digest"
                )
            if self.reason_code != "OK":
                raise DependencyOracleError(
                    "DEPENDENCY_BAD_RESOLUTION", "RESOLVED must carry reason_code OK"
                )
        else:
            if self.version is not None or self.digest is not None:
                raise DependencyOracleError(
                    "DEPENDENCY_BAD_RESOLUTION", "UNRESOLVED must not carry version/digest"
                )
            if not REASON_CODE_RE.match(self.reason_code) or self.reason_code == "OK":
                raise DependencyOracleError(
                    "DEPENDENCY_BAD_RESOLUTION",
                    f"UNRESOLVED requires a stable non-OK reason code, got {self.reason_code!r}",
                )

    @classmethod
    def unresolved(cls, key: str, reason_code: str = "UNKNOWN_KEY") -> DependencyResolution:
        return cls(key=key, status=STATUS_UNRESOLVED, reason_code=reason_code)

    def to_dict(self) -> dict[str, str | None]:
        return {
            "key": self.key,
            "status": self.status,
            "version": self.version,
            "digest": self.digest,
            "reason_code": self.reason_code,
        }


@dataclasses.dataclass(frozen=True)
class GovernanceEpochs:
    """Live governance snapshot returned by a :class:`GovernanceEpochSource`."""

    consent_epoch: str
    policy_version: str

    def __post_init__(self) -> None:
        _require_identifier(self.consent_epoch, "EPOCH_SOURCE_MALFORMED", "consent_epoch")
        if not isinstance(self.policy_version, str) or not SEMVER_RE.match(self.policy_version):
            raise GovernanceEpochError(
                "EPOCH_SOURCE_MALFORMED",
                f"policy_version {self.policy_version!r} must match {SEMVER_RE.pattern!r}",
            )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> GovernanceEpochs:
        if not isinstance(data, Mapping):
            raise GovernanceEpochError(
                "EPOCH_SOURCE_MALFORMED", f"expected an object, got {type(data).__name__}"
            )
        required = {"consent_epoch", "policy_version"}
        unknown = sorted(set(data) - required)
        if unknown:
            raise GovernanceEpochError(
                "EPOCH_SOURCE_MALFORMED", f"unexpected epoch keys: {unknown}"
            )
        missing = sorted(required - set(data))
        if missing:
            raise GovernanceEpochError("EPOCH_SOURCE_MALFORMED", f"missing epoch fields: {missing}")
        return cls(consent_epoch=data["consent_epoch"], policy_version=data["policy_version"])

    def to_dict(self) -> dict[str, str]:
        return {"consent_epoch": self.consent_epoch, "policy_version": self.policy_version}


@runtime_checkable
class DependencyOracle(Protocol):
    """Injected truth source for the required dependency closure.

    Implementations must be deterministic and pure (no hidden clock, network
    or randomness) and must never import candidate code; they resolve the
    *observed* current ``(version, digest)`` for a key. Comparison against the
    request's dispatch-time expectation lives in :func:`evaluate_psc`.
    """

    @property
    def oracle_id(self) -> str: ...  # pragma: no cover - protocol declaration

    def resolve(self, key: str) -> DependencyResolution: ...


@runtime_checkable
class GovernanceEpochSource(Protocol):
    """Injected truth source for live consent/policy epochs."""

    @property
    def source_id(self) -> str: ...  # pragma: no cover - protocol declaration

    def current_epochs(self, tenant: str, principal: str) -> GovernanceEpochs: ...


@dataclasses.dataclass(frozen=True)
class FrozenDependencyOracle:
    """Deterministic table-driven reference oracle (no I/O, no clock).

    The table is copied at construction so later external mutation cannot
    change resolutions; keys absent from the table resolve ``UNRESOLVED``
    (``UNKNOWN_KEY``) and are never silently treated as satisfied.
    """

    oracle_id: str
    table: Mapping[str, tuple[str, str]]

    def __post_init__(self) -> None:
        if not isinstance(self.oracle_id, str) or not self.oracle_id:
            raise DependencyOracleError("DEPENDENCY_ORACLE_ERROR", "oracle_id must be non-empty")
        object.__setattr__(self, "table", dict(self.table))
        for key, observed in self.table.items():
            if not isinstance(observed, tuple) or len(observed) != 2:
                raise DependencyOracleError(
                    "DEPENDENCY_BAD_RESOLUTION", f"table[{key!r}] must be (version, digest)"
                )
            DependencyRef(key=key, version=observed[0], digest=observed[1])

    def resolve(self, key: str) -> DependencyResolution:
        observed = self.table.get(key)
        if observed is None:
            return DependencyResolution.unresolved(key)
        return DependencyResolution(
            key=key, status=STATUS_RESOLVED, version=observed[0], digest=observed[1]
        )


@dataclasses.dataclass(frozen=True)
class FrozenEpochSource:
    """Deterministic table-driven reference epoch source (no I/O, no clock)."""

    source_id: str
    epochs_by_principal: Mapping[tuple[str, str], GovernanceEpochs]

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id:
            raise GovernanceEpochError("EPOCH_SOURCE_ERROR", "source_id must be non-empty")
        object.__setattr__(self, "epochs_by_principal", dict(self.epochs_by_principal))
        for key, epochs in self.epochs_by_principal.items():
            if not isinstance(epochs, GovernanceEpochs):
                raise GovernanceEpochError(
                    "EPOCH_SOURCE_MALFORMED",
                    f"epochs_by_principal[{key!r}] must be a GovernanceEpochs",
                )

    def current_epochs(self, tenant: str, principal: str) -> GovernanceEpochs:
        epochs = self.epochs_by_principal.get((tenant, principal))
        if epochs is None:
            raise GovernanceEpochError(
                "EPOCH_SOURCE_UNKNOWN_PRINCIPAL",
                "no live governance epochs for the requested (tenant, principal) pair",
            )
        return epochs


@dataclasses.dataclass(frozen=True)
class PscDecision:
    """Typed advisory witness decision (``psc_decision.v1``, JSON-serializable).

    ``COMMIT`` is an advisory candidate only: the atomic transaction must
    repeat every predicate under actual backend isolation before any write.
    ``INDETERMINATE`` is a first-class outcome and is never counted as a safe
    rejection or a completion; it may still record the dependency keys that
    were verified before the unknown was hit (audit provenance, never tally).
    """

    request_id: str
    outcome: str
    reason_code: str
    scope: PolicyScope
    request_sha256: str
    verified_dependency_keys: tuple[str, ...] = ()
    enforcement: str = ENFORCEMENT_ADVISORY
    contract_version: str = PSC_INTERFACE_VERSION
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not IDENTIFIER_RE.match(self.request_id):
            raise PscDecisionError(
                "DECISION_MALFORMED", f"request_id {self.request_id!r} violates the v1 pattern"
            )
        if self.outcome not in PSC_OUTCOMES:
            raise PscDecisionError(
                "DECISION_MALFORMED", f"outcome {self.outcome!r} not in {sorted(PSC_OUTCOMES)}"
            )
        if not REASON_CODE_RE.match(self.reason_code):
            raise PscDecisionError(
                "DECISION_MALFORMED",
                f"reason_code {self.reason_code!r} violates the stable-code pattern",
            )
        if not isinstance(self.scope, PolicyScope):
            raise PscDecisionError("DECISION_MALFORMED", "scope must be a PolicyScope")
        if not isinstance(self.request_sha256, str) or not SHA256_RE.match(self.request_sha256):
            raise PscDecisionError(
                "DECISION_MALFORMED", "request_sha256 must be 64 lowercase hex chars"
            )
        if isinstance(self.verified_dependency_keys, list):
            object.__setattr__(
                self, "verified_dependency_keys", tuple(self.verified_dependency_keys)
            )
        if not isinstance(self.verified_dependency_keys, tuple) or not all(
            isinstance(key, str) and IDENTIFIER_RE.match(key)
            for key in self.verified_dependency_keys
        ):
            raise PscDecisionError(
                "DECISION_MALFORMED", "verified_dependency_keys must be identifier strings"
            )
        if self.enforcement != ENFORCEMENT_ADVISORY:
            raise PscDecisionError(
                "DECISION_MALFORMED",
                f"enforcement {self.enforcement!r} != {ENFORCEMENT_ADVISORY!r}: a witness outside "
                "the transaction is advisory by construction",
            )
        if self.outcome == OUTCOME_COMMIT and (
            not self.verified_dependency_keys
            or len(set(self.verified_dependency_keys)) != len(self.verified_dependency_keys)
        ):
            raise PscDecisionError(
                "DECISION_MALFORMED", "COMMIT requires the deduplicated keys it verified"
            )
        if self.outcome != OUTCOME_COMMIT and len(set(self.verified_dependency_keys)) != len(
            self.verified_dependency_keys
        ):
            raise PscDecisionError(
                "DECISION_MALFORMED",
                f"{self.outcome} verified_dependency_keys must be deduplicated",
            )

    @property
    def is_commit(self) -> bool:
        return self.outcome == OUTCOME_COMMIT

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PscDecision:
        if not isinstance(data, Mapping):
            raise PscDecisionError(
                "DECISION_NOT_AN_OBJECT", f"expected an object, got {type(data).__name__}"
            )
        unknown = sorted(set(data) - set(_DECISION_FIELDS))
        if unknown:
            raise PscDecisionError("DECISION_UNKNOWN_FIELD", f"unexpected decision keys: {unknown}")
        missing = [field for field in _DECISION_FIELDS if field not in data]
        if missing:
            raise PscDecisionError("DECISION_MISSING_FIELD", f"missing decision fields: {missing}")
        raw_keys = data["verified_dependency_keys"]
        if not isinstance(raw_keys, list):
            raise PscDecisionError(
                "DECISION_MALFORMED", "verified_dependency_keys must be an array"
            )
        raw_scope = data["scope"]
        return cls(
            request_id=data["request_id"],
            outcome=data["outcome"],
            reason_code=data["reason_code"],
            scope=(
                raw_scope
                if isinstance(raw_scope, PolicyScope)
                else PolicyScope.from_dict(raw_scope)
            ),
            request_sha256=data["request_sha256"],
            verified_dependency_keys=tuple(raw_keys),
            enforcement=data["enforcement"],
            contract_version=data["contract_version"],
            detail=data["detail"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "outcome": self.outcome,
            "reason_code": self.reason_code,
            "detail": self.detail,
            "scope": self.scope.to_dict(),
            "verified_dependency_keys": list(self.verified_dependency_keys),
            "enforcement": self.enforcement,
            "contract_version": self.contract_version,
            "request_sha256": self.request_sha256,
        }


def _best_effort_request_id(request: Any) -> str:
    if isinstance(request, PscRequest):
        return request.request_id
    if isinstance(request, Mapping):
        candidate = request.get("request_id")
        if isinstance(candidate, str) and IDENTIFIER_RE.match(candidate):
            return candidate
    return "unknown"


def _input_sha256(request: Any) -> str:
    if isinstance(request, PscRequest):
        return request.canonical_sha256
    if isinstance(request, Mapping):
        try:
            normalized = json.loads(json.dumps(request, sort_keys=True, default=str))
        except (TypeError, ValueError):
            normalized = {"unserializable_mapping": type(request).__name__}
        return hashlib.sha256(_canonical_json(normalized).encode("utf-8")).hexdigest()
    return hashlib.sha256(
        _canonical_json({"uncoercible_type": type(request).__name__}).encode("utf-8")
    ).hexdigest()


def _coerce_request(request: Any) -> PscRequest:
    if isinstance(request, PscRequest):
        return request
    return PscRequest.from_dict(request)


def _require_wiring(dependency_oracle: Any, epoch_source: Any) -> None:
    resolve = getattr(dependency_oracle, "resolve", None)
    if not callable(resolve):
        raise PscContractError(
            "DEPENDENCY_ORACLE_NOT_CALLABLE",
            "dependency_oracle must expose resolve(key) -> DependencyResolution",
        )
    oracle_id = getattr(dependency_oracle, "oracle_id", None)
    if not isinstance(oracle_id, str) or not oracle_id:
        raise PscContractError("DEPENDENCY_ORACLE_NOT_CALLABLE", "oracle_id must be non-empty")
    current = getattr(epoch_source, "current_epochs", None)
    if not callable(current):
        raise PscContractError(
            "EPOCH_SOURCE_NOT_CALLABLE",
            "epoch_source must expose current_epochs(tenant, principal) -> GovernanceEpochs",
        )
    source_id = getattr(epoch_source, "source_id", None)
    if not isinstance(source_id, str) or not source_id:
        raise PscContractError("EPOCH_SOURCE_NOT_CALLABLE", "source_id must be non-empty")


def _decision(
    request: Any,
    outcome: str,
    reason_code: str,
    detail: str,
    scope: PolicyScope | None,
    verified: Sequence[str],
) -> PscDecision:
    return PscDecision(
        request_id=_best_effort_request_id(request),
        outcome=outcome,
        reason_code=reason_code,
        scope=scope if scope is not None else _fallback_scope(),
        request_sha256=_input_sha256(request),
        verified_dependency_keys=tuple(verified),
        detail=detail,
    )


def evaluate_psc(
    request: PscRequest | Mapping[str, Any],
    *,
    dependency_oracle: DependencyOracle,
    epoch_source: GovernanceEpochSource,
) -> PscDecision:
    """Evaluate one advisory PSC witness decision; total and deterministic.

    Order of predicates (first stable outcome wins): structural scope/request
    validation, dispatch-vs-claimed scope binding, live governance epoch
    freshness, then per-key dependency closure verification through the
    injected oracle. Any non-``COMMIT`` outcome is fail-closed; every
    verification is repeated inside the real atomic transaction by the
    caller's commit kernel.
    """
    _require_wiring(dependency_oracle, epoch_source)
    try:
        req = _coerce_request(request)
    except PscContractError as exc:
        return _decision(request, OUTCOME_REJECT, exc.reason_code, exc.detail, None, ())
    verified: list[str] = []
    if req.dispatch_scope != req.scope:
        diverging = [
            field
            for field in _SCOPE_FIELDS
            if getattr(req.dispatch_scope, field) != getattr(req.scope, field)
        ]
        return _decision(
            req,
            OUTCOME_REJECT,
            "SCOPE_CONFUSION",
            f"dispatch binding diverges from claimed scope in field(s): {diverging}",
            req.scope,
            verified,
        )
    try:
        epochs = epoch_source.current_epochs(req.scope.tenant, req.scope.principal)
    except PscContractError as exc:
        return _decision(
            req, OUTCOME_INDETERMINATE, exc.reason_code, exc.detail, req.scope, verified
        )
    except Exception as exc:
        return _decision(
            req,
            OUTCOME_INDETERMINATE,
            "EPOCH_SOURCE_ERROR",
            f"epoch source raised: {type(exc).__name__}",
            req.scope,
            verified,
        )
    if not isinstance(epochs, GovernanceEpochs):
        return _decision(
            req,
            OUTCOME_INDETERMINATE,
            "EPOCH_SOURCE_MALFORMED",
            f"epoch source returned {type(epochs).__name__}, not GovernanceEpochs",
            req.scope,
            verified,
        )
    if epochs.consent_epoch != req.scope.consent_epoch:
        return _decision(
            req,
            OUTCOME_REJECT,
            "EPOCH_CONSENT_STALE",
            "consent epoch drifted between the claimed scope and live governance",
            req.scope,
            verified,
        )
    relation = _policy_relation(req.scope.policy_version, epochs.policy_version)
    if relation == "DOWNGRADE":
        return _decision(
            req,
            OUTCOME_REJECT,
            "EPOCH_POLICY_DOWNGRADE",
            "claimed policy_version is older than the live policy version",
            req.scope,
            verified,
        )
    if relation == "DIVERGENT":
        return _decision(
            req,
            OUTCOME_REJECT,
            "EPOCH_POLICY_DIVERGENT",
            "claimed policy_version has no orderable relation to the live policy version",
            req.scope,
            verified,
        )
    for ref in req.required_dependencies:
        try:
            resolution = dependency_oracle.resolve(ref.key)
        except PscContractError as exc:
            return _decision(
                req,
                OUTCOME_INDETERMINATE,
                "DEPENDENCY_ORACLE_ERROR",
                f"oracle failed for {ref.key}: {exc.reason_code}",
                req.scope,
                verified,
            )
        except Exception as exc:
            return _decision(
                req,
                OUTCOME_INDETERMINATE,
                "DEPENDENCY_ORACLE_ERROR",
                f"oracle raised for {ref.key}: {type(exc).__name__}",
                req.scope,
                verified,
            )
        if not isinstance(resolution, DependencyResolution) or resolution.key != ref.key:
            return _decision(
                req,
                OUTCOME_INDETERMINATE,
                "DEPENDENCY_ORACLE_MALFORMED",
                f"oracle returned a malformed/mismatched resolution for {ref.key}",
                req.scope,
                verified,
            )
        if resolution.status == STATUS_UNRESOLVED:
            return _decision(
                req,
                OUTCOME_INDETERMINATE,
                "DEPENDENCY_UNRESOLVED",
                f"required dependency {ref.key} is unresolved "
                f"(oracle reason: {resolution.reason_code}); unknown dependencies fail "
                "closed as INDETERMINATE, never as safe rejections",
                req.scope,
                verified,
            )
        if (resolution.version, resolution.digest) != (ref.version, ref.digest):
            return _decision(
                req,
                OUTCOME_REJECT,
                "DEPENDENCY_STALE",
                f"required dependency {ref.key} changed since dispatch "
                f"(claimed {ref.version}/{ref.digest[:12]}..., "
                f"observed {resolution.version}/{(resolution.digest or '')[:12]}...)",
                req.scope,
                verified,
            )
        verified.append(ref.key)
    return _decision(
        req,
        OUTCOME_COMMIT,
        "ADVISORY_COMMIT_ELIGIBLE",
        "all advisory predicates passed; re-verify every predicate inside the "
        "atomic transaction before writing",
        req.scope,
        verified,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: ``evaluate <psc_request.v1.json>`` — prints the decision, exit 0/2."""
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="CLARA 2027 PSC advisory witness CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)
    evaluate = sub.add_parser("evaluate", help="evaluate a psc_request.v1 JSON document")
    evaluate.add_argument("request_path")
    evaluate.add_argument("--oracle-id", default="cli_frozen_oracle")
    evaluate.add_argument("--epoch-source-id", default="cli_frozen_epochs")
    args = parser.parse_args(argv)
    if args.cmd != "evaluate":  # pragma: no cover - argparse constrains cmd
        return 2
    raw = json.loads(Path(args.request_path).read_text(encoding="utf-8"))
    governance = raw.get("live_governance", {})
    observed = raw.pop("observed_dependencies", [])
    raw.pop("live_governance", None)
    pure_epochs = {k: v for k, v in governance.items() if k in ("consent_epoch", "policy_version")}
    try:
        decision = evaluate_psc(
            raw,
            dependency_oracle=FrozenDependencyOracle(
                oracle_id=args.oracle_id,
                table={
                    item["key"]: (item["version"], item["digest"])
                    for item in observed
                    if isinstance(item, Mapping) and {"key", "version", "digest"} <= set(item)
                },
            ),
            epoch_source=FrozenEpochSource(
                source_id=args.epoch_source_id,
                epochs_by_principal={
                    (
                        governance.get("tenant", "unknown"),
                        governance.get("principal", "unknown"),
                    ): GovernanceEpochs.from_dict(pure_epochs),
                },
            ),
        )
    except PscContractError as exc:
        print(json.dumps({"ok": False, "reason_code": exc.reason_code, "detail": exc.detail}))
        return 1
    print(json.dumps(decision.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
