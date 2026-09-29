"""Unit tests for Phase 5 (E05 Root-Cause Replay of Historical Mismatches).

Tests cover:
1. Architecture (A): Causal tracing for V2-05 and V2-09 mismatch mechanisms.
2. Statistics (B): Timing perturbation instrumentation, Wilson confidence bounds, distributions.
3. Implementation (C): Replay drivers (v205, v209), analysis generator, safety invariant checks.
4. Reproducibility (D): Sealing generator, protocol validation, reproduce_e05 offline execution.
5. Red Team (E): Historical artifact immutability, reconciliation honesty, zero forbidden commits.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from evaluation.glhs_toctou_root_cause.analyze_root_cause import (
    HISTORICAL_V2_05,
    HISTORICAL_V2_09,
    _wilson_upper,
    run_analysis,
)
from evaluation.glhs_toctou_root_cause.replay_v2_05 import (
    run_replay as run_replay_v205,
)
from evaluation.glhs_toctou_root_cause.replay_v2_09 import (
    run_replay as run_replay_v209,
)
from evaluation.glhs_toctou_root_cause.seal import (
    seal_experiment_e05,
    sha256_file,
    validate_e05_protocol,
)
from reproduce_e05 import reproduce_and_verify

ROOT = Path(__file__).resolve().parent.parent.parent.parent
PROTOCOL_PATH = ROOT / "protocols/E05_toctou_root_cause/protocol.json"
ARTIFACT_DIR = ROOT / "research/glhs_journal/q2_r2/protocols/E05_toctou_root_cause"
HISTORICAL_DIR = ROOT / "research/glhs_journal/protocol_v2"


class TestArchitectureCausalTracing:
    """Task 1: Architecture role verification."""

    def test_v205_causal_mechanism(self) -> None:
        """Verify V2-05 causal mechanism is consent_revoke vs propose_assertion re-check."""
        assert HISTORICAL_V2_05["id"] == "TOCTOU-V2-05"
        assert HISTORICAL_V2_05["expected_classification"] == "indeterminate_ordering"
        assert HISTORICAL_V2_05["observed_classification"] == "rejected_after_or_during_governance_race"
        assert HISTORICAL_V2_05["forbidden_commit_observed"] is False
        assert HISTORICAL_V2_05["safety_success"] is True

    def test_v209_causal_mechanism(self) -> None:
        """Verify V2-09 causal mechanism is consent_revoke vs apply_transition re-check."""
        assert HISTORICAL_V2_09["id"] == "TOCTOU-V2-09"
        assert HISTORICAL_V2_09["expected_classification"] == "indeterminate_ordering"
        assert HISTORICAL_V2_09["observed_classification"] == "rejected_during_or_before_governance_race"
        assert HISTORICAL_V2_09["forbidden_commit_observed"] is False
        assert HISTORICAL_V2_09["safety_success"] is True


class TestStatisticsInstrumentation:
    """Task 2: Statistics role verification."""

    def test_wilson_upper_bound(self) -> None:
        """Verify Wilson confidence bound calculation."""
        # 100 trials, 98 successes -> upper bound close to 0.99
        ub = _wilson_upper(98, 100)
        assert 0.95 <= ub <= 1.0

        # 0 trials -> 1.0
        assert _wilson_upper(0, 0) == 1.0

    def test_v205_perturbation_distribution(self) -> None:
        """Verify timing perturbation distribution for V2-05."""
        rpt = run_replay_v205(perturbation_count=5, master_seed=20260928)
        assert rpt.perturbation_count == 5
        assert len(rpt.trials) == 5
        assert rpt.root_cause_classification == "conservative_safe_rejection_by_implementation"

        # Check fields in trial record
        t0 = rpt.trials[0]
        assert "trial_id" in t0
        assert "seed" in t0
        assert "governance_delay_us" in t0
        assert "proposal_delay_us" in t0
        assert "observed_classification" in t0
        assert t0["forbidden_commit"] is False
        assert t0["safety_success"] is True

    def test_v209_perturbation_distribution(self) -> None:
        """Verify timing perturbation distribution for V2-09."""
        rpt = run_replay_v209(perturbation_count=5, master_seed=20260929)
        assert rpt.perturbation_count == 5
        assert len(rpt.trials) == 5
        assert rpt.root_cause_classification == "conservative_safe_rejection_by_implementation"

        t0 = rpt.trials[0]
        assert "trial_id" in t0
        assert "seed" in t0
        assert "governance_delay_us" in t0
        assert "commit_delay_us" in t0
        assert t0["forbidden_commit"] is False
        assert t0["safety_success"] is True


class TestImplementationReplayAndAnalysis:
    """Task 3: Implementation role verification."""

    def test_run_analysis_structure(self) -> None:
        """Verify consolidated root-cause analysis output."""
        analysis = run_analysis()
        assert analysis["analysis_id"] == "E05-TOCTOU-ROOT-CAUSE-20260928"
        assert analysis["schema_version"] == "glhs-e05-root-cause-analysis-v1"
        assert analysis["safety_verdict"]["verdict"] == "SAFETY_PRESERVED"
        assert analysis["safety_verdict"]["forbidden_commits_historical"] == 0
        assert analysis["safety_verdict"]["forbidden_commits_replay_v205"] == 0
        assert analysis["safety_verdict"]["forbidden_commits_replay_v209"] == 0
        assert analysis["artifact_integrity"]["historical_artifacts_modified"] is False
        assert "TOCTOU-V2-05" in analysis["analysis"]
        assert "TOCTOU-V2-09" in analysis["analysis"]

    def test_zero_forbidden_commits_invariant(self) -> None:
        """Ensure no trial in V2-05 or V2-09 produces a forbidden commit."""
        v205_rpt = run_replay_v205(perturbation_count=5)
        v209_rpt = run_replay_v209(perturbation_count=5)

        for t in v205_rpt.trials:
            assert t["forbidden_commit"] is not True
            assert t["safety_success"] is True

        for t in v209_rpt.trials:
            assert t["forbidden_commit"] is not True
            assert t["safety_success"] is True


class TestReproducibilityAndSealing:
    """Task 4: Reproducibility role verification."""

    def test_protocol_validation(self) -> None:
        """Verify protocol.json validation."""
        protocol_data = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
        res = validate_e05_protocol(protocol_data)
        assert res["valid"] is True
        assert res["protocol_id"] == "E05-TOCTOU-ROOT-CAUSE"

    def test_seal_experiment_e05(self, tmp_path: Path) -> None:
        """Verify SHA-256 seal generator."""
        seal_doc = seal_experiment_e05(
            protocol_path=PROTOCOL_PATH,
            artifact_dir=tmp_path,
            perturbation_count=5,
        )
        assert seal_doc["schema_version"] == "glhs-e05-root-cause-seal-v1"
        assert seal_doc["status"] == "SEALED"
        assert seal_doc["claim_eligible"] is True
        assert seal_doc["total_perturbations"] >= 10
        assert seal_doc["forbidden_commits_observed"] == 0

    def test_offline_reproduction(self) -> None:
        """Verify offline reproduction via reproduce_e05.py."""
        result = reproduce_and_verify(
            artifact_dir=ARTIFACT_DIR,
            protocol_path=PROTOCOL_PATH,
        )
        assert result["status"] == "REPRODUCED_AND_VERIFIED"
        assert result["protocol_id"] == "E05-TOCTOU-ROOT-CAUSE"
        assert result["claim_eligible"] is True
        assert result["safety_verdict"] == "SAFETY_PRESERVED"
        assert result["total_perturbations"] == 200


class TestRedTeamImmutabilityAndHonesty:
    """Task 5: Red Team role verification."""

    def test_historical_artifacts_untouched(self) -> None:
        """Verify historical reference files in protocol_v2/ have NOT been edited."""
        v2_protocol_path = HISTORICAL_DIR / "postgres_toctou_protocol_v2.json"
        v2_raw_path = HISTORICAL_DIR / "run_v2_raw.json"
        v2_analysis_path = HISTORICAL_DIR / "analysis_v2.json"

        assert v2_protocol_path.exists(), "Historical protocol_v2 missing!"
        assert v2_raw_path.exists(), "Historical run_v2_raw missing!"
        assert v2_analysis_path.exists(), "Historical analysis_v2 missing!"

        # Verify historical raw data still contains the historical mismatches
        raw_data = json.loads(v2_raw_path.read_text(encoding="utf-8"))
        audit_items = raw_data.get("classification_audit", [])
        v205_historical = next(s for s in audit_items if s["id"] == "TOCTOU-V2-05")
        v209_historical = next(s for s in audit_items if s["id"] == "TOCTOU-V2-09")

        assert v205_historical["expected_classification"] == "indeterminate_ordering"
        assert v205_historical["observed_classification"] == "rejected_after_or_during_governance_race"
        assert v205_historical["matches"] is False

        assert v209_historical["expected_classification"] == "indeterminate_ordering"
        assert v209_historical["observed_classification"] == "rejected_during_or_before_governance_race"
        assert v209_historical["matches"] is False

    def test_reconciliation_honesty(self) -> None:
        """Verify reconciliation note explains mismatches without altering history."""
        analysis = run_analysis()
        rec = analysis["formal_reconciliation"]

        assert "DO NOT modify" in analysis["artifact_integrity"]["note"] or "IMMUTABLE" in analysis["artifact_integrity"]["note"]
        assert "EXECUTED_V2_OBSERVATION_MISMATCH" in rec
        assert "conservative_safe_rejection" in rec
        assert "0" == str(analysis["safety_verdict"]["forbidden_commits_historical"])
