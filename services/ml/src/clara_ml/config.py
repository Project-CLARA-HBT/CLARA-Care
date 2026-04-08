from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "clara-ml"
    environment: str = "development"
    default_embedder: str = "bge-m3"
    embedding_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "EMBEDDING_API_KEY",
            "RAG_EMBEDDING_API_KEY",
            "YESCALE_API_KEY",
        ),
    )
    embedding_base_url: str = Field(
        default="https://api.yescale.io/v1",
        validation_alias=AliasChoices("EMBEDDING_BASE_URL", "RAG_EMBEDDING_BASE_URL"),
    )
    embedding_model: str = Field(
        default="text-embedding-3-large",
        validation_alias=AliasChoices("EMBEDDING_MODEL", "RAG_EMBEDDING_MODEL"),
    )
    embedding_timeout_seconds: float = Field(
        default=6.0,
        validation_alias=AliasChoices(
            "EMBEDDING_TIMEOUT_SECONDS",
            "RAG_EMBEDDING_TIMEOUT_SECONDS",
        ),
    )
    deepseek_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "DEEPSEEK_API_KEY",
            "YESCALE_API_KEY",
            "EMBEDDING_API_KEY",
        ),
    )
    primary_llm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "PRIMARY_LLM_API_KEY",
            "HITECHCLOUD_API_KEY",
        ),
    )
    primary_llm_base_url: str = Field(
        default="https://platform.hitechcloud.one/v1",
        validation_alias=AliasChoices(
            "PRIMARY_LLM_BASE_URL",
            "HITECHCLOUD_BASE_URL",
        ),
    )
    primary_llm_model: str = Field(
        default="gpt-5.3-codex-high",
        validation_alias=AliasChoices(
            "PRIMARY_LLM_MODEL",
            "HITECHCLOUD_MODEL",
        ),
    )
    llm_deepseek_only: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "LLM_DEEPSEEK_ONLY",
            "DISABLE_PRIMARY_LLM",
        ),
    )
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        validation_alias="DEEPSEEK_BASE_URL",
    )
    deepseek_model: str = Field(default="deepseek-v3.2", validation_alias="DEEPSEEK_MODEL")
    deepseek_required: bool = Field(
        default=False,
        validation_alias="DEEPSEEK_REQUIRED",
    )
    deepseek_timeout_seconds: float = Field(
        default=45.0,
        validation_alias=AliasChoices("DEEPSEEK_TIMEOUT_SECONDS", "DEEPSEEK_TIMEOUT"),
    )
    llm_global_max_concurrency: int = Field(
        default=2,
        validation_alias=AliasChoices(
            "LLM_GLOBAL_MAX_CONCURRENCY",
            "DEEPSEEK_MAX_CONCURRENCY",
        ),
        ge=1,
        le=16,
    )
    llm_global_min_interval_seconds: float = Field(
        default=0.4,
        validation_alias=AliasChoices(
            "LLM_GLOBAL_MIN_INTERVAL_SECONDS",
            "DEEPSEEK_MIN_INTERVAL_SECONDS",
        ),
        ge=0.0,
        le=10.0,
    )
    llm_global_jitter_seconds: float = Field(
        default=0.15,
        validation_alias=AliasChoices(
            "LLM_GLOBAL_JITTER_SECONDS",
            "DEEPSEEK_JITTER_SECONDS",
        ),
        ge=0.0,
        le=5.0,
    )
    deep_beta_pass_cap: int = Field(
        default=24,
        validation_alias="DEEP_BETA_PASS_CAP",
        ge=6,
        le=64,
    )
    deep_beta_reasoning_llm_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "DEEP_BETA_REASONING_LLM_ENABLED",
            "DEEP_BETA_LLM_REASONING_ENABLED",
        ),
    )
    deep_beta_reasoning_llm_nodes: int = Field(
        default=8,
        validation_alias="DEEP_BETA_REASONING_LLM_NODES",
        ge=2,
        le=16,
    )
    deep_beta_reasoning_llm_timeout_seconds: float = Field(
        default=20.0,
        validation_alias=AliasChoices(
            "DEEP_BETA_REASONING_LLM_TIMEOUT_SECONDS",
            "DEEP_BETA_LLM_REASONING_TIMEOUT_SECONDS",
        ),
        ge=2.0,
        le=120.0,
    )
    deep_beta_reasoning_parallel_workers: int = Field(
        default=6,
        validation_alias="DEEP_BETA_REASONING_PARALLEL_WORKERS",
        ge=1,
        le=8,
    )
    deep_beta_reasoning_rounds: int = Field(
        default=3,
        validation_alias="DEEP_BETA_REASONING_ROUNDS",
        ge=1,
        le=4,
    )
    deep_beta_gap_fill_max_passes: int = Field(
        default=4,
        validation_alias="DEEP_BETA_GAP_FILL_MAX_PASSES",
        ge=0,
        le=8,
    )
    deep_beta_gap_fill_max_queries: int = Field(
        default=12,
        validation_alias="DEEP_BETA_GAP_FILL_MAX_QUERIES",
        ge=1,
        le=24,
    )
    deep_beta_report_llm_enabled: bool = Field(
        default=True,
        validation_alias="DEEP_BETA_REPORT_LLM_ENABLED",
    )
    deep_beta_report_min_words: int = Field(
        default=4200,
        validation_alias=AliasChoices(
            "DEEP_BETA_REPORT_MIN_WORDS",
            "DEEP_BETA_REPORT_MIN_CHARS",
        ),
        ge=900,
        le=12000,
    )
    deep_beta_report_target_pages: int = Field(
        default=10,
        validation_alias="DEEP_BETA_REPORT_TARGET_PAGES",
        ge=3,
        le=12,
    )
    deep_beta_report_words_per_page: int = Field(
        default=420,
        validation_alias="DEEP_BETA_REPORT_WORDS_PER_PAGE",
        ge=250,
        le=700,
    )
    deep_beta_report_expansion_rounds: int = Field(
        default=4,
        validation_alias="DEEP_BETA_REPORT_EXPANSION_ROUNDS",
        ge=0,
        le=5,
    )
    deep_beta_report_timeout_seconds: float = Field(
        default=120.0,
        validation_alias="DEEP_BETA_REPORT_TIMEOUT_SECONDS",
        ge=20.0,
        le=240.0,
    )
    deep_beta_report_max_tokens: int = Field(
        default=8192,
        validation_alias="DEEP_BETA_REPORT_MAX_TOKENS",
        ge=1024,
        le=32768,
    )
    deep_beta_quality_gate_enabled: bool = Field(
        default=True,
        validation_alias="DEEP_BETA_QUALITY_GATE_ENABLED",
    )
    deep_beta_quality_gate_timeout_seconds: float = Field(
        default=18.0,
        validation_alias="DEEP_BETA_QUALITY_GATE_TIMEOUT_SECONDS",
        ge=2.0,
        le=120.0,
    )
    deep_beta_evidence_verification_enabled: bool = Field(
        default=True,
        validation_alias="DEEP_BETA_EVIDENCE_VERIFICATION_ENABLED",
    )
    deep_beta_evidence_verification_timeout_seconds: float = Field(
        default=22.0,
        validation_alias="DEEP_BETA_EVIDENCE_VERIFICATION_TIMEOUT_SECONDS",
        ge=2.0,
        le=120.0,
    )
    deepseek_retries_per_base: int = Field(
        default=1,
        validation_alias="DEEPSEEK_RETRIES_PER_BASE",
        ge=0,
        le=5,
    )
    deepseek_retry_backoff_seconds: float = Field(
        default=0.9,
        validation_alias="DEEPSEEK_RETRY_BACKOFF_SECONDS",
        ge=0.0,
        le=5.0,
    )
    deepseek_audio_model: str = Field(
        default="whisper-1",
        validation_alias=AliasChoices(
            "DEEPSEEK_AUDIO_MODEL",
            "DEEPSEEK_TRANSCRIBE_MODEL",
            "DEEPSEEK_AUDIO_TRANSCRIPTION_MODEL",
        ),
    )
    deepseek_audio_language: str = Field(
        default="vi",
        validation_alias=AliasChoices("DEEPSEEK_AUDIO_LANGUAGE", "DEEPSEEK_TRANSCRIBE_LANGUAGE"),
    )
    ml_internal_api_key: str = Field(
        default="",
        validation_alias="ML_INTERNAL_API_KEY",
    )
    external_ddi_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("EXTERNAL_DDI_ENABLED", "CAREGUARD_EXTERNAL_DDI_ENABLED"),
    )
    external_ddi_timeout_seconds: float = Field(
        default=1.5,
        validation_alias=AliasChoices(
            "EXTERNAL_DDI_TIMEOUT_SECONDS", "CAREGUARD_EXTERNAL_DDI_TIMEOUT_SECONDS"
        ),
    )
    pubmed_connector_timeout_seconds: float = Field(
        default=4.0,
        validation_alias=AliasChoices(
            "PUBMED_CONNECTOR_TIMEOUT_SECONDS", "RAG_EXTERNAL_TIMEOUT_SECONDS"
        ),
    )
    pubmed_esearch_max_results: int = Field(
        default=3,
        validation_alias="PUBMED_ESEARCH_MAX_RESULTS",
        ge=1,
        le=10,
    )
    europe_pmc_max_results: int = Field(
        default=3,
        validation_alias="EUROPE_PMC_MAX_RESULTS",
        ge=1,
        le=10,
    )
    rag_external_connectors_enabled: bool = Field(
        default=True,
        validation_alias="RAG_EXTERNAL_CONNECTORS_ENABLED",
    )
    rag_external_parallel_workers: int = Field(
        default=3,
        validation_alias=AliasChoices(
            "RAG_EXTERNAL_PARALLEL_WORKERS",
            "RAG_EXTERNAL_MAX_PARALLEL",
        ),
        ge=1,
        le=16,
    )
    rag_external_min_interval_seconds: float = Field(
        default=0.2,
        validation_alias=AliasChoices(
            "RAG_EXTERNAL_MIN_INTERVAL_SECONDS",
            "RAG_EXTERNAL_THROTTLE_SECONDS",
        ),
        ge=0.0,
        le=5.0,
    )
    rag_external_jitter_seconds: float = Field(
        default=0.1,
        validation_alias=AliasChoices(
            "RAG_EXTERNAL_JITTER_SECONDS",
            "RAG_EXTERNAL_THROTTLE_JITTER_SECONDS",
        ),
        ge=0.0,
        le=2.0,
    )
    research_inter_step_pause_seconds: float = Field(
        default=0.35,
        validation_alias=AliasChoices(
            "RESEARCH_INTER_STEP_PAUSE_SECONDS",
            "RESEARCH_STAGE_PAUSE_SECONDS",
        ),
        ge=0.0,
        le=10.0,
    )
    research_inter_step_jitter_seconds: float = Field(
        default=0.15,
        validation_alias=AliasChoices(
            "RESEARCH_INTER_STEP_JITTER_SECONDS",
            "RESEARCH_STAGE_PAUSE_JITTER_SECONDS",
        ),
        ge=0.0,
        le=3.0,
    )
    rag_graphrag_enabled: bool = Field(
        default=False,
        validation_alias="RAG_GRAPHRAG_ENABLED",
    )
    rag_graphrag_max_neighbors: int = Field(
        default=8,
        validation_alias="RAG_GRAPHRAG_MAX_NEIGHBORS",
        ge=1,
        le=32,
    )
    rag_graphrag_expansion_docs: int = Field(
        default=4,
        validation_alias="RAG_GRAPHRAG_EXPANSION_DOCS",
        ge=1,
        le=16,
    )
    rag_biomed_graph_enabled: bool = Field(
        default=True,
        validation_alias="RAG_BIOMED_GRAPH_ENABLED",
    )
    rag_biomed_graph_path: str = Field(
        default="",
        validation_alias="RAG_BIOMED_GRAPH_PATH",
    )
    rag_biomed_graph_max_edges: int = Field(
        default=12,
        validation_alias="RAG_BIOMED_GRAPH_MAX_EDGES",
        ge=1,
        le=64,
    )
    rag_force_search_index: bool = Field(
        default=True,
        validation_alias="RAG_FORCE_SEARCH_INDEX",
    )
    searxng_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("SEARXNG_BASE_URL", "SEARXNG_PUBLIC_BASE_URL"),
    )
    searxng_timeout_seconds: float = Field(
        default=3.0,
        validation_alias="SEARXNG_TIMEOUT_SECONDS",
    )
    searxng_crawl_enabled: bool = Field(
        default=True,
        validation_alias="SEARXNG_CRAWL_ENABLED",
    )
    searxng_crawl_top_k: int = Field(
        default=2,
        validation_alias="SEARXNG_CRAWL_TOP_K",
        ge=0,
        le=8,
    )
    searxng_crawl_timeout_seconds: float = Field(
        default=2.0,
        validation_alias="SEARXNG_CRAWL_TIMEOUT_SECONDS",
    )
    searxng_crawl_allowed_domains: str = Field(
        default=(
            "who.int,nih.gov,ncbi.nlm.nih.gov,pubmed.ncbi.nlm.nih.gov,"
            "open.fda.gov,fda.gov,dailymed.nlm.nih.gov,"
            "clinicaltrials.gov,ema.europa.eu,bmj.com,thelancet.com"
        ),
        validation_alias="SEARXNG_CRAWL_ALLOWED_DOMAINS",
    )
    semantic_scholar_timeout_seconds: float = Field(
        default=3.0,
        validation_alias="SEMANTIC_SCHOLAR_TIMEOUT_SECONDS",
    )
    semantic_scholar_api_key: str = Field(
        default="",
        validation_alias="SEMANTIC_SCHOLAR_API_KEY",
    )
    semantic_scholar_max_results: int = Field(
        default=3,
        validation_alias="SEMANTIC_SCHOLAR_MAX_RESULTS",
        ge=1,
        le=20,
    )
    web_crawl_enabled: bool = Field(
        default=True,
        validation_alias="WEB_CRAWL_ENABLED",
    )
    web_crawl_timeout_seconds: float = Field(
        default=1.5,
        validation_alias="WEB_CRAWL_TIMEOUT_SECONDS",
    )
    web_crawl_max_pages: int = Field(
        default=3,
        validation_alias="WEB_CRAWL_MAX_PAGES",
        ge=1,
        le=10,
    )
    web_crawl_max_chars: int = Field(
        default=1200,
        validation_alias="WEB_CRAWL_MAX_CHARS",
        ge=300,
        le=8000,
    )
    web_crawl_allowed_domains: str = Field(
        default=(
            "who.int,nih.gov,ncbi.nlm.nih.gov,pubmed.ncbi.nlm.nih.gov,"
            "open.fda.gov,fda.gov,dailymed.nlm.nih.gov,"
            "clinicaltrials.gov,ema.europa.eu,bmj.com,thelancet.com"
        ),
        validation_alias="WEB_CRAWL_ALLOWED_DOMAINS",
    )
    evidence_search_enforced: bool = Field(
        default=True,
        validation_alias="EVIDENCE_SEARCH_ENFORCED",
    )
    otel_export_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("OTEL_EXPORT_ENABLED", "CLARA_OTEL_EXPORT_ENABLED"),
    )
    otel_export_endpoint: str = Field(
        default="",
        validation_alias=AliasChoices(
            "OTEL_EXPORT_ENDPOINT",
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "CLARA_OTEL_EXPORT_ENDPOINT",
        ),
    )
    otel_export_timeout_seconds: float = Field(
        default=1.5,
        validation_alias=AliasChoices(
            "OTEL_EXPORT_TIMEOUT_SECONDS",
            "CLARA_OTEL_EXPORT_TIMEOUT_SECONDS",
        ),
        ge=0.1,
        le=10.0,
    )
    rag_biomedical_rerank_enabled: bool = Field(
        default=False,
        validation_alias="RAG_BIOMEDICAL_RERANK_ENABLED",
    )
    rag_reranker_enabled: bool = Field(
        default=False,
        validation_alias="RAG_RERANKER_ENABLED",
    )
    rag_reranker_strategy: str = Field(
        default="embedding",
        validation_alias="RAG_RERANKER_STRATEGY",
    )
    rag_reranker_model: str = Field(
        default="embedding-cosine-reranker-v1",
        validation_alias="RAG_RERANKER_MODEL",
    )
    rag_reranker_top_n: int = Field(
        default=12,
        validation_alias="RAG_RERANKER_TOP_N",
        ge=1,
        le=128,
    )
    rag_reranker_timeout_ms: int = Field(
        default=250,
        validation_alias="RAG_RERANKER_TIMEOUT_MS",
        ge=50,
        le=30000,
    )
    rag_reranker_llm_enabled: bool = Field(
        default=False,
        validation_alias="RAG_RERANKER_LLM_ENABLED",
    )
    rag_reranker_llm_top_n: int = Field(
        default=6,
        validation_alias="RAG_RERANKER_LLM_TOP_N",
        ge=1,
        le=24,
    )
    rag_reranker_llm_timeout_ms: int = Field(
        default=900,
        validation_alias="RAG_RERANKER_LLM_TIMEOUT_MS",
        ge=100,
        le=30000,
    )
    rag_reranker_cache_enabled: bool = Field(
        default=True,
        validation_alias="RAG_RERANKER_CACHE_ENABLED",
    )
    rag_reranker_cache_ttl_seconds: int = Field(
        default=180,
        validation_alias="RAG_RERANKER_CACHE_TTL_SECONDS",
        ge=1,
        le=3600,
    )
    rag_reranker_cache_max_entries: int = Field(
        default=512,
        validation_alias="RAG_RERANKER_CACHE_MAX_ENTRIES",
        ge=32,
        le=10000,
    )
    rule_verification_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "RULE_VERIFICATION_ENABLED",
            "RAG_RULE_VERIFICATION_ENABLED",
            "VERIFICATION_ENABLED",
        ),
    )
    rag_nli_enabled: bool = Field(
        default=True,
        validation_alias="RAG_NLI_ENABLED",
    )
    rag_nli_strategy: str = Field(
        default="heuristic",
        validation_alias="RAG_NLI_STRATEGY",
    )
    rag_nli_timeout_ms: int = Field(
        default=180,
        validation_alias="RAG_NLI_TIMEOUT_MS",
        ge=50,
        le=30000,
    )
    rag_nli_llm_enabled: bool = Field(
        default=False,
        validation_alias="RAG_NLI_LLM_ENABLED",
    )
    rag_nli_llm_timeout_ms: int = Field(
        default=900,
        validation_alias="RAG_NLI_LLM_TIMEOUT_MS",
        ge=100,
        le=30000,
    )
    rag_nli_min_confidence: float = Field(
        default=0.35,
        validation_alias="RAG_NLI_MIN_CONFIDENCE",
        ge=0.0,
        le=1.0,
    )
    rag_biomedical_rerank_alpha: float = Field(
        default=0.28,
        validation_alias="RAG_BIOMEDICAL_RERANK_ALPHA",
        ge=0.0,
        le=1.0,
    )
    rag_biomedical_rerank_top_n: int = Field(
        default=8,
        validation_alias="RAG_BIOMEDICAL_RERANK_TOP_N",
        ge=0,
        le=64,
    )
    council_neural_enabled: bool = Field(
        default=False,
        validation_alias="COUNCIL_NEURAL_ENABLED",
    )
    council_neural_shadow_mode: bool = Field(
        default=True,
        validation_alias="COUNCIL_NEURAL_SHADOW_MODE",
    )
    council_neural_medium_threshold: float = Field(
        default=0.45,
        validation_alias="COUNCIL_NEURAL_MEDIUM_THRESHOLD",
        ge=0.0,
        le=1.0,
    )
    council_neural_high_threshold: float = Field(
        default=0.72,
        validation_alias="COUNCIL_NEURAL_HIGH_THRESHOLD",
        ge=0.0,
        le=1.0,
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
