#!/usr/bin/env python3
"""Static guard for the CI/CD no-raw-log artifact policy."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = (
    ROOT / ".github/workflows/ci.yml",
    ROOT / ".github/workflows/cd.yml",
)


def _non_comment_lines(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("#")]


def main() -> int:
    failures: list[str] = []
    for workflow in WORKFLOWS:
        lines = _non_comment_lines(workflow)
        for number, line in enumerate(lines, start=1):
            if "docker compose" in line and " logs" in line:
                failures.append(f"{workflow.relative_to(ROOT)}:{number} invokes raw docker compose logs")
        if not any("check_ci_artifact_safety.py" in line for line in lines):
            failures.append(f"{workflow.relative_to(ROOT)} does not invoke the artifact safety guard")

    deploy_compose = ROOT / "deploy/docker/docker-compose.deploy.yml"
    deploy_text = deploy_compose.read_text(encoding="utf-8")
    if "SEARXNG_SECRET: ${SEARXNG_SECRET:?" not in deploy_text:
        failures.append("production compose does not require SEARXNG_SECRET")

    settings = ROOT / "deploy/docker/searxng/settings.yml"
    if "clara-searxng-change-this-secret" in settings.read_text(encoding="utf-8"):
        failures.append("SearXNG settings retain the old shared static secret")

    if failures:
        for failure in failures:
            print(f"[artifact-policy] {failure}", file=sys.stderr)
        return 1

    print("[artifact-policy] CI/CD uploads no raw compose logs and production requires SearXNG_SECRET")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
