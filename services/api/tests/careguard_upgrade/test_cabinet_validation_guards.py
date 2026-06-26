"""Cabinet duplicate guard, owner-scope, and quantity/expiry validation.

Feature: clara-selfmed-careguard-upgrade (task 3.2)

Pins Requirements 1.5 (duplicate guard on ``(cabinet_id, normalized_name)``),
1.6 (owner-scope enforcement on mutations), and 1.7 (quantity/expiry validation
with descriptive, PII-free Vietnamese errors). These guards are unconditional —
they do not depend on any new feature flag — and only reject clearly-invalid
input, so previously-valid requests remain accepted (flags-off equivalence).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

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


# --- Req 1.5: duplicate guard on (cabinet_id, normalized_name) ---------------


def test_create_rejects_duplicate_normalized_name() -> None:
    token = _login("guard-dup-create@example.com")
    first = _add_item(token, drug_name="Warfarin")
    assert first.status_code == 200

    # A different brand alias that normalizes to the same canonical ingredient
    # must be rejected as a duplicate (keyed on normalized_name, not raw text).
    second = _add_item(token, drug_name="Coumadin")
    assert second.status_code == 409
    assert "Thuốc đã tồn tại" in second.json()["detail"]


def test_create_duplicate_does_not_create_second_row() -> None:
    token = _login("guard-dup-norow@example.com")
    assert _add_item(token, drug_name="Metformin").status_code == 200
    assert _add_item(token, drug_name="Glucophage").status_code == 409

    cabinet = client.get(
        "/api/v1/careguard/cabinet",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    metformin_rows = [
        item for item in cabinet["items"] if item["normalized_name"] == "metformin"
    ]
    assert len(metformin_rows) == 1


# --- Req 1.6: owner-scope enforcement ----------------------------------------


def test_update_by_non_owner_is_rejected() -> None:
    owner = _login("guard-owner-a@example.com")
    outsider = _login("guard-owner-b@example.com")
    created = _add_item(owner, drug_name="Aspirin")
    assert created.status_code == 200
    item_id = created.json()["id"]

    response = client.patch(
        f"/api/v1/careguard/cabinet/items/{item_id}",
        headers={"Authorization": f"Bearer {outsider}"},
        json={"dosage": "100mg"},
    )
    assert response.status_code == 404
    assert "Không tìm thấy thuốc" in response.json()["detail"]


def test_delete_by_non_owner_leaves_row_intact() -> None:
    owner = _login("guard-owner-del-a@example.com")
    outsider = _login("guard-owner-del-b@example.com")
    created = _add_item(owner, drug_name="Ibuprofen")
    assert created.status_code == 200
    item_id = created.json()["id"]

    delete = client.delete(
        f"/api/v1/careguard/cabinet/items/{item_id}",
        headers={"Authorization": f"Bearer {outsider}"},
    )
    assert delete.status_code == 404

    # The owner's row is untouched.
    cabinet = client.get(
        "/api/v1/careguard/cabinet",
        headers={"Authorization": f"Bearer {owner}"},
    ).json()
    assert any(item["id"] == item_id for item in cabinet["items"])


# --- Req 1.7: quantity / expiry validation -----------------------------------


def test_create_rejects_negative_quantity() -> None:
    token = _login("guard-qty-neg@example.com")
    response = _add_item(token, drug_name="Paracetamol", quantity=-1)
    assert response.status_code == 422
    assert "Số lượng" in response.json()["detail"]


def test_create_rejects_absurd_quantity() -> None:
    token = _login("guard-qty-big@example.com")
    response = _add_item(token, drug_name="Paracetamol", quantity=10_000_000)
    assert response.status_code == 422
    assert "Số lượng" in response.json()["detail"]


def test_create_accepts_zero_and_positive_quantity() -> None:
    token = _login("guard-qty-ok@example.com")
    assert _add_item(token, drug_name="Loratadine", quantity=0).status_code == 200
    assert _add_item(token, drug_name="Cetirizine", quantity=30).status_code == 200


def test_update_rejects_negative_quantity() -> None:
    token = _login("guard-qty-update@example.com")
    created = _add_item(token, drug_name="Atorvastatin", quantity=10)
    assert created.status_code == 200
    item_id = created.json()["id"]

    response = client.patch(
        f"/api/v1/careguard/cabinet/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"quantity": -5},
    )
    assert response.status_code == 422
    assert "Số lượng" in response.json()["detail"]


def test_create_rejects_absurdly_past_expiry() -> None:
    token = _login("guard-exp-past@example.com")
    response = _add_item(
        token, drug_name="Amoxicillin", expires_on="1700-01-01T00:00:00Z"
    )
    assert response.status_code == 422
    assert "Ngày hết hạn" in response.json()["detail"]


def test_create_accepts_plausible_expiry() -> None:
    token = _login("guard-exp-ok@example.com")
    response = _add_item(
        token, drug_name="Omeprazole", expires_on="2030-06-01T00:00:00Z"
    )
    assert response.status_code == 200


def test_update_rejects_absurdly_far_future_expiry() -> None:
    token = _login("guard-exp-future@example.com")
    created = _add_item(token, drug_name="Sertraline")
    assert created.status_code == 200
    item_id = created.json()["id"]

    response = client.patch(
        f"/api/v1/careguard/cabinet/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"expires_on": "2999-01-01T00:00:00Z"},
    )
    assert response.status_code == 422
    assert "Ngày hết hạn" in response.json()["detail"]
