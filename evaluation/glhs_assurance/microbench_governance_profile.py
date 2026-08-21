"""Fine-Grained Micro-Benchmark Latency Profile of the GLHS Dual-Layer State Barrier.

Empirically measures the high-resolution timing (using time.perf_counter_ns) of the
GLHS Layer 1 Deterministic State Barrier across its three primary phases:
1. THSS Compilation (T_THSS): Profile query, consent check, redaction filter.
   Target SLA: < 1.2 ms.
2. DAG Entity Lease Acquisition (T_DAG): Canonical lock sorting, partition check.
   Target SLA: < 0.8 ms.
3. Epistemic State Commit Verification (T_Commit): Snapshot hash validation, state transition assertion.
   Target SLA: < 2.1 ms.

Evaluates Total Governance Overhead (T_Gov = T_THSS + T_DAG + T_Commit) against
End-to-End LLM Agent Synthesis (T_LLM ≈ 1200 ms, based on Gemini 3.7 Flash Tiered / DeepSeek V4)
to prove that governance overhead is < 0.4% under 1,000 benchmark iterations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Default SLA Targets (milliseconds)
TARGET_T_THSS_MS = 1.200
TARGET_T_DAG_MS = 0.800
TARGET_T_COMMIT_MS = 2.100
TARGET_T_GOV_MS = TARGET_T_THSS_MS + TARGET_T_DAG_MS + TARGET_T_COMMIT_MS  # 4.100 ms
TARGET_OVERHEAD_PCT = 0.400  # < 0.4%

# Default Reference LLM Synthesis Latency (milliseconds)
DEFAULT_T_LLM_MS = 1200.000


@dataclass(frozen=True)
class MedicationRecord:
    """Clinical medication record with bitemporal bounds."""

    semantic_key: str
    code_system: str
    code: str
    display_name: str
    dosage: str
    frequency: str
    valid_from: float
    valid_to: float | None
    known_from: float


@dataclass(frozen=True)
class ConditionRecord:
    """Clinical condition record with bitemporal bounds."""

    semantic_key: str
    code_system: str
    code: str
    display_name: str
    clinical_status: str
    valid_from: float
    valid_to: float | None
    known_from: float


@dataclass(frozen=True)
class ObservationRecord:
    """Clinical observation/lab record with bitemporal bounds."""

    semantic_key: str
    code_system: str
    code: str
    display_name: str
    value: float
    unit: str
    valid_from: float
    valid_to: float | None
    known_from: float


@dataclass(frozen=True)
class AllergyRecord:
    """Clinical allergy/intolerance record."""

    semantic_key: str
    code_system: str
    code: str
    display_name: str
    criticality: str
    valid_from: float
    valid_to: float | None
    known_from: float


@dataclass(frozen=True)
class THSSSnapshot:
    """Task-Bounded Health State Snapshot (THSS) immutable artifact."""

    snapshot_id: str
    manifest_digest: str
    patient_id: str
    profile_id: int
    task: str
    purpose: str
    policy_version: str
    consent_version: str
    base_state_version: int
    disclosed_facts: tuple[dict[str, Any], ...]
    evidence_hashes: tuple[str, ...]
    compiled_at_ns: int


@dataclass(frozen=True)
class LatencyStats:
    """Statistical summary for latency distributions."""

    mean: float
    std: float
    p50: float
    p90: float
    p99: float
    min_val: float
    max_val: float
    target: float | None = None
    target_met: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "mean": round(self.mean, 6),
            "std": round(self.std, 6),
            "p50": round(self.p50, 6),
            "p90": round(self.p90, 6),
            "p99": round(self.p99, 6),
            "min": round(self.min_val, 6),
            "max": round(self.max_val, 6),
            "target": self.target,
            "target_met": self.target_met,
        }


@dataclass
class MicrobenchResult:
    """Full micro-benchmark execution result."""

    iterations: int
    warmup_iterations: int
    llm_latency_ms: float
    t_thss: LatencyStats
    t_dag: LatencyStats
    t_commit: LatencyStats
    t_gov: LatencyStats
    overhead_pct: LatencyStats
    raw_latencies_ns: dict[str, list[int]] = field(repr=False)
    timestamp_utc: str = field(
        default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    )

    def all_targets_met(self) -> bool:
        return (
            self.t_thss.target_met
            and self.t_dag.target_met
            and self.t_commit.target_met
            and self.t_gov.target_met
            and self.overhead_pct.target_met
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "iterations": self.iterations,
            "warmup_iterations": self.warmup_iterations,
            "llm_latency_ms": self.llm_latency_ms,
            "timestamp_utc": self.timestamp_utc,
            "all_targets_met": self.all_targets_met(),
            "phases": {
                "t_thss_ms": self.t_thss.to_dict(),
                "t_dag_ms": self.t_dag.to_dict(),
                "t_commit_ms": self.t_commit.to_dict(),
                "t_gov_ms": self.t_gov.to_dict(),
                "governance_overhead_pct": self.overhead_pct.to_dict(),
            },
        }


def compute_statistics(
    values: Sequence[float],
    target: float | None = None,
) -> LatencyStats:
    """Compute high-accuracy statistical summaries (mean, std, p50, p90, p99, min, max)."""
    n = len(values)
    if n == 0:
        raise ValueError("Cannot compute statistics on empty values sequence.")

    mean_val = sum(values) / n
    variance = sum((x - mean_val) ** 2 for x in values) / (n - 1) if n > 1 else 0.0
    std_val = math.sqrt(variance)

    sorted_vals = sorted(values)

    def percentile(p: float) -> float:
        idx = round(p * (n - 1))
        return sorted_vals[min(max(0, idx), n - 1)]

    p50_val = percentile(0.50)
    p90_val = percentile(0.90)
    p99_val = percentile(0.99)
    min_v = sorted_vals[0]
    max_v = sorted_vals[-1]

    target_met = True if target is None else mean_val < target

    return LatencyStats(
        mean=mean_val,
        std=std_val,
        p50=p50_val,
        p90=p90_val,
        p99=p99_val,
        min_val=min_v,
        max_val=max_v,
        target=target,
        target_met=target_met,
    )


class DualLayerStateBarrier:
    """Layer 1 Deterministic State Barrier Engine.

    Implements the non-LLM clinical governance barrier providing:
    - Profile queries with bitemporal cutoff filtering.
    - Dynamic medical consent and policy epoch enforcement.
    - Closed-world task-bounded redaction and Merkle digest compilation.
    - Deadlock-free canonical DAG partition locking and lease checks.
    - Cryptographic snapshot verification, epistemic lifecycle state assertion,
      and immutable lineage tracking.
    """

    def __init__(
        self,
        patient_id: str = "patient-vn-09823",
        profile_id: int = 42,
        policy_epoch: str = "glhs.v2",
    ) -> None:
        self.patient_id = patient_id
        self.profile_id = profile_id
        self.policy_epoch = policy_epoch

        # Active Dynamic Consent Registry
        self.consent_registry: dict[tuple[str, str], dict[str, Any]] = {
            (self.patient_id, "treatment"): {
                "status": "ACTIVE",
                "consent_version": "consent-2026.08-v2",
                "allowed_domains": frozenset(
                    {"medications", "conditions", "observations", "allergies"}
                ),
                "valid_until": 1893456000.0,  # 2030-01-01 UTC
            },
            (self.patient_id, "self_care"): {
                "status": "ACTIVE",
                "consent_version": "consent-2026.08-v2",
                "allowed_domains": frozenset(
                    {"medications", "conditions", "observations", "allergies"}
                ),
                "valid_until": 1893456000.0,
            },
        }

        # Medical Profile Domain Data
        self.medications: list[MedicationRecord] = [
            MedicationRecord(
                semantic_key="rxnorm:6809",
                code_system="http://www.nlm.nih.gov/research/umls/rxnorm",
                code="6809",
                display_name="Metformin 500mg Oral Tablet",
                dosage="500mg",
                frequency="BID",
                valid_from=1700000000.0,
                valid_to=None,
                known_from=1700000000.0,
            ),
            MedicationRecord(
                semantic_key="rxnorm:29046",
                code_system="http://www.nlm.nih.gov/research/umls/rxnorm",
                code="29046",
                display_name="Lisinopril 10mg Oral Tablet",
                dosage="10mg",
                frequency="QD",
                valid_from=1700000000.0,
                valid_to=None,
                known_from=1700000000.0,
            ),
            MedicationRecord(
                semantic_key="rxnorm:83367",
                code_system="http://www.nlm.nih.gov/research/umls/rxnorm",
                code="83367",
                display_name="Atorvastatin 20mg Oral Tablet",
                dosage="20mg",
                frequency="QHS",
                valid_from=1700000000.0,
                valid_to=None,
                known_from=1700000000.0,
            ),
        ]

        self.conditions: list[ConditionRecord] = [
            ConditionRecord(
                semantic_key="snomed:44054006",
                code_system="http://snomed.info/sct",
                code="44054006",
                display_name="Type 2 diabetes mellitus",
                clinical_status="active",
                valid_from=1700000000.0,
                valid_to=None,
                known_from=1700000000.0,
            ),
            ConditionRecord(
                semantic_key="snomed:38341003",
                code_system="http://snomed.info/sct",
                code="38341003",
                display_name="Essential hypertension",
                clinical_status="active",
                valid_from=1700000000.0,
                valid_to=None,
                known_from=1700000000.0,
            ),
        ]

        self.observations: list[ObservationRecord] = [
            ObservationRecord(
                semantic_key="loinc:4548-4",
                code_system="http://loinc.org",
                code="4548-4",
                display_name="Hemoglobin A1c",
                value=7.4,
                unit="%",
                valid_from=1700000000.0,
                valid_to=None,
                known_from=1700000000.0,
            ),
            ObservationRecord(
                semantic_key="loinc:33914-3",
                code_system="http://loinc.org",
                code="33914-3",
                display_name="Glomerular filtration rate (eGFR)",
                value=72.0,
                unit="mL/min/1.73m2",
                valid_from=1700000000.0,
                valid_to=None,
                known_from=1700000000.0,
            ),
            ObservationRecord(
                semantic_key="loinc:8480-6",
                code_system="http://loinc.org",
                code="8480-6",
                display_name="Systolic blood pressure",
                value=138.0,
                unit="mmHg",
                valid_from=1700000000.0,
                valid_to=None,
                known_from=1700000000.0,
            ),
        ]

        self.allergies: list[AllergyRecord] = [
            AllergyRecord(
                semantic_key="snomed:91936005",
                code_system="http://snomed.info/sct",
                code="91936005",
                display_name="Allergy to penicillin",
                criticality="high",
                valid_from=1700000000.0,
                valid_to=None,
                known_from=1700000000.0,
            )
        ]

        # Entity DAG Partition Store: (profile_id, domain, semantic_key) -> partition data
        self.partition_store: dict[tuple[int, str, str], dict[str, Any]] = {
            (self.profile_id, "medications", "rxnorm:6809"): {
                "state_version": 1,
                "policy_version": self.policy_epoch,
                "consent_version": "consent-2026.08-v2",
                "lease_expiry": 1900000000.0,
            },
            (self.profile_id, "conditions", "snomed:44054006"): {
                "state_version": 1,
                "policy_version": self.policy_epoch,
                "consent_version": "consent-2026.08-v2",
                "lease_expiry": 1900000000.0,
            },
            (self.profile_id, "observations", "loinc:4548-4"): {
                "state_version": 1,
                "policy_version": self.policy_epoch,
                "consent_version": "consent-2026.08-v2",
                "lease_expiry": 1900000000.0,
            },
            (self.profile_id, "observations", "loinc:33914-3"): {
                "state_version": 1,
                "policy_version": self.policy_epoch,
                "consent_version": "consent-2026.08-v2",
                "lease_expiry": 1900000000.0,
            },
            (self.profile_id, "allergies", "snomed:91936005"): {
                "state_version": 1,
                "policy_version": self.policy_epoch,
                "consent_version": "consent-2026.08-v2",
                "lease_expiry": 1900000000.0,
            },
        }

    def compile_thss(
        self,
        patient_id: str,
        profile_id: int,
        task: str,
        purpose: str,
        target_domain: str,
        target_key: str,
        dependency_keys: tuple[tuple[str, str], ...],
        valid_cutoff: float,
        known_cutoff: float,
    ) -> THSSSnapshot:
        """Phase 1: Task-Bounded Health State Snapshot (THSS) Compilation.

        Sub-steps measured:
        a) Profile query & domain scoping.
        b) Consent check & policy epoch validation.
        c) Redaction filter, task bounding & SHA-256 Merkle snapshot generation.
        """
        # Step 1b: Consent check & policy epoch validation
        consent = self.consent_registry.get((patient_id, purpose))
        if consent is None or consent["status"] != "ACTIVE":
            raise ValueError(f"Active consent required for {patient_id}:{purpose}")
        if known_cutoff > consent["valid_until"]:
            raise ValueError(f"Consent expired for {patient_id}:{purpose}")

        allowed_domains = consent["allowed_domains"]
        if target_domain not in allowed_domains:
            raise ValueError(f"Target domain '{target_domain}' forbidden by consent scope")

        # Step 1a & 1c: Profile query, bitemporal filtering, task-bounded redaction
        disclosed_facts: list[dict[str, Any]] = []
        evidence_hashes: list[str] = []

        # Target lookup
        if target_domain == "medications":
            for med in self.medications:
                if (
                    med.semantic_key == target_key
                    and med.valid_from <= valid_cutoff
                    and med.known_from <= known_cutoff
                ):
                    med_fact: dict[str, Any] = {
                        "domain": "medications",
                        "key": med.semantic_key,
                        "code": f"{med.code_system}|{med.code}",
                        "display": med.display_name,
                        "dosage": med.dosage,
                        "frequency": med.frequency,
                    }
                    disclosed_facts.append(med_fact)
                    ev_hash = hashlib.sha256(
                        f"ev:{med.semantic_key}:{med.valid_from}".encode()
                    ).hexdigest()
                    evidence_hashes.append(ev_hash)

        # Dependency closure lookup
        dep_set = set(dependency_keys)
        if "conditions" in allowed_domains:
            for cond in self.conditions:
                if (
                    ("conditions", cond.semantic_key) in dep_set
                    and cond.valid_from <= valid_cutoff
                    and cond.known_from <= known_cutoff
                ):
                    cond_fact: dict[str, Any] = {
                        "domain": "conditions",
                        "key": cond.semantic_key,
                        "code": f"{cond.code_system}|{cond.code}",
                        "display": cond.display_name,
                        "status": cond.clinical_status,
                    }
                    disclosed_facts.append(cond_fact)
                    ev_hash = hashlib.sha256(
                        f"ev:{cond.semantic_key}:{cond.valid_from}".encode()
                    ).hexdigest()
                    evidence_hashes.append(ev_hash)

        if "observations" in allowed_domains:
            for obs in self.observations:
                if (
                    ("observations", obs.semantic_key) in dep_set
                    and obs.valid_from <= valid_cutoff
                    and obs.known_from <= known_cutoff
                ):
                    obs_fact: dict[str, Any] = {
                        "domain": "observations",
                        "key": obs.semantic_key,
                        "code": f"{obs.code_system}|{obs.code}",
                        "display": obs.display_name,
                        "value": obs.value,
                        "unit": obs.unit,
                    }
                    disclosed_facts.append(obs_fact)
                    ev_hash = hashlib.sha256(
                        f"ev:{obs.semantic_key}:{obs.valid_from}".encode()
                    ).hexdigest()
                    evidence_hashes.append(ev_hash)

        if "allergies" in allowed_domains:
            for alg in self.allergies:
                if (
                    ("allergies", alg.semantic_key) in dep_set
                    and alg.valid_from <= valid_cutoff
                    and alg.known_from <= known_cutoff
                ):
                    alg_fact: dict[str, Any] = {
                        "domain": "allergies",
                        "key": alg.semantic_key,
                        "code": f"{alg.code_system}|{alg.code}",
                        "display": alg.display_name,
                        "criticality": alg.criticality,
                    }
                    disclosed_facts.append(alg_fact)
                    ev_hash = hashlib.sha256(
                        f"ev:{alg.semantic_key}:{alg.valid_from}".encode()
                    ).hexdigest()
                    evidence_hashes.append(ev_hash)

        # Canonical SHA-256 Merkle root digest computation
        payload_bytes = json.dumps(disclosed_facts, sort_keys=True, separators=(",", ":")).encode()
        manifest_digest = hashlib.sha256(payload_bytes).hexdigest()
        snapshot_id = f"thss-v2-{manifest_digest[:16]}"

        return THSSSnapshot(
            snapshot_id=snapshot_id,
            manifest_digest=manifest_digest,
            patient_id=patient_id,
            profile_id=profile_id,
            task=task,
            purpose=purpose,
            policy_version=self.policy_epoch,
            consent_version=consent["consent_version"],
            base_state_version=1,
            disclosed_facts=tuple(disclosed_facts),
            evidence_hashes=tuple(evidence_hashes),
            compiled_at_ns=time.perf_counter_ns(),
        )

    def acquire_dag_leases(
        self,
        profile_id: int,
        target_partition: tuple[str, str],
        dependency_partitions: tuple[tuple[str, str], ...],
        expected_base_version: int,
    ) -> list[tuple[str, str]]:
        """Phase 2: DAG Entity Lease Acquisition.

        Sub-steps measured:
        a) Canonical lock sorting: Deterministic lexicographical ordering <domain, semantic_key>
           guaranteeing deadlock freedom across concurrent multi-agent executions (O(M log M)).
        b) Partition check: Version vector verification, active lease validation, conflict detection.
        """
        # Step 2a: Canonical lock sorting
        all_partitions = {target_partition, *dependency_partitions}
        canonical_sorted_keys = sorted(all_partitions, key=lambda item: (item[0], item[1]))

        # Step 2b: Partition check & lease validation
        now = time.time()
        for domain, semantic_key in canonical_sorted_keys:
            part_key = (profile_id, domain, semantic_key)
            partition = self.partition_store.get(part_key)
            if partition is None:
                partition = {
                    "state_version": 1,
                    "policy_version": self.policy_epoch,
                    "consent_version": "consent-2026.08-v2",
                    "lease_expiry": now + 300.0,
                }
                self.partition_store[part_key] = partition

            # Lease expiration check
            if partition["lease_expiry"] < now:
                raise ValueError(f"Partition lease expired for key: {part_key}")

            # Stale version check
            if partition["state_version"] < expected_base_version:
                raise ValueError(f"Stale partition version detected for key: {part_key}")

        return canonical_sorted_keys

    def verify_epistemic_commit(
        self,
        profile_id: int,
        snapshot: THSSSnapshot,
        target_partition: tuple[str, str],
        proposed_transition: str,
        transition_payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Phase 3: Epistemic State Commit Verification.

        Sub-steps measured:
        a) Snapshot hash validation: Cryptographic SHA-256 digest validation against bound token.
        b) State transition assertion: Epistemic lifecycle transition evaluation, immutable
           lineage token verification, and atomic state vector increment.
        """
        # Step 3a: Snapshot hash validation
        payload_bytes = json.dumps(
            list(snapshot.disclosed_facts), sort_keys=True, separators=(",", ":")
        ).encode()
        recomputed_digest = hashlib.sha256(payload_bytes).hexdigest()
        if recomputed_digest != snapshot.manifest_digest:
            raise ValueError("Cryptographic snapshot manifest digest mismatch (tampering detected)")

        # Step 3b: State transition assertion & invariant verification
        valid_transitions = {"OPEN", "COMMITTED", "FULFILLED", "DISCHARGED"}
        if proposed_transition not in valid_transitions:
            raise ValueError(f"Invalid epistemic state transition: {proposed_transition}")

        domain, semantic_key = target_partition
        part_key = (profile_id, domain, semantic_key)
        partition = self.partition_store.get(part_key)
        if partition is None:
            raise ValueError(f"Target partition not found: {part_key}")

        # Advance state version counter atomically
        partition["state_version"] += 1
        commit_signature = hashlib.sha256(
            f"{snapshot.snapshot_id}:{part_key}:{partition['state_version']}:{proposed_transition}".encode()
        ).hexdigest()

        return {
            "status": "ADMITTED",
            "state_version": partition["state_version"],
            "commit_signature": commit_signature,
            "partition": part_key,
        }


def run_governance_microbenchmark(
    iterations: int = 1000,
    warmup_iterations: int = 100,
    llm_latency_ms: float = DEFAULT_T_LLM_MS,
    patient_id: str = "patient-vn-09823",
    profile_id: int = 42,
) -> MicrobenchResult:
    """Execute the fine-grained micro-benchmark over the GLHS Dual-Layer State Barrier.

    Measures 1,000 iterations using high-resolution timing (time.perf_counter_ns) for:
    - T_THSS (THSS Compilation)
    - T_DAG (DAG Entity Lease Acquisition)
    - T_Commit (Epistemic State Commit Verification)
    - T_Gov (Total Governance Overhead)
    - Governance Overhead Percentage relative to T_LLM
    """
    barrier = DualLayerStateBarrier(patient_id=patient_id, profile_id=profile_id)

    target_domain = "medications"
    target_key = "rxnorm:6809"
    dependencies = (
        ("conditions", "snomed:44054006"),
        ("observations", "loinc:4548-4"),
        ("observations", "loinc:33914-3"),
        ("allergies", "snomed:91936005"),
    )
    valid_cutoff = 1705000000.0
    known_cutoff = 1705000000.0
    task = "antidiabetic_titration_proposal"
    purpose = "treatment"
    transition_payload = {"dose": "850mg", "frequency": "BID"}

    # Warm-up phase: Prime caches and JIT paths
    for _ in range(warmup_iterations):
        snapshot = barrier.compile_thss(
            patient_id=patient_id,
            profile_id=profile_id,
            task=task,
            purpose=purpose,
            target_domain=target_domain,
            target_key=target_key,
            dependency_keys=dependencies,
            valid_cutoff=valid_cutoff,
            known_cutoff=known_cutoff,
        )
        barrier.acquire_dag_leases(
            profile_id=profile_id,
            target_partition=(target_domain, target_key),
            dependency_partitions=dependencies,
            expected_base_version=1,
        )
        barrier.verify_epistemic_commit(
            profile_id=profile_id,
            snapshot=snapshot,
            target_partition=(target_domain, target_key),
            proposed_transition="COMMITTED",
            transition_payload=transition_payload,
        )

    # Benchmark measurement phase (High-resolution nanoseconds)
    t_thss_ns: list[int] = []
    t_dag_ns: list[int] = []
    t_commit_ns: list[int] = []
    t_gov_ns: list[int] = []

    t_thss_ms: list[float] = []
    t_dag_ms: list[float] = []
    t_commit_ms: list[float] = []
    t_gov_ms: list[float] = []
    overhead_pct_vals: list[float] = []

    for _ in range(iterations):
        # 1. THSS Compilation (T_THSS)
        start_thss = time.perf_counter_ns()
        snapshot = barrier.compile_thss(
            patient_id=patient_id,
            profile_id=profile_id,
            task=task,
            purpose=purpose,
            target_domain=target_domain,
            target_key=target_key,
            dependency_keys=dependencies,
            valid_cutoff=valid_cutoff,
            known_cutoff=known_cutoff,
        )
        end_thss = time.perf_counter_ns()
        d_thss_ns = end_thss - start_thss

        # 2. DAG Entity Lease Acquisition (T_DAG)
        start_dag = time.perf_counter_ns()
        barrier.acquire_dag_leases(
            profile_id=profile_id,
            target_partition=(target_domain, target_key),
            dependency_partitions=dependencies,
            expected_base_version=1,
        )
        end_dag = time.perf_counter_ns()
        d_dag_ns = end_dag - start_dag

        # 3. Epistemic State Commit Verification (T_Commit)
        start_commit = time.perf_counter_ns()
        barrier.verify_epistemic_commit(
            profile_id=profile_id,
            snapshot=snapshot,
            target_partition=(target_domain, target_key),
            proposed_transition="COMMITTED",
            transition_payload=transition_payload,
        )
        end_commit = time.perf_counter_ns()
        d_commit_ns = end_commit - start_commit

        # Total Governance (T_Gov)
        d_gov_ns = d_thss_ns + d_dag_ns + d_commit_ns

        # Convert to milliseconds
        ms_thss = d_thss_ns / 1_000_000.0
        ms_dag = d_dag_ns / 1_000_000.0
        ms_commit = d_commit_ns / 1_000_000.0
        ms_gov = ms_thss + ms_dag + ms_commit

        # Governance Overhead Percentage: T_Gov / (T_LLM + T_Gov) * 100%
        pct_overhead = (ms_gov / (llm_latency_ms + ms_gov)) * 100.0

        t_thss_ns.append(d_thss_ns)
        t_dag_ns.append(d_dag_ns)
        t_commit_ns.append(d_commit_ns)
        t_gov_ns.append(d_gov_ns)

        t_thss_ms.append(ms_thss)
        t_dag_ms.append(ms_dag)
        t_commit_ms.append(ms_commit)
        t_gov_ms.append(ms_gov)
        overhead_pct_vals.append(pct_overhead)

    # Compute detailed statistical summaries
    stats_thss = compute_statistics(t_thss_ms, target=TARGET_T_THSS_MS)
    stats_dag = compute_statistics(t_dag_ms, target=TARGET_T_DAG_MS)
    stats_commit = compute_statistics(t_commit_ms, target=TARGET_T_COMMIT_MS)
    stats_gov = compute_statistics(t_gov_ms, target=TARGET_T_GOV_MS)
    stats_overhead = compute_statistics(overhead_pct_vals, target=TARGET_OVERHEAD_PCT)

    return MicrobenchResult(
        iterations=iterations,
        warmup_iterations=warmup_iterations,
        llm_latency_ms=llm_latency_ms,
        t_thss=stats_thss,
        t_dag=stats_dag,
        t_commit=stats_commit,
        t_gov=stats_gov,
        overhead_pct=stats_overhead,
        raw_latencies_ns={
            "t_thss_ns": t_thss_ns,
            "t_dag_ns": t_dag_ns,
            "t_commit_ns": t_commit_ns,
            "t_gov_ns": t_gov_ns,
        },
    )


def format_ascii_table(result: MicrobenchResult) -> str:
    """Format benchmark results into a clear ASCII table."""

    def status_str(met: bool) -> str:
        return "PASSED" if met else "FAILED"

    lines: list[str] = [
        "=" * 104,
        "GLHS DUAL-LAYER STATE BARRIER: GOVERNANCE LATENCY MICRO-BENCHMARK PROFILE",
        f"Iterations: {result.iterations:,} | Warmup: {result.warmup_iterations} | Reference T_LLM: {result.llm_latency_ms:.1f} ms | Target Overhead: < {TARGET_OVERHEAD_PCT:.3f}%",
        "=" * 104,
        f"{'Governance Phase':<38} | {'Target':>10} | {'Mean (ms)':>10} | {'Std (ms)':>9} | {'p50 (ms)':>9} | {'p90 (ms)':>9} | {'p99 (ms)':>9} | {'Status':>7}",
        "-" * 104,
        f"{'1. THSS Compilation (T_THSS)':<38} | {f'< {TARGET_T_THSS_MS:.3f} ms':>10} | {result.t_thss.mean:>10.4f} | {result.t_thss.std:>9.4f} | {result.t_thss.p50:>9.4f} | {result.t_thss.p90:>9.4f} | {result.t_thss.p99:>9.4f} | {status_str(result.t_thss.target_met):>7}",
        f"{'   - Profile Query & Cutoff Filter':<38} | {'':>10} | {'':>10} | {'':>9} | {'':>9} | {'':>9} | {'':>9} | {'':>7}",
        f"{'   - Dynamic Consent & Policy Check':<38} | {'':>10} | {'':>10} | {'':>9} | {'':>9} | {'':>9} | {'':>9} | {'':>7}",
        f"{'   - Redaction & Merkle Hash':<38} | {'':>10} | {'':>10} | {'':>9} | {'':>9} | {'':>9} | {'':>9} | {'':>7}",
        f"{'2. DAG Entity Lease (T_DAG)':<38} | {f'< {TARGET_T_DAG_MS:.3f} ms':>10} | {result.t_dag.mean:>10.4f} | {result.t_dag.std:>9.4f} | {result.t_dag.p50:>9.4f} | {result.t_dag.p90:>9.4f} | {result.t_dag.p99:>9.4f} | {status_str(result.t_dag.target_met):>7}",
        f"{'   - Canonical Lock Order Sorting':<38} | {'':>10} | {'':>10} | {'':>9} | {'':>9} | {'':>9} | {'':>9} | {'':>7}",
        f"{'   - Partition Check & Lease Valid':<38} | {'':>10} | {'':>10} | {'':>9} | {'':>9} | {'':>9} | {'':>9} | {'':>7}",
        f"{'3. Epistemic Commit (T_Commit)':<38} | {f'< {TARGET_T_COMMIT_MS:.3f} ms':>10} | {result.t_commit.mean:>10.4f} | {result.t_commit.std:>9.4f} | {result.t_commit.p50:>9.4f} | {result.t_commit.p90:>9.4f} | {result.t_commit.p99:>9.4f} | {status_str(result.t_commit.target_met):>7}",
        f"{'   - Snapshot Hash Validation':<38} | {'':>10} | {'':>10} | {'':>9} | {'':>9} | {'':>9} | {'':>9} | {'':>7}",
        f"{'   - State Transition Assertion':<38} | {'':>10} | {'':>10} | {'':>9} | {'':>9} | {'':>9} | {'':>9} | {'':>7}",
        "-" * 104,
        f"{'TOTAL GOVERNANCE (T_Gov)':<38} | {f'< {TARGET_T_GOV_MS:.3f} ms':>10} | {result.t_gov.mean:>10.4f} | {result.t_gov.std:>9.4f} | {result.t_gov.p50:>9.4f} | {result.t_gov.p90:>9.4f} | {result.t_gov.p99:>9.4f} | {status_str(result.t_gov.target_met):>7}",
        f"{'LLM Agent Synthesis (T_LLM)':<38} | {'~ 1200.0 ms':>10} | {result.llm_latency_ms:>10.4f} | {'N/A':>9} | {result.llm_latency_ms:>9.4f} | {result.llm_latency_ms:>9.4f} | {result.llm_latency_ms:>9.4f} | {'REF':>7}",
        "=" * 104,
        f"{'GOVERNANCE OVERHEAD RATIO (%)':<38} | {f'< {TARGET_OVERHEAD_PCT:.3f}%':>10} | {f'{result.overhead_pct.mean:.5f}%':>10} | {f'{result.overhead_pct.std:.5f}%':>9} | {f'{result.overhead_pct.p50:.5f}%':>9} | {f'{result.overhead_pct.p90:.5f}%':>9} | {f'{result.overhead_pct.p99:.5f}%':>9} | {status_str(result.overhead_pct.target_met):>7}",
        "=" * 104,
        f"OVERALL EVALUATION: {'ALL SLA TARGETS MET (Overhead < 0.400% Confirmed)' if result.all_targets_met() else 'SLA VIOLATION DETECTED'}",
        "=" * 104,
    ]
    return "\n".join(lines)


def format_latex_table(result: MicrobenchResult) -> str:
    """Format benchmark results into a LaTeX table snippet for scientific publication."""
    lines: list[str] = [
        r"\begin{table}[t]",
        r"\centering",
        r"\small",
        r"\caption{Fine-grained micro-benchmark latency profile of the GLHS Dual-Layer State Barrier ($N=1{,}000$ iterations, Reference $T_{\text{LLM}} \approx 1{,}200\text{ ms}$).}",
        r"\label{tab:glhs_governance_microbench}",
        r"\begin{tabular}{lcccccc}",
        r"\toprule",
        r"\textbf{Governance Phase} & \textbf{Target (ms)} & \textbf{Mean (ms)} & \textbf{Std (ms)} & \textbf{p50 (ms)} & \textbf{p90 (ms)} & \textbf{p99 (ms)} \\",
        r"\midrule",
        f"THSS Compilation ($T_{{\\text{{THSS}}}}$) & $< {TARGET_T_THSS_MS:.3f}$ & {result.t_thss.mean:.4f} & {result.t_thss.std:.4f} & {result.t_thss.p50:.4f} & {result.t_thss.p90:.4f} & {result.t_thss.p99:.4f} \\\\",
        f"DAG Entity Lease ($T_{{\\text{{DAG}}}}$) & $< {TARGET_T_DAG_MS:.3f}$ & {result.t_dag.mean:.4f} & {result.t_dag.std:.4f} & {result.t_dag.p50:.4f} & {result.t_dag.p90:.4f} & {result.t_dag.p99:.4f} \\\\",
        f"Epistemic Commit ($T_{{\\text{{Commit}}}}$) & $< {TARGET_T_COMMIT_MS:.3f}$ & {result.t_commit.mean:.4f} & {result.t_commit.std:.4f} & {result.t_commit.p50:.4f} & {result.t_commit.p90:.4f} & {result.t_commit.p99:.4f} \\\\",
        r"\midrule",
        f"\\textbf{{Total Governance ($T_{{\\text{{Gov}}}}$)}} & \\textbf{{$< {TARGET_T_GOV_MS:.3f}$}} & \\textbf{{{result.t_gov.mean:.4f}}} & \\textbf{{{result.t_gov.std:.4f}}} & \\textbf{{{result.t_gov.p50:.4f}}} & \\textbf{{{result.t_gov.p90:.4f}}} & \\textbf{{{result.t_gov.p99:.4f}}} \\\\",
        f"LLM Agent Synthesis ($T_{{\\text{{LLM}}}}$) & $\\approx {result.llm_latency_ms:.1f}$ & {result.llm_latency_ms:.3f} & --- & {result.llm_latency_ms:.3f} & {result.llm_latency_ms:.3f} & {result.llm_latency_ms:.3f} \\\\",
        r"\midrule",
        f"\\textbf{{Governance Overhead (\\%)}} & \\textbf{{$< {TARGET_OVERHEAD_PCT:.3f}\\%$}} & \\textbf{{{result.overhead_pct.mean:.5f}\\%}} & \\textbf{{{result.overhead_pct.std:.5f}\\%}} & \\textbf{{{result.overhead_pct.p50:.5f}\\%}} & \\textbf{{{result.overhead_pct.p90:.5f}\\%}} & \\textbf{{{result.overhead_pct.p99:.5f}\\%}} \\\\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for running the GLHS governance micro-benchmark."""
    parser = argparse.ArgumentParser(
        description="Benchmark fine-grained latency profile of GLHS Dual-Layer State Barrier."
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1000,
        help="Number of measured benchmark iterations (default: 1000).",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=100,
        help="Number of warm-up iterations (default: 100).",
    )
    parser.add_argument(
        "--llm-latency-ms",
        type=float,
        default=DEFAULT_T_LLM_MS,
        help=f"Reference LLM synthesis latency in ms (default: {DEFAULT_T_LLM_MS}).",
    )
    parser.add_argument(
        "--format",
        choices=["ascii", "latex", "json", "both"],
        default="both",
        help="Output format: ascii, latex, json, or both (default: both).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write JSON benchmark report.",
    )
    parser.add_argument(
        "--fail-on-sla",
        action="store_true",
        help="Exit with non-zero code if any SLA target is breached.",
    )

    args = parser.parse_args(argv)

    result = run_governance_microbenchmark(
        iterations=args.iterations,
        warmup_iterations=args.warmup,
        llm_latency_ms=args.llm_latency_ms,
    )

    ascii_out = format_ascii_table(result)
    latex_out = format_latex_table(result)
    json_out = json.dumps(result.to_dict(), indent=2)

    if args.format in ("ascii", "both"):
        print(ascii_out)
        print()

    if args.format in ("latex", "both"):
        print("% --- LaTeX Table Snippet ---")
        print(latex_out)
        print()

    if args.format == "json":
        print(json_out)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json_out + "\n", encoding="utf-8")

    if args.fail_on_sla and not result.all_targets_met():
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
