"""Tests for COMPSAC-X02_closure_oracle — independent declarative oracle.

Positive controls prove the oracle derives the expected governed closures
(governance anchors to live state epochs, entity/evidence/lease rows follow
the declarative rule table) deterministically and JSON-serializably.
Adversarial controls prove independence and fail-closed semantics:

- ``assert_oracle_independence`` accepts the clean oracle source but refuses
  any source variant that imports the candidate DSL module
  (``evaluation.venue2027.compsac.dependency_dsl``) with ``CANDIDATE_IMPORT`` —
  covering plain import, from-import, aliased import, dotted relative paths
  and an injected import appended to the real source (tamper control).
- Unknown resources, review-flagged ambiguous rules, empty and malformed
  operations, and a wrong state type all fail closed with stable reason codes.
- The test module imports only the oracle (independent-oracle rule): no
  candidate DSL import, no DB, no model, no clock/randomness.
"""

from __future__ import annotations

import json

import pytest

from evaluation.venue2027.compsac.independent_closure_oracle import (
    CANDIDATE_DSL_MODULE,
    CLOSURE_ORACLE_VERSION,
    REASON_AMBIGUOUS_RULE_REVIEW,
    REASON_CANDIDATE_IMPORT,
    REASON_EMPTY_OPERATION,
    REASON_MALFORMED_OPERATION,
    REASON_STATE_MISMATCH,
    REASON_UNRULED_RESOURCE,
    RESOURCE_RULES,
    ClosureResult,
    Dependency,
    DependencyKind,
    OracleError,
    OracleOperation,
    OracleState,
    assert_no_wildcard_omission,
    assert_oracle_independence,
    expected_dependencies,
    expected_with_report,
    run_self_checks,
    scan_source_for_candidate_imports,
)

STATE = OracleState(consent_epoch=41, policy_epoch=7)


# ---------------------------------------------------------------------------
# Positive controls — governed operations derive the expected closure
# ---------------------------------------------------------------------------


def test_positive_governed_medication_write() -> None:
    op = OracleOperation(
        "op-med-write",
        writes=("medication",),
        reads=("consent", "allergy", "lab_digest", "write_lease"),
    )
    closure = expected_dependencies(op, STATE)
    by_key = {(d.kind, d.resource): d for d in closure}
    assert by_key[(DependencyKind.ENTITY, "medication")] == Dependency(
        DependencyKind.ENTITY, "medication", "current", "depends_on_current"
    )
    assert by_key[(DependencyKind.GOVERNANCE, "consent")] == Dependency(
        DependencyKind.GOVERNANCE, "consent", 41, "governed_by"
    )
    assert by_key[(DependencyKind.ENTITY, "allergy")].predicate == "depends_on_current"
    assert by_key[(DependencyKind.EVIDENCE, "lab_digest")].predicate == "backed_by"
    assert by_key[(DependencyKind.LEASE, "write_lease")].predicate == "held_under"
    assert_no_wildcard_omission(closure, op)
    assert len(closure) == 5


def test_positive_governance_anchors_to_state_epochs() -> None:
    op = OracleOperation("op-governance", writes=("policy",), reads=("consent",))
    closure = expected_dependencies(op, OracleState(consent_epoch=99, policy_epoch=12))
    by_resource = {d.resource: d for d in closure}
    assert by_resource["consent"].required_version_or_epoch == 99
    assert by_resource["policy"].required_version_or_epoch == 12
    other = expected_dependencies(op, OracleState(consent_epoch=100, policy_epoch=12))
    assert {d.required_version_or_epoch for d in other if d.resource == "consent"} == {100}


def test_positive_write_and_read_of_same_resource_deduplicates() -> None:
    op = OracleOperation("op-readwrite", writes=("history",), reads=("history",))
    closure = expected_dependencies(op, STATE)
    assert len(closure) == 1
    (dep,) = closure
    assert dep.kind is DependencyKind.ENTITY and dep.resource == "history"


def test_positive_deterministic_and_json_serializable() -> None:
    op = OracleOperation("op-stable", writes=("medication",), reads=("consent",))
    first = expected_with_report(op, STATE)
    second = expected_with_report(op, STATE)
    assert first.closure == second.closure
    assert first.closure_sha256 == second.closure_sha256
    assert len(first.closure_sha256) == 64
    payload = json.dumps(first.to_dict(), sort_keys=True).encode()
    assert isinstance(json.loads(payload), dict)
    assert first.oracle_version == CLOSURE_ORACLE_VERSION
    # from_dict round-trip stays JSON-serializable and equivalent.
    op2 = OracleOperation.from_dict(op.to_dict())
    assert op2 == op
    assert expected_dependencies(op2, STATE) == first.closure


def test_positive_closure_result_success_record() -> None:
    report = expected_with_report(OracleOperation("op-report", ("allergy",), ("consent",)), STATE)
    assert isinstance(report, ClosureResult)
    assert report.ok and report.reason_code is None and report.detail is None
    as_dict = report.to_dict()
    assert as_dict["ok"] is True
    assert {(d["kind"], d["resource"]) for d in as_dict["closure"]} == {
        (DependencyKind.ENTITY.value, "allergy"),
        (DependencyKind.GOVERNANCE.value, "consent"),
    }


def test_positive_self_checks_and_rule_table_shape() -> None:
    results = run_self_checks(STATE)
    assert [r.ok for r in results] == [True, False, False]
    assert results[1].reason_code == REASON_AMBIGUOUS_RULE_REVIEW
    assert results[2].reason_code == REASON_UNRULED_RESOURCE
    assert all(isinstance(r, ClosureResult) for r in results)
    for resource, rule in RESOURCE_RULES.items():
        assert isinstance(rule.kind, DependencyKind)
        assert isinstance(resource, str) and resource
        assert isinstance(rule.predicate, str) and rule.predicate


# ---------------------------------------------------------------------------
# Adversarial controls — independence from the candidate DSL
# ---------------------------------------------------------------------------


def test_adversarial_clean_source_passes_independence() -> None:
    assert_oracle_independence()  # live module source: must not raise
    assert scan_source_for_candidate_imports() == frozenset()


@pytest.mark.parametrize(
    "snippet",
    [
        f"import {CANDIDATE_DSL_MODULE}",
        f"import {CANDIDATE_DSL_MODULE} as dsl",
        f"from {CANDIDATE_DSL_MODULE} import Dependency",
        "from evaluation.venue2027.compsac import dependency_dsl",
        "import dependency_dsl",
        "from dependency_dsl import compile_dependencies",
        "import compsac.dependency_dsl",
    ],
)
def test_adversarial_candidate_import_refused(snippet: str) -> None:
    with pytest.raises(OracleError) as excinfo:
        assert_oracle_independence(f'"""doc"""\n{snippet}\n')
    assert excinfo.value.reason_code == REASON_CANDIDATE_IMPORT
    assert "dependency_dsl" in excinfo.value.detail


def test_adversarial_tampered_live_source_refused() -> None:
    # Tamper control: appending one candidate import to the real source must
    # flip the verdict (the scan really reads the source it is given).
    source = (
        __import__("pathlib")
        .Path(
            __import__(
                "evaluation.venue2027.compsac.independent_closure_oracle", fromlist=["x"]
            ).__file__
        )
        .read_text(encoding="utf-8")
    )
    with pytest.raises(OracleError) as excinfo:
        assert_oracle_independence(source + f"\nimport {CANDIDATE_DSL_MODULE}\n")
    assert excinfo.value.reason_code == REASON_CANDIDATE_IMPORT


def test_adversarial_unrelated_imports_accepted() -> None:
    # ast is exact: similar-looking names of OTHER modules must not trip it.
    snippet = (
        "import ast\n"
        "from evaluation.venue2027.compsac.independent_closure_oracle import OracleError\n"
        "import my_dependency_dsl_tests\n"
        "from dataclasses import dataclass\n"
    )
    assert scan_source_for_candidate_imports(snippet) == frozenset()
    assert_oracle_independence(snippet)


def test_adversarial_dynamic_import_flagged() -> None:
    # importlib/__import__ calls cannot be statically proven safe; the scan
    # reports them for review instead of silently passing the independence
    # claim (fail closed on the unknown, per INDEPENDENT_EVIDENCE_PROTOCOL 2).
    dynamic_snippet = 'x = __import__("evaluation.venue2027.compsac.dependency_dsl")\n'
    flagged = scan_source_for_candidate_imports(dynamic_snippet)
    assert flagged == frozenset({"__dynamic__"})
    with pytest.raises(OracleError) as excinfo:
        assert_oracle_independence(dynamic_snippet)
    assert excinfo.value.reason_code == REASON_CANDIDATE_IMPORT
    importlib_snippet = (
        "import importlib\n"
        'm = importlib.import_module("evaluation.venue2027.compsac.dependency_dsl")\n'
    )
    assert scan_source_for_candidate_imports(importlib_snippet) == frozenset({"__dynamic__"})
    with pytest.raises(OracleError):
        assert_oracle_independence(importlib_snippet)


# ---------------------------------------------------------------------------
# Adversarial controls — fail-closed closure semantics
# ---------------------------------------------------------------------------


def test_adversarial_unknown_resource_fails_closed() -> None:
    for bad in (("_writes", "ghost_row"), ("reads", "phantom_consent")):
        op = OracleOperation(
            "op-bad",
            writes=(bad[1],) if bad[0] == "_writes" else (),
            reads=() if bad[0] == "_writes" else (bad[1],),
        )
        with pytest.raises(OracleError) as excinfo:
            expected_dependencies(op, STATE)
        assert excinfo.value.reason_code == REASON_UNRULED_RESOURCE
        assert bad[1] in excinfo.value.detail
    report = expected_with_report(OracleOperation("op-bad2", ("ghost_row",), ()), STATE)
    assert report.ok is False and report.reason_code == REASON_UNRULED_RESOURCE
    assert report.closure == frozenset()


def test_adversarial_ambiguous_rule_escalates_for_review() -> None:
    op = OracleOperation("op-ambiguous", writes=("medication_note",), reads=("consent",))
    with pytest.raises(OracleError) as excinfo:
        expected_dependencies(op, STATE)
    assert excinfo.value.reason_code == REASON_AMBIGUOUS_RULE_REVIEW
    assert "medication_note" in excinfo.value.detail
    # A clean operation is never poisoned by an unrelated flagged resource.
    clean = expected_dependencies(OracleOperation("op-clean", ("consent",), ()), STATE)
    assert {d.resource for d in clean} == {"consent"}


def test_adversarial_empty_and_malformed_operations_refused() -> None:
    with pytest.raises(OracleError) as excinfo:
        expected_dependencies(OracleOperation("op-empty", (), ()), STATE)
    assert excinfo.value.reason_code == REASON_EMPTY_OPERATION
    with pytest.raises(OracleError) as excinfo:
        expected_dependencies(OracleOperation("", ("medication",), ()), STATE)
    assert excinfo.value.reason_code == REASON_MALFORMED_OPERATION
    with pytest.raises(OracleError) as excinfo:
        expected_dependencies(OracleOperation("op-bad-id", ("",), ()), STATE)
    assert excinfo.value.reason_code == REASON_MALFORMED_OPERATION
    with pytest.raises(OracleError) as excinfo:
        OracleOperation.from_dict({"writes": ["medication"], "reads": []})
    assert excinfo.value.reason_code == REASON_MALFORMED_OPERATION
    assert expected_with_report(OracleOperation("op-empty2", (), ()), STATE).reason_code == (
        REASON_EMPTY_OPERATION
    )


def test_adversarial_wrong_state_type_fails_closed() -> None:
    with pytest.raises(OracleError) as excinfo:
        expected_dependencies(OracleOperation("op-any", ("medication",), ()), {"consent_epoch": 1})  # type: ignore[arg-type]
    assert excinfo.value.reason_code == REASON_STATE_MISMATCH


def test_adversarial_no_silent_dependency_drop() -> None:
    # Every emitted dependency's resource must be a declared write/read, and
    # every declared write/read must carry a dependency — no wildcard closure.
    op = OracleOperation("op-total", writes=("medication", "allergy"), reads=("policy",))
    closure = expected_dependencies(op, STATE)
    assert {d.resource for d in closure} == set(op.writes) | set(op.reads)
    assert_no_wildcard_omission(closure, op)
    with pytest.raises(OracleError):
        assert_no_wildcard_omission(frozenset(d for d in closure if d.resource != "policy"), op)
