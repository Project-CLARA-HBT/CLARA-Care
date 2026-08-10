from contextlib import contextmanager

from clara_ml.config import settings
from clara_ml.llm.deepseek_client import DeepSeekResponse
from clara_ml.llm.model_registry import ModelTask
from clara_ml.rag.langchain_adapter import build_prompt
from clara_ml.rag.pipeline import RagPipelineP0
from clara_ml.rag.retriever import Document


@contextmanager
def _graphrag_flags(*, enabled: bool, max_neighbors: int = 8, expansion_docs: int = 4):
    prev_enabled = settings.rag_graphrag_enabled
    prev_neighbors = settings.rag_graphrag_max_neighbors
    prev_expansion = settings.rag_graphrag_expansion_docs
    prev_domain_enabled = settings.rag_biomed_graph_enabled
    settings.rag_graphrag_enabled = enabled
    settings.rag_graphrag_max_neighbors = max_neighbors
    settings.rag_graphrag_expansion_docs = expansion_docs
    settings.rag_biomed_graph_enabled = enabled
    try:
        yield
    finally:
        settings.rag_graphrag_enabled = prev_enabled
        settings.rag_graphrag_max_neighbors = prev_neighbors
        settings.rag_graphrag_expansion_docs = prev_expansion
        settings.rag_biomed_graph_enabled = prev_domain_enabled


def test_rag_pipeline_returns_sources_and_answer():
    pipe = RagPipelineP0(deepseek_api_key="")
    result = pipe.run("canh bao tuong tac thuoc", deepseek_fallback_enabled=True)
    assert len(result.retrieved_ids) > 0
    assert "LOCAL_FALLBACK_V1" in result.answer
    assert result.model_used == "local-synth-v1"


def test_serialize_context_preserves_primary_trial_provenance():
    rows = RagPipelineP0._serialize_context(
        [
            Document(
                id="pubmed-32970396",
                text="DAPA-CKD abstract",
                metadata={
                    "source": "pubmed",
                    "title": "Dapagliflozin in Patients with Chronic Kidney Disease",
                    "pmid": "32970396",
                    "doi": "10.1056/NEJMoa2024816",
                    "nct_ids": ["NCT03036150"],
                    "publication_types": ["Randomized Controlled Trial"],
                    "source_type": "primary_trial",
                    "study_design": "randomized_controlled_trial",
                },
            )
        ]
    )

    assert rows[0]["pmid"] == "32970396"
    assert rows[0]["doi"] == "10.1056/NEJMoa2024816"
    assert rows[0]["nct_ids"] == ["NCT03036150"]
    assert rows[0]["source_type"] == "primary_trial"
    assert rows[0]["study_design"] == "randomized_controlled_trial"


def test_degraded_pool_reserves_primary_trials_before_editorial():
    def _row(score: float, doc_id: str, source_type: str):
        return (
            score,
            doc_id,
            Document(
                id=doc_id,
                text=doc_id,
                metadata={
                    "source": "pubmed",
                    "retrieval_origin": "external_scientific",
                    "source_type": source_type,
                },
            ),
            0,
        )

    ranked = [
        _row(0.99, "pubmed-editorial", "evidence_synthesis"),
        _row(0.61, "pubmed-dapa-ckd", "primary_trial"),
        _row(0.49, "pubmed-empa-kidney", "primary_trial"),
    ]

    selected = RagPipelineP0().retriever._diversified_degraded_pool(ranked, limit=2)

    assert [row[1] for row in selected] == [
        "pubmed-dapa-ckd",
        "pubmed-empa-kidney",
    ]


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


class _TransientThenSuccessClient:
    def __init__(self) -> None:
        self.calls = 0

    @property
    def model(self) -> str:
        return "deepseek-v3.2"

    def generate(self, prompt: str, system_prompt: str | None = None) -> DeepSeekResponse:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("timeout: upstream gateway")
        return DeepSeekResponse(content="provider-retry-answer", model="deepseek-v3.2")


class _SuccessfulClient:
    @property
    def model(self) -> str:
        return "deepseek-v3.2"

    def generate(self, prompt: str, system_prompt: str | None = None) -> DeepSeekResponse:
        return DeepSeekResponse(content="provider-answer", model="deepseek-v3.2")


class _CapturingClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, str | None]] = []

    @property
    def model(self) -> str:
        return "deepseek-v3.2"

    def generate(self, prompt: str, system_prompt: str | None = None) -> DeepSeekResponse:
        self.calls.append({"prompt": prompt, "system_prompt": system_prompt})
        return DeepSeekResponse(content="captured-answer", model="deepseek-v3.2")


class _RecordingRuntimeClient:
    calls: list[dict[str, object]] = []

    def __init__(self, **kwargs) -> None:
        self._kwargs = dict(kwargs)
        type(self).calls.append(self._kwargs)

    @classmethod
    def from_runtime(cls, llm_runtime, *, timeout_seconds, **kwargs):
        runtime = llm_runtime if isinstance(llm_runtime, dict) else {}
        return cls(
            api_key=str(runtime.get("api_key") or "").strip(),
            base_url=str(runtime.get("base_url") or "").strip(),
            model=str(runtime.get("model") or "").strip(),
            timeout_seconds=timeout_seconds,
            **kwargs,
        )

    @property
    def model(self) -> str:
        return str(self._kwargs.get("model") or "deepseek-v3.2")

    def generate(self, prompt: str, system_prompt: str | None = None) -> DeepSeekResponse:
        return DeepSeekResponse(content="runtime-answer", model=self.model)


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


def test_rag_pipeline_uses_injected_provider_client_without_network():
    pipe = RagPipelineP0(llm_client=_SuccessfulClient())
    result = pipe.run("canh bao nsaid")
    assert result.answer == "provider-answer"
    assert result.model_used == "deepseek-v3.2"


def test_rag_pipeline_ignores_legacy_connection_override_constructor_values(monkeypatch):
    calls: list[dict[str, object]] = []

    def _registered_client(task, task_settings, *, timeout_seconds, retries_per_base):
        calls.append(
            {
                "task": task,
                "api_key": task_settings.deepseek_api_key,
                "base_url": task_settings.deepseek_base_url,
                "model": task_settings.deepseek_model,
                "timeout_seconds": timeout_seconds,
                "retries_per_base": retries_per_base,
            }
        )
        return _SuccessfulClient(), object()

    monkeypatch.setattr("clara_ml.rag.pipeline.build_task_client", _registered_client)
    RagPipelineP0(
        deepseek_api_key="explicit-key",
        deepseek_base_url="https://internal.example/v1",
        deepseek_model="explicit-model",
        deepseek_timeout_seconds=31,
    )

    assert calls == []


def test_rag_pipeline_fallback_when_deepseek_fails():
    pipe = RagPipelineP0(
        deepseek_api_key="test-key",
        llm_client=_FailingClient(),
    )
    result = pipe.run("canh bao tuong tac nsaid", deepseek_fallback_enabled=True)
    assert result.model_used == "local-synth-v1"
    assert "LOCAL_FALLBACK_V1" in result.answer
    assert "## Kết luận nhanh" in result.answer


def test_rag_pipeline_deep_beta_uses_long_form_generation_path() -> None:
    client = _CapturingClient()
    pipe = RagPipelineP0(
        deepseek_api_key="test-key",
        llm_client=client,
    )

    result = pipe.run(
        "tuong tac warfarin voi ibuprofen va naproxen nguy co xuat huyet",
        planner_hints={"research_mode": "deep_beta"},
        low_context_threshold=0.0,
    )

    assert result.answer == "captured-answer"
    assert result.model_used == "deepseek-v3.2"
    assert len(client.calls) == 1
    prompt_call = client.calls[0]
    assert prompt_call["prompt"] is not None
    assert "structured clinical dossier / evidence brief" in prompt_call["prompt"]
    assert "Include contradiction handling" in prompt_call["prompt"]
    assert "Perplexity-like research answer style" not in prompt_call["prompt"]
    assert prompt_call["system_prompt"] is not None
    assert "deep beta clinical dossier synthesizer" in prompt_call["system_prompt"]
    assert "contradiction audit" in prompt_call["system_prompt"]
    assert "Perplexity synthesis" not in prompt_call["system_prompt"]

    retrieval_trace = result.context_debug.get("retrieval_trace", {})
    assert retrieval_trace.get("orchestrator_mode") == "deep"


def test_rag_pipeline_deep_mode_keeps_existing_reader_first_long_form_contract() -> None:
    client = _CapturingClient()
    pipe = RagPipelineP0(
        deepseek_api_key="test-key",
        llm_client=client,
    )

    result = pipe.run(
        "tuong tac warfarin voi ibuprofen va naproxen nguy co xuat huyet",
        planner_hints={"research_mode": "deep"},
        low_context_threshold=0.0,
    )

    assert result.answer == "captured-answer"
    assert result.model_used == "deepseek-v3.2"
    assert len(client.calls) == 1
    prompt_call = client.calls[0]
    assert prompt_call["prompt"] is not None
    assert "Write in a Perplexity-like research answer style" in prompt_call["prompt"]
    assert "Be detailed, but avoid sounding like an internal dossier" in prompt_call["prompt"]
    assert prompt_call["system_prompt"] is not None
    assert "Produce a long-form, evidence-grounded" in prompt_call["system_prompt"]
    assert "avoid dossier-like boilerplate" in prompt_call["system_prompt"]


def test_local_synthesis_avoids_source_dump_in_main_body() -> None:
    answer = RagPipelineP0._local_synthesis(
        "canh bao warfarin va nsaid",
        [
            Document(
                id="pmid-1",
                text="Warfarin and NSAID co-use increases bleeding risk and needs closer monitoring.",
                metadata={"source": "pubmed", "title": "Warfarin bleeding risk"},
            )
        ],
        answer_language="vi",
    )
    assert "LOCAL_FALLBACK_V1" in answer
    assert "Nguồn nổi bật" not in answer
    assert "pubmed" not in answer


def test_build_no_rag_prompt_uses_reader_facing_section_contract() -> None:
    prompt = RagPipelineP0._build_no_rag_prompt(
        "compare DASH and Mediterranean", answer_language="en"
    )
    assert (
        "## Quick conclusion, ## Key points, ## Practical application, ## Important caveats"
        in prompt
    )
    assert "## Detailed analysis" not in prompt


def test_rag_pipeline_recovers_from_transient_llm_failure_with_compact_retry():
    client = _TransientThenSuccessClient()
    pipe = RagPipelineP0(
        deepseek_api_key="test-key",
        llm_client=client,
    )
    result = pipe.run("canh bao tuong tac nsaid voi warfarin")
    assert result.model_used == "deepseek-v3.2"
    assert result.answer == "provider-retry-answer"
    assert client.calls == 2
    assert any(
        event.get("stage") == "llm_generation_retry" and event.get("status") == "completed"
        for event in result.flow_events
    )


def test_rag_pipeline_reuses_default_deepseek_client_for_deepseek_only_runtime():
    pipe = RagPipelineP0(
        deepseek_api_key="deepseek-only-key",
        llm_client=_SuccessfulClient(),
    )
    previous_deepseek_only = settings.llm_deepseek_only
    previous_base_url = settings.deepseek_base_url
    previous_model = settings.deepseek_model
    try:
        settings.llm_deepseek_only = True
        settings.deepseek_base_url = "https://api.yescale.vip/v1"
        settings.deepseek_model = "deepseek-v3.2"
        _RecordingRuntimeClient.calls = []

        result = pipe.run(
            "khi bi so mui toi nen lam gi",
            low_context_threshold=0.0,
            llm_runtime={
                "provider": "deepseek",
                "api_key": "deepseek-only-key",
                "base_url": "https://api.yescale.vip/v1",
                "model": "deepseek-v3.2",
            },
        )
    finally:
        settings.llm_deepseek_only = previous_deepseek_only
        settings.deepseek_base_url = previous_base_url
        settings.deepseek_model = previous_model

    assert result.answer == "provider-answer"
    assert _RecordingRuntimeClient.calls == []


def test_rag_pipeline_ignores_per_request_runtime_override(monkeypatch):
    pipe = RagPipelineP0(
        deepseek_api_key="default-key",
        llm_client=_SuccessfulClient(),
    )
    previous_timeout = settings.deepseek_timeout_seconds
    previous_deepseek_only = settings.llm_deepseek_only
    try:
        settings.deepseek_timeout_seconds = 60
        settings.llm_deepseek_only = False
        _RecordingRuntimeClient.calls = []

        def _registered_client(task, task_settings, *, timeout_seconds, retries_per_base):
            assert task is ModelTask.RAG_SYNTHESIS
            assert retries_per_base == 0
            return (
                _RecordingRuntimeClient(
                    api_key=task_settings.deepseek_api_key,
                    base_url=task_settings.deepseek_base_url,
                    model=task_settings.deepseek_model,
                    timeout_seconds=timeout_seconds,
                ),
                object(),
            )

        monkeypatch.setattr("clara_ml.rag.pipeline.build_task_client", _registered_client)

        result = pipe.run(
            "compare dash and mediterranean",
            llm_runtime={
                "provider": "deepseek",
                "api_key": "runtime-key",
                "base_url": "https://runtime.example/v1",
                "model": "deepseek-v3.2",
            },
        )
    finally:
        settings.deepseek_timeout_seconds = previous_timeout
        settings.llm_deepseek_only = previous_deepseek_only

    assert result.answer == "provider-answer"
    assert _RecordingRuntimeClient.calls == []


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
    result = pipe.run("tuong tac warfarin va nsaid", deepseek_fallback_enabled=True)

    retrieval_trace = result.context_debug.get("retrieval_trace")
    assert isinstance(retrieval_trace, dict)
    assert retrieval_trace.get("document_count") == len(result.retrieved_ids)
    rerank = retrieval_trace.get("index_summary", {}).get("rerank", {})
    assert isinstance(rerank, dict)
    assert "rerank_topn" in rerank
    assert isinstance(rerank.get("rerank_latency_ms"), float)
    assert isinstance(rerank.get("rerank_cache_hit"), bool)
    assert isinstance(result.trace, dict)
    assert isinstance(result.trace.get("planner"), dict)
    assert isinstance(result.trace.get("retrieval"), dict)


def test_rag_pipeline_exposes_reasoning_event_summary_for_api_consumers():
    pipe = RagPipelineP0(deepseek_api_key="")
    result = pipe.run("tuong tac warfarin va ibuprofen", deepseek_fallback_enabled=True)

    reasoning_events = result.context_debug.get("reasoning_events")
    assert isinstance(reasoning_events, list)
    assert len(reasoning_events) > 0
    assert all(
        "stage" in event and "status" in event
        for event in reasoning_events
        if isinstance(event, dict)
    )
    reasoning_trace = result.trace.get("reasoning", {})
    assert isinstance(reasoning_trace, dict)
    assert int(reasoning_trace.get("event_count") or 0) == len(reasoning_events)


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
        deepseek_fallback_enabled=True,
    )

    orchestrator_events = [
        event for event in result.flow_events if event.get("stage") == "retrieval_orchestrator"
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
        deepseek_fallback_enabled=True,
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
    assert "web_requires_scientific_connectors" in connector_toggles.get("disabled_reasons", [])


def test_rag_pipeline_orchestrator_applies_retrieval_budget_override():
    pipe = RagPipelineP0(deepseek_api_key="")
    result = pipe.run(
        "tuong tac warfarin voi ibuprofen va naproxen",
        planner_hints={
            "internal_top_k": 8,
            "hybrid_top_k": 8,
            "research_mode": "deep",
            "scientific_retrieval_enabled": True,
            "retrieval_budget": {
                "top_k_cap": 4,
                "max_connector_calls": 1,
                "latency_budget_ms": 1400,
            },
        },
        scientific_retrieval_enabled=True,
        web_retrieval_enabled=True,
        deepseek_fallback_enabled=True,
    )

    retrieval_trace = result.context_debug.get("retrieval_trace", {})
    orchestrator_plan = retrieval_trace.get("orchestrator_plan", {})
    assert isinstance(orchestrator_plan, dict)
    budgets = orchestrator_plan.get("budgets", {})
    assert int(budgets.get("top_k_cap") or 0) == 4
    assert int(budgets.get("max_connector_calls") or 0) == 1
    assert int(budgets.get("latency_budget_ms") or 0) == 1400
    adjusted_top_k = orchestrator_plan.get("top_k", {}).get("adjusted", {})
    assert int(adjusted_top_k.get("internal") or 0) <= 4
    assert int(adjusted_top_k.get("hybrid") or 0) <= 4
    decision_reasons = orchestrator_plan.get("decision_reasons", [])
    assert "planner_retrieval_budget_override" in decision_reasons


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
    result = pipe.run(
        "ddi warfarin ibuprofen",
        scientific_retrieval_enabled=False,
        deepseek_fallback_enabled=True,
    )

    retrieval_trace = result.context_debug.get("retrieval_trace")
    assert isinstance(retrieval_trace, dict)
    assert isinstance(retrieval_trace.get("search_plan"), dict)
    assert isinstance(retrieval_trace.get("index_summary"), dict)
    assert isinstance(retrieval_trace.get("index_summary", {}).get("rerank"), dict)
    assert isinstance(
        retrieval_trace.get("index_summary", {}).get("rerank", {}).get("rerank_cache_hit"),
        bool,
    )
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
    result = pipe.run("warfarin ibuprofen bleeding risk", deepseek_fallback_enabled=True)
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


def test_rag_pipeline_graphrag_sidecar_enabled_emits_events_and_summary():
    with _graphrag_flags(enabled=True, max_neighbors=5, expansion_docs=3):
        pipe = RagPipelineP0(deepseek_api_key="")
        result = pipe.run(
            "warfarin ibuprofen interaction bleeding risk",
            deepseek_fallback_enabled=True,
        )

    graphrag_events = [
        event for event in result.flow_events if event.get("stage") == "graphrag_sidecar"
    ]
    assert any(event.get("status") == "started" for event in graphrag_events)
    completed = [event for event in graphrag_events if event.get("status") == "completed"]
    assert completed

    retrieval_trace = result.context_debug.get("retrieval_trace", {})
    graphrag = retrieval_trace.get("graphrag", {})
    assert graphrag.get("enabled") is True
    assert int(graphrag.get("node_count") or 0) >= len(result.retrieved_ids)
    assert int(graphrag.get("edge_count") or 0) >= 0
    assert int(graphrag.get("expansion_count") or 0) <= 3
    assert retrieval_trace.get("graphrag_enabled") is True
    assert result.context_debug.get("graphrag_enabled") is True


def test_rag_pipeline_graphrag_sidecar_domain_graph_emits_hits():
    with _graphrag_flags(enabled=True, max_neighbors=6, expansion_docs=4):
        pipe = RagPipelineP0(deepseek_api_key="")
        result = pipe.run(
            "warfarin ibuprofen contraindication bleeding",
            deepseek_fallback_enabled=True,
        )

    retrieval_trace = result.context_debug.get("retrieval_trace", {})
    graphrag = retrieval_trace.get("graphrag", {})
    assert graphrag.get("enabled") is True
    assert graphrag.get("domain_graph_enabled") is True
    assert graphrag.get("domain_graph_loaded") is True
    assert int(graphrag.get("domain_entity_match_count") or 0) >= 2
    assert int(graphrag.get("domain_edge_hit_count") or 0) >= 1
    assert any(
        doc_id.startswith("graphrag-domain-")
        for doc_id in (graphrag.get("expansion_doc_ids") or [])
    )


def test_rag_pipeline_graphrag_sidecar_disabled_keeps_default_trace():
    with _graphrag_flags(enabled=False):
        pipe = RagPipelineP0(deepseek_api_key="")
        result = pipe.run("aspirin ibuprofen warning", deepseek_fallback_enabled=True)

    assert not any(event.get("stage") == "graphrag_sidecar" for event in result.flow_events)
    retrieval_trace = result.context_debug.get("retrieval_trace", {})
    graphrag = retrieval_trace.get("graphrag", {})
    assert graphrag.get("enabled") is False
    assert int(retrieval_trace.get("graphrag_expansion_count") or 0) == 0


def test_rag_pipeline_full_stack_request_does_not_override_runtime_disable_flags(monkeypatch):
    monkeypatch.setattr(settings, "rag_external_connectors_enabled", False)
    monkeypatch.setattr(settings, "rag_graphrag_enabled", False)

    pipe = RagPipelineP0(deepseek_api_key="")
    result = pipe.run(
        "warfarin ibuprofen interaction",
        planner_hints={"retrieval_stack_mode": "full"},
        scientific_retrieval_enabled=True,
        web_retrieval_enabled=True,
        deepseek_fallback_enabled=True,
    )

    retrieval_trace = result.context_debug.get("retrieval_trace", {})
    assert retrieval_trace.get("stack_mode_requested") == "full"
    assert retrieval_trace.get("graphrag_enabled") is False
    assert retrieval_trace.get("runtime_flags", {}).get("rag_graphrag_enabled") is False
    assert retrieval_trace.get("external_attempted") is False


def test_deep_scientific_plan_runs_external_connectors_after_persistent_candidates(
    monkeypatch,
):
    class _ScientificRetriever:
        def __init__(self) -> None:
            self.calls = 0
            self.last_trace: dict = {}

        def retrieve(self, query: str, **kwargs) -> list[Document]:
            self.calls += 1
            self.last_trace = {
                "search_phase": {
                    "total_candidates": 1,
                    "connectors_attempted": [
                        {"provider": "pubmed", "status": "completed", "result_count": 1}
                    ],
                    "source_errors": {},
                },
                "index_phase": {"selected_count": 1},
            }
            return [
                Document(
                    id="pubmed-32970396",
                    text="DAPA-CKD primary trial abstract and kidney outcome.",
                    metadata={"source": "pubmed", "pmid": "32970396", "score": 0.9},
                )
            ]

    retriever = _ScientificRetriever()
    pipe = RagPipelineP0(retriever=retriever, deepseek_api_key="")
    monkeypatch.setattr(settings, "rag_external_connectors_enabled", True)
    monkeypatch.setattr(pipe, "_persistent_retrieval_active", lambda: True)
    monkeypatch.setattr(
        pipe,
        "_persistent_retrieve",
        lambda *args, **kwargs: [
            Document(
                id="persistent-openfda",
                text="Unrelated indexed medicine context.",
                metadata={"source": "openfda", "score": 0.7},
            )
        ],
    )

    result = pipe.run(
        "Compare DAPA-CKD and EMPA-KIDNEY",
        planner_hints={
            "research_mode": "deep",
            "query_plan": {
                "original_query": "Compare DAPA-CKD and EMPA-KIDNEY",
                "canonical_query": "DAPA-CKD EMPA-KIDNEY",
                "source_queries": {
                    "internal": ["DAPA-CKD EMPA-KIDNEY"],
                    "scientific": ["DAPA-CKD EMPA-KIDNEY"],
                    "web": ["DAPA-CKD EMPA-KIDNEY"],
                },
                "provider_queries": {
                    "scientific": {
                        "pubmed": '("DAPA-CKD"[Title/Abstract] OR "EMPA-KIDNEY"[Title/Abstract])'
                    }
                },
                "decomposition": {},
            },
        },
        scientific_retrieval_enabled=True,
        web_retrieval_enabled=False,
        deepseek_fallback_enabled=True,
    )

    trace = result.context_debug["retrieval_trace"]
    assert retriever.calls == 1
    assert trace["retrieval_path"] == "persistent"
    assert trace["deep_scientific_plan"] is True
    assert trace["external_attempted"] is True
    assert result.retrieved_ids == ["pubmed-32970396"]
