"""CLARA-Care 2027 shared task SH-incident_repro.

Purpose
-------
Reproduce the known R4 append-only regression deterministically. The incident is
``ValueError: GLHS ledger rows are immutable; append a governed transition``
raised by the SQLAlchemy ``before_update`` listener on
``GlhsClinicalCommitmentProposal`` when the admission path writes the
``admission_decision`` / ``sealed_at`` projection fields.

This module is a *reproducer*, not a fix. It exits 0 only when the incident is
observed exactly as documented (same failing test ids and same reason string),
which is the evidence SH-guard_regression and SH-repair_immutable depend on.

Allowed input
-------------
Repository root plus the pytest target list from
``.github/workflows/glhs-r4-novelty-gate.yml``.

Failure semantics
-----------------
- Incident reproduced (expected failing ids + reason present) -> exit 0.
- Incident NOT reproduced (tests pass, or different failures) -> exit 1 with
  ``reason_code`` describing the divergence. Never reported as success.

Version
-------
``R4_INCIDENT_REPRO_VERSION = "1.0.0"``
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import subprocess
import sys
from pathlib import Path

R4_INCIDENT_REPRO_VERSION = "1.0.0"

INCIDENT_REASON = "GLHS ledger rows are immutable; append a governed transition"

# The exact failing test ids recorded by the 2026-11-14 source audit
# (CONTEXT/SOURCE_AUDIT_2026_11_14.md) and re-confirmed on this checkout.
EXPECTED_FAILING_TESTS: tuple[str, ...] = (
    "tests/test_glhs_r4_admission.py::test_full_valid_grwc_admission",
    "tests/test_glhs_r4_comparators.py::test_benchmark_decision_concordance_schedule_matrix",
    "tests/test_glhs_current_state_insufficiency.py::test_penicillin_allergy_current_state_insufficiency_witness",
    "tests/test_glhs_grwc_lineage.py::test_full_valid_review_chain",
)

# The full R4 gate target list, copied from .github/workflows/glhs-r4-novelty-gate.yml
R4_GATE_TARGETS: tuple[str, ...] = (
    "tests/test_glhs_r4_admission.py",
    "tests/test_glhs_r4_comparators.py",
    "tests/test_glhs_comparator_policies.py",
    "tests/test_glhs_current_state_insufficiency.py",
    "tests/test_glhs_inference_envelope.py",
    "tests/test_glhs_reason_codes.py",
    "tests/test_glhs_attestation_receipts.py",
    "tests/test_inference_attestation.py",
    "tests/test_glhs_grwc_lineage.py",
    "tests/test_glhs_mandatory_thss_binding.py",
)

MUTATION_LISTENER_ANCHOR = "services/api/src/clara_api/db/models.py:3040"
ADMISSION_WRITE_ANCHORS: tuple[str, ...] = (
    "services/api/src/clara_api/glhs/admission.py:698",
    "services/api/src/clara_api/glhs/admission.py:700",
)


@dataclasses.dataclass(frozen=True)
class IncidentTrace:
    reproduced: bool
    reason_code: str
    failed_tests: tuple[str, ...]
    unexpected_failures: tuple[str, ...]
    missing_expected_failures: tuple[str, ...]
    reason_observed: bool
    passed_count: int
    failed_count: int
    duration_seconds: float
    exit_code: int
    log_path: str
    listener_anchor_present: bool
    mutation_site_present: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "reproduced": self.reproduced,
            "reason_code": self.reason_code,
            "failed_tests": list(self.failed_tests),
            "unexpected_failures": list(self.unexpected_failures),
            "missing_expected_failures": list(self.missing_expected_failures),
            "reason_observed": self.reason_observed,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "duration_seconds": self.duration_seconds,
            "exit_code": self.exit_code,
            "log_path": self.log_path,
            "listener_anchor_present": self.listener_anchor_present,
            "mutation_site_present": self.mutation_site_present,
            "version": R4_INCIDENT_REPRO_VERSION,
        }


def _run_pytest(api_dir: Path, log_path: Path) -> tuple[int, str]:
    env = dict(os.environ)
    env.setdefault("DATABASE_URL", "sqlite+pysqlite:////tmp/clara_incident_repro.db")
    env.setdefault("AUTH_AUTO_PROVISION_USERS", "true")
    env.setdefault("AUTH_BOOTSTRAP_ADMIN_ENABLED", "true")
    env.setdefault("GLHS_RESEARCH_COMPARATORS_ENABLED", "true")
    env["PYTHONPATH"] = f"src:../ml/src:{api_dir.parent.parent}"
    argv = [
        "uv",
        "run",
        "pytest",
        "-q",
        *R4_GATE_TARGETS,
    ]
    res = subprocess.run(
        argv, cwd=api_dir, env=env, capture_output=True, text=True, check=False
    )
    output = res.stdout + res.stderr
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(output, encoding="utf-8")
    return res.returncode, output


def _parse_failures(output: str) -> tuple[list[str], int, int, float]:
    failed: list[str] = []
    for match in re.finditer(
        r"^(FAILED|ERROR) (tests/[^\s:]+::[^\s]+)", output, re.MULTILINE
    ):
        failed.append(match.group(2))
    passed = 0
    m = re.search(r"(\d+) passed", output)
    if m:
        passed = int(m.group(1))
    failed_count = 0
    m = re.search(r"(\d+) failed", output)
    if m:
        failed_count = int(m.group(1))
    duration = 0.0
    m = re.search(r"in ([\d.]+)s", output)
    if m:
        duration = float(m.group(1))
    return failed, passed, failed_count, duration


def reproduce_r4(repo: str | os.PathLike[str], *, log_path: str | Path | None = None) -> IncidentTrace:
    """Run the R4 gate and determine whether the documented incident reproduces."""

    root = Path(repo).resolve()
    api_dir = root / "services/api"
    log = Path(log_path) if log_path else root / "research/venue2027/proof/logs/SH-incident_repro.log"

    models_file = root / "services/api/src/clara_api/db/models.py"
    listener_present = (
        models_file.is_file()
        and INCIDENT_REASON in models_file.read_text(encoding="utf-8", errors="ignore")
    )
    mutation_site_present = all((root / a.split(":")[0]).is_file() for a in ADMISSION_WRITE_ANCHORS)

    exit_code, output = _run_pytest(api_dir, log)
    failed, passed, failed_count, duration = _parse_failures(output)
    reason_observed = INCIDENT_REASON in output

    expected = set(EXPECTED_FAILING_TESTS)
    observed = set(failed)
    unexpected = tuple(sorted(observed - expected))
    missing = tuple(sorted(expected - observed))

    reproduced = bool(
        expected
        and not unexpected
        and not missing
        and reason_observed
        and listener_present
        and mutation_site_present
    )
    reason_code = "INCIDENT_REPRODUCED" if reproduced else "INCIDENT_DIVERGED"

    return IncidentTrace(
        reproduced=reproduced,
        reason_code=reason_code,
        failed_tests=tuple(sorted(observed)),
        unexpected_failures=unexpected,
        missing_expected_failures=missing,
        reason_observed=reason_observed,
        passed_count=passed,
        failed_count=failed_count,
        duration_seconds=duration,
        exit_code=exit_code,
        log_path=str(log.relative_to(root) if log.is_relative_to(root) else log),
        listener_anchor_present=listener_present,
        mutation_site_present=mutation_site_present,
    )


def render_trace_markdown(trace: IncidentTrace, head_sha: str) -> str:
    """Render the human-readable regression trace artifact."""

    failing = "\n".join(f"- `{t}`" for t in trace.failed_tests) or "- (none)"
    return f"""# R4 Append-Only Regression Trace

> Generated by `research/venue2027/_shared/tools/r4_regression.py`
> Version `{R4_INCIDENT_REPRO_VERSION}` · schema `{trace.reason_code}`

## Verdict

**Incident reproduced: {trace.reproduced}** (`{trace.reason_code}`)

- Source HEAD: `{head_sha}`
- Reproducer exit code: `{trace.exit_code}` (mode: incident-confirmed)
- Suite totals: {trace.passed_count} passed / {trace.failed_count} failed in {trace.duration_seconds:.2f}s
- Full log: `{trace.log_path}`

## Failure signature

```
{trace.reason_code if not trace.reason_observed else INCIDENT_REASON}
```

Raised by the `before_update` SQLAlchemy listener registered for
`GlhsClinicalCommitmentProposal` at `{MUTATION_LISTENER_ANCHOR}`.

## Failing targets

{failing}

## Mutation path isolation

The incident is triggered when GRWC admission finalizes a reviewed proposal by
writing the projection fields `admission_decision` and `sealed_at`:

{chr(10).join(f"- `{a}`" for a in ADMISSION_WRITE_ANCHORS)}

`GlhsClinicalCommitmentProposal` is registered in the blanket immutable-model
loop, which rejects *any* UPDATE. The canonical proposal content is already
immutable-by-design (append a new reviewed proposal), so only these two
projection fields need an allow-list analogous to
`_protect_glhs_assertion_content`.

## Adversarial control

The suite is **not** modified to pass. `git status --porcelain` shows no changes
to `services/api/tests/` or `services/api/src/clara_api/db/models.py` in this
task. A green suite here would falsify the reproduction.

## Downstream

- `SH-guard_regression` must add failing tests for the permitted projection and
  the prohibited canonical mutation before any fix.
- `SH-repair_immutable` owns the actual allow-list change.
"""


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="CLARA 2027 SH-incident_repro")
    parser.add_argument("--repo", default=".")
    parser.add_argument(
        "--log", default=None, help="pytest log path (default under proof/logs)"
    )
    parser.add_argument(
        "--json-out", default="research/venue2027/_shared/r4_regression_trace.json"
    )
    parser.add_argument("--allow-divergence", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.repo).resolve()
    trace = reproduce_r4(root, log_path=args.log)
    head = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()

    out = root / args.json_out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(trace.to_dict(), indent=2) + "\n", encoding="utf-8")
    md = root / "research/venue2027/_shared/r4_regression_trace.md"
    md.write_text(render_trace_markdown(trace, head), encoding="utf-8")
    print(json.dumps(trace.to_dict(), indent=2))
    if trace.reproduced or args.allow_divergence:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
