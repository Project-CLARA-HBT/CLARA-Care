"""COMPSAC-X02_closure_oracle — independent declarative dependency oracle.

Purpose
-------
Reference oracle for "Dependency-Complete Optimistic Admission for Concurrent
Clinical AI Writes" (research/venue2027/VENUES/compsac/RESEARCH_BLUEPRINT.md,
RQ1/RQ2). It derives the expected dependency closure for a clinical write
operation from a *declarative, locally encoded* rule table — never by calling
the candidate compiler in ``evaluation/venue2027/compsac/dependency_dsl.py``.
The candidate and this module must agree only through independent
implementation; :func:`assert_oracle_independence` machine-checks the
independence invariant (GATES/INDEPENDENT_EVIDENCE_PROTOCOL.md item 2: "the
independent oracle must not import any candidate code") by scanning this
module's own source with :mod:`ast` and refusing any import of the candidate
DSL module (stable reason code ``CANDIDATE_IMPORT``).

Allowed input
-------------
- :class:`OracleOperation`: ``op_id``, ``writes``, ``reads`` (JSON-serializable
  via :meth:`OracleOperation.to_dict` / :meth:`OracleOperation.from_dict`);
  ids must be non-empty strings.
- The module-local declarative rule table :data:`RESOURCE_RULES`: resource id
  -> :class:`ResourceRule` (kind, version/epoch requirement, predicate,
  review flag). Ambiguous rules are flagged for review — the oracle never
  guesses: any operation touching a flagged resource returns the stable reason
  code ``AMBIGUOUS_RULE_REVIEW`` instead of a closure.
- :class:`OracleState`: consent/policy epoch snapshot the closure must anchor
  to (governance anchors are never omitted, blueprint COMPSAC-CASE-08).

Failure semantics (stable reason codes on :class:`OracleError`)
---------------------------------------------------------------
- ``EMPTY_OPERATION`` — an operation touching nothing cannot anchor
  governance and is refused rather than emitted as an empty closure.
- ``MALFORMED_OPERATION`` — non-string/empty ids.
- ``UNRULED_RESOURCE`` — a touched resource absent from the declarative rule
  table; fail closed, never silently dropped.
- ``AMBIGUOUS_RULE_REVIEW`` — a touched resource whose rule is flagged
  ``review_required``; escalated for human review, not guessed.
- ``STATE_MISMATCH`` — state is not an :class:`OracleState`.
- ``CANDIDATE_IMPORT`` — :func:`assert_oracle_independence` detected an import
  of the candidate DSL module in this file.

Version
-------
``CLOSURE_ORACLE_VERSION = "clara.compsac.closure-oracle-v1"``. Output is
JSON-serializable: :meth:`Dependency.to_dict`, :meth:`ClosureResult.to_dict`.
"""

from __future__ import annotations

import ast
import dataclasses
import enum
import hashlib
import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

CLOSURE_ORACLE_VERSION: Final[str] = "clara.compsac.closure-oracle-v1"

CANDIDATE_DSL_MODULE: Final[str] = "evaluation.venue2027.compsac.dependency_dsl"
CANDIDATE_DSL_BASENAMES: Final[tuple[str, ...]] = ("dependency_dsl",)

REASON_EMPTY_OPERATION: Final[str] = "EMPTY_OPERATION"
REASON_MALFORMED_OPERATION: Final[str] = "MALFORMED_OPERATION"
REASON_UNRULED_RESOURCE: Final[str] = "UNRULED_RESOURCE"
REASON_AMBIGUOUS_RULE_REVIEW: Final[str] = "AMBIGUOUS_RULE_REVIEW"
REASON_STATE_MISMATCH: Final[str] = "STATE_MISMATCH"
REASON_CANDIDATE_IMPORT: Final[str] = "CANDIDATE_IMPORT"
DYNAMIC_IMPORT_SENTINEL: Final[str] = "__dynamic__"


class DependencyKind(enum.StrEnum):
    """Kinds of required cross-resource dependency edges (oracle vocabulary)."""

    GOVERNANCE = "GOVERNANCE"
    ENTITY = "ENTITY"
    EVIDENCE = "EVIDENCE"
    LEASE = "LEASE"


@dataclasses.dataclass(frozen=True)
class Dependency:
    """One required cross-resource dependency edge (oracle-local type)."""

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
class OracleOperation:
    """A clinical write operation with its declared touch set."""

    op_id: str
    writes: tuple[str, ...]
    reads: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "op_id": self.op_id,
            "writes": list(self.writes),
            "reads": list(self.reads),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> OracleOperation:
        try:
            return cls(
                op_id=payload["op_id"],
                writes=tuple(payload["writes"]),
                reads=tuple(payload["reads"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise OracleError(
                REASON_MALFORMED_OPERATION, f"operation payload malformed: {exc}"
            ) from exc


@dataclasses.dataclass(frozen=True)
class OracleState:
    """Consent/policy epoch snapshot a closure must anchor to."""

    consent_epoch: int
    policy_epoch: int

    def to_dict(self) -> dict[str, Any]:
        return {"consent_epoch": self.consent_epoch, "policy_epoch": self.policy_epoch}


@dataclasses.dataclass(frozen=True)
class ResourceRule:
    """One declarative row of the oracle's local rule table.

    ``review_required=True`` marks an ambiguous rule: the oracle escalates any
    operation touching the resource instead of guessing a closure.
    """

    kind: DependencyKind
    version_or_epoch: str | int
    predicate: str
    review_required: bool = False


# Declarative reference rule table (module-local; deliberately NOT derived
# from, nor consulted against, the candidate DSL schema). "medication_note" is
# flagged ambiguous on purpose: its dependency semantics (draft vs committed
# note version) is under review and must never be silently guessed.
RESOURCE_RULES: Final[Mapping[str, ResourceRule]] = {
    "consent": ResourceRule(DependencyKind.GOVERNANCE, 0, "governed_by"),
    "policy": ResourceRule(DependencyKind.GOVERNANCE, 0, "governed_by"),
    "medication": ResourceRule(DependencyKind.ENTITY, "current", "depends_on_current"),
    "allergy": ResourceRule(DependencyKind.ENTITY, "current", "depends_on_current"),
    "history": ResourceRule(DependencyKind.ENTITY, "current", "depends_on_current"),
    "lab_digest": ResourceRule(DependencyKind.EVIDENCE, "current", "backed_by"),
    "imaging_digest": ResourceRule(DependencyKind.EVIDENCE, "current", "backed_by"),
    "write_lease": ResourceRule(DependencyKind.LEASE, "current", "held_under"),
    "medication_note": ResourceRule(
        DependencyKind.ENTITY, "current", "depends_on_current", review_required=True
    ),
}


class OracleError(Exception):
    """Fail-closed oracle rejection carrying a stable reason code."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        super().__init__(f"{reason_code}: {detail}" if detail else reason_code)
        self.reason_code = reason_code
        self.detail = detail


def _validate_operation(op: OracleOperation) -> frozenset[str]:
    if not isinstance(op, OracleOperation):
        raise OracleError(REASON_MALFORMED_OPERATION, "op must be an OracleOperation")
    if not isinstance(op.op_id, str) or not op.op_id:
        raise OracleError(REASON_MALFORMED_OPERATION, "op_id must be non-empty")
    for name in (*op.writes, *op.reads):
        if not isinstance(name, str) or not name:
            raise OracleError(
                REASON_MALFORMED_OPERATION, f"resource id must be non-empty string: {name!r}"
            )
    touched = frozenset((*op.writes, *op.reads))
    if not touched:
        raise OracleError(
            REASON_EMPTY_OPERATION,
            f"operation {op.op_id!r} touches nothing; governance still applies "
            "(COMPSAC-CASE-08) — refuse rather than emit an empty closure",
        )
    return touched


def expected_dependencies(op: OracleOperation, state: OracleState) -> frozenset[Dependency]:
    """Derive the EXPECTED dependency closure for ``op`` from the rule table.

    Exactly one dependency per distinct touched resource: kind, required
    version/epoch and predicate come from the declarative rule table row;
    GOVERNANCE rows anchor to the operation's state epochs (consent -> consent
    epoch, policy -> policy epoch). Unknown resources fail closed
    (``UNRULED_RESOURCE``) and review-flagged rules escalate
    (``AMBIGUOUS_RULE_REVIEW``) — nothing is ever silently dropped or guessed.
    """
    if not isinstance(state, OracleState):
        raise OracleError(REASON_STATE_MISMATCH, "state must be an OracleState")
    touched = _validate_operation(op)
    unruled = sorted(r for r in touched if r not in RESOURCE_RULES)
    if unruled:
        raise OracleError(REASON_UNRULED_RESOURCE, f"resources not in rule table: {unruled}")
    ambiguous = sorted(r for r in touched if RESOURCE_RULES[r].review_required)
    if ambiguous:
        raise OracleError(
            REASON_AMBIGUOUS_RULE_REVIEW,
            f"resources flagged for rule review on {op.op_id!r}: {ambiguous}",
        )
    closure: set[Dependency] = set()
    for resource in sorted(touched):
        rule = RESOURCE_RULES[resource]
        epoch: str | int = rule.version_or_epoch
        if rule.kind is DependencyKind.GOVERNANCE:
            epoch = state.consent_epoch if resource == "consent" else state.policy_epoch
        closure.add(Dependency(rule.kind, resource, epoch, rule.predicate))
    return frozenset(closure)


def assert_no_wildcard_omission(closure: Iterable[Dependency], op: OracleOperation) -> None:
    """Prove every declared write/read carries a same-resource dependency."""
    covered = {d.resource for d in closure}
    omitted = sorted((set(op.writes) | set(op.reads)) - covered)
    if omitted:
        raise OracleError(
            REASON_UNRULED_RESOURCE, f"wildcard omission detected: no dependency for {omitted}"
        )


def closure_sha256(closure: Iterable[Dependency]) -> str:
    """Canonical sha256 of a closure (sorted, JSON-serializable)."""
    canonical = json.dumps(
        sorted((d.to_dict() for d in closure), key=lambda d: (d["kind"], d["resource"])),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


@dataclasses.dataclass(frozen=True)
class ClosureResult:
    """JSON-serializable oracle outcome (fail-closed record on refusal)."""

    op_id: str
    ok: bool
    reason_code: str | None
    detail: str | None
    closure: frozenset[Dependency] = dataclasses.field(default_factory=frozenset)
    oracle_version: str = CLOSURE_ORACLE_VERSION
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
            "oracle_version": self.oracle_version,
            "closure_sha256": self.closure_sha256,
        }


def expected_with_report(op: OracleOperation, state: OracleState) -> ClosureResult:
    """Derive the closure and wrap success/failure into one report record."""
    try:
        closure = expected_dependencies(op, state)
    except OracleError as exc:
        return ClosureResult(
            op_id=getattr(op, "op_id", "?"),
            ok=False,
            reason_code=exc.reason_code,
            detail=exc.detail,
        )
    return ClosureResult(
        op_id=op.op_id,
        ok=True,
        reason_code=None,
        detail=None,
        closure=closure,
        closure_sha256=closure_sha256(closure),
    )


def _ast_import_targets(tree: ast.AST) -> set[str]:
    """Collect every module path this file's AST imports (import/from-import)."""
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            # ``from pkg import dependency_dsl`` binds the candidate via an
            # alias name; the from-module and every alias are both targets.
            if node.module:
                targets.add(node.module)
            targets.update(alias.name for alias in node.names)
    return targets


def scan_source_for_candidate_imports(source: str | None = None) -> frozenset[str]:
    """Parse this module's source with ast and return candidate imports found.

    An import is a candidate import if any dotted path component equals a
    candidate DSL basename (e.g. ``...compsac.dependency_dsl`` or
    ``dependency_dsl``) — matching by basename closes the
    relative-import/alias escape hatch while staying exact (never a substring
    match, so ``test_dependency_dsl``-style names of other modules do not trip
    it, and this module legitimately never needs the candidate). Dynamic
    imports (``__import__(...)`` / ``importlib.import_module(...)``) are
    reported as the sentinel ``__dynamic__``: their target is not statically
    provable, so they are flagged for review rather than guessed safe
    (INDEPENDENT_EVIDENCE_PROTOCOL.md item 2).
    """
    if source is None:
        source = Path(__file__).resolve().read_text(encoding="utf-8")
    tree = ast.parse(source, filename=__file__)
    found: set[str] = set()
    for target in _ast_import_targets(tree):
        parts = target.split(".")
        if any(part in CANDIDATE_DSL_BASENAMES for part in parts):
            found.add(target)
    for node in ast.walk(tree):
        dynamic = False
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                dynamic = True
            elif (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "import_module"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "importlib"
            ):
                dynamic = True
        if dynamic:
            found.add(DYNAMIC_IMPORT_SENTINEL)
    return frozenset(found)


def assert_oracle_independence(source: str | None = None) -> None:
    """Refuse any import of the candidate DSL module in this oracle module.

    Scans this module's *source* (live file by default, injected string in
    tests) with :mod:`ast` — never via ``sys.modules`` introspection, so a
    dynamic import the AST cannot see stays impossible in the first place and
    the check itself stays independent of import side effects. Raises
    :class:`OracleError` with ``CANDIDATE_IMPORT`` naming every offending
    import target.
    """
    if sys.modules.get(CANDIDATE_DSL_MODULE) is not None and False:  # pragma: no cover
        # Kept unreachable by design: sys.modules presence is NOT evidence of a
        # source-level dependency (the test suite legitimately imports the
        # candidate elsewhere). Independence is a source-level property.
        raise OracleError(REASON_CANDIDATE_IMPORT, CANDIDATE_DSL_MODULE)
    found = scan_source_for_candidate_imports(source)
    if found:
        raise OracleError(
            REASON_CANDIDATE_IMPORT,
            f"independent oracle imports candidate DSL module(s) or unresolved "
            f"dynamic import(s): {sorted(found)}",
        )


def run_self_checks(state: OracleState) -> Sequence[ClosureResult]:
    """Deterministic built-in self-checks (positive, ambiguous, unruled).

    Returns one :class:`ClosureResult` per self-check; raises only on internal
    inconsistency (a positive check that fails to compile), which would mean
    the rule table and the derivation logic drifted apart.
    """
    results = [
        expected_with_report(
            OracleOperation("selfcheck-med-write", ("medication",), ("consent", "allergy")), state
        ),
        expected_with_report(
            OracleOperation("selfcheck-ambiguous", ("medication_note",), ()), state
        ),
        expected_with_report(OracleOperation("selfcheck-unruled", ("ghost_row",), ()), state),
    ]
    if not results[0].ok:
        raise OracleError(
            REASON_UNRULED_RESOURCE,
            f"self-check positive case refused: {results[0].reason_code} {results[0].detail}",
        )
    return results
