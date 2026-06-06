"""Guardrail preservation golden-output harness (task 11.1).

This is the *baseline lock* for Epic 11. It captures the medical-safety
guardrail decisions and asserts there is **no behavioral drift** between:

* **flag-OFF**  — every persistent ``RAG_*`` flag False (legacy behavior), and
* **flag-ON**   — every persistent ``RAG_*`` flag True (persistent RAG enabled).

The persistent-RAG additions must be *inert* with respect to every guardrail:
toggling them can never move a guardrail decision. Each test therefore captures
the decision in both flag states and asserts they are identical, and also pins
the decision to a hardcoded golden value so any future drift in the guardrail
itself (not just the flags) trips the suite.

Guardrails LOCKED here (ML-side, live in ``services/ml``):

* CareGuard DDI **medium-floor** + openFDA free-text **severity cap** at "high"
  (``clara_ml.agents.careguard`` + ``clara_ml.clients.drug_sources``).
* FIDES **CRITICAL / contradiction** blocking
  (``clara_ml.factcheck.fides_lite``).
* Emergency **fast-path** routing (``clara_ml.routing`` — the ML-side core of
  the fast-path that runs before any retrieval/synthesis change).
* Legal / dosage **block** (``clara_ml.main._detect_legal_guard_violation``).

Guardrails DOCUMENTED as seams (enforced in ``services/api`` / web, asserted by
the Epic 11 property tests 11.2-11.6) — see ``test_documented_api_side_seams``.

Shared fixtures live in ``tests/safety/fixtures.py`` and are reused verbatim by
the property tests 11.2-11.6.
"""

from __future__ import annotations

import pytest

from . import fixtures as fx
from . import harness as hz

# ---------------------------------------------------------------------------
# 1. CareGuard DDI medium-floor (Requirement 14.1 / Property 24)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("payload", fx.DDI_PAYLOADS, ids=lambda p: p.label)
def test_ddi_floor_no_drift_between_flag_states(
    payload: fx.DdiPayload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CareGuard decision is identical flag-OFF vs flag-ON."""

    request = payload.as_request()

    hz.apply_flag_state(monkeypatch, enabled=False)
    baseline = hz.capture_careguard_decision(request)

    hz.apply_flag_state(monkeypatch, enabled=True)
    with_rag = hz.capture_careguard_decision(request)

    assert with_rag == baseline, (
        f"CareGuard decision drifted for {payload.label} when RAG flags toggled"
    )


@pytest.mark.parametrize("payload", fx.DDI_PAYLOADS, ids=lambda p: p.label)
def test_ddi_floor_holds_at_or_above_expected_minimum(
    payload: fx.DdiPayload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A flagged pair never surfaces below its expected severity floor.

    Locks the medium-floor invariant: the medium pair never collapses to "low"
    and the high pair stays at/above "high", under both flag states.
    """

    floor = hz.severity_rank(payload.min_severity)

    for enabled in (False, True):
        hz.apply_flag_state(monkeypatch, enabled=enabled)
        decision = hz.capture_careguard_decision(payload.as_request())

        # The aggregated risk level respects the floor.
        assert hz.severity_rank(decision["risk_level"]) >= floor

        # The pair's own DDI alert is present and respects the floor.
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
    """Golden baseline: clopidogrel+omeprazole stays medium in both states."""

    for enabled in (False, True):
        hz.apply_flag_state(monkeypatch, enabled=enabled)
        decision = hz.capture_careguard_decision(fx.DDI_MEDIUM_PAYLOAD.as_request())
        assert decision["risk_level"] == "medium"
        assert any(
            sev == "medium" and alert_type == "drug_drug"
            for sev, _meds, alert_type, _msg in decision["alerts"]
        )


# ---------------------------------------------------------------------------
# 2. openFDA free-text severity cap at "high" (Requirement 14.1 / Property 24)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("window", fx.OPENFDA_SEVERITY_WINDOWS)
def test_openfda_severity_cap_no_drift_and_never_critical(
    window: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """openFDA free-text severity is capped at "high" in both flag states."""

    hz.apply_flag_state(monkeypatch, enabled=False)
    baseline = hz.capture_openfda_severity(window)

    hz.apply_flag_state(monkeypatch, enabled=True)
    with_rag = hz.capture_openfda_severity(window)

    assert with_rag == baseline
    # The cap: free-text-derived severity is never "critical".
    assert with_rag in {"medium", "high"}
    assert hz.severity_rank(with_rag) <= hz.severity_rank("high")


def test_openfda_severity_high_cap_golden_values() -> None:
    """Golden baseline values for the severity inference function."""

    assert hz.capture_openfda_severity("this combination is contraindicated") == "high"
    assert hz.capture_openfda_severity("monitor closely for bleeding") == "medium"
    # Even the most alarming free text never escalates past "high".
    assert hz.capture_openfda_severity("severe fatal contraindicated") == "high"


# ---------------------------------------------------------------------------
# 3. FIDES CRITICAL / contradiction blocking (Requirement 14.5 / Property 28)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload", fx.CRITICAL_CLAIM_PAYLOADS, ids=lambda p: p.label
)
def test_fides_contradiction_block_no_drift_between_flag_states(
    payload: fx.FidesPayload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A contradiction (CRITICAL) verdict is identical flag-OFF vs flag-ON."""

    hz.apply_flag_state(monkeypatch, enabled=False)
    baseline = hz.capture_fides_decision(payload.answer, payload.retrieved_context)

    hz.apply_flag_state(monkeypatch, enabled=True)
    with_rag = hz.capture_fides_decision(payload.answer, payload.retrieved_context)

    assert with_rag == baseline


@pytest.mark.parametrize(
    "payload", fx.CRITICAL_CLAIM_PAYLOADS, ids=lambda p: p.label
)
def test_fides_critical_payloads_still_block(
    payload: fx.FidesPayload,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Golden baseline: each CRITICAL payload yields a blocking 'fail' verdict."""

    for enabled in (False, True):
        hz.apply_flag_state(monkeypatch, enabled=enabled)
        decision = hz.capture_fides_decision(
            payload.answer, payload.retrieved_context
        )
        assert decision["verdict"] == "fail"
        assert decision["has_contradiction"] is True


def test_fides_supported_claim_is_not_falsely_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Control: a supported claim passes, proving the harness isn't trivial."""

    payload = fx.SUPPORTED_CLAIM_PAYLOAD
    for enabled in (False, True):
        hz.apply_flag_state(monkeypatch, enabled=enabled)
        decision = hz.capture_fides_decision(
            payload.answer, payload.retrieved_context
        )
        assert decision["verdict"] == "pass"
        assert decision["has_contradiction"] is False


# ---------------------------------------------------------------------------
# 4. Emergency fast-path routing (Requirement 14.4 / Property 27) — ML-side core
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("query", fx.EMERGENCY_QUERIES)
def test_emergency_fastpath_no_drift_and_triggers(
    query: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Emergency routing is identical flag-OFF vs flag-ON and still triggers."""

    hz.apply_flag_state(monkeypatch, enabled=False)
    baseline = hz.capture_emergency_route(query)

    hz.apply_flag_state(monkeypatch, enabled=True)
    with_rag = hz.capture_emergency_route(query)

    assert with_rag == baseline
    assert with_rag["emergency"] is True
    assert with_rag["intent"] == "emergency_triage"


@pytest.mark.parametrize("query", fx.NON_EMERGENCY_QUERIES)
def test_non_emergency_queries_do_not_trigger_fastpath(
    query: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Control: benign queries never take the emergency fast-path."""

    for enabled in (False, True):
        hz.apply_flag_state(monkeypatch, enabled=enabled)
        decision = hz.capture_emergency_route(query)
        assert decision["emergency"] is False


# ---------------------------------------------------------------------------
# 5. Legal / dosage guard block (Requirement 14.2 / Property 25) — ML-side core
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case", fx.LEGAL_GUARD_QUERIES, ids=lambda c: c.label
)
def test_legal_guard_block_no_drift_and_blocks(
    case: fx.LegalGuardQuery,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legal/dosage blocking is identical flag-OFF vs flag-ON and still blocks."""

    hz.apply_flag_state(monkeypatch, enabled=False)
    baseline = hz.capture_legal_guard(case.query)

    hz.apply_flag_state(monkeypatch, enabled=True)
    with_rag = hz.capture_legal_guard(case.query)

    assert with_rag == baseline
    assert with_rag["blocked"] is True
    assert with_rag["reason"] == case.reason


@pytest.mark.parametrize("query", fx.LEGAL_GUARD_SAFE_QUERIES)
def test_benign_queries_not_blocked_by_legal_guard(
    query: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Control: benign queries are not blocked by the legal/dosage guard."""

    for enabled in (False, True):
        hz.apply_flag_state(monkeypatch, enabled=enabled)
        decision = hz.capture_legal_guard(query)
        assert decision["blocked"] is False


# ---------------------------------------------------------------------------
# 6. Aggregate no-drift sweep across every locked ML-side guardrail
# ---------------------------------------------------------------------------


def _all_ml_side_probes() -> list[tuple[str, hz.Probe]]:
    """Every locked ML-side guardrail decision as a zero-arg probe."""

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
        probes.append((f"legal:{case.label}", lambda c=case: hz.capture_legal_guard(c.query)))
    return probes


def test_no_guardrail_drift_across_all_ml_side_probes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Single sweep: no locked ML-side guardrail drifts when RAG flags flip."""

    drifted: list[str] = []
    for name, probe in _all_ml_side_probes():
        hz.apply_flag_state(monkeypatch, enabled=False)
        baseline = probe()
        hz.apply_flag_state(monkeypatch, enabled=True)
        with_rag = probe()
        if with_rag != baseline:
            drifted.append(name)

    assert not drifted, f"guardrail decisions drifted under RAG flags: {drifted}"


# ---------------------------------------------------------------------------
# 7. Documented API-side seams (asserted by property tests 11.2-11.6)
# ---------------------------------------------------------------------------


def test_documented_api_side_seams() -> None:
    """Document the guardrail seams enforced outside ``services/ml``.

    This is a living checklist, not an enforcement test. The ML-side pieces of
    every guardrail are locked above. The pieces below are enforced in
    ``services/api`` / web and are asserted by the Epic 11 property tests:

    * Consent gate (Requirement 14.3 / Property 26) -> task 11.4.
      SEAM: ``services/api`` ``core/consent.py`` consent record + the
      ``apps/web`` ``selfmed-consent-gate.tsx`` flow. Use
      ``fixtures.CONSENT_STATES`` (granted/absent) + ``fixtures.AUTH_MARKERS``
      (cookie-vs-bearer) to assert the self-med flow blocks identically when
      consent is absent.
      TODO(11.4): assert block parity against ``services/api`` consent gate.

    * Emergency fast-path, full request flow (Requirement 14.4 / Property 27)
      -> task 11.5. The routing-level core is LOCKED above
      (``test_emergency_fastpath_*``); the end-to-end ``/v1/chat/routed``
      bypass of retrieval/synthesis is the API-side seam.
      TODO(11.5): assert the API request flow takes the fast-path before any
      retrieval/synthesis change can alter routing, using
      ``fixtures.EMERGENCY_QUERIES``.

    * Dosage / legal block, full request flow (Requirement 14.2 / Property 25)
      -> task 11.3. The detector is LOCKED above
      (``test_legal_guard_block_*``); the API-side seam is the end-to-end
      refusal contract on ``/v1/chat/routed`` + ``/v1/research``.
      TODO(11.3): assert the refusal contract using ``fixtures.LEGAL_GUARD_QUERIES``.

    * Admin RBAC (Requirement 13.1 / Property 23) -> services/api property test.
      SEAM: ``services/api`` ``/admin/rag/*`` endpoints behind
      ``require_roles("admin")``. Use ``fixtures.ALL_ROLES`` /
      ``fixtures.NON_ADMIN_ROLES`` + ``fixtures.AUTH_MARKERS`` to assert
      non-admin -> 403 and missing credential -> 401.
      TODO(api): assert RBAC rejection codes for ``/admin/rag/*``.
    """

    # The fixtures the seam tests will consume must exist and be non-empty so
    # the downstream property tests (11.2-11.6) have a stable contract.
    assert set(fx.ALL_ROLES) == {"admin", "doctor", "normal"}
    assert {c.granted for c in fx.CONSENT_STATES} == {True, False}
    assert fx.AUTH_COOKIE in fx.AUTH_MARKERS and fx.AUTH_BEARER in fx.AUTH_MARKERS
    assert fx.EMERGENCY_KEYWORDS_VI and fx.EMERGENCY_KEYWORDS_EN
    assert fx.CRITICAL_CLAIM_PAYLOADS and fx.DDI_PAYLOADS
