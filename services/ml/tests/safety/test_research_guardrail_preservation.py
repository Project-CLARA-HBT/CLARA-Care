"""Guardrail-preservation assertions for the CLARA Research enhancement.

Feature: clara-research, task 21.1 — Implement guardrail-preservation assertions.

Epic 18 (Requirement 20) requires that *every* existing medical-safety guardrail
keeps behaving exactly as before once the deep-research enhancements ship. Every
new research behavior is additive and lands behind a default-off ``RESEARCH_*``
feature flag, so the safety contract reduces to a single invariant:

    Toggling the new research feature flags can never move a guardrail decision.

This suite locks that invariant for the guardrails called out in Requirement
20.1 and 20.5 by capturing each guardrail decision with **all research flags
OFF** (legacy behavior) and with **all research flags ON** and asserting the
decisions are identical, then pinning each decision to a golden value so any
future drift in the guardrail itself also trips the suite:

* DDI **medium-floor** (``clara_ml.agents.careguard``) — R20.1.
* openFDA free-text **severity cap** at "high"
  (``clara_ml.clients.drug_sources``) — R20.1.
* **FIDES CRITICAL / contradiction** block
  (``clara_ml.factcheck.fides_lite``) — R20.1.
* Emergency **fast-path** routing (``clara_ml.routing``) — R20.1.
* Legal / dosage **block** (``clara_ml.main._detect_legal_guard_violation``) —
  R20.1.
* Self-medication **consent gate** (mirrors the ``services/api`` gate) — R20.1.
* Decision-support **disclaimer** retention
  (``clara_ml.agents.research_tier2``) — R20.5.

This file is TEST-ONLY and reuses the shared safety fixtures
(``tests/safety/fixtures.py``) and decision-capture probes
(``tests/safety/harness.py``) verbatim; it differs from the persistent-RAG
guardrail suite only in which feature flags it sweeps.
"""

from __future__ import annotations

import pytest

from clara_ml.agents.research_tier2 import (
    _DECISION_SUPPORT_DISCLAIMER_BY_LANGUAGE,
    _apply_role_adaptive_output,
    _load_decision_support_disclaimer,
)
from clara_ml.config import settings as _settings

from . import fixtures as fx
from . import harness as hz

# ---------------------------------------------------------------------------
# CLARA Research feature flags (the "switches" the enhancement ships behind).
# ---------------------------------------------------------------------------

#: Every boolean ML-side ``RESEARCH_*`` flag declared for this enhancement
#: (task 1.1). Flag-OFF == every one False (legacy pipeline). Flag-ON == every
#: one True (all enhancements active). A guardrail decision MUST be identical in
#: both states (R20.1/R20.2).
RESEARCH_ML_FLAGS: tuple[str, ...] = (
    "research_query_decomposition_enabled",
    "research_gap_fill_enabled",
    "research_recency_trust_ranking_enabled",
    "research_pico_enabled",
    "research_grade_enabled",
    "research_evidence_signals_enabled",
    "research_consensus_enabled",
    "research_claim_trace_enabled",
    "research_role_adaptive_output_enabled",
)

#: The default-preserving value of the bounded gap-fill budget (legacy state)
#: and a saturated value used when every enhancement is on.
_GAP_FILL_MAX_OFF = 2
_GAP_FILL_MAX_ON = 8


def apply_research_flag_state(
    monkeypatch: pytest.MonkeyPatch,
    *,
    enabled: bool,
) -> None:
    """Set every CLARA Research feature flag on ``settings`` to ``enabled``.

    Also pins the NLI LLM path off so the FIDES capture stays deterministic and
    offline regardless of ambient configuration (mirrors
    ``harness.apply_flag_state``).
    """

    for flag in RESEARCH_ML_FLAGS:
        monkeypatch.setattr(_settings, flag, enabled, raising=False)
    monkeypatch.setattr(
        _settings,
        "research_gap_fill_max_passes",
        _GAP_FILL_MAX_ON if enabled else _GAP_FILL_MAX_OFF,
        raising=False,
    )
    # Keep FIDES claim verification on its deterministic, offline path.
    monkeypatch.setattr(_settings, "rag_nli_llm_enabled", False, raising=False)
    # The CareGuard DDI floor consults ``careguard_drugbank_enabled`` to decide
    # whether to merge the optional DrugBank shard layer. Pin it to its
    # default-preserving, network-free local-rules path (False) so the DDI-floor
    # decision is deterministic and orthogonal to the research flags under test.
    # ``object.__setattr__`` is used (not ``monkeypatch``) because the toggle may
    # not be a declared field in every build, and pydantic cannot ``delattr`` a
    # non-field on teardown; leaving it at its ``False`` default is benign.
    if getattr(_settings, "careguard_drugbank_enabled", None) is not False:
        object.__setattr__(_settings, "careguard_drugbank_enabled", False)


# ---------------------------------------------------------------------------
# 1. CareGuard DDI medium-floor (Requirement 20.1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("payload", fx.DDI_PAYLOADS, ids=lambda p: p.label)
def test_ddi_floor_no_drift_between_research_flag_states(
    payload: fx.DdiPayload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CareGuard decision is identical research-flags-OFF vs research-flags-ON."""

    request = payload.as_request()

    apply_research_flag_state(monkeypatch, enabled=False)
    baseline = hz.capture_careguard_decision(request)

    apply_research_flag_state(monkeypatch, enabled=True)
    with_research = hz.capture_careguard_decision(request)

    assert with_research == baseline, (
        f"CareGuard decision drifted for {payload.label} when research flags toggled"
    )


@pytest.mark.parametrize("payload", fx.DDI_PAYLOADS, ids=lambda p: p.label)
def test_ddi_floor_holds_at_or_above_expected_minimum(
    payload: fx.DdiPayload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A flagged pair never surfaces below its expected severity floor."""

    floor = hz.severity_rank(payload.min_severity)

    for enabled in (False, True):
        apply_research_flag_state(monkeypatch, enabled=enabled)
        decision = hz.capture_careguard_decision(payload.as_request())

        assert hz.severity_rank(decision["risk_level"]) >= floor

        matched = [
            alert_sev
            for alert_sev, _meds, alert_type, _msg in decision["alerts"]
            if alert_type == "drug_drug"
        ]
        assert matched, f"expected a drug_drug alert for {payload.label}"
        assert max(hz.severity_rank(sev) for sev in matched) >= floor


def test_ddi_medium_pair_never_collapses_to_low(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Golden baseline: clopidogrel+omeprazole stays medium under research flags."""

    for enabled in (False, True):
        apply_research_flag_state(monkeypatch, enabled=enabled)
        decision = hz.capture_careguard_decision(fx.DDI_MEDIUM_PAYLOAD.as_request())
        assert decision["risk_level"] == "medium"
        assert any(
            sev == "medium" and alert_type == "drug_drug"
            for sev, _meds, alert_type, _msg in decision["alerts"]
        )


# ---------------------------------------------------------------------------
# 2. openFDA free-text severity cap at "high" (Requirement 20.1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("window", fx.OPENFDA_SEVERITY_WINDOWS)
def test_openfda_severity_cap_no_drift_and_never_critical(
    window: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """openFDA free-text severity is capped at "high" in both research-flag states."""

    apply_research_flag_state(monkeypatch, enabled=False)
    baseline = hz.capture_openfda_severity(window)

    apply_research_flag_state(monkeypatch, enabled=True)
    with_research = hz.capture_openfda_severity(window)

    assert with_research == baseline
    assert with_research in {"medium", "high"}
    assert hz.severity_rank(with_research) <= hz.severity_rank("high")


# ---------------------------------------------------------------------------
# 3. FIDES CRITICAL / contradiction blocking (Requirement 20.1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("payload", fx.CRITICAL_CLAIM_PAYLOADS, ids=lambda p: p.label)
def test_fides_contradiction_block_no_drift_between_research_flag_states(
    payload: fx.FidesPayload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A contradiction (CRITICAL) verdict is identical OFF vs ON."""

    apply_research_flag_state(monkeypatch, enabled=False)
    baseline = hz.capture_fides_decision(payload.answer, payload.retrieved_context)

    apply_research_flag_state(monkeypatch, enabled=True)
    with_research = hz.capture_fides_decision(payload.answer, payload.retrieved_context)

    assert with_research == baseline


@pytest.mark.parametrize("payload", fx.CRITICAL_CLAIM_PAYLOADS, ids=lambda p: p.label)
def test_fides_critical_payloads_still_block(
    payload: fx.FidesPayload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Golden baseline: each CRITICAL payload yields a blocking 'fail' verdict."""

    for enabled in (False, True):
        apply_research_flag_state(monkeypatch, enabled=enabled)
        decision = hz.capture_fides_decision(payload.answer, payload.retrieved_context)
        assert decision["verdict"] == "fail"
        assert decision["has_contradiction"] is True


def test_fides_supported_claim_is_not_falsely_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Control: a supported claim passes, proving the harness isn't trivial."""

    payload = fx.SUPPORTED_CLAIM_PAYLOAD
    for enabled in (False, True):
        apply_research_flag_state(monkeypatch, enabled=enabled)
        decision = hz.capture_fides_decision(payload.answer, payload.retrieved_context)
        assert decision["verdict"] == "pass"
        assert decision["has_contradiction"] is False


# ---------------------------------------------------------------------------
# 4. Emergency fast-path routing (Requirement 20.1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("query", fx.EMERGENCY_QUERIES)
def test_emergency_fastpath_no_drift_and_triggers(
    query: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Emergency routing is identical OFF vs ON and still triggers."""

    apply_research_flag_state(monkeypatch, enabled=False)
    baseline = hz.capture_emergency_route(query)

    apply_research_flag_state(monkeypatch, enabled=True)
    with_research = hz.capture_emergency_route(query)

    assert with_research == baseline
    assert with_research["emergency"] is True
    assert with_research["intent"] == "emergency_triage"


@pytest.mark.parametrize("query", fx.NON_EMERGENCY_QUERIES)
def test_non_emergency_queries_do_not_trigger_fastpath(
    query: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Control: benign queries never take the emergency fast-path."""

    for enabled in (False, True):
        apply_research_flag_state(monkeypatch, enabled=enabled)
        decision = hz.capture_emergency_route(query)
        assert decision["emergency"] is False


# ---------------------------------------------------------------------------
# 5. Legal / dosage guard block (Requirement 20.1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", fx.LEGAL_GUARD_QUERIES, ids=lambda c: c.label)
def test_legal_guard_block_no_drift_and_blocks(
    case: fx.LegalGuardQuery,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legal/dosage blocking is identical OFF vs ON and still blocks.

    The guard runs in the research channel, exactly as ``/v1/research/tier2``
    invokes it before any retrieval/synthesis change can alter the decision.
    """

    apply_research_flag_state(monkeypatch, enabled=False)
    baseline = hz.capture_legal_guard(case.query, channel="research")

    apply_research_flag_state(monkeypatch, enabled=True)
    with_research = hz.capture_legal_guard(case.query, channel="research")

    assert with_research == baseline
    assert with_research["blocked"] is True
    assert with_research["reason"] == case.reason


@pytest.mark.parametrize("query", fx.LEGAL_GUARD_SAFE_QUERIES)
def test_benign_queries_not_blocked_by_legal_guard(
    query: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Control: benign queries are not blocked by the legal/dosage guard."""

    for enabled in (False, True):
        apply_research_flag_state(monkeypatch, enabled=enabled)
        decision = hz.capture_legal_guard(query, channel="research")
        assert decision["blocked"] is False


# ---------------------------------------------------------------------------
# 6. Self-medication consent gate (Requirement 20.1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("state", fx.CONSENT_STATES, ids=lambda s: s.label)
def test_consent_gate_no_drift_and_blocks_when_absent(
    state: fx.ConsentState,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The consent-gate decision is unaffected by the research flags.

    The gate blocks exactly when consent is absent (HTTP 428), in both flag
    states. The decision is a pure function of consent state and never reads any
    research flag, so toggling them must not move it.
    """

    apply_research_flag_state(monkeypatch, enabled=False)
    baseline = hz.capture_consent_gate(granted=state.granted)

    apply_research_flag_state(monkeypatch, enabled=True)
    with_research = hz.capture_consent_gate(granted=state.granted)

    assert with_research == baseline
    assert with_research["blocked"] is (not state.granted)
    if not state.granted:
        assert with_research["reason"] == hz.CONSENT_REQUIRED_REASON
        assert with_research["status_code"] == hz.CONSENT_BLOCK_STATUS


# ---------------------------------------------------------------------------
# 7. Decision-support disclaimer retention (Requirement 20.5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("answer_language", ["vi", "en"])
def test_disclaimer_asset_available_in_both_languages(
    answer_language: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The decision-support disclaimer asset is available regardless of flags."""

    for enabled in (False, True):
        apply_research_flag_state(monkeypatch, enabled=enabled)
        disclaimer = _load_decision_support_disclaimer(answer_language)
        assert disclaimer is not None
        assert disclaimer == _DECISION_SUPPORT_DISCLAIMER_BY_LANGUAGE[answer_language]
        # The disclaimer states outputs are decision support, not treatment
        # orders, and that CLARA-Care is not a medical device or EMR (R20.5).
        if answer_language == "en":
            assert "not a treatment order" in disclaimer
            assert "not a medical device or EMR" in disclaimer
        else:
            assert "hỗ trợ quyết định" in disclaimer
            assert "không phải là thiết bị y tế" in disclaimer


@pytest.mark.parametrize("role", list(fx.ALL_ROLES) + ["researcher", "unknown", None])
@pytest.mark.parametrize("answer_language", ["vi", "en"])
def test_disclaimer_retained_in_every_role_profile(
    role: str | None,
    answer_language: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every role's role-adaptive output retains the decision-support disclaimer.

    R20.5/R14.5: whenever the disclaimer asset is available, the delivered output
    for every role carries the disclaimer and records ``disclaimer_present`` as
    True. This holds with the rest of the research flags both off and on.
    """

    base_answer = "## Tóm tắt\n\nNội dung phân tích bằng chứng."
    expected_disclaimer = _DECISION_SUPPORT_DISCLAIMER_BY_LANGUAGE[answer_language]

    for enabled in (False, True):
        apply_research_flag_state(monkeypatch, enabled=enabled)
        rendered, output_profile, disclaimer_present = _apply_role_adaptive_output(
            base_answer,
            role=role,
            answer_language=answer_language,
        )
        assert disclaimer_present is True
        assert expected_disclaimer in rendered
        assert output_profile in {"normal", "researcher", "doctor"}


def test_disclaimer_not_duplicated_when_already_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The disclaimer is retained exactly once even if already in the draft."""

    apply_research_flag_state(monkeypatch, enabled=True)
    disclaimer = _DECISION_SUPPORT_DISCLAIMER_BY_LANGUAGE["vi"]
    draft = f"## Tóm tắt\n\nNội dung.\n\n{disclaimer}\n"

    rendered, _profile, disclaimer_present = _apply_role_adaptive_output(
        draft,
        role="doctor",
        answer_language="vi",
    )

    assert disclaimer_present is True
    assert rendered.count(disclaimer) == 1


# ---------------------------------------------------------------------------
# 8. Aggregate no-drift sweep across every locked guardrail
# ---------------------------------------------------------------------------


def _all_research_guardrail_probes() -> list[tuple[str, hz.Probe]]:
    """Every locked guardrail decision as a zero-arg probe."""

    probes: list[tuple[str, hz.Probe]] = []
    for payload in fx.DDI_PAYLOADS:
        request = payload.as_request()
        probes.append(
            (f"ddi:{payload.label}", lambda r=request: hz.capture_careguard_decision(r))
        )
    for window in fx.OPENFDA_SEVERITY_WINDOWS:
        probes.append(
            (f"openfda:{window!r}", lambda w=window: hz.capture_openfda_severity(w))
        )
    for payload in fx.CRITICAL_CLAIM_PAYLOADS:
        probes.append(
            (
                f"fides:{payload.label}",
                lambda p=payload: hz.capture_fides_decision(
                    p.answer, p.retrieved_context
                ),
            )
        )
    for query in fx.EMERGENCY_QUERIES:
        probes.append((f"emergency:{query}", lambda q=query: hz.capture_emergency_route(q)))
    for case in fx.LEGAL_GUARD_QUERIES:
        probes.append(
            (
                f"legal:{case.label}",
                lambda c=case: hz.capture_legal_guard(c.query, channel="research"),
            )
        )
    for state in fx.CONSENT_STATES:
        probes.append(
            (f"consent:{state.label}", lambda s=state: hz.capture_consent_gate(granted=s.granted))
        )
    return probes


def test_no_guardrail_drift_across_all_research_flag_probes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Single sweep: no locked guardrail drifts when research flags flip."""

    drifted: list[str] = []
    for name, probe in _all_research_guardrail_probes():
        apply_research_flag_state(monkeypatch, enabled=False)
        baseline = probe()
        apply_research_flag_state(monkeypatch, enabled=True)
        with_research = probe()
        if with_research != baseline:
            drifted.append(name)

    assert not drifted, f"guardrail decisions drifted under research flags: {drifted}"
