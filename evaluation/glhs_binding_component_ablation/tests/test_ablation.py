"""Comprehensive test suite for GLHS Phase 1 (E01) 2^3 Factorial Component Ablation."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from clara_api.db.base import Base
from clara_api.glhs.canonical_json import fast_canonical_digest
from clara_api.glhs.domain import GlhsInvariantError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from evaluation.glhs_binding_component_ablation import (
    adapter,
    binding_mask,
    observer,
)
from evaluation.glhs_binding_component_ablation.adapter import (
    binding_check_applied,
    validate_proposal_context,
)
from evaluation.glhs_binding_component_ablation.analyze import (
    _fit_factorial_logistic_regression,
    _mcnemar_exact_two_sided,
    _wilson_score_ci,
    analyze,
)
from evaluation.glhs_binding_component_ablation.binding_mask import (
    ALL_ARMS,
    ARMS,
    B000,
    B001,
    B010,
    B011,
    B100,
    B101,
    B110,
    B111,
    BindingMask,
    get_binding_mask,
)
from evaluation.glhs_binding_component_ablation.build_schedules import (
    FAMILY_IDS,
    SCHEDULES_PER_FAMILY,
    TOTAL_SCHEDULES,
    build_schedules,
)
from evaluation.glhs_binding_component_ablation.observer import (
    ExecutionRecord,
    Observer,
    read_records,
)
from evaluation.glhs_binding_component_ablation.postgres_runner import (
    _run_execution,
    run_ablation,
)
from evaluation.glhs_binding_component_ablation.seal import seal
from evaluation.glhs_binding_component_ablation.validate import (
    validate_execution_against_expected,
    validate_import_boundary,
    validate_no_production_flag,
    validate_protocol,
    validate_schedule_hash,
    validate_schedules,
)

BASE_DIR = Path(__file__).resolve().parents[3]
PACKAGE_DIR = BASE_DIR / "evaluation" / "glhs_binding_component_ablation"
SCHEDULES_PATH = PACKAGE_DIR / "schedules.json"
PROTOCOL_PATH = PACKAGE_DIR / "protocol.json"


@pytest.fixture()
def schedules_document() -> dict[str, Any]:
    return json.loads(SCHEDULES_PATH.read_text(encoding="utf-8"))


@pytest.fixture()
def protocol() -> dict[str, Any]:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


@pytest.fixture()
def sqlite_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def test_factorial_arms_structure() -> None:
    assert len(ALL_ARMS) == 8
    expected_vectors = {
        B000: (0, 0, 0),
        B100: (1, 0, 0),
        B010: (0, 1, 0),
        B001: (0, 0, 1),
        B110: (1, 1, 0),
        B101: (1, 0, 1),
        B011: (0, 1, 1),
        B111: (1, 1, 1),
    }
    for arm_name, vec in expected_vectors.items():
        mask = get_binding_mask(arm_name)
        assert mask.vector == vec
        assert mask.as_code() == arm_name
        assert mask.as_tuple() == (bool(vec[0]), bool(vec[1]), bool(vec[2]))

    with pytest.raises(ValueError, match="unknown_ablation_arm"):
        get_binding_mask("B999")


def test_schedule_inventory_invariants(schedules_document: dict[str, Any]) -> None:
    result = validate_schedules(schedules_document)
    assert result["valid"] is True
    assert result["total_schedules"] == TOTAL_SCHEDULES == 352
    schedules = schedules_document["schedules"]

    adversarial = [s for s in schedules if s["kind"] == "adversarial"]
    controls = [s for s in schedules if s["kind"] == "control"]
    assert len(adversarial) == 256
    assert len(controls) == 96

    for fam_name, expected_count in SCHEDULES_PER_FAMILY.items():
        fam_scheds = [s for s in schedules if s["family_name"] == fam_name]
        assert len(fam_scheds) == expected_count


def test_build_schedules_deterministic(schedules_document: dict[str, Any]) -> None:
    rebuilt = build_schedules()
    assert len(rebuilt) == TOTAL_SCHEDULES == 352
    assert rebuilt == schedules_document["schedules"]


def test_protocol_freeze_and_hash_verification(protocol: dict[str, Any]) -> None:
    val_result = validate_protocol(protocol)
    assert val_result["valid"] is True
    assert protocol["status"] == "FROZEN"
    assert protocol["primary_analysis"]["adaptive_sample_size"] is False
    validate_schedule_hash(
        SCHEDULES_PATH.read_bytes(),
        protocol["schedule_inventory"]["schedules_sha256"],
    )


def test_no_production_flags_and_clean_boundary() -> None:
    services_path = BASE_DIR / "services"
    flag_result = validate_no_production_flag(services_path)
    assert flag_result["clean"] is True

    import_result = validate_import_boundary(services_path)
    assert import_result["clean"] is True


def test_observer_chain_tamper_evident(tmp_path: Path) -> None:
    stream_path = tmp_path / "raw" / "test_exec.jsonl"
    obs = Observer(stream_path)

    rec1 = ExecutionRecord(
        run_id="TEST-RUN-1",
        schedule_id="SCHED-001",
        arm="B000",
        sequence=1,
        admitted=True,
        rejection_reason_code=None,
        snapshot_coordinates={"snap": "s1"},
        governance_coordinates={"gov": "g1"},
        binding_check_applied=False,
        expected_admissibility="valid_commit",
    )
    obs.append(rec1)

    rec2 = ExecutionRecord(
        run_id="TEST-RUN-1",
        schedule_id="SCHED-002",
        arm="B111",
        sequence=2,
        admitted=False,
        rejection_reason_code="proposal_snapshot_id_mismatch",
        snapshot_coordinates={"snap": "s2"},
        governance_coordinates={"gov": "g2"},
        binding_check_applied=True,
        expected_admissibility="invalid_commit_rejected",
    )
    obs.append(rec2)

    records = read_records(stream_path)
    assert len(records) == 2
    assert records[0]["hash"] == records[1]["prev_hash"]

    # Tamper with file
    lines = stream_path.read_text(encoding="utf-8").splitlines()
    tampered_record = json.loads(lines[0])
    tampered_record["admitted"] = False
    lines[0] = json.dumps(tampered_record)
    stream_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="observer_hash_mismatch|observer_chain_broken"):
        read_records(stream_path)


def test_mcnemar_and_wilson_statistics() -> None:
    # Equal discordance -> p = 1.0
    assert _mcnemar_exact_two_sided(0, 0) == 1.0
    assert _mcnemar_exact_two_sided(5, 5) == 1.0
    # Extreme discordance -> p < 0.001
    p_extreme = _mcnemar_exact_two_sided(32, 0)
    assert p_extreme < 1e-6

    # Wilson score interval bounds
    low, high = _wilson_score_ci(96, 96)
    assert low > 0.95
    assert high == 1.0

    low0, high0 = _wilson_score_ci(0, 32)
    assert low0 == 0.0
    assert high0 < 0.15


def test_factorial_logistic_regression_fit() -> None:
    records = []
    adv_ids = {"ADV-1", "ADV-2"}
    for arm in ALL_ARMS:
        mask = get_binding_mask(arm)
        # B000 admits all, B111 rejects all
        records.append({
            "schedule_id": "ADV-1",
            "arm": arm,
            "admitted": not mask.snapshot_identity,
        })
        records.append({
            "schedule_id": "ADV-2",
            "arm": arm,
            "admitted": not mask.snapshot_digest,
        })

    fit_result = _fit_factorial_logistic_regression(records, adv_ids)
    assert fit_result["fitted"] is True
    assert "c_id" in fit_result["coefficients"]
    assert "c_digest" in fit_result["coefficients"]
    assert "c_evidence" in fit_result["coefficients"]


def test_functional_sqlite_execution_per_family(sqlite_engine) -> None:
    """Run single schedules representing each family on SQLite engine across all 8 arms."""
    schedules_doc = json.loads(SCHEDULES_PATH.read_text(encoding="utf-8"))
    schedules = schedules_doc["schedules"]

    # Pick one representative schedule per family
    reps: list[dict[str, Any]] = []
    seen_fams: set[str] = set()
    for s in schedules:
        fam = s["family_name"]
        if fam not in seen_fams:
            reps.append(s)
            seen_fams.add(fam)

    assert len(reps) == 9

    records: list[dict[str, Any]] = []
    seq = 0
    run_id = f"TEST-SQLITE-{uuid4().hex[:6]}"

    for sched in reps:
        fam = sched["family_name"]
        for arm in ALL_ARMS:
            seq += 1
            mask = get_binding_mask(arm)
            with Session(sqlite_engine) as db:
                rec = _run_execution(
                    db,
                    schedule=sched,
                    arm=arm,
                    run_id=run_id,
                    sequence=seq,
                )
                rec_dict = asdict(rec)
                records.append(rec_dict)

                # Assert expected decision vector
                if fam == "CLEAN":
                    assert rec.admitted is True, f"Clean schedule {sched['schedule_id']} rejected on {arm}"
                elif fam == "ID-SUB":
                    if mask.snapshot_identity:
                        assert rec.admitted is False
                    else:
                        assert rec.admitted is True
                elif fam == "DIGEST-MUT":
                    if mask.snapshot_digest:
                        assert rec.admitted is False
                    else:
                        assert rec.admitted is True
                elif fam in {"EVIDENCE-OUTSIDE", "MIN-SET-SWAP"}:
                    if mask.evidence_membership:
                        assert rec.admitted is False
                    else:
                        assert rec.admitted is True
                elif fam == "EXPIRY-CONTROL":
                    assert rec.admitted is False, f"Expired schedule admitted on {arm}"

    # Verify execution audit passes
    audit_result = validate_execution_against_expected(records, reps)
    assert audit_result["valid"] is True


def test_seal_verification(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    seal_dir = tmp_path / "seal"
    raw_dir = results_dir / "raw"
    raw_dir.mkdir(parents=True)

    run_id = "SEAL-TEST-001"
    raw_file = raw_dir / f"executions_{run_id}.jsonl"
    obs = Observer(raw_file)
    obs.append(
        ExecutionRecord(
            run_id=run_id,
            schedule_id="S1",
            arm="B111",
            sequence=1,
            admitted=True,
            rejection_reason_code=None,
            snapshot_coordinates={},
            governance_coordinates={},
            binding_check_applied=True,
            expected_admissibility="valid_commit",
        )
    )

    manifest_file = results_dir / f"manifest_{run_id}.json"
    manifest_file.write_text(
        json.dumps({"run_id": run_id, "backend": "sqlite_smoke"}),
        encoding="utf-8",
    )

    analysis_file = results_dir / "analysis.json"
    analysis_file.write_text(json.dumps({"status": "ok"}), encoding="utf-8")

    seal_doc = seal(
        protocol_path=PROTOCOL_PATH,
        schedules_path=SCHEDULES_PATH,
        adapter_path=PACKAGE_DIR / "adapter.py",
        binding_mask_path=PACKAGE_DIR / "binding_mask.py",
        runner_path=PACKAGE_DIR / "postgres_runner.py",
        observer_path=PACKAGE_DIR / "observer.py",
        analyze_path=PACKAGE_DIR / "analyze.py",
        validate_path=PACKAGE_DIR / "validate.py",
        raw_paths=[raw_file],
        analysis_path=analysis_file,
        out_dir=seal_dir,
        run_id=run_id,
        freeze_id="TEST-FREEZE",
        results_dir=results_dir,
    )

    assert (seal_dir / "artifact-sha256.json").exists()
    assert (seal_dir / "seal.json").exists()
    assert seal_doc["total_executions_sealed"] == 1
    assert seal_doc["backend"] == "sqlite_smoke"
