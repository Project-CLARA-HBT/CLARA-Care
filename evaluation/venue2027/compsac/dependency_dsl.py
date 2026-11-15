"""COMPSAC-X01_readset_dsl — typed transaction dependency language.

Purpose
-------
Machine-checkable *dependency-closure oracle* input language for
"Dependency-Complete Optimistic Admission for Concurrent Clinical AI Writes"
(research/venue2027/VENUES/compsac/RESEARCH_BLUEPRINT.md, RQ1). A clinical
write operation declares its mutation targets, its read resources and the
cross-resource edges it relies on; :func:`compile_dependencies` derives the
*required* dependency closure — every declared write/read MUST appear as a
compiled :class:`Dependency` of the correct kind. There is no implicit
wildcard omission: a resource the operation touches but the schema cannot
describe is a compile failure (fail closed), never a silently dropped edge.

Allowed input
-------------
- :class:`Operation` with ``op_id``, ``writes``, ``reads`` and ``declared_edges``
  (JSON-serializable via :meth:`Operation.to_dict`); operations must be
  constructed with ``from_dict``/constructor for deterministic hashing.
- :class:`Schema` pinned to ``SCHEMA_VERSION``; a schema whose version differs
  is refused outright (``SCHEMA_VERSION_MISMATCH``).
- Schema resource table: GOVERNANCE anchors (consent/policy), ENTITY rows,
  EVIDENCE sources, LEASE holds. Predicates are schema-registered; an
  unregistered predicate fails closed (``UNKNOWN_PREDICATE``).

Failure semantics (stable reason codes on ``DependencyCompileError``)
----------------------------------------------------------------------
- ``UNKNOWN_MUTATION_TARGET`` — a declared write/read resource is absent from
  the schema resource table (or referenced by an edge without being declared
  on the operation).
- ``UNKNOWN_PREDICATE`` — an edge predicate is not schema-registered.
- ``SCHEMA_VERSION_MISMATCH`` — schema version differs from the DSL version.
- ``EMPTY_OPERATION`` — an operation with no writes and no reads cannot carry
  governance anchoring and is refused (blueprint COMPSAC-CASE-08: governance
  still applies; the empty-closure case belongs to the runtime, not the DSL).
- ``MALFORMED_OPERATION`` / ``MALFORMED_SCHEMA`` — non-string identifiers,
  empty resource ids, or self-edges.

Version
-------
``DEPENDENCY_DSL_VERSION = "clara.compsac.dependency-dsl-v1"``. Output is
JSON-serializable: :meth:`Dependency.to_dict`, :meth:`ClosureReport.to_dict`.
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from types import MappingProxyType
from typing import Any, Final

DEPENDENCY_DSL_VERSION: Final[str] = "clara.compsac.dependency-dsl-v1"

REASON_UNKNOWN_MUTATION_TARGET: Final[str] = "UNKNOWN_MUTATION_TARGET"
REASON_UNKNOWN_PREDICATE: Final[str] = "UNKNOWN_PREDICATE"
REASON_SCHEMA_VERSION_MISMATCH: Final[str] = "SCHEMA_VERSION_MISMATCH"
REASON_EMPTY_OPERATION: Final[str] = "EMPTY_OPERATION"
REASON_MALFORMED_OPERATION: Final[str] = "MALFORMED_OPERATION"
REASON_MALFORMED_SCHEMA: Final[str] = "MALFORMED_SCHEMA"


class DependencyKind(enum.StrEnum):
    """Resource kinds a clinical write can depend on.

    GOVERNANCE — consent/policy epochs (blueprint: governance anchors are never
    omitted, COMPSAC-CASE-08). ENTITY — clinical rows (medication, allergy,
    history). EVIDENCE — source documents/digests backing a claim. LEASE —
    bounded-time holds serializing concurrent writers.
    """

    GOVERNANCE = "GOVERNANCE"
    ENTITY = "ENTITY"
    EVIDENCE = "EVIDENCE"
    LEASE = "LEASE"


@dataclasses.dataclass(frozen=True)
class Dependency:
    """One required cross-resource dependency edge."""

    kind: DependencyKind
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
class Operation:
    """A clinical write operation with its declared touch set.

    ``declared_edges`` are (read_resource, predicate) pairs the operation
    author *claims* are semantically required; the compiler must still prove
    coverage of every write/read via schema-derived dependencies (no trust in
    the declaration alone).
    """

    op_id: str
    writes: tuple[str, ...]
    reads: tuple[str, ...]
    declared_edges: tuple[tuple[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "op_id": self.op_id,
            "writes": list(self.writes),
            "reads": list(self.reads),
            "declared_edges": [[r, p] for r, p in self.declared_edges],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Operation:
        try:
            return cls(
                op_id=payload["op_id"],
                writes=tuple(payload["writes"]),
                reads=tuple(payload["reads"]),
                declared_edges=tuple((r, p) for r, p in payload["declared_edges"]),
            )
        except (KeyError, TypeError) as exc:
            raise DependencyCompileError(
                REASON_MALFORMED_OPERATION, f"operation payload malformed: {exc}"
            ) from exc


@dataclasses.dataclass(frozen=True)
class Schema:
    """Frozen per-operation dependency schema (version-pinned)."""

    version: str
    resources: Mapping[str, DependencyKind]
    predicates: frozenset[str]
    default_versions: Mapping[str, str | int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "resources": {k: v.value for k, v in sorted(self.resources.items())},
            "predicates": sorted(self.predicates),
            "default_versions": dict(sorted(self.default_versions.items())),
        }


def make_schema(
    *,
    version: str = DEPENDENCY_DSL_VERSION,
    resources: Mapping[str, DependencyKind] | None = None,
    predicates: Iterable[str] = ("depends_on_current", "governed_by", "backed_by", "held_under"),
    default_versions: Mapping[str, str | int] | None = None,
) -> Schema:
    """Build a schema, failing closed on malformed resource tables."""
    res = dict(resources or {})
    preds = frozenset(predicates)
    defaults = dict(default_versions or {})
    for name, kind in res.items():
        if not isinstance(name, str) or not name or not isinstance(kind, DependencyKind):
            raise DependencyCompileError(REASON_MALFORMED_SCHEMA, f"bad resource entry: {name!r}")
    for name in preds:
        if not isinstance(name, str) or not name:
            raise DependencyCompileError(REASON_MALFORMED_SCHEMA, f"bad predicate entry: {name!r}")
    for name in defaults:
        if name not in res:
            raise DependencyCompileError(
                REASON_MALFORMED_SCHEMA,
                f"default version for unregistered resource: {name!r}",
            )
    return Schema(
        version=version,
        resources=types_mapping(res),
        predicates=preds,
        default_versions=types_mapping(defaults),
    )


def types_mapping(mapping: dict[str, Any]) -> Mapping[str, Any]:
    """Return an immutable mapping view (JSON-serializable round-trip safe)."""
    return MappingProxyType(mapping)


class DependencyCompileError(Exception):
    """Fail-closed compile rejection carrying a stable reason code."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(f"{reason_code}: {detail}" if detail else reason_code)
        self.reason_code = reason_code
        self.detail = detail


def compile_dependencies(op: Operation, schema: Schema) -> frozenset[Dependency]:
    """Derive the REQUIRED dependency closure for ``op`` under ``schema``.

    The closure contains exactly one dependency per distinct touched resource
    (writes ∪ reads): the kind comes from the schema resource table, the
    version/epoch from the schema-pinned default, and the predicate from the
    operation's declared edge when one exists (kind-default otherwise). Any
    unknown resource or predicate fails closed — nothing is omitted.
    """
    _refuse_version_mismatch(schema)
    _validate_shape(op)
    touched = _validate_resources(op, schema)
    edge_predicates: dict[str, str] = {}
    for read_resource, predicate in op.declared_edges:
        if predicate not in schema.predicates:
            raise DependencyCompileError(
                REASON_UNKNOWN_PREDICATE, f"predicate {predicate!r} not schema-registered"
            )
        edge_predicates[read_resource] = predicate
    closure: set[Dependency] = set()
    for resource in sorted(touched):
        kind = schema.resources[resource]
        closure.add(
            Dependency(
                kind=kind,
                resource=resource,
                required_version_or_epoch=schema.default_versions.get(
                    resource, _governance_epoch_floor(kind)
                ),
                predicate=edge_predicates.get(resource, _predicate_for(kind)),
            )
        )
    return frozenset(closure)


def _governance_epoch_floor(kind: DependencyKind) -> str | int:
    return 0 if kind is DependencyKind.GOVERNANCE else "current"


def _predicate_for(kind: DependencyKind) -> str:
    return {
        DependencyKind.GOVERNANCE: "governed_by",
        DependencyKind.ENTITY: "depends_on_current",
        DependencyKind.EVIDENCE: "backed_by",
        DependencyKind.LEASE: "held_under",
    }[kind]


def _refuse_version_mismatch(schema: Schema) -> None:
    if schema.version != DEPENDENCY_DSL_VERSION:
        raise DependencyCompileError(
            REASON_SCHEMA_VERSION_MISMATCH,
            f"schema {schema.version!r} != DSL {DEPENDENCY_DSL_VERSION!r}",
        )


def _validate_shape(op: Operation) -> None:
    if not isinstance(op.op_id, str) or not op.op_id:
        raise DependencyCompileError(REASON_MALFORMED_OPERATION, "op_id must be non-empty")
    if not op.writes and not op.reads:
        raise DependencyCompileError(
            REASON_EMPTY_OPERATION,
            f"operation {op.op_id!r} touches nothing; governance still applies "
            "(COMPSAC-CASE-08) — refuse rather than emit an empty closure",
        )
    for name in (*op.writes, *op.reads):
        if not isinstance(name, str) or not name:
            raise DependencyCompileError(
                REASON_MALFORMED_OPERATION, f"resource id must be non-empty string: {name!r}"
            )


def _validate_resources(op: Operation, schema: Schema) -> set[str]:
    touched = set(op.writes) | set(op.reads)
    for edge_read, _ in op.declared_edges:
        if edge_read not in touched:
            raise DependencyCompileError(
                REASON_UNKNOWN_MUTATION_TARGET,
                f"declared edge references undeclared read {edge_read!r} on {op.op_id!r}",
            )
    unknown = sorted(r for r in touched if r not in schema.resources)
    if unknown:
        raise DependencyCompileError(
            REASON_UNKNOWN_MUTATION_TARGET,
            f"resources not in schema table: {unknown}",
        )
    return touched


def assert_no_wildcard_omission(closure: frozenset[Dependency], op: Operation) -> None:
    """Prove every declared write/read has a same-resource dependency.

    Raises :class:`DependencyCompileError` (``UNKNOWN_MUTATION_TARGET``) naming
    the omitted resource — the property the independent oracle checks
    (blueprint COMPSAC-CASE-04: missing dependency edge detection).
    """
    covered = {d.resource for d in closure}
    omitted = sorted((set(op.writes) | set(op.reads)) - covered)
    if omitted:
        raise DependencyCompileError(
            REASON_UNKNOWN_MUTATION_TARGET,
            f"wildcard omission detected: no dependency for {omitted}",
        )


@dataclasses.dataclass(frozen=True)
class ClosureReport:
    """JSON-serializable compile outcome (fail-closed record on refusal)."""

    op_id: str
    ok: bool
    reason_code: str | None
    detail: str | None
    closure: frozenset[Dependency] = dataclasses.field(default_factory=frozenset)
    dsl_version: str = DEPENDENCY_DSL_VERSION
    closure_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "op_id": self.op_id,
            "ok": self.ok,
            "reason_code": self.reason_code,
            "detail": self.detail,
            "closure": sorted(
                (d.to_dict() for d in self.closure),
                key=lambda d: (d["kind"], d["resource"]),
            ),
            "dsl_version": self.dsl_version,
            "closure_sha256": self.closure_sha256,
        }


def compile_with_report(op: Operation, schema: Schema) -> ClosureReport:
    """Compile and wrap success/failure into one serializable report record."""
    try:
        closure = compile_dependencies(op, schema)
    except DependencyCompileError as exc:
        return ClosureReport(
            op_id=getattr(op, "op_id", "?"),
            ok=False,
            reason_code=exc.reason_code,
            detail=exc.detail,
        )
    canonical = json.dumps(
        sorted((d.to_dict() for d in closure), key=lambda d: (d["kind"], d["resource"])),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return ClosureReport(
        op_id=op.op_id,
        ok=True,
        reason_code=None,
        detail=None,
        closure=closure,
        closure_sha256=hashlib.sha256(canonical).hexdigest(),
    )


def compile_all(operations: Sequence[Operation], schema: Schema) -> list[ClosureReport]:
    """Compile a batch; per-operation failures are reports, never raised."""
    return [compile_with_report(op, schema) for op in operations]
