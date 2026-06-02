from __future__ import annotations

import hashlib
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock

from clara_api.core.config import get_settings
from clara_api.core.redis_security_store import RedisSecurityStore


@dataclass
class _LoginGuardState:
    attempts: deque[float]
    locked_until: float = 0.0


class LoginGuard:
    """In-memory login brute-force guard keyed by email + client IP."""

    def __init__(self) -> None:
        self._states: dict[str, _LoginGuardState] = defaultdict(
            lambda: _LoginGuardState(attempts=deque())
        )
        self._lock = Lock()
        self._redis = RedisSecurityStore()

    def _distributed_enabled(self) -> bool:
        settings = get_settings()
        return bool(settings.auth_login_distributed_enabled and settings.redis_url.strip())

    def _redis_key(self, suffix: str, key: str) -> str:
        settings = get_settings()
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return f"{settings.security_redis_key_prefix}:{suffix}:{digest}"

    def _prune(self, state: _LoginGuardState, now: float, window_seconds: int) -> None:
        cutoff = now - window_seconds
        while state.attempts and state.attempts[0] < cutoff:
            state.attempts.popleft()

    def is_blocked(self, key: str) -> int:
        settings = get_settings()
        if self._distributed_enabled():
            lock_ttl = self._redis.get_ttl(self._redis_key("auth:lock", key))
            if lock_ttl is not None:
                return max(0, lock_ttl)
        now = time.time()
        with self._lock:
            state = self._states[key]
            self._prune(state, now, settings.auth_login_window_seconds)
            if state.locked_until <= now:
                return 0
            return max(1, int(state.locked_until - now))

    def register_failure(self, key: str) -> int:
        settings = get_settings()
        if self._distributed_enabled():
            lock_key = self._redis_key("auth:lock", key)
            attempts_key = self._redis_key("auth:attempt", key)

            lock_ttl = self._redis.get_ttl(lock_key)
            if lock_ttl and lock_ttl > 0:
                return lock_ttl

            attempt_counter = self._redis.incr_with_ttl(
                attempts_key,
                ttl_seconds=settings.auth_login_window_seconds,
            )
            if attempt_counter is not None:
                attempts_count, _attempt_ttl = attempt_counter
                if attempts_count >= settings.auth_login_attempt_limit:
                    self._redis.set_lock(lock_key, ttl_seconds=settings.auth_login_lock_seconds)
                    self._redis.delete(attempts_key)
                    return settings.auth_login_lock_seconds
                return 0

        now = time.time()
        with self._lock:
            state = self._states[key]
            self._prune(state, now, settings.auth_login_window_seconds)
            state.attempts.append(now)
            if len(state.attempts) >= settings.auth_login_attempt_limit:
                state.locked_until = now + settings.auth_login_lock_seconds
            if state.locked_until <= now:
                return 0
            return max(1, int(state.locked_until - now))

    def register_success(self, key: str) -> None:
        if self._distributed_enabled():
            self._redis.delete(
                self._redis_key("auth:attempt", key),
                self._redis_key("auth:lock", key),
            )
        with self._lock:
            self._states.pop(key, None)


login_guard = LoginGuard()
