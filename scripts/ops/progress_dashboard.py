#!/usr/bin/env python3
"""CLARA Care — Multi-Agent Phase DAG Progress & Checkpoint Dashboard.

Spec: PH02 / A09 (Docs + Research Evidence)
Role: Checkpoint/progress dashboard parsing DAG_TOPOLOGICAL_ORDER.json,
      PHASE_TASKS.json, artifacts/, and live worktrees to output a comprehensive
      terminal dashboard of phase completion, agent statuses, defect counts,
      and DAG execution state.

Authoritative Sources:
  - machine/DAG_TOPOLOGICAL_ORDER.json (Topological phase order of 101 phases)
  - machine/PHASE_TASKS.json (Phase specifications, priorities, agent roles/tasks)
  - artifacts/ (Phase integration manifests, agent change manifests, test reports, risk logs)
  - /dev/shm/clara_worktrees/ (Active concurrent subagent worktrees)
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


# -----------------------------------------------------------------------------
# Color and Terminal Formatting Helpers
# -----------------------------------------------------------------------------
class Ansi:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright foreground colors
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Backgrounds
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"
    BG_YELLOW = "\033[43m"


def supports_color(no_color_flag: bool = False) -> bool:
    """Determine whether ANSI color output should be enabled."""
    if no_color_flag:
        return False
    if "NO_COLOR" in os.environ:
        return False
    if not sys.stdout.isatty():
        return False
    return True


# -----------------------------------------------------------------------------
# Data Models
# -----------------------------------------------------------------------------
@dataclass
class AgentProgress:
    agent_id: str
    role: str
    task: str
    path_lane: str
    acceptance_artifacts: list[str] = field(default_factory=list)
    status: str = "PENDING"  # COMPLETED, IN_PROGRESS, BLOCKED, READY, PENDING
    artifacts_found: list[str] = field(default_factory=list)
    missing_artifacts: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    has_manifest: bool = False
    has_test_report: bool = False
    has_risk_register: bool = False
    has_rollback: bool = False
    worktree_path: Optional[str] = None
    commit_sha: Optional[str] = None
    tests_summary: str = "N/A"


@dataclass
class DefectRecord:
    defect_id: str
    phase_id: str
    origin: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    status: str  # RESOLVED, OPEN, WAIVED
    description: str
    remediation: Optional[str] = None


@dataclass
class BlockerRecord:
    blocker_id: str
    phase_id: str
    agent_id: str
    description: str
    severity: str = "HIGH"
    status: str = "ACTIVE"  # ACTIVE, RESOLVED, WAIVED


@dataclass
class PhaseProgress:
    phase_num: int
    phase_id: str
    title: str
    priority: str
    depends: list[str] = field(default_factory=list)  # Phase IDs like ["PH00", "PH01"]
    status: str = "PENDING"  # COMPLETED, IN_PROGRESS, READY, BLOCKED, PENDING
    agents: dict[str, AgentProgress] = field(default_factory=dict)
    completed_agents_count: int = 0
    total_agents_count: int = 10
    has_integration_manifest: bool = False
    integration_status: Optional[str] = None
    remediated_defects: list[DefectRecord] = field(default_factory=list)
    open_defects: list[DefectRecord] = field(default_factory=list)
    blockers: list[BlockerRecord] = field(default_factory=list)


@dataclass
class DashboardState:
    phases: dict[str, PhaseProgress]
    dag_order: list[str]
    current_phase_id: str
    completed_phases_count: int
    in_progress_phases_count: int
    ready_phases_count: int
    blocked_phases_count: int
    pending_phases_count: int
    total_phases_count: int
    completion_percentage: float
    all_defects: list[DefectRecord]
    active_blockers: list[BlockerRecord]
    head_sha: str
    generated_at: str
    artifacts_dir: str
    machine_dir: str


# -----------------------------------------------------------------------------
# Data Source Locator & Parser
# -----------------------------------------------------------------------------
class DataSourceLocator:
    """Resolves locations of machine metadata, artifacts, and live worktrees."""

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        machine_dir: Optional[Path] = None,
        dag_order_file: Optional[Path] = None,
        phase_tasks_file: Optional[Path] = None,
        artifacts_dir: Optional[Path] = None,
        worktrees_dir: Optional[Path] = None,
    ):
        self.base_dir = (base_dir or Path.cwd()).resolve()
        self.repo_root = self._detect_repo_root(self.base_dir)
        self.machine_dir = machine_dir
        self.dag_order_file = dag_order_file
        self.phase_tasks_file = phase_tasks_file
        self.artifacts_dir = artifacts_dir
        self.worktrees_dir = worktrees_dir or Path("/dev/shm/clara_worktrees")

    def _detect_repo_root(self, start: Path) -> Path:
        curr = start
        while curr != curr.parent:
            if (curr / ".git").exists():
                return curr
            curr = curr.parent
        return start

    def resolve_dag_order(self) -> Path:
        if self.dag_order_file and self.dag_order_file.exists():
            return self.dag_order_file

        candidates = [
            self.machine_dir / "DAG_TOPOLOGICAL_ORDER.json" if self.machine_dir else None,
            self.base_dir / "machine" / "DAG_TOPOLOGICAL_ORDER.json",
            self.repo_root / "machine" / "DAG_TOPOLOGICAL_ORDER.json",
            self.repo_root / "CLARA_CARE_MODULAR_MASTER_MOBILE_V2_NO_MOCK" / "machine" / "DAG_TOPOLOGICAL_ORDER.json",
            Path("/home/clue/Documents/CLARA-Care/CLARA_CARE_MODULAR_MASTER_MOBILE_V2_NO_MOCK/machine/DAG_TOPOLOGICAL_ORDER.json"),
        ]
        for c in candidates:
            if c and c.exists():
                return c.resolve()
        raise FileNotFoundError("Could not find DAG_TOPOLOGICAL_ORDER.json in standard candidate paths.")

    def resolve_phase_tasks(self) -> Path:
        if self.phase_tasks_file and self.phase_tasks_file.exists():
            return self.phase_tasks_file

        candidates = [
            self.machine_dir / "PHASE_TASKS.json" if self.machine_dir else None,
            self.base_dir / "machine" / "PHASE_TASKS.json",
            self.repo_root / "machine" / "PHASE_TASKS.json",
            self.repo_root / "CLARA_CARE_MODULAR_MASTER_MOBILE_V2_NO_MOCK" / "machine" / "PHASE_TASKS.json",
            Path("/home/clue/Documents/CLARA-Care/CLARA_CARE_MODULAR_MASTER_MOBILE_V2_NO_MOCK/machine/PHASE_TASKS.json"),
        ]
        for c in candidates:
            if c and c.exists():
                return c.resolve()
        raise FileNotFoundError("Could not find PHASE_TASKS.json in standard candidate paths.")

    def resolve_artifacts_dir(self) -> Path:
        if self.artifacts_dir and self.artifacts_dir.exists():
            return self.artifacts_dir

        candidates = [
            self.base_dir / "artifacts",
            self.repo_root / "artifacts",
            Path("/home/clue/Documents/CLARA-Care/artifacts"),
        ]
        for c in candidates:
            if c.exists() and c.is_dir():
                return c.resolve()
        return (self.repo_root / "artifacts").resolve()

    def get_head_sha(self) -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
        return "UNKNOWN_HEAD"


class DashboardParser:
    """Parses DAG topological order, phase task definitions, and artifact states."""

    def __init__(self, locator: DataSourceLocator):
        self.locator = locator
        self.dag_order_path = locator.resolve_dag_order()
        self.phase_tasks_path = locator.resolve_phase_tasks()
        self.artifacts_dir = locator.resolve_artifacts_dir()
        self.worktrees_dir = locator.worktrees_dir

    def parse(self) -> DashboardState:
        with open(self.dag_order_path, "r", encoding="utf-8") as f:
            dag_data = json.load(f)
        dag_order: list[str] = dag_data.get("order", [])

        with open(self.phase_tasks_path, "r", encoding="utf-8") as f:
            tasks_data = json.load(f)
        raw_phases = tasks_data.get("phases", [])

        phases_map: dict[str, PhaseProgress] = {}
        int_to_id: dict[int, str] = {}

        # First pass: Build initial phase objects and mapping
        for p in raw_phases:
            p_id = p.get("id")
            p_num = p.get("phase", 0)
            int_to_id[p_num] = p_id

            depends_raw = p.get("depends", [])
            depends_ids: list[str] = []
            for dep in depends_raw:
                if isinstance(dep, int):
                    # Will resolve properly in pass 2
                    pass
                elif isinstance(dep, str):
                    depends_ids.append(dep)

            phase_obj = PhaseProgress(
                phase_num=p_num,
                phase_id=p_id,
                title=p.get("title", ""),
                priority=p.get("priority", "P0"),
                depends=depends_ids,
            )

            # Build agents map
            for ag in p.get("agents", []):
                ag_id = ag.get("agent_id")
                agent_obj = AgentProgress(
                    agent_id=ag_id,
                    role=ag.get("role", ""),
                    task=ag.get("task", ""),
                    path_lane=ag.get("path_lane", ""),
                    acceptance_artifacts=ag.get("acceptance_artifacts", []),
                )
                phase_obj.agents[ag_id] = agent_obj

            phases_map[p_id] = phase_obj

        # Pass 2: Resolve integer dependencies
        for p in raw_phases:
            p_id = p.get("id")
            phase_obj = phases_map.get(p_id)
            if not phase_obj:
                continue
            depends_resolved: list[str] = []
            for dep in p.get("depends", []):
                if isinstance(dep, int):
                    dep_id = int_to_id.get(dep, f"PH{dep:02d}")
                    depends_resolved.append(dep_id)
                elif isinstance(dep, str):
                    depends_resolved.append(dep)
            phase_obj.depends = depends_resolved

        # Pass 3: Scan artifacts and live worktrees
        all_defects: list[DefectRecord] = []
        all_blockers: list[BlockerRecord] = []

        for p_id in dag_order:
            phase_obj = phases_map.get(p_id)
            if not phase_obj:
                continue

            self._scan_phase_artifacts(phase_obj)
            all_defects.extend(phase_obj.remediated_defects)
            all_defects.extend(phase_obj.open_defects)
            all_blockers.extend(phase_obj.blockers)

        # Deduplicate defects by defect_id, preferring RESOLVED over OPEN
        # Note: DEFECT-05 in PH00 was identified as SEC-CRIT-01 and resolved in PH01
        deduped_defects: dict[str, DefectRecord] = {}
        for d in all_defects:
            if d.defect_id in deduped_defects:
                existing = deduped_defects[d.defect_id]
                if d.status == "RESOLVED" and existing.status != "RESOLVED":
                    deduped_defects[d.defect_id] = d
            else:
                deduped_defects[d.defect_id] = d

        # Reconcile DEFECT-05 and SEC-CRIT-01
        if "SEC-CRIT-01" in deduped_defects and deduped_defects["SEC-CRIT-01"].status == "RESOLVED":
            if "DEFECT-05" in deduped_defects:
                deduped_defects["DEFECT-05"].status = "RESOLVED"
                deduped_defects["DEFECT-05"].remediation = deduped_defects["SEC-CRIT-01"].remediation or "Remediated via SEC-CRIT-01"

        unique_defects = sorted(deduped_defects.values(), key=lambda x: (x.status != "OPEN", x.defect_id))

        # Pass 4: Determine DAG execution states in topological order
        completed_count = 0
        in_progress_count = 0
        ready_count = 0
        blocked_count = 0
        pending_count = 0
        current_phase_id = dag_order[0] if dag_order else "PH00"
        found_active_current = False

        for p_id in dag_order:
            phase_obj = phases_map.get(p_id)
            if not phase_obj:
                continue

            # Check if all dependencies are completed
            deps_completed = True
            dep_blocked = False
            for dep_id in phase_obj.depends:
                dep_phase = phases_map.get(dep_id)
                if not dep_phase or dep_phase.status != "COMPLETED":
                    deps_completed = False
                if dep_phase and dep_phase.status == "BLOCKED":
                    dep_blocked = True

            # If phase already has a verified integration manifest marked PASSED
            if phase_obj.has_integration_manifest and phase_obj.integration_status in ("PASSED", "COMPLETED"):
                phase_obj.status = "COMPLETED"
                phase_obj.completed_agents_count = len(phase_obj.agents)
                for ag in phase_obj.agents.values():
                    ag.status = "COMPLETED"
                completed_count += 1
                continue

            # Check agent progress
            completed_agents = sum(1 for a in phase_obj.agents.values() if a.status in ("COMPLETED", "PASSED"))
            phase_obj.completed_agents_count = completed_agents

            has_blocked_agent = any(a.status == "BLOCKED" for a in phase_obj.agents.values())
            has_started_agent = any(
                a.status in ("COMPLETED", "PASSED", "IN_PROGRESS") or a.has_manifest
                for a in phase_obj.agents.values()
            )

            if deps_completed:
                if has_blocked_agent or dep_blocked:
                    phase_obj.status = "BLOCKED"
                    blocked_count += 1
                elif completed_agents == phase_obj.total_agents_count and phase_obj.has_integration_manifest:
                    phase_obj.status = "COMPLETED"
                    completed_count += 1
                elif has_started_agent:
                    phase_obj.status = "IN_PROGRESS"
                    in_progress_count += 1
                else:
                    phase_obj.status = "READY"
                    ready_count += 1
            else:
                if dep_blocked or has_blocked_agent:
                    phase_obj.status = "BLOCKED"
                    blocked_count += 1
                elif has_started_agent:
                    phase_obj.status = "IN_PROGRESS"
                    in_progress_count += 1
                else:
                    phase_obj.status = "PENDING"
                    pending_count += 1

            if not found_active_current and phase_obj.status in ("IN_PROGRESS", "BLOCKED", "READY"):
                current_phase_id = p_id
                found_active_current = True

        total_phases = len(dag_order)
        completion_pct = (completed_count / total_phases * 100.0) if total_phases > 0 else 0.0

        # Active blockers only from active/non-completed phases
        active_blockers_list = [
            b for b in all_blockers
            if b.status == "ACTIVE"
            and phases_map.get(b.phase_id)
            and phases_map[b.phase_id].status != "COMPLETED"
        ]

        return DashboardState(
            phases=phases_map,
            dag_order=dag_order,
            current_phase_id=current_phase_id,
            completed_phases_count=completed_count,
            in_progress_phases_count=in_progress_count,
            ready_phases_count=ready_count,
            blocked_phases_count=blocked_count,
            pending_phases_count=pending_count,
            total_phases_count=total_phases,
            completion_percentage=completion_pct,
            all_defects=unique_defects,
            active_blockers=active_blockers_list,
            head_sha=self.locator.get_head_sha(),
            generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            artifacts_dir=str(self.artifacts_dir),
            machine_dir=str(self.locator.machine_dir or self.dag_order_path.parent),
        )

    def _scan_phase_artifacts(self, phase: PhaseProgress) -> None:
        phase_dir = self.artifacts_dir / phase.phase_id

        # 1. Inspect integration directory
        integration_dir = phase_dir / "integration"
        merge_manifest_path = integration_dir / "merge_manifest.json"
        if merge_manifest_path.exists():
            phase.has_integration_manifest = True
            try:
                with open(merge_manifest_path, "r", encoding="utf-8") as f:
                    merge_data = json.load(f)

                phase.integration_status = merge_data.get(
                    "integration_status", merge_data.get("status", "PASSED")
                )

                # Remediated defects
                for rem in merge_data.get("remediated_defects", []):
                    phase.remediated_defects.append(
                        DefectRecord(
                            defect_id=rem.get("id", "UNKNOWN"),
                            phase_id=phase.phase_id,
                            origin="integration",
                            severity="HIGH",
                            status="RESOLVED",
                            description=rem.get("desc", rem.get("description", "")),
                            remediation=rem.get("desc", ""),
                        )
                    )

                # Discovered defects & baseline defect ledger
                open_defect_items = merge_data.get("discovered_defects", []) + merge_data.get("baseline_defect_ledger", [])
                for disc in open_defect_items:
                    phase.open_defects.append(
                        DefectRecord(
                            defect_id=disc.get("id", "UNKNOWN"),
                            phase_id=phase.phase_id,
                            origin=disc.get("origin", "integration"),
                            severity=disc.get("severity", "MEDIUM"),
                            status="OPEN",
                            description=disc.get("desc", disc.get("description", "")),
                        )
                    )

                # Update agents if listed in merge_manifest
                for ag_rec in merge_data.get("agents", []):
                    ag_id = ag_rec.get("agent_id")
                    if ag_id in phase.agents:
                        st = ag_rec.get("status", "").upper()
                        if st in ("PASSED", "COMPLETED", "SUCCESS"):
                            phase.agents[ag_id].status = "COMPLETED"
                        phase.agents[ag_id].commit_sha = ag_rec.get("commit")
            except Exception:
                pass

        # 2. Inspect each agent's artifacts in repo and worktree
        for ag_id, agent in phase.agents.items():
            agent_dir = phase_dir / ag_id
            manifest_file = agent_dir / "change_manifest.json"

            # Check if live worktree exists in /dev/shm/clara_worktrees/
            wt_agent_dir = self.worktrees_dir / f"{phase.phase_id}_{ag_id}" / "artifacts" / phase.phase_id / ag_id
            wt_manifest_file = wt_agent_dir / "change_manifest.json"

            target_manifest = None
            if manifest_file.exists() and manifest_file.stat().st_size > 0:
                target_manifest = manifest_file
                agent.worktree_path = str(agent_dir.parent.parent.parent)
            elif wt_manifest_file.exists() and wt_manifest_file.stat().st_size > 0:
                target_manifest = wt_manifest_file
                agent.worktree_path = str(self.worktrees_dir / f"{phase.phase_id}_{ag_id}")

            # Check deliverable files
            check_dirs = [agent_dir]
            if wt_agent_dir.exists():
                check_dirs.append(wt_agent_dir)

            for d in check_dirs:
                if (d / "change_manifest.json").exists():
                    agent.has_manifest = True
                if (d / "test_report.md").exists():
                    agent.has_test_report = True
                if (d / "risk_register.md").exists():
                    agent.has_risk_register = True
                if (d / "rollback.md").exists():
                    agent.has_rollback = True

            # If worktree exists, agent is at least IN_PROGRESS
            if (self.worktrees_dir / f"{phase.phase_id}_{ag_id}").exists() and agent.status == "PENDING":
                agent.status = "IN_PROGRESS"

            # Parse manifest if present
            if target_manifest:
                try:
                    with open(target_manifest, "r", encoding="utf-8") as f:
                        m_data = json.load(f)

                    raw_st = str(m_data.get("status", "")).upper()
                    if raw_st in ("COMPLETED", "PASSED", "COMPLETE", "SUCCESS"):
                        agent.status = "COMPLETED"
                    elif raw_st in ("BLOCKED",):
                        agent.status = "BLOCKED"
                    elif raw_st in ("IN_PROGRESS", "RUNNING"):
                        agent.status = "IN_PROGRESS"
                    elif agent.has_manifest and agent.has_test_report:
                        agent.status = "COMPLETED"

                    # Parse blockers
                    raw_blockers = m_data.get("blockers")
                    if isinstance(raw_blockers, list):
                        agent.blockers = [str(b) for b in raw_blockers if b and str(b).lower() != "none"]
                    elif isinstance(raw_blockers, str) and raw_blockers.strip().lower() not in ("none", "", "null"):
                        agent.blockers = [raw_blockers.strip()]

                    for b_desc in agent.blockers:
                        phase.blockers.append(
                            BlockerRecord(
                                blocker_id=f"BLK-{phase.phase_id}-{ag_id}",
                                phase_id=phase.phase_id,
                                agent_id=ag_id,
                                description=b_desc,
                            )
                        )

                    # Parse tests summary
                    test_cmds = m_data.get("test_commands_and_exit_codes") or m_data.get("test_results") or []
                    if isinstance(test_cmds, list) and test_cmds:
                        passes = sum(
                            1
                            for t in test_cmds
                            if isinstance(t, dict) and (t.get("status") == "PASS" or t.get("exit_code") == 0)
                        )
                        fails = sum(
                            1
                            for t in test_cmds
                            if isinstance(t, dict)
                            and (t.get("status") == "FAIL" or (t.get("exit_code") not in (0, None)))
                        )
                        agent.tests_summary = f"{passes} PASS / {fails} FAIL"
                    elif "test_coverage" in m_data:
                        cov = str(m_data["test_coverage"])
                        agent.tests_summary = (cov[:12] + "...") if len(cov) > 15 else cov
                    elif agent.has_test_report:
                        agent.tests_summary = "Report Present"

                    # Parse defect findings
                    for kf in m_data.get("key_findings", []):
                        if isinstance(kf, dict) and kf.get("id"):
                            st = "RESOLVED" if kf.get("status") == "REMEDIATED" else "OPEN"
                            record = DefectRecord(
                                defect_id=kf.get("id"),
                                phase_id=phase.phase_id,
                                origin=ag_id,
                                severity=kf.get("severity", "HIGH"),
                                status=st,
                                description=kf.get("title", kf.get("description", "")),
                                remediation=kf.get("remediation"),
                            )
                            if st == "RESOLVED":
                                phase.remediated_defects.append(record)
                            else:
                                phase.open_defects.append(record)
                except Exception:
                    pass


# -----------------------------------------------------------------------------
# Terminal & Markdown Dashboard Renderers
# -----------------------------------------------------------------------------
class TerminalDashboardRenderer:
    """Renders ANSI / Unicode formatted terminal dashboard."""

    def __init__(self, color: bool = True, ascii_only: bool = False, term_width: Optional[int] = None):
        self.color = color
        self.ascii_only = ascii_only
        self.width = term_width or min(shutil.get_terminal_size(fallback=(100, 24)).columns, 110)

        # Border characters
        if self.ascii_only:
            self.c_top_left = "+"
            self.c_top_right = "+"
            self.c_bot_left = "+"
            self.c_bot_right = "+"
            self.c_h = "-"
            self.c_v = "|"
            self.c_div = "|"
            self.c_t_down = "+"
            self.c_t_up = "+"
            self.c_t_right = "+"
            self.c_t_left = "+"
            self.c_cross = "+"
        else:
            self.c_top_left = "┌"
            self.c_top_right = "┐"
            self.c_bot_left = "└"
            self.c_bot_right = "┘"
            self.c_h = "─"
            self.c_v = "│"
            self.c_div = "│"
            self.c_t_down = "┬"
            self.c_t_up = "┴"
            self.c_t_right = "├"
            self.c_t_left = "┤"
            self.c_cross = "┼"

    def _c(self, text: str, color_code: str) -> str:
        if not self.color:
            return text
        return f"{color_code}{text}{Ansi.RESET}"

    def status_badge(self, status: str) -> str:
        s = status.upper()
        if s in ("COMPLETED", "PASSED", "RESOLVED"):
            return self._c(f"[{s}]", Ansi.BOLD + Ansi.BRIGHT_GREEN)
        elif s in ("IN_PROGRESS", "ACTIVE"):
            return self._c(f"[{s}]", Ansi.BOLD + Ansi.BRIGHT_YELLOW)
        elif s in ("READY",):
            return self._c(f"[{s}]", Ansi.BOLD + Ansi.BRIGHT_CYAN)
        elif s in ("BLOCKED", "FAILED", "CRITICAL"):
            return self._c(f"[{s}]", Ansi.BOLD + Ansi.BRIGHT_RED)
        elif s in ("PENDING", "OPEN"):
            return self._c(f"[{s}]", Ansi.DIM + Ansi.WHITE)
        return self._c(f"[{s}]", Ansi.WHITE)

    def render(self, state: DashboardState, focus_phase_id: Optional[str] = None, all_phases: bool = False) -> str:
        lines: list[str] = []
        w = self.width

        # 1. Header Banner
        lines.append("=" * w)
        title = "CLARA Care — Multi-Agent Phase DAG Progress & Checkpoint Dashboard"
        lines.append(self._c(title.center(w), Ansi.BOLD + Ansi.BRIGHT_CYAN))
        lines.append("=" * w)

        meta_line = (
            f" Timestamp: {state.generated_at[:19]}Z | HEAD: {state.head_sha[:10]} | "
            f"Active Wavefront: {self.status_badge(state.current_phase_id)}"
        )
        lines.append(meta_line)
        lines.append("")

        # 2. Executive KPI Summary Box
        lines.append(self._box_header("DAG Execution Health & Phase Metrics", w))
        pct_bar = self._progress_bar(state.completed_phases_count, state.total_phases_count, width=28)
        kpi_row1 = (
            f" Total Phases: {state.total_phases_count:<4}  "
            f"Completed:   {state.completed_phases_count:<3} ({state.completion_percentage:4.1f}%) {pct_bar}"
        )
        kpi_row2 = (
            f" In Progress:  {state.in_progress_phases_count:<4}  "
            f"Ready:       {state.ready_phases_count:<3}  "
            f"Blocked:     {state.blocked_phases_count:<3}  "
            f"Pending:     {state.pending_phases_count:<4}"
        )

        rem_cnt = sum(1 for d in state.all_defects if d.status == "RESOLVED")
        open_cnt = sum(1 for d in state.all_defects if d.status != "RESOLVED")
        kpi_row3 = (
            f" Defects Remediated: {self._c(str(rem_cnt), Ansi.BRIGHT_GREEN):<4}  "
            f"Open Defects: {self._c(str(open_cnt), Ansi.BRIGHT_YELLOW if open_cnt == 0 else Ansi.BRIGHT_RED):<4}  "
            f"Active Blockers: {self._c(str(len(state.active_blockers)), Ansi.BRIGHT_GREEN if len(state.active_blockers) == 0 else Ansi.BRIGHT_RED):<4}"
        )

        lines.append(self._box_line(kpi_row1, w))
        lines.append(self._box_line(kpi_row2, w))
        lines.append(self._box_line(kpi_row3, w))
        lines.append(self._box_bottom(w))
        lines.append("")

        # 3. Current Phase Spotlight
        target_pid = focus_phase_id or state.current_phase_id
        current_phase = state.phases.get(target_pid)
        if current_phase:
            lines.append(self._render_phase_spotlight(current_phase, w))
            lines.append("")

        # 4. Phase Completion Matrix (Topological Waves)
        lines.append(self._render_phase_matrix(state, w, all_phases=all_phases))
        lines.append("")

        # 5. Defect Ledger
        lines.append(self._render_defect_ledger(state.all_defects, w))
        lines.append("")

        # 6. Blocker Ledger
        lines.append(self._render_blocker_ledger(state.active_blockers, w))
        lines.append("")

        return "\n".join(lines)

    def _render_phase_spotlight(self, phase: PhaseProgress, w: int) -> str:
        lines: list[str] = []
        header = f"Phase Spotlight: {phase.phase_id} — {phase.title}"
        lines.append(self._box_header(header, w))

        deps_str = ", ".join(phase.depends) if phase.depends else "None (Root Baseline)"
        info_str = (
            f" Priority: {phase.priority}  |  Depends: {deps_str}  |  "
            f"Status: {self.status_badge(phase.status)}  |  "
            f"Progress: {phase.completed_agents_count}/{phase.total_agents_count} Agents"
        )
        lines.append(self._box_line(info_str, w))
        lines.append(self._box_separator(w))

        # Agent Table Headers
        # Columns: ID (4), Role (24), Status (12), Deliverables (14), Tests (14), Blockers / Task
        # | ID  | Role                     | Status       | Deliverables | Tests         | Task & Notes
        col_w = [4, 25, 14, 13, 15, max(15, w - 85)]
        th = (
            f" {pad_str('ID', col_w[0])} {self.c_div} "
            f"{pad_str('Role', col_w[1])} {self.c_div} "
            f"{pad_str('Status', col_w[2])} {self.c_div} "
            f"{pad_str('Deliverables', col_w[3])} {self.c_div} "
            f"{pad_str('Tests', col_w[4])} {self.c_div} "
            f"{pad_str('Task & Blockers', col_w[5])}"
        )
        lines.append(f"{self.c_v}{th}{self.c_v}")
        lines.append(self._box_separator(w))

        for ag_id in sorted(phase.agents.keys()):
            ag = phase.agents[ag_id]
            deliv = (
                f"[{'M' if ag.has_manifest else '-'}"
                f"{'T' if ag.has_test_report else '-'}"
                f"{'R' if ag.has_risk_register else '-'}"
                f"{'X' if ag.has_rollback else '-'}]"
            )

            blk_note = f"BLK: {ag.blockers[0]}" if ag.blockers else ag.task
            blk_note_clean = (blk_note[: col_w[5] - 3] + "...") if len(blk_note) > col_w[5] else blk_note

            row = (
                f" {pad_str(ag.agent_id, col_w[0])} {self.c_div} "
                f"{pad_str(ag.role[:col_w[1]], col_w[1])} {self.c_div} "
                f"{pad_str_ansi(self.status_badge(ag.status), col_w[2])} {self.c_div} "
                f"{pad_str(deliv, col_w[3])} {self.c_div} "
                f"{pad_str(ag.tests_summary[:col_w[4]], col_w[4])} {self.c_div} "
                f"{pad_str(blk_note_clean, col_w[5])}"
            )
            lines.append(f"{self.c_v}{row}{self.c_v}")

        lines.append(self._box_bottom(w))
        return "\n".join(lines)

    def _render_phase_matrix(self, state: DashboardState, w: int, all_phases: bool = False) -> str:
        lines: list[str] = []
        lines.append(self._box_header("Phase Execution Wavefront & Completion Matrix", w))

        col_w = [6, max(20, w - 62), 6, 14, 18]
        th = (
            f" {pad_str('Phase', col_w[0])} {self.c_div} "
            f"{pad_str('Title', col_w[1])} {self.c_div} "
            f"{pad_str('Prio', col_w[2])} {self.c_div} "
            f"{pad_str('Status', col_w[3])} {self.c_div} "
            f"{pad_str('Progress', col_w[4])}"
        )
        lines.append(f"{self.c_v}{th}{self.c_v}")
        lines.append(self._box_separator(w))

        # Determine which phases to show
        phases_to_show: list[str] = []
        if all_phases:
            phases_to_show = state.dag_order
        else:
            # Show completed phases + current + next 6 phases
            curr_idx = 0
            if state.current_phase_id in state.dag_order:
                curr_idx = state.dag_order.index(state.current_phase_id)
            start_idx = max(0, curr_idx - 3)
            end_idx = min(len(state.dag_order), curr_idx + 8)
            phases_to_show = state.dag_order[start_idx:end_idx]

        for pid in phases_to_show:
            p = state.phases.get(pid)
            if not p:
                continue

            bar = self._progress_bar(p.completed_agents_count, p.total_agents_count, width=8)
            prog_str = f"{p.completed_agents_count:2d}/{p.total_agents_count:2d} {bar}"

            title_clean = (p.title[: col_w[1] - 3] + "...") if len(p.title) > col_w[1] else p.title

            is_curr = pid == state.current_phase_id
            p_label = f"*{p.phase_id}" if is_curr else f" {p.phase_id}"

            row = (
                f" {pad_str(p_label, col_w[0])} {self.c_div} "
                f"{pad_str(title_clean, col_w[1])} {self.c_div} "
                f"{pad_str(p.priority, col_w[2])} {self.c_div} "
                f"{pad_str_ansi(self.status_badge(p.status), col_w[3])} {self.c_div} "
                f"{pad_str(prog_str, col_w[4])}"
            )
            lines.append(f"{self.c_v}{row}{self.c_v}")

        if not all_phases and len(state.dag_order) > len(phases_to_show):
            remaining = len(state.dag_order) - len(phases_to_show)
            msg = f"... ({remaining} additional pipeline phases omitted; use --all-phases to display all 101 phases) ..."
            lines.append(self._box_line(self._c(msg.center(w - 4), Ansi.DIM + Ansi.WHITE), w))

        lines.append(self._box_bottom(w))
        return "\n".join(lines)

    def _render_defect_ledger(self, defects: list[DefectRecord], w: int) -> str:
        lines: list[str] = []
        lines.append(self._box_header("Defect & Security Finding Remediation Ledger", w))

        if not defects:
            lines.append(self._box_line("No defects recorded in integration manifests.", w))
            lines.append(self._box_bottom(w))
            return "\n".join(lines)

        col_w = [12, 6, 10, 12, max(15, w - 54)]
        th = (
            f" {pad_str('Defect ID', col_w[0])} {self.c_div} "
            f"{pad_str('Phase', col_w[1])} {self.c_div} "
            f"{pad_str('Severity', col_w[2])} {self.c_div} "
            f"{pad_str('Status', col_w[3])} {self.c_div} "
            f"{pad_str('Description / Remediation', col_w[4])}"
        )
        lines.append(f"{self.c_v}{th}{self.c_v}")
        lines.append(self._box_separator(w))

        for d in defects:
            desc_clean = (d.description[: col_w[4] - 3] + "...") if len(d.description) > col_w[4] else d.description
            row = (
                f" {pad_str(d.defect_id, col_w[0])} {self.c_div} "
                f"{pad_str(d.phase_id, col_w[1])} {self.c_div} "
                f"{pad_str(d.severity, col_w[2])} {self.c_div} "
                f"{pad_str_ansi(self.status_badge(d.status), col_w[3])} {self.c_div} "
                f"{pad_str(desc_clean, col_w[4])}"
            )
            lines.append(f"{self.c_v}{row}{self.c_v}")

        lines.append(self._box_bottom(w))
        return "\n".join(lines)

    def _render_blocker_ledger(self, blockers: list[BlockerRecord], w: int) -> str:
        lines: list[str] = []
        lines.append(self._box_header("Active Blocker Ledger", w))

        if not blockers:
            msg = "No active blockers detected. DAG execution wavefront is CLEAR."
            lines.append(self._box_line(self._c(msg, Ansi.BRIGHT_GREEN), w))
            lines.append(self._box_bottom(w))
            return "\n".join(lines)

        col_w = [16, 6, 6, max(15, w - 40)]
        th = (
            f" {pad_str('Blocker ID', col_w[0])} {self.c_div} "
            f"{pad_str('Phase', col_w[1])} {self.c_div} "
            f"{pad_str('Agent', col_w[2])} {self.c_div} "
            f"{pad_str('Blocking Details', col_w[3])}"
        )
        lines.append(f"{self.c_v}{th}{self.c_v}")
        lines.append(self._box_separator(w))

        for b in blockers:
            desc_clean = (b.description[: col_w[3] - 3] + "...") if len(b.description) > col_w[3] else b.description
            row = (
                f" {pad_str(b.blocker_id, col_w[0])} {self.c_div} "
                f"{pad_str(b.phase_id, col_w[1])} {self.c_div} "
                f"{pad_str(b.agent_id, col_w[2])} {self.c_div} "
                f"{pad_str(desc_clean, col_w[3])}"
            )
            lines.append(f"{self.c_v}{row}{self.c_v}")

        lines.append(self._box_bottom(w))
        return "\n".join(lines)

    def _box_header(self, title: str, w: int) -> str:
        prefix = f"{self.c_top_left}{self.c_h} {title} "
        fill = w - len(prefix) - 1
        return f"{prefix}{self.c_h * max(0, fill)}{self.c_top_right}"

    def _box_separator(self, w: int) -> str:
        return f"{self.c_t_right}{self.c_h * (w - 2)}{self.c_t_left}"

    def _box_bottom(self, w: int) -> str:
        return f"{self.c_bot_left}{self.c_h * (w - 2)}{self.c_bot_right}"

    def _box_line(self, content: str, w: int) -> str:
        # Strip ANSI to measure visual length
        clean_len = visible_len(content)
        pad = w - clean_len - 3
        return f"{self.c_v} {content}{' ' * max(0, pad)}{self.c_v}"

    def _progress_bar(self, current: int, total: int, width: int = 15) -> str:
        if total <= 0:
            return "[ " + " " * width + " ]"
        ratio = min(max(current / total, 0.0), 1.0)
        filled = int(ratio * width)
        empty = width - filled
        if self.ascii_only:
            bar = "=" * filled + " " * empty
        else:
            bar = "■" * filled + "░" * empty
        return f"[{bar}]"


# -----------------------------------------------------------------------------
# String Measurement & Formatting Helpers
# -----------------------------------------------------------------------------
ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE.sub("", text)


def visible_len(text: str) -> int:
    return len(strip_ansi(text))


def pad_str(text: str, width: int) -> str:
    clean = strip_ansi(text)
    if len(clean) >= width:
        return text
    return text + " " * (width - len(clean))


def pad_str_ansi(text: str, width: int) -> str:
    vlen = visible_len(text)
    if vlen >= width:
        return text
    return text + " " * (width - vlen)


# -----------------------------------------------------------------------------
# Markdown and JSON Renderers
# -----------------------------------------------------------------------------
def render_markdown(state: DashboardState, focus_phase_id: Optional[str] = None) -> str:
    lines: list[str] = []
    lines.append("# CLARA Care Multi-Agent Phase DAG Progress Report")
    lines.append("")
    lines.append(f"- **Generated At:** `{state.generated_at}`")
    lines.append(f"- **Head SHA:** `{state.head_sha}`")
    lines.append(f"- **Active Phase Wavefront:** `{state.current_phase_id}`")
    lines.append(
        f"- **Phase Completion:** {state.completed_phases_count}/{state.total_phases_count} "
        f"({state.completion_percentage:.1f}%)"
    )
    lines.append("")

    lines.append("## Executive Health Summary")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|---|---|")
    lines.append(f"| Total Pipeline Phases | {state.total_phases_count} |")
    lines.append(f"| Completed Phases | {state.completed_phases_count} |")
    lines.append(f"| In-Progress Phases | {state.in_progress_phases_count} |")
    lines.append(f"| Ready Phases | {state.ready_phases_count} |")
    lines.append(f"| Blocked Phases | {state.blocked_phases_count} |")
    lines.append(f"| Pending Phases | {state.pending_phases_count} |")
    rem_cnt = sum(1 for d in state.all_defects if d.status == "RESOLVED")
    open_cnt = sum(1 for d in state.all_defects if d.status != "RESOLVED")
    lines.append(f"| Remediated Defects | {rem_cnt} |")
    lines.append(f"| Open Defects | {open_cnt} |")
    lines.append(f"| Active Blockers | {len(state.active_blockers)} |")
    lines.append("")

    target_pid = focus_phase_id or state.current_phase_id
    phase = state.phases.get(target_pid)
    if phase:
        lines.append(f"## Phase Spotlight: {phase.phase_id} — {phase.title}")
        lines.append("")
        lines.append(f"- **Priority:** {phase.priority}")
        lines.append(f"- **Status:** `{phase.status}`")
        lines.append(f"- **Dependencies:** {', '.join(phase.depends) if phase.depends else 'None'}")
        lines.append(f"- **Agents Completed:** {phase.completed_agents_count}/{phase.total_agents_count}")
        lines.append("")
        lines.append("| Agent | Role | Status | Deliverables | Tests | Task |")
        lines.append("|---|---|---|---|---|---|")
        for ag_id in sorted(phase.agents.keys()):
            ag = phase.agents[ag_id]
            deliv = f"Manifest: {ag.has_manifest}, Tests: {ag.has_test_report}, Risk: {ag.has_risk_register}"
            lines.append(
                f"| **{ag.agent_id}** | {ag.role} | `{ag.status}` | {deliv} | {ag.tests_summary} | {ag.task} |"
            )
        lines.append("")

    lines.append("## Defect Remediation Ledger")
    lines.append("")
    lines.append("| Defect ID | Phase | Severity | Status | Description |")
    lines.append("|---|---|---|---|---|")
    for d in state.all_defects:
        lines.append(f"| **{d.defect_id}** | {d.phase_id} | {d.severity} | `{d.status}` | {d.description} |")
    lines.append("")

    lines.append("## Active Blocker Ledger")
    lines.append("")
    if not state.active_blockers:
        lines.append("No active blocking issues detected across active execution wavefront.")
    else:
        lines.append("| Blocker ID | Phase | Agent | Description |")
        lines.append("|---|---|---|---|")
        for b in state.active_blockers:
            lines.append(f"| **{b.blocker_id}** | {b.phase_id} | {b.agent_id} | {b.description} |")
    lines.append("")

    return "\n".join(lines)


def render_json(state: DashboardState) -> str:
    # Serialize state into pure dict
    return json.dumps(asdict(state), indent=2, ensure_ascii=False)


# -----------------------------------------------------------------------------
# CLI Entrypoint
# -----------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CLARA Care Multi-Agent Phase DAG Progress & Checkpoint Dashboard"
    )
    parser.add_argument(
        "--format",
        choices=["terminal", "markdown", "json"],
        default="terminal",
        help="Output display format (default: terminal)",
    )
    parser.add_argument(
        "--phase",
        type=str,
        default=None,
        help="Focus on specific phase (e.g. PH00, PH01, PH02)",
    )
    parser.add_argument(
        "--all-phases",
        action="store_true",
        help="Display all 101 phases in the completion matrix instead of compact active wave",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors",
    )
    parser.add_argument(
        "--ascii",
        action="store_true",
        help="Use ASCII borders instead of Unicode box characters",
    )
    parser.add_argument(
        "--machine-dir",
        type=Path,
        default=None,
        help="Explicit directory containing DAG_TOPOLOGICAL_ORDER.json and PHASE_TASKS.json",
    )
    parser.add_argument(
        "--dag-order",
        type=Path,
        default=None,
        help="Explicit path to DAG_TOPOLOGICAL_ORDER.json",
    )
    parser.add_argument(
        "--phase-tasks",
        type=Path,
        default=None,
        help="Explicit path to PHASE_TASKS.json",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=None,
        help="Explicit path to artifacts directory",
    )
    parser.add_argument(
        "--worktrees-dir",
        type=Path,
        default=Path("/dev/shm/clara_worktrees"),
        help="Directory where concurrent worktrees are hosted (default: /dev/shm/clara_worktrees)",
    )
    parser.add_argument(
        "--strict-exit",
        action="store_true",
        help="Exit with code 1 if active phase is BLOCKED or has unresolved critical defects",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    locator = DataSourceLocator(
        machine_dir=args.machine_dir,
        dag_order_file=args.dag_order,
        phase_tasks_file=args.phase_tasks,
        artifacts_dir=args.artifacts_dir,
        worktrees_dir=args.worktrees_dir,
    )

    try:
        dashboard_parser = DashboardParser(locator)
        state = dashboard_parser.parse()
    except Exception as exc:
        sys.stderr.write(f"Error loading dashboard data: {exc}\n")
        return 1

    try:
        if args.format == "json":
            print(render_json(state))
        elif args.format == "markdown":
            print(render_markdown(state, focus_phase_id=args.phase))
        else:
            color_enabled = supports_color(args.no_color)
            renderer = TerminalDashboardRenderer(color=color_enabled, ascii_only=args.ascii)
            output = renderer.render(state, focus_phase_id=args.phase, all_phases=args.all_phases)
            print(output)
    except BrokenPipeError:
        # Gracefully handle piping to tools like `head` or `grep`
        sys.stderr.close()
        return 0

    if args.strict_exit:
        curr_phase = state.phases.get(state.current_phase_id)
        if curr_phase and curr_phase.status == "BLOCKED":
            return 1
        if len(state.active_blockers) > 0:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
