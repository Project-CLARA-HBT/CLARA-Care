from datetime import UTC, datetime, timedelta

from clara_api.lifemap.review_findings import (
    ReviewFact,
    rule_first_findings,
    validate_model_proposals,
)


def _fact(ref: str, value: object, hour: int = 0) -> ReviewFact:
    return ReviewFact(
        revision_id=ref,
        field_key="blood_pressure",
        value=value,
        occurred_at=datetime(2026, 7, 29, hour, tzinfo=UTC),
        truth_state="confirmed",
    )


def test_rules_detect_duplicate_contradiction_and_missingness() -> None:
    findings = rule_first_findings(
        (
            _fact("r1", {"systolic": 120}),
            _fact("r2", {"systolic": 120}, 1),
            _fact("r3", {"systolic": 145}, 2),
        ),
        required_fields=frozenset({"blood_pressure", "measurement_position"}),
    )
    assert {finding.kind for finding in findings} == {
        "duplicate",
        "contradiction",
        "missingness",
    }
    assert all(finding.requires_human_resolution for finding in findings)


def test_invalidated_facts_do_not_create_findings() -> None:
    invalid = ReviewFact(
        revision_id="bad",
        field_key="blood_pressure",
        value={"systolic": 180},
        occurred_at=datetime.now(UTC),
        truth_state="invalidated",
    )
    assert rule_first_findings((invalid,)) == ()


def test_model_proposals_cannot_escape_authorized_revisions_or_resolve_truth() -> None:
    accepted = validate_model_proposals(
        [
            {
                "source": "nli",
                "revision_ids": ["r1", "r2"],
                "field_key": "symptom",
            },
            {
                "source": "llm",
                "revision_ids": ["other-profile"],
                "field_key": "symptom",
            },
            {"source": "unknown", "revision_ids": ["r1"], "field_key": "symptom"},
        ],
        authorized_revision_ids=frozenset({"r1", "r2"}),
    )
    assert len(accepted) == 1
    assert accepted[0].proposal_source == "nli"
    assert accepted[0].requires_human_resolution is True


def test_duplicate_window_is_bounded() -> None:
    findings = rule_first_findings(
        (_fact("r1", 120), _fact("r2", 120, 2)),
        duplicate_window=timedelta(hours=1),
    )
    assert findings == ()
