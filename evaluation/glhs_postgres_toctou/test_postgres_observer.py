from __future__ import annotations

from evaluation.glhs_postgres_toctou.postgres_observer import _normalized


def _race_payload() -> dict[str, object]:
    return {
        "id": "TOCTOU-03",
        "run_status": "EXECUTED",
        "commit_outcome": "transition_committed",
        "forbidden_commit_observed": None,
        "ordering_classification": "indeterminate_ordering_transition_committed",
        "revoke_commit_ns": 5,
        "commit_start_ns": 1,
        "commit_complete_ns": 9,
        "ledger_observation": {
            "transition_item_count": 1,
            "reconstruction_status": "exact_snapshot_linkage",
        },
        "latency_ms": 2.3,
    }


def test_observer_uses_consistent_ordering_classification_key() -> None:
    serial = _normalized(
        {
            "id": "TOCTOU-01",
            "run_status": "EXECUTED",
            "commit_outcome": "assertion_consent_mismatch",
            "forbidden_commit_observed": False,
            "latency_ms": 1.2,
        }
    )
    race = _normalized(_race_payload())

    assert serial["ordering"] == {"classification": "ordered_serial_schedule"}
    assert race["ordering"]["classification"] == "indeterminate_ordering_transition_committed"
    assert set(race["ordering"]) == {
        "classification",
        "revoke_commit_ns",
        "commit_start_ns",
        "commit_complete_ns",
    }


def test_observer_marks_exact_reconstruction_complete_only_when_linked() -> None:
    complete = _normalized(_race_payload())
    assert complete["audit"]["observer_complete"] is True
    assert complete["audit"]["persisted_audit_row"] is True

    incomplete = _normalized(
        {
            **_race_payload(),
            "ledger_observation": {
                "transition_item_count": 0,
                "reconstruction_status": "linkage_incomplete",
            },
        }
    )
    assert incomplete["audit"]["observer_complete"] is False
    assert incomplete["audit"]["persisted_audit_row"] is False


def test_observer_marks_no_commit_expected_as_complete() -> None:
    observed = _normalized(
        {
            "id": "TOCTOU-04",
            "run_status": "EXECUTED",
            "commit_outcome": "proposal_snapshot_policy_mismatch",
            "forbidden_commit_observed": False,
            "latency_ms": 3.4,
        }
    )
    assert observed["audit"]["observer_complete"] is True
    assert observed["audit"]["exact_reconstruction"] == "no_commit_expected"