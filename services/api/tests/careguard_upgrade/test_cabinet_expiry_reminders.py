"""Cabinet expiry computation + reminder-state persistence.

Feature: clara-selfmed-careguard-upgrade (task 3.4)

Covers Requirement 10:

* 10.1 — per-item expiry status (``expired`` / ``expiring_soon`` / ``ok``)
  derived from ``expires_on``.
* 10.2 — expired / expiring-soon counts surfaced in the cabinet summary.
* 10.3 — per-item reminder state persisted + exposed when
  ``SELFMED_EXPIRY_REMINDERS_ENABLED`` is on.
* 10.4 — with the flag off, behavior matches today (read-only expiry display,
  no reminder persistence).
* 10.5 — a missing ``expires_on`` is "no expiry data" (status ``None``) and is
  excluded from the rollup counts, without error.

Expiry display (status + summary) is unconditional and purely derived from
``expires_on``; only reminder *persistence* is flag-gated.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from clara_api.api.v1.endpoints.careguard import (
    EXPIRY_SOON_WINDOW_DAYS,
    _compute_expiry_status,
)
from clara_api.main import app

client = TestClient(app)


def _login(email: str) -> str:
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "secret123"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    status_response = client.get(
        "/api/v1/auth/consent-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status_response.status_code == 200
    required_version = status_response.json()["required_version"]
    accept_response = client.post(
        "/api/v1/auth/consent",
        headers={"Authorization": f"Bearer {token}"},
        json={"consent_version": required_version, "accepted": True},
    )
    assert accept_response.status_code == 200
    return token


def _add_item(token: str, **fields: object):
    payload = {"source": "manual", **fields}
    return client.post(
        "/api/v1/careguard/cabinet/items",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


# --- Req 10.1 / 10.5: per-item expiry status (unit) --------------------------


def test_compute_expiry_status_classifies_each_bucket() -> None:
    now = datetime(2030, 1, 1, tzinfo=UTC)
    assert _compute_expiry_status(None, now=now) is None
    assert _compute_expiry_status(now - timedelta(days=1), now=now) == "expired"
    assert _compute_expiry_status(now, now=now) == "expired"
    assert (
        _compute_expiry_status(now + timedelta(days=5), now=now) == "expiring_soon"
    )
    assert (
        _compute_expiry_status(
            now + timedelta(days=EXPIRY_SOON_WINDOW_DAYS), now=now
        )
        == "expiring_soon"
    )
    assert (
        _compute_expiry_status(
            now + timedelta(days=EXPIRY_SOON_WINDOW_DAYS + 1), now=now
        )
        == "ok"
    )


def test_compute_expiry_status_treats_naive_datetime_as_utc() -> None:
    now = datetime(2030, 1, 1, tzinfo=UTC)
    naive_past = datetime(2029, 12, 31)  # noqa: DTZ001 — exercising naive input
    assert _compute_expiry_status(naive_past, now=now) == "expired"


# --- Req 10.1 / 10.5: per-item expiry status (API) ---------------------------


def test_item_response_surfaces_expiry_status() -> None:
    token = _login("expiry-status@example.com")
    now = datetime.now(tz=UTC)

    expired = _add_item(
        token, drug_name="Aspirin", expires_on=_iso(now - timedelta(days=10))
    )
    soon = _add_item(
        token, drug_name="Ibuprofen", expires_on=_iso(now + timedelta(days=7))
    )
    ok = _add_item(
        token, drug_name="Paracetamol", expires_on=_iso(now + timedelta(days=365))
    )
    none = _add_item(token, drug_name="Loratadine")

    assert expired.json()["expiry_status"] == "expired"
    assert soon.json()["expiry_status"] == "expiring_soon"
    assert ok.json()["expiry_status"] == "ok"
    # No expiry data → no error, status None (Req 10.5).
    assert none.status_code == 200
    assert none.json()["expiry_status"] is None


# --- Req 10.2: cabinet summary rollup ----------------------------------------


def test_cabinet_summary_counts_expired_and_expiring_soon() -> None:
    token = _login("expiry-summary@example.com")
    now = datetime.now(tz=UTC)
    _add_item(token, drug_name="Warfarin", expires_on=_iso(now - timedelta(days=2)))
    _add_item(token, drug_name="Metformin", expires_on=_iso(now - timedelta(days=20)))
    _add_item(token, drug_name="Atorvastatin", expires_on=_iso(now + timedelta(days=10)))
    _add_item(token, drug_name="Omeprazole", expires_on=_iso(now + timedelta(days=400)))
    _add_item(token, drug_name="Cetirizine")  # no expiry data → excluded

    cabinet = client.get(
        "/api/v1/careguard/cabinet",
        headers={"Authorization": f"Bearer {token}"},
    ).json()

    summary = cabinet["expiry_summary"]
    assert summary["expired_count"] == 2
    assert summary["expiring_soon_count"] == 1
    assert summary["expiry_window_days"] == EXPIRY_SOON_WINDOW_DAYS


# --- Req 10.4: flag OFF → no reminder persistence ----------------------------


def test_reminder_not_persisted_when_flag_off() -> None:
    token = _login("expiry-reminder-off@example.com")
    created = _add_item(
        token,
        drug_name="Sertraline",
        expiry_reminder={"enabled": True, "remind_days_before": 7},
    )
    assert created.status_code == 200
    # Field is ignored and not exposed when the flag is off (Req 10.4).
    assert created.json()["expiry_reminder"] is None

    item_id = created.json()["id"]
    updated = client.patch(
        f"/api/v1/careguard/cabinet/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"expiry_reminder": {"enabled": True}},
    )
    assert updated.status_code == 200
    assert updated.json()["expiry_reminder"] is None


# --- Req 10.3: flag ON → reminder persisted + exposed ------------------------


def test_reminder_persisted_and_exposed_when_flag_on(set_flags) -> None:
    set_flags(selfmed_expiry_reminders_enabled=True)
    token = _login("expiry-reminder-on@example.com")

    reminder = {"enabled": True, "remind_days_before": 14}
    created = _add_item(token, drug_name="Digoxin", expiry_reminder=reminder)
    assert created.status_code == 200
    assert created.json()["expiry_reminder"] == reminder

    item_id = created.json()["id"]
    new_reminder = {"enabled": False, "remind_days_before": 3}
    updated = client.patch(
        f"/api/v1/careguard/cabinet/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"expiry_reminder": new_reminder},
    )
    assert updated.status_code == 200
    assert updated.json()["expiry_reminder"] == new_reminder

    # Reminder survives a fresh read (persisted, Req 10.3).
    cabinet = client.get(
        "/api/v1/careguard/cabinet",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    row = next(item for item in cabinet["items"] if item["id"] == item_id)
    assert row["expiry_reminder"] == new_reminder
