"""Tests for CLARA Agent Concurrency & Resource Headroom Limiter.

Spec: PH02 / A04 (ML + Retrieval)
Covers:
  - System memory and RAM disk headroom inspection.
  - ProcessSlotLimiter slot allocation, mutual exclusion, and kernel-level cleanup.
  - Concurrency quota enforcement (max 10 slots).
  - Timeout and quota breach denial paths.
  - AsyncAgentLimiter and ThreadAgentLimiter behavior.
  - Simulated high-concurrency multi-agent workload (10 agents parallel).
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from scripts.ops.agent_concurrency_limiter import (
    AgentConcurrencyLimiter,
    AsyncAgentLimiter,
    ConcurrencyQuotaExceededError,
    ProcessSlotLimiter,
    ResourceCheckResult,
    ResourceQuotaBreachError,
    ResourceQuotaConfig,
    ThreadAgentLimiter,
    get_memory_metrics,
    get_process_rss_mb,
    get_ramdisk_metrics,
)


@pytest.fixture
def temp_slot_dir() -> Iterator[Path]:
    """Provide clean isolated slot directory for testing."""
    tmp = Path(tempfile.mkdtemp(prefix="clara_test_slots_"))
    try:
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def test_config(temp_slot_dir: Path) -> ResourceQuotaConfig:
    """Return test configuration with custom slot dir."""
    return ResourceQuotaConfig(
        max_concurrency=10,
        min_ram_free_mb=100.0,
        max_ram_used_pct=99.0,
        min_ramdisk_free_mb=100.0,
        max_ramdisk_used_pct=99.0,
        max_agent_rss_mb=4096.0,
        slot_dir=temp_slot_dir,
        acquire_timeout_sec=2.0,
        poll_interval_sec=0.05,
    )


def test_system_memory_and_ramdisk_probes() -> None:
    """Verify host metrics probing returns valid numbers without exceptions."""
    total_ram, avail_ram, used_pct = get_memory_metrics()
    assert total_ram > 0
    assert avail_ram > 0
    assert 0.0 <= used_pct <= 100.0

    rd_total, rd_free, rd_used = get_ramdisk_metrics(Path("/dev/shm"))
    assert rd_total > 0
    assert rd_free >= 0
    assert 0.0 <= rd_used <= 100.0

    rss = get_process_rss_mb()
    assert rss > 0.0


def test_resource_headroom_check_pass(test_config: ResourceQuotaConfig) -> None:
    """Verify resource check succeeds when host headroom is within limits."""
    limiter = ProcessSlotLimiter(test_config)
    res = limiter.check_headroom("A04")
    assert isinstance(res, ResourceCheckResult)
    assert res.passed is True
    assert len(res.violations) == 0
    assert res.active_slots_count == 0
    assert res.max_concurrency == 10


def test_resource_headroom_check_memory_breach(test_config: ResourceQuotaConfig) -> None:
    """Verify resource check fails when available RAM threshold is breached."""
    breach_config = ResourceQuotaConfig(
        max_concurrency=10,
        min_ram_free_mb=99999999.0,  # Impossible threshold
        slot_dir=test_config.slot_dir,
    )
    limiter = ProcessSlotLimiter(breach_config)
    res = limiter.check_headroom("A04")
    assert res.passed is False
    assert any("RAM available" in v for v in res.violations)

    with pytest.raises(ResourceQuotaBreachError) as exc_info:
        with limiter.acquire("A04", check_headroom=True):
            pass
    assert "RAM available" in str(exc_info.value)


def test_resource_headroom_check_ramdisk_breach(test_config: ResourceQuotaConfig) -> None:
    """Verify resource check fails when RAM disk free space is below threshold."""
    breach_config = ResourceQuotaConfig(
        max_concurrency=10,
        min_ramdisk_free_mb=99999999.0,  # Impossible threshold
        slot_dir=test_config.slot_dir,
    )
    limiter = ProcessSlotLimiter(breach_config)
    res = limiter.check_headroom("A04")
    assert res.passed is False
    assert any("RAM disk free" in v for v in res.violations)

    with pytest.raises(ResourceQuotaBreachError) as exc_info:
        with limiter.acquire("A04", check_headroom=True):
            pass
    assert "RAM disk free" in str(exc_info.value)


def test_single_slot_acquire_and_release(test_config: ResourceQuotaConfig) -> None:
    """Verify acquiring and releasing a single slot works cleanly."""
    limiter = ProcessSlotLimiter(test_config)

    assert len(limiter.get_active_slots()) == 0

    with limiter.acquire(agent_id="A04", command="test_job", check_headroom=False) as slot:
        assert slot.slot_id == 0
        assert slot.agent_id == "A04"
        active = limiter.get_active_slots()
        assert len(active) == 1
        assert active[0].agent_id == "A04"
        assert active[0].pid == os.getpid()

    # Once exited, slot is freed
    assert len(limiter.get_active_slots()) == 0


def test_concurrency_slots_fill_and_timeout_denial(temp_slot_dir: Path) -> None:
    """Verify that when all slots are occupied, additional requests time out."""
    small_config = ResourceQuotaConfig(
        max_concurrency=3,
        slot_dir=temp_slot_dir,
        acquire_timeout_sec=0.25,
        poll_interval_sec=0.05,
    )
    limiter = ProcessSlotLimiter(small_config)

    # Acquire all 3 slots
    with limiter.acquire(agent_id="A01", check_headroom=False) as s0:
        with limiter.acquire(agent_id="A02", check_headroom=False) as s1:
            with limiter.acquire(agent_id="A03", check_headroom=False) as s2:
                assert {s0.slot_id, s1.slot_id, s2.slot_id} == {0, 1, 2}
                assert len(limiter.get_active_slots()) == 3

                # Attempting 4th agent must raise ConcurrencyQuotaExceededError
                with pytest.raises(ConcurrencyQuotaExceededError) as exc_info:
                    with limiter.acquire(agent_id="A04", timeout=0.2, check_headroom=False):
                        pass
                assert "All 3 slots occupied" in str(exc_info.value)


def test_concurrent_simulation_10_agents(temp_slot_dir: Path) -> None:
    """Test full 10-agent concurrent simulation respecting max_concurrency=10."""
    config = ResourceQuotaConfig(
        max_concurrency=10,
        slot_dir=temp_slot_dir,
        acquire_timeout_sec=5.0,
        poll_interval_sec=0.02,
    )
    coordinator = AgentConcurrencyLimiter(config=config)
    report = coordinator.simulate(num_agents=10, concurrency=10, duration_sec=0.1)

    assert report["num_agents"] == 10
    assert report["max_concurrency_configured"] == 10
    assert report["peak_concurrency_observed"] <= 10
    assert report["invariant_holds"] is True
    assert report["successful_count"] == 10
    assert report["failed_count"] == 0


def test_concurrent_simulation_throttling_over_capacity(temp_slot_dir: Path) -> None:
    """Test that 12 agents on concurrency=4 throttle correctly into batches."""
    config = ResourceQuotaConfig(
        max_concurrency=4,
        slot_dir=temp_slot_dir,
        acquire_timeout_sec=5.0,
        poll_interval_sec=0.02,
    )
    coordinator = AgentConcurrencyLimiter(config=config)
    report = coordinator.simulate(num_agents=12, concurrency=4, duration_sec=0.05)

    assert report["num_agents"] == 12
    assert report["max_concurrency_configured"] == 4
    assert report["peak_concurrency_observed"] <= 4
    assert report["invariant_holds"] is True
    assert report["successful_count"] == 12


def test_thread_agent_limiter(test_config: ResourceQuotaConfig) -> None:
    """Verify ThreadAgentLimiter bounds concurrent threads."""
    limiter = ThreadAgentLimiter(test_config)
    peak = 0
    lock = threading.Lock()

    def task() -> None:
        nonlocal peak
        with limiter.acquire(agent_id="A_thread", check_headroom=False):
            with lock:
                if limiter.active_count > peak:
                    peak = limiter.active_count
            time.sleep(0.05)

    threads = [threading.Thread(target=task) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert peak <= test_config.max_concurrency


@pytest.mark.asyncio
async def test_async_agent_limiter(test_config: ResourceQuotaConfig) -> None:
    """Verify AsyncAgentLimiter bounds concurrent coroutines."""
    limiter = AsyncAgentLimiter(test_config)
    peak = 0

    async def async_task() -> None:
        nonlocal peak
        async with limiter.acquire(agent_id="A_async", check_headroom=False):
            if limiter.active_count > peak:
                peak = limiter.active_count
            await asyncio.sleep(0.05)

    await asyncio.gather(*(async_task() for _ in range(15)))
    assert peak <= test_config.max_concurrency


def test_run_command_execution(test_config: ResourceQuotaConfig) -> None:
    """Verify coordinator run_command executes process under slot protection."""
    coordinator = AgentConcurrencyLimiter(config=test_config)
    rc = coordinator.run_command(
        command=["python3", "-c", "import sys; sys.exit(0)"],
        agent_id="A04",
        timeout=10.0,
        check_headroom=False,
    )
    assert rc == 0


def test_ml_concurrency_module_integration() -> None:
    """Verify clara_ml.agent_concurrency integration export."""
    from clara_ml.agent_concurrency import (
        get_async_agent_limiter,
        get_global_agent_limiter,
    )

    global_limiter = get_global_agent_limiter()
    assert isinstance(global_limiter, AgentConcurrencyLimiter)

    async_limiter = get_async_agent_limiter()
    assert isinstance(async_limiter, AsyncAgentLimiter)
