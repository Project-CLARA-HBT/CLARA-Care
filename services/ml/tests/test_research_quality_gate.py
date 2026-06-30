"""Unit tests for the research-quality CI regression gate (task 18.2, R17.3–17.5).

Covers:
* the ``RESEARCH_QUALITY_GATE_ENABLED`` flag reader (default-off, truthy spellings),
* recall-baseline resolution (explicit arg vs env vs default),
* :func:`run_regression_gate` — skipped when disabled, fail on recall regression
  below the recorded baseline (R17.3), fail on any other metric breach (R17.4),
  and pass when every metric meets its threshold, and
* :func:`format_gate_report` — each computed metric reported alongside its
  threshold (R17.5).
"""

from __future__ import annotations

from clara_ml.research_quality import (
    RegressionGateResult,
    ResearchEvalHarness,
    ResearchQualityThresholds,
    format_gate_report,
    load_research_golden_set,
    quality_gate_enabled,
    resolve_recall_baseline,
    run_regression_gate,
)

# ---------------------------------------------------------------------------
# Fakes (mirror the golden-set test harness so recall is perfect by default)
# ---------------------------------------------------------------------------


class _FakeRetriever:
    def __init__(self, by_query: dict[str, list[dict]]):
        self._by_query = by_query

    def retrieve(self, query: str, top_k: int = 10):
        return self._by_query.get(query, [])[:top_k]


def _doc(doc_ref: str, text: str) -> dict:
    return {"id": doc_ref, "text": text, "metadata": {"doc_ref": doc_ref}}


def _build_harness(*, perfect: bool = True) -> ResearchEvalHarness:
    items = load_research_golden_set()
    by_query: dict[str, list[dict]] = {}
    for it in items:
        if it.should_refuse:
            continue
        if perfect:
            by_query[it.query_vi] = [_doc(ref, it.gold_answer_vi) for ref in it.relevant_doc_ids]
        else:
            # Return no relevant docs → recall@k collapses to 0.
            by_query[it.query_vi] = []

    def answer_fn(query: str, context):
        item = next(i for i in items if i.query_vi == query)
        return f"{item.gold_answer_vi} {' '.join(item.must_cite)}"

    def refusal_fn(query: str) -> bool:
        return next(i for i in items if i.query_vi == query).should_refuse

    return ResearchEvalHarness(_FakeRetriever(by_query), answer_fn=answer_fn, refusal_fn=refusal_fn)


# ---------------------------------------------------------------------------
# Flag reader
# ---------------------------------------------------------------------------


def test_quality_gate_disabled_by_default():
    assert quality_gate_enabled({}) is False
    assert quality_gate_enabled({"RESEARCH_QUALITY_GATE_ENABLED": ""}) is False
    assert quality_gate_enabled({"RESEARCH_QUALITY_GATE_ENABLED": "false"}) is False
    assert quality_gate_enabled({"RESEARCH_QUALITY_GATE_ENABLED": "0"}) is False


def test_quality_gate_truthy_spellings():
    for token in ("1", "true", "TRUE", "Yes", "on", "t", "y"):
        assert quality_gate_enabled({"RESEARCH_QUALITY_GATE_ENABLED": token}) is True


# ---------------------------------------------------------------------------
# Baseline resolution
# ---------------------------------------------------------------------------


def test_resolve_recall_baseline_precedence():
    # explicit arg wins over env
    assert resolve_recall_baseline(0.7, env={"RESEARCH_QUALITY_RECALL_BASELINE": "0.2"}) == 0.7
    # env used when no explicit arg
    assert resolve_recall_baseline(env={"RESEARCH_QUALITY_RECALL_BASELINE": "0.55"}) == 0.55
    # default 0.0 when unset or unparseable
    assert resolve_recall_baseline(env={}) == 0.0
    assert resolve_recall_baseline(env={"RESEARCH_QUALITY_RECALL_BASELINE": "abc"}) == 0.0


# ---------------------------------------------------------------------------
# run_regression_gate
# ---------------------------------------------------------------------------


def test_gate_skipped_when_disabled_is_non_blocking():
    harness = _build_harness()
    result = run_regression_gate(harness, baseline_recall=1.0, enabled=False)
    assert result.enabled is False
    assert result.passed is True  # non-blocking skip
    assert result.exit_code == 0
    assert result.report is None
    assert result.summary is None
    assert "SKIPPED" in format_gate_report(result)


def test_gate_passes_when_all_metrics_meet_thresholds():
    harness = _build_harness(perfect=True)
    # Record the legacy recall baseline from this run, then gate the same run
    # against it: recall meets the baseline and every other metric meets its
    # threshold, so the gate passes.
    baseline = harness.record_recall_baseline("baseline", k=10)
    result = run_regression_gate(harness, baseline_recall=baseline, enabled=True)
    assert result.enabled is True
    assert result.passed is True
    assert result.exit_code == 0
    assert result.report is not None and result.report.passed is True


def test_gate_fails_on_recall_regression_below_baseline():
    # Retriever returns nothing relevant → mean recall 0.0, below any positive baseline (R17.3).
    harness = _build_harness(perfect=False)
    result = run_regression_gate(harness, baseline_recall=0.9, enabled=True)
    assert result.passed is False
    assert result.exit_code == 1
    recall_entry = next(e for e in result.report.entries if e["metric"] == "recall_at_k")
    assert recall_entry["passed"] is False
    assert recall_entry["threshold"] == 0.9


def test_gate_fails_on_metric_threshold_breach():
    # Recall at baseline (isolates the breach to faithfulness), but an impossible
    # faithfulness floor (>1.0) forces a metric-threshold breach (R17.4).
    harness = _build_harness(perfect=True)
    baseline = harness.record_recall_baseline("baseline", k=10)
    thresholds = ResearchQualityThresholds(faithfulness_floor=1.01)
    result = run_regression_gate(
        harness, baseline_recall=baseline, enabled=True, thresholds=thresholds
    )
    assert result.passed is False
    assert result.exit_code == 1
    failing_metrics = {e["metric"] for e in result.report.failing()}
    assert "faithfulness" in failing_metrics
    assert "recall_at_k" not in failing_metrics


# ---------------------------------------------------------------------------
# Threshold reporting (R17.5)
# ---------------------------------------------------------------------------


def test_format_gate_report_lists_each_metric_with_threshold():
    harness = _build_harness(perfect=True)
    baseline = harness.record_recall_baseline("baseline", k=10)
    result = run_regression_gate(harness, baseline_recall=baseline, enabled=True)
    text = format_gate_report(result)
    assert "Research Quality Gate: PASS" in text
    for metric in (
        "recall_at_k",
        "faithfulness",
        "citation_accuracy",
        "unsupported_claim_rate",
        "refusal_compliance",
    ):
        assert metric in text
    # Every metric line shows its comparison operator + threshold value.
    assert ">=" in text
    assert "<=" in text


def test_format_gate_report_for_disabled_result():
    text = format_gate_report(RegressionGateResult(enabled=False, passed=True))
    assert "SKIPPED" in text
    assert "RESEARCH_QUALITY_GATE_ENABLED" in text
