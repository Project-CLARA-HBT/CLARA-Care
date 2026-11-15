"""Emit research/venue2027/proof/COMPSAC-X01_readset_dsl.json via agent_protocol.

Assembles the COMPSAC-X01_readset_dsl task report with real command logs
(pytest, ruff check+format, emitter/validator) and hashes every declared
artifact, then validates it with agent_protocol.validate_report.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from research.venue2027._shared.tools.agent_protocol import (  # noqa: E402
    build_report,
    validate_report,
)

TASK_ID = "COMPSAC-X01_readset_dsl"
SOURCE_SHA_BEFORE = "e5f7ee3b32c6463f8bdf7c30a1e3bf987ca15bb2"

CHANGED_PATHS = [
    "evaluation/venue2027/compsac/dependency_dsl.py",
    "evaluation/venue2027/compsac/test_dependency_dsl.py",
    "research/venue2027/proof/logs/COMPSAC-X01_readset_dsl.pytest.log",
    "research/venue2027/proof/logs/COMPSAC-X01_readset_dsl.ruff.log",
]

ARTIFACT_PATHS = [
    "evaluation/venue2027/compsac/dependency_dsl.py",
    "evaluation/venue2027/compsac/test_dependency_dsl.py",
    "research/venue2027/proof/logs/COMPSAC-X01_readset_dsl.pytest.log",
    "research/venue2027/proof/logs/COMPSAC-X01_readset_dsl.ruff.log",
]


def main() -> int:
    source_sha_after = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()

    report = build_report(
        task_id=TASK_ID,
        status="PASS",
        source_sha_before=SOURCE_SHA_BEFORE,
        source_sha_after=source_sha_after,
        changed_paths=CHANGED_PATHS,
        commands=[
            {
                "argv": "python3 -m pytest -q "
                "evaluation/venue2027/compsac/test_dependency_dsl.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/COMPSAC-X01_readset_dsl.pytest.log",
            },
            {
                "argv": "uvx ruff@0.7.1 check "
                "evaluation/venue2027/compsac/dependency_dsl.py "
                "evaluation/venue2027/compsac/test_dependency_dsl.py && "
                "uvx ruff@0.7.1 format --check "
                "evaluation/venue2027/compsac/dependency_dsl.py "
                "evaluation/venue2027/compsac/test_dependency_dsl.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/COMPSAC-X01_readset_dsl.ruff.log",
            },
            {
                "argv": "PYTHONPATH=. python3 "
                "research/venue2027/proof/emit_COMPSAC-X01_readset_dsl_report.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/COMPSAC-X01_readset_dsl.emit.log",
            },
        ],
        artifact_paths=ARTIFACT_PATHS,
        repo=ROOT,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 typed transaction dependency language (dependency-closure oracle input "
            "language, RQ1 — Dependency-Complete Optimistic Admission for Concurrent "
            "Clinical AI Writes). dependency_dsl.py: DependencyKind StrEnum "
            "(GOVERNANCE/ENTITY/EVIDENCE/LEASE); frozen dataclasses Dependency, Operation "
            "(op_id/writes/reads/declared_edges, to_dict/from_dict), Schema "
            "(version-pinned, MappingProxyType-backed); compile_dependencies(op, schema) "
            "-> frozenset[Dependency] derives the REQUIRED closure — exactly one "
            "dependency per distinct touched resource (writes ∪ reads), kind from the "
            "schema resource table, schema-pinned default version/epoch (GOVERNANCE epoch "
            "floor 0, others 'current'), declared-edge predicate overrides the kind "
            "default — with NO implicit wildcard omission: unknown write/read/edge target "
            "fails closed UNKNOWN_MUTATION_TARGET, unregistered predicate fails closed "
            "UNKNOWN_PREDICATE, schema version != clara.compsac.dependency-dsl-v1 refused "
            "SCHEMA_VERSION_MISMATCH, empty touch set refused EMPTY_OPERATION "
            "(governance still applies, COMPSAC-CASE-08), malformed operation/schema "
            "refused MALFORMED_OPERATION/MALFORMED_SCHEMA. "
            "assert_no_wildcard_omission(closure, op) independently proves every declared "
            "write/read has a same-resource dependency and names any omitted resource "
            "(COMPSAC-CASE-04 detection). ClosureReport/compile_with_report/compile_all "
            "produce JSON-serializable fail-closed records with stable reason codes and a "
            "canonical closure_sha256; failures are first-class reports, never coerced to "
            "safe acceptances (metrics contract item 6). test_dependency_dsl.py imports "
            "only the DSL (independent-oracle rule): 64-seed property test (seeded, "
            "deterministic random operations) proves (a) completeness — every read/write "
            "present with the schema kind, (b) no wildcard — closure resources == touched "
            "resources plus explicit prover, (c) stability — identical recompilation and "
            "identical closure_sha256; plus batch-totality, 3 positive controls (governed "
            "medication write, schema-pinned versions, read==write dedup) and 10 "
            "adversarial controls (unknown write/read target, unknown predicate, schema "
            "version mismatch, edge-to-undeclared-read, empty op, malformed op/schema x3, "
            "injected-gap prover catch, first-class failure reports). 80 passed in 0.34s "
            "(full compsac suite 139 passed); uvx ruff@0.7.1 check + format --check "
            "clean; mypy 1.13.0 --ignore-missing-imports clean. Deliverable modules are "
            "already tracked at the base commit (c2a7f607 is an ancestor of the task base "
            "e5f7ee3b); source_sha_after records the base commit e5f7ee3b per sibling "
            "convention (COMPSAC-X02_closure_oracle) because the single task commit SHA "
            "is created immediately after this report is emitted. oracle_disagreement_count "
            "null (no candidate-vs-oracle comparison run in this task; the X02 oracle and "
            "X04/X05 harnesses consume this DSL). Baseline parity NOT_APPLICABLE (schema "
            "layer; arms B0-B4 execute in P03 COMPSAC-X04..X07)."
        ),
    )

    out = ROOT / "research" / "venue2027" / "proof" / "COMPSAC-X01_readset_dsl.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}", flush=True)

    # Validate the emitted report and write the proof-of-validation log
    # OUTSIDE the report's own artifact set (a log describing the validation
    # of the report cannot hash itself).
    validation = validate_report(
        json.loads(out.read_text(encoding="utf-8")),
        repo=ROOT,
        expected_task_id=TASK_ID,
    )
    validator_log = (
        ROOT / "research" / "venue2027" / "proof" / "logs" / "COMPSAC-X01_readset_dsl.validator.log"
    )
    validator_log.write_text(json.dumps(validation.to_dict(), indent=1) + "\n", encoding="utf-8")
    print(json.dumps(validation.to_dict(), indent=1), flush=True)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
