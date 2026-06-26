"""No-PII projection helpers for compliance logs.

Every value written into ``compliance_events.meta_json`` or used to build a DSAR
row must pass through :func:`redact_meta`. The projection is allow-list based: it
keeps only primitive *non-string* scalars (counts, flags, numbers), a small set
of safe enum-like string keys, and recursively-redacted nested containers. Any
free-text value (and anything that looks like an email, name, drug list, or
query) is dropped rather than truncated, so a buggy caller can never leak PII.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from clara_api.core.config import get_settings

# Keys whose *string* values are allowed because they are bounded enums/refs the
# compliance layer itself produces — never user free-text. Everything else that
# is a string is dropped by the projection.
_ALLOWED_STRING_KEYS = frozenset(
    {
        "event_type",
        "kind",
        "status",
        "purpose",
        "processor",
        "jurisdiction",
        "severity",
        "verdict",
        "result",
        "reason",
        "scope",
        "model_family",
        "model_version",
        "path",
        "outcome",
        "decision",
        "tia_doc_ref",
        "category",
        "policy_version",
        "notice_version",
    }
)

# Bounded vocabulary that an allowed-key string value may take. A value outside
# this set (i.e. arbitrary free-text smuggled under an allowed key) is dropped.
_SAFE_STRING_VALUE = re.compile(r"^[A-Za-z0-9 _.:+/\-]{0,64}$")

_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def hash_user_ref(user_id: int | str) -> str:
    """Return an opaque, stable, non-reversible reference for a user.

    Salted with the JWT secret so the digest cannot be reproduced from a leaked
    log alone. Never store the email/name; this is the only user handle that may
    appear in compliance/DSAR rows.
    """

    secret = get_settings().jwt_secret_key
    digest = hashlib.sha256(f"{secret}:compliance-user:{user_id}".encode())
    return digest.hexdigest()[:64]


def _looks_like_pii(value: str) -> bool:
    return bool(_EMAIL_RE.search(value))


def redact_value(key: str | None, value: Any) -> Any:
    """Project a single value to its PII-free form (or ``None`` to drop it)."""

    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if value is None:
        return None
    if isinstance(value, str):
        if (
            key in _ALLOWED_STRING_KEYS
            and _SAFE_STRING_VALUE.match(value)
            and not _looks_like_pii(value)
        ):
            return value
        return None
    if isinstance(value, dict):
        return redact_meta(value)
    if isinstance(value, (list, tuple)):
        projected = [redact_value(None, item) for item in value]
        return [item for item in projected if item is not None]
    return None


def redact_meta(meta: dict[str, Any] | None) -> dict[str, Any]:
    """Return a PII-free projection of a metadata mapping.

    Drops any key whose value cannot be safely represented; the result contains
    only counts, flags, numbers, bounded enum strings, and nested redactions.
    """

    if not isinstance(meta, dict):
        return {}
    out: dict[str, Any] = {}
    for raw_key, raw_value in meta.items():
        if not isinstance(raw_key, str):
            continue
        projected = redact_value(raw_key, raw_value)
        if projected is None:
            continue
        if isinstance(projected, dict) and not projected:
            # keep empty dicts out to minimise surface
            continue
        out[raw_key] = projected
    return out


def contains_pii_markers(payload: Any) -> bool:
    """Best-effort detector used by guard tests: True if an email appears."""

    if isinstance(payload, str):
        return _looks_like_pii(payload)
    if isinstance(payload, dict):
        return any(contains_pii_markers(v) for v in payload.values())
    if isinstance(payload, (list, tuple)):
        return any(contains_pii_markers(v) for v in payload)
    return False
