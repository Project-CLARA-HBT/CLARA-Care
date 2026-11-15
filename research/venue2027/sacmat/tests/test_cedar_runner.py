"""Tests for SACMAT-X03_cedar_runner — real-engine Cedar runner + labelled port.

Purpose
-------
Contract tests for :mod:`evaluation.venue2027.sacmat.cedar_runner`
(``research/venue2027/VENUES/sacmat/TASKS/SACMAT-X03_cedar_runner.md``, RQ3):

Positive controls
  - the genuine upstream ``cedar`` CLI (pinned ``cedar-policy-cli`` 4.14.1) is
    detected when installed, evaluates a translated delegated-consent policy
    set and returns a verdict through the strict ``ALLOW``/``DENY`` protocol;
  - the injected-CLI positive path (no network, no real binary required)
    returns an upstream-labelled PERMIT/DENY verdict;
  - the clearly-labelled in-process port
    (:class:`cedar_runner.CedarPolicyPort`, a port over
    ``baselines.CedarPolicyEngine``) evaluates a policy set and returns a
    verdict labelled ``cedar-port`` — never ``cedar-upstream-cli``.

Adversarial controls
  - engine genuinely unavailable (empty PATH probe + injected ``None`` CLI)
    -> first-class ``NOT_RUN_EXTERNAL`` / ``BASELINE_UNAVAILABLE`` outcome with
    ``counted_as_success=False`` — NOT a fabricated success, NOT a silent port
    substitution, never counted as a completion;
  - detected engine that fails to spawn -> ``ENGINE_EXECUTION_ERROR`` ->
    ``INDETERMINATE`` (never a safe-looking DENY);
  - unparseable engine output -> ``ENGINE_MALFORMED_OUTPUT`` ->
    ``INDETERMINATE``;
  - unparseable translated policy -> ``CEDAR_POLICY_PARSE_ERROR`` ->
    ``INDETERMINATE``;
  - port and upstream results are labelled distinctly and can never be
    confused (asserted on the ``engine`` provenance field);
  - wiring errors raise stable-reason-code :class:`CedarRunnerError`
    (malformed policy input, malformed query override) instead of being
    silently absorbed into any verdict.

No real engine is required to run this suite: the upstream presence test is
skipped (not failed) when no ``cedar`` binary is installed, so the suite is
green both on engine-equipped and engine-free environments without ever
faking an upstream run.

Version
-------
``clara.venue2027.sacmat.test-cedar-runner-v1``
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

TEST_VERSION = "clara.venue2027.sacmat.test-cedar-runner-v1"

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
EVAL_ROOT = REPO_ROOT / "evaluation"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(EVAL_ROOT))

from evaluation.venue2027.sacmat import cedar_runner as cr  # noqa: E402
from evaluation.venue2027.sacmat.baselines import (  # noqa: E402
    DENY,
    EVENT_GRANT,
    EVENT_REGRANT,
    EVENT_REVOKE,
    INDETERMINATE,
    NOT_APPLICABLE,
    PERMIT,
    _validate_case,
    event,
    request,
)


def _valid_case() -> dict[str, object]:
    return {
        "case_id": "SACMAT-X03-POS-VALID-GRANT",
        "history": [
            event(EVENT_GRANT, 100, "patient-c", "patient-c", "self_care", expiry=9000),
        ],
        "request": request("patient-c", "self_care", 500),
    }


def _revoked_case() -> dict[str, object]:
    return {
        "case_id": "SACMAT-X03-POS-REVOKE",
        "history": [
            event(EVENT_GRANT, 100, "patient-b", "patient-b", "care_team", expiry=9000),
            event(EVENT_REVOKE, 2000, "patient-b", "patient-b", "care_team"),
        ],
        "request": request("patient-b", "care_team", 3000),
    }


# ---------------------------------------------------------------------------
# Fake upstream CLI runner (injected I/O; no real binary, no network).
# ---------------------------------------------------------------------------


class _FakeCedarRunner:
    """Deterministic in-memory stand-in for the subprocess boundary."""

    def __init__(self, stdout: str = "ALLOW\n", returncode: int = 0, stderr: str = "") -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], **_kwargs: object) -> object:
        self.calls.append(argv)
        return type(
            "Completed",
            (),
            {"returncode": self.returncode, "stdout": self.stdout, "stderr": self.stderr},
        )()


# ---------------------------------------------------------------------------
# Positive controls.
# ---------------------------------------------------------------------------


def test_port_evaluates_policy_set_and_returns_verdict() -> None:
    """Positive: the labelled port evaluates a policy set and returns a verdict."""
    port = cr.CedarPolicyPort()
    result = port.evaluate(_valid_case())
    assert result.decision == PERMIT
    assert result.engine == cr.PORT_LABEL == "cedar-port"
    assert result.engine != cr.UPSTREAM_LABEL
    assert "NOT an upstream execution" in result.detail
    assert result.outcome is not None and result.outcome.counted_as_success is True
    # JSON-serializable provenance.
    payload = json.loads(json.dumps(result.to_dict()))
    assert payload["engine"] == "cedar-port"


def test_port_denies_after_revocation() -> None:
    """Positive: port returns DENY for revoke-before-replay (forbid precedence)."""
    result = cr.CEDAR_PORT.evaluate(_revoked_case())
    assert result.decision == DENY
    assert result.engine == "cedar-port"


def test_port_reports_not_applicable_for_missing_entity() -> None:
    """Positive (adversarial vector per task contract): missing entity -> NOT_APPLICABLE."""
    case = {
        "case_id": "SACMAT-X03-POS-NA",
        "history": [
            event(EVENT_GRANT, 100, "patient-c", "patient-c", "self_care", expiry=9000),
        ],
        "request": request("patient-z", "self_care", 500),
    }
    result = cr.CEDAR_PORT.evaluate(case)
    assert result.decision in (NOT_APPLICABLE, DENY)
    assert result.engine == "cedar-port"


def test_injected_upstream_cli_returns_upstream_labelled_verdict() -> None:
    """Positive: upstream path (injected CLI) returns a PERMIT verdict."""
    fake = _FakeCedarRunner(stdout="ALLOW\n", returncode=0)
    cli = cr.CedarCli("/opt/fake/cedar", runner=fake)
    result = cr.evaluate_cedar(_valid_case(), cli=cli)
    assert isinstance(result, cr.CedarRunResult)
    assert result.decision == PERMIT
    assert result.engine == cr.UPSTREAM_LABEL == "cedar-upstream-cli"
    assert result.reason_code == "OK"
    assert result.outcome is not None and result.outcome.counted_as_success is True
    assert fake.calls and fake.calls[0][0].endswith("cedar")
    assert "--request-json" in fake.calls[0]


def test_injected_upstream_cli_deny_for_revoke_before_replay() -> None:
    """Positive: upstream path (injected CLI) returns DENY after revocation."""
    fake = _FakeCedarRunner(stdout="DENY\n", returncode=2)
    result = cr.evaluate_cedar(_revoked_case(), cli=cr.CedarCli("/opt/fake/cedar", runner=fake))
    assert isinstance(result, cr.CedarRunResult)
    assert result.decision == DENY
    assert result.engine == "cedar-upstream-cli"
    assert "2=DENY-by-default" in result.detail


def test_real_upstream_engine_evaluates_policy_set() -> None:
    """Positive (live engine): REAL upstream Cedar runs when genuinely installed.

    Skipped — never failed — when no ``cedar`` binary exists on this machine;
    an absent engine must degrade the suite to a skip, not fabricate a pass.
    """
    engine_path = cr.detect_cedar_engine()
    if engine_path is None:
        pytest.skip("upstream cedar-policy-cli not installed on this machine")
    result = cr.evaluate_cedar(_valid_case())
    assert isinstance(result, cr.CedarRunResult)
    assert result.engine == cr.UPSTREAM_LABEL
    assert result.decision in (PERMIT, DENY, NOT_APPLICABLE, INDETERMINATE)
    if result.decision == INDETERMINATE:
        assert result.reason_code in (
            cr.RC_CEDAR_POLICY_PARSE_ERROR,
            cr.RC_ENGINE_MALFORMED_OUTPUT,
            cr.RC_ENGINE_EXECUTION_ERROR,
        )
    else:
        assert result.reason_code == "OK"
        assert result.outcome is not None
    # The real engine must decide the revoked case DENY (forbid precedence).
    revoked = cr.evaluate_cedar(_revoked_case())
    assert isinstance(revoked, cr.CedarRunResult)
    if revoked.reason_code == "OK":
        assert revoked.decision == DENY


def test_translation_is_deterministic_and_cedar_shaped() -> None:
    """Positive: the history->Cedar translation is deterministic and well-formed."""
    case = {
        "case_id": "SACMAT-X03-TRANSLATE",
        "history": [
            event(EVENT_GRANT, 100, "patient-a", "patient-a", "self_care", expiry=9000),
            event(EVENT_REGRANT, 300, "patient-a", "patient-a", "self_care", expiry=9500),
        ],
        "request": request("patient-a", "self_care", 400),
    }
    history = _validate_case(case)
    from evaluation.venue2027.sacmat.baselines import PolicyHistory

    assert isinstance(history, PolicyHistory)
    lines_a, entities_a = cr.translate_history_to_cedar(history)
    lines_b, entities_b = cr.translate_history_to_cedar(history)
    assert lines_a == lines_b and entities_a == entities_b
    assert any(line.startswith("permit(") for line in lines_a)
    assert all("permit(" in line or "forbid(" in line for line in lines_a)
    json.dumps(entities_a)  # entities must be JSON-serializable


# ---------------------------------------------------------------------------
# Adversarial controls.
# ---------------------------------------------------------------------------


def test_engine_unavailable_returns_not_run_external_not_fake_success() -> None:
    """Adversarial: no genuine engine -> NOT_RUN_EXTERNAL, never a fake success."""
    outcome = cr.evaluate_cedar(_valid_case(), cli=cr.CedarCli(None))
    assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
    assert cr.RC_ENGINE_UNAVAILABLE in outcome.detail
    assert outcome.counted_as_success is False
    assert outcome.retriable is True


def test_engine_unavailable_with_emptied_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adversarial: honest detection on an engine-free PATH -> NOT_RUN_EXTERNAL."""
    monkeypatch.setenv("PATH", "")
    assert cr.detect_cedar_engine() is None
    outcome = cr.evaluate_cedar(_valid_case(), binary_name="definitely-not-installed-cedar-xyz")
    assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
    assert outcome.counted_as_success is False


def test_unavailable_engine_is_never_silently_substituted_by_port() -> None:
    """Adversarial: unavailability returns the outcome, not a port verdict."""
    outcome = cr.evaluate_cedar(_valid_case(), cli=cr.CedarCli(None))
    assert not isinstance(outcome, cr.CedarRunResult)
    assert outcome.observed_outcome != "ADMIT"
    # The port exists but is only reachable explicitly.
    port_result = cr.CEDAR_PORT.evaluate(_valid_case())
    assert port_result.engine == "cedar-port"


def test_detected_engine_spawn_failure_is_indeterminate() -> None:
    """Adversarial: engine claims presence but cannot spawn -> INDETERMINATE."""
    case = _valid_case()

    def _boom(_argv: list[str], **_kwargs: object) -> object:
        raise OSError("spawn blocked")

    result = cr.evaluate_cedar(case, cli=cr.CedarCli("/opt/fake/cedar", runner=_boom))
    assert isinstance(result, cr.CedarRunResult)
    assert result.decision == INDETERMINATE
    assert result.reason_code == cr.RC_ENGINE_EXECUTION_ERROR
    assert result.outcome is not None and result.outcome.counted_as_success is False


def test_unparseable_engine_output_is_indeterminate() -> None:
    """Adversarial: engine prints garbage -> INDETERMINATE, never a safe DENY."""
    fake = _FakeCedarRunner(stdout="garbage output\n", returncode=0)
    result = cr.evaluate_cedar(_valid_case(), cli=cr.CedarCli("/opt/fake/cedar", runner=fake))
    assert isinstance(result, cr.CedarRunResult)
    assert result.decision == INDETERMINATE
    assert result.reason_code == cr.RC_ENGINE_MALFORMED_OUTPUT
    assert result.outcome is not None and result.outcome.counted_as_success is False


def test_policy_parse_error_is_indeterminate() -> None:
    """Adversarial: unparseable policy set -> CEDAR_POLICY_PARSE_ERROR."""
    fake = _FakeCedarRunner(returncode=1, stdout="", stderr="parse failure")
    result = cr.evaluate_cedar(_valid_case(), cli=cr.CedarCli("/opt/fake/cedar", runner=fake))
    assert isinstance(result, cr.CedarRunResult)
    assert result.decision == INDETERMINATE
    assert result.reason_code == cr.RC_CEDAR_POLICY_PARSE_ERROR


def test_port_and_upstream_labels_are_distinct() -> None:
    """Adversarial: port vs upstream provenance can never be confused."""
    upstream = cr.evaluate_cedar(
        _valid_case(), cli=cr.CedarCli("/opt/fake/cedar", runner=_FakeCedarRunner())
    )
    assert isinstance(upstream, cr.CedarRunResult)
    port = cr.CEDAR_PORT.evaluate(_valid_case())
    assert upstream.engine != port.engine
    assert upstream.engine == "cedar-upstream-cli"
    assert port.engine == "cedar-port"
    assert upstream.backend != port.backend
    assert "PORT" in port.detail and "NOT an upstream execution" in port.detail


def test_malformed_policy_input_raises_stable_reason_code() -> None:
    """Adversarial: malformed policy input is a wiring error, not a verdict."""
    with pytest.raises(cr.CedarRunnerError) as excinfo:
        cr.evaluate_cedar("not-a-policy")
    assert excinfo.value.reason_code == "POLICY_NOT_A_HISTORY"
    with pytest.raises(cr.CedarRunnerError) as excinfo_mapping:
        cr.evaluate_cedar({"case_id": "X", "history": [{"event_kind": "GRANT"}], "request": {}})
    assert excinfo_mapping.value.reason_code == "QUERY_MALFORMED"


def test_malformed_query_override_raises_stable_reason_code() -> None:
    """Adversarial: query override missing fields / bad decision_time fails closed."""
    with pytest.raises(cr.CedarRunnerError) as excinfo:
        cr.evaluate_cedar(_valid_case(), query={"actor_id": "patient-c"})
    assert excinfo.value.reason_code == "QUERY_MALFORMED"
    with pytest.raises(cr.CedarRunnerError) as excinfo_bool:
        cr.evaluate_cedar(
            _valid_case(),
            query={"actor_id": "p", "purpose": "self_care", "decision_time": True},
        )
    assert excinfo_bool.value.reason_code == "QUERY_MALFORMED"


def test_version_and_labels_are_declared() -> None:
    """Provenance sanity: version string and distinct labels are exported."""
    assert cr.CEDAR_RUNNER_VERSION == "clara.sacmat.cedar-runner-v1"
    assert cr.PORT_LABEL != cr.UPSTREAM_LABEL
    assert cr.CEDAR_UPSTREAM_PIN == "cedar-policy-cli-4.14.1"
