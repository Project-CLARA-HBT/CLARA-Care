"""Property test P15 — eval-gate threshold enforcement (task 9.2, Requirement 20).

Design Property 15 (Validates: Requirements 20.2, 20.3, 20.4):

    *For any* set of computed metrics and their declared thresholds, the
    evaluation gate reports pass *if and only if* every metric meets its
    threshold, and when it fails it identifies the breaching metric(s).

The deterministic enforcement core is the pure
:func:`~clara_ml.scribe.eval.harness.build_gate_result` over a list of
:class:`~clara_ml.scribe.eval.harness.EvalMetric`. A metric *meets* its threshold
when ``value >= threshold`` (it is a minimum floor; boundary equality passes),
and :meth:`EvalMetric.create` derives that ``passed`` flag. The gate then passes
iff EVERY metric passes, and ``failing`` names EXACTLY the breaching metrics
(value < threshold), in order.

The crafted-example coverage lives in ``test_scribe_eval_gate.py``; this module
strengthens Property 15 with randomized Hypothesis strategies over diverse metric
names, values, and thresholds — covering the iff in both directions (all-pass and
mixed/failing sets), boundary equality, negatives, and >1 values, across metric
lists from empty to many.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.scribe.eval.harness import EvalMetric, build_gate_result

# Finite floats spanning negatives, boundary, and >1 values — the full numeric
# space a metric value or declared threshold could take.
_finite_floats = st.floats(
    min_value=-1000.0,
    max_value=1000.0,
    allow_nan=False,
    allow_infinity=False,
)

# Metric names: arbitrary text plus the four real declared metric names, so we
# exercise both random labels and the production metric identifiers. Duplicates
# and empty strings are intentionally allowed (the gate keys off the flag/order,
# not name uniqueness).
_metric_names = st.one_of(
    st.text(max_size=24),
    st.sampled_from(
        [
            "structural_completeness",
            "grounded_claim_rate",
            "no_fabrication",
            "coding_precision",
        ]
    ),
)


def _metric_strategy() -> st.SearchStrategy[EvalMetric]:
    """A metric built via ``create`` from a random (name, value, threshold)."""

    return st.builds(
        EvalMetric.create,
        name=_metric_names,
        value=_finite_floats,
        threshold=_finite_floats,
    )


# Lists from empty to many metrics, so the iff is covered for the empty gate
# (vacuously passes) through large mixed sets.
_metric_lists = st.lists(_metric_strategy(), min_size=0, max_size=12)


# Feature: clara-scribe-enterprise, Property 15: eval-gate threshold enforcement
# Validates: Requirements 20.2, 20.3, 20.4
@settings(max_examples=300, deadline=None)
@given(value=_finite_floats, threshold=_finite_floats, name=_metric_names)
def test_property15_metric_create_derives_passed_from_threshold(
    value: float, threshold: float, name: str
) -> None:
    """``EvalMetric.create`` derives ``passed = value >= threshold`` (Req 20.2).

    Covers the boundary: when value == threshold the metric MUST pass (>= floor),
    across negatives and >1 values alike.
    """

    metric = EvalMetric.create(name, value, threshold)

    # passed is exactly the >= comparison of the coerced floats.
    assert metric.passed == (float(value) >= float(threshold))
    # Fields are faithfully recorded as floats.
    assert metric.value == float(value)
    assert metric.threshold == float(threshold)
    assert metric.name == str(name)


# Feature: clara-scribe-enterprise, Property 15: eval-gate threshold enforcement
# Validates: Requirements 20.2, 20.3, 20.4
@settings(max_examples=300, deadline=None)
@given(metrics=_metric_lists)
def test_property15_gate_passes_iff_every_metric_meets_threshold(
    metrics: list[EvalMetric],
) -> None:
    """The gate passes IFF every metric meets its threshold; names breaches (Req 20.3/20.4).

    For ANY set of metrics with arbitrary values/thresholds:
      * ``passed == all(m.passed)`` — passes iff every metric meets its threshold;
      * ``passed == (failing == [])`` — the verdict and the breach list agree;
      * ``failing`` is EXACTLY the names of the non-passing metrics (value <
        threshold), and ONLY those, preserving their original order.
    """

    result = build_gate_result(metrics)

    # The gate preserves the metrics it was given (order + identity).
    assert result.metrics == metrics

    # iff direction 1: pass exactly when every metric individually passed.
    expected_pass = all(m.passed for m in metrics)
    assert result.passed == expected_pass

    # iff direction 2 (Req 20.4): a pass is equivalent to an empty breach list.
    assert result.passed == (result.failing == [])

    # failing names EXACTLY the breaching metrics (value < threshold), and only
    # those, in their original order.
    expected_failing = [m.name for m in metrics if not m.passed]
    assert result.failing == expected_failing

    # Cross-check the breach predicate against the raw numeric comparison: a
    # metric breaches precisely when value < threshold (boundary equality is a
    # pass, never a breach).
    breaching_by_value = [m.name for m in metrics if m.value < m.threshold]
    assert result.failing == breaching_by_value


# Feature: clara-scribe-enterprise, Property 15: eval-gate threshold enforcement
# Validates: Requirements 20.2, 20.3, 20.4
@settings(max_examples=200, deadline=None)
@given(
    passing=st.lists(
        st.tuples(_metric_names, _finite_floats, st.floats(min_value=0.0, max_value=1.0)),
        min_size=1,
        max_size=8,
    )
)
def test_property15_all_passing_set_always_passes(
    passing: list[tuple[str, float, float]],
) -> None:
    """Forced-passing direction of the iff: a set where every metric meets its
    threshold ALWAYS yields a passing gate with no breaches (Req 20.3).

    Each metric is constructed with ``value`` boosted above its threshold so it is
    guaranteed to pass, exercising the all-pass branch densely.
    """

    metrics = [
        EvalMetric.create(name, threshold + abs(slack) + 1.0, threshold)
        for name, slack, threshold in passing
    ]
    result = build_gate_result(metrics)

    assert all(m.passed for m in metrics)
    assert result.passed is True
    assert result.failing == []


# Feature: clara-scribe-enterprise, Property 15: eval-gate threshold enforcement
# Validates: Requirements 20.2, 20.3, 20.4
@settings(max_examples=200, deadline=None)
@given(
    failing_specs=st.lists(
        st.tuples(_metric_names, st.floats(min_value=1e-3, max_value=10.0)),
        min_size=1,
        max_size=8,
    ),
    breach_index=st.integers(min_value=0),
)
def test_property15_any_breach_fails_and_is_named(
    failing_specs: list[tuple[str, float]], breach_index: int
) -> None:
    """Forced-failing direction of the iff: injecting at least one breaching metric
    makes the gate fail and names exactly the breaching metric(s) (Req 20.4).

    All but one metric are forced to pass (value == threshold, a boundary pass);
    the chosen one is forced to breach (value strictly below threshold). The gate
    must therefore fail and ``failing`` must contain exactly that breaching name.
    """

    idx = breach_index % len(failing_specs)
    metrics: list[EvalMetric] = []
    for i, (name, gap) in enumerate(failing_specs):
        threshold = 1.0
        if i == idx:
            # Strictly below threshold ⇒ guaranteed breach.
            metrics.append(EvalMetric.create(name, threshold - gap, threshold))
        else:
            # Boundary equality ⇒ guaranteed pass.
            metrics.append(EvalMetric.create(name, threshold, threshold))

    result = build_gate_result(metrics)

    assert result.passed is False
    # The injected breach is named.
    assert failing_specs[idx][0] in result.failing
    # failing names exactly the non-passing metrics, in order.
    assert result.failing == [m.name for m in metrics if not m.passed]
    # And those are precisely the value < threshold metrics (no false positives).
    assert result.failing == [m.name for m in metrics if m.value < m.threshold]
