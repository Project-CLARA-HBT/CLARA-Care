from __future__ import annotations

from evaluation.governance_adversarial.not_run_capability import (
    DEFAULT_MATRIX,
    IMPLEMENTABLE_FAITHFULLY,
    REQUIRES_LLM_ATTACK_STUDY,
    TASK_OR_ARM_SEMANTICS_UNSUPPORTED,
    build_capability_audit,
)


def _has_matrix() -> bool:
    return DEFAULT_MATRIX.is_file()


def _rows_fixture() -> list[dict[str, str]]:
    # Minimal rows for the six final-003 NOT_RUN families across four arms.
    families = [
        "cross_subject_retrieval",
        "purpose_mismatch",
        "policy_version_change",
        "gst_bypass_prompt",
        "patient_evidence_prompt_injection",
        "unrelated_disclosure_request",
    ]
    rows = []
    for family in families:
        for arm in ("UNBOUND", "STATE_VERSION_ONLY", "SNAPSHOT_BOUND_STATE_ONLY", "GLHS_STRICT"):
            rows.append(
                {
                    "family": family,
                    "arm": arm,
                    "not_run_n": "30",
                    "executed_n": "0",
                }
            )
    return rows


def test_classifies_all_not_run_families() -> None:
    audit = build_capability_audit(_rows_fixture())
    assert audit["classification_counts"] == {
        IMPLEMENTABLE_FAITHFULLY: 16,
        TASK_OR_ARM_SEMANTICS_UNSUPPORTED: 0,
        REQUIRES_LLM_ATTACK_STUDY: 8,
    }
    assert audit["families_by_category"][IMPLEMENTABLE_FAITHFULLY] == [
        "cross_subject_retrieval",
        "policy_version_change",
        "purpose_mismatch",
        "unrelated_disclosure_request",
    ]
    assert audit["families_by_category"][REQUIRES_LLM_ATTACK_STUDY] == [
        "gst_bypass_prompt",
        "patient_evidence_prompt_injection",
    ]


def test_completed_primary_families_noted_with_commit() -> None:
    audit = build_capability_audit(_rows_fixture())
    completed = {row["family"] for row in audit["rows"] if row["completed_since_final_003"]}
    assert completed == {"cross_subject_retrieval", "purpose_mismatch", "policy_version_change"}
    for row in audit["rows"]:
        if row["family"] in completed:
            assert row["completion_commit"] == "bd0d7d65"


def test_prompt_injection_families_kept_outside_core_endpoint() -> None:
    audit = build_capability_audit(_rows_fixture())
    for row in audit["rows"]:
        if row["family"] in {"gst_bypass_prompt", "patient_evidence_prompt_injection"}:
            assert row["capability"] == REQUIRES_LLM_ATTACK_STUDY
            assert "model-mediated" in str(row["technical_reason"])
            assert row["reporting_scope"] == "secondary_robustness_stress"


def test_technical_reason_present_everywhere() -> None:
    audit = build_capability_audit(_rows_fixture())
    for row in audit["rows"]:
        assert len(str(row["technical_reason"])) > 40


def test_reproduces_from_generated_matrix_when_present() -> None:
    if not _has_matrix():
        return
    from evaluation.governance_adversarial.not_run_capability import _load_matrix_rows

    rows = _load_matrix_rows(DEFAULT_MATRIX)
    audit = build_capability_audit(rows)
    assert audit["classification_counts"][IMPLEMENTABLE_FAITHFULLY] == 16
    assert audit["classification_counts"][REQUIRES_LLM_ATTACK_STUDY] == 8
