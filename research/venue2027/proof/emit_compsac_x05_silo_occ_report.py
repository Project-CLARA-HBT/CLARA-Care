"""Emit the COMPSAC-X05_silo_occ task proof report via agent_protocol.build_report."""

from __future__ import annotations

import json
import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
BASE = "06125d5291c6aa4b1d65df6df1d0d7e56de58463"

CHANGED_PATHS = [
    "evaluation/venue2027/compsac/silo_readset_port.py",
    "research/venue2027/compsac/tasks/silo_occ_impl.md",
    "research/venue2027/compsac/tests/test_x05_silo_occ.py",
    "research/venue2027/proof/logs/COMPSAC-X05_silo_occ.pytest.log",
    "research/venue2027/proof/logs/COMPSAC-X05_silo_occ.ruff.log",
    "research/venue2027/proof/logs/COMPSAC-X05_silo_occ.validator.log",
    "research/venue2027/proof/COMPSAC-X05_silo_occ.json",
]


def main() -> int:
    # Sibling convention (COMPSAC-X01_readset_dsl, COMPSAC-baselines): the task
    # is delivered as EXACTLY ONE commit that contains this report, so
    # source_sha_after records the base commit; the single task commit SHA is
    # created immediately after this report and reported in the handoff.
    sha_after = BASE

    report = ap.build_report(
        task_id="COMPSAC-X05_silo_occ",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED_PATHS,
        commands=[
            {
                "argv": (
                    "python3 -m pytest -q "
                    "research/venue2027/compsac/tests/test_x05_silo_occ.py "
                    "evaluation/venue2027/compsac/test_baselines.py"
                ),
                "exit_code": 0,
                "log_path": (
                    "research/venue2027/proof/logs/COMPSAC-X05_silo_occ.pytest.log"
                ),
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check evaluation/venue2027/compsac/"
                    "silo_readset_port.py research/venue2027/compsac/tests/"
                    "test_x05_silo_occ.py && uvx ruff@0.7.1 format --check "
                    "evaluation/venue2027/compsac/silo_readset_port.py "
                    "research/venue2027/compsac/tests/test_x05_silo_occ.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/COMPSAC-X05_silo_occ.ruff.log",
            },
        ],
        artifact_paths=[
            "evaluation/venue2027/compsac/silo_readset_port.py",
            "research/venue2027/compsac/tasks/silo_occ_impl.md",
            "research/venue2027/compsac/tests/test_x05_silo_occ.py",
            "research/venue2027/proof/logs/COMPSAC-X05_silo_occ.pytest.log",
            "research/venue2027/proof/logs/COMPSAC-X05_silo_occ.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="PASS",
        unresolved=[],
        notes=(
            "P03 task X05 Silo-style entity read-set OCC comparator (blueprint arm "
            "B1, strong algorithmic comparator for RQ2): delivered the task-manifest "
            "signature execute_occ(op, store) -> Outcome as a thin additive adapter in "
            "evaluation/venue2027/compsac/silo_readset_port.py (SILO_READSET_PORT_VERSION "
            "1.0.0) over the REAL B1 engine already in evaluation/venue2027/compsac/"
            "baselines.py (COMPSAC_BASELINES_VERSION 1.0.0, registry arm "
            "silo-style-entity-readset-occ, fidelity FAITHFUL_PORT) -- dispatched "
            "through its public run_baseline entry point; NO OCC decision logic is "
            "re-implemented, simulated or weakened here. EXPLICIT DISCLOSURE (task "
            "contract, module docstring, registry, and research/venue2027/compsac/tasks/"
            "silo_occ_impl.md section 3): the comparator is a faithful PORT of the "
            "published Silo algorithm (Tu et al., 'Speedy Transactions in Multicore "
            "In-Memory Databases', SOSP 2013, DOI 10.1145/2517349.2522713, Sec. 3-4: "
            "commit-time per-entity read validation, epoch-bound checks, writes install "
            "version+1) -- NOT Silo source code; no official Silo release exists to pin. "
            "Guarantee formalized in the spec: a COMMIT certifies the operation's entire "
            "DECLARED read set was never mutated between observation and commit "
            "(READSET_VERSION_STALE abort invalidates the operation and installs no "
            "writes); entities outside the declared read set -- including semantically "
            "REQUIRED dependencies the workload omits -- are outside the fence, which is "
            "exactly why the omitted-dependency write skew passes this arm. New API: "
            "SiloOperation frozen dataclass (JSON-serializable to_dict in the engine "
            "transaction shape; unknown keys refused OP_MALFORMED, never silently "
            "dropped), fail-closed input coercion (OP_MALFORMED / STORE_MALFORMED as "
            "EXECUTION_ERROR outcomes, never counted as safe rejections), engine reason "
            "codes (READSET_VERSION_STALE, ENTITY_UNKNOWN, CONSENT_EPOCH_STALE, "
            "POLICY_EPOCH_STALE) pass through unchanged; epoch bindings are resolved "
            "from the store records; no hidden clock/randomness/network. Tests (15, in "
            "research/venue2027/compsac/tests/test_x05_silo_occ.py) import the REAL B1 "
            "baseline and run read-set/commit schedules: commit-time read-set version "
            "validation proven (stale observed version aborts READSET_VERSION_STALE and "
            "the aborted operation's writes are NOT installed -- medication_order stays "
            "v1), plus ENTITY_UNKNOWN, consent/policy epoch rejections (ABA/epoch-cycle "
            "guard: version equality alone does not admit), tampered read_versions "
            "claim caught, degenerate no-op follows ENGINE semantics (adapter never "
            "reclassifies engine-legal input as input error), determinism and JSON "
            "serializability. SCIENTIFIC CONTRAST (RQ2, real abort counts from "
            "run_baseline detail, never assumed): on the canonical omitted-dependency "
            "write-skew schedule B1 ADMITS both transactions (aborted==0, committed==2) "
            "while B4 REJECTs the second commit on the omitted dependency edge "
            "(WRITE_EDGE_SUPERSEDED / REQUIRED_READ_EDGE_STALE, aborted>=1), same case "
            "same config; a closure-is-the-mechanism control adds the omitted edge to "
            "T2's DECLARED read set and B1's own fence then fires "
            "(READSET_VERSION_STALE, aborted==1) -- proving the differential is caused "
            "by the omitted dependency edge, not by any other arm difference. "
            "Backwards compatibility: evaluation/venue2027/compsac/baselines.py is "
            "UNTOUCHED (additive-only module); all 25 pre-existing test_baselines.py "
            "tests pass unmodified; 40 passed total, exit 0; uvx ruff@0.7.1 check + "
            "format --check clean, exit 0. baseline_parity=PASS (comparator executes "
            "the verified B1 arm verbatim; no fork, no drift). "
            "oracle_disagreement_count=0 (no oracle disagreement vector in scope; "
            "independent-oracle adjudication belongs to the COMPSAC-oracle task). "
            "source_sha_after records the base commit 06125d52 per sibling "
            "convention (COMPSAC-X01_readset_dsl): the single task commit is "
            "created immediately after this report and reported in the handoff. "
            "Next ready tasks in this "
            "scope: COMPSAC-X06_coarse_occ, COMPSAC-X07_scope_occ."
        ),
    )

    out = REPO / "research/venue2027/proof/COMPSAC-X05_silo_occ.json"
    out.write_text(json.dumps(report, indent=4, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        report,
        repo=REPO,
        expected_task_id="COMPSAC-X05_silo_occ",
    )
    log_path = REPO / (
        "research/venue2027/proof/logs/COMPSAC-X05_silo_occ.validator.log"
    )
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
