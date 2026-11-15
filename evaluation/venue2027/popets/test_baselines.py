"""Tests for POPETS-baselines (baseline fidelity adapters).

Positive controls (must pass):
- Each implemented baseline (coarse purge B1, always-recompute B2,
  purpose-bound keying design reference) runs end-to-end on a synthetic case
  and yields a determined ADMIT or REJECT pair outcome.
- Each implemented baseline is a real algorithm: per-dispatch records carry
  authorization decisions, cost counters (invalidation events, exposed bytes,
  key rotations) and distinguish revocation denial from source-missing denial.
- Determinism: the same case and ctx reproduce identical outcomes.
- parity_check(baseline_id) reproduces the official-style parity vector for
  every implemented baseline.

Adversarial controls (must be refused / honest, never fabricated):
- An unavailable baseline (ttl-only-cache, zanzibar-like-consistency-token-
  cache, zanzibar-openfga, muse-unlearning-comparator, unknown id) yields
  NOT_RUN_EXTERNAL with reason_code BASELINE_UNAVAILABLE - never a number.
- A constant-deny stub registered with a implemented name is refused:
  a stub cannot reproduce the implemented baselines' parity vectors, and the
  module refuses to route unimplemented ids into implemented code paths.
- A parity vector with a wrong expectation fails hard (PARITY_MISMATCH), and a
  missing fixture fails hard (PARITY_VECTOR_MISSING).
- Malformed workload input fails closed with EXECUTION_ERROR / stable reason
  code, never a silent safe rejection.
- Registry honesty: no entry claims a fidelity the module cannot deliver.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from evaluation.venue2027._shared.harness import Outcome, RunContext
from evaluation.venue2027.popets import baselines as bl


def _ctx(seed: int = 7) -> RunContext:
    return RunContext(
        campaign_id="camp-popets-baselines",
        case_id="case-1",
        arm_id="arm",
        seed=seed,
        source_commit="a" * 40,
        deadline_seconds=60.0,
    )


def _case(**overrides: object) -> dict[str, object]:
    case: dict[str, object] = {"case_id": "case-popets-1", "seed": 42}
    case.update(overrides)
    return case


IMPL_BASELINES = sorted(bl.IMPLEMENTED_BASELINES)
UNAVAIL_BASELINES = (
    "ttl-only-cache",
    "zanzibar-like-consistency-token-cache",
    "zanzibar-openfga",
    "muse-unlearning-comparator",
)


# ---------------------------------------------------------------------------
# Positive: each implemented baseline runs end-to-end on a synthetic case
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("baseline_id", IMPL_BASELINES)
def test_implemented_baseline_runs_end_to_end_determined(baseline_id: str) -> None:
    outcome = bl.run_baseline(baseline_id, _case(), _ctx())
    assert isinstance(outcome, Outcome)
    assert outcome.observed_outcome in ("ADMIT", "REJECT")
    assert outcome.counted_as_success is True
    detail = json.loads(outcome.detail)
    assert detail["baseline"] == baseline_id
    assert detail["dispatch_count"] >= 1
    assert detail["admitted"] + detail["rejected"] == detail["dispatch_count"]
    assert outcome.observed_outcome == ("ADMIT" if detail["admitted"] > 0 else "REJECT")


def test_coarse_purge_purges_all_purposes_and_grants_of_subject() -> None:
    workload = {
        "source_snapshot": {
            "vitals_1": "BP 120/80",
            "meds_1": "metformin",
            "admin_1": "tier B",
        },
        "revocations": [
            {"subject": "s1", "grant": "g-med", "purpose": "analytics", "at_seconds": 50}
        ],
        "dispatches": [
            {
                "dispatch_id": "pre",
                "subject": "s1",
                "grant": "g-med",
                "purpose": "clinical",
                "lineage": ["vitals_1"],
                "at_seconds": 10,
            },
            {
                "dispatch_id": "revoked",
                "subject": "s1",
                "grant": "g-med",
                "purpose": "analytics",
                "lineage": ["meds_1"],
                "at_seconds": 60,
            },
            {
                "dispatch_id": "other_grant_after_purge",
                "subject": "s1",
                "grant": "g-admin",
                "purpose": "clinical",
                "lineage": ["admin_1"],
                "at_seconds": 70,
            },
        ],
    }
    outcome = bl.run_baseline("coarse-cache-purge-on-revocation", _case(workload=workload), _ctx())
    detail = json.loads(outcome.detail)
    by_id = {r["dispatch_id"]: r for r in detail["dispatches"]}
    assert by_id["pre"]["outcome"] == "ADMIT"
    assert by_id["revoked"]["outcome"] == "REJECT"
    assert by_id["revoked"]["reason_code"] == "REVOKED_CONTEXT"
    # Unaffected grant on the same subject is still authorized (it never
    # depended on revoked coverage), but invalidation_events were paid.
    assert by_id["other_grant_after_purge"]["outcome"] == "ADMIT"
    assert detail["invalidation_events"] >= 1


def test_always_recompute_never_serves_cache_and_denies_revoked() -> None:
    workload = {
        "source_snapshot": {"vitals_1": "BP 120/80", "meds_1": "metformin"},
        "revocations": [
            {"subject": "s1", "grant": "g-med", "purpose": "analytics", "at_seconds": 50}
        ],
        "dispatches": [
            {
                "dispatch_id": "a",
                "subject": "s1",
                "grant": "g-med",
                "purpose": "clinical",
                "lineage": ["vitals_1"],
                "at_seconds": 10,
            },
            {
                "dispatch_id": "b",
                "subject": "s1",
                "grant": "g-med",
                "purpose": "clinical",
                "lineage": ["vitals_1"],
                "at_seconds": 20,
            },
            {
                "dispatch_id": "c",
                "subject": "s1",
                "grant": "g-med",
                "purpose": "analytics",
                "lineage": ["meds_1"],
                "at_seconds": 60,
            },
        ],
    }
    outcome = bl.run_baseline(
        "always-recompute-authorized-projection", _case(workload=workload), _ctx()
    )
    detail = json.loads(outcome.detail)
    by_id = {r["dispatch_id"]: r for r in detail["dispatches"]}
    assert by_id["a"]["outcome"] == "ADMIT"
    assert by_id["b"]["outcome"] == "ADMIT"
    assert all(r["cache_hit"] is False for r in detail["dispatches"])
    # One full recompute per dispatch (zero caching), the RQ3 cost marker.
    assert detail["invalidation_events"] == 3
    assert by_id["c"]["outcome"] == "REJECT"
    assert by_id["c"]["reason_code"] == "REVOKED_CONTEXT"


def test_purpose_keying_rotates_affected_purpose_only() -> None:
    workload = {
        "source_snapshot": {"vitals_1": "BP 120/80"},
        "revocations": [
            {"subject": "s1", "grant": "g-med", "purpose": "analytics", "at_seconds": 50}
        ],
        "dispatches": [
            {
                "dispatch_id": "same_purpose",
                "subject": "s1",
                "grant": "g-med",
                "purpose": "analytics",
                "lineage": ["vitals_1"],
                "at_seconds": 60,
            },
            {
                "dispatch_id": "other_purpose",
                "subject": "s1",
                "grant": "g-med",
                "purpose": "clinical",
                "lineage": ["vitals_1"],
                "at_seconds": 60,
            },
        ],
    }
    outcome = bl.run_baseline("purpose-bound-cache-keying", _case(workload=workload), _ctx())
    detail = json.loads(outcome.detail)
    by_id = {r["dispatch_id"]: r for r in detail["dispatches"]}
    assert by_id["same_purpose"]["cache_key_epoch"] == 1
    assert by_id["other_purpose"]["cache_key_epoch"] == 0
    assert detail["key_rotations"] == 1


def test_purpose_keying_exposes_transitive_gap_ablation_surface() -> None:
    """Keying without reverse edges must NOT cover transitively derived artifacts."""
    workload = {
        "source_snapshot": {"vitals_1": "BP 120/80"},
        "revocations": [
            {"subject": "s1", "grant": "g-med", "purpose": "analytics", "at_seconds": 50}
        ],
        "dispatches": [
            {
                "dispatch_id": "retry",
                "subject": "s1",
                "grant": "g-med",
                "purpose": "analytics",
                "lineage": ["retry_payload_1", "vitals_1"],
                "at_seconds": 60,
            }
        ],
    }
    outcome = bl.run_baseline("purpose-bound-cache-keying", _case(workload=workload), _ctx())
    detail = json.loads(outcome.detail)
    assert detail["transitive_gaps"] == 1


def test_baselines_are_real_algorithms_not_constant_deny() -> None:
    """The same workload yields BOTH admit and reject dispatches per baseline."""
    workload = {
        "source_snapshot": {"vitals_1": "BP 120/80", "admin_1": "tier B"},
        "revocations": [
            {"subject": "s1", "grant": "g-med", "purpose": "analytics", "at_seconds": 50}
        ],
        "dispatches": [
            {
                "dispatch_id": "ok",
                "subject": "s1",
                "grant": "g-admin",
                "purpose": "clinical",
                "lineage": ["admin_1"],
                "at_seconds": 10,
            },
            {
                "dispatch_id": "denied",
                "subject": "s1",
                "grant": "g-med",
                "purpose": "analytics",
                "lineage": ["vitals_1"],
                "at_seconds": 60,
            },
        ],
    }
    for baseline_id in IMPL_BASELINES:
        detail = json.loads(bl.run_baseline(baseline_id, _case(workload=workload), _ctx()).detail)
        outcomes = {r["outcome"] for r in detail["dispatches"]}
        assert outcomes == {"ADMIT", "REJECT"}, baseline_id


def test_determinism_same_case_and_ctx() -> None:
    for baseline_id in IMPL_BASELINES:
        first = bl.run_baseline(baseline_id, _case(), _ctx(seed=11))
        second = bl.run_baseline(baseline_id, _case(), _ctx(seed=11))
        assert first.to_dict() == second.to_dict()


def test_exposed_bytes_counted_for_admitted_dispatches() -> None:
    workload = {
        "source_snapshot": {"vitals_1": "BP 120/80"},
        "revocations": [],
        "dispatches": [
            {
                "dispatch_id": "d",
                "subject": "s1",
                "grant": "g-med",
                "purpose": "clinical",
                "lineage": ["vitals_1"],
                "at_seconds": 10,
            }
        ],
    }
    detail = json.loads(
        bl.run_baseline(
            "always-recompute-authorized-projection", _case(workload=workload), _ctx()
        ).detail
    )
    assert detail["exposed_bytes_total"] == len("BP 120/80")


# ---------------------------------------------------------------------------
# Parity: official-style vectors reproduce exactly for implemented baselines
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("baseline_id", IMPL_BASELINES)
def test_parity_check_implemented_reproduces_vector(baseline_id: str) -> None:
    assert bl.parity_check(baseline_id) is True


# ---------------------------------------------------------------------------
# Adversarial: unavailable baselines are honest (NOT_RUN_EXTERNAL), never fake
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("baseline_id", UNAVAIL_BASELINES)
def test_unavailable_baseline_returns_not_run_external(baseline_id: str) -> None:
    outcome = bl.run_baseline(baseline_id, _case(), _ctx())
    assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
    assert outcome.counted_as_success is False
    assert "BASELINE_UNAVAILABLE" in outcome.detail


def test_unknown_baseline_id_returns_not_run_external() -> None:
    outcome = bl.run_baseline("totally-unknown-arm", _case(), _ctx())
    assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
    assert "BASELINE_UNAVAILABLE" in outcome.detail


def test_empty_baseline_id_returns_not_run_external() -> None:
    outcome = bl.run_baseline("", _case(), _ctx())
    assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"


def test_unavailable_baseline_parity_is_none_not_fake_pass() -> None:
    for baseline_id in UNAVAIL_BASELINES:
        assert bl.parity_check(baseline_id) is None


def test_registry_fidelity_matches_implementation_honestly() -> None:
    for baseline_id, entry in bl.BASELINE_REGISTRY.items():
        if baseline_id in bl.IMPLEMENTED_BASELINES:
            assert entry["fidelity"] == "FAITHFUL_PORT", baseline_id
        else:
            assert entry["fidelity"] in ("UNAVAILABLE_NOT_RUN", "NOT_RUN_EXTERNAL"), baseline_id


def test_constant_deny_stub_cannot_pass_parity() -> None:
    """A constant-deny stub wearing an implemented name fails the parity vector."""

    def constant_deny(baseline_id: str, case: object, ctx: object = None) -> Outcome:
        return Outcome(observed_outcome="REJECT", counted_as_success=True, detail="stub")

    for baseline_id in IMPL_BASELINES:
        path = bl.FIXTURE_DIR / bl._PARITY_FIXTURES[baseline_id]
        vector = json.loads(path.read_text(encoding="utf-8"))
        with pytest.raises(AssertionError, match="PARITY_MISMATCH"):
            for step in vector["steps"]:
                stub = constant_deny(baseline_id, step["case"], step.get("ctx"))
                expected = step["expected_observed_outcome"]
                if stub.observed_outcome != expected:
                    raise AssertionError(f"PARITY_MISMATCH: {baseline_id} step {step['name']}")
                expected_detail = step.get("expected_detail_contains")
                if expected_detail is not None and expected_detail not in stub.detail:
                    raise AssertionError(
                        f"PARITY_MISMATCH: {baseline_id} step {step['name']} detail"
                    )


def test_implemented_dispatch_never_routes_unimplemented_id() -> None:
    """Registry fidelity gate: NOT_RUN_EXTERNAL ids can never reach implemented code."""
    sentinel_workload = {
        "source_snapshot": {"x": "1"},
        "revocations": [],
        "dispatches": [
            {
                "dispatch_id": "d",
                "subject": "s1",
                "grant": "g",
                "purpose": "p",
                "lineage": ["x"],
                "at_seconds": 0,
            }
        ],
    }
    case = _case(workload=sentinel_workload)
    for baseline_id in UNAVAIL_BASELINES:
        outcome = bl.run_baseline(baseline_id, case, _ctx())
        assert outcome.observed_outcome == "NOT_RUN_EXTERNAL"
        assert "dispatch_count" not in outcome.detail


# ---------------------------------------------------------------------------
# Adversarial: parity tampering is refused
# ---------------------------------------------------------------------------


def test_parity_vector_mismatch_fails_hard(tmp_path, monkeypatch) -> None:
    baseline_id = "coarse-cache-purge-on-revocation"
    original = json.loads(
        (bl.FIXTURE_DIR / bl._PARITY_FIXTURES[baseline_id]).read_text(encoding="utf-8")
    )
    original["steps"][0]["expected_observed_outcome"] = "REJECT"
    broken_dir = tmp_path / "fixtures"
    broken_dir.mkdir()
    broken_file = broken_dir / bl._PARITY_FIXTURES[baseline_id]
    broken_file.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(bl, "FIXTURE_DIR", broken_dir)
    with pytest.raises(AssertionError, match="PARITY_MISMATCH"):
        bl.parity_check(baseline_id)


def test_parity_missing_fixture_fails_closed(tmp_path, monkeypatch) -> None:
    empty_dir = tmp_path / "fixtures"
    empty_dir.mkdir()
    monkeypatch.setattr(bl, "FIXTURE_DIR", empty_dir)
    with pytest.raises(ValueError, match="PARITY_VECTOR_MISSING"):
        bl.parity_check("always-recompute-authorized-projection")


# ---------------------------------------------------------------------------
# Adversarial: malformed input fails closed, never a silent safe rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("baseline_id", IMPL_BASELINES)
def test_malformed_workload_fails_closed(baseline_id: str) -> None:
    bad = _case(workload={"source_snapshot": {"x": "1"}, "dispatches": []})
    outcome = bl.run_baseline(baseline_id, bad, _ctx())
    assert outcome.observed_outcome == "EXECUTION_ERROR"
    assert "WORKLOAD_MALFORMED" in outcome.detail


@pytest.mark.parametrize("baseline_id", IMPL_BASELINES)
def test_non_mapping_case_fails_closed(baseline_id: str) -> None:
    outcome = bl.run_baseline(baseline_id, "not-a-case", _ctx())  # type: ignore[arg-type]
    assert outcome.observed_outcome == "EXECUTION_ERROR"
    assert "CASE_MALFORMED" in outcome.detail


def test_dispatch_missing_field_fails_closed() -> None:
    bad = _case(
        workload={
            "source_snapshot": {"x": "1"},
            "revocations": [],
            "dispatches": [{"dispatch_id": "d1"}],
        }
    )
    outcome = bl.run_baseline("coarse-cache-purge-on-revocation", bad, _ctx())
    assert outcome.observed_outcome == "EXECUTION_ERROR"
    assert "WORKLOAD_MALFORMED" in outcome.detail


def test_outcome_type_matches_shared_harness_contract() -> None:
    """run_baseline returns the shared harness Outcome type (task contract)."""
    outcome = bl.run_baseline("always-recompute-authorized-projection", _case(), _ctx())
    assert type(outcome) is Outcome
    assert dataclasses.is_dataclass(outcome)
    outcome.to_dict()
