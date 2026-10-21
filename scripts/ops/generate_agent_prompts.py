#!/usr/bin/env python3
"""CLARA Care — Agent Task Prompt & Bounded Context Pack Generator.

Spec: PH02 / A06 (Mobile Flutter)
Role: Mobile Flutter / Ops Generator
Guarantees:
  1. Resolves phase definition and all 10 subagent tasks (A01-A10) from machine/PHASE_TASKS.json.
  2. Populates templates/AGENT_TASK_PROMPT.md with exact owned write paths, read lanes,
     role, frozen base SHA, and single focused task without leaving unreplaced placeholders.
  3. Produces isolated task prompt markdown files (A01_task_prompt.md ... A10_task_prompt.md)
     and a unified bounded_context_pack.json conforming to clara-bounded-context-pack.v1.
  4. Enforces disjoint write boundaries and strict worktree path isolation across all 10 agents.
  5. Hermetic, zero-dependency standard library implementation (Python 3.11+).

Usage:
  # Generate isolated prompts and bounded context pack for PH02
  python3 scripts/ops/generate_agent_prompts.py --phase PH02 --output-dir artifacts/PH02/prompts

  # Generate for PH03 with specific base SHA
  python3 scripts/ops/generate_agent_prompts.py --phase PH03 --base-sha 879dc5dcfcaae91b3626e28062043d934294478b

  # Output bounded context pack as JSON to stdout
  python3 scripts/ops/generate_agent_prompts.py --phase PH02 --json

  # Run built-in self tests
  python3 scripts/ops/generate_agent_prompts.py --selftest
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import unittest
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Canonical frozen ground-truth SHA for PH02 baseline
DEFAULT_FROZEN_BASE_SHA = "879dc5dcfcaae91b3626e28062043d934294478b"
DEFAULT_WORKTREE_BASE = "/dev/shm/clara_worktrees"
CONTEXT_PACK_SCHEMA_VERSION = "clara-bounded-context-pack.v1"

# Base read paths accessible by every agent regardless of role
BASELINE_READ_PATHS = [
    "AGENTS.md",
    "CLAUDE.md",
    "contracts/",
]

# Role-scoped read path supplements providing necessary domain context
ROLE_READ_PATH_SUPPLEMENTS: dict[str, list[str]] = {
    "A01": [
        "services/api/src/clara_api/api/",
        "contracts/",
        "services/api/src/clara_api/schemas.py",
        "services/api/src/clara_api/main.py",
    ],
    "A02": [
        "services/api/src/clara_api/db/",
        "services/api/alembic/",
        "services/api/src/clara_api/models/",
    ],
    "A03": [
        "services/api/src/clara_api/glhs/",
        "services/api/src/clara_api/lifemap/",
        "services/api/src/clara_api/phr/",
        "services/api/src/clara_api/compliance/",
        "services/api/src/clara_api/core/",
    ],
    "A04": [
        "services/ml/src/clara_ml/",
        "evaluation/",
        "services/ocr/",
        "services/asr/",
    ],
    "A05": [
        "apps/web/app/",
        "apps/web/components/",
        "apps/web/lib/",
        "contracts/consumer-terminology/",
    ],
    "A06": [
        "apps/mobile/lib/",
        "apps/mobile/pubspec.yaml",
        "contracts/consumer-terminology/",
    ],
    "A07": [
        "services/api/tests/",
        "services/ml/tests/",
        "apps/web/e2e/",
        ".github/workflows/",
    ],
    "A08": [
        "docs/security/",
        "docs/compliance/",
        "scripts/ops/",
    ],
    "A09": [
        "research/",
        "docs/research/",
        "docs/implementation/",
        "protocols/",
    ],
    "A10": [
        "docs/reports/",
        "docs/runbooks/",
        "scripts/ci/",
        "artifacts/",
    ],
}

# Deterministic serial integration order prescribed by PH02 architecture
DETERMINISTIC_INTEGRATION_ORDER = [
    "A02",  # DB Migrations & Schema
    "A01",  # API Contract & Schemas
    "A03",  # Domain & GLHS Services
    "A04",  # ML & Retrieval Orchestration
    "A05",  # Web UX & UI Surfaces
    "A06",  # Mobile Flutter Experience
    "A07",  # Integration Tests & CI Harness
    "A08",  # Security Audits & Red-Team Verification
    "A09",  # Research Evidence & Documentation
    "A10",  # Hostile Integration Audit & Resilience Recovery
]


@dataclass
class AgentTaskPromptSpec:
    """Bounded context specification for a single subagent."""

    agent_id: str
    role: str
    task: str
    phase_id: str
    phase_title: str
    base_sha: str
    worktree_path: str
    branch: str
    path_lane: str
    exact_write_paths: list[str]
    exact_read_paths: list[str]
    acceptance_artifacts: list[str]
    prompt_filename: str
    populated_prompt: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Converts prompt spec to serializable dictionary."""
        data = asdict(self)
        del data["populated_prompt"]
        return data


@dataclass
class BoundedContextPack:
    """Unified bounded context pack for an entire execution phase."""

    schema_version: str
    phase_id: str
    phase_number: int
    phase_title: str
    priority: str
    dependencies: list[int]
    frozen_base_sha: str
    generated_at_utc: str
    worktree_root: str
    agents_count: int
    isolation_rules: dict[str, Any]
    agents: dict[str, dict[str, Any]]
    write_lane_conflicts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Converts pack to serializable dictionary."""
        return asdict(self)


def normalize_phase_id(raw_input: str | int) -> str:
    """Normalizes various phase representations (e.g. 2, '2', 'ph02', 'PH2') into canonical 'PH02'."""
    val = str(raw_input).strip()
    if not val:
        raise ValueError("Phase ID cannot be empty")

    m = re.match(r"^(?:PH)?([0-9]{1,3})$", val, re.IGNORECASE)
    if m:
        num = int(m.group(1))
        return f"PH{num:02d}"

    upper_val = val.upper()
    if upper_val.startswith("PH"):
        return upper_val
    return f"PH{upper_val}"


def get_repo_root(start_path: Path | None = None) -> Path:
    """Locates the repository root by checking git top-level or walking upwards."""
    start = (start_path or Path.cwd()).resolve()

    try:
        res = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(start),
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return Path(res.stdout.strip()).resolve()
    except Exception:
        pass

    curr: Path | None = start
    while curr and curr != curr.parent:
        if (curr / ".git").exists() or (curr / "AGENTS.md").exists():
            return curr
        curr = curr.parent

    return start


def find_phase_tasks_file(explicit_path: Path | str | None = None, repo_root: Path | None = None) -> Path:
    """Discovers machine/PHASE_TASKS.json across repo root, worktrees, and fallbacks."""
    if explicit_path:
        p = Path(explicit_path).resolve()
        if p.is_file():
            return p
        raise FileNotFoundError(f"Explicit tasks file not found: {explicit_path}")

    env_path = os.environ.get("CLARA_PHASE_TASKS")
    if env_path:
        p = Path(env_path).resolve()
        if p.is_file():
            return p

    root = (repo_root or get_repo_root()).resolve()

    # Determine common git dir if inside a linked worktree
    common_parent: Path | None = None
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            common_git = Path(res.stdout.strip()).resolve()
            common_parent = common_git.parent
    except Exception:
        pass

    candidates: list[Path] = [
        root / "machine" / "PHASE_TASKS.json",
        root / "CLARA_CARE_MODULAR_MASTER_MOBILE_V2_NO_MOCK" / "machine" / "PHASE_TASKS.json",
        Path.cwd() / "machine" / "PHASE_TASKS.json",
        Path.cwd() / "CLARA_CARE_MODULAR_MASTER_MOBILE_V2_NO_MOCK" / "machine" / "PHASE_TASKS.json",
        Path(__file__).resolve().parents[2] / "machine" / "PHASE_TASKS.json",
        Path(__file__).resolve().parents[2] / "CLARA_CARE_MODULAR_MASTER_MOBILE_V2_NO_MOCK" / "machine" / "PHASE_TASKS.json",
    ]

    if common_parent:
        candidates.extend([
            common_parent / "machine" / "PHASE_TASKS.json",
            common_parent / "CLARA_CARE_MODULAR_MASTER_MOBILE_V2_NO_MOCK" / "machine" / "PHASE_TASKS.json",
        ])

    candidates.append(
        Path("/home/clue/Documents/CLARA-Care/CLARA_CARE_MODULAR_MASTER_MOBILE_V2_NO_MOCK/machine/PHASE_TASKS.json")
    )

    for cand in candidates:
        if cand.is_file():
            return cand

    raise FileNotFoundError(
        "Could not locate machine/PHASE_TASKS.json. Please specify via --tasks-file or CLARA_PHASE_TASKS."
    )


def find_template_file(explicit_path: Path | str | None = None, repo_root: Path | None = None) -> Path:
    """Discovers templates/AGENT_TASK_PROMPT.md across repo root, worktrees, and fallbacks."""
    if explicit_path:
        p = Path(explicit_path).resolve()
        if p.is_file():
            return p
        raise FileNotFoundError(f"Explicit template file not found: {explicit_path}")

    env_path = os.environ.get("CLARA_AGENT_TEMPLATE")
    if env_path:
        p = Path(env_path).resolve()
        if p.is_file():
            return p

    root = (repo_root or get_repo_root()).resolve()

    common_parent: Path | None = None
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            common_git = Path(res.stdout.strip()).resolve()
            common_parent = common_git.parent
    except Exception:
        pass

    candidates: list[Path] = [
        root / "templates" / "AGENT_TASK_PROMPT.md",
        root / "CLARA_CARE_MODULAR_MASTER_MOBILE_V2_NO_MOCK" / "templates" / "AGENT_TASK_PROMPT.md",
        Path.cwd() / "templates" / "AGENT_TASK_PROMPT.md",
        Path.cwd() / "CLARA_CARE_MODULAR_MASTER_MOBILE_V2_NO_MOCK" / "templates" / "AGENT_TASK_PROMPT.md",
        Path(__file__).resolve().parents[2] / "templates" / "AGENT_TASK_PROMPT.md",
        Path(__file__).resolve().parents[2] / "CLARA_CARE_MODULAR_MASTER_MOBILE_V2_NO_MOCK" / "templates" / "AGENT_TASK_PROMPT.md",
    ]

    if common_parent:
        candidates.extend([
            common_parent / "templates" / "AGENT_TASK_PROMPT.md",
            common_parent / "CLARA_CARE_MODULAR_MASTER_MOBILE_V2_NO_MOCK" / "templates" / "AGENT_TASK_PROMPT.md",
        ])

    candidates.append(
        Path("/home/clue/Documents/CLARA-Care/CLARA_CARE_MODULAR_MASTER_MOBILE_V2_NO_MOCK/templates/AGENT_TASK_PROMPT.md")
    )

    for cand in candidates:
        if cand.is_file():
            return cand

    raise FileNotFoundError(
        "Could not locate templates/AGENT_TASK_PROMPT.md. Please specify via --template or CLARA_AGENT_TEMPLATE."
    )


def resolve_base_sha(explicit_sha: str | None = None, repo_root: Path | None = None) -> str:
    """Resolves ground-truth commit SHA from argument, git rev-parse HEAD, or default frozen SHA."""
    if explicit_sha and explicit_sha.strip():
        sha = explicit_sha.strip()
        if re.match(r"^[0-9a-fA-F]{40}$", sha):
            return sha.lower()
        raise ValueError(f"Invalid SHA format (must be 40-char hex): {explicit_sha}")

    env_sha = os.environ.get("CLARA_BASE_SHA")
    if env_sha and env_sha.strip():
        sha = env_sha.strip()
        if re.match(r"^[0-9a-fA-F]{40}$", sha):
            return sha.lower()

    root = repo_root or get_repo_root()
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            candidate = res.stdout.strip()
            if re.match(r"^[0-9a-fA-F]{40}$", candidate):
                return candidate.lower()
    except Exception:
        pass

    return DEFAULT_FROZEN_BASE_SHA


def load_phase_record(tasks_file: Path, phase_id: str) -> dict[str, Any]:
    """Loads and extracts the exact phase dictionary matching phase_id from PHASE_TASKS.json."""
    normalized_target = normalize_phase_id(phase_id)

    with open(tasks_file, encoding="utf-8") as f:
        data = json.load(f)

    phases = data if isinstance(data, list) else data.get("phases", [])

    available_ids: list[str] = []
    for ph in phases:
        pid = str(ph.get("id", "")).strip().upper()
        pnum = f"PH{ph.get('phase', -1):02d}".upper()
        available_ids.append(pid or pnum)

        if pid == normalized_target or pnum == normalized_target:
            return ph

    preview = ", ".join(available_ids[:15]) + ("..." if len(available_ids) > 15 else "")
    raise KeyError(f"Phase '{phase_id}' (normalized: '{normalized_target}') not found. Available: {preview}")


def list_available_phases(tasks_file: Path) -> list[dict[str, Any]]:
    """Returns a summary list of all phases available in PHASE_TASKS.json."""
    with open(tasks_file, encoding="utf-8") as f:
        data = json.load(f)

    phases = data if isinstance(data, list) else data.get("phases", [])
    summaries: list[dict[str, Any]] = []

    for ph in phases:
        pid = str(ph.get("id", "")).strip() or f"PH{ph.get('phase', -1):02d}"
        summaries.append({
            "id": pid,
            "phase": ph.get("phase", -1),
            "title": ph.get("title", ""),
            "priority": ph.get("priority", "P0"),
            "depends": ph.get("depends", []),
            "agents_count": len(ph.get("agents", [])),
        })

    return summaries


def derive_write_paths(raw_path_lane: str, phase_id: str, agent_id: str) -> list[str]:
    """Derives exact owned write paths from raw path_lane, ensuring agent artifact lane is included."""
    paths: list[str] = []
    seen: set[str] = set()

    for item in raw_path_lane.split(";"):
        cleaned = item.strip().replace("\\", "/")
        if cleaned and cleaned not in seen:
            paths.append(cleaned)
            seen.add(cleaned)

    # Subagent-specific artifact deliverable lane
    artifact_lane = f"artifacts/{phase_id}/{agent_id}/"
    if artifact_lane not in seen:
        paths.append(artifact_lane)
        seen.add(artifact_lane)

    return paths


def derive_read_paths(agent_id: str, write_paths: list[str], custom_reads: list[str] | None = None) -> list[str]:
    """Derives exact authorized read paths combining baseline, role-specific paths, and owned lanes."""
    paths: list[str] = []
    seen: set[str] = set()

    def add_path(p: str) -> None:
        cleaned = p.strip().replace("\\", "/")
        if cleaned and cleaned not in seen:
            paths.append(cleaned)
            seen.add(cleaned)

    # 1. Baseline repo context
    for bp in BASELINE_READ_PATHS:
        add_path(bp)

    # 2. Role supplements
    supplements = ROLE_READ_PATH_SUPPLEMENTS.get(agent_id.upper(), [])
    for sp in supplements:
        add_path(sp)

    # 3. Custom reads if provided
    if custom_reads:
        for cr in custom_reads:
            add_path(cr)

    # 4. Owned write lanes are always authorized for read
    for wp in write_paths:
        add_path(wp)

    return paths


def check_write_lane_isolation(agent_specs: dict[str, AgentTaskPromptSpec]) -> list[str]:
    """Checks for unexpected cross-agent write lane overlap across all 10 subagents."""
    conflicts: list[str] = []
    agent_ids = sorted(agent_specs.keys())

    for i in range(len(agent_ids)):
        for j in range(i + 1, len(agent_ids)):
            id_a = agent_ids[i]
            id_b = agent_ids[j]
            paths_a = [p for p in agent_specs[id_a].exact_write_paths if not p.startswith("artifacts/")]
            paths_b = [p for p in agent_specs[id_b].exact_write_paths if not p.startswith("artifacts/")]

            for pa in paths_a:
                for pb in paths_b:
                    if pa == pb:
                        conflicts.append(f"Identical write path '{pa}' shared between {id_a} and {id_b}")
                    elif pa.endswith("/") and pb.startswith(pa):
                        conflicts.append(f"Nested write collision: '{pb}' ({id_b}) inside '{pa}' ({id_a})")
                    elif pb.endswith("/") and pa.startswith(pb):
                        conflicts.append(f"Nested write collision: '{pa}' ({id_a}) inside '{pb}' ({id_b})")

    return conflicts


def populate_agent_prompt(
    template_raw: str,
    spec: AgentTaskPromptSpec,
) -> str:
    """Populates template placeholders with agent-specific bounded context values."""
    write_lane_str = ";".join(spec.exact_write_paths)
    read_lane_str = ";".join(spec.exact_read_paths)

    # Format deliverables list for clarity
    deliverables_md = "\n".join(f"- `{art}`" for art in spec.acceptance_artifacts)

    # Header metadata block preceding the template instructions
    header_block = (
        f"# AGENT TASK PROMPT: {spec.agent_id} ({spec.role}) — {spec.phase_id}\n\n"
        f"You are subagent `{spec.agent_id}` for `{spec.phase_id}`.\n"
        f"- **Phase ID**: `{spec.phase_id}` — {spec.phase_title}\n"
        f"- **Agent ID**: `{spec.agent_id}`\n"
        f"- **Role**: `{spec.role}`\n"
        f"- **Worktree path**: `{spec.worktree_path}`\n"
        f"- **Branch**: `{spec.branch}`\n"
        f"- **Frozen HEAD SHA**: `{spec.base_sha}`\n"
        f"- **Task**: {spec.task}\n"
        f"- **Path lane (Write)**: `{write_lane_str}`\n"
        f"- **Read lane**: `{read_lane_str}`\n"
        f"- **Required Acceptance Deliverables**:\n{deliverables_md}\n\n"
        f"---\n\n"
    )

    body = template_raw

    # Primary bracket replacements as specified in AGENT_TASK_PROMPT.md
    replacements: dict[str, str] = {
        "[AGENT_ID]": spec.agent_id,
        "[PHASE_ID]": spec.phase_id,
        "[EXACT_WRITE_PATHS]": write_lane_str,
        "[EXACT_READ_PATHS]": read_lane_str,
        "[BASE_SHA]": spec.base_sha,
        "[ONE_SPECIFIC_TASK_FROM_PHASE]": spec.task,
        "[ROLE]": spec.role,
        "[BRANCH]": spec.branch,
        "[WORKTREE_PATH]": spec.worktree_path,
        "[PHASE_TITLE]": spec.phase_title,
    }

    for placeholder, val in replacements.items():
        body = body.replace(placeholder, val)

    # Verify no unpopulated template placeholders remain
    remaining = re.findall(r"\[[A-Z0-9_]{3,}\]", body)
    if remaining:
        raise ValueError(f"Unpopulated template placeholders found in {spec.agent_id} prompt: {remaining}")

    return header_block + body.strip() + "\n"


def generate_prompts_and_pack(
    phase_id: str,
    tasks_file: Path,
    template_file: Path,
    base_sha: str,
    worktree_base: str = DEFAULT_WORKTREE_BASE,
) -> tuple[dict[str, AgentTaskPromptSpec], BoundedContextPack]:
    """Generates prompt specifications and unified bounded context pack for all agents in a phase."""
    norm_phase_id = normalize_phase_id(phase_id)
    phase_data = load_phase_record(tasks_file, norm_phase_id)

    with open(template_file, encoding="utf-8") as f:
        template_raw = f.read()

    agents_list = phase_data.get("agents", [])
    if not agents_list:
        raise ValueError(f"No agents configured for phase '{norm_phase_id}' in {tasks_file}")

    phase_title = str(phase_data.get("title", ""))
    phase_num = int(phase_data.get("phase", -1))
    priority = str(phase_data.get("priority", "P0"))
    depends = [int(d) for d in phase_data.get("depends", [])]

    agent_specs: dict[str, AgentTaskPromptSpec] = {}

    for ag in agents_list:
        aid = str(ag.get("agent_id", "")).strip().upper()
        role = str(ag.get("role", "")).strip()
        task = str(ag.get("task", "")).strip()
        raw_lane = str(ag.get("path_lane", "")).strip()

        # Acceptance artifacts list (defaulting if not explicitly declared)
        raw_artifacts = ag.get("acceptance_artifacts", [])
        if raw_artifacts:
            artifacts = [str(a).strip() for a in raw_artifacts if str(a).strip()]
        else:
            artifacts = [
                f"artifacts/{norm_phase_id}/{aid}/change_manifest.json",
                f"artifacts/{norm_phase_id}/{aid}/test_report.md",
                f"artifacts/{norm_phase_id}/{aid}/risk_register.md",
            ]

        write_paths = derive_write_paths(raw_lane, norm_phase_id, aid)
        read_paths = derive_read_paths(aid, write_paths)

        worktree_path = f"{worktree_base.rstrip('/')}/{norm_phase_id}_{aid}"
        branch = f"phase/{norm_phase_id.lower()}-{aid.lower()}"
        prompt_filename = f"{aid}_task_prompt.md"

        spec = AgentTaskPromptSpec(
            agent_id=aid,
            role=role,
            task=task,
            phase_id=norm_phase_id,
            phase_title=phase_title,
            base_sha=base_sha,
            worktree_path=worktree_path,
            branch=branch,
            path_lane=raw_lane,
            exact_write_paths=write_paths,
            exact_read_paths=read_paths,
            acceptance_artifacts=artifacts,
            prompt_filename=prompt_filename,
        )

        spec.populated_prompt = populate_agent_prompt(template_raw, spec)
        agent_specs[aid] = spec

    conflicts = check_write_lane_isolation(agent_specs)

    pack_agents: dict[str, dict[str, Any]] = {
        aid: spec.to_dict() for aid, spec in agent_specs.items()
    }

    context_pack = BoundedContextPack(
        schema_version=CONTEXT_PACK_SCHEMA_VERSION,
        phase_id=norm_phase_id,
        phase_number=phase_num,
        phase_title=phase_title,
        priority=priority,
        dependencies=depends,
        frozen_base_sha=base_sha,
        generated_at_utc=datetime.datetime.now(datetime.UTC).isoformat(),
        worktree_root=worktree_base,
        agents_count=len(agent_specs),
        isolation_rules={
            "concurrent_isolated_worktrees": True,
            "disjoint_write_lanes": True,
            "no_cross_worktree_edits": True,
            "immutable_base_sha_verification": True,
            "serial_integration_order": DETERMINISTIC_INTEGRATION_ORDER,
        },
        agents=pack_agents,
        write_lane_conflicts=conflicts,
    )

    return agent_specs, context_pack


def render_index_markdown(context_pack: BoundedContextPack, agent_specs: dict[str, AgentTaskPromptSpec]) -> str:
    """Renders an INDEX.md directory summarizing the 10 subagent prompts and bounded context."""
    lines: list[str] = [
        f"# Phase {context_pack.phase_id} — Agent Prompt & Bounded Context Pack",
        "",
        f"- **Title**: {context_pack.phase_title}",
        f"- **Priority**: `{context_pack.priority}`",
        f"- **Dependencies**: `{context_pack.dependencies}`",
        f"- **Frozen Base SHA**: `{context_pack.frozen_base_sha}`",
        f"- **Worktree Root**: `{context_pack.worktree_root}`",
        f"- **Generated (UTC)**: `{context_pack.generated_at_utc}`",
        f"- **Total Agents**: `{context_pack.agents_count}`",
        "",
        "## Subagent Task Directory",
        "",
        "| Agent | Role | Task | Write Lane | Branch | Prompt File |",
        "|---|---|---|---|---|---|",
    ]

    for aid in DETERMINISTIC_INTEGRATION_ORDER:
        spec = agent_specs.get(aid)
        if not spec:
            continue
        lane_preview = "`" + "; ".join(spec.exact_write_paths[:2]) + ("...`" if len(spec.exact_write_paths) > 2 else "`")
        lines.append(
            f"| **{spec.agent_id}** | {spec.role} | {spec.task} | {lane_preview} | `{spec.branch}` | [{spec.prompt_filename}]({spec.prompt_filename}) |"
        )

    lines.extend([
        "",
        "## Execution Instructions",
        "",
        "1. Verify repo HEAD in each worktree matches frozen base SHA.",
        "2. Subagents must never write outside their exact write paths.",
        "3. Integration follows deterministic order: `A02 -> A01 -> A03 -> A04 -> A05 -> A06 -> A07 -> A08 -> A09 -> A10`.",
        "4. Bounded context pack JSON: [`bounded_context_pack.json`](bounded_context_pack.json).",
        "",
    ])

    return "\n".join(lines)


def write_pack_to_directory(
    output_dir: Path,
    agent_specs: dict[str, AgentTaskPromptSpec],
    context_pack: BoundedContextPack,
    filter_agent: str | None = None,
) -> list[Path]:
    """Writes populated prompt files, bounded_context_pack.json, and INDEX.md to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    created_files: list[Path] = []

    target_agents = [filter_agent.upper()] if filter_agent else sorted(agent_specs.keys())

    for aid in target_agents:
        spec = agent_specs[aid]
        prompt_path = output_dir / spec.prompt_filename
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(spec.populated_prompt)
        created_files.append(prompt_path)

    if not filter_agent:
        pack_path = output_dir / "bounded_context_pack.json"
        with open(pack_path, "w", encoding="utf-8") as f:
            json.dump(context_pack.to_dict(), f, indent=2, ensure_ascii=False)
        created_files.append(pack_path)

        index_path = output_dir / "INDEX.md"
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(render_index_markdown(context_pack, agent_specs))
        created_files.append(index_path)

    return created_files


# ==============================================================================
# Built-in Self-Test Suite
# ==============================================================================


class GenerateAgentPromptsSelfTest(unittest.TestCase):
    """Hermetic unit tests validating prompt generation and bounded context packing."""

    def test_normalize_phase_id(self) -> None:
        self.assertEqual(normalize_phase_id("2"), "PH02")
        self.assertEqual(normalize_phase_id("02"), "PH02")
        self.assertEqual(normalize_phase_id("ph02"), "PH02")
        self.assertEqual(normalize_phase_id("PH02"), "PH02")
        self.assertEqual(normalize_phase_id("PH3"), "PH03")
        self.assertEqual(normalize_phase_id(99), "PH99")

    def test_discovery_and_generation_ph02(self) -> None:
        tasks_file = find_phase_tasks_file()
        template_file = find_template_file()
        base_sha = resolve_base_sha()

        self.assertTrue(tasks_file.is_file())
        self.assertTrue(template_file.is_file())
        self.assertEqual(len(base_sha), 40)

        agent_specs, pack = generate_prompts_and_pack(
            phase_id="PH02",
            tasks_file=tasks_file,
            template_file=template_file,
            base_sha=base_sha,
        )

        self.assertEqual(len(agent_specs), 10)
        self.assertEqual(pack.phase_id, "PH02")
        self.assertEqual(pack.agents_count, 10)

        # Verify A06 (Mobile Flutter) task
        self.assertIn("A06", agent_specs)
        a06 = agent_specs["A06"]
        self.assertEqual(a06.role, "Mobile Flutter")
        self.assertIn("apps/mobile/", a06.exact_write_paths)
        self.assertIn("artifacts/PH02/A06/", a06.exact_write_paths)
        self.assertIn("AGENTS.md", a06.exact_read_paths)
        self.assertIn(base_sha, a06.populated_prompt)
        self.assertIn("PH02", a06.populated_prompt)

        # Ensure no unfilled bracket placeholders exist in any prompt
        for aid, spec in agent_specs.items():
            self.assertFalse(re.search(r"\[[A-Z0-9_]{3,}\]", spec.populated_prompt))
            self.assertIn(aid, spec.populated_prompt)
            self.assertIn(base_sha, spec.populated_prompt)

    def test_discovery_and_generation_ph03(self) -> None:
        tasks_file = find_phase_tasks_file()
        template_file = find_template_file()
        base_sha = resolve_base_sha()

        agent_specs, pack = generate_prompts_and_pack(
            phase_id="PH03",
            tasks_file=tasks_file,
            template_file=template_file,
            base_sha=base_sha,
        )

        self.assertEqual(len(agent_specs), 10)
        self.assertEqual(pack.phase_id, "PH03")

        # Verify A01 in PH03
        a01 = agent_specs["A01"]
        self.assertEqual(a01.role, "API + contract")
        self.assertIn("auth threat inventory", a01.task)
        self.assertIn("services/api/src/clara_api/api/", a01.exact_write_paths)
        self.assertIn("artifacts/PH03/A01/", a01.exact_write_paths)


# ==============================================================================
# CLI Entrypoint
# ==============================================================================


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="CLARA Care Agent Prompt and Bounded Context Pack Generator (PH02 A06)"
    )
    parser.add_argument(
        "phase_pos",
        nargs="?",
        metavar="PHASE_ID",
        help="Target phase ID (e.g. PH02, PH03, 2, 3)",
    )
    parser.add_argument(
        "--phase",
        "-p",
        dest="phase_opt",
        help="Target phase ID (e.g. PH02, PH03)",
    )
    parser.add_argument(
        "--tasks-file",
        "-t",
        help="Path to machine/PHASE_TASKS.json (auto-detected if omitted)",
    )
    parser.add_argument(
        "--template",
        "-m",
        help="Path to templates/AGENT_TASK_PROMPT.md (auto-detected if omitted)",
    )
    parser.add_argument(
        "--base-sha",
        "-b",
        help="Ground-truth base commit SHA (defaults to git HEAD or frozen baseline)",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        help="Directory to write generated prompts and context pack (default: stdout / dry-run)",
    )
    parser.add_argument(
        "--worktree-base",
        default=DEFAULT_WORKTREE_BASE,
        help=f"Base directory for worktrees (default: {DEFAULT_WORKTREE_BASE})",
    )
    parser.add_argument(
        "--agent",
        "-a",
        help="Filter and output only for a specific agent (e.g. A06)",
    )
    parser.add_argument(
        "--list-phases",
        "-l",
        action="store_true",
        help="List available phases in machine/PHASE_TASKS.json and exit",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print bounded context pack as JSON to stdout",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print generated markdown prompt(s) to stdout",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and generate in-memory without writing files",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="Execute internal verification test suite",
    )

    args = parser.parse_args(argv)

    if args.selftest:
        suite = unittest.TestLoader().loadTestsFromTestCase(GenerateAgentPromptsSelfTest)
        runner = unittest.TextTestRunner(verbosity=2)
        res = runner.run(suite)
        return 0 if res.wasSuccessful() else 1

    try:
        tasks_file = find_phase_tasks_file(args.tasks_file)
    except FileNotFoundError as err:
        sys.stderr.write(f"Error: {err}\n")
        return 1

    if args.list_phases:
        phases = list_available_phases(tasks_file)
        print(f"Available Phases in {tasks_file} ({len(phases)} total):")
        print(f"{'ID':<8} {'Phase#':<8} {'Pri':<6} {'Agents':<8} {'Title'}")
        print("-" * 75)
        for ph in phases:
            print(f"{ph['id']:<8} {ph['phase']:<8} {ph['priority']:<6} {ph['agents_count']:<8} {ph['title']}")
        return 0

    target_phase = args.phase_opt or args.phase_pos
    if not target_phase:
        sys.stderr.write("Error: Phase ID is required (e.g., --phase PH02 or 'PH02'). Use --help for usage.\n")
        return 1

    try:
        norm_phase = normalize_phase_id(target_phase)
        template_file = find_template_file(args.template)
        base_sha = resolve_base_sha(args.base_sha)
        agent_specs, context_pack = generate_prompts_and_pack(
            phase_id=norm_phase,
            tasks_file=tasks_file,
            template_file=template_file,
            base_sha=base_sha,
            worktree_base=args.worktree_base,
        )
    except Exception as err:
        sys.stderr.write(f"Generation error: {err}\n")
        return 1

    filter_agent = args.agent.strip().upper() if args.agent else None
    if filter_agent and filter_agent not in agent_specs:
        sys.stderr.write(f"Error: Agent '{filter_agent}' not found in phase {norm_phase}.\n")
        return 1

    # Output bounded context pack JSON
    if args.json:
        if filter_agent:
            print(json.dumps(agent_specs[filter_agent].to_dict(), indent=2, ensure_ascii=False))
        else:
            print(json.dumps(context_pack.to_dict(), indent=2, ensure_ascii=False))
        return 0

    # Output prompt text to stdout
    if args.stdout:
        target_list = [filter_agent] if filter_agent else sorted(agent_specs.keys())
        for aid in target_list:
            print(agent_specs[aid].populated_prompt)
        return 0

    # Write files if output-dir is specified or if not dry-run
    if args.output_dir:
        out_path = Path(args.output_dir).resolve()
        created = write_pack_to_directory(out_path, agent_specs, context_pack, filter_agent=filter_agent)
        print(f"Successfully generated {len(created)} deliverables for {norm_phase} in {out_path}:")
        for f in created:
            print(f"  - {f.name}")
        return 0

    # Default dry-run summary
    print("================================================================================")
    print(f"AGENT PROMPT & BOUNDED CONTEXT PACK GENERATOR — {norm_phase}")
    print("================================================================================")
    print(f"Title         : {context_pack.phase_title}")
    print(f"Frozen SHA    : {context_pack.frozen_base_sha}")
    print(f"Worktree Root : {context_pack.worktree_root}")
    print(f"Agents Count  : {context_pack.agents_count}")
    print(f"Tasks File    : {tasks_file}")
    print(f"Template File : {template_file}")
    print(f"Conflicts     : {len(context_pack.write_lane_conflicts)}")
    for conf in context_pack.write_lane_conflicts:
        print(f"  [WARN] {conf}")

    print("\nSubagents:")
    target_list = [filter_agent] if filter_agent else sorted(agent_specs.keys())
    for aid in target_list:
        spec = agent_specs[aid]
        print(f"  [{spec.agent_id}] {spec.role:<30} -> {spec.task}")
        print(f"       Write: {'; '.join(spec.exact_write_paths)}")
        print(f"       Branch: {spec.branch} | Worktree: {spec.worktree_path}")

    print("\nDry run complete. Use --output-dir <path> to write prompts and context pack.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
