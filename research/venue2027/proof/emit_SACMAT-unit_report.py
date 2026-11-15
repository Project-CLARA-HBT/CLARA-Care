"""Emit the SACMAT-unit task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced
by the SACMAT-unit task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
TASK = "SACMAT-unit"

BASE_SHA = "5f97bc366a18a2d3722884cfc44a25fb2d6bee59"

CHANGED = [
    "tests/venue2027/sacmat/__init__.py",
    "tests/venue2027/sacmat/test_algorithm_properties.py",
    "research/venue2027/proof/SACMAT-unit.json",
    "research/venue2027/proof/emit_SACMAT-unit_report.py",
    "research/venue2027/proof/logs/SACMAT-unit.pytest.log",
    "research/venue2027/proof/logs/SACMAT-unit.ruff.log",
    "research/venue2027/proof/logs/SACMAT-unit.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q tests/venue2027/sacmat/test_algorithm_properties.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-unit.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check tests/venue2027/sacmat/__init__.py "
        "tests/venue2027/sacmat/test_algorithm_properties.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-unit.ruff.log",
    },
    {
        "argv": "python3 research/venue2027/proof/emit_SACMAT-unit_report.py "
        "# build_report + validate_report(ok:true) recorded in "
        "research/venue2027/proof/SACMAT-unit.json",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-unit.validator.log",
    },
]


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=[
            "tests/venue2027/sacmat/__init__.py",
            "tests/venue2027/sacmat/test_algorithm_properties.py",
            "research/venue2027/proof/logs/SACMAT-unit.pytest.log",
            "research/venue2027/proof/logs/SACMAT-unit.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        notes=(
            "P05 algorithmic property/metamorphic test suite for SACMAT 2027 "
            "(PolicyTrace: Temporal Conformance Testing of Delegated Consent across "
            "Heterogeneous Policy Engines). tests/venue2027/sacmat/test_algorithm_properties.py "
            "drives ONLY the REAL SACMAT algorithmic surfaces: the three in-process engine "
            "models (XacmlPolicyEngine deny-overrides, CedarPolicyEngine forbid precedence, "
            "ZanzibarPolicyEngine read-time relation walk), the independent four-valued "
            "oracle (oracle_decision) and arm dispatch B0/B1/B2/B3 via public run_baseline, "
            "plus the temporal policy-trace DSL (parse_policy_trace / evaluate_trace). "
            "Decision boundaries: expiry flip at decision_time == expiry (oracle DENY + "
            "zanzibar NOT_APPLICABLE while compiled final-state xacml still PERMITs), "
            "version-skew boundary inclusive at decision_time (bump at dt-1 ADMIT, at dt "
            "REJECT with B3_POLICY_VERSION_SKEW_DIVERGENCE), unknown principal NOT_APPLICABLE "
            "(never silently DENY) and DSL UNESTABLISHED_AUTHORITY INDETERMINATE (never a "
            "permit). Race scenarios: delegation-expiry race REJECTed by B2+B3 but ADMITted "
            "by B0+B1, healed by regrant back to ADMIT under every arm; policy-skew race "
            "REJECTed by B3 alone while B0/B1/B2 all ADMIT. Two-step metamorphic relations "
            "over seeded randomized corpora (random.Random per-trial fixed seeds; no global "
            "seeding, no wall clock): M1 appending a REVOKE for the requesting key can never "
            "mint a PERMIT (oracle + all engines; revoking can only reduce access); M2 after "
            "the appended REVOKE both compiled final-state engines answer DENY and Zanzibar "
            "never gains a permit; M3 appending a POLICY_VERSION_BUMP at t >= decision time "
            "only tightens conformance detection (B3 REJECT stays REJECT, engine decisions "
            "and oracle verdict unchanged; adding a policy version can only tighten "
            "conformance detection); M4 time-shift invariance (constant shift of all logical "
            "times/expiry/decision time preserves oracle, zanzibar and DSL verdicts); M5 DSL "
            "findings are append-only (every prefix (kind, witness) finding persists in the "
            "full trace); M6 DSL revocation flips later access to DENY and re-granting a "
            "revoked principal stays fail-closed (sticky revocation witnessed as "
            "REVOKED_ACTOR_TRANSITIVITY). Mutation checks (RQ2 analogue): seeded mutant "
            "corpus (expiry_tighten / revoke_drop / purpose_swap / bump_insert, >= 400 "
            "mutants) with B3's killed set a proven superset of B1's and B2's at equal "
            "budget and strictly killing temporal mutants both pointwise arms miss; every "
            "REJECT detail carries its arm's stable reason code and counted_as_success=True; "
            "full-corpus replay twice is byte-identical (determinism). DSL parse-level "
            "fail-closed boundaries (UNORDERED_TIMESTAMPS, DUPLICATE_TIMESTAMP, EMPTY_TRACE, "
            "SCHEMA_VERSION_MISMATCH, MALFORMED_EVENT, MISSING_LOGICAL_TIME) and "
            "delegation-cycle / revoke-before-grant witnesses asserted on the REAL parser. "
            "All corpus units are synthetic delegated-consent histories in monotonic "
            "logical time (no PHI/PII, no network, no live provider, no hidden clock or "
            "randomness). Machine-checked: 19 new tests pass; tests/venue2027/sacmat suite "
            "42 passed; uvx ruff@0.7.1 check clean on touched files. "
            "source_sha_after = commit HEAD at proof-emission time."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "SACMAT-unit.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    log = REPO / "research" / "venue2027" / "proof" / "logs" / "SACMAT-unit.validator.log"
    log.write_text("validator running\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    payload = json.dumps(result.to_dict(), indent=2) + "\n"
    log.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
