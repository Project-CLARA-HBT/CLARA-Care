"""No-PII CareGuard observability metrics + admin-only aggregate read.

Feature: clara-selfmed-careguard-upgrade (task 10.1)

Pins Requirements 9.3, 9.4, 9.5 (and the flags-off guarantee, 12.1/12.2):

* Behind ``CAREGUARD_OBSERVABILITY_ENABLED`` the store records only no-PII
  metrics: per-source usage, fallback rate, normalization confidence, the active
  rule-set version label, and per-check latency (Req 9.3).
* The ``record_careguard_check`` projection extracts only allowlisted no-PII
  fields, so adversarial drug names / identifiers in the analysis result never
  reach the persisted aggregate (Req 9.2, 11.4).
* The aggregate read is exposed only to the admin role and is 404 when the flag
  is off, so the surface ships dark (Req 9.5, 12.1, 12.2).
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from clara_api.core.careguard_metrics import (
    CareGuardMetricsStore,
    get_careguard_metrics_store,
    record_careguard_check,
)
from clara_api.core.security import create_access_token
from clara_api.main import app

client = TestClient(app)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _admin_token() -> str:
    return create_access_token(subject="ops@admin.clara", role="admin")


def _normal_token() -> str:
    return create_access_token(subject="user@clara", role="normal")


# ---------------------------------------------------------------------------
# Store unit behavior (Req 9.3)
# ---------------------------------------------------------------------------


def test_store_aggregates_counts_rates_and_percentiles() -> None:
    store = CareGuardMetricsStore()
    store.record(
        source_used=["local_rules", "rxnav"],
        fallback_used=False,
        risk_level="high",
        rule_set_version="v1",
        latency_ms=100.0,
        normalization_confidences=[1.0, 0.6, 0.3],
    )
    store.record(
        source_used=["local_rules"],
        fallback_used=True,
        risk_level="low",
        rule_set_version="v1",
        latency_ms=200.0,
        normalization_confidences=[0.9],
    )

    snap = store.snapshot()
    assert snap["checks_total"] == 2
    assert snap["fallback_total"] == 1
    assert snap["fallback_rate_pct"] == 50.0
    assert snap["by_source"] == {"local_rules": 2, "rxnav": 1}
    assert snap["by_risk_level"] == {"high": 1, "low": 1}
    assert snap["by_rule_set_version"] == {"v1": 2}
    assert snap["latency"]["count"] == 2
    assert snap["latency"]["avg_ms"] == 150.0
    assert snap["latency"]["p50_ms"] <= snap["latency"]["p90_ms"] <= snap["latency"]["p99_ms"]
    # confidence buckets: 1.0/0.9 high, 0.6 medium, 0.3 low
    assert snap["normalization_confidence"]["count"] == 4
    assert snap["normalization_confidence"]["buckets"] == {"high": 2, "medium": 1, "low": 1}


def test_store_buckets_unknown_source_and_risk_labels() -> None:
    store = CareGuardMetricsStore()
    store.record(
        source_used=["local_rules", "sneaky-connector"],
        fallback_used=False,
        risk_level="catastrophic",
        rule_set_version="v1",
        latency_ms=10.0,
    )
    snap = store.snapshot()
    # Unknown source bucketed under "other"; never stored verbatim.
    assert snap["by_source"] == {"local_rules": 1, "other": 1}
    # Unknown risk coerced to "unknown".
    assert snap["by_risk_level"] == {"unknown": 1}


# ---------------------------------------------------------------------------
# No-PII projection (Req 9.2, 11.4)
# ---------------------------------------------------------------------------


def test_record_careguard_check_drops_pii() -> None:
    store = CareGuardMetricsStore()
    adversarial_result = {
        "risk": {"level": "critical", "factors": ["warfarin + ibuprofen"]},
        "ddi_alerts": [
            {"message": "warfarin tương tác ibuprofen", "drug_name": "warfarin"}
        ],
        "fallback_used": True,
        "metadata": {
            "source_used": ["local_rules", "openfda"],
            "fallback_used": True,
            "local_ddi_rules_version": "v1+drugbank-2026",
            "user_email": "patient@example.com",
        },
        "medications": ["warfarin", "ibuprofen"],
    }
    record_careguard_check(
        adversarial_result,
        latency_ms=42.0,
        normalization_confidences=[0.95],
        store=store,
    )
    serialized = json.dumps(store.snapshot())
    for secret in ("warfarin", "ibuprofen", "patient@example.com", "tương tác"):
        assert secret not in serialized
    # The allowlisted no-PII fields were still recorded.
    snap = store.snapshot()
    assert snap["checks_total"] == 1
    assert snap["fallback_total"] == 1
    assert snap["by_risk_level"] == {"critical": 1}
    assert snap["by_source"] == {"local_rules": 1, "openfda": 1}
    assert snap["by_rule_set_version"] == {"v1+drugbank-2026": 1}


# ---------------------------------------------------------------------------
# Admin-only aggregate read + flag gating (Req 9.5, 12.1, 12.2)
# ---------------------------------------------------------------------------


def test_metrics_endpoint_404_when_flag_off(set_flags) -> None:
    set_flags(careguard_observability_enabled=False)
    response = client.get("/api/v1/careguard/metrics", headers=_auth(_admin_token()))
    assert response.status_code == 404


def test_metrics_endpoint_admin_only_when_flag_on(set_flags) -> None:
    set_flags(careguard_observability_enabled=True)
    get_careguard_metrics_store().reset()

    admin = client.get("/api/v1/careguard/metrics", headers=_auth(_admin_token()))
    assert admin.status_code == 200
    body = admin.json()
    assert set(body) >= {
        "checks_total",
        "fallback_total",
        "fallback_rate_pct",
        "by_source",
        "by_risk_level",
        "by_rule_set_version",
        "latency",
        "normalization_confidence",
    }
    assert body["checks_total"] == 0


def test_metrics_endpoint_forbidden_for_non_admin(set_flags) -> None:
    set_flags(careguard_observability_enabled=True)
    response = client.get("/api/v1/careguard/metrics", headers=_auth(_normal_token()))
    assert response.status_code == 403
