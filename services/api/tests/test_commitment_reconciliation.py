"""Pure unit tests for the P1 Commitment Reconciliation Engine.

The engine is duck-typed: versions are ``SimpleNamespace`` fixtures and events
are plain dicts.  No database is involved; determinism (P12) is asserted via
identical ``algorithm_digest`` across repeated/concurrent calls.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from clara_api.glhs.commitment_reconciliation import reconcile_commitment
from clara_api.glhs.commitments import derive_lifecycle_predicates, policy_for
from clara_api.glhs.reconciliation import evaluate_commitment

_AT = datetime(2026, 1, 1, tzinfo=UTC)
_DUE = _AT + timedelta(days=30)
_GRACE = _AT + timedelta(days=37)


def _event(evidence_id: str, valid_at: datetime, known_at: datetime, **extra: object) -> dict:
    return {
        "evidence_id": evidence_id,
        "valid_at": valid_at.isoformat(),
        "known_at": known_at.isoformat(),
        **extra,
    }


def _fulfillment_event(evidence_id: str, at: datetime, **extra: object) -> dict:
    return _event(
        evidence_id,
        at,
        at,
        resource_type="Observation",
        code="x",
        status="final",
        **extra,
    )


def _version(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "profile_id": 7,
        "commitment_id": "commitment-1",
        "lifecycle_state": "OPEN",
        "anchor_valid_time": _AT,
        "anchor_known_time": _AT,
        "earliest_valid_time": _AT,
        "due_time": _DUE,
        "grace_end": _GRACE,
        "authority_class": "patient_report",
        "target_json": {"system": "http://loinc.org", "code": "x"},
        "dependencies_json": ["dep-1"],
        "minimum_evidence": 1,
        "conditional_trigger_json": None,
        "cancellation_predicate_json": None,
        "supersession_predicate_json": None,
        "fulfillment_predicate_json": {
            "op": "event",
            "equals": {"resource_type": "Observation", "code": "x", "status": "final"},
        },
        "partial_predicate_json": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _reconcile(
    version: SimpleNamespace, events: list[dict], *, cutoff: datetime | None = None
):
    point = cutoff or (_AT + timedelta(days=45))
    return reconcile_commitment(
        version, events, valid_at=point, known_at=point
    )


def test_late_backdated_evidence_is_excluded_by_known_at() -> None:
    event = _fulfillment_event("e1", _AT + timedelta(days=9))
    event["known_at"] = (_AT + timedelta(days=40)).isoformat()
    state = _reconcile(
        _version(),
        [event],
        cutoff=_AT + timedelta(days=31),
    )
    assert state.lifecycle_state == "OPEN"
    assert state.matched_evidence_ids == ()
    assert state.excluded_evidence == ({"evidence_id": "e1", "reason": "not_yet_known"},)
    assert state.reason_codes == ("no_terminal_predicate_satisfied", "no_visible_evidence")


def test_knowledge_time_cutoff_reveals_fulfillment() -> None:
    event = _fulfillment_event("e1", _AT + timedelta(days=9))
    event["known_at"] = (_AT + timedelta(days=40)).isoformat()
    before = _reconcile(_version(), [event], cutoff=_AT + timedelta(days=31))
    after = _reconcile(_version(), [event], cutoff=_AT + timedelta(days=45))
    assert before.lifecycle_state == "OPEN"
    assert after.lifecycle_state == "SATISFIED"
    assert after.matched_evidence_ids == ("e1",)
    assert after.predicate_matches["fulfillment"]["matched"] is True
    assert after.predicate_matches["fulfillment"]["matched_event_ids"] == ("e1",)
    assert after.reason_codes == ("fulfillment_predicate_satisfied",)


def test_fulfillment_decisive_event_and_time() -> None:
    state = _reconcile(_version(), [_fulfillment_event("e1", _AT + timedelta(days=9))])
    decisive = state.predicate_matches["fulfillment"]["decisive_event"]
    assert decisive is not None
    assert decisive["evidence_id"] == "e1"
    assert decisive["valid_at"] == (_AT + timedelta(days=9)).isoformat()
    assert state.decisive_valid_time == _AT + timedelta(days=9)
    assert state.timeliness == "BEFORE_DUE"
    assert state.timeliness_state == "BEFORE_DUE"


def test_cancellation_predicate_satisfied() -> None:
    version = _version(
        cancellation_predicate_json={
            "op": "event",
            "equals": {"resource_type": "Observation", "code": "x", "status": "cancelled"},
        }
    )
    events = [
        _fulfillment_event("e-fulfill", _AT + timedelta(days=9)),
        _event(
            "e-cancel",
            _AT + timedelta(days=10),
            _AT + timedelta(days=10),
            resource_type="Observation",
            code="x",
            status="cancelled",
        ),
    ]
    state = _reconcile(version, events)
    assert state.lifecycle_state == "CANCELLED"
    assert state.decisive_valid_time == _AT + timedelta(days=10)
    assert state.reason_codes == ("cancellation_predicate_satisfied",)


def test_supersession_takes_precedence_over_fulfillment() -> None:
    version = _version(
        supersession_predicate_json={
            "op": "event",
            "equals": {"resource_type": "Observation", "code": "replacement", "status": "final"},
        }
    )
    events = [
        _fulfillment_event("e-fulfill", _AT + timedelta(days=5)),
        _event(
            "e-supersede",
            _AT + timedelta(days=20),
            _AT + timedelta(days=20),
            resource_type="Observation",
            code="replacement",
            status="final",
        ),
    ]
    state = _reconcile(version, events)
    assert state.lifecycle_state == "SUPERSEDED"
    assert state.predicate_matches["supersession"]["decisive_event"]["evidence_id"] == "e-supersede"
    assert "supersession_predicate_satisfied" in state.reason_codes


def test_partial_completion() -> None:
    version = _version(
        partial_predicate_json={
            "op": "event",
            "equals": {"resource_type": "Observation", "code": "x", "status": "preliminary"},
        }
    )
    events = [
        _event(
            "e-partial",
            _AT + timedelta(days=9),
            _AT + timedelta(days=9),
            resource_type="Observation",
            code="x",
            status="preliminary",
        )
    ]
    state = _reconcile(version, events)
    assert state.lifecycle_state == "PARTIALLY_SATISFIED"
    assert state.predicate_matches["partial"]["matched"] is True
    assert state.reason_codes == ("partial_predicate_satisfied",)


def test_open_commitment_goes_overdue_and_escalates() -> None:
    state = _reconcile(_version(), [])
    assert state.lifecycle_state == "OPEN"
    assert state.evidence_state == "INSUFFICIENT_EVIDENCE"
    assert state.timeliness == "OVERDUE"
    assert state.escalation_reasons == (
        {"code": "commitment_insufficient_evidence", "commitment_id": "commitment-1"},
        {"code": "commitment_overdue", "commitment_id": "commitment-1"},
    )
    assert state.coverage["minimum_evidence"] is False


def test_overdue_escalation_appears_at_cutoff_after_grace() -> None:
    within_grace = _reconcile(_version(), [], cutoff=_AT + timedelta(days=35))
    overdue = _reconcile(_version(), [], cutoff=_AT + timedelta(days=40))
    assert within_grace.timeliness == "IN_GRACE"
    assert within_grace.escalation_reasons == (
        {"code": "commitment_insufficient_evidence", "commitment_id": "commitment-1"},
    )
    assert overdue.timeliness == "OVERDUE"
    assert overdue.escalation_reasons == (
        {"code": "commitment_insufficient_evidence", "commitment_id": "commitment-1"},
        {"code": "commitment_overdue", "commitment_id": "commitment-1"},
    )


def test_irrelevant_lower_authority_conflict_is_not_conflicted() -> None:
    version = _version(authority_class="lab_verified")
    event = _event(
        "e-contradict",
        _AT + timedelta(days=9),
        _AT + timedelta(days=9),
        resource_type="Observation",
        code="other",
        status="final",
        authority="unverified",
        relation="contradicts",
    )
    state = _reconcile(version, [event])
    assert state.evidence_state == "CLEAR"
    assert "comparable_evidence_conflict" not in state.reason_codes


def test_comparable_authority_target_conflict_is_conflicted() -> None:
    event = _event(
        "e-contradict",
        _AT + timedelta(days=9),
        _AT + timedelta(days=9),
        resource_type="Observation",
        code="other",
        status="final",
        authority="lab_verified",
        relation="contradicts",
    )
    version = _version(authority_class="lab_verified")
    state = _reconcile(version, [event])
    assert state.evidence_state == "CONFLICTED"
    assert "comparable_evidence_conflict" in state.reason_codes
    assert state.escalation_reasons == (
        {"code": "commitment_conflict", "commitment_id": "commitment-1"},
        {"code": "commitment_overdue", "commitment_id": "commitment-1"},
    )


def test_dependency_coverage_reflects_dependency_input() -> None:
    with_deps = _reconcile(_version(dependencies_json=["a", "b"]), [])
    without_deps = _reconcile(_version(dependencies_json=None), [])
    assert with_deps.coverage["dependencies"] is True
    assert without_deps.coverage["dependencies"] is False


def test_minimum_evidence_coverage_gates_sufficiency() -> None:
    version = _version(minimum_evidence=3)
    one = _reconcile(version, [_fulfillment_event("e1", _AT + timedelta(days=9))])
    three = _reconcile(
        version,
        [
            _fulfillment_event("e1", _AT + timedelta(days=9)),
            _fulfillment_event("e2", _AT + timedelta(days=10)),
            _fulfillment_event("e3", _AT + timedelta(days=11)),
        ],
    )
    assert one.coverage["minimum_evidence"] is False
    assert three.coverage["minimum_evidence"] is True


def test_fresh_observed_at_governs_timeliness_over_old_valid_at() -> None:
    """Old clinical valid time never marks a fulfilled commitment overdue when
    the source observation clock is fresh (freshness.py precedence)."""

    late_valid = _AT + timedelta(days=35)
    fresh_observed = _AT + timedelta(days=20)
    event = _fulfillment_event("e1", late_valid, observed_at=fresh_observed.isoformat())
    state = _reconcile(_version(), [event])
    assert state.timeliness == "BEFORE_DUE"
    assert state.decisive_valid_time == late_valid

    without_observation = _reconcile(_version(), [_fulfillment_event("e1", late_valid)])
    assert without_observation.timeliness == "IN_GRACE"


def test_algorithm_digest_changes_with_evidence_inputs() -> None:
    first = _reconcile(_version(), [_fulfillment_event("e1", _AT + timedelta(days=9))])
    second = _reconcile(
        _version(),
        [_fulfillment_event("e1", _AT + timedelta(days=9))],
        cutoff=_AT + timedelta(days=40),
    )
    assert first.algorithm_digest != second.algorithm_digest
    assert first.algorithm_digest != _reconcile(_version(), []).algorithm_digest


def test_cross_subject_evidence_is_excluded() -> None:
    event = _fulfillment_event("e-other", _AT + timedelta(days=9), profile_id=8)
    state = _reconcile(_version(), [event])
    assert state.matched_evidence_ids == ()
    assert state.excluded_evidence == (
        {"evidence_id": "e-other", "reason": "cross_subject_evidence"},
    )


def test_concurrent_writers_produce_identical_digests() -> None:
    events = [
        _fulfillment_event("e1", _AT + timedelta(days=9)),
        _event(
            "e2",
            _AT + timedelta(days=12),
            _AT + timedelta(days=12),
            resource_type="Observation",
            code="x",
            status="final",
        ),
    ]
    version = _version()
    first = reconcile_commitment(
        version, events, valid_at=_AT + timedelta(days=45), known_at=_AT + timedelta(days=45)
    )
    second = reconcile_commitment(
        version, events, valid_at=_AT + timedelta(days=45), known_at=_AT + timedelta(days=45)
    )
    assert first == second
    assert first.algorithm_digest == second.algorithm_digest
    assert first.predicate_matches["fulfillment"]["predicate_digest"] == second.predicate_matches[
        "fulfillment"
    ]["predicate_digest"]


def test_state_effective_at_defaults_to_anchor_and_explicit_time_wins() -> None:
    explicit = _AT + timedelta(days=3)
    defaulted = _reconcile(_version(), [])
    explicit_state = _reconcile(_version(state_effective_at=explicit), [])
    assert defaulted.state_effective_at == _AT
    assert defaulted.state_known_at == _AT
    assert explicit_state.state_effective_at == explicit
    assert explicit_state.anchor_valid_time == _AT


def test_legacy_evaluate_commitment_remains_compatible() -> None:
    version = _version()
    event = _fulfillment_event("e1", _AT + timedelta(days=9))
    state = evaluate_commitment(
        version,
        [event],
        valid_at=_AT + timedelta(days=45),
        known_at=_AT + timedelta(days=45),
    )
    assert state.lifecycle_state == "SATISFIED"
    assert state.matched_evidence_ids == ("e1",)
    assert state.reason_codes == ("fulfillment_predicate_satisfied",)


def test_derive_lifecycle_predicates_is_policy_frozen() -> None:
    policy = policy_for("observations")
    derived = derive_lifecycle_predicates(
        policy,
        action="repeat_measurement",
        target={"system": "http://loinc.org", "code": "x"},
        due_time=None,
    )
    fulfillment = derived["fulfillment"]
    assert fulfillment["op"] == "event"
    assert fulfillment["equals"] == {
        "resource_type": "Observation",
        "system": "http://loinc.org",
        "code": "x",
    }
    assert fulfillment["derived_from_policy"] == "observations"
    assert derived["cancellation"]["equals"]["status"] == "cancelled"
    assert derived["supersession"]["equals"]["status"] == "superseded"
    assert derived["partial"]["equals"]["status"] == "preliminary"
    assert all(
        item["derived_from_policy"] == "observations" for item in derived.values()
    )


def test_derive_lifecycle_predicates_returns_empty_when_not_derivable() -> None:
    policy = policy_for("observations")
    assert (
        derive_lifecycle_predicates(
            policy, action="no_such_action", target={"system": "s", "code": "c"}, due_time=None
        )
        == {}
    )


def test_derived_predicate_marker_round_trips_through_engine() -> None:
    """A derived predicate stamped with derived_from_policy must evaluate the
    same as the equivalent hand-authored predicate."""

    derived = derive_lifecycle_predicates(
        policy_for("observations"),
        action="repeat_measurement",
        target={"system": "http://loinc.org", "code": "x"},
        due_time=None,
    )["fulfillment"]
    event = _event(
        "e1",
        _AT + timedelta(days=9),
        _AT + timedelta(days=9),
        resource_type="Observation",
        system="http://loinc.org",
        code="x",
    )
    with_marker = _reconcile(_version(fulfillment_predicate_json=derived), [event])
    without_marker = _reconcile(
        _version(
            fulfillment_predicate_json={
                "op": "event",
                "equals": {
                    "resource_type": "Observation",
                    "system": "http://loinc.org",
                    "code": "x",
                },
            }
        ),
        [event],
    )
    assert with_marker.lifecycle_state == "SATISFIED"
    assert with_marker.lifecycle_state == without_marker.lifecycle_state
    assert with_marker.matched_evidence_ids == without_marker.matched_evidence_ids
    assert with_marker.algorithm_digest != without_marker.algorithm_digest
    assert (
        with_marker.predicate_matches["fulfillment"]["predicate_digest"]
        != without_marker.predicate_matches["fulfillment"]["predicate_digest"]
    )
