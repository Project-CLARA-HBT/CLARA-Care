from clara_ml.llm.deepseek_client import DeepSeekResponse
from clara_ml.rag.langchain_adapter import build_prompt
from clara_ml.rag.pipeline import RagPipelineP0
from clara_ml.rag.retriever import Document


def test_rag_pipeline_returns_sources_and_answer():
    pipe = RagPipelineP0(deepseek_api_key="")
    result = pipe.run("canh bao tuong tac thuoc")
    assert len(result.retrieved_ids) > 0
    assert "LOCAL_FALLBACK_V1" in result.answer
    assert result.model_used == "local-synth-v1"


def test_build_prompt_formats_variables():
    rendered = build_prompt(
        role="doctor",
        intent="doctor_case_review",
        template="Case: {case_summary}",
        variables={"case_summary": "BN nam 65t tang huyet ap"},
    )
    assert "doctor_case_review" in rendered
    assert "BN nam 65t" in rendered


class _FailingClient:
    @property
    def model(self) -> str:
        return "deepseek-v3.2"

    def generate(self, prompt: str, system_prompt: str | None = None):
        raise RuntimeError("provider down")


class _SuccessfulClient:
    @property
    def model(self) -> str:
        return "deepseek-v3.2"

    def generate(self, prompt: str, system_prompt: str | None = None) -> DeepSeekResponse:
        return DeepSeekResponse(content="provider-answer", model="deepseek-v3.2")


class _ExternalFailureRetriever:
    def retrieve_internal(
        self,
        query: str,
        top_k: int = 3,
        *,
        file_retrieval_enabled: bool = True,
        rag_sources: object = None,
        uploaded_documents: object = None,
    ) -> list[Document]:
        return [
            Document(
                id="internal-1",
                text="Warfarin can interact with NSAIDs and increase bleeding risk.",
                metadata={"source": "internal", "url": "", "score": 0.0},
            )
        ]

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        *,
        scientific_retrieval_enabled: bool = False,
        web_retrieval_enabled: bool = False,
        file_retrieval_enabled: bool = True,
        rag_sources: object = None,
        uploaded_documents: object = None,
    ) -> list[Document]:
        raise TimeoutError("external connectors busy")


def test_rag_pipeline_uses_provider_when_key_exists():
    pipe = RagPipelineP0(
        deepseek_api_key="test-key",
        llm_client=_SuccessfulClient(),
    )
    result = pipe.run("canh bao nsaid")
    assert result.answer == "provider-answer"
    assert result.model_used == "deepseek-v3.2"


def test_rag_pipeline_fallback_when_deepseek_fails():
    pipe = RagPipelineP0(
        deepseek_api_key="test-key",
        llm_client=_FailingClient(),
    )
    result = pipe.run("canh bao tuong tac nsaid")
    assert result.model_used == "local-synth-v1"
    assert "LOCAL_FALLBACK_V1" in result.answer
    assert "## Kết luận nhanh" in result.answer


def test_rag_pipeline_survives_external_retrieval_exception():
    pipe = RagPipelineP0(
        deepseek_api_key="test-key",
        llm_client=_SuccessfulClient(),
        retriever=_ExternalFailureRetriever(),
    )
    result = pipe.run(
        "canh bao warfarin va ibuprofen",
        scientific_retrieval_enabled=True,
        web_retrieval_enabled=False,
        file_retrieval_enabled=True,
    )

    assert result.answer == "provider-answer"
    assert result.model_used == "deepseek-v3.2"
    assert any(
        event.get("stage") == "external_scientific_retrieval" and event.get("status") == "error"
        for event in result.flow_events
    )
    assert all("payload" in event for event in result.flow_events if isinstance(event, dict))


def test_rag_pipeline_context_debug_includes_retrieval_trace():
    pipe = RagPipelineP0(deepseek_api_key="")
    result = pipe.run("tuong tac warfarin va nsaid")

    retrieval_trace = result.context_debug.get("retrieval_trace")
    assert isinstance(retrieval_trace, dict)
    assert retrieval_trace.get("document_count") == len(result.retrieved_ids)
    assert isinstance(result.trace, dict)
    assert isinstance(result.trace.get("planner"), dict)
    assert isinstance(result.trace.get("retrieval"), dict)


def test_rag_pipeline_emits_retrieval_orchestrator_events():
    pipe = RagPipelineP0(deepseek_api_key="")
    result = pipe.run(
        "tuong tac warfarin voi ibuprofen va naproxen nguy co xuat huyet",
        planner_hints={
            "internal_top_k": 3,
            "hybrid_top_k": 4,
            "research_mode": "deep",
            "reason_codes": ["evidence_heavy_query", "ddi_critical_query"],
            "query_focus": "evidence_review",
        },
        scientific_retrieval_enabled=True,
        web_retrieval_enabled=True,
    )

    orchestrator_events = [
        event
        for event in result.flow_events
        if event.get("stage") == "retrieval_orchestrator"
    ]
    assert len(orchestrator_events) >= 2
    assert any(event.get("status") == "started" for event in orchestrator_events)
    completed_events = [
        event for event in orchestrator_events if event.get("status") == "completed"
    ]
    assert completed_events
    completed_payload = completed_events[-1].get("payload", {})
    assert completed_payload.get("mode") == "deep"
    assert isinstance(completed_payload.get("profile"), dict)
    assert isinstance(completed_payload.get("complexity"), dict)
    assert isinstance(completed_payload.get("budgets"), dict)
    assert isinstance(completed_payload.get("top_k"), dict)
    assert isinstance(completed_payload.get("connector_toggles"), dict)

    retrieval_trace = result.context_debug.get("retrieval_trace", {})
    assert isinstance(retrieval_trace.get("orchestrator_plan"), dict)
    assert retrieval_trace.get("orchestrator_mode") == "deep"
    assert isinstance(result.context_debug.get("orchestrator_plan"), dict)
    assert isinstance(result.trace.get("orchestrator"), dict)


def test_rag_pipeline_orchestrator_adjusts_top_k_and_connector_toggles():
    pipe = RagPipelineP0(deepseek_api_key="")
    result = pipe.run(
        "uong paracetamol",
        planner_hints={
            "internal_top_k": 4,
            "hybrid_top_k": 4,
            "research_mode": "fast",
            "query_focus": "default",
        },
        scientific_retrieval_enabled=False,
        web_retrieval_enabled=True,
    )

    retrieval_trace = result.context_debug.get("retrieval_trace", {})
    orchestrator_plan = retrieval_trace.get("orchestrator_plan", {})
    assert isinstance(orchestrator_plan, dict)
    assert retrieval_trace.get("internal_top_k_requested") == 4
    assert orchestrator_plan.get("top_k", {}).get("requested", {}).get("internal") == 4
    assert orchestrator_plan.get("top_k", {}).get("adjusted", {}).get("internal") == 3
    assert retrieval_trace.get("internal_top_k") == 3
    assert orchestrator_plan.get("top_k", {}).get("deltas", {}).get("internal") == -1

    connector_toggles = orchestrator_plan.get("connector_toggles", {})
    assert connector_toggles.get("requested", {}).get("web") is True
    assert connector_toggles.get("requested", {}).get("scientific") is False
    assert connector_toggles.get("resolved", {}).get("web") is False
    assert "web_requires_scientific_connectors" in connector_toggles.get(
        "disabled_reasons", []
    )


def test_rag_pipeline_supports_retrieval_only_mode():
    pipe = RagPipelineP0(
        deepseek_api_key="test-key",
        llm_client=_SuccessfulClient(),
    )
    result = pipe.run("warfarin ibuprofen interaction", generation_enabled=False)
    assert result.model_used == "retrieval-only-v1"
    assert any(
        event.get("stage") == "llm_generation" and event.get("status") == "skipped"
        for event in result.flow_events
    )


def test_rag_pipeline_emits_search_and_index_events():
    pipe = RagPipelineP0(deepseek_api_key="")
    result = pipe.run("ddi warfarin ibuprofen", scientific_retrieval_enabled=False)

    retrieval_trace = result.context_debug.get("retrieval_trace")
    assert isinstance(retrieval_trace, dict)
    assert isinstance(retrieval_trace.get("search_plan"), dict)
    assert isinstance(retrieval_trace.get("index_summary"), dict)
    assert "source_attempts" in retrieval_trace

    assert any(
        event.get("stage") == "evidence_search" and event.get("status") in {"started", "completed"}
        for event in result.flow_events
    )
    assert any(
        event.get("stage") == "evidence_index" and event.get("status") in {"started", "completed"}
        for event in result.flow_events
    )


def test_rag_pipeline_retrieval_events_precede_answer_synthesis():
    pipe = RagPipelineP0(deepseek_api_key="")
    result = pipe.run("warfarin ibuprofen bleeding risk")
    assert isinstance(result.flow_events, list)
    assert len(result.flow_events) > 0

    synthesis_indices = [
        idx
        for idx, event in enumerate(result.flow_events)
        if str(event.get("stage", "")).strip().lower() == "answer_synthesis"
    ]
    assert synthesis_indices
    first_synthesis_index = synthesis_indices[0]

    retrieval_indices = [
        idx
        for idx, event in enumerate(result.flow_events)
        if any(
            token in str(event.get("stage", "")).strip().lower()
            for token in ("search", "retrieval", "index")
        )
    ]
    assert retrieval_indices
    assert max(retrieval_indices) < first_synthesis_index
