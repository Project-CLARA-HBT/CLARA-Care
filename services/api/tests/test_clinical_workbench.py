from uuid import uuid4

from fastapi.testclient import TestClient

from clara_api.main import app

client = TestClient(app)


def _headers(email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "secret"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_workbench_case_context_and_idempotent_run_are_owner_scoped() -> None:
    suffix = uuid4().hex
    owner = _headers(f"workbench-{suffix}@normal.clara")
    stranger = _headers(f"workbench-other-{suffix}@normal.clara")

    case_response = client.post(
        "/api/v1/clinical-workbench/cases",
        headers=owner,
        json={"title": "Medication review", "case_type": "medication"},
    )
    assert case_response.status_code == 201
    case_id = case_response.json()["id"]

    context_response = client.post(
        f"/api/v1/clinical-workbench/cases/{case_id}/context",
        headers=owner,
        json={
            "source_type": "patient_reported",
            "context": {"medications": ["warfarin"]},
            "provenance": {"captured_by": "user"},
        },
    )
    assert context_response.status_code == 201
    snapshot_id = context_response.json()["id"]

    idempotency_key = f"test-{uuid4().hex}"
    run_payload = {
        "protocol": "medication_review",
        "context_snapshot_id": snapshot_id,
        "request": {"question": "Review the current medication list"},
    }
    first = client.post(
        f"/api/v1/clinical-workbench/cases/{case_id}/runs",
        headers={**owner, "Idempotency-Key": idempotency_key},
        json=run_payload,
    )
    second = client.post(
        f"/api/v1/clinical-workbench/cases/{case_id}/runs",
        headers={**owner, "Idempotency-Key": idempotency_key},
        json=run_payload,
    )
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["status"] == "queued"

    assert client.get(
        f"/api/v1/clinical-workbench/cases/{case_id}", headers=stranger
    ).status_code == 404
    ledger = client.get(
        f"/api/v1/clinical-workbench/runs/{first.json()['id']}/ledger", headers=owner
    )
    assert ledger.status_code == 200
    assert ledger.json() == {"evidence": [], "claims": [], "artifacts": []}


def test_workbench_rejects_unknown_protocol() -> None:
    suffix = uuid4().hex
    headers = _headers(f"workbench-invalid-{suffix}@normal.clara")
    case_id = client.post(
        "/api/v1/clinical-workbench/cases",
        headers=headers,
        json={"title": "Invalid protocol test"},
    ).json()["id"]
    response = client.post(
        f"/api/v1/clinical-workbench/cases/{case_id}/runs",
        headers={**headers, "Idempotency-Key": f"test-{uuid4().hex}"},
        json={"protocol": "pretend_completed_work", "request": {}},
    )
    assert response.status_code == 422


def test_workbench_executes_real_adapter_and_persists_artifact(monkeypatch) -> None:
    suffix = uuid4().hex
    headers = _headers(f"workbench-execute-{suffix}@normal.clara")
    case_id = client.post(
        "/api/v1/clinical-workbench/cases",
        headers=headers,
        json={"title": "Medication execution"},
    ).json()["id"]
    run = client.post(
        f"/api/v1/clinical-workbench/cases/{case_id}/runs",
        headers={**headers, "Idempotency-Key": f"test-{uuid4().hex}"},
        json={
            "protocol": "medication_review",
            "request": {"medications": ["warfarin", "aspirin"]},
        },
    ).json()

    def real_adapter_stub(path: str, payload: dict) -> dict:
        assert path == "/v1/careguard/analyze"
        assert payload["medications"] == ["warfarin", "aspirin"]
        return {
            "alerts": [{"severity": "high", "source": "drugbank"}],
            "citations": [
                {
                    "source_id": "drugbank-pair-1",
                    "source": "drugbank",
                    "title": "DrugBank DDI pair",
                    "snippet": "Licensed interaction record",
                }
            ],
        }

    monkeypatch.setattr(
        "clara_api.api.v1.endpoints.ml_proxy.proxy_ml_post", real_adapter_stub
    )
    executed = client.post(
        f"/api/v1/clinical-workbench/runs/{run['id']}/execute", headers=headers
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["run"]["status"] == "completed"
    assert executed.json()["artifact_id"] is not None

    ledger = client.get(
        f"/api/v1/clinical-workbench/runs/{run['id']}/ledger", headers=headers
    ).json()
    assert ledger["evidence"][0]["source_type"] == "drugbank"
    assert ledger["artifacts"][0]["artifact_type"] == "medication_safety_review"
