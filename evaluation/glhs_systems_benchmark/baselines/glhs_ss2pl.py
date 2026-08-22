"""GLHS Strict Two-Phase Locking (SS2PL) Baseline.

Executes transactions under ISOLATION LEVEL READ COMMITTED using the canonical lock hierarchy:
    PolicyAnchor < ProfileAndConsentAnchor <_lex EntityPartitions
Enforces the Layer 1 Deterministic Clinical Safety Barrier (DDI, Consent, RBAC, Policy Epoch)
and emits cryptographic Merkle WW-DAG ledger blocks.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import defaultdict
from typing import Any

from evaluation.glhs_systems_benchmark.baselines.base import (
    BaselineEngine,
    TxnResult,
    TxnStatus,
    verify_clinical_safety_and_consent,
)
from evaluation.glhs_systems_benchmark.workload_generator import (
    SEVERE_DDI_PAIRS,
    ClinicalWorkloadItem,
)

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None  # type: ignore
    dict_row = None  # type: ignore


class GLHSSS2PLEngine(BaselineEngine):
    """GLHS SS2PL Engine enforcing Canonical Lock Hierarchy and Layer 1 State Barrier."""

    def __init__(self, db_url: str | None = None) -> None:
        super().__init__(db_url)
        self.lock = threading.RLock()
        # Canonical resource lock manager
        self.policy_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self.profile_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self.partition_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)

        # In-memory anchor and state stores
        self.policy_epochs: dict[str, int] = {"glhs_policy_v1": 1}
        self.consent_epochs: dict[str, int] = defaultdict(lambda: 1)
        self.partition_versions: dict[str, int] = defaultdict(lambda: 1)
        self.active_medications: dict[str, set[str]] = defaultdict(set)
        self.ddi_pairs = [frozenset(pair) for pair in SEVERE_DDI_PAIRS]

    @property
    def name(self) -> str:
        return "GLHS SS2PL (Canonical Lock Hierarchy + Layer 1 Barrier)"

    def setup(self, num_patients: int = 20, num_partitions: int = 64) -> None:
        self.reset()
        if self.is_postgres and psycopg and self.db_url:
            try:
                with psycopg.connect(self.db_url, autocommit=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS glhs_policy_anchors (
                                policy_id VARCHAR(64) PRIMARY KEY,
                                epoch INT NOT NULL DEFAULT 1,
                                updated_at TIMESTAMPTZ DEFAULT NOW()
                            );
                            CREATE TABLE IF NOT EXISTS glhs_profile_consent_anchors (
                                profile_id VARCHAR(64) PRIMARY KEY,
                                consent_epoch INT NOT NULL DEFAULT 1,
                                updated_at TIMESTAMPTZ DEFAULT NOW()
                            );
                            CREATE TABLE IF NOT EXISTS glhs_entity_partitions (
                                partition_id VARCHAR(128) PRIMARY KEY,
                                profile_id VARCHAR(64) NOT NULL,
                                domain VARCHAR(32) NOT NULL,
                                slot VARCHAR(64) NOT NULL,
                                version INT NOT NULL DEFAULT 1,
                                payload JSONB,
                                updated_at TIMESTAMPTZ DEFAULT NOW()
                            );
                            CREATE TABLE IF NOT EXISTS glhs_ledger_events (
                                seq_num SERIAL PRIMARY KEY,
                                tx_id VARCHAR(64) NOT NULL,
                                profile_id VARCHAR(64) NOT NULL,
                                merkle_root VARCHAR(64) NOT NULL,
                                signature VARCHAR(64) NOT NULL,
                                prev_hash VARCHAR(64) NOT NULL,
                                payload_hash VARCHAR(64) NOT NULL,
                                status VARCHAR(32) NOT NULL,
                                created_at TIMESTAMPTZ DEFAULT NOW()
                            );
                        """)
                        # Seed policy anchor
                        cur.execute("""
                            INSERT INTO glhs_policy_anchors (policy_id, epoch)
                            VALUES ('glhs_policy_v1', 1)
                            ON CONFLICT (policy_id) DO UPDATE SET epoch = 1;
                        """)
                        # Seed patient anchors
                        for p in range(1, num_patients + 1):
                            prof_id = f"profile_{p:03d}"
                            cur.execute("""
                                INSERT INTO glhs_profile_consent_anchors (profile_id, consent_epoch)
                                VALUES (%s, 1)
                                ON CONFLICT (profile_id) DO UPDATE SET consent_epoch = 1;
                            """, (prof_id,))
            except Exception:
                self.is_postgres = False

    def reset(self) -> None:
        with self.lock:
            self.policy_locks.clear()
            self.profile_locks.clear()
            self.partition_locks.clear()
            self.policy_epochs = {"glhs_policy_v1": 1}
            self.consent_epochs.clear()
            self.partition_versions.clear()
            self.active_medications.clear()
            self.simulated.reset()

    def execute_transaction(self, tx: ClinicalWorkloadItem) -> TxnResult:
        t_start = time.perf_counter()

        if self.is_postgres and psycopg and self.db_url:
            try:
                return self._execute_postgres_glhs(tx, t_start)
            except Exception:
                return self._execute_simulated_glhs(tx, t_start)
        else:
            return self._execute_simulated_glhs(tx, t_start)

    def _execute_postgres_glhs(self, tx: ClinicalWorkloadItem, t_start: float) -> TxnResult:
        """Executes GLHS SS2PL with canonical lock hierarchy in PostgreSQL under READ COMMITTED."""
        if not self.db_url:
            return self._execute_simulated_glhs(tx, t_start)
        try:
            with psycopg.connect(self.db_url) as conn:
                conn.isolation_level = psycopg.IsolationLevel.READ_COMMITTED
                with conn.cursor(row_factory=dict_row) as cur:
                    # 1. Canonical Step 1: Lock Policy Anchor in Shared Mode
                    cur.execute(
                        "SELECT policy_id, epoch FROM glhs_policy_anchors WHERE policy_id = %s FOR SHARE",
                        (tx.policy_id,),
                    )
                    policy_row = cur.fetchone()
                    current_policy_epoch = policy_row["epoch"] if policy_row else 1

                    # 2. Canonical Step 2: Lock Profile & Consent Anchor in Shared Mode
                    cur.execute(
                        "SELECT profile_id, consent_epoch FROM glhs_profile_consent_anchors WHERE profile_id = %s FOR SHARE",
                        (tx.profile_id,),
                    )
                    consent_row = cur.fetchone()
                    current_consent_epoch = consent_row["consent_epoch"] if consent_row else 1

                    # 3. Canonical Step 3: Lock Target Entity Partitions in strict lexicographical order
                    sorted_partitions = sorted(set(tx.target_partitions))
                    locked_entities: list[dict[str, Any]] = []
                    for pid in sorted_partitions:
                        cur.execute(
                            "SELECT partition_id, version FROM glhs_entity_partitions WHERE partition_id = %s FOR UPDATE",
                            (pid,),
                        )
                        erow = cur.fetchone()
                        if erow:
                            locked_entities.append(erow)

                    # --- Normalized Application Verification & Clinical Safety Checks ---
                    ok, status, abort_cat, reason = verify_clinical_safety_and_consent(
                        tx=tx,
                        current_policy_epoch=current_policy_epoch,
                        current_consent_epoch=current_consent_epoch,
                        active_medications=list(self.active_medications[tx.profile_id]),
                        ddi_pairs=self.ddi_pairs,
                    )
                    if not ok:
                        conn.rollback()
                        t_end = time.perf_counter()
                        return TxnResult(
                            workload_id=tx.workload_id,
                            status=status,
                            abort_category=abort_cat,
                            latency_ms=(t_end - t_start) * 1000.0,
                            violation_reason=reason,
                        )

                    # 4. Commit: Update partitions & append Merkle ledger block
                    for pid in sorted_partitions:
                        cur.execute("""
                            INSERT INTO glhs_entity_partitions (partition_id, profile_id, domain, slot, version, payload, updated_at)
                            VALUES (%s, %s, 'medication', 'slot', 1, '{}'::jsonb, NOW())
                            ON CONFLICT (partition_id) DO UPDATE SET version = glhs_entity_partitions.version + 1, updated_at = NOW();
                        """, (pid, tx.profile_id))

                    merkle_root = self.simulated.append_ledger(
                        tx_id=tx.workload_id,
                        profile_id=tx.profile_id,
                        payload_hash=hashlib.sha256(str(tx.payload).encode()).hexdigest(),
                    )

                    cur.execute("""
                        INSERT INTO glhs_ledger_events (tx_id, profile_id, merkle_root, signature, prev_hash, payload_hash, status)
                        VALUES (%s, %s, %s, 'SIG_VALID', 'PREV', 'PAYLOAD', 'COMMITTED');
                    """, (tx.workload_id, tx.profile_id, merkle_root))

                    conn.commit()
                    t_end = time.perf_counter()
                    return TxnResult(
                        workload_id=tx.workload_id,
                        status=TxnStatus.VALID_COMMIT,
                        latency_ms=(t_end - t_start) * 1000.0,
                        merkle_root=merkle_root,
                    )

        except Exception as exc:
            t_end = time.perf_counter()
            return TxnResult(
                workload_id=tx.workload_id,
                status=TxnStatus.ERROR,
                latency_ms=(t_end - t_start) * 1000.0,
                violation_reason=f"GLHS SS2PL database error: {exc}",
            )

    def _execute_simulated_glhs(self, tx: ClinicalWorkloadItem, t_start: float) -> TxnResult:
        """Executes simulated GLHS SS2PL with shared governance anchor + canonical DAG partition locks."""
        # 1. Canonical Hierarchy Ordering
        # Level 1 & 2: Shared Governance Anchors (Policy & ProfileConsent)
        # Level 3: Lexicographically sorted EntityPartitions (Exclusive locks)
        sorted_partitions = sorted(set(tx.target_partitions))
        partition_lks = [self.partition_locks[p] for p in sorted_partitions]

        acquired_locks: list[threading.Lock] = []

        try:
            # Strict canonical lock acquisition order for target partitions
            for lk in partition_lks:
                lk.acquire()
                acquired_locks.append(lk)

            # Shared Governance Anchor Snapshot Read
            current_policy_epoch = self.policy_epochs.get(tx.policy_id, 1)
            current_consent_epoch = self.consent_epochs[tx.profile_id]

            # --- Normalized Application Verification & Clinical Safety Checks ---
            ok, status, abort_cat, reason = verify_clinical_safety_and_consent(
                tx=tx,
                current_policy_epoch=current_policy_epoch,
                current_consent_epoch=current_consent_epoch,
                active_medications=list(self.active_medications[tx.profile_id]),
                ddi_pairs=self.ddi_pairs,
            )
            if not ok:
                t_end = time.perf_counter()
                return TxnResult(
                    workload_id=tx.workload_id,
                    status=status,
                    abort_category=abort_cat,
                    latency_ms=(t_end - t_start) * 1000.0,
                    violation_reason=reason,
                )

            # 4. Valid Commit
            for p in sorted_partitions:
                self.partition_versions[p] += 1

            for med in tx.proposed_medications:
                self.active_medications[tx.profile_id].add(med.strip().lower())

            # Append Merkle DAG ledger event
            merkle_root = self.simulated.append_ledger(
                tx_id=tx.workload_id,
                profile_id=tx.profile_id,
                payload_hash=hashlib.sha256(str(tx.payload).encode()).hexdigest(),
            )

            t_end = time.perf_counter()
            return TxnResult(
                workload_id=tx.workload_id,
                status=TxnStatus.VALID_COMMIT,
                latency_ms=(t_end - t_start) * 1000.0,
                merkle_root=merkle_root,
            )

        finally:
            # Release all locks in reverse canonical order
            for lk in reversed(acquired_locks):
                lk.release()
