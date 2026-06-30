"""CI regression gate runner + threshold reporting for Research quality (task 18.2, R17.3–17.5).

Task 18.1 built the pure aggregation core in
:mod:`clara_ml.research_quality.harness`:

* :func:`~clara_ml.research_quality.harness.research_quality_gate` — given a run
  summary, a recorded recall baseline, and configured thresholds, returns a
  :class:`~clara_ml.research_quality.harness.ResearchQualityGateReport` that lists
  each metric alongside its threshold and a pass/fail verdict.

This module wires that core into a **runnable CI regression gate** (Requirements
17.3–17.5):

* The gate FAILS when mean ``recall@k`` drops below the recorded legacy baseline
  (R17.3) OR any other metric breaches its configured threshold (R17.4).
* Each computed metric is reported alongside its threshold (R17.5) via
  :func:`format_gate_report`.
* The whole gate only runs when the ``RESEARCH_QUALITY_GATE_ENABLED`` flag is on
  (:func:`quality_gate_enabled`); when the flag is off the gate is *skipped*
  (non-blocking, exit code 0) so the enhancement ships dark and CI behavior is
  unchanged until the flag is turned on.

Design constraints honoured here:

* **Import-safe.** Importing this module opens no database connection, reads no
  settings, and constructs no retriever. Settings + the heavy retriever are
  imported lazily inside the default builders only when :func:`main` actually
  runs an enabled gate.
* **Dependency-injected + deterministic.** :func:`run_regression_gate` takes an
  already-constructed harness, an explicit baseline, and thresholds, and only
  delegates to the pure :func:`research_quality_gate`. The same inputs always
  yield the same verdict, report, and exit code, so the gate is unit-testable
  without any I/O.

Validates: Requirements 17.3, 17.4, 17.5.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from clara_ml.research_quality.harness import (
    ResearchEvalHarness,
    ResearchEvalSummary,
    ResearchQualityGateReport,
    ResearchQualityThresholds,
    research_quality_gate,
)

__all__ = [
    "QUALITY_GATE_ENV_VAR",
    "RECALL_BASELINE_ENV_VAR",
    "RegressionGateResult",
    "quality_gate_enabled",
    "resolve_recall_baseline",
    "run_regression_gate",
    "format_gate_report",
    "main",
]

#: Environment flag that turns the CI regression gate on. The canonical flag is
#: declared in the API settings (``RESEARCH_QUALITY_GATE_ENABLED``); the ML CI
#: runner reads the same environment variable so a single CI toggle drives both
#: services.
QUALITY_GATE_ENV_VAR = "RESEARCH_QUALITY_GATE_ENABLED"

#: Environment variable carrying the recorded legacy recall@k baseline the gate
#: compares against (Requirement 17.3). Recorded once via
#: :meth:`ResearchEvalHarness.record_recall_baseline` and pinned in CI config.
RECALL_BASELINE_ENV_VAR = "RESEARCH_QUALITY_RECALL_BASELINE"

# Truthy spellings accepted for the boolean flag (mirrors pydantic-settings bool
# parsing so the ML reader agrees with the API settings reader).
_TRUE_TOKENS = frozenset({"1", "true", "yes", "on", "t", "y"})


def quality_gate_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Return whether the research quality regression gate is enabled.

    Reads ``RESEARCH_QUALITY_GATE_ENABLED`` from ``env`` (defaults to
    :data:`os.environ`). The flag defaults to *off* so the gate is skipped and
    CI behavior is unchanged until it is explicitly enabled (R17 ships dark).
    """

    source = os.environ if env is None else env
    raw = source.get(QUALITY_GATE_ENV_VAR, "")
    return str(raw).strip().lower() in _TRUE_TOKENS


def resolve_recall_baseline(
    baseline_recall: float | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> float:
    """Resolve the recall@k baseline the gate compares against (Requirement 17.3).

    Precedence: an explicit ``baseline_recall`` argument wins; otherwise the
    value is read from ``RESEARCH_QUALITY_RECALL_BASELINE``; otherwise it
    defaults to ``0.0`` (no recorded baseline ⇒ recall cannot regress).
    """

    if baseline_recall is not None:
        return float(baseline_recall)
    source = os.environ if env is None else env
    raw = source.get(RECALL_BASELINE_ENV_VAR, "")
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return 0.0


@dataclass(frozen=True, slots=True)
class RegressionGateResult:
    """Outcome of a CI regression-gate evaluation.

    ``enabled`` reflects the ``RESEARCH_QUALITY_GATE_ENABLED`` flag. When the
    gate is disabled it is *skipped*: ``passed`` is ``True`` (non-blocking) and
    ``report``/``summary`` are ``None``. When enabled, ``passed`` mirrors the
    pure gate verdict and ``report``/``summary`` carry the per-metric detail.
    """

    enabled: bool
    passed: bool
    report: ResearchQualityGateReport | None = None
    summary: ResearchEvalSummary | None = None
    baseline_recall: float | None = None
    skipped_reason: str | None = None

    @property
    def exit_code(self) -> int:
        """Process exit code for CI: ``0`` when passed/skipped, ``1`` on failure."""

        return 0 if self.passed else 1


def run_regression_gate(
    harness: ResearchEvalHarness,
    *,
    baseline_recall: float,
    run_id: str = "research-quality-gate",
    k: int = 10,
    thresholds: ResearchQualityThresholds | None = None,
    enabled: bool | None = None,
    env: Mapping[str, str] | None = None,
) -> RegressionGateResult:
    """Run the golden-set evaluation and enforce the regression gate (R17.3–17.5).

    Steps:

    1. Resolve the ``RESEARCH_QUALITY_GATE_ENABLED`` flag (``enabled`` overrides
       the environment lookup when supplied). When disabled, return a *skipped*,
       non-blocking result without running the harness.
    2. Run the harness over the Vietnamese golden set to obtain a
       :class:`ResearchEvalSummary` with the five metric means.
    3. Delegate to the pure :func:`research_quality_gate`, which fails the gate
       when mean ``recall@k`` < ``baseline_recall`` (R17.3) or any other metric
       breaches its configured threshold (R17.4), and reports each metric
       alongside its threshold (R17.5).

    The only non-pure step is the harness run (step 2); the gate decision itself
    (step 3) is pure aggregation, so a fixed summary always yields the same
    verdict and report.
    """

    is_enabled = quality_gate_enabled(env) if enabled is None else bool(enabled)
    if not is_enabled:
        return RegressionGateResult(
            enabled=False,
            passed=True,
            baseline_recall=float(baseline_recall),
            skipped_reason=f"{QUALITY_GATE_ENV_VAR} is off",
        )

    summary = harness.run_eval(run_id, k=k)
    report = research_quality_gate(
        summary,
        baseline_recall=float(baseline_recall),
        thresholds=thresholds,
    )
    return RegressionGateResult(
        enabled=True,
        passed=report.passed,
        report=report,
        summary=summary,
        baseline_recall=float(baseline_recall),
    )


def _format_entry(entry: Mapping[str, Any]) -> str:
    """Render one metric line: status, name, value, comparison, threshold."""

    status = "PASS" if entry.get("passed") else "FAIL"
    metric = str(entry.get("metric", ""))
    value = float(entry.get("value", 0.0))
    comparison = str(entry.get("comparison", ""))
    threshold = float(entry.get("threshold", 0.0))
    return f"  [{status}] {metric:<24} = {value:.4f} ({comparison} {threshold:.4f})"


def format_gate_report(
    result: RegressionGateResult,
) -> str:
    """Render a human-readable gate report listing each metric + threshold (R17.5).

    The report header states the overall verdict (PASS/FAIL/SKIPPED) and each
    subsequent line shows a metric, its measured value, the comparison operator,
    and the threshold it was checked against — so a CI log surfaces exactly why
    the gate passed or failed.
    """

    if not result.enabled:
        reason = result.skipped_reason or f"{QUALITY_GATE_ENV_VAR} is off"
        return f"Research Quality Gate: SKIPPED ({reason})"

    verdict = "PASS" if result.passed else "FAIL"
    lines = [f"Research Quality Gate: {verdict}"]
    if result.baseline_recall is not None:
        lines.append(f"  recall@k baseline: {result.baseline_recall:.4f}")
    report = result.report
    if report is not None:
        lines.extend(_format_entry(entry) for entry in report.entries)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Default harness builder + CLI entrypoint (only used when the gate is enabled)
# ---------------------------------------------------------------------------


def _build_default_harness() -> ResearchEvalHarness:  # pragma: no cover - requires live store
    """Construct the production research-quality harness against the persistent store.

    Imported lazily and only invoked by :func:`main` when the gate is enabled, so
    this module stays import-safe. Mirrors ``admin_rag_handlers._build_retriever``
    (hybrid retriever from the live engine) and scores retrieval over the curated
    Vietnamese golden set.
    """

    from clara_ml import admin_rag_handlers

    engine = admin_rag_handlers._engine()
    if engine is None:
        raise RuntimeError("persistent store unavailable: cannot run research quality gate")
    retriever = admin_rag_handlers._build_retriever(engine)
    return ResearchEvalHarness(retriever)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - thin CLI shell
    """CLI entrypoint: run the regression gate and return a process exit code.

    Skips (exit 0) when ``RESEARCH_QUALITY_GATE_ENABLED`` is off; otherwise builds
    the default harness, runs the gate against the recorded recall baseline
    (``RESEARCH_QUALITY_RECALL_BASELINE``), prints the per-metric threshold
    report, and returns 0 on pass / 1 on failure.
    """

    if not quality_gate_enabled():
        print(format_gate_report(RegressionGateResult(enabled=False, passed=True)))
        return 0

    harness = _build_default_harness()
    result = run_regression_gate(
        harness,
        baseline_recall=resolve_recall_baseline(),
    )
    print(format_gate_report(result))
    return result.exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
