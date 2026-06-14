import asyncio
import time
from collections import deque
from typing import Any

from clara_api.clients.base_client import BaseClient
from clara_api.core.config import get_settings


class RateLimiter10RPS:
    """Simple asyncio rate limiter for 10 req/s."""

    def __init__(self, max_calls: int = 10, per_seconds: float = 1.0) -> None:
        self.max_calls = max_calls
        self.per_seconds = per_seconds
        self.calls: deque[float] = deque()
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self.lock:
            now = time.monotonic()
            while self.calls and now - self.calls[0] >= self.per_seconds:
                self.calls.popleft()

            if len(self.calls) >= self.max_calls:
                sleep_for = self.per_seconds - (now - self.calls[0])
                await asyncio.sleep(max(sleep_for, 0))
                now = time.monotonic()
                while self.calls and now - self.calls[0] >= self.per_seconds:
                    self.calls.popleft()

            self.calls.append(time.monotonic())


class PubMedClient(BaseClient):
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__()
        settings = get_settings()
        self.api_key = api_key
        self.rate_limiter = RateLimiter10RPS(max_calls=settings.pubmed_rate_limit_per_sec)

    async def _call(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        await self.rate_limiter.acquire()
        base_params = {"retmode": "json"}
        if self.api_key:
            base_params["api_key"] = self.api_key
        response = await self._request(
            "GET",
            f"{self.BASE_URL}/{endpoint}",
            params={**base_params, **params},
        )
        return response.json()

    async def esearch(self, term: str, db: str = "pubmed", retmax: int = 20) -> dict[str, Any]:
        return await self._call("esearch.fcgi", {"db": db, "term": term, "retmax": retmax})

    async def efetch(self, ids: list[str], db: str = "pubmed") -> dict[str, Any]:
        return await self._call("efetch.fcgi", {"db": db, "id": ",".join(ids)})

    async def elink(
        self, ids: list[str], dbfrom: str = "pubmed", db: str = "pubmed"
    ) -> dict[str, Any]:
        return await self._call(
            "elink.fcgi",
            {"dbfrom": dbfrom, "db": db, "id": ",".join(ids)},
        )
