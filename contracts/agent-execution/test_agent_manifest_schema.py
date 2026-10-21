"""Unit tests for Agent Execution Manifest JSON Schema and Pydantic validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
API_SRC = REPO_ROOT / "services" / "api" / "src"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))

from clara_api.schemas import (  # noqa: E402
    AgentManifestStatus,
    AgentTestRunItem,
    validate_agent_manifest_dict,
    validate_agent_manifest_json,
)

SCHEMA_PATH = REPO_ROOT / "contracts" / "agent-execution" / "agent-manifest.schema.json"
VALID_SHA = "879dc5dcfcaae91b3626e28062043d934294478b"


def load_json_schema() -> dict[str, Any]:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return cast(dict[str, Any], json.load(f))


# ============================================================================
# 1. JSON Schema Contract Structure Invariants
# ============================================================================


def test_schema_file_exists_and_is_valid_json() -> None:
    assert SCHEMA_PATH.exists(), f"Schema file not found at {SCHEMA_PATH}"
    schema = load_json_schema()
    assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert schema.get("type") == "object"


def test_schema_required_fields_contain_exact_mandated_invariants() -> None:
    schema = load_json_schema()
    required = set(schema.get("required", []))
    expected = {
        "phase_id",
        "agent_id",
        "base_sha",
        "branch",
        "files_changed",
        "tests_run",
        "status",
        "rollback_steps",
    }
    assert expected.issubset(required), f"Missing required fields: {expected - required}"


def test_schema_agent_id_enum_has_exact_10_agents() -> None:
    schema = load_json_schema()
    agent_enum = schema["properties"]["agent_id"]["enum"]
    expected_agents = [f"A{i:02d}" for i in range(1, 11)]
    assert agent_enum == expected_agents, f"Agent enum mismatch: {agent_enum}"


def test_schema_status_enum_matches_specification() -> None:
    schema = load_json_schema()
    status_enum = set(schema["properties"]["status"]["enum"])
    assert status_enum == {"PASSED", "FAILED", "BLOCKED"}


def test_schema_base_sha_pattern() -> None:
    schema = load_json_schema()
    pattern = schema["properties"]["base_sha"]["pattern"]
    assert "40" in pattern, "base_sha pattern must enforce 40 hex characters"


# ============================================================================
# 2. Pydantic Model Validation: Valid Manifests (Allow)
# ============================================================================


@pytest.mark.parametrize("agent_idx", range(1, 11))
def test_all_10_subagents_allowed(agent_idx: int) -> None:
    agent_id = f"A{agent_idx:02d}"
    data = {
        "phase_id": "PH02",
        "agent_id": agent_id,
        "base_sha": VALID_SHA,
        "branch": f"phase/ph02-{agent_id.lower()}",
        "files_changed": ["contracts/agent-execution/agent-manifest.schema.json"],
        "tests_run": ["pytest contracts/agent-execution/test_agent_manifest_schema.py"],
        "status": "PASSED",
        "rollback_steps": ["git checkout phase/ph02-a01~1"],
    }
    manifest = validate_agent_manifest_dict(data)
    assert manifest.agent_id == agent_id
    assert manifest.status == "PASSED"
    assert manifest.base_sha == VALID_SHA
    assert manifest.rollback_steps == ["git checkout phase/ph02-a01~1"]


@pytest.mark.parametrize("status", ["PASSED", "FAILED", "BLOCKED"])
def test_all_statuses_allowed(status: AgentManifestStatus) -> None:
    data = {
        "phase_id": "PH02",
        "agent_id": "A01",
        "base_sha": VALID_SHA,
        "branch": "phase/ph02-a01",
        "files_changed": ["artifacts/PH02/A01/change_manifest.json"],
        "tests_run": ["pytest contracts/agent-execution/test_agent_manifest_schema.py"],
        "status": status,
        "rollback_steps": ["git reset --hard HEAD~1"],
        "blockers": ["Upstream dependency not ready"] if status == "BLOCKED" else [],
    }
    manifest = validate_agent_manifest_dict(data)
    assert manifest.status == status


def test_structured_test_run_items_allowed() -> None:
    data = {
        "phase_id": "PH02",
        "agent_id": "A01",
        "base_sha": VALID_SHA,
        "branch": "phase/ph02-a01",
        "files_changed": ["services/api/src/clara_api/schemas.py"],
        "tests_run": [
            {
                "command": "pytest contracts/agent-execution/test_agent_manifest_schema.py",
                "exit_code": 0,
                "status": "PASSED",
                "duration_seconds": 1.25,
            },
            "ruff check services/api/src/clara_api/schemas.py",
        ],
        "status": "PASSED",
        "rollback_steps": ["git checkout HEAD~1"],
    }
    manifest = validate_agent_manifest_dict(data)
    assert len(manifest.tests_run) == 2
    item1 = manifest.tests_run[0]
    assert isinstance(item1, AgentTestRunItem)
    assert item1.command == "pytest contracts/agent-execution/test_agent_manifest_schema.py"
    assert item1.exit_code == 0
    assert item1.status == "PASSED"
    assert manifest.tests_run[1] == "ruff check services/api/src/clara_api/schemas.py"


def test_frozen_head_sha_alias_accepted() -> None:
    data = {
        "phase_id": "PH01",
        "agent_id": "A01",
        "frozen_head_sha": VALID_SHA,
        "branch": "phase/ph01-a01",
        "files_changed": ["artifacts/PH01/A01/change_manifest.json"],
        "tests_run": ["pytest tests/test_route_inventory_public_boundaries.py"],
        "status": "PASSED",
        "rollback_steps": ["git checkout HEAD~1"],
    }
    manifest = validate_agent_manifest_dict(data)
    assert manifest.base_sha == VALID_SHA


def test_files_changed_aggregation_from_created_and_modified() -> None:
    data = {
        "phase_id": "PH01",
        "agent_id": "A01",
        "base_sha": VALID_SHA,
        "branch": "phase/ph01-a01",
        "files_created": ["artifacts/PH01/A01/change_manifest.json"],
        "files_modified": ["services/api/src/clara_api/core/route_inventory.py"],
        "tests_run": ["pytest tests/test_route_inventory_public_boundaries.py"],
        "status": "PASSED",
        "rollback_steps": ["git checkout HEAD~1"],
    }
    manifest = validate_agent_manifest_dict(data)
    assert set(manifest.files_changed) == {
        "artifacts/PH01/A01/change_manifest.json",
        "services/api/src/clara_api/core/route_inventory.py",
    }


def test_rollback_steps_multiline_string_normalization() -> None:
    data = {
        "phase_id": "PH02",
        "agent_id": "A01",
        "base_sha": VALID_SHA,
        "branch": "phase/ph02-a01",
        "files_changed": ["contracts/agent-execution/agent-manifest.schema.json"],
        "tests_run": ["pytest contracts/agent-execution/test_agent_manifest_schema.py"],
        "status": "PASSED",
        "rollback_steps": """
        - git checkout 879dc5dcfcaae91b3626e28062043d934294478b
        - rm contracts/agent-execution/agent-manifest.schema.json
        - git status
        """,
    }
    manifest = validate_agent_manifest_dict(data)
    assert len(manifest.rollback_steps) == 3
    assert manifest.rollback_steps[0] == "git checkout 879dc5dcfcaae91b3626e28062043d934294478b"
    assert manifest.rollback_steps[1] == "rm contracts/agent-execution/agent-manifest.schema.json"
    assert manifest.rollback_steps[2] == "git status"


def test_json_string_validation() -> None:
    data = {
        "phase_id": "PH02",
        "agent_id": "A01",
        "base_sha": VALID_SHA,
        "branch": "phase/ph02-a01",
        "files_changed": ["contracts/agent-execution/agent-manifest.schema.json"],
        "tests_run": ["pytest contracts/agent-execution/test_agent_manifest_schema.py"],
        "status": "PASSED",
        "rollback_steps": ["git revert HEAD"],
    }
    json_str = json.dumps(data)
    manifest = validate_agent_manifest_json(json_str)
    assert manifest.phase_id == "PH02"
    assert manifest.agent_id == "A01"


# ============================================================================
# 3. Pydantic Model Validation: Invalid Manifests (Deny)
# ============================================================================


@pytest.mark.parametrize("invalid_agent", ["A00", "A11", "A99", "B01", "A1", "subagent-1"])
def test_invalid_agent_id_denied(invalid_agent: str) -> None:
    data = {
        "phase_id": "PH02",
        "agent_id": invalid_agent,
        "base_sha": VALID_SHA,
        "branch": "phase/ph02-a01",
        "files_changed": [],
        "tests_run": [],
        "status": "PASSED",
        "rollback_steps": ["git checkout HEAD~1"],
    }
    with pytest.raises(ValidationError) as exc_info:
        validate_agent_manifest_dict(data)
    assert "agent_id" in str(exc_info.value)


@pytest.mark.parametrize("invalid_phase", ["PH2", "PH002", "P02", "phase02", "ph02", ""])
def test_invalid_phase_id_denied(invalid_phase: str) -> None:
    data = {
        "phase_id": invalid_phase,
        "agent_id": "A01",
        "base_sha": VALID_SHA,
        "branch": "phase/ph02-a01",
        "files_changed": [],
        "tests_run": [],
        "status": "PASSED",
        "rollback_steps": ["git checkout HEAD~1"],
    }
    with pytest.raises(ValidationError) as exc_info:
        validate_agent_manifest_dict(data)
    assert "phase_id" in str(exc_info.value)


@pytest.mark.parametrize(
    "invalid_sha",
    [
        "879dc5d",  # too short (7 chars)
        "879dc5dcfcaae91b3626e28062043d934294478",  # 39 chars
        "879dc5dcfcaae91b3626e28062043d934294478bb",  # 41 chars
        "879dc5dcfcaae91b3626e28062043d934294478z",  # invalid hex char 'z'
        "",
    ],
)
def test_invalid_base_sha_denied(invalid_sha: str) -> None:
    data = {
        "phase_id": "PH02",
        "agent_id": "A01",
        "base_sha": invalid_sha,
        "branch": "phase/ph02-a01",
        "files_changed": [],
        "tests_run": [],
        "status": "PASSED",
        "rollback_steps": ["git checkout HEAD~1"],
    }
    with pytest.raises(ValidationError) as exc_info:
        validate_agent_manifest_dict(data)
    assert "base_sha" in str(exc_info.value)


@pytest.mark.parametrize("invalid_status", ["COMPLETED", "IN_PROGRESS", "RUNNING", "PASS", "FAIL", ""])
def test_invalid_status_denied(invalid_status: str) -> None:
    data = {
        "phase_id": "PH02",
        "agent_id": "A01",
        "base_sha": VALID_SHA,
        "branch": "phase/ph02-a01",
        "files_changed": [],
        "tests_run": [],
        "status": invalid_status,
        "rollback_steps": ["git checkout HEAD~1"],
    }
    with pytest.raises(ValidationError) as exc_info:
        validate_agent_manifest_dict(data)
    assert "status" in str(exc_info.value)


@pytest.mark.parametrize("empty_steps", [[], "", "   \n\n  "])
def test_empty_rollback_steps_denied(empty_steps: list[str] | str) -> None:
    data = {
        "phase_id": "PH02",
        "agent_id": "A01",
        "base_sha": VALID_SHA,
        "branch": "phase/ph02-a01",
        "files_changed": [],
        "tests_run": [],
        "status": "PASSED",
        "rollback_steps": empty_steps,
    }
    with pytest.raises(ValidationError) as exc_info:
        validate_agent_manifest_dict(data)
    assert "rollback_steps" in str(exc_info.value)


def test_missing_required_fields_denied() -> None:
    base_data = {
        "phase_id": "PH02",
        "agent_id": "A01",
        "base_sha": VALID_SHA,
        "branch": "phase/ph02-a01",
        "status": "PASSED",
        "rollback_steps": ["git checkout HEAD~1"],
    }
    for field in ("phase_id", "agent_id", "base_sha", "branch", "status", "rollback_steps"):
        corrupted = dict(base_data)
        del corrupted[field]
        with pytest.raises(ValidationError) as exc_info:
            validate_agent_manifest_dict(corrupted)
        assert field in str(exc_info.value)
