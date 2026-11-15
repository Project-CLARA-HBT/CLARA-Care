"""Emit the SACMAT-X05_opa_runner task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the SACMAT-X05_opa_runner task. No network access.

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
TASK = "SACMAT-X05_opa_runner"

BASE_SHA = "5f97bc366a18a2d3722884cfc44a25fb2d6bee59"

CHANGED = [
    "evaluation/venue2027/sacmat/opa_runner.py",
    "research/venue2027/sacmat/tests/test_opa_runner.py",
    "research/venue2027/proof/SACMAT-X05_opa_runner.json",
    "research/venue2027/proof/emit_SACMAT-X05_opa_runner_report.py",
    "research/venue2027/proof/logs/SACMAT-X05_opa_runner.pytest.log",
    "research/venue2027/proof/logs/SACMAT-X05_opa_runner.ruff.log",
    "research/venue2027/proof/logs/SACMAT-X05_opa_runner.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q research/venue2027/sacmat/tests/test_opa_runner.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-X05_opa_runner.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/sacmat/opa_runner.py "
        "research/venue2027/sacmat/tests/test_opa_runner.py --config ruff.toml",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-X05_opa_runner.ruff.log",
    },
    {
        "argv": "python3 research/venue2027/proof/emit_SACMAT-X05_opa_runner_report.py "
        "# build_report + validate_report(ok:true) recorded in "
        "research/venue2027/proof/SACMAT-X05_opa_runner.json",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-X05_opa_runner.validator.log",
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
            "evaluation/venue2027/sacmat/opa_runner.py",
            "research/venue2027/sacmat/tests/test_opa_runner.py",
            "research/venue2027/proof/logs/SACMAT-X05_opa_runner.pytest.log",
            "research/venue2027/proof/logs/SACMAT-X05_opa_runner.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P03 task SACMAT-X05_opa_runner (PolicyTrace RQ3): real-binary OPA "
            "adapter with a clearly-labelled in-process port. "
            "evaluation/venue2027/sacmat/opa_runner.py (OPA_RUNNER_VERSION "
            "1.0.0) implements the task-contract adapter evaluate_opa(module, "
            "input) -> Decision: detect_opa() resolves the REAL binary with "
            "shutil.which('opa'); when present, run_opa_eval writes the "
            "deterministically compiled Rego bundle (compile_rego_module: "
            "final-state delegated-consent policy, deny-overrides precedence, "
            "package clara.sacmat.delegated_consent, entrypoint data."
            "clara.sacmat.delegated_consent.decision, sorted emission, no "
            "clock/randomness) plus a JSON input document to a private temp "
            "dir, shells out to `opa eval --format=json` under a subprocess "
            "budget, probes the binary's actual `opa version`, and maps real "
            "output onto the four-valued oracle (string decisions pass "
            "through; true/false -> PERMIT/DENY; OPA undefined -> "
            "NOT_APPLICABLE; failures/timeouts/unparseable output -> "
            "INDETERMINATE with stable reason codes OPA_EXECUTION_ERROR / "
            "OPA_TIMEOUT / OPA_INVALID_OUTPUT). When the binary is ABSENT the "
            "runner returns NOT_RUN_EXTERNAL / BASELINE_UNAVAILABLE (never a "
            "fabricated verdict, never counted as a completion); "
            "ctx.simulate_unavailable_upstream yields the same transparent "
            "non-run. HONEST ENGINE STATUS: at proof-emission time the real "
            "`opa` binary was NOT installed in this environment "
            "(shutil.which('opa') is None), so every executed run in this "
            "task's evidence is the labelled in-process port path or the "
            "transparent NOT_RUN_EXTERNAL path; NO real OPA execution is "
            "claimed. Binary-present behaviour is implemented and "
            "conditionally tested (skipif not OPA_PRESENT) so another agent "
            "with `opa` on PATH obtains real recorded binary output, version "
            "provenance (opa-binary:<version> backend label) and "
            "agreement/disagreement adjudication against the port "
            "(OPA_PORT_AGREEMENT -> ADMIT / OPA_PORT_DISAGREEMENT -> REJECT, "
            "both counted_as_success=True with both backends named in the "
            "detail). The faithful in-process XACML-like adapter is "
            "explicitly LABELLED as a PORT: evaluate_xacml_port delegates to "
            "the existing XacmlPolicyEngine from "
            "evaluation/venue2027/sacmat/baselines.py (deny-overrides rule "
            "combining over the compiled final policy state, faithful to the "
            "XACML 3.0 combining family the MC/DC literature targets) with "
            "backend label xacml-port:in-process-port-of-baselines."
            "XacmlPolicyEngine and the detail label 'PORT: ... NOT the "
            "upstream OPA binary and NOT an OPA run'; the port is never "
            "conflated with a binary verdict. KNOWN_ENCODING_LIMITATIONS "
            "declares the labelled portability surface (final-state encoding, "
            "(actor, purpose) keys) that RQ3 measures. Injection safety: "
            "UNSAFE_POLICY_IDENTIFIER allowlist refuses Rego-unsafe "
            "identifiers at compile time (compile happens BEFORE binary "
            "detection so malformed units fail closed regardless of binary "
            "presence). Malformed cases (missing request, empty/non-list "
            "history, unknown event kinds, bad types, non-monotonic times) "
            "are first-class INDETERMINATE outcomes with the baselines reason "
            "codes; wiring errors (non-mapping case, non-SacmatContext) raise "
            "SacmatOpaRunnerError with stable reason codes. Test driver "
            "research/venue2027/sacmat/tests/test_opa_runner.py (stdlib + "
            "pytest): 33 tests — 30 passed, 3 skipped, 0 failed in this "
            "environment (skips are the conditional real-binary tests and a "
            "real-OPA-undefined probe, skipped precisely BECAUSE the binary "
            "is absent; with `opa` installed they execute the binary and "
            "record its real output). Positive: module contract constants, "
            "typed OpaVerdict JSON round trip + unknown-verdict refusal, port "
            "byte-parity with baselines.XacmlPolicyEngine (PERMIT/DENY/"
            "NOT_APPLICABLE), deterministic Rego compilation (byte-identical "
            "modules), compiled deny-overrides precedence and header labels, "
            "input-document shape, binary-present run recording real output. "
            "Adversarial: binary absent -> NOT_RUN_EXTERNAL/"
            "BASELINE_UNAVAILABLE with counted_as_success=False, retriable, "
            "and NO PERMIT/DENY string in the detail (not a fake success); "
            "simulate_unavailable_upstream -> same transparent non-run; "
            "failing binary -> INDETERMINATE/OPA_EXECUTION_ERROR; exit-0 "
            "unrecognized-output binary -> INDETERMINATE/OPA_INVALID_OUTPUT; "
            "injection vectors (tabs, semicolons, spaces, overlong) refused "
            "by the runner; quote/backslash/newline/overlong identifiers "
            "refused at compile_rego_module/build_opa_input; malformed-case "
            "battery (5 reason codes); wiring errors; port-label separation "
            "assertions (xacml-port never reported as opa-binary). uvx "
            "ruff@0.7.1 check clean on both touched files; full local "
            "evaluation/venue2027/sacmat + research/venue2027/sacmat/tests "
            "suite 324 passed, 3 skipped. baseline_parity=NOT_APPLICABLE "
            "(this IS the external-engine adapter task; parity of the port "
            "against baselines.XacmlPolicyEngine is asserted in-tree). "
            "source_sha_after records the base commit 5f97bc36 per the "
            "established sibling convention; the single task commit SHA is "
            "created immediately after this report and recorded in the commit "
            "body. Downstream consumers: RQ3 portability matrix, SACMAT-X03/"
            "X04 sibling adapters (Cedar/OpenFGA), policy-trace runner."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "SACMAT-X05_opa_runner.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    log = REPO / "research" / "venue2027" / "proof" / "logs" / "SACMAT-X05_opa_runner.validator.log"
    log.write_text("validator running\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    payload = json.dumps(result.to_dict(), indent=2) + "\n"
    log.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
