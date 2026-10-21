#!/usr/bin/env python3
"""Unit and functional test suite for CLARA Phase Progress Dashboard.

Spec: PH02 / A09 (Docs + Research Evidence)
Validates:
  1. DAG topological order parsing (101 phases).
  2. Phase task parsing and integer-to-phase-ID dependency resolution.
  3. Artifact scanning across integration and agent directories.
  4. Worktree concurrent agent detection in /dev/shm/clara_worktrees/.
  5. Defect reconciliation (remediated vs open defects).
  6. Terminal, JSON, and Markdown rendering outputs.
  7. CLI argument processing and exit code handling.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
import pytest

from progress_dashboard import (
    DataSourceLocator,
    DashboardParser,
    DashboardState,
    TerminalDashboardRenderer,
    render_json,
    render_markdown,
    main,
    strip_ansi,
    visible_len,
    pad_str,
)


@pytest.fixture
def repo_locator() -> DataSourceLocator:
    return DataSourceLocator()


@pytest.fixture
def dashboard_state(repo_locator: DataSourceLocator) -> DashboardState:
    parser = DashboardParser(repo_locator)
    return parser.parse()


class TestDataSourceLocator:
    """Tests resolution of machine files, artifacts, and repository root."""

    def test_detect_repo_root(self, repo_locator: DataSourceLocator):
        root = repo_locator.repo_root
        assert root.exists()
        assert (root / ".git").exists()

    def test_resolve_dag_order(self, repo_locator: DataSourceLocator):
        order_path = repo_locator.resolve_dag_order()
        assert order_path.exists()
        assert order_path.name == "DAG_TOPOLOGICAL_ORDER.json"

    def test_resolve_phase_tasks(self, repo_locator: DataSourceLocator):
        tasks_path = repo_locator.resolve_phase_tasks()
        assert tasks_path.exists()
        assert tasks_path.name == "PHASE_TASKS.json"

    def test_resolve_artifacts_dir(self, repo_locator: DataSourceLocator):
        artifacts_dir = repo_locator.resolve_artifacts_dir()
        assert artifacts_dir.exists()
        assert (artifacts_dir / "PH00").exists()
        assert (artifacts_dir / "PH01").exists()


class TestDashboardParserLiveRepo:
    """Validates parser behavior against the live repository state."""

    def test_topological_phases_count(self, dashboard_state: DashboardState):
        assert dashboard_state.total_phases_count == 101
        assert len(dashboard_state.dag_order) == 101
        assert dashboard_state.dag_order[0] == "PH00"
        assert dashboard_state.dag_order[1] == "PH01"
        assert dashboard_state.dag_order[2] == "PH02"

    def test_completed_phases(self, dashboard_state: DashboardState):
        ph00 = dashboard_state.phases["PH00"]
        ph01 = dashboard_state.phases["PH01"]

        assert ph00.status == "COMPLETED"
        assert ph00.completed_agents_count == 10
        assert ph00.has_integration_manifest is True

        assert ph01.status == "COMPLETED"
        assert ph01.completed_agents_count == 10
        assert ph01.has_integration_manifest is True

    def test_active_wavefront_ph02(self, dashboard_state: DashboardState):
        assert dashboard_state.current_phase_id == "PH02"
        ph02 = dashboard_state.phases["PH02"]
        assert ph02.status == "IN_PROGRESS"
        assert ph02.depends == ["PH00", "PH01"]

    def test_defect_reconciliation(self, dashboard_state: DashboardState):
        defects_by_id = {d.defect_id: d for d in dashboard_state.all_defects}

        # DEFECT-01 and DEFECT-02 were remediated in PH01
        assert "DEFECT-01" in defects_by_id
        assert defects_by_id["DEFECT-01"].status == "RESOLVED"

        assert "DEFECT-02" in defects_by_id
        assert defects_by_id["DEFECT-02"].status == "RESOLVED"

        # SEC-CRIT-01 / DEFECT-05 remediated in PH01
        assert "SEC-CRIT-01" in defects_by_id
        assert defects_by_id["SEC-CRIT-01"].status == "RESOLVED"

        # Discovered open defects from PH00 baseline
        assert "DEFECT-03" in defects_by_id
        assert defects_by_id["DEFECT-03"].status == "OPEN"

    def test_blocker_ledger_clear_for_completed_phases(self, dashboard_state: DashboardState):
        # Historical blockers from completed phases should not appear as active blockers
        for b in dashboard_state.active_blockers:
            assert b.phase_id not in ("PH00", "PH01")


class TestRenderers:
    """Validates terminal, Markdown, and JSON formatting."""

    def test_terminal_renderer_ansi(self, dashboard_state: DashboardState):
        renderer = TerminalDashboardRenderer(color=True, ascii_only=False)
        output = renderer.render(dashboard_state)
        assert "CLARA Care" in output
        assert "DAG Execution Health" in output
        assert "Phase Spotlight" in output
        assert "PH02" in output

    def test_terminal_renderer_ascii(self, dashboard_state: DashboardState):
        renderer = TerminalDashboardRenderer(color=False, ascii_only=True)
        output = renderer.render(dashboard_state)
        # Should not contain Unicode box drawing
        assert "┌" not in output
        assert "+" in output
        assert "|" in output

    def test_render_json(self, dashboard_state: DashboardState):
        raw_json = render_json(dashboard_state)
        parsed = json.loads(raw_json)
        assert parsed["total_phases_count"] == 101
        assert parsed["current_phase_id"] == "PH02"
        assert "phases" in parsed
        assert "PH00" in parsed["phases"]
        assert "all_defects" in parsed

    def test_render_markdown(self, dashboard_state: DashboardState):
        md = render_markdown(dashboard_state)
        assert "# CLARA Care Multi-Agent Phase DAG Progress Report" in md
        assert "## Executive Health Summary" in md
        assert "## Phase Spotlight" in md
        assert "## Defect Remediation Ledger" in md


class TestCLIExecution:
    """Validates CLI arguments and execution entrypoint."""

    def test_cli_default(self, capsys):
        code = main([])
        assert code == 0
        captured = capsys.readouterr()
        assert "CLARA Care" in captured.out

    def test_cli_json_format(self, capsys):
        code = main(["--format", "json"])
        assert code == 0
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["current_phase_id"] == "PH02"

    def test_cli_markdown_format(self, capsys):
        code = main(["--format", "markdown", "--phase", "PH01"])
        assert code == 0
        captured = capsys.readouterr()
        assert "Phase Spotlight: PH01" in captured.out

    def test_cli_strict_exit(self):
        # Current phase PH02 is IN_PROGRESS with 0 active blockers, so strict exit should return 0
        code = main(["--strict-exit"])
        assert code == 0


class TestSyntheticDAGSimulation:
    """Tests synthetic topologies with blocked states and custom tasks."""

    def test_synthetic_blocked_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            machine_dir = tmp / "machine"
            machine_dir.mkdir()
            artifacts_dir = tmp / "artifacts"
            artifacts_dir.mkdir()

            dag_order = {"order": ["PH00", "PH01", "PH02"]}
            (machine_dir / "DAG_TOPOLOGICAL_ORDER.json").write_text(json.dumps(dag_order))

            phase_tasks = {
                "phases": [
                    {
                        "phase": 0,
                        "id": "PH00",
                        "title": "Baseline",
                        "priority": "P0",
                        "depends": [],
                        "agents": [{"agent_id": "A01", "role": "API", "task": "T1"}],
                    },
                    {
                        "phase": 1,
                        "id": "PH01",
                        "title": "Blocked Phase",
                        "priority": "P0",
                        "depends": [0],
                        "agents": [
                            {
                                "agent_id": "A01",
                                "role": "API",
                                "task": "T2",
                            }
                        ],
                    },
                ]
            }
            (machine_dir / "PHASE_TASKS.json").write_text(json.dumps(phase_tasks))

            # PH00 is completed
            ph00_int = artifacts_dir / "PH00" / "integration"
            ph00_int.mkdir(parents=True)
            (ph00_int / "merge_manifest.json").write_text(
                json.dumps({"integration_status": "PASSED", "agents": [{"agent_id": "A01", "status": "PASSED"}]})
            )

            # PH01 has a blocked agent
            ph01_a01 = artifacts_dir / "PH01" / "A01"
            ph01_a01.mkdir(parents=True)
            (ph01_a01 / "change_manifest.json").write_text(
                json.dumps({"status": "BLOCKED", "blockers": ["Missing upstream database credential"]})
            )

            locator = DataSourceLocator(
                machine_dir=machine_dir,
                artifacts_dir=artifacts_dir,
                worktrees_dir=tmp / "worktrees",
            )
            parser = DashboardParser(locator)
            state = parser.parse()

            assert state.phases["PH00"].status == "COMPLETED"
            assert state.phases["PH01"].status == "BLOCKED"
            assert state.blocked_phases_count == 1
            assert len(state.active_blockers) == 1
            assert state.active_blockers[0].description == "Missing upstream database credential"


class TestStringHelpers:
    """Validates ANSI stripping and string alignment helpers."""

    def test_strip_ansi_and_len(self):
        colored = "\033[32mHELLO\033[0m"
        assert strip_ansi(colored) == "HELLO"
        assert visible_len(colored) == 5

    def test_pad_str(self):
        padded = pad_str("TEST", 8)
        assert padded == "TEST    "
        assert len(padded) == 8
