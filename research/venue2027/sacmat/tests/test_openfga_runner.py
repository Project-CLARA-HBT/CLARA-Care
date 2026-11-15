"""Tests for SACMAT-X04_openfga_runner — OpenFGA real-engine adapter.

Positive controls:
- The task-signature entry point ``evaluate_openfga(model, tuples, query)``
  evaluates translated delegation tuples on a REAL OpenFGA server when one
  is reachable: a written delegate tuple PERMITs through the engine's
  relation walk (record -> userset grantee -> user), an unrelated user
  does not (skipped, not failed, when no server is reachable).
- Server discovery honours the environment variables first and only
  reports endpoints answering ``/healthz`` with HTTP 200.
- The pinned model, consistency mode and pinned upstream revision are
  recorded in every real-run evidence block.

Adversarial controls:
- With NO reachable server the harness adapter returns
  ``NOT_RUN_EXTERNAL`` / ``BASELINE_UNAVAILABLE`` — never a fake success,
  never counted as a completion — while still labelling the port engine
  distinctly (``zanzibar-inprocess-port``) in the detail.
- ``simulate_unavailable_upstream`` forces the same transparent refusal.
- The port path is labelled ``zanzibar-inprocess-port`` and the real path
  ``openfga-http``: the two engine labels are distinct constants, asserted
  to never conflate a port with the pinned binary.
- A mid-run connection failure yields INDETERMINATE with a stable reason
  code (never a silent safe rejection, never a port fallback masquerading
  as a run).
- Malformed input fails closed INDETERMINATE with stable reason codes.
- Unknown engine labels, malformed contexts and non-mapping cases are
  wiring errors.

No live provider, no hidden clock/randomness in the port path; the real-
engine path talks only to the discovered OpenFGA HTTP endpoint.
"""

from __future__ import annotations

import json

import pytest

from evaluation.venue2027._shared.harness import Outcome
from evaluation.venue2027.sacmat import baselines as bl
from evaluation.venue2027.sacmat import openfga_adapter as ofa

REAL_SERVER = ofa.discover_openfga()
REAL_ENGINE_AVAILABLE = REAL_SERVER is not None

requires_real_engine = pytest.mark.skipif(
    not REAL_ENGINE_AVAILABLE, reason="no reachable OpenFGA server"
)


def case_grant(
    case_id: str = "SACMAT-X04-CASE-1",
    actor: str = "patient-a",
    purpose: str = bl.PURPOSE_SELF_CARE,
    delegate: str | None = None,
    expiry: int | None = 9000,
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "history": [
            bl.event(bl.EVENT_GRANT, 100, actor, delegate or actor, purpose, expiry=expiry)
        ],
        "request": bl.request(actor, purpose, 500),
    }


def case_regrant(
    case_id: str = "SACMAT-X04-CASE-REGRANT",
    actor: str = "patient-b",
) -> dict[str, object]:
    return {
        "case_id": case_id,
        "history": [
            bl.event(bl.EVENT_GRANT, 100, actor, actor, bl.PURPOSE_CARE_TEAM, expiry=2000),
            bl.event(bl.EVENT_REVOKE, 1500, actor, actor, bl.PURPOSE_CARE_TEAM),
            bl.event(bl.EVENT_REGRANT, 1600, actor, actor, bl.PURPOSE_CARE_TEAM, expiry=9000),
        ],
        "request": bl.request(actor, bl.PURPOSE_CARE_TEAM, 2000),
    }


def ctx(**overrides: object) -> bl.SacmatContext:
    return bl.SacmatContext(arm_id="SACMAT-X04", seed=7, **overrides)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Positive controls — engine labels, discovery, pinned constants.
# ---------------------------------------------------------------------------


def test_engine_labels_are_distinct_constants() -> None:
    assert ofa.ENGINE_REAL == "openfga-http"
    assert ofa.ENGINE_PORT == "zanzibar-inprocess-port"
    assert ofa.ENGINE_REAL != ofa.ENGINE_PORT


def test_pinned_upstream_recorded() -> None:
    assert ofa.OPENFGA_PINNED_IMAGE == "openfga/openfga:v1.22.1"
    assert len(ofa.OPENFGA_PINNED_REVISION) == 40
    assert ofa.OPENFGA_CONSISTENCY_MODE == "HIGHER_CONSISTENCY"


def test_discovery_env_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    # Env URL is probed first: a dead env URL is returned as the only
    # candidate's failure -> discovery returns None even when the default
    # well-known endpoint would answer (env precedence over defaults).
    monkeypatch.setenv("OPENFGA_API_URL", "http://127.0.0.1:59999")
    monkeypatch.delenv("OPENFGA_API_TOKEN", raising=False)
    assert ofa.discover_openfga(timeout=0.2) is None

    # With the env pointing at the live server, discovery returns exactly it.
    if REAL_SERVER is not None:
        monkeypatch.setenv("OPENFGA_API_URL", REAL_SERVER)
        assert ofa.discover_openfga() == REAL_SERVER


def test_discovery_unreachable_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENFGA_API_URL", "http://127.0.0.1:59999")
    monkeypatch.delenv("OPENFGA_API_TOKEN", raising=False)
    assert ofa.discover_openfga(timeout=0.2) is None


@requires_real_engine
def test_evaluate_openfga_signature_positive_and_negative() -> None:
    model = ofa.OpenFgaModel()
    scope = ofa._scope_id("patient-a", bl.PURPOSE_SELF_CARE)
    tuples = (
        ofa.OpenFgaTuple(
            user="user:patient-a", relation="delegate", object=f"consent_record:{scope}"
        ),
        ofa.OpenFgaTuple(
            user=f"consent_record:{scope}", relation="record", object=f"consent:{scope}"
        ),
        ofa.OpenFgaTuple(
            user=f"consent_record:{scope}#delegate",
            relation="delegate",
            object=f"consent:{scope}",
        ),
    )
    permit = ofa.evaluate_openfga(
        model,
        tuples,
        ofa.OpenFgaQuery("patient-a", bl.PURPOSE_SELF_CARE, scope, 500),
        base_url=REAL_SERVER,  # type: ignore[arg-type]
    )
    assert permit.decision == bl.PERMIT
    assert permit.engine_used == ofa.ENGINE_REAL
    assert permit.reason_code == "OK"
    deny = ofa.evaluate_openfga(
        model,
        tuples,
        ofa.OpenFgaQuery("intruder", bl.PURPOSE_SELF_CARE, scope, 500),
        base_url=REAL_SERVER,  # type: ignore[arg-type]
    )
    assert deny.decision == bl.NOT_APPLICABLE
    assert deny.engine_used == ofa.ENGINE_REAL


@requires_real_engine
def test_real_run_grant_then_revoke_then_regrant() -> None:
    outcome = ofa.run_case(case_regrant(), ctx())
    assert isinstance(outcome, Outcome)
    assert outcome.observed_outcome == "ADMIT"
    assert outcome.counted_as_success is True
    assert f"engine={ofa.ENGINE_REAL}" in outcome.detail
    assert '"last_action": "check"' in outcome.detail
    assert '"consistency": "HIGHER_CONSISTENCY"' in outcome.detail


@requires_real_engine
def test_real_run_revoked_delegate_rejects() -> None:
    case = {
        "case_id": "SACMAT-X04-CASE-REVOKED",
        "history": [
            bl.event(
                bl.EVENT_GRANT, 100, "patient-r", "patient-r", bl.PURPOSE_SELF_CARE, expiry=9000
            ),
            bl.event(bl.EVENT_REVOKE, 400, "patient-r", "patient-r", bl.PURPOSE_SELF_CARE),
        ],
        "request": bl.request("patient-r", bl.PURPOSE_SELF_CARE, 500),
    }
    outcome = ofa.run_case(case, ctx())
    assert outcome.observed_outcome == "REJECT"
    assert f"engine={ofa.ENGINE_REAL}" in outcome.detail


@requires_real_engine
def test_real_run_expired_delegation_not_applied() -> None:
    # Decision tick after expiry: the expire deletion removes the tuple.
    case = {
        "case_id": "SACMAT-X04-CASE-EXPIRED",
        "history": [
            bl.event(
                bl.EVENT_GRANT, 100, "patient-e", "patient-e", bl.PURPOSE_RESEARCH, expiry=300
            ),
            bl.event(bl.EVENT_EXPIRE, 400, "patient-e", "patient-e", bl.PURPOSE_RESEARCH),
        ],
        "request": bl.request("patient-e", bl.PURPOSE_RESEARCH, 500),
    }
    outcome = ofa.run_case(case, ctx())
    assert outcome.observed_outcome == "REJECT"


@requires_real_engine
def test_real_run_future_grant_invisible_at_decision_time() -> None:
    # The grant lands after the decision tick: replay must not apply it.
    case = {
        "case_id": "SACMAT-X04-CASE-FUTURE-GRANT",
        "history": [
            bl.event(
                bl.EVENT_GRANT, 1000, "patient-f", "patient-f", bl.PURPOSE_SELF_CARE, expiry=9000
            ),
        ],
        "request": bl.request("patient-f", bl.PURPOSE_SELF_CARE, 500),
    }
    outcome = ofa.run_case(case, ctx())
    assert outcome.observed_outcome == "REJECT"


# ---------------------------------------------------------------------------
# Adversarial controls — unavailable server, port labelling, fail-closed.
# ---------------------------------------------------------------------------


def test_unavailable_server_returns_not_run_external(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    # Point discovery at a dead port: no server reachable -> transparent refusal.
    monkeypatch.setenv("OPENFGA_API_URL", "http://127.0.0.1:59999")
    monkeypatch.delenv("OPENFGA_API_TOKEN", raising=False)
    outcome = ofa.run_case(case_grant(), ctx())
    assert isinstance(outcome, Outcome)
    assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
    assert outcome.counted_as_success is False
    assert outcome.retriable is True
    assert outcome.detail.startswith(f"{ofa.RC_BASELINE_UNAVAILABLE}|")
    # Port engine labelled distinctly inside the refusal detail.
    assert f"engine={ofa.ENGINE_PORT}" in outcome.detail
    assert ofa.ENGINE_REAL not in outcome.detail.split("port_evidence")[0].split("engine=")[1]


def test_simulate_unavailable_upstream_forces_port_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENFGA_API_URL", "http://127.0.0.1:59999")
    monkeypatch.delenv("OPENFGA_API_TOKEN", raising=False)
    outcome = ofa.run_case(case_grant(), ctx(simulate_unavailable_upstream=True))
    assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
    assert f"engine={ofa.ENGINE_PORT}" in outcome.detail


def test_port_evaluation_labelled_and_honest() -> None:
    history = bl._validate_case(case_grant())
    assert not isinstance(history, Outcome)
    query = ofa.OpenFgaQuery("patient-a", bl.PURPOSE_SELF_CARE, "pa_self_care", 500)
    decision = ofa.run_port_evaluation(history, query)
    assert decision.engine_used == ofa.ENGINE_PORT
    assert ofa.ENGINE_REAL not in json.dumps(decision.to_dict())
    assert decision.evidence["port_of"] == ofa.OPENFGA_PINNED_IMAGE
    # The port is a port of the pinned upstream's semantics, not the binary.
    assert "baselines.py:ZanzibarPolicyEngine" in str(decision.evidence["port_source"])


def test_connection_failure_is_indeterminate_not_fake_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Force discovery to find a URL that then refuses connections mid-run.
    monkeypatch.setenv("OPENFGA_API_URL", "http://127.0.0.1:59999")
    monkeypatch.delenv("OPENFGA_API_TOKEN", raising=False)
    # The URL answers nothing: discovery fails -> NOT_RUN_EXTERNAL (refusal),
    # proving an unreachable server is never a fake success.
    outcome = ofa.run_case(case_grant(), ctx())
    assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"

    # Server discovered but dies before the check: INDETERMINATE.
    monkeypatch.setattr(ofa, "discover_openfga", lambda *a, **k: "http://127.0.0.1:59999")
    outcome2 = ofa.run_case(case_grant(), ctx())
    assert outcome2.observed_outcome == "INDETERMINATE"
    assert ofa.RC_OPENFGA_CONNECTION_FAILED in outcome2.detail
    assert outcome2.counted_as_success is False


def test_engine_check_error_is_indeterminate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENFGA_API_URL", REAL_SERVER or "http://127.0.0.1:59999")
    monkeypatch.delenv("OPENFGA_API_TOKEN", raising=False)
    if REAL_SERVER is None:
        pytest.skip("no reachable OpenFGA server")
    # Model creation returns garbage -> stable reason code, INDETERMINATE.
    original = ofa._http_json

    def broken(method: str, url: str, payload: object, token: str, timeout: float) -> dict:
        if "/authorization-models" in url:
            return {"unexpected": "shape"}
        return original(method, url, payload, token, timeout)  # type: ignore[arg-type]

    monkeypatch.setattr(ofa, "_http_json", broken)
    outcome = ofa.run_case(case_grant(), ctx())
    assert outcome.observed_outcome == "INDETERMINATE"
    assert ofa.RC_OPENFGA_CHECK_ERROR in outcome.detail


def test_malformed_case_is_indeterminate_with_reason_code() -> None:
    bad = {"case_id": "X"}  # missing history + request
    outcome = ofa.run_case(bad, ctx())  # type: ignore[arg-type]
    assert outcome.observed_outcome == "INDETERMINATE"
    assert outcome.counted_as_success is False
    assert ofa.RC_HISTORY_MISSING in outcome.detail


def test_non_mapping_case_is_wiring_error() -> None:
    with pytest.raises(bl.SacmatBaselineError) as excinfo:
        ofa.run_case("not-a-mapping", ctx())  # type: ignore[arg-type]
    assert excinfo.value.reason_code == "CASE_NOT_AN_OBJECT"


def test_malformed_context_is_wiring_error() -> None:
    with pytest.raises(bl.SacmatBaselineError) as excinfo:
        ofa.run_case(case_grant(), "not-a-ctx")  # type: ignore[arg-type]
    assert excinfo.value.reason_code == ofa.RC_CONTEXT_MALFORMED


def test_http_error_maps_to_stable_reason_code(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force an HTTP 4xx from a stub server bound to a random port.
    import socket
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"SERVING"}')

        def do_POST(self) -> None:  # noqa: N802
            body = b'{"code":"validation_error","message":"boom"}'
            self.send_response(400)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            return

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = HTTPServer(("127.0.0.1", port), Handler)
    import threading

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(ofa.OpenFgaEngineError) as excinfo:
            ofa._http_json(
                "POST",
                f"http://127.0.0.1:{port}/stores",
                {"name": "x"},
                "",
                3.0,
            )
        assert excinfo.value.reason_code == ofa.RC_OPENFGA_CHECK_ERROR
        assert "HTTP 400" in excinfo.value.detail
    finally:
        server.shutdown()
        server.server_close()


def test_outcome_buckets_never_count_refusals_as_success() -> None:
    # The refusal and indeterminate paths are never counted successes.
    monkeypatch_env = {"OPENFGA_API_URL": ""}
    import os

    old = os.environ.get("OPENFGA_API_URL")
    os.environ["OPENFGA_API_URL"] = "http://127.0.0.1:59999"
    try:
        refusal = ofa.run_case(case_grant(), ctx())
        assert refusal.observed_outcome == "NOT_RUN_EXTERNAL"
        assert refusal.counted_as_success is False
    finally:
        if old is None:
            os.environ.pop("OPENFGA_API_URL", None)
        else:
            os.environ["OPENFGA_API_URL"] = old
    assert monkeypatch_env["OPENFGA_API_URL"] == ""  # silence unused-var lint
