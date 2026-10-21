"""Automated regression verification for task-scoped path governance and domain boundaries.

Verifies:
1. Ground-truth HEAD SHA immutability against frozen baseline 879dc5dcfcaae91b3626e28062043d934294478b.
2. Complete path disjointness across all 10 subagent roles (A01..A10) in Phase PH02.
3. Exclusive allocation of domain modules (glhs, lifemap, phr, compliance, core) to Agent A03.
4. Positive/negative access control enforcement (allow, deny, malformed, cross-lane, path traversal).
5. Strict domain boundary isolation ensuring zero direct imports of `clara_ml`.
6. Audit verification against PHASE_TASKS.json.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from clara_api.core.path_governance import (
    DOMAIN_MODULE_PATHS,
    FROZEN_BASE_SHA,
    PH02_AGENT_ALLOCATIONS,
    audit_domain_import_boundaries,
    audit_ph02_lane_disjointness,
    audit_phase_tasks_json,
    check_two_lanes_overlap,
    is_path_allowed_for_agent,
    normalize_lane_path,
    paths_have_overlap,
)


def test_repo_frozen_head_sha_integrity() -> None:
    """Ground-truth commit SHA or merge-base ancestor must match the frozen baseline exactly."""
    result = subprocess.run(
        ["git", "merge-base", FROZEN_BASE_SHA, "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    base_sha = result.stdout.strip()
    assert (
        base_sha == FROZEN_BASE_SHA
    ), f"Repo merge-base {base_sha} diverged from frozen baseline {FROZEN_BASE_SHA}"


def test_ph02_path_lane_disjointness_all_45_pairs() -> None:
    """All 10 subagent roles in PH02 must have 100% disjoint write path lanes (0 collisions)."""
    audit = audit_ph02_lane_disjointness()
    assert audit["total_agents"] == 10
    assert audit["total_pairs_evaluated"] == 45
    assert audit["is_disjoint"] is True
    assert audit["collision_count"] == 0
    assert audit["overlaps"] == []


def test_domain_modules_exclusively_allocated_to_a03() -> None:
    """Domain modules (glhs, lifemap, phr, compliance, core) belong exclusively to Agent A03."""
    a03_lanes = PH02_AGENT_ALLOCATIONS["A03"].path_lanes
    for domain_mod in DOMAIN_MODULE_PATHS:
        assert (
            domain_mod in a03_lanes
        ), f"Domain module {domain_mod} not present in A03 path lane"

    for agent_id, alloc in PH02_AGENT_ALLOCATIONS.items():
        if agent_id == "A03":
            continue
        for lane in alloc.path_lanes:
            for domain_mod in DOMAIN_MODULE_PATHS:
                assert not paths_have_overlap(
                    lane, domain_mod
                ), f"Agent {agent_id} illegally encroaches on domain module {domain_mod} via {lane}"


def test_path_access_check_matrix() -> None:
    """Verify positive allow, negative deny, cross-agent artifact, and traversal controls."""
    # Positive: A03 within domain lane
    allowed, reason = is_path_allowed_for_agent(
        "A03", "services/api/src/clara_api/glhs/commit_kernel.py"
    )
    assert allowed is True
    assert reason == "AUTHORIZED_TASK_LANE"

    allowed, reason = is_path_allowed_for_agent(
        "A03", "services/api/src/clara_api/compliance/service.py"
    )
    assert allowed is True
    assert reason == "AUTHORIZED_TASK_LANE"

    allowed, reason = is_path_allowed_for_agent(
        "A03", "services/api/src/clara_api/core/path_governance.py"
    )
    assert allowed is True
    assert reason == "AUTHORIZED_TASK_LANE"

    # Positive: A03 within own artifact directory
    allowed, reason = is_path_allowed_for_agent(
        "A03", "artifacts/PH02/A03/change_manifest.json"
    )
    assert allowed is True
    assert reason == "AUTHORIZED_ARTIFACT_LANE"

    # Negative: A03 attempting to write to A01 API routes
    allowed, reason = is_path_allowed_for_agent(
        "A03", "services/api/src/clara_api/api/router.py"
    )
    assert allowed is False
    assert reason == "PATH_OUT_OF_LANE"

    # Negative: A03 attempting to write to A02 DB migrations
    allowed, reason = is_path_allowed_for_agent(
        "A03", "services/api/alembic/versions/0070_new_table.py"
    )
    assert allowed is False
    assert reason == "PATH_OUT_OF_LANE"

    # Negative: A03 attempting to write to A06 Mobile code
    allowed, reason = is_path_allowed_for_agent(
        "A03", "apps/mobile/lib/main.dart"
    )
    assert allowed is False
    assert reason == "PATH_OUT_OF_LANE"

    # Negative: A01 attempting to write to A03 domain kernel
    allowed, reason = is_path_allowed_for_agent(
        "A01", "services/api/src/clara_api/glhs/commit_kernel.py"
    )
    assert allowed is False
    assert reason == "PATH_OUT_OF_LANE"

    # Negative: Cross-agent artifact write attempted
    allowed, reason = is_path_allowed_for_agent(
        "A03", "artifacts/PH02/A01/change_manifest.json"
    )
    assert allowed is False
    assert reason == "CROSS_AGENT_ARTIFACT_WRITE_PROHIBITED"

    # Negative: Directory traversal attempt
    allowed, reason = is_path_allowed_for_agent(
        "A03", "../etc/passwd"
    )
    assert allowed is False
    assert reason == "UNAUTHORIZED_PATH_TRAVERSAL"

    # Negative: Absolute path attempt
    allowed, reason = is_path_allowed_for_agent(
        "A03", "/services/api/src/clara_api/core/rbac.py"
    )
    assert allowed is False
    assert reason == "UNAUTHORIZED_PATH_TRAVERSAL"


def test_path_normalization_and_overlap_detector() -> None:
    """Validate path normalization corner cases and collision logic."""
    assert normalize_lane_path("services/api/src/clara_api/core") == "services/api/src/clara_api/core/"
    assert normalize_lane_path("services/api/src/clara_api/schemas.py") == "services/api/src/clara_api/schemas.py"
    assert normalize_lane_path("apps\\mobile\\") == "apps/mobile/"

    assert paths_have_overlap("apps/mobile/", "apps/mobile/lib/main.dart") is True
    assert paths_have_overlap("apps/web/app/", "apps/mobile/") is False

    lane_a = ["services/api/src/clara_api/core/"]
    lane_b = ["services/api/src/clara_api/core/rbac.py"]
    assert len(check_two_lanes_overlap(lane_a, lane_b)) == 1


def test_domain_import_boundaries_zero_ml_imports() -> None:
    """Domain modules must strictly avoid direct imports of clara_ml."""
    src_root = Path(__file__).resolve().parents[1] / "src"
    audit = audit_domain_import_boundaries(src_root=src_root)
    assert audit["scanned_domain_files"] > 20, "Expected at least 20 domain source files"
    assert (
        audit["boundary_preserved"] is True
    ), f"Forbidden clara_ml imports found in domain modules: {audit['forbidden_imports']}"
    assert audit["forbidden_imports_count"] == 0


def test_phase_tasks_json_audit_and_governance() -> None:
    """Audit PHASE_TASKS.json to verify PH02 disjointness and domain governance."""
    audit = audit_phase_tasks_json()
    if audit.get("status") == "FILE_NOT_FOUND":
        # In isolated CI environment where external spec package is omitted
        ph02_internal = audit["ph02_internal_audit"]
        assert ph02_internal["is_disjoint"] is True
        return

    assert audit["status"] == "AUDITED"
    assert audit["total_phases"] == 101
    assert audit["ph02_disjoint"] is True
    assert audit["ph02_overlap_count"] == 0
    assert audit["domain_ownership_intact"] is True
