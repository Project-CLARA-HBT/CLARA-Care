"""Tests for the GLHS exact-binding ablation (workstream C).

These tests never connect to a real database except in-memory SQLite for the
runner pipeline test; the frozen schedules/protocol artifacts are the test
inputs. The adapter imports the real production validation primitives, and the
dispatch tests monkeypatch those imported names only to verify arm selection.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import pytest
from clara_api.db.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from evaluation.glhs_binding_only_ablation import adapter
from evaluation.glhs_binding_only_ablation.analyze import (
    _mcnemar_exact_two_sided,
    analyze,
)
from evaluation.glhs_binding_only_ablation.build_schedules import (
    CONTROLS_PER_FAMILY,
    FAMILY_COUNT,
    TOTAL_SCHEDULES,
    build_schedules,
)
from evaluation.glhs_binding_only_ablation.observer import (
    ExecutionRecord,
    Observer,
    read_records,
)
from evaluation.glhs_binding_only_ablation.postgres_runner import (
    RunnerEnv,
    _run_execution,
)
from evaluation.glhs_binding_only_ablation.validate import (
    validate_arm_diff,
    validate_import_boundary,
    validate_no_production_flag,
    validate_protocol,
    validate_schedule_hash,
    validate_schedules,
)

BASE = Path(__file__).resolve().parents[3]
PACKAGE_DIR = BASE / "evaluation" / "glhs_binding_only_ablation"
SCHEDULES_PATH = PACKAGE_DIR / "schedules.json"
PROTOCOL_PATH = PACKAGE_DIR / "protocol.json"


@pytest.fixture()
def schedules_document() -> dict:
    return json.loads(SCHEDULES_PATH.read_text(encoding="utf-8"))


@pytest.fixture()
def protocol() -> dict:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def test_schedule_count_is_320(schedules_document: dict) -> None:
    schedules = schedules_document["schedules"]
    assert len(schedules) == TOTAL_SCHEDULES == 320
    adversarial = [s for s in schedules if s["kind"] == "adversarial"]
    controls = [s for s in schedules if s["kind"] == "control"]
    assert len(adversarial) == 256
    assert len(controls) == 64


def test_per_family_counts(schedules_document: dict) -> None:
    schedules = schedules_document["schedules"]
    for family_id in range(1, FAMILY_COUNT + 1):
        family = [s for s in schedules if s["family_id"] == family_id]
        assert len(family) == 40
        assert len([s for s in family if s["kind"] == "adversarial"]) == 32
        assert len([s for s in family if s["kind"] == "control"]) == CONTROLS_PER_FAMILY == 8


def test_expected_admissibility_matches_family_definition(schedules_document: dict) -> None:
    for schedule in schedules_document["schedules"]:
        if schedule["kind"] == "adversarial":
            assert schedule["expected_admissibility"] == "invalid_commit_rejected"
            assert schedule["current_coordinates_ok"] is True
            assert schedule["disclosure_delta_type"] != "none_control"
        else:
            assert schedule["expected_admissibility"] == "valid_commit"
            assert schedule["disclosure_delta_type"] == "none_control"
        assert schedule["arm"] == "BOTH"


def test_schedules_valid_and_reproducible(schedules_document: dict) -> None:
    result = validate_schedules(schedules_document)
    assert result["valid"] is True
    regenerated = build_schedules()
    assert regenerated == schedules_document["schedules"]


def test_protocol_is_frozen(protocol: dict) -> None:
    result = validate_protocol(protocol)
    assert result["valid"] is True
    assert protocol["status"] == "FROZEN"
    assert protocol["primary_analysis"]["adaptive_sample_size"] is False
    assert protocol["schedule_inventory"]["total"] == 320


def test_frozen_artifact_hashes_are_verified(protocol: dict) -> None:
    validate_schedule_hash(
        SCHEDULES_PATH.read_bytes(), protocol["schedule_inventory"]["schedules_sha256"]
    )
    broken = dict(protocol)
    broken["protocol_hash"] = "0" * 64
    with pytest.raises(ValueError, match="protocol_hash"):
        validate_protocol(broken)


def test_protocol_rejects_adaptive_sample_size() -> None:
    import copy

    protocol = copy.deepcopy(_load_protocol())
    protocol["primary_analysis"]["adaptive_sample_size"] = True
    with pytest.raises(ValueError, match="adaptive_sample_size"):
        validate_protocol(protocol)


def _load_protocol() -> dict:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def test_schedules_reject_wrong_count() -> None:
    document = {"schedules": []}
    with pytest.raises(ValueError, match="count_invalid"):
        validate_schedules(document)


def test_adapter_arms_defined() -> None:
    assert adapter.FULL_GOVERNANCE_NO_EXACT_BINDING == "FULL_GOVERNANCE_NO_EXACT_BINDING"
    assert adapter.GLHS_EXACT_BINDING == "GLHS_EXACT_BINDING"
    assert adapter.binding_check_applied(adapter.FULL_GOVERNANCE_NO_EXACT_BINDING) is False
    assert adapter.binding_check_applied(adapter.GLHS_EXACT_BINDING) is True


def test_adapter_arm_a_skips_exact_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"governance": 0, "disclosure": 0}
    db = type(
        "DB",
        (),
        {
            "execute": lambda self, statement: type(
                "Result", (), {"scalar_one_or_none": lambda self: None}
            )()
        },
    )()

    def _gov(*args, **kwargs):
        calls["governance"] += 1

    def _exact(*args, **kwargs):
        calls["disclosure"] += 1

    monkeypatch.setattr(adapter, "_validate_proposal_scope_coordinates", lambda **kwargs: None)
    monkeypatch.setattr(adapter, "_current_snapshot", lambda *args, **kwargs: object())
    monkeypatch.setattr(adapter, "validate_current_governance_coordinates", _gov)
    monkeypatch.setattr(adapter, "validate_exact_disclosure_dependency", _exact)
    adapter.validate_proposal_context(
        db,
        arm=adapter.FULL_GOVERNANCE_NO_EXACT_BINDING,
        scope=_fake_scope(),
        proposal=_fake_proposal(),
        evidence_ids=(),
        current_version=1,
        consent_version="c",
    )
    assert calls == {"governance": 1, "disclosure": 0}
    adapter.validate_proposal_context(
        db,
        arm=adapter.GLHS_EXACT_BINDING,
        scope=_fake_scope(),
        proposal=_fake_proposal(),
        evidence_ids=(),
        current_version=1,
        consent_version="c",
    )
    assert calls == {"governance": 2, "disclosure": 1}


def test_adapter_unknown_arm_rejected() -> None:
    with pytest.raises(ValueError, match="unknown_ablation_arm"):
        adapter.validate_proposal_context(
            None,
            arm="BOGUS",
            scope=None,
            proposal=None,
            evidence_ids=(),
            current_version=1,
            consent_version="c",
        )


def _fake_scope() -> object:
    return type(
        "Scope",
        (),
        {
            "profile": type("Profile", (), {"public_id": "p1", "id": 1})(),
            "purpose": "self_care",
        },
    )()


def _fake_proposal(**overrides: object) -> object:
    defaults = {
        "target_profile_public_id": "p1",
        "purpose": "self_care",
        "actor_user_id": 7,
        "actor_role": "owner",
        "task": "monitoring_repeat",
        "policy_version": "commitloop.v1",
        "consent_version": "c",
        "base_state_version": 1,
        "context_binding_mode": "snapshot_bound",
        "source_snapshot_id": "s1",
        "source_snapshot_digest": "d1",
    }
    defaults.update(overrides)
    return type("Proposal", (), defaults)()


def test_adapter_imports_real_production_primitives() -> None:
    from clara_api.glhs.gateway import (
        validate_current_governance_coordinates,
        validate_exact_disclosure_dependency,
    )

    assert (
        adapter.validate_current_governance_coordinates is validate_current_governance_coordinates
    )
    assert adapter.validate_exact_disclosure_dependency is validate_exact_disclosure_dependency
    assert not hasattr(adapter, "PRODUCTION_PRIMITIVES_AVAILABLE")


def test_adapter_refuses_production_import(tmp_path: Path) -> None:
    services_dir = tmp_path / "services"
    services_dir.mkdir()
    (services_dir / "probe.py").write_text(
        "import evaluation.glhs_binding_only_ablation.adapter\n", encoding="utf-8"
    )
    import importlib
    import sys

    sys.path.insert(0, str(tmp_path))
    module_name = "evaluation.glhs_binding_only_ablation.adapter"
    cached = sys.modules.pop(module_name, None)
    try:
        with pytest.raises(RuntimeError, match="evaluation-only"):
            importlib.import_module("services.probe")
    finally:
        if cached is not None:
            sys.modules[module_name] = cached
        sys.path.remove(str(tmp_path))


def test_no_production_flag_in_services() -> None:
    offenders = validate_no_production_flag(BASE / "services")
    assert offenders == []


def test_no_production_import_of_ablation_package() -> None:
    offenders = validate_import_boundary(BASE / "services")
    assert offenders == []


def _synthetic_records(
    schedules_document: dict, *, adversarial_arm_a_admits: bool = True
) -> list[dict]:
    records: list[dict] = []
    sequence = 0
    for schedule in schedules_document["schedules"]:
        adversarial = schedule["kind"] == "adversarial"
        for arm in (adapter.FULL_GOVERNANCE_NO_EXACT_BINDING, adapter.GLHS_EXACT_BINDING):
            sequence += 1
            admitted = (
                adversarial
                and arm == adapter.FULL_GOVERNANCE_NO_EXACT_BINDING
                and adversarial_arm_a_admits
            ) or (not adversarial)
            reason = None if admitted else "proposal_snapshot_scope_forbidden"
            governance = {
                "current_state_version": 1,
                "policy_version": "commitloop.v1",
                "consent_version": "medical_disclaimer:v1",
                "purpose": "self_care",
                "task": schedule["context"]["task"],
                "actor_role": "owner",
                "domain": schedule["context"]["domain"],
                "evidence_fingerprints": ["f1"],
            }
            records.append(
                dict(
                    asdict(
                        ExecutionRecord(
                            run_id="SYNTH",
                            schedule_id=schedule["schedule_id"],
                            arm=arm,
                            sequence=sequence,
                            admitted=admitted,
                            rejection_reason_code=reason,
                            snapshot_coordinates={
                                "disclosure_delta_type": schedule["disclosure_delta_type"]
                            },
                            governance_coordinates=governance,
                            binding_check_applied=adapter.binding_check_applied(arm),
                            expected_admissibility=schedule["expected_admissibility"],
                            txid=None,
                            backend_pid=None,
                            execution_utc=datetime.now(UTC).isoformat(),
                        )
                    )
                )
            )
    return records


def test_mcnemar_known_table() -> None:
    assert _mcnemar_exact_two_sided(0, 0) == 1.0
    assert _mcnemar_exact_two_sided(30, 0) == pytest.approx(2 * 0.5**30, rel=1e-12)
    expected = 2 * sum(math.comb(30, k) for k in range(25, 31)) * 0.5**30
    assert _mcnemar_exact_two_sided(25, 5) == pytest.approx(min(1.0, expected), rel=1e-12)


def test_analyze_pipeline_on_synthetic_data(protocol: dict, schedules_document: dict) -> None:
    records = _synthetic_records(schedules_document)
    result = analyze(schedules_document, records, protocol)
    assert result["claim_eligible"] is True
    primary = result["primary"]
    assert primary["denominator"] == 256
    assert primary["numerator_arm_a"] == 256
    assert primary["numerator_arm_b"] == 0
    assert primary["invalid_commit_acceptance_arm_a"] == 1.0
    assert primary["invalid_commit_acceptance_arm_b"] == 0.0
    assert primary["risk_difference_arm_a_minus_arm_b"] == 1.0
    assert primary["discordant_arm_a_admitted_arm_b_rejected"] == 256
    assert primary["discordant_arm_a_rejected_arm_b_admitted"] == 0
    assert primary["mcnemar_exact_two_sided_p"] == pytest.approx(2 * 0.5**256, rel=1e-12)
    for family_id in range(1, FAMILY_COUNT + 1):
        family = result["per_family"][str(family_id)]
        assert family["denominator"] == 32
        assert family["risk_difference_arm_a_minus_arm_b"] == 1.0
    assert (
        result["controls"]["acceptance"][adapter.FULL_GOVERNANCE_NO_EXACT_BINDING][
            "valid_commit_acceptance"
        ]
        == 1.0
    )
    assert (
        result["controls"]["acceptance"][adapter.GLHS_EXACT_BINDING]["valid_commit_acceptance"]
        == 1.0
    )


def test_bootstrap_is_deterministic(protocol: dict, schedules_document: dict) -> None:
    records = _synthetic_records(schedules_document)
    first = analyze(schedules_document, records, protocol)
    second = analyze(schedules_document, records, protocol)
    assert first["primary"]["ci95_paired_bootstrap"] == second["primary"]["ci95_paired_bootstrap"]


def test_arm_diff_detects_governance_drift(schedules_document: dict) -> None:
    records = _synthetic_records(schedules_document)
    assert validate_arm_diff(records)["valid"] is True
    target = next(r for r in records if r["arm"] == adapter.GLHS_EXACT_BINDING)
    target["governance_coordinates"]["consent_version"] = "different"
    assert validate_arm_diff(records)["valid"] is False


def test_observer_rejects_tampered_existing_stream(tmp_path: Path) -> None:
    path = tmp_path / "observations.jsonl"
    observer = Observer(path)
    record = ExecutionRecord(
        run_id="R",
        schedule_id="S",
        arm=adapter.GLHS_EXACT_BINDING,
        sequence=1,
        admitted=False,
        rejection_reason_code="x",
        snapshot_coordinates={},
        governance_coordinates={},
        binding_check_applied=True,
        expected_admissibility="invalid_commit_rejected",
        txid=None,
        backend_pid=None,
    )
    observer.append(record)
    path.write_text(
        path.read_text(encoding="utf-8").replace('"admitted":false', '"admitted":true'),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="hash_mismatch"):
        read_records(path)
    with pytest.raises(ValueError, match="hash_mismatch"):
        observer.append(record)


@pytest.fixture()
def memory_db() -> Session:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
        session.close()


def test_runner_pipeline_on_sqlite(schedules_document: dict, memory_db: Session) -> None:
    by_id = {s["schedule_id"]: s for s in schedules_document["schedules"]}
    adversarial = by_id["GLHS-BA-F01-A01"]
    control = by_id["GLHS-BA-F01-C01"]
    env = RunnerEnv(session_factory=lambda: memory_db)
    rec_a = _run_execution(
        env, adversarial, arm=adapter.FULL_GOVERNANCE_NO_EXACT_BINDING, run_id="T", sequence=1
    )
    rec_b = _run_execution(env, adversarial, arm=adapter.GLHS_EXACT_BINDING, run_id="T", sequence=2)
    assert rec_a.admitted is True
    assert rec_b.admitted is False
    assert rec_b.rejection_reason_code == "proposal_snapshot_scope_forbidden"
    assert rec_a.governance_coordinates == rec_b.governance_coordinates
    rec_c1 = _run_execution(
        env, control, arm=adapter.FULL_GOVERNANCE_NO_EXACT_BINDING, run_id="T", sequence=3
    )
    rec_c2 = _run_execution(env, control, arm=adapter.GLHS_EXACT_BINDING, run_id="T", sequence=4)
    assert rec_c1.admitted is True
    assert rec_c2.admitted is True


def test_runner_requires_attestation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GLHS_BINDING_ABLATION_ISOLATED_RESEARCH", raising=False)
    from evaluation.glhs_binding_only_ablation.postgres_runner import (
        _require_isolated_postgres,
    )

    with pytest.raises(RuntimeError, match="isolated_research_attestation"):
        _require_isolated_postgres("postgresql://u:p@h:5432/db")


def test_seal_hashes_match(protocol: dict, schedules_document: dict, tmp_path: Path) -> None:
    from evaluation.glhs_binding_only_ablation.seal import seal, sha256_file

    records = _synthetic_records(schedules_document)
    for record in records:
        record["run_id"] = "R1"
    analysis = analyze(schedules_document, records, protocol)
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    raw_dir = results_dir / "raw"
    raw_dir.mkdir()
    raw_path = raw_dir / "executions_R1.jsonl"
    observer = Observer(raw_path)
    for record in records:
        observer.append(ExecutionRecord(**record))
    assert len(read_records(raw_path)) == 640
    analysis_path = results_dir / "analysis.json"
    analysis_path.write_text(json.dumps(analysis), encoding="utf-8")
    manifest_path = results_dir / "manifest_R1.json"
    manifest_path.write_text(
        json.dumps(
            {"backend": "sqlite_smoke", "executed_executions": 640, "expected_executions": 640}
        ),
        encoding="utf-8",
    )
    sealed = seal(
        protocol_path=PROTOCOL_PATH,
        schedules_path=SCHEDULES_PATH,
        adapter_path=PACKAGE_DIR / "adapter.py",
        runner_path=PACKAGE_DIR / "postgres_runner.py",
        observer_path=PACKAGE_DIR / "observer.py",
        analyze_path=PACKAGE_DIR / "analyze.py",
        validate_path=PACKAGE_DIR / "validate.py",
        raw_paths=[raw_path],
        analysis_path=analysis_path,
        out_dir=tmp_path / "seal",
        run_id="R1",
        freeze_id=protocol["freeze_id"],
        results_dir=results_dir,
    )
    assert sealed["freeze_id"] == protocol["freeze_id"]
    assert sealed["backend"] == "sqlite_smoke"
    artifact_manifest = json.loads((tmp_path / "seal" / "artifact-sha256.json").read_text())
    assert artifact_manifest[str(SCHEDULES_PATH)] == sha256_file(SCHEDULES_PATH)
    assert sealed["protocol_sha256"] == sha256_file(PROTOCOL_PATH)
