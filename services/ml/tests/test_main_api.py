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


def test_metrics_endpoint_returns_prometheus_text_and_json_snapshot():
    response_prometheus = client.get("/metrics")
    assert response_prometheus.status_code == 200
    assert response_prometheus.headers["content-type"].startswith("text/plain")
    body_prometheus = response_prometheus.text

    assert "# TYPE requests_total counter" in body_prometheus
    assert "# TYPE error_total counter" in body_prometheus
    assert "# TYPE avg_latency_ms gauge" in body_prometheus
    assert "# TYPE by_path counter" in body_prometheus

    response_json = client.get("/metrics/json")
    assert response_json.status_code == 200
    body_json = response_json.json()

    assert set(["requests_total", "by_path", "error_total", "avg_latency_ms"]).issubset(
        body_json.keys()
    )
    assert body_json["requests_total"] == 1
    assert body_json["by_path"] == {"/metrics": 1}
    assert body_json["error_total"] == 0
    assert isinstance(body_json["avg_latency_ms"], float)
    assert body_json["avg_latency_ms"] >= 0.0


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

    response_metrics = client.get("/metrics/json")
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


def test_routed_chat_infer_rule_verification_flag_overrides_legacy(monkeypatch: pytest.MonkeyPatch):
    from clara_ml.main import rag_pipeline
    from clara_ml.rag.pipeline import RagResult

    original_run = rag_pipeline.run

    def _fake_run(*args, **kwargs):  # noqa: ARG001
        return RagResult(
            query="query",
            retrieved_ids=["doc-1"],
            answer="answer",
            model_used="local-synth-v1",
            retrieved_context=[],
            context_debug={},
            flow_events=[],
        )

    def _should_not_verify(**kwargs):  # noqa: ARG001
        raise AssertionError("run_fides_lite must be skipped when rule_verification_enabled=false")

    monkeypatch.setattr(rag_pipeline, "run", _fake_run)
    monkeypatch.setattr("clara_ml.main.run_fides_lite", _should_not_verify)
    try:
        response = client.post(
            "/v1/chat/routed",
            json={
                "query": "Toi can tu van tuong tac warfarin.",
                "rag_flow": {
                    "verification_enabled": True,
                    "rule_verification_enabled": False,
                },
            },
        )
    finally:
        monkeypatch.setattr(rag_pipeline, "run", original_run)

    assert response.status_code == 200
    body = response.json()
    assert body.get("factcheck") is None
    assert body["flow_applied"]["verification_enabled"] is False
    assert body["flow_applied"]["rule_verification_enabled"] is False
    assert not any(event.get("stage") == "verification" for event in body.get("flow_events", []))


def test_routed_chat_infer_propagates_rag_runtime_flags_to_pipeline_and_verifier(
    monkeypatch: pytest.MonkeyPatch,
):
    from clara_ml.factcheck.fides_lite import FactCheckResult
    from clara_ml.main import rag_pipeline
    from clara_ml.rag.pipeline import RagResult

    original_run = rag_pipeline.run
    captured: dict[str, object] = {}

    def _fake_run(*args, **kwargs):  # noqa: ARG001
        captured["pipeline_kwargs"] = dict(kwargs)
        return RagResult(
            query="query",
            retrieved_ids=["doc-1"],
            answer="answer",
            model_used="local-synth-v1",
            retrieved_context=[{"id": "doc-1", "text": "context"}],
            context_debug={},
            flow_events=[],
        )

    def _fake_verify(*, answer, retrieved_context, nli_enabled=None, mode="lite"):  # noqa: ARG001
        captured["nli_enabled"] = nli_enabled
        return FactCheckResult(
            enabled=True,
            stage="fides-lite-v1.2",
            verdict="pass",
            confidence=0.8,
            supported_claims=1,
            total_claims=1,
            unsupported_claims=[],
            evidence_count=1,
            severity="low",
            note="ok",
            fide_report={},
            verification_matrix=[],
            contradiction_summary={},
        )

    monkeypatch.setattr(rag_pipeline, "run", _fake_run)
    monkeypatch.setattr("clara_ml.main.run_fides_lite", _fake_verify)
    try:
        response = client.post(
            "/v1/chat/routed",
            json={
                "query": "Toi can tu van tuong tac warfarin.",
                "rag_flow": {
                    "rule_verification_enabled": True,
                    "rag_reranker_enabled": True,
                    "nli_model_enabled": False,
                    "rag_nli_enabled": True,
                    "rag_graphrag_enabled": False,
                },
            },
        )
    finally:
        monkeypatch.setattr(rag_pipeline, "run", original_run)

    assert response.status_code == 200
    body = response.json()
    pipeline_kwargs = body and captured.get("pipeline_kwargs")
    assert isinstance(pipeline_kwargs, dict)
    assert pipeline_kwargs.get("rag_reranker_enabled") is True
    assert pipeline_kwargs.get("rag_graphrag_enabled") is False
    assert captured.get("nli_enabled") is False
    assert body["flow_applied"]["nli_model_enabled"] is False
    assert body["flow_applied"]["rag_reranker_enabled"] is True
    assert body["flow_applied"]["rag_nli_enabled"] is False
    assert body["flow_applied"]["rag_graphrag_enabled"] is False


def test_routed_chat_infer_propagates_hitechcloud_runtime_to_pipeline(
    monkeypatch: pytest.MonkeyPatch,
):
    from clara_ml.main import rag_pipeline
    from clara_ml.rag.pipeline import RagResult

    original_run = rag_pipeline.run
    captured: dict[str, object] = {}

    def _fake_run(*args, **kwargs):  # noqa: ARG001
        captured["pipeline_kwargs"] = dict(kwargs)
        return RagResult(
            query="query",
            retrieved_ids=["doc-1"],
            answer="answer",
            model_used="local-synth-v1",
            retrieved_context=[],
            context_debug={},
            flow_events=[],
        )

    monkeypatch.setattr(rag_pipeline, "run", _fake_run)
    try:
        response = client.post(
            "/v1/chat/routed",
            json={
                "query": "Tôi cần giải thích tương tác thuốc.",
                "rag_flow": {
                    "llm_provider": "hitechcloud_gpt53_codex_high",
                    "llm_base_url": "https://platform.hitechcloud.one/v1",
                    "llm_model": "gpt-5.3-codex-high",
                    "llm_api_key": "test-key-hitech",
                },
            },
        )
    finally:
        monkeypatch.setattr(rag_pipeline, "run", original_run)

    assert response.status_code == 200
    body = response.json()
    pipeline_kwargs = captured.get("pipeline_kwargs")
    assert isinstance(pipeline_kwargs, dict)
    llm_runtime = pipeline_kwargs.get("llm_runtime")
    assert isinstance(llm_runtime, dict)
    assert llm_runtime.get("provider") == "hitechcloud_gpt53_codex_high"
    assert llm_runtime.get("base_url") == "https://platform.hitechcloud.one/v1"
    assert llm_runtime.get("model") == "gpt-5.3-codex-high"
    assert body["flow_applied"]["llm_provider"] == "hitechcloud_gpt53_codex_high"
    assert body["flow_applied"]["llm_base_url"] == "https://platform.hitechcloud.one/v1"
    assert body["flow_applied"]["llm_model"] == "gpt-5.3-codex-high"


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
    assert isinstance(body["metadata"].get("otel_trace_metadata"), dict)
    assert isinstance(body["telemetry"].get("search_plan"), dict)
    assert isinstance(body["telemetry"].get("index_summary"), dict)
    assert isinstance(body["telemetry"].get("source_attempts"), list)
    assert isinstance(body["telemetry"].get("otel_trace_metadata"), dict)
    assert body["metadata"]["verification_status"]["verdict"] in {"pass", "warn", "fail"}
    assert any(event.get("stage") == "evidence_search" for event in body["flow_events"])
    assert any(event.get("stage") == "evidence_index" for event in body["flow_events"])


def test_research_tier2_honors_rule_verification_flag_in_rag_flow():
    response = client.post(
        "/v1/research/tier2",
        json={
            "query": "Evaluate DDI evidence for warfarin and NSAID co-prescribing.",
            "rag_flow": {
                "verification_enabled": True,
                "rule_verification_enabled": False,
                "rag_nli_enabled": False,
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    flow_events = body.get("flow_events", [])
    assert any(
        event.get("stage") == "verification" and event.get("status") == "skipped"
        for event in flow_events
    )
    metadata = body.get("metadata", {})
    flow_flags = metadata.get("flow_flags", {})
    assert flow_flags.get("verification_enabled") is True
    assert flow_flags.get("rule_verification_enabled") is False
    assert flow_flags.get("rag_nli_enabled") is False


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


def test_research_tier2_deep_beta_mode_returns_runtime_contract():
    response = client.post(
        "/v1/research/tier2",
        json={
            "query": "Perform deep beta analysis for warfarin and ibuprofen safety profile.",
            "research_mode": "deep_beta",
        },
    )
    assert response.status_code == 200
    body = response.json()

    assert body["research_mode"] == "deep_beta"
    assert body["metadata"]["research_mode"] == "deep_beta"
    assert body["metadata"]["pipeline"] == "p2-research-tier2-deep-beta-v1"
    assert body["deep_pass_count"] >= 1

    verification_matrix = body.get("verification_matrix", {})
    assert isinstance(verification_matrix, dict)
    assert verification_matrix.get("version") == "claim-v2-nli"
    assert isinstance(verification_matrix.get("rows"), list)
    assert isinstance(verification_matrix.get("summary"), dict)
    assert "safety_override" in verification_matrix

    flow_events = body.get("flow_events", [])
    assert isinstance(flow_events, list)
    assert any(str(item.get("stage")).startswith("deep_beta") for item in flow_events)
    assert any(item.get("stage") == "verification_matrix" for item in flow_events)

    telemetry = body.get("telemetry", {})
    assert isinstance(telemetry, dict)
    index_summary = telemetry.get("index_summary", {})
    assert isinstance(index_summary, dict)
    rerank = index_summary.get("rerank", {})
    assert isinstance(rerank, dict)
    assert "rerank_topn" in rerank
    assert "rerank_latency_ms" in rerank

    stage_spans = body["metadata"].get("stage_spans")
    assert isinstance(stage_spans, list)
    assert any(str(item.get("stage")).startswith("deep_beta") for item in stage_spans)


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
    assert isinstance(body["council_consensus"], dict)
    assert body["council_consensus"]["winning_triage"] in {
        "routine_follow_up",
        "same_day_review",
        "emergency_escalation",
    }
    assert isinstance(body["council_consensus"]["vote_breakdown"], dict)
    assert 0.0 <= body["council_consensus"]["support_ratio"] <= 1.0
    assert 0.0 <= body["council_consensus"]["disagreement_index"] <= 1.0
    assert isinstance(body["consensus_summary"], str)
    assert body["consensus_summary"]
    assert isinstance(body["divergence_notes"], list)
    assert isinstance(body["final_recommendation"], str)
    assert body["final_recommendation"]
    assert isinstance(body["estimated_duration_minutes"], int)
    assert body["estimated_duration_minutes"] > 0
    assert body["emergency_escalation"]["triggered"] is False
    assert body["emergency_escalation"]["action"] == "standard_multidisciplinary_pathway"
    assert body["needs_more_info"] is False
    assert isinstance(body["followup_questions"], list)
    assert isinstance(body["confidence_score"], float)
    assert 0.0 <= body["confidence_score"] <= 1.0
    assert body["confidence_level"] in {"low", "medium", "high"}
    assert isinstance(body["data_quality_score"], float)
    assert 0.0 <= body["data_quality_score"] <= 1.0
    assert body["data_quality_level"] in {"low", "medium", "high"}
    assert isinstance(body["analyze"], dict)
    assert isinstance(body["details"], dict)
    assert isinstance(body["citations"], list)
    assert len(body["citations"]) >= 1
    assert isinstance(body["citation_quality"], dict)
    assert body["citation_quality"]["total_citations"] == len(body["citations"])
    for item in body["citations"]:
        assert 0.0 <= item["evidence_strength"] <= 1.0
        assert item["quality_flag"] in {
            "high_signal",
            "supporting_signal",
            "context_only",
            "negated_context",
        }
    assert isinstance(body["reasoning_timeline"], list)
    assert len(body["reasoning_timeline"]) >= 6
    steps = [item["step"] for item in body["reasoning_timeline"]]
    assert "consensus_decision" in steps
    assert "safety_gate" in steps
    assert isinstance(body["neural_risk"], dict)
    assert body["neural_risk"]["enabled"] is False
    assert body["neural_risk"]["model_version"] == "council-neural-shadow-v1"
    assert isinstance(body["research"], dict)
    assert isinstance(body["deepdive"], dict)
    assert body["analyze"]["consensus_triage"] in {
        "routine_follow_up",
        "same_day_review",
        "emergency_escalation",
    }
    assert body["analyze"]["needs_more_info"] is False
    assert isinstance(body["details"]["specialist_assessments"], list)
    assert isinstance(body["research"]["topics"], list)
    assert isinstance(body["deepdive"]["specialist_sections"], list)


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
    metadata = body["emergency_escalation"]["metadata"]
    assert metadata["priority"] == "critical"
    assert metadata["recommended_sla_minutes"] == 5
    assert metadata["requires_human_handoff"] is True
    assert metadata["generated_at_utc"].endswith("Z")
    assert isinstance(metadata["trigger_evidence"], list)
    assert len(metadata["trigger_evidence"]) >= 1
    assert body["estimated_duration_minutes"] == 5
    assert "Emergency escalation triggered" in body["final_recommendation"]
    assert body["needs_more_info"] is False
    assert isinstance(body["emergency_escalation"]["negated_red_flags"], list)
    assert body["analyze"]["emergency_triggered"] is True
    assert body["confidence_level"] in {"medium", "high"}


def test_council_run_supports_neural_shadow_scoring():
    response = client.post(
        "/v1/council/run",
        json={
            "symptoms": ["fatigue", "palpitations"],
            "labs": {"egfr": 55, "glucose": 280},
            "medications": ["metformin", "ibuprofen", "aspirin"],
            "history": ["type 2 diabetes", "chronic kidney disease"],
            "specialists": ["cardiology", "endocrinology", "nephrology"],
            "council_neural_enabled": True,
        },
    )
    assert response.status_code == 200
    body = response.json()

    assert isinstance(body["neural_risk"], dict)
    assert body["neural_risk"]["enabled"] is True
    assert body["neural_risk"]["shadow_mode"] is True
    assert body["neural_risk"]["model_version"] == "council-neural-shadow-v1"
    assert body["neural_risk"]["risk_band"] in {"low", "medium", "high"}
    assert 0.0 <= body["neural_risk"]["risk_probability"] <= 1.0
    assert body["neural_risk"]["recommended_triage"] in {
        "routine_follow_up",
        "same_day_review",
        "emergency_escalation",
    }
    assert isinstance(body["neural_risk"]["feature_map"], dict)
    assert isinstance(body["neural_risk"]["top_contributors"], list)
    assert len(body["neural_risk"]["top_contributors"]) >= 1


def test_council_run_negation_aware_and_insufficient_data_gate():
    response = client.post(
        "/v1/council/run",
        json={
            "symptoms": ["no chest pain", "denies shortness of breath"],
            "labs": {},
            "medications": [],
            "history": [],
            "specialists": ["cardiology", "neurology"],
        },
    )
    assert response.status_code == 200
    body = response.json()

    assert body["emergency_escalation"]["triggered"] is False
    assert body["emergency_escalation"]["red_flags"] == []
    assert isinstance(body["emergency_escalation"]["negated_red_flags"], list)
    assert len(body["emergency_escalation"]["negated_red_flags"]) >= 1
    assert body["needs_more_info"] is True
    assert isinstance(body["followup_questions"], list)
    assert len(body["followup_questions"]) >= 1
    assert body["analyze"]["needs_more_info"] is True
    assert body["confidence_level"] == "low"
    assert "insufficient" in body["final_recommendation"].lower()
    assert isinstance(body["citations"], list)
    assert any(item.get("evidence_type") == "negated_symptom" for item in body["citations"])
    assert body["citation_quality"]["negated_context_count"] >= 1
    assert body["emergency_escalation"]["metadata"]["priority"] in {"same_day", "routine", "urgent"}


def test_council_consult_with_transcript_and_overrides(monkeypatch: pytest.MonkeyPatch):
    def _fake_run_council_intake(**_kwargs):
        return {
            "symptoms": ["fatigue"],
            "labs": [],
            "medications": ["metformin"],
            "history": ["type 2 diabetes"],
            "council_payload": {
                "symptoms": ["fatigue"],
                "labs": {"glucose": 210.0},
                "medications": ["metformin"],
                "history": ["type 2 diabetes"],
            },
            "model_used": "deepseek-v3.2",
            "warnings": [],
            "missing_fields": [],
            "field_confidence": {"symptoms": 0.95},
        }

    monkeypatch.setattr("clara_ml.main.run_council_intake", _fake_run_council_intake)

    response = client.post(
        "/v1/council/consult",
        json={
            "transcript": "bn met moi, duong huyet cao",
            "symptoms": ["palpitations"],
            "specialists": ["cardiology", "endocrinology"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requested_specialists"] == ["cardiology", "endocrinology"]
    assert isinstance(body["final_recommendation"], str)
    assert body["intake"]["model_used"] == "deepseek-v3.2"
    assert isinstance(body["intake"]["warnings"], list)


def test_council_consult_missing_input_returns_400():
    response = client.post("/v1/council/consult", json={})

    assert response.status_code == 400
    assert "Missing consult input" in response.json()["detail"]


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
            "needs_more_info": False,
            "followup_questions": [],
            "confidence_score": 0.93,
            "confidence_level": "high",
            "data_quality_score": 0.84,
            "data_quality_level": "high",
            "analyze": {
                "needs_more_info": False,
                "followup_questions": [],
                "confidence": {"score": 0.93, "level": "high"},
                "data_quality": {"score": 0.84, "level": "high"},
            },
            "details": {"section_counts": {"symptoms": 1, "labs": 0, "medications": 0, "history": 1}},
            "citations": [{"source_id": "intake-symptom-1"}],
            "research": {"mode": "intake_extraction_v2", "topics": []},
            "deepdive": {"extraction": {"model_used": "deepseek-v3.2"}},
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
    assert body["needs_more_info"] is False
    assert body["confidence_level"] == "high"
    assert body["data_quality_level"] == "high"
    assert isinstance(body["analyze"], dict)
    assert isinstance(body["details"], dict)
    assert isinstance(body["citations"], list)
    assert isinstance(body["research"], dict)
    assert isinstance(body["deepdive"], dict)

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
