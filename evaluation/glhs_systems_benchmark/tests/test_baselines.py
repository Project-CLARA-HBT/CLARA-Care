"""Unit and behavioral tests for all 6 transactional concurrency baselines."""

from __future__ import annotations

from evaluation.glhs_systems_benchmark.baselines import (
    AbortCategory,
    FHIRBundleAdapterEngine,
    GLHSSS2PLEngine,
    PostgresSSIEngine,
    Standard2PLEngine,
    StandardOCCEngine,
    TxnStatus,
    ZanzibarModelEngine,
)
from evaluation.glhs_systems_benchmark.workload_generator import (
    generate_clean_update,
    generate_disjoint_partition,
    generate_severe_ddi,
    generate_toctou_revocation,
)


def test_glhs_ss2pl_clean_update() -> None:
    engine = GLHSSS2PLEngine()
    engine.setup()
    tx = generate_clean_update("tx_glhs_01", patient_idx=1, seed=42)
    res = engine.execute_transaction(tx)

    assert res.status == TxnStatus.VALID_COMMIT
    assert res.merkle_root is not None
    assert len(engine.simulated.ledger_events) == 1


def test_glhs_ss2pl_blocks_toctou_revocation() -> None:
    engine = GLHSSS2PLEngine()
    engine.setup()
    tx = generate_toctou_revocation("tx_glhs_toctou", patient_idx=1, seed=42)
    res = engine.execute_transaction(tx)

    assert res.status == TxnStatus.SAFE_ABORT
    assert res.abort_category == AbortCategory.GOVERNANCE_REVOCATION
    assert "Consent epoch revoked" in str(res.violation_reason)


def test_glhs_ss2pl_blocks_severe_ddi() -> None:
    engine = GLHSSS2PLEngine()
    engine.setup()
    tx = generate_severe_ddi("tx_glhs_ddi", patient_idx=1, seed=42)
    res = engine.execute_transaction(tx)

    assert res.status == TxnStatus.SAFE_ABORT
    assert res.abort_category == AbortCategory.CLINICAL_DDI_SAFETY
    assert "clinical safety barrier" in str(res.violation_reason).lower()


def test_glhs_ss2pl_disjoint_partitions_no_false_stale() -> None:
    engine = GLHSSS2PLEngine()
    engine.setup()
    for i in range(10):
        tx = generate_disjoint_partition(f"tx_glhs_disjoint_{i}", partition_idx=i, seed=42 + i)
        res = engine.execute_transaction(tx)
        assert res.status == TxnStatus.VALID_COMMIT
        assert res.abort_category != AbortCategory.FALSE_STALE


def test_postgres_ssi_semantics() -> None:
    engine = PostgresSSIEngine()
    engine.setup()

    # Clean update
    tx_clean = generate_clean_update("tx_ssi_clean", patient_idx=1, seed=42)
    res_clean = engine.execute_transaction(tx_clean)
    assert res_clean.status == TxnStatus.VALID_COMMIT

    # TOCTOU drift is caught by normalized consent freshness check
    tx_toctou = generate_toctou_revocation("tx_ssi_toctou", patient_idx=1, seed=42)
    res_toctou = engine.execute_transaction(tx_toctou)
    assert res_toctou.status == TxnStatus.SAFE_ABORT
    assert res_toctou.abort_category == AbortCategory.GOVERNANCE_REVOCATION

    # Severe DDI is caught by normalized clinical safety check
    tx_ddi = generate_severe_ddi("tx_ssi_ddi", patient_idx=1, seed=42)
    res_ddi = engine.execute_transaction(tx_ddi)
    assert res_ddi.status == TxnStatus.SAFE_ABORT
    assert res_ddi.abort_category == AbortCategory.CLINICAL_DDI_SAFETY


def test_standard_2pl_semantics() -> None:
    engine = Standard2PLEngine()
    engine.setup()

    tx_clean = generate_clean_update("tx_2pl_clean", patient_idx=1, seed=42)
    res_clean = engine.execute_transaction(tx_clean)
    assert res_clean.status == TxnStatus.VALID_COMMIT

    tx_toctou = generate_toctou_revocation("tx_2pl_toctou", patient_idx=1, seed=42)
    res_toctou = engine.execute_transaction(tx_toctou)
    assert res_toctou.status == TxnStatus.SAFE_ABORT
    assert res_toctou.abort_category == AbortCategory.GOVERNANCE_REVOCATION


def test_standard_occ_semantics() -> None:
    engine = StandardOCCEngine(max_retries=2)
    engine.setup()

    tx_clean = generate_clean_update("tx_occ_clean", patient_idx=1, seed=42)
    res_clean = engine.execute_transaction(tx_clean)
    assert res_clean.status == TxnStatus.VALID_COMMIT

    tx_toctou = generate_toctou_revocation("tx_occ_toctou", patient_idx=1, seed=42)
    res_toctou = engine.execute_transaction(tx_toctou)
    assert res_toctou.status == TxnStatus.SAFE_ABORT
    assert res_toctou.abort_category == AbortCategory.GOVERNANCE_REVOCATION


def test_fhir_bundle_adapter_semantics() -> None:
    engine = FHIRBundleAdapterEngine()
    engine.setup()

    tx_clean = generate_clean_update("tx_fhir_clean", patient_idx=1, seed=42)
    res_clean = engine.execute_transaction(tx_clean)
    assert res_clean.status == TxnStatus.VALID_COMMIT

    tx_toctou = generate_toctou_revocation("tx_fhir_toctou", patient_idx=1, seed=42)
    res_toctou = engine.execute_transaction(tx_toctou)
    assert res_toctou.status == TxnStatus.SAFE_ABORT
    assert res_toctou.abort_category == AbortCategory.GOVERNANCE_REVOCATION


def test_zanzibar_model_semantics() -> None:
    engine = ZanzibarModelEngine()
    engine.setup()

    tx_clean = generate_clean_update("tx_zan_clean", patient_idx=1, seed=42)
    res_clean = engine.execute_transaction(tx_clean)
    assert res_clean.status == TxnStatus.VALID_COMMIT

    tx_toctou = generate_toctou_revocation("tx_zan_toctou", patient_idx=1, seed=42)
    res_toctou = engine.execute_transaction(tx_toctou)
    assert res_toctou.status == TxnStatus.SAFE_ABORT
    assert res_toctou.abort_category == AbortCategory.GOVERNANCE_REVOCATION
