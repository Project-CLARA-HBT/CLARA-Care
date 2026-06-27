"""Threshold-based alert engine (Requirement 8).

Feature: clara-admin-observability (task 8.1)

This module promotes the previously ephemeral ``/system/ecosystem``
``federation_alerts`` into a stateful engine that produces stable, bounded
:class:`Alert` values, reconciles their firing/cleared transitions into the
``alert_state`` table, and records acknowledgements by stable id.

Design alignment
----------------
* ``Alert`` carries a *stable* id (deterministic from rule + target) used as the
  dedupe key, a *bounded* severity (``info`` | ``warning`` | ``critical``), the
  originating source, a bounded no-PII message, and a coarse, PII-free context.
* :meth:`AlertEngine.evaluate` mirrors the established ecosystem thresholds (ML
  unreachable/degraded, API 5xx warn/critical, flow events stale/missing) so the
  engine is a single source of truth derived from the existing observability
  primitives — no new collection path is introduced (Requirements 8.1, 10.3).
* :meth:`AlertEngine.reconcile` persists not-firing→firing and firing→cleared
  transitions to ``alert_state`` keyed by the stable id; re-firing a previously
  cleared alert resets its acknowledged flag so it is presented as new again,
  while a still-firing condition is *not* re-presented (Requirements 8.4, 8.5).
* :meth:`AlertEngine.acknowledge` persists the acknowledged state by stable id.

Everything is gated by ``admin_observability_alerting_enabled``. With the flag
off, :meth:`evaluate`, :meth:`reconcile`, :meth:`deliver`, and
:meth:`acknowledge` are inert (no-ops returning empty/``None``) and execute no
write or outbound path, so behavior equals the pre-feature baseline
(Requirement 12.2).

Webhook delivery (:meth:`deliver`, task 8.2) posts a PII-free projection of the
newly-firing alerts to ``admin_observability_alert_webhook_url`` and is
best-effort: with no URL configured it is in-app only, and any delivery failure
(network/timeout/non-2xx) is swallowed and never propagated so the evaluating
request is never broken (Requirements 8.2, 8.3, 8.6, 11.2). The acknowledge
endpoint is wired separately (task 8.3). The Alembic migration that creates
``alert_state`` is authored separately (task 1.3); this module only references
the table/columns described in the design data model.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import Boolean, DateTime, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from clara_api.api.v1.endpoints.analytics import AnalyticsAggregator
from clara_api.core.config import Settings, get_settings
from clara_api.core.research_telemetry import strip_pii
from clara_api.db.base import Base

logger = logging.getLogger(__name__)

#: Bounded outbound timeout for best-effort webhook delivery. Kept small so a
#: slow/unreachable sink can never stall the evaluating request (Requirement 8.6).
_DELIVERY_TIMEOUT_SECONDS = 5.0

# ---------------------------------------------------------------------------
# Bounded severity vocabulary + threshold constants
# ---------------------------------------------------------------------------

SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_CRITICAL = "critical"

#: The closed set of permitted severities. Any value outside this set is a bug.
SEVERITIES: frozenset[str] = frozenset({SEVERITY_INFO, SEVERITY_WARNING, SEVERITY_CRITICAL})

#: Alert lifecycle states persisted in ``alert_state``.
STATE_FIRING = "firing"
STATE_CLEARED = "cleared"

# Thresholds mirror the existing ``/system/ecosystem`` runtime rules so the
# engine never diverges from the surface it promotes.
API_5XX_WARN_PCT = 2.0
API_5XX_CRITICAL_PCT = 8.0
FLOW_STALE_MINUTES = 30.0

# Stable rule targets (the second half of every stable id; the first half is the
# rule namespace). Kept as constants so ids never drift across evaluations.
_TARGET_ML = "ml_dependency"
_TARGET_API = "api_runtime"
_TARGET_FLOW = "flow_event_stream"


def stable_alert_id(rule: str, target: str) -> str:
    """Build a stable, deterministic dedupe key from a rule and its target.

    The id is a pure function of ``(rule, target)`` — it carries no timestamp,
    counter, or PII — so the same condition always maps to the same id across
    evaluations, which is what makes dedupe and acknowledge state coherent
    (Requirement 8.1, 8.5).
    """

    return f"{rule.strip().lower()}:{target.strip().lower()}"


def _now() -> datetime:
    return datetime.now(tz=UTC)


# ---------------------------------------------------------------------------
# Alert value object
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Alert:
    """A threshold-derived operational signal.

    ``id`` is the stable dedupe key, ``severity`` is bounded to
    :data:`SEVERITIES`, ``source`` names the originating subsystem, ``message``
    is a bounded, no-PII string, and ``context`` carries only coarse, PII-free
    signals (counts, ratios, severities, thresholds).
    """

    id: str
    severity: str
    source: str
    message: str
    context: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(
                f"Alert severity must be one of {sorted(SEVERITIES)}; got {self.severity!r}"
            )
        if not self.id:
            raise ValueError("Alert id must be a non-empty stable identifier")

    def as_dict(self) -> dict[str, Any]:
        """A plain, serialisable view (coarse, PII-free by construction)."""

        return {
            "id": self.id,
            "severity": self.severity,
            "source": self.source,
            "message": self.message,
            "context": dict(self.context),
        }


@dataclass(frozen=True)
class AlertState:
    """An immutable snapshot of a row in ``alert_state``.

    Returned by :meth:`AlertEngine.reconcile` / :meth:`AlertEngine.acknowledge`
    so callers never have to touch the live ORM row.
    """

    alert_id: str
    severity: str
    state: str
    acknowledged: bool
    first_fired_at: datetime | None
    last_evaluated_at: datetime | None
    last_delivered_at: datetime | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "severity": self.severity,
            "state": self.state,
            "acknowledged": self.acknowledged,
            "first_fired_at": self.first_fired_at.isoformat() if self.first_fired_at else None,
            "last_evaluated_at": (
                self.last_evaluated_at.isoformat() if self.last_evaluated_at else None
            ),
            "last_delivered_at": (
                self.last_delivered_at.isoformat() if self.last_delivered_at else None
            ),
        }


# ---------------------------------------------------------------------------
# Persistence model (references the design ``alert_state`` data model)
# ---------------------------------------------------------------------------


class AlertStateRow(Base):
    """ORM mapping for the ``alert_state`` table (design data model).

    The physical table is created by the additive migration authored in task
    1.3; this mapping only *references* the schema so the engine can read/write
    firing/ack state. Columns mirror the design exactly:

    ``alert_id`` (pk), ``severity``, ``state``, ``acknowledged``,
    ``first_fired_at``, ``last_evaluated_at``, ``last_delivered_at`` (nullable).
    """

    __tablename__ = "alert_state"

    alert_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    severity: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(16), default=STATE_FIRING)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    first_fired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


def _row_to_state(row: AlertStateRow) -> AlertState:
    return AlertState(
        alert_id=row.alert_id,
        severity=row.severity,
        state=row.state,
        acknowledged=bool(row.acknowledged),
        first_fired_at=row.first_fired_at,
        last_evaluated_at=row.last_evaluated_at,
        last_delivered_at=row.last_delivered_at,
    )


# ---------------------------------------------------------------------------
# Input extraction helpers (robust to the ecosystem-shaped payloads)
# ---------------------------------------------------------------------------


def _coerce_float(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_server_error_rate(metrics: Any) -> float:
    """Read the 5xx server-error percentage from a metrics payload.

    Accepts the ecosystem/runtime shapes: ``server_error_rate_pct`` is preferred,
    falling back to ``error_rate_pct`` (the ecosystem runtime computes that from
    5xx counts). Missing/garbage → ``0.0`` (no alert).
    """

    if not isinstance(metrics, Mapping):
        return 0.0
    for key in ("server_error_rate_pct", "error_rate_pct"):
        value = _coerce_float(metrics.get(key))
        if value is not None:
            return value
    return 0.0


def _extract_ml_status(deps: Any) -> str:
    """Normalise an ML dependency status to ``ok`` | ``degraded`` | ``down``.

    Accepts a bare status string, ``{"status": ...}``, or the dependency-snapshot
    shape ``{"ml": {"status": ...}}`` / ``{"dependencies": {"ml": {...}}}``.
    """

    raw: Any = deps
    if isinstance(deps, Mapping):
        if isinstance(deps.get("dependencies"), Mapping):
            deps = deps["dependencies"]
        ml = deps.get("ml") if isinstance(deps.get("ml"), Mapping) else None
        if ml is not None:
            raw = ml.get("status")
        elif "status" in deps:
            raw = deps.get("status")
        elif "ml_status" in deps:
            raw = deps.get("ml_status")
    status = str(raw or "").strip().lower()
    if status in {"ok", "healthy", "up"}:
        return "ok"
    if status in {"down", "unreachable", "unavailable", "error"}:
        return "down"
    if status in {"degraded", "unhealthy", "warn", "warning"}:
        return "degraded"
    # Unknown/blank ⇒ treat as down so a missing probe never silently passes.
    return "down" if status == "" else "degraded"


def _extract_flow(flow_health: Any) -> tuple[int, float | None]:
    """Return ``(event_count, minutes_since_last_event)`` from a flow payload."""

    if not isinstance(flow_health, Mapping):
        return 0, None
    count = (
        _coerce_int(flow_health.get("event_count"))
        if flow_health.get("event_count") is not None
        else _coerce_int(flow_health.get("count"))
    )
    minutes = _coerce_float(flow_health.get("minutes_since_last_event"))
    if minutes is None:
        minutes = _coerce_float(flow_health.get("minutes_since"))
    return (count or 0), minutes


# ---------------------------------------------------------------------------
# Alert engine
# ---------------------------------------------------------------------------


class AlertEngine:
    """Evaluate threshold rules, reconcile transitions, and persist acks.

    Gated by ``admin_observability_alerting_enabled``: when disabled every public
    method is inert and performs no write.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def enabled(self) -> bool:
        return bool(self._settings.admin_observability_alerting_enabled)

    # -- rule evaluation ---------------------------------------------------

    def evaluate(self, metrics: Any, deps: Any, flow_health: Any) -> list[Alert]:
        """Produce the current set of firing :class:`Alert` values.

        Each rule that crosses its threshold yields exactly one alert with a
        stable id and a bounded severity (Requirement 8.1). When alerting is
        disabled the engine is inert and returns ``[]``.
        """

        if not self.enabled:
            return []

        alerts: list[Alert] = []
        alerts.extend(self._evaluate_ml(deps))
        alerts.extend(self._evaluate_api_5xx(metrics))
        alerts.extend(self._evaluate_flow(flow_health))
        return alerts

    def _evaluate_ml(self, deps: Any) -> list[Alert]:
        status = _extract_ml_status(deps)
        if status == "down":
            return [
                Alert(
                    id=stable_alert_id("ml", _TARGET_ML),
                    severity=SEVERITY_CRITICAL,
                    source="ml_dependency",
                    message="ML dependency is unreachable from the API runtime.",
                    context={"ml_status": status},
                )
            ]
        if status == "degraded":
            return [
                Alert(
                    id=stable_alert_id("ml", _TARGET_ML),
                    severity=SEVERITY_WARNING,
                    source="ml_dependency",
                    message="ML dependency is reachable but unhealthy/degraded.",
                    context={"ml_status": status},
                )
            ]
        return []

    def _evaluate_api_5xx(self, metrics: Any) -> list[Alert]:
        rate = _extract_server_error_rate(metrics)
        if rate >= API_5XX_CRITICAL_PCT:
            severity = SEVERITY_CRITICAL
        elif rate >= API_5XX_WARN_PCT:
            severity = SEVERITY_WARNING
        else:
            return []
        return [
            Alert(
                id=stable_alert_id("api", _TARGET_API),
                severity=severity,
                source="api_runtime",
                message=f"API 5xx ratio is {round(rate, 3)}% "
                f"(warn ≥ {API_5XX_WARN_PCT}%, critical ≥ {API_5XX_CRITICAL_PCT}%).",
                context={
                    "server_error_rate_pct": round(rate, 3),
                    "warn_pct": API_5XX_WARN_PCT,
                    "critical_pct": API_5XX_CRITICAL_PCT,
                },
            )
        ]

    def _evaluate_flow(self, flow_health: Any) -> list[Alert]:
        count, minutes = _extract_flow(flow_health)
        if count <= 0:
            return [
                Alert(
                    id=stable_alert_id("flow", _TARGET_FLOW),
                    severity=SEVERITY_WARNING,
                    source="flow_event_stream",
                    message="No flow events are available in the recent runtime window.",
                    context={"event_count": 0},
                )
            ]
        if minutes is None or minutes > FLOW_STALE_MINUTES:
            return [
                Alert(
                    id=stable_alert_id("flow", _TARGET_FLOW),
                    severity=SEVERITY_WARNING,
                    source="flow_event_stream",
                    message=(
                        "Latest flow event is stale "
                        f"(> {FLOW_STALE_MINUTES:g} minutes since last event)."
                    ),
                    context={
                        "event_count": count,
                        "minutes_since_last_event": (
                            round(minutes, 3) if minutes is not None else None
                        ),
                        "stale_threshold_minutes": FLOW_STALE_MINUTES,
                    },
                )
            ]
        return []

    # -- transition reconciliation ----------------------------------------

    def reconcile(self, db: Session, alerts: list[Alert]) -> list[AlertState]:
        """Persist firing/cleared transitions for ``alerts`` to ``alert_state``.

        Returns the states that *transitioned into firing* on this evaluation
        (not-firing → firing). A condition that is still firing from a prior
        evaluation is updated in place but **not** returned, so a persistent
        condition is not re-presented and fires delivery at most once per
        transition (Requirements 8.4, 8.5). Previously-firing alerts that are no
        longer present transition to ``cleared``.

        When alerting is disabled this is a no-op returning ``[]`` (no write).
        """

        if not self.enabled:
            return []

        now = _now()
        current: dict[str, Alert] = {alert.id: alert for alert in alerts}
        existing: dict[str, AlertStateRow] = {
            row.alert_id: row for row in db.execute(select(AlertStateRow)).scalars()
        }

        newly_firing: list[AlertState] = []

        for alert_id, alert in current.items():
            row = existing.get(alert_id)
            if row is None:
                row = AlertStateRow(
                    alert_id=alert_id,
                    severity=alert.severity,
                    state=STATE_FIRING,
                    acknowledged=False,
                    first_fired_at=now,
                    last_evaluated_at=now,
                )
                db.add(row)
                newly_firing.append(_row_to_state(row))
                continue

            transitioned = row.state != STATE_FIRING
            if transitioned:
                # clear → fire: present as new again and reset the ack flag so a
                # previously-acknowledged-then-cleared alert re-surfaces (Req 8.4).
                row.first_fired_at = now
                row.acknowledged = False
                row.state = STATE_FIRING
            row.severity = alert.severity
            row.last_evaluated_at = now
            if transitioned:
                newly_firing.append(_row_to_state(row))

        # Anything previously firing but absent now → cleared.
        for alert_id, row in existing.items():
            if alert_id not in current and row.state == STATE_FIRING:
                row.state = STATE_CLEARED
                row.last_evaluated_at = now

        db.flush()
        return newly_firing

    # -- delivery ----------------------------------------------------------

    def _build_delivery_payload(self, fired: list[Alert]) -> dict[str, Any]:
        """Project the newly-firing alerts into a PII-free delivery payload.

        Each alert's plain view is passed through the same projection the durable
        sink composes — ``AnalyticsAggregator._project_pii_free`` (analytics
        key-denylist) followed by ``research_telemetry.strip_pii`` (PHR/identity
        container denylist + email/long-digit value scrubbing) — so no PII can
        ever reach the outbound sink, including value-level markers under
        non-denylisted keys (Requirements 8.2, 11.2). Alerts are PII-free by
        construction; composing both projections is defense-in-depth.
        """

        projected = [
            strip_pii(AnalyticsAggregator._project_pii_free(alert.as_dict())) for alert in fired
        ]
        return {"alerts": projected, "count": len(projected)}

    def deliver(self, fired: list[Alert]) -> None:
        """Best-effort, no-PII webhook delivery of newly-firing alerts.

        ``fired`` is the set of alerts that transitioned not-firing → firing on
        this evaluation (mapped from :meth:`reconcile`'s return), so delivery
        happens at most once per transition and a persistent condition never
        re-delivers (Requirements 8.2, 8.5).

        Behavior:

        * Inert when alerting is disabled or there is nothing newly firing
          (no outbound, no side effect — Requirement 12.2).
        * When no ``admin_observability_alert_webhook_url`` is configured, alerts
          are surfaced in-app only and **no** outbound POST is attempted
          (graceful no-op — Requirement 8.3).
        * The payload is the PII-free projection of the fired alerts
          (Requirements 8.2, 11.2).
        * Any delivery failure — connection/timeout/network error or a non-2xx
          response — is swallowed and logged (no PII) and **never** propagated,
          so the evaluating request is never broken (Requirement 8.6).
        """

        if not self.enabled or not fired:
            return

        webhook_url = (self._settings.admin_observability_alert_webhook_url or "").strip()
        if not webhook_url:
            # No sink configured → in-app only, no outbound delivery (Req 8.3).
            return

        payload = self._build_delivery_payload(fired)
        try:
            response = httpx.post(webhook_url, json=payload, timeout=_DELIVERY_TIMEOUT_SECONDS)
            # Non-2xx (e.g. 4xx/5xx) raises and is swallowed below (Req 8.6).
            response.raise_for_status()
        except Exception:  # noqa: BLE001 - best-effort delivery; never propagate (Req 8.6)
            # Log without any alert content/PII; the request must never break.
            logger.warning(
                "alert webhook delivery failed (count=%d); swallowed", len(fired)
            )

    # -- acknowledgement ---------------------------------------------------

    def acknowledge(self, db: Session, alert_id: str) -> AlertState | None:
        """Persist the acknowledged state for ``alert_id`` by its stable id.

        Returns the updated :class:`AlertState`, or ``None`` when alerting is
        disabled (inert) or no row exists for the id. An acknowledged alert is
        not re-presented as new until it clears and re-fires (Requirement 8.4) —
        the clear-and-refire reset lives in :meth:`reconcile`.
        """

        if not self.enabled:
            return None

        row = db.execute(
            select(AlertStateRow).where(AlertStateRow.alert_id == alert_id)
        ).scalar_one_or_none()
        if row is None:
            return None

        row.acknowledged = True
        row.last_evaluated_at = _now()
        db.flush()
        return _row_to_state(row)
