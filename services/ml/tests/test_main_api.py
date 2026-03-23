from fastapi.testclient import TestClient

from clara_ml.main import app

client = TestClient(app)


def test_routed_chat_infer_returns_routing_and_answer():
    response = client.post("/v1/chat/routed", json={"query": "Toi can tu van an uong khi dung thuoc."})
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "normal"
    assert body["emergency"] is False
    assert isinstance(body["retrieved_ids"], list)
    assert body["model_used"] in {"local-synth-v1", "deepseek-v3.2"}
    assert body["answer"]


def test_routed_chat_infer_emergency_fast_path():
    response = client.post("/v1/chat/routed", json={"query": "Kho tho, dau nguc du doi, xin giup."})
    assert response.status_code == 200
    body = response.json()
    assert body["emergency"] is True
    assert body["role"] == "doctor"
    assert body["intent"] == "emergency_triage"
    assert body["model_used"] == "emergency-fastpath-v1"
    assert body["retrieved_ids"] == []


def test_research_tier2_returns_progressive_schema():
    response = client.post(
        "/v1/research/tier2",
        json={"query": "Evaluate DDI evidence for warfarin and NSAID co-prescribing."},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["metadata"]["response_style"] == "progressive"
    assert isinstance(body["metadata"]["stages"], list)
    assert body["metadata"]["fallback_used"] is True
    assert isinstance(body["plan_steps"], list)
    assert len(body["plan_steps"]) >= 3
    assert isinstance(body["citations"], list)
    assert len(body["citations"]) >= 1
    assert isinstance(body["answer"], str)
    assert body["answer"]


def test_careguard_analyze_returns_risk_and_alerts():
    response = client.post(
        "/v1/careguard/analyze",
        json={
            "symptoms": ["chest pain"],
            "labs": {"egfr": 25},
            "medications": ["warfarin", "ibuprofen"],
            "allergies": ["penicillin"],
        },
    )
    assert response.status_code == 200
    body = response.json()

    assert body["risk"]["level"] == "high"
    assert body["risk"]["score"] >= 5
    assert isinstance(body["risk"]["factors"], list)
    assert isinstance(body["ddi_alerts"], list)
    assert any(alert["type"] == "drug_drug" for alert in body["ddi_alerts"])
    assert isinstance(body["recommendation"], str)
    assert body["recommendation"]
    assert body["metadata"]["fallback_used"] is True


def test_scribe_soap_returns_structured_soap():
    response = client.post(
        "/v1/scribe/soap",
        json={
            "transcript": (
                "Patient reports cough and fever for 3 days. "
                "BP 120/80, HR 90, temp 38.2. Exam noted mild crackles."
            )
        },
    )
    assert response.status_code == 200
    body = response.json()

    assert set(["subjective", "objective", "assessment", "plan"]).issubset(body.keys())
    assert isinstance(body["subjective"]["chief_complaint"], str)
    assert isinstance(body["objective"]["vitals"], dict)
    assert body["objective"]["vitals"]["blood_pressure"] == "120/80"
    assert isinstance(body["assessment"]["problems"], list)
    assert isinstance(body["plan"]["next_steps"], list)
    assert body["metadata"]["fallback_used"] is True
