from __future__ import annotations

from datetime import timedelta

from clara_ml.agents import research_tier2 as tier2
from clara_ml.rag.pipeline import RagResult


def test_filter_context_for_ddi_keeps_authoritative_label_rows():
    topic = "Tương tác warfarin với thuốc giảm đau"
    rows = [
        {
            "id": "openfda-warfarin",
            "source": "openfda",
            "title": "Warfarin sodium",
            "text": "Warfarin label and safety information.",
            "url": "https://open.fda.gov/apis/drug/label/",
        },
        {
            "id": "pubmed-unrelated",
            "source": "pubmed",
            "title": "Mediterranean diet review",
            "text": "Dietary intervention for cardiovascular prevention.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
        },
    ]

    filtered = tier2._filter_context_for_topic(topic, rows)

    assert isinstance(filtered, list)
    assert any(item.get("id") == "openfda-warfarin" for item in filtered)
    assert all(item.get("id") != "pubmed-unrelated" for item in filtered)


def test_run_research_tier2_falls_back_to_merged_context_when_ddi_filter_empty(
    monkeypatch,
):
    def _force_empty_filter(topic: str, rows: list[dict]) -> list[dict]:
        return []

    def _fake_pipeline_run(self, query: str, **kwargs) -> RagResult:  # pragma: no cover - helper
        return RagResult(
            query=query,
            retrieved_ids=["openfda-1-warfarin"],
            answer="Nội dung tạm.",
            model_used="deepseek-v3.2",
            retrieved_context=[
                {
                    "id": "openfda-1-warfarin",
                    "source": "openfda",
                    "title": "Warfarin sodium",
                    "text": "Warfarin interaction and bleeding warning.",
                    "url": "https://open.fda.gov/apis/drug/label/",
                    "score": 0.88,
                }
            ],
            context_debug={
                "relevance": 0.7,
                "low_context_threshold": 0.15,
                "source_counts": {"openfda": 1},
                "retrieval_trace": {
                    "source_attempts": [
                        {"provider": "openfda", "status": "completed", "documents": 1}
                    ],
                    "index_summary": {"selected_count": 1},
                    "search_plan": {"query": query},
                },
            },
            flow_events=[],
            trace={"retrieval": {"source_attempts": [{"provider": "openfda"}]}},
        )

    monkeypatch.setattr(tier2, "_filter_context_for_topic", _force_empty_filter)
    monkeypatch.setattr(tier2.RagPipelineP1, "run", _fake_pipeline_run)

    result = tier2.run_research_tier2(
        {
            "query": "Tương tác warfarin với thuốc giảm đau phổ biến",
            "research_mode": "fast",
            "strict_deepseek_required": False,
        }
    )

    citations = result.get("citations", [])
    assert isinstance(citations, list)
    assert len(citations) >= 1
    assert citations[0].get("source") != "system_fallback"
    assert result.get("fallback_used") is False
    assert isinstance(result.get("source_attempts"), list)
    assert isinstance(result.get("source_errors"), dict)
    assert "fallback_reason" in result
    assert isinstance(result.get("query_plan"), dict)
    assert isinstance(result.get("telemetry", {}).get("query_plan"), dict)
    assert isinstance(result.get("metadata", {}).get("source_attempts"), list)
    assert isinstance(result.get("metadata", {}).get("source_errors"), dict)


def test_build_planner_hints_applies_latency_guard_for_fast_ddi_query():
    hints = tier2._build_planner_hints(
        topic="Tương tác warfarin với ibuprofen ở người cao tuổi",
        source_mode=None,
        route_role="researcher",
        route_intent="evidence_review",
        uploaded_documents=[],
        rag_sources=[],
        research_mode="fast",
    )
    assert hints["scientific_retrieval_enabled"] is False
    assert hints["web_retrieval_enabled"] is False
    assert "fast_mode_latency_guard" in hints["reason_codes"]
    assert "fast_scientific_disabled_for_sla" in hints["reason_codes"]


def test_filter_context_for_ddi_keeps_primary_alias_rows():
    topic = "Tương tác warfarin với thuốc giảm đau"
    rows = [
        {
            "id": "dailymed-coumadin",
            "source": "dailymed",
            "title": "Coumadin prescribing information",
            "text": "Coumadin (warfarin) interaction warnings with NSAID.",
            "url": "https://dailymed.nlm.nih.gov/",
        },
        {
            "id": "unrelated-topic",
            "source": "pubmed",
            "title": "Hypertension diet article",
            "text": "DASH nutrition intervention outcomes.",
            "url": "https://pubmed.ncbi.nlm.nih.gov/999/",
        },
    ]

    filtered = tier2._filter_context_for_topic(topic, rows)

    assert any(item.get("id") == "dailymed-coumadin" for item in filtered)
    assert all(item.get("id") != "unrelated-topic" for item in filtered)


def test_normalize_retrieval_events_adds_sequence_and_elapsed():
    base = tier2._now_iso()
    later = (tier2.datetime.fromisoformat(base) + timedelta(milliseconds=35)).isoformat()
    events = [
        {
            "stage": "planner",
            "status": "completed",
            "timestamp": base,
            "source_count": 0,
            "note": "ok",
            "payload": {},
        },
        {
            "stage": "retrieval",
            "status": "completed",
            "timestamp": later,
            "source_count": 2,
            "note": "ok",
            "payload": {},
        },
    ]

    normalized = tier2._normalize_retrieval_events(events)

    assert normalized[0]["event_sequence"] == 1
    assert normalized[1]["event_sequence"] == 2
    assert normalized[1]["payload"]["event_sequence"] == 2
    assert normalized[1]["payload"]["elapsed_ms"] >= 30


def test_build_source_aware_query_plan_handles_vi_en_ddi():
    query_plan = tier2._build_source_aware_query_plan(
        topic="Tương tác warfarin với ibuprofen nguy cơ chảy máu",
        research_mode="fast",
        keywords=["warfarin", "ibuprofen", "interaction", "bleeding"],
    )

    assert query_plan["is_ddi_query"] is True
    assert isinstance(query_plan.get("canonical_query"), str)
    assert "warfarin" in query_plan.get("canonical_query", "").lower()
    assert isinstance(query_plan.get("source_queries"), dict)
    assert len(query_plan["source_queries"].get("internal", [])) >= 1
    assert len(query_plan["source_queries"].get("scientific", [])) >= 1
    assert isinstance(query_plan.get("decomposition"), dict)
    assert len(query_plan["decomposition"].get("fast_pass_queries", [])) >= 1


def test_run_research_tier2_emits_contradiction_miner_and_verification_matrix(monkeypatch):
    def _fake_pipeline_run(self, query: str, **kwargs) -> RagResult:  # pragma: no cover - helper
        return RagResult(
            query=query,
            retrieved_ids=["doc-verify-1"],
            answer="Warfarin khong lam tang nguy co chay mau khi dung cung ibuprofen.",
            model_used="deepseek-v3.2",
            retrieved_context=[
                {
                    "id": "doc-verify-1",
                    "source": "pubmed",
                    "title": "Clinical interaction summary",
                    "text": (
                        "Tai lieu cho thay warfarin co the lam tang nguy co chay mau "
                        "khi dung cung ibuprofen."
                    ),
                    "url": "https://pubmed.ncbi.nlm.nih.gov/10000001/",
                    "score": 0.9,
                }
            ],
            context_debug={
                "relevance": 0.8,
                "low_context_threshold": 0.15,
                "source_counts": {"pubmed": 1},
                "retrieval_trace": {
                    "source_attempts": [
                        {"provider": "pubmed", "status": "completed", "documents": 1}
                    ],
                    "index_summary": {"selected_count": 1},
                    "search_plan": {"query": query},
                },
            },
            flow_events=[],
            trace={"retrieval": {"source_attempts": [{"provider": "pubmed"}]}},
        )

    monkeypatch.setattr(tier2.RagPipelineP1, "run", _fake_pipeline_run)

    result = tier2.run_research_tier2(
        {
            "query": "Tương tác warfarin với ibuprofen",
            "research_mode": "fast",
            "strict_deepseek_required": False,
        }
    )

    verification_matrix = result.get("verification_matrix", {})
    assert isinstance(verification_matrix, dict)
    assert isinstance(verification_matrix.get("rows"), list)
    assert isinstance(verification_matrix.get("summary"), dict)
    assert isinstance(verification_matrix.get("contradiction_summary"), dict)
    assert isinstance(result.get("metadata", {}).get("verification_matrix"), dict)
    assert isinstance(result.get("telemetry", {}).get("verification_matrix"), dict)

    flow_events = result.get("flow_events", [])
    assert isinstance(flow_events, list)
    contradiction_idx = next(
        idx for idx, event in enumerate(flow_events) if event.get("stage") == "contradiction_miner"
    )
    matrix_idx = next(
        idx for idx, event in enumerate(flow_events) if event.get("stage") == "verification_matrix"
    )
    assert contradiction_idx < matrix_idx

    contradiction_event = flow_events[contradiction_idx]
    matrix_event = flow_events[matrix_idx]
    assert isinstance(contradiction_event.get("payload"), dict)
    assert isinstance(matrix_event.get("payload"), dict)
    assert "summary" in contradiction_event["payload"]
    assert "rows" in matrix_event["payload"]
    assert "summary" in matrix_event["payload"]
