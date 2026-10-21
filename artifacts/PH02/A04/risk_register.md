# Risk Register: PH02_A04 Resource Quotas & Concurrency Limiting

## Risk Assessment Matrix

| Risk ID | Category | Description | Severity | Likelihood | Mitigation / Invariant | Status |
|---|---|---|---|---|---|---|
| **RR-PH02-A04-01** | System OOM | 10 subagents executing concurrent builds or ML inferences exhaust host physical memory, triggering kernel OOM killer. | Critical | Medium | Pre-flight memory headroom check verifies available RAM >= `min_ram_free_mb` (1024 MB) and total usage <= `max_ram_used_pct` (90%). Active monitoring terminates runaway tasks exceeding per-agent RSS quota (4096 MB). | Controlled |
| **RR-PH02-A04-02** | RAM Disk Exhaustion | Concurrent worktrees on `/dev/shm` exhaust tmpfs capacity, causing `ENOSPC` errors during git operations or pytest runs. | Critical | Medium | RAM disk headroom probe checks free space on `/dev/shm` >= `min_ramdisk_free_mb` (512 MB) and usage <= 90%. Denies new tasks and alerts before disk is completely filled. | Controlled |
| **RR-PH02-A04-03** | Orphan Lock Stalling | An agent process terminates unexpectedly (SIGKILL / power loss), leaving slot lock files permanently held. | High | Low | Implementation uses advisory POSIX locks (`fcntl.flock`). In the Linux kernel, flock descriptors are tied to open file table entries and are unconditionally released when the holding process terminates, preventing orphan lock starvation. | Controlled |
| **RR-PH02-A04-04** | Acquisition Race Conditions | Two agents competing for the same slot file acquire it simultaneously, causing concurrency breaches > 10. | High | Low | Slot acquisition tests `fcntl.flock(fd, LOCK_EX | LOCK_NB)` atomically. Only the winning descriptor holds the exclusive lock; all other concurrent attempts fail-open to probe subsequent slots (0 through 9). | Controlled |
| **RR-PH02-A04-05** | Fallback on Non-tmpfs Hosts | Deploying to an environment lacking a mounted `/dev/shm` tmpfs partition or running under restricted container permissions. | Medium | Low | `ProcessSlotLimiter` checks directory writability on initialization and automatically falls back to `/tmp/.clara_agent_concurrency_<uid>` if `/dev/shm` is unwritable or absent. | Controlled |
| **RR-PH02-A04-06** | PII/PHI Exposure in Slot Metadata | Command arguments containing patient or query metadata written into world-readable slot lock files. | Critical | Low | Slots strictly store sanitized agent IDs (`A01`..`A10`), PID, timestamp, and truncated command strings without user/query payload. File permissions are restricted to `0o600`. | Controlled |
| **RR-PH02-A04-07** | CPU Starvation / Thrashing | 10 intensive CPU-bound jobs cause extreme scheduling latency on low-core runners. | Medium | Low | Semaphore 10 caps max concurrency. Polling loop uses exponential/interval backoff (0.2s) with configurable timeout to avoid busy-wait spin loops. | Controlled |

---

## Architectural Invariants & Safety Guarantees

1. **Strict Concurrency Bound:** No more than 10 subagents may hold active slots simultaneously under default configuration (`CLARA_MAX_CONCURRENCY=10`).
2. **Crash-Resilient State:** Advisory file locking (`fcntl.flock`) ensures zero lock leaks upon process crash or cancellation.
3. **Double Headroom Guard:** Both system RAM and RAM disk storage must have sufficient free headroom before an execution slot is granted.
4. **No-PII Telemetry:** Slot tracking and execution logs never include sensitive patient health information (PHI) or personal identifiable information (PII).
5. **Dual Interface:** Both CLI subprocess execution (`scripts/ops/agent_concurrency_limiter.py run`) and native ML Python coroutines (`clara_ml.agent_concurrency.AsyncAgentLimiter`) share the identical quota rules.
