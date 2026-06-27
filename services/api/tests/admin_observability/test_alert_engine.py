"""Unit tests for the threshold alert engine (task 8.1).

Feature: clara-admin-observability

Covers the alert engine contract from Requirement 8.1/8.4/8.5 at the example
level:

* ``Alert`` enforces a bounded severity and a non-empty stable id;
* ``evaluate`` produces stable ids + bounded severities for the ML, API-5xx, and
  flow rules, and is inert when alerting is disabled (flags-off baseline);
* ``reconcile`` persists not-firing→firing and firing→cleared transitions to
  ``alert_state`` and returns a newly-firing state only once per transition
  (dedupe / single-fire);
* ``acknowledge`` persists the acknowledged state and a clear-and-refire resets
  it so the alert is presented as new again.

These compose with the repo-root conftest (real ``alert_state`` table via
``Base.metadata.create_all`` + per-test row reset) and the package conftest
(``set_flags`` to flip ``admin_observability_alerting_enabled``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest

from clara_api.db.session import SessionLocal
from clara_api.observability import alerts as alerts_module
from clara_api.observability.alerts import (
    API_5XX_CRITICAL_PCT,
    API_5XX_WARN_PCT,
    SEVERITIES,
    STATE_CLEARED,
    STATE_FIRING,
    Alert,
    AlertEngine,
    AlertStateRow,
    stable_alert_id,
)

# Threshold-crossing inputs that fire all three rules at once.
_ALL_DOWN_DEPS = {"ml": {"status": "down"}}
_HOT_METRICS = {"server_error_rate_pct": 12.0}
_MISSING_FLOW = {"event_count": 0, "minutes_since_last_event": None}

# A healthy snapshot that fires nothing.
_OK_DEPS = {"ml": {"status": "ok"}}
_OK_METRICS = {"server_error_rate_pct": 0.0}
_FRESH_FLOW = {"event_count": 5, "minutes_since_last_event": 1.0}


def _enabled_engine() -> AlertEngine:
    return AlertEngine(SimpleNamespace(admin_observability_alerting_enabled=True))


def _disabled_engine() -> AlertEngine:
    return AlertEngine(SimpleNamespace(admin_observability_alerting_enabled=False))


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# Alert value object
# ---------------------------------------------------------------------------


def test_alert_rejects_unbounded_severity() -> None:
    with pytest.raises(ValueError):
        Alert(id="x:y", severity="fatal", source="api_runtime", message="bad")


def test_alert_rejects_empty_id() -> None:
    with pytest.raises(ValueError):
        Alert(id="", severity="warning", source="api_runtime", message="no id")


def test_stable_alert_id_is_deterministic() -> None:
    assert stable_alert_id("API", " api_runtime ") == stable_alert_id("api", "api_runtime")


# ---------------------------------------------------------------------------
# evaluate
# ---------------------------------------------------------------------------


def test_evaluate_is_inert_when_disabled() -> None:
    engine = _disabled_engine()
    assert engine.evaluate(_HOT_METRICS, _ALL_DOWN_DEPS, _MISSING_FLOW) == []


def test_evaluate_emits_stable_bounded_alerts_for_all_rules() -> None:
    engine = _enabled_engine()
    alerts = engine.evaluate(_HOT_METRICS, _ALL_DOWN_DEPS, _MISSING_FLOW)

    ids = {a.id for a in alerts}
    assert ids == {
        stable_alert_id("ml", "ml_dependency"),
        stable_alert_id("api", "api_runtime"),
        stable_alert_id("flow", "flow_event_stream"),
    }
    # Every alert has a bounded severity and a non-empty stable id.
    for alert in alerts:
        assert alert.severity in SEVERITIES
        assert alert.id


def test_evaluate_healthy_snapshot_fires_nothing() -> None:
    engine = _enabled_engine()
    assert engine.evaluate(_OK_METRICS, _OK_DEPS, _FRESH_FLOW) == []


def test_evaluate_ml_degraded_is_warning_unreachable_is_critical() -> None:
    engine = _enabled_engine()
    degraded = engine.evaluate(_OK_METRICS, {"ml": {"status": "degraded"}}, _FRESH_FLOW)
    assert [a.severity for a in degraded] == ["warning"]

    down = engine.evaluate(_OK_METRICS, {"ml": {"status": "down"}}, _FRESH_FLOW)
    assert [a.severity for a in down] == ["critical"]


def test_evaluate_api_5xx_warn_vs_critical_band() -> None:
    engine = _enabled_engine()
    warn = engine.evaluate({"server_error_rate_pct": API_5XX_WARN_PCT}, _OK_DEPS, _FRESH_FLOW)
    assert [a.severity for a in warn] == ["warning"]

    critical = engine.evaluate(
        {"server_error_rate_pct": API_5XX_CRITICAL_PCT}, _OK_DEPS, _FRESH_FLOW
    )
    assert [a.severity for a in critical] == ["critical"]

    below = engine.evaluate(
        {"server_error_rate_pct": API_5XX_WARN_PCT - 0.1}, _OK_DEPS, _FRESH_FLOW
    )
    assert below == []


def test_evaluate_flow_stale_and_missing() -> None:
    engine = _enabled_engine()
    stale = engine.evaluate(
        _OK_METRICS, _OK_DEPS, {"event_count": 3, "minutes_since_last_event": 99.0}
    )
    assert [a.id for a in stale] == [stable_alert_id("flow", "flow_event_stream")]

    missing = engine.evaluate(_OK_METRICS, _OK_DEPS, {"event_count": 0})
    assert [a.id for a in missing] == [stable_alert_id("flow", "flow_event_stream")]


# ---------------------------------------------------------------------------
# reconcile
# ---------------------------------------------------------------------------


def test_reconcile_is_inert_when_disabled(db) -> None:
    engine = _disabled_engine()
    alerts = [Alert(id="api:api_runtime", severity="critical", source="api_runtime", message="x")]
    assert engine.reconcile(db, alerts) == []
    assert db.query(AlertStateRow).count() == 0


def test_reconcile_persists_firing_then_dedupes(db) -> None:
    engine = _enabled_engine()
    alerts = engine.evaluate(_HOT_METRICS, _ALL_DOWN_DEPS, _MISSING_FLOW)

    first = engine.reconcile(db, alerts)
    # All three transition into firing on the first evaluation.
    assert len(first) == 3
    rows = {r.alert_id: r for r in db.query(AlertStateRow).all()}
    assert all(r.state == STATE_FIRING for r in rows.values())

    # A second evaluation of the *same* persistent condition fires nothing new.
    second = engine.reconcile(db, alerts)
    assert second == []
    assert db.query(AlertStateRow).count() == 3


def test_reconcile_clears_resolved_alerts(db) -> None:
    engine = _enabled_engine()
    firing = engine.evaluate(_HOT_METRICS, _ALL_DOWN_DEPS, _MISSING_FLOW)
    engine.reconcile(db, firing)

    # Everything recovers → no alerts → all rows transition to cleared.
    engine.reconcile(db, [])
    rows = db.query(AlertStateRow).all()
    assert rows
    assert all(r.state == STATE_CLEARED for r in rows)


def test_reconcile_refire_resets_acknowledged(db) -> None:
    engine = _enabled_engine()
    api_alert = [
        Alert(id="api:api_runtime", severity="critical", source="api_runtime", message="x")
    ]

    engine.reconcile(db, api_alert)
    engine.acknowledge(db, "api:api_runtime")
    assert db.get(AlertStateRow, "api:api_runtime").acknowledged is True

    # Clear, then re-fire: the alert is presented as new again (ack reset).
    engine.reconcile(db, [])
    assert db.get(AlertStateRow, "api:api_runtime").state == STATE_CLEARED

    refired = engine.reconcile(db, api_alert)
    assert [s.alert_id for s in refired] == ["api:api_runtime"]
    row = db.get(AlertStateRow, "api:api_runtime")
    assert row.state == STATE_FIRING
    assert row.acknowledged is False


# ---------------------------------------------------------------------------
# acknowledge
# ---------------------------------------------------------------------------


def test_acknowledge_is_inert_when_disabled(db) -> None:
    engine = _disabled_engine()
    assert engine.acknowledge(db, "api:api_runtime") is None


def test_acknowledge_unknown_id_is_noop(db) -> None:
    engine = _enabled_engine()
    assert engine.acknowledge(db, "does:not-exist") is None


def test_acknowledge_persists_state(db) -> None:
    engine = _enabled_engine()
    engine.reconcile(
        db,
        [Alert(id="api:api_runtime", severity="warning", source="api_runtime", message="x")],
    )
    state = engine.acknowledge(db, "api:api_runtime")
    assert state is not None
    assert state.acknowledged is True
    assert isinstance(state.last_evaluated_at, datetime)
    assert state.last_evaluated_at.tzinfo is not None
    assert state.last_evaluated_at <= datetime.now(tz=UTC)


# ---------------------------------------------------------------------------
# deliver (task 8.2 — no-PII webhook delivery)
# ---------------------------------------------------------------------------


class _FakeResponse:
    """Minimal httpx.Response stand-in for delivery tests."""

    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"non-2xx: {self.status_code}", request=None, response=None
            )


def _delivery_engine(*, enabled: bool = True, webhook_url: str = "") -> AlertEngine:
    return AlertEngine(
        SimpleNamespace(
            admin_observability_alerting_enabled=enabled,
            admin_observability_alert_webhook_url=webhook_url,
        )
    )


@pytest.fixture
def captured_posts(monkeypatch):
    """Patch the module-level httpx.post and capture every outbound call."""

    calls: list[dict] = []

    def _fake_post(url, *, json=None, timeout=None):  # noqa: ANN001, ANN202
        calls.append({"url": url, "json": json, "timeout": timeout})
        return _FakeResponse(200)

    monkeypatch.setattr(alerts_module.httpx, "post", _fake_post)
    return calls


_FIRED = [Alert(id="api:api_runtime", severity="critical", source="api_runtime", message="x")]


def test_deliver_is_inert_when_disabled(captured_posts) -> None:
    engine = _delivery_engine(enabled=False, webhook_url="https://hook.example/alerts")
    engine.deliver(_FIRED)
    assert captured_posts == []


def test_deliver_no_url_is_in_app_only_no_post(captured_posts) -> None:
    engine = _delivery_engine(enabled=True, webhook_url="")
    engine.deliver(_FIRED)
    assert captured_posts == []


def test_deliver_empty_fired_makes_no_post(captured_posts) -> None:
    engine = _delivery_engine(enabled=True, webhook_url="https://hook.example/alerts")
    engine.deliver([])
    assert captured_posts == []


def test_deliver_posts_pii_free_payload(captured_posts) -> None:
    engine = _delivery_engine(enabled=True, webhook_url="https://hook.example/alerts")
    fired = [
        Alert(
            id="api:api_runtime",
            severity="critical",
            source="api_runtime",
            message="API 5xx ratio high",
            # PII injected via a denylisted key and a value-level marker.
            context={"email": "leak@example.com", "count": 3},
        )
    ]

    engine.deliver(fired)

    assert len(captured_posts) == 1
    call = captured_posts[0]
    assert call["url"] == "https://hook.example/alerts"
    assert call["timeout"] == alerts_module._DELIVERY_TIMEOUT_SECONDS

    body = call["json"]
    assert body["count"] == 1
    delivered = body["alerts"][0]
    # The denylisted PII key is dropped and the safe count survives.
    assert "email" not in delivered["context"]
    assert delivered["context"]["count"] == 3
    # No PII value markers anywhere in the serialized payload.
    import json as _json

    assert "leak@example.com" not in _json.dumps(body)


def test_deliver_swallows_connection_failure(monkeypatch) -> None:
    engine = _delivery_engine(enabled=True, webhook_url="https://hook.example/alerts")

    def _boom(url, *, json=None, timeout=None):  # noqa: ANN001, ANN202
        raise httpx.ConnectError("unreachable")

    monkeypatch.setattr(alerts_module.httpx, "post", _boom)

    # Must not raise — failures are swallowed (Requirement 8.6).
    engine.deliver(_FIRED)


def test_deliver_swallows_non_2xx_response(monkeypatch) -> None:
    engine = _delivery_engine(enabled=True, webhook_url="https://hook.example/alerts")

    def _server_error(url, *, json=None, timeout=None):  # noqa: ANN001, ANN202
        return _FakeResponse(503)

    monkeypatch.setattr(alerts_module.httpx, "post", _server_error)

    # raise_for_status raises on 5xx; deliver must swallow it (Requirement 8.6).
    engine.deliver(_FIRED)
