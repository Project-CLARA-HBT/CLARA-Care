"""Session-security helper for refresh rotation, token denylist, and reuse events.

This module is part of the ``clara-platform-hardening`` spec (Requirement 2 —
Authentication and session hardening). It is purely additive and gated behind
the ``HARDENING_*`` feature flags: with both flags off every method is a
behavior-preserving no-op, so the authentication flow is byte-for-byte
equivalent to the pre-hardening baseline (Requirements 2.7, 11.1, 11.2).

The helper reuses the existing :class:`RedisSecurityStore` backend (the same
best-effort, fail-open Redis pattern used by ``LoginGuard``) rather than
introducing a new control path. All persisted state is opaque and contains
**no PII**: token identifiers are stored only as SHA-256 digests, and the
reuse-detection event records counts and hashed references — never names,
emails, query text, or any user-identifying free text.

Redis key layout (prefix from ``settings.security_redis_key_prefix``):

==========================================  =======  ============================
key                                         value    TTL
==========================================  =======  ============================
``<prefix>:jti:deny:<sha256(jti)>``         ``1``    token remaining lifetime
``<prefix>:refresh:rot:<sha256(jti)>``      ``1``    refresh-token lifetime
``<prefix>:reuse``                          counter  refresh-token lifetime
==========================================  =======  ============================

Design reference: design.md §B (SessionSecurity), Properties 4–6.
"""

from __future__ import annotations

import hashlib
import logging

from clara_api.core.config import get_settings
from clara_api.core.redis_security_store import RedisSecurityStore
from clara_api.core.security import create_refresh_token, decode_refresh_token

logger = logging.getLogger(__name__)


class SessionSecurity:
    """Refresh-token rotation, ``jti`` denylist, and no-PII reuse detection.

    The two behaviors are gated independently:

    * Refresh rotation (:meth:`rotate_refresh`, :meth:`is_refresh_reused`) is
      gated by ``HARDENING_REFRESH_ROTATION_ENABLED``.
    * The logout/revocation denylist (:meth:`revoke`, :meth:`is_revoked`) is
      gated by ``HARDENING_TOKEN_DENYLIST_ENABLED``.

    When a flag is off the corresponding methods are no-ops (writes are skipped;
    membership checks return ``False``), preserving current behavior.
    """

    def __init__(self, store: RedisSecurityStore | None = None) -> None:
        self._redis = store if store is not None else RedisSecurityStore()

    # -- internal helpers -------------------------------------------------

    @staticmethod
    def _digest(jti: str) -> str:
        """Return an opaque SHA-256 digest of a token id (no PII is stored)."""
        return hashlib.sha256(jti.encode("utf-8")).hexdigest()

    def _key(self, suffix: str, jti: str) -> str:
        settings = get_settings()
        return f"{settings.security_redis_key_prefix}:{suffix}:{self._digest(jti)}"

    @staticmethod
    def _refresh_ttl_seconds() -> int:
        """Conservative TTL bound for refresh-derived markers (full lifetime)."""
        settings = get_settings()
        return max(1, int(settings.jwt_refresh_minutes) * 60)

    @staticmethod
    def _refresh_rotation_enabled() -> bool:
        return bool(get_settings().hardening_refresh_rotation_enabled)

    @staticmethod
    def _denylist_enabled() -> bool:
        return bool(get_settings().hardening_token_denylist_enabled)

    # -- refresh rotation (Requirements 2.2, 2.3) -------------------------

    def rotate_refresh(
        self,
        old_jti: str,
        subject: str,
        role: str,
        *,
        old_ttl_seconds: int | None = None,
    ) -> tuple[str, str]:
        """Invalidate ``old_jti`` and mint a fresh refresh token.

        Returns ``(new_refresh_token, new_jti)``. When refresh rotation is
        disabled this still issues a new refresh token but does **not**
        invalidate the presented one, preserving the current non-rotating
        flow (the prior token remains valid until natural expiry).

        The old token is invalidated two ways so reuse can be detected even if
        only one flag is enabled: a rotation marker (consulted by
        :meth:`is_refresh_reused`) and a denylist entry (consulted by
        :meth:`is_revoked`).
        """
        new_refresh = create_refresh_token(subject, role)
        new_jti = str(decode_refresh_token(new_refresh).get("jti", ""))

        if not self._refresh_rotation_enabled():
            return new_refresh, new_jti

        ttl = (
            old_ttl_seconds
            if old_ttl_seconds and old_ttl_seconds > 0
            else self._refresh_ttl_seconds()
        )
        # Rotation marker — lets reuse detection work even when the denylist
        # flag is off (gated by the refresh-rotation flag only).
        self._redis.set_lock(self._key("refresh:rot", old_jti), ttl_seconds=ttl)
        # Also deny the old jti so token resolution rejects it when the
        # denylist flag is on.
        self._redis.set_lock(self._key("jti:deny", old_jti), ttl_seconds=ttl)
        return new_refresh, new_jti

    def is_refresh_reused(self, jti: str) -> bool:
        """Return ``True`` when ``jti`` was already rotated (a replayed token).

        Gated by ``HARDENING_REFRESH_ROTATION_ENABLED``; returns ``False`` when
        the flag is off or the backend is unavailable (fail-open for
        availability, matching the existing security-store pattern).
        """
        if not self._refresh_rotation_enabled():
            return False
        ttl = self._redis.get_ttl(self._key("refresh:rot", jti))
        return bool(ttl is not None and ttl > 0)

    # -- denylist / logout revocation (Requirement 2.4) -------------------

    def revoke(self, jti: str, ttl_seconds: int) -> None:
        """Add ``jti`` to the denylist for ``ttl_seconds`` (the token's TTL).

        No-op when the denylist flag is off. ``ttl_seconds`` should be the
        token's remaining lifetime so the entry expires at natural expiry.
        """
        if not self._denylist_enabled():
            return
        self._redis.set_lock(self._key("jti:deny", jti), ttl_seconds=max(1, ttl_seconds))

    def is_revoked(self, jti: str) -> bool:
        """Return ``True`` when ``jti`` is denylisted (revoked or rotated).

        Gated by ``HARDENING_TOKEN_DENYLIST_ENABLED``; returns ``False`` when
        the flag is off or the backend is unavailable (fail-open).
        """
        if not self._denylist_enabled():
            return False
        ttl = self._redis.get_ttl(self._key("jti:deny", jti))
        return bool(ttl is not None and ttl > 0)

    # -- reuse detection event (Requirement 2.3) --------------------------

    def record_reuse(self, jti: str) -> None:
        """Record a no-PII reuse-detection event for a replayed token.

        Stores only an aggregate counter and logs an opaque hashed reference;
        no names, emails, or free text are ever emitted.
        """
        settings = get_settings()
        counter_key = f"{settings.security_redis_key_prefix}:reuse"
        result = self._redis.incr_with_ttl(counter_key, ttl_seconds=self._refresh_ttl_seconds())
        total = result[0] if result is not None else None
        logger.warning(
            "refresh_token_reuse_detected",
            extra={
                "event": "refresh_token_reuse_detected",
                "jti_digest": self._digest(jti),
                "reuse_count": total,
            },
        )


# Module-level singleton mirroring the ``login_guard`` convention.
session_security = SessionSecurity()
