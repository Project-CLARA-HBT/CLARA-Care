"""Unit tests for the durable, owner-isolated ResearchUploadStore (R2).

Covers the db and object content backends, durability across a fresh store
instance (simulated restart / different worker), owner isolation, and the
fail-loud (no silent data loss) behavior when a backend is unavailable.

These are example/edge unit tests; the universal round-trip and owner-isolation
properties (Property 4 / Property 5) are authored separately as PBT tasks 3.4
and 3.5.
"""

from __future__ import annotations

import uuid

import pytest

from clara_api.core.research_upload_store import (
    ResearchUploadAuthorizationError,
    ResearchUploadNotFoundError,
    ResearchUploadStore,
    ResearchUploadStoreUnavailable,
)
from clara_api.db.models import User
from clara_api.db.session import SessionLocal


def _make_user(email: str, role: str = "researcher") -> int:
    with SessionLocal() as db:
        user = User(email=email, hashed_password="x", role=role, full_name="T")
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id


def _meta(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "filename": "notes.txt",
        "content_type": "text/plain",
        "ocr_bridge_kind": "text",
        "token_count": 3,
    }
    base.update(overrides)
    return base


# --- db backend round-trip (R2.1, R2.2, R2.6) -------------------------------


def test_db_backend_put_then_get_round_trip() -> None:
    owner = _make_user(f"store-db-{uuid.uuid4()}@example.com")
    data = "Bệnh nhân tiểu đường type 2".encode()
    text = "Bệnh nhân tiểu đường type 2"

    with SessionLocal() as db:
        store = ResearchUploadStore(db)
        assert store.backend == "db"
        stored = store.put(owner, data, text, _meta(filename="dm.txt"))

    file_id = stored.file_id
    assert stored.storage_kind == "db"
    assert stored.raw_bytes == data
    assert stored.extracted_text == text
    assert stored.ocr_bridge_kind == "text"

    # Fresh store instance / session simulates a restart or another worker.
    with SessionLocal() as db:
        resolved = ResearchUploadStore(db).get(file_id, owner)

    assert resolved.raw_bytes == data
    assert resolved.extracted_text == text
    assert resolved.ocr_bridge_kind == "text"
    assert resolved.filename == "dm.txt"
    assert resolved.owner_user_id == owner


def test_as_document_shape_matches_legacy_dict() -> None:
    owner = _make_user(f"store-doc-{uuid.uuid4()}@example.com")
    with SessionLocal() as db:
        stored = ResearchUploadStore(db).put(
            owner, b"hello", "hello", _meta(preview="hello", token_count=1)
        )
    doc = stored.as_document()
    assert set(doc) == {
        "file_id",
        "filename",
        "content_type",
        "size",
        "created_at",
        "text",
        "preview",
        "token_count",
    }
    assert doc["text"] == "hello"
    assert doc["preview"] == "hello"
    assert doc["size"] == len(b"hello")


def test_preview_defaults_to_truncated_text() -> None:
    owner = _make_user(f"store-prev-{uuid.uuid4()}@example.com")
    long_text = "x" * 1000
    with SessionLocal() as db:
        stored = ResearchUploadStore(db).put(owner, long_text.encode(), long_text, _meta())
    assert stored.preview == "x" * 500


# --- owner isolation (R2.3, R2.4) -------------------------------------------


def test_get_by_non_owner_raises_authorization_error() -> None:
    owner = _make_user(f"store-owner-{uuid.uuid4()}@example.com")
    other = _make_user(f"store-other-{uuid.uuid4()}@example.com")
    with SessionLocal() as db:
        stored = ResearchUploadStore(db).put(owner, b"secret", "secret", _meta())

    with SessionLocal() as db:
        store = ResearchUploadStore(db)
        with pytest.raises(ResearchUploadAuthorizationError):
            store.get(stored.file_id, other)
        # Owner still resolves fine.
        assert store.get(stored.file_id, owner).owner_user_id == owner


def test_stored_owner_equals_uploader() -> None:
    owner = _make_user(f"store-uploader-{uuid.uuid4()}@example.com")
    with SessionLocal() as db:
        stored = ResearchUploadStore(db).put(owner, b"abc", "abc", _meta())
    assert stored.owner_user_id == owner


def test_get_unknown_file_id_raises_not_found() -> None:
    owner = _make_user(f"store-missing-{uuid.uuid4()}@example.com")
    with SessionLocal() as db:
        with pytest.raises(ResearchUploadNotFoundError):
            ResearchUploadStore(db).get("does-not-exist", owner)


# --- object backend round-trip (R2.1, R2.2, R2.5, R2.6) ---------------------


def test_object_backend_round_trip_filesystem(tmp_path) -> None:
    owner = _make_user(f"store-obj-{uuid.uuid4()}@example.com")
    object_url = f"file://{tmp_path}"
    data = b"object-stored-bytes"

    with SessionLocal() as db:
        store = ResearchUploadStore(db, object_store_url=object_url)
        assert store.backend == "object"
        stored = store.put(owner, data, "object text", _meta(filename="o.txt"))

    assert stored.storage_kind == "object"
    assert stored.storage_ref and stored.storage_ref.endswith(stored.file_id)
    # Bytes live in the object store, not inline in the row.
    assert any(tmp_path.rglob("*")), "expected object bytes written to filesystem store"

    with SessionLocal() as db:
        resolved = ResearchUploadStore(db, object_store_url=object_url).get(stored.file_id, owner)
    assert resolved.raw_bytes == data
    assert resolved.extracted_text == "object text"


def test_object_backend_missing_object_surfaces_unavailable(tmp_path) -> None:
    owner = _make_user(f"store-obj-miss-{uuid.uuid4()}@example.com")
    object_url = f"file://{tmp_path}"
    with SessionLocal() as db:
        stored = ResearchUploadStore(db, object_store_url=object_url).put(
            owner, b"data", "data", _meta()
        )

    # Delete the underlying object to simulate an unavailable / lost blob.
    for path in tmp_path.rglob("*"):
        if path.is_file():
            path.unlink()

    with SessionLocal() as db:
        store = ResearchUploadStore(db, object_store_url=object_url)
        with pytest.raises(ResearchUploadStoreUnavailable):
            store.get(stored.file_id, owner)


def test_unsupported_object_store_scheme_is_unavailable() -> None:
    owner = _make_user(f"store-bad-scheme-{uuid.uuid4()}@example.com")
    with SessionLocal() as db:
        store = ResearchUploadStore(db, object_store_url="ftp://example.com/bucket")
        with pytest.raises(ResearchUploadStoreUnavailable):
            store.put(owner, b"data", "data", _meta())
