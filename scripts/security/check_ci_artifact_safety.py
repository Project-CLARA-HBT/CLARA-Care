#!/usr/bin/env python3
"""Fail closed before CI/CD uploads a diagnostic artifact.

The command is intentionally narrow: it is for small, machine-generated health
and compose-status artifacts only. It does not claim to de-identify arbitrary
logs or clinical content. Raw container logs are therefore never an accepted
input; operators must retrieve them from the controlled runtime with the
incident process in ``docs/runbooks/ci-artifact-safety.md``.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email", re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")),
    ("phone", re.compile(r"(?<!\d)(?:\+?84|0)\s?(?:\d[ .-]?){8,10}\d(?!\d)")),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{12,}")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "credential_assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|authorization|cookie|password|secret|token|"
            r"database_url|jwt_secret(?:_key)?)\s*[:=]\s*(?!\[REDACTED\])\S+"
        ),
    ),
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="artifact files to inspect")
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="ignore a missing optional artifact path",
    )
    return parser.parse_args()


def _find_violation(path: Path) -> str | None:
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"cannot read ({exc.__class__.__name__})"

    for rule_name, pattern in RULES:
        if pattern.search(content):
            return rule_name
    return None


def main() -> int:
    args = _parse_args()
    failed = False
    checked = 0
    for path in args.paths:
        if not path.exists():
            if args.allow_missing:
                continue
            print(f"[artifact-safety] missing required artifact: {path}", file=sys.stderr)
            failed = True
            continue
        if not path.is_file():
            print(f"[artifact-safety] artifact is not a file: {path}", file=sys.stderr)
            failed = True
            continue
        checked += 1
        violation = _find_violation(path)
        if violation:
            print(
                f"[artifact-safety] refusing upload of {path}: matched {violation}; "
                "do not upload raw logs or clinical content",
                file=sys.stderr,
            )
            failed = True

    if not checked:
        print("[artifact-safety] no artifact files were available to inspect", file=sys.stderr)
        return 1
    if failed:
        return 1
    print(f"[artifact-safety] checked {checked} diagnostic artifact(s): no basic secret/PII marker")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
