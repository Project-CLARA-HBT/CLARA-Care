from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from clara_api.core.security import create_access_token
from clara_api.db import session as db_session
from clara_api.db.models import (
    Query as QueryModel,
)
from clara_api.db.models import (
    SessionModel,
    User,
)
from clara_api.main import app

client = TestClient(app)

ADMIN_EMAIL = "ops@admin.clara"
RESEARCHER_EMAIL = "alice@research.clara"


def _admin_token() -> str:
    """Mint an admin access token directly (offline, no login/OTP/SMTP path).

    The Product_Analytics endpoint is gated by ``require_roles("admin")``,
    which only inspects the decoded JWT role — it performs no database lookup
    and no outbound network call. Minting the token here keeps the test
    hermetic and fast: it never exercises password hashing, the login OTP
    flow, or the SMTP dispatch path.
    """

    return create_access_token(subject=ADMIN_EMAIL, role="admin")


def _researcher_token() -> str:
    return create_access_token(subject=RESEARCHER_EMAIL, role="researcher")


def _seed_chat_activity() -> None:
    """Seed a single chat query so the aggregation reports usage in-range."""

    with db_session.SessionLocal() as db:
        user = User(
            email=ADMIN_EMAIL,
            hashed_password="x",
            role="admin",
            full_name="Ops Admin",
            is_email_verified=True,
            status="active",
            last_login_at=datetime.now(tz=UTC),
        )
        db.add(user)
        db.flush()
        session_row = SessionModel(user_id=user.id, title="Analytics Session")
        db.add(session_row)
        db.flush()
        db.add(
            QueryModel(
                session_id=session_row.id,
                role="admin",
                user_input="product analytics query",
                response_text="{}",
            )
        )
        db.commit()


def _assert_populated_shape(payload: dict) -> None:
    datetime.fromisoformat(payload["generated_at"])
    assert isinstance(payload["range"], list)
    assert len(payload["range"]) == 2
    assert isinstance(payload["active_user_trend"], list)
    assert isinstance(payload["surface_usage"], list)
    assert isinstance(payload["funnels"], list)
    assert isinstance(payload["retention"], list)
    assert isinstance(payload["has_data"], bool)


def test_product_analytics_success_for_admin() -> None:
    token = _admin_token()
    _seed_chat_activity()
    now = datetime.now(tz=UTC)

    today = now.date().isoformat()
    start = (now - timedelta(days=7)).date().isoformat()
    response = client.get(
        "/api/v1/system/analytics/product",
        params={"from": start, "to": today},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    _assert_populated_shape(payload)
    assert payload["has_data"] is True
    surfaces = {row["surface"] for row in payload["surface_usage"]}
    assert "chat" in surfaces

    # PII-free: no free-text query/email/drug content leaks into the aggregation.
    serialized = response.text.lower()
    assert "product analytics query" not in serialized
    assert "ops@admin.clara" not in serialized


def test_product_analytics_defaults_range_when_unspecified() -> None:
    token = _admin_token()
    response = client.get(
        "/api/v1/system/analytics/product",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    _assert_populated_shape(payload)
    start_str, end_str = payload["range"]
    start = datetime.fromisoformat(start_str).date()
    end = datetime.fromisoformat(end_str).date()
    assert start <= end


def test_product_analytics_empty_range_returns_populated_shape() -> None:
    token = _admin_token()
    # A future window guarantees no data falls inside it.
    future_start = (datetime.now(tz=UTC) + timedelta(days=400)).date().isoformat()
    future_end = (datetime.now(tz=UTC) + timedelta(days=430)).date().isoformat()

    response = client.get(
        "/api/v1/system/analytics/product",
        params={"from": future_start, "to": future_end},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    _assert_populated_shape(payload)
    assert payload["has_data"] is False
    assert payload["active_user_trend"] == []
    # Surface usage shape is still present (counts are zero).
    assert {row["surface"] for row in payload["surface_usage"]} >= {"chat", "council", "scribe"}


def test_product_analytics_invalid_range_returns_422() -> None:
    token = _admin_token()
    later = datetime.now(tz=UTC).date().isoformat()
    earlier = (datetime.now(tz=UTC) - timedelta(days=10)).date().isoformat()

    response = client.get(
        "/api/v1/system/analytics/product",
        params={"from": later, "to": earlier},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


def test_product_analytics_invalid_date_format_returns_422() -> None:
    token = _admin_token()
    response = client.get(
        "/api/v1/system/analytics/product",
        params={"from": "not-a-date", "to": "2026-01-01"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


def test_product_analytics_forbidden_for_non_admin() -> None:
    token = _researcher_token()
    response = client.get(
        "/api/v1/system/analytics/product",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_product_analytics_unauthorized_without_token() -> None:
    client.cookies.clear()
    response = client.get("/api/v1/system/analytics/product")
    assert response.status_code == 401
