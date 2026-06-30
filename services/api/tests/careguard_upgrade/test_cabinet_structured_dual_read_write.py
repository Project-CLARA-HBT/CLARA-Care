"""Dual-read / dual-write for the medicine-cabinet brand/manufacturer fields.

Feature: clara-selfmed-careguard-upgrade (task 3.1)

Pins the dual-read/dual-write behavior gated by
``SELFMED_CABINET_STRUCTURED_FIELDS_ENABLED`` (Requirements 1.2, 1.3, 1.4):

* flag ON  -> brand/manufacturer persist in first-class columns; the note is
  stored clean (no legacy ``[meta]`` prefix).
* flag OFF -> legacy ``[meta]`` note encoding (byte-for-byte today's behavior);
  the structured columns stay null.
* legacy ``[meta]`` notes remain decodable regardless of the flag (no data
  loss across a flag flip).
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from clara_api.db.models import MedicineItem
from clara_api.db.session import SessionLocal
from clara_api.main import app

client = TestClient(app)

_ITEM_NOTE_META_PREFIX = "[meta]"


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


def _db_item(item_id: int) -> MedicineItem:
    with SessionLocal() as db:
        item = db.execute(
            select(MedicineItem).where(MedicineItem.id == item_id)
        ).scalar_one()
        # Detach a lightweight copy of the values we assert on.
        db.expunge(item)
        return item


def test_structured_flag_on_writes_columns_and_clean_note(set_flags) -> None:
    set_flags(selfmed_cabinet_structured_fields_enabled=True)
    token = _login("dual-write-on@example.com")

    response = client.post(
        "/api/v1/careguard/cabinet/items",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "drug_name": "Warfarin",
            "brand_name": "Coumadin",
            "manufacturer": "Bristol",
            "note": "uống buổi tối",
            "source": "manual",
        },
    )
    assert response.status_code == 200
    body = response.json()
    item_id = body["id"]
    assert body["brand_name"] == "Coumadin"
    assert body["manufacturer"] == "Bristol"
    assert body["note"] == "uống buổi tối"

    # Structured columns persisted; note kept clean (no legacy meta prefix).
    item = _db_item(item_id)
    assert item.brand_name == "Coumadin"
    assert item.manufacturer == "Bristol"
    assert item.note == "uống buổi tối"
    assert _ITEM_NOTE_META_PREFIX not in item.note


def test_structured_flag_off_uses_legacy_meta_note(set_flags) -> None:
    set_flags(selfmed_cabinet_structured_fields_enabled=False)
    token = _login("dual-write-off@example.com")

    response = client.post(
        "/api/v1/careguard/cabinet/items",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "drug_name": "Metformin",
            "brand_name": "Glucophage",
            "manufacturer": "Merck",
            "source": "manual",
        },
    )
    assert response.status_code == 200
    body = response.json()
    item_id = body["id"]
    # Response still surfaces decoded brand/manufacturer (dual-read).
    assert body["brand_name"] == "Glucophage"
    assert body["manufacturer"] == "Merck"

    # Legacy behavior: structured columns stay null, brand/manufacturer live in
    # the ``[meta]`` note encoding.
    item = _db_item(item_id)
    assert item.brand_name is None
    assert item.manufacturer is None
    assert item.note.startswith(_ITEM_NOTE_META_PREFIX)
    assert "Glucophage" in item.note
    assert "Merck" in item.note


def test_legacy_meta_note_decodable_after_flag_flip(set_flags) -> None:
    # Write under the legacy scheme (flag off)...
    set_flags(selfmed_cabinet_structured_fields_enabled=False)
    token = _login("dual-read-flip@example.com")
    create = client.post(
        "/api/v1/careguard/cabinet/items",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "drug_name": "Aspirin",
            "brand_name": "Aspirin Cardio",
            "manufacturer": "Bayer",
            "source": "manual",
        },
    )
    assert create.status_code == 200
    item_id = create.json()["id"]
    legacy_item = _db_item(item_id)
    assert legacy_item.brand_name is None
    assert legacy_item.note.startswith(_ITEM_NOTE_META_PREFIX)

    # ...then flip the flag on and read: brand/manufacturer still decode from the
    # legacy note with no data loss (Req 1.4).
    set_flags(selfmed_cabinet_structured_fields_enabled=True)
    read = client.get(
        "/api/v1/careguard/cabinet",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert read.status_code == 200
    items = {item["id"]: item for item in read.json()["items"]}
    assert items[item_id]["brand_name"] == "Aspirin Cardio"
    assert items[item_id]["manufacturer"] == "Bayer"


def test_structured_column_takes_precedence_on_read(set_flags) -> None:
    set_flags(selfmed_cabinet_structured_fields_enabled=True)
    token = _login("dual-read-precedence@example.com")
    create = client.post(
        "/api/v1/careguard/cabinet/items",
        headers={"Authorization": f"Bearer {token}"},
        json={"drug_name": "Ibuprofen", "brand_name": "Advil", "source": "manual"},
    )
    assert create.status_code == 200
    item_id = create.json()["id"]

    update = client.patch(
        f"/api/v1/careguard/cabinet/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"manufacturer": "Pfizer"},
    )
    assert update.status_code == 200
    body = update.json()
    assert body["brand_name"] == "Advil"
    assert body["manufacturer"] == "Pfizer"

    item = _db_item(item_id)
    assert item.brand_name == "Advil"
    assert item.manufacturer == "Pfizer"
    assert _ITEM_NOTE_META_PREFIX not in (item.note or "")
