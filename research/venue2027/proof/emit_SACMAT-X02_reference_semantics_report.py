"""Emit the SACMAT-X02_reference_semantics task proof report via agent_protocol.build_report."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
BASE = "e373f6e46465917ad4fbd7d6656e77e51c4805db"

CHANGED = [
    "evaluation/venue2027/sacmat/reference_semantics.py",
    "evaluation/venue2027/sacmat/test_reference_semantics.py",
    "research/venue2027/proof/logs/SACMAT-X02_reference_semantics.pytest.log",
    "research/venue2027/proof/logs/SACMAT-X02_reference_semantics.ruff.log",
    "research/venue2027/proof/logs/SACMAT-X02_reference_semantics.validator.log",
    "research/venue2027/proof/SACMAT-X02_reference_semantics.json",
]


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id="SACMAT-X02_reference_semantics",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/sacmat/test_reference_semantics.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/SACMAT-X02_reference_semantics.pytest.log",
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check evaluation/venue2027/sacmat/reference_semantics.py "
                    "evaluation/venue2027/sacmat/test_reference_semantics.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/SACMAT-X02_reference_semantics.ruff.log",
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 format --check evaluation/venue2027/sacmat/reference_semantics.py "
                    "evaluation/venue2027/sacmat/test_reference_semantics.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/SACMAT-X02_reference_semantics.ruff.log",
            },
        ],
        artifact_paths=[
            "evaluation/venue2027/sacmat/reference_semantics.py",
            "evaluation/venue2027/sacmat/test_reference_semantics.py",
            "research/venue2027/proof/logs/SACMAT-X02_reference_semantics.pytest.log",
            "research/venue2027/proof/logs/SACMAT-X02_reference_semantics.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 task SACMAT-X02_reference_semantics (RQ3): language-independent "
            "reference decision oracle for PolicyTrace. "
            "evaluation/venue2027/sacmat/reference_semantics.py implements "
            "reference_decide(trace, request) -> ReferenceVerdict from first "
            "principles — it imports NO candidate policy engine or baseline arm "
            "(verified: module imports only stdlib) and may accept "
            "PolicyTrace-shaped input (any object/dict exposing .events with "
            "kind/principal/tenant/resource/purpose/policy_state/logical_time "
            "records) via duck-typed field access without depending on that "
            "module. DELEGATE convention: policy_state carries the delegating "
            "source, principal is the delegate gaining authority. History is "
            "replayed in logical-time order per (tenant, resource, purpose) "
            "scope implementing the four mandated semantic axes: (1) grant "
            "ordering — authority records carry the logical time they were "
            "(re-)established; an access at a decision time before the grant "
            "came into force is expiry divergence -> DENY; (2) delegation "
            "transitivity — DELEGATE inherits the source's active authority and "
            "records edges both forward (BFS cycle detection) and inverted "
            "(delegate -> delegators) so multi-hop redelegation chains resolve; "
            "a delegation whose source has no active authority at that logical "
            "time is UNRESOLVABLE_DELEGATION -> UNKNOWN (never a forced deny); "
            "an edge closing a cycle taints every principal on the cycle in "
            "scope (delegated consent must be acyclic) -> DENY; (3) revocation "
            "dominance — REVOKE removes the actor's authority and is remembered "
            "as an epoch; the query principal's authority chain is walked "
            "UPSTREAM over the inverted delegation graph so any revoked actor "
            "backing inherited authority at or before decision_time denies "
            "(revoked-actor transitivity; a downstream redelegation cannot "
            "resurrect revoked authority, while a fresh direct GRANT clears the "
            "principal's own revocation epoch as a new authority basis); "
            "(4) obligation satisfaction — every declared obligation must be "
            "strictly satisfied (True), one fault -> DENY. Fail-closed "
            "composition: missing/None/non-int logical_time on any event or "
            "missing decision_time -> INDETERMINATE MISSING_LOGICAL_TIME "
            "(temporal precedence undecidable, never a safe-looking denial); "
            "empty/unknown query purpose -> DENY UNKNOWN_PURPOSE; malformed "
            "identifiers -> INDETERMINATE MALFORMED_EVENT; empty trace -> DENY "
            "EMPTY_TRACE; unsupported event kinds -> UNKNOWN "
            "UNSUPPORTED_CONSTRUCT; otherwise ALLOW. Four-valued portable "
            "verdict (ALLOW/DENY/INDETERMINATE/UNKNOWN) with stable reason "
            "codes, JSON-serializable dataclasses, canonical trace_sha256, no "
            "clock/randomness/I/O. "
            "test_reference_semantics.py imports only the reference module "
            "(independence rule): 8 positive controls (conformant grant->access "
            "ALLOW, delegation transitivity ALLOW for two-hop chains, expiry "
            "divergence DENY, revocation dominance DENY, re-grant after "
            "revocation restores direct authority, satisfied obligations ALLOW, "
            "JSON round-trip stability, PolicyTrace-shaped duck-typed input "
            "accepted) and 12 adversarial controls (revoke-before-grant DENY, "
            "delegation cycle never permits, missing event logical_time -> "
            "INDETERMINATE, missing decision_time -> INDETERMINATE, "
            "revoked-actor transitive DENY, redelegation chain to revoked root "
            "DENY, unknown purpose DENY, purpose mismatch DENY, obligation "
            "fault DENY, empty trace DENY, unsupported kind UNKNOWN, "
            "unresolvable delegation UNKNOWN) plus malformed-query "
            "INDETERMINATE and JSON-serializability checks. 27 passed in 0.25s; "
            "uvx ruff@0.7.1 check + format --check clean. "
            "source_sha_after records base commit e373f6e4 per sibling "
            "convention; the single task commit SHA is created immediately "
            "after this report and reported in the handoff. Baseline parity "
            "NOT_APPLICABLE (reference-semantics layer; engine arms execute in "
            "P03). Dependency SACMAT-schema PASS verified in "
            "STATE/completion.json before start. Next ready tasks: SACMAT-X03.. "
            "per taskctl ready."
        ),
    )

    out_path = REPO / "research/venue2027/proof/SACMAT-X02_reference_semantics.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="SACMAT-X02_reference_semantics",
    )
    log_path = REPO / "research/venue2027/proof/logs/SACMAT-X02_reference_semantics.validator.log"
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
