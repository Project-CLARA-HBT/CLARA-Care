"""CLARA ML Subsystem Agent Concurrency & Resource Headroom Limiter.

Spec: PH02 / A04 (ML + Retrieval)
Provides ML pipelines and retrieval workers with safe 10-concurrency limits,
asyncio semaphores, memory monitoring, and RAM disk headroom protection.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repository root is on sys.path for scripts.ops imports
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ops.agent_concurrency_limiter import (  # noqa: E402
    AgentConcurrencyLimiter,
    AsyncAgentLimiter,
    ConcurrencyLimitError,
    ConcurrencyQuotaExceededError,
    ProcessSlotLimiter,
    ResourceCheckResult,
    ResourceQuotaBreachError,
    ResourceQuotaConfig,
    SlotInfo,
    get_memory_metrics,
    get_process_rss_mb,
    get_ramdisk_metrics,
)

_GLOBAL_LIMITER: AgentConcurrencyLimiter | None = None
_GLOBAL_ASYNC_LIMITER: AsyncAgentLimiter | None = None


def get_global_agent_limiter(config: ResourceQuotaConfig | None = None) -> AgentConcurrencyLimiter:
    """Return singleton instance of AgentConcurrencyLimiter."""
    global _GLOBAL_LIMITER
    if _GLOBAL_LIMITER is None or config is not None:
        _GLOBAL_LIMITER = AgentConcurrencyLimiter(config=config)
    return _GLOBAL_LIMITER


def get_async_agent_limiter(config: ResourceQuotaConfig | None = None) -> AsyncAgentLimiter:
    """Return singleton instance of AsyncAgentLimiter."""
    global _GLOBAL_ASYNC_LIMITER
    if _GLOBAL_ASYNC_LIMITER is None or config is not None:
        _GLOBAL_ASYNC_LIMITER = AsyncAgentLimiter(config=config)
    return _GLOBAL_ASYNC_LIMITER


def check_system_headroom(agent_id: str = "A04") -> ResourceCheckResult:
    """Check host memory and RAM disk headroom."""
    limiter = get_global_agent_limiter()
    return limiter.process_limiter.check_headroom(agent_id=agent_id)


__all__ = [
    "AgentConcurrencyLimiter",
    "AsyncAgentLimiter",
    "ConcurrencyLimitError",
    "ConcurrencyQuotaExceededError",
    "ProcessSlotLimiter",
    "ResourceCheckResult",
    "ResourceQuotaBreachError",
    "ResourceQuotaConfig",
    "SlotInfo",
    "check_system_headroom",
    "get_async_agent_limiter",
    "get_global_agent_limiter",
    "get_memory_metrics",
    "get_process_rss_mb",
    "get_ramdisk_metrics",
]
