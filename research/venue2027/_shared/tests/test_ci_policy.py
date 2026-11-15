"""Tests for SH-unified_ci (research/venue2027/_shared/tools/ci_policy.py).

Positive controls:
- A research-only change set (research/venue2027/_shared/) selects the full R4
  gate (secret_scan, chronology, r4_pytest, claim_lint, e22_offline) plus
  artifact checks on pull_request.
- A docs-only change set selects only the docs check (quality/docs-check) and
  never a heavy R4/pytest job.
- Production classes select their SUT suites (api/ml/web) without the R4 gate.
- The embedded default policy table audits clean against the real repo, and
  the recorded R4 gate evidence is green.

Adversarial controls (each must be REFUSED, never silently treated as safe):
- A policy entry naming a nonexistent workflow is refused
  (MISSING_GATE_WORKFLOW).
- A policy entry referencing a nonexistent script is refused
  (MISSING_GATE_SCRIPT).
- A policy routing a research-claim-bearing class to a trivial check instead
  of the R4 gate is refused (RESEARCH_CLASS_MISSING_R4_GATE).
- An auto run that silently changes frozen release data is refused
  (FROZEN_RELEASE_DATA_AUTO_RUN) — heavy frozen campaign only on
  workflow_dispatch or signed tag.
- A nightly schedule run must stay light smoke (HEAVY_GATE_ON_SCHEDULE).
- An unknown event fails closed with no claimed gates (UNKNOWN_EVENT).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(TOOLS))

import ci_policy  # noqa: E402

RESEARCH_ONLY_CHANGE = ("research/venue2027/_shared/tools/ci_policy.py",)
DOCS_ONLY_CHANGE = ("docs/getting-started.md",)


# --------------------------------------------------------------- positive
def test_research_only_change_selects_full_r4_gate() -> None:
    checks = ci_policy.choose_gate(RESEARCH_ONLY_CHANGE, event="pull_request")
    assert checks.ok_to_auto_run is True
    assert checks.requires_r4_gate is True
    for job_id in ("secret_scan", "chronology", "r4_pytest", "claim_lint", "e22_offline"):
        assert job_id in checks.required_job_ids, checks.to_dict()
    assert "artifact_safety_policy" in checks.required_job_ids


def test_research_only_change_routes_to_r4_workflow_not_trivial_check() -> None:
    """A change requiring the R4 gate can never be routed to a trivial check."""

    checks = ci_policy.choose_gate(RESEARCH_ONLY_CHANGE, event="pull_request")
    required = set(checks.required_job_ids)
    assert "r4_pytest" in required
    # Every R4-bearing required job must be served by the real R4 workflow.
    assert all(
        job.workflow == ci_policy.R4_WORKFLOW
        for job in checks.required_jobs
        if job.job_id in ci_policy.R4_GATE_JOB_IDS
    )


def test_docs_only_change_selects_docs_check_only() -> None:
    checks = ci_policy.choose_gate(DOCS_ONLY_CHANGE, event="pull_request")
    assert checks.ok_to_auto_run is True
    assert checks.required_job_ids == ("quality",)
    assert not checks.requires_r4_gate
    assert checks.change_class == "docs"


def test_production_classes_select_sut_suites_without_r4_gate() -> None:
    api = ci_policy.choose_gate(("services/api/src/clara_api/main.py",), event="pull_request")
    assert "api_tests" in api.required_job_ids and not api.requires_r4_gate
    ml = ci_policy.choose_gate(("services/ml/src/clara_ml/main.py",), event="pull_request")
    assert "ml_tests" in ml.required_job_ids and not ml.requires_r4_gate
    web = ci_policy.choose_gate(("apps/web/app/page.tsx",), event="pull_request")
    assert "web_lint_build" in web.required_job_ids and not web.requires_r4_gate


def test_gate_config_change_pulls_r4_gate_plus_repo_gates() -> None:
    checks = ci_policy.choose_gate(
        (".github/workflows/glhs-r4-novelty-gate.yml",), event="pull_request"
    )
    assert checks.requires_r4_gate is True
    assert "scripts_syntax" in checks.required_job_ids
    assert "artifact_safety_policy" in checks.required_job_ids


def test_signed_tag_release_data_adds_release_gate_and_allows_run() -> None:
    checks = ci_policy.choose_gate(("research/glhs_journal/q4_r4/protocols/e22.yaml",), event="tag")
    assert checks.ok_to_auto_run is True
    assert "eval_release_gate" in checks.required_job_ids
    assert checks.requires_r4_gate is True


def test_controlled_dispatch_allows_frozen_campaign() -> None:
    checks = ci_policy.choose_gate(
        ("research/glhs_journal/q4_r4/experiments_plan_r4.json",),
        event="workflow_dispatch",
    )
    assert checks.ok_to_auto_run is True
    assert checks.requires_r4_gate is True


def test_default_policy_table_audits_clean_against_real_repo() -> None:
    result = ci_policy.audit_policy(repo=REPO_ROOT)
    assert result.ok is True, result.to_dict()
    assert result.reason_codes == ("OK",)
    assert result.entries_audited > 0


def test_recorded_r4_gate_evidence_is_green() -> None:
    ok, code = ci_policy.assert_r4_gate_green(REPO_ROOT)
    assert ok is True, code
    assert code == "R4_EVIDENCE_OK"


def test_checks_to_dict_is_json_serializable() -> None:
    import json

    checks = ci_policy.choose_gate(RESEARCH_ONLY_CHANGE, event="pull_request")
    payload = json.dumps(checks.to_dict())
    assert "r4_pytest" in payload


# ------------------------------------------------------------ adversarial
def test_policy_naming_nonexistent_workflow_refused() -> None:
    entry = ci_policy.PolicyEntry(
        change_class="research_evidence",
        job_id="r4_pytest",
        workflow=".github/workflows/does-not-exist.yml",
        job="some-job",
        argv="python3 research/glhs_journal/q4_r4/chronology_validator_r4.py",
        blocking=True,
        script="research/glhs_journal/q4_r4/chronology_validator_r4.py",
    )
    result = ci_policy.audit_policy([entry], repo=REPO_ROOT)
    assert result.ok is False
    assert "MISSING_GATE_WORKFLOW" in result.reason_codes


def test_policy_naming_nonexistent_script_refused() -> None:
    entry = ci_policy.PolicyEntry(
        change_class="gate_config",
        job_id="claim_lint",
        workflow=ci_policy.R4_WORKFLOW,
        job="r4-claim-lint",
        argv="python3 scripts/ci/never_written.py",
        blocking=True,
        script="scripts/ci/never_written.py",
    )
    result = ci_policy.audit_policy([entry], repo=REPO_ROOT)
    assert result.ok is False
    assert "MISSING_GATE_SCRIPT" in result.reason_codes


def test_policy_routing_research_claim_to_trivial_check_refused() -> None:
    """The R4 gate cannot be swapped out for a docs-only check."""

    trivial = ci_policy.PolicyEntry(
        change_class="research_evidence",
        job_id="quality",
        workflow=ci_policy.CI_WORKFLOW,
        job="quality",
        argv="bash scripts/docs/check-docs-links.sh",
        blocking=True,
        script="scripts/docs/check-docs-links.sh",
    )
    result = ci_policy.audit_policy([trivial], repo=REPO_ROOT)
    assert result.ok is False
    assert "RESEARCH_CLASS_MISSING_R4_GATE" in result.reason_codes


def test_frozen_release_data_auto_run_refused() -> None:
    for event in ("pull_request", "push", "schedule"):
        checks = ci_policy.choose_gate(
            ("research/glhs_journal/q4_r4/provenance_metadata_r4.json",), event=event
        )
        assert not checks.ok_to_auto_run, (event, checks.to_dict())
        assert "FROZEN_RELEASE_DATA_AUTO_RUN" in checks.refusal_codes


def test_heavy_gate_on_nightly_schedule_refused() -> None:
    checks = ci_policy.choose_gate(("services/api/src/clara_api/main.py",), event="schedule")
    assert not checks.ok_to_auto_run
    assert "HEAVY_GATE_ON_SCHEDULE" in checks.refusal_codes


def test_unknown_event_fails_closed_with_no_claimed_gates() -> None:
    checks = ci_policy.choose_gate(RESEARCH_ONLY_CHANGE, event="full-moon")
    assert checks.required_jobs == () and checks.optional_jobs == ()
    assert checks.refusal_codes == ("UNKNOWN_EVENT",)


def test_empty_and_none_change_sets_are_noops() -> None:
    for change_set in ((), [], None, ""):
        checks = ci_policy.choose_gate(change_set, event="pull_request")
        assert checks.required_jobs == () and checks.optional_jobs == ()
        assert checks.ok_to_auto_run is True


def test_frozen_release_evidence_guards_fail_closed(tmp_path: pathlib.Path) -> None:
    missing = ci_policy.assert_r4_gate_green(tmp_path)
    assert missing == (False, "R4_EVIDENCE_MISSING")
    evidence = tmp_path / "research" / "venue2027" / "_shared"
    evidence.mkdir(parents=True)
    (evidence / "green_gate.json").write_text('{"overall_status": "FAIL"}', encoding="utf-8")
    not_green = ci_policy.assert_r4_gate_green(tmp_path)
    assert not_green == (False, "R4_GATE_NOT_GREEN")


def test_audit_policy_empty_table_refused(tmp_path: pathlib.Path) -> None:
    result = ci_policy.audit_policy([], repo=tmp_path)
    assert result.ok is False
    assert result.reason_codes == ("POLICY_EMPTY",)


@pytest.mark.parametrize(
    "entry_kwargs,expected_code",
    [
        (
            {
                "change_class": "not-a-class",
                "job_id": "quality",
                "workflow": ci_policy.CI_WORKFLOW,
                "job": "quality",
                "argv": "x",
                "blocking": True,
                "script": "scripts/docs/check-docs-links.sh",
            },
            "UNKNOWN_CHANGE_CLASS",
        ),
        (
            {
                "change_class": "docs",
                "job_id": "quality",
                "workflow": "README.md",
                "job": "quality",
                "argv": "x",
                "blocking": True,
                "script": "scripts/docs/check-docs-links.sh",
            },
            "MISSING_GATE_WORKFLOW",
        ),
        (
            {
                "change_class": "docs",
                "job_id": "quality",
                "workflow": ci_policy.CI_WORKFLOW,
                "job": "quality",
                "argv": "   ",
                "blocking": True,
                "script": "scripts/docs/check-docs-links.sh",
            },
            "POLICY_ENTRY_INVALID",
        ),
    ],
)
def test_policy_entry_invalid_vectors(entry_kwargs: dict, expected_code: str) -> None:
    result = ci_policy.audit_policy([ci_policy.PolicyEntry(**entry_kwargs)], repo=REPO_ROOT)
    assert result.ok is False
    assert expected_code in result.reason_codes
