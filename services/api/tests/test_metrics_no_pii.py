"""Confirm the API metrics surface records only coarse, PII-free labels.

Task 11.3 (clara-platform-hardening) / Requirement 10.5: latency and
error-rate metrics must be sufficient to detect regressions WITHOUT introducing
PII into the metrics surface. The metrics store keys requests by the matched
route *template* (e.g. ``/items/{item_id}``), status code, and aggregate
latency/counts only. It must never embed a raw path containing an id, a query
string, or any request/user content.

These tests build a minimal app around ``APIMetricsMiddleware`` so they stay
fast and independent of the full application wiring.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from clara_api.core.metrics import (
    APIMetricsMiddleware,
    APIMetricsStore,
    format_metrics_prometheus,
    get_api_metrics_store,
)


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(APIMetricsMiddleware)

    @app.get("/items/{item_id}")
    def read_item(item_id: str) -> dict[str, str]:
        return {"item_id": item_id}

    return app


def test_route_label_uses_template_not_raw_path_id_or_query() -> None:
    # Snapshot baseline so the assertions are robust to shared store state.
    store = get_api_metrics_store()
    before = store.snapshot()["by_route"].get("/items/{item_id}", 0)

    app = _build_app()
    client = TestClient(app)

    # A request carrying a PII-shaped identifier and query string.
    secret_id = "patient-ssn-123-45-6789"
    response = client.get(f"/items/{secret_id}?email=jane.doe%40example.com&q=chest+pain")
    assert response.status_code == 200

    snapshot = store.snapshot()
    by_route = snapshot["by_route"]

    # The coarse route template is recorded and incremented...
    assert by_route.get("/items/{item_id}", 0) == before + 1

    # ...and no raw path/id/query value leaks into any route label.
    route_labels = " ".join(by_route.keys())
    assert secret_id not in route_labels
    assert "ssn" not in route_labels
    assert "email" not in route_labels
    assert "chest" not in route_labels
    assert "?" not in route_labels


def test_snapshot_only_exposes_coarse_non_pii_fields() -> None:
    store = APIMetricsStore()
    store.record("/items/{item_id}", 200, 12.5)
    store.record("/items/{item_id}", 404, 3.0)

    snapshot = store.snapshot()

    # Exactly the coarse aggregate fields, nothing free-text.
    assert set(snapshot.keys()) == {
        "requests_total",
        "by_route",
        "by_status",
        "avg_latency_ms",
    }
    assert snapshot["requests_total"] == 2
    assert snapshot["by_route"] == {"/items/{item_id}": 2}
    assert snapshot["by_status"] == {"200": 1, "404": 1}
    assert isinstance(snapshot["avg_latency_ms"], float)


def test_prometheus_output_contains_no_id_or_query_content() -> None:
    store = APIMetricsStore()
    # Even if a template-style label is recorded, only the placeholder appears.
    store.record("/items/{item_id}", 200, 5.0)
    store.record("/items/{item_id}", 500, 9.0)

    body = format_metrics_prometheus(store.snapshot())

    assert 'by_route{route="/items/{item_id}"}' in body
    assert 'by_status{status="200"}' in body
    assert 'by_status{status="500"}' in body
    # No concrete id value or query string ever rendered.
    assert "123-45-6789" not in body
    assert "?" not in body
    assert "email=" not in body
