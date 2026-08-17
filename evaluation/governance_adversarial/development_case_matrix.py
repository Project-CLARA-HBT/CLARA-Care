"""Operator-driven development case-matrix executor for isolated RIVF arms.

Runs the prespecified development mutation families against one attested
isolated research deployment over the real HTTP/API path and records only
sanitized per-case observations.  It is explicitly NOT a headline frozen
benchmark: there is no frozen statistics plan, no independent non-equivalence
review, and no sealed headline run behind this module.

Three flows are supported:

- ``single``: one full-phase probe call per case.
- ``expiry``: create a short-lived snapshot proposal, sleep past its expiry,
  then commit it (real time passage between disclosure and commit).
- ``policy_restart``: create a proposal, run an operator-supplied command that
  restarts the deployment with the research-gated policy override, then commit
  the same proposal (a deployment-level policy update between phases).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evaluation.governance_adversarial.development_smoke import _request

PROBE_PATH = "/api/v1/govred-research/synthetic-commit-probe"
ARM_PATH = "/api/v1/govred-research/arm"

ARMS = (
    "UNBOUND",
    "STATE_VERSION_ONLY",
    "SNAPSHOT_BOUND_STATE_ONLY",
    "GLHS_STRICT",
)

_EXPIRY_SNAPSHOT_SECONDS = 2
_EXPIRY_SLEEP_SECONDS = 4

# case_id -> {mutation, flow, expected per arm}.  A committed concurrent
# schedule is reported as ``indeterminate_ordering_transition_committed``
# whenever the governance writer landed; a clean commit with no writer is the
# only non-indeterminate committed outcome under that family.
DEVELOPMENT_MATRIX: dict[str, dict[str, object]] = {
    "F00_BASELINE": {
        "mutation": "none",
        "flow": "single",
        "expected": {arm: ("transition_committed",) for arm in ARMS},
    },
    "F01_CONSENT_REVOKE": {
        "mutation": "consent_revoke",
        "flow": "single",
        "expected": {
            "UNBOUND": ("transition_committed",),
            "STATE_VERSION_ONLY": ("transition_committed",),
            "SNAPSHOT_BOUND_STATE_ONLY": ("transition_committed",),
            "GLHS_STRICT": ("assertion_consent_mismatch",),
        },
    },
    "F02_POLICY_VERSION_CHANGE": {
        "mutation": "policy_version_change",
        "flow": "policy_restart",
        "expected": {
            "UNBOUND": ("transition_committed",),
            "STATE_VERSION_ONLY": ("transition_committed",),
            "SNAPSHOT_BOUND_STATE_ONLY": ("transition_committed",),
            "GLHS_STRICT": ("assertion_policy_mismatch",),
        },
    },
    "F03_ACTOR_SWITCH_REPLAY": {
        "mutation": "actor_switch_replay",
        "flow": "single",
        "expected": {
            "UNBOUND": ("transition_committed",),
            "STATE_VERSION_ONLY": ("transition_committed",),
            "SNAPSHOT_BOUND_STATE_ONLY": ("transition_committed",),
            "GLHS_STRICT": ("proposal_snapshot_actor_mismatch",),
        },
    },
    "F04_SUBJECT_CROSS_REPLAY": {
        "mutation": "subject_cross_replay",
        "flow": "single",
        "expected": {arm: ("assertion_scope_forbidden",) for arm in ARMS},
    },
    "F05_STALE_STATE": {
        "mutation": "state_advance",
        "flow": "single",
        "expected": {
            "UNBOUND": ("transition_committed",),
            "STATE_VERSION_ONLY": ("stale_state_version",),
            "SNAPSHOT_BOUND_STATE_ONLY": ("stale_state_version",),
            "GLHS_STRICT": ("stale_state_version",),
        },
    },
    "F06_SNAPSHOT_DIGEST_INVALID": {
        "mutation": "snapshot_digest_invalid",
        "flow": "single",
        "expected": {
            # The real PostgreSQL boundary rejects the tampering UPDATE with a
            # persistence-layer trigger before admission is reached.
            "UNBOUND": ("NOT_RUN",),
            "STATE_VERSION_ONLY": ("NOT_RUN",),
            "SNAPSHOT_BOUND_STATE_ONLY": ("ledger_tampering_rejected",),
            "GLHS_STRICT": ("ledger_tampering_rejected",),
        },
    },
    "F07_SNAPSHOT_EXPIRED": {
        "mutation": "snapshot_expired",
        "flow": "expiry",
        "expected": {
            "UNBOUND": ("NOT_RUN",),
            "STATE_VERSION_ONLY": ("NOT_RUN",),
            "SNAPSHOT_BOUND_STATE_ONLY": ("proposal_snapshot_expired",),
            "GLHS_STRICT": ("proposal_snapshot_expired",),
        },
    },
    "F08_CONCURRENT_GOVERNANCE_WRITER": {
        "mutation": "concurrent_governance_writer",
        "flow": "single",
        "expected": {
            "UNBOUND": ("transition_committed", "indeterminate_ordering_transition_committed"),
            "STATE_VERSION_ONLY": (
                "transition_committed",
                "indeterminate_ordering_transition_committed",
            ),
            "SNAPSHOT_BOUND_STATE_ONLY": (
                "transition_committed",
                "indeterminate_ordering_transition_committed",
            ),
            "GLHS_STRICT": (
                "assertion_consent_mismatch",
                "indeterminate_ordering_transition_committed",
            ),
        },
    },
}


@dataclass(frozen=True)
class CaseOutcome:
    pass_: bool
    row: dict[str, object]


def _identity_with_transport(
    base_url: str,
    label: str,
    transport: Callable[..., tuple[int, dict[str, Any]]],
) -> tuple[str, str]:
    suffix = secrets.token_hex(8)
    email = f"rivf-{label}-{suffix}@example.com"
    password = f"Rivf{suffix}9"
    status, _ = transport(base_url, "/api/v1/auth/register", method="POST", body={
        "email": email,
        "password": password,
        "full_name": f"Synthetic {label}",
        "accepted_terms": True,
        "accepted_privacy": True,
        "accepted_medical_consent": True,
    })
    if status != 200:
        raise RuntimeError(f"synthetic_registration_failed:{status}")
    status, login = transport(base_url, "/api/v1/auth/login", method="POST", body={"email": email, "password": password})
    token = login.get("access_token") if status == 200 else None
    if not isinstance(token, str):
        raise TypeError("synthetic_login_failed")
    status, consent_status = transport(base_url, "/api/v1/auth/consent-status", token=token)
    required_version = (
        consent_status.get("required_version")
        if status == 200 and isinstance(consent_status, dict)
        else None
    )
    if not isinstance(required_version, str):
        raise TypeError(f"synthetic_consent_status_failed:{status}")
    status, _ = transport(
        base_url,
        "/api/v1/auth/consent",
        method="POST",
        body={"consent_version": required_version, "accepted": True},
        token=token,
    )
    if status != 200:
        raise RuntimeError(f"synthetic_consent_accept_failed:{status}")
    status, profiles = transport(base_url, "/api/v1/profiles", token=token)
    if status != 200 or not isinstance(profiles, list) or len(profiles) != 1:
        raise RuntimeError("synthetic_profile_provisioning_failed")
    profile_id = profiles[0].get("id")
    if not isinstance(profile_id, str):
        raise TypeError("synthetic_profile_identifier_missing")
    return token, profile_id


def _normalized_outcome(http_status: int, response: dict[str, Any]) -> str:
    if http_status == 201 and response.get("outcome") == "transition_committed":
        return "transition_committed"
    if http_status == 201:
        return str(response.get("outcome") or "transition_committed")
    detail = response.get("detail")
    if isinstance(detail, dict) and isinstance(detail.get("code"), str):
        return detail["code"]
    if http_status == 409:
        return "invariant_rejected"
    if http_status == 400:
        return "bad_request"
    return f"http_{http_status}"


def _response_sha256(response: dict[str, Any]) -> str:
    raw = json.dumps(response, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def arm_report(
    base_url: str,
    transport: Callable[..., tuple[int, dict[str, Any]]],
) -> dict[str, Any]:
    token, _profile = _identity_with_transport(base_url, "arm-report", transport)
    status, response = transport(base_url, ARM_PATH, token=token)
    if status != 200 or not isinstance(response, dict) or "arm" not in response:
        raise RuntimeError(f"govred_arm_report_failed:{status}")
    return response


def _probe_request(
    *,
    base_url: str,
    transport: Callable[..., tuple[int, dict[str, Any]]],
    token: str,
    mutation: str,
    sentinel_id: str,
    phase: str = "full",
    probe_id: str | None = None,
    snapshot_expires_in_seconds: int = 300,
    expected: tuple[str, ...] | None = None,
) -> tuple[int, dict[str, Any]]:
    del expected  # retained for API symmetry with future oracles
    return transport(
        base_url,
        PROBE_PATH,
        method="POST",
        body={
            "mutation": mutation,
            "sentinel_id": sentinel_id,
            "phase": phase,
            "probe_id": probe_id,
            "snapshot_expires_in_seconds": snapshot_expires_in_seconds,
        },
        token=token,
    )


def _outcome_row(
    *,
    case_id: str,
    mutation: str,
    arm: str,
    sentinel_id: str,
    expected: tuple[str, ...],
    status: str,
    http_status: int | None,
    outcome: str | None,
    latency_ms: int,
    response_sha256: str | None,
    note: str | None = None,
) -> dict[str, object]:
    pass_ = status == "EXECUTED" and outcome in expected
    row: dict[str, object] = {
        "case_id": case_id,
        "mutation": mutation,
        "arm": arm,
        "status": status,
        "http_status": http_status,
        "outcome": outcome,
        "expected_outcomes": list(expected),
        "pass": pass_,
        "sentinel_id": sentinel_id,
        "latency_ms": latency_ms,
        "response_sha256": response_sha256,
        "raw_response_persisted": False,
    }
    if note:
        row["note"] = note
    return row


def run_single_case(
    *,
    base_url: str,
    arm: str,
    case_id: str,
    mutation: str,
    sentinel_id: str,
    expected: tuple[str, ...],
    transport: Callable[..., tuple[int, dict[str, Any]]],
) -> CaseOutcome:
    """Execute one development logical case over the real HTTP boundary."""
    if expected == ("NOT_RUN",):
        return CaseOutcome(
            True,
            {
                "case_id": case_id,
                "mutation": mutation,
                "arm": arm,
                "status": "NOT_RUN",
                "reason": "mutation_not_applicable_to_arm",
            },
        )
    token, _profile = _identity_with_transport(base_url, f"dev-{sentinel_id}", transport)
    started = time.monotonic()
    status, response = _probe_request(
        base_url=base_url,
        transport=transport,
        token=token,
        mutation=mutation,
        sentinel_id=sentinel_id,
    )
    latency_ms = int((time.monotonic() - started) * 1000)
    outcome = _normalized_outcome(status, response)
    return CaseOutcome(
        outcome in expected,
        _outcome_row(
            case_id=case_id,
            mutation=mutation,
            arm=arm,
            sentinel_id=sentinel_id,
            expected=expected,
            status="EXECUTED" if outcome in expected else "OUTCOME_MISMATCH",
            http_status=status,
            outcome=outcome,
            latency_ms=latency_ms,
            response_sha256=_response_sha256(response),
        ),
    )


def run_expiry_case(
    *,
    base_url: str,
    arm: str,
    case_id: str,
    mutation: str,
    sentinel_id: str,
    expected: tuple[str, ...],
    transport: Callable[..., tuple[int, dict[str, Any]]],
) -> CaseOutcome:
    """Create a short-lived snapshot proposal, wait past expiry, then commit."""
    if expected == ("NOT_RUN",):
        return CaseOutcome(
            True,
            {
                "case_id": case_id,
                "mutation": mutation,
                "arm": arm,
                "status": "NOT_RUN",
                "reason": "mutation_not_applicable_to_arm",
            },
        )
    token, _profile = _identity_with_transport(base_url, f"dev-{sentinel_id}", transport)
    started = time.monotonic()
    create_status, created = _probe_request(
        base_url=base_url,
        transport=transport,
        token=token,
        mutation=mutation,
        sentinel_id=sentinel_id,
        phase="create",
        snapshot_expires_in_seconds=_EXPIRY_SNAPSHOT_SECONDS,
    )
    if create_status != 201 or not isinstance(created.get("probe_id"), str):
        outcome = _normalized_outcome(create_status, created)
        return CaseOutcome(
            False,
            _outcome_row(
                case_id=case_id,
                mutation=mutation,
                arm=arm,
                sentinel_id=sentinel_id,
                expected=expected,
                status="OUTCOME_MISMATCH",
                http_status=create_status,
                outcome=outcome,
                latency_ms=int((time.monotonic() - started) * 1000),
                response_sha256=_response_sha256(created),
            ),
        )
    time.sleep(_EXPIRY_SLEEP_SECONDS)
    commit_status, committed = _probe_request(
        base_url=base_url,
        transport=transport,
        token=token,
        mutation=mutation,
        sentinel_id=sentinel_id,
        phase="commit",
        probe_id=created["probe_id"],
    )
    latency_ms = int((time.monotonic() - started) * 1000)
    outcome = _normalized_outcome(commit_status, committed)
    return CaseOutcome(
        outcome in expected,
        _outcome_row(
            case_id=case_id,
            mutation=mutation,
            arm=arm,
            sentinel_id=sentinel_id,
            expected=expected,
            status="EXECUTED" if outcome in expected else "OUTCOME_MISMATCH",
            http_status=commit_status,
            outcome=outcome,
            latency_ms=latency_ms,
            response_sha256=_response_sha256(committed),
            note="Two-phase expiry schedule: create(snapshot_expires_in=2s) -> sleep(4s) -> commit.",
        ),
    )


def run_policy_restart_case(
    *,
    base_url: str,
    arm: str,
    case_id: str,
    mutation: str,
    sentinel_id: str,
    expected: tuple[str, ...],
    transport: Callable[..., tuple[int, dict[str, Any]]],
    restart_command: str,
) -> CaseOutcome:
    """Create a proposal, restart the deployment under the next policy version,
    then commit the same proposal (deployment-level policy update)."""
    token, _profile = _identity_with_transport(base_url, f"dev-{sentinel_id}", transport)
    started = time.monotonic()
    create_status, created = _probe_request(
        base_url=base_url,
        transport=transport,
        token=token,
        mutation=mutation,
        sentinel_id=sentinel_id,
        phase="create",
    )
    if create_status != 201 or not isinstance(created.get("probe_id"), str):
        outcome = _normalized_outcome(create_status, created)
        return CaseOutcome(
            False,
            _outcome_row(
                case_id=case_id,
                mutation=mutation,
                arm=arm,
                sentinel_id=sentinel_id,
                expected=expected,
                status="OUTCOME_MISMATCH",
                http_status=create_status,
                outcome=outcome,
                latency_ms=int((time.monotonic() - started) * 1000),
                response_sha256=_response_sha256(created),
            ),
        )
    completed = subprocess.run(
        restart_command,
        shell=True,
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if completed.returncode != 0:
        return CaseOutcome(
            False,
            _outcome_row(
                case_id=case_id,
                mutation=mutation,
                arm=arm,
                sentinel_id=sentinel_id,
                expected=expected,
                status="INFRASTRUCTURE_ERROR",
                http_status=None,
                outcome=None,
                latency_ms=int((time.monotonic() - started) * 1000),
                response_sha256=None,
                note=f"Policy-restart command failed rc={completed.returncode}.",
            ),
        )
    commit_status, committed = _probe_request(
        base_url=base_url,
        transport=transport,
        token=token,
        mutation=mutation,
        sentinel_id=sentinel_id,
        phase="commit",
        probe_id=created["probe_id"],
    )
    latency_ms = int((time.monotonic() - started) * 1000)
    outcome = _normalized_outcome(commit_status, committed)
    return CaseOutcome(
        outcome in expected,
        _outcome_row(
            case_id=case_id,
            mutation=mutation,
            arm=arm,
            sentinel_id=sentinel_id,
            expected=expected,
            status="EXECUTED" if outcome in expected else "OUTCOME_MISMATCH",
            http_status=commit_status,
            outcome=outcome,
            latency_ms=latency_ms,
            response_sha256=_response_sha256(committed),
            note="Two-phase policy schedule: create -> operator restart under next policy -> commit.",
        ),
    )


def _source_revision() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except Exception:  # noqa: BLE001 - research tooling is best-effort here
        return "unknown"


def _git_dirty() -> bool:
    try:
        return bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
        )
    except Exception:  # noqa: BLE001
        return True


def run_matrix(
    *,
    base_url: str,
    arm: str,
    run_id: str,
    replicates: int = 1,
    transport: Callable[..., tuple[int, dict[str, Any]]] | None = None,
    policy_restart_command: str | None = None,
) -> dict[str, object]:
    if arm not in ARMS:
        raise ValueError("govred_development_arm_invalid")
    if transport is None:
        transport = _request
    report = arm_report(base_url, transport)
    if report["arm"] != arm:
        raise RuntimeError(
            f"govred_arm_mismatch:expected={arm},reported={report['arm']}"
        )
    rows: list[dict[str, object]] = []
    failed: list[str] = []
    for case_id, spec in DEVELOPMENT_MATRIX.items():
        mutation = str(spec["mutation"])
        flow = str(spec["flow"])
        expected = tuple(spec["expected"][arm])  # type: ignore[index]
        for replicate in range(1, replicates + 1):
            sentinel = f"dev{run_id.split('-')[-1]}{case_id[1:3]}{replicate}"
            if flow == "single":
                outcome = run_single_case(
                    base_url=base_url,
                    arm=arm,
                    case_id=case_id,
                    mutation=mutation,
                    sentinel_id=sentinel,
                    expected=expected,
                    transport=transport,
                )
            elif flow == "expiry":
                outcome = run_expiry_case(
                    base_url=base_url,
                    arm=arm,
                    case_id=case_id,
                    mutation=mutation,
                    sentinel_id=sentinel,
                    expected=expected,
                    transport=transport,
                )
            elif flow == "policy_restart":
                if not policy_restart_command:
                    outcome = CaseOutcome(
                        True,
                        {
                            "case_id": case_id,
                            "mutation": mutation,
                            "arm": arm,
                            "status": "NOT_RUN",
                            "reason": "policy_restart_schedule_required",
                        },
                    )
                else:
                    outcome = run_policy_restart_case(
                        base_url=base_url,
                        arm=arm,
                        case_id=case_id,
                        mutation=mutation,
                        sentinel_id=sentinel,
                        expected=expected,
                        transport=transport,
                        restart_command=policy_restart_command,
                    )
            else:
                raise ValueError(f"govred_unknown_flow:{flow}")
            rows.append(outcome.row)
            if not outcome.pass_:
                failed.append(f"{case_id}#{replicate}")
    return {
        "schema_version": "govred-development-case-matrix-v1",
        "status": "development_matrix_not_headline",
        "run_id": run_id,
        "arm": arm,
        "arm_report": report,
        "base_url_host": base_url.split("//")[-1].split("/")[0],
        "source_revision": _source_revision(),
        "git_dirty": _git_dirty(),
        "started_at_utc": datetime.now(UTC).isoformat(),
        "replicates": replicates,
        "case_count": len(rows),
        "not_run_count": sum(1 for row in rows if row.get("status") == "NOT_RUN"),
        "mismatch_count": len(failed),
        "mismatches": failed,
        "cases": rows,
        "headline_claims_permitted": False,
        "note": "Development case matrix only; no frozen manifest, statistics plan, or headline outcome.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--arm", choices=ARMS, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--replicates", type=int, default=1)
    parser.add_argument("--policy-restart-command")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_matrix(
        base_url=args.base_url,
        arm=args.arm,
        run_id=args.run_id,
        replicates=args.replicates,
        policy_restart_command=args.policy_restart_command,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if result["mismatch_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
