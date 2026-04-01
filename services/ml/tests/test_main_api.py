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
    response_chat = client.post(
        "/v1/chat/routed", json={"query": "Toi can tu van an uong khi dung thuoc."}
    )
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
    response = client.post(
        "/v1/chat/routed", json={"query": "Toi can tu van an uong khi dung thuoc."}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "normal"
    assert body["emergency"] is False
    assert isinstance(body["retrieved_ids"], list)
    assert body["model_used"] in {"local-synth-v1", "deepseek-v3.2"}
    assert body["answer"]
    assert "factcheck" in body


def test_routed_chat_infer_uses_smalltalk_fastpath_for_greeting():
    response = client.post("/v1/chat/routed", json={"query": "hi"})
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "general_guidance"
    assert body["model_used"] == "smalltalk-fastpath-v1"
    assert body["retrieved_ids"] == []
    assert "chào" in body["answer"].lower()
    assert any(
        event.get("stage") == "smalltalk_fastpath" and event.get("status") == "completed"
        for event in body["flow_events"]
    )


def test_routed_chat_infer_emergency_fast_path():
    response = client.post("/v1/chat/routed", json={"query": "Kho tho, dau nguc du doi, xin giup."})
    assert response.status_code == 200
    body = response.json()
    assert body["emergency"] is True
    assert body["role"] == "doctor"
    assert body["intent"] == "emergency_triage"
    assert body["model_used"] == "emergency-fastpath-v1"
    assert body["retrieved_ids"] == []


def test_routed_chat_infer_blocks_prescription_and_dosage_requests():
    response = client.post(
        "/v1/chat/routed",
        json={"query": "Tôi nên uống mấy viên warfarin mỗi ngày, kê đơn giúp tôi."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "medical_policy_refusal"
    assert body["model_used"] == "legal-hard-guard-v1"
    assert body["emergency"] is False
    assert body["retrieved_ids"] == []
    assert "không có thẩm quyền kê đơn" in body["answer"].lower()


def test_routed_chat_infer_recovers_with_degraded_mode(monkeypatch: pytest.MonkeyPatch):
    from clara_ml.main import rag_pipeline
    from clara_ml.rag.pipeline import RagResult

    original_run = rag_pipeline.run
    state = {"calls": 0}

    def _flaky_run(*args, **kwargs):
        state["calls"] += 1
        if state["calls"] == 1:
            raise TimeoutError("external retrieval timeout")
        return RagResult(
            query=str(args[0]) if args else "query",
            retrieved_ids=["internal-1"],
            answer="degraded-answer",
            model_used="deepseek-v3.2",
            retrieved_context=[],
            context_debug={},
            flow_events=[],
        )

    monkeypatch.setattr(rag_pipeline, "run", _flaky_run)
    try:
        response = client.post(
            "/v1/chat/routed",
            json={"query": "toi bi dau da day khi dung warfarin"},
        )
    finally:
        monkeypatch.setattr(rag_pipeline, "run", original_run)

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "degraded-answer"
    assert body["model_used"] == "deepseek-v3.2"
    assert any(
        event.get("stage") == "degraded_recovery" and event.get("status") == "completed"
        for event in body["flow_events"]
    )


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
    assert isinstance(body.get("sources"), list)
    assert len(body["sources"]) >= 1
    assert body["sources"] == body["citations"]
    assert isinstance(body["answer"], str)
    assert body["answer"]
    assert isinstance(body.get("flow_events"), list)
    assert any(event.get("stage") == "planner" for event in body["flow_events"])
    assert any(event.get("stage") == "verification" for event in body["flow_events"])
    assert all("payload" in event for event in body["flow_events"] if isinstance(event, dict))
    assert isinstance(body["metadata"].get("planner_trace"), dict)
    assert isinstance(body["metadata"].get("retrieval_trace"), dict)
    assert isinstance(body["metadata"].get("verifier_trace"), dict)
    assert isinstance(body["telemetry"].get("search_plan"), dict)
    assert isinstance(body["telemetry"].get("index_summary"), dict)
    assert isinstance(body["telemetry"].get("source_attempts"), list)
    assert body["metadata"]["verification_status"]["verdict"] in {"pass", "warn", "fail"}
    assert any(event.get("stage") == "evidence_search" for event in body["flow_events"])
    assert any(event.get("stage") == "evidence_index" for event in body["flow_events"])


def test_research_tier2_blocks_prescription_and_dosage_requests():
    response = client.post(
        "/v1/research/tier2",
        json={"query": "Kê đơn và cho tôi liều warfarin mỗi ngày."},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["intent"] == "medical_policy_refusal"
    assert body["model_used"] == "legal-hard-guard-v1"
    assert body["emergency"] is False
    assert body["retrieved_ids"] == []
    assert body["guard_reason"] in {"prescription_request", "dosage_request"}


def test_research_tier2_blocks_guideline_wording_when_requesting_diagnosis_or_dose():
    response = client.post(
        "/v1/research/tier2",
        json={"query": "Guideline-based diagnosis for chest pain and recommended dose for me."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "medical_policy_refusal"
    assert body["model_used"] == "legal-hard-guard-v1"
    assert body["guard_reason"] in {"diagnosis_request", "dosage_request"}


def test_research_tier2_blocks_vietnamese_diacritic_prescription_only():
    response = client.post(
        "/v1/research/tier2",
        json={"query": "Bạn kê đơn kháng sinh cho tôi luôn nhé."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "medical_policy_refusal"
    assert body["model_used"] == "legal-hard-guard-v1"
    assert body["guard_reason"] == "prescription_request"


def test_research_tier2_blocks_vietnamese_diacritic_diagnosis_only():
    response = client.post(
        "/v1/research/tier2",
        json={"query": "Tôi có phải bị suy tim không? Hãy chẩn đoán."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "medical_policy_refusal"
    assert body["model_used"] == "legal-hard-guard-v1"
    assert body["guard_reason"] == "diagnosis_request"


def test_chat_legal_guard_blocks_vietnamese_non_accent_phrasing():
    response = client.post(
        "/v1/chat/routed",
        json={"query": "toi mac benh gi va nen uong may vien warfarin moi ngay"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "medical_policy_refusal"
    assert body["model_used"] == "legal-hard-guard-v1"
    assert body["guard_reason"] in {"diagnosis_request", "dosage_request"}


def test_research_tier2_emergency_escalates_fastpath():
    response = client.post(
        "/v1/research/tier2",
        json={"query": "Bệnh nhân đau ngực dữ dội, khó thở và ngất xỉu"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "emergency_triage"
    assert body["emergency"] is True
    assert body["policy_action"] == "escalate"
    assert body["model_used"] == "research-emergency-guard-v1"


def test_research_tier2_recovers_with_safe_fallback(monkeypatch: pytest.MonkeyPatch):
    import clara_ml.main as main_module

    original_runner = main_module.run_research_tier2

    def _boom(_payload):
        raise RuntimeError("deepseek_generation_failed")

    monkeypatch.setattr(main_module, "run_research_tier2", _boom)
    try:
        response = client.post(
            "/v1/research/tier2",
            json={"query": "Warfarin va NSAID co gi nguy hiem?"},
        )
    finally:
        monkeypatch.setattr(main_module, "run_research_tier2", original_runner)

    assert response.status_code == 200
    body = response.json()
    assert body["model_used"] == "ml-safe-fallback-v1"
    assert body["fallback"] is True
    assert body["policy_action"] == "warn"
    assert str(body["fallback_reason"]).startswith("RuntimeError")
    assert isinstance(body.get("answer_markdown"), str)
    assert "kết luận nhanh" in body["answer_markdown"].lower()
    assert isinstance(body.get("sources"), list)
    assert len(body["sources"]) >= 1
    assert isinstance(body.get("flow_events"), list)
    assert any(event.get("stage") == "fallback_response" for event in body["flow_events"])
    generation_events = [
        event for event in body["flow_events"] if event.get("stage") == "rag_generation"
    ]
    assert generation_events
    assert "deepseek_generation_failed" not in str(generation_events[0].get("note", "")).lower()


def test_research_tier2_flow_search_index_events_precede_synthesis():
    response = client.post(
        "/v1/research/tier2",
        json={
            "query": "Compare evidence for aspirin + ibuprofen bleeding risk in older adults.",
            "research_mode": "deep",
        },
    )
    assert response.status_code == 200
    body = response.json()
    events = body.get("flow_events", [])
    assert isinstance(events, list)
    assert len(events) > 0

    synthesis_indices = [
        idx
        for idx, event in enumerate(events)
        if str(event.get("stage", "")).strip().lower() == "answer_synthesis"
    ]
    assert synthesis_indices, "Missing answer_synthesis event in tier2 flow."
    first_synthesis_index = synthesis_indices[0]

    retrieval_like_indices = [
        idx
        for idx, event in enumerate(events)
        if any(
            token in str(event.get("stage", "")).strip().lower()
            for token in ("search", "retrieval", "index")
        )
    ]
    assert retrieval_like_indices, "Missing retrieval/search/index events in tier2 flow."
    assert max(retrieval_like_indices) < first_synthesis_index


def test_research_tier2_deep_mode_returns_multi_pass_telemetry():
    response = client.post(
        "/v1/research/tier2",
        json={
            "query": "Compare evidence for aspirin + ibuprofen bleeding risk in older adults.",
            "research_mode": "deep",
        },
    )
    assert response.status_code == 200
    body = response.json()

    assert body["research_mode"] == "deep"
    assert body["metadata"]["research_mode"] == "deep"
    assert isinstance(body.get("trace_id"), str)
    assert isinstance(body.get("run_id"), str)
    assert body["metadata"]["trace_id"] == body["trace_id"] == body["telemetry"]["trace_id"]
    assert body["metadata"]["run_id"] == body["run_id"] == body["telemetry"]["run_id"]
    assert body["metadata"]["pipeline"] == "p2-research-tier2-deep-v1"
    assert body["deep_pass_count"] >= 1
    assert body["metadata"]["deep_pass_count"] >= 1
    assert body["telemetry"]["scores"]["deep_pass_count"] >= 1
    assert any(
        event.get("stage") == "deep_research" and event.get("status") == "completed"
        for event in body.get("flow_events", [])
    )
    assert any(
        event.get("stage") == "deep_retrieval_pass" and event.get("status") == "completed"
        for event in body.get("flow_events", [])
    )
    assert any(
        event.get("stage") == "deep_retrieval_pass"
        and event.get("status") == "completed"
        and isinstance(event.get("payload"), dict)
        and "docs_found" in event["payload"]
        and "source_errors" in event["payload"]
        for event in body.get("flow_events", [])
    )
    source_attempts = body["telemetry"].get("source_attempts")
    if source_attempts is None:
        source_attempts = body["telemetry"].get("deep_pass_summaries")
    assert isinstance(source_attempts, list)
    assert len(source_attempts) >= 1

    index_summary = body["telemetry"].get("index_summary")
    if index_summary is None:
        retrieval_trace = body.get("retrieval_trace", {})
        index_summary = {
            "retrieved_count": retrieval_trace.get("retrieved_count"),
            "source_counts": retrieval_trace.get("source_counts"),
        }
    assert isinstance(index_summary, dict)
    assert "retrieved_count" in index_summary
    assert "source_counts" in index_summary
    stage_spans = body["metadata"].get("stage_spans")
    assert isinstance(stage_spans, list)
    assert any(str(item.get("stage")) == "deep_research" for item in stage_spans)


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
        assert set(
            ["specialist", "reasoning_log", "key_findings", "triage", "recommendation"]
        ).issubset(item.keys())
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


def test_council_intake_transcript_only_success(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    def _fake_run_council_intake(**kwargs):
        captured.update(kwargs)
        return {
            "transcript": "bn đau đầu 2 ngày",
            "symptoms": ["đau đầu"],
            "labs": [],
            "medications": [],
            "history": ["tăng huyết áp"],
            "text_fields": {
                "symptoms_input": "đau đầu",
                "labs_input": "",
                "medications_input": "",
                "history_input": "tăng huyết áp",
            },
            "warnings": [],
            "model_used": "deepseek-v3.2",
        }

    monkeypatch.setattr("clara_ml.main.run_council_intake", _fake_run_council_intake)

    response = client.post(
        "/v1/council/intake",
        data={"transcript": "bn đau đầu 2 ngày"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["text_fields"]["symptoms_input"] == "đau đầu"
    assert body["model_used"] == "deepseek-v3.2"

    assert captured["transcript"] == "bn đau đầu 2 ngày"
    assert captured["audio_bytes"] is None
    assert captured["audio_filename"] == "audio-input"
    assert captured["audio_content_type"] == "application/octet-stream"


def test_council_intake_missing_input_returns_400():
    response = client.post("/v1/council/intake")

    assert response.status_code == 400
    assert "Either transcript or audio_file is required" in response.json()["detail"]


def test_council_intake_runtime_error_returns_400(monkeypatch: pytest.MonkeyPatch):
    def _fake_run_council_intake(**_kwargs):
        raise RuntimeError("deepseek unavailable")

    monkeypatch.setattr("clara_ml.main.run_council_intake", _fake_run_council_intake)

    response = client.post(
        "/v1/council/intake",
        data={"transcript": "bn khó thở"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "deepseek unavailable"
