import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from clara_api.db.models import Query as QueryModel
from clara_api.db.models import SessionModel, User
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_research_conversations_create_list_delete() -> None:
    token = _login("research-owner@example.com")

    create_response = client.post(
        "/api/v1/research/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "query": "So sánh DASH và Địa Trung Hải",
            "result": {
                "tier": "tier2",
                "answer": "So sánh ngắn gọn",
                "citations": [{"title": "Paper A"}],
            },
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["id"] > 0
    assert created["query"] == "So sánh DASH và Địa Trung Hải"
    assert created["tier"] == "tier2"
    assert created["result"]["tier"] == "tier2"
    conversation_id = created["id"]

    list_response = client.get(
        "/api/v1/research/conversations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    payload = list_response.json()
    assert isinstance(payload["items"], list)
    assert len(payload["items"]) == 1
    assert payload["items"][0]["id"] == conversation_id

    delete_response = client.delete(
        f"/api/v1/research/conversations/{conversation_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True

    list_after_delete = client.get(
        "/api/v1/research/conversations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_after_delete.status_code == 200
    assert list_after_delete.json()["items"] == []


def test_research_conversation_append_and_list_messages() -> None:
    token = _login("research-thread@example.com")

    create_response = client.post(
        "/api/v1/research/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "query": "Câu hỏi mở đầu",
            "result": {
                "tier": "tier2",
                "answer": "Trả lời mở đầu",
                "citations": [{"title": "Paper A"}],
            },
        },
    )
    assert create_response.status_code == 200
    conversation_id = create_response.json()["id"]

    append_response = client.post(
        f"/api/v1/research/conversations/{conversation_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "query": "Câu hỏi follow-up",
            "result": {
                "tier": "tier2",
                "answer": "Trả lời follow-up",
                "citations": [{"title": "Paper B"}],
            },
        },
    )
    assert append_response.status_code == 200
    payload = append_response.json()
    assert payload["id"] == conversation_id
    assert payload["query"] == "Câu hỏi follow-up"

    messages_response = client.get(
        f"/api/v1/research/conversations/{conversation_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert messages_response.status_code == 200
    messages_payload = messages_response.json()
    assert messages_payload["conversation_id"] == conversation_id
    assert len(messages_payload["items"]) == 2
    assert messages_payload["items"][0]["query"] == "Câu hỏi mở đầu"
    assert messages_payload["items"][1]["query"] == "Câu hỏi follow-up"


def test_research_conversations_list_isolated_by_user() -> None:
    owner_token = _login("owner-a@example.com")
    other_token = _login("owner-b@example.com")

    owner_create = client.post(
        "/api/v1/research/conversations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"query": "Q owner", "result": {"tier": "tier1", "answer": "A owner"}},
    )
    assert owner_create.status_code == 200

    other_create = client.post(
        "/api/v1/research/conversations",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"query": "Q other", "result": {"tier": "tier1", "answer": "A other"}},
    )
    assert other_create.status_code == 200

    owner_list = client.get(
        "/api/v1/research/conversations",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert owner_list.status_code == 200
    owner_items = owner_list.json()["items"]
    assert len(owner_items) == 1
    assert owner_items[0]["query"] == "Q owner"

    other_list = client.get(
        "/api/v1/research/conversations",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert other_list.status_code == 200
    other_items = other_list.json()["items"]
    assert len(other_items) == 1
    assert other_items[0]["query"] == "Q other"


def test_research_conversations_reject_invalid_payloads() -> None:
    token = _login("invalid-payload@example.com")

    missing_query = client.post(
        "/api/v1/research/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"result": {"tier": "tier1", "answer": "ok"}},
    )
    assert missing_query.status_code == 422

    missing_result = client.post(
        "/api/v1/research/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "abc"},
    )
    assert missing_result.status_code == 422

    invalid_tier = client.post(
        "/api/v1/research/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "abc", "result": {"tier": "tier-unknown", "answer": "x"}},
    )
    assert invalid_tier.status_code == 422
    assert "tier1" in invalid_tier.json()["detail"]


def test_research_conversations_list_handles_legacy_response_text() -> None:
    token = _login("legacy-research@example.com")

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "legacy-research@example.com").first()
        assert user is not None
        session_obj = SessionModel(
            user_id=user.id,
            title="legacy session",
        )
        db.add(session_obj)
        db.flush()
        db.add(
            QueryModel(
                session_id=session_obj.id,
                role="normal",
                user_input="legacy query",
                response_text="legacy plain text response",
                created_at=datetime.now(tz=UTC),
            )
        )
        db.commit()

    list_response = client.get(
        "/api/v1/research/conversations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert len(items) == 1
    assert items[0]["query"] == "legacy query"
    assert items[0]["result"]["tier"] == "tier1"
    assert items[0]["result"]["answer"] == "legacy plain text response"

    # Sanity check JSON payload path as well.
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "legacy-research@example.com").first()
        assert user is not None
        session_obj = SessionModel(user_id=user.id, title="json session")
        db.add(session_obj)
        db.flush()
        payload = json.dumps({"result": {"tier": "tier2", "answer": "json stored"}})
        db.add(
            QueryModel(
                session_id=session_obj.id,
                role="normal",
                user_input="json query",
                response_text=payload,
            )
        )
        db.commit()

    list_response = client.get(
        "/api/v1/research/conversations?limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert len(items) == 2
    assert any(item["result"]["tier"] == "tier2" for item in items)


def test_research_conversations_infers_tier2_from_new_ml_metadata_keys() -> None:
    token = _login("legacy-ml-metadata@example.com")

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "legacy-ml-metadata@example.com").first()
        assert user is not None
        session_obj = SessionModel(user_id=user.id, title="metadata session")
        db.add(session_obj)
        db.flush()
        payload = json.dumps(
            {
                "result": {
                    "answer": "metadata-only result",
                    "query_plan": {"query": "warfarin ibuprofen", "query_terms": ["warfarin"]},
                    "source_attempts": [{"source": "pubmed", "status": "completed"}],
                    "source_errors": {"openfda": ["timeout"]},
                    "fallback_reason": "upstream_timeout",
                }
            }
        )
        db.add(
            QueryModel(
                session_id=session_obj.id,
                role="normal",
                user_input="metadata query",
                response_text=payload,
            )
        )
        db.commit()

    list_response = client.get(
        "/api/v1/research/conversations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert len(items) == 1
    assert items[0]["query"] == "metadata query"
    assert items[0]["tier"] == "tier2"
    assert items[0]["result"]["tier"] == "tier2"
    assert items[0]["result"]["query_plan"]["query"] == "warfarin ibuprofen"
    assert items[0]["result"]["source_attempts"][0]["source"] == "pubmed"
    assert items[0]["result"]["source_errors"] == {"openfda": ["timeout"]}
    assert items[0]["result"]["fallback_reason"] == "upstream_timeout"


def test_research_conversation_persists_canonical_deep_beta_contract() -> None:
    token = _login("deep-beta-conversation@example.com")

    create_response = client.post(
        "/api/v1/research/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "query": "Deep beta persistence",
            "result": {
                "tier": "tier2",
                "answer": "contract check",
                "research_mode": "deep-beta",
                "metadata": {
                    "research_mode": "deep-beta",
                    "fallback_reason": "upstream_timeout",
                },
                "source_errors": {"openfda": "timeout"},
            },
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["result"]["research_mode"] == "deep_beta"
    assert created["result"]["metadata"]["research_mode"] == "deep_beta"
    assert created["result"]["fallback"] is True
    assert created["result"]["fallback_used"] is True
    assert created["result"]["metadata"]["fallback_used"] is True
    assert created["result"]["fallback_reason"] == "upstream_timeout"

    with SessionLocal() as db:
        row = db.query(QueryModel).filter(QueryModel.id == created["query_id"]).first()
        assert row is not None
        stored = json.loads(row.response_text)
    stored_result = stored["result"]
    assert stored_result["research_mode"] == "deep_beta"
    assert stored_result["metadata"]["research_mode"] == "deep_beta"
    assert stored_result["fallback"] is True
    assert stored_result["fallback_used"] is True
    assert stored_result["metadata"]["fallback_used"] is True


def test_research_conversations_infers_tier2_when_research_mode_is_deep_beta() -> None:
    token = _login("deep-beta-legacy@example.com")

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "deep-beta-legacy@example.com").first()
        assert user is not None
        session_obj = SessionModel(user_id=user.id, title="deep beta legacy")
        db.add(session_obj)
        db.flush()
        payload = json.dumps(
            {
                "result": {
                    "answer": "legacy deep beta",
                    "research_mode": "deep_beta",
                    "metadata": {"research_mode": "deep_beta"},
                }
            }
        )
        db.add(
            QueryModel(
                session_id=session_obj.id,
                role="normal",
                user_input="deep beta legacy query",
                response_text=payload,
            )
        )
        db.commit()

    list_response = client.get(
        "/api/v1/research/conversations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert len(items) == 1
    assert items[0]["tier"] == "tier2"
    assert items[0]["result"]["tier"] == "tier2"
    assert items[0]["result"]["research_mode"] == "deep_beta"
