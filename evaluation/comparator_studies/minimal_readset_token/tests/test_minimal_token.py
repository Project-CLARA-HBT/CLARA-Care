"""Comprehensive test suite for E02 Minimal Alternative Binding Baseline.

Verifies:
1. Token generation, canonical serialization, schema compliance, roundtrip deserialization
2. HMAC signing, verification, and tamper detection
3. Validator evaluation across all invariant dimensions and error codes
4. Postgres/SQLite adapter execution and database state consistency
5. Full 352-schedule suite execution across GLHS B111, MIN_READSET_TOKEN, HMAC_READSET_TOKEN, and B000
6. Decision concordance (100% agreement between GLHS B111 and minimal read-set tokens)
7. Error rates (0% FAR and 0% FRR on minimal tokens; high FAR on B000)
8. Metadata byte size reduction of minimal tokens vs GLHS B111
9. Comparative metrics analysis and reporting
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from clara_api.db.base import Base
from clara_api.glhs.domain import GlhsInvariantError
from sqlalchemy import create_engine

from evaluation.comparator_studies.minimal_readset_token import (
    E02_ARMS,
    HMAC_TOKEN_SCHEMA,
    MIN_TOKEN_SCHEMA,
    HmacReadsetToken,
    MinReadsetToken,
    MinReadsetTokenPostgresAdapter,
    StateDependency,
    analyze_minimal_token_results,
    compute_evidence_commitment,
    generate_hmac_readset_token,
    generate_markdown_report,
    generate_min_readset_token,
    run_minimal_token_experiment,
    validate_readset_token,
)


@pytest.fixture
def sample_token_kwargs() -> dict[str, Any]:
    return {
        "profile_id": "1",
        "actor_id": "7",
        "actor_role": "owner",
        "purpose": "self_care",
        "task": "monitoring_repeat",
        "snapshot_id": "SNAP-ORIG-001",
        "snapshot_digest": "a" * 64,
        "disclosed_evidence_ids": ("EVD-001", "EVD-002"),
        "state_dependencies": (StateDependency(key="observations:bp", observed_version=1),),
        "policy_version": "commitloop.v1",
        "consent_version": "medical_disclaimer:v1",
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }


@pytest.fixture
def in_memory_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


class TestTokenStructureAndSerialization:
    def test_generate_min_readset_token(self, sample_token_kwargs):
        tok = generate_min_readset_token(**sample_token_kwargs)
        assert tok.schema == MIN_TOKEN_SCHEMA
        assert tok.profile_id == "1"
        assert tok.actor_id == "7"
        assert tok.actor_role == "owner"
        assert tok.purpose == "self_care"
        assert tok.task == "monitoring_repeat"
        assert tok.snapshot_id == "SNAP-ORIG-001"
        assert len(tok.evidence_commitment) == 64
        assert len(tok.state_dependencies) == 1
        assert tok.state_dependencies[0].key == "observations:bp"
        assert tok.state_dependencies[0].observed_version == 1

    def test_canonical_serialization_roundtrip(self, sample_token_kwargs):
        tok = generate_min_readset_token(**sample_token_kwargs)
        c_bytes = tok.to_canonical_bytes()
        assert isinstance(c_bytes, bytes)
        assert len(c_bytes) > 0

        c_json = tok.to_canonical_json()
        assert isinstance(c_json, str)

        deserialized = MinReadsetToken.from_json(c_json)
        assert deserialized.profile_id == tok.profile_id
        assert deserialized.snapshot_id == tok.snapshot_id
        assert deserialized.evidence_commitment == tok.evidence_commitment
        assert deserialized.state_dependencies == tok.state_dependencies
        assert deserialized.expires_at == tok.expires_at

    def test_deterministic_evidence_commitment(self):
        ev1 = ["EVD-002", "EVD-001", "EVD-003"]
        ev2 = ["EVD-003", "EVD-001", "EVD-002"]
        comm1 = compute_evidence_commitment(ev1)
        comm2 = compute_evidence_commitment(ev2)
        assert comm1 == comm2
        assert len(comm1) == 64

    def test_schema_json_file_validity(self):
        schema_path = Path(__file__).parent.parent / "schema.json"
        assert schema_path.exists()
        schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
        assert schema_data["title"] == "MinimalReadsetToken"
        assert "properties" in schema_data
        assert "evidence_commitment" in schema_data["properties"]


class TestHmacReadsetToken:
    def test_hmac_token_signing_and_verification(self, sample_token_kwargs):
        key = b"super-secret-key-for-e02-testing"
        hmac_tok = generate_hmac_readset_token(**sample_token_kwargs, hmac_key=key)

        assert hmac_tok.schema == HMAC_TOKEN_SCHEMA
        assert hmac_tok.signature
        assert len(hmac_tok.signature) == 64
        assert hmac_tok.verify_hmac(key) is True
        assert hmac_tok.verify_hmac(b"wrong-key") is False

    def test_hmac_tamper_detection(self, sample_token_kwargs):
        key = b"super-secret-key-for-e02-testing"
        hmac_tok = generate_hmac_readset_token(**sample_token_kwargs, hmac_key=key)

        # 1. Tamper with actor_role
        tampered_dict = hmac_tok.to_dict()
        tampered_dict["actor_role"] = "clinician"
        tampered_tok = HmacReadsetToken.from_dict(tampered_dict)
        assert tampered_tok.verify_hmac(key) is False

        # 2. Tamper with snapshot_id
        tampered_dict2 = hmac_tok.to_dict()
        tampered_dict2["snapshot_id"] = "SNAP-FORGED-999"
        tampered_tok2 = HmacReadsetToken.from_dict(tampered_dict2)
        assert tampered_tok2.verify_hmac(key) is False

        # 3. Tamper with signature
        tampered_dict3 = hmac_tok.to_dict()
        tampered_dict3["signature"] = "0" * 64
        tampered_tok3 = HmacReadsetToken.from_dict(tampered_dict3)
        assert tampered_tok3.verify_hmac(key) is False


class TestValidatorEngine:
    def test_valid_token_passes(self, sample_token_kwargs):
        tok = generate_min_readset_token(**sample_token_kwargs)
        res = validate_readset_token(
            tok,
            current_profile_id=1,
            current_actor_id=7,
            current_actor_role="owner",
            current_purpose="self_care",
            current_task="monitoring_repeat",
            current_state_version=1,
            current_policy_version="commitloop.v1",
            current_consent_version="medical_disclaimer:v1",
            observed_evidence_ids=["EVD-001"],
            expected_snapshot_id="SNAP-ORIG-001",
            expected_snapshot_digest="a" * 64,
        )
        assert res.valid is True
        assert res.reason_code == "accepted"

    def test_expired_token_fails(self, sample_token_kwargs):
        kwargs = dict(sample_token_kwargs)
        kwargs["expires_at"] = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
        tok = generate_min_readset_token(**kwargs)
        res = validate_readset_token(
            tok,
            current_profile_id=1,
            current_actor_id=7,
            current_actor_role="owner",
            current_purpose="self_care",
            current_task="monitoring_repeat",
            current_state_version=1,
        )
        assert res.valid is False
        assert res.reason_code == "proposal_snapshot_expired"

    def test_coordinate_mismatches_fail(self, sample_token_kwargs):
        tok = generate_min_readset_token(**sample_token_kwargs)

        # Profile mismatch
        res1 = validate_readset_token(
            tok,
            current_profile_id=99,
            current_actor_id=7,
            current_actor_role="owner",
            current_purpose="self_care",
            current_task="monitoring_repeat",
            current_state_version=1,
        )
        assert res1.valid is False
        assert res1.reason_code == "proposal_snapshot_scope_forbidden"

        # Actor mismatch
        res2 = validate_readset_token(
            tok,
            current_profile_id=1,
            current_actor_id=99,
            current_actor_role="owner",
            current_purpose="self_care",
            current_task="monitoring_repeat",
            current_state_version=1,
        )
        assert res2.valid is False
        assert res2.reason_code == "proposal_snapshot_actor_mismatch"

        # Role mismatch
        res3 = validate_readset_token(
            tok,
            current_profile_id=1,
            current_actor_id=7,
            current_actor_role="clinician",
            current_purpose="self_care",
            current_task="monitoring_repeat",
            current_state_version=1,
        )
        assert res3.valid is False
        assert res3.reason_code == "proposal_snapshot_role_mismatch"

        # Purpose mismatch
        res4 = validate_readset_token(
            tok,
            current_profile_id=1,
            current_actor_id=7,
            current_actor_role="owner",
            current_purpose="research",
            current_task="monitoring_repeat",
            current_state_version=1,
        )
        assert res4.valid is False
        assert res4.reason_code == "proposal_snapshot_purpose_mismatch"

        # Task mismatch
        res5 = validate_readset_token(
            tok,
            current_profile_id=1,
            current_actor_id=7,
            current_actor_role="owner",
            current_purpose="self_care",
            current_task="other_task",
            current_state_version=1,
        )
        assert res5.valid is False
        assert res5.reason_code == "proposal_snapshot_task_mismatch"

    def test_stale_state_version_fails(self, sample_token_kwargs):
        tok = generate_min_readset_token(**sample_token_kwargs)
        res = validate_readset_token(
            tok,
            current_profile_id=1,
            current_actor_id=7,
            current_actor_role="owner",
            current_purpose="self_care",
            current_task="monitoring_repeat",
            current_state_version=2,  # Stale: token observed version 1
        )
        assert res.valid is False
        assert res.reason_code == "proposal_base_state_version_mismatch"

    def test_undisclosed_evidence_fails(self, sample_token_kwargs):
        tok = generate_min_readset_token(**sample_token_kwargs)
        res = validate_readset_token(
            tok,
            current_profile_id=1,
            current_actor_id=7,
            current_actor_role="owner",
            current_purpose="self_care",
            current_task="monitoring_repeat",
            current_state_version=1,
            observed_evidence_ids=["EVD-001", "EVD-OUTSIDE-999"],
        )
        assert res.valid is False
        assert res.reason_code == "proposal_evidence_not_disclosed"

    def test_snapshot_id_and_digest_mismatches_fail(self, sample_token_kwargs):
        tok = generate_min_readset_token(**sample_token_kwargs)

        # Snapshot ID mismatch
        res_id = validate_readset_token(
            tok,
            current_profile_id=1,
            current_actor_id=7,
            current_actor_role="owner",
            current_purpose="self_care",
            current_task="monitoring_repeat",
            current_state_version=1,
            expected_snapshot_id="SNAP-DIFFERENT-002",
            expected_snapshot_digest="a" * 64,
        )
        assert res_id.valid is False
        assert res_id.reason_code == "proposal_snapshot_id_mismatch"

        # Snapshot digest mismatch
        res_dig = validate_readset_token(
            tok,
            current_profile_id=1,
            current_actor_id=7,
            current_actor_role="owner",
            current_purpose="self_care",
            current_task="monitoring_repeat",
            current_state_version=1,
            expected_snapshot_id="SNAP-ORIG-001",
            expected_snapshot_digest="b" * 64,
        )
        assert res_dig.valid is False
        assert res_dig.reason_code == "proposal_snapshot_digest_mismatch"

    def test_hmac_token_validation_with_key(self, sample_token_kwargs):
        key = b"valid-key-123"
        hmac_tok = generate_hmac_readset_token(**sample_token_kwargs, hmac_key=key)

        # Valid key
        res_ok = validate_readset_token(
            hmac_tok,
            current_profile_id=1,
            current_actor_id=7,
            current_actor_role="owner",
            current_purpose="self_care",
            current_task="monitoring_repeat",
            current_state_version=1,
            hmac_key=key,
        )
        assert res_ok.valid is True

        # Invalid key
        res_bad = validate_readset_token(
            hmac_tok,
            current_profile_id=1,
            current_actor_id=7,
            current_actor_role="owner",
            current_purpose="self_care",
            current_task="monitoring_repeat",
            current_state_version=1,
            hmac_key=b"invalid-key-456",
        )
        assert res_bad.valid is False
        assert res_bad.reason_code == "proposal_hmac_signature_invalid"

        # Missing key
        res_nokey = validate_readset_token(
            hmac_tok,
            current_profile_id=1,
            current_actor_id=7,
            current_actor_role="owner",
            current_purpose="self_care",
            current_task="monitoring_repeat",
            current_state_version=1,
            hmac_key=None,
        )
        assert res_nokey.valid is False
        assert res_nokey.reason_code == "proposal_hmac_key_required"

    def test_raise_on_error_mode(self, sample_token_kwargs):
        tok = generate_min_readset_token(**sample_token_kwargs)
        with pytest.raises(GlhsInvariantError, match="proposal_snapshot_actor_mismatch"):
            validate_readset_token(
                tok,
                current_profile_id=1,
                current_actor_id=999,
                current_actor_role="owner",
                current_purpose="self_care",
                current_task="monitoring_repeat",
                current_state_version=1,
                raise_on_error=True,
            )


class TestPostgresAdapterAndArmExecution:
    def test_adapter_executes_clean_schedule(self, in_memory_engine):
        adapter = MinReadsetTokenPostgresAdapter(in_memory_engine)
        adapter.setup_schema()

        sched = {
            "schedule_id": "TEST-CLEAN-001",
            "family_name": "CLEAN",
            "context": {
                "action": "repeat_measurement",
                "actor_role": "owner",
                "domain": "observations",
                "evidence_count": 1,
                "purpose": "self_care",
                "task": "monitoring_repeat",
            },
            "evidence_set": {
                "disclosed_provenance_ids": ["EVD-001"],
                "observed_evidence_ids": ["EVD-001"],
            },
            "snapshot_fields": {
                "source_snapshot_id": "SNAP-ORIG-001",
                "expires_in_seconds": 3600,
            },
            "expected_admissibility": "valid_commit_accepted",
        }

        # All 4 arms should admit clean schedule
        for arm in E02_ARMS:
            outcome = adapter.execute_schedule(sched, arm=arm)
            assert outcome.admitted is True, f"{arm} should admit clean schedule"
            assert outcome.reason_code == "accepted"
            assert outcome.db_reads > 0
            assert outcome.db_writes > 0

    def test_adapter_rejects_adversarial_schedule(self, in_memory_engine):
        adapter = MinReadsetTokenPostgresAdapter(in_memory_engine)
        adapter.setup_schema()

        # ID-SUB schedule
        sched_id_sub = {
            "schedule_id": "TEST-ID-SUB-001",
            "family_name": "ID-SUB",
            "context": {
                "action": "repeat_measurement",
                "actor_role": "owner",
                "domain": "observations",
                "evidence_count": 1,
                "purpose": "self_care",
                "task": "monitoring_repeat",
            },
            "evidence_set": {
                "disclosed_provenance_ids": ["EVD-001"],
                "observed_evidence_ids": ["EVD-001"],
            },
            "snapshot_fields": {
                "source_snapshot_id": "SNAP-SUB-001",
                "expires_in_seconds": 3600,
            },
            "expected_admissibility": "invalid_commit_rejected",
        }

        outcome_b111 = adapter.execute_schedule(sched_id_sub, arm="GLHS_B111")
        outcome_min = adapter.execute_schedule(sched_id_sub, arm="MIN_READSET_TOKEN")
        outcome_hmac = adapter.execute_schedule(sched_id_sub, arm="HMAC_READSET_TOKEN")
        outcome_b000 = adapter.execute_schedule(sched_id_sub, arm="B000")

        assert outcome_b111.admitted is False
        assert outcome_min.admitted is False
        assert outcome_hmac.admitted is False
        # B000 does not check snapshot ID, so it false-accepts
        assert outcome_b000.admitted is True


class TestFullCorpusReplayAndConcordance:
    @pytest.fixture(scope="class")
    @classmethod
    def full_experiment_summary(cls, tmp_path_factory):
        tmp_dir = tmp_path_factory.mktemp("e02_full_run")
        protocol_path = Path("protocols/E01_binding_components/protocol.json")
        schedules_path = Path("protocols/E01_binding_components/schedules.json")

        summary = run_minimal_token_experiment(
            protocol_path=protocol_path,
            schedules_path=schedules_path,
            output_dir=tmp_dir,
            backend="sqlite",
        )
        return summary, tmp_dir

    def test_total_executions_count(self, full_experiment_summary):
        summary, tmp_dir = full_experiment_summary
        assert summary["total_schedules"] == 352
        assert summary["total_executions"] == 352 * 4  # 1,408 executions
        assert set(summary["evaluated_arms"]) == set(E02_ARMS)

    def test_100_percent_clean_control_admission(self, full_experiment_summary):
        summary, _ = full_experiment_summary
        for arm in ("GLHS_B111", "MIN_READSET_TOKEN", "HMAC_READSET_TOKEN", "B000"):
            arm_stat = summary["arm_summaries"][arm]
            assert arm_stat["clean_controls_total"] == 96
            assert arm_stat["clean_controls_admitted"] == 96
            assert arm_stat["false_negative_count"] == 0
            assert arm_stat["false_rejection_rate"] == 0.0

    def test_0_percent_adversarial_false_acceptance_on_bound_arms(self, full_experiment_summary):
        summary, _ = full_experiment_summary
        for arm in ("GLHS_B111", "MIN_READSET_TOKEN", "HMAC_READSET_TOKEN"):
            arm_stat = summary["arm_summaries"][arm]
            assert arm_stat["adversarial_total"] == 256
            assert arm_stat["adversarial_admitted"] == 0
            assert arm_stat["false_positive_count"] == 0
            assert arm_stat["false_acceptance_rate"] == 0.0

    def test_b000_unbound_control_fails_safety(self, full_experiment_summary):
        summary, _ = full_experiment_summary
        b000_stat = summary["arm_summaries"]["B000"]
        # B000 should false-accept snapshot-dependent adversarial schedules
        assert b000_stat["false_positive_count"] > 0
        assert b000_stat["false_acceptance_rate"] > 0.5

    def test_concordance_analysis_and_byte_reduction(self, full_experiment_summary):
        summary, tmp_dir = full_experiment_summary
        runs_file = tmp_dir / "raw" / "runs.jsonl"
        assert runs_file.exists()

        records = [json.loads(line) for line in runs_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(records) == 1408

        analysis = analyze_minimal_token_results(records)
        assert analysis["total_runs_analyzed"] == 1408
        assert analysis["total_unique_schedules"] == 352

        concordance = analysis["concordance_against_glhs_b111"]

        # MIN_READSET_TOKEN vs GLHS_B111: 100% concordance
        min_c = concordance["MIN_READSET_TOKEN"]
        assert min_c["concordance_rate"] == 1.0
        assert min_c["discordant_schedules"] == 0
        assert min_c["mcnemar_p_value"] == 1.0
        assert min_c["byte_reduction_pct"] > 0  # Should achieve significant byte reduction

        # HMAC_READSET_TOKEN vs GLHS_B111: 100% concordance
        hmac_c = concordance["HMAC_READSET_TOKEN"]
        assert hmac_c["concordance_rate"] == 1.0
        assert hmac_c["discordant_schedules"] == 0
        assert hmac_c["mcnemar_p_value"] == 1.0
        assert hmac_c["byte_reduction_pct"] > 0

        # Markdown report generation
        md_report = generate_markdown_report(analysis)
        assert "# E02 Minimal Alternative Binding Baseline" in md_report
        assert "MIN_READSET_TOKEN" in md_report
        assert "HMAC_READSET_TOKEN" in md_report
