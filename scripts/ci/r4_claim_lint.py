#!/usr/bin/env python3
"""GLHS R4 Claim Lint & Prohibited Phrase Checker.

Enforces that manuscripts, docstrings, and protocol documents do not contain
prohibited overclaims regarding semantic neural consumption, unearned priority,
or unproven equivalence bounds.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

BANNED_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"proves?\s+semantic\s+(?:model\s+)?consumption", re.IGNORECASE),
        "Overclaim: Neural semantic consumption cannot be proven by server dispatch. Use 'server-attested disclosure supply'.",
    ),
    (
        re.compile(r"first\s+transactional\s+ai\s+memory", re.IGNORECASE),
        "Overclaim: Unearned priority claim 'first transactional AI memory'.",
    ),
    (
        re.compile(r"proves?\s+what\s+the\s+model\s+(?:internally\s+)?consumed", re.IGNORECASE),
        "Overclaim: Internal model consumption is out of scope. Use 'server-attested disclosure supply'.",
    ),
    (
        re.compile(r"needs\s+N\s*=\s*384\s+to\s+prove\s+±\s*2%", re.IGNORECASE),
        "Overclaim: Unbacked power claim. Clarify N=384 was the original prospective plan.",
    ),
]

SCAN_TARGETS = [
    REPO_ROOT / "research" / "glhs_journal" / "q4_r4",
    REPO_ROOT / "docs" / "formal",
]


def lint_file(path: Path) -> list[str]:
    violations: list[str] = []
    # Skip binary files or gitkeep
    if path.suffix in (".png", ".jpg", ".sha256", ".cpython-312.pyc", ".pyc") or path.name in (".gitkeep", "r4_blocker_ledger.json"):
        return violations

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return violations

    for pattern, explanation in BANNED_PATTERNS:
        matches = list(pattern.finditer(text))
        for m in matches:
            lineno = text.count("\n", 0, m.start()) + 1
            line = text.splitlines()[lineno - 1] if lineno <= len(text.splitlines()) else ""
            # If the line explicitly lists forbidden phrases as an example of what NOT to say, skip
            if "Forbidden" in line or "Do NOT claim" in line or "NO " in line:
                continue
            matched_str = m.group(0)
            violations.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: Found '{matched_str}' -> {explanation}")

    return violations


def main() -> int:
    print("================================================================================")
    print("GLHS R4 — PROHIBITED PHRASE & CLAIM LINT SWEEP")
    print("================================================================================\n")

    total_violations = 0
    scanned_count = 0

    for target in SCAN_TARGETS:
        if target.is_file():
            files = [target]
        elif target.is_dir():
            files = list(target.rglob("*"))
        else:
            continue

        for f in files:
            if f.is_file():
                scanned_count += 1
                v = lint_file(f)
                if v:
                    total_violations += len(v)
                    for err in v:
                        print(f"[FAIL] {err}")

    print(f"\nScanned {scanned_count} files across R4 directories.")
    if total_violations == 0:
        print(">>> SUCCESS: 0 prohibited phrases detected. All claims compliant with R4 budget. <<<\n")
        return 0
    else:
        print(f">>> FAILED: Found {total_violations} claim violations requiring remediation. <<<\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
