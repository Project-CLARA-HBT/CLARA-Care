import asyncio
import time
from abc import ABC

import httpx


class CircuitBreakerOpenError(RuntimeError):
    pass


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, reset_timeout: int = 30) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.opened_at: float | None = None

    def check(self) -> None:
        if self.opened_at is None:
            return
        if time.time() - self.opened_at > self.reset_timeout:
            self.failures = 0
            self.opened_at = None
            return
        raise CircuitBreakerOpenError("Circuit breaker đang mở")

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = time.time()


class BaseClient(ABC):  # noqa: B024 - shared concrete base (no abstract methods by design)
    def __init__(
        self, timeout: float = 15.0, max_retries: int = 3, backoff_base: float = 0.5
    ) -> None:
        self.client = httpx.AsyncClient(timeout=timeout)
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.circuit_breaker = CircuitBreaker()

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        self.circuit_breaker.check()

        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.request(method, url, **kwargs)
                response.raise_for_status()
                self.circuit_breaker.record_success()
                return response
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                self.circuit_breaker.record_failure()
                if attempt >= self.max_retries:
                    break
                await asyncio.sleep(self.backoff_base * (2**attempt))

        assert last_exc is not None
        raise last_exc

    async def close(self) -> None:
        await self.client.aclose()
