"""CLARA-Care 2027 COMPSAC task COMPSAC-candidate — dependency-complete optimistic admission.

Purpose
-------
CANDIDATE design (Phase P04, priority; blueprint arm B4 of
``research/venue2027/VENUES/compsac/RESEARCH_BLUEPRINT.md``) for
"Dependency-Complete Optimistic Admission for Concurrent Clinical AI Writes".
This module is a DESIGN OBJECT: it defines the admission algorithm, its typed
inputs/outputs, its fail-closed reason codes, its ablation hooks and its
mutation registry. It contains NO empirical results, NO performance numbers
and NO win rates; the P04 gate forbids main-test claims.

Contribution under study (mechanism axis): scope-local optimistic versioning
that validates the REQUIRED dependency closure of a clinical write operation
— plus consent/policy epochs — in canonical lock order, minimizing
false-stale rejection (COMPSAC-CASE-01) without allowing omitted-dependency
write skew (COMPSAC-CASE-02/05).

Independence boundary (never violated by this module)
-----------------------------------------------------
The REQUIRED dependency closure is derived by an INJECTED closure oracle
(``AdmissionScope.dependency_oracle``), never by rules internal to the
candidate. The candidate validates exactly the closure the oracle returns
(joined with the operation's own declared touch set, which no oracle can omit
on the operation's behalf). If the oracle is missing, refuses, or returns a
malformed closure, admission FAILS CLOSED as ``ERROR`` (never guessed, never
silently treated as a safe rejection). Completeness of the injected closure
itself (COMPSAC-CASE-04, missing dependency edge) is adjudicated by the
independent oracle OUTSIDE this module; the candidate deliberately does not
second-guess the injected oracle.

Allowed input
-------------
- :class:`WriteOperation` — the AI-generated clinical write under admission:
  ``op_id``, ``operation_type``, ``declared_reads``, ``declared_writes``,
  ``write_values`` (JSON-serializable via :meth:`WriteOperation.from_dict`).
- :class:`ClinicalWriteStore` — deterministic in-memory versioned store:
  per-entity ``version``/``value``/``consent_epoch``/``policy_epoch``, a
  governance epoch register (``consent``/``policy``) and a coarse
  ``global_epoch`` counter used only by the global-version ablation.
- :class:`AdmissionScope` — tenant/principal/purpose binding, the
  consent/policy epochs the operation was authorized under, the version
  vector observed at operation start (``snapshot_versions``), the coarse
  snapshot epoch (``snapshot_global_epoch``) and the INJECTED closure oracle.

Algorithmic definition (canonical admission pipeline)
-----------------------------------------------------
``admit(op, store, scope)`` executes, in order, with first-failure-wins:

1. **Shape validation** (fail closed → ``ERROR``): op, store and scope types
   and fields; an operation with an empty touch set is refused
   (``OP_MALFORMED``) because nothing can anchor governance onto it.
2. **Injected closure derivation**: ``closure = scope.dependency_oracle(op)``.
   Missing oracle → ``ERROR/CLOSURE_ORACLE_MISSING``; a raised
   :class:`ClosureOracleRefusal` (or any oracle fault) →
   ``ERROR/CLOSURE_ORACLE_REFUSED``; a non-frozenset of :class:`DependencyEdge`
   → ``ERROR/CLOSURE_ORACLE_MALFORMED``.
3. **Validation scope join**: ``validation_entities = closure entities (non-
   GOVERNANCE) ∪ declared_reads ∪ declared_writes``. The operation's own
   declared touch set is always its own responsibility.
4. **Canonical lock order**: governance anchors first (consent, then policy),
   then GOVERNANCE closure edges sorted by resource, then validation
   entities sorted lexicographically. A single total order over all admitted
   operations is deadlock-free by construction (COMPSAC-CASE-06) and makes
   admission independent of oracle iteration order.
5. **Governance validation**: the scope-bound consent/policy epochs must equal
   the store's live governance register (``CONSENT_EPOCH_STALE`` /
   ``POLICY_EPOCH_STALE``); every GOVERNANCE closure edge must bind the live
   epoch of its named governance resource (``GOVERNANCE_EPOCH_STALE``,
   unknown resource → ``ERROR/UNKNOWN_GOVERNANCE_RESOURCE``). An empty
   domain closure never skips this step (COMPSAC-CASE-08: governance anchors
   are never omitted).
6. **Scope-local version fence** (mode ``scope_local``): for each validation
   entity in canonical order — unknown entity → ``ERROR/UNKNOWN_ENTITY``;
   snapshot version missing → ``ERROR/SNAPSHOT_INCOMPLETE``; a declared write
   target whose current version moved past its snapshot →
   ``WRITE_TARGET_SUPERSEDED``; any other closure/touch entity whose current
   version differs from the snapshot → ``REQUIRED_EDGE_STALE``; then the
   entity's live per-entity consent/policy epoch must equal the scope-bound
   epoch (``CONSENT_EPOCH_STALE`` / ``POLICY_EPOCH_STALE``).
7. **Coarse fence** (mode ``global_version`` only, reached via
   :func:`ablation_global_version`): the single profile-wide
   ``global_epoch`` must equal ``scope.snapshot_global_epoch``, else
   ``GLOBAL_EPOCH_STALE`` (B0-style widest fence: any concurrent write
   anywhere aborts — the false-stale upper bound). Epochs are still enforced.
8. **Install on ADMIT**: every declared write installs ``version + 1`` in
   canonical order (bumping ``global_epoch``). REJECT/ERROR install nothing.

Failure semantics
-----------------
Stable uppercase reason codes; decisions are ``ADMIT`` (reason ``OK``),
``REJECT`` (a determined concurrency-control outcome, counted) or ``ERROR``
(a fail-closed infrastructure/oracle/shape fault, never counted as a safe
rejection, never installing state). Unknown mutation ids in
:func:`admit_with_mutation` fail closed with ``ERROR/UNKNOWN_MUTATION``.

Ablation hooks (real mechanism axes for the P04 ablation study)
---------------------------------------------------------------
- :func:`ablation_no_closure` — replaces the injected oracle with a
  declared-only oracle: omitted cross-resource dependencies leave the fence
  entirely, so the canonical write-skew pair is ADMITTED (RQ2 instrument).
- :func:`ablation_global_version` — replaces the scope-local version fence
  with the single coarse profile epoch: safe but false-stale under unrelated
  concurrent writes (RQ1 comparator B0 semantics).

Mutation registry (mutation-adequacy instrument, P04 gate)
----------------------------------------------------------
:func:`admit_with_mutation` applies a named, documented degradation of the
pipeline (e.g. ``M1-drop-epoch-validation``). Tests must demonstrate each
mutation is CAUGHT as a behavioral differential against the candidate.

Version
-------
``CANDIDATE_ID = "clara.compsac.candidate.dependency-complete-scope-local-occ"``,
``CANDIDATE_VERSION = "1.0.0"``. :func:`describe_mechanism` returns the
machine-readable mechanism description. All output types are
JSON-serializable via ``to_dict``.
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Final

CANDIDATE_ID: Final[str] = "clara.compsac.candidate.dependency-complete-scope-local-occ"
CANDIDATE_VERSION: Final[str] = "1.0.0"

MODE_SCOPE_LOCAL: Final[str] = "scope_local"
MODE_GLOBAL_VERSION: Final[str] = "global_version"
KNOWN_MODES: Final[frozenset[str]] = frozenset({MODE_SCOPE_LOCAL, MODE_GLOBAL_VERSION})

DECISION_ADMIT: Final[str] = "ADMIT"
DECISION_REJECT: Final[str] = "REJECT"
DECISION_ERROR: Final[str] = "ERROR"
DETERMINED_DECISIONS: Final[frozenset[str]] = frozenset({DECISION_ADMIT, DECISION_REJECT})

REASON_OK: Final[str] = "OK"
REASON_OP_MALFORMED: Final[str] = "OP_MALFORMED"
REASON_STORE_MALFORMED: Final[str] = "STORE_MALFORMED"
REASON_SCOPE_MALFORMED: Final[str] = "SCOPE_MALFORMED"
REASON_CLOSURE_ORACLE_MISSING: Final[str] = "CLOSURE_ORACLE_MISSING"
REASON_CLOSURE_ORACLE_REFUSED: Final[str] = "CLOSURE_ORACLE_REFUSED"
REASON_CLOSURE_ORACLE_MALFORMED: Final[str] = "CLOSURE_ORACLE_MALFORMED"
REASON_UNKNOWN_ENTITY: Final[str] = "UNKNOWN_ENTITY"
REASON_UNKNOWN_GOVERNANCE_RESOURCE: Final[str] = "UNKNOWN_GOVERNANCE_RESOURCE"
REASON_SNAPSHOT_INCOMPLETE: Final[str] = "SNAPSHOT_INCOMPLETE"
REASON_CONSENT_EPOCH_STALE: Final[str] = "CONSENT_EPOCH_STALE"
REASON_POLICY_EPOCH_STALE: Final[str] = "POLICY_EPOCH_STALE"
REASON_GOVERNANCE_EPOCH_STALE: Final[str] = "GOVERNANCE_EPOCH_STALE"
REASON_REQUIRED_EDGE_STALE: Final[str] = "REQUIRED_EDGE_STALE"
REASON_WRITE_TARGET_SUPERSEDED: Final[str] = "WRITE_TARGET_SUPERSEDED"
REASON_GLOBAL_EPOCH_STALE: Final[str] = "GLOBAL_EPOCH_STALE"
REASON_UNKNOWN_MUTATION: Final[str] = "UNKNOWN_MUTATION"

GOVERNANCE_CONSENT: Final[str] = "consent"
GOVERNANCE_POLICY: Final[str] = "policy"

M1_DROP_EPOCH_VALIDATION: Final[str] = "M1-drop-epoch-validation"
M2_DECLARED_READS_ONLY: Final[str] = "M2-declared-reads-only"
M3_IGNORE_SUPERSEDED_WRITES: Final[str] = "M3-ignore-superseded-writes"


class EdgeKind(enum.StrEnum):
    """Kind of a required dependency edge (blueprint resource classes)."""

    ENTITY = "ENTITY"
    GOVERNANCE = "GOVERNANCE"
    EVIDENCE = "EVIDENCE"
    LEASE = "LEASE"


@dataclasses.dataclass(frozen=True)
class DependencyEdge:
    """One required dependency edge produced by the INJECTED closure oracle."""

    kind: EdgeKind
    resource: str
    required_version_or_epoch: str | int
    predicate: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "resource": self.resource,
            "required_version_or_epoch": self.required_version_or_epoch,
            "predicate": self.predicate,
        }


@dataclasses.dataclass(frozen=True)
class WriteOperation:
    """The AI-generated clinical write operation under admission."""

    op_id: str
    operation_type: str
    declared_reads: tuple[str, ...]
    declared_writes: tuple[str, ...]
    write_values: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op_id": self.op_id,
            "operation_type": self.operation_type,
            "declared_reads": list(self.declared_reads),
            "declared_writes": list(self.declared_writes),
            "write_values": dict(self.write_values),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> WriteOperation:
        return cls(
            op_id=payload["op_id"],
            operation_type=payload["operation_type"],
            declared_reads=tuple(payload["declared_reads"]),
            declared_writes=tuple(payload["declared_writes"]),
            write_values=dict(payload.get("write_values") or {}),
        )


class ClosureOracleRefusal(Exception):
    """Raised by an injected closure oracle to fail closed (escalate, not guess)."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(f"{reason_code}: {detail}" if detail else reason_code)
        self.reason_code = reason_code
        self.detail = detail


DependencyOracle = Callable[[WriteOperation], frozenset[DependencyEdge]]


class ClinicalWriteStore:
    """Deterministic in-memory versioned clinical write store (passive register).

    Entities carry an integer ``version``, a ``value`` and optional per-entity
    ``consent_epoch``/``policy_epoch`` bindings. A governance register holds
    the live consent/policy epochs. A coarse ``global_epoch`` counter moves on
    every install; it exists ONLY for the global-version ablation. All
    concurrency decisions belong to the admission pipeline, never to the store.
    """

    def __init__(
        self,
        entities: Mapping[str, Mapping[str, Any]] | None = None,
        governance_epochs: Mapping[str, str] | None = None,
        global_epoch: int = 1,
    ) -> None:
        self._entities: dict[str, dict[str, Any]] = {}
        for entity, record in (entities or {}).items():
            self._entities[str(entity)] = {
                "version": int(record["version"]),
                "value": record.get("value"),
                "consent_epoch": record.get("consent_epoch"),
                "policy_epoch": record.get("policy_epoch"),
            }
        gov = dict(governance_epochs or {})
        self._governance: dict[str, str] = {
            GOVERNANCE_CONSENT: str(gov.get(GOVERNANCE_CONSENT, "c1")),
            GOVERNANCE_POLICY: str(gov.get(GOVERNANCE_POLICY, "p1")),
        }
        self._global_epoch = int(global_epoch)

    def version_of(self, entity: str) -> int | None:
        record = self._entities.get(entity)
        return None if record is None else int(record["version"])

    def entity_epoch(self, entity: str, kind: str) -> str | None:
        record = self._entities.get(entity)
        if record is None:
            return None
        value = record.get(kind)
        return None if value is None else str(value)

    def governance_epoch(self, kind: str) -> str | None:
        value = self._governance.get(kind)
        return None if value is None else str(value)

    @property
    def global_epoch(self) -> int:
        return self._global_epoch

    def install(self, entity: str, value: Any) -> int:
        record = self._entities.setdefault(
            entity, {"version": 0, "value": None, "consent_epoch": None, "policy_epoch": None}
        )
        record["version"] = int(record["version"]) + 1
        record["value"] = value
        self._global_epoch += 1
        return int(record["version"])

    def set_entity_epoch(self, entity: str, kind: str, epoch: str) -> None:
        self._entities.setdefault(
            entity, {"version": 0, "value": None, "consent_epoch": None, "policy_epoch": None}
        )[kind] = epoch

    def set_governance_epoch(self, kind: str, epoch: str) -> None:
        if kind not in (GOVERNANCE_CONSENT, GOVERNANCE_POLICY):
            raise ValueError(f"unknown governance kind: {kind!r}")
        self._governance[kind] = str(epoch)

    def current_version_map(self) -> dict[str, int]:
        return {entity: int(record["version"]) for entity, record in self._entities.items()}

    def snapshot(self) -> dict[str, Any]:
        """Version vector + epochs observed by an operation starting now."""
        return {
            "versions": dict(sorted(self.current_version_map().items())),
            "global_epoch": self._global_epoch,
            "consent_epoch": self.governance_epoch(GOVERNANCE_CONSENT),
            "policy_epoch": self.governance_epoch(GOVERNANCE_POLICY),
        }


@dataclasses.dataclass(frozen=True)
class AdmissionScope:
    """Scope binding + snapshot + INJECTED closure oracle for one admission."""

    tenant_id: str
    principal_id: str
    purpose: str
    consent_epoch: str
    policy_epoch: str
    dependency_oracle: DependencyOracle | None
    snapshot_versions: Mapping[str, int]
    snapshot_global_epoch: int
    mode: str = MODE_SCOPE_LOCAL

    def with_oracle(self, oracle: DependencyOracle | None) -> AdmissionScope:
        return dataclasses.replace(self, dependency_oracle=oracle)

    def with_mode(self, mode: str) -> AdmissionScope:
        return dataclasses.replace(self, mode=mode)


@dataclasses.dataclass(frozen=True)
class AdmissionOutcome:
    """Determined admission decision (JSON-serializable via ``to_dict``)."""

    decision: str
    reason_code: str
    op_id: str
    mode: str
    counted_as_success: bool
    fail_closed: bool
    validation_order: tuple[str, ...]
    closure_size: int
    injected_oracle_used: bool
    detail: str
    outcome_digest: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason_code": self.reason_code,
            "op_id": self.op_id,
            "mode": self.mode,
            "counted_as_success": self.counted_as_success,
            "fail_closed": self.fail_closed,
            "validation_order": list(self.validation_order),
            "closure_size": self.closure_size,
            "injected_oracle_used": self.injected_oracle_used,
            "detail": self.detail,
            "outcome_digest": self.outcome_digest,
        }


@dataclasses.dataclass(frozen=True)
class MutationSpec:
    """One documented pipeline degradation applied by ``admit_with_mutation``."""

    mutation_id: str
    description: str
    mechanism_axis: str


MUTATION_REGISTRY: Final[Mapping[str, MutationSpec]] = {
    M1_DROP_EPOCH_VALIDATION: MutationSpec(
        mutation_id=M1_DROP_EPOCH_VALIDATION,
        description=(
            "Removes every consent/policy epoch check (governance register, GOVERNANCE "
            "closure edges and per-entity epoch bindings); a consent-revoked concurrent "
            "write becomes admissible"
        ),
        mechanism_axis="governance-epoch-validation",
    ),
    M2_DECLARED_READS_ONLY: MutationSpec(
        mutation_id=M2_DECLARED_READS_ONLY,
        description=(
            "Drops the injected dependency closure from the validation scope (declared "
            "touch set only); an omitted-dependency write skew becomes admissible"
        ),
        mechanism_axis="dependency-closure",
    ),
    M3_IGNORE_SUPERSEDED_WRITES: MutationSpec(
        mutation_id=M3_IGNORE_SUPERSEDED_WRITES,
        description=(
            "Skips the write-target supersede check; a declared write landing on an "
            "entity concurrently moved past the snapshot becomes admissible"
        ),
        mechanism_axis="write-target-fence",
    ),
}


def _canonical_digest(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _outcome(
    *,
    decision: str,
    reason_code: str,
    op: WriteOperation | None,
    scope: AdmissionScope | None,
    closure_size: int,
    validation_order: Sequence[str],
    injected_oracle_used: bool,
    extra: Mapping[str, Any] | None = None,
) -> AdmissionOutcome:
    determined = decision in DETERMINED_DECISIONS
    op_id = getattr(op, "op_id", "?") if op is not None else "?"
    mode = getattr(scope, "mode", "?") if scope is not None else "?"
    detail: dict[str, Any] = {
        "candidate_id": CANDIDATE_ID,
        "candidate_version": CANDIDATE_VERSION,
        "op_id": op_id,
        "operation_type": getattr(op, "operation_type", None) if op is not None else None,
        "decision": decision,
        "reason_code": reason_code,
        "mode": mode,
        "closure_size": closure_size,
        "validation_order": list(validation_order),
        "injected_oracle_used": injected_oracle_used,
        "fail_closed": not determined,
    }
    if extra:
        detail.update(extra)
    detail_json = json.dumps(detail, sort_keys=True, separators=(",", ":"))
    digest_payload = {
        "decision": decision,
        "reason_code": reason_code,
        "op_id": op_id,
        "mode": mode,
        "closure_size": closure_size,
        "validation_order": list(validation_order),
    }
    return AdmissionOutcome(
        decision=decision,
        reason_code=reason_code,
        op_id=op_id,
        mode=mode,
        counted_as_success=determined,
        fail_closed=not determined,
        validation_order=tuple(validation_order),
        closure_size=closure_size,
        injected_oracle_used=injected_oracle_used,
        detail=detail_json,
        outcome_digest=_canonical_digest(digest_payload),
    )


def _validate_shape(
    op: WriteOperation, store: ClinicalWriteStore, scope: AdmissionScope
) -> str | None:
    if not isinstance(op, WriteOperation):
        return REASON_OP_MALFORMED
    if not isinstance(op.op_id, str) or not op.op_id:
        return REASON_OP_MALFORMED
    if not isinstance(op.operation_type, str) or not op.operation_type:
        return REASON_OP_MALFORMED
    for name in (*op.declared_reads, *op.declared_writes):
        if not isinstance(name, str) or not name:
            return REASON_OP_MALFORMED
    if not op.declared_reads and not op.declared_writes:
        return REASON_OP_MALFORMED
    if not isinstance(op.write_values, Mapping):
        return REASON_OP_MALFORMED
    if not isinstance(store, ClinicalWriteStore):
        return REASON_STORE_MALFORMED
    if not isinstance(scope, AdmissionScope):
        return REASON_SCOPE_MALFORMED
    for field_name in ("tenant_id", "principal_id", "purpose", "consent_epoch", "policy_epoch"):
        value = getattr(scope, field_name)
        if not isinstance(value, str) or not value:
            return REASON_SCOPE_MALFORMED
    if scope.mode not in KNOWN_MODES:
        return REASON_SCOPE_MALFORMED
    if not isinstance(scope.snapshot_versions, Mapping):
        return REASON_SCOPE_MALFORMED
    for entity, version in scope.snapshot_versions.items():
        if not isinstance(entity, str) or not entity:
            return REASON_SCOPE_MALFORMED
        if isinstance(version, bool) or not isinstance(version, int):
            return REASON_SCOPE_MALFORMED
    if isinstance(scope.snapshot_global_epoch, bool) or not isinstance(
        scope.snapshot_global_epoch, int
    ):
        return REASON_SCOPE_MALFORMED
    return None


def _declared_only_oracle(op: WriteOperation) -> frozenset[DependencyEdge]:
    """Ablation oracle: closure = the operation's own declared touch set only."""
    edges: set[DependencyEdge] = set()
    for resource in op.declared_reads:
        edges.add(DependencyEdge(EdgeKind.ENTITY, resource, "snapshot", "depends_on_current"))
    for resource in op.declared_writes:
        edges.add(DependencyEdge(EdgeKind.ENTITY, resource, "snapshot", "depends_on_current"))
    return frozenset(edges)


def ablation_no_closure(scope: AdmissionScope) -> AdmissionScope:
    """P04 ablation hook: drop the dependency closure from the fence.

    Replaces the injected closure oracle with a declared-only oracle, so the
    required cross-resource dependencies the workload never declares leave the
    validation scope entirely. On the canonical omitted-dependency schedule
    this ADMITS the write-skew pair that the candidate REJECTs — proving the
    closure (not the version fence) is the mechanism. Governance epochs are
    NOT weakened by this ablation.
    """
    return scope.with_oracle(_declared_only_oracle)


def ablation_global_version(scope: AdmissionScope) -> AdmissionScope:
    """P04 ablation hook: replace the scope-local fence with one coarse epoch.

    Mode ``global_version`` validates a single profile-wide ``global_epoch``
    (blueprint arm B0 semantics): any concurrent committed write anywhere
    aborts the operation — safe, but the false-stale upper bound that
    scope-local versioning exists to remove (RQ1 comparator).
    """
    return scope.with_mode(MODE_GLOBAL_VERSION)


def admit(op: WriteOperation, store: ClinicalWriteStore, scope: AdmissionScope) -> AdmissionOutcome:
    """Dependency-complete optimistic admission of ``op`` against ``store``.

    Implements the canonical pipeline documented in the module docstring:
    injected closure derivation, governance + scope-local version validation
    in canonical lock order, install-on-admit. Fail closed on every
    infrastructure fault (``ERROR``), determined ``ADMIT``/``REJECT`` otherwise.
    """
    return _admit_pipeline(op, store, scope, mutations=frozenset())


def admit_with_mutation(
    op: WriteOperation, store: ClinicalWriteStore, scope: AdmissionScope, mutation_id: str
) -> AdmissionOutcome:
    """Run the admission pipeline with one registered mutation applied.

    Mutation-adequacy instrument: each registry entry is a documented
    degradation; tests must catch every mutation as a behavioral differential
    against :func:`admit`. Unknown ids fail closed (``ERROR/UNKNOWN_MUTATION``).
    """
    if mutation_id not in MUTATION_REGISTRY:
        return _outcome(
            decision=DECISION_ERROR,
            reason_code=REASON_UNKNOWN_MUTATION,
            op=op,
            scope=scope,
            closure_size=0,
            validation_order=(),
            injected_oracle_used=False,
            extra={"mutation_id": str(mutation_id)},
        )
    return _admit_pipeline(op, store, scope, mutations=frozenset({mutation_id}))


def _admit_pipeline(
    op: WriteOperation,
    store: ClinicalWriteStore,
    scope: AdmissionScope,
    mutations: frozenset[str],
) -> AdmissionOutcome:
    shape_error = _validate_shape(op, store, scope)
    if shape_error is not None:
        return _outcome(
            decision=DECISION_ERROR,
            reason_code=shape_error,
            op=op,
            scope=scope,
            closure_size=0,
            validation_order=(),
            injected_oracle_used=False,
        )

    oracle = scope.dependency_oracle
    if oracle is None or not callable(oracle):
        return _outcome(
            decision=DECISION_ERROR,
            reason_code=REASON_CLOSURE_ORACLE_MISSING,
            op=op,
            scope=scope,
            closure_size=0,
            validation_order=(),
            injected_oracle_used=False,
        )
    try:
        closure = oracle(op)
    except ClosureOracleRefusal as exc:
        return _outcome(
            decision=DECISION_ERROR,
            reason_code=REASON_CLOSURE_ORACLE_REFUSED,
            op=op,
            scope=scope,
            closure_size=0,
            validation_order=(),
            injected_oracle_used=True,
            extra={"oracle_refusal_reason": exc.reason_code, "oracle_refusal_detail": exc.detail},
        )
    except Exception as exc:  # noqa: BLE001 — oracle faults must fail closed, never guessed
        return _outcome(
            decision=DECISION_ERROR,
            reason_code=REASON_CLOSURE_ORACLE_REFUSED,
            op=op,
            scope=scope,
            closure_size=0,
            validation_order=(),
            injected_oracle_used=True,
            extra={"oracle_fault": type(exc).__name__},
        )
    if not isinstance(closure, frozenset) or not all(
        isinstance(edge, DependencyEdge) for edge in closure
    ):
        return _outcome(
            decision=DECISION_ERROR,
            reason_code=REASON_CLOSURE_ORACLE_MALFORMED,
            op=op,
            scope=scope,
            closure_size=0,
            validation_order=(),
            injected_oracle_used=True,
        )
    if M2_DECLARED_READS_ONLY in mutations:
        closure = frozenset()

    governance_edges = sorted(
        (edge for edge in closure if edge.kind is EdgeKind.GOVERNANCE),
        key=lambda edge: edge.resource,
    )
    closure_entities = {edge.resource for edge in closure if edge.kind is not EdgeKind.GOVERNANCE}
    validation_entities = sorted(
        closure_entities | set(op.declared_reads) | set(op.declared_writes)
    )
    canonical_order = [GOVERNANCE_CONSENT, GOVERNANCE_POLICY]
    canonical_order += [f"edge:{edge.resource}" for edge in governance_edges]
    canonical_order += validation_entities

    drop_epochs = M1_DROP_EPOCH_VALIDATION in mutations
    ignore_superseded = M3_IGNORE_SUPERSEDED_WRITES in mutations

    def reject_or_error(
        decision: str, reason_code: str, extra: Mapping[str, Any]
    ) -> AdmissionOutcome:
        return _outcome(
            decision=decision,
            reason_code=reason_code,
            op=op,
            scope=scope,
            closure_size=len(closure),
            validation_order=canonical_order,
            injected_oracle_used=True,
            extra=extra,
        )

    if not drop_epochs:
        if scope.consent_epoch != store.governance_epoch(GOVERNANCE_CONSENT):
            return reject_or_error(
                DECISION_REJECT,
                REASON_CONSENT_EPOCH_STALE,
                {"stage": "governance-register", "resource": GOVERNANCE_CONSENT},
            )
        if scope.policy_epoch != store.governance_epoch(GOVERNANCE_POLICY):
            return reject_or_error(
                DECISION_REJECT,
                REASON_POLICY_EPOCH_STALE,
                {"stage": "governance-register", "resource": GOVERNANCE_POLICY},
            )
    for edge in governance_edges:
        if drop_epochs:
            break
        live = store.governance_epoch(edge.resource)
        if live is None:
            return reject_or_error(
                DECISION_ERROR,
                REASON_UNKNOWN_GOVERNANCE_RESOURCE,
                {"stage": "governance-edge", "resource": edge.resource},
            )
        if str(edge.required_version_or_epoch) != live:
            reason = (
                REASON_CONSENT_EPOCH_STALE
                if edge.resource == GOVERNANCE_CONSENT
                else REASON_POLICY_EPOCH_STALE
                if edge.resource == GOVERNANCE_POLICY
                else REASON_GOVERNANCE_EPOCH_STALE
            )
            return reject_or_error(
                DECISION_REJECT,
                reason,
                {"stage": "governance-edge", "resource": edge.resource},
            )

    if scope.mode == MODE_GLOBAL_VERSION:
        if store.global_epoch != scope.snapshot_global_epoch:
            return reject_or_error(
                DECISION_REJECT,
                REASON_GLOBAL_EPOCH_STALE,
                {
                    "stage": "global-epoch-fence",
                    "observed_global_epoch": scope.snapshot_global_epoch,
                    "current_global_epoch": store.global_epoch,
                },
            )
    for entity in validation_entities:
        current_version = store.version_of(entity)
        if current_version is None:
            return reject_or_error(
                DECISION_ERROR,
                REASON_UNKNOWN_ENTITY,
                {"stage": "entity", "resource": entity},
            )
        if scope.mode == MODE_SCOPE_LOCAL:
            if entity not in scope.snapshot_versions:
                return reject_or_error(
                    DECISION_ERROR,
                    REASON_SNAPSHOT_INCOMPLETE,
                    {"stage": "entity", "resource": entity},
                )
            observed = int(scope.snapshot_versions[entity])
            if current_version != observed:
                is_write_target = entity in op.declared_writes
                if is_write_target and not ignore_superseded:
                    return reject_or_error(
                        DECISION_REJECT,
                        REASON_WRITE_TARGET_SUPERSEDED,
                        {
                            "stage": "entity",
                            "resource": entity,
                            "observed": observed,
                            "current": current_version,
                        },
                    )
                if not is_write_target:
                    return reject_or_error(
                        DECISION_REJECT,
                        REASON_REQUIRED_EDGE_STALE,
                        {
                            "stage": "entity",
                            "resource": entity,
                            "observed": observed,
                            "current": current_version,
                        },
                    )
        if drop_epochs:
            continue
        live_consent = store.entity_epoch(entity, "consent_epoch")
        if live_consent is not None and scope.consent_epoch != live_consent:
            return reject_or_error(
                DECISION_REJECT,
                REASON_CONSENT_EPOCH_STALE,
                {"stage": "entity-epoch", "resource": entity},
            )
        live_policy = store.entity_epoch(entity, "policy_epoch")
        if live_policy is not None and scope.policy_epoch != live_policy:
            return reject_or_error(
                DECISION_REJECT,
                REASON_POLICY_EPOCH_STALE,
                {"stage": "entity-epoch", "resource": entity},
            )

    for entity in sorted(op.declared_writes):
        store.install(entity, op.write_values.get(entity))
    return _outcome(
        decision=DECISION_ADMIT,
        reason_code=REASON_OK,
        op=op,
        scope=scope,
        closure_size=len(closure),
        validation_order=canonical_order,
        injected_oracle_used=True,
        extra={
            "installed": {entity: store.version_of(entity) for entity in sorted(op.declared_writes)}
        },
    )


def describe_mechanism() -> dict[str, Any]:
    """Machine-readable mechanism description (design record, no results)."""
    return {
        "candidate_id": CANDIDATE_ID,
        "candidate_version": CANDIDATE_VERSION,
        "name": "Dependency-complete scope-local optimistic admission",
        "blueprint_arm": "B4",
        "blueprint": "research/venue2027/VENUES/compsac/RESEARCH_BLUEPRINT.md",
        "phase": "P04 (candidate design; no empirical results)",
        "algorithmic_definition": [
            "shape-validate op/store/scope (fail closed ERROR)",
            "derive REQUIRED dependency closure via the INJECTED oracle (fail closed on missing/refusal/malformed)",
            "join validation scope: closure entities + declared reads + declared writes",
            "validate governance register and GOVERNANCE closure edges (epochs; never omitted even for empty closures)",
            "scope-local mode: per-entity snapshot version fence + per-entity consent/policy epochs, canonical sorted order",
            "global_version mode (ablation): single profile-wide global_epoch fence",
            "install declared writes version+1 on ADMIT in canonical order",
        ],
        "mechanism_axes": {
            "dependency_closure": "injected per-operation required cross-resource edges",
            "scope_local_versioning": "per-entity snapshot fences instead of one profile epoch",
            "governance_epochs": "consent/policy register + per-entity bindings validated under the fence",
            "canonical_lock_order": "governance anchors first, then sorted entities (deadlock-free, order-independent)",
        },
        "ablation_hooks": {
            "ablation_no_closure": "drops the injected closure -> omitted-dependency write skew becomes admissible (RQ2)",
            "ablation_global_version": "coarse profile epoch fence -> safe but false-stale upper bound (RQ1, B0 semantics)",
        },
        "mutation_registry": {
            mutation_id: spec.description for mutation_id, spec in MUTATION_REGISTRY.items()
        },
        "fail_closed_reason_codes": [
            REASON_OP_MALFORMED,
            REASON_STORE_MALFORMED,
            REASON_SCOPE_MALFORMED,
            REASON_CLOSURE_ORACLE_MISSING,
            REASON_CLOSURE_ORACLE_REFUSED,
            REASON_CLOSURE_ORACLE_MALFORMED,
            REASON_UNKNOWN_ENTITY,
            REASON_UNKNOWN_GOVERNANCE_RESOURCE,
            REASON_SNAPSHOT_INCOMPLETE,
            REASON_UNKNOWN_MUTATION,
        ],
        "determined_reason_codes": [
            REASON_OK,
            REASON_REQUIRED_EDGE_STALE,
            REASON_WRITE_TARGET_SUPERSEDED,
            REASON_CONSENT_EPOCH_STALE,
            REASON_POLICY_EPOCH_STALE,
            REASON_GOVERNANCE_EPOCH_STALE,
            REASON_GLOBAL_EPOCH_STALE,
        ],
        "documented_limitation": (
            "Negative-predicate phantom inserts (COMPSAC-CASE-05) are outside the "
            "in-process version fence; they are adjudicated by the PostgreSQL "
            "SERIALIZABLE baseline comparison in the P05 phase, not by this design."
        ),
    }
