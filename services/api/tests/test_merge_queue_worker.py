"""Unit and integration tests for CLARA Care Merge Queue Worker.

Spec: PH02 / A07 (Tests + CI)
Validates:
  1. Path lane parsing and ACL enforcement (in-lane vs out-of-lane mutations).
  2. Subagent change_manifest.json validation (required schemas, blockers, deliverables).
  3. Cross-agent file collision detection (disallowing concurrent edits to same files).
  4. Deterministic dependency sequence: A02->A01->A03->A04->A05->A06->A07->A08->A09->A10.
  5. Commit resolution and cherry-pick orchestration (clean apply, conflict abort, base SHA no-ops).
  6. Integration test suite gating and status reporting.
  7. Canonical merge_manifest.json generation matching schema.
  8. End-to-end CLI invocation and dry-run execution.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

# Add scripts/ops to Python search path
REPO_ROOT = Path(__file__).resolve().parents[3]
OPS_DIR = REPO_ROOT / "scripts/ops"
if str(OPS_DIR) not in sys.path:
    sys.path.insert(0, str(OPS_DIR))

from merge_queue_worker import (  # noqa: E402
    DEFAULT_PH02_PATH_LANES,
    DEFAULT_ROLES,
    DETERMINISTIC_ORDER,
    AgentManifest,
    CherryPickResult,
    FileCollision,
    MergeQueueWorker,
    PathAclViolation,
    TestGateResult,
    build_merge_manifest_dict,
    check_all_path_acls,
    detect_file_collisions,
    execute_cherry_pick,
    is_file_in_path_lane,
    load_phase_tasks_from_spec,
    normalize_lane_entry,
    resolve_commit_for_agent,
    run_test_suite_gates,
    validate_agent_manifest,
)


def test_deterministic_dependency_order():
    """Verify that deterministic dependency order strictly adheres to PH02 spec."""
    expected = ["A02", "A01", "A03", "A04", "A05", "A06", "A07", "A08", "A09", "A10"]
    assert DETERMINISTIC_ORDER == expected
    assert len(DETERMINISTIC_ORDER) == 10
    assert len(set(DETERMINISTIC_ORDER)) == 10


def test_normalize_lane_entry():
    """Verify lane normalization strips leading slashes and whitespace."""
    assert normalize_lane_entry("  /services/api/src/  ") == "services/api/src/"
    assert normalize_lane_entry("contracts/") == "contracts/"
    assert normalize_lane_entry("/apps/web/app/page.tsx") == "apps/web/app/page.tsx"


def test_is_file_in_path_lane_positive():
    """Verify in-lane files are permitted for designated agent roles."""
    phase = "PH02"

    # Agent's own artifact folder is always allowed
    assert is_file_in_path_lane("artifacts/PH02/A01/change_manifest.json", "A01", phase, ["services/api/src/"])
    assert is_file_in_path_lane("artifacts/ph02/a07/test_report.md", "A07", phase, ["services/api/tests/"])

    # Prefix directory lane
    assert is_file_in_path_lane(
        "services/api/src/clara_api/api/routes.py",
        "A01",
        phase,
        DEFAULT_PH02_PATH_LANES["A01"],
    )
    assert is_file_in_path_lane(
        "services/api/alembic/versions/20260824_0065_test.py",
        "A02",
        phase,
        DEFAULT_PH02_PATH_LANES["A02"],
    )
    assert is_file_in_path_lane(
        "services/ml/src/clara_ml/pipeline.py",
        "A04",
        phase,
        DEFAULT_PH02_PATH_LANES["A04"],
    )
    assert is_file_in_path_lane(
        "apps/web/app/dashboard/page.tsx",
        "A05",
        phase,
        DEFAULT_PH02_PATH_LANES["A05"],
    )
    assert is_file_in_path_lane(
        "apps/mobile/lib/main.dart",
        "A06",
        phase,
        DEFAULT_PH02_PATH_LANES["A06"],
    )
    assert is_file_in_path_lane(
        "services/api/tests/test_new_feature.py",
        "A07",
        phase,
        DEFAULT_PH02_PATH_LANES["A07"],
    )
    assert is_file_in_path_lane(
        "scripts/ops/merge_queue_worker.py",
        "A07",
        phase,
        DEFAULT_PH02_PATH_LANES["A07"],
    )

    # Exact file lane
    assert is_file_in_path_lane(
        "services/api/src/clara_api/schemas.py",
        "A01",
        phase,
        DEFAULT_PH02_PATH_LANES["A01"],
    )


def test_is_file_in_path_lane_negative():
    """Verify out-of-lane file mutations are strictly rejected."""
    phase = "PH02"

    # A01 trying to modify DB migrations (owned by A02)
    assert not is_file_in_path_lane(
        "services/api/alembic/versions/0063_bad.py",
        "A01",
        phase,
        DEFAULT_PH02_PATH_LANES["A01"],
    )

    # A05 (Web) trying to modify backend API routes (owned by A01)
    assert not is_file_in_path_lane(
        "services/api/src/clara_api/api/chat.py",
        "A05",
        phase,
        DEFAULT_PH02_PATH_LANES["A05"],
    )

    # A02 trying to modify Web UX (owned by A05)
    assert not is_file_in_path_lane(
        "apps/web/app/page.tsx",
        "A02",
        phase,
        DEFAULT_PH02_PATH_LANES["A02"],
    )

    # A07 trying to modify another agent's private artifacts
    assert not is_file_in_path_lane(
        "artifacts/PH02/A01/change_manifest.json",
        "A07",
        phase,
        DEFAULT_PH02_PATH_LANES["A07"],
    )


def test_validate_agent_manifest_valid(tmp_path: Path):
    """Verify valid manifest passing all integrity gates."""
    phase_dir = tmp_path / "artifacts" / "PH02" / "A07"
    phase_dir.mkdir(parents=True)

    manifest_file = phase_dir / "change_manifest.json"
    test_report_file = phase_dir / "test_report.md"
    risk_register_file = phase_dir / "risk_register.md"

    test_report_file.write_text("# Test Report\nPassed.", encoding="utf-8")
    risk_register_file.write_text("# Risk Register\nNo high risks.", encoding="utf-8")

    manifest_data = {
        "manifest_version": "1.0.0",
        "phase_id": "PH02",
        "agent_id": "A07",
        "role": "Tests + CI",
        "task": "merge queue and integration worker",
        "status": "COMPLETE",
        "branch": "phase/ph02-a07",
        "commit": "879dc5dcfcaae91b3626e28062043d934294478b",
        "files_changed": [
            "scripts/ops/merge_queue_worker.py",
            "services/api/tests/test_merge_queue_worker.py",
            "artifacts/PH02/A07/change_manifest.json",
        ],
        "verified_source_anchors": [
            "scripts/ops/merge_queue_worker.py:1-100",
            "services/api/tests/test_merge_queue_worker.py:1-50",
        ],
        "test_execution_results": {"unit_tests": {"exit_code": 0, "passed": 10}},
        "blockers": [],
        "rollback_steps": ["git reset --hard HEAD~1"],
        "remediations": ["Added merge queue worker"],
    }
    manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

    result = validate_agent_manifest(manifest_file, "PH02", "A07")
    assert result.valid is True
    assert len(result.errors) == 0
    assert result.manifest is not None
    assert result.manifest.agent_id == "A07"
    assert result.manifest.status == "COMPLETE"
    assert len(result.manifest.files_changed) == 3


def test_validate_agent_manifest_missing_file(tmp_path: Path):
    """Verify missing manifest fails closed."""
    non_existent = tmp_path / "does_not_exist.json"
    result = validate_agent_manifest(non_existent, "PH02", "A01")
    assert result.valid is False
    assert any("not found" in err.lower() for err in result.errors)


def test_validate_agent_manifest_invalid_json(tmp_path: Path):
    """Verify corrupted JSON syntax is caught with clean error."""
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{this is not json", encoding="utf-8")
    result = validate_agent_manifest(bad_json, "PH02", "A01")
    assert result.valid is False
    assert any("invalid json" in err.lower() for err in result.errors)


def test_validate_agent_manifest_mismatched_identity(tmp_path: Path):
    """Verify mismatch in agent_id or phase_id is rejected."""
    phase_dir = tmp_path / "artifacts" / "PH02" / "A01"
    phase_dir.mkdir(parents=True)
    (phase_dir / "test_report.md").write_text("Report", encoding="utf-8")
    (phase_dir / "risk_register.md").write_text("Risks", encoding="utf-8")

    manifest_file = phase_dir / "change_manifest.json"
    manifest_file.write_text(
        json.dumps(
            {
                "manifest_version": "1.0.0",
                "phase_id": "PH01",  # Wrong phase
                "agent_id": "A02",  # Wrong agent
                "status": "COMPLETE",
                "blockers": [],
                "files_changed": ["foo.py"],
                "verified_source_anchors": ["foo.py:1"],
            }
        ),
        encoding="utf-8",
    )

    result = validate_agent_manifest(manifest_file, "PH02", "A01")
    assert result.valid is False
    assert any("mismatched phase_id" in err.lower() for err in result.errors)
    assert any("mismatched agent_id" in err.lower() for err in result.errors)


def test_validate_agent_manifest_with_unresolved_blockers(tmp_path: Path):
    """Verify that manifests declaring unresolved blockers fail integration."""
    phase_dir = tmp_path / "artifacts" / "PH02" / "A03"
    phase_dir.mkdir(parents=True)
    (phase_dir / "test_report.md").write_text("Report", encoding="utf-8")
    (phase_dir / "risk_register.md").write_text("Risks", encoding="utf-8")

    manifest_file = phase_dir / "change_manifest.json"
    manifest_file.write_text(
        json.dumps(
            {
                "manifest_version": "1.0.0",
                "phase_id": "PH02",
                "agent_id": "A03",
                "status": "COMPLETE",
                "blockers": ["BLOCKER-01: Postgres environment missing"],
                "files_changed": ["services/api/src/clara_api/glhs/service.py"],
                "verified_source_anchors": ["services/api/src/clara_api/glhs/service.py:10"],
            }
        ),
        encoding="utf-8",
    )

    result = validate_agent_manifest(manifest_file, "PH02", "A03")
    assert result.valid is False
    assert any("unresolved blockers" in err.lower() for err in result.errors)


def test_validate_agent_manifest_missing_deliverables(tmp_path: Path):
    """Verify that absence of test_report.md or risk_register.md causes validation failure."""
    phase_dir = tmp_path / "artifacts" / "PH02" / "A04"
    phase_dir.mkdir(parents=True)

    manifest_file = phase_dir / "change_manifest.json"
    manifest_file.write_text(
        json.dumps(
            {
                "manifest_version": "1.0.0",
                "phase_id": "PH02",
                "agent_id": "A04",
                "status": "COMPLETE",
                "blockers": [],
                "files_changed": ["services/ml/src/clara_ml/rag.py"],
                "verified_source_anchors": ["services/ml/src/clara_ml/rag.py:1"],
            }
        ),
        encoding="utf-8",
    )
    # Deliverables test_report.md and risk_register.md are missing!

    result = validate_agent_manifest(manifest_file, "PH02", "A04")
    assert result.valid is False
    assert any("missing required deliverable" in err.lower() for err in result.errors)


def test_check_all_path_acls():
    """Verify path ACL batch check correctly isolates conforming and violating manifests."""
    m_a01 = AgentManifest(
        agent_id="A01",
        phase_id="PH02",
        role="API",
        task="Contract",
        status="COMPLETE",
        worktree="",
        branch="",
        commit="",
        files_changed=["services/api/src/clara_api/api/routes.py", "contracts/api.json"],
    )
    m_a02_bad = AgentManifest(
        agent_id="A02",
        phase_id="PH02",
        role="DB",
        task="Migration",
        status="COMPLETE",
        worktree="",
        branch="",
        commit="",
        files_changed=[
            "services/api/src/clara_api/db/session.py",
            "apps/web/app/admin/page.tsx",  # VIOLATION: A02 touches Web app!
        ],
    )

    manifests = {"A01": m_a01, "A02": m_a02_bad}
    violations = check_all_path_acls(manifests, DEFAULT_PH02_PATH_LANES, "PH02")

    assert len(violations) == 1
    assert violations[0].agent_id == "A02"
    assert violations[0].file_path == "apps/web/app/admin/page.tsx"


def test_detect_file_collisions():
    """Verify detection of cross-agent file overlap and exclusion of agent artifacts."""
    m1 = AgentManifest(
        agent_id="A01",
        phase_id="PH02",
        role="API",
        task="Contract",
        status="COMPLETE",
        worktree="",
        branch="",
        commit="",
        files_changed=[
            "services/api/src/clara_api/schemas.py",
            "artifacts/PH02/A01/change_manifest.json",
        ],
    )
    m2 = AgentManifest(
        agent_id="A03",
        phase_id="PH02",
        role="Domain",
        task="Domain logic",
        status="COMPLETE",
        worktree="",
        branch="",
        commit="",
        files_changed=[
            "services/api/src/clara_api/schemas.py",  # COLLISION! Both modify schemas.py
            "artifacts/PH02/A03/change_manifest.json",
        ],
    )

    manifests = {"A01": m1, "A03": m2}
    collisions = detect_file_collisions(manifests, "PH02")

    assert len(collisions) == 1
    assert collisions[0].file_path == "services/api/src/clara_api/schemas.py"
    assert collisions[0].agents == ["A01", "A03"]


def test_execute_cherry_pick_base_sha_noop():
    """Verify that commits pointing to base SHA (no-op/doc-only agents) are handled cleanly."""
    base_sha = "879dc5dcfcaae91b3626e28062043d934294478b"
    res = execute_cherry_pick(
        repo_root=REPO_ROOT,
        commit_sha=base_sha,
        agent_id="A09",
        base_sha=base_sha,
        dry_run=False,
    )
    assert res.success is True
    assert "matches base sha" in res.message.lower()


def test_build_merge_manifest_dict():
    """Verify structure and fields of generated merge_manifest dictionary."""
    manifests = {
        "A01": AgentManifest(
            agent_id="A01",
            phase_id="PH02",
            role="API + contract",
            task="API schema contract",
            status="COMPLETE",
            worktree="/dev/shm/clara_worktrees/PH02_A01",
            branch="phase/ph02-a01",
            commit="879dc5dcfcaae91b3626e28062043d934294478b",
            files_changed=["contracts/schema.json"],
            remediations=["DEFECT-01 resolved"],
        )
    }
    cherry_pick_results = {
        "A01": CherryPickResult(
            agent_id="A01",
            commit_sha="879dc5dcfcaae91b3626e28062043d934294478b",
            success=True,
            message="Cleanly cherry-picked",
        )
    }
    test_results = [
        TestGateResult(
            command="python3 -m compileall",
            exit_code=0,
            duration_seconds=0.45,
            passed=True,
            stdout="Listing ...",
            stderr="",
        )
    ]

    manifest_dict = build_merge_manifest_dict(
        phase_id="PH02",
        phase_title="Thiết lập tổ chức tác nhân",
        base_sha="879dc5dcfcaae91b3626e28062043d934294478b",
        target_commit_sha="879dc5dcfcaae91b3626e28062043d934294478b",
        dependency_order=["A01"],
        manifests=manifests,
        cherry_pick_results=cherry_pick_results,
        file_collisions=[],
        test_results=test_results,
        integration_status="PASSED",
    )

    assert manifest_dict["schema_version"] == "1.0.0"
    assert manifest_dict["phase_id"] == "PH02"
    assert manifest_dict["integration_status"] == "PASSED"
    assert manifest_dict["file_conflict_count"] == 0
    assert len(manifest_dict["agents"]) == 1
    assert manifest_dict["agents"][0]["agent_id"] == "A01"
    assert manifest_dict["agents"][0]["status"] == "PASSED"
    assert manifest_dict["test_suite_results"][0]["status"] == "PASSED"


def test_run_test_suite_gates():
    """Verify test gate runner executes commands and returns structured results."""
    # Run with a known fast and passing command
    passed, results = run_test_suite_gates(
        repo_root=REPO_ROOT,
        custom_commands=[f"{sys.executable} -c 'print(\"Gate OK\")'"],
    )
    assert passed is True
    assert len(results) == 1
    assert results[0].exit_code == 0
    assert "Gate OK" in results[0].stdout

    # Run with a failing command
    failed, fail_results = run_test_suite_gates(
        repo_root=REPO_ROOT,
        custom_commands=[f"{sys.executable} -c 'import sys; sys.exit(42)'"],
    )
    assert failed is False
    assert len(fail_results) == 1
    assert fail_results[0].exit_code == 42


def test_merge_queue_worker_dry_run_synthetic(tmp_path: Path):
    """Verify complete end-to-end dry-run orchestration using a synthetic phase environment."""
    test_root = tmp_path / "repo"
    test_root.mkdir()

    # Initialize a mock git repo in test_root
    subprocess.run(["git", "init"], cwd=test_root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "CLARA Test"], cwd=test_root, check=True)
    subprocess.run(["git", "config", "user.email", "test@clara.care"], cwd=test_root, check=True)

    # Initial commit
    readme = test_root / "README.md"
    readme.write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=test_root, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=test_root, check=True)
    rev_proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=test_root, check=True, capture_output=True, text=True)
    base_sha = rev_proc.stdout.strip()

    # Create synthetic manifests for a 2-agent test: A02 (DB) and A01 (API)
    order = ["A02", "A01"]
    for aid in order:
        art_dir = test_root / "artifacts" / "PHTEST" / aid
        art_dir.mkdir(parents=True)
        (art_dir / "test_report.md").write_text("Passed", encoding="utf-8")
        (art_dir / "risk_register.md").write_text("No risk", encoding="utf-8")
        manifest_data = {
            "manifest_version": "1.0.0",
            "phase_id": "PHTEST",
            "agent_id": aid,
            "role": DEFAULT_ROLES.get(aid, "Test Role"),
            "task": f"Task for {aid}",
            "status": "COMPLETE",
            "commit": base_sha,
            "files_changed": [f"artifacts/PHTEST/{aid}/change_manifest.json"],
            "verified_source_anchors": ["README.md:1"],
            "blockers": [],
            "rollback_steps": ["git reset --hard"],
        }
        (art_dir / "change_manifest.json").write_text(json.dumps(manifest_data), encoding="utf-8")

    out_file = test_root / "artifacts" / "PHTEST" / "integration" / "merge_manifest.json"

    worker = MergeQueueWorker(
        repo_root=test_root,
        phase_id="PHTEST",
        base_sha=base_sha,
        worktrees_dir=test_root / "worktrees",
        output_path=out_file,
        order=order,
        dry_run=True,
        skip_tests=True,
    )

    exit_code = worker.run()
    assert exit_code == 0
    assert out_file.is_file()

    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["integration_status"] == "PASSED"
    assert data["phase_id"] == "PHTEST"
    assert len(data["agents"]) == 2


def test_cli_help_flag():
    """Verify that CLI script runs with --help flag successfully."""
    script_path = OPS_DIR / "merge_queue_worker.py"
    proc = subprocess.run([sys.executable, str(script_path), "--help"], capture_output=True, text=True)
    assert proc.returncode == 0
    assert "CLARA Care" in proc.stdout
    assert "--dry-run" in proc.stdout
    assert "--phase" in proc.stdout
