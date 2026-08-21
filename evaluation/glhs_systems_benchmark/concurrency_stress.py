"""Multi-Threaded Concurrency Stress & Zipfian Skew Benchmark Suite.

Evaluates transactional throughput (TPS), latencies (p50, p95, p99), false-stale abort rates,
true-conflict abort rates, and unsafe commit rates across:
- Concurrency levels: W in {1, 2, 4, 8, 16, 32, 64, 128}
- Zipfian skew parameters: alpha in {0.0, 0.5, 0.9, 1.2}
"""

from __future__ import annotations

import concurrent.futures
import math
import random
import time
from dataclasses import asdict, dataclass
from typing import Any

from evaluation.glhs_systems_benchmark.baselines.base import (
    BaselineEngine,
    TxnResult,
    compute_metrics,
)
from evaluation.glhs_systems_benchmark.baselines.fhir_bundle_adapter import FHIRBundleAdapterEngine
from evaluation.glhs_systems_benchmark.baselines.glhs_ss2pl import GLHSSS2PLEngine
from evaluation.glhs_systems_benchmark.baselines.postgres_ssi import PostgresSSIEngine
from evaluation.glhs_systems_benchmark.baselines.standard_2pl import Standard2PLEngine
from evaluation.glhs_systems_benchmark.baselines.standard_occ import StandardOCCEngine
from evaluation.glhs_systems_benchmark.baselines.zanzibar_model import ZanzibarModelEngine
from evaluation.glhs_systems_benchmark.workload_generator import (
    ClinicalWorkloadItem,
    PartitionCoord,
    ScenarioFamily,
)


class ZipfianSampler:
    """Fast discrete Zipfian distribution sampler using inverse CDF binary search."""

    def __init__(self, n_items: int, alpha: float, seed: int = 42) -> None:
        self.n_items = max(1, n_items)
        self.alpha = float(alpha)
        self.rng = random.Random(seed)

        if self.alpha == 0.0:
            self.probabilities = [1.0 / self.n_items] * self.n_items
        else:
            weights = [1.0 / math.pow(i + 1, self.alpha) for i in range(self.n_items)]
            total_w = sum(weights)
            self.probabilities = [w / total_w for w in weights]

        self.cumulative: list[float] = []
        cum = 0.0
        for p in self.probabilities:
            cum += p
            self.cumulative.append(cum)
        self.cumulative[-1] = 1.0

    def sample(self) -> int:
        """Sample an item index in [0, n_items - 1] according to Zipfian skew."""
        r = self.rng.random()
        low, high = 0, len(self.cumulative) - 1
        while low < high:
            mid = (low + high) // 2
            if r <= self.cumulative[mid]:
                high = mid
            else:
                low = mid + 1
        return low


@dataclass
class ConcurrencyGridPointResult:
    """Result for a single (paradigm, workers, alpha) evaluation point."""

    paradigm: str
    workers: int
    alpha: float
    total_tx: int
    throughput_tps: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    mean_latency_ms: float
    valid_commits: int
    true_stale_aborts: int
    false_stale_aborts: int
    unsafe_commits: int
    unsafe_commit_rate: float
    false_stale_rate: float
    true_stale_rate: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConcurrencyStressReport:
    """Complete multi-dimensional concurrency benchmark report."""

    evaluated_workers: list[int]
    evaluated_alphas: list[float]
    evaluated_paradigms: list[str]
    total_experiments: int
    results: list[ConcurrencyGridPointResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluated_workers": self.evaluated_workers,
            "evaluated_alphas": self.evaluated_alphas,
            "evaluated_paradigms": self.evaluated_paradigms,
            "total_experiments": self.total_experiments,
            "results": [r.to_dict() for r in self.results],
        }


def generate_skewed_workload(
    workers: int,
    tx_per_worker: int,
    alpha: float,
    n_partitions: int = 64,
    seed: int = 42,
) -> list[ClinicalWorkloadItem]:
    """Generates a batch of transactions distributed across workers with Zipfian partition access."""
    sampler = ZipfianSampler(n_partitions, alpha, seed=seed)
    total_tx = workers * tx_per_worker
    workload: list[ClinicalWorkloadItem] = []

    for i in range(total_tx):
        wid = f"stress_w{workers}_a{alpha:.1f}_{i:05d}"
        part_idx = sampler.sample()
        prof_id = f"profile_{(part_idx % 16) + 1:03d}"
        slot = f"entity_{part_idx:03d}"
        coord = PartitionCoord(profile_id=prof_id, domain="medication", slot=slot)

        # 10% chance of governance drift and 5% chance of severe DDI for stress testing
        has_drift = (i % 10 == 0)
        has_ddi = (i % 20 == 0)

        workload.append(
            ClinicalWorkloadItem(
                workload_id=wid,
                scenario_family=ScenarioFamily.DISJOINT_PARTITIONS if alpha == 0.0 else ScenarioFamily.CLEAN_UPDATE,
                patient_id=f"patient_{(part_idx % 16) + 1:03d}",
                profile_id=prof_id,
                policy_id="glhs_policy_v1",
                expected_policy_epoch=1,
                expected_consent_epoch=1,
                target_partitions=[coord.to_key()],
                proposed_medications=[f"med_{part_idx:03d}"],
                active_medications=[],
                has_governance_drift=has_drift,
                has_severe_ddi=has_ddi,
                is_disjoint=(alpha == 0.0),
                payload={"action": "skewed_stress_mutation", "slot": slot, "val": i},
            )
        )

    return workload


def run_single_stress_trial(
    engine: BaselineEngine,
    workload: list[ClinicalWorkloadItem],
    workers: int,
    alpha: float,
) -> ConcurrencyGridPointResult:
    """Executes a single concurrency stress test across worker threads."""
    engine.setup(num_patients=20, num_partitions=64)

    def _execute_worker_task(tx: ClinicalWorkloadItem) -> TxnResult:
        return engine.execute_transaction(tx)

    t_start = time.perf_counter()
    results: list[TxnResult] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_execute_worker_task, tx) for tx in workload]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    t_end = time.perf_counter()
    elapsed = max(1e-6, t_end - t_start)

    metrics = compute_metrics(engine.name, results, elapsed)

    return ConcurrencyGridPointResult(
        paradigm=engine.name,
        workers=workers,
        alpha=alpha,
        total_tx=metrics.total_tx,
        throughput_tps=metrics.throughput_tps,
        p50_latency_ms=metrics.p50_latency_ms,
        p95_latency_ms=metrics.p95_latency_ms,
        p99_latency_ms=metrics.p99_latency_ms,
        mean_latency_ms=metrics.mean_latency_ms,
        valid_commits=metrics.valid_commits,
        true_stale_aborts=metrics.true_stale_aborts,
        false_stale_aborts=metrics.false_stale_aborts,
        unsafe_commits=metrics.unsafe_commits,
        unsafe_commit_rate=metrics.unsafe_commit_rate,
        false_stale_rate=metrics.false_stale_rate,
        true_stale_rate=metrics.true_stale_rate,
    )


def run_concurrency_stress_grid(
    workers_list: list[int] | None = None,
    alphas_list: list[float] | None = None,
    paradigms: list[str] | None = None,
    tx_per_worker: int = 50,
    db_url: str | None = None,
    seed: int = 42,
) -> ConcurrencyStressReport:
    """Executes the full W x alpha grid across baseline paradigms."""
    if workers_list is None:
        workers_list = [1, 2, 4, 8, 16, 32, 64, 128]
    if alphas_list is None:
        alphas_list = [0.0, 0.5, 0.9, 1.2]

    # Map available engines
    engine_factory: dict[str, type[BaselineEngine]] = {
        "glhs_ss2pl": GLHSSS2PLEngine,
        "standard_2pl": Standard2PLEngine,
        "standard_occ": StandardOCCEngine,
        "postgres_ssi": PostgresSSIEngine,
        "fhir_bundle": FHIRBundleAdapterEngine,
        "zanzibar": ZanzibarModelEngine,
    }

    selected_paradigms = paradigms or list(engine_factory.keys())
    results: list[ConcurrencyGridPointResult] = []

    for p_name in selected_paradigms:
        if p_name not in engine_factory:
            continue
        engine_cls = engine_factory[p_name]
        engine = engine_cls(db_url=db_url)

        for alpha in alphas_list:
            for w in workers_list:
                workload = generate_skewed_workload(
                    workers=w,
                    tx_per_worker=tx_per_worker,
                    alpha=alpha,
                    n_partitions=64,
                    seed=seed + int(alpha * 100) + w,
                )
                point_res = run_single_stress_trial(
                    engine=engine,
                    workload=workload,
                    workers=w,
                    alpha=alpha,
                )
                results.append(point_res)

    return ConcurrencyStressReport(
        evaluated_workers=workers_list,
        evaluated_alphas=alphas_list,
        evaluated_paradigms=selected_paradigms,
        total_experiments=len(results),
        results=results,
    )
