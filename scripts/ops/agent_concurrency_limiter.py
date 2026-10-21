#!/usr/bin/env python3
"""CLARA Agent Concurrency & Resource Headroom Limiter.

Spec: PH02 / A04 (ML + Retrieval)
Role: Resource quotas and semaphore 10 management.
Guarantees:
  1. Concurrency control: Maximum 10 concurrent subagents (process-level & asyncio).
  2. Memory monitoring: System available RAM & process RSS monitoring to prevent OOM.
  3. RAM disk (/dev/shm) headroom verification: Ensures sufficient tmpfs space for
     concurrent worktrees and build artifacts.
  4. Automatic kernel-level cleanup: Uses advisory POSIX file locks (fcntl.flock)
     which are unconditionally released by the kernel upon process termination.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import dataclasses
import datetime
import fcntl
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections.abc import AsyncIterator, Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    import psutil  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore[assignment]

logger = logging.getLogger("agent_concurrency_limiter")

# --- Defaults & Environment Variable Mappings ---
DEFAULT_MAX_CONCURRENCY = int(os.getenv("CLARA_MAX_CONCURRENCY", "10"))
DEFAULT_MIN_RAM_FREE_MB = float(os.getenv("CLARA_MIN_RAM_FREE_MB", "1024.0"))
DEFAULT_MAX_RAM_USED_PCT = float(os.getenv("CLARA_MAX_RAM_USED_PCT", "90.0"))
DEFAULT_MIN_RAMDISK_FREE_MB = float(os.getenv("CLARA_MIN_RAMDISK_FREE_MB", "512.0"))
DEFAULT_MAX_RAMDISK_USED_PCT = float(os.getenv("CLARA_MAX_RAMDISK_USED_PCT", "90.0"))
DEFAULT_MAX_AGENT_RSS_MB = float(os.getenv("CLARA_MAX_AGENT_RSS_MB", "4096.0"))
DEFAULT_RAMDISK_PATH = os.getenv("CLARA_RAMDISK_PATH", "/dev/shm")
DEFAULT_SLOT_DIR = os.getenv("CLARA_SLOT_DIR", "/dev/shm/.clara_agent_concurrency")


class ConcurrencyLimitError(RuntimeError):
    """Base exception for agent concurrency limiter errors."""


class ResourceQuotaBreachError(ConcurrencyLimitError):
    """Raised when memory or RAM disk thresholds are violated."""


class ConcurrencyQuotaExceededError(ConcurrencyLimitError):
    """Raised when all concurrency slots are exhausted and acquisition times out."""


class AgentExecutionError(ConcurrencyLimitError):
    """Raised when an agent command fails under execution."""


@dataclass(frozen=True)
class ResourceQuotaConfig:
    """Configuration quotas for subagent execution."""

    max_concurrency: int = DEFAULT_MAX_CONCURRENCY
    min_ram_free_mb: float = DEFAULT_MIN_RAM_FREE_MB
    max_ram_used_pct: float = DEFAULT_MAX_RAM_USED_PCT
    min_ramdisk_free_mb: float = DEFAULT_MIN_RAMDISK_FREE_MB
    max_ramdisk_used_pct: float = DEFAULT_MAX_RAMDISK_USED_PCT
    max_agent_rss_mb: float = DEFAULT_MAX_AGENT_RSS_MB
    ramdisk_path: Path = field(default_factory=lambda: Path(DEFAULT_RAMDISK_PATH))
    slot_dir: Path = field(default_factory=lambda: Path(DEFAULT_SLOT_DIR))
    acquire_timeout_sec: float = 60.0
    poll_interval_sec: float = 0.2


@dataclass
class SlotInfo:
    """Information regarding a single concurrency slot."""

    slot_id: int
    pid: int
    agent_id: str
    command: str
    acquired_at: str
    hostname: str = ""
    rss_mb: float = 0.0


@dataclass
class ResourceCheckResult:
    """Result of host memory and RAM disk headroom inspection."""

    passed: bool
    timestamp: str
    ram_total_mb: float
    ram_available_mb: float
    ram_used_pct: float
    ramdisk_total_mb: float
    ramdisk_free_mb: float
    ramdisk_used_pct: float
    active_slots_count: int
    max_concurrency: int
    active_slots: list[dict[str, Any]] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_memory_metrics() -> tuple[float, float, float]:
    """Retrieve system memory metrics (total_mb, available_mb, used_pct)."""
    if psutil is not None:
        vm = psutil.virtual_memory()
        total_mb = vm.total / (1024 * 1024)
        available_mb = vm.available / (1024 * 1024)
        used_pct = float(vm.percent)
        return total_mb, available_mb, used_pct

    # Fallback to /proc/meminfo on Linux without psutil
    meminfo_path = Path("/proc/meminfo")
    if meminfo_path.exists():
        data: dict[str, float] = {}
        with meminfo_path.open("r", encoding="utf-8") as f:
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val_parts = parts[1].strip().split()
                    if val_parts:
                        try:
                            data[key] = float(val_parts[0]) / 1024.0  # kB to MB
                        except ValueError:
                            pass
        total_mb = data.get("MemTotal", 16384.0)
        available_mb = data.get("MemAvailable", data.get("MemFree", 8192.0))
        used_pct = max(0.0, min(100.0, ((total_mb - available_mb) / total_mb) * 100.0))
        return total_mb, available_mb, used_pct

    # Generic fallback
    return 16384.0, 8192.0, 50.0


def get_ramdisk_metrics(ramdisk_path: Path) -> tuple[float, float, float]:
    """Retrieve RAM disk storage metrics (total_mb, free_mb, used_pct)."""
    target = ramdisk_path if ramdisk_path.exists() else Path("/tmp")
    try:
        usage = shutil.disk_usage(target)
        total_mb = usage.total / (1024 * 1024)
        free_mb = usage.free / (1024 * 1024)
        used_mb = usage.used / (1024 * 1024)
        used_pct = (used_mb / total_mb * 100.0) if total_mb > 0 else 0.0
        return total_mb, free_mb, used_pct
    except Exception as exc:
        logger.warning(f"Failed to query disk metrics for {target}: {exc}")
        return 16384.0, 8192.0, 50.0


def get_process_rss_mb(pid: int | None = None) -> float:
    """Return Resident Set Size (RSS) memory in MB for the target PID."""
    target_pid = pid if pid is not None else os.getpid()
    if psutil is not None:
        try:
            proc = psutil.Process(target_pid)
            return float(proc.memory_info().rss) / (1024 * 1024)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0

    # /proc fallback
    statm_path = Path(f"/proc/{target_pid}/statm")
    if statm_path.exists():
        try:
            pages = int(statm_path.read_text().split()[1])
            page_size = os.sysconf("SC_PAGE_SIZE")
            return (pages * page_size) / (1024 * 1024)
        except Exception:
            return 0.0
    return 0.0


def is_pid_alive(pid: int) -> bool:
    """Check if a process with given PID is alive."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class ProcessSlotLimiter:
    """Cross-process concurrency limiter using file locks with flock."""

    def __init__(self, config: ResourceQuotaConfig | None = None) -> None:
        self.config = config or ResourceQuotaConfig()
        self._thread_lock = threading.Lock()
        self._slot_dir = self._resolve_slot_dir()

    def _resolve_slot_dir(self) -> Path:
        """Resolve slot directory, falling back to /tmp if default is not writable."""
        target = self.config.slot_dir
        try:
            target.mkdir(parents=True, exist_ok=True)
            # Safe probe with unique PID/thread tag
            probe = target / f".probe_{os.getpid()}_{threading.get_ident()}"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return target
        except Exception:
            fallback = Path(f"/tmp/.clara_agent_concurrency_{os.getuid()}")
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback

    def _slot_path(self, slot_id: int) -> Path:
        return self._slot_dir / f"slot_{slot_id:02d}.lock"

    def get_active_slots(self) -> list[SlotInfo]:
        """Scan slot files and return currently active (locked) slots."""
        active: list[SlotInfo] = []
        for slot_id in range(self.config.max_concurrency):
            slot_file = self._slot_path(slot_id)
            if not slot_file.exists():
                continue

            try:
                fd = os.open(slot_file, os.O_RDWR)
            except OSError:
                continue

            try:
                # Probe lock non-blockingly
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # If we succeeded in acquiring the lock, slot is actually free (or stale)
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
            except (BlockingIOError, OSError):
                # Lock is held by another active process!
                os.close(fd)
                try:
                    content = slot_file.read_text(encoding="utf-8")
                    data = json.loads(content)
                    pid = int(data.get("pid", 0))
                    rss = get_process_rss_mb(pid) if pid > 0 else 0.0
                    active.append(
                        SlotInfo(
                            slot_id=slot_id,
                            pid=pid,
                            agent_id=str(data.get("agent_id", "unknown")),
                            command=str(data.get("command", "")),
                            acquired_at=str(data.get("acquired_at", "")),
                            hostname=str(data.get("hostname", "")),
                            rss_mb=rss,
                        )
                    )
                except Exception:
                    active.append(
                        SlotInfo(
                            slot_id=slot_id,
                            pid=-1,
                            agent_id="unknown",
                            command="",
                            acquired_at="",
                        )
                    )
        return active

    def check_headroom(self, agent_id: str = "A04") -> ResourceCheckResult:
        """Inspect RAM and RAM disk headroom against configured quotas."""
        now_iso = datetime.datetime.now(datetime.UTC).isoformat()
        ram_total, ram_avail, ram_used_pct = get_memory_metrics()
        rd_total, rd_free, rd_used_pct = get_ramdisk_metrics(self.config.ramdisk_path)
        active_slots = self.get_active_slots()

        violations: list[str] = []
        if ram_avail < self.config.min_ram_free_mb:
            violations.append(
                f"RAM available ({ram_avail:.1f} MB) < minimum threshold ({self.config.min_ram_free_mb:.1f} MB)"
            )
        if ram_used_pct > self.config.max_ram_used_pct:
            violations.append(
                f"RAM usage ({ram_used_pct:.1f}%) > maximum threshold ({self.config.max_ram_used_pct:.1f}%)"
            )
        if rd_free < self.config.min_ramdisk_free_mb:
            violations.append(
                f"RAM disk free ({rd_free:.1f} MB) < minimum threshold ({self.config.min_ramdisk_free_mb:.1f} MB)"
            )
        if rd_used_pct > self.config.max_ramdisk_used_pct:
            violations.append(
                f"RAM disk usage ({rd_used_pct:.1f}%) > maximum threshold ({self.config.max_ramdisk_used_pct:.1f}%)"
            )

        passed = len(violations) == 0
        return ResourceCheckResult(
            passed=passed,
            timestamp=now_iso,
            ram_total_mb=ram_total,
            ram_available_mb=ram_avail,
            ram_used_pct=ram_used_pct,
            ramdisk_total_mb=rd_total,
            ramdisk_free_mb=rd_free,
            ramdisk_used_pct=rd_used_pct,
            active_slots_count=len(active_slots),
            max_concurrency=self.config.max_concurrency,
            active_slots=[asdict(s) for s in active_slots],
            violations=violations,
        )

    def _try_acquire_slot(
        self, agent_id: str, command: str = ""
    ) -> tuple[int, int] | None:
        """Attempt to acquire any free slot between 0 and max_concurrency - 1.

        Returns (slot_id, fd) if acquired, or None if all slots are locked.
        """
        for slot_id in range(self.config.max_concurrency):
            slot_file = self._slot_path(slot_id)
            try:
                fd = os.open(slot_file, os.O_CREAT | os.O_RDWR, 0o600)
            except OSError:
                continue

            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Acquired successfully!
                payload = {
                    "slot_id": slot_id,
                    "pid": os.getpid(),
                    "agent_id": agent_id,
                    "command": command[:256],
                    "acquired_at": datetime.datetime.now(datetime.UTC).isoformat(),
                    "hostname": os.uname().nodename,
                }
                os.ftruncate(fd, 0)
                os.lseek(fd, 0, os.SEEK_SET)
                os.write(fd, json.dumps(payload, indent=2).encode("utf-8"))
                os.fsync(fd)
                return slot_id, fd
            except (BlockingIOError, OSError):
                os.close(fd)
                continue
        return None

    def release_slot(self, slot_id: int, fd: int) -> None:
        """Release lock and close descriptor for the slot."""
        try:
            os.ftruncate(fd, 0)
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            try:
                os.close(fd)
            except OSError:
                pass

    @contextlib.contextmanager
    def acquire(
        self,
        agent_id: str = "A04",
        command: str = "",
        timeout: float | None = None,
        check_headroom: bool = True,
    ) -> Iterator[SlotInfo]:
        """Context manager to acquire a slot under semaphore and headroom constraints."""
        timeout_sec = timeout if timeout is not None else self.config.acquire_timeout_sec
        deadline = time.monotonic() + timeout_sec

        # 1. Check headroom before attempting acquisition
        if check_headroom:
            headroom = self.check_headroom(agent_id=agent_id)
            if not headroom.passed:
                raise ResourceQuotaBreachError(
                    f"Resource headroom check failed for agent {agent_id}: {'; '.join(headroom.violations)}"
                )

        # 2. Acquire slot with retry loop until timeout
        slot_handle: tuple[int, int] | None = None
        while time.monotonic() < deadline:
            slot_handle = self._try_acquire_slot(agent_id=agent_id, command=command)
            if slot_handle is not None:
                break
            time.sleep(self.config.poll_interval_sec)

        if slot_handle is None:
            active = self.get_active_slots()
            raise ConcurrencyQuotaExceededError(
                f"Timed out waiting for free slot after {timeout_sec:.1f}s. "
                f"All {self.config.max_concurrency} slots occupied by: {[s.agent_id for s in active]}"
            )

        slot_id, fd = slot_handle
        slot_info = SlotInfo(
            slot_id=slot_id,
            pid=os.getpid(),
            agent_id=agent_id,
            command=command,
            acquired_at=datetime.datetime.now(datetime.UTC).isoformat(),
            hostname=os.uname().nodename,
            rss_mb=get_process_rss_mb(),
        )

        try:
            yield slot_info
        finally:
            self.release_slot(slot_id, fd)


class AsyncAgentLimiter:
    """Asyncio concurrency limiter with pre-flight resource checks."""

    def __init__(self, config: ResourceQuotaConfig | None = None) -> None:
        self.config = config or ResourceQuotaConfig()
        self._semaphore = asyncio.Semaphore(self.config.max_concurrency)
        self._active_count = 0
        self._lock = asyncio.Lock()

    @property
    def active_count(self) -> int:
        return self._active_count

    @property
    def available_slots(self) -> int:
        return max(0, self.config.max_concurrency - self._active_count)

    async def check_headroom(self) -> ResourceCheckResult:
        """Run headroom check in worker thread."""
        loop = asyncio.get_running_loop()
        limiter = ProcessSlotLimiter(self.config)
        return await loop.run_in_executor(None, limiter.check_headroom)

    @contextlib.asynccontextmanager
    async def acquire(
        self, agent_id: str = "A04", check_headroom: bool = True
    ) -> AsyncIterator[None]:
        """Acquire an asyncio concurrency slot."""
        if check_headroom:
            res = await self.check_headroom()
            if not res.passed:
                raise ResourceQuotaBreachError(
                    f"Async limiter denied execution for {agent_id}: {'; '.join(res.violations)}"
                )

        await self._semaphore.acquire()
        async with self._lock:
            self._active_count += 1
        try:
            yield
        finally:
            async with self._lock:
                self._active_count -= 1
            self._semaphore.release()


class ThreadAgentLimiter:
    """Thread-level bounded semaphore limiter with headroom guards."""

    def __init__(self, config: ResourceQuotaConfig | None = None) -> None:
        self.config = config or ResourceQuotaConfig()
        self._semaphore = threading.BoundedSemaphore(self.config.max_concurrency)
        self._active_count = 0
        self._lock = threading.Lock()
        self._process_limiter = ProcessSlotLimiter(self.config)

    @property
    def active_count(self) -> int:
        with self._lock:
            return self._active_count

    @contextlib.contextmanager
    def acquire(
        self, agent_id: str = "A04", timeout: float | None = None, check_headroom: bool = True
    ) -> Iterator[None]:
        timeout_sec = timeout if timeout is not None else self.config.acquire_timeout_sec
        if check_headroom:
            res = self._process_limiter.check_headroom(agent_id=agent_id)
            if not res.passed:
                raise ResourceQuotaBreachError(
                    f"Thread limiter denied execution for {agent_id}: {'; '.join(res.violations)}"
                )

        acquired = self._semaphore.acquire(timeout=timeout_sec)
        if not acquired:
            raise ConcurrencyQuotaExceededError(
                f"Thread limiter timed out after {timeout_sec:.1f}s for agent {agent_id}"
            )

        with self._lock:
            self._active_count += 1
        try:
            yield
        finally:
            with self._lock:
                self._active_count -= 1
            self._semaphore.release()


class AgentConcurrencyLimiter:
    """Unified coordinator managing cross-process execution, monitoring, and simulation."""

    def __init__(self, config: ResourceQuotaConfig | None = None) -> None:
        self.config = config or ResourceQuotaConfig()
        self.process_limiter = ProcessSlotLimiter(self.config)
        self.thread_limiter = ThreadAgentLimiter(self.config)

    def check(self) -> ResourceCheckResult:
        """Inspect current headroom and active slots."""
        return self.process_limiter.check_headroom()

    def run_command(
        self,
        command: list[str],
        agent_id: str = "A04",
        timeout: float | None = None,
        check_headroom: bool = True,
        cwd: str | Path | None = None,
    ) -> int:
        """Run a command in a child process protected by concurrency and headroom quotas."""
        cmd_str = " ".join(command)
        logger.info(f"Agent {agent_id} requesting slot for: {cmd_str}")

        with self.process_limiter.acquire(
            agent_id=agent_id,
            command=cmd_str,
            timeout=timeout,
            check_headroom=check_headroom,
        ) as slot:
            logger.info(f"Agent {agent_id} acquired slot #{slot.slot_id} (PID {os.getpid()})")

            # Spawn process
            proc = subprocess.Popen(
                command,
                cwd=str(cwd) if cwd else None,
                preexec_fn=os.setsid if hasattr(os, "setsid") else None,
            )

            # Background thread to monitor memory & headroom during execution
            stop_event = threading.Event()
            quota_violation: list[str] = []

            def monitor_worker() -> None:
                while not stop_event.is_set():
                    try:
                        child_rss = get_process_rss_mb(proc.pid)
                        if child_rss > self.config.max_agent_rss_mb:
                            quota_violation.append(
                                f"Agent {agent_id} RSS ({child_rss:.1f} MB) exceeded quota ({self.config.max_agent_rss_mb:.1f} MB)"
                            )
                            logger.error(quota_violation[-1])
                            proc.terminate()
                            break

                        # Check RAM disk headroom
                        _, rd_free, _ = get_ramdisk_metrics(self.config.ramdisk_path)
                        if rd_free < (self.config.min_ramdisk_free_mb / 2.0):
                            quota_violation.append(
                                f"Critical RAM disk emergency: free space ({rd_free:.1f} MB) critically depleted"
                            )
                            logger.error(quota_violation[-1])
                            proc.terminate()
                            break
                    except Exception:
                        pass
                    stop_event.wait(1.0)

            monitor_thread = threading.Thread(target=monitor_worker, daemon=True)
            monitor_thread.start()

            # Handle termination signals cleanly
            def handle_signal(sig: int, frame: Any) -> None:
                logger.warning(f"Caught signal {sig}, terminating child process {proc.pid}")
                try:
                    if hasattr(os, "killpg"):
                        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    else:
                        proc.terminate()
                except OSError:
                    pass
                sys.exit(128 + sig)

            old_sigint = signal.signal(signal.SIGINT, handle_signal)
            old_sigterm = signal.signal(signal.SIGTERM, handle_signal)

            try:
                returncode = proc.wait(timeout=timeout)
                stop_event.set()
                monitor_thread.join(timeout=1.0)

                if quota_violation:
                    raise ResourceQuotaBreachError(f"Process terminated: {quota_violation[0]}")
                return returncode
            finally:
                signal.signal(signal.SIGINT, old_sigint)
                signal.signal(signal.SIGTERM, old_sigterm)

    def simulate(
        self,
        num_agents: int = 10,
        concurrency: int = 10,
        duration_sec: float = 0.5,
    ) -> dict[str, Any]:
        """Simulate concurrent workload to verify concurrency invariant <= concurrency."""
        config = dataclasses.replace(self.config, max_concurrency=concurrency)
        limiter = ProcessSlotLimiter(config)

        peak_active = 0
        active_lock = threading.Lock()
        currently_active = 0
        results: list[dict[str, Any]] = []

        def worker(agent_idx: int) -> None:
            nonlocal peak_active, currently_active
            agent_name = f"A{agent_idx+1:02d}"
            t0 = time.monotonic()
            try:
                with limiter.acquire(
                    agent_id=agent_name,
                    command="simulated_task",
                    timeout=15.0,
                    check_headroom=False,  # bypass strict host check for synthetic simulation
                ) as slot:
                    with active_lock:
                        currently_active += 1
                        if currently_active > peak_active:
                            peak_active = currently_active

                    # Simulate workload
                    time.sleep(duration_sec)

                    with active_lock:
                        currently_active -= 1

                elapsed = time.monotonic() - t0
                results.append(
                    {
                        "agent": agent_name,
                        "slot": slot.slot_id,
                        "status": "COMPLETED",
                        "elapsed_sec": round(elapsed, 3),
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "agent": agent_name,
                        "slot": -1,
                        "status": "FAILED",
                        "error": str(exc),
                    }
                )

        threads = [
            threading.Thread(target=worker, args=(i,)) for i in range(num_agents)
        ]
        start_time = time.monotonic()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        total_time = time.monotonic() - start_time

        successful = [r for r in results if r["status"] == "COMPLETED"]
        failed = [r for r in results if r["status"] == "FAILED"]

        return {
            "num_agents": num_agents,
            "max_concurrency_configured": concurrency,
            "peak_concurrency_observed": peak_active,
            "invariant_holds": peak_active <= concurrency,
            "total_wall_sec": round(total_time, 3),
            "successful_count": len(successful),
            "failed_count": len(failed),
            "results": results,
        }


def print_formatted_check(result: ResourceCheckResult) -> None:
    """Print readable terminal report of resource headroom check."""
    print("=" * 72)
    print(" CLARA CARE — AGENT RESOURCE QUOTA & CONCURRENCY LIMITER")
    print("=" * 72)
    print(f"Timestamp:              {result.timestamp}")
    print(f"System RAM Total:       {result.ram_total_mb:.1f} MB")
    print(f"System RAM Available:   {result.ram_available_mb:.1f} MB")
    print(f"System RAM Used:        {result.ram_used_pct:.1f}%")
    print("-" * 72)
    print(f"RAM Disk (/dev/shm):    Total: {result.ramdisk_total_mb:.1f} MB | Free: {result.ramdisk_free_mb:.1f} MB ({result.ramdisk_used_pct:.1f}% used)")
    print("-" * 72)
    print(f"Active Slots:           {result.active_slots_count} / {result.max_concurrency} slots occupied")

    if result.active_slots:
        print("\n[ACTIVE AGENT SLOTS]")
        for slot in result.active_slots:
            print(
                f"  - Slot #{slot['slot_id']:02d}: Agent {slot['agent_id']:<6} "
                f"PID {slot['pid']:<7} RSS: {slot['rss_mb']:.1f} MB | {slot['command']}"
            )
    else:
        print("  - All concurrency slots are currently FREE.")

    print("-" * 72)
    if result.violations:
        print("[QUOTA VIOLATIONS / INSUFFICIENT HEADROOM]")
        for v in result.violations:
            print(f"  [FAIL] {v}")
        print("-" * 72)
        print("HEADROOM STATUS: FAIL (Backoff or clean disk before launching tasks)")
    else:
        print("HEADROOM STATUS: PASS (Safe to execute concurrent subagents)")
    print("=" * 72)


def build_cli_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="CLARA Agent Concurrency & RAM Disk Headroom Limiter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Action to perform")

    # check
    check_p = subparsers.add_parser("check", help="Inspect RAM, RAM disk, and active slots")
    check_p.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    # status
    subparsers.add_parser("status", help="Alias for check --json")

    # run
    run_p = subparsers.add_parser("run", help="Run a command protected by concurrency & quotas")
    run_p.add_argument("--agent", required=True, help="Subagent ID (e.g. A01..A10)")
    run_p.add_argument("--timeout", type=float, default=300.0, help="Max execution timeout in seconds")
    run_p.add_argument("--bypass-headroom", action="store_true", help="Bypass host headroom check")
    run_p.add_argument("command", nargs=argparse.REMAINDER, help="Command and arguments to execute")

    # simulate
    sim_p = subparsers.add_parser("simulate", help="Run simulated concurrent workload")
    sim_p.add_argument("--agents", type=int, default=10, help="Number of simulated agents (default: 10)")
    sim_p.add_argument("--concurrency", type=int, default=10, help="Concurrency limit (default: 10)")
    sim_p.add_argument("--duration", type=float, default=0.5, help="Simulated task duration in sec")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_cli_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    limiter = AgentConcurrencyLimiter()

    if args.subcommand in ("check", None):
        as_json = getattr(args, "json", False)
        result = limiter.check()
        if as_json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print_formatted_check(result)
        return 0 if result.passed else 1

    elif args.subcommand == "status":
        result = limiter.check()
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.passed else 1

    elif args.subcommand == "run":
        cmd = args.command
        # If user passed -- before command, strip leading '--'
        if cmd and cmd[0] == "--":
            cmd = cmd[1:]
        if not cmd:
            print("Error: No command specified to run.", file=sys.stderr)
            return 2

        try:
            returncode = limiter.run_command(
                command=cmd,
                agent_id=args.agent,
                timeout=args.timeout,
                check_headroom=not args.bypass_headroom,
            )
            return returncode
        except ConcurrencyLimitError as exc:
            print(f"Concurrency limiter error: {exc}", file=sys.stderr)
            return 1

    elif args.subcommand == "simulate":
        print(f"Simulating {args.agents} agents with concurrency limit {args.concurrency}...")
        report = limiter.simulate(
            num_agents=args.agents,
            concurrency=args.concurrency,
            duration_sec=args.duration,
        )
        print(json.dumps(report, indent=2))
        if not report["invariant_holds"]:
            print(f"ERROR: Invariant breached! Peak concurrency {report['peak_concurrency_observed']} > {args.concurrency}", file=sys.stderr)
            return 1
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
