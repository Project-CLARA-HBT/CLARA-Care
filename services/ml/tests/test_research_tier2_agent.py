from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
import urllib.error

import pytest

from clara_ml.agents import research_tier2 as tier2
from clara_ml.rag.pipeline import RagPipelineP1, RagResult
from clara_ml.rag.retriever import Document


@pytest.fixture(autouse=True)
def _disable_deepseek_planner_by_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(tier2.settings, "deepseek_api_key", "")


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


def test_resolve_runtime_llm_config_prefers_env_in_deepseek_only(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(tier2.settings, "llm_deepseek_only", True)
    monkeypatch.setattr(tier2.settings, "deepseek_api_key", "env-deepseek-key")
    monkeypatch.setattr(tier2.settings, "deepseek_base_url", "https://api.yescale.vip/v1")
    monkeypatch.setattr(tier2.settings, "deepseek_model", "deepseek-v3.2")

    provider, api_key, base_url, model = tier2._resolve_runtime_llm_config(
        {
            "provider": "hitechcloud_gpt53_codex_high",
            "api_key": "runtime-hitech-key",
            "base_url": "https://platform.hitechcloud.one/v1",
            "model": "gpt-5.3-codex-high",
        }
    )

    assert provider == "deepseek"
    assert api_key == "env-deepseek-key"
    assert base_url == "https://api.yescale.vip/v1"
    assert model == "deepseek-v3.2"


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


def test_build_planner_hints_fast_mode_downgrades_full_stack_mode_to_auto():
    hints = tier2._build_planner_hints(
        topic="Tương tác warfarin với ibuprofen ở người cao tuổi",
        source_mode=None,
        route_role="researcher",
        route_intent="evidence_review",
        uploaded_documents=[],
        rag_sources=[],
        research_mode="fast",
        retrieval_stack_mode="full",
    )
    assert hints["retrieval_stack_mode"] == "auto"
    assert hints["scientific_retrieval_enabled"] is False
    assert hints["web_retrieval_enabled"] is False
    assert hints["graphrag_enabled_override"] is None
    assert "stack_mode_full_downgraded_for_fast_mode" in hints["reason_codes"]
    assert "retrieval_stack_mode_auto" in hints["reason_codes"]
    assert "stack_mode_full_force_scientific" not in hints["reason_codes"]
    assert "stack_mode_full_force_web" not in hints["reason_codes"]
    assert "stack_mode_full_force_graphrag" not in hints["reason_codes"]


def test_emit_otel_trace_best_effort_does_not_expose_endpoint_or_error_details(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(tier2.settings, "otel_export_enabled", True)
    monkeypatch.setattr(tier2.settings, "otel_export_endpoint", "http://internal-collector.local:4318/v1/traces")

    def _raise_http_error(*args, **kwargs):
        raise urllib.error.HTTPError(
            url="http://internal-collector.local:4318/v1/traces",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(tier2.urllib.request, "urlopen", _raise_http_error)
    status = tier2._emit_otel_trace_best_effort(
        otel_trace_metadata={"trace_id": "trace-123"},
        flow_events=[{"stage": "planner"}],
    )

    assert status["enabled"] is True
    assert status["sent"] is False
    assert status["http_status"] == 403
    assert status["error"] == "export_failed"
    assert "endpoint" not in status
    assert "internal-collector.local" not in str(status)


def test_build_planner_hints_deep_mode_full_stack_forces_connectors_only():
    hints = tier2._build_planner_hints(
        topic="Tương tác warfarin với ibuprofen ở người cao tuổi",
        source_mode=None,
        route_role="researcher",
        route_intent="evidence_review",
        uploaded_documents=[],
        rag_sources=[],
        research_mode="deep",
        retrieval_stack_mode="full",
    )
    assert hints["retrieval_stack_mode"] == "full"
    assert hints["scientific_retrieval_enabled"] is True
    assert hints["web_retrieval_enabled"] is True
    assert hints["graphrag_enabled_override"] is None
    assert "retrieval_stack_mode_full" in hints["reason_codes"]
    assert "stack_mode_full_downgraded_for_fast_mode" not in hints["reason_codes"]
    assert "stack_mode_full_force_scientific" in hints["reason_codes"]
    assert "stack_mode_full_force_web" in hints["reason_codes"]
    assert "stack_mode_full_force_graphrag" not in hints["reason_codes"]


def test_apply_keyword_filter_to_query_plan_aligns_keywords_by_source_language():
    base_query_plan = {
        "original_query": "Tương tác warfarin với ibuprofen",
        "canonical_query": "warfarin interaction with ibuprofen bleeding risk",
        "language_hint": "mixed",
        "source_queries": {
            "internal": ["Tương tác warfarin với ibuprofen"],
            "scientific": ["warfarin interaction clinical evidence"],
            "web": ["warfarin interaction guideline"],
        },
    }

    report = tier2._apply_keyword_filter_to_query_plan(
        topic="Tương tác warfarin với ibuprofen",
        query_plan=base_query_plan,
        planner_keywords=["tuong", "tac", "warfarin", "interaction", "guideline"],
        source_mode="davidrug",
    )

    keywords_by_source = report.get("keywords_by_source", {})
    assert "interaction" not in keywords_by_source.get("internal", [])
    assert "guideline" not in keywords_by_source.get("web", [])
    assert "tuong" not in keywords_by_source.get("scientific", [])
    assert "tac" not in keywords_by_source.get("scientific", [])

    query_plan = report.get("query_plan", {})
    source_queries = query_plan.get("source_queries", {})
    assert isinstance(source_queries.get("internal"), list)
    assert isinstance(source_queries.get("scientific"), list)
    assert isinstance(source_queries.get("web"), list)
    assert source_queries.get("scientific")
    assert query_plan.get("keyword_filter", {}).get("target_language_by_source", {}).get("web") == "vi"


def test_filter_keywords_by_language_marks_fallback_only_when_bucket_becomes_empty():
    filtered_keywords, fallback_used = tier2._filter_keywords_by_language(
        ["warfarin", "ibuprofen"],
        target_language="vi",
    )
    assert filtered_keywords == ["warfarin", "ibuprofen"]
    assert fallback_used is False

    filtered_all_generic, fallback_all_generic = tier2._filter_keywords_by_language(
        ["interaction", "guideline"],
        target_language="vi",
    )
    assert filtered_all_generic == ["interaction", "guideline"]
    assert fallback_all_generic is True


def test_source_router_prefers_scientific_for_critical_ddi():
    decision = tier2.decide_source_route(
        query="Tương tác warfarin và ibuprofen có nguy cơ xuất huyết nghiêm trọng không?",
        research_mode="deep",
        has_uploaded_documents=False,
        is_ddi_query=True,
        is_ddi_critical_query=True,
        language_hint="vi",
        web_policy_allowed=True,
    )
    assert decision.retrieval_route == "scientific-heavy"
    assert decision.enable_scientific is True
    assert decision.enable_internal is True
    assert decision.confidence >= 0.9


def test_source_router_respects_web_policy_block():
    decision = tier2.decide_source_route(
        query="Tương tác warfarin với ibuprofen",
        research_mode="deep",
        has_uploaded_documents=False,
        is_ddi_query=False,
        is_ddi_critical_query=False,
        language_hint="vi",
        web_policy_allowed=False,
    )
    assert decision.enable_web is False
    assert decision.retrieval_route in {"internal-heavy", "scientific-heavy"}


def test_source_router_critical_ddi_overrides_file_grounded_path():
    decision = tier2.decide_source_route(
        query="Warfarin và NSAID có nguy cơ xuất huyết nghiêm trọng không?",
        research_mode="deep",
        has_uploaded_documents=True,
        is_ddi_query=True,
        is_ddi_critical_query=True,
        language_hint="mixed",
        web_policy_allowed=True,
    )
    assert decision.retrieval_route == "scientific-heavy"
    assert decision.enable_scientific is True


def test_run_research_tier2_emits_retrieval_route_metadata(monkeypatch: pytest.MonkeyPatch):
    def _fake_pipeline_run(self, query: str, **kwargs) -> RagResult:  # pragma: no cover - helper
        return RagResult(
            query=query,
            retrieved_ids=["doc-1"],
            answer="Nội dung tạm thời.",
            model_used="deepseek-v3.2",
            retrieved_context=[
                {
                    "id": "doc-1",
                    "source": "pubmed",
                    "title": "Warfarin Interaction",
                    "text": "Relevant context.",
                    "url": "https://pubmed.ncbi.nlm.nih.gov/1/",
                    "score": 0.87,
                }
            ],
            context_debug={
                "relevance": 0.72,
                "low_context_threshold": 0.2,
                "retrieval_trace": {
                    "source_attempts": [{"provider": "pubmed", "status": "completed", "documents": 1}],
                    "source_errors": {},
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
            "research_mode": "deep",
            "strict_deepseek_required": False,
        }
    )
    assert result.get("retrieval_route") in {
        "internal-heavy",
        "scientific-heavy",
        "web-assisted",
        "file-grounded",
        "balanced",
    }
    assert isinstance(result.get("router_confidence"), float)
    assert 0.0 <= result.get("router_confidence", 0.0) <= 1.0
    metadata = result.get("metadata", {})
    telemetry = result.get("telemetry", {})
    assert metadata.get("retrieval_route") == result.get("retrieval_route")
    assert telemetry.get("retrieval_route") == result.get("retrieval_route")
    assert metadata.get("router_confidence") == result.get("router_confidence")
    assert telemetry.get("router_confidence") == result.get("router_confidence")
    assert "degraded_path" in result
    assert "degraded_path" in metadata
    assert "degraded_path" in telemetry
    assert isinstance(result.get("source_errors"), dict)
    assert isinstance(metadata.get("source_errors"), dict)
    assert isinstance(telemetry.get("source_errors"), dict)
    assert "fallback_reason" in result
    assert "fallback_reason" in metadata
    assert "fallback_reason" in telemetry


def test_run_research_tier2_emits_keyword_filter_and_evidence_review_nodes(
    monkeypatch: pytest.MonkeyPatch,
):
    def _fake_pipeline_run(self, query: str, **kwargs) -> RagResult:  # pragma: no cover - helper
        return RagResult(
            query=query,
            retrieved_ids=["doc-1", "doc-2"],
            answer="Nội dung tạm thời.",
            model_used="deepseek-v3.2",
            retrieved_context=[
                {
                    "id": "doc-1",
                    "source": "pubmed",
                    "title": "Warfarin Interaction",
                    "text": "Relevant context.",
                    "url": "https://pubmed.ncbi.nlm.nih.gov/1/",
                    "score": 0.87,
                },
                {
                    "id": "doc-2",
                    "source": "openfda",
                    "title": "Warfarin label",
                    "text": "FDA label context.",
                    "url": "https://open.fda.gov/apis/drug/label/",
                    "score": 0.82,
                },
            ],
            context_debug={
                "relevance": 0.72,
                "low_context_threshold": 0.2,
                "retrieval_trace": {
                    "source_attempts": [{"provider": "pubmed", "status": "completed", "documents": 2}],
                    "source_errors": {},
                    "index_summary": {"selected_count": 2},
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
            "research_mode": "deep",
            "strict_deepseek_required": False,
        }
    )

    flow_stages = [str(item.get("stage")) for item in result.get("flow_events", []) if isinstance(item, dict)]
    assert "keyword_filter" in flow_stages
    assert "evidence_review" in flow_stages

    telemetry = result.get("telemetry", {})
    assert isinstance(telemetry.get("keyword_filter"), dict)
    assert isinstance(telemetry.get("evidence_review"), dict)

    reasoning_steps = result.get("reasoning_steps", [])
    assert any(str(item.get("stage")) == "keyword_filter" for item in reasoning_steps if isinstance(item, dict))
    assert any(str(item.get("stage")) == "evidence_review" for item in reasoning_steps if isinstance(item, dict))


def test_rag_pipeline_honors_graphrag_enabled_override_runtime(monkeypatch):
    class _FakeRetriever:
        def __init__(self) -> None:
            self.last_trace: dict = {}

        def retrieve_internal(self, query: str, top_k: int = 3, **_kwargs) -> list[Document]:
            self.last_trace = {
                "search_phase": {
                    "query_terms": ["warfarin", "ibuprofen"],
                    "connectors_attempted": [
                        {"provider": "internal_corpus", "status": "completed", "documents": 1}
                    ],
                    "source_errors": {},
                    "total_candidates": 1,
                },
                "index_phase": {
                    "before_dedupe_count": 1,
                    "after_dedupe_count": 1,
                    "selected_count": 1,
                    "duration_ms": 1.0,
                },
                "search_plan": {
                    "query": query,
                    "query_terms": ["warfarin", "ibuprofen"],
                    "top_k": top_k,
                    "phase": "internal",
                    "total_candidates": 1,
                },
                "source_attempts": [
                    {"provider": "internal_corpus", "status": "completed", "documents": 1}
                ],
                "source_errors": {},
                "index_summary": {
                    "before_dedupe_count": 1,
                    "after_dedupe_count": 1,
                    "selected_count": 1,
                    "duration_ms": 1.0,
                },
                "crawl_summary": {},
            }
            return [
                Document(
                    id="internal-1",
                    text="warfarin ibuprofen interaction warning",
                    metadata={"source": "internal", "url": "https://internal.example/1", "score": 0.9},
                )
            ]

        def retrieve(self, *args, **kwargs) -> list[Document]:  # pragma: no cover - defensive
            raise AssertionError("Hybrid retrieve should not be called in this test.")

    class _FakeGraphSidecar:
        def __init__(self) -> None:
            self.expand_calls = 0

        def expand(self, query: str, documents: list[Document], max_neighbors: int, expansion_docs: int):
            self.expand_calls += 1
            return SimpleNamespace(
                summary={
                    "enabled": True,
                    "node_count": 2,
                    "edge_count": 1,
                    "expansion_count": 1,
                    "max_neighbors": max_neighbors,
                    "expansion_doc_budget": expansion_docs,
                },
                expansion_docs=[
                    Document(
                        id="graph-1",
                        text="Graph-sidecar linked evidence",
                        metadata={"source": "graphrag", "url": "https://graph.example/1", "score": 0.7},
                    )
                ],
            )

    monkeypatch.setattr(tier2.settings, "rag_graphrag_enabled", False)
    pipeline = RagPipelineP1(retriever=_FakeRetriever(), llm_client=None, deepseek_api_key="")
    fake_sidecar = _FakeGraphSidecar()
    pipeline._graphrag = fake_sidecar

    result = pipeline.run(
        "warfarin ibuprofen interaction",
        generation_enabled=False,
        planner_hints={"graphrag_enabled_override": True},
    )

    retrieval_trace = result.trace["retrieval"]
    assert fake_sidecar.expand_calls == 1
    assert retrieval_trace["graphrag_enabled"] is True
    assert retrieval_trace["graphrag_expansion_count"] == 1
    assert retrieval_trace["stack_coverage"]["graph_used"] is True
    assert retrieval_trace["stack_coverage"]["graph_expansion_count"] == 1
    assert any(
        event.get("stage") == "graphrag_sidecar" and event.get("status") == "completed"
        for event in result.flow_events
    )


def test_rag_pipeline_full_stack_does_not_override_disabled_runtime_toggles(monkeypatch):
    class _FakeRetriever:
        def __init__(self) -> None:
            self.last_trace: dict = {}

        def retrieve_internal(self, query: str, top_k: int = 3, **_kwargs) -> list[Document]:
            self.last_trace = {
                "search_phase": {
                    "query_terms": ["warfarin", "ibuprofen"],
                    "connectors_attempted": [
                        {"provider": "internal_corpus", "status": "completed", "documents": 1}
                    ],
                    "source_errors": {},
                    "total_candidates": 1,
                },
                "index_phase": {
                    "before_dedupe_count": 1,
                    "after_dedupe_count": 1,
                    "selected_count": 1,
                    "duration_ms": 1.0,
                },
                "source_attempts": [
                    {"provider": "internal_corpus", "status": "completed", "documents": 1}
                ],
                "source_errors": {},
                "index_summary": {"selected_count": 1},
            }
            return [
                Document(
                    id="internal-1",
                    text="warfarin ibuprofen interaction warning",
                    metadata={"source": "internal", "url": "https://internal.example/1", "score": 0.9},
                )
            ]

        def retrieve(self, *args, **kwargs) -> list[Document]:  # pragma: no cover - defensive
            raise AssertionError("Hybrid retrieve should not be called in this test.")

    class _FakeGraphSidecar:
        def __init__(self) -> None:
            self.expand_calls = 0

        def expand(self, query: str, documents: list[Document], max_neighbors: int, expansion_docs: int):
            self.expand_calls += 1
            return SimpleNamespace(summary={"enabled": True}, expansion_docs=[])

    monkeypatch.setattr(tier2.settings, "rag_external_connectors_enabled", False)
    monkeypatch.setattr(tier2.settings, "rag_graphrag_enabled", False)
    pipeline = RagPipelineP1(retriever=_FakeRetriever(), llm_client=None, deepseek_api_key="")
    fake_sidecar = _FakeGraphSidecar()
    pipeline._graphrag = fake_sidecar

    result = pipeline.run(
        "warfarin ibuprofen interaction",
        generation_enabled=False,
        planner_hints={"retrieval_stack_mode": "full"},
    )

    retrieval_trace = result.trace["retrieval"]
    assert retrieval_trace["stack_mode_requested"] == "full"
    assert retrieval_trace["graphrag_enabled"] is False
    assert retrieval_trace["stack_coverage"]["scientific_used"] is False
    assert retrieval_trace["stack_coverage"]["web_used"] is False
    assert retrieval_trace["stack_coverage"]["graph_used"] is False
    assert fake_sidecar.expand_calls == 0


def test_rag_pipeline_full_stack_mode_degrades_when_web_provider_missing(monkeypatch):
    class _FakeRetriever:
        def __init__(self) -> None:
            self.last_trace: dict = {}

        def retrieve_internal(self, query: str, top_k: int = 3, **_kwargs) -> list[Document]:
            self.last_trace = {
                "search_phase": {
                    "query_terms": ["warfarin", "ibuprofen"],
                    "connectors_attempted": [
                        {"provider": "internal_corpus", "status": "completed", "documents": 1}
                    ],
                    "source_errors": {},
                    "total_candidates": 1,
                },
                "index_phase": {
                    "before_dedupe_count": 1,
                    "after_dedupe_count": 1,
                    "selected_count": 1,
                    "duration_ms": 1.0,
                },
            }
            return [
                Document(
                    id="internal-1",
                    text="internal evidence",
                    metadata={"source": "internal", "url": "https://internal.example/1", "score": 0.9},
                )
            ]

        def retrieve(self, query: str, top_k: int = 3, **_kwargs) -> list[Document]:
            self.last_trace = {
                "search_phase": {
                    "query_terms": ["warfarin", "ibuprofen", "interaction"],
                    "connectors_attempted": [
                        {"provider": "pubmed", "status": "completed", "documents": 1}
                    ],
                    "source_errors": {},
                    "total_candidates": 1,
                },
                "index_phase": {
                    "before_dedupe_count": 1,
                    "after_dedupe_count": 1,
                    "selected_count": 1,
                    "duration_ms": 1.0,
                },
            }
            return [
                Document(
                    id="pubmed-1",
                    text="scientific evidence",
                    metadata={"source": "pubmed", "url": "https://pubmed.ncbi.nlm.nih.gov/123/", "score": 0.88},
                )
            ]

    class _FakeGraphSidecar:
        def expand(self, query: str, documents: list[Document], max_neighbors: int, expansion_docs: int):
            return SimpleNamespace(
                summary={
                    "enabled": True,
                    "node_count": 2,
                    "edge_count": 1,
                    "expansion_count": 0,
                    "max_neighbors": max_neighbors,
                    "expansion_doc_budget": expansion_docs,
                },
                expansion_docs=[],
            )

    pipeline = RagPipelineP1(retriever=_FakeRetriever(), llm_client=None, deepseek_api_key="")
    pipeline._graphrag = _FakeGraphSidecar()
    monkeypatch.setattr(pipeline, "_context_relevance", lambda _query, _docs: 0.0)

    result = pipeline.run(
        "warfarin ibuprofen interaction",
        generation_enabled=False,
        planner_hints={"retrieval_stack_mode": "full", "graphrag_enabled_override": True},
    )

    retrieval_trace = result.trace["retrieval"]
    assert retrieval_trace["stack_mode_requested"] == "full"
    assert retrieval_trace["stack_mode_effective"] == "auto"
    assert retrieval_trace["stack_coverage"]["vector_internal_used"] is True
    assert retrieval_trace["stack_coverage"]["scientific_used"] is True
    assert retrieval_trace["stack_coverage"]["web_used"] is False
    assert retrieval_trace["stack_coverage"]["graph_used"] is True
    assert "stack_mode_effective_auto_missing_stack" in retrieval_trace["stack_mode_reason_codes"]
    assert "stack_mode_missing_web" in retrieval_trace["stack_mode_reason_codes"]


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
    provider_queries = query_plan.get("provider_queries")
    assert isinstance(provider_queries, dict)
    scientific_provider_queries = provider_queries.get("scientific")
    assert isinstance(scientific_provider_queries, dict)
    assert "pubmed" in scientific_provider_queries
    web_provider_queries = provider_queries.get("web")
    assert isinstance(web_provider_queries, dict)
    assert "searxng" in web_provider_queries


def test_run_research_tier2_llm_query_planner_success_path(monkeypatch):
    class _FakePlannerClient:
        def generate(self, prompt: str, system_prompt: str | None = None) -> SimpleNamespace:
            return SimpleNamespace(
                content=(
                    "```json\n"
                    "{\n"
                    '  "canonical_query": "warfarin interaction with ibuprofen bleeding risk guidance",\n'
                    '  "language_hint": "mixed",\n'
                    '  "keywords": ["warfarin", "ibuprofen", "interaction", "bleeding", "guideline"],\n'
                    '  "source_queries": {\n'
                    '    "internal": ["warfarin ibuprofen warning"],\n'
                    '    "scientific": ["warfarin ibuprofen clinical evidence"],\n'
                    '    "web": ["warfarin ibuprofen guideline warning"]\n'
                    "  },\n"
                    '  "decomposition": {\n'
                    '    "deep_pass_queries": ["warfarin ibuprofen systematic review"],\n'
                    '    "deep_beta_pass_queries": ["warfarin ibuprofen subgroup bleeding evidence"]\n'
                    "  }\n"
                    "}\n"
                    "```"
                ),
                model="deepseek-v3.2",
            )

    def _fake_pipeline_run(self, query: str, **kwargs) -> RagResult:  # pragma: no cover - helper
        planner_hints = kwargs.get("planner_hints", {})
        if not isinstance(planner_hints, dict):
            planner_hints = {}
        query_plan = planner_hints.get("query_plan", {}) if isinstance(planner_hints, dict) else {}
        generation_enabled = bool(kwargs.get("generation_enabled", True))
        return RagResult(
            query=query,
            retrieved_ids=["doc-llm-plan-1"],
            answer="Tổng hợp bằng chứng về tương tác warfarin và ibuprofen.",
            model_used="deepseek-v3.2",
            retrieved_context=[
                {
                    "id": "doc-llm-plan-1",
                    "source": "pubmed",
                    "title": "Evidence summary",
                    "text": "Evidence text",
                    "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
                    "score": 0.89,
                }
            ],
            context_debug={
                "relevance": 0.89,
                "low_context_threshold": 0.15,
                "source_counts": {"pubmed": 1},
                "retrieval_trace": {
                    "source_attempts": [
                        {"provider": "pubmed", "status": "completed", "documents": 1}
                    ],
                    "index_summary": {"selected_count": 1, "retrieved_count": 1},
                    "crawl_summary": {"domains": []},
                    "query_plan": query_plan,
                },
            },
            flow_events=[],
            trace={
                "retrieval": {
                    "source_attempts": [{"provider": "pubmed", "status": "completed"}],
                    "index_summary": {"selected_count": 1, "retrieved_count": 1},
                    "crawl_summary": {"domains": []},
                    "hybrid": {"source_errors": {}},
                },
                "generation": {"mode": "llm"} if generation_enabled else {"mode": "retrieval_only"},
            },
        )

    def _fake_factcheck(answer: str, retrieved_context: list[dict]) -> SimpleNamespace:
        return SimpleNamespace(
            stage="fides_lite",
            verdict="pass",
            severity="low",
            confidence=0.95,
            supported_claims=1,
            total_claims=1,
            unsupported_claims=[],
            evidence_count=max(len(retrieved_context), 1),
            note="OK",
            verification_matrix=[],
            contradiction_summary={
                "version": "claim-v1",
                "has_contradiction": False,
                "contradiction_count": 0,
                "claims": [],
                "details": [],
                "note": "No contradiction detected.",
            },
        )

    monkeypatch.setattr(tier2.settings, "deepseek_api_key", "test-key")
    monkeypatch.setattr(tier2, "_build_query_planner_client", lambda: _FakePlannerClient())
    monkeypatch.setattr(tier2.RagPipelineP1, "run", _fake_pipeline_run)
    monkeypatch.setattr(tier2, "run_fides_lite", _fake_factcheck)

    result = tier2.run_research_tier2(
        {
            "query": "Tương tác warfarin với ibuprofen",
            "research_mode": "fast",
            "strict_deepseek_required": False,
        }
    )

    assert "llm_query_planner_enabled" in result["metadata"]["planner_trace"]["planner_hints"][
        "reason_codes"
    ]
    assert result["query_plan"]["canonical_query"].startswith("warfarin interaction")
    assert len(result["query_plan"]["source_queries"]["internal"]) >= 1
    llm_events = [event for event in result["flow_events"] if event.get("stage") == "llm_query_planner"]
    assert any(event.get("status") == "completed" for event in llm_events)


def test_run_research_tier2_fast_mode_full_stack_request_downgrades_to_auto(monkeypatch):
    captured_calls: list[dict] = []

    def _fake_pipeline_run(self, query: str, **kwargs) -> RagResult:  # pragma: no cover - helper
        planner_hints = kwargs.get("planner_hints", {})
        if not isinstance(planner_hints, dict):
            planner_hints = {}
        captured_calls.append({"query": query, **kwargs})
        stack_mode = str(planner_hints.get("retrieval_stack_mode") or "auto")
        stack_coverage = {
            "vector_internal_used": True,
            "graph_used": True,
            "graph_expansion_count": 1,
            "scientific_used": True,
            "web_used": True,
        }
        retrieval_trace = {
            "source_attempts": [
                {"provider": "internal_corpus", "status": "completed", "documents": 1},
                {"provider": "pubmed", "status": "completed", "documents": 1},
                {"provider": "searxng", "status": "completed", "documents": 1},
            ],
            "source_errors": {},
            "index_summary": {"selected_count": 4, "retrieved_count": 4},
            "crawl_summary": {"domains": ["example.org"]},
            "query_plan": planner_hints.get("query_plan", {}),
            "graphrag_enabled": True,
            "graphrag_expansion_count": 1,
            "graphrag_node_count": 2,
            "graphrag_edge_count": 1,
            "stack_mode_requested": stack_mode,
            "stack_mode_effective": "full" if stack_mode == "full" else "auto",
            "stack_coverage": stack_coverage,
        }
        return RagResult(
            query=query,
            retrieved_ids=["internal-1", "pubmed-1", "searxng-1", "graph-1"],
            answer="Tổng hợp bằng chứng đầy đủ từ nhiều lớp retrieval.",
            model_used="deepseek-v3.2",
            retrieved_context=[
                {
                    "id": "internal-1",
                    "source": "internal",
                    "title": "Internal policy note",
                    "text": "Internal context.",
                    "url": "https://internal.example/1",
                    "score": 0.8,
                },
                {
                    "id": "pubmed-1",
                    "source": "pubmed",
                    "title": "PubMed evidence",
                    "text": "Scientific context.",
                    "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
                    "score": 0.9,
                },
                {
                    "id": "searxng-1",
                    "source": "searxng",
                    "title": "Web evidence",
                    "text": "Web context.",
                    "url": "https://example.org/web-evidence",
                    "score": 0.7,
                },
                {
                    "id": "graph-1",
                    "source": "graphrag",
                    "title": "Graph expansion",
                    "text": "Graph sidecar evidence.",
                    "url": "https://example.org/graph-evidence",
                    "score": 0.75,
                },
            ],
            context_debug={
                "relevance": 0.91,
                "low_context_threshold": kwargs.get("low_context_threshold", 0.15),
                "source_counts": {"internal": 1, "pubmed": 1, "searxng": 1, "graphrag": 1},
                "retrieval_trace": retrieval_trace,
            },
            flow_events=[
                {
                    "stage": "external_scientific_retrieval",
                    "timestamp": tier2._now_iso(),
                    "status": "completed",
                    "source_count": 2,
                    "note": "External scientific retrieval completed.",
                    "payload": {"provider": "pubmed"},
                },
                {
                    "stage": "graphrag_sidecar",
                    "timestamp": tier2._now_iso(),
                    "status": "completed",
                    "source_count": 1,
                    "note": "Graph sidecar completed.",
                    "payload": {"expansion_count": 1},
                },
            ],
            trace={
                "retrieval": retrieval_trace,
                "generation": {"mode": "llm"},
            },
        )

    def _fake_factcheck(answer: str, retrieved_context: list[dict]) -> SimpleNamespace:
        return SimpleNamespace(
            stage="fides_lite",
            verdict="pass",
            severity="low",
            confidence=0.95,
            supported_claims=1,
            total_claims=1,
            unsupported_claims=[],
            evidence_count=max(len(retrieved_context), 1),
            note="OK",
            verification_matrix=[],
            contradiction_summary={
                "version": "claim-v1",
                "has_contradiction": False,
                "contradiction_count": 0,
                "claims": [],
                "details": [],
                "note": "No contradiction detected.",
            },
        )

    monkeypatch.setattr(tier2.RagPipelineP1, "run", _fake_pipeline_run)
    monkeypatch.setattr(tier2, "run_fides_lite", _fake_factcheck)

    result = tier2.run_research_tier2(
        {
            "query": "Compare warfarin and ibuprofen evidence.",
            "research_mode": "fast",
            "retrieval_stack_mode": "full",
            "strict_deepseek_required": False,
        }
    )

    assert len(captured_calls) == 1
    call = captured_calls[0]
    assert call["scientific_retrieval_enabled"] is False
    assert call["web_retrieval_enabled"] is False
    assert call["planner_hints"]["retrieval_stack_mode"] == "auto"
    assert call["planner_hints"]["graphrag_enabled_override"] is None

    assert "stack_mode_full_downgraded_for_fast_mode" in result["metadata"]["planner_trace"]["planner_hints"][
        "reason_codes"
    ]
    assert result["telemetry"]["stack_mode"]["requested"] == "auto"
    assert result["telemetry"]["stack_mode"]["effective"] == "auto"
    assert result["telemetry"]["stack_coverage"]["vector_internal_used"] is True
    assert result["telemetry"]["stack_coverage"]["scientific_used"] is True
    assert result["telemetry"]["stack_coverage"]["web_used"] is True
    assert result["telemetry"]["stack_coverage"]["graph_used"] is True
    assert result["telemetry"]["stack_coverage"]["graph_expansion_count"] == 1
    assert any(
        event.get("stage") == "external_scientific_retrieval"
        and event.get("status") == "completed"
        for event in result.get("flow_events", [])
    )
    assert any(
        event.get("stage") == "graphrag_sidecar" and event.get("status") == "completed"
        for event in result.get("flow_events", [])
    )


def test_run_research_tier2_full_stack_mode_degrades_to_auto_when_stack_missing(monkeypatch):
    def _fake_pipeline_run(self, query: str, **kwargs) -> RagResult:  # pragma: no cover - helper
        planner_hints = kwargs.get("planner_hints", {})
        if not isinstance(planner_hints, dict):
            planner_hints = {}
        retrieval_trace = {
            "source_attempts": [
                {"provider": "internal_corpus", "status": "completed", "documents": 1},
                {"provider": "pubmed", "status": "completed", "documents": 1},
            ],
            "source_errors": {},
            "index_summary": {"selected_count": 2, "retrieved_count": 2},
            "crawl_summary": {"domains": []},
            "query_plan": planner_hints.get("query_plan", {}),
            "graphrag_enabled": True,
            "graphrag_expansion_count": 1,
            "graphrag_node_count": 2,
            "graphrag_edge_count": 1,
            "stack_mode_requested": "full",
            # Simulate inconsistent upstream trace; agent telemetry must harden this.
            "stack_mode_effective": "full",
            "stack_mode_reason_codes": ["stack_mode_effective_full"],
            "stack_coverage": {
                "vector_internal_used": True,
                "graph_used": True,
                "graph_expansion_count": 1,
                "scientific_used": True,
                "web_used": False,
            },
        }
        return RagResult(
            query=query,
            retrieved_ids=["internal-1", "pubmed-1"],
            answer="Thiếu lớp web retrieval nên full stack không đạt.",
            model_used="deepseek-v3.2",
            retrieved_context=[
                {
                    "id": "internal-1",
                    "source": "internal",
                    "title": "Internal context",
                    "text": "Internal evidence.",
                    "url": "https://internal.example/1",
                    "score": 0.82,
                },
                {
                    "id": "pubmed-1",
                    "source": "pubmed",
                    "title": "Scientific context",
                    "text": "Scientific evidence.",
                    "url": "https://pubmed.ncbi.nlm.nih.gov/87654321/",
                    "score": 0.88,
                },
            ],
            context_debug={
                "relevance": 0.9,
                "low_context_threshold": kwargs.get("low_context_threshold", 0.15),
                "source_counts": {"internal": 1, "pubmed": 1},
                "retrieval_trace": retrieval_trace,
            },
            flow_events=[],
            trace={
                "retrieval": retrieval_trace,
                "generation": {"mode": "llm"},
            },
        )

    def _fake_factcheck(answer: str, retrieved_context: list[dict]) -> SimpleNamespace:
        return SimpleNamespace(
            stage="fides_lite",
            verdict="pass",
            severity="low",
            confidence=0.95,
            supported_claims=1,
            total_claims=1,
            unsupported_claims=[],
            evidence_count=max(len(retrieved_context), 1),
            note="OK",
            verification_matrix=[],
            contradiction_summary={
                "version": "claim-v1",
                "has_contradiction": False,
                "contradiction_count": 0,
                "claims": [],
                "details": [],
                "note": "No contradiction detected.",
            },
        )

    monkeypatch.setattr(tier2.RagPipelineP1, "run", _fake_pipeline_run)
    monkeypatch.setattr(tier2, "run_fides_lite", _fake_factcheck)

    result = tier2.run_research_tier2(
        {
            "query": "Compare warfarin and ibuprofen evidence.",
            "research_mode": "deep",
            "retrieval_stack_mode": "full",
            "strict_deepseek_required": False,
        }
    )

    assert result["telemetry"]["stack_mode"]["requested"] == "full"
    assert result["telemetry"]["stack_mode"]["effective"] == "auto"
    reason_codes = result["telemetry"]["stack_mode"]["reason_codes"]
    assert "stack_mode_effective_auto_missing_stack" in reason_codes
    assert "stack_mode_missing_web" in reason_codes
    assert "stack_mode_effective_adjusted_from_retrieval_trace" in reason_codes
    assert result["telemetry"]["stack_coverage"]["vector_internal_used"] is True
    assert result["telemetry"]["stack_coverage"]["scientific_used"] is True
    assert result["telemetry"]["stack_coverage"]["graph_used"] is True
    assert result["telemetry"]["stack_coverage"]["web_used"] is False


def test_run_research_tier2_llm_query_planner_fallback_path(monkeypatch):
    class _BadPlannerClient:
        def generate(self, prompt: str, system_prompt: str | None = None) -> SimpleNamespace:
            return SimpleNamespace(
                content='{"canonical_query":"UNEXPECTED_CANONICAL_ONLY"}',
                model="deepseek-v3.2",
            )

    def _fake_pipeline_run(self, query: str, **kwargs) -> RagResult:  # pragma: no cover - helper
        planner_hints = kwargs.get("planner_hints", {})
        query_plan = planner_hints.get("query_plan", {}) if isinstance(planner_hints, dict) else {}
        return RagResult(
            query=query,
            retrieved_ids=["doc-fallback-1"],
            answer="Nội dung tổng hợp.",
            model_used="deepseek-v3.2",
            retrieved_context=[
                {
                    "id": "doc-fallback-1",
                    "source": "pubmed",
                    "title": "Fallback evidence",
                    "text": "Fallback evidence text.",
                    "url": "https://pubmed.ncbi.nlm.nih.gov/10000001/",
                    "score": 0.8,
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
                    "index_summary": {"selected_count": 1, "retrieved_count": 1},
                    "crawl_summary": {"domains": []},
                    "query_plan": query_plan,
                },
            },
            flow_events=[],
            trace={
                "retrieval": {
                    "source_attempts": [{"provider": "pubmed", "status": "completed"}],
                    "index_summary": {"selected_count": 1, "retrieved_count": 1},
                    "crawl_summary": {"domains": []},
                    "hybrid": {"source_errors": {}},
                },
                "generation": {"mode": "llm"},
            },
        )

    def _fake_factcheck(answer: str, retrieved_context: list[dict]) -> SimpleNamespace:
        return SimpleNamespace(
            stage="fides_lite",
            verdict="pass",
            severity="low",
            confidence=0.9,
            supported_claims=1,
            total_claims=1,
            unsupported_claims=[],
            evidence_count=max(len(retrieved_context), 1),
            note="OK",
            verification_matrix=[],
            contradiction_summary={
                "version": "claim-v1",
                "has_contradiction": False,
                "contradiction_count": 0,
                "claims": [],
                "details": [],
                "note": "No contradiction detected.",
            },
        )

    topic = "Tương tác warfarin với ibuprofen"
    expected_base = tier2._build_source_aware_query_plan(
        topic=topic,
        research_mode="fast",
        keywords=tier2.query_terms(topic),
    )

    monkeypatch.setattr(tier2.settings, "deepseek_api_key", "test-key")
    monkeypatch.setattr(tier2, "_build_query_planner_client", lambda: _BadPlannerClient())
    monkeypatch.setattr(tier2.RagPipelineP1, "run", _fake_pipeline_run)
    monkeypatch.setattr(tier2, "run_fides_lite", _fake_factcheck)

    result = tier2.run_research_tier2(
        {
            "query": topic,
            "research_mode": "fast",
            "strict_deepseek_required": False,
        }
    )

    assert "llm_query_planner_fallback" in result["metadata"]["planner_trace"]["planner_hints"][
        "reason_codes"
    ]
    assert "llm_query_planner_enabled" not in result["metadata"]["planner_trace"]["planner_hints"][
        "reason_codes"
    ]
    assert result["query_plan"]["canonical_query"] == expected_base["canonical_query"]
    llm_events = [event for event in result["flow_events"] if event.get("stage") == "llm_query_planner"]
    assert any(event.get("status") == "degraded" for event in llm_events)


def test_run_research_tier2_includes_chart_specs_visual_assets_and_reasoning_digest(monkeypatch):
    def _fake_pipeline_run(self, query: str, **kwargs) -> RagResult:  # pragma: no cover - helper
        planner_hints = kwargs.get("planner_hints", {})
        if not isinstance(planner_hints, dict):
            planner_hints = {}
        generation_enabled = bool(kwargs.get("generation_enabled", True))
        return RagResult(
            query=query,
            retrieved_ids=["doc-visual-1"],
            answer="Kết quả tổng hợp bằng chứng cần theo dõi chảy máu.",
            model_used="deepseek-v3.2",
            retrieved_context=[
                {
                    "id": "doc-visual-1",
                    "source": "pubmed",
                    "title": "Bleeding risk evidence",
                    "text": "Evidence details for table and chart.",
                    "url": "https://pubmed.ncbi.nlm.nih.gov/11111111/",
                    "score": 0.84,
                }
            ],
            context_debug={
                "relevance": 0.84,
                "low_context_threshold": kwargs.get("low_context_threshold", 0.12),
                "source_counts": {"pubmed": 1},
                "retrieval_trace": {
                    "source_attempts": [
                        {"provider": "pubmed", "status": "completed", "documents": 1}
                    ],
                    "index_summary": {"selected_count": 1, "retrieved_count": 1},
                    "crawl_summary": {"domains": []},
                    "query_plan": planner_hints.get("query_plan", {}),
                },
            },
            flow_events=[],
            trace={
                "retrieval": {
                    "source_attempts": [{"provider": "pubmed", "status": "completed"}],
                    "index_summary": {"selected_count": 1, "retrieved_count": 1},
                    "crawl_summary": {"domains": []},
                    "hybrid": {"source_errors": {}},
                },
                "generation": {"mode": "llm"} if generation_enabled else {"mode": "retrieval_only"},
            },
        )

    def _fake_factcheck(answer: str, retrieved_context: list[dict]) -> SimpleNamespace:
        return SimpleNamespace(
            stage="fides_lite",
            verdict="pass",
            severity="low",
            confidence=0.9,
            supported_claims=2,
            total_claims=2,
            unsupported_claims=[],
            evidence_count=max(len(retrieved_context), 1),
            note="OK",
            verification_matrix=[
                {
                    "claim": "Tăng nguy cơ chảy máu",
                    "support_status": "supported",
                    "overlap_score": 0.88,
                    "confidence": 0.87,
                    "evidence_ref": "pubmed",
                    "evidence_snippet": "Evidence details",
                }
            ],
            contradiction_summary={
                "version": "claim-v1",
                "has_contradiction": False,
                "contradiction_count": 0,
                "claims": [],
                "details": [],
                "note": "No contradiction detected.",
            },
        )

    monkeypatch.setattr(tier2.RagPipelineP1, "run", _fake_pipeline_run)
    monkeypatch.setattr(tier2, "run_fides_lite", _fake_factcheck)

    result = tier2.run_research_tier2(
        {
            "query": "Compare warfarin and ibuprofen bleeding risk evidence",
            "research_mode": "deep_beta",
            "deep_pass_count": 2,
            "strict_deepseek_required": False,
        }
    )

    assert isinstance(result.get("chart_specs"), list)
    assert len(result["chart_specs"]) >= 1
    assert all(item.get("type") == "chart-spec" for item in result["chart_specs"])
    assert isinstance(result.get("visual_assets"), list)
    assert len(result["visual_assets"]) >= 1
    assert isinstance(result.get("reasoning_digest"), dict)
    assert isinstance(result["reasoning_digest"].get("highlights"), list)
    assert result["render_hints"]["markdown"] is True
    assert result["render_hints"]["tables"] is True
    assert result["render_hints"]["mermaid"] is False
    assert "## Điểm chính" in result["answer_markdown"]
    assert "## Ứng dụng thực tế" in result["answer_markdown"]
    assert "## Lưu ý an toàn" in result["answer_markdown"]
    assert "## Tóm tắt điều hành" not in result["answer_markdown"]
    assert "## Bảng tổng hợp bằng chứng" not in result["answer_markdown"]


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
    assert verification_matrix.get("version") == "claim-v2-nli"
    assert isinstance(verification_matrix.get("rows"), list)
    assert isinstance(verification_matrix.get("summary"), dict)
    assert isinstance(verification_matrix.get("contradiction_summary"), dict)
    if verification_matrix.get("rows"):
        first_row = verification_matrix["rows"][0]
        assert "claim_type" in first_row
        assert first_row.get("support_status") in {"supported", "contradicted", "insufficient"}
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


def test_run_research_tier2_applies_safety_override_warn_for_insufficient(monkeypatch):
    def _fake_pipeline_run(self, query: str, **kwargs) -> RagResult:  # pragma: no cover - helper
        return RagResult(
            query=query,
            retrieved_ids=["doc-safe-1"],
            answer="Khuyen nghi an toan.",
            model_used="deepseek-v3.2",
            retrieved_context=[
                {
                    "id": "doc-safe-1",
                    "source": "pubmed",
                    "title": "Safety note",
                    "text": "Can can nhac can than trong mot so tinh huong.",
                    "url": "https://pubmed.ncbi.nlm.nih.gov/10000009/",
                    "score": 0.8,
                }
            ],
            context_debug={"relevance": 0.6, "retrieval_trace": {"index_summary": {"selected_count": 1}}},
            flow_events=[],
            trace={"retrieval": {"source_attempts": [{"provider": "pubmed"}]}},
        )

    def _fake_factcheck(answer: str, retrieved_context: list[dict]):  # noqa: ARG001
        return SimpleNamespace(
            enabled=True,
            stage="fides-lite-v1.2",
            verdict="pass",
            confidence=0.83,
            supported_claims=1,
            total_claims=1,
            unsupported_claims=[],
            evidence_count=max(len(retrieved_context), 1),
            severity="low",
            note="OK",
            verification_matrix=[
                {
                    "claim": "Nen dung 2 vien moi lan.",
                    "claim_type": "dosage",
                    "support_status": "insufficient",
                    "confidence": 0.22,
                    "overlap_score": 0.11,
                    "evidence_ref": None,
                    "evidence_snippet": "",
                    "rationale": "Thieu evidence cho dosage claim",
                }
            ],
            contradiction_summary={"version": "claim-v2-nli", "has_contradiction": False, "contradiction_count": 0},
        )

    monkeypatch.setattr(tier2.RagPipelineP1, "run", _fake_pipeline_run)
    monkeypatch.setattr(tier2, "run_fides_lite", _fake_factcheck)

    result = tier2.run_research_tier2(
        {
            "query": "Huong dan lieu dung warfarin",
            "research_mode": "fast",
            "strict_deepseek_required": False,
        }
    )

    assert result.get("policy_action") == "warn"
    matrix = result.get("verification_matrix", {})
    assert isinstance(matrix, dict)
    override = matrix.get("safety_override", {})
    assert isinstance(override, dict)
    assert override.get("applied") is True
    assert override.get("reason") == "safety_critical_insufficient"
    assert any(
        event.get("stage") == "safety_override" and event.get("status") == "warning"
        for event in result.get("flow_events", [])
    )


def test_run_research_tier2_applies_safety_override_block_for_contradicted(monkeypatch):
    def _fake_pipeline_run(self, query: str, **kwargs) -> RagResult:  # pragma: no cover - helper
        return RagResult(
            query=query,
            retrieved_ids=["doc-safe-2"],
            answer="Khuyen nghi an toan.",
            model_used="deepseek-v3.2",
            retrieved_context=[
                {
                    "id": "doc-safe-2",
                    "source": "pubmed",
                    "title": "Contraindication note",
                    "text": "Chong chi dinh su dung chung trong truong hop nay.",
                    "url": "https://pubmed.ncbi.nlm.nih.gov/10000010/",
                    "score": 0.82,
                }
            ],
            context_debug={"relevance": 0.66, "retrieval_trace": {"index_summary": {"selected_count": 1}}},
            flow_events=[],
            trace={"retrieval": {"source_attempts": [{"provider": "pubmed"}]}},
        )

    def _fake_factcheck(answer: str, retrieved_context: list[dict]):  # noqa: ARG001
        return SimpleNamespace(
            enabled=True,
            stage="fides-lite-v1.2",
            verdict="pass",
            confidence=0.84,
            supported_claims=1,
            total_claims=1,
            unsupported_claims=[],
            evidence_count=max(len(retrieved_context), 1),
            severity="low",
            note="OK",
            verification_matrix=[
                {
                    "claim": "Khong co chong chi dinh voi benh nen nay.",
                    "claim_type": "contraindication",
                    "support_status": "contradicted",
                    "confidence": 0.72,
                    "overlap_score": 0.41,
                    "evidence_ref": "doc-safe-2",
                    "evidence_snippet": "Chong chi dinh su dung chung",
                    "rationale": "Claim mâu thuẫn với evidence",
                }
            ],
            contradiction_summary={"version": "claim-v2-nli", "has_contradiction": True, "contradiction_count": 1},
        )

    monkeypatch.setattr(tier2.RagPipelineP1, "run", _fake_pipeline_run)
    monkeypatch.setattr(tier2, "run_fides_lite", _fake_factcheck)

    result = tier2.run_research_tier2(
        {
            "query": "Chong chi dinh warfarin voi benh nen",
            "research_mode": "fast",
            "strict_deepseek_required": False,
        }
    )

    assert result.get("policy_action") == "block"
    matrix = result.get("verification_matrix", {})
    assert isinstance(matrix, dict)
    override = matrix.get("safety_override", {})
    assert isinstance(override, dict)
    assert override.get("applied") is True
    assert override.get("reason") == "safety_critical_contradicted"
    assert any(
        event.get("stage") == "safety_override" and event.get("status") == "blocked"
        for event in result.get("flow_events", [])
    )


def test_normalize_research_mode_supports_deep_beta_aliases():
    assert tier2._normalize_research_mode({"research_mode": "deep_beta"}) == "deep_beta"
    assert tier2._normalize_research_mode({"research_mode": "deep-beta"}) == "deep_beta"
    assert tier2._normalize_research_mode({"research_mode": "deep"}) == "deep"
    assert tier2._normalize_research_mode({"research_mode": "fast"}) == "fast"


def test_build_plan_steps_deep_beta_is_longer_than_deep():
    deep_steps = tier2._build_plan_steps(
        "warfarin ibuprofen bleeding risk",
        None,
        research_mode="deep",
    )
    beta_steps = tier2._build_plan_steps(
        "warfarin ibuprofen bleeding risk",
        None,
        research_mode="deep_beta",
    )

    assert len(beta_steps) > len(deep_steps)
    assert any(step.step == "retrieval_budgeting" for step in beta_steps)
    assert any(step.step == "reasoning_chain_audit" for step in beta_steps)


def test_run_research_tier2_deep_beta_emits_beta_stages_and_metadata(monkeypatch):
    call_log: list[dict] = []

    def _fake_pipeline_run(self, query: str, **kwargs) -> RagResult:  # pragma: no cover - helper
        planner_hints = kwargs.get("planner_hints", {})
        if not isinstance(planner_hints, dict):
            planner_hints = {}
        generation_enabled = bool(kwargs.get("generation_enabled", True))
        query_focus = str(planner_hints.get("query_focus") or "")
        doc_prefix = query_focus or "final"
        call_log.append(
            {
                "query": query,
                "generation_enabled": generation_enabled,
                "query_focus": query_focus,
            }
        )
        return RagResult(
            query=query,
            retrieved_ids=[f"{doc_prefix}-doc-1"],
            answer="Tong hop bang chung beta mode.",
            model_used="deepseek-v3.2",
            retrieved_context=[
                {
                    "id": f"{doc_prefix}-doc-1",
                    "source": "pubmed",
                    "title": f"Evidence for {doc_prefix}",
                    "text": "Clinical evidence summary for retrieval pass.",
                    "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
                    "score": 0.81,
                }
            ],
            context_debug={
                "relevance": 0.81,
                "low_context_threshold": kwargs.get("low_context_threshold", 0.12),
                "source_counts": {"pubmed": 1},
                "retrieval_trace": {
                    "source_attempts": [
                        {"provider": "pubmed", "status": "completed", "documents": 1}
                    ],
                    "index_summary": {"selected_count": 1, "retrieved_count": 1},
                    "crawl_summary": {"domains": []},
                    "search_plan": {"query": query},
                    "query_plan": planner_hints.get("query_plan", {}),
                },
            },
            flow_events=[
                {
                    "stage": "index_search",
                    "timestamp": tier2._now_iso(),
                    "status": "completed",
                    "source_count": 1,
                    "note": "Index search completed.",
                    "payload": {"provider": "pubmed", "query_focus": query_focus or "final"},
                }
            ],
            trace={
                "retrieval": {
                    "source_attempts": [{"provider": "pubmed", "status": "completed"}],
                    "index_summary": {"selected_count": 1, "retrieved_count": 1},
                    "crawl_summary": {"domains": []},
                    "hybrid": {"source_errors": {}},
                },
                "generation": {"mode": "llm"} if generation_enabled else {},
            },
        )

    def _fake_factcheck(answer: str, retrieved_context: list[dict]) -> SimpleNamespace:
        return SimpleNamespace(
            stage="fides_lite",
            verdict="pass",
            severity="low",
            confidence=0.93,
            supported_claims=2,
            total_claims=2,
            unsupported_claims=[],
            evidence_count=max(len(retrieved_context), 1),
            note="Consistency checks passed.",
            verification_matrix=[
                {
                    "claim": "Main claim",
                    "support_status": "supported",
                    "overlap_score": 0.91,
                    "confidence": 0.9,
                    "evidence_ref": "pubmed",
                    "evidence_snippet": "Clinical evidence summary.",
                }
            ],
            contradiction_summary={
                "version": "claim-v1",
                "has_contradiction": False,
                "contradiction_count": 0,
                "claims": [],
                "details": [],
                "note": "No contradiction detected.",
            },
        )

    monkeypatch.setattr(tier2.RagPipelineP1, "run", _fake_pipeline_run)
    monkeypatch.setattr(tier2, "run_fides_lite", _fake_factcheck)

    result = tier2.run_research_tier2(
        {
            "query": "Compare warfarin and ibuprofen bleeding-risk evidence in older adults.",
            "research_mode": "deep_beta",
            "deep_pass_count": 4,
            "strict_deepseek_required": False,
        }
    )

    assert result["research_mode"] == "deep_beta"
    assert result["metadata"]["research_mode"] == "deep_beta"
    assert result["metadata"]["pipeline"] == "p2-research-tier2-deep-beta-v1"
    assert result["deep_pass_count"] == 4
    assert len(result["pass_summaries"]) == 4
    assert len(result["metadata"]["pass_summaries"]) == 4
    assert len(result["telemetry"]["pass_summaries"]) == 4
    assert isinstance(result["metadata"]["reasoning_steps"], list)
    assert len(result["metadata"]["reasoning_steps"]) >= 6
    assert isinstance(result["metadata"]["retrieval_budgets"], dict)
    assert result["metadata"]["retrieval_budgets"]["target_pass_count"] == 4
    assert isinstance(result["metadata"]["chain_status"], dict)
    assert result["metadata"]["chain_status"]["status"] == "completed"
    assert isinstance(result.get("trace_id"), str)
    assert isinstance(result.get("run_id"), str)
    assert result["trace_id"]
    assert result["run_id"]
    assert result["metadata"]["trace_id"] == result["trace_id"]
    assert result["metadata"]["run_id"] == result["run_id"]
    assert result["telemetry"]["trace_id"] == result["trace_id"]
    assert result["telemetry"]["run_id"] == result["run_id"]
    assert result["trace"]["trace_id"] == result["trace_id"]
    assert result["trace"]["run_id"] == result["run_id"]
    stage_spans = result["metadata"].get("stage_spans", [])
    assert isinstance(stage_spans, list)
    assert len(stage_spans) >= 1
    assert result["telemetry"].get("stage_spans") == stage_spans
    deep_beta_span = next(
        item
        for item in stage_spans
        if str(item.get("stage")) == "deep_beta_multi_pass_retrieval"
    )
    assert isinstance(deep_beta_span.get("start_at"), str)
    assert isinstance(deep_beta_span.get("end_at"), str)
    assert deep_beta_span.get("duration_ms") is not None

    flow_events = result["flow_events"]
    stages = {str(event.get("stage")) for event in flow_events}
    assert {
        "deep_beta_scope",
        "deep_beta_hypothesis_map",
        "deep_beta_retrieval_budget",
        "deep_beta_multi_pass_retrieval",
        "deep_beta_retrieval_pass",
        "deep_beta_evidence_audit",
        "deep_beta_claim_graph",
        "deep_beta_chain_synthesis",
        "deep_beta_chain_verification",
    }.issubset(stages)
    assert sum(
        1
        for event in flow_events
        if event.get("stage") == "deep_beta_retrieval_pass"
        and event.get("status") == "completed"
    ) == 4
    assert sum(1 for item in call_log if item.get("generation_enabled") is False) == 4
    evidence_audit_span = next(
        item
        for item in stage_spans
        if str(item.get("stage")) == "deep_beta_evidence_audit"
    )
    assert isinstance(evidence_audit_span.get("start_at"), str)
    assert isinstance(evidence_audit_span.get("end_at"), str)
    assert evidence_audit_span.get("event_count", 0) >= 2
    answer = str(result.get("answer", ""))
    assert "```mermaid" not in answer
    assert "```chart-spec" not in answer
    assert "## Nguồn tham chiếu" not in answer


def test_run_research_tier2_deep_mode_does_not_emit_beta_stages(monkeypatch):
    def _fake_pipeline_run(self, query: str, **kwargs) -> RagResult:  # pragma: no cover - helper
        generation_enabled = bool(kwargs.get("generation_enabled", True))
        return RagResult(
            query=query,
            retrieved_ids=["doc-deep-1"],
            answer="Tong hop deep mode.",
            model_used="deepseek-v3.2",
            retrieved_context=[
                {
                    "id": "doc-deep-1",
                    "source": "pubmed",
                    "title": "Deep evidence",
                    "text": "Evidence summary.",
                    "url": "https://pubmed.ncbi.nlm.nih.gov/10000001/",
                    "score": 0.85,
                }
            ],
            context_debug={
                "relevance": 0.85,
                "low_context_threshold": kwargs.get("low_context_threshold", 0.12),
                "source_counts": {"pubmed": 1},
                "retrieval_trace": {
                    "source_attempts": [
                        {"provider": "pubmed", "status": "completed", "documents": 1}
                    ],
                    "index_summary": {"selected_count": 1, "retrieved_count": 1},
                    "crawl_summary": {"domains": []},
                    "search_plan": {"query": query},
                },
            },
            flow_events=[],
            trace={
                "retrieval": {
                    "source_attempts": [{"provider": "pubmed", "status": "completed"}],
                    "index_summary": {"selected_count": 1, "retrieved_count": 1},
                    "crawl_summary": {"domains": []},
                    "hybrid": {"source_errors": {}},
                },
                "generation": {"mode": "llm"} if generation_enabled else {},
            },
        )

    def _fake_factcheck(answer: str, retrieved_context: list[dict]) -> SimpleNamespace:
        return SimpleNamespace(
            stage="fides_lite",
            verdict="pass",
            severity="low",
            confidence=0.9,
            supported_claims=1,
            total_claims=1,
            unsupported_claims=[],
            evidence_count=max(len(retrieved_context), 1),
            note="OK",
            verification_matrix=[],
            contradiction_summary={
                "version": "claim-v1",
                "has_contradiction": False,
                "contradiction_count": 0,
                "claims": [],
                "details": [],
                "note": "No contradiction detected.",
            },
        )

    monkeypatch.setattr(tier2.RagPipelineP1, "run", _fake_pipeline_run)
    monkeypatch.setattr(tier2, "run_fides_lite", _fake_factcheck)

    result = tier2.run_research_tier2(
        {
            "query": "Compare warfarin and ibuprofen evidence.",
            "research_mode": "deep",
            "deep_pass_count": 2,
            "strict_deepseek_required": False,
        }
    )

    assert result["research_mode"] == "deep"
    assert result["metadata"]["pipeline"] == "p2-research-tier2-deep-v1"
    assert result["metadata"]["trace_id"] == result["trace_id"] == result["telemetry"]["trace_id"]
    assert result["metadata"]["run_id"] == result["run_id"] == result["telemetry"]["run_id"]
    stage_spans = result["metadata"].get("stage_spans", [])
    assert isinstance(stage_spans, list)
    deep_span = next(item for item in stage_spans if str(item.get("stage")) == "deep_research")
    assert isinstance(deep_span.get("start_at"), str)
    assert isinstance(deep_span.get("end_at"), str)
    assert deep_span.get("duration_ms") is not None
    assert not any(
        str(event.get("stage", "")).startswith("deep_beta")
        for event in result.get("flow_events", [])
    )


def test_strip_html_from_mermaid_blocks_removes_html_tags() -> None:
    markdown = (
        "```mermaid\n"
        "flowchart TD\n"
        "A[Start]<br/> --> B<p>Done</p>\n"
        "```\n"
    )
    cleaned = tier2._strip_html_from_mermaid_blocks(markdown)
    assert "<br" not in cleaned.lower()
    assert "<p>" not in cleaned.lower()
    assert "```mermaid" in cleaned


def test_strip_html_from_mermaid_blocks_normalizes_inline_citations() -> None:
    markdown = (
        "```mermaid\n"
        "flowchart TD\n"
        "A[Claim] --> B[Khuyến nghị [pubmed-30879339] [1]]\n"
        "```\n"
    )
    cleaned = tier2._strip_html_from_mermaid_blocks(markdown)
    assert "[pubmed-30879339]" not in cleaned
    assert "[1]" not in cleaned
    assert "(pubmed-30879339)" in cleaned
    assert "(1)" in cleaned


def test_dedupe_duplicate_h2_headings_removes_repeated_conclusion() -> None:
    markdown = (
        "## Kết luận nhanh\n"
        "A.\n\n"
        "## Kết luận nhanh\n"
        "B.\n\n"
        "## Tóm tắt điều hành\n"
        "C.\n"
    )
    cleaned = tier2._dedupe_duplicate_h2_headings(markdown)
    assert cleaned.count("## Kết luận nhanh") == 1
    assert cleaned.count("## Tóm tắt điều hành") == 1
    assert "B." not in cleaned


def test_dedupe_duplicate_h2_headings_handles_prefixed_required_heading() -> None:
    markdown = (
        "## Kết luận nhanh\n"
        "Nội dung ngắn.\n\n"
        "## Kết luận nhanh Warfarin có nguy cơ cao\n"
        "Nội dung dài hơn và đầy đủ hơn.\n\n"
        "## Tóm tắt điều hành\n"
        "Tóm tắt.\n"
    )
    cleaned = tier2._dedupe_duplicate_h2_headings(markdown)
    assert cleaned.count("## Kết luận nhanh") == 1
    assert "## Kết luận nhanh Warfarin có nguy cơ cao" not in cleaned
    assert "Nội dung dài hơn và đầy đủ hơn." in cleaned


def test_ensure_deep_beta_report_artifacts_appends_missing_blocks() -> None:
    report = "## Kết luận nhanh\nNo table no mermaid no chart."
    fixed = tier2._ensure_deep_beta_report_artifacts(
        markdown_text=report,
        deep_pass_summaries=[{"pass_index": 1, "subquery": "warfarin interaction", "retrieved_count": 3}],
        evidence_verification={
            "supported_claims": ["c1"],
            "unsupported_claims": [],
            "contradicted_claims": [],
        },
        verification_summary={"support_ratio": 0.8},
    )
    assert "| Pass | Subquery | Retrieved |" in fixed


def test_ensure_deep_beta_report_artifacts_injects_reasoning_chain_section() -> None:
    fixed = tier2._ensure_deep_beta_report_artifacts(
        markdown_text="## Kết luận nhanh\nTóm tắt ngắn.",
        deep_pass_summaries=[],
        reasoning_nodes=[
            {
                "node": "deep_beta_evidence_audit",
                "confidence": 0.82,
                "reasoning_chain": [
                    {
                        "claim": "Nguy cơ xuất huyết tăng khi phối hợp warfarin và NSAID.",
                        "evidence": "Nguồn openfda + tổng quan hệ thống cho thấy tăng bleeding events.",
                        "inference": "Rủi ro cao hơn ở người cao tuổi hoặc có bệnh nền.",
                        "clinical_action": "Ưu tiên tránh phối hợp hoặc theo dõi sát dấu hiệu xuất huyết.",
                        "confidence": 0.81,
                    }
                ],
            }
        ],
        evidence_verification={},
        verification_summary={},
    )
    assert "## Chuỗi lập luận bằng chứng" in fixed
    assert "| Node | Claim | Evidence | Inference | Clinical action | Confidence |" in fixed


def test_run_deep_beta_llm_reasoning_node_extracts_reasoning_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeReasoningClient:
        def generate(self, prompt: str, system_prompt: str | None = None) -> SimpleNamespace:
            return SimpleNamespace(
                content=(
                    "{"
                    '"confidence": 0.84,'
                    '"insights": ["Ưu tiên cảnh giác xuất huyết nhóm nguy cơ cao"],'
                    '"actions": ["Bổ sung truy xuất guideline cập nhật 2025"],'
                    '"watchouts": ["Khác biệt baseline nguy cơ giữa nhóm bệnh nền"],'
                    '"reasoning_chain": ['
                    "{"
                    '"claim":"Nguy cơ xuất huyết tăng khi phối hợp warfarin và ibuprofen",'
                    '"evidence":"Nhãn thuốc + systematic review cho thấy tăng bleeding signal",'
                    '"inference":"Tác động cộng gộp trên đông máu làm tăng biến cố bất lợi",'
                    '"clinical_action":"Hạn chế phối hợp, theo dõi dấu hiệu xuất huyết sớm",'
                    '"confidence":0.8'
                    "}"
                    "],"
                    '"follow_up_queries": ["warfarin ibuprofen bleeding subgroup elderly"],'
                    '"evidence_checks": ["cross-check guideline recommendation consistency"]'
                    "}"
                ),
                model="deepseek-v3.2",
            )

    monkeypatch.setattr(tier2.settings, "deepseek_api_key", "test-key")
    monkeypatch.setattr(
        tier2,
        "_build_reasoning_client",
        lambda **kwargs: _FakeReasoningClient(),
    )

    result = tier2._run_deep_beta_llm_reasoning_node(
        node_name="deep_beta_evidence_audit",
        objective="Audit evidence quality and unresolved gaps.",
        topic="Tương tác warfarin với ibuprofen",
        query_plan={},
        retrieval_budget={},
        deep_pass_summaries=[],
        evidence_rows=[],
    )

    assert result["status"] == "completed"
    assert isinstance(result.get("reasoning_chain"), list)
    assert len(result["reasoning_chain"]) == 1
    assert "warfarin" in str(result["reasoning_chain"][0]["claim"]).lower()


def test_sanitize_user_facing_answer_markdown_removes_redundant_sections() -> None:
    raw = (
        "## Kết luận nhanh\n"
        "Hệ thống tạm thời dùng fallback local để đảm bảo không gián đoạn trả lời.\n\n"
        "```mermaid\nflowchart TD\nA-->B\n```\n\n"
        "## Nguồn tham chiếu\n"
        "- [1] demo\n"
    )
    cleaned = tier2._sanitize_user_facing_answer_markdown(raw)
    assert "fallback local" not in cleaned.lower()
    assert "```mermaid" not in cleaned
    assert "## Nguồn tham chiếu" not in cleaned


def test_sanitize_user_facing_answer_markdown_fast_enforces_compact_layout() -> None:
    raw = (
        "## Kết luận nhanh\n"
        "DASH và Địa Trung Hải đều hữu ích.\n\n"
        "## Câu hỏi nghiên cứu (PICO)\n"
        "- Population ...\n\n"
        "security\n"
        "Ma trận quyết định an toàn\n"
        "AI Verified\n"
        "Claim\n"
        "Verdict\n"
        "Confidence\n"
        "Hệ thống tạm thời dùng fallback local để đảm bảo không gián đoạn trả lời.\n\n"
        "## Phân tích chi tiết\n"
        "So sánh ưu nhược điểm theo mục tiêu điều trị.\n"
    )
    cleaned = tier2._sanitize_user_facing_answer_markdown(raw, research_mode="fast")
    assert "## Kết luận nhanh" in cleaned
    assert "## Điểm chính" in cleaned
    assert "## Ứng dụng thực tế" in cleaned
    assert "## Lưu ý an toàn" in cleaned
    assert "## Câu hỏi nghiên cứu (PICO)" not in cleaned
    assert "Ma trận quyết định an toàn" not in cleaned
    assert "AI Verified" not in cleaned
    assert "fallback local" not in cleaned.lower()


def test_sanitize_user_facing_answer_markdown_deep_removes_deep_beta_sections() -> None:
    raw = (
        "## Kết luận nhanh\n"
        "Nội dung tóm tắt.\n\n"
        "## Kế hoạch nghiên cứu\n"
        "- Bóc tách truy xuất.\n\n"
        "## Câu hỏi nghiên cứu (PICO)\n"
        "- Population ...\n\n"
        "## Ma trận quyết định an toàn\n"
        "| Mục đánh giá | Mức hiện tại | Hành động khuyến nghị |\n"
        "| --- | --- | --- |\n"
        "| Mức rủi ro tổng quát | Trung bình | Theo dõi sát |\n"
    )
    cleaned = tier2._sanitize_user_facing_answer_markdown(raw, research_mode="deep")
    assert "## Kết luận nhanh" in cleaned
    assert "## Điểm chính" in cleaned
    assert "## Ứng dụng thực tế" in cleaned
    assert "## Lưu ý an toàn" in cleaned
    assert "## Kế hoạch nghiên cứu" not in cleaned
    assert "## Câu hỏi nghiên cứu (PICO)" not in cleaned
    assert "## Ma trận quyết định an toàn" not in cleaned


def test_sanitize_user_facing_answer_markdown_deep_beta_removes_telemetry_h3_blocks() -> None:
    raw = (
        "## Kết luận nhanh\n"
        "Nội dung chính.\n\n"
        "### Ma trận reasoning nodes\n"
        "| Node | Status |\n"
        "| --- | --- |\n"
        "| audit | completed |\n\n"
        "### Hồ sơ nguồn mở rộng\n"
        "| Source ID | Nguồn |\n"
        "| --- | --- |\n"
        "| pmid-1 | pubmed |\n\n"
        "## Bảng tổng hợp bằng chứng\n"
        "| ID | Summary |\n"
        "| --- | --- |\n"
        "| 1 | Nội dung |\n\n"
        "## Phân tích chi tiết\n"
        "Nội dung phân tích giữ lại.\n"
    )
    cleaned = tier2._sanitize_user_facing_answer_markdown(raw, research_mode="deep_beta")
    assert "### Ma trận reasoning nodes" not in cleaned
    assert "### Hồ sơ nguồn mở rộng" not in cleaned
    assert "## Bảng tổng hợp bằng chứng" not in cleaned
    assert "## Kết luận nhanh" in cleaned
    assert "## Điểm chính" in cleaned
    assert "## Ứng dụng thực tế" in cleaned
    assert "## Lưu ý an toàn" in cleaned


def test_has_reader_friendly_layout_rejects_extra_report_sections() -> None:
    raw = (
        "## Kết luận nhanh\n"
        "Tóm tắt.\n\n"
        "## Điểm chính\n"
        "Phân tích.\n\n"
        "## Ứng dụng thực tế\n"
        "- Áp dụng.\n\n"
        "## Lưu ý an toàn\n"
        "- Theo dõi.\n\n"
        "## Kế hoạch nghiên cứu\n"
        "- Extra section.\n"
    )
    assert tier2._has_reader_friendly_layout(raw, research_mode="deep") is False


def test_sanitize_user_facing_answer_markdown_normalizes_mixed_language_headings() -> None:
    raw = (
        "MARKDOWN\n"
        "## Quick conclusion\n"
        "This is the short conclusion.\n\n"
        "## Detailed analysis\n"
        "• First point\n"
        "2) Second point\n\n"
        "## Safety recommendations\n"
        "Check interactions carefully.\n\n"
        "## Monitoring and red flags\n"
        "Escalate if chest pain develops.\n"
    )
    cleaned = tier2._sanitize_user_facing_answer_markdown(raw, research_mode="fast")
    assert "MARKDOWN" not in cleaned
    assert "## Quick conclusion" not in cleaned
    assert "## Detailed analysis" not in cleaned
    assert "## Safety recommendations" not in cleaned
    assert "## Monitoring and red flags" not in cleaned
    assert "## Kết luận nhanh" in cleaned
    assert "## Điểm chính" in cleaned
    assert "## Ứng dụng thực tế" in cleaned
    assert "## Lưu ý an toàn" in cleaned
    assert "- First point" in cleaned
    assert "2. Second point" in cleaned


def test_sanitize_user_facing_answer_markdown_can_emit_english_sections() -> None:
    raw = (
        "## Kết luận nhanh\n"
        "Nội dung chính bằng tiếng Việt.\n\n"
        "## Phân tích chi tiết\n"
        "- Một ý đầu tiên.\n"
        "- Một ý thứ hai.\n"
    )
    cleaned = tier2._sanitize_user_facing_answer_markdown(
        raw,
        research_mode="fast",
        answer_language="en",
    )
    assert "## Quick conclusion" in cleaned
    assert "## Key points" in cleaned
    assert "## Practical application" in cleaned
    assert "## Important caveats" in cleaned
    assert "## Kết luận nhanh" not in cleaned


def test_sanitize_user_facing_answer_markdown_removes_query_and_local_context_labels() -> None:
    raw = (
        "## Kết luận nhanh\n"
        "Tóm tắt ngắn.\n\n"
        "Query: Hello\n"
        "Dưới đây là ngữ cảnh đã truy xuất và rút gọn ở chế độ cục bộ:\n"
        "| ID | SOURCE |\n"
        "| --- | --- |\n"
        "| 1 | pubmed |\n"
    )
    cleaned = tier2._sanitize_user_facing_answer_markdown(raw, research_mode="fast")
    assert "Query: Hello" not in cleaned
    assert "ngữ cảnh đã truy xuất" not in cleaned.lower()


def test_normalize_reader_facing_block_keeps_paragraph_layout_when_requested() -> None:
    text = (
        "Đây là đoạn phân tích đầu tiên về khác biệt chính giữa hai chiến lược.\n\n"
        "Đây là đoạn thứ hai giải thích ý nghĩa thực hành thay vì ép thành checklist."
    )
    normalized = tier2._normalize_reader_facing_block(
        text,
        max_items=5,
        max_len=420,
        prefer_paragraphs=True,
    )
    assert normalized.startswith("Đây là đoạn phân tích đầu tiên")
    assert "- Đây là đoạn" not in normalized


def test_ensure_markdown_structure_deep_uses_practical_sections() -> None:
    structured = tier2._ensure_markdown_structure(
        topic="So sánh DASH và Địa Trung Hải",
        answer="Hai chế độ ăn đều có lợi nhưng khác mục tiêu chính.",
        citations=[],
        research_mode="deep",
        plan_steps=[],
    )
    assert "## Điểm chính" in structured
    assert "## Ứng dụng thực tế" in structured
    assert "## Lưu ý an toàn" in structured
    assert "## Kế hoạch nghiên cứu" not in structured


def test_resolve_report_word_budget_by_mode() -> None:
    deep_min, deep_target, deep_max = tier2._resolve_report_word_budget("deep")
    beta_min, beta_target, beta_max = tier2._resolve_report_word_budget("deep_beta")
    assert deep_min < beta_min
    assert deep_target < beta_target
    assert deep_max < beta_max


def test_resolve_adaptive_report_word_budget_reduces_deep_beta_for_sparse_evidence() -> None:
    base_min, base_target, _base_max = tier2._resolve_report_word_budget("deep_beta")
    adaptive_min, adaptive_target, adaptive_max = tier2._resolve_adaptive_report_word_budget(
        research_mode="deep_beta",
        citation_count=2,
        deep_pass_count=2,
        reasoning_node_count=1,
    )
    assert adaptive_min < base_min
    assert adaptive_target < base_target
    assert adaptive_max > adaptive_target


def test_resolve_report_section_contract_by_mode() -> None:
    deep_sections, _ = tier2._resolve_report_section_contract("deep")
    beta_sections, _ = tier2._resolve_report_section_contract("deep_beta")
    assert "## Điểm chính" in deep_sections
    assert "## Ứng dụng thực tế" in deep_sections
    assert "## Câu hỏi nghiên cứu (PICO)" not in deep_sections
    assert "## Điểm chính" in beta_sections
    assert "## Lưu ý an toàn" in beta_sections


def test_resolve_report_style_profile_by_mode() -> None:
    deep_profile = tier2._resolve_report_style_profile("deep")
    beta_profile = tier2._resolve_report_style_profile("deep_beta")
    assert deep_profile["tone"] == "clinical_briefing_reader_first"
    assert beta_profile["tone"] == "high_signal_research_answer"
    assert isinstance(deep_profile["must_do"], list) and deep_profile["must_do"]
    assert isinstance(beta_profile["avoid"], list) and beta_profile["avoid"]
