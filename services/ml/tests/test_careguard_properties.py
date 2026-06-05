"""Property-based tests for CareGuard DDI aggregation invariants.

Feature: product-polish-analytics

These tests use hypothesis to verify the universal correctness properties for
the CareGuard severity-aggregation and alert-merge logic in
``clara_ml.agents.careguard``:

- Property 6 (Validates: Requirements 3.2) -- openFDA-only co-occurrence never
  creates a standalone alert; it can only enrich a pre-existing local/RxNav
  alert.
- Property 7 (Validates: Requirements 3.3) -- any ``drug_drug`` alert ranked
  ``medium`` floors the overall risk level at ``medium``; a genuine ``low`` set
  is not bumped; ``high``/``critical`` aggregation is unchanged (the floor never
  reduces an already-higher level).
"""

from __future__ import annotations

from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from clara_ml.agents.careguard import (
    _SEVERITY_RANK,
    _merge_drug_alerts,
    _normalize_severity,
    _pair_key,
    _risk_from_signals,
)

# A small fixed pool of lowercase, already-normalized medication tokens. Drawing
# pairs from a constrained pool deliberately increases the chance that the same
# pair appears across local/RxNav/openFDA sources, exercising the enrichment
# path as well as the standalone-suppression path.
_MED_POOL = [
    "amlodipine",
    "aspirin",
    "warfarin",
    "ibuprofen",
    "metformin",
    "lisinopril",
    "simvastatin",
    "digoxin",
    "clopidogrel",
    "omeprazole",
    "spironolactone",
    "tramadol",
]

_CANONICAL_SEVERITIES = ["low", "medium", "high", "critical"]
_CRITICAL_SYMPTOM_POOL = [
    "chest pain",
    "shortness of breath",
    "fainting",
    "severe bleeding",
]
_LAB_FLAG_POOL = ["severe_renal_impairment", "elevated_creatinine"]


@st.composite
def _drug_pair(draw: st.DrawFn) -> tuple[str, str]:
    """Generate a sorted pair of two distinct medication tokens."""
    meds = draw(
        st.lists(st.sampled_from(_MED_POOL), min_size=2, max_size=2, unique=True)
    )
    return tuple(sorted(meds))  # type: ignore[return-value]


def _drug_drug_alert(pair: tuple[str, str], severity: str, tag: str) -> dict[str, Any]:
    return {
        "type": "drug_drug",
        "severity": severity,
        "medications": list(pair),
        "message": f"{tag} interaction between {pair[0]} and {pair[1]}.",
        "source": tag,
    }


# ---------------------------------------------------------------------------
# Property 6: openFDA-only evidence never creates a standalone alert.
# ---------------------------------------------------------------------------


@settings(max_examples=200)
@given(
    local=st.lists(st.tuples(_drug_pair(), st.sampled_from(_CANONICAL_SEVERITIES)), max_size=6),
    rxnav=st.lists(st.tuples(_drug_pair(), st.sampled_from(_CANONICAL_SEVERITIES)), max_size=6),
    openfda=st.lists(
        st.tuples(
            _drug_pair(),
            st.integers(min_value=0, max_value=50),  # label_mentions
            st.integers(min_value=0, max_value=500),  # event_reports
        ),
        max_size=8,
    ),
)
def test_property_6_openfda_only_evidence_never_creates_standalone_alert(
    local: list[tuple[tuple[str, str], str]],
    rxnav: list[tuple[tuple[str, str], str]],
    openfda: list[tuple[tuple[str, str], int, int]],
) -> None:
    """Feature: product-polish-analytics, Property 6: openFDA-only evidence never creates a standalone alert.

    Validates: Requirements 3.2
    """
    local_alerts = [
        _drug_drug_alert(pair, severity, "local_rules") for pair, severity in local
    ]
    external_alerts = [
        _drug_drug_alert(pair, severity, "rxnav") for pair, severity in rxnav
    ]
    openfda_evidence = {
        tuple(sorted(pair)): {
            "label_mentions": label_mentions,
            "event_reports": event_reports,
        }
        for pair, label_mentions, event_reports in openfda
    }

    merged = _merge_drug_alerts(local_alerts, external_alerts, openfda_evidence)

    merged_keys = {_pair_key(alert["medications"]) for alert in merged}
    preexisting_keys = {
        _pair_key(alert["medications"])
        for alert in (*local_alerts, *external_alerts)
        if len(_pair_key(alert["medications"])) >= 2
    }
    openfda_keys = set(openfda_evidence.keys())

    # Core invariant: every alert in the merged output must trace back to a
    # pre-existing local or RxNav alert. No standalone alert is fabricated.
    assert merged_keys <= preexisting_keys

    # A pair whose ONLY evidence is openFDA co-occurrence is never present.
    openfda_only_keys = openfda_keys - preexisting_keys
    assert merged_keys.isdisjoint(openfda_only_keys)

    # When openFDA evidence coincides with a pre-existing alert, it attaches as
    # enrichment (source tag + evidence counts) rather than a new alert.
    merged_by_key = {_pair_key(alert["medications"]): alert for alert in merged}
    for key in openfda_keys & preexisting_keys:
        enriched = merged_by_key[key]
        assert "openfda" in set(str(enriched.get("source", "")).split(","))
        evidence = enriched.get("evidence", {})
        assert evidence.get("openfda_label_mentions") == openfda_evidence[key]["label_mentions"]
        assert evidence.get("openfda_event_reports") == openfda_evidence[key]["event_reports"]


# ---------------------------------------------------------------------------
# Property 7: a medium drug_drug alert floors the overall risk at medium.
# ---------------------------------------------------------------------------


@st.composite
def _ddi_alert_set(draw: st.DrawFn) -> list[dict[str, Any]]:
    """Generate a mixed set of drug_drug and drug_allergy alerts."""
    drug_drug = draw(
        st.lists(
            st.tuples(_drug_pair(), st.sampled_from(_CANONICAL_SEVERITIES)),
            max_size=6,
        )
    )
    allergy = draw(
        st.lists(
            st.tuples(st.sampled_from(_MED_POOL), st.sampled_from(_CANONICAL_SEVERITIES)),
            max_size=3,
        )
    )
    alerts: list[dict[str, Any]] = [
        _drug_drug_alert(pair, severity, "local_rules") for pair, severity in drug_drug
    ]
    alerts.extend(
        {
            "type": "drug_allergy",
            "severity": severity,
            "medications": [med],
            "message": f"Allergy conflict for {med}.",
            "source": "local_rules",
        }
        for med, severity in allergy
    )
    return alerts


def _has_drug_drug_with(alerts: list[dict[str, Any]], severities: set[str]) -> bool:
    return any(
        alert.get("type") == "drug_drug"
        and _normalize_severity(alert.get("severity")) in severities
        for alert in alerts
    )


@settings(max_examples=200)
@given(
    alerts=_ddi_alert_set(),
    critical_symptoms=st.lists(st.sampled_from(_CRITICAL_SYMPTOM_POOL), max_size=4, unique=True),
    lab_flags=st.lists(st.sampled_from(_LAB_FLAG_POOL), max_size=2, unique=True),
)
def test_property_7_medium_drug_drug_floors_overall_risk_at_medium(
    alerts: list[dict[str, Any]],
    critical_symptoms: list[str],
    lab_flags: list[str],
) -> None:
    """Feature: product-polish-analytics, Property 7: a medium drug_drug alert floors the overall risk at medium.

    Validates: Requirements 3.3
    """
    _, level = _risk_from_signals(alerts, critical_symptoms, lab_flags)
    level_rank = _SEVERITY_RANK[level]

    # (1) Medium floor: a medium drug_drug alert forces overall risk >= medium.
    if _has_drug_drug_with(alerts, {"medium"}):
        assert level_rank >= _SEVERITY_RANK["medium"]

    # (3) High/critical aggregation unchanged: the medium floor only raises a
    # sub-medium level, so a high/critical drug_drug alert is never reduced to
    # medium even when a medium alert co-exists in the same set.
    if _has_drug_drug_with(alerts, {"high", "critical"}):
        assert level_rank >= _SEVERITY_RANK["high"]


@settings(max_examples=200)
@given(
    low_alerts=st.lists(
        st.tuples(_drug_pair(), st.just("low")),
        max_size=6,
    )
)
def test_property_7_genuine_low_alert_set_is_not_bumped(
    low_alerts: list[tuple[tuple[str, str], str]],
) -> None:
    """Feature: product-polish-analytics, Property 7: a genuine low alert set is not floored upward.

    Validates: Requirements 3.3
    """
    alerts = [_drug_drug_alert(pair, severity, "local_rules") for pair, severity in low_alerts]

    # A set of only low-severity drug_drug alerts, with no critical symptoms or
    # lab flags, has no medium signal to trigger the floor and must stay low.
    _, level = _risk_from_signals(alerts, [], [])
    assert level == "low"
