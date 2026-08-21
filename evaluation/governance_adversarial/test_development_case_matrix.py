"""Contract tests for the development case-matrix executor."""

from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.governance_adversarial.development_case_matrix import (
    ARMS,
    DEVELOPMENT_MATRIX,
    _normalized_outcome,
    _response_sha256,
    _wait_for_health,
    run_matrix,
    run_single_case,
)


class FakeTransport:
    def __init__(self, *, arm: str) -> None:
        self.arm = arm
        self.requests: list[tuple[str, dict]] = []
        self.probe_plan: dict[str, tuple[int, dict]] = {}
        self.phase_probe_plan: dict[str, tuple[int, dict]] = {}

    def _default_probe_response(self, mutation: str, phase: str) -> tuple[int, dict]:
        if phase == "create":
            return 201, {
                "arm": self.arm,
                "phase": "create",
                "probe_id": "probe-created-1",
                "proposal_public_id": "proposal-1",
                "snapshot_public_id": "snap-1" if mutation in {"snapshot_expired"} else None,
                "snapshot_expires_at": "2026-08-17T00:00:00+00:00",
            }
        for mutations in DEVELOPMENT_MATRIX.values():
            for name in [mutations["mutation"]]:
                if name != mutation:
                    continue
                expected = mutations["expected"][self.arm]
                if expected == ("NOT_RUN",):
                    return 400, {"detail": {"code": "mutation_not_applicable_to_arm"}}
                outcome = expected[0]
                if outcome.startswith("transition_committed"):
                    return 201, {"outcome": outcome}
                return 409, {"detail": {"code": outcome}}
        return 201, {"outcome": "transition_committed"}

    def __call__(
        self,
        base_url: str,
        path: str,
        *,
        method: str = "GET",
        body: dict | None = None,
        token: str | None = None,
        profile: str | None = None,
    ) -> tuple[int, dict]:
        if path == "/health":
            return 200, {}
        if path == "/api/v1/govred-research/arm":
            return 200, {
                "arm": self.arm,
                "bind_snapshot": True,
                "revalidate_state": True,
                "revalidate_governance": True,
            }
        self.requests.append((path, body or {}))
        if path == "/api/v1/auth/register":
            return 200, {}
        if path == "/api/v1/auth/login":
            return 200, {"access_token": "synthetic-token"}
        if path == "/api/v1/auth/consent-status":
            return 200, {"required_version": "v1", "accepted": False}
        if path == "/api/v1/auth/consent":
            return 200, {"consent_version": "v1"}
        if path == "/api/v1/profiles":
            return 200, [{"id": "profile-1"}]
        if path == "/api/v1/govred-research/synthetic-commit-probe":
            mutation = (body or {}).get("mutation", "none")
            phase = (body or {}).get("phase", "full")
            if (mutation, phase) in self.phase_probe_plan:
                return self.phase_probe_plan[(mutation, phase)]
            return self.probe_plan.get(mutation, self._default_probe_response(mutation, phase))
        raise AssertionError(f"unexpected_path:{path}")


def test_normalized_outcome_maps_http_errors() -> None:
    assert _normalized_outcome(201, {"outcome": "transition_committed"}) == "transition_committed"
    assert (
        _normalized_outcome(409, {"detail": {"code": "stale_state_version"}})
        == "stale_state_version"
    )
    assert _normalized_outcome(500, {"detail": "boom"}) == "http_500"


def test_response_sha256_is_deterministic() -> None:
    payload = {"arm": "UNBOUND", "outcome": "transition_committed"}
    assert _response_sha256(payload) == _response_sha256(payload)
    assert len(_response_sha256(payload)) == 64


def test_health_wait_retries_connection_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def transport(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionResetError
        return 200, {}

    monkeypatch.setattr(
        "evaluation.governance_adversarial.development_case_matrix.time.sleep",
        lambda _seconds: None,
    )

    assert _wait_for_health("http://127.0.0.1:1", transport, attempts=2)
    assert calls == 2


def test_run_case_marks_not_applicable_mutation_not_run() -> None:
    outcome = run_single_case(
        base_url="http://127.0.0.1:1",
        arm="UNBOUND",
        case_id="F06_SNAPSHOT_DIGEST_INVALID",
        mutation="snapshot_digest_invalid",
        sentinel_id="dev-test-1",
        expected=("NOT_RUN",),
        transport=FakeTransport(arm="UNBOUND"),
    )
    assert outcome.pass_ is True
    assert outcome.row["status"] == "NOT_RUN"
    assert outcome.row["reason"] == "mutation_not_applicable_to_arm"


def test_run_case_records_pass_and_sanitized_observation() -> None:
    transport = FakeTransport(arm="GLHS_STRICT")
    transport.probe_plan["consent_revoke"] = (
        409,
        {"detail": {"code": "assertion_consent_mismatch"}},
    )
    outcome = run_single_case(
        base_url="http://127.0.0.1:1",
        arm="GLHS_STRICT",
        case_id="F01_CONSENT_REVOKE",
        mutation="consent_revoke",
        sentinel_id="dev-test-2",
        expected=("assertion_consent_mismatch",),
        transport=transport,
    )
    assert outcome.pass_ is True
    assert outcome.row["http_status"] == 409
    assert outcome.row["outcome"] == "assertion_consent_mismatch"
    assert outcome.row["raw_response_persisted"] is False
    assert len(outcome.row["response_sha256"]) == 64
    assert isinstance(outcome.row["latency_ms"], int)


def test_run_case_records_mismatch() -> None:
    transport = FakeTransport(arm="GLHS_STRICT")
    transport.probe_plan["consent_revoke"] = (201, {"outcome": "transition_committed"})
    outcome = run_single_case(
        base_url="http://127.0.0.1:1",
        arm="GLHS_STRICT",
        case_id="F01_CONSENT_REVOKE",
        mutation="consent_revoke",
        sentinel_id="dev-test-3",
        expected=("assertion_consent_mismatch",),
        transport=transport,
    )
    assert outcome.pass_ is False
    assert outcome.row["status"] == "OUTCOME_MISMATCH"


def test_run_matrix_verifies_arm_report_and_writes_all_cases() -> None:
    transport = FakeTransport(arm="STATE_VERSION_ONLY")
    matrix = run_matrix(
        base_url="http://127.0.0.1:1",
        arm="STATE_VERSION_ONLY",
        run_id="dev-run-1",
        transport=transport,
    )
    assert matrix["status"] == "development_matrix_not_headline"
    assert matrix["headline_claims_permitted"] is False
    assert matrix["arm"] == "STATE_VERSION_ONLY"
    assert matrix["mismatch_count"] == 0
    assert matrix["case_count"] == len(DEVELOPMENT_MATRIX)
    not_run = [row for row in matrix["cases"] if row["status"] == "NOT_RUN"]
    reasons = {row["reason"] for row in not_run}
    assert reasons == {"mutation_not_applicable_to_arm", "policy_restart_schedule_required"}


def test_run_matrix_policy_restart_command_marks_executed() -> None:
    transport = FakeTransport(arm="GLHS_STRICT")
    matrix = run_matrix(
        base_url="http://127.0.0.1:1",
        arm="GLHS_STRICT",
        run_id="dev-run-2",
        transport=transport,
        policy_restart_command="true",
    )
    policy_case = next(
        row for row in matrix["cases"] if row["case_id"] == "F02_POLICY_VERSION_CHANGE"
    )
    assert policy_case["status"] == "EXECUTED"
    assert policy_case["outcome"] == "assertion_policy_mismatch"
    assert matrix["mismatch_count"] == 0


def test_run_matrix_records_explicit_source_attestation() -> None:
    matrix = run_matrix(
        base_url="http://127.0.0.1:1",
        arm="UNBOUND",
        run_id="dev-run-source",
        transport=FakeTransport(arm="UNBOUND"),
        source_revision="a" * 40,
        source_tree_clean=True,
    )

    assert matrix["source_revision"] == "a" * 40
    assert matrix["git_dirty"] is False


def test_run_matrix_rejects_arm_mismatch() -> None:
    transport = FakeTransport(arm="UNBOUND")
    with pytest.raises(RuntimeError, match="govred_arm_mismatch"):
        run_matrix(
            base_url="http://127.0.0.1:1",
            arm="GLHS_STRICT",
            run_id="dev-run-3",
            transport=transport,
        )


def test_matrix_covers_all_families_for_every_arm() -> None:
    for case_id, spec in DEVELOPMENT_MATRIX.items():
        assert set(spec["expected"]) == set(ARMS), f"{case_id}"
        assert spec["mutation"] in {
            "none",
            "consent_revoke",
            "state_advance",
            "policy_version_change",
            "subject_cross_replay",
            "snapshot_digest_invalid",
            "snapshot_expired",
            "actor_switch_replay",
            "concurrent_governance_writer",
        }
        assert spec["flow"] in {"single", "expiry", "policy_restart"}


def test_matrix_main_writes_json(tmp_path: Path) -> None:
    from evaluation.governance_adversarial.development_case_matrix import main

    with pytest.raises(SystemExit) as raised:
        main()
    assert raised.value.code != 0
