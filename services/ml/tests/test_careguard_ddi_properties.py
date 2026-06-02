"""Property-based tests for CareGuard DDI aggregation invariants.

Covers two design properties for the product-polish-analytics feature:

- Property 6 (Requirements 3.2): openFDA-only co-occurrence evidence never
  creates a standalone DDI alert; it may only enrich a pre-existing
  local/RxNav alert.
- Property 7 (Requirements 3.3): a ``medium`` ``drug_drug`` alert floors the
  aggregated overall risk level at ``medium`` while leaving a genuine
  ``low``-only set and ``high``/``critical`` aggregation unchanged.

These exercise the aggregation core directly (``_merge_drug_alerts`` and
``_risk_from_signals``) so the invariants hold across arbitrary signal sets.
"""

from __future__ import annotations

from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.agents.careguard import (
    _merge_drug_alerts,
    _pair_key,
    _risk_from_signals,
)

_SEVERITIES = ["low", "medium", "high", "critical"]
_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}
_DRUGS = [
    "amlodipine",
    "aspirin",
    "clopidogrel",
    "ibuprofen",
    "omeprazole",
    "warfarin",
]


@st.composite
def _drug_pair(draw: st.DrawFn) -> list[str]:
    """A sorted pair of two distinct drug tokens."""
    pair = draw(
        st.lists(st.sampled_from(_DRUGS), min_size=2, max_size=2, unique=True)
    )
    return sorted(pair)


@st.composite
def _drug_drug_alert(draw: st.DrawFn) -> dict[str, Any]:
    """A well-formed ``drug_drug`` alert over a distinct drug pair."""
    return {
        "type": "drug_drug",
        "severity": draw(st.sampled_from(_SEVERITIES)),
        "medications": draw(_drug_pair()),
        "message": "Potential DDI detected.",
        "source": draw(st.sampled_from(["local_rules", "rxnav"])),
    }


@st.composite
def _openfda_evidence(draw: st.DrawFn) -> dict[tuple[str, str], dict[str, int]]:
    """openFDA co-occurrence evidence keyed by a sorted drug pair."""
    pairs = draw(st.lists(_drug_pair(), max_size=5))
    evidence: dict[tuple[str, str], dict[str, int]] = {}
    for pair in pairs:
        evidence[tuple(pair)] = {
            "label_mentions": draw(st.integers(min_value=0, max_value=50)),
            "event_reports": draw(st.integers(min_value=0, max_value=500)),
        }
    return evidence


# Feature: product-polish-analytics, Property 6: openFDA-only evidence never creates a standalone alert
# Validates: Requirements 3.2
@settings(max_examples=200)
@given(
    local_alerts=st.lists(_drug_drug_alert(), max_size=5),
    external_alerts=st.lists(_drug_drug_alert(), max_size=5),
    openfda_evidence=_openfda_evidence(),
)
def test_property6_openfda_only_evidence_never_creates_standalone_alert(
    local_alerts: list[dict[str, Any]],
    external_alerts: list[dict[str, Any]],
    openfda_evidence: dict[tuple[str, str], dict[str, int]],
) -> None:
    merged = _merge_drug_alerts(local_alerts, external_alerts, openfda_evidence)

    output_pairs = {tuple(sorted(alert["medications"])) for alert in merged}
    existing_pairs = {
        _pair_key(alert["medications"])
        for alert in [*local_alerts, *external_alerts]
        if len(_pair_key(alert["medications"])) >= 2
    }

    # The merged alert set covers exactly the pairs backed by a local/RxNav
    # alert — openFDA evidence never introduces a new pair.
    assert output_pairs == existing_pairs

    # Any pair whose ONLY evidence is openFDA co-occurrence is absent.
    for pair in openfda_evidence:
        key = tuple(sorted(pair))
        if key not in existing_pairs:
            assert key not in output_pairs

    # openFDA evidence that matches a pre-existing alert attaches only as
    # enrichment on that alert (never as a standalone alert).
    openfda_pairs = {tuple(sorted(pair)) for pair in openfda_evidence}
    for alert in merged:
        key = tuple(sorted(alert["medications"]))
        if key in openfda_pairs:
            evidence = alert.get("evidence", {})
            assert "openfda_label_mentions" in evidence
            assert "openfda_event_reports" in evidence


# Feature: product-polish-analytics, Property 7: a medium drug_drug alert floors the overall risk at medium
# Validates: Requirements 3.3
@settings(max_examples=200)
@given(alerts=st.lists(_drug_drug_alert(), min_size=1, max_size=8))
def test_property7_medium_drug_drug_alert_floors_overall_risk_at_medium(
    alerts: list[dict[str, Any]],
) -> None:
    _, level = _risk_from_signals(alerts, [], [])
    severities = [alert["severity"] for alert in alerts]

    # Any medium drug_drug alert floors the aggregated risk at >= medium.
    if "medium" in severities:
        assert _RANK[level] >= _RANK["medium"]

    # A genuinely low-only set (no other signals) stays low.
    if all(severity == "low" for severity in severities):
        assert level == "low"

    # high/critical aggregation is unchanged: the medium floor never lowers a
    # set that already contains a high/critical drug_drug alert.
    if any(severity in {"high", "critical"} for severity in severities):
        assert _RANK[level] >= _RANK["high"]
