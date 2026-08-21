"""Unit tests for the Vietnamese golden set + metric computation (task 18.1, R17.1/R17.2).

Covers:
* the five research-quality metrics (bounds + documented edge cases),
* the curated Vietnamese golden set shape (Vietnamese-first, refusal coverage), and
* the harness computing all five metrics over the golden set and recording a
  legacy recall@k baseline.
"""

from __future__ import annotations

from clara_ml.research_quality import (
    DEFAULT_RESEARCH_GOLDEN_SET,
    RESEARCH_CATEGORIES,
    ResearchEvalHarness,
    ResearchGoldenItem,
    citation_accuracy,
    faithfulness,
    load_research_golden_set,
    recall_at_k,
    refusal_compliance,
    unsupported_claim_rate,
)
from clara_ml.research_quality.harness import research_quality_gate

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeRetriever:
    """Returns gold-relevant docs for each golden item keyed by query substring."""

    def __init__(self, by_query: dict[str, list[dict]]):
        self._by_query = by_query

    def retrieve(self, query: str, top_k: int = 10):
        return self._by_query.get(query, [])[:top_k]


def _doc(doc_ref: str, text: str, url: str = "") -> dict:
    return {"id": doc_ref, "text": text, "metadata": {"doc_ref": doc_ref, "url": url}}


# ---------------------------------------------------------------------------
# Metrics: bounds + edge cases
# ---------------------------------------------------------------------------


def test_recall_at_k_basic_and_edges():
    assert recall_at_k(["a", "b", "c"], ["a", "c"], 3) == 1.0
    assert recall_at_k(["a", "x"], ["a", "c"], 3) == 0.5
    # de-dupe: repeating an id cannot inflate recall
    assert recall_at_k(["a", "a", "a"], ["a", "c"], 3) == 0.5
    # edge cases
    assert recall_at_k(["a"], [], 3) == 0.0
    assert recall_at_k(["a"], ["a"], 0) == 0.0
    assert recall_at_k([], ["a"], 3) == 0.0


def test_faithfulness_basic_and_edges():
    answer = "Metformin giảm đường huyết."
    supported = faithfulness(answer, ["Metformin giúp giảm đường huyết hiệu quả."])
    assert supported == 1.0
    # no context -> unsupported
    assert faithfulness(answer, []) == 0.0
    # no claims -> vacuously faithful
    assert faithfulness("", ["bất kỳ"]) == 1.0


def test_citation_accuracy_basic_and_edges():
    assert citation_accuracy(["dailymed:warfarin-spl"], ["dailymed:warfarin-spl"]) == 1.0
    assert citation_accuracy([], ["dailymed:warfarin-spl"]) == 0.0
    # no required citations -> trivially satisfied
    assert citation_accuracy([], []) == 1.0


def test_unsupported_claim_rate_is_faithfulness_complement():
    answer = "Warfarin cần theo dõi INR. Aspirin tăng nguy cơ chảy máu."
    texts = ["Warfarin cần theo dõi INR định kỳ."]
    f = faithfulness(answer, texts)
    u = unsupported_claim_rate(answer, texts)
    assert abs((f + u) - 1.0) < 1e-9
    # edges
    assert unsupported_claim_rate("", ["x"]) == 0.0
    assert unsupported_claim_rate("Có claim ở đây.", []) == 1.0


def test_refusal_compliance_matches_decision():
    assert refusal_compliance(True, True) == 1.0
    assert refusal_compliance(False, False) == 1.0
    assert refusal_compliance(False, True) == 0.0  # missed refusal
    assert refusal_compliance(True, False) == 0.0  # over-refusal


# ---------------------------------------------------------------------------
# Golden set shape
# ---------------------------------------------------------------------------


def test_golden_set_is_vietnamese_first_and_well_formed():
    items = load_research_golden_set()
    assert items == DEFAULT_RESEARCH_GOLDEN_SET
    assert len(items) >= 8
    qids = [it.qid for it in items]
    assert len(qids) == len(set(qids))  # unique qids
    for it in items:
        assert isinstance(it, ResearchGoldenItem)
        assert it.category in RESEARCH_CATEGORIES
        assert it.query_vi.strip()  # Vietnamese-first primary query


def test_golden_set_has_refusal_coverage():
    items = load_research_golden_set()
    refusals = [it for it in items if it.should_refuse]
    assert refusals, "golden set must include >= 1 out-of-scope refusal item (R10.5)"
    for it in refusals:
        assert it.category == "out_of_scope"


def test_load_returns_fresh_copy():
    a = load_research_golden_set()
    a.clear()
    assert load_research_golden_set(), "module constant must not be mutated by callers"


# ---------------------------------------------------------------------------
# Harness: all five metrics computed over the golden set + baseline
# ---------------------------------------------------------------------------


def _build_harness() -> ResearchEvalHarness:
    items = load_research_golden_set()
    by_query: dict[str, list[dict]] = {}
    for it in items:
        if it.should_refuse:
            continue
        docs = [_doc(ref, it.gold_answer_vi) for ref in it.relevant_doc_ids]
        by_query[it.query_vi] = docs

    def answer_fn(query: str, context):
        # Echo the gold answer + cite each retrieved doc_ref so citation_accuracy is meaningful.
        item = next(i for i in items if i.query_vi == query)
        refs = " ".join(item.must_cite)
        return f"{item.gold_answer_vi} {refs}"

    def refusal_fn(query: str) -> bool:
        item = next(i for i in items if i.query_vi == query)
        return item.should_refuse

    return ResearchEvalHarness(
        _FakeRetriever(by_query),
        answer_fn=answer_fn,
        refusal_fn=refusal_fn,
    )


def test_harness_computes_all_five_metrics_per_item():
    harness = _build_harness()
    summary = harness.run_eval("run-1", k=10)

    assert summary.n == len(load_research_golden_set())
    assert summary.rows
    metric_keys = {
        "recall_at_k",
        "faithfulness",
        "citation_accuracy",
        "unsupported_claim_rate",
        "refusal_compliance",
    }
    assert set(summary.metrics().keys()) == metric_keys
    for value in summary.metrics().values():
        assert 0.0 <= value <= 1.0

    # Refusal item handled correctly (no retrieval/answer, compliant refusal).
    refusal_rows = [r for r in summary.rows if r.should_refuse]
    assert refusal_rows
    for row in refusal_rows:
        assert row.did_refuse is True
        assert row.refusal_compliance == 1.0


def test_harness_records_recall_baseline():
    harness = _build_harness()
    summary = harness.run_eval("baseline-run", k=10)
    baseline = harness.record_recall_baseline("baseline-run-2", k=10)
    assert 0.0 <= baseline <= 1.0
    assert baseline == summary.mean_recall
    # With the fake retriever returning gold docs, every non-refusal item has perfect recall.
    for row in summary.rows:
        if not row.should_refuse:
            assert row.recall_at_k == 1.0


def test_quality_gate_reports_each_metric_with_threshold():
    harness = _build_harness()
    summary = harness.run_eval("run-2", k=10)
    report = research_quality_gate(summary, baseline_recall=summary.mean_recall)

    metrics_reported = {entry["metric"] for entry in report.entries}
    assert metrics_reported == {
        "recall_at_k",
        "faithfulness",
        "citation_accuracy",
        "unsupported_claim_rate",
        "refusal_compliance",
    }
    for entry in report.entries:
        assert "threshold" in entry and "value" in entry and "passed" in entry
