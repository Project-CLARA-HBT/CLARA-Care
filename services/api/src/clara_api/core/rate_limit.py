import ipaddress
import os
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from clara_api.core.config import get_settings

_TRUE_VALUES = {"1", "true", "yes", "on"}
_CLEANUP_INTERVAL_SECONDS = 30.0
_FORCE_CLEANUP_BUCKET_COUNT = 5000


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE_VALUES


def _proxy_trust_enabled() -> bool:
    if _bool_env("RATE_LIMIT_TRUST_PROXY_HEADERS", default=False):
        return True
    return _bool_env("RATE_LIMIT_TRUST_PROXY", default=False)


def _normalize_forwarded_ip(value: str) -> str | None:
    candidate = value.strip().strip('"')
    if not candidate or candidate.lower() == "unknown":
        return None

    if candidate.startswith("[") and "]" in candidate:
        candidate = candidate[1 : candidate.index("]")]
    elif candidate.count(":") == 1:
        host, port = candidate.rsplit(":", maxsplit=1)
        if port.isdigit():
            candidate = host

    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return None
    return candidate


def _extract_x_forwarded_for_ip(header_value: str) -> str | None:
    for item in header_value.split(","):
        candidate = _normalize_forwarded_ip(item)
        if candidate:
            return candidate
    return None


def _extract_forwarded_ip(header_value: str) -> str | None:
    for section in header_value.split(","):
        for part in section.split(";"):
            key, separator, raw_value = part.strip().partition("=")
            if separator != "=" or key.lower() != "for":
                continue
            candidate = _normalize_forwarded_ip(raw_value)
            if candidate:
                return candidate
    return None


def _parse_trusted_proxies(raw_value: str) -> tuple[set[str], list[ipaddress._BaseNetwork]]:
    trusted_hosts: set[str] = set()
    trusted_networks: list[ipaddress._BaseNetwork] = []

    for item in [entry.strip() for entry in raw_value.split(",") if entry.strip()]:
        try:
            if "/" in item:
                trusted_networks.append(ipaddress.ip_network(item, strict=False))
                continue
            trusted_hosts.add(str(ipaddress.ip_address(item)))
        except ValueError:
            trusted_hosts.add(item)

    return trusted_hosts, trusted_networks


def _is_trusted_proxy(host: str, trusted_hosts: set[str], trusted_networks: list) -> bool:
    if not host:
        return False
    if host in trusted_hosts:
        return True
    try:
        host_ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(host_ip in network for network in trusted_networks)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """In-memory global rate limiter for P0.

    Keyed by resolved client IP + path.
    """

    def __init__(self, app):
        super().__init__(app)
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()
        self._last_cleanup_at = time.monotonic()

    def _resolve_client_ip(self, request: Request) -> str:
        immediate_host = request.client.host if request.client else "unknown"
        if not _proxy_trust_enabled():
            return immediate_host

        raw_trusted_proxies = os.getenv("RATE_LIMIT_TRUSTED_PROXIES", "").strip()
        if raw_trusted_proxies:
            trusted_hosts, trusted_networks = _parse_trusted_proxies(raw_trusted_proxies)
            if not _is_trusted_proxy(immediate_host, trusted_hosts, trusted_networks):
                return immediate_host

        xff = request.headers.get("x-forwarded-for", "")
        forwarded = request.headers.get("forwarded", "")
        forwarded_ip = _extract_x_forwarded_for_ip(xff) or _extract_forwarded_ip(forwarded)
        return forwarded_ip or immediate_host

    def _cleanup_expired_buckets(self, *, now: float, cutoff: float) -> None:
        force_cleanup = len(self._buckets) >= _FORCE_CLEANUP_BUCKET_COUNT
        if not force_cleanup and now - self._last_cleanup_at < _CLEANUP_INTERVAL_SECONDS:
            return
        for bucket_key in list(self._buckets.keys()):
            queue = self._buckets.get(bucket_key)
            if queue is None:
                continue
            while queue and queue[0] < cutoff:
                queue.popleft()
            if not queue:
                self._buckets.pop(bucket_key, None)
        self._last_cleanup_at = now

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        limit = max(1, int(settings.rate_limit_requests))
        window_seconds = max(1, int(settings.rate_limit_window_seconds))
        now = time.monotonic()
        cutoff = now - window_seconds
        key = f"{self._resolve_client_ip(request)}:{request.url.path}"

        retry_after = 1
        with self._lock:
            self._cleanup_expired_buckets(now=now, cutoff=cutoff)
            queue = self._buckets[key]
            while queue and queue[0] < cutoff:
                queue.popleft()

            if len(queue) >= limit:
                retry_after = max(1, int(window_seconds - (now - queue[0])))
            else:
                queue.append(now)
                retry_after = 0

        if retry_after > 0:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Quá giới hạn request, vui lòng thử lại sau",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)
