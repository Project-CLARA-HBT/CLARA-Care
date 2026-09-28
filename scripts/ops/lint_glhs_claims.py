#!/usr/bin/env python3
"""Automated Claim Linter for GLHS R3 Manuscripts and Documentation.

Enforces the 7 forbidden claim categories defined in `claim_budget.json`:
  1. PRIORITY_OR_FIRST
  2. ABSOLUTE_SECURITY
  3. CLINICAL_EFFICACY
  4. MECHANISM_UNIQUENESS
  5. UNBACKED_PROVIDER_CLAIM
  6. SIMULATION_AS_PRODUCTION
  7. INTERNAL_AGENT_ADJUDICATION

Usage:
    python3 scripts/ops/lint_glhs_claims.py [file_path ...]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLAIM_BUDGET_PATH = REPO_ROOT / "research" / "glhs_journal" / "q3_r3" / "claim_budget.json"


def lint_file(file_path: Path, forbidden_claims: list[dict]) -> list[str]:
    """Lint a single file against forbidden claim regexes."""
    if not file_path.exists():
        return [f"File not found: {file_path}"]

    text = file_path.read_text(encoding="utf-8")
    violations = []

    for rule in forbidden_claims:
        category = rule["category"]
        regex_pattern = rule.get("regex")
        if not regex_pattern:
            continue

        pat = re.compile(regex_pattern, re.IGNORECASE)
        for line_idx, line in enumerate(text.splitlines(), start=1):
            match = pat.search(line)
            if match:
                violations.append(
                    f"[{category}] {file_path.name}:{line_idx} — Match: '{match.group(0)}'\n"
                    f"  Line: {line.strip()}\n"
                    f"  Rationale: {rule.get('rationale', 'Violates claim budget')}"
                )

    return violations


def main() -> None:
    if not CLAIM_BUDGET_PATH.exists():
        print(f"Error: Claim budget file missing at {CLAIM_BUDGET_PATH}", file=sys.stderr)
        sys.exit(1)

    with CLAIM_BUDGET_PATH.open("r", encoding="utf-8") as f:
        budget_data = json.load(f)

    forbidden_claims = budget_data.get("forbidden_claims", [])

    if len(sys.argv) > 1:
        target_paths = [Path(arg) for arg in sys.argv[1:]]
    else:
        # Default target paths: Q3 R3 manuscript files and master specs
        target_paths = [
            REPO_ROOT / "research" / "glhs_journal" / "q3_r3" / "MANUSCRIPT_MASTER_R3.md",
            REPO_ROOT / "research" / "glhs_journal" / "q3_r3" / "manuscript_introduction_rewrite.md",
            REPO_ROOT / "research" / "glhs_journal" / "q3_r3" / "manuscript_methods_rewrite.md",
            REPO_ROOT / "research" / "glhs_journal" / "q3_r3" / "manuscript_results_rewrite.md",
        ]

    total_violations = []
    files_audited = 0

    for path in target_paths:
        if path.exists():
            files_audited += 1
            file_violations = lint_file(path, forbidden_claims)
            if file_violations:
                total_violations.extend(file_violations)

    print(f"==================================================================")
    print(f" GLHS R3 AUTOMATED CLAIM LINTER (Audited {files_audited} files)")
    print(f" Budget Specification: research/glhs_journal/q3_r3/claim_budget.json")
    print(f"==================================================================")

    if total_violations:
        print(f"FAIL: Found {len(total_violations)} claim budget violations:\n", file=sys.stderr)
        for v in total_violations:
            print(v, file=sys.stderr)
            print("-" * 60, file=sys.stderr)
        sys.exit(1)
    else:
        print("[PASS] Zero claim budget violations detected across all audited manuscript files.")
        sys.exit(0)


if __name__ == "__main__":
    main()
