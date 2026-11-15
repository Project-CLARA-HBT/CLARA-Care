"""Tests for SACMAT-X05_opa_runner — real-binary OPA adapter with labelled port.

Positive controls:
- Module and version constants are present and well-formed; the runner emits
  JSON-serializable typed verdicts (:class:`OpaVerdict.to_dict` round trip).
- The labelled in-process port is faithful to the XACML-like baseline engine:
  a valid grant PERMITs, a revoked grant DENYs (deny-overrides precedence),
  an unrelated request is NOT_APPLICABLE — byte-identical decisions to
  ``baselines.XacmlPolicyEngine`` on the same cases.
- Rego compilation is deterministic (byte-identical modules for identical
  histories), deny-overrides compiles DENY precedence, and a compiled module
  plus input document feed the task-contract adapter.
- If the REAL ``opa`` binary is present on PATH, the runner executes it and
  records the binary's actual output (version probed from the binary; verdict
  provenance labelled ``opa-binary``); agreement/disagreement with the port is
  a first-class ADMIT/REJECT. If absent, tests assert the honest path instead
  (see adversarial controls).

Adversarial controls:
- ``opa`` ABSENT -> NOT_RUN_EXTERNAL / BASELINE_UNAVAILABLE with
  ``counted_as_success=False``, retriable, and NO fabricated verdict — never a
  fake success, never silently counted as a completion.
- ``ctx.simulate_unavailable_upstream=True`` -> the same transparent
  NOT_RUN_EXTERNAL even if a binary were present.
- Real-binary execution failures are INDETERMINATE with stable reason codes
  (OPA_EXECUTION_ERROR / OPA_INVALID_OUTPUT), never mapped onto PERMIT/DENY.
- Unsafe identifiers (Rego injection vectors: quotes, backslashes, newlines,
  overlong fields) are refused with UNSAFE_POLICY_IDENTIFIER.
- Malformed cases (missing request, non-monotonic history, unknown event
  kind, non-mapping case, wrong ctx type) fail closed with stable reason
  codes.
- The port verdict is always distinctly labelled (``xacml-port``) and never
  reported as an OPA binary run.

Failure semantics: adversarial results are first-class Outcome objects or
typed verdicts with stable reason codes, never unhandled exceptions miscounted
as safe rejections (wiring errors are the documented exception and raise).

Honesty note: this suite never asserts that OPA ran unless
``shutil.which('opa')`` actually resolved a binary in this environment; the
binary-present tests are conditional on real detection.
"""

from __future__ import annotations

import shutil

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.sacmat import baselines, opa_runner
from evaluation.venue2027.sacmat.baselines import (
    EVENT_GRANT,
    EVENT_POLICY_VERSION_BUMP,
    EVENT_REVOKE,
    PURPOSE_CARE_TEAM,
    PURPOSE_SELF_CARE,
    SacmatContext,
    event,
    request,
)
from evaluation.venue2027.sacmat.opa_runner import (
    KNOWN_ENCODING_LIMITATIONS,
    OPA_PINNED_VERSION,
    OPA_QUERY,
    OPA_RUNNER_VERSION,
    REGO_PACKAGE,
    XACML_PORT_BACKEND,
    XACML_PORT_LABEL,
    OpaVerdict,
    SacmatOpaRunnerError,
    build_opa_input,
    compile_rego_module,
    detect_opa,
    evaluate_opa,
    evaluate_xacml_port,
    run_opa_eval,
    run_opa_runner,
)

OPA_RUNNER_TEST_VERSION = "1.0.0"

OPA_PRESENT = detect_opa() is not None


def _ctx(**overrides: object) -> SacmatContext:
    return SacmatContext(arm_id="X05-opa-runner", **overrides)  # type: ignore[arg-type]


def _valid_grant_case() -> dict[str, object]:
    return {
        "case_id": "SACMAT-X05-POSITIVE-VALID-GRANT",
        "history": [
            event(EVENT_GRANT, 100, "patient-a", "patient-a", PURPOSE_SELF_CARE, expiry=9000),
        ],
        "request": request("patient-a", PURPOSE_SELF_CARE, 500),
    }


def _revoked_case() -> dict[str, object]:
    return {
        "case_id": "SACMAT-X05-POSITIVE-REVOKED",
        "history": [
            event(EVENT_GRANT, 100, "patient-b", "patient-b", PURPOSE_CARE_TEAM, expiry=9000),
            event(EVENT_REVOKE, 2000, "patient-b", "patient-b", PURPOSE_CARE_TEAM),
        ],
        "request": request("patient-b", PURPOSE_CARE_TEAM, 3000),
    }


# ---------------------------------------------------------------------------
# Module contract.
# ---------------------------------------------------------------------------


def test_module_contract_constants_present() -> None:
    assert OPA_RUNNER_VERSION == "1.0.0"
    assert OPA_PINNED_VERSION == "v1.22.4"
    assert OPA_QUERY == f"data.{REGO_PACKAGE}.decision"
    assert KNOWN_ENCODING_LIMITATIONS
    assert "port" in XACML_PORT_BACKEND
    assert XACML_PORT_LABEL.startswith("PORT:")


def test_verdict_is_json_serializable_round_trip() -> None:
    verdict = OpaVerdict(
        verdict=baselines.PERMIT,
        reason_code=baselines.PERMIT,
        detail="d",
        backend="opa-binary:test",
        opa_version="9.9.9",
        exit_code=0,
    )
    payload = verdict.to_dict()
    assert payload["verdict"] == baselines.PERMIT
    assert payload["backend"] == "opa-binary:test"
    assert payload["opa_version"] == "9.9.9"


def test_verdict_rejects_unknown_value() -> None:
    with pytest.raises(SacmatOpaRunnerError) as err:
        OpaVerdict(verdict="MAYBE", reason_code="X", detail="d", backend="b")
    assert err.value.reason_code == "VERDICT_UNKNOWN"


# ---------------------------------------------------------------------------
# Positive: labelled port fidelity to the XACML-like baseline engine.
# ---------------------------------------------------------------------------


def test_port_matches_xacml_baseline_engine() -> None:
    for case in (_valid_grant_case(), _revoked_case()):
        history = baselines._validate_case(case)  # type: ignore[arg-type]
        assert isinstance(history, baselines.PolicyHistory)
        expected = baselines.XacmlPolicyEngine().evaluate(history, history.request)
        assert evaluate_xacml_port(history) == expected


def test_port_permit_deny_not_applicable() -> None:
    history = baselines._validate_case(_valid_grant_case())  # type: ignore[arg-type]
    assert isinstance(history, baselines.PolicyHistory)
    assert evaluate_xacml_port(history) == baselines.PERMIT
    revoked = baselines._validate_case(_revoked_case())  # type: ignore[arg-type]
    assert isinstance(revoked, baselines.PolicyHistory)
    assert evaluate_xacml_port(revoked) == baselines.DENY
    unrelated = baselines._validate_case(
        {
            "case_id": "SACMAT-X05-POSITIVE-UNRELATED",
            "history": [
                event(EVENT_GRANT, 100, "patient-c", "patient-c", PURPOSE_SELF_CARE, expiry=9000),
            ],
            "request": request("stranger", PURPOSE_SELF_CARE, 500),
        }
    )
    assert isinstance(unrelated, baselines.PolicyHistory)
    assert evaluate_xacml_port(unrelated) == baselines.NOT_APPLICABLE


# ---------------------------------------------------------------------------
# Positive: deterministic Rego compilation.
# ---------------------------------------------------------------------------


def test_compile_rego_module_is_deterministic() -> None:
    case = {
        "case_id": "SACMAT-X05-DETERMINISM",
        "history": [
            event(EVENT_GRANT, 100, "patient-a", "patient-a", PURPOSE_SELF_CARE, expiry=9000),
            event(EVENT_REVOKE, 2000, "patient-b", "patient-b", PURPOSE_CARE_TEAM),
            event(EVENT_GRANT, 3000, "patient-b", "patient-b", PURPOSE_CARE_TEAM, expiry=8000),
        ],
        "request": request("patient-a", PURPOSE_SELF_CARE, 500),
    }
    history = baselines._validate_case(case)  # type: ignore[arg-type]
    assert isinstance(history, baselines.PolicyHistory)
    assert compile_rego_module(history) == compile_rego_module(history)


def test_compiled_module_has_deny_overrides_and_header_labels() -> None:
    history = baselines._validate_case(_revoked_case())  # type: ignore[arg-type]
    assert isinstance(history, baselines.PolicyHistory)
    module = compile_rego_module(history)
    assert f"package {REGO_PACKAGE}" in module
    assert "opa_runner.py" in module
    assert "deny_match" in module
    assert 'decision := "DENY" if deny_match' in module
    assert "_deny_pairs" in module


def test_build_opa_input_shape() -> None:
    history = baselines._validate_case(_valid_grant_case())  # type: ignore[arg-type]
    assert isinstance(history, baselines.PolicyHistory)
    doc = build_opa_input(history)
    assert doc == {
        "actor_id": "patient-a",
        "purpose": PURPOSE_SELF_CARE,
        "decision_time": 500,
    }


# ---------------------------------------------------------------------------
# Positive: real binary execution (conditional on actual presence).
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not OPA_PRESENT, reason="real opa binary not installed on PATH")
def test_real_binary_runs_and_records_actual_output() -> None:
    """When OPA IS installed, run it and record the real binary's output."""
    binary = detect_opa()
    assert binary is not None
    case = _valid_grant_case()
    history = baselines._validate_case(case)  # type: ignore[arg-type]
    assert isinstance(history, baselines.PolicyHistory)
    module = compile_rego_module(history)
    verdict = run_opa_eval(module, build_opa_input(history), opa_binary=binary)
    assert verdict.verdict in {
        baselines.PERMIT,
        baselines.DENY,
        baselines.NOT_APPLICABLE,
        baselines.INDETERMINATE,
    }
    assert verdict.backend.startswith("opa-binary:")
    assert verdict.opa_version != "unknown"
    adapter_decision = evaluate_opa(module, build_opa_input(history), opa_binary=binary)
    assert adapter_decision == verdict.verdict
    outcome = run_opa_runner(case, _ctx())
    assert isinstance(outcome, Outcome)
    assert outcome.observed_outcome in {"ADMIT", "REJECT"}
    assert outcome.counted_as_success is True
    assert "opa-binary:" in outcome.detail
    assert XACML_PORT_BACKEND in outcome.detail


@pytest.mark.skipif(not OPA_PRESENT, reason="real opa binary not installed on PATH")
def test_real_binary_string_decision_contract() -> None:
    """The compiled string-decision policy evaluates through the real binary."""
    binary = detect_opa()
    assert binary is not None
    module = "\n".join(
        [
            "import rego.v1",
            f"package {REGO_PACKAGE}",
            'decision := "PERMIT" if input.actor_id == "patient-a"',
            "",
        ]
    )
    verdict = run_opa_eval(module, {"actor_id": "patient-a"}, opa_binary=binary)
    assert verdict.verdict == baselines.PERMIT


# ---------------------------------------------------------------------------
# Adversarial: binary absent -> transparent NOT_RUN_EXTERNAL, never fake success.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(OPA_PRESENT, reason="opa is installed; absence path not applicable")
def test_binary_absent_returns_not_run_external_verdict() -> None:
    verdict = run_opa_eval('package x\np := true', {"a": 1})
    assert verdict.verdict == "NOT_RUN_EXTERNAL"
    assert verdict.reason_code == opa_runner.RC_BASELINE_UNAVAILABLE
    assert verdict.backend == opa_runner.OPA_BINARY_BACKEND_PREFIX
    outcome = run_opa_runner(_valid_grant_case(), _ctx())
    assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
    assert outcome.counted_as_success is False
    assert outcome.retriable is True
    assert opa_runner.RC_BASELINE_UNAVAILABLE in outcome.detail


@pytest.mark.skipif(OPA_PRESENT, reason="opa is installed; absence path not applicable")
def test_binary_absent_run_adapter_is_not_counted() -> None:
    outcome = run_opa_runner(_revoked_case(), _ctx())
    assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
    assert outcome.counted_as_success is False
    assert "PERMIT" not in outcome.detail
    assert "DENY" not in outcome.detail


def test_simulated_unavailable_upstream_is_transparent_non_run() -> None:
    outcome = run_opa_runner(_valid_grant_case(), _ctx(simulate_unavailable_upstream=True))
    assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
    assert outcome.counted_as_success is False
    assert outcome.retriable is True
    assert opa_runner.RC_BASELINE_UNAVAILABLE in outcome.detail


# ---------------------------------------------------------------------------
# Adversarial: real-binary failure modes map to INDETERMINATE (not decisions).
# ---------------------------------------------------------------------------


def test_binary_execution_failure_is_indeterminate(tmp_path: object) -> None:
    """A real but failing binary yields INDETERMINATE / OPA_EXECUTION_ERROR."""
    fake = shutil.which("python3")
    assert fake is not None
    verdict = run_opa_eval(
        "import rego.v1\npackage nope\np := true\n",
        {"a": 1},
        opa_binary=fake,
        timeout_seconds=10.0,
    )
    assert verdict.verdict == baselines.INDETERMINATE
    assert verdict.reason_code == opa_runner.RC_OPA_EXECUTION_ERROR


def test_binary_invalid_output_is_indeterminate(tmp_path: object) -> None:
    """A real binary exiting 0 with unparseable stdout yields OPA_INVALID_OUTPUT."""
    import pathlib

    fake = pathlib.Path(str(tmp_path)) / "fake_opa.py"
    # Ignores argv entirely and prints JSON with an unrecognized result shape.
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json\nprint(json.dumps({'result': [{'expressions': []}]}))\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    verdict = run_opa_eval(
        "import rego.v1\npackage nope\np := true\n",
        {"a": 1},
        opa_binary=str(fake),
        timeout_seconds=10.0,
    )
    assert verdict.verdict == baselines.INDETERMINATE
    assert verdict.reason_code == opa_runner.RC_OPA_INVALID_OUTPUT
    assert "unrecognized result shape" in verdict.detail


def test_undefined_query_maps_to_not_applicable(tmp_path: object) -> None:
    """A real OPA that returns no result set maps to NOT_APPLICABLE (when present)."""
    binary = detect_opa()
    if binary is None:
        pytest.skip("real opa binary not installed on PATH")
    module = "import rego.v1\npackage empty.test\n\nother := true\n"
    verdict = run_opa_eval(module, {"a": 1}, opa_binary=binary)
    assert verdict.verdict == baselines.NOT_APPLICABLE


# ---------------------------------------------------------------------------
# Adversarial: Rego injection / unsafe identifiers.
# ---------------------------------------------------------------------------

#: Vectors that baselines' type check ACCEPTS (plain non-empty strings) but the
#: Rego allowlist must refuse at compile time.
_INJECTION_VECTORS: tuple[str, ...] = (
    "patient\ttab",
    "patient;drop",
    "patient space end",
    "a" * 65,
)


@pytest.mark.parametrize("bad_actor", _INJECTION_VECTORS)
def test_unsafe_identifiers_refused_by_runner(bad_actor: str) -> None:
    case = {
        "case_id": "SACMAT-X05-INJECTION",
        "history": [
            event(EVENT_GRANT, 100, bad_actor, bad_actor, PURPOSE_SELF_CARE, expiry=9000),
        ],
        "request": request(bad_actor, PURPOSE_SELF_CARE, 500),
    }
    outcome = run_opa_runner(case, _ctx(simulate_unavailable_upstream=False))
    assert outcome.observed_outcome in {baselines.INDETERMINATE, "NOT_RUN_EXTERNAL"}
    if outcome.observed_outcome == baselines.INDETERMINATE:
        assert opa_runner.RC_UNSAFE_POLICY_IDENTIFIER in outcome.detail
    else:
        assert opa_runner.RC_BASELINE_UNAVAILABLE in outcome.detail
    assert outcome.counted_as_success is False


@pytest.mark.parametrize(
    "bad_actor",
    [
        'patient" } #',
        "patient\\",
        "patient\n}",
        "a" * 65,
    ],
)
def test_compile_refuses_unsafe_identifiers(bad_actor: str) -> None:
    history = baselines._validate_case(
        {
            "case_id": "SACMAT-X05-COMPILE-INJECTION",
            "history": [
                event(EVENT_GRANT, 100, bad_actor, bad_actor, PURPOSE_SELF_CARE, expiry=9000),
            ],
            "request": request(bad_actor, PURPOSE_SELF_CARE, 500),
        }
    )
    assert isinstance(history, baselines.PolicyHistory)
    with pytest.raises(SacmatOpaRunnerError) as err:
        compile_rego_module(history)
    assert err.value.reason_code == opa_runner.RC_UNSAFE_POLICY_IDENTIFIER
    with pytest.raises(SacmatOpaRunnerError):
        build_opa_input(history)


# ---------------------------------------------------------------------------
# Adversarial: malformed cases fail closed with stable reason codes.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("case_payload", "reason_code"),
    [
        ({"history": [], "request": request("a", PURPOSE_SELF_CARE, 1)}, "CASE_ID_MISSING"),
        (
            {
                "case_id": "SACMAT-X05-EMPTY-HISTORY",
                "history": [],
                "request": request("a", PURPOSE_SELF_CARE, 1),
            },
            "HISTORY_EVENT_EMPTY",
        ),
        (
            {
                "case_id": "SACMAT-X05-NON-MONOTONIC",
                "history": [
                    event(EVENT_GRANT, 500, "a", "a", PURPOSE_SELF_CARE, expiry=9000),
                    event(EVENT_GRANT, 100, "b", "b", PURPOSE_SELF_CARE, expiry=9000),
                ],
                "request": request("a", PURPOSE_SELF_CARE, 1),
            },
            baselines.RC_EVENT_TIME_NOT_MONOTONIC,
        ),
        (
            {
                "case_id": "SACMAT-X05-UNKNOWN-KIND",
                "history": [
                    {"event_kind": "MUTATE", "logical_time": 1, "actor_id": "a", "delegate_id": "a", "purpose": "p"},
                ],
                "request": request("a", PURPOSE_SELF_CARE, 1),
            },
            baselines.RC_EVENT_KIND_UNKNOWN,
        ),
        (
            {
                "case_id": "SACMAT-X05-NO-REQUEST",
                "history": [
                    event(EVENT_GRANT, 100, "a", "a", PURPOSE_SELF_CARE, expiry=9000),
                ],
            },
            baselines.RC_REQUEST_MISSING,
        ),
    ],
)
def test_malformed_cases_fail_closed(case_payload: dict[str, object], reason_code: str) -> None:
    outcome = run_opa_runner(case_payload, _ctx())
    assert outcome.observed_outcome == baselines.INDETERMINATE
    assert reason_code in outcome.detail
    assert outcome.counted_as_success is False


def test_non_mapping_case_raises_wiring_error() -> None:
    with pytest.raises(SacmatOpaRunnerError) as err:
        run_opa_runner("not-a-case", _ctx())  # type: ignore[arg-type]
    assert err.value.reason_code == opa_runner.RC_CASE_NOT_AN_OBJECT


def test_non_sacmat_context_raises_wiring_error() -> None:
    with pytest.raises(SacmatOpaRunnerError) as err:
        run_opa_runner(_valid_grant_case(), "not-a-ctx")  # type: ignore[arg-type]
    assert err.value.reason_code == opa_runner.RC_CONTEXT_MALFORMED


# ---------------------------------------------------------------------------
# Port label separation: the port is never reported as a real OPA run.
# ---------------------------------------------------------------------------


def test_port_label_is_distinct_from_binary_backend() -> None:
    assert XACML_PORT_BACKEND.startswith("xacml-port")
    assert "opa-binary" not in XACML_PORT_BACKEND
    assert "port of the XACML-like engine model" in XACML_PORT_LABEL
    assert "NOT the upstream OPA binary" in XACML_PORT_LABEL


def test_version_bump_events_do_not_break_compilation() -> None:
    case = {
        "case_id": "SACMAT-X05-VERSION-BUMP",
        "history": [
            event(EVENT_GRANT, 100, "patient-a", "patient-a", PURPOSE_SELF_CARE, expiry=9000),
            event(EVENT_POLICY_VERSION_BUMP, 2000, "system", "system", "*"),
        ],
        "request": request("patient-a", PURPOSE_SELF_CARE, 500),
    }
    history = baselines._validate_case(case)  # type: ignore[arg-type]
    assert isinstance(history, baselines.PolicyHistory)
    module = compile_rego_module(history)
    assert f"package {REGO_PACKAGE}" in module
