"""CLARA API v2 Architecture Conventions.

Defines unified envelopes, cursor pagination, optimistic concurrency / ETag
preconditions, idempotency helpers, and localized message metadata.
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Sequence
from typing import Any, Generic, Literal, TypeVar

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class MessageMetadata(BaseModel):
    """Metadata for localized user messages, warnings, and targeted actions."""

    model_config = ConfigDict(extra="ignore")

    key: str = Field(
        ...,
        description="Localization or catalog key (e.g. 'errors.item_not_found')",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Typed parameters for string interpolation",
    )
    severity: Literal["info", "success", "warning", "error", "critical"] | str = Field(
        default="info",
        description="Severity level for client presentation",
    )
    action_target: str | None = Field(
        default=None,
        description="Optional target identifier, field name, or URI for the UI action",
    )


class ApiV2ResponseEnvelope(BaseModel, Generic[T]):
    """Standardized response envelope for all API v2 endpoints."""

    model_config = ConfigDict(extra="ignore")

    data: T = Field(description="Payload data")
    meta: dict[str, Any] | None = Field(
        default=None,
        description="Response metadata (e.g. timestamp, request ID, server version)",
    )
    message: MessageMetadata | None = Field(
        default=None,
        description="Primary message metadata if applicable",
    )
    warnings: list[MessageMetadata] = Field(
        default_factory=list,
        description="Non-fatal warnings or advisories",
    )

    @classmethod
    def wrap(
        cls,
        data: T,
        *,
        meta: dict[str, Any] | None = None,
        message: MessageMetadata | None = None,
        warnings: list[MessageMetadata] | None = None,
    ) -> ApiV2ResponseEnvelope[T]:
        """Convenience constructor to wrap payload into ApiV2ResponseEnvelope."""
        return cls(
            data=data,
            meta=meta,
            message=message,
            warnings=warnings or [],
        )


class ApiV2ErrorEnvelope(BaseModel):
    """Standardized error envelope for API v2 error responses."""

    model_config = ConfigDict(extra="ignore")

    code: str = Field(
        ...,
        description="Machine-readable code (e.g. 'state_conflict', 'unauthorized')",
    )
    message_key: str | None = Field(
        default=None,
        description="Localization key for UI client display",
    )
    message: str = Field(
        ...,
        description="Human-readable fallback error explanation",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Interpolation parameters for UI translation",
    )
    details: Any = Field(
        default=None,
        description="Granular error details (e.g. field errors, trace hint)",
    )
    safe_to_reapply: bool = Field(
        default=False,
        description="Whether safe for client to reapply automatically without user review",
    )
    current_version: str | int | None = Field(
        default=None,
        description="Current resource version/ETag if this was a concurrency/state conflict",
    )
    changed_fields: list[str] = Field(
        default_factory=list,
        description="Fields that were modified upstream during a conflict",
    )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)

    def as_response(self, status_code: int = status.HTTP_400_BAD_REQUEST) -> JSONResponse:
        return JSONResponse(status_code=status_code, content=self.to_dict())

    def as_exception(
        self,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        headers: dict[str, str] | None = None,
    ) -> ApiV2HTTPException:
        return ApiV2HTTPException(
            status_code=status_code,
            error=self,
            headers=headers,
        )


class ApiV2HTTPException(HTTPException):
    """FastAPI HTTPException carrying an ApiV2ErrorEnvelope."""

    def __init__(
        self,
        status_code: int,
        error: ApiV2ErrorEnvelope | None = None,
        *,
        code: str = "bad_request",
        message: str = "Bad Request",
        message_key: str | None = None,
        params: dict[str, Any] | None = None,
        details: Any = None,
        safe_to_reapply: bool = False,
        current_version: str | int | None = None,
        changed_fields: list[str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        if error is None:
            error = ApiV2ErrorEnvelope(
                code=code,
                message=message,
                message_key=message_key,
                params=params or {},
                details=details,
                safe_to_reapply=safe_to_reapply,
                current_version=current_version,
                changed_fields=changed_fields or [],
            )
        self.error = error
        super().__init__(
            status_code=status_code,
            detail=error.model_dump(exclude_none=True),
            headers=headers,
        )


class CursorPaginationParams(BaseModel):
    """Cursor-based pagination query parameters and codec helpers."""

    model_config = ConfigDict(extra="ignore")

    cursor: str | None = Field(
        default=None,
        description="Opaque cursor token for the requested page",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of items to return (1-100)",
    )
    direction: Literal["forward", "backward"] | str = Field(
        default="forward",
        description="Pagination direction",
    )

    @staticmethod
    def encode_cursor(data: dict[str, Any] | str | int | float) -> str:
        """Encode arbitrary cursor payload into URL-safe base64 string."""
        if isinstance(data, (dict, list)):
            raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        else:
            raw = json.dumps({"v": data}, separators=(",", ":"))
        return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")

    @staticmethod
    def decode_cursor(cursor: str | None) -> dict[str, Any] | None:
        """Safely decode an opaque URL-safe base64 cursor token.

        Raises ApiV2HTTPException(422) if cursor is corrupt or non-base64.
        """
        if not cursor or not cursor.strip():
            return None
        token = cursor.strip()
        padding = 4 - (len(token) % 4)
        if padding != 4:
            token += "=" * padding
        try:
            raw_bytes = base64.urlsafe_b64decode(token)
            payload = json.loads(raw_bytes.decode("utf-8"))
            if isinstance(payload, dict):
                return payload
            return {"v": payload}
        except Exception as exc:
            raise ApiV2HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="invalid_cursor",
                message="Invalid pagination cursor token",
                message_key="errors.invalid_cursor",
                details=str(exc),
            ) from exc


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard generic cursor-paginated response structure."""

    model_config = ConfigDict(extra="ignore")

    items: list[T] = Field(
        default_factory=list,
        description="List of records in the current page",
    )
    next_cursor: str | None = Field(
        default=None,
        description="Opaque cursor token for the next page",
    )
    prev_cursor: str | None = Field(
        default=None,
        description="Opaque cursor token for the previous page",
    )
    has_more: bool = Field(
        default=False,
        description="Whether more items exist in the pagination direction",
    )
    total_count: int | None = Field(
        default=None,
        description="Total items count if available",
    )

    @classmethod
    def create(
        cls,
        items: Sequence[T],
        *,
        next_cursor: str | None = None,
        prev_cursor: str | None = None,
        has_more: bool = False,
        total_count: int | None = None,
    ) -> PaginatedResponse[T]:
        """Convenience constructor for PaginatedResponse."""
        item_list = list(items)
        return cls(
            items=item_list,
            next_cursor=next_cursor,
            prev_cursor=prev_cursor,
            has_more=has_more or bool(next_cursor),
            total_count=total_count,
        )


class BaseVersionPrecondition:
    """ETag / If-Match and base_version concurrency preconditions helper."""

    @staticmethod
    def format_etag(version: int | str, *, weak: bool = False) -> str:
        """Format a version value into a standard HTTP ETag header string."""
        clean = str(version).strip().strip('"')
        prefix = "W/" if weak else ""
        return f'{prefix}"{clean}"'

    @staticmethod
    def parse_etag(etag: str | None) -> str | None:
        """Parse and normalize an ETag string to its raw version value."""
        if etag is None:
            return None
        candidate = etag.strip()
        if candidate.startswith("W/"):
            candidate = candidate[2:].strip()
        return candidate.strip('"').strip() or None

    @classmethod
    def validate_precondition(
        cls,
        if_match: str | None,
        current_version: int | str,
        *,
        allow_none: bool = True,
        changed_fields: list[str] | None = None,
        status_code: int = status.HTTP_412_PRECONDITION_FAILED,
    ) -> None:
        """Validate an HTTP If-Match header against the resource's current version."""
        if if_match is None or not if_match.strip():
            if not allow_none:
                raise ApiV2HTTPException(
                    status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                    code="precondition_required",
                    message="An If-Match header or base_version is required for this operation",
                    message_key="errors.precondition_required",
                )
            return

        parsed = cls.parse_etag(if_match)
        if parsed is None:
            raise ApiV2HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="invalid_if_match",
                message="Malformed If-Match header value",
                message_key="errors.invalid_if_match",
            )

        if parsed == "*":
            # Wildcard "*" matches any existing version
            return

        if str(parsed) != str(current_version):
            raise ApiV2HTTPException(
                status_code=status_code,
                code="state_conflict",
                message="Resource state has changed since base version was read",
                message_key="errors.state_conflict",
                current_version=str(current_version),
                changed_fields=changed_fields or [],
                safe_to_reapply=False,
                details={
                    "expected_version": parsed,
                    "current_version": str(current_version),
                    "changed_fields": changed_fields or [],
                },
            )

    @classmethod
    def validate_base_version(
        cls,
        base_version: int | str | None,
        current_version: int | str,
        *,
        allow_none: bool = True,
        changed_fields: list[str] | None = None,
        status_code: int = status.HTTP_409_CONFLICT,
    ) -> None:
        """Validate a body base_version field against current resource version."""
        if base_version is None:
            if not allow_none:
                raise ApiV2HTTPException(
                    status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                    code="base_version_required",
                    message="A base_version is required for this operation",
                    message_key="errors.base_version_required",
                )
            return

        if str(base_version).strip() != str(current_version).strip():
            raise ApiV2HTTPException(
                status_code=status_code,
                code="state_conflict",
                message="State conflict: base_version does not match current resource version",
                message_key="errors.state_conflict",
                current_version=str(current_version),
                changed_fields=changed_fields or [],
                safe_to_reapply=False,
                details={
                    "base_version": str(base_version),
                    "current_version": str(current_version),
                    "changed_fields": changed_fields or [],
                },
            )


class IdempotencyKeyHelper:
    """Helper for Idempotency-Key validation, hashing, and conflict detection."""

    MIN_KEY_LENGTH = 1
    MAX_KEY_LENGTH = 128

    @classmethod
    def validate_key(
        cls,
        key: str | None,
        *,
        min_length: int = MIN_KEY_LENGTH,
        max_length: int = MAX_KEY_LENGTH,
        required: bool = True,
    ) -> str | None:
        """Validate that idempotency key satisfies length bounds and is clean."""
        if key is None or not key.strip():
            if required:
                raise ApiV2HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    code="missing_idempotency_key",
                    message="An Idempotency-Key header is required for this operation",
                    message_key="errors.missing_idempotency_key",
                )
            return None

        clean = key.strip()
        if len(clean) < min_length or len(clean) > max_length:
            raise ApiV2HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                code="invalid_idempotency_key",
                message=f"Idempotency-Key must be between {min_length} and {max_length} characters",
                message_key="errors.invalid_idempotency_key",
                params={"min_length": min_length, "max_length": max_length},
            )
        return clean

    @staticmethod
    def compute_key_hash(key: str) -> str:
        """Compute deterministic SHA-256 hash of the idempotency key."""
        clean = key.strip()
        return hashlib.sha256(clean.encode("utf-8")).hexdigest()

    @staticmethod
    def compute_request_digest(
        payload: Any,
        *,
        method: str = "",
        path: str = "",
        extra_context: dict[str, Any] | None = None,
    ) -> str:
        """Compute deterministic SHA-256 hash of canonical JSON request payload."""
        envelope: dict[str, Any] = {
            "payload": payload,
        }
        if method:
            envelope["method"] = method.upper()
        if path:
            envelope["path"] = path
        if extra_context:
            envelope["context"] = extra_context

        canonical = json.dumps(
            envelope,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def check_digest_conflict(
        cls,
        stored_digest: str,
        incoming_digest: str,
    ) -> None:
        """Raise 409 Conflict if idempotency key was previously used with different body."""
        if stored_digest != incoming_digest:
            raise ApiV2HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                code="idempotency_conflict",
                message="Idempotency-Key was already used with a different request payload",
                message_key="errors.idempotency_conflict",
                safe_to_reapply=False,
            )
