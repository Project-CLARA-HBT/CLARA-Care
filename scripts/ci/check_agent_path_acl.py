#!/usr/bin/env python3
"""Ownership and Path ACL Checker.

Enforces subagent path isolation across execution phases.
Verifies git diffs or file lists against the designated `path_lane` for each
agent, failing immediately if any touched file lies outside the agent's lane.

Usage:
    # Check specific files for an agent
    python3 scripts/ci/check_agent_path_acl.py --agent-id A05 --phase-id PH02 --files apps/web/app/page.tsx

    # Check git diff against a base commit
    python3 scripts/ci/check_agent_path_acl.py --agent-id A05 --phase-id PH02 --base 879dc5dcfcaae91b3626e28062043d934294478b

    # Pipe diff or file list via stdin
    git diff --name-only | python3 scripts/ci/check_agent_path_acl.py A05 PH02 -

    # Run internal self-tests
    python3 scripts/ci/check_agent_path_acl.py --selftest
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import posixpath
import re
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any, Sequence

def _detect_repo_root() -> Path:
    """Detects active git repository or worktree root, falling back to script ancestor."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return Path(res.stdout.strip()).resolve()
    except Exception:
        pass
    return Path(__file__).resolve().parents[2]


REPO_ROOT = _detect_repo_root()

# Canonical default path lanes by agent role across phases
DEFAULT_AGENT_LANES: dict[str, list[str]] = {
    "A01": [
        "services/api/src/clara_api/api/",
        "contracts/",
        "services/api/src/clara_api/schemas.py",
    ],
    "A02": [
        "services/api/src/clara_api/db/",
        "services/api/alembic/versions/",
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
    ],
    "A06": [
        "apps/mobile/",
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
        "docs/interoperability/",
    ],
    "A10": [
        "docs/reports/",
        "docs/runbooks/",
        "scripts/ci/",
        "artifacts/phase-gates/",
    ],
}


def _clean_diff_path(raw_path: str, repo_root: Path | None = None) -> str:
    """Cleans and normalizes a file path from diff headers or lists."""
    if not raw_path:
        return ""

    p = raw_path.strip().strip("'\"")
    if p in ("/dev/null", "dev/null", "nul"):
        return "/dev/null"

    # Git diff prefix stripping (a/..., b/...)
    if p.startswith("a/") or p.startswith("b/"):
        p = p[2:]

    # Normalize slashes
    p = p.replace("\\", "/")

    # Check if absolute path inside repo root
    root = (repo_root or REPO_ROOT).resolve()
    try:
        abs_p = Path(p).resolve()
        if abs_p.is_relative_to(root):
            p = str(abs_p.relative_to(root)).replace("\\", "/")
    except Exception:
        pass

    # Normalize POSIX path
    norm = posixpath.normpath(p)
    if norm == ".":
        return ""
    norm = norm.lstrip("/")
    return norm


def _split_git_diff_line(line_content: str) -> list[str]:
    """Splits 'diff --git a/file b/file' considering quoted paths."""
    parts: list[str] = []
    current: list[str] = []
    in_quote = False
    escape = False

    for char in line_content:
        if escape:
            current.append(char)
            escape = False
        elif char == "\\":
            escape = True
        elif char == '"':
            in_quote = not in_quote
        elif char == " " and not in_quote:
            if current:
                parts.append("".join(current))
                current = []
        else:
            current.append(char)

    if current:
        parts.append("".join(current))

    return parts


def extract_changed_files_from_diff(diff_content: str, repo_root: Path | None = None) -> list[str]:
    """Extracts changed file paths from unified diff or file list text."""
    files: set[str] = set()
    lines = diff_content.splitlines()

    has_diff_headers = any(
        line.startswith(("diff --git ", "--- ", "+++ ", "rename from ", "copy from "))
        for line in lines
    )

    if has_diff_headers:
        for line in lines:
            line_s = line.strip()
            if line_s.startswith("diff --git "):
                remainder = line_s[len("diff --git "):]
                parts = _split_git_diff_line(remainder)
                if len(parts) >= 2:
                    for part in (parts[0], parts[1]):
                        cleaned = _clean_diff_path(part, repo_root=repo_root)
                        if cleaned and cleaned != "/dev/null":
                            files.add(cleaned)
            elif line_s.startswith("--- "):
                cleaned = _clean_diff_path(line_s[4:], repo_root=repo_root)
                if cleaned and cleaned != "/dev/null":
                    files.add(cleaned)
            elif line_s.startswith("+++ "):
                cleaned = _clean_diff_path(line_s[4:], repo_root=repo_root)
                if cleaned and cleaned != "/dev/null":
                    files.add(cleaned)
            elif line_s.startswith("rename from ") or line_s.startswith("copy from "):
                part = line_s.split(maxsplit=2)[-1]
                cleaned = _clean_diff_path(part, repo_root=repo_root)
                if cleaned and cleaned != "/dev/null":
                    files.add(cleaned)
            elif line_s.startswith("rename to ") or line_s.startswith("copy to "):
                part = line_s.split(maxsplit=2)[-1]
                cleaned = _clean_diff_path(part, repo_root=repo_root)
                if cleaned and cleaned != "/dev/null":
                    files.add(cleaned)
        return sorted(files)

    # Line-by-line file list or git status porcelain output
    for line in lines:
        line_s = line.strip()
        if not line_s or line_s.startswith("#"):
            continue

        # Handle git status / diff name-status: e.g. "M  file.py", "R100 old -> new"
        status_match = re.match(r"^([MADRCU?!\s]{1,3}|R\d+)\s+(.+)$", line_s)
        if status_match and not (Path(line_s).exists() and not Path(status_match.group(2)).exists()):
            path_part = status_match.group(2).strip()
            if " -> " in path_part:
                for sub in path_part.split(" -> "):
                    c = _clean_diff_path(sub, repo_root=repo_root)
                    if c and c != "/dev/null":
                        files.add(c)
            elif "\t" in path_part:
                for sub in path_part.split("\t"):
                    c = _clean_diff_path(sub, repo_root=repo_root)
                    if c and c != "/dev/null":
                        files.add(c)
            else:
                c = _clean_diff_path(path_part, repo_root=repo_root)
                if c and c != "/dev/null":
                    files.add(c)
        else:
            c = _clean_diff_path(line_s, repo_root=repo_root)
            if c and c != "/dev/null":
                files.add(c)

    return sorted(files)


def find_phase_tasks_file(
    explicit_path: Path | str | None = None,
    repo_root: Path | None = None,
) -> Path | None:
    """Locates the PHASE_TASKS.json file across standard repository locations."""
    if explicit_path:
        p = Path(explicit_path).resolve()
        if p.is_file():
            return p

    env_path = os.environ.get("PHASE_TASKS_PATH")
    if env_path:
        p = Path(env_path).resolve()
        if p.is_file():
            return p

    root = (repo_root or REPO_ROOT).resolve()
    candidates = [
        root / "machine" / "PHASE_TASKS.json",
        root / "CLARA_CARE_MODULAR_MASTER_MOBILE_V2_NO_MOCK" / "machine" / "PHASE_TASKS.json",
        root.parent / "CLARA_CARE_MODULAR_MASTER_MOBILE_V2_NO_MOCK" / "machine" / "PHASE_TASKS.json",
        Path("/home/clue/Documents/CLARA-Care/CLARA_CARE_MODULAR_MASTER_MOBILE_V2_NO_MOCK/machine/PHASE_TASKS.json"),
    ]

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    return None


def get_agent_path_lanes(
    agent_id: str,
    phase_id: str,
    phase_tasks_path: Path | str | None = None,
    explicit_lane: str | list[str] | None = None,
    extra_lanes: list[str] | None = None,
    repo_root: Path | None = None,
) -> list[str]:
    """Resolves designated path lanes for a given agent and phase."""
    normalized_agent = agent_id.strip().upper()
    normalized_phase = phase_id.strip().upper()

    lanes: list[str] = []

    # 1. Explicit lane override
    if explicit_lane:
        if isinstance(explicit_lane, str):
            raw_entries = [entry.strip() for entry in explicit_lane.replace(",", ";").split(";") if entry.strip()]
        else:
            raw_entries = [entry.strip() for entry in explicit_lane if entry.strip()]
        lanes.extend(raw_entries)
    else:
        # 2. Check PHASE_TASKS.json
        tasks_file = find_phase_tasks_file(explicit_path=phase_tasks_path, repo_root=repo_root)
        found_in_tasks = False
        if tasks_file:
            try:
                with open(tasks_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for ph in data.get("phases", []):
                    ph_id = str(ph.get("id", "")).upper()
                    ph_num = f"PH{ph.get('phase', '')}".upper()
                    if ph_id == normalized_phase or ph_num == normalized_phase:
                        for ag in ph.get("agents", []):
                            if str(ag.get("agent_id", "")).upper() == normalized_agent:
                                raw_lane = ag.get("path_lane", "")
                                for entry in raw_lane.split(";"):
                                    entry_s = entry.strip()
                                    if entry_s:
                                        lanes.append(entry_s)
                                # Also allow listed acceptance artifacts
                                for artifact in ag.get("acceptance_artifacts", []):
                                    if artifact.strip():
                                        lanes.append(artifact.strip())
                                found_in_tasks = True
                                break
                        if found_in_tasks:
                            break
            except Exception:
                pass

        # 3. Fallback to default lanes
        if not found_in_tasks and normalized_agent in DEFAULT_AGENT_LANES:
            lanes.extend(DEFAULT_AGENT_LANES[normalized_agent])

    # 4. Invariant: Agent is always permitted its own phase artifact directory
    artifact_prefix = f"artifacts/{normalized_phase}/{normalized_agent}/"
    if artifact_prefix not in lanes:
        lanes.append(artifact_prefix)

    # 4b. Invariant: A10 is the phase-gate auditor and always permitted phase-gates
    if normalized_agent == "A10":
        if "artifacts/phase-gates/" not in lanes:
            lanes.append("artifacts/phase-gates/")

    # 5. Task-specific lane adjustments
    # PH02 A05 is assigned 'ownership and path ACL checker' in scripts/ci/
    if normalized_phase == "PH02" and normalized_agent == "A05":
        if "scripts/ci/" not in lanes:
            lanes.append("scripts/ci/")

    # 6. Extra lanes if requested
    if extra_lanes:
        for extra in extra_lanes:
            if extra.strip() and extra.strip() not in lanes:
                lanes.append(extra.strip())

    # De-duplicate while preserving order
    deduped: list[str] = []
    seen: set[str] = set()
    for lane in lanes:
        cleaned = posixpath.normpath(lane.strip().lstrip("/"))
        if lane.endswith("/") and not cleaned.endswith("/"):
            cleaned += "/"
        if cleaned not in seen:
            seen.add(cleaned)
            deduped.append(cleaned)

    return deduped


def is_path_allowed(file_path: str, allowed_lanes: Sequence[str]) -> bool:
    """Checks whether a single file path is allowed under any designated lane."""
    if not file_path or file_path == "/dev/null":
        return True

    norm_file = posixpath.normpath(file_path.strip().lstrip("/"))

    # Deny directory traversal out of root
    if norm_file.startswith("../") or norm_file == "..":
        return False

    for lane in allowed_lanes:
        lane_clean = lane.strip()
        if not lane_clean:
            continue

        norm_lane = posixpath.normpath(lane_clean.lstrip("/"))

        # 1. Exact path match (files or root directory match)
        if norm_file == norm_lane:
            return True

        # 2. Directory prefix match
        # If lane ends with / or norm_lane has no file extension (directory)
        if lane_clean.endswith("/") or not posixpath.splitext(norm_lane)[1]:
            dir_prefix = norm_lane if norm_lane.endswith("/") else norm_lane + "/"
            if norm_file.startswith(dir_prefix):
                return True

        # 3. Wildcard / Glob pattern match
        if any(c in lane_clean for c in "*?[]"):
            if fnmatch.fnmatch(norm_file, norm_lane):
                return True

    return False


def get_git_changed_files(
    base_sha: str | None = None,
    head_sha: str = "HEAD",
    repo_root: Path | None = None,
) -> list[str]:
    """Queries git for modified, added, renamed, or untracked files."""
    cwd = (repo_root or REPO_ROOT).resolve()
    files: set[str] = set()

    # 1. Diffs between base and head
    if base_sha:
        cmd = ["git", "diff", "--name-only", f"{base_sha}..{head_sha}"]
        res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                c = _clean_diff_path(line, repo_root=cwd)
                if c and c != "/dev/null":
                    files.add(c)

    # 2. Uncommitted changes and untracked files in the working directory
    cmd_status = ["git", "status", "--porcelain"]
    res_status = subprocess.run(cmd_status, cwd=cwd, capture_output=True, text=True, check=False)
    if res_status.returncode == 0:
        for line in res_status.stdout.splitlines():
            line_s = line.strip()
            if not line_s:
                continue
            entry = line[3:].strip()
            if " -> " in entry:
                for sub in entry.split(" -> "):
                    c = _clean_diff_path(sub, repo_root=cwd)
                    if c and c != "/dev/null":
                        files.add(c)
            else:
                c = _clean_diff_path(entry, repo_root=cwd)
                if c and c != "/dev/null":
                    files.add(c)

    return sorted(files)


def check_agent_path_acl(
    agent_id: str,
    phase_id: str,
    files: list[str] | None = None,
    diff_text: str | None = None,
    diff_file: Path | str | None = None,
    base_sha: str | None = None,
    head_sha: str = "HEAD",
    explicit_lane: str | list[str] | None = None,
    extra_lanes: list[str] | None = None,
    phase_tasks_path: Path | str | None = None,
    repo_root: Path | None = None,
) -> tuple[bool, list[str], list[str], list[str]]:
    """Evaluates files or git diffs against an agent's path lane.

    Returns:
        (passed, allowed_lanes, evaluated_files, violations)
    """
    root = (repo_root or REPO_ROOT).resolve()
    allowed_lanes = get_agent_path_lanes(
        agent_id=agent_id,
        phase_id=phase_id,
        phase_tasks_path=phase_tasks_path,
        explicit_lane=explicit_lane,
        extra_lanes=extra_lanes,
        repo_root=root,
    )

    evaluated_files: set[str] = set()

    # Priority 1: Explicit list of files
    if files:
        for f in files:
            c = _clean_diff_path(f, repo_root=root)
            if c and c != "/dev/null":
                evaluated_files.add(c)

    # Priority 2: Diff file
    if diff_file:
        df_path = Path(diff_file).resolve()
        if df_path.is_file():
            content = df_path.read_text(encoding="utf-8", errors="replace")
            for c in extract_changed_files_from_diff(content, repo_root=root):
                evaluated_files.add(c)

    # Priority 3: Diff text
    if diff_text:
        for c in extract_changed_files_from_diff(diff_text, repo_root=root):
            evaluated_files.add(c)

    # Priority 4: Git repository check
    if not evaluated_files and (base_sha or not (files or diff_file or diff_text)):
        for c in get_git_changed_files(base_sha=base_sha, head_sha=head_sha, repo_root=root):
            evaluated_files.add(c)

    eval_sorted = sorted(evaluated_files)
    violations: list[str] = []

    for f in eval_sorted:
        if not is_path_allowed(f, allowed_lanes):
            violations.append(f)

    passed = len(violations) == 0
    return passed, allowed_lanes, eval_sorted, violations


# ==============================================================================
# Self-Test Suite
# ==============================================================================


class AgentPathAclTestCase(unittest.TestCase):
    """Test suite for path ACL checking logic and diff parsing."""

    def test_allowed_files_pass(self) -> None:
        passed, _, _, violations = check_agent_path_acl(
            agent_id="A05",
            phase_id="PH02",
            files=[
                "apps/web/app/dashboard/page.tsx",
                "apps/web/components/ui/button.tsx",
                "apps/web/lib/utils.ts",
                "scripts/ci/check_agent_path_acl.py",
                "artifacts/PH02/A05/change_manifest.json",
            ],
        )
        self.assertTrue(passed)
        self.assertEqual(violations, [])

    def test_disallowed_files_fail(self) -> None:
        passed, _, _, violations = check_agent_path_acl(
            agent_id="A05",
            phase_id="PH02",
            files=[
                "apps/web/app/dashboard/page.tsx",
                "services/api/src/clara_api/main.py",
                "apps/mobile/lib/main.dart",
            ],
        )
        self.assertFalse(passed)
        self.assertIn("services/api/src/clara_api/main.py", violations)
        self.assertIn("apps/mobile/lib/main.dart", violations)
        self.assertEqual(len(violations), 2)

    def test_cross_agent_artifact_modification_rejected(self) -> None:
        passed, _, _, violations = check_agent_path_acl(
            agent_id="A05",
            phase_id="PH02",
            files=[
                "artifacts/PH02/A05/change_manifest.json",
                "artifacts/PH02/A02/change_manifest.json",
            ],
        )
        self.assertFalse(passed)
        self.assertIn("artifacts/PH02/A02/change_manifest.json", violations)
        self.assertEqual(len(violations), 1)

    def test_directory_boundary_safety(self) -> None:
        # apps/web/app/ must NOT allow apps/web/app_other.tsx
        lanes = ["apps/web/app/"]
        self.assertTrue(is_path_allowed("apps/web/app/page.tsx", lanes))
        self.assertTrue(is_path_allowed("apps/web/app/nested/foo.ts", lanes))
        self.assertFalse(is_path_allowed("apps/web/app_other.tsx", lanes))
        self.assertFalse(is_path_allowed("apps/web/package.json", lanes))

    def test_exact_file_lane(self) -> None:
        lanes = ["services/api/src/clara_api/schemas.py"]
        self.assertTrue(is_path_allowed("services/api/src/clara_api/schemas.py", lanes))
        self.assertFalse(is_path_allowed("services/api/src/clara_api/schemas.py.bak", lanes))
        self.assertFalse(is_path_allowed("services/api/src/clara_api/schemas_extra.py", lanes))

    def test_path_traversal_rejected(self) -> None:
        lanes = ["apps/web/app/"]
        self.assertFalse(is_path_allowed("../secret.txt", lanes))
        self.assertFalse(is_path_allowed("apps/web/app/../../services/api/main.py", lanes))

    def test_unified_diff_parsing(self) -> None:
        sample_diff = """
diff --git a/apps/web/app/page.tsx b/apps/web/app/page.tsx
index 1234567..89abcdef 100644
--- a/apps/web/app/page.tsx
+++ b/apps/web/app/page.tsx
@@ -1,3 +1,3 @@
-// old
+// new
diff --git a/services/api/src/clara_api/main.py b/services/api/src/clara_api/main.py
new file mode 100644
--- /dev/null
+++ b/services/api/src/clara_api/main.py
@@ -0,0 +1 @@
+# unauthorized change
"""
        extracted = extract_changed_files_from_diff(sample_diff)
        self.assertIn("apps/web/app/page.tsx", extracted)
        self.assertIn("services/api/src/clara_api/main.py", extracted)
        self.assertEqual(len(extracted), 2)

        passed, _, _, violations = check_agent_path_acl(
            agent_id="A05",
            phase_id="PH02",
            diff_text=sample_diff,
        )
        self.assertFalse(passed)
        self.assertEqual(violations, ["services/api/src/clara_api/main.py"])

    def test_diff_rename_detection(self) -> None:
        sample_diff = """
diff --git a/apps/web/old_name.ts b/apps/web/app/new_name.ts
similarity index 100%
rename from apps/web/old_name.ts
rename to apps/web/app/new_name.ts
"""
        extracted = extract_changed_files_from_diff(sample_diff)
        self.assertIn("apps/web/old_name.ts", extracted)
        self.assertIn("apps/web/app/new_name.ts", extracted)

    def test_git_status_porcelain_parsing(self) -> None:
        sample_status = """
M  apps/web/app/page.tsx
A  scripts/ci/check_agent_path_acl.py
?? artifacts/PH02/A05/change_manifest.json
"""
        extracted = extract_changed_files_from_diff(sample_status)
        self.assertEqual(
            extracted,
            [
                "apps/web/app/page.tsx",
                "artifacts/PH02/A05/change_manifest.json",
                "scripts/ci/check_agent_path_acl.py",
            ],
        )

    def test_explicit_lane_override(self) -> None:
        passed, lanes, _, violations = check_agent_path_acl(
            agent_id="A05",
            phase_id="PH02",
            explicit_lane="custom/folder/;another/file.py",
            files=["custom/folder/sub.ts", "another/file.py"],
        )
        self.assertTrue(passed)
        self.assertEqual(violations, [])
        self.assertTrue(any("custom/folder" in l for l in lanes))


# ==============================================================================
# CLI Entry Point
# ==============================================================================


def run_self_tests() -> int:
    """Runs internal unittest test suite."""
    suite = unittest.TestLoader().loadTestsFromTestCase(AgentPathAclTestCase)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify git diff or file list against designated agent path lane.",
    )
    parser.add_argument(
        "positional_args",
        nargs="*",
        help="Optional positional args: [agent_id] [phase_id] [files... or - for stdin]",
    )
    parser.add_argument(
        "-a", "--agent", "--agent-id",
        dest="agent_id",
        help="Agent identifier (e.g. A01..A10)",
    )
    parser.add_argument(
        "-p", "--phase", "--phase-id",
        dest="phase_id",
        help="Phase identifier (e.g. PH00..PH10)",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        help="List of file paths to check against the designated path lane",
    )
    parser.add_argument(
        "--diff",
        dest="diff_input",
        help="Unified diff text or path to a diff patch file",
    )
    parser.add_argument(
        "--base", "--base-sha",
        dest="base_sha",
        help="Git base SHA / commit reference to diff against",
    )
    parser.add_argument(
        "--head", "--head-sha",
        dest="head_sha",
        default="HEAD",
        help="Git head reference (default: HEAD)",
    )
    parser.add_argument(
        "--path-lane",
        dest="explicit_lane",
        help="Override or specify exact path lane (semicolon or comma delimited)",
    )
    parser.add_argument(
        "--extra-lane",
        action="append",
        dest="extra_lanes",
        help="Additional allowed path prefix(es)",
    )
    parser.add_argument(
        "--phase-tasks",
        dest="phase_tasks_path",
        help="Explicit path to PHASE_TASKS.json",
    )
    parser.add_argument(
        "--repo-root",
        dest="repo_root",
        help="Explicit repository or worktree root directory",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print verbose evaluation details",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="Execute internal verification test suite",
    )

    args = parser.parse_args(argv)

    if args.selftest:
        return run_self_tests()

    # Process positional arguments if flags omitted
    pos_args = list(args.positional_args)
    agent_id = args.agent_id
    phase_id = args.phase_id
    files = list(args.files) if args.files else []
    read_stdin = False

    if not agent_id and pos_args:
        candidate = pos_args.pop(0)
        if re.match(r"^[aA]\d+$", candidate):
            agent_id = candidate
        else:
            pos_args.insert(0, candidate)

    if not phase_id and pos_args:
        candidate = pos_args.pop(0)
        if re.match(r"^[pP][hH]?\d+$", candidate):
            phase_id = candidate
        else:
            pos_args.insert(0, candidate)

    # Any remaining positional args
    for item in pos_args:
        if item == "-":
            read_stdin = True
        else:
            files.append(item)

    if not agent_id:
        print("[ERROR] Agent ID required (e.g. --agent-id A05 or positional arg)", file=sys.stderr)
        return 2

    if not phase_id:
        phase_id = "PH02"  # Default to current execution phase if omitted

    # Read stdin if explicitly requested or if piped
    diff_text: str | None = None
    diff_file: str | None = None

    if read_stdin or (not sys.stdin.isatty() and not files and not args.diff_input and not args.base_sha):
        try:
            stdin_content = sys.stdin.read()
            if stdin_content.strip():
                diff_text = stdin_content
        except Exception as e:
            print(f"[ERROR] Failed to read from stdin: {e}", file=sys.stderr)
            return 2

    if args.diff_input:
        if Path(args.diff_input).is_file():
            diff_file = args.diff_input
        else:
            diff_text = args.diff_input

    effective_repo_root = (
        Path(args.repo_root).resolve() if args.repo_root else _detect_repo_root()
    )

    passed, allowed_lanes, evaluated_files, violations = check_agent_path_acl(
        agent_id=agent_id,
        phase_id=phase_id,
        files=files if files else None,
        diff_text=diff_text,
        diff_file=diff_file,
        base_sha=args.base_sha,
        head_sha=args.head_sha,
        explicit_lane=args.explicit_lane,
        extra_lanes=args.extra_lanes,
        phase_tasks_path=args.phase_tasks_path,
        repo_root=effective_repo_root,
    )

    if args.json:
        payload = {
            "status": "PASS" if passed else "FAIL",
            "exit_code": 0 if passed else 1,
            "agent_id": agent_id.upper(),
            "phase_id": phase_id.upper(),
            "allowed_lanes": allowed_lanes,
            "evaluated_files_count": len(evaluated_files),
            "evaluated_files": evaluated_files,
            "violations_count": len(violations),
            "violations": violations,
        }
        print(json.dumps(payload, indent=2))
        return 0 if passed else 1

    # Text report
    print("=" * 80)
    if passed:
        print(f"PATH ACL CHECKER — PASSED (Agent: {agent_id.upper()}, Phase: {phase_id.upper()})")
    else:
        print(f"PATH ACL CHECKER — VIOLATION DETECTED (Agent: {agent_id.upper()}, Phase: {phase_id.upper()})")
    print("=" * 80)
    print(f"Evaluated Files : {len(evaluated_files)}")
    print(f"Allowed Lanes   : {len(allowed_lanes)}")
    for lane in allowed_lanes:
        print(f"  - {lane}")

    if args.verbose or not passed:
        print("\nEvaluated Changes:")
        if not evaluated_files:
            print("  (No modified files detected)")
        for f in evaluated_files:
            status_tag = "[FAIL]" if f in violations else "[OK]  "
            print(f"  {status_tag} {f}")

    if not passed:
        print("\n" + "!" * 80)
        print(f"PATH ACL VIOLATIONS ({len(violations)}):")
        for v in violations:
            print(f"  [DISALLOWED] {v}")
        print("!" * 80)
        print("Remediation: An agent must not modify files outside its designated path lane.")
        print("Revert changes or file a DEPENDENCY_REQUEST.md for the owning agent.")
        return 1

    print("\nResult: All touched files conform strictly to the designated path lane.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
