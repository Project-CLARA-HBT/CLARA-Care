from __future__ import annotations

import logging
from typing import Any

from clara_api.core.config import get_settings

logger = logging.getLogger(__name__)


class RedisSecurityStore:
    """Best-effort Redis helper for distributed security controls.

    Fail-open by returning None on Redis outages so API remains available.
    """

    def __init__(self) -> None:
        self._client: Any | None = None
        self._disabled = False

    def _get_client(self) -> Any | None:
        if self._disabled:
            return None
        if self._client is not None:
            return self._client
        settings = get_settings()
        redis_url = settings.redis_url.strip()
        if not redis_url:
            return None
        try:
            from redis import Redis  # type: ignore[import-not-found]

            self._client = Redis.from_url(
                redis_url,
                decode_responses=False,
                socket_timeout=1.5,
                socket_connect_timeout=1.5,
                health_check_interval=30,
            )
            return self._client
        except Exception:
            logger.exception("Redis security store unavailable")
            self._disabled = True
            return None

    def incr_with_ttl(self, key: str, *, ttl_seconds: int) -> tuple[int, int] | None:
        client = self._get_client()
        if client is None:
            return None
        try:
            with client.pipeline() as pipe:
                pipe.incr(key)
                pipe.ttl(key)
                count_raw, ttl_raw = pipe.execute()
            count = int(count_raw)
            ttl = int(ttl_raw)
            if count == 1 or ttl <= 0:
                client.expire(key, max(1, ttl_seconds))
                ttl = max(1, ttl_seconds)
            return count, max(1, ttl)
        except Exception:
            logger.exception("Redis incr_with_ttl failed")
            return None

    def set_lock(self, key: str, *, ttl_seconds: int) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            return bool(client.set(key, b"1", ex=max(1, ttl_seconds)))
        except Exception:
            logger.exception("Redis set_lock failed")
            return False

    def get_ttl(self, key: str) -> int | None:
        client = self._get_client()
        if client is None:
            return None
        try:
            ttl = int(client.ttl(key))
            if ttl <= 0:
                return 0
            return ttl
        except Exception:
            logger.exception("Redis get_ttl failed")
            return None

    def delete(self, *keys: str) -> None:
        if not keys:
            return
        client = self._get_client()
        if client is None:
            return
        try:
            client.delete(*keys)
        except Exception:
            logger.exception("Redis delete failed")

