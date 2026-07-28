"""Durable, owner-isolated research upload store (R2).

``ResearchUploadStore`` persists uploaded research files in durable storage so
they survive a process restart and are visible to every worker through the
shared database. Two content backends are supported, selected purely by
configuration:

- ``db``     - file bytes are inlined in ``research_uploaded_files.raw_bytes``.
               Survives restart and is visible to all workers via the shared DB
               (R2.1, R2.2, R2.5).
- ``object`` - file bytes live in an S3-compatible / filesystem object store
               addressed by ``RESEARCH_UPLOAD_OBJECT_STORE_URL``. The DB row
               keeps metadata + extracted text and a ``storage_ref`` object key.

The store keeps the existing extraction / OCR-bridge result verbatim: callers
pass the already-extracted ``text`` plus the ``ocr_bridge_kind`` produced by the
existing ``_extract_basic_text`` upload path, so the retrieval-facing document
shape is identical regardless of which backend stored the bytes (R2.6).

When the configured backend is unavailable while durable uploads are enabled,
the store raises :class:`ResearchUploadStoreUnavailable` so the API can surface
a ``503`` rather than silently losing data (R2.5 - no silent data loss).

Owner isolation (R2.3, R2.4): every stored record carries the uploader's
``owner_user_id``. Resolving a file as a different user raises
:class:`ResearchUploadAuthorizationError` and the content is never returned.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from clara_api.db.models import ResearchUploadedFile

# Mirror the upload endpoint's preview budget so previews are byte-identical
# whether a file flows through the in-memory fallback or the durable store.
_PREVIEW_CHAR_LIMIT = 500
_OBJECT_KEY_PREFIX = "research-uploads"


class ResearchUploadStoreError(Exception):
    """Base class for durable-upload store failures."""


class ResearchUploadNotFoundError(ResearchUploadStoreError):
    """Raised when no uploaded file exists for the requested ``file_id``."""


class ResearchUploadAuthorizationError(ResearchUploadStoreError):
    """Raised when a requester does not own the referenced uploaded file (R2.4)."""


class ResearchUploadStoreUnavailable(ResearchUploadStoreError):
    """Raised when the configured storage backend is unavailable (R2.5 - 503)."""


@dataclass(frozen=True)
class StoredUpload:
    """A resolved uploaded file with its content bytes materialized."""

    file_id: str
    owner_user_id: int
    filename: str
    content_type: str
    size: int
    storage_kind: str
    storage_ref: str | None
    raw_bytes: bytes
    extracted_text: str
    preview: str
    token_count: int
    ocr_bridge_kind: str
    created_at: datetime | None

    def as_document(self) -> dict[str, Any]:
        """Return the document shape consumed by ``_build_uploaded_documents``.

        Matches the legacy in-memory dict shape so downstream job building is
        unchanged when the durable store is enabled (R2.6, back-compat).
        """

        created = self.created_at.isoformat() if isinstance(self.created_at, datetime) else None
        return {
            "file_id": self.file_id,
            "filename": self.filename,
            "content_type": self.content_type,
            "size": self.size,
            "created_at": created,
            "text": self.extracted_text,
            "preview": self.preview,
            "token_count": self.token_count,
        }


@runtime_checkable
class ObjectStoreClient(Protocol):
    """Minimal object-store contract used by the ``object`` backend."""

    def put_object(self, key: str, data: bytes) -> None: ...

    def get_object(self, key: str) -> bytes: ...

    def delete_object(self, key: str) -> None: ...


class _FilesystemObjectStore:
    """Filesystem-backed object store for ``file://`` URLs.

    Used for local development and tests; bytes are written under ``root`` keyed
    by the object key. A missing object surfaces as a store-unavailable error so
    callers never observe silent data loss.
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    def _path_for(self, key: str) -> Path:
        # Keep the key relative; reject traversal outside the configured root.
        relative = Path(key.lstrip("/"))
        resolved = (self._root / relative).resolve()
        root_resolved = self._root.resolve()
        if root_resolved not in resolved.parents and resolved != root_resolved:
            raise ResearchUploadStoreUnavailable(
                "Resolved object key escapes the configured object-store root"
            )
        return resolved

    def put_object(self, key: str, data: bytes) -> None:
        path = self._path_for(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except OSError as exc:  # pragma: no cover - filesystem failure path
            raise ResearchUploadStoreUnavailable(
                f"Filesystem object store write failed: {exc.__class__.__name__}"
            ) from exc

    def get_object(self, key: str) -> bytes:
        path = self._path_for(key)
        if not path.is_file():
            raise ResearchUploadStoreUnavailable(
                "Object store entry is missing for the requested file"
            )
        try:
            return path.read_bytes()
        except OSError as exc:  # pragma: no cover - filesystem failure path
            raise ResearchUploadStoreUnavailable(
                f"Filesystem object store read failed: {exc.__class__.__name__}"
            ) from exc

    def delete_object(self, key: str) -> None:
        path = self._path_for(key)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:  # pragma: no cover - filesystem failure path
            raise ResearchUploadStoreUnavailable(
                f"Filesystem object store delete failed: {exc.__class__.__name__}"
            ) from exc


class _S3ObjectStore:
    """S3-compatible object store backed by ``boto3`` (lazy import).

    Supports ``s3://bucket/optional/prefix`` and S3-compatible endpoints via
    ``http(s)://host/bucket/optional/prefix``. If ``boto3`` is unavailable or the
    client cannot be constructed, construction raises
    :class:`ResearchUploadStoreUnavailable` (surfaced as ``503``).
    """

    def __init__(self, url: str) -> None:
        parsed = urlparse(url)
        scheme = (parsed.scheme or "").lower()
        try:
            import boto3
        except Exception as exc:  # pragma: no cover - depends on optional dep
            raise ResearchUploadStoreUnavailable(
                "Object store backend configured but the S3 client (boto3) is not installed"
            ) from exc

        path_parts = [part for part in (parsed.path or "").split("/") if part]
        if scheme == "s3":
            if not parsed.netloc:
                raise ResearchUploadStoreUnavailable("s3:// object store URL is missing a bucket")
            self._bucket = parsed.netloc
            self._prefix = "/".join(path_parts)
            endpoint_url = os.getenv("RESEARCH_UPLOAD_OBJECT_STORE_ENDPOINT") or None
        else:  # http / https endpoint: first path segment is the bucket
            if not path_parts:
                raise ResearchUploadStoreUnavailable(
                    "object store endpoint URL is missing a bucket path segment"
                )
            self._bucket = path_parts[0]
            self._prefix = "/".join(path_parts[1:])
            endpoint_url = f"{scheme}://{parsed.netloc}"

        try:
            self._client = boto3.client("s3", endpoint_url=endpoint_url)
        except Exception as exc:  # pragma: no cover - depends on optional dep
            raise ResearchUploadStoreUnavailable(
                f"Failed to construct the S3 object-store client: {exc.__class__.__name__}"
            ) from exc

    def _full_key(self, key: str) -> str:
        return f"{self._prefix}/{key}" if self._prefix else key

    def put_object(self, key: str, data: bytes) -> None:
        try:
            self._client.put_object(Bucket=self._bucket, Key=self._full_key(key), Body=data)
        except Exception as exc:  # pragma: no cover - depends on optional dep
            raise ResearchUploadStoreUnavailable(
                f"Object store write failed: {exc.__class__.__name__}"
            ) from exc

    def get_object(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=self._full_key(key))
            return bytes(response["Body"].read())
        except Exception as exc:  # pragma: no cover - depends on optional dep
            raise ResearchUploadStoreUnavailable(
                f"Object store read failed: {exc.__class__.__name__}"
            ) from exc

    def delete_object(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=self._full_key(key))
        except Exception as exc:  # pragma: no cover - depends on optional dep
            raise ResearchUploadStoreUnavailable(
                f"Object store delete failed: {exc.__class__.__name__}"
            ) from exc


def build_object_store_client(url: str) -> ObjectStoreClient:
    cleaned = (url or "").strip()
    if not cleaned:
        raise ResearchUploadStoreUnavailable("Object store backend selected but no URL configured")

    parsed = urlparse(cleaned)
    scheme = (parsed.scheme or "").lower()
    if scheme == "file":
        return _FilesystemObjectStore(Path(parsed.path or "/"))
    if scheme in {"s3", "http", "https"}:
        return _S3ObjectStore(cleaned)
    raise ResearchUploadStoreUnavailable(
        f"Unsupported object store URL scheme: {scheme or '(none)'}"
    )


class ResearchUploadStore:
    """Durable upload store with selectable ``db`` and ``object`` backends.

    The backend is ``object`` when an object-store URL is configured, otherwise
    ``db`` (bytes inlined in the row). A single store instance is bound to a DB
    session; constructing a new instance against the same database simulates a
    process restart or a different worker.
    """

    def __init__(self, db: Session, *, object_store_url: str | None = None) -> None:
        self._db = db
        self._object_store_url = (object_store_url or "").strip()
        self._object_client: ObjectStoreClient | None = None

    @property
    def backend(self) -> str:
        return "object" if self._object_store_url else "db"

    def _client(self) -> ObjectStoreClient:
        if self._object_client is None:
            self._object_client = build_object_store_client(self._object_store_url)
        return self._object_client

    @staticmethod
    def _object_key(owner_user_id: int, file_id: str) -> str:
        return f"{_OBJECT_KEY_PREFIX}/{int(owner_user_id)}/{file_id}"

    def put(
        self,
        owner_user_id: int,
        data: bytes,
        text: str,
        meta: dict[str, Any] | None = None,
    ) -> StoredUpload:
        """Persist an uploaded file and return its stored representation.

        ``data`` is the raw file bytes, ``text`` the already-extracted text from
        the existing ``_extract_basic_text`` path, and ``meta`` carries the
        upload metadata (``filename``, ``content_type``, ``size``, ``preview``,
        ``token_count``, ``ocr_bridge_kind`` and optionally a pre-chosen
        ``file_id``).
        """

        meta = dict(meta or {})
        owner_id = int(owner_user_id)
        file_id = str(meta.get("file_id") or uuid4())
        filename = str(meta.get("filename") or "uploaded-file")
        content_type = str(meta.get("content_type") or "application/octet-stream")
        data = bytes(data or b"")
        text = text or ""
        raw_size = meta.get("size")
        size = int(raw_size) if raw_size is not None else len(data)
        if meta.get("preview") is not None:
            preview = str(meta["preview"])
        else:
            preview = text[:_PREVIEW_CHAR_LIMIT]
        token_count = int(meta.get("token_count") or 0)
        ocr_bridge_kind = str(meta.get("ocr_bridge_kind") or "")

        backend = self.backend
        storage_ref: str | None = None
        raw_bytes: bytes | None = None
        if backend == "object":
            storage_ref = self._object_key(owner_id, file_id)
            # _client() raises ResearchUploadStoreUnavailable when the backend
            # cannot be reached, so an enabled-but-broken object store surfaces
            # a 503 instead of silently dropping the upload.
            self._client().put_object(storage_ref, data)
        else:
            raw_bytes = data

        record = ResearchUploadedFile(
            file_id=file_id,
            owner_user_id=owner_id,
            filename=filename,
            content_type=content_type,
            size=size,
            storage_kind=backend,
            storage_ref=storage_ref,
            raw_bytes=raw_bytes,
            extracted_text=text,
            preview=preview,
            token_count=token_count,
            ocr_bridge_kind=ocr_bridge_kind,
        )
        self._db.add(record)
        self._db.commit()
        self._db.refresh(record)
        return self._to_stored(record, data)

    def get(self, file_id: str, owner_user_id: int) -> StoredUpload:
        """Resolve an uploaded file by ``file_id`` enforcing owner isolation.

        Raises :class:`ResearchUploadNotFoundError` when the id is unknown,
        :class:`ResearchUploadAuthorizationError` when the requester is not the
        owner (R2.4), and :class:`ResearchUploadStoreUnavailable` when the
        backend cannot return the bytes (R2.5).
        """

        record = self._db.execute(
            select(ResearchUploadedFile).where(ResearchUploadedFile.file_id == str(file_id))
        ).scalar_one_or_none()
        if record is None:
            raise ResearchUploadNotFoundError(f"No uploaded file for file_id={file_id!r}")
        if int(record.owner_user_id) != int(owner_user_id):
            raise ResearchUploadAuthorizationError(
                "Requesting user does not own the referenced uploaded file"
            )

        data = self._load_bytes(record)
        return self._to_stored(record, data)

    def _load_bytes(self, record: ResearchUploadedFile) -> bytes:
        if record.storage_kind == "object":
            if not record.storage_ref:
                raise ResearchUploadStoreUnavailable(
                    "Object-backed upload is missing its storage reference"
                )
            return self._client().get_object(record.storage_ref)
        return bytes(record.raw_bytes or b"")

    @staticmethod
    def _to_stored(record: ResearchUploadedFile, data: bytes) -> StoredUpload:
        return StoredUpload(
            file_id=record.file_id,
            owner_user_id=int(record.owner_user_id),
            filename=record.filename,
            content_type=record.content_type,
            size=int(record.size or 0),
            storage_kind=record.storage_kind,
            storage_ref=record.storage_ref,
            raw_bytes=bytes(data or b""),
            extracted_text=record.extracted_text or "",
            preview=record.preview or "",
            token_count=int(record.token_count or 0),
            ocr_bridge_kind=record.ocr_bridge_kind or "",
            created_at=record.created_at,
        )
