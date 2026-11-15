"""Emit the SACMAT-X04_openfga_runner task proof report via agent_protocol.build_report."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
BASE = "5f97bc366a18a2d3722884cfc44a25fb2d6bee59"

CHANGED = [
    "evaluation/venue2027/sacmat/openfga_adapter.py",
    "research/venue2027/sacmat/tests/test_openfga_runner.py",
    "research/venue2027/proof/SACMAT-X04_openfga_runner.json",
    "research/venue2027/proof/emit_SACMAT-X04_openfga_runner_report.py",
    "research/venue2027/proof/logs/SACMAT-X04_openfga_runner.pytest.log",
    "research/venue2027/proof/logs/SACMAT-X04_openfga_runner.ruff.log",
    "research/venue2027/proof/logs/SACMAT-X04_openfga_runner.suite.log",
    "research/venue2027/proof/logs/SACMAT-X04_openfga_runner.live.log",
    "research/venue2027/proof/logs/SACMAT-X04_openfga_runner.validator.log",
    "artifacts/venue2027/sacmat/x04-openfga-runner-run1/openfga_runner.json",
]


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id="SACMAT-X04_openfga_runner",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": "python3 -m pytest -q research/venue2027/sacmat/tests/test_openfga_runner.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/SACMAT-X04_openfga_runner.pytest.log",
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check evaluation/venue2027/sacmat/openfga_adapter.py "
                    "research/venue2027/sacmat/tests/test_openfga_runner.py && "
                    "uvx ruff@0.7.1 format --check evaluation/venue2027/sacmat/openfga_adapter.py "
                    "research/venue2027/sacmat/tests/test_openfga_runner.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/SACMAT-X04_openfga_runner.ruff.log",
            },
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/SACMAT-X04_openfga_runner.suite.log",
            },
            {
                "argv": (
                    "python3 (live engine probe, log only) -> "
                    "research/venue2027/proof/logs/SACMAT-X04_openfga_runner.live.log + "
                    "artifacts/venue2027/sacmat/x04-openfga-runner-run1/openfga_runner.json"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/SACMAT-X04_openfga_runner.live.log",
            },
        ],
        artifact_paths=[
            "evaluation/venue2027/sacmat/openfga_adapter.py",
            "research/venue2027/sacmat/tests/test_openfga_runner.py",
            "research/venue2027/proof/logs/SACMAT-X04_openfga_runner.pytest.log",
            "research/venue2027/proof/logs/SACMAT-X04_openfga_runner.ruff.log",
            "research/venue2027/proof/logs/SACMAT-X04_openfga_runner.suite.log",
            "research/venue2027/proof/logs/SACMAT-X04_openfga_runner.live.log",
            "artifacts/venue2027/sacmat/x04-openfga-runner-run1/openfga_runner.json",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="PASS",
        unresolved=[],
        notes=(
            "P03 task SACMAT-X04_openfga_runner (RQ3): OpenFGA real-engine adapter. "
            "evaluation/venue2027/sacmat/openfga_adapter.py implements the task "
            "signature evaluate_openfga(model, tuples, query) -> OpenFgaDecision "
            "(portable four-valued PERMIT/DENY/NOT_APPLICABLE/INDETERMINATE) with "
            "two clearly labelled, never-confused execution modes. REAL mode "
            "(engine=openfga-http): a live OpenFGA server is discovered via "
            "OPENFGA_API_URL/OPENFGA_API_TOKEN env or well-known local endpoints "
            "(/healthz HTTP 200 only); the delegated-consent history is translated "
            "explicitly onto a PINNED schema-1.1 authorization model (consent_record"
            "#delegate user tuples; consent#record link + consent#delegate userset "
            "grantee typed consent_record#delegate; can_access=computedUserset("
            "delegate)) and evaluated by the ACTUAL engine via POST /check under the "
            "PINNED consistency mode HIGHER_CONSISTENCY. Pinned upstream: "
            "openfga/openfga:v1.22.1 -> 44054f542f64e9b9589dd26a595081b3d2cfd942. "
            "Event mapping: GRANT/REGRANT write delegate tuples, REVOKE deletes "
            "them, EXPIRE is realized as explicit tuple deletion at the expire tick "
            "(OpenFGA tuples carry no TTL — the one semantic boundary of the "
            "mapping, disclosed not hidden), POLICY_VERSION_BUMP re-creates the "
            "store with a fresh model instance (model_epoch bump). Replay applies "
            "only events at ticks <= decision_time (temporal precedence by "
            "replay). OpenFGA returns pure reachability: allowed=true -> PERMIT, "
            "allowed=false -> NOT_APPLICABLE (no explicit-deny construct — "
            "portability limit asserted in tests); HTTP 4xx -> INDETERMINATE "
            "OPENFGA_CHECK_ERROR; mid-run connection failure -> INDETERMINATE "
            "OPENFGA_CONNECTION_FAILED (never a silent safe rejection, never a "
            "port fallback masquerading as a run). PORT mode "
            "(engine=zanzibar-inprocess-port): when no server is reachable, "
            "run_case returns NOT_RUN_EXTERNAL / BASELINE_UNAVAILABLE (never "
            "counted, retriable) while still running the FAITHFUL-PORT labelled "
            "in-process Zanzibar relation walk ported from "
            "baselines.ZanzibarPolicyEngine (Zanzibar ATC 2019 / OpenFGA v1.22.1 "
            "documented semantics) — EXECUTION_CONTRACT rule 8: no toy "
            "substitution under a real name, the port result is evidence in the "
            "refusal detail, never a fake upstream success. HONEST ENGINE STATUS: "
            "a real OpenFGA v1.22.1 server (docker, pinned image digest "
            "44054f54...) WAS running at 127.0.0.1:18080 during this task and the "
            "real-engine tests + live probe executed against it: clean grant "
            "ADMIT/PERMIT, grant-revoke-regrant ADMIT/PERMIT (regrant in force), "
            "revoked delegate REJECT/NOT_APPLICABLE, expired delegation REJECT, "
            "future grant invisible at decision time REJECT — all recorded with "
            "pinned image/consistency evidence in "
            "artifacts/venue2027/sacmat/x04-openfga-runner-run1/openfga_runner.json "
            "(engine_used=openfga-http, server_reachable=true). Without a server "
            "the suite honestly reports: 13 passed + 6 skipped (real-engine tests "
            "skipped, NOT faked) and the adapter path returns NOT_RUN_EXTERNAL. "
            "19 positive+adversarial tests: engine labels distinct constants, "
            "pinned constants, env-precedence discovery, dead-port discovery "
            "None, evaluate_openfga positive+negative against the real engine, "
            "regrant/revoked/expiry/future-grant real-engine vectors, "
            "NOT_RUN_EXTERNAL refusal with port engine labelled in detail, "
            "simulate_unavailable_upstream forces refusal, port labelled "
            "zanzibar-inprocess-port and never conflated with openfga-http, "
            "connection failure -> INDETERMINATE, engine check error -> "
            "INDETERMINATE with stable reason code, malformed case -> "
            "INDETERMINATE, non-mapping case/malformed context -> wiring errors, "
            "HTTP 4xx -> stable reason code (stub server), refusals never "
            "counted. Machine-checked: pytest 19 passed (log), ruff@0.7.1 check + "
            "format --check clean (log), full evaluation/venue2027 suite 1661 "
            "passed (log). baseline_parity=PASS: the adapter consumes the same "
            "synthetic (policy history, request) case contract as baselines.py "
            "and the port path reuses ZanzibarPolicyEngine verbatim (equal "
            "semantics, labelled port). Dependency SACMAT-baselines PASS "
            "verified in STATE/completion.json before start. source_sha_after "
            "records base commit 5f97bc36 per sibling convention; the single "
            "task commit SHA is created immediately after this report and "
            "reported in the handoff. Next ready tasks per taskctl ready."
        ),
    )

    out_path = REPO / "research/venue2027/proof/SACMAT-X04_openfga_runner.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="SACMAT-X04_openfga_runner",
    )
    log_path = REPO / "research/venue2027/proof/logs/SACMAT-X04_openfga_runner.validator.log"
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
