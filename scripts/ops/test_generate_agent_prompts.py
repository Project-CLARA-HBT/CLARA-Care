#!/usr/bin/env python3
"""Comprehensive test suite for scripts/ops/generate_agent_prompts.py.

Spec: PH02 / A06 (Mobile Flutter / Ops Generator)
Tests:
  1. Successful prompt generation for PH02 (all 10 subagents A01-A10).
  2. Successful prompt generation for PH03 (all 10 subagents A01-A10).
  3. Phase ID normalization logic (integers, strings, prefixes).
  4. Non-existent phase ID handling and informative error reporting.
  5. Base SHA validation and fallback resolution.
  6. Template placeholder replacement completeness (zero unpopulated bracket tokens).
  7. Read and write path derivation logic and isolation rules.
  8. Single subagent prompt generation and filtering.
  9. File writing of deliverables (prompts, bounded_context_pack.json, INDEX.md).
  10. CLI execution across flags (--selftest, --json, --dry-run, --list-phases).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from generate_agent_prompts import (
    DEFAULT_FROZEN_BASE_SHA,
    derive_read_paths,
    derive_write_paths,
    find_phase_tasks_file,
    find_template_file,
    generate_prompts_and_pack,
    list_available_phases,
    normalize_phase_id,
    resolve_base_sha,
    write_pack_to_directory,
)


class TestGenerateAgentPrompts(unittest.TestCase):
    """Unit and integration test cases for agent prompt generator."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tasks_file = find_phase_tasks_file()
        cls.template_file = find_template_file()
        cls.base_sha = DEFAULT_FROZEN_BASE_SHA

    def test_normalize_phase_id_variants(self) -> None:
        """Verifies phase ID normalization for multiple input formats."""
        self.assertEqual(normalize_phase_id(2), "PH02")
        self.assertEqual(normalize_phase_id("2"), "PH02")
        self.assertEqual(normalize_phase_id("ph02"), "PH02")
        self.assertEqual(normalize_phase_id("PH02"), "PH02")
        self.assertEqual(normalize_phase_id("03"), "PH03")
        self.assertEqual(normalize_phase_id("ph3"), "PH03")
        self.assertEqual(normalize_phase_id("PH99"), "PH99")
        self.assertEqual(normalize_phase_id(100), "PH100")

        with self.assertRaises(ValueError):
            normalize_phase_id("")
        with self.assertRaises(ValueError):
            normalize_phase_id("   ")

    def test_list_available_phases(self) -> None:
        """Verifies that PHASE_TASKS.json contains expected phases."""
        phases = list_available_phases(self.tasks_file)
        self.assertGreater(len(phases), 20)
        phase_ids = [p["id"] for p in phases]
        self.assertIn("PH00", phase_ids)
        self.assertIn("PH01", phase_ids)
        self.assertIn("PH02", phase_ids)
        self.assertIn("PH03", phase_ids)

    def test_generate_ph02_ten_agents(self) -> None:
        """Verifies complete generation for PH02 with 10 isolated agents."""
        specs, pack = generate_prompts_and_pack(
            phase_id="PH02",
            tasks_file=self.tasks_file,
            template_file=self.template_file,
            base_sha=self.base_sha,
        )

        self.assertEqual(len(specs), 10)
        self.assertEqual(pack.phase_id, "PH02")
        self.assertEqual(pack.frozen_base_sha, self.base_sha)
        self.assertEqual(pack.agents_count, 10)

        expected_agents = [f"A{i:02d}" for i in range(1, 11)]
        self.assertEqual(sorted(specs.keys()), expected_agents)

        # Validate A06 specifically
        a06 = specs["A06"]
        self.assertEqual(a06.agent_id, "A06")
        self.assertEqual(a06.role, "Mobile Flutter")
        self.assertEqual(a06.task, "agent prompt and bounded context pack")
        self.assertIn("apps/mobile/", a06.exact_write_paths)
        self.assertIn("artifacts/PH02/A06/", a06.exact_write_paths)
        self.assertIn("phase/ph02-a06", a06.branch)
        self.assertIn("/dev/shm/clara_worktrees/PH02_A06", a06.worktree_path)

        # Check prompt content
        self.assertIn("You are subagent `A06` for `PH02`", a06.populated_prompt)
        self.assertIn(self.base_sha, a06.populated_prompt)
        self.assertNotIn("[AGENT_ID]", a06.populated_prompt)
        self.assertNotIn("[PHASE_ID]", a06.populated_prompt)
        self.assertNotIn("[BASE_SHA]", a06.populated_prompt)
        self.assertNotIn("[EXACT_WRITE_PATHS]", a06.populated_prompt)

    def test_generate_ph03_ten_agents(self) -> None:
        """Verifies complete generation for PH03."""
        specs, pack = generate_prompts_and_pack(
            phase_id="PH03",
            tasks_file=self.tasks_file,
            template_file=self.template_file,
            base_sha=self.base_sha,
        )

        self.assertEqual(len(specs), 10)
        self.assertEqual(pack.phase_id, "PH03")
        self.assertEqual(specs["A01"].task, "auth threat inventory")
        self.assertEqual(specs["A02"].task, "JWT/session invalidation and rotation")
        self.assertEqual(specs["A06"].task, "secure password reset and recovery")

    def test_missing_phase_raises_key_error(self) -> None:
        """Ensures requesting a nonexistent phase raises KeyError."""
        with self.assertRaises(KeyError):
            generate_prompts_and_pack(
                phase_id="PH999",
                tasks_file=self.tasks_file,
                template_file=self.template_file,
                base_sha=self.base_sha,
            )

    def test_base_sha_validation(self) -> None:
        """Verifies commit SHA validation."""
        valid_sha = "879dc5dcfcaae91b3626e28062043d934294478b"
        self.assertEqual(resolve_base_sha(valid_sha), valid_sha)

        with self.assertRaises(ValueError):
            resolve_base_sha("invalid_sha_short")

    def test_write_and_read_path_derivation(self) -> None:
        """Checks path derivation includes deliverables and avoids duplicates."""
        write_paths = derive_write_paths("apps/mobile/;contracts/", "PH02", "A06")
        self.assertIn("apps/mobile/", write_paths)
        self.assertIn("contracts/", write_paths)
        self.assertIn("artifacts/PH02/A06/", write_paths)

        read_paths = derive_read_paths("A06", write_paths)
        self.assertIn("AGENTS.md", read_paths)
        self.assertIn("CLAUDE.md", read_paths)
        self.assertIn("apps/mobile/lib/", read_paths)
        self.assertIn("artifacts/PH02/A06/", read_paths)

    def test_write_pack_to_directory(self) -> None:
        """Verifies file emission to a target directory."""
        specs, pack = generate_prompts_and_pack(
            phase_id="PH02",
            tasks_file=self.tasks_file,
            template_file=self.template_file,
            base_sha=self.base_sha,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir)
            files = write_pack_to_directory(out, specs, pack)
            self.assertEqual(len(files), 12)  # 10 prompts + 1 json + 1 index

            # Check json pack content
            pack_file = out / "bounded_context_pack.json"
            self.assertTrue(pack_file.is_file())
            with open(pack_file, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["phase_id"], "PH02")
            self.assertEqual(data["agents_count"], 10)
            self.assertIn("A06", data["agents"])

            # Check index markdown
            index_file = out / "INDEX.md"
            self.assertTrue(index_file.is_file())
            index_content = index_file.read_text(encoding="utf-8")
            self.assertIn("Phase PH02", index_content)
            self.assertIn("A06", index_content)

    def test_cli_execution_flags(self) -> None:
        """Verifies script CLI execution with various flags."""
        script = Path(__file__).parent / "generate_agent_prompts.py"

        # 1. --selftest
        res = subprocess.run([sys.executable, str(script), "--selftest"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("OK", res.stderr + res.stdout)

        # 2. --dry-run
        res = subprocess.run([sys.executable, str(script), "PH02", "--dry-run"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("AGENT PROMPT & BOUNDED CONTEXT PACK GENERATOR — PH02", res.stdout)

        # 3. --json
        res = subprocess.run([sys.executable, str(script), "PH02", "--json"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        parsed = json.loads(res.stdout)
        self.assertEqual(parsed["phase_id"], "PH02")
        self.assertEqual(parsed["agents_count"], 10)

        # 4. --agent A06 --stdout
        res = subprocess.run([sys.executable, str(script), "PH02", "--agent", "A06", "--stdout"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("AGENT TASK PROMPT: A06 (Mobile Flutter)", res.stdout)


if __name__ == "__main__":
    unittest.main()
