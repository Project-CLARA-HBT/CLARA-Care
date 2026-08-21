from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from clara_api.api.v1.endpoints import lifemap_review
from clara_api.core.config import get_settings
from clara_api.lifemap.review_findings import (
    ReviewFact,
    rule_first_findings,
    validate_model_proposals,
)
from clara_api.main import app

client = TestClient(app)


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
                "relation": "possible_conflict",
            },
            {
                "source": "llm",
                "revision_ids": ["other-profile", "r1"],
                "field_key": "symptom",
                "relation": "possible_duplicate",
            },
            {
                "source": "unknown",
                "revision_ids": ["r1", "r2"],
                "field_key": "symptom",
                "relation": "possible_duplicate",
            },
        ],
        authorized_revision_ids=frozenset({"r1", "r2"}),
    )
    assert len(accepted) == 1
    assert accepted[0].proposal_source == "nli"
    assert accepted[0].reason_code == "possible_conflict"
    assert accepted[0].requires_human_resolution is True


def test_duplicate_window_is_bounded() -> None:
    findings = rule_first_findings(
        (_fact("r1", 120), _fact("r2", 120, 2)),
        duplicate_window=timedelta(hours=1),
    )
    assert findings == ()


def _account() -> dict[str, str]:
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": f"review-{uuid4().hex}@normal.clara",
            "password": "secret123",
        },
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.put(
        "/api/v1/phr/record", headers=headers, json={"full_name": "Review"}
    ).status_code == 200
    consent = client.get("/api/v1/auth/consent-status", headers=headers).json()
    assert client.post(
        "/api/v1/auth/consent",
        headers=headers,
        json={"consent_version": consent["required_version"]},
    ).status_code == 200
    return headers


def test_persisted_findings_require_human_action_and_are_idempotent(
    monkeypatch,
) -> None:
    monkeypatch.setattr(get_settings(), "lifemap_ai_review_findings_enabled", True)
    headers = _account()
    for suffix in ("a", "b"):
        response = client.post(
            "/api/v1/lifemap/events",
            headers={**headers, "Idempotency-Key": f"{suffix}-{uuid4().hex}"},
            json={
                "event_type": "symptom_report",
                "occurred_at": "2026-07-29T08:00:00Z",
                "payload": {"symptom": "đau đầu"},
                "truth_state": "confirmed",
            },
        )
        assert response.status_code == 201
    first = client.post("/api/v1/lifemap/v2/review-findings/scan", headers=headers)
    second = client.post("/api/v1/lifemap/v2/review-findings/scan", headers=headers)
    assert first.status_code == 200
    assert len(first.json()) == len(second.json()) == 1
    finding = first.json()[0]
    assert finding["status"] == "pending"
    action_headers = {**headers, "Idempotency-Key": uuid4().hex}
    resolved = client.post(
        f"/api/v1/lifemap/v2/review-findings/{finding['id']}/actions",
        headers=action_headers,
        json={"action": "resolved", "reason": "Đã kiểm tra nguồn"},
    )
    replay = client.post(
        f"/api/v1/lifemap/v2/review-findings/{finding['id']}/actions",
        headers=action_headers,
        json={"action": "resolved", "reason": "Đã kiểm tra nguồn"},
    )
    assert resolved.status_code == 200
    assert replay.json()["idempotent_replay"] is True
    assert replay.json()["status"] == "resolved"


def test_model_review_pairs_are_profile_scoped_and_human_resolution_only(
    monkeypatch,
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "lifemap_ai_review_findings_enabled", True)
    monkeypatch.setattr(settings, "lifemap_review_model_proposals_enabled", True)
    calls: list[dict] = []

    def _model_pairs(_path: str, payload: dict, **_kwargs: object) -> dict:
        calls.append(payload)
        facts = payload["facts"]
        return {
            "proposals": [
                {
                    "source": "llm",
                    "relation": "possible_conflict",
                    "revision_ids": [facts[0]["revision_id"], facts[1]["revision_id"]],
                    "field_key": facts[0]["field_key"],
                },
                {
                    "source": "llm",
                    "relation": "possible_duplicate",
                    "revision_ids": ["another-profile", facts[0]["revision_id"]],
                    "field_key": facts[0]["field_key"],
                },
            ]
        }

    monkeypatch.setattr(lifemap_review, "proxy_ml_post", _model_pairs)
    headers = _account()
    for suffix, symptom in (("first", "đau đầu"), ("second", "chóng mặt")):
        response = client.post(
            "/api/v1/lifemap/events",
            headers={**headers, "Idempotency-Key": f"{suffix}-{uuid4().hex}"},
            json={
                "event_type": "symptom_report",
                "occurred_at": "2026-07-29T08:00:00Z",
                "payload": {"symptom": symptom},
                "truth_state": "confirmed",
            },
        )
        assert response.status_code == 201

    findings = client.post("/api/v1/lifemap/v2/review-findings/scan", headers=headers)

    assert findings.status_code == 200
    assert len(calls) == 1
    assert set(calls[0]) == {"facts"}
    assert all(set(fact) == {"revision_id", "field_key", "payload"} for fact in calls[0]["facts"])
    model_findings = [item for item in findings.json() if item["kind"] == "model_proposal"]
    assert len(model_findings) == 1
    assert model_findings[0]["proposal_source"] == "llm"
    assert model_findings[0]["reason_code"] == "possible_conflict"
    assert model_findings[0]["requires_human_resolution"] is True
    assert model_findings[0]["status"] == "pending"
