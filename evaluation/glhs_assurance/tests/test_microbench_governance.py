"""Unit tests for GLHS Dual-Layer State Barrier Micro-Benchmark."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.glhs_assurance.microbench_governance_profile import (
    DEFAULT_T_LLM_MS,
    TARGET_OVERHEAD_PCT,
    TARGET_T_COMMIT_MS,
    TARGET_T_DAG_MS,
    TARGET_T_GOV_MS,
    TARGET_T_THSS_MS,
    DualLayerStateBarrier,
    THSSSnapshot,
    compute_statistics,
    format_ascii_table,
    format_latex_table,
    main,
    run_governance_microbenchmark,
)


def test_microbenchmark_full_1000_iterations_sla_compliance() -> None:
    """Verify that 1,000 iterations execute and strictly meet all SLA targets."""
    result = run_governance_microbenchmark(
        iterations=1000,
        warmup_iterations=50,
        llm_latency_ms=DEFAULT_T_LLM_MS,
    )

    assert result.iterations == 1000
    assert result.warmup_iterations == 50
    assert result.all_targets_met() is True

    # Phase 1: T_THSS < 1.2 ms
    assert result.t_thss.target == TARGET_T_THSS_MS
    assert result.t_thss.mean < TARGET_T_THSS_MS
    assert result.t_thss.p99 < TARGET_T_THSS_MS
    assert result.t_thss.target_met is True

    # Phase 2: T_DAG < 0.8 ms
    assert result.t_dag.target == TARGET_T_DAG_MS
    assert result.t_dag.mean < TARGET_T_DAG_MS
    assert result.t_dag.p99 < TARGET_T_DAG_MS
    assert result.t_dag.target_met is True

    # Phase 3: T_Commit < 2.1 ms
    assert result.t_commit.target == TARGET_T_COMMIT_MS
    assert result.t_commit.mean < TARGET_T_COMMIT_MS
    assert result.t_commit.p99 < TARGET_T_COMMIT_MS
    assert result.t_commit.target_met is True

    # Total Governance Overhead: T_Gov < 4.1 ms
    assert result.t_gov.target == TARGET_T_GOV_MS
    assert result.t_gov.mean < TARGET_T_GOV_MS
    assert result.t_gov.p99 < TARGET_T_GOV_MS
    assert result.t_gov.target_met is True

    # Governance Overhead Ratio: < 0.400%
    assert result.overhead_pct.target == TARGET_OVERHEAD_PCT
    assert result.overhead_pct.mean < TARGET_OVERHEAD_PCT
    assert result.overhead_pct.p99 < TARGET_OVERHEAD_PCT
    assert result.overhead_pct.target_met is True

    # Check percentile monotonicity
    for stats in (
        result.t_thss,
        result.t_dag,
        result.t_commit,
        result.t_gov,
        result.overhead_pct,
    ):
        assert stats.min_val <= stats.p50 <= stats.p90 <= stats.p99 <= stats.max_val
        assert stats.std >= 0.0


def test_thss_compilation_semantics_and_filtering() -> None:
    """Verify task-bounding, consent gating, bitemporal cutoff, and Merkle digest generation."""
    barrier = DualLayerStateBarrier(patient_id="test-p1", profile_id=101)

    # 1. Successful compilation with task-bounded dependencies
    snapshot = barrier.compile_thss(
        patient_id="test-p1",
        profile_id=101,
        task="titration_review",
        purpose="treatment",
        target_domain="medications",
        target_key="rxnorm:6809",
        dependency_keys=(("conditions", "snomed:44054006"), ("observations", "loinc:4548-4")),
        valid_cutoff=1705000000.0,
        known_cutoff=1705000000.0,
    )

    assert snapshot.patient_id == "test-p1"
    assert snapshot.profile_id == 101
    assert snapshot.manifest_digest is not None
    assert len(snapshot.manifest_digest) == 64  # SHA-256 hex length
    assert snapshot.snapshot_id.startswith("thss-v2-")
    assert len(snapshot.disclosed_facts) == 3  # 1 target med + 1 condition + 1 observation
    assert len(snapshot.evidence_hashes) == 3

    # Verify closed-world filtering (unrelated conditions/observations excluded)
    fact_keys = {f["key"] for f in snapshot.disclosed_facts}
    assert "rxnorm:6809" in fact_keys
    assert "snomed:44054006" in fact_keys
    assert "loinc:4548-4" in fact_keys
    assert "rxnorm:29046" not in fact_keys
    assert "snomed:38341003" not in fact_keys

    # 2. Consent gating rejection
    with pytest.raises(ValueError, match="Active consent required"):
        barrier.compile_thss(
            patient_id="unconsented-patient",
            profile_id=101,
            task="titration_review",
            purpose="treatment",
            target_domain="medications",
            target_key="rxnorm:6809",
            dependency_keys=(),
            valid_cutoff=1705000000.0,
            known_cutoff=1705000000.0,
        )

    # 3. Forbidden domain rejection
    barrier.consent_registry[("test-p1", "treatment")]["allowed_domains"] = frozenset(
        {"conditions"}
    )
    with pytest.raises(ValueError, match="Target domain 'medications' forbidden"):
        barrier.compile_thss(
            patient_id="test-p1",
            profile_id=101,
            task="titration_review",
            purpose="treatment",
            target_domain="medications",
            target_key="rxnorm:6809",
            dependency_keys=(),
            valid_cutoff=1705000000.0,
            known_cutoff=1705000000.0,
        )


def test_dag_entity_lease_canonical_sorting_and_partition_checks() -> None:
    """Verify deadlock-free canonical sorting and DAG partition lease checks."""
    barrier = DualLayerStateBarrier(patient_id="test-p2", profile_id=202)

    # Unsorted input keys across domains
    target = ("medications", "rxnorm:6809")
    deps = (
        ("observations", "loinc:8480-6"),
        ("conditions", "snomed:44054006"),
        ("allergies", "snomed:91936005"),
        ("observations", "loinc:4548-4"),
    )

    sorted_keys = barrier.acquire_dag_leases(
        profile_id=202,
        target_partition=target,
        dependency_partitions=deps,
        expected_base_version=1,
    )

    # Verify canonical lexicographical ordering
    assert sorted_keys == [
        ("allergies", "snomed:91936005"),
        ("conditions", "snomed:44054006"),
        ("medications", "rxnorm:6809"),
        ("observations", "loinc:4548-4"),
        ("observations", "loinc:8480-6"),
    ]

    # Stale version detection
    barrier.partition_store[(202, "medications", "rxnorm:6809")]["state_version"] = 0
    with pytest.raises(ValueError, match="Stale partition version detected"):
        barrier.acquire_dag_leases(
            profile_id=202,
            target_partition=target,
            dependency_partitions=deps,
            expected_base_version=1,
        )

    # Expired lease detection
    barrier.partition_store[(202, "medications", "rxnorm:6809")]["state_version"] = 1
    barrier.partition_store[(202, "medications", "rxnorm:6809")]["lease_expiry"] = 0.0
    with pytest.raises(ValueError, match="Partition lease expired"):
        barrier.acquire_dag_leases(
            profile_id=202,
            target_partition=target,
            dependency_partitions=deps,
            expected_base_version=1,
        )


def test_epistemic_state_commit_verification_and_tamper_detection() -> None:
    """Verify cryptographic SHA-256 snapshot verification and epistemic state assertion."""
    barrier = DualLayerStateBarrier(patient_id="test-p3", profile_id=303)

    snapshot = barrier.compile_thss(
        patient_id="test-p3",
        profile_id=303,
        task="titration_review",
        purpose="treatment",
        target_domain="medications",
        target_key="rxnorm:6809",
        dependency_keys=(("conditions", "snomed:44054006"),),
        valid_cutoff=1705000000.0,
        known_cutoff=1705000000.0,
    )

    target_part = ("medications", "rxnorm:6809")

    # 1. Valid commit transition
    res = barrier.verify_epistemic_commit(
        profile_id=303,
        snapshot=snapshot,
        target_partition=target_part,
        proposed_transition="COMMITTED",
        transition_payload={"dose": "1000mg"},
    )
    assert res["status"] == "ADMITTED"
    assert res["state_version"] == 2
    assert "commit_signature" in res

    # 2. Tampered snapshot detection (corrupted fact payload)
    tampered_facts = list(snapshot.disclosed_facts)
    tampered_facts[0] = {**tampered_facts[0], "dosage": "9999mg"}
    tampered_snapshot = THSSSnapshot(
        snapshot_id=snapshot.snapshot_id,
        manifest_digest=snapshot.manifest_digest,  # Original digest mismatching tampered facts
        patient_id=snapshot.patient_id,
        profile_id=snapshot.profile_id,
        task=snapshot.task,
        purpose=snapshot.purpose,
        policy_version=snapshot.policy_version,
        consent_version=snapshot.consent_version,
        base_state_version=snapshot.base_state_version,
        disclosed_facts=tuple(tampered_facts),
        evidence_hashes=snapshot.evidence_hashes,
        compiled_at_ns=snapshot.compiled_at_ns,
    )

    with pytest.raises(ValueError, match="tampering detected"):
        barrier.verify_epistemic_commit(
            profile_id=303,
            snapshot=tampered_snapshot,
            target_partition=target_part,
            proposed_transition="COMMITTED",
            transition_payload={"dose": "1000mg"},
        )

    # 3. Invalid transition rejection
    with pytest.raises(ValueError, match="Invalid epistemic state transition"):
        barrier.verify_epistemic_commit(
            profile_id=303,
            snapshot=snapshot,
            target_partition=target_part,
            proposed_transition="INVALID_EPISODIC_STATE",
            transition_payload={},
        )


def test_statistical_computation_accuracy() -> None:
    """Verify mean, std, percentiles against reference mathematical definitions."""
    sample = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    stats = compute_statistics(sample, target=8.0)

    assert stats.mean == pytest.approx(5.5, rel=1e-5)
    assert stats.min_val == 1.0
    assert stats.max_val == 10.0
    assert stats.p50 == pytest.approx(5.5, abs=0.5)
    assert stats.target == 8.0
    assert stats.target_met is True

    # Failed SLA check
    stats_failed = compute_statistics(sample, target=5.0)
    assert stats_failed.target_met is False

    with pytest.raises(ValueError, match="empty values"):
        compute_statistics([])


def test_ascii_and_latex_table_formatters() -> None:
    """Verify ASCII and LaTeX table format generation."""
    result = run_governance_microbenchmark(iterations=10, warmup_iterations=2)

    ascii_out = format_ascii_table(result)
    assert "GLHS DUAL-LAYER STATE BARRIER" in ascii_out
    assert "THSS Compilation" in ascii_out
    assert "DAG Entity Lease" in ascii_out
    assert "Epistemic Commit" in ascii_out
    assert "TOTAL GOVERNANCE" in ascii_out
    assert "PASSED" in ascii_out

    latex_out = format_latex_table(result)
    assert r"\begin{table}" in latex_out
    assert r"\begin{tabular}" in latex_out
    assert r"THSS Compilation ($T_{\text{THSS}}$)" in latex_out
    assert r"DAG Entity Lease ($T_{\text{DAG}}$)" in latex_out
    assert r"Epistemic Commit ($T_{\text{Commit}}$)" in latex_out
    assert r"\textbf{Total Governance ($T_{\text{Gov}}$)}" in latex_out
    assert r"\textbf{Governance Overhead (\%)}" in latex_out
    assert r"\end{table}" in latex_out


def test_cli_execution(tmp_path: Path) -> None:
    """Verify CLI entrypoint flags and output artifact saving."""
    out_file = tmp_path / "microbench_report.json"
    exit_code = main(
        [
            "--iterations",
            "20",
            "--warmup",
            "5",
            "--format",
            "json",
            "--output",
            str(out_file),
            "--fail-on-sla",
        ]
    )

    assert exit_code == 0
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["iterations"] == 20
    assert data["all_targets_met"] is True
    assert "phases" in data
    assert "t_thss_ms" in data["phases"]
    assert "governance_overhead_pct" in data["phases"]
