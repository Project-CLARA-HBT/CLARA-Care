"""Tests for COMPSAC-X01_readset_dsl — dependency closure property test.

Independent property test (seeded, deterministic random operations): the
compiled closure must be (a) COMPLETE — every declared read/write resource
appears as a dependency of the correct kind, (b) WILDCARD-FREE — no resource
is dropped or summarized away, and (c) STABLE — recompilation of the same
operation under the same schema yields an identical closure (and identical
sha256). Adversarial controls fail closed with stable reason codes:
UNKNOWN_MUTATION_TARGET (unknown write/read target, unknown edge read),
UNKNOWN_PREDICATE, SCHEMA_VERSION_MISMATCH, plus malformed-input refusal.
The test module imports only the DSL under test (independent oracle rule):
no candidate runtime, no DB, no model, no clock/randomness beyond the seeded
`random.Random` instance created locally.
"""

from __future__ import annotations

import hashlib
import json
import random
from typing import cast

import pytest

from evaluation.venue2027.compsac.dependency_dsl import (
    DEPENDENCY_DSL_VERSION,
    REASON_EMPTY_OPERATION,
    REASON_MALFORMED_OPERATION,
    REASON_MALFORMED_SCHEMA,
    REASON_SCHEMA_VERSION_MISMATCH,
    REASON_UNKNOWN_MUTATION_TARGET,
    REASON_UNKNOWN_PREDICATE,
    ClosureReport,
    Dependency,
    DependencyCompileError,
    DependencyKind,
    Operation,
    Schema,
    assert_no_wildcard_omission,
    compile_all,
    compile_dependencies,
    compile_with_report,
    make_schema,
)

KIND_FOR_RESOURCE_HINT = {
    "consent": DependencyKind.GOVERNANCE,
    "policy": DependencyKind.GOVERNANCE,
    "medication": DependencyKind.ENTITY,
    "allergy": DependencyKind.ENTITY,
    "history": DependencyKind.ENTITY,
    "lab_digest": DependencyKind.EVIDENCE,
    "imaging_digest": DependencyKind.EVIDENCE,
    "write_lease": DependencyKind.LEASE,
}
ALL_RESOURCES = sorted(KIND_FOR_RESOURCE_HINT)
ALL_PREDICATES = ("depends_on_current", "governed_by", "backed_by", "held_under")


def build_schema() -> Schema:
    return make_schema(resources=dict(KIND_FOR_RESOURCE_HINT))


def seeded_operation(rng: random.Random, index: int) -> Operation:
    """Deterministic random operation over the fixed resource universe."""
    n_writes = rng.randint(1, 3)
    n_reads = rng.randint(1, 3)
    writes = rng.sample(ALL_RESOURCES, n_writes)
    reads = rng.sample(ALL_RESOURCES, min(n_reads, len(ALL_RESOURCES) - n_writes + 1))
    edge_pool = sorted(set(reads) | set(writes))
    edges = [(rng.choice(edge_pool), rng.choice(ALL_PREDICATES)) for _ in range(rng.randint(0, 3))]
    return Operation(
        op_id=f"synthetic-op-{index}",
        writes=tuple(dict.fromkeys(writes)),
        reads=tuple(r for r in dict.fromkeys(reads) if r not in writes),
        declared_edges=tuple(dict.fromkeys(edges)),
    )


KIND_FOR_RESOURCE = {r: k for r, k in KIND_FOR_RESOURCE_HINT.items()}


# ---------------------------------------------------------------------------
# (a) completeness + (b) no wildcard omission + (c) stability — property test
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(64))
def test_property_closure_complete_no_wildcard_stable(seed: int) -> None:
    rng = random.Random(2026_0000 + seed)
    schema = build_schema()
    op = seeded_operation(rng, seed)

    closure = compile_dependencies(op, schema)

    # (a) COMPLETE: every touched resource is present with the schema kind.
    for resource in {*(op.writes), *(op.reads)}:
        matches = [d for d in closure if d.resource == resource]
        assert matches, f"closure missing resource {resource!r}"
        assert all(d.kind is KIND_FOR_RESOURCE[resource] for d in matches)
        assert all(d.required_version_or_epoch is not None for d in matches)

    # (b) NO WILDCARD: closure resources ⊆ touched resources, and the explicit
    # prover confirms no declared write/read lost its dependency.
    touched = set(op.writes) | set(op.reads)
    closure_resources = {d.resource for d in closure}
    assert closure_resources == touched, "closure invented or dropped resources"
    assert_no_wildcard_omission(closure, op)  # raises on omission

    # (c) STABLE: byte-identical recompilation, frozenset equality, same sha.
    closure_again = compile_dependencies(op, schema)
    assert closure == closure_again
    report_a = compile_with_report(op, schema)
    report_b = compile_with_report(op, schema)
    assert report_a.closure_sha256 == report_b.closure_sha256
    assert len(closure) == len(set((d.kind, d.resource) for d in closure))
    # Round-trip: JSON-serializable output survives a canonical dump/reload.
    payload = json.dumps(report_a.to_dict(), sort_keys=True).encode()
    assert hashlib.sha256(payload).hexdigest()


def test_property_batch_reports_are_total(seed: int = 7) -> None:
    rng = random.Random(777)
    schema = build_schema()
    ops = [seeded_operation(rng, i) for i in range(16)]
    reports = compile_all(ops, schema)
    assert len(reports) == len(ops)
    assert all(isinstance(r, ClosureReport) and r.ok for r in reports)
    for op, report in zip(ops, reports, strict=True):
        assert report.op_id == op.op_id
        assert_no_wildcard_omission(report.closure, op)


# ---------------------------------------------------------------------------
# Positive controls (governed operations compile as specified)
# ---------------------------------------------------------------------------


def test_positive_governed_medication_write() -> None:
    schema = build_schema()
    op = Operation(
        op_id="op-med-write",
        writes=("medication",),
        reads=("consent", "allergy", "lab_digest", "write_lease"),
        declared_edges=(("allergy", "depends_on_current"), ("consent", "governed_by")),
    )
    closure = compile_dependencies(op, schema)
    by_key = {(d.kind, d.resource): d for d in closure}
    assert by_key[(DependencyKind.ENTITY, "medication")].predicate == "depends_on_current"
    assert by_key[(DependencyKind.GOVERNANCE, "consent")].predicate == "governed_by"
    assert by_key[(DependencyKind.ENTITY, "allergy")].predicate == "depends_on_current"
    assert by_key[(DependencyKind.EVIDENCE, "lab_digest")].predicate == "backed_by"
    assert by_key[(DependencyKind.LEASE, "write_lease")].predicate == "held_under"
    assert_no_wildcard_omission(closure, op)


def test_positive_schema_pinned_default_versions_win() -> None:
    schema = make_schema(
        resources=dict(KIND_FOR_RESOURCE_HINT),
        default_versions={"consent": 41, "medication": "v7"},
    )
    op = Operation(
        op_id="op-versions",
        writes=("medication",),
        reads=("consent",),
        declared_edges=(),
    )
    closure = compile_dependencies(op, schema)
    by_resource = {d.resource: d for d in closure}
    assert by_resource["consent"].required_version_or_epoch == 41
    assert by_resource["medication"].required_version_or_epoch == "v7"


def test_positive_write_and_read_of_same_resource_single_dependency() -> None:
    schema = build_schema()
    op = Operation(
        op_id="op-readwrite",
        writes=("history",),
        reads=("history",),
        declared_edges=(),
    )
    closure = compile_dependencies(op, schema)
    assert len(closure) == 1  # one resource, one dependency (deduplicated)
    (dep,) = closure
    assert dep.kind is DependencyKind.ENTITY and dep.resource == "history"


# ---------------------------------------------------------------------------
# Adversarial controls — fail closed with stable reason codes
# ---------------------------------------------------------------------------


def test_adversarial_unknown_write_target_fails_closed() -> None:
    op = Operation("op-bad-write", ("medication", "ghost_resource"), (), ())
    with pytest.raises(DependencyCompileError) as excinfo:
        compile_dependencies(op, build_schema())
    assert excinfo.value.reason_code == REASON_UNKNOWN_MUTATION_TARGET
    assert "ghost_resource" in excinfo.value.detail


def test_adversarial_unknown_read_target_fails_closed() -> None:
    op = Operation("op-bad-read", (), ("phantom_row",), ())
    with pytest.raises(DependencyCompileError) as excinfo:
        compile_dependencies(op, build_schema())
    assert excinfo.value.reason_code == REASON_UNKNOWN_MUTATION_TARGET


def test_adversarial_unknown_predicate_fails_closed() -> None:
    op = Operation(
        "op-bad-predicate",
        ("medication",),
        ("allergy",),
        (("allergy", "vibes_based_dependency"),),
    )
    with pytest.raises(DependencyCompileError) as excinfo:
        compile_dependencies(op, build_schema())
    assert excinfo.value.reason_code == REASON_UNKNOWN_PREDICATE


def test_adversarial_schema_version_mismatch_refused() -> None:
    stale_schema = make_schema(
        version="clara.compsac.dependency-dsl-v0-RETired",
        resources=dict(KIND_FOR_RESOURCE_HINT),
    )
    op = Operation("op-any", ("medication",), (), ())
    with pytest.raises(DependencyCompileError) as excinfo:
        compile_dependencies(op, stale_schema)
    assert excinfo.value.reason_code == REASON_SCHEMA_VERSION_MISMATCH


def test_adversarial_edge_references_undeclared_read_fails_closed() -> None:
    # Edge references a real schema resource the operation never declared.
    op = Operation(
        "op-edge-undeclared",
        ("medication",),
        ("consent",),
        (("allergy", "depends_on_current"),),
    )
    with pytest.raises(DependencyCompileError) as excinfo:
        compile_dependencies(op, build_schema())
    assert excinfo.value.reason_code == REASON_UNKNOWN_MUTATION_TARGET


def test_adversarial_empty_operation_refused() -> None:
    with pytest.raises(DependencyCompileError) as excinfo:
        compile_dependencies(Operation("op-empty", (), (), ()), build_schema())
    assert excinfo.value.reason_code == REASON_EMPTY_OPERATION


def test_adversarial_malformed_operation_refused() -> None:
    with pytest.raises(DependencyCompileError) as excinfo:
        compile_dependencies(Operation("", ("medication",), (), ()), build_schema())
    assert excinfo.value.reason_code == REASON_MALFORMED_OPERATION
    with pytest.raises(DependencyCompileError) as excinfo:
        Operation.from_dict({"writes": ["medication"], "reads": [], "declared_edges": []})
    assert excinfo.value.reason_code == REASON_MALFORMED_OPERATION


def test_adversarial_malformed_schema_refused() -> None:
    with pytest.raises(DependencyCompileError) as excinfo:
        # str, not DependencyKind — cast only types the adversarial literal.
        make_schema(resources=cast("dict[str, DependencyKind]", {"medication": "ENTITY"}))
    assert excinfo.value.reason_code == REASON_MALFORMED_SCHEMA
    with pytest.raises(DependencyCompileError) as excinfo:
        make_schema(
            resources=dict(KIND_FOR_RESOURCE_HINT),
            default_versions={"unregistered": 1},
        )
    assert excinfo.value.reason_code == REASON_MALFORMED_SCHEMA


def test_adversarial_wildcard_omission_prover_catches_injected_gap() -> None:
    # The independent-prover contract: a closure that drops a declared write is
    # detected by assert_no_wildcard_omission, never waved through.
    schema = build_schema()
    op = Operation("op-gap", ("medication", "allergy"), ("consent",), ())
    full_closure = compile_dependencies(op, schema)
    injected_gap = frozenset(d for d in full_closure if d.resource != "allergy")
    assert len(injected_gap) == len(full_closure) - 1
    with pytest.raises(DependencyCompileError) as excinfo:
        assert_no_wildcard_omission(injected_gap, op)
    assert excinfo.value.reason_code == REASON_UNKNOWN_MUTATION_TARGET
    assert "allergy" in excinfo.value.detail


def test_report_failures_are_first_class_not_safe_acceptances() -> None:
    # Failures surface as structured reports with reason codes — never as ok
    # reports, and never as silently empty closures (metrics contract: report
    # indeterminate/rejected separately, do not coerce to PASS).
    bad_ops = [
        Operation("op-ghost", ("ghost_resource",), (), ()),
        Operation(
            "op-bad-pred",
            ("medication",),
            ("allergy",),
            (("allergy", "unregistered_pred"),),
        ),
    ]
    reports = compile_all(bad_ops, build_schema())
    assert [r.ok for r in reports] == [False, False]
    assert [r.reason_code for r in reports] == [
        REASON_UNKNOWN_MUTATION_TARGET,
        REASON_UNKNOWN_PREDICATE,
    ]
    assert all(r.closure == frozenset() for r in reports)


def test_dependency_and_report_are_json_serializable() -> None:
    schema = build_schema()
    op = Operation("op-json", ("medication",), ("consent",), (("consent", "governed_by"),))
    report = compile_with_report(op, schema)
    payload = json.dumps(report.to_dict(), sort_keys=True)
    assert f'"{DEPENDENCY_DSL_VERSION}"' in payload
    restored = json.loads(payload)
    assert restored["ok"] is True
    assert {d["resource"] for d in restored["closure"]} == {"medication", "consent"}


def test_str_enum_kind_serializes_as_plain_string() -> None:
    dep = Dependency(
        kind=DependencyKind.GOVERNANCE,
        resource="policy",
        required_version_or_epoch=0,
        predicate="governed_by",
    )
    assert json.loads(json.dumps(dep.to_dict()))["kind"] == "GOVERNANCE"
