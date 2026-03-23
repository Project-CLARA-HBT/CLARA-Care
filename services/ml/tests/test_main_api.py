import pytest
from fastapi.testclient import TestClient

from clara_ml.main import app
from clara_ml.observability import metrics_collector

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_in_memory_metrics():
    metrics_collector.reset()
    yield
    metrics_collector.reset()


def test_metrics_endpoint_returns_snapshot_schema():
    response = client.get("/metrics")
    assert response.status_code == 200
    body = response.json()

    assert set(["requests_total", "by_path", "error_total", "avg_latency_ms"]).issubset(body.keys())
    assert body["requests_total"] == 0
    assert body["by_path"] == {}
    assert body["error_total"] == 0
    assert isinstance(body["avg_latency_ms"], float)
    assert body["avg_latency_ms"] == 0.0


def test_health_details_returns_dependency_and_config_flags():
    response = client.get("/health/details")
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "ok"
    assert body["service"] == "clara-ml"
    assert isinstance(body["environment"], str)
    assert isinstance(body["deepseek_configured"], bool)
    assert isinstance(body["router_ready"], bool)
    assert body["router_ready"] is True
    assert isinstance(body["rag_ready"], bool)
    assert body["rag_ready"] is True
    assert isinstance(body["prompt_loader_ready"], bool)
    assert body["prompt_loader_ready"] is True


def test_metrics_increment_after_tracked_requests():
    response_chat = client.post("/v1/chat/routed", json={"query": "Toi can tu van an uong khi dung thuoc."})
    assert response_chat.status_code == 200

    response_research = client.post(
        "/v1/research/tier2",
        json={"query": "Evaluate DDI evidence for warfarin and NSAID co-prescribing."},
    )
    assert response_research.status_code == 200

    response_careguard = client.post(
        "/v1/careguard/analyze",
        json={
            "symptoms": ["chest pain"],
            "labs": {"egfr": 25},
            "medications": ["warfarin", "ibuprofen"],
            "allergies": ["penicillin"],
        },
    )
    assert response_careguard.status_code == 200

    response_scribe = client.post(
        "/v1/scribe/soap",
        json={
            "transcript": (
                "Patient reports cough and fever for 3 days. "
                "BP 120/80, HR 90, temp 38.2. Exam noted mild crackles."
            )
        },
    )
    assert response_scribe.status_code == 200

    response_council = client.post(
        "/v1/council/run",
        json={
            "symptoms": ["fatigue", "palpitations"],
            "labs": {"egfr": 58, "glucose": 210},
            "medications": ["metformin"],
            "history": ["type 2 diabetes"],
            "specialists": ["cardiology", "endocrinology", "nephrology"],
        },
    )
    assert response_council.status_code == 200

    response_metrics = client.get("/metrics")
    assert response_metrics.status_code == 200
    metrics = response_metrics.json()

    assert metrics["requests_total"] == 5
    assert metrics["error_total"] == 0
    assert metrics["avg_latency_ms"] >= 0.0
    assert metrics["by_path"]["/v1/chat/routed"] == 1
    assert metrics["by_path"]["/v1/research/tier2"] == 1
    assert metrics["by_path"]["/v1/careguard/analyze"] == 1
    assert metrics["by_path"]["/v1/scribe/soap"] == 1
    assert metrics["by_path"]["/v1/council/run"] == 1


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


def test_council_run_returns_expected_schema():
    response = client.post(
        "/v1/council/run",
        json={
            "symptoms": ["fatigue", "palpitations"],
            "labs": {"egfr": 58, "glucose": 210},
            "medications": ["metformin"],
            "history": ["type 2 diabetes"],
            "specialists": ["cardiology", "endocrinology", "nephrology"],
        },
    )
    assert response.status_code == 200
    body = response.json()

    assert body["requested_specialists"] == ["cardiology", "endocrinology", "nephrology"]
    assert isinstance(body["per_specialist_reasoning_logs"], list)
    assert len(body["per_specialist_reasoning_logs"]) == 3
    for item in body["per_specialist_reasoning_logs"]:
        assert set(["specialist", "reasoning_log", "key_findings", "triage", "recommendation"]).issubset(
            item.keys()
        )
        assert isinstance(item["reasoning_log"], list)
        assert isinstance(item["key_findings"], list)
        assert item["triage"] in {"routine_follow_up", "same_day_review", "emergency_escalation"}
        assert isinstance(item["recommendation"], str)
        assert item["recommendation"]

    assert isinstance(body["conflict_list"], list)
    assert isinstance(body["consensus_summary"], str)
    assert body["consensus_summary"]
    assert isinstance(body["divergence_notes"], list)
    assert isinstance(body["final_recommendation"], str)
    assert body["final_recommendation"]
    assert isinstance(body["estimated_duration_minutes"], int)
    assert body["estimated_duration_minutes"] > 0
    assert body["emergency_escalation"]["triggered"] is False
    assert body["emergency_escalation"]["action"] == "standard_multidisciplinary_pathway"


def test_council_run_emergency_escalation_on_red_flags():
    response = client.post(
        "/v1/council/run",
        json={
            "symptoms": ["severe chest pain", "shortness of breath"],
            "labs": {"troponin": 0.09},
            "medications": ["warfarin"],
            "history": "hypertension",
            "specialists": ["cardiology", "neurology"],
        },
    )
    assert response.status_code == 200
    body = response.json()

    assert body["emergency_escalation"]["triggered"] is True
    assert isinstance(body["emergency_escalation"]["red_flags"], list)
    assert len(body["emergency_escalation"]["red_flags"]) >= 1
    assert body["emergency_escalation"]["action"] == "immediate_emergency_referral"
    assert body["estimated_duration_minutes"] == 5
    assert "Emergency escalation triggered" in body["final_recommendation"]
