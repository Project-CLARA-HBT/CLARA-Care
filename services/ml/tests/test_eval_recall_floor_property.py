"""Property-based tests for the retrieval recall floor CI gate.

Feature: rag-knowledge-pipeline, Property 17: Retrieval recall floor.

Design reference (design.md -> Correctness Properties):
    Property 17: Retrieval recall floor. Over the golden eval set, ``recall@k``
    is greater than or equal to the configured floor (regression guard);
    persistent hybrid retrieval recall@k is ``>=`` the legacy in-memory
    baseline on the same set.

Requirement 11.3 (requirements.md -> Requirement 11, Acceptance Criteria #3):
    IF ``recall@k`` falls below the configured floor OR persistent hybrid
    ``recall@k`` falls below the legacy in-memory baseline on the same golden
    set, THEN THE Eval_Harness SHALL fail the CI gate.

Target: the real eval harness + CI gate exported by
:mod:`clara_ml.rag.eval.harness` (:class:`EvalHarness`, :func:`gate`) which
aggregates the pure ``recall@k`` from :mod:`clara_ml.rag.eval.metrics`
(:func:`recall_at_k`) into a deterministic pass/fail verdict.

The property is validated *without a database* by driving the harness with:

* synthetic :class:`~clara_ml.rag.eval.golden_set.GoldenItem` rows (each with a
  controlled set of ``relevant_doc_ids``), injected via the ``golden_loader``
  seam; and
* a :class:`_StubRetriever` that maps each question to a controllable list of
  ``hit`` (relevant) + ``filler`` (irrelevant) ids.

Because each item returns exactly ``h`` of its ``n_rel`` relevant ids inside the
top-``k`` window (the stub never returns more than ``k`` ids), every per-item
``recall@k`` is the exact rational ``h / n_rel`` and the run's ``mean_recall``
is fully determined by the generated scenario. That lets the test compare the
harness's measured recall against an independently computed expectation and then
assert the gate fires exactly when recall drops below the configured floor /
the legacy baseline.

Two complementary properties are exercised:

* FLOOR GATE -- the gate fails iff measured ``mean_recall < floor`` and passes
  iff ``mean_recall >= floor`` (the configured-floor regression guard).
* BASELINE GATE -- when a legacy in-memory baseline recall is supplied, the
  gate fails iff the persistent retriever's ``mean_recall`` falls below that
  baseline on the *same* golden set.

Validates: Requirements 11.3.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

# Import the store package first so it fully initializes before any other rag
# module is pulled in; store/__init__ wires an import cycle that only resolves
# cleanly when ``clara_ml.rag.store`` loads first. Importing it has no DB side
# effects and keeps this test importable in isolation.
import clara_ml.rag.store  # noqa: F401
from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.rag.eval.golden_set import GoldenItem
from clara_ml.rag.eval.harness import EvalHarness, gate

# Small tolerance for floating-point mean-recall comparisons.
_TOL = 1e-9

# Stub settings injected into the harness so ``build_config_snapshot`` never
# imports the real ``clara_ml.config`` (keeps the test hermetic: no env / no DB).
_STUB_SETTINGS = SimpleNamespace()


class _StubRetriever:
    """A DB-free retriever returning a precomputed id list per question.

    ``retrieve(query, top_k)`` looks the query up in ``mapping`` and returns the
    first ``top_k`` ids verbatim. Ids are returned as plain strings; the
    harness's ``_doc_id`` resolves a bare string to itself, so each returned id
    is scored directly by ``recall_at_k`` with no document wrapper needed.
    """

    def __init__(self, mapping: dict[str, list[str]]) -> None:
        self._mapping = mapping

    def retrieve(self, query: str, top_k: int) -> list[str]:
        return list(self._mapping.get(query, []))[:top_k]


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------


@st.composite
def _recall_scenario(draw: st.DrawFn) -> tuple[int, list[GoldenItem], dict[str, list[str]], float]:
    """A golden set + stub retrieval map with a fully determined ``mean_recall``.

    For each item:

    * ``n_rel`` relevant ids are generated (``relevant_doc_ids``);
    * the retriever returns ``h`` of them (the "hits", ``0 <= h <= n_rel``)
      followed by ``n_fill`` irrelevant filler ids;
    * the total returned count is held ``<= k`` so the top-``k`` window never
      truncates a hit, making the per-item ``recall@k`` exactly ``h / n_rel``.

    Returns ``(k, items, mapping, expected_mean_recall)``.
    """

    k = draw(st.integers(min_value=3, max_value=15))
    n_items = draw(st.integers(min_value=1, max_value=6))

    items: list[GoldenItem] = []
    mapping: dict[str, list[str]] = {}
    per_item_recall: list[float] = []

    for i in range(n_items):
        n_rel = draw(st.integers(min_value=1, max_value=min(k, 8)))
        h = draw(st.integers(min_value=0, max_value=n_rel))
        # Keep the whole returned list within the top-k window so no hit is
        # truncated and recall stays exactly h / n_rel.
        n_fill = draw(st.integers(min_value=0, max_value=k - h))

        question = f"q{i}"  # unique per item -> unambiguous mapping lookup
        relevant_ids = [f"q{i}-rel-{j}" for j in range(n_rel)]
        hit_ids = relevant_ids[:h]
        filler_ids = [f"q{i}-irr-{j}" for j in range(n_fill)]

        mapping[question] = hit_ids + filler_ids
        items.append(
            GoldenItem(
                qid=f"qid-{i}",
                question_vi=question,
                category="ddi",
                relevant_doc_ids=relevant_ids,
            )
        )
        per_item_recall.append(h / n_rel)

    expected_mean = sum(per_item_recall) / len(per_item_recall)
    return k, items, mapping, expected_mean


def _make_harness(items: list[GoldenItem], mapping: dict[str, list[str]]) -> EvalHarness:
    """Build a harness over the stub retriever + injected golden loader."""

    return EvalHarness(
        _StubRetriever(mapping),
        golden_loader=lambda: list(items),
        settings=_STUB_SETTINGS,
    )


# ---------------------------------------------------------------------------
# Property 17a -- configured recall floor regression guard
# ---------------------------------------------------------------------------


# Feature: rag-knowledge-pipeline, Property 17: Retrieval recall floor
# Validates: Requirements 11.3
@settings(max_examples=200, deadline=None)
@given(scenario=_recall_scenario(), floor=st.floats(min_value=0.0, max_value=1.0))
def test_property17_recall_floor_gate(
    scenario: tuple[int, list[GoldenItem], dict[str, list[str]], float],
    floor: float,
) -> None:
    k, items, mapping, expected_mean = scenario
    harness = _make_harness(items, mapping)

    summary = harness.run_eval("run-floor", k=k, recall_floor=floor)

    # The harness must measure exactly the controlled mean recall.
    assert summary.mean_recall == pytest.approx(expected_mean, abs=_TOL)
    assert 0.0 <= summary.mean_recall <= 1.0

    # CI gate semantics: pass iff measured recall >= floor, fail iff below it.
    assert summary.passed == (summary.mean_recall >= floor)

    # Independent directional check on the controlled recall, away from the
    # exact-equality boundary (avoids floating-point ties).
    if expected_mean + _TOL < floor:
        assert summary.passed is False
    elif expected_mean - _TOL > floor:
        assert summary.passed is True


# ---------------------------------------------------------------------------
# Property 17b -- persistent recall vs legacy in-memory baseline
# ---------------------------------------------------------------------------


@st.composite
def _baseline_scenario(
    draw: st.DrawFn,
) -> tuple[int, list[GoldenItem], dict[str, list[str]], dict[str, list[str]], float, float]:
    """One golden set evaluated by two retrievers: persistent vs legacy.

    Both retrievers answer the *same* questions over the *same*
    ``relevant_doc_ids`` but with independently controlled hit counts, yielding
    a ``persistent_mean`` and a ``legacy_mean`` (the baseline) that the gate
    compares per Requirement 11.3.
    """

    k = draw(st.integers(min_value=3, max_value=15))
    n_items = draw(st.integers(min_value=1, max_value=6))

    items: list[GoldenItem] = []
    persistent_map: dict[str, list[str]] = {}
    legacy_map: dict[str, list[str]] = {}
    persistent_recall: list[float] = []
    legacy_recall: list[float] = []

    for i in range(n_items):
        n_rel = draw(st.integers(min_value=1, max_value=min(k, 8)))
        h_persistent = draw(st.integers(min_value=0, max_value=n_rel))
        h_legacy = draw(st.integers(min_value=0, max_value=n_rel))

        question = f"q{i}"
        relevant_ids = [f"q{i}-rel-{j}" for j in range(n_rel)]

        # Each retriever returns its own hits first; no filler is needed since
        # n_rel <= k keeps every hit inside the top-k window.
        persistent_map[question] = relevant_ids[:h_persistent]
        legacy_map[question] = relevant_ids[:h_legacy]

        items.append(
            GoldenItem(
                qid=f"qid-{i}",
                question_vi=question,
                category="ddi",
                relevant_doc_ids=relevant_ids,
            )
        )
        persistent_recall.append(h_persistent / n_rel)
        legacy_recall.append(h_legacy / n_rel)

    persistent_mean = sum(persistent_recall) / len(persistent_recall)
    legacy_mean = sum(legacy_recall) / len(legacy_recall)
    return k, items, persistent_map, legacy_map, persistent_mean, legacy_mean


# Feature: rag-knowledge-pipeline, Property 17: Retrieval recall floor
# Validates: Requirements 11.3
@settings(max_examples=200, deadline=None)
@given(scenario=_baseline_scenario())
def test_property17_persistent_vs_legacy_baseline_gate(
    scenario: tuple[int, list[GoldenItem], dict[str, list[str]], dict[str, list[str]], float, float],
) -> None:
    k, items, persistent_map, legacy_map, persistent_mean, legacy_mean = scenario

    # Establish the legacy in-memory baseline on the golden set.
    legacy_summary = _make_harness(items, legacy_map).run_eval("run-legacy", k=k)
    assert legacy_summary.mean_recall == pytest.approx(legacy_mean, abs=_TOL)

    # Evaluate the persistent retriever and gate it against that baseline.
    persistent_summary = _make_harness(items, persistent_map).run_eval(
        "run-persistent",
        k=k,
        recall_floor=0.0,  # floor satisfied by construction -> isolate the baseline clause
        baseline_recall=legacy_summary.mean_recall,
    )
    assert persistent_summary.mean_recall == pytest.approx(persistent_mean, abs=_TOL)

    # Gate fails iff the persistent recall regressed below the legacy baseline.
    assert persistent_summary.passed == (
        persistent_summary.mean_recall >= legacy_summary.mean_recall
    )

    # Independent directional check away from the equality boundary.
    if persistent_mean + _TOL < legacy_mean:
        assert persistent_summary.passed is False
    elif persistent_mean - _TOL > legacy_mean:
        assert persistent_summary.passed is True


# ---------------------------------------------------------------------------
# Focused example-based unit tests (complement the PBT)
# ---------------------------------------------------------------------------


def test_recall_floor_fails_below_floor() -> None:
    # One item, 1 of 2 relevant ids retrieved -> recall 0.5 < floor 0.8 -> fail.
    items = [
        GoldenItem(
            qid="qid-0",
            question_vi="q0",
            category="ddi",
            relevant_doc_ids=["q0-rel-0", "q0-rel-1"],
        )
    ]
    mapping = {"q0": ["q0-rel-0", "q0-irr-0"]}
    summary = _make_harness(items, mapping).run_eval("run", k=10, recall_floor=0.8)
    assert summary.mean_recall == pytest.approx(0.5, abs=_TOL)
    assert summary.passed is False


def test_recall_floor_passes_at_or_above_floor() -> None:
    # Both relevant ids retrieved -> recall 1.0 >= floor 1.0 -> pass.
    items = [
        GoldenItem(
            qid="qid-0",
            question_vi="q0",
            category="ddi",
            relevant_doc_ids=["q0-rel-0", "q0-rel-1"],
        )
    ]
    mapping = {"q0": ["q0-rel-0", "q0-rel-1"]}
    summary = _make_harness(items, mapping).run_eval("run", k=10, recall_floor=1.0)
    assert summary.mean_recall == pytest.approx(1.0, abs=_TOL)
    assert summary.passed is True


def test_persistent_recall_below_legacy_baseline_fails() -> None:
    items = [
        GoldenItem(
            qid="qid-0",
            question_vi="q0",
            category="ddi",
            relevant_doc_ids=["q0-rel-0", "q0-rel-1"],
        )
    ]
    legacy = _make_harness(items, {"q0": ["q0-rel-0", "q0-rel-1"]}).run_eval("legacy", k=10)
    persistent = _make_harness(items, {"q0": ["q0-rel-0"]}).run_eval(
        "persistent", k=10, recall_floor=0.0, baseline_recall=legacy.mean_recall
    )
    assert legacy.mean_recall == pytest.approx(1.0, abs=_TOL)
    assert persistent.mean_recall == pytest.approx(0.5, abs=_TOL)
    assert persistent.passed is False


def test_gate_is_pure_and_deterministic() -> None:
    # The same summary always yields the same verdict (no I/O, no randomness).
    items = [
        GoldenItem(
            qid="qid-0",
            question_vi="q0",
            category="ddi",
            relevant_doc_ids=["q0-rel-0", "q0-rel-1"],
        )
    ]
    summary = _make_harness(items, {"q0": ["q0-rel-0"]}).run_eval("run", k=10)
    assert gate(summary, recall_floor=0.5) is True
    assert gate(summary, recall_floor=0.5) is True
    assert gate(summary, recall_floor=0.6) is False
