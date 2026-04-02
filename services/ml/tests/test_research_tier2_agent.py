from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

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


def test_build_planner_hints_deep_mode_full_stack_still_forces_connectors_and_graphrag():
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
    assert hints["graphrag_enabled_override"] is True
    assert "retrieval_stack_mode_full" in hints["reason_codes"]
    assert "stack_mode_full_downgraded_for_fast_mode" not in hints["reason_codes"]
    assert "stack_mode_full_force_scientific" in hints["reason_codes"]
    assert "stack_mode_full_force_web" in hints["reason_codes"]
    assert "stack_mode_full_force_graphrag" in hints["reason_codes"]


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
    assert "## Tóm tắt điều hành" in result["answer_markdown"]
    assert "## Bảng tổng hợp bằng chứng" in result["answer_markdown"]


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
