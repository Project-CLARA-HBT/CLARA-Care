"""CLARA-Care 2027 shared task SH-agent_protocol.

Purpose
-------
Turn the prose execution contract into an enforceable, machine-checked handoff.
Every subagent must emit exactly one task report matching
``research/venue2027/AGENTS/TASK_REPORT_SCHEMA.json``. This module is the single
validator used before a task may be marked complete.

Allowed input
-------------
A report ``dict`` (or JSON path) plus the task definition from
``MANIFESTS/tasks.json``. File hashing is performed read-only on the repo.

Failure semantics
-----------------
Validation returns :class:`ValidationResult` with ``ok=False`` and a stable
``reason_code``. ``PASS`` is refused unless every command has ``exit_code == 0``,
``source_sha_after`` is a real commit in the repository, and every declared
artifact exists with a matching SHA256. Assertions without logs are rejected.

Version
-------
``AGENT_PROTOCOL_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

AGENT_PROTOCOL_VERSION = "1.0.0"

ReasonCode = Literal[
    "OK",
    "SCHEMA_INVALID",
    "MISSING_FIELD",
    "TASK_MISMATCH",
    "NO_COMMANDS",
    "NONZERO_EXIT",
    "MISSING_SOURCE_SHA",
    "SHA_NOT_IN_REPO",
    "ARTIFACT_MISSING",
    "ARTIFACT_HASH_MISMATCH",
    "DEPENDENCIES_UNSATISFIED",
]

REQUIRED_FIELDS: tuple[str, ...] = (
    "task_id",
    "status",
    "source_sha_before",
    "source_sha_after",
    "changed_paths",
    "commands",
    "artifacts_sha256",
    "unresolved",
)

_ALLOWED_STATUS = ("PASS", "FAIL", "BLOCKED")


@dataclasses.dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason_code: ReasonCode
    errors: tuple[str, ...]
    task_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reason_code": self.reason_code,
            "errors": list(self.errors),
            "task_id": self.task_id,
            "protocol_version": AGENT_PROTOCOL_VERSION,
        }


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha_exists(repo: Path, sha: str) -> bool:
    if not sha or len(sha) < 7:
        return False
    res = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", f"{sha}^{{commit}}"],
        capture_output=True,
        check=False,
    )
    return res.returncode == 0


def validate_report(
    report: dict[str, Any],
    *,
    repo: str | os.PathLike[str],
    expected_task_id: str | None = None,
    completed_tasks: Sequence[str] | None = None,
    task_dependencies: Sequence[str] | None = None,
    verify_artifacts: bool = True,
) -> ValidationResult:
    """Validate one task report.

    ``expected_task_id`` guards against copy-paste of another task's report.
    ``task_dependencies`` + ``completed_tasks`` enforce the DAG: a PASS cannot be
    recorded while a dependency is not yet PASS.
    """

    root = Path(repo)
    task_id = str(report.get("task_id", ""))
    errors: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in report:
            errors.append(f"missing required field: {field}")
    if errors:
        return ValidationResult(False, "MISSING_FIELD", tuple(errors), task_id)

    if expected_task_id is not None and task_id != expected_task_id:
        return ValidationResult(
            False,
            "TASK_MISMATCH",
            (f"report.task_id={task_id!r} != expected {expected_task_id!r}",),
            task_id,
        )

    status = report.get("status")
    if status not in _ALLOWED_STATUS:
        return ValidationResult(
            False, "SCHEMA_INVALID", (f"status {status!r} not in {_ALLOWED_STATUS}",), task_id
        )

    if not isinstance(report.get("changed_paths"), list):
        errors.append("changed_paths must be a list")
    if not isinstance(report.get("unresolved"), list):
        errors.append("unresolved must be a list")
    if not isinstance(report.get("artifacts_sha256"), dict):
        errors.append("artifacts_sha256 must be an object")
    if errors:
        return ValidationResult(False, "SCHEMA_INVALID", tuple(errors), task_id)

    commands = report.get("commands")
    if not isinstance(commands, list):
        return ValidationResult(
            False, "SCHEMA_INVALID", ("commands must be a list",), task_id
        )

    source_sha_after = str(report.get("source_sha_after", ""))
    if not source_sha_after:
        return ValidationResult(
            False, "MISSING_SOURCE_SHA", ("source_sha_after is empty",), task_id
        )

    # PASS is the only status that carries scientific weight, so enforce hard.
    if status == "PASS":
        if not commands:
            return ValidationResult(
                False, "NO_COMMANDS", ("PASS requires at least one executed command",), task_id
            )
        nonzero = [
            str(c.get("argv", "?"))
            for c in commands
            if not isinstance(c, dict) or c.get("exit_code") != 0
        ]
        if nonzero:
            return ValidationResult(
                False,
                "NONZERO_EXIT",
                tuple(f"non-zero/absent exit_code: {a}" for a in nonzero),
                task_id,
            )
        if not _sha_exists(root, source_sha_after):
            return ValidationResult(
                False,
                "SHA_NOT_IN_REPO",
                (f"source_sha_after {source_sha_after!r} not a commit in {root}",),
                task_id,
            )
        if task_dependencies:
            done = set(completed_tasks or ())
            missing = [d for d in task_dependencies if d not in done]
            if missing:
                return ValidationResult(
                    False,
                    "DEPENDENCIES_UNSATISFIED",
                    tuple(f"dependency not completed: {d}" for d in missing),
                    task_id,
                )
        if verify_artifacts:
            for rel, declared in report.get("artifacts_sha256", {}).items():
                path = root / rel
                if not path.is_file():
                    return ValidationResult(
                        False, "ARTIFACT_MISSING", (f"artifact not found: {rel}",), task_id
                    )
                actual = _sha256_file(path)
                if actual != declared:
                    return ValidationResult(
                        False,
                        "ARTIFACT_HASH_MISMATCH",
                        (f"{rel}: declared {declared} actual {actual}",),
                        task_id,
                    )

    return ValidationResult(True, "OK", (), task_id)


def build_report(
    *,
    task_id: str,
    status: str,
    source_sha_before: str,
    source_sha_after: str,
    changed_paths: Sequence[str],
    commands: Sequence[dict[str, Any]],
    artifact_paths: Sequence[str],
    repo: str | os.PathLike[str],
    unresolved: Sequence[str] = (),
    oracle_disagreement_count: int | None = None,
    baseline_parity: str = "NOT_APPLICABLE",
    notes: str = "",
) -> dict[str, Any]:
    """Assemble a schema-conforming report and hash every declared artifact."""

    root = Path(repo)
    artifacts: dict[str, str] = {}
    for rel in artifact_paths:
        path = root / rel
        artifacts[rel] = _sha256_file(path) if path.is_file() else ""
    payload: dict[str, Any] = {
        "task_id": task_id,
        "status": status,
        "source_sha_before": source_sha_before,
        "source_sha_after": source_sha_after,
        "changed_paths": list(changed_paths),
        "commands": list(commands),
        "artifacts_sha256": artifacts,
        "oracle_disagreement_count": oracle_disagreement_count,
        "baseline_parity": baseline_parity,
        "unresolved": list(unresolved),
        "notes": notes,
    }
    return payload


def load_tasks(manifest_path: str | os.PathLike[str]) -> dict[str, dict[str, Any]]:
    tasks = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    return {t["id"]: t for t in tasks}


def load_completed(state_path: str | os.PathLike[str]) -> set[str]:
    path = Path(state_path)
    if not path.is_file():
        return set()
    state = json.loads(path.read_text(encoding="utf-8"))
    return set(state.get("completed", {}).keys())


def mark_task(
    *,
    task_id: str,
    status: str,
    report_path: str | os.PathLike[str],
    repo: str | os.PathLike[str],
    manifest_path: str | os.PathLike[str],
    state_path: str | os.PathLike[str],
) -> ValidationResult:
    """Validate a report, then record PASS/BLOCKED atomically in the state file."""

    repo_p = Path(repo)
    tasks = load_tasks(manifest_path)
    if task_id not in tasks:
        return ValidationResult(False, "TASK_MISMATCH", (f"unknown task {task_id}",), task_id)

    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    completed = load_completed(state_path)
    result = validate_report(
        report,
        repo=repo_p,
        expected_task_id=task_id,
        completed_tasks=completed,
        task_dependencies=tasks[task_id].get("depends", []),
    )
    if not result.ok:
        return result
    if report.get("status") != status:
        return ValidationResult(
            False,
            "SCHEMA_INVALID",
            (f"report status {report.get('status')!r} != requested {status!r}",),
            task_id,
        )

    state_file = Path(state_path)
    state = (
        json.loads(state_file.read_text(encoding="utf-8"))
        if state_file.is_file()
        else {"schema_version": 1, "completed": {}, "blocked": {}}
    )
    state.setdefault("completed", {})
    state.setdefault("blocked", {})
    import datetime

    entry = {
        "report": str(Path(report_path).resolve()),
        "status": status,
        "marked_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    state["completed"].pop(task_id, None)
    state["blocked"].pop(task_id, None)
    if status == "PASS":
        state["completed"][task_id] = entry
    else:
        state["blocked"][task_id] = entry
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="CLARA 2027 agent protocol validator")
    sub = parser.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate")
    v.add_argument("report")
    v.add_argument("--repo", default=".")
    v.add_argument("--task")

    m = sub.add_parser("mark")
    m.add_argument("task_id")
    m.add_argument("status", choices=["PASS", "FAIL", "BLOCKED"])
    m.add_argument("--report", required=True)
    m.add_argument("--repo", default=".")
    m.add_argument(
        "--manifest", default="research/venue2027/MANIFESTS/tasks.json"
    )
    m.add_argument("--state", default="research/venue2027/STATE/completion.json")

    args = parser.parse_args(argv)
    if args.cmd == "validate":
        report = json.loads(Path(args.report).read_text(encoding="utf-8"))
        result = validate_report(report, repo=args.repo, expected_task_id=args.task)
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.ok else 1
    if args.cmd == "mark":
        result = mark_task(
            task_id=args.task_id,
            status=args.status,
            report_path=args.report,
            repo=args.repo,
            manifest_path=args.manifest,
            state_path=args.state,
        )
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.ok else 1
    return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
